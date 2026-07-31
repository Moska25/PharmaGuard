"""
APScheduler reminder engine for PharmaGuard.

The scheduler runs in the background every minute. It checks for three events:
10 minutes before medication, exact medication time, and missed deadline.
Signals are emitted to the PyQt main thread where popups are safely displayed.
"""

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from PyQt5.QtCore import QObject, pyqtSignal

from database import DatabaseManager


class ReminderScheduler(QObject):
    """Background medication reminder checker."""

    reminder_due = pyqtSignal(str, object)

    EVENT_TEN_MINUTES = "ten_minutes"
    EVENT_EXACT_TIME = "exact_time"
    EVENT_MISSED = "missed"

    def __init__(self, database_manager: DatabaseManager, patient_id=None) -> None:
        super().__init__()
        self.database_manager = database_manager
        self.patient_id = patient_id
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        """Start checking medication reminders every minute."""
        if self.scheduler.running:
            return

        self.scheduler.add_job(
            self.check_medication_times,
            trigger="interval",
            minutes=1,
            next_run_time=datetime.now(),
            id="pharma_guard_reminder_check",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.start()

    def stop(self) -> None:
        """Stop the background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)

    def check_medication_times(self) -> None:
        """Check all not-taken reminders for today or earlier dates."""
        now = datetime.now().replace(second=0, microsecond=0)
        today = now.date().isoformat()
        medications = self.database_manager.get_pending_medications_for_scheduler(today, self.patient_id)

        for medication in medications:
            scheduled_time = medication.scheduled_datetime().replace(second=0, microsecond=0)
            ten_minute_time = medication.ten_minutes_before_datetime().replace(second=0, microsecond=0)

            if now == ten_minute_time and not medication.notified_10min_before:
                self.database_manager.mark_notification_sent(
                    medication.medication_id,
                    "notified_10min_before",
                )
                self.reminder_due.emit(self.EVENT_TEN_MINUTES, medication)
                continue

            if now == scheduled_time and not medication.notified_exact_time:
                self.database_manager.mark_notification_sent(
                    medication.medication_id,
                    "notified_exact_time",
                )
                self.reminder_due.emit(self.EVENT_EXACT_TIME, medication)
                continue

            if now > scheduled_time and not medication.missed_notification_sent:
                self.database_manager.mark_notification_sent(
                    medication.medication_id,
                    "missed_notification_sent",
                )
                self.reminder_due.emit(self.EVENT_MISSED, medication)
