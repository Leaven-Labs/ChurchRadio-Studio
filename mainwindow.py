"""The main window (Qt): a menu at the left and four pages: Broadcast (drop a service recording on
it to make the broadcast MP3), Songs, History and Settings."""
import atexit
import datetime as dt
import os
import queue
import threading
import time

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QScrollBar, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import audio
import builder
import catalog
import churchyear
import servicecal
import cli
import paths
import player
import prelude
import setup_wizard
import songs_window
import ui
import updates

MEDIA = "Service recordings (*.mkv *.mp4 *.wav *.mp3 *.m4a);;All files (*)"
CLIP_SECONDS = 12  # how much "Play from start cut" and "Play to end cut" play
LINE_SECONDS = 60  # Play under the picture: the recording is played in pieces of this length, one after the other
# (a longer piece takes longer to cut before the sound starts: about a second for five minutes)
NUDGES = (-5, -1, 1, 5)  # the small buttons that move a cut, in seconds
ZOOM_STEP = 0.5  # the zoom buttons: half (or twice) as many seconds across the picture
UPDATE_CHECK_MS = 1500  # the app looks for a new version this long after its window opens
CREDIT = "Created by Aaron Steger. Published by Leaven Labs."
PAGES = (("broadcast", "Broadcast"), ("songs", "Songs"), ("history", "History"), ("settings", "Settings"))
# What the window says it is doing, from the lines the build writes to the log: the words that
# mark the line, the step of the progress list it starts, and the status text.
STEPS = (("in the first", "start", "Finding the start of the service ..."),
         ("in the last", "end", "Finding the end of the service ..."),
         ("Cutting long silences", "silence", "Cutting long silences ..."),
         ("Reading song catalog", "songs", "Choosing the songs ..."),
         ("Listening to", "songs", "Listening to new songs ..."),
         ("Evening out the loudness", "mp3", "Evening out the loudness ..."),
         ("Writing MP3", "mp3", "Writing the MP3 ..."))
# The progress list: a step's name before, while and after it is done.
STEP_ROWS = (("start", "Find the start", "Finding the start", "Found the start"),
             ("end", "Find the end", "Finding the end", "Found the end"),
             ("silence", "Cut long silences", "Cutting long silences", "Cut long silences"),
             ("songs", "Choose the songs", "Choosing the songs", "Chose the songs"),
             ("mp3", "Write the MP3", "Writing the MP3", "Wrote the MP3"))


def step_for(line):
    """The status text for a log line, or None if the line does not start a new step."""
    return next((text for mark, _key, text in STEPS if mark in line), None)


def step_key(line):
    """The step of the progress list a log line starts, or None."""
    return next((key for mark, key, _text in STEPS if mark in line), None)


def long_time(sec):
    """A length for reading: "1 h 14 min", "52 min"."""
    minutes = int(round(sec / 60))
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


clock = ui.clock


def time_left(seconds):
    """How long the MP3 will still take, for reading: "about 2 min left"."""
    if seconds < 45:
        return "less than a minute left"
    return f"about {max(1, int(round(seconds / 60)))} min left"


def nice_date(date):
    return f"{date:%a, %b} {date.day}, {date.year}"


def season_name(date):
    season = churchyear.season(date)
    return songs_window.SEASON_LABELS.get(season, season.title())


def about(parent):
    """Who made the app, its version and license, and where the third-party licenses are."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"About {paths.APP_NAME}")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(30, 22, 30, 18)
    lay.setSpacing(6)
    icon = QLabel()
    pix = QPixmap(paths.asset("icon-256.png"))
    if not pix.isNull():
        icon.setPixmap(pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(icon, 0, Qt.AlignCenter)
    for text, kind in ((paths.APP_NAME, "title"), (f"Version {paths.version()}", "sub"), ("", ""), (CREDIT, ""),
                       ("Free software under the MIT License.\nCopyright (c) 2026 Aaron Steger", ""),
                       ("The headings are set in Fraunces (SIL Open Font License).", "small")):
        lab = ui.label(text, kind)
        lab.setAlignment(Qt.AlignCenter)
        lay.addWidget(lab)

    def licenses():
        folder = os.path.join(paths.resources_dir(), "licenses")
        target = folder if os.path.isdir(folder) else os.path.join(paths.program_dir(), "LICENSE")
        try:
            songs_window.play(target)  # opens the folder / file in Explorer, Finder or the file manager
        except OSError as e:
            QMessageBox.critical(dlg, "About", str(e))

    def look():
        dlg.accept()
        parent.check_updates(asked=True)

    lic, close = QPushButton("Licenses"), QPushButton("Close")
    lic.setAutoDefault(False)
    lic.clicked.connect(licenses)
    upd = QPushButton("Check for updates")
    upd.setAutoDefault(False)
    upd.clicked.connect(look)
    close.setDefault(True)
    close.clicked.connect(dlg.accept)
    row = QHBoxLayout()
    row.addStretch()
    if hasattr(parent, "check_updates"):
        row.addWidget(upd)
    row.addWidget(lic)
    row.addWidget(close)
    row.addStretch()
    lay.addSpacing(10)
    lay.addLayout(row)
    dlg.exec()


class DropArea(QFrame):
    """The card a recording is dropped on. (The whole window takes drops; this shows it.) With no
    recording it asks for one; then it shows the recording's name, length and folder."""

    def __init__(self, on_browse, on_play=None):
        super().__init__()
        self.setObjectName("drop")
        self.setMinimumHeight(120)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)

        self.empty = QWidget()
        col = QVBoxLayout(self.empty)
        col.setAlignment(Qt.AlignCenter)
        col.setSpacing(4)
        big = ui.label("Drop the service recording here", "dropbig")
        big.setAlignment(Qt.AlignCenter)
        small = ui.label("MKV, MP4, WAV, MP3 or M4A", "sub")
        small.setAlignment(Qt.AlignCenter)
        self.browse = QPushButton("Browse...")
        ui.primary(self.browse)
        self.browse.setFixedWidth(130)
        self.browse.clicked.connect(on_browse)
        col.addWidget(big)
        col.addWidget(small)
        col.addSpacing(8)
        col.addWidget(self.browse, 0, Qt.AlignCenter)
        lay.addWidget(self.empty)

        self.file = QWidget()
        row = QHBoxLayout(self.file)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.addWidget(ui.IconTile("file", 52))
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setAlignment(Qt.AlignVCenter)
        self.name, self.where = ui.label("", "big"), ui.label("", "sub")
        col.addWidget(self.name)
        col.addWidget(self.where)
        row.addLayout(col, 1)
        self.play_start, self.play_end = QPushButton("Play from start cut"), QPushButton("Play to end cut")
        for which, b in (("start", self.play_start), ("end", self.play_end)):
            b.setEnabled(False)
            b.setMinimumWidth(150)
            b.setToolTip(f"Hear the {CLIP_SECONDS} seconds " + ("the service will start with."
                                                               if which == "start" else "the service will end with."))
            b.clicked.connect(lambda _on=False, w=which: on_play(w) if on_play else None)
            row.addWidget(b)
        lay.addWidget(self.file)
        self.file.hide()
        self.path, self.length = "", None

    def set_file(self, path, length=None):
        """Show the recording (length in seconds, once it is known)."""
        self.path, self.length = path, length
        self.name.setText(os.path.basename(path))
        folder = os.path.dirname(path)
        self.where.setText(" · ".join(t for t in (long_time(length) if length else "", folder) if t))
        self.empty.hide()
        self.file.show()
        self.setMinimumHeight(88)
        ui.set_prop(self, "has", "true")

    def set_over(self, over):
        ui.set_prop(self, "over", "true" if over else "false")


