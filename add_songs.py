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
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import audio
import catalog
import identify
import paths
import pdlookup
import prelude
import songs_window

AUDIO = (("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.wma *.aac"), ("All files", "*.*"))
COLUMNS = (("use", "Use", 40, "center"), ("title", "Title", 220, "w"), ("seasons", "Seasons", 120, "w"),
           ("how", "Found by", 180, "w"), ("pd", "Public domain", 95, "center"), ("heard", "Words heard", 210, "w"),
           ("file", "File", 140, "w"))


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


class SongReview:
    def __init__(self, parent, items, csv_path, folders, mode="add", min_words=catalog.MIN_WORDS,
                 models_folder="", get_edges=None, rows=None, on_done=None, keep=False, check_pd=False):
        self.items, self.path, self.folders, self.mode = list(items), csv_path, list(folders), mode
        self.min_words, self.models_folder, self.get_edges = min_words, models_folder, get_edges
        self.rows, self.on_done, self.keep, self.check_pd = rows or {}, on_done, keep, check_pd
        self.hymns, self.pd_offline = [], False
        self.result, self.use = {}, {}
        self.q, self.stop = queue.Queue(), False
        self.win = w = tk.Toplevel(parent)
        w.title("Add songs" if mode == "add" else "Identify songs")
        w.geometry("1020x560")
        w.transient(parent)
        w.protocol("WM_DELETE_WINDOW", self.cancel)

        intro = ("The app listens to each song and suggests a title and when it may play. Check the "
                 "suggestions, change any that are wrong, untick songs you don't want, then click ")
        ttk.Label(w, text=intro + ("Add." if mode == "add" else "Save."), wraplength=980,
                  justify="left").pack(fill="x", padx=10, pady=(10, 4))
        if mode == "add":
            row = ttk.Frame(w)
            row.pack(fill="x", padx=10, pady=4)
            ttk.Label(row, text="Put the songs in:").pack(side="left")
            self.dest = tk.StringVar(value=self.folders[0] if self.folders else "")
            self.dest_box = ttk.Combobox(row, values=self.folders, textvariable=self.dest, width=70)
            self.dest_box.pack(side="left", padx=6)
            ttk.Button(row, text="Other folder...", command=self.pick_dest).pack(side="left")
        self.pd_var = tk.BooleanVar(value=check_pd)
        ttk.Checkbutton(w, text="Also check whether each song is in the public domain (needs the internet)",
                        variable=self.pd_var, command=self.pd_toggled).pack(anchor="w", padx=10, pady=(0, 4))

        body = ttk.Frame(w)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        self.tree = ttk.Treeview(body, columns=[c[0] for c in COLUMNS], show="headings", selectmode="extended")
        for key, text, width, anchor in COLUMNS:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor=anchor, stretch=key in ("title", "heard"))
        self.tree.tag_configure("off", foreground="#888888")
        self.tree.tag_configure("unsure", foreground="#9a5b00")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for i, item in enumerate(self.items):
            self.use[item] = True
            self.tree.insert("", "end", iid=item, values=("✔", "(listening ...)", "", "", "", "",
                                                          os.path.basename(item)))
        self.tree.bind("<Button-1>", self.click)
        self.tree.bind("<Double-1>", self.double_click)

        bottom = ttk.Frame(w)
        bottom.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bottom, text="Play", command=self.play_selected).pack(side="left")
        ttk.Button(bottom, text="Rename...", command=self.rename_selected).pack(side="left", padx=(12, 0))
        ttk.Button(bottom, text="Seasons...", command=self.seasons_selected).pack(side="left", padx=4)
        self.save_btn = ttk.Button(bottom, text="Add" if mode == "add" else "Save", command=self.save)
        self.save_btn.pack(side="right")
        self.save_btn.state(["disabled"])
        ttk.Button(bottom, text="Cancel", command=self.cancel).pack(side="right", padx=6)
        self.bar = ttk.Progressbar(bottom, maximum=max(1, len(self.items)), length=160)
        self.bar.pack(side="right", padx=12)
        self.status = ttk.Label(bottom, text="Loading the speech model ...")
        self.status.pack(side="right")

        threading.Thread(target=self.work, daemon=True).start()
        w.after(150, self.poll)
        w.grab_set()

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
        self.check_pd = self.pd_var.get()
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
                                    "Public domain... in the Songs window."))

    def poll(self):
        if not self.win.winfo_exists():
            return
        while not self.q.empty():
            msg = self.q.get()
            if msg[0] == "progress":
                self.bar["value"] = msg[1]
                self.status.config(text=f"Listening to song {msg[1] + 1} of {len(self.items)} ...")
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
                self.tree.item(msg[1], values=("", "(could not read)", "", msg[2][:80], "", "", os.path.basename(msg[1])),
                               tags=("off",))
            elif msg[0] == "note":
                messagebox.showwarning("Songs", msg[1], parent=self.win)
            elif msg[0] == "finished":
                self.bar["value"] = len(self.items)
                n = sum(1 for k in self.items if self.use.get(k) and k in self.result)
                self.status.config(text=f"Done. {n} song(s) ticked.")
                self.save_btn.state(["!disabled"])
        self.win.after(150, self.poll)  # goes on: a renamed song is looked up again

    def refresh(self, item):
        r = self.result.get(item)
        if not r:
            return
        how = r["how"] + ("; no words: added turned off" if r["no_words"] and self.mode == "add" else "")
        seasons = songs_window.seasons_text({"seasons": ";".join(r["seasons"])})
        tags = ("off",) if not self.use[item] else (("unsure",) if r["sure"] < 0.6 else ())
        pd = pdlookup.STATUS_LABELS.get(r["pd"]["status"], "") if r.get("pd") else (
            "..." if self.check_pd and not self.pd_offline else "")
        self.tree.item(item, values=("✔" if self.use[item] else "", r["title"], seasons, how, pd,
                                     r["heard"][:120] or "(no words heard)", os.path.basename(item)), tags=tags)

    # ---- editing ------------------------------------------------------------------------
    def selected(self):
        return [k for k in self.tree.selection() if k in self.result]

    def click(self, e):
        if self.tree.identify_region(e.x, e.y) == "cell" and self.tree.identify_column(e.x) == "#1":
            key = self.tree.identify_row(e.y)
            if key in self.result:
                self.use[key] = not self.use[key]
                self.refresh(key)
                return "break"
        return None

    def double_click(self, e):
        key, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        if key not in self.result or col == "#1":
            return
        self.tree.selection_set([key])
        if col == "#3":
            self.seasons_selected()
        else:
            self.rename(key)

    def rename_selected(self):
        keys = self.selected()
        if keys:
            self.rename(keys[0])

    def rename(self, key):
        self.tree.see(key)
        x, y, w, h = self.tree.bbox(key, "#2")
        ent = ttk.Entry(self.tree)
        ent.insert(0, self.result[key]["title"])
        ent.select_range(0, "end")
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set()

        def done(keep):
            if not ent.winfo_exists() or getattr(ent, "done", False):
                return
            ent.done = True
            if keep and ent.get().strip() and ent.get().strip() != self.result[key]["title"]:
                title = ent.get().strip()
                self.result[key].update(title=title, how="title you typed", sure=1.0, pd=None)
                self.refresh(key)
                if self.check_pd and not self.pd_offline:  # the answer was for the old title
                    threading.Thread(target=self.look_up, args=(key, title), daemon=True).start()
            ent.destroy()

        ent.bind("<Return>", lambda e: done(True))
        ent.bind("<Escape>", lambda e: done(False))
        ent.bind("<FocusOut>", lambda e: done(True))

    def seasons_selected(self):
        keys = self.selected()
        if not keys:
            return
        name = self.result[keys[0]]["title"] if len(keys) == 1 else f"{len(keys)} songs"

        def ok(tags):
            for k in keys:
                self.result[k]["seasons"] = list(tags)
                self.refresh(k)

        songs_window.ask_seasons(self.win, name, self.result[keys[0]]["seasons"], ok)

    def play_selected(self):
        keys = self.selected()
        if keys:
            try:
                songs_window.play(keys[0])
            except OSError as e:
                messagebox.showerror("Play", str(e), parent=self.win)

    def pick_dest(self):
        d = filedialog.askdirectory(parent=self.win, title="Folder for the new songs")
        if d:
            self.dest.set(os.path.normpath(d))

    # ---- save ---------------------------------------------------------------------------
    def chosen(self):
        return [k for k in self.items if self.use.get(k) and k in self.result]

    def save(self):
        keys = self.chosen()
        if not keys:
            messagebox.showinfo("Songs", "No songs are ticked.", parent=self.win)
            return
        try:
            folders = self.save_add(keys) if self.mode == "add" else self.save_identify(keys)
        except OSError as e:
            messagebox.showerror("Songs", f"Could not save:\n{e}\n\nIf songs.csv is open in Excel, "
                                          "close it and try again.", parent=self.win)
            return
        if folders is None:
            return
        self.win.destroy()
        if self.on_done:
            self.on_done(folders if self.mode == "add" else None)

    def save_add(self, keys):
        """Copy the ticked songs into the chosen folder and add them to the song list."""
        dest = self.dest.get().strip()
        if not dest:
            messagebox.showerror("Add songs", "Choose the folder to put the songs in.", parent=self.win)
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

    def cancel(self):
        self.stop = True
        self.win.destroy()
        if self.on_done:
            self.on_done(None)
