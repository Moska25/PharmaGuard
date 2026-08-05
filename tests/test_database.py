"""
Database tests.

Everything here runs against a throwaway SQLite file, so the suite never touches
a real installation and never needs a committed database.
"""

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from auth_manager import AuthManager
from medication import Medication


def make_medication(**overrides) -> Medication:
    defaults = {
        "patient_name": "Ana Beridze",
        "medicine_name": "Metformin",
        "dosage": "500 mg",
        "medication_date": date.today().isoformat(),
        "medicine_time": "08:00",
        "taking_rule": "After food",
    }
    defaults.update(overrides)
    return Medication(**defaults)


class TestSchema:
    def test_all_tables_are_created_on_first_open(self, database):
        with database._connection() as connection:
            names = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        assert {"users", "medications", "patient_medical_history", "settings", "audit_log"} <= names

    def test_opening_an_existing_database_is_idempotent(self, tmp_path):
        from database import DatabaseManager

        path = str(tmp_path / "twice.db")
        DatabaseManager(path).create_user("Ana", "Beridze", "hash")
        # Re-opening must not wipe or duplicate anything.
        assert len(DatabaseManager(path).list_users()) == 1


class TestUsers:
    def test_username_is_generated_from_the_name(self, database):
        user = database.create_user("Ana", "Beridze", "hash")
        assert user.username == "anaberidze0001"

    def test_duplicate_names_get_distinct_usernames(self, database):
        first = database.create_user("Ana", "Beridze", "hash")
        second = database.create_user("Ana", "Beridze", "hash")
        third = database.create_user("Ana", "Beridze", "hash")
        assert [first.username, second.username, third.username] == [
            "anaberidze0001",
            "anaberidze0002",
            "anaberidze0003",
        ]

    def test_non_alphanumeric_characters_are_stripped(self, database):
        user = database.create_user("Ana-Maria", "O'Beridze Jr.", "hash")
        assert user.username == "anamariaoberidzejr0001"

    def test_names_with_no_usable_characters_fall_back(self, database):
        user = database.create_user("...", "!!!", "hash")
        assert user.username == "patient0001"

    def test_lookup_by_username_is_whitespace_tolerant(self, database):
        user = database.create_user("Ana", "Beridze", "hash")
        assert database.get_user_by_username("  anaberidze0001  ").user_id == user.user_id

    def test_new_accounts_are_active(self, database):
        assert database.create_user("Ana", "Beridze", "hash").is_active == 1

    def test_deactivating_and_reactivating(self, database):
        user = database.create_user("Ana", "Beridze", "hash")
        database.update_user_active_status(user.user_id, False)
        assert database.get_user_by_id(user.user_id).is_active == 0
        database.update_user_active_status(user.user_id, True)
        assert database.get_user_by_id(user.user_id).is_active == 1

    def test_search_matches_first_last_full_name_and_username(self, database):
        database.create_user("Ana", "Beridze", "hash")
        database.create_user("Luka", "Tsiklauri", "hash")
        assert len(database.list_users("Ana")) == 1
        assert len(database.list_users("Tsiklauri")) == 1
        assert len(database.list_users("Ana Beridze")) == 1
        assert len(database.list_users("lukatsiklauri")) == 1
        assert len(database.list_users("nobody")) == 0

    def test_active_filter(self, database):
        active = database.create_user("Ana", "Beridze", "hash")
        inactive = database.create_user("Luka", "Tsiklauri", "hash")
        database.update_user_active_status(inactive.user_id, False)
        assert [u.user_id for u in database.list_users(active_filter="active")] == [active.user_id]
        assert [u.user_id for u in database.list_users(active_filter="inactive")] == [inactive.user_id]

    def test_password_update_is_persisted(self, database):
        user = database.create_user("Ana", "Beridze", "old")
        database.update_user_password(user.user_id, AuthManager.hash_password("New!Pass1"))
        assert AuthManager.verify_password(
            "New!Pass1", database.get_user_by_id(user.user_id).password
        )


