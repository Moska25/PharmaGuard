"""
Application entry point for PharmaGuard.

Run this file with:
    python main.py
"""

import sys
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from auth_manager import AuthManager
from database import DatabaseManager
from login_dialog import LoginDialog
from styles import set_app_theme
from ui import MainWindow


def set_windows_app_id() -> None:
    """Give Windows a custom app id so the taskbar uses the PharmaGuard icon."""
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PharmaGuard.Desktop")
    except Exception:
        pass


def load_app_icon() -> QIcon:
    """Load the PharmaGuard logo icon from the assets folder."""
    base_dir = Path(__file__).resolve().parent
    icon_path = base_dir / "assets" / "pharmaguard.ico"
    old_icon_path = base_dir / "assets" / "logo.ico"
    fallback_path = base_dir / "assets" / "logo.png"

    if icon_path.exists():
        return QIcon(str(icon_path))
    if old_icon_path.exists():
        return QIcon(str(old_icon_path))
    return QIcon(str(fallback_path))


class ApplicationController:
    """Owns login, logout, and main-window replacement."""

    def __init__(self, app: QApplication, app_icon: QIcon) -> None:
        self.app = app
        self.app_icon = app_icon
        self.database_manager = DatabaseManager()
        self.auth_manager = AuthManager(self.database_manager)
        self.window = None
        set_app_theme(self.database_manager.get_setting("theme", "Light Theme"))

    def show_login(self) -> bool:
        """Show the login dialog and open a role-specific main window."""
        previous_window = self.window
        if previous_window is not None:
            previous_window.hide()

        login_dialog = LoginDialog(self.auth_manager)
        if not self.app_icon.isNull():
            login_dialog.setWindowIcon(self.app_icon)

        if login_dialog.exec_() != LoginDialog.Accepted:
            if previous_window is not None:
                previous_window.close()
                previous_window.deleteLater()
                self.window = None
            return False

        self.window = MainWindow(
            self.database_manager,
            self.auth_manager,
            login_dialog.logged_in_user,
        )
        if not self.app_icon.isNull():
            self.window.setWindowIcon(self.app_icon)
        self.window.logout_requested.connect(self.handle_logout)
        self.window.show()

        if previous_window is not None:
            previous_window.close()
            previous_window.deleteLater()

        return True

    def handle_logout(self) -> None:
        """Return to the login screen after the user clicks Logout."""
        if not self.show_login():
            self.app.quit()


def main() -> int:
    """Create application objects and start the PyQt event loop."""
    set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("PharmaGuard")
    app.setOrganizationName("PharmaGuard")

    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    controller = ApplicationController(app, app_icon)
    if not controller.show_login():
        return 0

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
