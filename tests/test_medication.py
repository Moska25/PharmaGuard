"""
Medication model tests: date/time maths and table sorting.

All time-dependent assertions pass an explicit reference time. Nothing here may
depend on when the suite happens to run.
"""

from datetime import datetime

import pytest

from medication import Medication, sort_medications

NOON = datetime(2026, 8, 4, 12, 0)


def make(**overrides) -> Medication:
    defaults = {
        "patient_name": "Ana Beridze",
        "medicine_name": "Metformin",
        "dosage": "500 mg",
        "medication_date": "2026-08-04",
        "medicine_time": "12:00",
        "taking_rule": "After food",
    }
    defaults.update(overrides)
    return Medication(**defaults)


class TestTimeNormalisation:
    @pytest.mark.parametrize(
        "raw,expected",
        [("08:00", "08:00"), ("8", "08:00"), ("08", "08:00"), ("  09:30  ", "09:30")],
    )
    def test_normalised_forms(self, raw, expected):
        assert make(medicine_time=raw).normalized_medicine_time() == expected

    def test_bare_hour_is_parseable_rather_than_raising(self):
        """Regression: "8" used to survive unpadded and blow up strptime."""
        assert make(medicine_time="8").scheduled_datetime() == datetime(2026, 8, 4, 8, 0)

    def test_scheduled_datetime_combines_date_and_time(self):
        assert make(medicine_time="08:30").scheduled_datetime() == datetime(2026, 8, 4, 8, 30)

    def test_ten_minutes_before(self):
        assert make(medicine_time="08:30").ten_minutes_before_datetime() == datetime(2026, 8, 4, 8, 20)


class TestOverdue:
    def test_untaken_and_past_is_overdue(self):
        assert make(medicine_time="11:00").is_overdue(NOON)

    def test_untaken_and_future_is_not_overdue(self):
        assert not make(medicine_time="13:00").is_overdue(NOON)

    def test_taken_is_never_overdue(self):
        assert not make(medicine_time="06:00", status=Medication.TAKEN).is_overdue(NOON)

    def test_exactly_on_time_is_not_yet_overdue(self):
        assert not make(medicine_time="12:00").is_overdue(NOON)

    def test_minutes_late_is_zero_when_not_overdue(self):
        assert make(medicine_time="13:00").minutes_late(NOON) == 0

    def test_minutes_late_when_overdue(self):
        assert make(medicine_time="10:30").minutes_late(NOON) == 90

    def test_minutes_until_is_negative_once_past(self):
        assert make(medicine_time="11:00").minutes_until(NOON) == -60
        assert make(medicine_time="14:00").minutes_until(NOON) == 120


class TestRemainingText:
    def test_taken(self):
        assert make(status=Medication.TAKEN).remaining_time_text(NOON) == "Taken"

    def test_upcoming(self):
        assert make(medicine_time="14:30").remaining_time_text(NOON) == "2h 30m remaining"

    def test_overdue(self):
        assert make(medicine_time="09:45").remaining_time_text(NOON) == "Overdue by 2h 15m"


class TestSorting:
    @pytest.fixture
    def batch(self):
        return [
            make(medication_date="2026-08-03", medicine_name="Zinc", patient_name="Zoe Kapanadze"),
            make(medication_date="2026-08-05", medicine_name="Aspirin", patient_name="Ana Beridze"),
            make(
                medication_date="2026-08-04",
                medicine_name="Metformin",
                patient_name="Luka Tsiklauri",
                status=Medication.TAKEN,
            ),
        ]

    def test_date_newest_first(self, batch):
        assert [m.medication_date for m in sort_medications(batch, "Date newest first")] == [
            "2026-08-05",
            "2026-08-04",
            "2026-08-03",
        ]

    def test_date_oldest_first(self, batch):
        assert [m.medication_date for m in sort_medications(batch, "Date oldest first")] == [
            "2026-08-03",
            "2026-08-04",
            "2026-08-05",
        ]

    def test_patient_name_alphabetical(self, batch):
        assert [m.patient_name for m in sort_medications(batch, "Patient name A-Z")][0] == "Ana Beridze"

    def test_medicine_name_alphabetical(self, batch):
        assert [m.medicine_name for m in sort_medications(batch, "Medicine name A-Z")] == [
            "Aspirin",
            "Metformin",
            "Zinc",
        ]

    def test_taken_first(self, batch):
        assert sort_medications(batch, "Taken first")[0].status == Medication.TAKEN

    def test_not_taken_first(self, batch):
        assert sort_medications(batch, "Not Taken first")[0].status == Medication.NOT_TAKEN

    def test_unknown_option_falls_back_to_chronological(self, batch):
        assert [m.medication_date for m in sort_medications(batch, "nonsense")] == [
            "2026-08-03",
            "2026-08-04",
            "2026-08-05",
        ]

    def test_sorting_does_not_mutate_the_input(self, batch):
        before = [m.medication_date for m in batch]
        sort_medications(batch, "Date newest first")
        assert [m.medication_date for m in batch] == before

    def test_empty_list(self):
        assert sort_medications([], "Date newest first") == []
