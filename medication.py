"""
Medication model for PharmaGuard.

This class represents one medication reminder and contains small helper
methods for date/time calculations used by the GUI and scheduler.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


MEDICATION_SORT_OPTIONS = [
    "Date newest first",
    "Date oldest first",
    "Patient name A-Z",
    "Medicine name A-Z",
    "Taken first",
    "Not Taken first",
    "Overdue first",
]


@dataclass
class Medication:
    """One medication reminder record."""

    patient_name: str
    medicine_name: str
    dosage: str
    medication_date: str
    medicine_time: str
    taking_rule: str
    status: str = "Not Taken"
    category: str = ""
    warning: str = ""
    medication_id: Optional[int] = None
    patient_id: Optional[int] = None
    created_at: str = ""
    notified_10min_before: int = 0
    notified_exact_time: int = 0
    missed_notification_sent: int = 0

    TAKEN = "Taken"
    NOT_TAKEN = "Not Taken"

    @classmethod
    def from_row(cls, row) -> "Medication":
        """Create a Medication object from a sqlite3.Row."""
        return cls(
            medication_id=row["id"],
            patient_id=row["patient_id"],
            patient_name=row["patient_name"],
            medicine_name=row["medicine_name"],
            dosage=row["dosage"],
            medication_date=row["medication_date"],
            medicine_time=row["medicine_time"],
            taking_rule=row["taking_rule"],
            status=row["status"],
            category=row["category"] or "",
            warning=row["warning"] or "",
            created_at=row["created_at"] or "",
            notified_10min_before=int(row["notified_10min_before"] or 0),
            notified_exact_time=int(row["notified_exact_time"] or 0),
            missed_notification_sent=int(row["missed_notification_sent"] or 0),
        )

    def to_insert_tuple(self) -> tuple:
        """Return values in the order used by DatabaseManager.add_medication."""
        return (
            self.patient_name.strip(),
            self.patient_id,
            self.medicine_name.strip(),
            self.dosage.strip(),
            self.medication_date,
            self.medicine_time,
            self.taking_rule,
            self.status,
            self.category,
            self.warning,
            int(self.notified_10min_before),
            int(self.notified_exact_time),
            int(self.missed_notification_sent),
        )

    def to_update_tuple(self) -> tuple:
        """Return editable values in the order used by update_medication."""
        return (
            self.patient_name.strip(),
            self.patient_id,
            self.medicine_name.strip(),
            self.dosage.strip(),
            self.medication_date,
            self.medicine_time,
            self.taking_rule,
            self.status,
            self.category,
            self.warning,
            int(self.medication_id or 0),
        )

    def scheduled_datetime(self) -> datetime:
        """Return the exact scheduled date and time."""
        return datetime.strptime(
            f"{self.medication_date} {self.normalized_medicine_time()}",
            "%Y-%m-%d %H:%M",
        )

    def normalized_medicine_time(self) -> str:
        """Return time as HH:MM."""
        value = (self.medicine_time or "").strip()
        if len(value) == 2 and value.isdigit():
            return f"{value}:00"
        return value

    def is_taken(self) -> bool:
        """Return True when this medication was marked as taken."""
        return self.status == self.TAKEN

    def is_overdue(self, reference_time: Optional[datetime] = None) -> bool:
        """Return True when the reminder time passed and it is still not taken."""
        reference = reference_time or datetime.now()
        return self.status == self.NOT_TAKEN and reference > self.scheduled_datetime()

    def minutes_until(self, reference_time: Optional[datetime] = None) -> int:
        """Return whole minutes until the scheduled time."""
        reference = reference_time or datetime.now()
        return int((self.scheduled_datetime() - reference).total_seconds() // 60)

    def minutes_late(self, reference_time: Optional[datetime] = None) -> int:
        """Return whole minutes late. Returns 0 if it is not overdue."""
        if not self.is_overdue(reference_time):
            return 0
        return abs(self.minutes_until(reference_time))

    def remaining_time_text(self, reference_time: Optional[datetime] = None) -> str:
        """Build a readable remaining/overdue/taken status."""
        if self.is_taken():
            return "Taken"

        minutes = self.minutes_until(reference_time)
        absolute_minutes = abs(minutes)
        hours = absolute_minutes // 60
        mins = absolute_minutes % 60

        if minutes < 0:
            return f"Overdue by {hours}h {mins}m"
        return f"{hours}h {mins}m remaining"

    def ten_minutes_before_datetime(self) -> datetime:
        """Return the reminder time for the 10-minute warning."""
        return self.scheduled_datetime() - timedelta(minutes=10)

    def warning_message(self) -> str:
        """Return warning text for the medication."""
        return self.warning or ""


def sort_medications(medications: List[Medication], option: str) -> List[Medication]:
    """Sort medications using an option shared by tables."""
    if option == "Date newest first":
        return sorted(
            medications,
            key=lambda item: (item.medication_date, item.normalized_medicine_time()),
            reverse=True,
        )

    key_functions = {
        "Patient name A-Z": lambda item: (item.patient_name.lower(), item.medication_date),
        "Medicine name A-Z": lambda item: (item.medicine_name.lower(), item.medication_date),
        "Taken first": lambda item: (item.status != Medication.TAKEN, item.medication_date),
        "Not Taken first": lambda item: (item.status != Medication.NOT_TAKEN, item.medication_date),
        "Overdue first": lambda item: (not item.is_overdue(), item.medication_date),
    }
    key = key_functions.get(
        option,
        lambda item: (item.medication_date, item.normalized_medicine_time()),
    )
    return sorted(medications, key=key)
