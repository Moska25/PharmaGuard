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
            # The statistics tab opens with nothing selected, which would
            # screenshot as a set of empty charts. Put it in a state that
            # actually shows the demo data.
            if label == "Statistics":
                tab = window.statistics_tab
                tab.date_range_combo.setCurrentText(tab.RANGE_MONTH)
                tab.patient_selector.all_patients_checkbox.setChecked(True)
                tab.update_statistics()
                QApplication.processEvents()
            slug = (
                label.lower()
                .replace(" / ", "-")
                .replace(" ", "-")
                .replace("/", "-")
            )
            capture(window, slug, suffix=suffix)

        window.close()
        login.close()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
