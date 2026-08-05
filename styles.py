"""
Centralized PharmaGuard styles: the "Clinical Instrument" identity.

The look is a calibrated medical device. Precise, calm, flat, nothing playful:
this app tells someone whether they took their heart medication. Spec lives in
`MOSKA_MAIN/shared/UI_IDENTITIES.md`.

Light and dark used to be two hand-maintained strings, and they had drifted badly
- dark carried 380 lines of rules while light carried 8, so every card, tab and
title fell back to stock Qt in light mode. Both themes are now generated from one
template and two token dicts, so a rule can no longer exist in one theme only.

Every colour below was picked against a measured contrast ratio, not by eye:
body text clears WCAG AA 4.5:1 on its own surface, and the signal bars clear the
3:1 required of a meaningful non-text element. The spec's `#0D9488` teal only
reaches 3.74:1 under white button text, so `#0F766E` fills buttons and `#0D9488`
is kept for rules and focus rings where it carries no text.
"""

import sys

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QApplication, QStyledItemDelegate

# Two families, three weights, per the anti-slop rules.
#
# The native family has to come first for the running platform, not just appear
# somewhere in the list: Qt resolves left to right and logs
# "Populating font family aliases took Nms. Replace uses of missing font family"
# for a leading name it cannot find. "Segoe UI" was hardcoded, so every macOS
# launch paid that warning. Apple's "SF Pro Text" and "SF Mono" are not exposed
# to Qt's font database either, which is why the macOS head is Helvetica Neue.
if sys.platform == "darwin":
    _UI_HEAD, _MONO_HEAD = '"Helvetica Neue", Helvetica', "Menlo, Monaco"
elif sys.platform.startswith("win"):
    _UI_HEAD, _MONO_HEAD = '"Segoe UI"', '"Cascadia Mono", Consolas'
else:
    _UI_HEAD, _MONO_HEAD = '"Noto Sans", "DejaVu Sans"', '"DejaVu Sans Mono"'

UI_FONTS = f'{_UI_HEAD}, "Segoe UI", "Helvetica Neue", Inter, sans-serif'
MONO_FONTS = f'{_MONO_HEAD}, Menlo, Consolas, "DejaVu Sans Mono", "Courier New", monospace'

# Status kinds used by the row edge bar and the row tint.
TAKEN = "taken"
DUE = "due"
OVERDUE = "overdue"

LIGHT_TOKENS = {
    "surface": "#F7F9FC",
    "panel": "#FFFFFF",
    "panel_alt": "#F2F5FA",
    "inset": "#FFFFFF",
    "border": "#DCE3EC",
    "border_strong": "#C3CEDB",
    "text": "#0F172A",
    # The spec's #7C8BA1 muted reads 3.46:1 on white, under the 4.5:1 body
    # minimum. Darkened for light mode only; dark mode keeps the spec value.
    "muted": "#5C6B7F",
    "accent": "#0D9488",
    "accent_fill": "#0F766E",
    "accent_fill_hover": "#0D9488",
    "accent_wash": "rgba(13, 148, 136, 0.10)",
    "on_accent": "#FFFFFF",
    "signal_taken": "#059669",
    "signal_due": "#B45309",
    "signal_overdue": "#DC2626",
    "danger_fill": "#DC2626",
    "danger_fill_hover": "#B91C1C",
    "tint_taken": "#F2FAF6",
    "tint_overdue": "#FEF4F4",
    "selection": "#CFE9E5",
    "on_selection": "#0F172A",
    "disabled_bg": "#EEF1F6",
    "disabled_text": "#7E8B9C",
}

DARK_TOKENS = {
    "surface": "#0B1220",
    "panel": "#111C2E",
    "panel_alt": "#16233A",
    "inset": "#0B1220",
    "border": "#22304A",
    "border_strong": "#33415C",
    "text": "#E6EDF7",
    "muted": "#7C8BA1",
    "accent": "#14B8A6",
    "accent_fill": "#0F766E",
    "accent_fill_hover": "#0D9488",
    "accent_wash": "rgba(20, 184, 166, 0.14)",
    "on_accent": "#E6EDF7",
    "signal_taken": "#10B981",
    "signal_due": "#F59E0B",
    "signal_overdue": "#EF4444",
    "danger_fill": "#B91C1C",
    "danger_fill_hover": "#991B1B",
    "tint_taken": "#0E2A22",
    "tint_overdue": "#2A1418",
    "selection": "#134E4A",
    "on_selection": "#E6EDF7",
    "disabled_bg": "#16223A",
    "disabled_text": "#66748A",
}


