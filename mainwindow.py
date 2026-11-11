"""The main window (Qt): drop a service recording on it to make the broadcast MP3."""
import atexit
import os
import queue
import threading

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget)

import audio
import builder
import churchyear
import cli
import paths
import prelude
import setup_wizard
import songs_window
import ui

MEDIA = "Service recordings (*.mkv *.mp4 *.wav *.mp3 *.m4a);;All files (*)"
CREDIT = "Created by Aaron Steger. Published by Leaven Labs."
# What the window says it is doing, from the lines the build writes to the log.
STEPS = (("in the first", "Finding the start of the service ..."),
         ("in the last", "Finding the end of the service ..."),
         ("Cutting long silences", "Cutting long silences ..."),
         ("Reading song catalog", "Choosing the songs ..."),
         ("Listening to", "Listening to new songs ..."),
         ("Writing MP3", "Writing the MP3 ..."))


def step_for(line):
    """The status text for a log line, or None if the line does not start a new step."""
    return next((text for mark, text in STEPS if mark in line), None)


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
    """The big area a recording is dropped on. (The whole window takes drops; this shows it.)"""

    def __init__(self, on_browse):
        super().__init__()
        self.setObjectName("drop")
        self.setMinimumHeight(130)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(4)
        big = ui.label("Drop the service recording here", "dropbig")
        big.setAlignment(Qt.AlignCenter)
        small = ui.label("MKV, MP4, WAV, MP3 or M4A", "sub")
        small.setAlignment(Qt.AlignCenter)
        self.browse = QPushButton("Browse...")
        self.browse.setObjectName("primary")
        self.browse.setFixedWidth(130)
        self.browse.clicked.connect(on_browse)
        lay.addWidget(big)
        lay.addWidget(small)
        lay.addSpacing(8)
        lay.addWidget(self.browse, 0, Qt.AlignCenter)

    def set_over(self, over):
        self.setProperty("over", "true" if over else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.q, self.busy, self.warning = queue.Queue(), False, None
        atexit.register(lambda: self.busy and cli.drop_lock())  # window closed mid-build
        self.setObjectName("root")
        self.setAcceptDrops(True)
        self.resize(840, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        top = QHBoxLayout()
        icon = QLabel()
        pix = QPixmap(paths.asset("icon-256.png"))
        if not pix.isNull():
            icon.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            top.addWidget(icon)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(ui.label(paths.APP_NAME, "title"))
        self.name_label = ui.label("", "sub")
        names.addWidget(self.name_label)
        top.addLayout(names)
        top.addStretch()
        self.songs_btn = QPushButton("Songs...")
        self.songs_btn.clicked.connect(self.songs)
        self.settings_btn = QPushButton("Settings...")
        self.settings_btn.clicked.connect(lambda: self.settings())
        about_btn = QPushButton("About")
        about_btn.setObjectName("ghost")
        about_btn.clicked.connect(lambda: about(self))
        for b in (self.songs_btn, self.settings_btn, about_btn):
            top.addWidget(b)
        lay.addLayout(top)

        self.drop = DropArea(self.browse)
        lay.addWidget(self.drop)

        options = ui.card()
        row = QHBoxLayout(options)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(22)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(ui.label("Service date", "hint"))
        self.date = ui.DateField()
        self.date.setFixedWidth(140)
        col.addWidget(self.date)
        row.addLayout(col)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(ui.label("Service start", "hint"))
        self.mode = QComboBox()
        self.mode.addItems(prelude.MODES)
        self.mode.setFixedWidth(150)
        col.addWidget(self.mode)
        row.addLayout(col)
        col = QVBoxLayout()
        col.setSpacing(6)
        self.cut_end = QCheckBox()
        self.cut_end.setChecked(True)
        self.compress = QCheckBox()
        col.addWidget(self.cut_end)
        col.addWidget(self.compress)
        row.addLayout(col)
        row.addStretch()
        lay.addWidget(options)
        self.start_hint = ui.label("", "hint", wrap=True)
        lay.addWidget(self.start_hint)

        self.status = ui.label("Ready.", "strong")
        lay.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1)
        lay.addWidget(self.bar)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(ui.fixed_font())
        lay.addWidget(self.text, 1)

        try:
            comp = {**audio.COMPRESSION, **builder.load_config().get("compression", {})}
        except (OSError, ValueError):
            comp = audio.COMPRESSION
        self.compress.setChecked(bool(comp["enabled"]))
        self.compress.setText(f"Compress the final MP3 ({comp['ratio']}:1, for radio)")
        self.show_settings()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

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
        self.start_hint.setText(f'Service start: Auto = cut the organ before "{start}" but keep a choir song. '
                                "Organ start = always cut there. Keep start = cut nothing (bell choir).")
        end = cfg.get("end_answer_phrase") or cfg.get("end_phrase") or prelude.END_PHRASE
        self.cut_end.setText(f'End the service at "{end}"')
        mode = cfg.get("service_start", prelude.MODES[0])
        self.mode.setCurrentText(mode if mode in prelude.MODES else prelude.MODES[0])

    def load_config(self, title):
        try:
            return builder.load_config()
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, title, f"Could not read config.json:\n{e}")
            return None

    def settings(self, first_run=False):
        """Open the setup wizard (first start) or Settings."""
        if self.busy:
            return
        cfg = self.load_config("Settings")
        if cfg is not None:
            setup_wizard.SetupWizard(self, cfg, on_done=self.show_settings, first_run=first_run).exec()

    def browse(self):
        f, _filter = QFileDialog.getOpenFileName(self, "Service recording", "", MEDIA)
        if f:
            self.start(os.path.normpath(f))

    def songs(self):
        """Open the Songs window (turn songs on/off, rename, seasons, play)."""
        if self.busy:
            return
        cfg = self.load_config("Songs")
        if cfg is None:
            return
        db = cfg.get("song_silence_db", audio.EDGE_SILENCE_DB)
        songs_window.SongsWindow(self, builder.songs_csv(), cfg.get("song_folders", []),
                                 cfg.get("song_min_words", songs_window.catalog.MIN_WORDS),
                                 get_edges=(lambda f: audio.edge_silence(f, db))
                                 if cfg.get("trim_song_silence", True) else None,
                                 models_folder=cfg.get("models_folder", ""),
                                 on_folders=self.save_song_folders).exec()

    def save_song_folders(self, folders):
        """Add songs put songs in a new folder: remember it in the settings."""
        try:
            cfg = builder.load_config()
            cfg["song_folders"] = list(folders)
            builder.save_config(cfg)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Songs", f"Could not save the song folders:\n{e}")

    # ---- a recording dropped on the window --------------------------------------------
    def dragEnterEvent(self, e):  # noqa: N802  (Qt's name)
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

    def set_busy(self, busy):
        self.busy = busy
        for w in (self.songs_btn, self.settings_btn, self.drop.browse):
            w.setEnabled(not busy)
        self.bar.setRange(0, 0 if busy else 1)  # 0..0: a moving bar, there is no known end
        self.bar.setValue(0)

    def start(self, path):
        if self.busy:
            return
        if not cli.take_lock("the app window"):
            QMessageBox.warning(self, paths.APP_NAME, "A broadcast is already being made "
                                f"({cli.lock_owner()}). Try again when it is done.")
            return
        date = churchyear.service_date(self.date.get(), self.date.changed, os.path.basename(path))
        if date != self.date.get():
            self.date.set_date(date)  # show the date read from the file name
        self.warning = None
        self.set_busy(True)
        self.text.clear()
        self.status.setText(f"Working on {os.path.basename(path)} ...")
        threading.Thread(target=self.work, args=(path, date, self.mode.currentText(), self.cut_end.isChecked(),
                                                 self.compress.isChecked()), daemon=True).start()

    def work(self, path, date, mode, cut_end, compress):
        try:
            self.q.put(("done", builder.build(path, date=date, log=self.log, start_mode=mode,
                                              warn=self.set_warning, cut_end=cut_end, compress=compress)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def set_warning(self, msg):
        self.warning = msg

    def poll(self):
        while not self.q.empty():
            kind, msg = self.q.get()
            if kind == "log":
                self.text.appendPlainText(msg)
                step = step_for(msg)
                if step and self.busy:
                    self.status.setText(step)
                continue
            cli.drop_lock()
            self.set_busy(False)
            self.status.setText("Done." if kind == "done" else "Failed.")
            self.text.appendPlainText(("" if kind == "done" else "ERROR: ") + msg)
            if kind == "done" and self.warning:
                self.status.setText("Done, but the MP3 is too long. Edit it in Audacity.")
                QMessageBox.warning(self, f"{paths.APP_NAME} - too long", f"MP3 saved:\n{msg}\n\n{self.warning}")
            elif kind == "done":
                self.bar.setValue(1)
                QMessageBox.information(self, paths.APP_NAME, "MP3 saved:\n" + msg)
            else:
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
    """--uitest: make every window once without showing it on a screen, and exit. No models, no
    internet. The release build runs it to check that the windows work in the packaged program."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = ui.start_app(["uitest"], "light")
    cfg = builder.load_config()
    made = []
    for theme in ("light", "dark"):
        ui.apply_theme(app, theme)
        window = MainWindow()
        ui.apply_theme(app, theme)  # MainWindow set the theme from the settings
        windows = [window, setup_wizard.SetupWizard(window, cfg, first_run=False),
                   songs_window.SongsWindow(window, builder.songs_csv(), [])]
        for w in windows:
            w.show()
            app.processEvents()
            size = w.grab().size()
            if size.width() < 200 or size.height() < 100:
                raise RuntimeError(f"{type(w).__name__} was not drawn")
            made.append(f"{type(w).__name__} {size.width()}x{size.height()}")
        wizard = windows[1]
        for page in range(len(wizard.pages)):
            if wizard.pages[page] != wizard.page_models:  # that page makes the models folder
                wizard.go(page)
                app.processEvents()
        wizard.collect()
        for w in reversed(windows):
            w.done(0) if isinstance(w, QDialog) else w.close()
        app.processEvents()
    print(f"uitest: Qt {ui.qt_version()}, " + ", ".join(made))
    print("uitest: OK")
