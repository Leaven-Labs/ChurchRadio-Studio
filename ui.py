"""The look of the app (Qt): colours for light and dark, the style sheet, and small shared parts.

theme in config.json: "auto" (follow the system), "light" or "dark".
"""
import os

from PySide6.QtCore import QDate, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter
from PySide6.QtWidgets import (QApplication, QDateEdit, QFrame, QLabel, QMessageBox, QStyle,
                               QStyledItemDelegate)

import paths
from churchyear import default_service_date

THEMES = ("auto", "light", "dark")
THEME_LABELS = {"auto": "Same as the system", "light": "Light", "dark": "Dark"}

LIGHT = dict(bg="#f6f7f9", card="#ffffff", text="#1c2330", sub="#667085", line="#e3e6eb", accent="#2f6fd0",
             accent2="#255bb0", soft="#eaf1fc", softline="#9dbcf0", log="#fbfbfc", sel="#e4edfb", hover="#f0f2f5",
             ok="#1a7f4b", okbg="#e3f5ea", warn="#9a5b00", warnbg="#fdf1dc", no="#b42318", nobg="#fde8e6",
             off="#98a1b0", disabled="#b4bac4")
DARK = dict(bg="#171a20", card="#20242c", text="#e8ebf0", sub="#98a1b0", line="#313742", accent="#5b93e8",
            accent2="#4a80d4", soft="#1f2b40", softline="#3d5f99", log="#1b1e25", sel="#263650", hover="#2a2f39",
            ok="#5fd093", okbg="#173524", warn="#f0b45a", warnbg="#3a2c12", no="#f58a80", nobg="#402019",
            off="#6b7483", disabled="#565d6a")

colors = dict(LIGHT)  # the colours in use (changed in place by apply_theme)


def _url(name):
    return paths.asset(name).replace("\\", "/")


def style_sheet(c):
    return f"""
QWidget {{ font-size: 13px; color: {c['text']}; }}
QMainWindow, QDialog, QWidget#root {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['line']}; }}
QFrame#card {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 10px; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 17px; font-weight: 600; }}
QLabel#heading {{ font-size: 16px; font-weight: 600; }}
QLabel#sub, QLabel#hint {{ color: {c['sub']}; }}
QLabel#strong {{ font-weight: 600; }}
QLabel#error {{ color: {c['no']}; }}
QFrame#drop {{ background: {c['soft']}; border: 2px dashed {c['softline']}; border-radius: 12px; }}
QFrame#drop[over="true"] {{ border: 2px solid {c['accent']}; }}
QLabel#dropbig {{ font-size: 18px; font-weight: 600; color: {c['accent']}; }}
QPushButton {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 7px; padding: 6px 14px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['sel']}; }}
QPushButton:focus {{ border-color: {c['softline']}; }}
QPushButton:disabled {{ color: {c['disabled']}; }}
QPushButton#primary {{ background: {c['accent']}; border: 1px solid {c['accent2']}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {c['accent2']}; }}
QPushButton#primary:disabled {{ background: {c['line']}; border-color: {c['line']}; color: {c['disabled']}; }}
QPushButton#ghost {{ border: none; background: transparent; color: {c['sub']}; }}
QPushButton#ghost:hover {{ color: {c['text']}; }}
QLineEdit, QComboBox, QDateEdit, QListWidget {{ background: {c['card']}; border: 1px solid {c['line']};
    border-radius: 7px; padding: 5px 9px; selection-background-color: {c['accent']}; selection-color: white; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border-color: {c['accent']}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {c['disabled']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({_url('ui-chevron.png')}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['line']};
    selection-background-color: {c['sel']}; selection-color: {c['text']}; outline: 0; }}
QListWidget::item {{ padding: 4px; }}
QListWidget::item:selected {{ background: {c['sel']}; color: {c['text']}; }}
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator, QTableView::indicator {{ width: 16px; height: 16px; border: 1px solid {c['softline']};
    border-radius: 4px; background: {c['card']}; }}
QCheckBox::indicator:checked, QTableView::indicator:checked {{ background: {c['accent']};
    border-color: {c['accent2']}; image: url({_url('ui-tick.png')}); }}
QRadioButton::indicator {{ width: 14px; height: 14px; border: 1px solid {c['softline']}; border-radius: 8px;
    background: {c['card']}; }}
QRadioButton::indicator:checked {{ border: 5px solid {c['accent']}; width: 6px; height: 6px; }}
QPlainTextEdit {{ background: {c['log']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 6px;
    selection-background-color: {c['accent']}; selection-color: white; }}
QProgressBar {{ background: {c['line']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
QTableWidget {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 8px;
    selection-background-color: {c['sel']}; selection-color: {c['text']}; outline: 0; }}
QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {c['line']}; }}
QTableWidget::item:selected {{ background: {c['sel']}; color: {c['text']}; }}
QTableWidget QLineEdit {{ border-radius: 0; padding: 0 6px; }}
QHeaderView::section {{ background: {c['card']}; color: {c['sub']}; font-weight: 600; border: none;
    border-bottom: 1px solid {c['line']}; padding: 7px 8px; }}
QTableCornerButton::section {{ background: {c['card']}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {c['softline']}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {c['softline']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QCalendarWidget QWidget {{ alternate-background-color: {c['card']}; }}
QCalendarWidget QAbstractItemView {{ background: {c['card']}; selection-background-color: {c['accent']};
    selection-color: white; }}
QCalendarWidget QToolButton {{ color: {c['text']}; background: transparent; border: none; padding: 4px 8px; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {c['card']}; }}
QGroupBox {{ border: 1px solid {c['line']}; border-radius: 8px; margin-top: 10px; padding: 12px 10px 8px 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {c['sub']}; }}
QMessageBox QLabel {{ min-width: 260px; }}
"""


