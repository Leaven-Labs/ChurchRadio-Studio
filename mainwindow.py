"""The main window (Qt): a menu at the left and four pages: Broadcast (drop a service recording on
it to make the broadcast MP3), Songs, History and Settings."""
import atexit
import datetime as dt
import os
import queue
import threading

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import audio
import builder
import catalog
import churchyear
import cli
import paths
import prelude
import setup_wizard
import songs_window
import ui

MEDIA = "Service recordings (*.mkv *.mp4 *.wav *.mp3 *.m4a);;All files (*)"
CREDIT = "Created by Aaron Steger. Published by Leaven Labs."
PAGES = (("broadcast", "Broadcast"), ("songs", "Songs"), ("history", "History"), ("settings", "Settings"))
# What the window says it is doing, from the lines the build writes to the log: the words that
# mark the line, the step of the progress list it starts, and the status text.
STEPS = (("in the first", "start", "Finding the start of the service ..."),
         ("in the last", "end", "Finding the end of the service ..."),
         ("Cutting long silences", "silence", "Cutting long silences ..."),
         ("Reading song catalog", "songs", "Choosing the songs ..."),
         ("Listening to", "songs", "Listening to new songs ..."),
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
                       ("Free software under the MIT License.\nCopyright (c) 2026 Aaron Steger", "")):
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

    lic, close = QPushButton("Licenses"), QPushButton("Close")
    lic.setAutoDefault(False)
    lic.clicked.connect(licenses)
    close.setDefault(True)
    close.clicked.connect(dlg.accept)
    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(lic)
    row.addWidget(close)
    row.addStretch()
    lay.addSpacing(10)
    lay.addLayout(row)
    dlg.exec()


