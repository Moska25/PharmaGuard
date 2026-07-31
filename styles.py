"""Centralized PharmaGuard styles."""

from PyQt5.QtWidgets import QApplication


LIGHT_STYLE = """
QWidget {
    background-color: #f2f5f9;
    color: #202631;
    font-family: Segoe UI, Arial, sans-serif;
    font-size: 10.5pt;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #d8e1ea;
    border-radius: 10px;
    margin-top: 12px;
    padding: 16px;
    color: #18324a;
    font-weight: 700;
}
QGroupBox#LoginCard {
    padding: 22px;
    margin-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
}
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit, QListWidget {
    background-color: #ffffff;
    border: 1px solid #c8d3df;
    border-radius: 8px;
    min-height: 30px;
    padding: 7px 10px;
    selection-background-color: #3B82F6;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QTextEdit:focus {
    border: 1px solid #3B82F6;
}
QPushButton {
    background-color: #3B82F6;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 700;
}
QPushButton:hover {
    background-color: #2563EB;
}
QPushButton:pressed {
    background-color: #1d4ed8;
}
QPushButton:disabled {
    background-color: #cbd5e1;
    color: #64748b;
}
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #d8e1ea;
    border-radius: 10px;
    gridline-color: #e3e9f0;
    selection-background-color: #dbeafe;
    selection-color: #102a43;
}
QHeaderView::section {
    background-color: #e8eef6;
    color: #1f3347;
    border: none;
    border-right: 1px solid #d6dee9;
    padding: 9px;
    font-weight: 800;
}
"""


