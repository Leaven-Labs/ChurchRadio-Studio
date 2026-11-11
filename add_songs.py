"""Add songs / Identify: the app suggests a title and church seasons for each song, the person
checks them in a table, and then they are saved to the song list.

mode "add":      new files. They are copied into one of the song folders on Save.
mode "identify": songs already in the list (for example the ones with no title yet), or all of
                 them in one bulk scan. keep=True keeps the title and seasons a song already has.
check_pd=True also looks up whether each song is in the public domain (pdlookup.py), with the
title found, and saves the answer with the song. A tick box in the window turns it on or off at
any time; turned on, it also looks up the songs already done.
For each song the app reads its tags, listens to the start of it, and matches the words against
the hymn list (identify.py). It also measures the length, the silence at the start and end, and
whether it has words: a song with no words is added turned off.
"""
import os
import queue
import shutil
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QHeaderView, QMessageBox, QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

import audio
import catalog
import identify
import paths
import pdlookup
import prelude
import songs_window
import ui

AUDIO = "Audio files (*.mp3 *.wav *.m4a *.flac *.ogg *.wma *.aac);;All files (*)"
COLUMNS = (("Use", 52), ("Title", 230), ("Seasons", 130), ("Found by", 190), ("Public domain", 120),
           ("Words heard", 220), ("File", 150))
USE, TITLE, SEASONS, HOW, PD, HEARD, FILE = range(7)


def hymn_lists():
    """The hymn list shipped with the app, then the church's own hymns.csv (adds and replaces)."""
    return identify.load_hymns(os.path.join(paths.bundled_dir(), "hymns.csv"),
                               os.path.join(paths.data_dir(), "hymns.csv"))


def unique_path(folder, name):
    """folder/name, or folder/name (2).ext ... if that file already exists."""
    base, ext = os.path.splitext(name)
    dst, n = os.path.join(folder, name), 2
    while os.path.exists(dst):
        dst = os.path.join(folder, f"{base} ({n}){ext}")
        n += 1
    return dst


def analyse(path, hymns, models_folder="", min_words=catalog.MIN_WORDS, get_edges=None, known_title="",
            known_seasons=None):
    """Everything the review needs about one song (runs in the background).

    known_seasons (a list) with known_title: the song keeps both; the lyrics match is only told."""
    dur = audio.duration(path)
    tags = identify.read_tags(path)
    heard, sure = identify.heard_words(path, dur, models_folder)
    words = sure if sure >= min_words else max(sure, prelude.count_words(path, dur, models_folder))
    lead, tail = get_edges(path) if get_edges else (None, None)
    found = identify.identify(path, hymns, tags, heard, known_title)
    if known_title and known_seasons is not None:
        hint = ""
        if found["hymn"] and pdlookup.norm(found["hymn"]) != pdlookup.norm(known_title):
            hint = f'; the words sound like "{found["hymn"]}"'
        found = {**found, "seasons": list(known_seasons), "how": "title and seasons kept" + hint}
    return {**found, "duration": dur, "words": words, "no_words": words < min_words,
            "heard": heard, "lead": lead, "tail": tail}


def public_domain(title, hymns):
    """{'status', 'note'} for the title, or raises pdlookup.LookupError_ (offline)."""
    r = pdlookup.lookup(title, hymns)
    return {"status": r["status"], "note": r["note"]}


