"""The settings: as a setup wizard on the first start, and as the Settings page of the main window.

They ask for everything that is particular to a church: the broadcast name and length, the look
(light or dark), the intro, the song folders, the words that start and end the service, the
patriotic holidays, and they can download the speech models.
Everything is saved to the user's config.json (builder.save_config).

SettingsForm holds the fields. As a wizard it shows one page at a time (Back / Next); as the
Settings page it shows them all under each other, with one Save button.
"""
import os
import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLineEdit,
                               QListWidget, QMessageBox, QProgressBar, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

import builder
import churchyear
import prelude
import songs_window
import ui

AUDIO = "Audio files (*.mp3 *.wav *.m4a *.flac *.ogg *.wma *.aac);;All files (*)"
HOLIDAY_LABELS = {"memorial": "Memorial Day", "independence": "Independence Day (July 4)",
                  "veterans": "Veterans Day", "labor": "Labor Day"}
MODELS_MB = 620  # base.en + small.en, about


def folder_size_mb(folder):
    total = 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1e6


class SettingsForm(QWidget):
    """The settings fields. wizard: one page at a time, with Back / Next (first_run: from the
    welcome page, and Finish only on the last page); else all of them on one page with Save.
    on_done(cfg) is called after saving, on_cancel() when Cancel is clicked in the wizard."""

    def __init__(self, cfg, on_done=None, wizard=False, first_run=False, on_cancel=None):
        super().__init__()
        self.cfg, self.on_done, self.wizard, self.first_run = dict(cfg), on_done, wizard, first_run
        self.folders = list(self.cfg.get("song_folders") or [])
        self.pages = [self.page_welcome, self.page_broadcast, self.page_intro, self.page_songs,
                      self.page_service, self.page_models, self.page_done]
        self.titles = ["Welcome", "Broadcast", "Intro", "Songs", "Service words", "Speech models", "Done"]
        self.download = None
        self.closed = False
        self.done_ok = False
        self.page = 0
        lay = QVBoxLayout(self)
        if not wizard:
            self.all_on_one_page(lay)
            return
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        nav = QHBoxLayout()
        self.step_label = ui.label("", "sub")
        nav.addWidget(self.step_label)
        nav.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(lambda: on_cancel() if on_cancel else None)
        self.back_btn = QPushButton("< Back")
        self.back_btn.clicked.connect(lambda: self.go(self.page - 1))
        self.next_btn = QPushButton("Next >")
        self.next_btn.clicked.connect(lambda: self.go(self.page + 1))
        self.finish_btn = QPushButton("Save")
        self.finish_btn.setObjectName("primary")
        self.finish_btn.clicked.connect(self.finish)
        for b in (cancel, self.back_btn, self.next_btn, self.finish_btn):
            b.setAutoDefault(False)
            nav.addWidget(b)
            if b is cancel:
                nav.addSpacing(14)
        lay.addLayout(nav)
        for build in self.pages:  # every page is made once; the last one is filled in when shown
            self.body = QVBoxLayout()
            self.body.setContentsMargins(0, 0, 0, 0)
            self.body.setSpacing(8)
            holder = QWidget()
            holder.setLayout(self.body)
            self.stack.addWidget(holder)
            build()
            self.body.addStretch()
        self.go(0 if first_run else 1)

    def all_on_one_page(self, lay):
        """The Settings page: every group of settings in its own card, and Save at the top."""
        lay.setContentsMargins(28, 24, 12, 0)
        lay.setSpacing(16)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 16, 0)
        top.setSpacing(12)
        top.addWidget(ui.label("Settings", "pagetitle"))
        self.saved_label = ui.label("", "sub")
        top.addWidget(self.saved_label)
        top.addStretch()
        self.finish_btn = QPushButton("Save")
        self.finish_btn.setObjectName("primary")
        self.finish_btn.setAutoDefault(False)
        self.finish_btn.clicked.connect(self.finish)
        top.addWidget(self.finish_btn)
        lay.addLayout(top)
        inside = QWidget()
        inside.setObjectName("scrollbody")
        cards = QVBoxLayout(inside)
        cards.setContentsMargins(0, 0, 16, 24)
        cards.setSpacing(16)
        for build in self.pages:
            if build in (self.page_welcome, self.page_done):
                continue
            card = ui.card()
            self.body = QVBoxLayout(card)
            self.body.setContentsMargins(20, 16, 20, 18)
            self.body.setSpacing(8)
            build()
            cards.addWidget(card)
        cards.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inside)
        lay.addWidget(scroll, 1)

    def set_folders(self, folders):
        """The song folders were changed elsewhere (Add songs made a new one)."""
        self.folders = list(folders)
        self.cfg["song_folders"] = list(folders)
        self.folder_list.clear()
        self.folder_list.addItems(self.folders)
        self.count_songs()

    # ---- settings <-> fields -------------------------------------------------------------
    def collect(self):
        """The settings as typed, or raise ValueError with a message for the person."""
        c = dict(self.cfg)
        name = self.name.text().strip()
        if not name or any(ch in name for ch in '\\/:*?"<>|'):
            raise ValueError('The broadcast name is used in the file name: it cannot be empty or '
                             'contain \\ / : * ? " < > |')
        try:
            minutes, tol = int(self.minutes.text()), int(self.tolerance.text())
        except ValueError:
            raise ValueError("The broadcast length and the allowed extra time must be whole numbers.")
        if not 5 <= minutes <= 300 or not 0 <= tol <= 600:
            raise ValueError("The broadcast length must be 5 to 300 minutes, the extra time 0 to 600 seconds.")
        intro = self.intro.text().strip()
        if intro and not os.path.isfile(intro):
            raise ValueError(f"The intro file was not found:\n{intro}")
        c.update(broadcast_name=name, target_minutes=minutes, tolerance_seconds=tol,
                 date_format=self.date_format.currentData() or builder.DATE_FORMAT,
                 output_folder=self.output.text().strip(), intro=intro,
                 theme=ui.THEMES[self.theme.currentIndex()],
                 song_folders=list(self.folders),
                 start_phrase=self.start_phrase.text().strip(),
                 service_start=self.service_start.currentText(),
                 end_phrase=self.end_phrase.text().strip(),
                 end_answer_phrase=self.end_answer.text().strip(),
                 patriotic_holidays=[h for h, box in self.holidays.items() if box.isChecked()])
        return c

    # ---- navigation ---------------------------------------------------------------------
    def go(self, page):
        if not self.wizard or not 0 <= page < len(self.pages):
            return
        self.page = page
        last = page == len(self.pages) - 1
        if last:
            self.fill_done()
        elif self.pages[page] == self.page_models:
            self.show_models()
        self.stack.setCurrentIndex(page)
        self.back_btn.setEnabled(page > (0 if self.first_run else 1))
        self.next_btn.setEnabled(not last)
        if self.first_run:
            self.finish_btn.setText("Finish")
            self.finish_btn.setEnabled(last and self.done_ok)
        else:
            self.finish_btn.setText("Save")
        self.step_label.setText(f"Step {page + 1} of {len(self.pages)}: {self.titles[page]}")

    def heading(self, text, sub=""):
        self.body.addWidget(ui.label(text, "heading"))
        if sub:
            self.body.addWidget(ui.label(sub, wrap=True))
            self.body.addSpacing(8)

    def row(self, text, widget, hint="", width=0):
        """One line: a label, the field and a hint. Returns the line's layout (to add a button)."""
        line = QHBoxLayout()
        lab = ui.label(text)
        lab.setFixedWidth(200)
        line.addWidget(lab)
        if width:
            widget.setFixedWidth(width)
        line.addWidget(widget, 0 if width else 1)
        if hint:
            line.addWidget(ui.label(hint, "hint"))
        if width:
            line.addStretch()
        self.body.addLayout(line)
        return line

    def button(self, text, slot):
        b = QPushButton(text)
        b.setAutoDefault(False)
        b.clicked.connect(slot)
        return b

    # ---- pages --------------------------------------------------------------------------
    def page_welcome(self):
        self.heading("Welcome", "This app makes your radio broadcast from the week's service recording: "
                     "your intro, the service (with the organ prelude and the end cut off), and songs "
                     "that fill the time. These few steps set it up for your church. You can change "
                     "everything later on the Settings page.")

    def page_broadcast(self):
        c = self.cfg
        self.heading("Your broadcast", "The name is used for the MP3 file and its title, with the service "
                     "date after it. Use your station's or program's name.")
        self.name = QLineEdit(c.get("broadcast_name") or builder.DEFAULT_NAME)
        self.minutes = QLineEdit(str(c.get("target_minutes", 60)))
        self.tolerance = QLineEdit(str(c.get("tolerance_seconds", 30)))
        self.output = QLineEdit(c.get("output_folder", ""))
        self.row("Broadcast name:", self.name, width=240)
        # The date in the file name and title: short (numbers) or long (the month as a word), and
        # the ways to write each. A format typed in config.json is listed too.
        fmt = builder.date_format(c)
        self.date_style = ui.Segments([style for style, _formats in builder.DATE_FORMATS])
        self.date_format = QComboBox()
        self.date_format.setFixedWidth(240)
        self.date_formats = {style: list(formats) for style, formats in builder.DATE_FORMATS}
        if fmt not in self.date_formats[builder.date_style(fmt)]:
            self.date_formats[builder.date_style(fmt)].append(fmt)
        holder = QWidget()
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(10)
        line.addWidget(self.date_style)
        line.addWidget(self.date_format)
        line.addStretch()
        self.row("Date in the file name:", holder)
        self.name_example = ui.label("", "hint")
        self.body.addWidget(self.name_example)
        self.body.addSpacing(6)
        self.date_style.set_current(builder.date_style(fmt))
        self.show_date_formats(fmt)
        self.date_style.changed.connect(lambda _style: self.show_date_formats())
        self.date_format.currentIndexChanged.connect(lambda _i: self.show_name_example())
        self.name.textChanged.connect(lambda _text: self.show_name_example())
        self.row("Length (minutes):", self.minutes, width=70)
        self.row("May run over by (seconds):", self.tolerance, "songs never go past this", width=70)
        line = self.row("Save the MP3 in:", self.output)
        line.addWidget(self.button("Browse...", lambda: self.pick_folder(self.output)))
        self.body.addWidget(ui.label("Leave it empty to save the MP3 next to the service recording.", "hint"))
        self.body.addSpacing(10)
        self.theme = QComboBox()
        self.theme.addItems([ui.THEME_LABELS[t] for t in ui.THEMES])
        theme = c.get("theme", "auto")
        self.theme.setCurrentIndex(ui.THEMES.index(theme) if theme in ui.THEMES else 0)
        self.row("The app's look:", self.theme, "light or dark", width=200)

    def show_date_formats(self, chosen=None):
        """List the date formats of the style chosen (Short or Long), each as the example date."""
        box = self.date_format
        box.blockSignals(True)
        box.clear()
        for fmt in self.date_formats[self.date_style.current()]:
            box.addItem(builder.format_date(builder.EXAMPLE_DATE, fmt), fmt)
        box.setCurrentIndex(max(0, box.findData(chosen)) if chosen else 0)
        box.blockSignals(False)
        self.show_name_example()

    def show_name_example(self):
        cfg = {"broadcast_name": self.name.text(), "date_format": self.date_format.currentData()}
        self.name_example.setText(f'The MP3 is named "{builder.output_name(cfg, builder.EXAMPLE_DATE)}" '
                                  "(for a service on November 15, 2026).")

    def pick_folder(self, field):
        d = QFileDialog.getExistingDirectory(self, "Folder", field.text())
        if d:
            field.setText(os.path.normpath(d))

    def page_intro(self):
        self.heading("Your intro", "The intro plays first, before the service. Leave it empty if you "
                     "have no intro.")
        self.intro = QLineEdit(self.cfg.get("intro", ""))
        self.row("Intro file:", self.intro)
        line = QHBoxLayout()
        line.addSpacing(206)
        line.addWidget(self.button("Browse...", self.pick_intro))
        line.addWidget(self.button("Play", lambda: self.play(self.intro.text())))
        line.addWidget(self.button("No intro", lambda: self.intro.setText("")))
        line.addStretch()
        self.body.addLayout(line)

    def pick_intro(self):
        f, _filter = QFileDialog.getOpenFileName(self, "Intro", "", AUDIO)
        if f:
            self.intro.setText(os.path.normpath(f))

    def play(self, path):
        if path and os.path.isfile(path):
            try:
                songs_window.play(path)
            except OSError as e:
                QMessageBox.critical(self, "Play", str(e))

    def page_songs(self):
        self.heading("Your songs", "Songs from these folders (and the folders inside them) fill the "
                     "time after the service. The app picks songs for the church season and avoids "
                     "repeats. You can turn songs on or off, rename them and set their seasons on "
                     "the Songs page.")
        line = QHBoxLayout()
        self.folder_list = QListWidget()
        self.folder_list.addItems(self.folders)
        self.folder_list.setMinimumHeight(190)
        line.addWidget(self.folder_list, 1)
        col = QVBoxLayout()
        col.addWidget(self.button("Add folder...", self.add_folder))
        col.addWidget(self.button("Remove", self.remove_folder))
        col.addStretch()
        line.addLayout(col)
        self.body.addLayout(line)
        self.folder_note = ui.label("", "hint", wrap=True)
        self.body.addWidget(self.folder_note)
        self.count_songs()

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "A folder with songs")
        if d and os.path.normpath(d) not in self.folders:
            self.folders.append(os.path.normpath(d))
            self.folder_list.addItem(os.path.normpath(d))
            self.count_songs()

    def remove_folder(self):
        for i in sorted((self.folder_list.row(item) for item in self.folder_list.selectedItems()), reverse=True):
            self.folder_list.takeItem(i)
            del self.folders[i]
        self.count_songs()

    def count_songs(self):
        import catalog
        n = len(catalog.scan([d for d in self.folders if os.path.isdir(d)]))
        missing = [d for d in self.folders if not os.path.isdir(d)]
        self.folder_note.setText(f"{n} song file(s) found." +
                                 (f"  Not found: {', '.join(missing)}" if missing else ""))

    def page_service(self):
        c = self.cfg
        self.heading("Service words", "The app listens for these words to cut the recording. Type "
                     "them as your pastor and congregation say them.")
        self.start_phrase = QLineEdit(c.get("start_phrase", "Good morning"))
        self.service_start = QComboBox()
        self.service_start.addItems(prelude.MODES)
        mode = c.get("service_start", prelude.MODES[0])
        self.service_start.setCurrentText(mode if mode in prelude.MODES else prelude.MODES[0])
        self.end_phrase = QLineEdit(c.get("end_phrase", prelude.END_PHRASE))
        self.end_answer = QLineEdit(c.get("end_answer_phrase", prelude.END_ANSWER_PHRASE))
        self.row("The service starts with:", self.start_phrase, 'e.g. "Good morning"', width=260)
        self.row("Before those words:", self.service_start, "Auto = cut the organ prelude but keep a choir song",
                 width=140)
        self.row("The pastor's last words:", self.end_phrase, 'e.g. "Go now in peace"', width=260)
        self.row("The congregation answers:", self.end_answer, "the cut is right after this", width=260)
        self.body.addWidget(ui.label("Leave the answer empty if your congregation does not answer; the "
                                     "cut is then a few seconds after the pastor's last words.", "hint", wrap=True))
        self.body.addSpacing(6)
        box = QGroupBox("Patriotic songs play only on the weekend of:")
        inside = QVBoxLayout(box)
        on = set(c.get("patriotic_holidays", churchyear.HOLIDAYS))
        self.holidays = {}
        for h, text in HOLIDAY_LABELS.items():
            self.holidays[h] = QCheckBox(text)
            self.holidays[h].setChecked(h in on)
            inside.addWidget(self.holidays[h])
        self.body.addWidget(box)

    def page_models(self):
        self.heading("Speech models", f"The app uses two speech-recognition models (about {MODELS_MB} MB) "
                     "to find the start and end of the service. They download once and are then used "
                     "offline. Download them now, or they download during the first build.")
        self.model_note = ui.label("", wrap=True)
        self.body.addWidget(self.model_note)
        self.bar = QProgressBar()
        self.bar.setRange(0, MODELS_MB)
        self.bar.setTextVisible(False)
        self.bar.setMaximumWidth(500)
        self.body.addWidget(self.bar)
        self.dl_btn = self.button("Download now", self.start_download)
        line = QHBoxLayout()
        line.addWidget(self.dl_btn)
        line.addStretch()
        self.body.addLayout(line)

    def show_models(self):
        """When the page is shown: are the models here already?"""
        if self.download and self.download["thread"].is_alive():
            return  # watch_download is keeping the page up to date
        try:
            folder = self.models_folder = prelude._models_dir(self.cfg.get("models_folder", ""))
        except OSError as e:
            self.model_note.setText(f"The models folder cannot be used: {e}")
            self.dl_btn.setEnabled(False)
            return
        ready = all(prelude._model_ready(folder, m) for m in (prelude.MODEL_NAME, prelude.END_MODEL_NAME))
        if not (self.download and self.download["error"]):
            self.model_note.setText("The models are already on this PC." if ready else
                                    f"Not downloaded yet. They go to {folder}")
        self.bar.setValue(MODELS_MB if ready else 0)
        self.dl_btn.setEnabled(not ready)

    def start_download(self):
        state = {"error": None}

        def work():
            try:
                for m in (prelude.MODEL_NAME, prelude.END_MODEL_NAME):
                    prelude._get_model(self.cfg.get("models_folder", ""), m)
            except Exception as e:  # noqa: BLE001
                state["error"] = str(e)

        state["thread"] = threading.Thread(target=work, daemon=True)
        self.download = state
        state["thread"].start()
        self.dl_btn.setEnabled(False)
        self.watch_download()

    def watch_download(self):
        if self.closed:
            return
        if self.download["thread"].is_alive():
            mb = folder_size_mb(self.models_folder)
            self.bar.setValue(int(min(mb, MODELS_MB * 0.99)))
            self.model_note.setText(f"Downloading ... {mb:.0f} MB of about {MODELS_MB} MB")
            QTimer.singleShot(700, self.watch_download)
        elif self.download["error"]:
            self.model_note.setText(f"Download failed: {self.download['error']}\n"
                                    "Check the internet connection and try again.")
            self.dl_btn.setEnabled(True)
        else:
            self.bar.setValue(MODELS_MB)
            self.model_note.setText("The models are on this PC. They are used offline from now on.")

    def page_done(self):
        """The last page: made empty, and filled in by fill_done each time it is shown."""
        self.done_body = self.body

    def fill_done(self):
        self.body = self.done_body
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.done_ok = False
        try:
            c = self.collect()
        except ValueError as e:
            self.heading("Almost done", "Please go back and fix this:")
            self.body.addWidget(ui.label(str(e), "error", wrap=True))
            self.body.addStretch()
            return
        self.done_ok = True
        self.heading("All set", "Click Finish to save. Then drop the service recording on the window "
                     "to make the broadcast." if self.first_run else "Click Save to keep these settings.")
        lines = [f"Broadcast: {c['broadcast_name']}, {c['target_minutes']} minutes",
                 f'MP3 file name: "{builder.output_name(c, builder.EXAMPLE_DATE)}" (for November 15, 2026)',
                 f"Intro: {c['intro'] or '(none)'}",
                 f"Song folders: {len(c['song_folders'])}",
                 f'Service starts at "{c["start_phrase"]}" and ends after "{c["end_answer_phrase"] or c["end_phrase"]}"',
                 f"MP3 saved in: {c['output_folder'] or 'the folder of the service recording'}"]
        for line in lines:
            self.body.addWidget(ui.label("•  " + line, wrap=True))
        if not c["song_folders"]:
            self.body.addSpacing(8)
            self.body.addWidget(ui.label("No song folders: no songs will be added after the service.", "error"))
        self.body.addStretch()

    # ---- save ---------------------------------------------------------------------------
    def finish(self):
        if not self.wizard:
            try:  # keep what was written to the settings since the page was made
                self.cfg = {**self.cfg, **builder.load_config(), "song_folders": list(self.folders)}
            except (OSError, ValueError):
                pass
        try:
            c = self.collect()
        except ValueError as e:
            QMessageBox.critical(self, "Settings", str(e))
            return
        c["setup_done"] = True
        try:
            builder.save_config(c)
        except OSError as e:
            QMessageBox.critical(self, "Settings", f"Could not save the settings:\n{e}")
            return
        self.cfg = dict(c)
        if not self.wizard:
            self.saved_label.setText("Saved.")
            QTimer.singleShot(4000, lambda: None if self.closed else self.saved_label.setText(""))
        if self.on_done:
            self.on_done(c)


class SetupWizard(QDialog):
    """The setup wizard of the first start: the settings, one page at a time. on_done(cfg) is
    called after saving. Open it with exec()."""

    def __init__(self, parent, cfg, on_done=None, first_run=True):
        super().__init__(parent)
        self.first_run, self.on_done = first_run, on_done
        self.setWindowTitle("Set up ChurchRadio Studio" if first_run else "Settings")
        self.resize(800, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        self.form = SettingsForm(cfg, on_done=self.saved, wizard=True, first_run=first_run, on_cancel=self.reject)
        lay.addWidget(self.form)

    def saved(self, cfg):
        QDialog.accept(self)
        if self.on_done:
            self.on_done(cfg)

    def done(self, result):
        self.form.closed = True
        super().done(result)

    def reject(self):
        """Cancel, Esc or the window's close button."""
        if self.first_run and not ui.ask(self, "Set up", "Stop the setup? It opens again the next time you "
                                                         "start the app."):
            return
        super().reject()
