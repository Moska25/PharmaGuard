"""
APScheduler reminder engine for PharmaGuard.

The scheduler runs in the background every minute. It checks for three events:
10 minutes before medication, exact medication time, and missed deadline.
Signals are emitted to the PyQt main thread where popups are safely displayed.
"""

from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from PyQt5.QtCore import QObject, pyqtSignal

from database import DatabaseManager


class ReminderScheduler(QObject):
    """Background medication reminder checker."""

    reminder_due = pyqtSignal(str, object)

    EVENT_TEN_MINUTES = "ten_minutes"
    EVENT_EXACT_TIME = "exact_time"
    EVENT_MISSED = "missed"

    # How long after the scheduled minute a dose still counts as "due now"
    # rather than "missed". Matches the original one-minute tick behaviour.
    MISSED_GRACE = timedelta(minutes=1)

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

    def check_medication_times(self, reference_time: Optional[datetime] = None) -> None:
        """
        Check all not-taken reminders for today or earlier dates.

        Each event is matched against a time *window* rather than an exact minute.
        The previous version compared ``now == scheduled_time``, which meant a
        single skipped tick - the machine asleep, the app busy, a job overrun -
        dropped that reminder permanently. For a medication app that silent miss
        is the worst possible failure, so a late check still fires the reminder.

        ``reference_time`` is injectable so the transitions can be tested without
        waiting on the wall clock.
        """
        now = (reference_time or datetime.now()).replace(second=0, microsecond=0)
        today = now.date().isoformat()
        medications = self.database_manager.get_pending_medications_for_scheduler(today, self.patient_id)

        for medication in medications:
            scheduled_time = medication.scheduled_datetime().replace(second=0, microsecond=0)
            ten_minute_time = medication.ten_minutes_before_datetime().replace(second=0, microsecond=0)
            missed_time = scheduled_time + self.MISSED_GRACE

            if not medication.notified_10min_before and ten_minute_time <= now < scheduled_time:
                self._fire(self.EVENT_TEN_MINUTES, medication, "notified_10min_before")
                continue

            if not medication.notified_exact_time and scheduled_time <= now < missed_time:
                self._fire(self.EVENT_EXACT_TIME, medication, "notified_exact_time")
                continue

            if not medication.missed_notification_sent and now >= missed_time:
                self._fire(self.EVENT_MISSED, medication, "missed_notification_sent")

    def _fire(self, event: str, medication, flag_name: str) -> None:
        """Record that a notification was sent, then hand it to the UI thread."""
        self.database_manager.mark_notification_sent(medication.medication_id, flag_name)
        setattr(medication, flag_name, 1)
        self.reminder_due.emit(event, medication)
