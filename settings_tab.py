"""Settings and audit-log tab for PharmaGuard."""

import csv

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from styles import current_app_style
from user import User


class SettingsTab(QWidget):
    AUDIT_HEADERS = ["Date/Time", "User", "Role", "Action", "Details"]

    def __init__(
        self,
        database_manager,
        current_user,
        apply_settings_callback=None,
        audit_callback=None,
        refresh_callback=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.database_manager = database_manager
        self.current_user = current_user
        self.apply_settings_callback = apply_settings_callback
        self.audit_callback = audit_callback
        self.refresh_callback = refresh_callback
        self._build_ui()
        self.load_settings()
        self.refresh_audit_logs()

    def is_admin(self) -> bool:
        return self.current_user.role == User.ROLE_ADMIN

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        settings_group = QGroupBox("Settings")
        form = QFormLayout(settings_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light Theme", "Dark Theme"])
        self.sound_combo = QComboBox()
        self.sound_combo.addItems(["On", "Off"])
        self.windows_notification_combo = QComboBox()
        self.windows_notification_combo.addItems(["On", "Off"])
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_label = QLabel("85%")
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume_slider)
        volume_row.addWidget(self.volume_label)
        self.default_limit_combo = QComboBox()
        self.default_limit_combo.addItems(["20", "50", "100", "All"])
        self.auto_logout_combo = QComboBox()
        self.auto_logout_combo.addItems(["Off", "5", "10", "15", "30"])
        self.restore_button = QPushButton("Restore Default Settings")
        self.restore_button.setObjectName("WarningButton")

        form.addRow("Theme", self.theme_combo)
        form.addRow("Notification sounds", self.sound_combo)
        form.addRow("Windows notifications", self.windows_notification_combo)
        form.addRow("Notification volume", volume_row)
        if self.is_admin():
            form.addRow("Default daily row limit", self.default_limit_combo)
            form.addRow("Auto logout minutes", self.auto_logout_combo)
        layout.addWidget(settings_group)
        layout.addWidget(self.restore_button)

        self.theme_combo.currentTextChanged.connect(lambda: self.save_setting("theme", self.theme_combo.currentText()))
        self.sound_combo.currentTextChanged.connect(lambda: self.save_setting("notification_sounds", self.sound_combo.currentText()))
        self.windows_notification_combo.currentTextChanged.connect(lambda: self.save_setting("windows_notifications", self.windows_notification_combo.currentText()))
        self.default_limit_combo.currentTextChanged.connect(lambda: self.save_setting("daily_row_limit", self.default_limit_combo.currentText()))
        self.auto_logout_combo.currentTextChanged.connect(lambda: self.save_setting("auto_logout_minutes", self.auto_logout_combo.currentText()))
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.restore_button.clicked.connect(self.restore_defaults)

        if self.is_admin():
            self._build_audit_section(layout)
        layout.addStretch()
        self.setStyleSheet(current_app_style())

    def _build_audit_section(self, layout) -> None:
        group = QGroupBox("Audit Log")
        group_layout = QVBoxLayout(group)

        filter_row = QGridLayout()
        self.audit_search_input = QLineEdit()
        self.audit_search_input.setPlaceholderText("Search username, action, role, or details")
        self.audit_role_combo = QComboBox()
        self.audit_role_combo.addItems(["All", "admin", "user"])
        self.audit_start_date = QDateEdit()
        self.audit_start_date.setCalendarPopup(True)
        self.audit_start_date.setDisplayFormat("yyyy-MM-dd")
        self.audit_start_date.setDate(QDate.currentDate().addMonths(-1))
        self.audit_end_date = QDateEdit()
        self.audit_end_date.setCalendarPopup(True)
        self.audit_end_date.setDisplayFormat("yyyy-MM-dd")
        self.audit_end_date.setDate(QDate.currentDate())
        self.export_button = QPushButton("Export CSV")

        filter_row.addWidget(QLabel("Search"), 0, 0)
        filter_row.addWidget(self.audit_search_input, 0, 1)
        filter_row.addWidget(QLabel("Role"), 0, 2)
        filter_row.addWidget(self.audit_role_combo, 0, 3)
        filter_row.addWidget(QLabel("From"), 1, 0)
        filter_row.addWidget(self.audit_start_date, 1, 1)
        filter_row.addWidget(QLabel("To"), 1, 2)
        filter_row.addWidget(self.audit_end_date, 1, 3)
        filter_row.addWidget(self.export_button, 1, 4)
        group_layout.addLayout(filter_row)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(len(self.AUDIT_HEADERS))
        self.audit_table.setHorizontalHeaderLabels(self.AUDIT_HEADERS)
        self.audit_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.audit_table.setAlternatingRowColors(True)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.horizontalHeader().setStretchLastSection(True)
        group_layout.addWidget(self.audit_table)
        layout.addWidget(group)

        self.audit_search_input.textChanged.connect(self.refresh_audit_logs)
        self.audit_role_combo.currentTextChanged.connect(self.refresh_audit_logs)
        self.audit_start_date.dateChanged.connect(self.refresh_audit_logs)
        self.audit_end_date.dateChanged.connect(self.refresh_audit_logs)
        self.export_button.clicked.connect(self.export_audit_csv)

    def load_settings(self) -> None:
        self.theme_combo.setCurrentText(self.database_manager.get_setting("theme", "Light Theme"))
        self.sound_combo.setCurrentText(self.database_manager.get_setting("notification_sounds", "On"))
        self.windows_notification_combo.setCurrentText(self.database_manager.get_setting("windows_notifications", "On"))
        self.default_limit_combo.setCurrentText(self.database_manager.get_setting("daily_row_limit", "20"))
        self.auto_logout_combo.setCurrentText(self.database_manager.get_setting("auto_logout_minutes", "Off"))
        self.volume_slider.setValue(int(self.database_manager.get_setting("notification_volume", "85")))
        self.apply_settings()

    def save_setting(self, key: str, value: str) -> None:
        self.database_manager.set_setting(key, value)
        if key == "theme":
            self.log("Theme changed", value)
        else:
            self.log("Settings changed", f"{key}: {value}")
        self.apply_settings()

    def on_volume_changed(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self.save_setting("notification_volume", str(value))

    def apply_settings(self) -> None:
        if self.apply_settings_callback:
            self.apply_settings_callback()

    def restore_defaults(self) -> None:
        defaults = {
            "theme": "Light Theme",
            "notification_sounds": "On",
            "windows_notifications": "On",
            "notification_volume": "85",
            "daily_row_limit": "20",
            "auto_logout_minutes": "Off",
        }
        for key, value in defaults.items():
            self.database_manager.set_setting(key, value)
        self.log("Settings changed", "Restored default settings")
        self.load_settings()

    def refresh_audit_logs(self, *_args) -> None:
        if not self.is_admin() or not hasattr(self, "audit_table"):
            return
        logs = self.database_manager.get_audit_logs(
            search_text=self.audit_search_input.text(),
            role=self.audit_role_combo.currentText(),
            start_date=self.audit_start_date.date().toString("yyyy-MM-dd"),
            end_date=self.audit_end_date.date().toString("yyyy-MM-dd"),
        )
        self.audit_table.setRowCount(len(logs))
        for row_index, log in enumerate(logs):
            values = [
                log.get("created_at", ""),
                log.get("actor_username", "") or "-",
                log.get("actor_role", "") or "-",
                log.get("action", ""),
                log.get("details", ""),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.audit_table.setItem(row_index, column_index, item)
        self.audit_table.resizeColumnsToContents()

    def export_audit_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Audit Log", "audit_log.csv", "CSV Files (*.csv)")
        if not path:
            return
        logs = self.database_manager.get_audit_logs(
            search_text=self.audit_search_input.text(),
            role=self.audit_role_combo.currentText(),
            start_date=self.audit_start_date.date().toString("yyyy-MM-dd"),
            end_date=self.audit_end_date.date().toString("yyyy-MM-dd"),
        )
        try:
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(self.AUDIT_HEADERS)
                for log in logs:
                    writer.writerow([
                        log.get("created_at", ""),
                        log.get("actor_username", ""),
                        log.get("actor_role", ""),
                        log.get("action", ""),
                        log.get("details", ""),
                    ])
        except OSError as error:
            QMessageBox.warning(self, "Export Failed", str(error))
            return
        QMessageBox.information(self, "Export Complete", "Audit log was exported successfully.")

    def log(self, action: str, details: str) -> None:
        if self.audit_callback:
            self.audit_callback(action, details)
