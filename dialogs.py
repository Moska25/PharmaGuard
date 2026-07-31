"""
Dialog classes for PharmaGuard.

Includes the edit medication dialog, the copy-day date picker, and the custom
reminder popup used by scheduler notifications.
"""

from typing import Callable, Dict

from PyQt5.QtCore import QDate, Qt, QTime
from PyQt5.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

from medication import Medication
from styles import current_app_style


class EditMedicationDialog(QDialog):
    """Dialog for editing an existing medication reminder."""

    def __init__(
        self,
        medication: Medication,
        medicine_info: Dict[str, Dict[str, str]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.medication = medication
        self.medicine_info = medicine_info
        self.setWindowTitle("Edit Medication")
        self.setMinimumWidth(460)
        self._build_ui()
        self._load_medication()
        self._connect_events()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.patient_input = QLineEdit()
        self.medicine_combo = QComboBox()
        self.medicine_combo.setEditable(True)
        self.medicine_combo.addItems(
            sorted(info["medicine_name"] for info in self.medicine_info.values())
        )
        self.dosage_input = QLineEdit()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("HH:mm")

        self.rule_combo = QComboBox()
        self.rule_combo.addItems(["Before Food", "After Food", "With Food"])

        self.status_combo = QComboBox()
        self.status_combo.addItems([Medication.NOT_TAKEN, Medication.TAKEN])

        self.category_label = QLabel("Category: -")
        self.warning_label = QLabel("Warning: -")
        self.warning_label.setWordWrap(True)

        form.addRow("Patient / პაციენტი", self.patient_input)
        form.addRow("Medicine / წამალი", self.medicine_combo)
        form.addRow("Dosage / დოზა", self.dosage_input)
        form.addRow("Date / თარიღი", self.date_edit)
        form.addRow("Time / დრო", self.time_input)
        form.addRow("Taking rule", self.rule_combo)
        form.addRow("Status", self.status_combo)
        form.addRow(self.category_label)
        form.addRow(self.warning_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

    def _load_medication(self) -> None:
        self.patient_input.setText(self.medication.patient_name)
        self.medicine_combo.setCurrentText(self.medication.medicine_name)
        self.dosage_input.setText(self.medication.dosage)
        self.date_edit.setDate(QDate.fromString(self.medication.medication_date, "yyyy-MM-dd"))
        self.time_input.setTime(QTime.fromString(self.medication.normalized_medicine_time(), "HH:mm"))
        self.rule_combo.setCurrentText(self.medication.taking_rule)
        self.status_combo.setCurrentText(self.medication.status)
        self.update_medicine_details(self.medication.medicine_name)

    def _connect_events(self) -> None:
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.medicine_combo.currentTextChanged.connect(self.update_medicine_details)

    def update_medicine_details(self, medicine_name: str) -> None:
        """Autofill category, warning, and default rule from CSV data."""
        info = self.medicine_info.get(medicine_name.strip().lower())
        if not info:
            self.category_label.setText(f"Category: {self.medication.category or '-'}")
            self.warning_label.setText(f"Warning: {self.medication.warning or '-'}")
            return

        self.category_label.setText(f"Category: {info['category']}")
        self.warning_label.setText(f"Warning: {info['warning']}")
        self.rule_combo.setCurrentText(info["default_rule"])

    def category_text(self) -> str:
        text = self.category_label.text().replace("Category:", "", 1).strip()
        return "" if text == "-" else text

    def warning_text(self) -> str:
        text = self.warning_label.text().replace("Warning:", "", 1).strip()
        return "" if text == "-" else text

    def get_medication(self) -> Medication:
        """Return the edited Medication object."""
        return Medication(
            medication_id=self.medication.medication_id,
            patient_id=self.medication.patient_id,
            patient_name=self.patient_input.text().strip(),
            medicine_name=self.medicine_combo.currentText().strip(),
            dosage=self.dosage_input.text().strip(),
            medication_date=self.date_edit.date().toString("yyyy-MM-dd"),
            medicine_time=self.time_input.time().toString("HH:mm"),
            taking_rule=self.rule_combo.currentText(),
            status=self.status_combo.currentText(),
            category=self.category_text(),
            warning=self.warning_text(),
        )


class CopyDayDialog(QDialog):
    """Dialog that asks for the target date used by the copy-day feature."""

    def __init__(self, source_date: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Copy Selected Day")
        self.setMinimumWidth(360)
        self.source_date = source_date
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Copy all medications from {self.source_date} to:"))

        self.target_date_edit = QDateEdit()
        self.target_date_edit.setCalendarPopup(True)
        self.target_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.target_date_edit.setDate(QDate.currentDate())
        layout.addWidget(self.target_date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def target_date(self) -> str:
        """Return the selected target date as YYYY-MM-DD."""
        return self.target_date_edit.date().toString("yyyy-MM-dd")


class MedicalHistoryDialog(QDialog):
    """Add or edit a patient's medical history record."""

    FIELD_LABELS = [
        ("diagnosis", "Diagnosis"),
        ("condition_notes", "Condition Notes"),
        ("allergies", "Allergies"),
        ("chronic_diseases", "Chronic Diseases"),
        ("past_surgeries", "Past Surgeries"),
        ("current_symptoms", "Current Symptoms"),
        ("doctor_notes", "Doctor Notes"),
    ]

    def __init__(self, record=None, parent=None) -> None:
        super().__init__(parent)
        self.record = record or {}
        self.inputs = {}
        self.setWindowTitle("Medical History")
        self.setMinimumSize(520, 560)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.diagnosis_input = QLineEdit()
        self.diagnosis_input.setText(self.record.get("diagnosis", ""))
        form.addRow("Diagnosis", self.diagnosis_input)
        self.inputs["diagnosis"] = self.diagnosis_input

        for key, label in self.FIELD_LABELS[1:]:
            text_edit = QTextEdit()
            text_edit.setMinimumHeight(64)
            text_edit.setPlainText(self.record.get(key, "") or "")
            form.addRow(label, text_edit)
            self.inputs[key] = text_edit

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(self.buttons)

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def get_data(self) -> Dict[str, str]:
        data = {"diagnosis": self.diagnosis_input.text().strip()}
        for key, widget in self.inputs.items():
            if key != "diagnosis":
                data[key] = widget.toPlainText().strip()
        return data


class ReminderDialog(QDialog):
    """Custom popup shown for reminder and missed-deadline notifications."""

    def __init__(
        self,
        title: str,
        medication: Medication,
        notification_manager,
        mark_taken_callback: Callable[[int], None],
        event_type: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.medication = medication
        self.notification_manager = notification_manager
        self.mark_taken_callback = mark_taken_callback
        self.event_type = event_type
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setWindowModality(Qt.NonModal)
        self._build_ui(title)
        self._apply_styles()

    def _build_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setObjectName("ReminderTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        details = QTextEdit()
        details.setReadOnly(True)
        details.setMinimumHeight(190)
        details.setText(self._details_text())
        layout.addWidget(details)

        warning = self.medication.warning_message()
        if warning:
            warning_label = QLabel(f"Warning: {warning}")
            warning_label.setObjectName("WarningText")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        button_row = QHBoxLayout()
        self.mark_taken_button = QPushButton("Mark As Taken")
        self.mute_button = QPushButton("Mute Sound")
        self.close_button = QPushButton("Close")

        self.mark_taken_button.clicked.connect(self.mark_as_taken)
        self.mute_button.clicked.connect(self.notification_manager.stop_current_sound)
        self.close_button.clicked.connect(self.close)

        button_row.addWidget(self.mark_taken_button)
        button_row.addWidget(self.mute_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    def _details_text(self) -> str:
        """Build reminder details for the popup body."""
        lines = [
            f"Patient: {self.medication.patient_name}",
            f"Medicine: {self.medication.medicine_name}",
            f"Dosage: {self.medication.dosage}",
            f"Date: {self.medication.medication_date}",
            f"Time: {self.medication.normalized_medicine_time()}",
            f"Taking rule: {self.medication.taking_rule}",
            f"Status: {self.medication.status}",
            f"Category: {self.medication.category or '-'}",
        ]

        if self.event_type == "missed":
            minutes_late = self.medication.minutes_late()
            hours = minutes_late // 60
            minutes = minutes_late % 60
            lines.append(f"How late: {hours}h {minutes}m")

        return "\n".join(lines)

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def mark_as_taken(self) -> None:
        """Mark the medication as taken from inside the popup."""
        if self.medication.medication_id is not None:
            self.mark_taken_callback(int(self.medication.medication_id))
        self.close()