class DropArea(QFrame):
    """The card a recording is dropped on. (The whole window takes drops; this shows it.) With no
    recording it asks for one; then it shows the recording's name, length and folder."""

    def __init__(self, on_browse):
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
        self.browse.setObjectName("primary")
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
        atexit.register(lambda: self.busy and cli.drop_lock())  # window closed mid-build
        self.setObjectName("root")
        self.setAcceptDrops(True)
        self.resize(1180, 860)
        self.setMinimumSize(980, 700)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.make_side())
        self.pages = QStackedWidget()
        lay.addWidget(self.pages, 1)

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
        side = QFrame()
        side.setObjectName("side")
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

        self.drop = DropArea(self.browse)
        lay.addWidget(self.drop)

        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(24)
        self.cut_end = QCheckBox()
        self.cut_end.setChecked(True)
        self.compress = QCheckBox()
        row.addWidget(self.cut_end)
        row.addWidget(self.compress)
        row.addStretch()
        lay.addLayout(row)
        self.start_hint = ui.label("", "hint", wrap=True)
        self.start_hint.setContentsMargins(4, 0, 4, 0)
        lay.addWidget(self.start_hint)

        self.wave_card = ui.card()  # shown once there is a recording
        col = QVBoxLayout(self.wave_card)
        col.setContentsMargins(20, 18, 20, 14)
        col.setSpacing(10)
        col.addWidget(ui.label("WHERE THE SERVICE IS CUT", "caps"))
        self.wave = ui.Waveform()
        col.addWidget(self.wave)
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
        col.addWidget(self.bar)
        col.addStretch()
        cards.addWidget(progress, 4)
        lay.addLayout(cards)

        row = QHBoxLayout()
        self.details_btn = QPushButton()
        self.details_btn.setObjectName("ghost")
        self.details_btn.setCursor(Qt.PointingHandCursor)
        self.details_btn.clicked.connect(lambda: self.show_details(not self.text.isVisibleTo(page)))
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
        return page

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
        self.pages.setCurrentIndex([k for k, _text in PAGES].index(key))

    def show_season(self):
        self.season_label.setText(f"{season_name(self.date.get())} season")

    def show_settings(self, cfg=None):
        """Put the church's own words, name and look in the window (after setup or Settings)."""
        try:
            cfg = cfg or builder.load_config()
        except (OSError, ValueError):
            cfg = {}
        ui.apply_theme(ui.QApplication.instance(), cfg.get("theme", "auto"))
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
        for w in (self.nav["songs"], self.nav["settings"], self.drop.browse, self.choose_btn):
            w.setEnabled(not busy)
        self.bar.setRange(0, 0 if busy else 1)  # 0..0: a moving bar, there is no known end
        self.bar.setValue(0)

    def start(self, path):
        if self.busy:
            return
        if self.songs_page.working():
            QMessageBox.warning(self, paths.APP_NAME, "The song list is being updated. Try again when it is done.")
            return
        if not cli.take_lock("the app window"):
            QMessageBox.warning(self, paths.APP_NAME, "A broadcast is already being made "
                                f"({cli.lock_owner()}). Try again when it is done.")
            return
        date = churchyear.service_date(self.date.get(), self.date.changed, os.path.basename(path))
        if date != self.date.get():
            self.date.set_date(date)  # show the date read from the file name
            self.show_season()
        self.warning = None
        self.show_page("broadcast")
        self.set_busy(True)
        self.text.clear()
        self.drop.set_file(path)
        self.start_hint.hide()  # (it is the tooltip of Start too) room for the picture of the recording
        self.wave.reset()
        self.wave_card.show()
        threading.Thread(target=self.draw_recording, args=(path,), daemon=True).start()
        self.choose_btn.setText("Choose another recording")
        self.show_hour(None)
        for row in self.steps.values():
            row.set("todo", "")
        self.status.setText(f"Working on {os.path.basename(path)} ...")
        threading.Thread(target=self.work, args=(path, date, self.mode.currentText(), self.cut_end.isChecked(),
                                                 self.compress.isChecked()), daemon=True).start()

    def work(self, path, date, mode, cut_end, compress):
        try:
            try:
                self.tell("recording", audio.duration(path))
            except Exception:  # noqa: BLE001  (the build says what is wrong with the file)
                pass
            self.q.put(("done", builder.build(path, date=date, log=self.log, start_mode=mode,
                                              warn=self.set_warning, cut_end=cut_end, compress=compress,
                                              tell=self.tell)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def draw_recording(self, path):
        """In the background, next to the build: read how loud the recording is along its length."""
        try:
            levels = audio.loudness_outline(path)
        except Exception:  # noqa: BLE001  (only the picture is missing; the build says what is wrong)
            levels = None
        self.q.put(("wave", (path, levels)))

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
        while not self.q.empty():
            kind, msg = self.q.get()
            if kind == "tell":
                if self.busy:
                    self.told(*msg)
                continue
            if kind == "wave":  # may come after the build is done; not for an older recording
                if msg[0] == self.drop.path:
                    self.wave.set_levels(msg[1])
                continue
            if kind == "log":
                self.text.appendPlainText(msg)
                step = step_for(msg)
                if step and self.busy:
                    self.status.setText(step)
                    self.step_starts(step_key(msg))
                continue
            cli.drop_lock()
            self.set_busy(False)
            self.status.setText("Done." if kind == "done" else "Failed.")
            self.text.appendPlainText(("" if kind == "done" else "ERROR: ") + msg)
            for row in self.steps.values():
                if kind == "done":
                    row.set("done")
                elif row.state == "doing":
                    row.set("failed")
            self.history_page.reload()
            if kind == "done" and self.warning:
                self.status.setText("Done, but the MP3 is too long. Edit it in Audacity.")
                QMessageBox.warning(self, f"{paths.APP_NAME} - too long", f"MP3 saved:\n{msg}\n\n{self.warning}")
            elif kind == "done":
                self.bar.setValue(1)
                QMessageBox.information(self, paths.APP_NAME, "MP3 saved:\n" + msg)
            else:
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
        first_run = not builder.load_config().get("setup_done")
    except (OSError, ValueError):
        first_run = True
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
        window.wave.set_levels([abs((i * 37) % 100 - 50) / 50 for i in range(600)])
        window.wave.set_length(4440.0)
        window.wave.set_cut("start", 542.0)
        window.wave.set_cut("end", 4095.0)
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