def _stylesheet(t: dict) -> str:
    """Build the full sheet for one token set. Both themes come from here."""
    return f"""
/* ---- base -------------------------------------------------------------- */
QWidget {{
    background-color: {t['surface']};
    color: {t['text']};
    font-family: {UI_FONTS};
    font-size: 10.5pt;
}}
QMainWindow, QDialog {{
    background-color: {t['surface']};
}}
QScrollArea, QScrollArea > QWidget > QWidget, QSplitter {{
    background-color: {t['surface']};
    border: none;
}}
QLabel {{
    background: transparent;
    color: {t['text']};
}}

/* ---- type scale: three weights, no more ------------------------------- */
QLabel#AppTitle {{
    font-size: 19pt;
    font-weight: 600;
    letter-spacing: -0.4px;
}}
QLabel#DashboardTitle, QLabel#StatisticsTitle, QLabel#ProfileTitle, QLabel#LoginTitle {{
    font-size: 15pt;
    font-weight: 600;
    letter-spacing: -0.2px;
}}
QLabel#Subtitle, QLabel#LoginMotto, QLabel#MutedText {{
    color: {t['muted']};
    font-weight: 400;
}}
QLabel#SectionTitle, QLabel#ChartTitle, QLabel#ItemTitle {{
    font-weight: 600;
}}
/* Section labels read as instrument legends, not headings. */
QLabel#CardTitle {{
    color: {t['muted']};
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.8px;
}}
QLabel#CardValue, QLabel#SummaryValue {{
    color: {t['text']};
    font-family: {MONO_FONTS};
    font-size: 20pt;
    font-weight: 500;
}}
QLabel#ResultCountText {{
    color: {t['muted']};
    font-family: {MONO_FONTS};
    font-size: 9pt;
    padding: 6px 2px;
}}
QLabel#SummaryText, QLabel#ActiveFilter {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-left: 3px solid {t['accent']};
    border-radius: 6px;
    color: {t['text']};
    font-family: {MONO_FONTS};
    font-size: 9.5pt;
    padding: 10px 12px;
}}
QLabel#LoginDemoHint {{
    background-color: {t['accent_wash']};
    border: 1px solid {t['accent']};
    border-radius: 6px;
    color: {t['text']};
    padding: 10px 12px;
}}

/* Empty and warning states share one flat treatment. */
QLabel#EmptyState {{
    background-color: {t['panel_alt']};
    border: 1px dashed {t['border_strong']};
    border-radius: 6px;
    color: {t['muted']};
    padding: 16px;
}}
/* Reminder popup. The banner's left edge takes the event's signal colour via a
   dynamic `kind` property set in dialogs.py, and the headline states the event
   in words so the meaning survives greyscale and colour vision deficiency. */
QLabel#ReminderBanner {{
    background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-left: 4px solid {t['muted']};
    border-radius: 6px;
    font-size: 12pt;
    font-weight: 600;
    padding: 12px 14px;
}}
QLabel#ReminderBanner[kind="due"] {{
    border-left-color: {t['signal_due']};
}}
QLabel#ReminderBanner[kind="overdue"] {{
    border-left-color: {t['signal_overdue']};
}}
QLabel#ReminderBanner[kind="taken"] {{
    border-left-color: {t['signal_taken']};
}}
QLabel#ReminderMedicine {{
    font-size: 16pt;
    font-weight: 600;
    letter-spacing: -0.3px;
}}
QLabel#ReminderTime {{
    color: {t['text']};
    font-family: {MONO_FONTS};
    font-size: 26pt;
    font-weight: 500;
}}
QLabel#WarningText, QLabel#MedicalWarning {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-left: 3px solid {t['signal_due']};
    border-radius: 6px;
    color: {t['text']};
    padding: 10px 12px;
}}

/* ---- cards: 1px border, no shadow, 8px grid ---------------------------- */
QGroupBox {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    margin-top: 16px;
    padding: 16px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {t['muted']};
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.8px;
}}
QGroupBox#LoginCard {{
    padding: 20px;
    margin-top: 12px;
}}
QWidget#DashboardCard, QWidget#StatisticsCard, QWidget#ChartCard {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    border-radius: 6px;
}}

/* ---- inputs ------------------------------------------------------------ */
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit, QListWidget, QSpinBox {{
    background-color: {t['inset']};
    border: 1px solid {t['border_strong']};
    border-radius: 6px;
    color: {t['text']};
    min-height: 24px;
    padding: 6px 10px;
    selection-background-color: {t['selection']};
    selection-color: {t['on_selection']};
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTimeEdit:hover, QTextEdit:hover {{
    border-color: {t['muted']};
}}
/* Focus is visible on every control: keyboard users are not an afterthought. */
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus,
QTextEdit:focus, QListWidget:focus, QSpinBox:focus {{
    border: 2px solid {t['accent']};
    padding: 5px 9px;
}}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QTimeEdit:disabled {{
    background-color: {t['disabled_bg']};
    border-color: {t['border']};
    color: {t['disabled_text']};
}}
QDateEdit, QTimeEdit {{
    font-family: {MONO_FONTS};
}}
QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['panel']};
    border: 1px solid {t['border_strong']};
    color: {t['text']};
    padding: 4px;
    selection-background-color: {t['selection']};
    selection-color: {t['on_selection']};
}}

/* ---- buttons: one accent, quiet by default ----------------------------- */
/* Everything used to be a filled blue block, so a row of six buttons had no
   hierarchy at all. Default is now quiet; only a real primary or destructive
   action earns fill. */
QPushButton {{
    background-color: {t['panel']};
    border: 1px solid {t['border_strong']};
    border-radius: 6px;
    color: {t['text']};
    padding: 8px 14px;
    font-weight: 500;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {t['panel_alt']};
    border-color: {t['muted']};
}}
QPushButton:pressed {{
    background-color: {t['border']};
}}
QPushButton:focus {{
    border: 2px solid {t['accent']};
    padding: 7px 13px;
}}
QPushButton:disabled {{
    background-color: {t['disabled_bg']};
    border-color: {t['border']};
    color: {t['disabled_text']};
}}
QPushButton#PrimaryButton, QPushButton#SuccessButton {{
    background-color: {t['accent_fill']};
    border: 1px solid {t['accent_fill']};
    color: {t['on_accent']};
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover, QPushButton#SuccessButton:hover {{
    background-color: {t['accent_fill_hover']};
    border-color: {t['accent_fill_hover']};
}}
QPushButton#PrimaryButton:disabled, QPushButton#SuccessButton:disabled,
QPushButton#DangerButton:disabled, QPushButton#WarningButton:disabled {{
    background-color: {t['disabled_bg']};
    border-color: {t['border']};
    color: {t['disabled_text']};
}}
QPushButton#DangerButton {{
    background-color: {t['danger_fill']};
    border: 1px solid {t['danger_fill']};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton#DangerButton:hover {{
    background-color: {t['danger_fill_hover']};
    border-color: {t['danger_fill_hover']};
}}
QPushButton#WarningButton {{
    border: 1px solid {t['signal_due']};
    color: {t['signal_due']};
    font-weight: 600;
}}
QPushButton#WarningButton:hover {{
    background-color: {t['panel_alt']};
}}
QDialogButtonBox QPushButton {{
    min-width: 92px;
}}

/* ---- tables: flat, tabular, hairline rules ----------------------------- */
QTableWidget {{
    background-color: {t['panel']};
    alternate-background-color: {t['panel_alt']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    color: {t['text']};
    gridline-color: {t['border']};
    selection-background-color: {t['selection']};
    selection-color: {t['on_selection']};
}}
QTableWidget::item {{
    border: none;
    padding: 7px 8px 7px 12px;
}}
QTableWidget::item:selected {{
    background-color: {t['selection']};
    color: {t['on_selection']};
}}
QHeaderView::section {{
    background-color: {t['surface']};
    border: none;
    border-bottom: 1px solid {t['border_strong']};
    border-right: 1px solid {t['border']};
    color: {t['muted']};
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.6px;
    padding: 9px 8px;
}}
QTableCornerButton::section {{
    background-color: {t['surface']};
    border: none;
}}

/* ---- tabs: a thin accent rule, never a filled tab ---------------------- */
QTabWidget::pane {{
    background-color: {t['surface']};
    border: none;
    border-top: 1px solid {t['border']};
    top: -1px;
}}
/* No font-weight here, in either state, on purpose. QTabBar measures its tab
   widths from the widget font; a weight set only in the stylesheet paints
   wider than what was measured, and "Calendar / Daily View" lost a character
   off each end. Selection is carried by the accent rule and the panel fill,
   which cost no width at all. */
QTabBar::tab {{
    background-color: transparent;
    border: none;
    border-top: 2px solid transparent;
    color: {t['muted']};
    margin-right: 2px;
    min-height: 30px;
    padding: 8px 18px;
}}
QTabBar::tab:hover {{
    color: {t['text']};
}}
QTabBar::tab:selected {{
    background-color: {t['panel']};
    border-top: 2px solid {t['accent']};
    color: {t['text']};
}}
QTabBar::tab:focus {{
    color: {t['accent']};
}}

/* ---- calendar ---------------------------------------------------------- */
QCalendarWidget QWidget {{
    alternate-background-color: {t['panel_alt']};
}}
QCalendarWidget QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: {t['text']};
    padding: 6px;
}}
QCalendarWidget QToolButton:hover {{
    background-color: {t['panel_alt']};
}}
QCalendarWidget QAbstractItemView {{
    background-color: {t['panel']};
    border: 1px solid {t['border']};
    color: {t['text']};
    font-family: {MONO_FONTS};
    outline: 0;
    selection-background-color: {t['accent_fill']};
    selection-color: {t['on_accent']};
}}

/* ---- misc controls ----------------------------------------------------- */
QCheckBox {{
    color: {t['text']};
    spacing: 8px;
}}
/* Applying a stylesheet to the parent drops Qt off native subcontrol painting,
   which left every checkbox rendering as an empty box in both states - the
   statistics filter said "All Patients" while its own box looked unticked.
   A filled accent square is unambiguous and needs no image asset. */
QCheckBox::indicator, QListWidget::indicator {{
    background-color: {t['inset']};
    border: 1px solid {t['border_strong']};
    border-radius: 3px;
    height: 14px;
    width: 14px;
}}
QCheckBox::indicator:hover, QListWidget::indicator:hover {{
    border-color: {t['accent']};
}}
QCheckBox::indicator:checked, QListWidget::indicator:checked {{
    background-color: {t['accent_fill']};
    border: 4px solid {t['accent_fill']};
}}
QCheckBox::indicator:disabled, QListWidget::indicator:disabled {{
    background-color: {t['disabled_bg']};
    border-color: {t['border']};
}}
QCheckBox:focus {{
    color: {t['accent']};
}}
QSlider::groove:horizontal {{
    background: {t['border']};
    border-radius: 2px;
    height: 4px;
}}
QSlider::handle:horizontal {{
    background: {t['accent_fill']};
    border-radius: 7px;
    margin: -5px 0;
    width: 14px;
}}
QScrollBar:vertical {{
    background: transparent;
    border: none;
    margin: 0;
    width: 10px;
}}
QScrollBar:horizontal {{
    background: transparent;
    border: none;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['border_strong']};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:horizontal {{
    background: {t['border_strong']};
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: {t['muted']};
}}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
    border: none;
    height: 0;
    width: 0;
}}
QToolTip {{
    background-color: {t['panel']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    color: {t['text']};
    padding: 6px 8px;
}}
"""