def system_is_dark():
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # an older Qt
        return False


def apply_theme(app, theme="auto"):
    """Set the app's colours: "auto" follows the system's light or dark setting."""
    theme = theme if theme in THEMES else "auto"
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "setColorScheme"):  # the window title bars follow too (Qt 6.8+)
        hints.setColorScheme({"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(
            theme, Qt.ColorScheme.Unknown))
    dark = theme == "dark" or (theme == "auto" and system_is_dark())
    colors.clear()
    colors.update(DARK if dark else LIGHT)
    app.setStyleSheet(style_sheet(colors))


def start_app(argv, theme="auto"):
    """The QApplication, with the Fusion style (the same on every system), the icon and the theme."""
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(paths.APP_NAME)
    app.setStyle("Fusion")
    for name in ("icon.ico", "icon-256.png"):
        if os.path.isfile(paths.asset(name)):
            app.setWindowIcon(QIcon(paths.asset(name)))
            break
    apply_theme(app, theme)
    return app


def fixed_font(size=9):
    f = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    f.setPointSize(size)
    return f


def label(text="", kind="", wrap=False):
    """A QLabel; kind is its style: title, heading, sub, hint, strong or error."""
    lab = QLabel(text)
    if kind:
        lab.setObjectName(kind)
    lab.setWordWrap(wrap)
    return lab


def card():
    f = QFrame()
    f.setObjectName("card")
    return f


def ask(parent, title, text):
    """A yes / no question. True for yes."""
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


class PillDelegate(QStyledItemDelegate):
    """Draws a table cell's text as a coloured label. The item's Qt.UserRole says which colours:
    "ok", "warn" or "no" (anything else: plain text)."""

    def paint(self, painter, option, index):
        text, kind = index.data(Qt.DisplayRole), index.data(Qt.UserRole)
        if not text or kind not in ("ok", "warn", "no"):
            super().paint(painter, option, index)
            return
        style = option.widget.style() if option.widget else QApplication.style()
        blank = type(option)(option)
        self.initStyleOption(blank, index)
        blank.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, blank, painter, option.widget)  # the row's background
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        w = painter.fontMetrics().horizontalAdvance(text) + 20
        h = min(option.rect.height() - 10, 22)
        rect = QRectF(option.rect.x() + 8, option.rect.center().y() - h / 2 + 1, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colors[kind + "bg"]))
        painter.drawRoundedRect(rect, h / 2, h / 2)
        painter.setPen(QColor(colors[kind]))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()


class DateField(QDateEdit):
    """The service date, with a pop-out calendar (weeks start on Sunday). get() is the date shown;
    changed is True once the person picked a date themselves (set_date from code does not count)."""

    def __init__(self, date=None):
        super().__init__()
        self.changed = False
        self.setCalendarPopup(True)
        self.setDisplayFormat("MM/dd/yyyy")
        self.calendarWidget().setFirstDayOfWeek(Qt.Sunday)
        self.calendarWidget().setGridVisible(False)
        self.set_date(date or default_service_date())
        self.dateChanged.connect(self._picked)

    def _picked(self, _date):
        self.changed = True

    def get(self):
        return self.date().toPython()

    def set_date(self, date):
        was = self.blockSignals(True)  # set from code: not the person's choice
        self.setDate(QDate(date.year, date.month, date.day))
        self.blockSignals(was)


def qt_version():
    from PySide6.QtCore import qVersion
    return qVersion()
