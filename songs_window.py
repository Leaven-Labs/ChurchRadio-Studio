"""Songs window: turn songs on or off, rename them, set their church seasons, play them.

Every change is saved to songs.csv at once (the same file Excel opens).
"""
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import audio
import catalog
import churchyear

SEASON_LABELS = {"advent": "Advent", "christmas": "Christmas", "epiphany": "Epiphany", "lent": "Lent",
                 "holyweek": "Holy Week", "easter": "Easter", "pentecost": "Pentecost",
                 churchyear.PATRIOTIC: "Patriotic"}
SHOW = ("All songs", "On", "Off", "No words")
COLUMNS = (("on", "On", 40, "center"), ("title", "Title", 300, "w"), ("seasons", "Seasons", 170, "w"),
           ("length", "Length", 60, "e"), ("words", "Words", 55, "e"), ("file", "File", 230, "w"))


def title_of(row):
    return row.get("title") or os.path.splitext(os.path.basename(row["file"]))[0]


def seasons_text(row):
    tags = [t.strip().lower() for t in (row.get("seasons") or "").split(";") if t.strip()]
    return ", ".join(SEASON_LABELS.get(t, t) for t in tags if t != "general") or "General"


def no_words(row, min_words=catalog.MIN_WORDS):
    w = (row.get("words") or "").strip()
    return w.isdigit() and int(w) < min_words


def matches(row, show, find, min_words=catalog.MIN_WORDS):
    """True if the row is listed for the Show choice and the Find text."""
    if show == "On" and not catalog.is_on(row) or show == "Off" and catalog.is_on(row):
        return False
    if show == "No words" and not no_words(row, min_words):
        return False
    find = find.strip().lower()
    return not find or find in title_of(row).lower() or find in os.path.basename(row["file"]).lower()


