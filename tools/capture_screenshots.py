"""
Render the PharmaGuard screens to docs/screenshots/ for the README.

Runs headless, against a throwaway seeded database, so the captures are
reproducible and never contain real patient data:

    QT_QPA_PLATFORM=offscreen python tools/capture_screenshots.py

Pass --theme dark for the dark-theme set.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

import styles  # noqa: E402
from auth_manager import AuthManager  # noqa: E402
from database import DatabaseManager  # noqa: E402
from login_dialog import LoginDialog  # noqa: E402
from seed_demo_data import seed  # noqa: E402
from ui import MainWindow  # noqa: E402
from user import User  # noqa: E402

OUTPUT = ROOT / "docs" / "screenshots"
WINDOW_SIZE = (1360, 860)


def capture(widget, name: str, *, suffix: str = "") -> Path:
    """Grab a widget to PNG. Qt renders offscreen, so no window server is needed."""
    QApplication.processEvents()
    destination = OUTPUT / f"{name}{suffix}.png"
    widget.grab().save(str(destination))
    print(f"  {destination.relative_to(ROOT)}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    arguments = parser.parse_args()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    suffix = "-dark" if arguments.theme == "dark" else ""

    workspace = Path(tempfile.mkdtemp(prefix="pharmaguard-shots-"))
    try:
        database = DatabaseManager(str(workspace / "shots.db"))
        seed(database)

        # MainWindow re-reads the theme from the settings table on construction
        # (ui.py), so setting it only on the QApplication is not enough.
        theme_name = "Dark Theme" if arguments.theme == "dark" else "Light Theme"
        database.set_setting("theme", theme_name)

        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("PharmaGuard")
        styles.set_app_theme(theme_name)

        auth = AuthManager(database)
        print(f"Capturing {arguments.theme} theme:")

        login = LoginDialog(auth)
        login.resize(460, login.sizeHint().height())
        capture(login, "login", suffix=suffix)

        admin = User(
            user_id=None,
            first_name="Admin",
            last_name="",
            username=auth.admin_username,
            password="",
            role=User.ROLE_ADMIN,
        )
        window = MainWindow(database, auth, admin)
        window.resize(*WINDOW_SIZE)
        window.show()

        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            QApplication.processEvents()
            label = window.tabs.tabText(index)
            slug = (
                label.lower()
                .replace(" / ", "-")
                .replace(" ", "-")
                .replace("/", "-")
            )
            capture(window, slug, suffix=suffix)

        capture_dialogs(database, suffix)

        window.close()
        login.close()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    return 0


def capture_dialogs(database: DatabaseManager, suffix: str) -> None:
    """
    Capture the modal surfaces, which walking the tab bar never reaches.

    The reminder popup is the single most demo-able moment in the app - it is
    what the whole scheduler exists to produce - and it appeared in no
    screenshot at all until this was added.
    """
    from dialogs import CopyDayDialog, EditMedicationDialog, ReminderDialog  # noqa: E402
    from notification_manager import NotificationManager  # noqa: E402
    from scheduler import ReminderScheduler  # noqa: E402

    notifications = NotificationManager()
    # Nothing should play a sound or raise an OS notification during a capture.
    notifications.apply_settings(sounds_enabled=False, desktop_enabled=False, volume=0)

    # Today's doses, not the whole history. load_all_medications is ordered by
    # date ascending, so taking the first overdue row picked one from the far
    # end of the seeded 21-day window and the popup read "Missed by 21d 3h".
    today = date.today().isoformat()
    todays_doses = database.load_medications_by_date(today)
    overdue = next((item for item in todays_doses if item.is_overdue()), todays_doses[0])
    upcoming = next(
        (item for item in todays_doses if not item.is_overdue() and not item.is_taken()),
        todays_doses[-1],
    )

    dialogs = {
        # Missed is the more informative of the three states to show: it is the
        # only one that reports how late the dose now is.
        "reminder-missed": ReminderDialog(
            title="Missed Medication Deadline",
            medication=overdue,
            notification_manager=notifications,
            mark_taken_callback=lambda _id: None,
            event_type=ReminderScheduler.EVENT_MISSED,
        ),
        "reminder-due": ReminderDialog(
            title="Medication Reminder - 10 Minutes Left",
            medication=upcoming,
            notification_manager=notifications,
            mark_taken_callback=lambda _id: None,
            event_type=ReminderScheduler.EVENT_TEN_MINUTES,
        ),
        "edit-medication": EditMedicationDialog(upcoming, {}),
        "copy-day": CopyDayDialog(upcoming.medication_date),
    }
    for name, dialog in dialogs.items():
        dialog.setStyleSheet(styles.current_app_style())
        dialog.adjustSize()
        QApplication.processEvents()
        capture(dialog, name, suffix=suffix)
        dialog.close()


if __name__ == "__main__":
    raise SystemExit(main())