LIGHT_STYLE = _stylesheet(LIGHT_TOKENS)
DARK_STYLE = _stylesheet(DARK_TOKENS)
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


def tokens(theme: str = "") -> dict:
    """Return the active token set, so widgets never hardcode a hex value."""
    return DARK_TOKENS if (theme or current_theme()) == "Dark Theme" else LIGHT_TOKENS


def signal_color(kind: str, theme: str = "") -> str:
    """Map a medication status kind to its signal colour in the active theme."""
    palette = tokens(theme)
    return {
        TAKEN: palette["signal_taken"],
        DUE: palette["signal_due"],
        OVERDUE: palette["signal_overdue"],
    }.get(kind, palette["muted"])


def row_tint(kind: str, row_index: int, theme: str = "") -> str:
    """
    Background for one medication row.

    Deliberately near-invisible. The old sheet washed whole rows in pink and
    green, which is loud, and unusable for anyone with a colour vision
    deficiency because colour was the only carrier. The signal now lives in the
    4px edge bar plus the Status and Remaining text; this is only a hint.
    """
    palette = tokens(theme)
    if kind == TAKEN:
        return palette["tint_taken"]
    if kind == OVERDUE:
        return palette["tint_overdue"]
    return palette["panel"] if row_index % 2 == 0 else palette["panel_alt"]


def mono_font(point_size: float = 0, bold: bool = False) -> QFont:
    """A tabular-figure font so times, dosages and counts align in a column."""
    font = QFont()
    font.setFamilies([family.strip().strip('"') for family in MONO_FONTS.split(",")])
    font.setStyleHint(QFont.Monospace)
    if point_size:
        font.setPointSizeF(point_size)
    font.setBold(bold)
    return font


class StatusEdgeDelegate(QStyledItemDelegate):
    """
    Paint a row's status as a 4px signal-coloured edge on its first column.

    Qt stylesheets cannot address a table row, and a delegate is the only way to
    draw inside one. The edge is scannable straight down a long list in a way a
    text column in the middle of eleven others is not, and it leaves the row
    background almost untouched so the text stays readable.
    """

    EDGE_WIDTH = 4
    STATUS_ROLE = Qt.UserRole + 17

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        kind = index.data(self.STATUS_ROLE)
        if index.column() != 0 or not kind:
            return
        painter.save()
        painter.fillRect(
            QRect(option.rect.left(), option.rect.top(), self.EDGE_WIDTH, option.rect.height()),
            QColor(signal_color(kind)),
        )
        painter.restore()
