"""The Songs page: turn songs on or off, rename them, set their church seasons, play them.

Every change is saved to songs.csv at once (the same file Excel opens).
"""
import os
import queue
import subprocess
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QFileDialog, QHBoxLayout,
                               QHeaderView, QInputDialog, QLineEdit, QMenu, QMessageBox, QPushButton,
                               QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import audio
import catalog
import churchyear
import pdlookup
import ui

SEASON_LABELS = {"advent": "Advent", "christmas": "Christmas", "epiphany": "Epiphany", "lent": "Lent",
                 "holyweek": "Holy Week", "easter": "Easter", "pentecost": "Pentecost",
                 churchyear.PATRIOTIC: "Patriotic"}
SHOW = ("All songs", "On", "Off", "No words", "Public domain", "Allowed to broadcast", "Needs permission",
        "Not looked up")
# The choices above the list: what the button says, and its name in matches().
FILTERS = (("All", "All songs"), ("Allowed to broadcast", "Allowed to broadcast"),
           ("Needs permission", "Needs permission"), ("Not looked up", "Not looked up"), ("No words", "No words"),
           ("Off", "Off"))
COLUMNS = (("On", 76), ("", 48), ("Title", 300), ("Season", 190), ("Length", 90), ("May broadcast", 180))
ON, PLAY, TITLE, SEASONS, LENGTH, PD = range(6)
ROW_HEIGHT = 46
KEY = Qt.UserRole + 1  # on the Title item: the song's key in the song list (its file path)
PD_KIND = {"yes": "ok", "allowed": "ok", "check": "warn", "no": "no"}  # the colour of the label
BROADCAST_LABELS = {"yes": "Public domain", "allowed": "Allowed", "no": "Needs permission", "check": "Check",
                    "unknown": "Not found"}
NO_SELECTION = ("Click a switch to turn a song on or off. Double-click a title to rename it, or its season to "
                "choose when it plays. Select a song to see why it may or may not be broadcast.")
FILES_CSV = "CSV files (*.csv);;All files (*)"
PD_ABOUT = ("The app looks up each song's title on Wikidata (free, open data) and says whether the song "
            "(its words and tune) is in the public domain in the US: published before {first}.\n\n"
            "Allowed = under copyright, but released under a license that lets anyone broadcast it "
            "(Creative Commons), or you gave a permission. Needs permission = under copyright. Check = the "
            "original is old, but a newer version (for example an English translation) may be the one "
            "sung. Not found = Wikidata does not know the song.\n\n"
            "If you have permission for a song (a streaming or radio license such as CCLI, or the writer's "
            "OK), select it and click Add permission to mark it Allowed.\n\n"
            "This is a guide, not legal advice. It is about the song, not the recording: a modern "
            "recording or arrangement of an old hymn is still protected.")


def title_of(row):
    return row.get("title") or os.path.splitext(os.path.basename(row["file"]))[0]


def seasons_text(row):
    tags = [t.strip().lower() for t in (row.get("seasons") or "").split(";") if t.strip()]
    return ", ".join(SEASON_LABELS.get(t, t) for t in tags if t != "general") or "General"


def pd_label(row):
    """What the Public domain column shows: a typed permission shows as Allowed."""
    pd = (row.get("public_domain") or "").strip().lower()
    if (row.get("permission") or "").strip() and pd != "yes":
        return pdlookup.STATUS_LABELS["allowed"]
    return pdlookup.STATUS_LABELS.get(pd, "")


def broadcast_label(row):
    """What the May broadcast column shows: "Public domain", "Allowed", "Needs permission", "Check",
    "Not found", or nothing for a song not looked up yet."""
    pd = (row.get("public_domain") or "").strip().lower()
    if (row.get("permission") or "").strip() and pd != "yes":
        pd = "allowed"
    return BROADCAST_LABELS.get(pd, "")


def no_words(row, min_words=catalog.MIN_WORDS):
    w = (row.get("words") or "").strip()
    return w.isdigit() and int(w) < min_words


