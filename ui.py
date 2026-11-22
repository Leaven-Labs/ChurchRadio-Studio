"""The look of the app (Qt): colours for light and dark, the style sheet, and small shared parts.

theme in config.json: "auto" (follow the system), "light" or "dark".

The look is the website's (docs/index.html): its gradient of navy, blue and green with gold for a
spark, its heading typeface (fraunces.py), a glow under what matters, and a few small animations.
The animations run only while the window is shown; `motion` in config.json turns them off.
"""
import math
import os
import re

from PySide6.QtCore import (QByteArray, QDate, QEasingCurve, QElapsedTimer, QEvent, QObject, QPointF, QRectF,
                            QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QDateEdit, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QSizePolicy, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

import paths
from churchyear import default_service_date

THEMES = ("auto", "light", "dark")
THEME_LABELS = {"auto": "Same as the system", "light": "Light", "dark": "Dark"}

LIGHT = dict(bg="#f4f5f8", side="#ebedf2", card="#ffffff", text="#1c2330", sub="#667085", line="#e1e4ea",
             accent="#2f6fd0", accent2="#255bb0", soft="#eaf1fc", softline="#9dbcf0", log="#fbfbfc", sel="#e4edfb",
             hover="#eef0f4", ok="#1a7f4b", okbg="#e3f5ea", warn="#9a5b00", warnbg="#fdf1dc", no="#b42318",
             nobg="#fde8e6", off="#98a1b0", disabled="#b4bac4", intro="#8b6fe0", song="#2aa98c", track="#cfd4dc",
             knob="#ffffff",
             # the website's gradient (g1 to g3) and its gold, its gradient words (t1, t2), the buttons' gradient
             g1="#1f3a68", g2="#2f6fd0", g3="#2aa98c", spark="#f2c14e", t1="#2f6fd0", t2="#1c9a80",
             btn1="#2559b4", btn2="#2a86b6", glow=0.7)
DARK = dict(bg="#14171c", side="#191c23", card="#1f232d", text="#e8ebf0", sub="#98a1b0", line="#2c323d",
            accent="#5b93e8", accent2="#4a80d4", soft="#1a2434", softline="#3d5f99", log="#191c23", sel="#22304a",
            hover="#272c37", ok="#5fd093", okbg="#173524", warn="#f0b45a", warnbg="#3a2c12", no="#f58a80",
            nobg="#402019", off="#6b7483", disabled="#565d6a", intro="#a78bfa", song="#45c4a8", track="#3a414d",
            knob="#aab2c0",
            g1="#1f3a68", g2="#2f6fd0", g3="#2aa98c", spark="#f2c14e", t1="#7aa8ee", t2="#45c4a8",
            btn1="#4a80d4", btn2="#3d93c9", glow=0.9)

colors = dict(LIGHT)  # the colours in use (changed in place by apply_theme)
DISPLAY = "Fraunces"  # the headings' typeface (fraunces.py); without it Qt takes the system's
motion = True  # the small animations; set_motion() changes it (`motion` in config.json)


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
QLabel#title {{ font-family: "{DISPLAY}"; font-size: 20px; font-weight: 600; }}
QLabel#appname {{ font-family: "{DISPLAY}"; font-size: 17px; font-weight: 600; }}
QLabel#pagetitle {{ font-family: "{DISPLAY}"; font-size: 27px; font-weight: 600; }}
QLabel#big {{ font-size: 15px; font-weight: 600; }}
QLabel#caps {{ font-size: 11px; font-weight: 700; color: {c['sub']}; }}
QLabel#small {{ font-size: 12px; color: {c['sub']}; }}
QLabel#pill {{ font-weight: 600; border-radius: 11px; padding: 3px 10px; }}
QLabel#pill[kind="ok"] {{ background: {c['okbg']}; color: {c['ok']}; }}
QLabel#pill[kind="warn"] {{ background: {c['warnbg']}; color: {c['warn']}; }}
QLabel#pill[kind="no"] {{ background: {c['nobg']}; color: {c['no']}; }}
QLabel#heading {{ font-family: "{DISPLAY}"; font-size: 19px; font-weight: 600; }}
QLabel#sub, QLabel#hint {{ color: {c['sub']}; }}
QLabel#strong {{ font-weight: 600; }}
QLabel#error {{ color: {c['no']}; }}
QLabel#warntext {{ color: {c['warn']}; }}
QFrame#drop {{ background: {c['soft']}; border: 2px dashed {c['softline']}; border-radius: 12px; }}
QFrame#drop[has="true"] {{ background: {c['card']}; border: 1px solid {c['line']}; }}
QFrame#drop[over="true"] {{ border: 2px solid {c['accent']}; }}
QLabel#dropbig {{ font-family: "{DISPLAY}"; font-size: 21px; font-weight: 600; color: {c['accent']}; }}
QPushButton {{ background: {c['card']}; border: 1px solid {c['line']}; border-radius: 8px; padding: 7px 16px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['sel']}; }}
QPushButton:focus {{ border-color: {c['softline']}; }}
QPushButton:disabled {{ color: {c['disabled']}; }}
QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['btn1']}, stop:1 {c['btn2']});
    border: 1px solid {c['btn1']}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['btn2']}, stop:1 {c['btn1']}); }}
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
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['g2']}, stop:1 {c['g3']});
    border-radius: 3px; }}
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
QScrollBar#track:horizontal {{ background: {c['line']}; border-radius: 4px; height: 8px; margin: 0; }}
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


