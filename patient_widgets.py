"""
Reusable patient-selection widgets for PharmaGuard.

These helpers keep patient search consistent across Add Medication,
Calendar / Daily View, Statistics, and User Profile.
"""

from typing import Iterable, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from user import User


class SearchablePatientComboBox(QComboBox):
    """Editable patient combo box with contains-style completion."""

    ALL_PATIENTS_TEXT = "All Patients"

    def __init__(self, include_all: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.include_all = include_all
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMinimumHeight(34)
        self.setMinimumWidth(240)
        self.lineEdit().setPlaceholderText("Search patient name or username")
        self._configure_completer()

    def _configure_completer(self) -> None:
        completer = QCompleter(self.model(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

    def populate(
        self,
        users: Iterable[User],
        selected_patient_id: Optional[int] = None,
        keep_current_text: bool = False,
    ) -> None:
        """Load patient users while preserving a valid selection when possible."""
        current_text = self.currentText().strip() if keep_current_text else ""
        self.blockSignals(True)
        self.clear()

        if self.include_all:
            self.addItem(self.ALL_PATIENTS_TEXT, None)

        for user in users:
            if user.role == User.ROLE_USER:
                self.addItem(user.display_name(), user.user_id)

        if selected_patient_id is not None:
            index = self.findData(selected_patient_id)
            if index >= 0:
                self.setCurrentIndex(index)
            elif self.count() > 0:
                self.setCurrentIndex(0)
        elif current_text:
            index = self.findText(current_text, Qt.MatchFixedString)
            if index >= 0:
                self.setCurrentIndex(index)
            else:
                self.setEditText(current_text)
        elif self.count() > 0:
            self.setCurrentIndex(0)

        self._configure_completer()
        self.blockSignals(False)

    def selected_patient_id(self) -> Tuple[bool, Optional[int]]:
        """
        Return (is_valid, patient_id).

        patient_id is None only when the combo is configured with All Patients
        and the All Patients option is selected.
        """
        typed_text = self.currentText().strip()
        if not typed_text:
            return False, None

        for index in range(self.count()):
            if self.itemText(index).strip().lower() == typed_text.lower():
                previous_block_state = self.blockSignals(True)
                self.setCurrentIndex(index)
                self.blockSignals(previous_block_state)
                return True, self.itemData(index)

        return False, None

    def warn_if_invalid(self, parent=None) -> bool:
        """Show the shared friendly warning when typed text is not a real option."""
        if self.selected_patient_id()[0]:
            return True
        if self.currentText().strip():
            QMessageBox.warning(parent or self, "Invalid Patient", "Please select a valid patient from the list.")
        return False


class PatientMultiSelectWidget(QWidget):
    """Admin statistics selector that supports All, one, or many patients."""

    selection_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.all_patients_checkbox = QCheckBox(SearchablePatientComboBox.ALL_PATIENTS_TEXT)
        self.all_patients_checkbox.setChecked(False)

        self.patient_combo = SearchablePatientComboBox(include_all=False)
        self.patient_combo.setToolTip("Search patient by first name, last name, full name, or username.")
        self.add_patient_button = QPushButton("Add Patient")
        self.add_patient_button.setToolTip("Add the selected patient to the statistics filter.")

        top_row.addWidget(self.all_patients_checkbox)
        top_row.addWidget(QLabel("Find Patient"))
        top_row.addWidget(self.patient_combo, stretch=1)
        top_row.addWidget(self.add_patient_button)
        layout.addLayout(top_row)

        self.patient_list = QListWidget()
        self.patient_list.setMinimumHeight(115)
        layout.addWidget(self.patient_list)

        self.all_patients_checkbox.toggled.connect(self.on_all_patients_toggled)
        self.add_patient_button.clicked.connect(self.add_selected_patient)
        self.patient_list.itemChanged.connect(self.on_patient_item_changed)

    def populate(
        self,
        users: Iterable[User],
        selected_patient_ids: Optional[List[int]] = None,
        all_selected: bool = False,
    ) -> None:
        """Load patients into the searchable combo and checkbox list."""
        selected_ids = set(selected_patient_ids or [])
        users = [user for user in users if user.role == User.ROLE_USER]

        self._loading = True
        self.patient_combo.populate(users)
        self.patient_list.clear()

        for user in users:
            item = QListWidgetItem(user.display_name())
            item.setData(Qt.UserRole, user.user_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if user.user_id in selected_ids else Qt.Unchecked)
            self.patient_list.addItem(item)

        self.all_patients_checkbox.setChecked(all_selected)
        self._loading = False

    def on_all_patients_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked:
            self._loading = True
            for index in range(self.patient_list.count()):
                self.patient_list.item(index).setCheckState(Qt.Unchecked)
            self._loading = False
        self.selection_changed.emit()

    def on_patient_item_changed(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        if item.checkState() == Qt.Checked:
            self._loading = True
            self.all_patients_checkbox.setChecked(False)
            self._loading = False
        self.selection_changed.emit()

    def add_selected_patient(self) -> None:
        """Check the patient chosen in the searchable combo."""
        is_valid, patient_id = self.patient_combo.selected_patient_id()
        if not is_valid or patient_id is None:
            QMessageBox.warning(self, "Invalid Patient", "Please select a valid patient from the list.")
            return

        self._loading = True
        self.all_patients_checkbox.setChecked(False)
        for index in range(self.patient_list.count()):
            item = self.patient_list.item(index)
            if item.data(Qt.UserRole) == patient_id:
                item.setCheckState(Qt.Checked)
                self.patient_list.setCurrentItem(item)
                break
        self._loading = False
        self.selection_changed.emit()

    def is_all_selected(self) -> bool:
        """Return True when All Patients is active."""
        return self.all_patients_checkbox.isChecked()

    def selected_patient_ids(self) -> List[int]:
        """Return all checked patient ids."""
        selected_ids: List[int] = []
        for index in range(self.patient_list.count()):
            item = self.patient_list.item(index)
            if item.checkState() == Qt.Checked:
                selected_ids.append(int(item.data(Qt.UserRole)))
        return selected_ids