class TestMedications:
    def test_add_then_read_back(self, database):
        medication_id = database.add_medication(make_medication())
        stored = database.get_medication_by_id(medication_id)
        assert stored.medicine_name == "Metformin"
        assert stored.status == Medication.NOT_TAKEN

    def test_update_changes_editable_fields(self, database):
        medication_id = database.add_medication(make_medication())
        stored = database.get_medication_by_id(medication_id)
        stored.dosage = "1000 mg"
        stored.medicine_time = "09:30"
        database.update_medication(stored)
        reloaded = database.get_medication_by_id(medication_id)
        assert (reloaded.dosage, reloaded.medicine_time) == ("1000 mg", "09:30")

    def test_delete_removes_the_record(self, database):
        medication_id = database.add_medication(make_medication())
        database.delete_medication(medication_id)
        assert database.get_medication_by_id(medication_id) is None

    def test_status_update(self, database):
        medication_id = database.add_medication(make_medication())
        database.update_medication_status(medication_id, Medication.TAKEN)
        assert database.get_medication_by_id(medication_id).status == Medication.TAKEN

    def test_notification_flags_are_set_individually(self, database):
        medication_id = database.add_medication(make_medication())
        database.mark_notification_sent(medication_id, "notified_10min_before")
        stored = database.get_medication_by_id(medication_id)
        assert stored.notified_10min_before == 1
        assert stored.notified_exact_time == 0

    def test_unknown_notification_flag_is_rejected(self, database):
        """Flag names are interpolated into SQL, so only the allow-list may pass."""
        medication_id = database.add_medication(make_medication())
        with pytest.raises(ValueError):
            database.mark_notification_sent(medication_id, "status = 'Taken' --")

    def test_filter_by_date(self, database):
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        database.add_medication(make_medication(medication_date=today))
        database.add_medication(make_medication(medication_date=tomorrow))
        assert len(database.load_medications_by_date(today)) == 1

    def test_filter_by_patient(self, database):
        first = database.create_user("Ana", "Beridze", "hash")
        second = database.create_user("Luka", "Tsiklauri", "hash")
        database.add_medication(make_medication(patient_id=first.user_id))
        database.add_medication(make_medication(patient_id=second.user_id))
        assert len(database.load_all_medications(patient_id=first.user_id)) == 1
        assert len(database.load_all_medications()) == 2

    def test_date_range_is_inclusive_at_both_ends(self, database):
        base = date.today()
        for offset in range(4):
            database.add_medication(
                make_medication(medication_date=(base + timedelta(days=offset)).isoformat())
            )
        found = database.load_medications_for_range(
            base.isoformat(), (base + timedelta(days=2)).isoformat()
        )
        assert len(found) == 3

    def test_dates_with_medications_is_deduplicated(self, database):
        today = date.today().isoformat()
        database.add_medication(make_medication(medication_date=today))
        database.add_medication(make_medication(medication_date=today, medicine_time="20:00"))
        assert database.get_dates_with_medications() == {today}

    def test_scheduler_query_ignores_taken_and_future_doses(self, database):
        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()
        database.add_medication(make_medication(medication_date=yesterday))
        database.add_medication(make_medication(medication_date=today.isoformat()))
        database.add_medication(make_medication(medication_date=tomorrow))
        taken = database.add_medication(make_medication(medication_date=today.isoformat()))
        database.update_medication_status(taken, Medication.TAKEN)

        pending = database.get_pending_medications_for_scheduler(today.isoformat())
        assert len(pending) == 2
        assert all(item.status == Medication.NOT_TAKEN for item in pending)


class TestCopyDay:
    def test_copies_every_record_to_the_target_date(self, database):
        source = date.today().isoformat()
        target = (date.today() + timedelta(days=1)).isoformat()
        database.add_medication(make_medication(medication_date=source))
        database.add_medication(make_medication(medication_date=source, medicine_time="20:00"))

        assert database.copy_day(source, target) == 2
        assert len(database.load_medications_by_date(target)) == 2

    def test_copied_records_are_reset_to_not_taken(self, database):
        source = date.today().isoformat()
        target = (date.today() + timedelta(days=1)).isoformat()
        medication_id = database.add_medication(make_medication(medication_date=source))
        database.update_medication_status(medication_id, Medication.TAKEN)
        database.mark_notification_sent(medication_id, "notified_exact_time")

        database.copy_day(source, target)
        copied = database.load_medications_by_date(target)[0]
        assert copied.status == Medication.NOT_TAKEN
        assert copied.notified_exact_time == 0

    def test_copying_an_empty_day_is_a_no_op(self, database):
        assert database.copy_day("2020-01-01", "2020-01-02") == 0


class TestStatistics:
    def test_counts_split_by_status(self, database):
        today = date.today().isoformat()
        taken = database.add_medication(make_medication(medication_date=today))
        database.update_medication_status(taken, Medication.TAKEN)
        database.add_medication(make_medication(medication_date=today, medicine_time="23:59"))

        stats = database.get_statistics_for_date(today)
        assert stats["total"] == 2
        assert stats["taken"] == 1
        assert stats["not_taken"] == 1

    def test_overdue_counts_only_past_untaken_doses(self, database):
        today = date.today().isoformat()
        database.add_medication(make_medication(medication_date=today, medicine_time="00:01"))
        database.add_medication(make_medication(medication_date=today, medicine_time="23:59"))
        # 00:01 is in the past for any run after one minute past midnight.
        assert database.get_statistics_for_date(today)["overdue"] >= 1

    def test_empty_day_returns_zeros(self, database):
        assert database.get_statistics_for_date("2020-01-01") == {
            "total": 0,
            "taken": 0,
            "not_taken": 0,
            "overdue": 0,
        }