def set_motion(on):
    """Turn the small animations on or off (what is already on screen stops by itself)."""
    global motion
    motion = bool(on)


def load_display_font():
    """Give Qt the headings' typeface. Without it (a broken install) the headings are in the system's."""
    if DISPLAY in QFontDatabase.families():
        return
    import fraunces
    QFontDatabase.addApplicationFontFromData(QByteArray(fraunces.TTF))


def start_app(argv, theme="auto"):
    """The QApplication, with the Fusion style (the same on every system), the icon and the theme."""
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(paths.APP_NAME)
    app.setStyle("Fusion")
    load_display_font()
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
    lab = Title(text) if kind == "pagetitle" else QLabel(text)
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


# ---- gradients, glows and what moves --------------------------------------------------------
def mix(a, b, t):
    """The colour a part t (0 to 1) of the way from a to b."""
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def gradient(x1, x2, *names):
    """A left-to-right gradient from x1 to x2 through the named colours of the theme."""
    g = QLinearGradient(x1, 0, x2, 0)
    for i, name in enumerate(names):
        g.setColorAt(i / (len(names) - 1), QColor(colors[name]))
    return g


def glide(owner, change, ms=180):
    """An animation from 0 to 1 that calls change(value); start it with .setDirection() and .start()."""
    anim = QVariantAnimation(owner)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(ms)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.valueChanged.connect(change)
    return anim


class Moving(QWidget):
    """A widget with a clock: tick(seconds) is called 25 times a second while the widget is shown,
    wanted() is true and the animations are on. Hidden (the window is minimised), nothing runs."""

    def __init__(self):
        super().__init__()
        self._clock = QTimer(self)
        self._clock.setInterval(40)
        self._clock.timeout.connect(self._step)
        self._since = QElapsedTimer()

    moving = property(lambda self: self._clock.isActive())

    def wanted(self):
        return True

    def wake(self):
        """Start or stop the clock, after something changed."""
        if motion and self.isVisible() and self.wanted():
            if not self._clock.isActive():
                self._since.start()
                self._clock.start()
        elif self._clock.isActive():
            self._clock.stop()
            self.update()

    def showEvent(self, _event):  # noqa: N802
        self.wake()

    def hideEvent(self, _event):  # noqa: N802
        self._clock.stop()

    def _step(self):
        if not (motion and self.wanted()):
            self._clock.stop()
        else:
            self.tick(self._since.elapsed() / 1000)
        self.update()

    def tick(self, seconds):
        pass