class ResultCard(QFrame):
    """Shown when the broadcast is made: the MP3's name, length and folder, with Play and Show in
    folder. If it is too long for the hour, the card says so and what to do."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.path = ""
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(16)
        self.tile = ui.IconTile("check", 44, "ok")
        row.addWidget(self.tile, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.head, self.where = ui.label("", "big"), ui.label("", "sub")
        self.warning = ui.label("", "warntext", wrap=True)
        for lab in (self.head, self.where, self.warning):
            col.addWidget(lab)
        row.addLayout(col, 1)
        self.play_btn, self.folder_btn = QPushButton("Play"), QPushButton("Show in folder")
        self.cue_btn = QPushButton("Cue sheet")
        self.cue_btn.setToolTip("Open the list of what plays when (a CSV file, for your station and license reports).")
        ui.primary(self.play_btn)
        self.play_btn.clicked.connect(lambda: self.open(False))
        self.folder_btn.clicked.connect(lambda: self.open(True))
        self.cue_btn.clicked.connect(lambda: self.open(False, builder.cue_sheet_path(self.path)))
        row.addWidget(self.play_btn, 0, Qt.AlignTop)
        row.addWidget(self.cue_btn, 0, Qt.AlignTop)
        row.addWidget(self.folder_btn, 0, Qt.AlignTop)
        self.hide()

    def show_result(self, path, length=None, warning=None):
        """path: the MP3; length: its seconds, if known; warning: why it needs editing by hand."""
        self.path = path
        self.tile.set_kind("warn" if warning else "ok")
        self.head.setText("The broadcast is saved, but it is too long" if warning else "The broadcast is ready")
        self.where.setText(" · ".join(t for t in (os.path.basename(path), clock(length) if length else "",
                                                  os.path.dirname(path)) if t))
        self.warning.setText(warning or "")
        self.warning.setVisible(bool(warning))
        self.cue_btn.setVisible(os.path.exists(builder.cue_sheet_path(path)))
        self.show()

    def open(self, folder, target=None):
        """Play the MP3 in the PC's music player, open the folder it is in, or open target."""
        target = target or (os.path.dirname(self.path) if folder else self.path)
        if not os.path.exists(target):
            QMessageBox.warning(self, paths.APP_NAME, f"Not found (moved or deleted):\n{target}")
            return
        try:
            songs_window.play(target)
        except OSError as e:
            QMessageBox.critical(self, paths.APP_NAME, str(e))


class UpdateBanner(QFrame):
    """The card at the top of the Broadcast page that says a new version is there, shows the
    download and says how it went. on_update: Update now was clicked; on_cancel: the download is
    to be stopped."""

    def __init__(self, on_update, on_cancel):
        super().__init__()
        self.setObjectName("card")
        self.update_info, self.ready = None, False
        col = QVBoxLayout(self)
        col.setContentsMargins(20, 12, 20, 12)
        col.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(10)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.head, self.sub = ui.label("", "big"), ui.label("", "sub", wrap=True)
        texts.addWidget(self.head)
        texts.addWidget(self.sub)
        row.addLayout(texts, 1)
        self.update_btn, self.page_btn = QPushButton("Update now"), QPushButton("Open the download page")
        self.new_btn, self.later_btn = QPushButton("What's new"), QPushButton("Later")
        self.cancel_btn = QPushButton("Cancel")
        ui.primary(self.update_btn)
        self.update_btn.clicked.connect(on_update)
        self.page_btn.clicked.connect(self.open_page)
        self.new_btn.clicked.connect(lambda: self.notes.setVisible(self.notes.isHidden()))
        self.later_btn.clicked.connect(self.hide)
        self.cancel_btn.clicked.connect(on_cancel)
        for b in (self.update_btn, self.page_btn, self.new_btn, self.cancel_btn, self.later_btn):
            row.addWidget(b, 0, Qt.AlignTop)
        col.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        col.addWidget(self.bar)
        self.notes = ui.label("", wrap=True)
        col.addWidget(self.notes)
        self.hide()

    def lay_out(self, head, sub, buttons=(), bar=False, later="Later"):
        """Show these texts and buttons. later: what the button that shuts the card says."""
        self.later_btn.setText(later)
        self.head.setText(head)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        for b in (self.update_btn, self.page_btn, self.new_btn, self.cancel_btn, self.later_btn):
            b.setVisible(b in buttons)
            b.setEnabled(True)
        self.bar.setVisible(bar)
        self.notes.hide()
        self.show()

    def offer(self, info, can_install):
        """A newer version is there. info: see updates.release_info."""
        self.update_info, self.ready = info, False
        mine = paths.version()
        lines = updates.whats_new(info["notes"])
        self.notes.setText("\n".join(lines))
        able = can_install and bool(info["url"])
        self.lay_out(f"Version {info['version']} is available",
                     (f"You have version {mine}. " if updates.is_release() else "This is a development build. ")
                     + ("Update now downloads it and installs it over this one; your settings, songs and "
                        "history are kept." if able else "Download it from the releases page."),
                     ((self.update_btn if able else self.page_btn,) + ((self.new_btn,) if lines else ())
                      + (self.later_btn,)))
        self.update_btn.setText("Update now")

    def say(self, head, sub="", page=False):
        """A plain message (the newest version is here; why it could not be asked or installed)."""
        self.lay_out(head, sub, ((self.page_btn,) if page else ()) + (self.later_btn,), later="Close")

    def downloading(self, got=0, total=0):
        if not self.bar.isVisible() or self.head.text() != "Downloading the new version ...":
            self.lay_out("Downloading the new version ...", "", (self.cancel_btn,), bar=True)
        self.bar.setRange(0, 1000 if total else 0)
        self.bar.setValue(int(got / total * 1000) if total else 0)
        self.sub.setVisible(bool(total))
        self.sub.setText(f"{got / 1e6:.0f} of {total / 1e6:.0f} MB" if total else "")

    def wait_for_build(self):
        """Downloaded while a broadcast is being made: it is installed when the person asks again."""
        self.ready = True
        self.lay_out("The new version is downloaded", "It can be installed when the broadcast is made.",
                     (self.update_btn, self.later_btn))
        self.update_btn.setText("Install now")

    def installing(self, text="Installing the new version ..."):
        self.lay_out(text, "")
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)

    def open_page(self):
        QDesktopServices.openUrl(QUrl((self.update_info or {}).get("page") or updates.RELEASES_PAGE))