def matches(row, show, find, min_words=catalog.MIN_WORDS):
    """True if the row is listed for the Show choice and the Find text."""
    if show == "On" and not catalog.is_on(row) or show == "Off" and catalog.is_on(row):
        return False
    if show == "No words" and not no_words(row, min_words):
        return False
    pd = (row.get("public_domain") or "").strip().lower()
    permission = bool((row.get("permission") or "").strip())
    if show == "Public domain" and pd != "yes" or show == "Allowed to broadcast" and not catalog.cleared(row):
        return False
    if show == "Needs permission" and (pd not in ("no", "check") or permission):
        return False
    if show == "Not looked up" and (pd or permission):
        return False
    find = find.strip().lower()
    return not find or find in title_of(row).lower() or find in os.path.basename(row["file"]).lower()


def pd_kind(row):
    """The colour of the Public domain label: "ok", "warn", "no" or "" (see ui.PillDelegate)."""
    pd = (row.get("public_domain") or "").strip().lower()
    if (row.get("permission") or "").strip() and pd != "yes":
        pd = "allowed"
    return PD_KIND.get(pd, "")


def play(path):
    """Open the song in the PC's music player."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


def buttons_row(*buttons):
    """A row of buttons at the bottom of a box, pushed to the right."""
    row = QHBoxLayout()
    row.addStretch()
    for b in buttons:
        row.addWidget(b)
    return row


def ask_seasons(parent, name, current, on_ok):
    """A small box to tick the seasons a song may play in. on_ok(list of season tags) is called
    on OK (an empty list = General, any time of the year)."""
    current = set(current)
    dlg = QDialog(parent)
    dlg.setWindowTitle("Seasons")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.addWidget(ui.label(f"When may {name} play?", "strong", wrap=True))
    tick = {}
    for tag, text in SEASON_LABELS.items():
        tick[tag] = QCheckBox(text + (" (only on the holiday weekend)" if tag == churchyear.PATRIOTIC else ""))
        tick[tag].setChecked(tag in current)
        lay.addWidget(tick[tag])
    lay.addWidget(ui.label("None ticked = General: may play any time of the year.", "hint"))
    ok, cancel = QPushButton("OK"), QPushButton("Cancel")
    ok.setObjectName("primary")
    ok.setDefault(True)
    ok.clicked.connect(dlg.accept)
    cancel.clicked.connect(dlg.reject)
    lay.addSpacing(6)
    lay.addLayout(buttons_row(cancel, ok))
    if dlg.exec() == QDialog.Accepted:
        on_ok([t for t in SEASON_LABELS if tick[t].isChecked()])


def ask_identify(parent, rows, selected, on_ok):
    """Which songs to identify: the selected ones, the ones with no title, or all of them (a bulk
    scan). Calls on_ok(keys, keep titles and seasons already set, also check public domain)."""
    untitled = [k for k, r in rows.items() if not (r.get("title") or "").strip()]
    groups = [(f"The selected songs ({len(selected)})", list(selected)),
              (f"Songs with no title ({len(untitled)})", untitled),
              (f"All songs ({len(rows)}): a bulk scan", list(rows))]
    groups = [g for g in groups if g[1]]
    if not groups:
        QMessageBox.information(parent, "Identify", "There are no songs in the list yet.")
        return
    dlg = QDialog(parent)
    dlg.setWindowTitle("Identify songs")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(18, 16, 18, 16)
    intro = ui.label("The app listens to the start of each song and suggests its title and seasons. "
                     "You check the suggestions before anything is saved.", wrap=True)
    intro.setMinimumWidth(400)
    lay.addWidget(intro)
    which = QButtonGroup(dlg)
    for i, (text, _keys) in enumerate(groups):
        radio = QRadioButton(text)
        radio.setChecked(i == 0)
        which.addButton(radio, i)
        lay.addWidget(radio)
    lay.addSpacing(6)
    keep = QCheckBox("Keep the titles and seasons songs already have\n(only songs with no title get a suggestion)")
    keep.setChecked(True)
    check_pd = QCheckBox("Also check whether each song is in the public domain\n(needs the internet)")
    check_pd.setChecked(True)
    lay.addWidget(keep)
    lay.addWidget(check_pd)
    lay.addWidget(ui.label("Listening takes a few seconds per song: a bulk scan of many songs can take a "
                           "while. Cancel in the next window keeps nothing.", "hint", wrap=True))
    start, cancel = QPushButton("Start"), QPushButton("Cancel")
    start.setObjectName("primary")
    start.setDefault(True)
    start.clicked.connect(dlg.accept)
    cancel.clicked.connect(dlg.reject)
    lay.addSpacing(6)
    lay.addLayout(buttons_row(cancel, start))
    if dlg.exec() == QDialog.Accepted:
        on_ok(groups[which.checkedId()][1], keep.isChecked(), check_pd.isChecked())


class SongsPage(QWidget):
    """The Songs page of the main window. reload() reads the song list again (when the page is
    opened); shutdown() stops its background work (when the window closes)."""

    def __init__(self, csv_path, folders, min_words=catalog.MIN_WORDS, get_edges=None, models_folder="",
                 on_folders=None):
        super().__init__()
        self.path, self.on_folders = csv_path, on_folders
        self.use(folders, min_words, get_edges, models_folder)
        self.rows = catalog.load(csv_path)
        self.row_of, self.counts, self.filling, self.closed, self.pd_running = {}, "", False, False, False
        self.jobs = 0  # background work that writes songs.csv (import, look for new songs)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(ui.label("Songs", "pagetitle"))
        self.status = ui.label("", "sub")
        top.addWidget(self.status)
        top.addStretch()
        self.import_btn = QPushButton("Import list")
        self.import_btn.clicked.connect(self.import_list)
        self.find_btn = QPushButton("Look for new songs")
        self.find_btn.clicked.connect(self.rescan)
        self.pd_btn = QPushButton("Check public domain")
        self.pd_btn.clicked.connect(self.public_domain)
        add = QPushButton("Add songs")
        add.setObjectName("primary")
        add.clicked.connect(self.add_songs)
        for b in (self.import_btn, self.find_btn, self.pd_btn, add):
            b.setAutoDefault(False)
            top.addWidget(b)
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Find a song")
        self.find.setClearButtonEnabled(True)
        self.find.setMinimumWidth(160)
        self.find.setMaximumWidth(320)
        self.find.textChanged.connect(lambda _t: self.fill())
        row.addWidget(self.find, 1)
        self.show_box = ui.Segments([text for text, _show in FILTERS])
        self.show_box.changed.connect(lambda _name: self.fill())
        row.addWidget(self.show_box)
        row.addStretch()
        lay.addLayout(row)

        self.table = t = QTableWidget(0, len(COLUMNS))
        t.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        t.verticalHeader().hide()
        t.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        t.setShowGrid(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.ExtendedSelection)
        t.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        t.setItemDelegateForColumn(ON, ui.SwitchDelegate(t))
        t.setItemDelegateForColumn(PLAY, ui.PlayDelegate(t))
        t.setItemDelegateForColumn(SEASONS, ui.ChipDelegate(t))
        t.setItemDelegateForColumn(PD, ui.PillDelegate(t))
        head = t.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setHighlightSections(False)
        for i, (_text, width) in enumerate(COLUMNS):
            t.setColumnWidth(i, width)
        head.setSectionResizeMode(TITLE, QHeaderView.Stretch)
        head.setSectionResizeMode(ON, QHeaderView.Fixed)
        head.setSectionResizeMode(PLAY, QHeaderView.Fixed)
        t.itemChanged.connect(self.item_changed)
        t.cellClicked.connect(self.click)
        t.cellDoubleClicked.connect(self.double_click)
        t.itemSelectionChanged.connect(self.show_note)
        t.setContextMenuPolicy(Qt.CustomContextMenu)
        t.customContextMenuRequested.connect(self.menu)
        for key, slot in ((Qt.Key_Space, lambda: self.set_on(None)), (Qt.Key_Return, self.play_selected),
                          (Qt.Key_Enter, self.play_selected)):
            QShortcut(QKeySequence(key), t, slot, context=Qt.WidgetShortcut)
        lay.addWidget(t, 1)

        # Under the list: the selected song, why it may (not) be broadcast, and what can be done with it.
        detail = ui.card()
        box = QHBoxLayout(detail)
        box.setContentsMargins(20, 16, 20, 16)
        box.setSpacing(14)
        self.pill = ui.label("", "pill")
        box.addWidget(self.pill, 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(3)
        self.note_title = ui.label("", "strong")
        self.note = ui.label("", "sub", wrap=True)
        text.addWidget(self.note_title)
        text.addWidget(self.note)
        box.addLayout(text, 1)
        self.rename_btn, self.seasons_btn = QPushButton("Rename"), QPushButton("Seasons")
        self.identify_btn, self.permission_btn = QPushButton("Identify"), QPushButton("Add permission")
        for b, slot in ((self.rename_btn, self.rename_selected), (self.seasons_btn, self.seasons_selected),
                        (self.identify_btn, self.identify_selected), (self.permission_btn, self.permission_selected)):
            b.setAutoDefault(False)
            b.clicked.connect(slot)
            box.addWidget(b, 0, Qt.AlignVCenter)
        lay.addWidget(detail)

        self.fill()

    def use(self, folders, min_words=catalog.MIN_WORDS, get_edges=None, models_folder=""):
        """Take what the settings say: the song folders, and how songs are measured."""
        self.folders, self.min_words, self.get_edges = folders, min_words, get_edges
        self.models_folder = models_folder

    def reload(self):
        """Read songs.csv again (a build or Excel may have changed it). An empty list: look for songs."""
        if self.working():
            return
        self.rows = catalog.load(self.path)
        self.fill()
        if not self.rows:
            self.rescan()

    def working(self):
        """True while background work is writing songs.csv: no broadcast is made meanwhile."""
        return self.pd_running or self.jobs > 0

    def shutdown(self):
        self.closed = True  # the background work and its timers stop
        self.pd_running = False

    # ---- list ---------------------------------------------------------------------------
    def fill(self):
        t = self.table
        sel, scroll = set(self.selected()), t.verticalScrollBar().value()
        self.filling = True
        t.setRowCount(0)
        self.row_of = {}
        shown = [k for k in sorted(self.rows, key=lambda k: title_of(self.rows[k]).lower())
                 if matches(self.rows[k], dict(FILTERS)[self.show_box.current()], self.find.text(),
                            self.min_words)]
        t.setRowCount(len(shown))
        for i, key in enumerate(shown):
            self.row_of[key] = i
            for col in range(len(COLUMNS)):
                t.setItem(i, col, QTableWidgetItem())
            self.put(i, key)
        t.clearSelection()
        mode = t.selectionMode()
        t.setSelectionMode(QAbstractItemView.MultiSelection)  # so every kept row is selected again
        for key in sel:
            if key in self.row_of:
                t.selectRow(self.row_of[key])
        t.setSelectionMode(mode)
        t.verticalScrollBar().setValue(scroll)
        self.filling = False
        on = sum(catalog.is_on(r) for r in self.rows.values())
        self.counts = f"{len(self.rows)} songs, {on} on"
        self.status.setText(self.counts if len(shown) == len(self.rows) else f"{len(shown)} shown. {self.counts}")
        self.show_note()

    def put(self, i, key):
        """Write one song into table row i."""
        r, t = self.rows[key], self.table
        on = catalog.is_on(r)
        texts = ("", "", title_of(r), seasons_text(r), audio.fmt(catalog._duration(r)), broadcast_label(r))
        for col, text in enumerate(texts):
            item = t.item(i, col)
            item.setText(text)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | (Qt.ItemIsEditable if col == TITLE else
                                                                    Qt.NoItemFlags))
            item.setForeground(QColor(ui.colors["text" if on else "off"]))
        t.item(i, ON).setData(Qt.UserRole, on)
        t.item(i, ON).setToolTip("On: the song may be chosen for a broadcast. Click to turn it "
                                 + ("off." if on else "on."))
        t.item(i, PLAY).setToolTip("Play the song")
        t.item(i, TITLE).setData(KEY, key)
        t.item(i, TITLE).setToolTip(r["file"])
        t.item(i, PD).setData(Qt.UserRole, pd_kind(r))

    def refresh(self, key):
        if key in self.row_of:
            was, self.filling = self.filling, True
            self.put(self.row_of[key], key)
            self.filling = was

    def later(self, call):
        """Run call() when the table has finished what it is doing (it may not be refilled from
        inside one of its own signals)."""
        QTimer.singleShot(0, lambda: None if self.closed else call())

    def save(self):
        try:
            catalog.save(self.path, self.rows)
            return True
        except OSError as e:
            QMessageBox.critical(self, "Songs", f"Could not save songs.csv:\n{e}\n\n"
                                 "If songs.csv is open in Excel, close it and try again.")
            return False

    # ---- actions ------------------------------------------------------------------------
    def key_at(self, row):
        item = self.table.item(row, TITLE)
        return item.data(KEY) if item else None

    def selected(self):
        model = self.table.selectionModel()
        rows = sorted(i.row() for i in model.selectedRows()) if model else []
        return [k for k in (self.key_at(r) for r in rows) if k in self.rows]

    def item_changed(self, item):
        """The person typed a new title."""
        if self.filling or item.column() != TITLE:
            return
        key = self.key_at(item.row())
        if key not in self.rows:
            return
        self.rows[key]["title"] = " ".join(item.text().split())
        self.save()
        self.later(self.fill)

    def click(self, row, col):
        """A click on the switch turns the song on or off; on the play button, plays it."""
        key = self.key_at(row)
        if key not in self.rows:
            return
        if col == ON:
            self.set_on(None, [key])
        elif col == PLAY:
            self.play(key)

    def double_click(self, row, col):
        key = self.key_at(row)
        if key and col == SEASONS:
            self.edit_seasons([key])
        elif key and col in (LENGTH, PD):  # a double-click on the title itself already edits it
            self.rename(key)

    def menu(self, pos):
        """Right-click on the list: everything that can be done with the selected songs."""
        if not self.selected():
            return
        m = QMenu(self)
        for text, slot in (("Play", self.play_selected), (None, None), ("Turn on", lambda: self.set_on(True)),
                           ("Turn off", lambda: self.set_on(False)), (None, None),
                           ("Rename", self.rename_selected), ("Seasons", self.seasons_selected),
                           ("Identify", self.identify_selected), (None, None),
                           ("Check public domain", self.public_domain), ("Permission", self.permission_selected)):
            if text is None:
                m.addSeparator()
            else:
                m.addAction(text, slot)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def set_on(self, on, keys=None):
        """Turn the songs on (True), off (False), or flip each one (None)."""
        keys = keys or self.selected()
        for k in keys:
            r = self.rows[k]
            r["enabled"] = "yes" if (not catalog.is_on(r) if on is None else on) else "no"
        if keys and self.save():
            self.fill()

    def play_selected(self):
        keys = self.selected()
        if keys:
            self.play(keys[0])

    def play(self, key):
        path = self.rows[key]["file"]
        if not os.path.exists(path):
            QMessageBox.critical(self, "Songs", f"File not found:\n{path}")
            return
        try:
            play(path)
        except OSError as e:
            QMessageBox.critical(self, "Songs", f"Could not play the song:\n{e}")

    def rename_selected(self):
        keys = self.selected()
        if keys:
            self.rename(keys[0])

    def rename(self, key):
        """Edit the title in place, in the Title cell. Enter saves, Esc cancels."""
        if key in self.row_of:
            item = self.table.item(self.row_of[key], TITLE)
            self.table.scrollToItem(item)
            self.table.setFocus()
            self.table.editItem(item)

    def seasons_selected(self):
        keys = self.selected()
        if keys:
            self.edit_seasons(keys)

    def edit_seasons(self, keys):
        """Tick the seasons the song(s) may play in. None ticked = General (any time)."""
        current = [t.strip().lower() for t in (self.rows[keys[0]].get("seasons") or "").split(";") if t.strip()]
        name = title_of(self.rows[keys[0]]) if len(keys) == 1 else f"{len(keys)} songs"

        def ok(tags):
            for k in keys:
                self.rows[k]["seasons"] = ";".join(tags)
            if self.save():
                self.fill()

        ask_seasons(self, name, current, ok)

    def add_songs(self):
        """Pick song files, let the app identify them, confirm, and copy them into a song folder."""
        import add_songs
        files, _filter = QFileDialog.getOpenFileNames(self, "Songs to add", "", add_songs.AUDIO)
        if files:
            add_songs.SongReview(self, [os.path.normpath(f) for f in files], self.path, self.folders, mode="add",
                                 min_words=self.min_words, models_folder=self.models_folder,
                                 get_edges=self.get_edges, on_done=self.after_review, check_pd=True).exec()

    def identify_selected(self):
        """Suggest titles and seasons for songs: the selected ones, those without a title, or all of
        them (a bulk scan), and if asked, look up whether they are in the public domain as well."""
        ask_identify(self, self.rows, self.selected(), self.run_identify)

    def run_identify(self, keys, keep, check_pd):
        import add_songs
        keys = [k for k in keys if os.path.exists(self.rows[k]["file"])]
        if not keys:
            QMessageBox.information(self, "Identify", "None of these song files could be found.")
            return
        add_songs.SongReview(self, keys, self.path, self.folders, mode="identify",
                             min_words=self.min_words, models_folder=self.models_folder,
                             rows=self.rows, on_done=self.after_review, keep=keep, check_pd=check_pd).exec()

    def after_review(self, folders=None):
        if folders is not None and folders != self.folders:
            self.folders = folders
            if self.on_folders:
                self.on_folders(folders)
        self.rows = catalog.load(self.path)
        self.fill()

    def import_list(self):
        """Explain the import file, offer the template, then import the file the person picks."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Import song list")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 16, 18, 16)
        text = ("Add many songs at once, or change their titles, seasons and on/off, from a CSV file "
                "(Excel: Save As → CSV).\n\n"
                "Columns:\n"
                "  file — the song's full path, or its file name if it is in one of your song folders\n"
                "  title — the song name\n"
                "  seasons — advent, christmas, epiphany, lent, holyweek, easter, pentecost or\n"
                "      patriotic, separated by ; (empty or general = any time of the year)\n"
                "  enabled — yes or no\n\n"
                "For a song already in your list, an empty cell keeps what is there now. "
                "The song files are not copied: they stay where they are.")
        about = ui.label(text, wrap=True)
        about.setMinimumWidth(540)
        lay.addWidget(about)
        picked = []

        def template():
            f, _filter = QFileDialog.getSaveFileName(dlg, "Save the template", "song import template.csv", FILES_CSV)
            if not f:
                return
            try:
                catalog.write_template(f)
            except OSError as e:
                QMessageBox.critical(dlg, "Import song list", f"Could not save the template:\n{e}")
                return
            if ui.ask(dlg, "Import song list", "Template saved. Replace the example rows with your "
                      "songs, save it, then click Import a file....\n\nOpen it now?"):
                try:
                    play(f)  # opens it in Excel (or the PC's CSV program)
                except OSError as e:
                    QMessageBox.critical(dlg, "Import song list", str(e))

        def pick():
            f, _filter = QFileDialog.getOpenFileName(dlg, "Song list to import", "", FILES_CSV)
            if f:
                picked.append(f)
                dlg.accept()

        tpl, imp, close = QPushButton("Download template..."), QPushButton("Import a file..."), QPushButton("Close")
        imp.setObjectName("primary")
        tpl.clicked.connect(template)
        imp.clicked.connect(pick)
        close.clicked.connect(dlg.reject)
        row = QHBoxLayout()
        row.addWidget(tpl)
        row.addStretch()
        row.addWidget(imp)
        row.addWidget(close)
        lay.addSpacing(8)
        lay.addLayout(row)
        if dlg.exec() == QDialog.Accepted and picked:
            self.run_import(picked[0])

    def show_note(self):
        """Under the list: why the selected song is (or is not) in the public domain, the
        permission typed for it, and its file."""
        keys = self.selected()
        r = self.rows.get(keys[0]) if len(keys) == 1 else None
        text, label, permission = [], "", ""
        if r:
            note, permission = (r.get("pd_note") or "").strip(), (r.get("permission") or "").strip()
            label = broadcast_label(r)
            if note:
                text.append(note if note.endswith((".", "?", "!")) else note + ".")
            if permission:
                text.append(f"Allowed to broadcast: {permission}")
            words = (r.get("words") or "").strip()
            text.append(r["file"] + (f"  ({words} words heard)" if words else ""))
        self.note_title.setText(title_of(r) if r else f"{len(keys)} songs selected" if keys else "No song selected")
        self.note.setText("\n".join(text) if r else "" if keys else NO_SELECTION)
        self.note.setVisible(bool(self.note.text()))
        self.pill.setText(label)
        self.pill.setVisible(bool(label))
        ui.set_prop(self.pill, "kind", pd_kind(r) if r else "")
        self.rename_btn.setEnabled(len(keys) == 1)
        self.seasons_btn.setEnabled(bool(keys))
        self.permission_btn.setEnabled(bool(keys))
        self.permission_btn.setText("Change permission" if permission else "Add permission")

    def permission_selected(self):
        """Type why the church may broadcast the selected songs (a license, a letter). Empty clears it."""
        keys = self.selected()
        if not keys:
            QMessageBox.information(self, "Permission", "Select the songs you have permission to broadcast.")
            return
        name = title_of(self.rows[keys[0]]) if len(keys) == 1 else f"these {len(keys)} songs"
        text, ok = QInputDialog.getText(
            self, "Permission", f"Why may you broadcast {name}?\n\nFor example: CCLI Streaming License 123456, "
            "your station's radio license, or \"email from the writer, 3 May 2026\".\n"
            "The song is then shown as Allowed. Leave it empty to take the permission off.",
            QLineEdit.Normal, self.rows[keys[0]].get("permission") or "")
        if not ok:
            return
        for k in keys:
            self.rows[k]["permission"] = " ".join(text.split())
        if self.save():
            self.fill()

    def public_domain(self):
        """Look up whether the selected songs (or every song not looked up yet) are in the public domain."""
        if self.pd_running:  # the button says Stop while it runs
            self.pd_running = False
            self.pd_btn.setText("Stopping ...")
            self.pd_btn.setEnabled(False)
            return
        keys = self.selected() or [k for k, r in self.rows.items() if not (r.get("public_domain") or "").strip()]
        if not keys:
            QMessageBox.information(self, "Public domain", "Every song has been looked up. Select songs to look "
                                    "them up again.")
            return
        about = PD_ABOUT.format(first=pdlookup.cutoff_year() + 1)
        if QMessageBox.question(self, "Public domain", f"Look up {len(keys)} song(s)? This needs the internet "
                                f"and takes a second or two per song.\n\n{about}",
                                QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok) != QMessageBox.Ok:
            return
        hymns = []
        try:
            import identify
            import paths
            hymns = identify.load_hymns(os.path.join(paths.bundled_dir(), "hymns.csv"))
        except (OSError, ValueError):
            pass
        self.pd_running = True
        self.pd_btn.setText("Stop")
        q = queue.Queue()
        titles = {k: title_of(self.rows[k]) for k in keys}

        def work():
            for i, k in enumerate(keys):
                if not self.pd_running:
                    break
                q.put(("progress", i))
                try:
                    q.put(("done", k, pdlookup.lookup(titles[k], hymns)))
                except pdlookup.LookupError_ as e:
                    q.put(("error", str(e)))
                    return
                time.sleep(pdlookup.PAUSE)
            q.put(("finished",))

        def poll():
            if self.closed:
                return
            while not q.empty():
                msg = q.get()
                if msg[0] == "progress":
                    self.status.setText(f"Looking up song {msg[1] + 1} of {len(keys)} ...")
                elif msg[0] == "done":
                    k, r = msg[1], msg[2]
                    if k in self.rows:
                        self.rows[k]["public_domain"], self.rows[k]["pd_note"] = r["status"], r["note"]
                        self.save()
                        self.refresh(k)
                        self.show_note()
                else:
                    self.pd_running = False
                    self.pd_btn.setText("Check public domain")
                    self.pd_btn.setEnabled(True)
                    self.fill()
                    if msg[0] == "error":
                        QMessageBox.critical(self, "Public domain", msg[1])
                    return
            QTimer.singleShot(150, poll)

        threading.Thread(target=work, daemon=True).start()
        poll()

    def in_background(self, work, then):
        """Run work() in a thread, then call then(result or None, error text or None) in the window."""
        result = {}

        def run():
            try:
                result["out"] = work()
            except Exception as e:  # noqa: BLE001  told to the person by then()
                result["error"] = str(e)

        def wait():
            if self.closed:
                return
            if t.is_alive():
                QTimer.singleShot(200, wait)
                return
            self.jobs -= 1
            then(result.get("out"), result.get("error"))

        self.jobs += 1
        t = threading.Thread(target=run, daemon=True)
        t.start()
        wait()

    def run_import(self, import_path):
        """Import in the background (new songs are measured, which can take a minute)."""
        self.import_btn.setEnabled(False)
        self.status.setText("Importing the song list ...")

        def then(out, error):
            self.import_btn.setEnabled(True)
            if error is not None:
                self.status.setText(self.counts)
                QMessageBox.critical(self, "Import song list", f"Could not import the song list:\n{error}\n\n"
                                     "If songs.csv is open in Excel, close it and try again.")
                return
            self.rows, added, updated, problems = out
            self.fill()
            msg = f"{added} song(s) added, {updated} updated."
            self.status.setText(f"{msg} {self.counts}")
            if problems:
                more = f"\n... and {len(problems) - 15} more." if len(problems) > 15 else ""
                QMessageBox.warning(self, "Import song list", f"{msg}\n\nThese lines were skipped:\n"
                                    + "\n".join(problems[:15]) + more)
            else:
                QMessageBox.information(self, "Import song list", msg)

        self.in_background(lambda: catalog.import_csv(self.path, import_path, self.folders, audio.duration,
                                                      get_edges=self.get_edges, log=lambda m: None), then)

    def rescan(self):
        """Look in the song folders for new songs (reads their lengths; can take a minute)."""
        self.find_btn.setEnabled(False)
        self.status.setText("Looking for new songs ...")

        def then(rows, error):
            self.find_btn.setEnabled(True)
            if error is not None:
                QMessageBox.critical(self, "Songs", f"Could not read the song folders:\n{error}")
                self.fill()
                return
            before = set(self.rows)
            self.rows = rows
            self.fill()
            new = len(set(self.rows) - before)
            if before:
                self.status.setText(f"{new} new song(s) found. {self.counts}")

        self.in_background(lambda: catalog.update(self.path, self.folders, audio.duration, log=lambda m: None,
                                                  get_edges=self.get_edges), then)
