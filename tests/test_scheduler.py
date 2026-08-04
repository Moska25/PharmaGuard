"""
Reminder scheduler tests.

These cover the behaviour that actually matters in a medication app: a reminder
must fire even when the check runs late. The scheduler previously compared
``now == scheduled_time`` exactly, so one skipped minute - laptop asleep, a busy
UI thread, an overrunning job - silently dropped that reminder forever.

Every case injects a reference time; none of them touch the wall clock.
"""

from datetime import date, datetime, timedelta

import pytest

from medication import Medication
from scheduler import ReminderScheduler

TODAY = date.today()
DOSE_TIME = "12:00"
SCHEDULED = datetime.combine(TODAY, datetime.min.time()).replace(hour=12)


@pytest.fixture
def scheduler(database):
    """A scheduler wired to a temp database, recording emitted events."""
    instance = ReminderScheduler(database)
    events = []
    instance.reminder_due.connect(lambda event, medication: events.append((event, medication)))
    instance.events = events
    return instance


@pytest.fixture
def dose(database):
    medication_id = database.add_medication(
        Medication(
            patient_name="Ana Beridze",
            medicine_name="Metformin",
            dosage="500 mg",
            medication_date=TODAY.isoformat(),
            medicine_time=DOSE_TIME,
            taking_rule="After food",
        )
    )
    return medication_id


def test_nothing_fires_long_before_the_dose(scheduler, dose):
    scheduler.check_medication_times(SCHEDULED - timedelta(hours=2))
    assert scheduler.events == []


def test_ten_minute_warning_fires_in_its_window(scheduler, dose):
    scheduler.check_medication_times(SCHEDULED - timedelta(minutes=10))
    assert [event for event, _ in scheduler.events] == [ReminderScheduler.EVENT_TEN_MINUTES]


def test_ten_minute_warning_still_fires_when_the_check_runs_late(scheduler, dose):
    """The regression that motivated the rewrite: a late check must not go silent."""
    scheduler.check_medication_times(SCHEDULED - timedelta(minutes=4))
    assert [event for event, _ in scheduler.events] == [ReminderScheduler.EVENT_TEN_MINUTES]


def test_exact_time_event_fires_at_the_dose_minute(scheduler, dose):
    scheduler.check_medication_times(SCHEDULED)
    assert [event for event, _ in scheduler.events] == [ReminderScheduler.EVENT_EXACT_TIME]


def test_missed_event_fires_once_the_grace_period_passes(scheduler, dose):
    scheduler.check_medication_times(SCHEDULED + timedelta(minutes=1))
    assert [event for event, _ in scheduler.events] == [ReminderScheduler.EVENT_MISSED]


def test_hours_late_still_reports_missed(scheduler, dose):
    scheduler.check_medication_times(SCHEDULED + timedelta(hours=6))
    assert [event for event, _ in scheduler.events] == [ReminderScheduler.EVENT_MISSED]


def test_each_event_fires_at_most_once(scheduler, dose):
    scheduler.check_medication_times(SCHEDULED - timedelta(minutes=10))
    scheduler.check_medication_times(SCHEDULED - timedelta(minutes=9))
    scheduler.check_medication_times(SCHEDULED - timedelta(minutes=8))
    assert len(scheduler.events) == 1


def test_full_lifecycle_emits_each_event_exactly_once(scheduler, dose):
    for offset in range(-15, 5):
        scheduler.check_medication_times(SCHEDULED + timedelta(minutes=offset))
    assert [event for event, _ in scheduler.events] == [
        ReminderScheduler.EVENT_TEN_MINUTES,
        ReminderScheduler.EVENT_EXACT_TIME,
        ReminderScheduler.EVENT_MISSED,
    ]


def test_flags_are_persisted_so_a_restart_does_not_re_notify(scheduler, database, dose):
    scheduler.check_medication_times(SCHEDULED - timedelta(minutes=10))
    assert database.get_medication_by_id(dose).notified_10min_before == 1

    restarted = ReminderScheduler(database)
    fired = []
    restarted.reminder_due.connect(lambda event, medication: fired.append(event))
    restarted.check_medication_times(SCHEDULED - timedelta(minutes=9))
    assert fired == []


def test_taken_medication_never_notifies(scheduler, database, dose):
    database.update_medication_status(dose, Medication.TAKEN)
    for offset in range(-15, 5):
        scheduler.check_medication_times(SCHEDULED + timedelta(minutes=offset))
    assert scheduler.events == []


def test_scheduler_is_scoped_to_its_patient(database):
    ana = database.create_user("Ana", "Beridze", "hash")
    luka = database.create_user("Luka", "Tsiklauri", "hash")
    for user in (ana, luka):
        database.add_medication(
            Medication(
                patient_name=user.full_name,
                patient_id=user.user_id,
                medicine_name="Metformin",
                dosage="500 mg",
                medication_date=TODAY.isoformat(),
                medicine_time=DOSE_TIME,
                taking_rule="After food",
            )
        )

    scoped = ReminderScheduler(database, patient_id=ana.user_id)
    fired = []
    scoped.reminder_due.connect(lambda event, medication: fired.append(medication))
    scoped.check_medication_times(SCHEDULED)
    assert len(fired) == 1
    assert fired[0].patient_id == ana.user_id
