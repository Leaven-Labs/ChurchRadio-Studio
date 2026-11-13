"""The look of the app (Qt): colours for light and dark, the style sheet, and small shared parts.

theme in config.json: "auto" (follow the system), "light" or "dark".
"""
import os

from PySide6.QtCore import QDate, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPainterPath, QPen,
                           QPolygonF)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QDateEdit, QFrame, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QSizePolicy, QStyle, QStyledItemDelegate,
                               QWidget)

import paths
from churchyear import default_service_date

THEMES = ("auto", "light", "dark")
THEME_LABELS = {"auto": "Same as the system", "light": "Light", "dark": "Dark"}

LIGHT = dict(bg="#f4f5f8", side="#ebedf2", card="#ffffff", text="#1c2330", sub="#667085", line="#e1e4ea",
             accent="#2f6fd0", accent2="#255bb0", soft="#eaf1fc", softline="#9dbcf0", log="#fbfbfc", sel="#e4edfb",
             hover="#eef0f4", ok="#1a7f4b", okbg="#e3f5ea", warn="#9a5b00", warnbg="#fdf1dc", no="#b42318",
             nobg="#fde8e6", off="#98a1b0", disabled="#b4bac4", intro="#8b6fe0", song="#2aa98c", track="#cfd4dc",
             knob="#ffffff")
DARK = dict(bg="#14171c", side="#191c23", card="#1f232d", text="#e8ebf0", sub="#98a1b0", line="#2c323d",
            accent="#5b93e8", accent2="#4a80d4", soft="#1a2434", softline="#3d5f99", log="#191c23", sel="#22304a",
            hover="#272c37", ok="#5fd093", okbg="#173524", warn="#f0b45a", warnbg="#3a2c12", no="#f58a80",
            nobg="#402019", off="#6b7483", disabled="#565d6a", intro="#a78bfa", song="#45c4a8", track="#3a414d",
            knob="#aab2c0")

colors = dict(LIGHT)  # the colours in use (changed in place by apply_theme)


def _url(name):
    return paths.asset(name).replace("\\", "/")


