"""Login and create-user dialogs for PharmaGuard."""

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from auth_manager import DEMO_ADMIN_PASSWORD, DEMO_ADMIN_USERNAME, AuthManager
from styles import current_app_style


class CreateUserDialog(QDialog):
    """Small dialog for creating patient accounts."""

    def __init__(self, auth_manager: AuthManager, parent=None) -> None:
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.created_user = None
        self.setWindowTitle("Create Patient User")
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        form.addRow("First name", self.first_name_input)
        form.addRow("Last name", self.last_name_input)
        form.addRow("Password", self.password_input)

        button_row = QHBoxLayout()
        self.create_button = QPushButton("Create User")
        self.cancel_button = QPushButton("Cancel")
        self.create_button.clicked.connect(self.create_user)
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.create_button)
        button_row.addWidget(self.cancel_button)

        layout.addLayout(form)
        layout.addLayout(button_row)

    def create_user(self) -> None:
        """Validate input and create a patient user."""
        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        password = self.password_input.text().strip()

        if not first_name or not last_name or not password:
            QMessageBox.warning(self, "Missing Information", "First name, last name, and password are required.")
            return

        try:
            self.created_user = self.auth_manager.create_patient_user(first_name, last_name, password)
        except ValueError as error:
            QMessageBox.warning(self, "Weak Password", str(error))
            return
        except Exception as error:
            print(f"Create user error: {error}")
            QMessageBox.critical(self, "User Error", "Could not create the user. Please try again.")
            return

        QMessageBox.information(
            self,
            "User Created",
            f"Patient account created.\nUsername: {self.created_user.username}",
        )
        self.accept()


class LoginDialog(QDialog):
    """Login screen shown before the main PharmaGuard window opens."""

    def __init__(self, auth_manager: AuthManager, parent=None) -> None:
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.logged_in_user = None
        self.setWindowTitle("PharmaGuard Login")
        self.setMinimumWidth(420)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
        if logo_path.exists():
            logo = QLabel()
            logo.setAlignment(Qt.AlignCenter)
            logo.setPixmap(QPixmap(str(logo_path)).scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(logo)

        title = QLabel("PharmaGuard Login")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        motto = QLabel("Never miss a dose.")
        motto.setObjectName("LoginMotto")
        motto.setAlignment(Qt.AlignCenter)
        layout.addWidget(motto)

        if self.auth_manager.using_demo_admin:
            demo_hint = QLabel(
                f"Demo mode — admin login <b>{DEMO_ADMIN_USERNAME}</b> / "
                f"<b>{DEMO_ADMIN_PASSWORD}</b><br>"
                "Set PHARMAGUARD_ADMIN_PASSWORD to disable this notice."
            )
            demo_hint.setObjectName("LoginDemoHint")
            demo_hint.setAlignment(Qt.AlignCenter)
            demo_hint.setWordWrap(True)
            layout.addWidget(demo_hint)

        login_group = QGroupBox("Sign In")
        login_group.setObjectName("LoginCard")
        form = QFormLayout(login_group)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Login as Admin", "Login as User"])
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        form.addRow("Login type", self.role_combo)
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)
        layout.addWidget(login_group)

        button_row = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.create_user_button = QPushButton("Create User")
        self.cancel_button = QPushButton("Cancel")

        self.login_button.clicked.connect(self.login)
        self.create_user_button.clicked.connect(self.open_create_user_dialog)
        self.cancel_button.clicked.connect(self.reject)

        button_row.addWidget(self.login_button)
        button_row.addWidget(self.create_user_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def login(self) -> None:
        """Authenticate admin or patient login."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Missing Login", "Please enter username and password.")
            return

        if self.role_combo.currentText() == "Login as Admin":
            self.logged_in_user = self.auth_manager.login_admin(username, password)
        else:
            self.logged_in_user = self.auth_manager.login_user(username, password)

        if self.logged_in_user is None:
            message = self.auth_manager.last_login_error or "Invalid username or password."
            self.auth_manager.database_manager.add_audit_log(
                "Login failed",
                f"Username: {username}",
                actor_username=username,
                actor_role="admin" if self.role_combo.currentText() == "Login as Admin" else "user",
            )
            QMessageBox.warning(self, "Login Failed", message)
            return

        self.auth_manager.database_manager.add_audit_log(
            "Login success",
            f"Username: {self.logged_in_user.username}",
            actor_user_id=self.logged_in_user.user_id,
            actor_username=self.logged_in_user.username,
            actor_role=self.logged_in_user.role,
        )
        self.accept()

    def open_create_user_dialog(self) -> None:
        """Allow patient account creation from the login screen."""
        dialog = CreateUserDialog(self.auth_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.created_user:
            self.auth_manager.database_manager.add_audit_log(
                "User created",
                f"Username: {dialog.created_user.username}",
                actor_username=dialog.created_user.username,
                actor_role=dialog.created_user.role,
            )
            self.role_combo.setCurrentText("Login as User")
            self.username_input.setText(dialog.created_user.username)
            self.password_input.clear()