class Title(QLabel):
    """A page's title in the gradient of the website's headline. A band of gold light crosses it once
    each time the page is shown."""

    def __init__(self, text=""):
        super().__init__(text)
        self.shine = 2.0  # where the band is, 0 (left) to 1 (right); outside that there is none
        self.sweep = glide(self, self._move, 1100)
        self.sweep.setEasingCurve(QEasingCurve.InOutSine)

    def _move(self, t):
        self.shine = -0.2 + 1.4 * t
        self.update()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if motion:
            self.sweep.stop()
            self.sweep.start()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(self.font())
        width = max(1, self.fontMetrics().horizontalAdvance(self.text()))
        left = self.contentsRect().left()
        g = QLinearGradient(left, 0, left + width, 0)
        g.setColorAt(0, QColor(colors["t1"]))
        g.setColorAt(1, QColor(colors["t2"]))
        for offset, light in ((-0.1, 0), (0, 0.9), (0.1, 0)):
            at = self.shine + offset
            if 0 < at < 1:
                g.setColorAt(at, mix(mix(colors["t1"], colors["t2"], at), colors["spark"], light))
        p.setPen(QPen(QBrush(g), 1))
        p.drawText(self.contentsRect(), Qt.AlignLeft | Qt.AlignVCenter, self.text())
        p.end()


class _Glow(QObject):
    """The glow under a main button: it grows while the pointer is on the button, and is gone while
    the button cannot be pressed."""

    def __init__(self, button):
        super().__init__(button)
        self.button = button
        self.effect = QGraphicsDropShadowEffect(button)
        self.effect.setOffset(0, 4)
        button.setGraphicsEffect(self.effect)
        self.rise = glide(self, self._lift)
        self._lift(0.0)
        self.effect.setEnabled(button.isEnabled())
        button.installEventFilter(self)

    def _lift(self, t):
        color = QColor(colors["g2"])
        color.setAlpha(round((0.42 + 0.3 * t) * colors["glow"] * 255))
        self.effect.setColor(color)
        self.effect.setBlurRadius(16 + 12 * t)

    def eventFilter(self, _obj, event):  # noqa: N802
        kind = event.type()
        if kind == QEvent.EnabledChange:
            self.effect.setEnabled(self.button.isEnabled())
        elif kind in (QEvent.Enter, QEvent.Leave) and motion and self.button.isEnabled():
            self.rise.setDirection(QVariantAnimation.Forward if kind == QEvent.Enter else QVariantAnimation.Backward)
            self.rise.start()
        return False


def primary(button):
    """Make `button` the main button of its page or window: the gradient (in the style sheet) and a
    glow under it."""
    button.setObjectName("primary")
    _Glow(button)
    return button


_strips = {}