class HistoryPage(QWidget):
    """The broadcasts made so far (history.json), the newest first: play one, or open its folder."""
    COLUMNS = (("Service date", 170), ("Season", 120), ("Broadcast", 280), ("Songs", 300))

    def __init__(self):
        super().__init__()
        self.outputs = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(ui.label("History", "pagetitle"))
        self.status = ui.label("", "sub")
        top.addWidget(self.status)
        top.addStretch()
        self.play_btn, self.folder_btn = QPushButton("Play"), QPushButton("Show in folder")
        self.play_btn.clicked.connect(lambda: self.open(False))
        self.folder_btn.clicked.connect(lambda: self.open(True))
        top.addWidget(self.play_btn)
        top.addWidget(self.folder_btn)
        lay.addLayout(top)
        self.table = t = QTableWidget(0, len(self.COLUMNS))
        t.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        t.verticalHeader().hide()
        t.verticalHeader().setDefaultSectionSize(songs_window.ROW_HEIGHT)
        t.setShowGrid(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setWordWrap(False)
        t.setItemDelegateForColumn(1, ui.ChipDelegate(t))
        head = t.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setHighlightSections(False)
        for i, (_text, width) in enumerate(self.COLUMNS):
            t.setColumnWidth(i, width)
        head.setSectionResizeMode(3, QHeaderView.Stretch)
        t.itemSelectionChanged.connect(self.selection_changed)
        t.cellDoubleClicked.connect(lambda _row, _col: self.open(False))
        lay.addWidget(t, 1)
        self.empty = ui.label("No broadcast has been made yet. The broadcasts you make are listed here.", "sub")
        lay.addWidget(self.empty)
        self.reload()

    def reload(self):
        hist = list(reversed(builder.load_history()))
        try:
            titles = {k: songs_window.title_of(r) for k, r in catalog.load(builder.songs_csv()).items()}
        except (OSError, ValueError):
            titles = {}
        t = self.table
        t.setRowCount(len(hist))
        self.outputs = []
        for i, entry in enumerate(hist):
            out = str(entry.get("output") or "")
            self.outputs.append(out)
            try:
                date = dt.date.fromisoformat(str(entry.get("date")))
                day, season = nice_date(date), season_name(date)
            except ValueError:
                day, season = str(entry.get("date") or ""), ""
            songs = [titles.get(f) or os.path.splitext(os.path.basename(str(f)))[0] for f in entry.get("songs") or []]
            gone = bool(out) and not os.path.exists(out)
            for col, text in enumerate((day, season, os.path.basename(out) + (" (not found)" if gone else ""),
                                        ", ".join(songs) or "no songs")):
                item = QTableWidgetItem(text)
                item.setToolTip(out if col == 2 else "\n".join(songs) if col == 3 else "")
                t.setItem(i, col, item)
        self.status.setText(f"{len(hist)} broadcast{'' if len(hist) == 1 else 's'}" if hist else "")
        self.empty.setVisible(not hist)
        self.selection_changed()

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.outputs[rows[0].row()] if rows and rows[0].row() < len(self.outputs) else ""

    def selection_changed(self):
        for b in (self.play_btn, self.folder_btn):
            b.setEnabled(bool(self.selected()))

    def open(self, folder):
        """Play the selected broadcast in the PC's music player, or open the folder it is in."""
        out = self.selected()
        target = os.path.dirname(out) if folder else out
        if not target:
            return
        if not os.path.exists(target):
            QMessageBox.warning(self, "History", f"Not found (moved or deleted):\n{target}")
            return
        try:
            songs_window.play(target)
        except OSError as e:
            QMessageBox.critical(self, "History", str(e))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.q, self.busy, self.warning, self.hour = queue.Queue(), False, None, None
        self.job = None  # the recording on the page: {"path"}, and "made" once its broadcast is made
        self.stopper = None  # stops the work that is going on (Cancel)
        self.reviewing = False  # the cuts were found and wait for the person's OK (see self.review)
        self.updating = None  # the update that is being downloaded or installed: {"stop", "path"}
        self.player, self.playing, self.play_starting, self.mp3_started = player.Player(), None, False, None
        # Playing: one piece at a time. play_count tells the newest piece from the ones before it;
        # line: the piece Play under the picture is playing: {"from", "seconds", "started"}.
        self.play_count, self.play_lock, self.line = 0, threading.Lock(), None
        atexit.register(lambda: self.busy and cli.drop_lock())  # window closed mid-build
        self.space = QShortcut(QKeySequence(Qt.Key_Space), self)  # play / pause, on the Broadcast page
        self.space.activated.connect(self.play_line)
        self.space.setEnabled(False)
        self.here_keys = {}  # S and E: put the start / end cut at the play marker (Broadcast page)
        for which, key in (("start", Qt.Key_S), ("end", Qt.Key_E)):
            k = self.here_keys[which] = QShortcut(QKeySequence(key), self)
            k.activated.connect(lambda w=which: self.cut_here(w))
            k.setEnabled(False)
        self.setObjectName("root")
        self.setAcceptDrops(True)
        self.resize(1180, 860)
        self.setMinimumSize(980, 700)
        whole = QVBoxLayout(self)
        whole.setContentsMargins(0, 0, 0, 0)
        whole.setSpacing(0)
        self.beam = ui.Beam()  # the gradient line along the top; a light runs along it during a build
        whole.addWidget(self.beam)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        whole.addLayout(lay, 1)
        lay.addWidget(self.make_side())
        self.pages = QStackedWidget()
        lay.addWidget(self.pages, 1)
        self.curtain = ui.Curtain(self.pages)  # a page that is chosen fades in

        try:
            cfg = builder.load_config()
        except (OSError, ValueError):
            cfg = {}
        self.songs_page = songs_window.SongsPage(builder.songs_csv(), cfg.get("song_folders", []),
                                                 on_folders=self.save_song_folders)
        self.history_page = HistoryPage()
        self.settings_form = None  # made when the Settings page is first opened (it counts the song files)
        self.settings_holder = QWidget()
        QVBoxLayout(self.settings_holder).setContentsMargins(0, 0, 0, 0)
        for page in (self.make_broadcast_page(), self.songs_page, self.history_page, self.settings_holder):
            self.pages.addWidget(page)

        comp = {**audio.COMPRESSION, **cfg.get("compression", {})}
        self.review.setChecked(bool(cfg.get("review_cuts", False)))
        self.review.toggled.connect(self.save_review)
        self.compress.setChecked(bool(comp["enabled"]))
        self.compress.setText(f"Compress the final MP3 ({comp['ratio']}:1, for radio)")
        self.show_settings()
        self.show_season()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

    # ---- the parts of the window --------------------------------------------------------
    def make_side(self):
        """The menu at the left: the app and broadcast names, the pages, the version and season."""
        side = ui.Side()
        side.setFixedWidth(224)
        col = QVBoxLayout(side)
        col.setContentsMargins(14, 22, 14, 16)
        col.setSpacing(4)
        top = QHBoxLayout()
        top.setContentsMargins(6, 0, 0, 0)
        top.setSpacing(12)
        icon = QLabel()
        pix = QPixmap(paths.asset("icon-256.png"))
        if not pix.isNull():
            ratio = self.devicePixelRatioF()
            pix = pix.scaled(int(40 * ratio), int(40 * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix.setDevicePixelRatio(ratio)
            icon.setPixmap(pix)
            top.addWidget(icon, 0, Qt.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(ui.label(paths.APP_NAME.replace(" ", "\n", 1), "appname"))
        self.name_label = ui.label("", "small", wrap=True)
        names.addWidget(self.name_label)
        top.addLayout(names, 1)
        col.addLayout(top)
        col.addSpacing(22)
        self.nav = {}
        for key, text in PAGES:
            b = self.nav[key] = ui.NavButton(key, text)
            b.clicked.connect(lambda _on=False, k=key: self.show_page(k))
            col.addWidget(b)
        self.nav["broadcast"].setChecked(True)
        col.addStretch()
        foot = QVBoxLayout()
        foot.setContentsMargins(8, 0, 0, 0)
        foot.setSpacing(2)
        foot.addWidget(ui.label(f"Version {paths.version()}", "small"))
        self.season_label = ui.label("", "small")
        foot.addWidget(self.season_label)
        col.addLayout(foot)
        about_btn = QPushButton("About")
        about_btn.setObjectName("ghost")
        about_btn.setStyleSheet("text-align: left; padding: 4px 8px;")
        about_btn.setCursor(Qt.PointingHandCursor)
        about_btn.clicked.connect(lambda: about(self))
        col.addWidget(about_btn)
        return side

    def make_broadcast_page(self):
        page = QWidget()
        page.setObjectName("scrollbody")
        self.scroll = scroll = QScrollArea()  # a low screen (a small laptop) scrolls the page
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(ui.label("This week's broadcast", "pagetitle"))
        top.addStretch()
        self.date = ui.DateField()
        self.date.dateChanged.connect(lambda _d: self.show_season())
        top.addWidget(ui.field("Service date", self.date))
        self.mode = QComboBox()
        self.mode.addItems(prelude.MODES)
        self.mode.setMinimumWidth(120)
        self.mode_field = ui.field("Start", self.mode)
        top.addWidget(self.mode_field)
        self.choose_btn = QPushButton("Choose a recording")
        self.choose_btn.clicked.connect(self.browse)
        top.addWidget(self.choose_btn)
        lay.addLayout(top)

        self.update_banner = UpdateBanner(self.start_update, self.cancel_update)  # shown when there is a new version
        lay.addWidget(self.update_banner)
        self.drop = DropArea(self.browse, self.play)
        lay.addWidget(self.drop)

        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(24)
        self.cut_end = QCheckBox()
        self.cut_end.setChecked(True)
        self.compress = QCheckBox()
        self.review = QCheckBox("Check the cuts before the MP3 is written")
        self.review.setToolTip("The app finds the start and the end and then waits: play them, move them if "
                               "they are wrong, and click Make the broadcast.")
        row.addWidget(self.cut_end)
        row.addWidget(self.compress)
        row.addWidget(self.review)
        row.addStretch()
        lay.addLayout(row)
        self.start_hint = ui.label("", "hint", wrap=True)
        self.start_hint.setContentsMargins(4, 0, 4, 0)
        lay.addWidget(self.start_hint)
        self.result = ResultCard()  # shown when the broadcast is made, with a glow under it
        lay.addWidget(ui.Underglow(self.result))

        self.wave_card = ui.card()  # shown once there is a recording
        col = QVBoxLayout(self.wave_card)
        col.setContentsMargins(20, 18, 20, 14)
        col.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(ui.label("WHERE THE SERVICE IS CUT", "caps"))
        head.addStretch()
        self.wave_hint = ui.label("Drag a marker or type its time to move a cut. Click in the picture to listen "
                                  "from there.", "small")
        self.wave_hint.setToolTip("Keys: click a cut (or press Tab) and move it with ← and → (Shift: 5 seconds). "
                                  "S and E put the start and end cut at the play marker. Space plays and pauses.")
        head.addWidget(self.wave_hint)
        col.addLayout(head)
        self.memory = QWidget()  # the cuts are remembered from last time: say so, and offer to listen again
        line = QHBoxLayout(self.memory)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(10)
        self.memory_text = ui.label("", "small")
        self.listen_btn = QPushButton("Listen again")
        self.listen_btn.setObjectName("mini")
        self.listen_btn.setToolTip("Forget these cuts and listen for the start and end of the service again.")
        self.listen_btn.clicked.connect(self.listen_again)
        line.addWidget(self.memory_text)
        line.addWidget(self.listen_btn)
        line.addStretch()
        self.memory.hide()
        col.addWidget(self.memory)
        self.wave = ui.Waveform()
        self.wave.moved.connect(self.cut_moved)
        self.wave.changed.connect(self.show_cut_times)
        self.wave.viewed.connect(self.show_zoom)
        self.wave.sought.connect(self.line_sought)
        col.addWidget(self.wave)
        # Under the picture: play from the play marker; zoom closer, further, to a cut, the whole
        # recording; and the bar that moves along the recording.
        row = QHBoxLayout()
        row.setSpacing(6)
        self.line_btn = QPushButton("Play")
        self.line_btn.setObjectName("mini")
        self.line_btn.setMinimumWidth(64)
        self.line_btn.setFocusPolicy(Qt.NoFocus)
        self.line_btn.setToolTip("Play the recording from the play marker, and pause it (or press the space "
                                 "bar). Click in the picture to put the marker where you want to listen.")
        self.line_btn.clicked.connect(self.play_line)
        self.line_time = ui.label("", "small")  # where the play marker is
        self.line_time.setMinimumWidth(62)
        row.addWidget(self.line_btn)
        row.addWidget(self.line_time)
        self.here_btns = {}
        for which, text in (("start", "Start cut here"), ("end", "End cut here")):
            b = self.here_btns[which] = QPushButton(text)
            b.setObjectName("mini")
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(f"Put the {which} cut at the play marker (or press {'S' if which == 'start' else 'E'}).")
            b.clicked.connect(lambda _on=False, w=which: self.cut_here(w))
            row.addWidget(b)
        row.addSpacing(8)
        self.zoom_label = ui.label("Zoom", "small")
        row.addWidget(self.zoom_label)
        self.zoom_btns = {}
        for key, text, tip, slot in (
                ("out", "−", "Zoom out: show more of the recording.", lambda: self.wave.zoom(1 / ZOOM_STEP)),
                ("in", "+", "Zoom in: show the recording closer. (Or hold Ctrl and turn the mouse wheel.)",
                 lambda: self.wave.zoom(ZOOM_STEP)),
                ("start", "Start cut", "Show the start cut from near.", lambda: self.wave.zoom_to("start")),
                ("end", "End cut", "Show the end cut from near.", lambda: self.wave.zoom_to("end")),
                ("all", "Whole recording", "Zoom all the way out.", self.wave.show_all)):
            b = self.zoom_btns[key] = QPushButton(text)
            b.setObjectName("mini")
            b.setToolTip(tip)
            b.clicked.connect(lambda _on=False, f=slot: f())
            row.addWidget(b)
        self.wave_scroll = QScrollBar(Qt.Horizontal)  # zoomed in: moves along the recording
        self.wave_scroll.setObjectName("track")
        self.wave_scroll.setToolTip("Move along the recording. (Or hold Shift and turn the mouse wheel.)")
        keep = self.wave_scroll.sizePolicy()
        keep.setRetainSizeWhenHidden(True)
        self.wave_scroll.setSizePolicy(keep)
        self.wave_scroll.valueChanged.connect(lambda v: self.wave.show_part(v / 10, self.wave.span()))
        row.addSpacing(8)
        row.addWidget(self.wave_scroll, 1)
        col.addLayout(row)
        row = QHBoxLayout()  # each cut's time and small steps for it, and the button that uses the cuts
        row.setSpacing(6)
        self.nudges, self.cut_times, self.cut_labels = [], {}, []
        self.make_btn = QPushButton("Make the broadcast")
        ui.primary(self.make_btn)
        self.make_btn.clicked.connect(self.make)
        for which in ("start", "end"):
            lab = ui.label("Start" if which == "start" else "End", "small")
            box = self.cut_times[which] = QLineEdit()  # the cut's time, to read and to type
            box.setFixedWidth(86)
            box.setPlaceholderText("nothing cut")
            box.setToolTip(f"Where the service {'starts' if which == 'start' else 'ends'} in the recording. Type "
                           "a time (9:02, 9:02.4 or 1:08:15) and press Enter. Empty = nothing is cut here.")
            box.editingFinished.connect(lambda w=which: self.cut_typed(w))
            self.cut_labels.append(lab)
            row.addWidget(lab)
            row.addWidget(box)
            for sec in NUDGES:
                b = QPushButton(f"{'−' if sec < 0 else '+'}{abs(sec)} s")
                b.setObjectName("mini")
                b.setToolTip(f"Move the {which} cut {abs(sec)} second{'' if abs(sec) == 1 else 's'} "
                             + ("earlier." if sec < 0 else "later."))
                b.clicked.connect(lambda _on=False, w=which, s=sec: self.wave.nudge(w, s))
                self.nudges.append(b)
                row.addWidget(b)
            if which == "start":
                row.addStretch()
                row.addWidget(self.make_btn)
                row.addStretch()
        col.addLayout(row)
        lay.addWidget(self.wave_card)
        self.wave_card.hide()

        cards = QHBoxLayout()
        cards.setSpacing(16)
        hour = ui.card()
        col = QVBoxLayout(hour)
        col.setContentsMargins(20, 18, 20, 18)
        col.setSpacing(10)
        col.addWidget(ui.label("THE HOUR", "caps"))
        self.hour_bar = ui.HourBar()
        col.addWidget(self.hour_bar)
        legend = QHBoxLayout()
        self.legend, self.total = ui.label("", "sub"), ui.label("", "strong")
        self.legend.setTextFormat(Qt.RichText)
        legend.addWidget(self.legend, 1)
        legend.addWidget(self.total)
        col.addLayout(legend)
        self.song_list = QVBoxLayout()
        self.song_list.setSpacing(6)
        col.addLayout(self.song_list)
        col.addStretch()
        cards.addWidget(hour, 5)

        progress = ui.card()
        col = QVBoxLayout(progress)
        col.setContentsMargins(20, 18, 20, 18)
        col.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(ui.label("PROGRESS", "caps"))
        head.addStretch()
        self.status = ui.label("Ready.", "sub")
        head.addWidget(self.status)
        col.addLayout(head)
        col.addSpacing(4)
        self.steps = {}
        for key, todo, doing, done in STEP_ROWS:
            self.steps[key] = ui.StepRow(todo, doing, done)
            col.addWidget(self.steps[key])
        col.addSpacing(6)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1)
        self.cancel_btn = QPushButton("Cancel")  # shown while a broadcast is being made
        self.cancel_btn.setObjectName("mini")
        self.cancel_btn.setToolTip("Stop making this broadcast. Nothing is saved; cuts already found are kept.")
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.hide()
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.bar, 1)
        row.addWidget(self.cancel_btn)
        col.addLayout(row)
        col.addStretch()
        cards.addWidget(progress, 4)
        lay.addLayout(cards)

        row = QHBoxLayout()
        self.details_btn = QPushButton()
        self.details_btn.setObjectName("ghost")
        self.details_btn.setCursor(Qt.PointingHandCursor)
        self.details_btn.clicked.connect(lambda: self.show_details(self.text.isHidden()))
        row.addWidget(self.details_btn)
        row.addStretch()
        lay.addLayout(row)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(ui.fixed_font())
        self.text.setMinimumHeight(90)
        lay.addWidget(self.text, 1)
        self.filler = QWidget()
        lay.addWidget(self.filler, 1)
        self.show_details(False)
        self.show_hour(None)
        self.show_cut_controls()
        return scroll

    def show_details(self, show):
        """Show or hide everything the build wrote (the log), under the cards."""
        self.text.setVisible(show)
        self.filler.setVisible(not show)
        self.details_btn.setText("Hide the details" if show else "Show the details")

    def show_page(self, key, models=True):
        """Open a page of the menu. models=False: do not look for the speech models (--uitest)."""
        if self.busy and key in ("songs", "settings"):
            key = "broadcast"
        cfg = self.load_config(dict(PAGES)[key]) if key in ("songs", "settings") else None
        if key in ("songs", "settings") and cfg is None:
            key = "broadcast"
        if key == "songs":
            db = cfg.get("song_silence_db", audio.EDGE_SILENCE_DB)
            self.songs_page.use(cfg.get("song_folders", []), cfg.get("song_min_words", catalog.MIN_WORDS),
                                (lambda f: audio.edge_silence(f, db)) if cfg.get("trim_song_silence", True) else None,
                                cfg.get("models_folder", ""))
            self.songs_page.reload()
        elif key == "history":
            self.history_page.reload()
        elif key == "settings":
            if self.settings_form is None:
                self.settings_form = setup_wizard.SettingsForm(cfg, on_done=self.show_settings)
                self.settings_holder.layout().addWidget(self.settings_form)
            if models:
                self.settings_form.show_models()
        self.nav[key].setChecked(True)
        index = [k for k, _text in PAGES].index(key)
        other = index != self.pages.currentIndex()
        self.pages.setCurrentIndex(index)
        if other:
            self.curtain.drop()
        self.show_space()

    def show_season(self):
        self.season_label.setText(f"{season_name(self.date.get())} season")

    def show_settings(self, cfg=None):
        """Put the church's own words, name and look in the window (after setup or Settings)."""
        try:
            cfg = cfg or builder.load_config()
        except (OSError, ValueError):
            cfg = {}
        ui.apply_theme(ui.QApplication.instance(), cfg.get("theme", "auto"))
        ui.set_motion(cfg.get("motion", True))
        name = (cfg.get("broadcast_name") or "").strip()
        self.setWindowTitle(f"{paths.APP_NAME} - {name}" if name else paths.APP_NAME)
        self.name_label.setText(name)
        start = cfg.get("start_phrase") or "Good morning"
        self.start_hint.setText(f'Start: Auto = cut the organ before "{start}" but keep a choir song. '
                                "Organ start = always cut there. Keep start = cut nothing (bell choir).")
        self.mode_field.setToolTip(self.start_hint.text())
        end = cfg.get("end_answer_phrase") or cfg.get("end_phrase") or prelude.END_PHRASE
        self.cut_end.setText(f'End the service at "{end}"')
        mode = cfg.get("service_start", prelude.MODES[0])
        self.mode.setCurrentText(mode if mode in prelude.MODES else prelude.MODES[0])
        self.songs_page.fill()  # the colours of the look are in the list
        self.show_hour(self.hour)

    def show_hour(self, hour):
        """Fill The hour card from what the build told: {"intro", "service", "songs", "target"}."""
        self.hour = hour
        while self.song_list.count():
            item = self.song_list.takeAt(0)
            for i in range(item.layout().count() if item.layout() else 0):
                item.layout().itemAt(i).widget().deleteLater()
        if not hour:
            self.hour_bar.set_parts([])
            self.legend.setText("The intro, the service and the songs are shown here once the service is cut.")
            self.total.setText("")
            return
        songs = hour["songs"]
        self.hour_bar.set_parts([("intro", hour["intro"], ""), ("service", hour["service"],
                                                                f"Service {audio.fmt(hour['service'])}")]
                                + [("song", sec, "") for _title, sec in songs])
        song_sec = sum(sec for _title, sec in songs)
        parts = ([("intro", f"Intro {audio.fmt(hour['intro'])}")] if hour["intro"] else []) + \
            [("accent", f"Service {audio.fmt(hour['service'])}")] + \
            ([("song", f"{len(songs)} song{'' if len(songs) == 1 else 's'} {audio.fmt(song_sec)}")] if songs else [])
        self.legend.setText(" &nbsp;&nbsp;&nbsp; ".join(
            f'<span style="color:{ui.colors[color]}">■</span>&nbsp; {text}' for color, text in parts))
        self.total.setText(clock(hour["intro"] + hour["service"] + song_sec))
        for title, sec in songs:
            row = QHBoxLayout()
            row.addWidget(ui.label(title), 1)
            row.addWidget(ui.label(audio.fmt(sec), "sub"))
            self.song_list.addLayout(row)

    def load_config(self, title):
        try:
            return builder.load_config()
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, title, f"Could not read config.json:\n{e}")
            return None

    def settings(self, first_run=False):
        """Open the setup wizard (first start) or the Settings page."""
        if self.busy:
            return
        if not first_run:
            self.show_page("settings")
            return
        cfg = self.load_config("Settings")
        if cfg is not None:
            setup_wizard.SetupWizard(self, cfg, on_done=self.show_settings, first_run=True).exec()

    def browse(self):
        f, _filter = QFileDialog.getOpenFileName(self, "Service recording", "", MEDIA)
        if f:
            self.start(os.path.normpath(f))

    def save_song_folders(self, folders):
        """Add songs put songs in a new folder: remember it in the settings."""
        try:
            cfg = builder.load_config()
            cfg["song_folders"] = list(folders)
            builder.save_config(cfg)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Songs", f"Could not save the song folders:\n{e}")
            return
        if self.settings_form is not None:
            self.settings_form.set_folders(folders)

    def closeEvent(self, event):  # noqa: N802  (Qt's name)
        if self.busy and self.stopper:
            self.stopper.stop()  # no ffmpeg is left running behind a closed window
        if self.updating:
            self.updating["stop"] = True
        self.player.close()
        self.songs_page.shutdown()
        if self.settings_form is not None:
            self.settings_form.closed = True
        super().closeEvent(event)

    # ---- a recording dropped on the window --------------------------------------------
    def dragEnterEvent(self, e):  # noqa: N802
        if not self.busy and any(u.isLocalFile() for u in e.mimeData().urls()):
            e.acceptProposedAction()
            self.drop.set_over(True)

    def dragLeaveEvent(self, e):  # noqa: N802
        self.drop.set_over(False)

    def dropEvent(self, e):  # noqa: N802
        self.drop.set_over(False)
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if files:
            e.acceptProposedAction()
            # After the drop has ended: a message box inside it would freeze the file manager.
            QTimer.singleShot(0, lambda: self.start(os.path.normpath(files[0])))

    # ---- making the broadcast -----------------------------------------------------------
    def log(self, msg):
        self.q.put(("log", msg))

    def tell(self, what, value):
        self.q.put(("tell", (what, value)))

    def set_busy(self, busy):
        self.busy = busy
        self.beam.set_busy(busy)
        for w in (self.nav["songs"], self.nav["settings"], self.drop.browse, self.choose_btn):
            w.setEnabled(not busy)
        self.bar.setRange(0, 0 if busy else 1)  # 0..0: a moving bar, there is no known end
        self.bar.setValue(0)
        self.mp3_started = None
        self.cancel_btn.setVisible(busy)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel")
        self.show_cut_controls()

    def cancel(self):
        """Stop the broadcast that is being made (the work ends at once or after a few seconds)."""
        if self.busy and self.stopper and not self.stopper.stopped():
            self.stopper.stop()
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText("Stopping ...")
            self.status.setText("Stopping ...")

    def show_cut_controls(self, make=None):
        """The cuts can be moved and played once they are known, and moved only while no broadcast
        is being made. make: show (True) or hide (False) the Make the broadcast button."""
        known = self.wave.known()
        self.wave.set_editable(known and not self.busy)
        for b in self.nudges:
            b.setVisible(known)
            b.setEnabled(not self.busy)
        for w in list(self.cut_times.values()) + self.cut_labels + [self.line_btn, self.line_time]:
            w.setVisible(known)
        for box in self.cut_times.values():
            box.setEnabled(not self.busy)
        for w in [self.zoom_label] + list(self.zoom_btns.values()):
            w.setVisible(known)
        self.show_zoom()
        self.show_space()
        self.wave_hint.setVisible(known and not self.busy)
        for b in (self.drop.play_start, self.drop.play_end):
            b.setEnabled(known)
        if make is not None:
            self.make_btn.setVisible(make)
        if not known:
            self.make_btn.hide()
        self.make_btn.setEnabled(not self.busy)
        self.listen_btn.setEnabled(not self.busy)
        self.make_btn.setText("Make the broadcast again" if (self.job or {}).get("made") else "Make the broadcast")

    def save_review(self, on):
        """Remember the "Check the cuts" tick for the next time."""
        try:
            cfg = builder.load_config()
            cfg["review_cuts"] = bool(on)
            builder.save_config(cfg)
        except (OSError, ValueError):
            pass  # only not remembered

    def may_start(self):
        """True if a broadcast can be made now (then the lock is taken); else the person is told why."""
        if self.busy:
            return False
        if self.updating and self.updating.get("installing"):
            QMessageBox.warning(self, paths.APP_NAME, "The new version is being installed. The app closes soon.")
            return False
        if self.songs_page.working():
            QMessageBox.warning(self, paths.APP_NAME, "The song list is being updated. Try again when it is done.")
            return False
        if not cli.take_lock("the app window"):
            QMessageBox.warning(self, paths.APP_NAME, "A broadcast is already being made "
                                f"({cli.lock_owner()}). Try again when it is done.")
            return False
        return True

    def start(self, path):
        """A recording was chosen: find its cuts and (unless they are checked first) make the broadcast."""
        if not self.may_start():
            return
        date = servicecal.service_date(self.date.get(), self.date.changed, os.path.basename(path))
        if date != self.date.get():
            self.date.set_date(date)  # show the date read from the file name
            self.show_season()
        self.job = {"path": path}
        self.stop_playing()
        self.drop.set_file(path)
        self.start_hint.hide()  # (it is the tooltip of Start too) room for the picture of the recording
        self.wave.reset()
        self.wave_card.show()
        threading.Thread(target=self.draw_recording, args=(path,), daemon=True).start()
        self.choose_btn.setText("Choose another recording")
        self.launch(None)

    def listen_again(self):
        """Listen for the cuts of this recording again (not the ones remembered)."""
        if self.job and self.may_start():
            self.stop_playing()
            self.launch(None, listen_again=True)

    def make(self):
        """Make the broadcast with the cuts as they are in the picture (checked or moved by the person)."""
        if not self.job or not self.wave.known() or not self.may_start():
            return
        self.launch((self.wave.cuts.get("start") or 0.0, self.wave.cuts.get("end")))

    def launch(self, cuts, listen_again=False):
        """Start the work in the background (the lock is taken). cuts None: use the cuts remembered
        for this recording, or listen for them (listen_again: listen in any case)."""
        self.warning, self.reviewing = None, False
        self.memory.hide()
        self.result.hide()
        self.stopper = audio.Stopper()
        self.show_page("broadcast")
        self.set_busy(True)
        self.show_cut_controls(make=False)
        self.text.clear()
        self.show_hour(None)
        for row in self.steps.values():
            row.set("todo", "")
        path = self.job["path"]
        self.status.setText(f"Working on {os.path.basename(path)} ...")
        threading.Thread(target=self.work, args=(path, self.date.get(), self.mode.currentText(),
                                                 self.cut_end.isChecked(), self.compress.isChecked(), cuts,
                                                 self.review.isChecked(), self.stopper, listen_again),
                         daemon=True).start()

    def work(self, path, date, mode, cut_end, compress, cuts=None, review=False, stopper=None, listen_again=False):
        try:
            with audio.stoppable(stopper or audio.Stopper()):  # (Cancel stops it: self.cancel)
                if cuts is None:
                    try:
                        self.tell("recording", audio.duration(path))
                    except Exception:  # noqa: BLE001  (the build says what is wrong with the file)
                        pass
                    if review:  # only the cuts; the person makes the broadcast (self.make)
                        found = None if listen_again else builder.remembered_cuts(
                            path, builder.cut_settings(builder.load_config(), mode, cut_end))
                        if found:
                            self.log(builder.remembered_text(found) + ". (Not listened to again.)")
                            for what, value in (("remembered", found), ("start", found["start"]),
                                                ("end", found["end"])):
                                self.tell(what, value)
                            self.q.put(("review", (found["start"], found["end"])))
                        else:
                            self.q.put(("review", builder.find_cuts(path, None, mode, cut_end, self.log, self.tell)))
                        return
                out = builder.build(path, date=date, log=self.log, start_mode=mode, warn=self.set_warning,
                                    cut_end=cut_end, compress=compress, tell=self.tell, cuts=cuts,
                                    listen_again=listen_again)
            try:
                length = audio.duration(out)
            except Exception:  # noqa: BLE001  (only the length on the card is missing)
                length = None
            self.q.put(("done", (out, length)))
        except audio.Stopped:
            self.q.put(("stopped", None))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def draw_recording(self, path):
        """In the background, next to the build: read how loud the recording is along its length."""
        try:
            levels, detail = audio.loudness_picture(path)
        except Exception:  # noqa: BLE001  (only the picture is missing; the build says what is wrong)
            levels = detail = None
        self.q.put(("wave", (path, levels, detail)))

    # ---- a new version of the app -------------------------------------------------------
    def check_updates(self, asked=False):
        """Ask GitHub, in the background, if there is a newer version. asked: the person clicked
        Check for updates (then the answer is shown also when there is none, or it failed)."""
        if self.updating:
            return
        if asked:
            self.show_page("broadcast")
            self.update_banner.say("Looking for a new version ...")

        def run():
            try:
                self.q.put(("update", (asked, updates.check(), None)))
            except Exception as e:  # noqa: BLE001  (told only if the person asked)
                self.q.put(("update", (asked, None, str(e))))

        threading.Thread(target=run, daemon=True).start()

    def update_found(self, asked, info, error):
        banner = self.update_banner
        if self.updating:
            return
        if info:
            banner.offer(info, updates.can_install())
        elif not asked:
            return  # at the start of the app: quiet when there is nothing new, or no internet
        elif error:
            banner.say("Could not look for a new version", error, page=True)
        else:
            banner.say(f"Version {paths.version()} is the newest version")
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(banner))

    def start_update(self):
        """Update now: download the new version (checked against its checksum), then install it."""
        banner = self.update_banner
        if banner.ready and self.updating:  # downloaded while a broadcast was made: install it now
            self.install_update(self.updating["path"])
            return
        info = banner.update_info
        if self.updating or not info:
            return
        self.updating = state = {"stop": False, "path": ""}
        banner.downloading()

        def run():
            try:
                path = updates.download(info, lambda got, total: self.q.put(("update-progress", (got, total))),
                                        lambda: state["stop"])
                self.q.put(("update-ready", path))
            except updates.Cancelled:
                self.q.put(("update-failed", ""))
            except Exception as e:  # noqa: BLE001  told to the person
                self.q.put(("update-failed", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def cancel_update(self):
        if self.updating:
            self.updating["stop"] = True
            self.update_banner.cancel_btn.setEnabled(False)

    def install_update(self, path):
        """Start the downloaded update and close the app. Not while a broadcast is being made, here
        or by a scheduled run: the update replaces the program's files."""
        self.updating["path"] = path
        if self.busy or self.songs_page.working() or cli.lock_owner():
            self.update_banner.wait_for_build()
            return
        self.updating["installing"] = True
        self.update_banner.installing()

        def run():
            try:
                self.q.put(("update-installed", updates.install(path)))
            except Exception as e:  # noqa: BLE001  told to the person
                self.q.put(("update-failed", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def update_told(self, kind, msg):
        """What the update's background work told (see poll)."""
        banner = self.update_banner
        if kind == "update":
            self.update_found(*msg)
        elif kind == "update-progress":
            if self.updating and not self.updating["path"]:
                banner.downloading(*msg)
        elif kind == "update-ready":
            self.install_update(msg)
        elif kind == "update-failed":
            info, self.updating = banner.update_info, None
            banner.ready = False
            if msg:
                banner.say("The update could not be installed", msg, page=True)
            elif info:  # the download was cancelled: the offer is back
                banner.offer(info, updates.can_install())
        elif kind == "update-installed":
            banner.installing(msg)
            banner.bar.hide()
            QTimer.singleShot(2500, self.quit_for_update)

    def quit_for_update(self):
        self.close()
        ui.QApplication.instance().quit()

    # ---- the cuts: moved and played by the person --------------------------------------
    def cut_moved(self, which):
        """A cut was dragged or nudged: show its new time and offer to make the broadcast with it."""
        at = self.wave.cuts.get(which)
        self.steps[which].set("done", clock(at) if at else "nothing cut")
        if self.job:  # the same recording chosen again starts with these cuts
            builder.remember_cuts(self.job["path"], self.wave.cuts.get("start"), self.wave.cuts.get("end"), "hand")
        self.memory.hide()
        if self.playing in ("start", "end"):  # (that piece is not where the cut is any more)
            self.stop_playing()
        self.show_cut_controls(make=True)
        if not self.reviewing:
            self.status.setText("The cuts were moved.")

    def show_cut_times(self):
        """The boxes under the picture show where the cuts are (not while a time is being typed)."""
        for which, box in self.cut_times.items():
            if not (box.hasFocus() and box.isModified()):
                at = self.wave.cuts.get(which)
                text = ui.clock_exact(at) if at else ""
                if box.text() != text:
                    box.setText(text)

    def cut_typed(self, which):
        """A time was typed for a cut (Enter, or the box was left): put the cut there. Something
        that is not a time is taken back."""
        box = self.cut_times[which]
        if not box.isModified():
            return
        box.setModified(False)
        text = box.text().strip()
        at = ui.parse_clock(text) if text else (0.0 if which == "start" else self.wave.length)
        if at is None:
            self.status.setText(f'"{text}" is not a time. Type it like 9:02 or 1:08:15.')
        else:
            self.wave.place(which, at)  # (kept apart from the other cut and inside the recording)
        self.show_cut_times()

    def show_zoom(self):
        """The zoom buttons and the bar under the picture follow the part of the recording shown."""
        wave, bar = self.wave, self.wave_scroll
        self.zoom_btns["out"].setEnabled(wave.zoomed())
        self.zoom_btns["all"].setEnabled(wave.zoomed())
        self.zoom_btns["in"].setEnabled(wave.span() > wave.MIN_SPAN)
        bar.blockSignals(True)
        bar.setRange(0, int(round(max(0.0, wave.length - wave.span()) * 10)))
        bar.setPageStep(max(1, int(wave.span() * 10)))
        bar.setSingleStep(max(1, int(wave.span())))
        bar.setValue(int(round(wave.first() * 10)))
        bar.blockSignals(False)
        bar.setVisible(wave.zoomed() and wave.known())

    def show_space(self):
        """The space bar plays and pauses only on the Broadcast page, once there is something to play.
        S and E (and the buttons for them) work there too, while the cuts can be moved and there is a
        play marker."""
        here = self.pages.currentIndex() == 0 and self.wave.known() and bool(self.job)
        self.space.setEnabled(here)
        for which in ("start", "end"):
            self.here_keys[which].setEnabled(here and not self.busy)
            self.here_btns[which].setVisible(self.wave.known())
            self.here_btns[which].setEnabled(here and not self.busy and self.wave.playhead is not None)

    def cut_here(self, which):
        """S / E, or the buttons: put the start or end cut at the play marker."""
        if self.busy or not self.job or not self.wave.known():
            return
        if self.wave.playhead is None:
            self.status.setText("Click in the picture first to put the play marker where the cut should go.")
            return
        self.wave.place(which, self.wave.playhead)  # (kept apart from the other cut and inside the recording)
        self.wave.choose(which)

    def start_playing(self, which, at, seconds):
        """Play `seconds` of the recording from `at`, in the background (ffmpeg cuts the piece first).
        which: "start" or "end" (the play buttons of the cuts) or "line" (Play under the picture).
        Only the newest piece asked for is played."""
        self.play_count += 1
        count, path = self.play_count, self.job["path"]
        self.playing, self.play_starting = which, True
        self.line = {"from": at, "seconds": seconds, "started": None} if which == "line" else None

        def run():
            with self.play_lock:  # (one after the other: each stops the piece before it)
                if count != self.play_count:
                    return  # another piece was asked for meanwhile
                try:
                    self.player.play(path, at, seconds)
                    self.q.put(("played", (count, None)))
                except Exception as e:  # noqa: BLE001  told to the person
                    self.q.put(("played", (count, str(e))))

        threading.Thread(target=run, daemon=True).start()

    def stop_playing(self):
        """Stop what is playing. The play marker stays where it is."""
        self.play_count += 1  # (a piece that is still being cut is not played)
        self.player.stop()
        self.playing, self.play_starting, self.line = None, False, None

    def is_playing(self, which):
        return self.playing == which and (self.play_starting or self.player.playing())

    def play(self, which):
        """Play the seconds after the start cut, or before the end cut. A second click stops it."""
        if not self.job or not self.wave.known():
            return
        if self.is_playing(which):
            self.stop_playing()
            return
        if which == "start":
            at = self.wave.cuts.get("start") or 0.0
        else:
            at = max(0.0, (self.wave.cuts.get("end") or self.wave.length) - CLIP_SECONDS)
        self.start_playing(which, at, CLIP_SECONDS)

    def play_line(self):
        """Play under the picture, or the space bar: play the recording from the play marker, or
        pause it there. With no marker yet (or at the very end) it plays from the start cut."""
        if not self.job or not self.wave.known():
            return
        if self.is_playing("line"):
            self.stop_playing()  # pause: the marker stays where the sound was
            return
        at = self.wave.playhead
        if at is None or at >= self.wave.length - 0.5:
            at = self.wave.cut_at("start")
        self.play_line_from(at)

    def play_line_from(self, at):
        self.wave.set_playhead(at)
        self.start_playing("line", at, min(LINE_SECONDS, max(0.0, self.wave.length - at)))

    def line_sought(self, at):
        """The play marker was put somewhere in the picture: what is playing goes on from there."""
        if self.playing == "line":
            self.play_line_from(at)
        self.show_playing()

    def follow_line(self):
        """While the recording plays from the play marker: the marker moves along, the picture
        follows it when zoomed in, and the next piece starts when one is over."""
        line = self.line
        if self.playing != "line" or not line or line["started"] is None:
            return
        at, end = line["from"] + time.time() - line["started"], line["from"] + line["seconds"]
        if self.player.playing() and at < end:
            wave = self.wave
            if not wave.seeking:
                wave.set_playhead(at)
                # Zoomed in, the picture turns the page when the marker runs out of it. Not when
                # the person has moved the picture somewhere else to look there.
                seen = wave.first() <= at <= wave.first() + wave.span()
                if wave.zoomed() and not wave.drag and not seen and line.get("seen") == wave.view:
                    wave.show_part(at - wave.span() * 0.05, wave.span())
                    seen = True
                line["seen"] = wave.view if seen else None  # (the part shown when the marker was last in it)
        elif at >= end - 0.5 and end < self.wave.length - 0.5:
            self.play_line_from(end)  # the piece is over: the next one
        else:  # the end of the recording, or the sound stopped by itself
            self.wave.set_playhead(min(at, end))
            self.stop_playing()

    def show_playing(self):
        """The play button of the piece that is playing says Stop (under the picture: Pause), and
        the time next to Play is where the play marker is."""
        self.follow_line()
        on = self.playing if self.play_starting or self.player.playing() else None
        for which, b, text in (("start", self.drop.play_start, "Play from start cut"),
                               ("end", self.drop.play_end, "Play to end cut"), ("line", self.line_btn, "Play")):
            want = ("Pause" if which == "line" else "Stop") if on == which else text
            if b.text() != want:
                b.setText(want)
        at = self.wave.playhead
        want = ui.clock_exact(at) if at is not None else ""
        if self.line_time.text() != want:
            self.line_time.setText(want)
        for b in self.here_btns.values():
            want = bool(at is not None and self.job and self.wave.known() and not self.busy)
            if b.isEnabled() != want:
                b.setEnabled(want)

    def set_warning(self, msg):
        self.warning = msg

    def step_starts(self, key):
        """A step of the progress list starts: the ones before it are done."""
        keys = list(self.steps)
        for k in keys[:keys.index(key)]:
            if self.steps[k].state != "done":
                self.steps[k].set("done")
        if self.steps[key].state != "done":
            self.steps[key].set("doing")

    def told(self, what, value):
        """A number from the build (see builder.build): show it in the progress list or The hour."""
        if what == "recording":
            self.drop.set_file(self.drop.path, value)
            self.wave.set_length(value)
        elif what == "mp3":
            if self.mp3_started is None:
                self.mp3_started = time.time()
                self.bar.setRange(0, 1000)
            self.bar.setValue(int(value * 1000))
            spent = time.time() - self.mp3_started
            if value >= 0.05 and spent >= 3 and self.steps["mp3"].state != "done":
                self.steps["mp3"].set("doing", time_left(spent * (1 - value) / value))
        elif what == "remembered":
            self.memory_text.setText(builder.remembered_text(value) + ". The app did not listen again.")
            self.memory.show()
        elif what in ("start", "end"):
            self.wave.set_cut(what, value)
            self.steps[what].set("done", clock(value) if value else "nothing cut")
        elif what == "silence":
            self.steps[what].set("done", f"{value:.1f} s")
        elif what == "hour":
            n = len(value["songs"])
            self.steps["songs"].set("done", f"{n} song{'' if n == 1 else 's'}" if n else "none needed")
            self.show_hour(value)

    def poll(self):
        self.show_playing()
        while not self.q.empty():
            kind, msg = self.q.get()
            if kind == "tell":
                if self.busy:
                    self.told(*msg)
                continue
            if kind.startswith("update"):  # a new version: found, downloading, installed
                self.update_told(kind, msg)
                continue
            if kind == "wave":  # may come after the build is done; not for an older recording
                if msg[0] == self.drop.path:
                    self.wave.set_levels(msg[1], msg[2], audio.DETAIL_PER_SECOND)
                continue
            if kind == "played":  # a piece has started to play, or could not be played
                count, error = msg
                if count != self.play_count:  # not the newest piece any more
                    if not self.play_starting:
                        self.player.stop()  # it was stopped while it was being cut
                    continue
                self.play_starting = False
                if error:
                    self.stop_playing()
                    QMessageBox.warning(self, paths.APP_NAME, f"Could not play the recording:\n{error}")
                elif self.line:
                    self.line["started"] = time.time()
                continue
            if kind == "review":  # the cuts are found: the person checks them and clicks Make the broadcast
                cli.drop_lock()
                self.reviewing = True
                self.set_busy(False)
                self.show_cut_controls(make=True)
                for key in ("start", "end"):
                    self.steps[key].set("done")
                self.status.setText("Check the cuts, then click Make the broadcast.")
                continue
            if kind == "log":
                self.text.appendPlainText(msg)
                step = step_for(msg)
                if step and self.busy:
                    self.status.setText(step)
                    self.step_starts(step_key(msg))
                continue
            cli.drop_lock()  # the work has ended: "done", "stopped" (Cancel) or "error"
            self.set_busy(False)
            self.status.setText({"done": "Done.", "stopped": "Stopped."}.get(kind, "Failed."))
            self.text.appendPlainText("Stopped: no broadcast was made." if kind == "stopped" else
                                      "ERROR: " + msg if kind == "error" else f"Saved: {msg[0]}")
            for row in self.steps.values():
                if kind == "done":
                    row.set("done")
                elif row.state == "doing":
                    row.set("todo" if kind == "stopped" else "failed", "")
            self.steps["mp3"].set(self.steps["mp3"].state, "")  # (it said how long was left)
            if kind == "done":
                self.job["made"] = True
            self.show_cut_controls(make=kind != "done")
            self.history_page.reload()
            if kind == "done":
                self.bar.setValue(1)
                self.result.show_result(msg[0], msg[1], self.warning)
                if self.warning:
                    self.status.setText("Done, but the MP3 is too long.")
                # (once the page is laid out again with the card in it)
                QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.result))
            elif kind == "error":
                self.show_details(True)
                QMessageBox.critical(self, paths.APP_NAME, msg)


class FileOpener(QObject):
    """macOS: a recording dropped on the app's icon (or opened with the app) arrives as an event."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.FileOpen and event.file():
            self.window.start(event.file())
            return True
        return False


def theme_setting():
    try:
        return builder.load_config().get("theme", "auto")
    except (OSError, ValueError):
        return "auto"


def run(argv):
    """Open the window. argv: the program's arguments (a recording dropped on its icon)."""
    app = ui.start_app(argv[:1], theme_setting())
    window = MainWindow()
    app.installEventFilter(FileOpener(window))
    window.show()
    try:
        cfg = builder.load_config()
    except (OSError, ValueError):
        cfg = {}
    first_run = not cfg.get("setup_done")
    # A new version? Asked once, quietly, at each start (Settings turns it off). Not from source:
    # a development build has no version to compare.
    if cfg.get("check_updates", True) and updates.is_release():
        QTimer.singleShot(UPDATE_CHECK_MS, window.check_updates)
    # -psn_...: the process number older macOS passes to an app opened from the Finder.
    args = [a for a in argv[1:] if not a.startswith("-psn_")]
    if first_run:
        QTimer.singleShot(200, lambda: window.settings(first_run=True))
    elif args:  # file dropped on the program icon
        QTimer.singleShot(300, lambda: window.start(args[0]))
    return app.exec()


def uitest():
    """--uitest: make every window and page once without showing it on a screen, and exit. No
    models, no internet. The release build runs it to check that the windows work in the packaged
    program."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = ui.start_app(["uitest"], "light")
    cfg = builder.load_config()
    made = []

    def drawn(w, name):
        app.processEvents()
        size = w.grab().size()
        if size.width() < 200 or size.height() < 100:
            raise RuntimeError(f"{name} was not drawn")
        made.append(f"{name} {size.width()}x{size.height()}")

    for theme in ("light", "dark"):
        ui.apply_theme(app, theme)
        window = MainWindow()
        ui.apply_theme(app, theme)  # MainWindow set the theme from the settings
        window.show()
        window.show_hour({"intro": 32.0, "service": 3080.0, "target": 3600, "songs": [("A song", 242.0)]})
        window.step_starts("mp3")
        window.wave_card.show()
        window.wave.set_levels([abs((i * 37) % 100 - 50) / 50 for i in range(600)],
                               [abs((i * 7) % 100 - 50) / 50 for i in range(4440 * 20)], 20)
        window.wave.set_length(4440.0)
        window.wave.set_cut("start", 542.0)
        window.wave.set_cut("end", 4095.0)
        window.job = {"path": "service.mkv"}
        window.show_cut_controls(make=True)
        window.wave.nudge("start", -5)
        if window.wave.cuts["start"] != 537.0 or window.steps["start"].value.text() != "8:57":
            raise RuntimeError("the start cut did not move")
        window.cut_times["end"].setText("1:08:10")  # a time typed for the end cut
        window.cut_times["end"].setModified(True)
        window.cut_typed("end")
        if window.wave.cuts["end"] != 4090.0 or window.cut_times["start"].text() != "8:57.0":
            raise RuntimeError("the end cut was not put where it was typed")
        window.wave.zoom_to("start")  # zoomed in on the start cut, and out again
        drawn(window, "zoomed")
        if not window.wave.zoomed() or window.wave_scroll.isHidden():
            raise RuntimeError("the picture of the recording did not zoom in")
        window.wave.show_all()
        window.wave.set_playhead(600.0)  # the play marker, and Play under the picture
        window.show_playing()
        if window.line_btn.isHidden() or window.line_time.text() != "10:00.0":
            raise RuntimeError("the play marker is not shown")
        window.update_banner.offer(updates.release_info({"tag_name": "v9.9.9", "body": "## What's new\n- **More.**"}),
                                   theme == "dark")
        window.result.show_result("Church Radio 2026-11-15.mp3", 3600.0, "Too long." if theme == "dark" else None)
        window.set_busy(True)  # (the Cancel button, and the light along the top line)
        drawn(window, "making")
        for _ in range(6):  # what moves: let the clocks and animations run for a moment
            time.sleep(0.03)
            drawn(window, "moving")
        made[:] = [m for m in made if not m.startswith("moving")]
        window.set_busy(False)
        ui.set_motion(False)
        drawn(window, "still")
        ui.set_motion(True)
        for key, _text in PAGES:
            window.show_page(key, models=False)  # (looking for the models makes the models folder)
            if window.pages.currentIndex() != [k for k, _t in PAGES].index(key):
                raise RuntimeError(f"the {key} page did not open")
            drawn(window, key)
        window.settings_form.collect()
        wizard = setup_wizard.SetupWizard(window, cfg, first_run=True)
        wizard.show()
        drawn(wizard, "SetupWizard")
        form = wizard.form
        for page in range(len(form.pages)):
            if form.pages[page] != form.page_models:
                form.go(page)
                app.processEvents()
        form.collect()
        wizard.done(0)
        window.close()
        app.processEvents()
    print(f"uitest: Qt {ui.qt_version()}, " + ", ".join(made))
    print("uitest: OK")