class SongReview(QDialog):
    """The review table. Open it with exec(). on_done(song folders or None) is called when it closes."""

    def __init__(self, parent, items, csv_path, folders, mode="add", min_words=catalog.MIN_WORDS,
                 models_folder="", get_edges=None, rows=None, on_done=None, keep=False, check_pd=False):
        super().__init__(parent)
        self.items, self.path, self.folders, self.mode = list(items), csv_path, list(folders), mode
        self.min_words, self.models_folder, self.get_edges = min_words, models_folder, get_edges
        self.rows, self.on_done, self.keep, self.check_pd = rows or {}, on_done, keep, check_pd
        self.hymns, self.pd_offline = [], False
        self.result, self.use = {}, {}
        self.q, self.stop, self.filling = queue.Queue(), False, False
        self.row_of = {item: i for i, item in enumerate(self.items)}
        self.setWindowTitle("Add songs" if mode == "add" else "Identify songs")
        self.resize(1080, 600)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        intro = ("The app listens to each song and suggests a title and when it may play. Check the "
                 "suggestions, change any that are wrong, untick songs you don't want, then click ")
        lay.addWidget(ui.label(intro + ("Add." if mode == "add" else "Save."), wrap=True))
        if mode == "add":
            row = QHBoxLayout()
            row.addWidget(ui.label("Put the songs in:"))
            self.dest = QComboBox()
            self.dest.setEditable(True)
            self.dest.addItems(self.folders)
            row.addWidget(self.dest, 1)
            other = QPushButton("Other folder...")
            other.setAutoDefault(False)
            other.clicked.connect(self.pick_dest)
            row.addWidget(other)
            lay.addLayout(row)
        self.pd_box = QCheckBox("Also check whether each song is in the public domain (needs the internet)")
        self.pd_box.setChecked(check_pd)
        self.pd_box.toggled.connect(self.pd_toggled)
        lay.addWidget(self.pd_box)

        self.table = t = QTableWidget(len(self.items), len(COLUMNS))
        t.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        t.verticalHeader().hide()
        t.verticalHeader().setDefaultSectionSize(34)
        t.setShowGrid(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.ExtendedSelection)
        t.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        t.setItemDelegateForColumn(PD, ui.PillDelegate(t))
        head = t.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setHighlightSections(False)
        for i, (_text, width) in enumerate(COLUMNS):
            t.setColumnWidth(i, width)
        head.setSectionResizeMode(TITLE, QHeaderView.Stretch)
        head.setSectionResizeMode(USE, QHeaderView.Fixed)
        self.filling = True
        for i, item in enumerate(self.items):
            self.use[item] = True
            for col in range(len(COLUMNS)):
                cell = QTableWidgetItem()
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                t.setItem(i, col, cell)
            self.put(i, True, "(listening ...)", "", "", "", "", "", item)
        self.filling = False
        t.itemChanged.connect(self.item_changed)
        t.cellDoubleClicked.connect(self.double_click)
        lay.addWidget(t, 1)

        bottom = QHBoxLayout()
        for text, slot in (("Play", self.play_selected), ("Rename...", self.rename_selected),
                           ("Seasons...", self.seasons_selected)):
            b = QPushButton(text)
            b.setAutoDefault(False)
            b.clicked.connect(slot)
            bottom.addWidget(b)
        bottom.addSpacing(12)
        self.status = ui.label("Loading the speech model ...", "sub")
        bottom.addWidget(self.status, 1)
        self.bar = QProgressBar()
        self.bar.setRange(0, max(1, len(self.items)))
        self.bar.setTextVisible(False)
        self.bar.setFixedWidth(160)
        bottom.addWidget(self.bar)
        bottom.addSpacing(12)
        cancel = QPushButton("Cancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        self.save_btn = QPushButton("Add" if mode == "add" else "Save")
        self.save_btn.setObjectName("primary")
        self.save_btn.setAutoDefault(False)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        bottom.addWidget(self.save_btn)
        lay.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(150)
        threading.Thread(target=self.work, daemon=True).start()

    def put(self, i, use, title, seasons, how, pd, pd_kind, heard, item, look="text", editable=False):
        """Write one song into table row i. look: the text colour ("text", "off" or "warn")."""
        t = self.table
        for col, text in enumerate(("", title, seasons, how, pd, heard, os.path.basename(item))):
            cell = t.item(i, col)
            cell.setText(text)
            cell.setForeground(QColor(ui.colors[look]))
        t.item(i, USE).setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | (Qt.ItemIsUserCheckable if editable
                                                                          else Qt.NoItemFlags))
        t.item(i, USE).setCheckState(Qt.Checked if use else Qt.Unchecked)
        t.item(i, TITLE).setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | (Qt.ItemIsEditable if editable
                                                                            else Qt.NoItemFlags))
        t.item(i, PD).setData(Qt.UserRole, pd_kind)
        t.item(i, HOW).setToolTip(how)
        t.item(i, HEARD).setToolTip(heard)
        t.item(i, FILE).setToolTip(item)

    def done(self, result):
        """Closing the window any way: stop the background work and tell the Songs window."""
        saved = result == QDialog.Accepted
        self.stop = True
        self.timer.stop()
        super().done(result)
        if self.on_done:
            self.on_done(self.saved_folders if saved and self.mode == "add" else None)

    # ---- background work ----------------------------------------------------------------
    def work(self):
        try:
            hymns = hymn_lists()
        except Exception as e:  # noqa: BLE001
            hymns = []
            self.q.put(("note", f"Could not read the hymn list: {e}"))
        self.hymns = hymns
        for i, item in enumerate(self.items):
            if self.stop:
                return
            self.q.put(("progress", i))
            row = self.rows.get(item) or {}
            known = (row.get("title") or "").strip() if self.keep else ""
            seasons = [t.strip().lower() for t in (row.get("seasons") or "").split(";") if t.strip()]
            try:
                r = analyse(item, hymns, self.models_folder, self.min_words, self.get_edges,
                            known_title=known, known_seasons=seasons if known else None)
            except Exception as e:  # noqa: BLE001
                self.q.put(("error", item, str(e)))
                continue
            self.q.put(("done", item, r))
            if self.check_pd and not self.pd_offline:
                self.look_up(item, r["title"])
        self.q.put(("finished",))

    def pd_toggled(self):
        """The tick box: on looks up the songs already done (and the rest as they are done)."""
        self.check_pd = self.pd_box.isChecked()
        if self.check_pd:
            self.pd_offline = False  # try again: the internet may be back
            todo = [(k, r["title"]) for k, r in self.result.items() if not r.get("pd")]
            if todo:
                threading.Thread(target=self.look_up_all, args=(todo,), daemon=True).start()
        for k in self.result:
            self.refresh(k)

    def look_up_all(self, todo):
        for item, title in todo:
            if self.stop or not self.check_pd or self.pd_offline:
                return
            self.look_up(item, title)

    def look_up(self, item, title):
        """Public-domain lookup for one song (in the background). Offline: told once, then skipped."""
        try:
            self.q.put(("pd", item, title, public_domain(title, self.hymns)))
        except pdlookup.LookupError_ as e:
            if not self.pd_offline:
                self.pd_offline = True
                self.q.put(("note", f"{e}\n\nThe songs are still identified; look them up later with "
                                    "Check public domain... in the Songs window."))

    def poll(self):
        while not self.q.empty():
            msg = self.q.get()
            if msg[0] == "progress":
                self.bar.setValue(msg[1])
                self.status.setText(f"Listening to song {msg[1] + 1} of {len(self.items)} ...")
            elif msg[0] == "done":
                self.result[msg[1]] = msg[2]
                self.refresh(msg[1])
            elif msg[0] == "pd":
                _, item, title, pd = msg
                if item in self.result and self.result[item]["title"] == title:  # not renamed since
                    self.result[item]["pd"] = pd
                    self.refresh(item)
            elif msg[0] == "error":
                self.use[msg[1]] = False
                self.filling = True
                self.put(self.row_of[msg[1]], False, "(could not read)", "", msg[2][:80], "", "", "", msg[1],
                         look="off")
                self.filling = False
            elif msg[0] == "note":
                QMessageBox.warning(self, "Songs", msg[1])
            elif msg[0] == "finished":
                self.bar.setValue(len(self.items))
                n = sum(1 for k in self.items if self.use.get(k) and k in self.result)
                self.status.setText(f"Done. {n} song(s) ticked.")
                self.save_btn.setEnabled(True)
        # The timer goes on: a renamed song is looked up again.

    def refresh(self, item):
        r = self.result.get(item)
        if not r:
            return
        how = r["how"] + ("; no words: added turned off" if r["no_words"] and self.mode == "add" else "")
        seasons = songs_window.seasons_text({"seasons": ";".join(r["seasons"])})
        look = "off" if not self.use[item] else ("warn" if r["sure"] < 0.6 else "text")
        status = r["pd"]["status"] if r.get("pd") else ""
        pd = pdlookup.STATUS_LABELS.get(status, "") if r.get("pd") else (
            "..." if self.check_pd and not self.pd_offline else "")
        was, self.filling = self.filling, True
        self.put(self.row_of[item], self.use[item], r["title"], seasons, how, pd,
                 songs_window.PD_KIND.get(status, ""), r["heard"][:120] or "(no words heard)", item,
                 look=look, editable=True)
        self.filling = was

    # ---- editing ------------------------------------------------------------------------
    def selected(self):
        rows = sorted(i.row() for i in self.table.selectionModel().selectedRows())
        return [self.items[r] for r in rows if self.items[r] in self.result]

    def item_changed(self, cell):
        """The person ticked the Use box, or typed a new title."""
        if self.filling:
            return
        key = self.items[cell.row()]
        if key not in self.result:
            return
        if cell.column() == USE:
            self.use[key] = cell.checkState() == Qt.Checked
        elif cell.column() == TITLE:
            title = " ".join(cell.text().split())
            if title and title != self.result[key]["title"]:
                self.result[key].update(title=title, how="title you typed", sure=1.0, pd=None)
                if self.check_pd and not self.pd_offline:  # the answer was for the old title
                    threading.Thread(target=self.look_up, args=(key, title), daemon=True).start()
        else:
            return
        QTimer.singleShot(0, lambda: None if self.stop else self.refresh(key))

    def double_click(self, row, col):
        key = self.items[row]
        if key not in self.result:
            return
        if col == SEASONS:
            self.table.selectRow(row)
            self.seasons_selected()
        elif col not in (USE, TITLE):  # a double-click on the title itself already edits it
            self.rename(key)

    def rename_selected(self):
        keys = self.selected()
        if keys:
            self.rename(keys[0])

    def rename(self, key):
        cell = self.table.item(self.row_of[key], TITLE)
        self.table.scrollToItem(cell)
        self.table.setFocus()
        self.table.editItem(cell)

    def seasons_selected(self):
        keys = self.selected()
        if not keys:
            return
        name = self.result[keys[0]]["title"] if len(keys) == 1 else f"{len(keys)} songs"

        def ok(tags):
            for k in keys:
                self.result[k]["seasons"] = list(tags)
                self.refresh(k)

        songs_window.ask_seasons(self, name, self.result[keys[0]]["seasons"], ok)

    def play_selected(self):
        keys = self.selected()
        if keys:
            try:
                songs_window.play(keys[0])
            except OSError as e:
                QMessageBox.critical(self, "Play", str(e))

    def pick_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Folder for the new songs")
        if d:
            self.dest.setEditText(os.path.normpath(d))

    # ---- save ---------------------------------------------------------------------------
    def chosen(self):
        return [k for k in self.items if self.use.get(k) and k in self.result]

    def save(self):
        keys = self.chosen()
        if not keys:
            QMessageBox.information(self, "Songs", "No songs are ticked.")
            return
        try:
            folders = self.save_add(keys) if self.mode == "add" else self.save_identify(keys)
        except OSError as e:
            QMessageBox.critical(self, "Songs", f"Could not save:\n{e}\n\nIf songs.csv is open in Excel, "
                                 "close it and try again.")
            return
        if folders is None:
            return
        self.saved_folders = folders
        self.accept()

    def save_add(self, keys):
        """Copy the ticked songs into the chosen folder and add them to the song list."""
        dest = self.dest.currentText().strip()
        if not dest:
            QMessageBox.critical(self, "Add songs", "Choose the folder to put the songs in.")
            return None
        os.makedirs(dest, exist_ok=True)
        rows = catalog.load(self.path)
        for k in keys:
            r = self.result[k]
            same = os.path.normcase(os.path.abspath(os.path.dirname(k))) == os.path.normcase(os.path.abspath(dest))
            dst = k if same else unique_path(dest, os.path.basename(k))
            if not same:
                shutil.copy2(k, dst)
            rows[dst] = {"file": dst, "title": r["title"], "duration": f"{r['duration']:.1f}",
                         "seasons": ";".join(r["seasons"]), "enabled": "no" if r["no_words"] else "yes",
                         "words": str(r["words"]),
                         "start_silence": "" if r["lead"] is None else f"{r['lead']:.2f}",
                         "end_silence": "" if r["tail"] is None else f"{r['tail']:.2f}"}
            self.save_pd(rows[dst], r)
        catalog.save(self.path, rows)
        folders = list(self.folders)
        if not any(os.path.normcase(os.path.abspath(dest)).startswith(os.path.normcase(os.path.join(os.path.abspath(f), "")))
                   or os.path.normcase(os.path.abspath(dest)) == os.path.normcase(os.path.abspath(f)) for f in folders):
            folders.append(dest)
        return folders

    def save_identify(self, keys):
        """Write the confirmed titles and seasons into the song list."""
        rows = catalog.load(self.path)
        for k in keys:
            if k in rows:
                rows[k]["title"] = self.result[k]["title"]
                rows[k]["seasons"] = ";".join(self.result[k]["seasons"])
                if not (rows[k].get("words") or "").strip():
                    rows[k]["words"] = str(self.result[k]["words"])
                self.save_pd(rows[k], self.result[k])
        catalog.save(self.path, rows)
        return []

    @staticmethod
    def save_pd(row, result):
        """The public-domain answer found during the scan, if any (a permission typed is kept)."""
        if result.get("pd"):
            row["public_domain"], row["pd_note"] = result["pd"]["status"], result["pd"]["note"]
