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
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

from medication import Medication, format_duration
from styles import DUE, OVERDUE, current_app_style, mono_font

# The medication field labels, in one place so the Add Medication tab in ui.py
# and the Edit dialog here cannot drift apart. Five of these were bilingual and
# two were English-only, which reads as an unfinished translation rather than a
# choice; the users are a Georgian clinic, so the set is completed rather than
# stripped. (label, attribute name on EditMedicationDialog)
FIELD_LABELS = [
    ("Patient / პაციენტი", "patient_input"),
    ("Medicine / წამალი", "medicine_combo"),
    ("Dosage / დოზა", "dosage_input"),
    ("Date / თარიღი", "date_edit"),
    ("Time / დრო", "time_input"),
    ("Taking rule / მიღების წესი", "rule_combo"),
    ("Status / სტატუსი", "status_combo"),
]


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
        self.category_label.setObjectName("MutedText")
        # The warning is the clinically load-bearing line here. It used to render
        # in the same plain body text as the category, so "Do not exceed 8 puffs
        # daily" carried exactly as much weight as "Bronchodilator".
        self.warning_label = QLabel("Warning: -")
        self.warning_label.setObjectName("WarningText")
        self.warning_label.setWordWrap(True)

        for label, widget in FIELD_LABELS:
            form.addRow(label, getattr(self, widget))
        form.addRow(self.category_label)
        form.addRow(self.warning_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setObjectName("PrimaryButton")
        self.buttons.button(QDialogButtonBox.Save).setDefault(True)
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
            self.warning_label.setText(self.medication.warning or "No specific warning recorded.")
            return

        self.category_label.setText(f"Category: {info['category']}")
        self.warning_label.setText(info["warning"] or "No specific warning recorded.")
        self.rule_combo.setCurrentText(info["default_rule"])

    def category_text(self) -> str:
        text = self.category_label.text().replace("Category:", "", 1).strip()
        return "" if text == "-" else text

    def warning_text(self) -> str:
        text = self.warning_label.text().strip()
        return "" if text in ("-", "No specific warning recorded.") else text

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
        buttons.button(QDialogButtonBox.Ok).setObjectName("PrimaryButton")
        buttons.button(QDialogButtonBox.Ok).setDefault(True)
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
        self.buttons.button(QDialogButtonBox.Save).setObjectName("PrimaryButton")
        self.buttons.button(QDialogButtonBox.Save).setDefault(True)
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

    # Each scheduler event gets its own headline and signal colour, so a missed
    # dose never looks like a ten-minute heads-up. The word carries the meaning
    # as well as the colour, because the colour alone is not readable by
    # everyone and does not survive a greyscale screenshot.
    EVENT_BANNERS = {
        "ten_minutes": ("Due in 10 minutes", DUE),
        "exact_time": ("Due now", DUE),
        "missed": ("Missed", OVERDUE),
    }

    def _build_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        headline, kind = self.EVENT_BANNERS.get(self.event_type, (title, DUE))
        banner = QLabel(self._banner_text(headline))
        banner.setObjectName("ReminderBanner")
        # Read back by the stylesheet as QLabel#ReminderBanner[kind="..."].
        banner.setProperty("kind", kind)
        banner.setWordWrap(True)
        layout.addWidget(banner)

        # What the patient actually acts on, at the size that says so.
        medicine = QLabel(f"{self.medication.medicine_name} {self.medication.dosage}".strip())
        medicine.setObjectName("ReminderMedicine")
        medicine.setWordWrap(True)
        layout.addWidget(medicine)

        time_label = QLabel(self.medication.normalized_medicine_time())
        time_label.setObjectName("ReminderTime")
        layout.addWidget(time_label)

        layout.addLayout(self._detail_grid())

        warning = self.medication.warning_message()
        if warning:
            warning_label = QLabel(warning)
            warning_label.setObjectName("WarningText")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        layout.addStretch()

        button_row = QHBoxLayout()
        self.mark_taken_button = QPushButton("Mark As Taken")
        # The one action this popup exists to offer. Everything else is quiet.
        self.mark_taken_button.setObjectName("PrimaryButton")
        self.mark_taken_button.setDefault(True)
        self.mute_button = QPushButton("Mute Sound")
        self.close_button = QPushButton("Close")

        self.mark_taken_button.clicked.connect(self.mark_as_taken)
        self.mute_button.clicked.connect(self.notification_manager.stop_current_sound)
        self.close_button.clicked.connect(self.close)

        button_row.addWidget(self.mark_taken_button, stretch=1)
        button_row.addWidget(self.mute_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    def _banner_text(self, headline: str) -> str:
        """Headline plus, for a missed dose, how late it now is."""
        if self.event_type != "missed":
            return headline
        return f"{headline} by {format_duration(self.medication.minutes_late())}"

    def _detail_grid(self) -> QGridLayout:
        """Secondary fields as legend-over-value pairs rather than a text dump."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)

        fields = [
            ("PATIENT", self.medication.patient_name),
            ("DATE", self.medication.medication_date),
            ("TAKING RULE", self.medication.taking_rule),
            ("CATEGORY", self.medication.category or "-"),
        ]
        for index, (legend, value) in enumerate(fields):
            legend_label = QLabel(legend)
            legend_label.setObjectName("CardTitle")
            value_label = QLabel(str(value))
            value_label.setWordWrap(True)
            if legend == "DATE":
                value_label.setFont(mono_font())
            grid.addWidget(legend_label, (index // 2) * 2, index % 2)
            grid.addWidget(value_label, (index // 2) * 2 + 1, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return grid

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def mark_as_taken(self) -> None:
        """Mark the medication as taken from inside the popup."""
        if self.medication.medication_id is not None:
            self.mark_taken_callback(int(self.medication.medication_id))
        self.close()
