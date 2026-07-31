"""
User Profile tab for PharmaGuard.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from auth_manager import AuthManager
from database import DatabaseManager
from medication import Medication
from dialogs import MedicalHistoryDialog
from login_dialog import CreateUserDialog
from patient_widgets import SearchablePatientComboBox
from styles import current_app_style
from user import User


class UserProfileTab(QWidget):
    """Shows admin user-management tools or the patient profile."""

    ACTIVE_FILTERS = {
        "All Users": None,
        "Active Users": "active",
        "Inactive Users": "inactive",
    }
    HISTORY_HEADERS = [
        "Diagnosis",
        "Condition Notes",
        "Allergies",
        "Chronic Diseases",
        "Past Surgeries",
        "Current Symptoms",
        "Doctor Notes",
        "Created At",
        "Updated At",
    ]

    def __init__(
        self,
        database_manager: DatabaseManager,
        auth_manager: AuthManager,
        current_user: User,
        on_user_changed=None,
        on_logout=None,
        audit_callback=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.database_manager = database_manager
        self.auth_manager = auth_manager
        self.current_user = current_user
        self.on_user_changed = on_user_changed
        self.on_logout = on_logout
        self.audit_callback = audit_callback
        self.medical_history_records = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(14)

        header_layout = QHBoxLayout()
        title = QLabel("User Profile")
        title.setObjectName("ProfileTitle")
        self.logout_button = QPushButton("Logout")
        self.logout_button.setObjectName("LogoutButton")
        self.logout_button.setToolTip("Sign out and return to the login screen.")
        self.logout_button.clicked.connect(self.request_logout)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.logout_button)
        self.layout.addLayout(header_layout)

        if self.current_user.role == User.ROLE_ADMIN:
            self._build_admin_view()
        else:
            self._build_patient_view()

        self._apply_styles()

    def _build_admin_view(self) -> None:
        create_group = QGroupBox("Create Patient User")
        create_layout = QHBoxLayout(create_group)
        self.create_user_button = QPushButton("Create User")
        self.create_user_button.setObjectName("SuccessButton")
        self.create_user_button.setToolTip("Create a new patient account.")
        self.create_user_button.clicked.connect(self.open_create_user_dialog)
        create_layout.addWidget(self.create_user_button)
        create_layout.addStretch()
        self.layout.addWidget(create_group)

        list_group = QGroupBox("Patient Users")
        list_layout = QVBoxLayout(list_group)
        search_row = QHBoxLayout()
        self.user_search_combo = SearchablePatientComboBox(include_all=True)
        self.user_search_combo.setToolTip("Search users by first name, last name, full name, or username.")
        self.user_search_combo.currentTextChanged.connect(self.refresh_users_table)
        self.user_search_combo.lineEdit().editingFinished.connect(self.warn_if_invalid_user_filter)
        self.reset_password_button = QPushButton("Reset User Password")
        self.reset_password_button.clicked.connect(self.reset_selected_user_password)
        self.activate_user_button = QPushButton("Activate User")
        self.activate_user_button.setObjectName("SuccessButton")
        self.activate_user_button.clicked.connect(lambda: self.set_selected_user_active(True))
        self.deactivate_user_button = QPushButton("Deactivate User")
        self.deactivate_user_button.setObjectName("DangerButton")
        self.deactivate_user_button.clicked.connect(lambda: self.set_selected_user_active(False))
        self.user_status_filter_combo = QComboBox()
        self.user_status_filter_combo.addItems(list(self.ACTIVE_FILTERS.keys()))
        self.user_status_filter_combo.currentTextChanged.connect(self.on_user_status_filter_changed)
        search_row.addWidget(QLabel("Find User"))
        search_row.addWidget(self.user_search_combo, stretch=1)
        search_row.addWidget(QLabel("Status"))
        search_row.addWidget(self.user_status_filter_combo)
        search_row.addWidget(self.reset_password_button)
        search_row.addWidget(self.activate_user_button)
        search_row.addWidget(self.deactivate_user_button)
        list_layout.addLayout(search_row)

        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(["ID", "Full Name", "Username", "Role", "Status", "Created Date"])
        self.users_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.horizontalHeader().setStretchLastSection(True)
        list_layout.addWidget(self.users_table)

        self.layout.addWidget(list_group)
        self._build_medical_history_section(admin=True)

    def _build_patient_view(self) -> None:
        info_group = QGroupBox("My Profile")
        info_layout = QFormLayout(info_group)
        info_layout.addRow("Full name", QLabel(self.current_user.full_name))
        info_layout.addRow("Username", QLabel(self.current_user.username))
        info_layout.addRow("Role", QLabel("Patient"))
        self.layout.addWidget(info_group)

        summary_group = QGroupBox("Medication Summary")
        summary_layout = QGridLayout(summary_group)
        self.summary_labels = {}
        for index, key in enumerate(["Total", "Taken", "Not Taken", "Overdue"]):
            label = QLabel("0")
            label.setObjectName("SummaryValue")
            summary_layout.addWidget(QLabel(key), 0, index)
            summary_layout.addWidget(label, 1, index)
            self.summary_labels[key] = label
        self.layout.addWidget(summary_group)

        password_group = QGroupBox("Change Password")
        password_layout = QFormLayout(password_group)
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.change_password_button = QPushButton("Change Password")
        self.change_password_button.clicked.connect(self.change_own_password)
        password_layout.addRow("New password", self.new_password_input)
        password_layout.addRow(self.change_password_button)
        self.layout.addWidget(password_group)
        self._build_medical_history_section(admin=False)
        self.layout.addStretch()

    def _build_medical_history_section(self, admin: bool) -> None:
        group = QGroupBox("Medical History")
        layout = QVBoxLayout(group)

        if admin:
            filter_row = QHBoxLayout()
            self.history_patient_combo = SearchablePatientComboBox(include_all=True)
            self.history_patient_combo.setToolTip("Search patient by first name, last name, full name, or username.")
            self.history_patient_combo.currentTextChanged.connect(self.refresh_medical_history_table)
            self.history_search_input = QLineEdit()
            self.history_search_input.setPlaceholderText("Search patient, username, diagnosis, or notes")
            self.history_search_input.textChanged.connect(self.refresh_medical_history_table)
            filter_row.addWidget(QLabel("Patient"))
            filter_row.addWidget(self.history_patient_combo, stretch=1)
            filter_row.addWidget(QLabel("Search"))
            filter_row.addWidget(self.history_search_input, stretch=1)
            layout.addLayout(filter_row)

            button_row = QHBoxLayout()
            self.add_history_button = QPushButton("Add Diagnosis")
            self.edit_history_button = QPushButton("Edit Selected")
            self.delete_history_button = QPushButton("Delete Selected")
            self.add_history_button.setObjectName("SuccessButton")
            self.delete_history_button.setObjectName("DangerButton")
            self.add_history_button.clicked.connect(self.add_medical_history)
            self.edit_history_button.clicked.connect(self.edit_medical_history)
            self.delete_history_button.clicked.connect(self.delete_medical_history)
            button_row.addWidget(self.add_history_button)
            button_row.addWidget(self.edit_history_button)
            button_row.addWidget(self.delete_history_button)
            button_row.addStretch()
            layout.addLayout(button_row)
        else:
            note = QLabel("Doctor/admin notes are shown here for your account.")
            note.setObjectName("MutedText")
            layout.addWidget(note)

        self.medical_history_table = QTableWidget()
        self.medical_history_table.setColumnCount(len(self.HISTORY_HEADERS))
        self.medical_history_table.setHorizontalHeaderLabels(self.HISTORY_HEADERS)
        self.medical_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.medical_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.medical_history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.medical_history_table.setAlternatingRowColors(True)
        self.medical_history_table.verticalHeader().setVisible(False)
        self.medical_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.medical_history_table.horizontalHeader().setStretchLastSection(True)
        if admin:
            self.medical_history_table.itemSelectionChanged.connect(self.update_history_button_states)
            self.update_history_button_states()
        layout.addWidget(self.medical_history_table)
        self.layout.addWidget(group)

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def refresh(self) -> None:
        """Refresh tab content."""
        if self.current_user.role == User.ROLE_ADMIN:
            self.refresh_user_search_options()
            self.refresh_users_table()
            self.refresh_history_patient_combo()
            self.refresh_medical_history_table()
        else:
            self.refresh_patient_summary()
            self.refresh_medical_history_table()

    def open_create_user_dialog(self) -> None:
        dialog = CreateUserDialog(self.auth_manager, self)
        if dialog.exec_() == CreateUserDialog.Accepted:
            self.refresh_user_search_options()
            self.refresh_users_table()
            if dialog.created_user:
                self.log_action("User created", dialog.created_user.username)
            if self.on_user_changed:
                self.on_user_changed()

    def refresh_user_search_options(self) -> None:
        """Reload the searchable user filter for admins."""
        if self.current_user.role != User.ROLE_ADMIN:
            return
        is_valid, selected_user_id = self.user_search_combo.selected_patient_id()
        self.user_search_combo.populate(
            self.database_manager.list_users(active_filter=self.current_active_filter()),
            selected_patient_id=selected_user_id if is_valid else None,
            keep_current_text=True,
        )
        if self.user_search_combo.count() > 0 and self.user_search_combo.itemData(0) is None:
            self.user_search_combo.setItemText(0, "All Users")

    def refresh_history_patient_combo(self) -> None:
        if self.current_user.role != User.ROLE_ADMIN or not hasattr(self, "history_patient_combo"):
            return
        is_valid, selected_user_id = self.history_patient_combo.selected_patient_id()
        self.history_patient_combo.populate(
            self.database_manager.list_users(),
            selected_patient_id=selected_user_id if is_valid else None,
            keep_current_text=True,
        )

    def on_user_status_filter_changed(self) -> None:
        """Refresh search options and table after changing active status filter."""
        self.refresh_user_search_options()
        self.refresh_users_table()

    def current_active_filter(self):
        """Return active/inactive filter value for database queries."""
        if not hasattr(self, "user_status_filter_combo"):
            return None
        return self.ACTIVE_FILTERS.get(self.user_status_filter_combo.currentText())

    def refresh_users_table(self) -> None:
        if self.current_user.role != User.ROLE_ADMIN:
            return

        is_valid, selected_user_id = self.user_search_combo.selected_patient_id()
        if is_valid and selected_user_id is not None:
            selected_user = self.database_manager.get_user_by_id(int(selected_user_id))
            active_filter = self.current_active_filter()
            matches_filter = (
                not active_filter
                or active_filter == "active" and selected_user and selected_user.is_active
                or active_filter == "inactive" and selected_user and not selected_user.is_active
            )
            users = [selected_user] if selected_user and matches_filter else []
        elif is_valid:
            users = self.database_manager.list_users(active_filter=self.current_active_filter())
        else:
            users = []

        self.users_table.setRowCount(len(users))
        for row_index, user in enumerate(users):
            values = [user.user_id, user.full_name, user.username, user.role, user.status_text(), user.created_at]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column_index in [0, 3, 4]:
                    item.setTextAlignment(Qt.AlignCenter)
                if column_index == 4:
                    item.setForeground(Qt.darkGreen if user.is_active else Qt.red)
                self.users_table.setItem(row_index, column_index, item)
        self.users_table.resizeColumnsToContents()
        if selected_user_id is not None and self.users_table.rowCount() > 0:
            self.users_table.selectRow(0)

    def warn_if_invalid_user_filter(self) -> None:
        """Warn when an admin types a user value that is not in the list."""
        self.user_search_combo.warn_if_invalid(self)

    def selected_user_id(self) -> int:
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            return 0
        row = selected_rows[0].row()
        return int(self.users_table.item(row, 0).text())

    def selected_history_id(self) -> int:
        selected_rows = self.medical_history_table.selectionModel().selectedRows()
        if not selected_rows:
            return 0
        item = self.medical_history_table.item(selected_rows[0].row(), 0)
        return int(item.data(Qt.UserRole) or 0)

    def selected_history_record(self):
        history_id = self.selected_history_id()
        for record in self.medical_history_records:
            if int(record["id"]) == history_id:
                return record
        return None

    def selected_history_patient_id(self):
        if self.current_user.role != User.ROLE_ADMIN:
            return self.current_user.user_id
        is_valid, patient_id = self.history_patient_combo.selected_patient_id()
        return patient_id if is_valid else -1

    def refresh_medical_history_table(self, *_args) -> None:
        if not hasattr(self, "medical_history_table"):
            return

        patient_id = self.selected_history_patient_id()
        if patient_id == -1:
            records = []
        else:
            search_text = self.history_search_input.text() if hasattr(self, "history_search_input") else ""
            records = self.database_manager.get_medical_history_by_patient(patient_id, search_text)

        self.medical_history_records = records
        self.medical_history_table.setRowCount(len(records))
        fields = [
            "diagnosis",
            "condition_notes",
            "allergies",
            "chronic_diseases",
            "past_surgeries",
            "current_symptoms",
            "doctor_notes",
            "created_at",
            "updated_at",
        ]

        for row_index, record in enumerate(records):
            for column_index, field in enumerate(fields):
                item = QTableWidgetItem(str(record.get(field, "") or ""))
                item.setToolTip(item.text())
                if column_index == 0:
                    item.setData(Qt.UserRole, record["id"])
                    item.setData(Qt.UserRole + 1, record["patient_id"])
                self.medical_history_table.setItem(row_index, column_index, item)

        self.medical_history_table.resizeColumnsToContents()
        if self.current_user.role == User.ROLE_ADMIN:
            self.update_history_button_states()

    def update_history_button_states(self) -> None:
        if not hasattr(self, "edit_history_button"):
            return
        has_selection = bool(self.medical_history_table.selectionModel().selectedRows()) if self.medical_history_table.selectionModel() else False
        self.edit_history_button.setEnabled(has_selection)
        self.delete_history_button.setEnabled(has_selection)

    def add_medical_history(self) -> None:
        patient_id = self.selected_history_patient_id()
        if not patient_id:
            QMessageBox.warning(self, "Patient Missing", "Please select a valid patient from the list.")
            return

        dialog = MedicalHistoryDialog(parent=self)
        if dialog.exec_() != MedicalHistoryDialog.Accepted:
            return

        try:
            self.database_manager.add_medical_history(int(patient_id), dialog.get_data())
        except ValueError as error:
            QMessageBox.warning(self, "Missing Information", str(error))
            return
        self.log_action("Medical history added", f"Patient ID {patient_id}")
        self.refresh_medical_history_table()
        if self.on_user_changed:
            self.on_user_changed()

    def edit_medical_history(self) -> None:
        record = self.selected_history_record()
        if not record:
            QMessageBox.warning(self, "No Selection", "Please select a medical history record first.")
            return

        dialog = MedicalHistoryDialog(record, self)
        if dialog.exec_() != MedicalHistoryDialog.Accepted:
            return

        try:
            self.database_manager.update_medical_history(int(record["id"]), dialog.get_data())
        except ValueError as error:
            QMessageBox.warning(self, "Missing Information", str(error))
            return
        self.log_action("Medical history edited", f"Record ID {record['id']}")
        self.refresh_medical_history_table()
        if self.on_user_changed:
            self.on_user_changed()

    def delete_medical_history(self) -> None:
        history_id = self.selected_history_id()
        if not history_id:
            QMessageBox.warning(self, "No Selection", "Please select a medical history record first.")
            return

        answer = QMessageBox.question(
            self,
            "Delete Diagnosis",
            "Delete the selected medical history record?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.database_manager.delete_medical_history(history_id)
        self.log_action("Medical history deleted", f"Record ID {history_id}")
        self.refresh_medical_history_table()
        if self.on_user_changed:
            self.on_user_changed()

    def reset_selected_user_password(self) -> None:
        user_id = self.selected_user_id()
        if not user_id:
            QMessageBox.warning(self, "No Selection", "Please select a user first.")
            return
        new_password = "Patient123!"
        try:
            self.auth_manager.change_password(user_id, new_password)
        except ValueError as error:
            QMessageBox.warning(self, "Weak Password", str(error))
            return
        self.log_action("Password reset", f"User ID {user_id}")
        QMessageBox.information(self, "Password Reset", f"Password was reset to: {new_password}")

    def set_selected_user_active(self, is_active: bool) -> None:
        """Activate or deactivate the selected user."""
        user_id = self.selected_user_id()
        if not user_id:
            QMessageBox.warning(self, "No Selection", "Please select a user first.")
            return

        selected_user = self.database_manager.get_user_by_id(user_id)
        if selected_user is None:
            QMessageBox.warning(self, "Not Found", "Selected user no longer exists.")
            self.refresh()
            return

        if selected_user.user_id == self.current_user.user_id:
            QMessageBox.warning(self, "Action Not Allowed", "You cannot deactivate your own account.")
            return

        if not is_active:
            answer = QMessageBox.question(
                self,
                "Deactivate User",
                "Are you sure you want to deactivate this user?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        self.database_manager.update_user_active_status(user_id, is_active)
        self.log_action("User activated" if is_active else "User deactivated", selected_user.username)
        self.refresh_user_search_options()
        self.refresh_users_table()
        if self.on_user_changed:
            self.on_user_changed()

    def refresh_patient_summary(self) -> None:
        medications = self.database_manager.load_all_medications(self.current_user.user_id)
        taken = sum(1 for item in medications if item.status == Medication.TAKEN)
        not_taken = sum(1 for item in medications if item.status == Medication.NOT_TAKEN)
        overdue = sum(1 for item in medications if item.is_overdue())
        self.summary_labels["Total"].setText(str(len(medications)))
        self.summary_labels["Taken"].setText(str(taken))
        self.summary_labels["Not Taken"].setText(str(not_taken))
        self.summary_labels["Overdue"].setText(str(overdue))

    def change_own_password(self) -> None:
        password = self.new_password_input.text().strip()
        if not password:
            QMessageBox.warning(self, "Missing Password", "Please enter a new password.")
            return
        try:
            self.auth_manager.change_password(self.current_user.user_id, password)
        except ValueError as error:
            QMessageBox.warning(self, "Weak Password", str(error))
            return
        self.new_password_input.clear()
        self.log_action("Password changed", self.current_user.username)
        QMessageBox.information(self, "Password Changed", "Your password has been updated.")

    def request_logout(self) -> None:
        """Ask for confirmation and then return control to the main app."""
        answer = QMessageBox.question(
            self,
            "Logout",
            "Do you want to log out?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes and self.on_logout:
            self.log_action("Logout", self.current_user.username)
            self.on_logout()

    def log_action(self, action: str, details: str = "") -> None:
        if self.audit_callback:
            self.audit_callback(action, details)