def style_sheet(c):
    return f"""
QWidget {{ font-size: 13px; color: {c['text']}; }}
QMainWindow, QDialog, QWidget#root {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['line']}; }}
QFrame#card {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 12px; }}
QFrame#side {{ background: {c['side']}; border: none; border-right: 1px solid {c['line']}; }}
QFrame#field {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 8px; }}
QFrame#field QDateEdit, QFrame#field QComboBox {{ border: none; background: transparent; padding: 2px 2px;
    font-weight: 600; }}
QScrollArea, QWidget#scrollbody {{ background: transparent; border: none; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 17px; font-weight: 600; }}
QLabel#appname {{ font-size: 15px; font-weight: 700; }}
QLabel#pagetitle {{ font-size: 22px; font-weight: 700; }}
QLabel#big {{ font-size: 15px; font-weight: 600; }}
QLabel#caps {{ font-size: 11px; font-weight: 700; color: {c['sub']}; }}
QLabel#small {{ font-size: 12px; color: {c['sub']}; }}
QLabel#pill {{ font-weight: 600; border-radius: 11px; padding: 3px 10px; }}
QLabel#pill[kind="ok"] {{ background: {c['okbg']}; color: {c['ok']}; }}
QLabel#pill[kind="warn"] {{ background: {c['warnbg']}; color: {c['warn']}; }}
QLabel#pill[kind="no"] {{ background: {c['nobg']}; color: {c['no']}; }}
QLabel#heading {{ font-size: 16px; font-weight: 600; }}
QLabel#sub, QLabel#hint {{ color: {c['sub']}; }}
QLabel#strong {{ font-weight: 600; }}
QLabel#error {{ color: {c['no']}; }}
QLabel#warntext {{ color: {c['warn']}; }}
QFrame#drop {{ background: {c['soft']}; border: 2px dashed {c['softline']}; border-radius: 12px; }}
QFrame#drop[has="true"] {{ background: {c['card']}; border: 1px solid {c['line']}; }}
QFrame#drop[over="true"] {{ border: 2px solid {c['accent']}; }}
QLabel#dropbig {{ font-size: 18px; font-weight: 600; color: {c['accent']}; }}
QPushButton {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 7px 16px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['sel']}; }}
QPushButton:focus {{ border-color: {c['softline']}; }}
QPushButton:disabled {{ color: {c['disabled']}; }}
QPushButton#primary {{ background: {c['accent']}; border: 1px solid {c['accent2']}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {c['accent2']}; }}
QPushButton#primary:disabled {{ background: {c['line']}; border-color: {c['line']}; color: {c['disabled']}; }}
QPushButton#mini {{ padding: 3px 9px; font-size: 12px; border-radius: 6px; }}
QPushButton#ghost {{ border: none; background: transparent; color: {c['sub']}; }}
QPushButton#ghost:hover {{ color: {c['text']}; }}
QFrame#segs {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 8px; }}
QPushButton#seg {{ background: transparent; border: none; border-right: 1px solid {c['line']}; border-radius: 0;
    padding: 7px 13px; color: {c['sub']}; }}
QPushButton#seg:hover {{ color: {c['text']}; }}
QPushButton#seg[pos="first"] {{ border-top-left-radius: 7px; border-bottom-left-radius: 7px; }}
QPushButton#seg[pos="last"] {{ border-right: none; border-top-right-radius: 7px; border-bottom-right-radius: 7px; }}
QPushButton#seg:checked {{ background: {c['soft']}; color: {c['accent']}; font-weight: 600; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['line']}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {c['sel']}; }}
QMenu::item:disabled {{ color: {c['disabled']}; }}
QMenu::separator {{ height: 1px; background: {c['line']}; margin: 4px 6px; }}
QLineEdit, QComboBox, QDateEdit, QListWidget {{ background: {c['card']}; border: 1px solid {c['line']};
    border-radius: 8px; padding: 6px 10px; selection-background-color: {c['accent']}; selection-color: white; }}
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
QTableWidget {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 12px;
    selection-background-color: {c['sel']}; selection-color: {c['text']}; outline: 0; }}
QTableWidget::item {{ padding: 4px 10px; border-bottom: 1px solid {c['line']}; }}
QTableWidget::item:selected {{ background: {c['sel']}; color: {c['text']}; }}
QTableWidget QLineEdit {{ border-radius: 0; padding: 0 6px; }}
QHeaderView::section {{ background: {c['card']}; color: {c['sub']}; font-weight: 600; border: none;
    border-bottom: 1px solid {c['line']}; padding: 10px 10px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section:first {{ border-top-left-radius: 11px; }}
QHeaderView::section:last, QHeaderView::section:only-one {{ border-top-right-radius: 11px; }}
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
    """A QLabel; kind is its style: title, pagetitle, heading, big, caps, sub, small, hint, strong or error."""
    lab = QLabel(text)
    if kind:
        lab.setObjectName(kind)
    if kind == "caps":
        font = lab.font()
        font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        lab.setFont(font)
    lab.setWordWrap(wrap)
    return lab


def card():
    f = QFrame()
    f.setObjectName("card")
    return f


def ask(parent, title, text):
    """A yes / no question. True for yes."""
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


def set_prop(widget, name, value):
    """Set a property the style sheet looks at (QFrame#drop[over="true"]) and restyle the widget."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def field(text, widget):
    """A small box with a grey label and a field in it: [Service date  Sun, Nov 15, 2026]."""
    box = QFrame()
    box.setObjectName("field")
    row = QHBoxLayout(box)
    row.setContentsMargins(12, 3, 6, 3)
    row.setSpacing(4)
    row.addWidget(label(text, "sub"))
    row.addWidget(widget)
    return box


# ---- small drawings: no picture files, and they take the colours of the theme ---------------
def draw_icon(p, name, rect, color):
    """Draw the icon `name` in rect (a square): broadcast, songs, history, settings, file, play, check."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(rect.x(), rect.y())
    p.scale(rect.width() / 20.0, rect.height() / 20.0)  # drawn on a 20 x 20 grid
    color = QColor(color)
    p.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    def line(*xy):
        p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(xy[::2], xy[1::2])]))

    if name == "broadcast":
        for r in (4.6, 8.2):
            box = QRectF(10 - r, 10 - r, 2 * r, 2 * r)
            p.drawArc(box, -48 * 16, 96 * 16)
            p.drawArc(box, 132 * 16, 96 * 16)
        p.setBrush(color)
        p.drawEllipse(QPointF(10, 10), 1.5, 1.5)
    elif name == "songs":
        p.drawEllipse(QPointF(5.4, 15), 2.3, 2.3)
        p.drawEllipse(QPointF(14.4, 13), 2.3, 2.3)
        line(7.7, 15, 7.7, 5, 16.7, 3, 16.7, 13)
    elif name == "history":
        p.drawEllipse(QPointF(10, 10), 7.6, 7.6)
        line(10, 5.6, 10, 10, 13, 12)
    elif name == "settings":
        for y, x in ((5, 13), (10, 7), (15, 12)):
            line(3, y, 17, y)
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), 1.9, 1.9)
    elif name == "file":
        line(11.5, 2.5, 5, 2.5, 5, 17.5, 15.5, 17.5, 15.5, 6.5, 11.5, 2.5, 11.5, 6.5, 15.5, 6.5)
    elif name == "play":
        p.setBrush(color)
        p.drawPolygon(QPolygonF([QPointF(7.6, 5.6), QPointF(15, 10), QPointF(7.6, 14.4)]))
    elif name == "check":
        line(5.6, 10.4, 8.8, 13.4, 14.6, 7)
    p.restore()


class IconTile(QWidget):
    """An icon on a soft rounded square (the file in the recording card). kind: its colours:
    "accent", "ok" (the broadcast is made) or "warn" (made, but too long)."""
    KINDS = {"accent": ("soft", "accent"), "ok": ("okbg", "ok"), "warn": ("warnbg", "warn")}

    def __init__(self, name, size=44, kind="accent"):
        super().__init__()
        self.name, self.kind = name, kind
        self.setFixedSize(size, size)

    def set_kind(self, kind):
        self.kind = kind
        self.update()

    def paintEvent(self, _event):  # noqa: N802  (Qt's name)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        ground, color = self.KINDS[self.kind]
        p.setBrush(QColor(colors[ground]))
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        m = self.width() * 0.28
        draw_icon(p, self.name, QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m), colors[color])


class NavButton(QAbstractButton):
    """A line of the menu at the left: an icon and a name. The page shown is the checked one."""

    def __init__(self, icon, text):
        super().__init__()
        self.icon_name = icon
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):  # noqa: N802
        return QSize(180, 40)

    def enterEvent(self, event):  # noqa: N802
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        if on or (self.underMouse() and self.isEnabled()):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colors["card" if on else "hover"]))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0, 1, 0, -1), 9, 9)
        color = colors["disabled"] if not self.isEnabled() else colors["text" if on else "sub"]
        draw_icon(p, self.icon_name, QRectF(12, (self.height() - 18) / 2, 18, 18), color)
        font = QFont(self.font())
        font.setPixelSize(15)
        font.setWeight(QFont.DemiBold if on else QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(self.rect().adjusted(42, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class Segments(QFrame):
    """A row of joined buttons, one of them chosen: [All | Allowed to broadcast | Off]."""
    changed = Signal(str)

    def __init__(self, names):
        super().__init__()
        self.setObjectName("segs")
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        self.group, self.buttons = QButtonGroup(self), {}
        for i, name in enumerate(names):
            b = self.buttons[name] = QPushButton(name)
            b.setObjectName("seg")
            b.setProperty("pos", "first" if i == 0 else "last" if i == len(names) - 1 else "mid")
            b.setCheckable(True)
            b.setAutoDefault(False)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _on=False, n=name: self.changed.emit(n))
            self.group.addButton(b)
            row.addWidget(b)

    def current(self):
        return next(name for name, b in self.buttons.items() if b.isChecked())

    def set_current(self, name):
        if name in self.buttons and name != self.current():
            self.buttons[name].setChecked(True)
            self.changed.emit(name)


class HourBar(QWidget):
    """The broadcast as one bar: the intro, the service and each song, to scale."""
    COLORS = {"intro": "intro", "service": "accent", "song": "song"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.setFixedHeight(40)

    def set_parts(self, parts):
        """parts: [(kind, seconds, text drawn in the part if it fits)], kind: intro, service or song."""
        self.parts = [p for p in parts if p[1] > 0]
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 9, 9)
        p.setClipPath(clip)
        total = sum(sec for _kind, sec, _text in self.parts)
        if not total:
            p.fillRect(rect, QColor(colors["line"]))
            return
        p.fillRect(rect, QColor(colors["card"]))  # shows as the thin gaps between the parts
        font = QFont(self.font())
        font.setBold(True)
        p.setFont(font)
        gap, x = 2.0, 0.0
        room = rect.width() - gap * (len(self.parts) - 1)
        for kind, sec, text in self.parts:
            w = room * sec / total
            part = QRectF(x, 0, w, rect.height())
            p.fillRect(part, QColor(colors[self.COLORS.get(kind, "accent")]))
            if text and p.fontMetrics().horizontalAdvance(text) + 28 < w:
                p.setPen(QColor("white"))
                p.drawText(part.adjusted(14, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
            x += w + gap


def clock(sec):
    """A place in a recording or a length: "9:02", "1:08:15"."""
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class Waveform(QWidget):
    """The recording drawn as its loudness along its length, with the two cuts marked: the part
    that is broadcast is bright, what is cut off before the start and after the end is dim."""
    TOP, BOTTOM = 30, 24  # room for the cut labels above the wave and the times under it
    GRAB = 9              # a click this many pixels from a cut's line takes hold of it
    APART = 30.0          # the cuts stay at least this many seconds apart
    moved = Signal(str)   # the person moved a cut ("start" or "end"): with the mouse, or nudge()
    changed = Signal()    # what is drawn changed (the close-ups of the cuts draw themselves again)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(self.TOP + 72 + self.BOTTOM)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.editable, self.drag = False, None
        self.reset()

    def reset(self):
        """A new recording: nothing is known yet."""
        self.levels, self.length, self.cuts, self.note = None, 0.0, {}, "Reading the recording ..."
        self.detail, self.per_second = None, 0  # the loudness in small slices, for the close-ups
        self.drag = None
        self.redraw()

    def redraw(self):
        self.update()
        self.changed.emit()

    def known(self):
        """True once the length and both cuts are known: the cuts can be shown and moved."""
        return self.length > 0 and "start" in self.cuts and "end" in self.cuts

    def set_editable(self, on):
        """Let the person drag the cuts (not while a broadcast is being made)."""
        self.editable = bool(on)
        if not on:
            self.drag = None
            self.unsetCursor()
        self.changed.emit()

    def cut_x(self, which):
        """Where the line of a cut is drawn (a cut that cuts nothing: at that end of the picture)."""
        at = self.cuts.get(which)
        if which == "start":
            return self.width() * min(max((at or 0.0) / self.length, 0.0), 1.0) if self.length else 0.0
        return self.width() * min(max(at / self.length, 0.0), 1.0) if at and self.length else float(self.width())

    def move_cut(self, which, seconds):
        """Put a cut at `seconds`, kept inside the recording and apart from the other cut. At the
        very start or end of the recording the cut cuts nothing (None)."""
        if not self.known():
            return
        if which == "start":
            limit = (self.cuts.get("end") or self.length) - self.APART
            at = round(min(max(seconds, 0.0), max(limit, 0.0)), 1)
            self.cuts["start"] = at or None
        else:
            at = round(max(min(seconds, self.length), (self.cuts.get("start") or 0.0) + self.APART), 1)
            self.cuts["end"] = None if at >= self.length else at
        self.redraw()

    def nudge(self, which, seconds):
        """Move a cut a little earlier (-) or later (+)."""
        if self.editable and self.known():
            now = self.cuts.get(which)
            self.move_cut(which, (now if now is not None else 0.0 if which == "start" else self.length) + seconds)
            self.moved.emit(which)

    def cut_near(self, x):
        """The cut whose line is at x (within GRAB), or None."""
        if not (self.editable and self.known()):
            return None
        near = sorted((abs(x - self.cut_x(which)), which) for which in ("start", "end"))
        return near[0][1] if near[0][0] <= self.GRAB else None

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.drag = self.cut_near(event.position().x())

    def mouseMoveEvent(self, event):  # noqa: N802
        x = event.position().x()
        if self.drag and self.width():
            self.move_cut(self.drag, x / self.width() * self.length)
        elif self.cut_near(x):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self.drag and event.button() == Qt.LeftButton:
            which, self.drag = self.drag, None
            self.moved.emit(which)

    def set_levels(self, levels, detail=None, per_second=0):
        """levels: numbers 0..1 along the recording, or None if it failed; detail: the same in small
        slices, per_second of them for each second (audio.loudness_picture)."""
        self.levels = levels or None
        self.detail, self.per_second = (detail, per_second) if levels and detail and per_second else (None, 0)
        self.note = "" if levels else "The recording could not be drawn. The broadcast is not affected."
        self.redraw()

    def set_length(self, seconds):
        self.length = max(0.0, seconds or 0.0)
        self.redraw()

    def set_cut(self, which, seconds):
        """which: "start" or "end". seconds into the recording; None or 0 = nothing cut there."""
        self.cuts[which] = seconds or None
        self.redraw()

    def steps(self):
        """The times written under the wave: at most six, at round minutes."""
        for minutes in (1, 2, 5, 10, 15, 30, 60, 120):
            if self.length / (minutes * 60) <= 5.5:
                return [t * minutes * 60 for t in range(int(self.length // (minutes * 60)) + 1)]
        return [0]

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, mid_h = float(self.width()), self.height() - self.TOP - self.BOTTOM
        wave = QRectF(0, self.TOP, w, mid_h)
        length = self.length
        x_of = (lambda sec: w * min(max(sec / length, 0.0), 1.0)) if length else (lambda sec: 0.0)
        start, end, known = self.cut_x("start"), self.cut_x("end"), bool(length) and bool(self.cuts)

        for part in ((0.0, start), (end, w)) if known else ():  # what is cut off: a darker ground
            if part[1] - part[0] > 0.5:
                p.fillRect(QRectF(part[0], self.TOP, part[1] - part[0], mid_h), QColor(colors["bg"]))
        p.setPen(Qt.NoPen)
        if self.levels:
            n, x, cy = len(self.levels), 1.0, wave.center().y()
            while x < w - 1:
                level = self.levels[min(n - 1, int(x / w * n))]
                h = max(2.0, level * (mid_h - 8))
                inside = not known or start <= x <= end
                p.setBrush(QColor(colors["accent" if inside else "disabled"]))
                p.setOpacity(1.0 if inside else 0.55)
                p.drawRoundedRect(QRectF(x, cy - h / 2, 2, h), 1, 1)
                x += 4
            p.setOpacity(1.0)
        else:
            p.setPen(QColor(colors["sub"]))
            p.drawText(wave, Qt.AlignCenter, self.note)

        font = QFont(self.font())
        font.setBold(True)
        if known:  # the two cuts: a line through the wave and a label above it
            for which, x, name in (("start", start, "Start"), ("end", end, "End")):
                at = self.cuts.get(which)
                text = f"{name} {clock(at)}" if at else f"{name}: nothing cut"
                p.setFont(font)
                tw = p.fontMetrics().horizontalAdvance(text) + 18
                left = min(max(x - 1 if which == "start" else x + 1 - tw, 0.0), w - tw)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(colors["accent"]))
                p.drawRoundedRect(QRectF(left, 0, tw, 22), 5, 5)
                p.drawRect(QRectF(min(max(x - 1, 0.0), w - 2), 20, 2, self.height() - self.BOTTOM - 20))
                p.setPen(QColor("white"))
                p.drawText(QRectF(left, 0, tw, 22), Qt.AlignCenter, text)

        if length:  # the times under the wave; the last one is the length of the recording
            p.setFont(self.font())
            p.setPen(QColor(colors["sub"]))
            fm, y = p.fontMetrics(), self.height() - self.BOTTOM + 6
            last = clock(length)
            last_x = w - fm.horizontalAdvance(last)
            p.drawText(QRectF(last_x, y, w - last_x, 18), Qt.AlignLeft | Qt.AlignVCenter, last)
            for sec in self.steps():
                text = clock(sec)
                tw = fm.horizontalAdvance(text)
                x = min(max(x_of(sec) - (tw / 2 if sec else 0), 0.0), w - tw)
                if x + tw + 14 < last_x:
                    p.drawText(QRectF(x, y, tw + 2, 18), Qt.AlignLeft | Qt.AlignVCenter, text)


def clock_exact(sec):
    """A place in a recording to a tenth of a second: "9:02.4"."""
    tenths = int(round(sec * 10))
    return f"{clock(tenths // 10)}.{tenths % 10}"


class CloseUp(QWidget):
    """One cut of a Waveform seen from near: SPAN seconds of the recording around the cut, so
    that it can be put in a pause between two words. A click puts the cut there, a drag moves it."""
    SPAN = 40.0           # seconds shown
    TOP, BOTTOM = 22, 20  # room for the caption above the wave and the times under it

    def __init__(self, wave, which):
        super().__init__()
        self.wave, self.which, self.anchor = wave, which, None
        self.setMinimumHeight(self.TOP + 56 + self.BOTTOM)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        wave.changed.connect(self.wave_changed)

    def wave_changed(self):
        if not self.can_move():
            self.anchor = None
        self.setCursor(Qt.SizeHorCursor) if self.can_move() else self.unsetCursor()
        self.update()

    def can_move(self):
        return self.wave.editable and self.wave.known()

    def at(self):
        """Where the cut is (a cut that cuts nothing: the very start or end of the recording)."""
        at = self.wave.cuts.get(self.which)
        return at if at else 0.0 if self.which == "start" else self.wave.length

    def first(self):
        """The second at the left edge: the cut is in the middle; while it is dragged the picture
        stays where it was."""
        return (self.at() if self.anchor is None else self.anchor) - self.SPAN / 2

    def seconds_at(self, x):
        return self.first() + x / max(1, self.width()) * self.SPAN

    def x_of(self, sec):
        return (sec - self.first()) / self.SPAN * self.width()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.can_move():
            self.anchor = self.at()
            self.wave.move_cut(self.which, self.seconds_at(event.position().x()))

    def mouseMoveEvent(self, event):  # noqa: N802
        if self.anchor is not None:
            self.wave.move_cut(self.which, self.seconds_at(event.position().x()))

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self.anchor is not None and event.button() == Qt.LeftButton:
            self.anchor = None
            self.update()
            self.wave.moved.emit(self.which)

    def level(self, a, b):
        """The loudness (0..1) of the recording from second a to b."""
        per, detail = self.wave.per_second, self.wave.detail
        i = int(a * per)
        some = detail[i:max(i + 1, int(b * per))]
        return sum(some) / len(some) if some else 0.0

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        wave, start = self.wave, self.which == "start"
        w, mid_h = float(self.width()), self.height() - self.TOP - self.BOTTOM
        area = QRectF(0, self.TOP, w, mid_h)
        p.setPen(QColor(colors["sub"]))
        name = "Start cut" if start else "End cut"
        if not wave.known():
            p.drawText(QRectF(0, 0, w, self.TOP - 4), Qt.AlignLeft | Qt.AlignVCenter, name)
            return
        cut, length = self.at(), wave.length
        cut_x = min(max(self.x_of(cut), 0.0), w)
        p.drawText(QRectF(0, 0, w, self.TOP - 4), Qt.AlignLeft | Qt.AlignVCenter, f"{name}, close up")
        font = QFont(self.font())
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(colors["text"]))
        cuts_nothing = not wave.cuts.get(self.which)
        p.drawText(QRectF(0, 0, w, self.TOP - 4), Qt.AlignRight | Qt.AlignVCenter,
                   "nothing cut" if cuts_nothing else clock_exact(cut))
        p.setFont(self.font())

        # what is cut off: a darker ground, as in the picture of the whole recording
        off = QRectF(0, self.TOP, cut_x, mid_h) if start else QRectF(cut_x, self.TOP, w - cut_x, mid_h)
        p.fillRect(off, QColor(colors["bg"]))
        p.setPen(Qt.NoPen)
        if wave.detail:
            x, cy, per_px = 1.0, area.center().y(), self.SPAN / w
            while x < w - 1:
                sec = self.seconds_at(x)
                if 0.0 <= sec < length:
                    h = max(2.0, self.level(sec, sec + 3 * per_px) * (mid_h - 6))
                    inside = sec >= cut if start else sec <= cut
                    p.setBrush(QColor(colors["accent" if inside else "disabled"]))
                    p.setOpacity(1.0 if inside else 0.55)
                    p.drawRoundedRect(QRectF(x, cy - h / 2, 2, h), 1, 1)
                x += 3
            p.setOpacity(1.0)
        else:
            p.setPen(QColor(colors["sub"]))
            p.drawText(area, Qt.AlignCenter, wave.note)
            p.setPen(Qt.NoPen)
        p.setBrush(QColor(colors["accent"]))  # the cut: a line with a grip at the top
        line_x = min(max(cut_x - 1, 0.0), w - 2)
        p.drawRect(QRectF(line_x, self.TOP - 2, 2, mid_h + 4))
        p.drawEllipse(QPointF(line_x + 1, self.TOP - 2), 4, 4)

        p.setPen(QColor(colors["sub"]))  # the times under it, every ten seconds
        fm, y = p.fontMetrics(), self.height() - self.BOTTOM + 3
        sec = max(0, int(self.first() // 10 + 1) * 10)
        while sec <= min(length, self.first() + self.SPAN):
            text = clock(sec)
            tw = fm.horizontalAdvance(text)
            x = self.x_of(sec) - tw / 2
            if 0 <= x <= w - tw:
                p.drawText(QRectF(x, y, tw + 2, 16), Qt.AlignLeft | Qt.AlignVCenter, text)
            sec += 10


class StepMark(QWidget):
    """The mark before a step: an empty ring (todo), a turning ring (doing), a green tick (done)
    or a red ring (failed)."""

    def __init__(self):
        super().__init__()
        self.state, self.angle = "todo", 0
        self.setFixedSize(22, 22)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.turn)

    def turn(self):
        self.angle = (self.angle + 24) % 360
        self.update()

    def set_state(self, state):
        self.state = state
        if state == "doing":
            self.timer.start(60)
        else:
            self.timer.stop()
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        box = QRectF(2, 2, 18, 18)
        if self.state == "done":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colors["ok"]))
            p.drawEllipse(box)
            draw_icon(p, "check", QRectF(3, 3, 16, 16), colors["card"])
            return
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(colors["no" if self.state == "failed" else "line"]), 2))
        p.drawEllipse(box)
        if self.state == "doing":
            p.setPen(QPen(QColor(colors["accent"]), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(box, -self.angle * 16, 100 * 16)


class StepRow(QWidget):
    """One step of the build: its mark, what it is, and at the right what was found."""

    def __init__(self, todo, doing, done):
        super().__init__()
        self.texts = {"todo": todo, "doing": doing, "done": done, "failed": todo}
        self.state = "todo"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(10)
        self.mark, self.text, self.value = StepMark(), label(todo), label("", "sub")
        row.addWidget(self.mark)
        row.addWidget(self.text, 1)
        row.addWidget(self.value)

    def set(self, state, value=None):
        """state: todo, doing, done or failed. value: the text at the right (None keeps it)."""
        self.state = state
        self.mark.set_state(state)
        self.text.setText(self.texts[state])
        self.text.setObjectName("strong" if state == "doing" else "sub" if state == "todo" else "")
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)
        if value is not None:
            self.value.setText(value)


# ---- how the cells of the Songs table are drawn ---------------------------------------------
def _row_background(delegate, painter, option, index):
    """The cell's own background (the selected row's colour, the line under it), with no text."""
    style = option.widget.style() if option.widget else QApplication.style()
    blank = type(option)(option)
    delegate.initStyleOption(blank, index)
    blank.text = ""
    style.drawControl(QStyle.CE_ItemViewItem, blank, painter, option.widget)


class PillDelegate(QStyledItemDelegate):
    """Draws a table cell's text as a coloured label. The item's Qt.UserRole says which colours:
    "ok", "warn" or "no" (anything else: plain text)."""

    def paint(self, painter, option, index):
        text, kind = index.data(Qt.DisplayRole), index.data(Qt.UserRole)
        if not text or kind not in ("ok", "warn", "no"):
            super().paint(painter, option, index)
            return
        _row_background(self, painter, option, index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        w = painter.fontMetrics().horizontalAdvance(text) + 22
        h = min(option.rect.height() - 10, 24)
        rect = QRectF(option.rect.x() + 10, option.rect.center().y() - h / 2 + 1, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colors[kind + "bg"]))
        painter.drawRoundedRect(rect, h / 2, h / 2)
        painter.setPen(QColor(colors[kind]))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()


class ChipDelegate(QStyledItemDelegate):
    """Draws each part of the cell's text ("Lent, Easter") in a small outlined box."""

    def paint(self, painter, option, index):
        _row_background(self, painter, option, index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipRect(option.rect)
        brush = index.data(Qt.ForegroundRole)
        dim = brush is not None and QColor(brush.color() if hasattr(brush, "color") else brush) == QColor(colors["off"])
        x, h = option.rect.x() + 10.0, 24.0
        for text in [t.strip() for t in (index.data(Qt.DisplayRole) or "").split(",") if t.strip()]:
            w = painter.fontMetrics().horizontalAdvance(text) + 18
            rect = QRectF(x, option.rect.center().y() - h / 2 + 1, w, h)
            painter.setPen(QPen(QColor(colors["line"]), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(colors["off" if dim else "sub"]))
            painter.drawText(rect, Qt.AlignCenter, text)
            x += w + 6
        painter.restore()


class SwitchDelegate(QStyledItemDelegate):
    """Draws the cell as an on / off switch. The item's Qt.UserRole is True for on."""

    def paint(self, painter, option, index):
        _row_background(self, painter, option, index)
        on = bool(index.data(Qt.UserRole))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = 40.0, 22.0
        rect = QRectF(option.rect.x() + 16, option.rect.center().y() - h / 2 + 1, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colors["accent" if on else "track"]))
        painter.drawRoundedRect(rect, h / 2, h / 2)
        painter.setBrush(QColor("white" if on else colors["knob"]))
        r = h / 2 - 3
        painter.drawEllipse(QPointF(rect.right() - h / 2 if on else rect.left() + h / 2, rect.center().y()), r, r)
        painter.restore()


class PlayDelegate(QStyledItemDelegate):
    """Draws a round play button in the cell."""

    def paint(self, painter, option, index):
        _row_background(self, painter, option, index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        d = 28.0
        circle = QRectF(option.rect.center().x() - d / 2 + 1, option.rect.center().y() - d / 2 + 1, d, d)
        painter.setPen(QPen(QColor(colors["line"]), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(circle)
        draw_icon(painter, "play", circle.adjusted(6, 6, -6, -6), colors["sub"])
        painter.restore()


class DateField(QDateEdit):
    """The service date, with a pop-out calendar (weeks start on Sunday). get() is the date shown;
    changed is True once the person picked a date themselves (set_date from code does not count)."""

    def __init__(self, date=None):
        super().__init__()
        self.changed = False
        self.setCalendarPopup(True)
        self.setDisplayFormat("ddd, MMM d, yyyy")
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