class TestMedicalHistory:
    def test_add_and_read_back(self, database, patient):
        database.add_medical_history(patient.user_id, {"diagnosis": "Type 2 diabetes"})
        records = database.get_medical_history_by_patient(patient.user_id)
        assert len(records) == 1
        assert records[0]["diagnosis"] == "Type 2 diabetes"

    def test_diagnosis_is_required(self, database, patient):
        with pytest.raises(ValueError):
            database.add_medical_history(patient.user_id, {"diagnosis": "   "})

    def test_patient_is_required(self, database):
        with pytest.raises(ValueError):
            database.add_medical_history(None, {"diagnosis": "Something"})

    def test_delete(self, database, patient):
        history_id = database.add_medical_history(patient.user_id, {"diagnosis": "Migraine"})
        database.delete_medical_history(history_id)
        assert database.get_medical_history_by_patient(patient.user_id) == []


class TestSettingsAndAudit:
    def test_setting_round_trip(self, database):
        database.set_setting("theme", "dark")
        assert database.get_setting("theme") == "dark"

    def test_missing_setting_returns_the_default(self, database):
        assert database.get_setting("nope", "fallback") == "fallback"

    def test_setting_is_overwritten_not_duplicated(self, database):
        database.set_setting("theme", "dark")
        database.set_setting("theme", "light")
        assert database.get_setting("theme") == "light"

    def test_audit_entries_are_recorded(self, database):
        database.add_audit_log("Login success", "Username: anaberidze0001", actor_role="user")
        logs = database.get_audit_logs()
        assert len(logs) == 1
        assert logs[0]["action"] == "Login success"


class TestAuditLogTimezone:
    """
    created_at is stored in UTC; every date the UI filters by is local.

    Anywhere off UTC that gap swallows entries. West of UTC an action taken at
    21:00 local carries tomorrow's UTC date, so an audit search ending "today"
    returned nothing; east of UTC the same happens to the early hours against a
    search starting "today". An audit trail that hides entries without saying
    so is worse than no audit trail, hence the explicit cover.
    """

    @staticmethod
    def _write_at(database, utc_timestamp: str) -> None:
        """Insert one entry with a chosen UTC created_at, bypassing the default."""
        with sqlite3.connect(database.db_path) as connection:
            connection.execute(
                """
                INSERT INTO audit_log (actor_username, actor_role, action, details, created_at)
                VALUES ('nabashidze0001', 'user', 'Login success', 'probe', ?)
                """,
                (utc_timestamp,),
            )

    def test_an_entry_whose_utc_date_differs_from_its_local_date_is_still_found(self, database):
        """
        The regression itself, pinned deterministically.

        Using the live clock would only catch the bug during the hours when the
        two dates happen to disagree, so the timestamp is chosen from the
        machine's own offset to guarantee they disagree.
        """
        offset = datetime.now().astimezone().utcoffset()
        if offset == timedelta(0):
            pytest.skip("machine runs on UTC, so no local/UTC date gap exists to test")

        # Pick the local time that is guaranteed to land on a different UTC date
        # for this machine's offset. West of UTC (offset < 0) local runs behind,
        # so a late evening maps to the next UTC day. East of UTC it runs ahead,
        # so an early morning maps to the previous one. Either way the naive
        # comparison this replaced put the entry outside a single-day range.
        local_day = date(2026, 8, 4)
        local_moment = (
            datetime(2026, 8, 4, 0, 30) if offset > timedelta(0) else datetime(2026, 8, 4, 23, 30)
        )
        utc_moment = local_moment - offset
        assert utc_moment.date() != local_day, "timestamp must straddle the date boundary"
        self._write_at(database, utc_moment.strftime("%Y-%m-%d %H:%M:%S"))

        found = database.get_audit_logs(
            start_date=local_day.isoformat(),
            end_date=local_day.isoformat(),
        )
        assert len(found) == 1, (
            f"entry at {local_moment} local (stored {utc_moment} UTC) must fall inside "
            f"a filter for {local_day}"
        )

    def test_a_stored_utc_timestamp_is_returned_as_local_time(self, database):
        self._write_at(database, "2026-08-04 22:30:00")
        entry = database.get_audit_logs()[0]
        expected = datetime(2026, 8, 4, 22, 30, tzinfo=timezone.utc).astimezone()
        assert entry["created_at"] == expected.strftime("%Y-%m-%d %H:%M:%S")

    def test_an_entry_outside_the_range_is_still_excluded(self, database):
        self._write_at(database, "2020-01-01 12:00:00")
        assert database.get_audit_logs(start_date="2026-01-01", end_date="2026-12-31") == []

    def test_created_date_on_a_user_is_reported_in_local_time(self, database):
        database.create_user("Nino", "Abashidze", "hash")
        stored = sqlite3.connect(database.db_path).execute(
            "SELECT created_at FROM users"
        ).fetchone()[0]
        listed = database.list_users()[0].created_at
        expected = (
            datetime.strptime(stored, "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=timezone.utc)
            .astimezone()
        )
        assert listed == expected.strftime("%Y-%m-%d %H:%M:%S")