def play(path):
    """Open the song in the PC's music player."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


def ask_seasons(parent, name, current, on_ok):
    """A small box to tick the seasons a song may play in. on_ok(list of season tags) is called
    on OK (an empty list = General, any time of the year)."""
    current = set(current)
    dlg = tk.Toplevel(parent)
    dlg.title("Seasons")
    dlg.transient(parent)
    dlg.resizable(False, False)
    ttk.Label(dlg, text=f"When may {name} play?", wraplength=320).pack(anchor="w", padx=12, pady=(12, 6))
    tick = {}
    for tag, label in SEASON_LABELS.items():
        tick[tag] = tk.BooleanVar(value=tag in current)
        ttk.Checkbutton(dlg, text=label + (" (only on the holiday weekend)" if tag == churchyear.PATRIOTIC else ""),
                        variable=tick[tag]).pack(anchor="w", padx=20)
    ttk.Label(dlg, text="None ticked = General: may play any time of the year.",
              foreground="#555555").pack(anchor="w", padx=12, pady=(6, 0))
    btns = ttk.Frame(dlg)
    btns.pack(fill="x", padx=12, pady=12)

    def ok():
        tags = [t for t in SEASON_LABELS if tick[t].get()]
        dlg.destroy()
        on_ok(tags)

    ttk.Button(btns, text="OK", command=ok).pack(side="right")
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=6)
    dlg.bind("<Return>", lambda e: ok())
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    dlg.update_idletasks()  # open it over the middle of the window it belongs to
    dlg.geometry(f"+{parent.winfo_rootx() + (parent.winfo_width() - dlg.winfo_width()) // 2}"
                 f"+{parent.winfo_rooty() + (parent.winfo_height() - dlg.winfo_height()) // 3}")
    dlg.grab_set()
    return dlg


class SongsWindow:
    def __init__(self, parent, csv_path, folders, min_words=catalog.MIN_WORDS, get_edges=None,
                 models_folder="", on_folders=None):
        self.path, self.folders, self.min_words, self.get_edges = csv_path, folders, min_words, get_edges
        self.models_folder, self.on_folders = models_folder, on_folders
        self.rows = catalog.load(csv_path)
        self.win = w = tk.Toplevel(parent)
        w.title("Songs")
        w.geometry("900x560")
        w.transient(parent)
        w.grab_set()  # no build while songs are edited

        top = ttk.Frame(w)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="Find:").pack(side="left")
        self.find = tk.StringVar()
        self.find.trace_add("write", lambda *_: self.fill())
        ttk.Entry(top, textvariable=self.find, width=24).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Show:").pack(side="left")
        self.show = tk.StringVar(value=SHOW[0])
        cb = ttk.Combobox(top, values=SHOW, state="readonly", width=10, textvariable=self.show)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill())
        self.find_btn = ttk.Button(top, text="Look for new songs", command=self.rescan)
        self.find_btn.pack(side="right")
        ttk.Button(top, text="Add songs...", command=self.add_songs).pack(side="right", padx=6)

        ttk.Label(w, text="Click On to turn a song on or off. Double-click a title to rename it, "
                          "or Seasons to choose when it plays.").pack(fill="x", padx=10)
        body = ttk.Frame(w)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        self.tree = ttk.Treeview(body, columns=[c[0] for c in COLUMNS], show="headings", selectmode="extended")
        for key, text, width, anchor in COLUMNS:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor=anchor, stretch=key in ("title", "file"))
        self.tree.tag_configure("off", foreground="#888888")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.click)
        self.tree.bind("<Double-1>", self.double_click)
        self.tree.bind("<space>", lambda e: self.set_on(None))
        self.tree.bind("<Return>", lambda e: self.play_selected())

        bottom = ttk.Frame(w)
        bottom.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bottom, text="Play", command=self.play_selected).pack(side="left")
        ttk.Button(bottom, text="Turn on", command=lambda: self.set_on(True)).pack(side="left", padx=(12, 0))
        ttk.Button(bottom, text="Turn off", command=lambda: self.set_on(False)).pack(side="left", padx=4)
        ttk.Button(bottom, text="Rename...", command=self.rename_selected).pack(side="left", padx=(12, 0))
        ttk.Button(bottom, text="Seasons...", command=self.seasons_selected).pack(side="left", padx=4)
        ttk.Button(bottom, text="Identify...", command=self.identify_selected).pack(side="left", padx=(12, 0))
        ttk.Button(bottom, text="Close", command=w.destroy).pack(side="right")
        self.status = ttk.Label(bottom, text="")
        self.status.pack(side="right", padx=12)

        self.fill()
        if not self.rows:
            self.rescan()

    # ---- list ---------------------------------------------------------------------------
    def fill(self):
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for key in sorted(self.rows, key=lambda k: title_of(self.rows[k]).lower()):
            r = self.rows[key]
            if not matches(r, self.show.get(), self.find.get(), self.min_words):
                continue
            self.tree.insert("", "end", iid=key, values=self.values(r), tags=() if catalog.is_on(r) else ("off",))
            shown += 1
        keep = [k for k in sel if self.tree.exists(k)]
        if keep:
            self.tree.selection_set(keep)
        on = sum(catalog.is_on(r) for r in self.rows.values())
        self.counts = f"{len(self.rows)} songs, {on} on"
        self.status.config(text=self.counts if shown == len(self.rows) else f"{shown} shown. {self.counts}")

    def values(self, r):
        w = (r.get("words") or "").strip()
        return ("✔" if catalog.is_on(r) else "", title_of(r), seasons_text(r),
                audio.fmt(catalog._duration(r)), w if w else "-", os.path.basename(r["file"]))

    def refresh(self, key):
        r = self.rows[key]
        if self.tree.exists(key):
            self.tree.item(key, values=self.values(r), tags=() if catalog.is_on(r) else ("off",))

    def save(self):
        try:
            catalog.save(self.path, self.rows)
            return True
        except OSError as e:
            messagebox.showerror("Songs", f"Could not save songs.csv:\n{e}\n\n"
                                          "If songs.csv is open in Excel, close it and try again.", parent=self.win)
            return False

    # ---- actions ------------------------------------------------------------------------
    def selected(self):
        return list(self.tree.selection())

    def click(self, e):
        if self.tree.identify_region(e.x, e.y) == "cell" and self.tree.identify_column(e.x) == "#1":
            key = self.tree.identify_row(e.y)
            if key:
                self.tree.selection_set([key])
                self.set_on(None, [key])
                return "break"
        return None

    def double_click(self, e):
        key, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        if not key or col == "#1":
            return
        self.tree.selection_set([key])
        if col == "#3":
            self.edit_seasons([key])
        else:
            self.rename(key)

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
        if not keys:
            return
        path = self.rows[keys[0]]["file"]
        if not os.path.exists(path):
            messagebox.showerror("Songs", f"File not found:\n{path}", parent=self.win)
            return
        try:
            play(path)
        except OSError as e:
            messagebox.showerror("Songs", f"Could not play the song:\n{e}", parent=self.win)

    def rename_selected(self):
        keys = self.selected()
        if keys:
            self.rename(keys[0])

    def rename(self, key):
        """Edit the title in place: an entry box over the Title cell. Enter saves, Esc cancels."""
        self.tree.see(key)
        x, y, w, h = self.tree.bbox(key, "#2")
        ent = ttk.Entry(self.tree)
        ent.insert(0, self.rows[key].get("title") or title_of(self.rows[key]))
        ent.select_range(0, "end")
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set()

        def done(keep):
            if not ent.winfo_exists() or getattr(ent, "done", False):
                return
            ent.done = True
            if keep:
                self.rows[key]["title"] = ent.get().strip()
                if self.save():
                    self.refresh(key)
            ent.destroy()
            self.tree.focus_set()

        ent.bind("<Return>", lambda e: done(True))
        ent.bind("<KP_Enter>", lambda e: done(True))
        ent.bind("<Escape>", lambda e: done(False))
        ent.bind("<FocusOut>", lambda e: done(True))

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

        ask_seasons(self.win, name, current, ok)

    def add_songs(self):
        """Pick song files, let the app identify them, confirm, and copy them into a song folder."""
        import add_songs
        from tkinter import filedialog
        files = filedialog.askopenfilenames(parent=self.win, title="Songs to add", filetypes=add_songs.AUDIO)
        if files:
            add_songs.SongReview(self.win, list(files), self.path, self.folders, mode="add",
                                 min_words=self.min_words, models_folder=self.models_folder,
                                 get_edges=self.get_edges, on_done=self.after_review)

    def identify_selected(self):
        """Suggest titles and seasons for the selected songs (or every song without a title)."""
        import add_songs
        keys = self.selected() or [k for k, r in self.rows.items() if not (r.get("title") or "").strip()]
        keys = [k for k in keys if os.path.exists(self.rows[k]["file"])]
        if not keys:
            messagebox.showinfo("Identify", "Select the songs to identify (every song already has a title).",
                                parent=self.win)
            return
        add_songs.SongReview(self.win, keys, self.path, self.folders, mode="identify",
                             min_words=self.min_words, models_folder=self.models_folder,
                             rows=self.rows, on_done=self.after_review)

    def after_review(self, folders=None):
        if folders is not None and folders != self.folders:
            self.folders = folders
            if self.on_folders:
                self.on_folders(folders)
        self.rows = catalog.load(self.path)
        self.fill()
        self.win.grab_set()

    def rescan(self):
        """Look in the song folders for new songs (reads their lengths; can take a minute)."""
        self.find_btn.state(["disabled"])
        self.status.config(text="Looking for new songs ...")
        result = {}

        def work():
            try:
                result["rows"] = catalog.update(self.path, self.folders, audio.duration, log=lambda m: None,
                                                get_edges=self.get_edges)
            except Exception as e:  # noqa: BLE001
                result["error"] = str(e)

        def wait():
            if not self.win.winfo_exists():
                return
            if t.is_alive():
                self.win.after(200, wait)
                return
            self.find_btn.state(["!disabled"])
            if "error" in result:
                messagebox.showerror("Songs", f"Could not read the song folders:\n{result['error']}", parent=self.win)
                self.fill()
                return
            before = set(self.rows)
            self.rows = result["rows"]
            self.fill()
            new = len(set(self.rows) - before)
            self.status.config(text=f"{new} new song(s) found. {self.counts}" if before else self.counts)

        t = threading.Thread(target=work, daemon=True)
        t.start()
        wait()
