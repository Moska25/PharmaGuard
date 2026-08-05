"""
Statistics tab for PharmaGuard.

The widget keeps filtering simple: one date-range selector, one patient filter,
one sort dropdown, summary cards, separate chart containers, and a table.
Everything is placed inside a scroll area so the content never overlaps.
"""

from collections import Counter
from datetime import date, timedelta
from calendar import monthrange
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from database import DatabaseManager
from medication import MEDICATION_SORT_OPTIONS, Medication, sort_medications
from patient_widgets import PatientMultiSelectWidget
from styles import current_app_style, tokens
from user import User


class StatisticsWindow(QWidget):
    """Shows filtered medication statistics and charts."""

    RANGE_TODAY = "Today"
    RANGE_WEEK = "This Week"
    RANGE_MONTH = "This Month"
    RANGE_YEAR = "This Year"
    RANGE_CUSTOM = "Custom Range"
    ALL_PATIENTS = "All Patients"

    TABLE_HEADERS = ["Date", "Time", "Patient", "Medicine", "Dosage", "Status"]

    def __init__(self, database_manager: DatabaseManager, current_user: Optional[User] = None, parent=None) -> None:
        super().__init__(parent)
        self.database_manager = database_manager
        self.current_user = current_user
        self.selected_date = QDate.currentDate().toString("yyyy-MM-dd")
        self._build_ui()
        # Defaults before the signal wiring, so construction does not fire a
        # refresh against a selector that has no patients loaded yet.
        self._apply_default_view()
        self._connect_events()
        self.update_date_edit_visibility()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        outer_layout.addWidget(self.scroll_area)

        content = QWidget()
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        self.title_label = QLabel("Statistics")
        self.title_label.setObjectName("StatisticsTitle")
        layout.addWidget(self.title_label)

        layout.addWidget(self._create_filter_group())

        self.active_filter_label = QLabel("Showing statistics for Today - No patients selected")
        self.active_filter_label.setObjectName("ActiveFilter")
        layout.addWidget(self.active_filter_label)

        self.empty_state_label = QLabel("No medication data found for this filter.")
        self.empty_state_label.setObjectName("EmptyState")
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_label.hide()
        layout.addWidget(self.empty_state_label)

        summary_group = QGroupBox("Summary")
        summary_layout = QGridLayout(summary_group)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(12)
        self._add_summary_cards(summary_layout)
        layout.addWidget(summary_group)

        charts_group = QGroupBox("Charts")
        charts_layout = QGridLayout(charts_group)
        charts_layout.setHorizontalSpacing(14)
        charts_layout.setVerticalSpacing(14)

        self.taken_canvas = self._create_chart_container(charts_layout, "Taken vs Not Taken", 0, 0, 1, 2)
        self.daily_canvas = self._create_chart_container(charts_layout, "Daily Medication Count", 1, 0, 1, 2)
        layout.addWidget(charts_group)

        table_group = QGroupBox("Medication Table")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(220)
        table_layout.addWidget(self.table)
        layout.addWidget(table_group)

        self._apply_styles()

    def _create_filter_group(self) -> QGroupBox:
        filter_group = QGroupBox("Date Range")
        grid = QGridLayout(filter_group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(
            [
                self.RANGE_TODAY,
                self.RANGE_WEEK,
                self.RANGE_MONTH,
                self.RANGE_YEAR,
                self.RANGE_CUSTOM,
            ]
        )

        self.patient_filter_label = QLabel("Patients")
        self.patient_selector = PatientMultiSelectWidget()

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(MEDICATION_SORT_OPTIONS)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Refresh statistics using the selected filters.")

        self.start_date_label = QLabel("Start Date")
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setDate(QDate.currentDate())

        self.end_date_label = QLabel("End Date")
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())

        grid.addWidget(QLabel("Date Range"), 0, 0)
        grid.addWidget(self.date_range_combo, 0, 1)
        grid.addWidget(QLabel("Sort"), 0, 2)
        grid.addWidget(self.sort_combo, 0, 3)
        grid.addWidget(self.refresh_button, 0, 4)

        grid.addWidget(self.patient_filter_label, 1, 0)
        grid.addWidget(self.patient_selector, 1, 1, 1, 4)

        grid.addWidget(self.start_date_label, 2, 0)
        grid.addWidget(self.start_date_edit, 2, 1)
        grid.addWidget(self.end_date_label, 2, 2)
        grid.addWidget(self.end_date_edit, 2, 3)

        return filter_group

    def _add_summary_cards(self, layout: QGridLayout) -> None:
        self.card_labels: Dict[str, QLabel] = {}
        cards = [
            ("total", "Total"),
            ("taken", "Taken"),
            ("not_taken", "Not Taken"),
            ("overdue", "Overdue"),
            ("completion", "Completion %"),
        ]

        for index, (key, title) in enumerate(cards):
            card = QWidget()
            card.setObjectName("StatisticsCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(4)

            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            value_label = QLabel("0")
            value_label.setObjectName("CardValue")

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            self.card_labels[key] = value_label
            layout.addWidget(card, index // 3, index % 3)

    def _create_chart_container(
        self,
        layout: QGridLayout,
        title: str,
        row: int,
        column: int,
        row_span: int = 1,
        column_span: int = 1,
    ) -> FigureCanvas:
        container = QWidget()
        container.setObjectName("ChartCard")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("ChartTitle")
        container_layout.addWidget(title_label)

        figure = Figure(figsize=(4.8, 2.6), dpi=100)
        figure.patch.set_facecolor(tokens()["panel"])
        canvas = FigureCanvas(figure)
        canvas.setMinimumHeight(230)
        container_layout.addWidget(canvas)
        layout.addWidget(container, row, column, row_span, column_span)
        return canvas

    def _apply_default_view(self) -> None:
        """
        Open on All Patients over This Month rather than on an empty tab.

        The tab used to land on Today with nothing selected, so the first thing
        anyone saw was five zeros, two blank charts and an instruction to go and
        pick a filter. `tools/capture_screenshots.py` had to set this state by
        hand before it could take a usable screenshot, which is a good sign the
        default was wrong rather than the screenshot.
        """
        self.date_range_combo.setCurrentText(self.RANGE_MONTH)
        self.patient_selector.all_patients_checkbox.setChecked(True)

    def _connect_events(self) -> None:
        self.date_range_combo.currentTextChanged.connect(self.on_date_range_changed)
        self.patient_selector.selection_changed.connect(lambda: self.refresh_current_view())
        self.sort_combo.currentTextChanged.connect(lambda: self.refresh_current_view())
        self.start_date_edit.dateChanged.connect(lambda: self.refresh_current_view())
        self.end_date_edit.dateChanged.connect(lambda: self.refresh_current_view())
        self.refresh_button.clicked.connect(lambda: self.update_statistics())

    def _apply_styles(self) -> None:
        self.setStyleSheet(current_app_style())

    def update_statistics(self, selected_date: str = "") -> None:
        """Refresh the statistics tab. MainWindow calls this after changes."""
        if selected_date:
            self.selected_date = selected_date
        self.refresh_patient_options()
        self.update_date_edit_visibility()
        self.refresh_current_view()

    def refresh_patient_options(self) -> None:
        selected_ids = self.patient_selector.selected_patient_ids()
        all_selected = self.patient_selector.is_all_selected()
        users = [user for user in self.database_manager.list_users() if user.role == User.ROLE_USER]

        if self.current_user and self.current_user.role == User.ROLE_USER:
            self.patient_filter_label.setVisible(False)
            self.patient_selector.setVisible(False)
            return

        self.patient_filter_label.setVisible(True)
        self.patient_selector.setVisible(True)
        self.patient_selector.populate(
            users,
            selected_patient_ids=selected_ids,
            all_selected=all_selected,
        )

    def on_date_range_changed(self) -> None:
        self.update_date_edit_visibility()
        self.refresh_current_view()

    def update_date_edit_visibility(self) -> None:
        show_custom = self.date_range_combo.currentText() == self.RANGE_CUSTOM
        for widget in [
            self.start_date_label,
            self.start_date_edit,
            self.end_date_label,
            self.end_date_edit,
        ]:
            widget.setVisible(show_custom)

    def selected_range(self) -> Tuple[date, date, str]:
        today = date.today()
        option = self.date_range_combo.currentText()

        if option == self.RANGE_WEEK:
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return start, end, self.RANGE_WEEK

        if option == self.RANGE_MONTH:
            last_day = monthrange(today.year, today.month)[1]
            return date(today.year, today.month, 1), date(today.year, today.month, last_day), self.RANGE_MONTH

        if option == self.RANGE_YEAR:
            return date(today.year, 1, 1), date(today.year, 12, 31), self.RANGE_YEAR

        if option == self.RANGE_CUSTOM:
            start = self.start_date_edit.date().toPyDate()
            end = self.end_date_edit.date().toPyDate()
            if start > end:
                start, end = end, start
            return start, end, f"Custom Range ({start.isoformat()} to {end.isoformat()})"

        return today, today, self.RANGE_TODAY

    def refresh_current_view(self) -> None:
        start, end, range_label = self.selected_range()
        patient_ids = None
        if self.current_user and self.current_user.role == User.ROLE_USER:
            patient_ids = [self.current_user.user_id]
            patient_label = self.current_user.full_name
        else:
            if self.patient_selector.is_all_selected():
                patient_label = self.ALL_PATIENTS
            else:
                patient_ids = self.patient_selector.selected_patient_ids()
                if not patient_ids:
                    self.active_filter_label.setText(f"Showing statistics for {range_label} - No patients selected")
                    self.empty_state_label.setText(
                        "Please select All Patients or choose one or more patients to view statistics."
                    )
                    self.empty_state_label.setVisible(True)
                    self.update_summary_cards(self.calculate_statistics([]))
                    self.update_charts([])
                    self.update_table([])
                    return
                patient_label = self.patient_selection_label(patient_ids)

        medications = self.database_manager.load_medications_for_range(
            start.isoformat(),
            end.isoformat(),
        )
        if patient_ids is not None:
            selected_id_set = set(patient_ids)
            medications = [item for item in medications if item.patient_id in selected_id_set]
        medications = sort_medications(medications, self.sort_combo.currentText())
        stats = self.calculate_statistics(medications)

        self.active_filter_label.setText(f"Showing statistics for {range_label} · {patient_label}")
        self.empty_state_label.setText("No medication data found for this filter.")
        self.empty_state_label.setVisible(len(medications) == 0)
        self.update_summary_cards(stats)
        self.update_charts(medications)
        self.update_table(medications)

    def patient_selection_label(self, patient_ids: List[int]) -> str:
        """Build a readable label for selected statistics patients."""
        users_by_id = {user.user_id: user for user in self.database_manager.list_users()}
        if len(patient_ids) == 1:
            user = users_by_id.get(patient_ids[0])
            return user.full_name if user else "1 Selected Patient"
        return f"{len(patient_ids)} Selected Patients"

    def calculate_statistics(self, medications: List[Medication]) -> Dict[str, int]:
        total = len(medications)
        taken = sum(1 for item in medications if item.status == Medication.TAKEN)
        not_taken = sum(1 for item in medications if item.status == Medication.NOT_TAKEN)
        overdue = sum(1 for item in medications if item.is_overdue())
        completion = round((taken / total) * 100) if total else 0
        return {
            "total": total,
            "taken": taken,
            "not_taken": not_taken,
            "overdue": overdue,
            "completion": completion,
        }

    def update_summary_cards(self, stats: Dict[str, int]) -> None:
        self.card_labels["total"].setText(str(stats["total"]))
        self.card_labels["taken"].setText(str(stats["taken"]))
        self.card_labels["not_taken"].setText(str(stats["not_taken"]))
        self.card_labels["overdue"].setText(str(stats["overdue"]))
        self.card_labels["completion"].setText(f"{stats['completion']}%")

    def update_charts(self, medications: List[Medication]) -> None:
        taken = sum(1 for item in medications if item.status == Medication.TAKEN)
        not_taken = sum(1 for item in medications if item.status == Medication.NOT_TAKEN)

        palette = tokens()
        self.draw_pie_chart(
            self.taken_canvas,
            ["Taken", "Not Taken"],
            [taken, not_taken],
            [palette["signal_taken"], palette["signal_overdue"]],
        )
        self.draw_daily_count_chart(self.daily_canvas, medications)

    def draw_pie_chart(self, canvas: FigureCanvas, labels: List[str], values: List[int], colors: List[str]) -> None:
        figure = canvas.figure
        figure.clear()
        palette = tokens()
        figure.patch.set_facecolor(palette["panel"])
        axis = figure.add_subplot(111)
        axis.set_facecolor(palette["panel"])
        if sum(values) == 0:
            axis.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                fontsize=11,
                color=palette["muted"],
            )
            axis.set_axis_off()
        else:
            axis.pie(
                values,
                labels=labels,
                autopct="%1.0f%%",
                startangle=90,
                colors=colors,
                textprops={"fontsize": 9, "color": palette["text"]},
            )
            axis.axis("equal")
        figure.tight_layout()
        canvas.draw()

    def draw_daily_count_chart(self, canvas: FigureCanvas, medications: List[Medication]) -> None:
        figure = canvas.figure
        figure.clear()
        palette = tokens()
        figure.patch.set_facecolor(palette["panel"])
        axis = figure.add_subplot(111)
        axis.set_facecolor(palette["panel"])
        counts = Counter(item.medication_date for item in medications)

        if not counts:
            axis.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                fontsize=11,
                color=palette["muted"],
            )
            axis.set_axis_off()
        else:
            dates = sorted(counts)
            values = [counts[item] for item in dates]
            axis.bar(dates, values, color=palette["accent"])
            axis.tick_params(axis="x", rotation=30, labelsize=8, colors=palette["muted"])
            axis.tick_params(axis="y", labelsize=8, colors=palette["muted"])
            axis.set_ylabel("Count")
            axis.yaxis.label.set_color(palette["muted"])
            for spine in axis.spines.values():
                spine.set_color(palette["border"])

        figure.tight_layout()
        canvas.draw()

    def update_table(self, medications: List[Medication]) -> None:
        self.table.setRowCount(len(medications))

        for row_index, medication in enumerate(medications):
            values = [
                medication.medication_date,
                medication.normalized_medicine_time(),
                medication.patient_name,
                medication.medicine_name,
                medication.dosage,
                medication.status,
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column_index in [0, 1, 5]:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column_index, item)

        self.table.resizeColumnsToContents()