DARK_STYLE = """
QWidget {
    background-color: #0F172A;
    color: #F8FAFC;
    font-family: Segoe UI, Inter, Arial, sans-serif;
    font-size: 10.5pt;
}
QMainWindow, QDialog {
    background-color: #0F172A;
    color: #F8FAFC;
}
QScrollArea, QScrollArea > QWidget > QWidget, QSplitter {
    background-color: #0F172A;
    border: none;
}
QGroupBox {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
    margin-top: 14px;
    padding: 18px;
    color: #F8FAFC;
    font-weight: 800;
}
QGroupBox#LoginCard {
    padding: 22px;
    margin-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #CBD5E1;
    background-color: #1E293B;
}
QLabel {
    color: #F8FAFC;
    background: transparent;
}
QLabel#AppTitle, QLabel#DashboardTitle, QLabel#StatisticsTitle, QLabel#ProfileTitle, QLabel#LoginTitle {
    color: #F8FAFC;
    font-size: 24pt;
    font-weight: 900;
}
QLabel#AppTitle {
    font-size: 29pt;
}
QLabel#Subtitle, QLabel#LoginMotto, QLabel#MutedText {
    color: #94A3B8;
    font-weight: 600;
}
QLabel#LoginMotto {
    color: #22C55E;
    font-size: 12pt;
}
QLabel#SectionTitle, QLabel#ChartTitle, QLabel#ItemTitle {
    color: #F8FAFC;
    font-weight: 800;
}
QLabel#SummaryText, QLabel#ActiveFilter {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    color: #CBD5E1;
    padding: 10px 12px;
    font-weight: 700;
}
QLabel#ResultCountText {
    color: #22C55E;
    font-weight: 800;
    padding: 6px 10px;
}
QLabel#EmptyState {
    background-color: rgba(245, 158, 11, 0.12);
    border: 1px solid #F59E0B;
    border-radius: 10px;
    color: #FBBF24;
    padding: 12px;
    font-weight: 800;
}
QLabel#WarningText, QLabel#MedicalWarning {
    background-color: rgba(245, 158, 11, 0.14);
    border: 1px solid #F59E0B;
    border-radius: 10px;
    color: #FCD34D;
    padding: 10px;
    font-weight: 800;
}
QWidget#DashboardCard, QWidget#StatisticsCard, QWidget#ChartCard {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
}
QLabel#CardTitle {
    color: #94A3B8;
    font-size: 9.5pt;
    font-weight: 800;
    text-transform: uppercase;
}
QLabel#CardIcon {
    background-color: rgba(59, 130, 246, 0.18);
    border: 1px solid rgba(59, 130, 246, 0.35);
    border-radius: 10px;
    color: #93C5FD;
    min-width: 34px;
    min-height: 34px;
    font-size: 14pt;
    font-weight: 900;
}
QLabel#CardValue, QLabel#SummaryValue {
    color: #F8FAFC;
    font-size: 22pt;
    font-weight: 900;
}
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit, QListWidget {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 10px;
    color: #F8FAFC;
    min-height: 34px;
    padding: 8px 11px;
    selection-background-color: #3B82F6;
    selection-color: #F8FAFC;
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTimeEdit:hover, QTextEdit:hover, QListWidget:hover {
    border: 1px solid #475569;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QTextEdit:focus {
    border: 1px solid #3B82F6;
}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QTimeEdit:disabled {
    background-color: #111827;
    color: #64748B;
    border: 1px solid #1F2937;
}
QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down {
    border: none;
    width: 28px;
}
QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    selection-background-color: #2563EB;
    selection-color: #F8FAFC;
    padding: 6px;
}
QPushButton {
    background-color: #3B82F6;
    color: #F8FAFC;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 800;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #2563EB;
}
QPushButton:pressed {
    background-color: #1D4ED8;
}
QPushButton:disabled {
    background-color: #334155;
    color: #94A3B8;
}
QPushButton#LogoutButton {
    background-color: #22C55E;
}
QPushButton#LogoutButton:hover {
    background-color: #16A34A;
}
QPushButton#SuccessButton {
    background-color: #22C55E;
}
QPushButton#SuccessButton:hover {
    background-color: #16A34A;
}
QPushButton#DangerButton {
    background-color: #EF4444;
}
QPushButton#DangerButton:hover {
    background-color: #DC2626;
}
QPushButton#WarningButton {
    background-color: #F59E0B;
}
QPushButton#WarningButton:hover {
    background-color: #D97706;
}
QPushButton[text*="Delete"], QPushButton[text*="Deactivate"], QPushButton[text*="Cancel"] {
    background-color: #EF4444;
}
QPushButton[text*="Delete"]:hover, QPushButton[text*="Deactivate"]:hover, QPushButton[text*="Cancel"]:hover {
    background-color: #DC2626;
}
QPushButton[text*="Taken"], QPushButton[text*="Completed"], QPushButton[text*="Activate"], QPushButton[text*="Create"] {
    background-color: #22C55E;
}
QPushButton[text*="Taken"]:hover, QPushButton[text*="Completed"]:hover, QPushButton[text*="Activate"]:hover, QPushButton[text*="Create"]:hover {
    background-color: #16A34A;
}
QTableWidget {
    background-color: #0F172A;
    alternate-background-color: #111C31;
    border: 1px solid #334155;
    border-radius: 12px;
    color: #F8FAFC;
    gridline-color: #1E293B;
    selection-background-color: #2563EB;
    selection-color: #F8FAFC;
}
QTableWidget::item {
    padding: 8px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #2563EB;
    color: #F8FAFC;
}
QHeaderView::section {
    background-color: #1E293B;
    color: #CBD5E1;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #334155;
    padding: 10px;
    font-weight: 900;
}
QTabWidget::pane {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 12px;
    top: -1px;
}
QTabBar::tab {
    background-color: #1E293B;
    color: #CBD5E1;
    min-width: 170px;
    min-height: 38px;
    padding: 10px 20px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    font-size: 10.5pt;
    font-weight: 800;
}
QTabBar::tab:hover {
    background-color: #26354A;
    color: #F8FAFC;
}
QTabBar::tab:selected {
    background-color: #2563EB;
    color: #F8FAFC;
}
QCalendarWidget QWidget {
    alternate-background-color: #111C31;
}
QCalendarWidget QToolButton {
    background-color: #1E293B;
    color: #F8FAFC;
    border-radius: 8px;
    padding: 7px;
}
QCalendarWidget QToolButton:hover {
    background-color: #2563EB;
}
QCalendarWidget QAbstractItemView {
    background-color: #0F172A;
    color: #CBD5E1;
    selection-background-color: #3B82F6;
    selection-color: #F8FAFC;
    border: 1px solid #334155;
    outline: 0;
}
QCheckBox {
    color: #CBD5E1;
    spacing: 8px;
}
QSlider::groove:horizontal {
    height: 8px;
    background: #334155;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #3B82F6;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QDialogButtonBox QPushButton {
    min-width: 100px;
}
QToolTip {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px;
}
"""


COMMON_STYLE = LIGHT_STYLE


def app_style(theme: str = "Light Theme") -> str:
    return DARK_STYLE if theme == "Dark Theme" else LIGHT_STYLE


def set_app_theme(theme: str) -> None:
    app = QApplication.instance()
    if app:
        app.setProperty("pharmaguard_theme", theme)
        app.setStyleSheet(app_style(theme))


def current_theme() -> str:
    app = QApplication.instance()
    return app.property("pharmaguard_theme") if app and app.property("pharmaguard_theme") else "Light Theme"


def current_app_style() -> str:
    return app_style(current_theme())
