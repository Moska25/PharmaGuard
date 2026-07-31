"""
Main PyQt5 interface for PharmaGuard.

The UI is organized with a QTabWidget:
1. Dashboard
2. Add Medication (admin only)
3. Calendar / Daily View
4. Statistics
5. User Profile
"""

import sqlite3
from pathlib import Path
from typing import Dict, List

import pandas as pd
from PyQt5.QtCore import QDate, Qt, QTime, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QIcon, QTextCharFormat
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from database import DatabaseManager
from auth_manager import AuthManager
from dashboard import DashboardTab
from dialogs import CopyDayDialog, EditMedicationDialog, ReminderDialog
from medication import MEDICATION_SORT_OPTIONS, Medication, sort_medications
from notification_manager import NotificationManager
from patient_widgets import SearchablePatientComboBox
from scheduler import ReminderScheduler
from settings_tab import SettingsTab
from statistics_window import StatisticsWindow
from styles import app_style, current_theme, set_app_theme
from user import User
from user_profile import UserProfileTab


class MainWindow(QMainWindow):
    """Main application window for PharmaGuard."""

    logout_requested = pyqtSignal()

    STATUS_FILTERS = ["All", "Taken", "Not Taken", "Overdue"]

    TABLE_HEADERS = [
        "ID",
        "Patient",
        "Medicine",
        "Dosage",
        "Date",
        "Time",
        "Rule",
        "Status",
        "Category",
        "Warning",
        "Remaining",
    ]

    def __init__(self, database_manager: DatabaseManager, auth_manager: AuthManager, current_user: User) -> None:
        super().__init__()
        self.database_manager = database_manager
        self.auth_manager = auth_manager
        self.current_user = current_user
        self.current_session_role = current_user.role
        self.current_user_id = current_user.user_id
        self.notification_manager = NotificationManager(self)
        self.apply_saved_settings()
        self.scheduler = ReminderScheduler(
            self.database_manager,
            None if self.current_session_role == User.ROLE_ADMIN else self.current_user_id,
        )
        self.csv_path = Path(__file__).resolve().parent / "medicine_info.csv"
        self.medicine_info = self.load_medicine_info()
        self.selected_date = QDate.currentDate()
        self.highlighted_dates = set()
        self.active_reminder_dialogs = []

        self.setWindowTitle("PharmaGuard - Medication Reminder and Tracking")
        self.setMinimumSize(1200, 750)
        self.set_pharmaguard_icon()

        self._build_ui()
        self._connect_events()
        self._apply_styles()
        self.refresh_all()

        self.scheduler.reminder_due.connect(self.handle_reminder_event)
        if self.current_session_role == User.ROLE_USER:
            self.scheduler.start()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(60_000)

    def is_admin(self) -> bool:
        """Return True for admin login."""
        return self.current_session_role == User.ROLE_ADMIN

    def log_action(self, action: str, details: str = "") -> None:
        self.database_manager.add_audit_log(
            action=action,
            details=details,
            actor_user_id=self.current_user_id,
            actor_username=self.current_user.username,
            actor_role=self.current_session_role,
        )

    def apply_saved_settings(self) -> None:
        theme = self.database_manager.get_setting("theme", "Light Theme")
        sounds_enabled = self.database_manager.get_setting("notification_sounds", "On") == "On"
        desktop_enabled = self.database_manager.get_setting("windows_notifications", "On") == "On"
        volume = int(self.database_manager.get_setting("notification_volume", "85"))
        app = QApplication.instance()
        if app:
            set_app_theme(theme)
        self.notification_manager.apply_settings(sounds_enabled, desktop_enabled, volume)
        if hasattr(self, "daily_limit_combo"):
            self.daily_limit_combo.setCurrentText(self.database_manager.get_setting("daily_row_limit", "20"))
        if hasattr(self, "settings_tab"):
            self.refresh_theme_styles()
            self.settings_tab.refresh_audit_logs()

    def refresh_theme_styles(self) -> None:
        self._apply_styles()
        for widget in [
            getattr(self, "dashboard_tab", None),
            getattr(self, "statistics_tab", None),
            getattr(self, "profile_tab", None),
            getattr(self, "settings_tab", None),
        ]:
            if widget and hasattr(widget, "_apply_styles"):
                widget._apply_styles()
            elif widget:
                widget.setStyleSheet(app_style(self.database_manager.get_setting("theme", "Light Theme")))

    def can_show_medication_notification(self, medication: Medication) -> bool:
        """Return True only when this session may receive medication alerts."""
        if self.current_session_role == User.ROLE_ADMIN:
            return False
        return medication.patient_id == self.current_user_id

    def daily_filter_patient_id(self):
        """Return the patient id selected in Daily View, if any."""
        if not self.is_admin():
            return self.current_user.user_id
        if hasattr(self, "daily_patient_combo"):
            is_valid, patient_id = self.daily_patient_combo.selected_patient_id()
            if is_valid:
                return patient_id
            return -1
        return None

    def set_pharmaguard_icon(self) -> None:
        """Set the main window icon when the icon file is available."""
        icon_path = Path(__file__).resolve().parent / "assets" / "pharmaguard.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def load_medicine_info(self) -> Dict[str, Dict[str, str]]:
        """Load medicine information from CSV with pandas."""
        if not self.csv_path.exists():
            return {}

        dataframe = pd.read_csv(self.csv_path)
        medicine_info: Dict[str, Dict[str, str]] = {}

        for _, row in dataframe.iterrows():
            name = str(row["medicine_name"]).strip()
            medicine_info[name.lower()] = {
                "medicine_name": name,
                "category": str(row["category"]).strip(),
                "default_rule": str(row["default_rule"]).strip(),
                "warning": str(row["warning"]).strip(),
            }

        medicine_info.update(
            {
                "aspirin": {
                    "medicine_name": "Aspirin",
                    "category": "Blood thinner",
                    "default_rule": "After Food",
                    "warning": "Can increase bleeding risk",
                },
                "metformin": {
                    "medicine_name": "Metformin",
                    "category": "Diabetes medicine",
                    "default_rule": "With Food",
                    "warning": "Take with meals",
                },
                "omeprazole": {
                    "medicine_name": "Omeprazole",
                    "category": "Stomach medicine",
                    "default_rule": "Before Food",
                    "warning": "Usually taken before breakfast",
                },
            }
        )

        return medicine_info

    def _build_ui(self) -> None:
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        self.setCentralWidget(central_widget)

        title = QLabel("PharmaGuard")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Medication reminder and tracking system")
        subtitle.setObjectName("Subtitle")

        self.tabs = QTabWidget()
        self.dashboard_tab = DashboardTab(
            self.database_manager,
            self.current_user,
            mark_taken_callback=lambda medication_id: self.set_medication_status(
                medication_id,
                Medication.TAKEN,
                show_message=True,
            ),
        )
        self.add_tab = self._build_add_medication_tab() if self.is_admin() else None
        self.calendar_tab = self._build_calendar_tab()
        self.statistics_tab = StatisticsWindow(self.database_manager, self.current_user)
        self.profile_tab = UserProfileTab(
            self.database_manager,
            self.auth_manager,
            self.current_user,
            on_user_changed=self.refresh_after_user_change,
            on_logout=self.request_logout,
            audit_callback=self.log_action,
        )
        self.settings_tab = SettingsTab(
            self.database_manager,
            self.current_user,
            apply_settings_callback=self.apply_saved_settings,
            audit_callback=self.log_action,
        )

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        if self.add_tab is not None:
            self.tabs.addTab(self.add_tab, "Add Medication")
        self.tabs.addTab(self.calendar_tab, "Calendar / Daily View")
        self.tabs.addTab(self.statistics_tab, "Statistics")
        self.tabs.addTab(self.profile_tab, "User Profile")
        self.tabs.addTab(self.settings_tab, "Settings")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(self.tabs)

    def refresh_after_user_change(self) -> None:
        """Refresh patient-dependent controls after admin creates a user."""
        if self.is_admin() and self.add_tab is not None:
            self.refresh_patient_user_combo()
        self.refresh_daily_patient_combo()
        self.refresh_all()

    def _build_add_medication_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        form_group = QGroupBox("Add Medication / წამლის დამატება")
        form_layout = QGridLayout(form_group)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)

        self.patient_user_combo = SearchablePatientComboBox(include_all=False)
        self.patient_user_combo.setToolTip("Search and select the patient user who will receive this medication.")
        self.patient_user_combo.setMinimumWidth(260)

        self.medicine_combo = QComboBox()
        self.medicine_combo.setEditable(True)
        self.medicine_combo.addItems(
            sorted(info["medicine_name"] for info in self.medicine_info.values())
        )
        self.medicine_combo.setInsertPolicy(QComboBox.NoInsert)

        self.dosage_input = QLineEdit()
        self.dosage_input.setPlaceholderText("Example: 500 mg")

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())

        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("HH:mm")
        self.time_input.setTime(QTime.currentTime())

        self.rule_combo = QComboBox()
        self.rule_combo.addItems(["Before Food", "After Food", "With Food"])

        self.status_combo = QComboBox()
        self.status_combo.addItems([Medication.NOT_TAKEN, Medication.TAKEN])

        self.category_label = QLabel("Category: -")
        self.warning_label = QLabel("Warning: -")
        self.warning_label.setWordWrap(True)
        self.patient_medical_warning_label = QLabel("")
        self.patient_medical_warning_label.setObjectName("MedicalWarning")
        self.patient_medical_warning_label.setWordWrap(True)
        self.patient_medical_warning_label.hide()

        form_layout.addWidget(QLabel("Patient / პაციენტი"), 0, 0)
        form_layout.addWidget(self.patient_user_combo, 0, 1)
        form_layout.addWidget(QLabel("Medicine / წამალი"), 0, 2)
        form_layout.addWidget(self.medicine_combo, 0, 3)
        form_layout.addWidget(QLabel("Dosage / დოზა"), 0, 4)
        form_layout.addWidget(self.dosage_input, 0, 5)

        form_layout.addWidget(QLabel("Date / თარიღი"), 1, 0)
        form_layout.addWidget(self.date_edit, 1, 1)
        form_layout.addWidget(QLabel("Time / დრო"), 1, 2)
        form_layout.addWidget(self.time_input, 1, 3)
        form_layout.addWidget(QLabel("Taking Rule"), 1, 4)
        form_layout.addWidget(self.rule_combo, 1, 5)

        form_layout.addWidget(QLabel("Status"), 2, 0)
        form_layout.addWidget(self.status_combo, 2, 1)
        form_layout.addWidget(self.category_label, 3, 0, 1, 3)
        form_layout.addWidget(self.warning_label, 3, 3, 1, 3)
        form_layout.addWidget(self.patient_medical_warning_label, 4, 0, 1, 6)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add Medication")
        self.clear_form_button = QPushButton("Clear Form")
        self.add_button.setObjectName("SuccessButton")
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.clear_form_button)
        button_row.addStretch()

        layout.addWidget(form_group)
        layout.addLayout(button_row)
        layout.addStretch()

        self.refresh_patient_user_combo()
        self.update_patient_medical_warning()
        return tab

    def refresh_patient_user_combo(self) -> None:
        """Reload created patient users for the Add Medication dropdown."""
        if not self.is_admin() or not hasattr(self, "patient_user_combo"):
            return

        _, current_patient_id = self.patient_user_combo.selected_patient_id()
        self.patient_user_combo.populate(
            self.database_manager.list_users(),
            selected_patient_id=current_patient_id,
            keep_current_text=True,
        )
        self.update_patient_medical_warning()

    def selected_patient_user(self):
        """Return the selected patient user only when the combo text is valid."""
        if not hasattr(self, "patient_user_combo"):
            return None

        is_valid, patient_id = self.patient_user_combo.selected_patient_id()
        if not is_valid or patient_id is None:
            return None
        return self.database_manager.get_user_by_id(int(patient_id))

    def refresh_daily_patient_combo(self) -> None:
        """Reload unique patients for the Calendar / Daily View filter."""
        if not hasattr(self, "daily_patient_combo"):
            return

        if self.is_admin():
            _, current_patient_id = self.daily_patient_combo.selected_patient_id()
            self.daily_patient_combo.include_all = True
            self.daily_patient_combo.populate(
                self.database_manager.list_users(),
                selected_patient_id=current_patient_id,
                keep_current_text=True,
            )
            self.daily_patient_label.setVisible(True)
            self.daily_patient_combo.setVisible(True)
        else:
            self.daily_patient_combo.include_all = False
            self.daily_patient_combo.populate(
                [self.current_user],
                selected_patient_id=self.current_user.user_id,
            )
            self.daily_patient_label.setVisible(False)
            self.daily_patient_combo.setVisible(False)

    def _build_calendar_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setSelectedDate(self.selected_date)
        left_layout.addWidget(self.calendar)

        search_group = QGroupBox("Search")
        search_form = QFormLayout(search_group)
        self.daily_patient_combo = SearchablePatientComboBox(include_all=True)
        self.daily_search_input = QLineEdit()
        self.daily_search_input.setPlaceholderText("Search patient or medicine")
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(self.STATUS_FILTERS)
        self.search_date_checkbox = QCheckBox("Filter by date")
        self.search_date_checkbox.setChecked(True)
        self.search_date_edit = QDateEdit()
        self.search_date_edit.setCalendarPopup(True)
        self.search_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.search_date_edit.setDate(self.selected_date)
        self.clear_search_button = QPushButton("Clear Search")

        self.daily_patient_label = QLabel("Patient")
        search_form.addRow(self.daily_patient_label, self.daily_patient_combo)
        search_form.addRow("Search", self.daily_search_input)
        search_form.addRow("Status", self.status_filter_combo)
        search_form.addRow(self.search_date_checkbox)
        search_form.addRow("Date", self.search_date_edit)
        search_form.addRow(self.clear_search_button)
        left_layout.addWidget(search_group)
        left_layout.addStretch()
        self.refresh_daily_patient_combo()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)

        self.daily_title_label = QLabel("Daily Medications")
        self.daily_title_label.setObjectName("SectionTitle")
        self.daily_summary_label = QLabel("")
        self.daily_summary_label.setObjectName("SummaryText")

        sort_row = QHBoxLayout()
        sort_label = QLabel("Sort")
        self.daily_sort_combo = QComboBox()
        self.daily_sort_combo.addItems(MEDICATION_SORT_OPTIONS)
        self.daily_sort_combo.setToolTip("Sort the visible medication table.")
        show_label = QLabel("Show")
        self.daily_limit_combo = QComboBox()
        self.daily_limit_combo.addItems(["20", "50", "100", "All"])
        self.daily_limit_combo.setCurrentText(self.database_manager.get_setting("daily_row_limit", "20"))
        self.daily_limit_combo.setToolTip("Choose how many medication records to display.")
        self.daily_limit_combo.setMinimumWidth(90)
        self.daily_result_count_label = QLabel("Showing 0 of 0 medications")
        self.daily_result_count_label.setObjectName("ResultCountText")
        sort_row.addWidget(sort_label)
        sort_row.addWidget(self.daily_sort_combo)
        sort_row.addSpacing(16)
        sort_row.addWidget(show_label)
        sort_row.addWidget(self.daily_limit_combo)
        sort_row.addSpacing(16)
        sort_row.addWidget(self.daily_result_count_label)
        sort_row.addStretch()

        button_row = QHBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete Selected")
        self.mark_taken_button = QPushButton("Mark As Taken")
        self.mark_not_taken_button = QPushButton("Mark Not Taken")
        self.copy_day_button = QPushButton("Copy Selected Day")
        self.refresh_button = QPushButton("Refresh")
        self.delete_button.setObjectName("DangerButton")
        self.mark_taken_button.setObjectName("SuccessButton")

        for button in [
            self.edit_button,
            self.delete_button,
            self.mark_taken_button,
            self.mark_not_taken_button,
            self.copy_day_button,
            self.refresh_button,
        ]:
            button_row.addWidget(button)

        if not self.is_admin():
            self.edit_button.hide()
            self.delete_button.hide()
            self.copy_day_button.hide()

        button_row.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        right_layout.addWidget(self.daily_title_label)
        right_layout.addWidget(self.daily_summary_label)
        right_layout.addLayout(sort_row)
        right_layout.addLayout(button_row)
        right_layout.addWidget(self.table)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([330, 900])
        layout.addWidget(splitter)

        return tab

    def _connect_events(self) -> None:
        if self.is_admin() and self.add_tab is not None:
            self.add_button.clicked.connect(self.add_medication)
            self.clear_form_button.clicked.connect(self.clear_add_form)
            self.medicine_combo.currentTextChanged.connect(self.update_add_medicine_details)
            self.patient_user_combo.currentTextChanged.connect(self.update_patient_medical_warning)
            self.patient_user_combo.lineEdit().editingFinished.connect(
                lambda: self.patient_user_combo.warn_if_invalid(self)
            )

        self.calendar.clicked.connect(self.on_calendar_date_clicked)
        self.daily_patient_combo.currentTextChanged.connect(self.refresh_all)
        self.daily_patient_combo.lineEdit().editingFinished.connect(
            lambda: self.is_admin() and self.daily_patient_combo.warn_if_invalid(self)
        )
        self.daily_search_input.textChanged.connect(self.refresh_table)
        self.status_filter_combo.currentTextChanged.connect(self.refresh_table)
        self.search_date_checkbox.stateChanged.connect(self.refresh_table)
        self.search_date_edit.dateChanged.connect(self.on_search_date_changed)
        self.clear_search_button.clicked.connect(self.clear_search)
        self.daily_sort_combo.currentTextChanged.connect(self.refresh_table)
        self.daily_limit_combo.currentTextChanged.connect(self.refresh_table)
        self.table.itemSelectionChanged.connect(self.update_button_states)

        self.edit_button.clicked.connect(self.edit_selected_medication)
        self.delete_button.clicked.connect(self.delete_selected_medication)
        self.mark_taken_button.clicked.connect(lambda: self.update_selected_status(Medication.TAKEN))
        self.mark_not_taken_button.clicked.connect(lambda: self.update_selected_status(Medication.NOT_TAKEN))
        self.copy_day_button.clicked.connect(self.copy_selected_day)
        self.refresh_button.clicked.connect(self.refresh_all)

        if self.is_admin() and self.add_tab is not None and self.medicine_combo.currentText():
            self.update_add_medicine_details(self.medicine_combo.currentText())

        self.update_button_states()

    def _apply_styles(self) -> None:
        self.setStyleSheet(app_style(self.database_manager.get_setting("theme", "Light Theme")))

        buttons = [
            self.edit_button,
            self.delete_button,
            self.mark_taken_button,
            self.mark_not_taken_button,
            self.copy_day_button,
            self.refresh_button,
            self.clear_search_button,
        ]
        if self.is_admin() and self.add_tab is not None:
            buttons.extend([self.add_button, self.clear_form_button])

        for button in buttons:
            button.setCursor(Qt.PointingHandCursor)

        if self.is_admin() and self.add_tab is not None:
            self.add_button.setToolTip("Save a new medication reminder.")
            self.clear_form_button.setToolTip("Clear the Add Medication form.")
        self.edit_button.setToolTip("Edit the selected medication.")
        self.delete_button.setToolTip("Delete the selected medication after confirmation.")
        self.mark_taken_button.setToolTip("Mark the selected medication as taken.")
        self.mark_not_taken_button.setToolTip("Mark the selected medication as not taken.")
        self.copy_day_button.setToolTip("Copy all medications from this day to another date.")
        self.refresh_button.setToolTip("Refresh calendar, table, and statistics.")
        self.clear_search_button.setToolTip("Clear search and status filters.")

    def update_button_states(self) -> None:
        """Enable row actions only when a medication row is selected."""
        has_selection = bool(self.table.selectionModel().selectedRows()) if self.table.selectionModel() else False
        for button in [
            self.mark_taken_button,
            self.mark_not_taken_button,
        ]:
            button.setEnabled(has_selection)
        if self.is_admin():
            self.edit_button.setEnabled(has_selection)
            self.delete_button.setEnabled(has_selection)
            self.copy_day_button.setEnabled(True)

    def update_add_medicine_details(self, medicine_name: str) -> None:
        """Autofill CSV-based category, warning, and taking rule."""
        info = self.medicine_info.get(medicine_name.strip().lower())
        if not info:
            self.category_label.setText("Category: -")
            self.warning_label.setText("Warning: -")
            return

        self.category_label.setText(f"Category: {info['category']}")
        self.warning_label.setText(f"Warning: {info['warning']}")
        self.rule_combo.setCurrentText(info["default_rule"])

    def category_text(self) -> str:
        """Return category text from the Add Medication tab."""
        text = self.category_label.text().replace("Category:", "", 1).strip()
        return "" if text == "-" else text

    def warning_text(self) -> str:
        """Return warning text from the Add Medication tab."""
        text = self.warning_label.text().replace("Warning:", "", 1).strip()
        return "" if text == "-" else text

    def update_patient_medical_warning(self, *_args) -> None:
        if not hasattr(self, "patient_medical_warning_label"):
            return

        patient_user = self.selected_patient_user()
        summary = (
            self.database_manager.get_latest_medical_summary(patient_user.user_id)
            if patient_user
            else {}
        )
        lines = []
        allergies = (summary.get("allergies") or "").strip()
        chronic_diseases = (summary.get("chronic_diseases") or "").strip()
        if allergies:
            lines.append(f"Patient has recorded allergies: {allergies}")
        if chronic_diseases:
            lines.append(f"Chronic diseases: {chronic_diseases}")

        self.patient_medical_warning_label.setText("\n".join(lines))
        self.patient_medical_warning_label.setVisible(bool(lines))

    def add_medication(self) -> None:
        """Validate and save a new medication reminder."""
        if self.patient_user_combo.count() == 0:
            QMessageBox.warning(self, "No Patient Users", "Please create a patient user first.")
            return

        patient_user = self.selected_patient_user()
        if patient_user is None:
            QMessageBox.warning(self, "Patient Missing", "Please select a valid patient from the list.")
            return

        patient_name = patient_user.full_name
        medicine_name = self.medicine_combo.currentText().strip()
        dosage = self.dosage_input.text().strip()
        medication_date = self.date_edit.date().toString("yyyy-MM-dd")
        medicine_time = self.time_input.time().toString("HH:mm")

        required_fields = {
            "patient name": patient_name,
            "medicine name": medicine_name,
            "dosage": dosage,
            "medication date": medication_date,
            "medicine time": medicine_time,
        }
        missing_fields = [label for label, value in required_fields.items() if not value]
        if missing_fields:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in: " + ", ".join(missing_fields),
            )
            return

        medication = Medication(
            patient_id=patient_user.user_id,
            patient_name=patient_name,
            medicine_name=medicine_name,
            dosage=dosage,
            medication_date=medication_date,
            medicine_time=medicine_time,
            taking_rule=self.rule_combo.currentText(),
            status=self.status_combo.currentText(),
            category=self.category_text(),
            warning=self.warning_text(),
        )

        try:
            self.database_manager.add_medication(medication)
        except sqlite3.IntegrityError as error:
            print(f"SQLite integrity error while adding medication: {error}")
            QMessageBox.critical(
                self,
                "Database Error",
                "The medication could not be saved because required database information is missing.",
            )
            return
        except ValueError as error:
            print(f"Validation error while adding medication: {error}")
            QMessageBox.warning(self, "Missing Information", str(error))
            return

        self.notification_manager.notify_medication_added(medicine_name, patient_name)
        self.log_action("Medication added", f"{medicine_name} for {patient_name}")
        QMessageBox.information(self, "Medication Added", "Medication was added successfully.")
        self.clear_add_form(keep_date=True)
        self.refresh_all()
        self.tabs.setCurrentWidget(self.calendar_tab)

    def clear_add_form(self, keep_date: bool = False) -> None:
        """Reset add form fields."""
        self.dosage_input.clear()
        self.status_combo.setCurrentText(Medication.NOT_TAKEN)
        self.time_input.setTime(QTime.currentTime())
        if not keep_date:
            self.date_edit.setDate(QDate.currentDate())
        self.medicine_combo.setFocus()

    def on_calendar_date_clicked(self, date_value: QDate) -> None:
        """Refresh daily view when the user selects a calendar date."""
        self.selected_date = date_value
        self.search_date_checkbox.setChecked(True)
        self.search_date_edit.setDate(date_value)
        self.refresh_all()

    def on_search_date_changed(self, date_value: QDate) -> None:
        """Use the search date as the active daily view date."""
        self.selected_date = date_value
        self.calendar.setSelectedDate(date_value)
        self.refresh_all()

    def selected_date_text(self) -> str:
        """Return selected date as YYYY-MM-DD."""
        if self.search_date_checkbox.isChecked():
            return self.search_date_edit.date().toString("yyyy-MM-dd")
        return self.selected_date.toString("yyyy-MM-dd")

    def load_visible_medications(self) -> List[Medication]:
        """Load medications that match the current search controls."""
        search_text = self.daily_search_input.text().strip().lower()
        status_filter = self.status_filter_combo.currentText()
        selected_patient_id = self.daily_filter_patient_id()

        if self.search_date_checkbox.isChecked():
            medications = self.database_manager.load_medications_by_date(
                self.selected_date_text(),
                selected_patient_id,
            )
        else:
            medications = self.database_manager.load_all_medications(selected_patient_id)

        if search_text:
            medications = [
                item
                for item in medications
                if search_text in item.patient_name.lower()
                or search_text in item.medicine_name.lower()
            ]

        if status_filter == "Taken":
            medications = [item for item in medications if item.status == Medication.TAKEN]
        elif status_filter == "Not Taken":
            medications = [item for item in medications if item.status == Medication.NOT_TAKEN]
        elif status_filter == "Overdue":
            medications = [item for item in medications if item.is_overdue()]
        return medications

    def refresh_all(self) -> None:
        """Refresh dashboard, calendar highlights, daily table, and statistics tab."""
        self.dashboard_tab.refresh()
        self.refresh_calendar_highlights()
        self.refresh_table()
        self.statistics_tab.update_statistics(self.selected_date_text())
        self.profile_tab.refresh()

    def request_logout(self) -> None:
        """Tell the application controller to return to the login screen."""
        self.scheduler.stop()
        self.notification_manager.stop_current_sound()
        self.logout_requested.emit()

    def refresh_calendar_highlights(self) -> None:
        """Highlight calendar days that already contain medication reminders."""
        for date_text in self.highlighted_dates:
            date_value = QDate.fromString(date_text, "yyyy-MM-dd")
            if date_value.isValid():
                self.calendar.setDateTextFormat(date_value, QTextCharFormat())

        self.highlighted_dates = self.database_manager.get_dates_with_medications(self.daily_filter_patient_id())
        highlight_format = QTextCharFormat()
        if current_theme() == "Dark Theme":
            highlight_format.setBackground(QBrush(QColor("#1D4ED8")))
            highlight_format.setForeground(QBrush(QColor("#F8FAFC")))
        else:
            highlight_format.setBackground(QBrush(QColor("#d8ecff")))
            highlight_format.setForeground(QBrush(QColor("#0f4f86")))
        highlight_format.setFontWeight(700)

        for date_text in self.highlighted_dates:
            date_value = QDate.fromString(date_text, "yyyy-MM-dd")
            if date_value.isValid():
                self.calendar.setDateTextFormat(date_value, highlight_format)

    def refresh_table(self) -> None:
        """Reload the medication table and summary labels."""
        medications = self.load_visible_medications()
        medications = sort_medications(medications, self.daily_sort_combo.currentText())
        total_matches = len(medications)
        selected_limit = self.daily_limit_combo.currentText()
        if selected_limit != "All":
            medications = medications[: int(selected_limit)]
        self.table.setRowCount(len(medications))

        for row_index, medication in enumerate(medications):
            values = [
                medication.medication_id,
                medication.patient_name,
                medication.medicine_name,
                medication.dosage,
                medication.medication_date,
                medication.normalized_medicine_time(),
                medication.taking_rule,
                medication.status,
                medication.category,
                medication.warning_message(),
                medication.remaining_time_text(),
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column_index in [0, 4, 5, 7, 10]:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column_index, item)

            self.highlight_table_row(row_index, medication)

        self.table.resizeColumnsToContents()
        self.update_daily_summary()
        self.daily_result_count_label.setText(
            f"Showing {len(medications)} of {total_matches} medications"
        )
        self.update_button_states()

    def highlight_table_row(self, row_index: int, medication: Medication) -> None:
        """Apply green, red, or yellow row background based on status."""
        dark = current_theme() == "Dark Theme"
        if medication.is_taken():
            background = QColor("#14532d" if dark else "#dff3e7")
        elif medication.is_overdue():
            background = QColor("#7f1d1d" if dark else "#ffd7d7")
        else:
            if dark:
                background = QColor("#0F172A") if row_index % 2 == 0 else QColor("#111C31")
            else:
                background = QColor("#ffffff") if row_index % 2 == 0 else QColor("#f7f9fc")

        for column_index in range(self.table.columnCount()):
            item = self.table.item(row_index, column_index)
            if item:
                item.setBackground(background)

    def update_daily_summary(self) -> None:
        """Update selected-day count label."""
        date_text = self.selected_date_text()
        stats = self.database_manager.get_statistics_for_date(date_text, self.daily_filter_patient_id())
        self.daily_title_label.setText(f"Daily Medications - {date_text}")
        self.daily_summary_label.setText(
            " | ".join(
                [
                    f"Total: {stats['total']}",
                    f"Taken: {stats['taken']}",
                    f"Not Taken: {stats['not_taken']}",
                    f"Overdue: {stats['overdue']}",
                ]
            )
        )

    def selected_medication_id(self) -> int:
        """Return selected medication id from the table, or 0 if none."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return 0
        row = selected_rows[0].row()
        return int(self.table.item(row, 0).text())

    def edit_selected_medication(self) -> None:
        """Open EditMedicationDialog for the selected row."""
        medication_id = self.selected_medication_id()
        if not medication_id:
            QMessageBox.warning(self, "No Selection", "Please select a medication first.")
            return

        medication = self.database_manager.get_medication_by_id(medication_id)
        if medication is None:
            QMessageBox.warning(self, "Not Found", "Selected medication no longer exists.")
            self.refresh_all()
            return
        if not self.is_admin():
            QMessageBox.warning(self, "Permission Denied", "Patient users cannot edit medication details.")
            return

        dialog = EditMedicationDialog(medication, self.medicine_info, self)
        if dialog.exec_() == EditMedicationDialog.Accepted:
            updated_medication = dialog.get_medication()
            if not updated_medication.patient_name or not updated_medication.medicine_name or not updated_medication.dosage:
                QMessageBox.warning(self, "Missing Information", "Patient, medicine, and dosage are required.")
                return
            try:
                self.database_manager.update_medication(updated_medication)
            except sqlite3.Error as error:
                print(f"SQLite error while editing medication: {error}")
                QMessageBox.critical(
                    self,
                    "Database Error",
                    "The medication could not be updated. Please check the information and try again.",
                )
                return
            self.refresh_all()
            self.log_action("Medication edited", f"ID {medication_id}")

    def delete_selected_medication(self) -> None:
        """Delete the selected medication after confirmation."""
        medication_id = self.selected_medication_id()
        if not medication_id:
            QMessageBox.warning(self, "No Selection", "Please select a medication first.")
            return
        if not self.is_admin():
            QMessageBox.warning(self, "Permission Denied", "Patient users cannot delete medications.")
            return

        answer = QMessageBox.question(
            self,
            "Delete Medication",
            "Delete the selected medication?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.database_manager.delete_medication(medication_id)
        self.log_action("Medication deleted", f"ID {medication_id}")
        self.refresh_all()

    def update_selected_status(self, status: str) -> None:
        """Mark selected medication as Taken or Not Taken."""
        medication_id = self.selected_medication_id()
        if not medication_id:
            QMessageBox.warning(self, "No Selection", "Please select a medication first.")
            return

        self.set_medication_status(medication_id, status, show_message=True)

    def set_medication_status(self, medication_id: int, status: str, show_message: bool = False) -> None:
        """Update medication status and send taken notification when needed."""
        medication = self.database_manager.get_medication_by_id(medication_id)
        if medication is None:
            self.refresh_all()
            return
        if not self.is_admin() and medication.patient_id != self.current_user_id:
            QMessageBox.warning(self, "Permission Denied", "You can only update your own medications.")
            self.refresh_all()
            return

        self.database_manager.update_medication_status(medication_id, status)
        self.log_action(f"Medication marked {status}", f"ID {medication_id}: {medication.medicine_name}")

        if status == Medication.TAKEN:
            if self.can_show_medication_notification(medication):
                self.notification_manager.notify_medication_taken(
                    medication.medicine_name,
                    medication.patient_name,
                )
            if show_message:
                QMessageBox.information(
                    self,
                    "Medication Taken",
                    "Medication was marked as taken.",
                )

        self.refresh_all()

    def copy_selected_day(self) -> None:
        """Copy all medications from the selected day to a target date."""
        source_date = self.selected_date_text()
        if not self.is_admin():
            QMessageBox.warning(self, "Permission Denied", "Only admin can copy medications between days.")
            return

        source_count = len(self.database_manager.load_medications_by_date(source_date))
        if source_count == 0:
            QMessageBox.information(self, "No Medications", "This day has no medications to copy.")
            return

        dialog = CopyDayDialog(source_date, self)
        if dialog.exec_() != CopyDayDialog.Accepted:
            return

        target_date = dialog.target_date()
        copied_count = self.database_manager.copy_day(source_date, target_date)
        self.log_action("Medication day copied", f"{source_date} to {target_date}: {copied_count} medication(s)")
        QMessageBox.information(
            self,
            "Day Copied",
            f"Copied {copied_count} medication(s) to {target_date}.",
        )
        self.selected_date = QDate.fromString(target_date, "yyyy-MM-dd")
        self.search_date_edit.setDate(self.selected_date)
        self.calendar.setSelectedDate(self.selected_date)
        self.refresh_all()

    def clear_search(self) -> None:
        """Clear patient and medicine search while keeping the selected date."""
        if self.is_admin() and hasattr(self, "daily_patient_combo"):
            self.daily_patient_combo.setCurrentIndex(0)
        self.daily_search_input.clear()
        self.status_filter_combo.setCurrentText("All")
        self.daily_limit_combo.setCurrentText("20")
        self.search_date_checkbox.setChecked(True)
        self.search_date_edit.setDate(self.selected_date)
        self.refresh_all()

    def handle_reminder_event(self, event_type: str, medication: Medication) -> None:
        """Show custom popup, desktop notification, and sound for reminders."""
        if not self.can_show_medication_notification(medication):
            return

        title, sound_file = self.reminder_title_and_sound(event_type, medication)
        message = (
            f"{medication.patient_name}: {medication.medicine_name} "
            f"{medication.dosage} at {medication.normalized_medicine_time()}"
        )

        if medication.warning_message():
            message += f"\nWarning: {medication.warning_message()}"

        self.notification_manager.play_sound(sound_file)
        self.notification_manager.show_desktop_notification(title, message, timeout=10)

        dialog = ReminderDialog(
            title=title,
            medication=medication,
            notification_manager=self.notification_manager,
            mark_taken_callback=self.mark_medication_taken_from_popup,
            event_type=event_type,
            parent=self,
        )
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda: self.remove_closed_dialog(dialog))
        self.active_reminder_dialogs.append(dialog)
        dialog.show()
        self.refresh_all()

    def reminder_title_and_sound(self, event_type: str, medication: Medication) -> tuple:
        """Return popup title and custom sound filename for a reminder type."""
        if event_type == ReminderScheduler.EVENT_TEN_MINUTES:
            return "Medication Reminder - 10 Minutes Left", "ten_min_before_checkin.wav"

        if event_type == ReminderScheduler.EVENT_EXACT_TIME:
            return "Medication Time", "checkin.wav"

        return "Missed Medication Deadline", "missed_deadline.wav"

    def mark_medication_taken_from_popup(self, medication_id: int) -> None:
        """Handle Mark As Taken button from custom reminder popup."""
        self.notification_manager.stop_current_sound()
        self.set_medication_status(medication_id, Medication.TAKEN, show_message=False)

    def remove_closed_dialog(self, dialog: ReminderDialog) -> None:
        """Remove a closed non-modal reminder dialog from the reference list."""
        if dialog in self.active_reminder_dialogs:
            self.active_reminder_dialogs.remove(dialog)

    def closeEvent(self, event) -> None:
        """Stop scheduler and sound before closing the application."""
        self.scheduler.stop()
        self.notification_manager.stop_current_sound()
        event.accept()
