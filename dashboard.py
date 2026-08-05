"""
Dashboard tab for PharmaGuard.

The dashboard gives admins a global overview and patient users a personal
today view with a checklist.
"""

from datetime import date, datetime
from typing import Callable, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database import DatabaseManager
from medication import Medication
from patient_widgets import SearchablePatientComboBox
from styles import current_app_style
from user import User


class DashboardTab(QWidget):
    """Role-aware dashboard for admins and patient users."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        current_user: User,
        mark_taken_callback: Optional[Callable[[int], None]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.database_manager = database_manager
        self.current_user = current_user
        self.mark_taken_callback = mark_taken_callback
        self.card_labels = {}
        self.content_layout = None
        self.admin_summary_patient_id = None
        self._build_ui()

    def is_admin(self) -> bool:
        """Return True when the logged-in user is admin."""
        return self.current_user.role == User.ROLE_ADMIN

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(self.scroll_area)

        content = QWidget()
        self.scroll_area.setWidget(content)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(18, 18, 18, 18)
        self.content_layout.setSpacing(16)

        self.title_label = QLabel("Dashboard")
        self.title_label.setObjectName("DashboardTitle")
        self.content_layout.addWidget(self.title_label)

        self.summary_group = QGroupBox("Overview")
        self.summary_layout = QGridLayout(self.summary_group)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(12)
        # Equal columns, so a short final row of tiles still lines up with the
        # row above it instead of the last tile stretching to fill the gap.
        for column in range(3):
            self.summary_layout.setColumnStretch(column, 1)
        self.content_layout.addWidget(self.summary_group)

        self.main_sections_layout = QVBoxLayout()
        self.main_sections_layout.setSpacing(14)
        self.content_layout.addLayout(self.main_sections_layout)
        self.content_layout.addStretch()

        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def refresh(self) -> None:
        """Refresh all dashboard cards and lists."""
        self.clear_layout(self.summary_layout)
        self.clear_layout(self.main_sections_layout)
        self.card_labels.clear()

        if self.is_admin():
            self.title_label.setText("Dashboard - Admin Overview")
            self.render_admin_dashboard()
        else:
            self.title_label.setText(f"Dashboard - {self.current_user.full_name}")
            self.render_user_dashboard()

    def render_admin_dashboard(self) -> None:
        """Render hospital/doctor overview for admin."""
        today_text = date.today().isoformat()
        today_medications = self.database_manager.load_medications_by_date(today_text)
        all_medications = self.database_manager.load_all_medications()
        patients = [user for user in self.database_manager.list_users() if user.role == User.ROLE_USER]

        missed = sorted(
            [item for item in today_medications if item.is_overdue()],
            key=lambda item: item.scheduled_datetime(),
            reverse=True,
        )
        upcoming = self.upcoming_medications(today_medications)
        taken = sum(1 for item in today_medications if item.status == Medication.TAKEN)
        taken_percent = round((taken / len(today_medications)) * 100) if today_medications else 0

        cards = [
            ("Today Total Medications", len(today_medications)),
            ("Missed Medications", len(missed)),
            ("Upcoming Today", len(upcoming)),
            ("Total Patients", len(patients)),
            ("Taken Today %", f"{taken_percent}%"),
        ]
        self.add_cards(cards)

        self.main_sections_layout.addWidget(
            self.create_medication_list_group(
                "Next 5 Upcoming Today",
                upcoming[:5],
                show_patient=True,
                empty_text="Nothing further due today across all patients.",
            )
        )
        self.main_sections_layout.addWidget(
            self.create_medication_list_group(
                "Missed Medications",
                missed[:5],
                show_patient=True,
                empty_text="No missed doses today. Overdue doses appear here as soon as one passes its time.",
            )
        )
        self.main_sections_layout.addWidget(self.create_admin_medical_summary_group(patients))

        if not all_medications:
            self.main_sections_layout.addWidget(
                self.empty_message(
                    "No medications recorded yet. Use the Add Medication tab to schedule the first dose."
                )
            )

    def render_user_dashboard(self) -> None:
        """Render patient personal dashboard."""
        today_text = date.today().isoformat()
        medications = self.database_manager.load_medications_by_date(today_text, self.current_user.user_id)
        missed = [item for item in medications if item.is_overdue()]
        taken = [item for item in medications if item.status == Medication.TAKEN]
        not_taken = [item for item in medications if item.status == Medication.NOT_TAKEN]
        upcoming = self.upcoming_medications(medications)
        next_medication = upcoming[0] if upcoming else None
        progress = round((len(taken) / len(medications)) * 100) if medications else 0

        cards = [
            ("My Medications Today", len(medications)),
            ("Taken Today", len(taken)),
            ("Not Taken Today", len(not_taken)),
            ("Missed Today", len(missed)),
            ("Next Medicine", next_medication.medicine_name if next_medication else "-"),
            ("Today Progress %", f"{progress}%"),
        ]
        self.add_cards(cards)

        self.main_sections_layout.addWidget(self.create_user_medical_summary_group())
        self.main_sections_layout.addWidget(self.create_next_medication_card(next_medication))
        self.main_sections_layout.addWidget(self.create_checklist_group(medications))

    def add_cards(self, cards: List[tuple]) -> None:
        """
        Add metric tiles in a responsive grid.

        The tiles used to carry a decorative "+ ! > # %" glyph cycled by index,
        so the symbol had no relationship to the number beside it. A glyph that
        means nothing is noise on a clinical readout, so the tile is now just
        the legend and the figure.
        """
        for index, (title, value) in enumerate(cards):
            card = QWidget()
            card.setObjectName("DashboardCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 16)
            layout.setSpacing(6)

            title_label = QLabel(str(title).upper())
            title_label.setObjectName("CardTitle")
            value_label = QLabel(str(value))
            value_label.setObjectName("CardValue")
            value_label.setWordWrap(True)

            layout.addWidget(title_label)
            layout.addWidget(value_label)
            self.summary_layout.addWidget(card, index // 3, index % 3)

    def upcoming_medications(self, medications: List[Medication]) -> List[Medication]:
        """Return not-taken medications scheduled later today."""
        now = datetime.now()
        return sorted(
            [
                item
                for item in medications
                if item.status == Medication.NOT_TAKEN and item.scheduled_datetime() >= now
            ],
            key=lambda item: item.scheduled_datetime(),
        )

    def create_next_medication_card(self, medication: Optional[Medication]) -> QGroupBox:
        """Create the user's next-medication card."""
        group = QGroupBox("Next Medication")
        layout = QVBoxLayout(group)

        if medication is None:
            layout.addWidget(self.empty_message("Nothing further due today. Your next dose appears here once one is scheduled."))
            return group

        title = QLabel(f"{medication.medicine_name} - {medication.dosage}")
        title.setObjectName("ItemTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Time: {medication.normalized_medicine_time()}"))
        layout.addWidget(QLabel(f"Taking rule: {medication.taking_rule}"))
        if medication.warning_message():
            warning = QLabel(f"Warning: {medication.warning_message()}")
            warning.setObjectName("WarningText")
            warning.setWordWrap(True)
            layout.addWidget(warning)
        return group

    def create_admin_medical_summary_group(self, patients: List[User]) -> QGroupBox:
        group = QGroupBox("Patient Medical Summary")
        layout = QVBoxLayout(group)

        if not patients:
            layout.addWidget(self.empty_message("No patient accounts yet. Create one from the User Profile tab."))
            return group

        row = QHBoxLayout()
        combo = SearchablePatientComboBox(include_all=False)
        combo.populate(patients, selected_patient_id=self.admin_summary_patient_id)
        is_valid, patient_id = combo.selected_patient_id()
        if is_valid:
            self.admin_summary_patient_id = patient_id
        combo.currentTextChanged.connect(lambda: self.on_admin_summary_patient_changed(combo))
        row.addWidget(QLabel("Patient"))
        row.addWidget(combo, stretch=1)
        layout.addLayout(row)

        layout.addWidget(self.medical_summary_card(self.admin_summary_patient_id))
        return group

    def create_user_medical_summary_group(self) -> QGroupBox:
        group = QGroupBox("My Medical Summary")
        layout = QVBoxLayout(group)
        layout.addWidget(self.medical_summary_card(self.current_user.user_id))
        return group

    def medical_summary_card(self, patient_id: Optional[int]) -> QWidget:
        card = QWidget()
        card.setObjectName("DashboardCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        summary = self.database_manager.get_latest_medical_summary(int(patient_id)) if patient_id else {}

        if not summary:
            layout.addWidget(self.empty_message("No medical history recorded. Add a diagnosis for this patient from the User Profile tab."))
            return card

        rows = [
            ("Latest diagnosis", summary.get("diagnosis") or "-"),
            ("Allergies", summary.get("allergies") or "-"),
            ("Chronic diseases", summary.get("chronic_diseases") or "-"),
        ]
        for label, value in rows:
            title = QLabel(label)
            title.setObjectName("CardTitle")
            text = QLabel(str(value))
            text.setObjectName("ItemTitle")
            text.setWordWrap(True)
            layout.addWidget(title)
            layout.addWidget(text)
        return card

    def on_admin_summary_patient_changed(self, combo: SearchablePatientComboBox) -> None:
        is_valid, patient_id = combo.selected_patient_id()
        if is_valid and patient_id:
            self.admin_summary_patient_id = patient_id
            self.refresh()

    def create_checklist_group(self, medications: List[Medication]) -> QGroupBox:
        """Create today's checklist for patient users."""
        group = QGroupBox("Today Medication Checklist")
        layout = QVBoxLayout(group)

        if not medications:
            layout.addWidget(self.empty_message("No doses scheduled for today. Your administrator sets your schedule."))
            return group

        for medication in sorted(medications, key=lambda item: item.normalized_medicine_time()):
            row = QHBoxLayout()
            text = QLabel(
                f"{medication.normalized_medicine_time()}  |  {medication.medicine_name}  |  "
                f"{medication.dosage}  |  {medication.status}"
            )
            text.setObjectName("ItemTitle" if medication.status != Medication.TAKEN else "MutedText")
            text.setWordWrap(True)
            row.addWidget(text, stretch=1)

            button = QPushButton("Mark Taken")
            button.setEnabled(medication.status != Medication.TAKEN)
            button.setToolTip("Mark this medication as taken.")
            if medication.medication_id is not None:
                button.clicked.connect(
                    lambda _, med_id=medication.medication_id: self.mark_taken_callback
                    and self.mark_taken_callback(med_id)
                )
            row.addWidget(button)
            layout.addLayout(row)

        return group

    def create_medication_list_group(
        self,
        title: str,
        medications: List[Medication],
        show_patient: bool = False,
        empty_text: str = "Nothing to show here yet.",
    ) -> QGroupBox:
        """Create a simple dashboard medication list."""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)

        if not medications:
            layout.addWidget(self.empty_message(empty_text))
            return group

        for medication in medications:
            label_text = (
                f"{medication.normalized_medicine_time()}  |  {medication.medicine_name}  |  "
                f"{medication.dosage}  |  {medication.status}"
            )
            if show_patient:
                label_text = f"{medication.patient_name}  |  {label_text}"
            label = QLabel(label_text)
            label.setObjectName("ItemTitle")
            label.setWordWrap(True)
            layout.addWidget(label)
        return group

    def empty_message(self, text: str) -> QLabel:
        """Create an empty-state label. The text must say what to do next."""
        label = QLabel(text)
        label.setObjectName("EmptyState")
        label.setWordWrap(True)
        return label

    def clear_layout(self, layout) -> None:
        """Remove child widgets/layouts before dashboard refresh."""
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()
            if child_layout is not None:
                self.clear_layout(child_layout)
            if widget is not None:
                widget.deleteLater()