def _glow_strip(width):
    """A soft band of the gradient, `width` wide when drawn: painted small and drawn large, which blurs it."""
    key = (max(8, width // 10), colors["g2"], colors["g3"])
    if key not in _strips:
        if len(_strips) > 40:
            _strips.clear()
        w, h = key[0], 10
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        p = QPainter(image)
        p.fillRect(0, 0, w, h, gradient(0, w, "g2", "g3"))
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        down = QLinearGradient(0, 0, 0, h)  # strongest in the middle, nothing at the top and bottom
        for at, alpha in ((0, 0), (0.5, 255), (1, 0)):
            down.setColorAt(at, QColor(0, 0, 0, alpha))
        p.fillRect(0, 0, w, h, down)
        across = QLinearGradient(0, 0, w, 0)  # and nothing at the two ends
        for at, alpha in ((0, 0), (0.18, 255), (0.82, 255), (1, 0)):
            across.setColorAt(at, QColor(0, 0, 0, alpha))
        p.fillRect(0, 0, w, h, across)
        p.end()
        _strips[key] = image
    return _strips[key]


class Underglow(Moving):
    """Holds one widget (a card) and lets the gradient glow under its lower edge, as under the website's
    buttons and screenshot. The glow breathes slowly. It is shown and hidden with its widget."""
    ROOM, INSET = 14, 26

    def __init__(self, child):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, self.ROOM)
        box.addWidget(child)
        self.child, self.level = child, 0.8
        child.installEventFilter(self)
        self.setVisible(not child.isHidden())

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.child and event.type() in (QEvent.ShowToParent, QEvent.HideToParent):
            self.setVisible(event.type() == QEvent.ShowToParent)
        return False

    def tick(self, seconds):
        self.level = 0.72 + 0.28 * math.sin(seconds * 2 * math.pi / 5)

    def paintEvent(self, _event):  # noqa: N802
        width = self.width() - 2 * self.INSET
        if width < 40:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(self.level * colors["glow"])
        p.drawImage(QRectF(self.INSET, self.height() - 2 * self.ROOM - 2, width, 2 * self.ROOM + 2), _glow_strip(width))
        p.end()


class Beam(Moving):
    """The gradient line along the top of the window. While a broadcast is being made (set_busy), a
    band of gold light runs along it."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(3)
        self.busy, self.at, self.lap = False, -1.0, 0

    def set_busy(self, on):
        self.busy = on
        self.wake()

    def wanted(self):
        return self.busy or self.at >= 0

    def tick(self, seconds):
        lap, part = divmod(seconds / 1.8, 1)
        if not self.busy and (self.at < 0 or lap != self.lap):  # the work is done: this run was the last
            self.at = -1.0
            return
        self.at, self.lap = part, lap

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        w = self.width()
        p.fillRect(self.rect(), gradient(0, w, "g1", "g2", "g3"))
        if self.moving and self.at >= 0:
            mid = (-0.15 + 1.3 * self.at) * w
            light = QLinearGradient(mid - 0.12 * w, 0, mid + 0.12 * w, 0)
            spark = QColor(colors["spark"])
            for at, alpha in ((0, 0), (0.5, 255), (1, 0)):
                spark.setAlpha(alpha)
                light.setColorAt(at, spark)
            p.fillRect(self.rect(), light)
        p.end()


class Curtain(QWidget):
    """Laid over the pages when another page is chosen, in the window's colour, and faded away at once:
    the new page seems to fade in. Nothing is put on the pages themselves."""

    def __init__(self, over):
        super().__init__(over)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.alpha = 0.0
        self.fade = glide(self, self._set, 220)
        self.fade.finished.connect(self.hide)
        self.hide()

    def _set(self, t):
        self.alpha = 1 - t
        self.update()

    def drop(self):
        over = self.parentWidget()
        if not (motion and over.isVisible()):
            return
        self.setGeometry(over.rect())
        self.alpha = 1.0
        self.raise_()
        self.show()
        self.fade.stop()
        self.fade.start()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        color = QColor(colors["bg"])
        color.setAlphaF(self.alpha)
        p.fillRect(self.rect(), color)
        p.end()


class Side(QFrame):
    """The menu's column at the left: its colour, with the gradient's blue glowing softly from the
    corner behind the app's name and a little green from the bottom."""

    def __init__(self):
        super().__init__()
        self.setObjectName("side")

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(colors["side"]))
        for name, center, radius, strength in (("g2", QPointF(20, 10), 300, 0.26),
                                               ("g3", QPointF(self.width() * 0.2, self.height() + 40), 260, 0.16)):
            color = QColor(colors[name])
            glow = QRadialGradient(center, radius)
            color.setAlphaF(strength * colors["glow"])
            glow.setColorAt(0, color)
            color.setAlphaF(0)
            glow.setColorAt(1, color)
            p.fillRect(self.rect(), glow)
        p.setPen(QColor(colors["line"]))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        p.end()


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
    """A line of the menu at the left: an icon and a name. The page shown is the checked one; it has a
    short line of the gradient at its left that grows when it is chosen."""

    def __init__(self, icon, text):
        super().__init__()
        self.icon_name = icon
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.on = 0.0  # how far it is chosen, 0 to 1
        self.slide = glide(self, self._set, 220)
        self.toggled.connect(self._choose)

    def _set(self, t):
        self.on = t
        self.update()

    def _choose(self, checked):
        if motion and self.isVisible():
            self.slide.setDirection(QVariantAnimation.Forward if checked else QVariantAnimation.Backward)
            self.slide.start()
        else:
            self.slide.stop()
            self._set(1.0 if checked else 0.0)

    def sizeHint(self):  # noqa: N802
        return QSize(180, 40)

    def enterEvent(self, event):  # noqa: N802
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on, r = self.isChecked(), QRectF(self.rect()).adjusted(0, 1, 0, -1)
        p.setPen(Qt.NoPen)
        if self.underMouse() and self.isEnabled() and not on:
            p.setBrush(QColor(colors["hover"]))
            p.drawRoundedRect(r, 9, 9)
        if self.on > 0:
            p.setOpacity(self.on)
            p.setBrush(QColor(colors["card"]))
            p.drawRoundedRect(r, 9, 9)
            p.setOpacity(1)
            tall = 18 * self.on
            line = QLinearGradient(0, r.center().y() - 9, 0, r.center().y() + 9)
            line.setColorAt(0, QColor(colors["g2"]))
            line.setColorAt(1, QColor(colors["g3"]))
            p.setBrush(line)
            p.drawRoundedRect(QRectF(0, r.center().y() - tall / 2, 3, tall), 1.5, 1.5)
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
    """The broadcast as one bar: the intro, the service and each song, to scale. When a new hour is
    shown, the bar fills once from the left behind a gold needle, as on the website."""
    COLORS = {"intro": "intro", "service": "accent", "song": "song"}

    def __init__(self):
        super().__init__()
        self.parts, self.filled = [], 1.0
        self.setFixedHeight(40)
        self.fill = glide(self, self._fill, 1300)

    def _fill(self, t):
        self.filled = t
        self.update()

    def set_parts(self, parts):
        """parts: [(kind, seconds, text drawn in the part if it fits)], kind: intro, service or song."""
        parts = [p for p in parts if p[1] > 0]
        new = parts != self.parts
        self.parts = parts
        self.fill.stop()
        self.filled = 1.0
        if new and parts and motion and self.isVisible():
            self.fill.start()
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 9, 9)
        p.setClipPath(clip)
        total = sum(sec for _kind, sec, _text in self.parts)
        p.fillRect(rect, QColor(colors["line"]))
        if not total:
            return
        edge = rect.width() * self.filled
        p.setClipRect(QRectF(0, 0, edge, rect.height()), Qt.IntersectClip)
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
        if self.filled < 1:  # the needle, with its light
            p.setClipPath(clip)
            spark = QColor(colors["spark"])
            for wide, alpha in ((14, 40), (8, 70), (3, 255)):
                spark.setAlpha(alpha)
                p.fillRect(QRectF(edge - wide / 2, 0, wide, rect.height()), spark)


def clock(sec):
    """A place in a recording or a length: "9:02", "1:08:15"."""
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class Waveform(QWidget):
    """The recording drawn as its loudness along its length, with the two cuts marked: the part
    that is broadcast is bright, what is cut off before the start and after the end is dim.

    It shows the whole recording, or (zoomed in) a part of it: zoom(), zoom_to(), show_all();
    Ctrl + the mouse wheel zooms where the pointer is.

    A click or a drag beside the cuts puts the play marker there (playhead: where the recording
    is played from, see MainWindow.play_line); sought tells where it was put.

    Keys: a click on a cut, or Tab, chooses it (chosen; it is drawn with a ring while the picture
    has the keyboard); the left and right arrows move it a second (with Shift, NUDGE_FAR seconds)."""
    TOP, BOTTOM = 30, 24  # room for the cut labels above the wave and the times under it
    GRAB = 9              # a click this many pixels from a cut's line takes hold of it
    APART = 30.0          # the cuts stay at least this many seconds apart
    MIN_SPAN = 10.0       # zoomed in as far as it goes: this many seconds across the picture
    CUT_SPAN = 120.0      # zoom_to: this many seconds around a cut
    NUDGE_FAR = 5.0       # Shift + an arrow moves the chosen cut this many seconds
    moved = Signal(str)   # the person moved a cut ("start" or "end"): mouse, nudge() or place()
    changed = Signal()    # the cuts or what is known of the recording changed
    sought = Signal(float)  # the person put the play marker at this second (click, or the end of a drag)
    viewed = Signal()     # the part of the recording shown changed (zoom, scroll)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(self.TOP + 72 + self.BOTTOM)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.editable, self.drag, self.seeking, self.view, self.playhead = False, None, False, None, None
        self.chosen = None  # the cut the arrow keys move: "start", "end" or None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setToolTip("Click a cut (or press Tab) to choose it, then move it with the left and right arrows "
                        "(1 second; with Shift, 5). S and E put the start and end cut at the play marker. "
                        "The space bar plays and pauses.")
        self.reset()

    def reset(self):
        """A new recording: nothing is known yet."""
        self.levels, self.length, self.cuts, self.note = None, 0.0, {}, "Reading the recording ..."
        self.detail, self.per_second = None, 0  # the loudness in small slices, drawn when zoomed in
        self.drag, self.seeking, self.playhead, self.chosen = None, False, None, None
        was, self.view = self.view, None  # zoomed in: (the first second shown, how many seconds)
        self.redraw()
        if was:
            self.viewed.emit()

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

    # ---- the part of the recording shown ------------------------------------------------
    def zoomed(self):
        return self.view is not None

    def first(self):
        """The second at the left edge."""
        return self.view[0] if self.view else 0.0

    def span(self):
        """How many seconds are shown across the picture."""
        return self.view[1] if self.view else self.length

    def x_of(self, sec):
        return (sec - self.first()) / self.span() * self.width() if self.length else 0.0

    def seconds_at(self, x):
        return self.first() + x / max(1, self.width()) * self.span()

    def show_part(self, first, span):
        """Show `span` seconds from second `first` (kept inside the recording)."""
        if not self.length:
            return
        span = min(max(span, self.MIN_SPAN), self.length)
        view = None if span >= self.length - 0.01 else (min(max(first, 0.0), self.length - span), span)
        if view != self.view:
            self.view = view
            self.redraw()
            self.viewed.emit()

    def zoom(self, factor, around=None):
        """Zoom in (factor below 1) or out. around: the second that stays where it is (the middle
        of the picture if not given)."""
        if not self.length:
            return
        span = self.span()
        around = self.first() + span / 2 if around is None else around
        new = min(max(span * factor, self.MIN_SPAN), self.length)
        self.show_part(around - (around - self.first()) / span * new, new)

    def zoom_to(self, which):
        """Show a cut from near: CUT_SPAN seconds with the cut in the middle (or as much closer
        as the picture already is)."""
        span = min(self.span(), self.CUT_SPAN)
        self.show_part(self.cut_at(which) - span / 2, span)

    def show_all(self):
        self.show_part(0.0, self.length)

    # ---- the cuts -----------------------------------------------------------------------
    def cut_at(self, which):
        """The second a cut is at (a cut that cuts nothing: the very start or end of the recording)."""
        at = self.cuts.get(which)
        return at if at else 0.0 if which == "start" else self.length

    def cut_x(self, which):
        """Where the line of a cut is drawn (left of 0 or right of the width: not in the part shown)."""
        if not self.length:
            return 0.0 if which == "start" else float(self.width())
        return self.x_of(min(max(self.cut_at(which), 0.0), self.length))

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
        self.place(which, self.cut_at(which) + seconds)

    def place(self, which, seconds):
        """The person puts a cut at `seconds` (a time typed, or a nudge)."""
        if self.editable and self.known():
            self.move_cut(which, seconds)
            self.moved.emit(which)

    def set_playhead(self, seconds):
        """Put the play marker at `seconds` (None: no marker)."""
        at = None if seconds is None or not self.length else min(max(seconds, 0.0), self.length)
        if at != self.playhead:
            self.playhead = at
            self.update()

    def cut_near(self, x):
        """The cut whose line is at x (within GRAB), or None."""
        if not (self.editable and self.known()):
            return None
        near = sorted((abs(x - self.cut_x(which)), which) for which in ("start", "end"))
        return near[0][1] if near[0][0] <= self.GRAB else None

    def choose(self, which):
        """Choose the cut the arrow keys move (None: none)."""
        if which != self.chosen:
            self.chosen = which
            self.update()

    def focusInEvent(self, event):  # noqa: N802
        """Tab into the picture chooses the start cut (Shift+Tab: the end cut)."""
        if self.editable and self.known() and event.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason):
            self.choose("start" if event.reason() == Qt.TabFocusReason else "end")
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):  # noqa: N802
        self.update()
        super().focusOutEvent(event)

    def focusNextPrevChild(self, forward):  # noqa: N802
        """Tab goes from the start cut to the end cut, then on to the next control (Shift+Tab back)."""
        if self.editable and self.known() and self.hasFocus():
            if forward and self.chosen == "start":
                self.choose("end")
                return True
            if not forward and self.chosen == "end":
                self.choose("start")
                return True
        return super().focusNextPrevChild(forward)

    def keyPressEvent(self, event):  # noqa: N802
        step = {Qt.Key_Left: -1.0, Qt.Key_Right: 1.0}.get(event.key())
        if step and self.chosen and self.editable and self.known():
            self.nudge(self.chosen, step * (self.NUDGE_FAR if event.modifiers() & Qt.ShiftModifier else 1.0))
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            self.drag = self.cut_near(x)
            if self.drag:
                self.choose(self.drag)
            if not self.drag and self.known():  # beside the cuts: the play marker goes there
                self.seeking = True
                self.set_playhead(self.seconds_at(x))

    def mouseMoveEvent(self, event):  # noqa: N802
        x = event.position().x()
        if self.drag and self.width():
            self.move_cut(self.drag, self.seconds_at(x))
        elif self.seeking:
            self.set_playhead(self.seconds_at(x))
        elif self.cut_near(x):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        if self.drag:
            which, self.drag = self.drag, None
            self.moved.emit(which)
        if self.seeking:
            self.seeking = False
            self.sought.emit(self.playhead or 0.0)

    def wheelEvent(self, event):  # noqa: N802
        """Ctrl + wheel zooms where the pointer is; zoomed in, Shift + wheel (or a sideways
        wheel) moves along the recording. A plain wheel scrolls the page, as everywhere."""
        up, side = event.angleDelta().y(), event.angleDelta().x()
        if self.length and up and event.modifiers() & Qt.ControlModifier:
            self.zoom(0.8 if up > 0 else 1.25, self.seconds_at(event.position().x()))
        elif self.zoomed() and (side or (up and event.modifiers() & Qt.ShiftModifier)):
            self.show_part(self.first() - (side or up) / 120 * self.span() / 8, self.span())
        else:
            event.ignore()
            return
        event.accept()

    def set_levels(self, levels, detail=None, per_second=0):
        """levels: numbers 0..1 along the recording, or None if it failed; detail: the same in small
        slices, per_second of them for each second (audio.loudness_picture)."""
        self.levels = levels or None
        self.detail, self.per_second = (detail, per_second) if levels and detail and per_second else (None, 0)
        self.note = "" if levels else "The recording could not be drawn. The broadcast is not affected."
        self.redraw()

    def set_length(self, seconds):
        self.length = max(0.0, seconds or 0.0)
        if self.view and self.view[0] + self.view[1] > self.length:
            self.view = None
            self.viewed.emit()
        self.redraw()

    def set_cut(self, which, seconds):
        """which: "start" or "end". seconds into the recording; None or 0 = nothing cut there."""
        self.cuts[which] = seconds or None
        self.redraw()

    def level(self, a, b):
        """The loudness (0..1) from second a to b: from the small slices when the picture is
        zoomed in further than the outline of the whole recording shows."""
        n = len(self.levels)
        if self.detail and b - a < self.length / n:
            i = int(a * self.per_second)
            some = self.detail[i:max(i + 1, int(b * self.per_second))]
            return sum(some) / len(some) if some else 0.0
        return self.levels[min(n - 1, max(0, int(a / self.length * n)))] if self.length else 0.0

    def steps(self):
        """The times written under the wave: at most six, at round minutes (zoomed in: at round
        seconds too)."""
        sizes = (60, 120, 300, 600, 900, 1800, 3600, 7200)
        first, span = self.first(), self.span()
        for step in ((1, 2, 5, 10, 15, 30) + sizes) if self.zoomed() else sizes:
            if span / step <= 5.5:
                return [t * step for t in range(int(-(-first // step)), int((first + span) // step) + 1)]
        return [0]

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, mid_h = float(self.width()), self.height() - self.TOP - self.BOTTOM
        wave = QRectF(0, self.TOP, w, mid_h)
        length = self.length
        known = bool(length) and bool(self.cuts)
        start, end = self.cut_x("start"), self.cut_x("end")
        cut_from, cut_to = min(max(start, 0.0), w), min(max(end, 0.0), w)  # (of the part shown)

        for part in ((0.0, cut_from), (cut_to, w)) if known else ():  # what is cut off: a darker ground
            if part[1] - part[0] > 0.5:
                p.fillRect(QRectF(part[0], self.TOP, part[1] - part[0], mid_h), QColor(colors["bg"]))
        p.setPen(Qt.NoPen)
        if self.levels and length:
            x, cy, per_bar = 1.0, wave.center().y(), self.span() / w * 4
            while x < w - 1:
                sec = self.seconds_at(x)
                h = max(2.0, self.level(sec, sec + per_bar) * (mid_h - 8))
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
            off = {"left": 0.0, "right": 0.0}  # room taken by the labels of cuts that are not in the part shown
            for which, x, name in (("start", start, "Start"), ("end", end, "End")):
                at = self.cuts.get(which)
                text = f"{name} {clock(at)}" if at else f"{name}: nothing cut"
                side = "left" if x < -0.5 else "right" if x > w + 0.5 else ""
                text = f"‹ {text}" if side == "left" else f"{text} ›" if side == "right" else text
                p.setFont(font)
                tw = p.fontMetrics().horizontalAdvance(text) + 18
                if side:  # the cut is to the left or right of the part shown: its label waits at that edge
                    left = off[side] if side == "left" else w - tw - off[side]
                    off[side] += tw + 4
                else:
                    left = min(max(x - 1 if which == "start" else x + 1 - tw, 0.0), w - tw)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(colors["accent"]))
                p.setOpacity(0.6 if side else 1.0)
                p.drawRoundedRect(QRectF(left, 0, tw, 22), 5, 5)
                if which == self.chosen and self.hasFocus() and self.editable:  # the cut the arrows move
                    p.setOpacity(1.0)
                    p.setPen(QPen(QColor(colors["spark"]), 2))
                    p.setBrush(Qt.NoBrush)
                    p.drawRoundedRect(QRectF(left + 1, 1, tw - 2, 20), 5, 5)
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(colors["accent"]))
                    p.setOpacity(0.6 if side else 1.0)
                if not side:
                    p.drawRect(QRectF(min(max(x - 1, 0.0), w - 2), 20, 2, self.height() - self.BOTTOM - 20))
                p.setOpacity(1.0)
                p.setPen(QColor("white"))
                p.drawText(QRectF(left, 0, tw, 22), Qt.AlignCenter, text)

        if self.playhead is not None and length and -0.5 <= self.x_of(self.playhead) <= w + 0.5:
            x = min(max(self.x_of(self.playhead), 1.0), w - 1)  # the play marker: a thin line with a head
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colors["text"]))
            p.drawRect(QRectF(x - 0.75, self.TOP - 4, 1.5, mid_h + 8))
            p.drawPolygon(QPolygonF([QPointF(x - 5, self.TOP - 9), QPointF(x + 5, self.TOP - 9), QPointF(x, self.TOP - 1)]))

        if length:  # the times under the wave; the last one is the length of the recording
            p.setFont(self.font())
            p.setPen(QColor(colors["sub"]))
            fm, y = p.fontMetrics(), self.height() - self.BOTTOM + 6
            last_x = w
            if not self.zoomed():
                last = clock(length)
                last_x = w - fm.horizontalAdvance(last)
                p.drawText(QRectF(last_x, y, w - last_x, 18), Qt.AlignLeft | Qt.AlignVCenter, last)
            for sec in self.steps():
                text = clock(sec)
                tw = fm.horizontalAdvance(text)
                x = min(max(self.x_of(sec) - (tw / 2 if sec else 0), 0.0), w - tw)
                if x + tw + (14 if not self.zoomed() else 0) <= last_x:
                    p.drawText(QRectF(x, y, tw + 2, 18), Qt.AlignLeft | Qt.AlignVCenter, text)


def parse_clock(text):
    """The seconds of a place in a recording as a person types it: "9:02", "9:02.4", "1:08:15",
    "542" or "542.5" (a comma works as the point). None if it is not a time."""
    parts = text.strip().replace(",", ".").split(":")
    if not 1 <= len(parts) <= 3 or not all(re.fullmatch(r"\d+", part) for part in parts[:-1]) \
            or not re.fullmatch(r"\d+(\.\d*)?", parts[-1]):
        return None
    if len(parts) > 1 and (float(parts[-1]) >= 60 or (len(parts) == 3 and int(parts[1]) >= 60)):
        return None
    sec = 0.0
    for part in parts:
        sec = sec * 60 + float(part)
    return sec


def clock_exact(sec):
    """A place in a recording to a tenth of a second: "9:02.4"."""
    tenths = int(round(sec * 10))
    return f"{clock(tenths // 10)}.{tenths % 10}"


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
        if on:
            track = QLinearGradient(rect.left(), 0, rect.right(), 0)
            track.setColorAt(0, QColor(colors["btn1"]))
            track.setColorAt(1, QColor(colors["btn2"]))
            painter.setBrush(track)
        else:
            painter.setBrush(QColor(colors["track"]))
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
