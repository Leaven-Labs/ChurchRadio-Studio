"""Setup wizard: shown on the first start, and again from the Settings... button.

It asks for everything that is particular to a church: the broadcast name and length, the intro,
the song folders, the words that start and end the service, the patriotic holidays, and it can
download the speech models.
Everything is saved to the user's config.json (builder.save_config).
"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import builder
import churchyear
import prelude
import songs_window

AUDIO = (("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.wma *.aac"), ("All files", "*.*"))
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



class SetupWizard:
    """first_run: start at the welcome page; else (Settings) start at the broadcast page and
    allow Save on every page. on_done(cfg) is called after saving."""

    def __init__(self, parent, cfg, on_done=None, first_run=True):
        self.cfg, self.on_done, self.first_run = dict(cfg), on_done, first_run
        self.win = w = tk.Toplevel(parent)
        w.title("Set up ChurchRadio Studio" if first_run else "Settings")
        w.geometry("780x540")
        w.transient(parent)
        w.protocol("WM_DELETE_WINDOW", self.cancel)

        self.body = ttk.Frame(w)
        self.body.pack(fill="both", expand=True, padx=18, pady=(14, 6))
        nav = ttk.Frame(w)
        nav.pack(fill="x", padx=18, pady=(0, 14))
        self.step_label = ttk.Label(nav, foreground="#555555")
        self.step_label.pack(side="left")
        self.finish_btn = ttk.Button(nav, text="Save", command=self.finish)
        self.finish_btn.pack(side="right")
        self.next_btn = ttk.Button(nav, text="Next >", command=lambda: self.go(self.page + 1))
        self.next_btn.pack(side="right", padx=6)
        self.back_btn = ttk.Button(nav, text="< Back", command=lambda: self.go(self.page - 1))
        self.back_btn.pack(side="right")
        ttk.Button(nav, text="Cancel", command=self.cancel).pack(side="right", padx=(0, 18))

        self.make_vars()
        self.pages = [self.page_welcome, self.page_broadcast, self.page_intro, self.page_songs,
                      self.page_service, self.page_models, self.page_done]
        self.titles = ["Welcome", "Broadcast", "Intro", "Songs", "Service words", "Speech models", "Done"]
        self.download = None
        self.done_ok = False
        self.page = 0
        self.go(0 if first_run else 1)
        w.grab_set()

    # ---- settings <-> fields -------------------------------------------------------------
    def make_vars(self):
        c = self.cfg
        self.v = {
            "broadcast_name": tk.StringVar(value=c.get("broadcast_name") or builder.DEFAULT_NAME),
            "target_minutes": tk.StringVar(value=str(c.get("target_minutes", 60))),
            "tolerance_seconds": tk.StringVar(value=str(c.get("tolerance_seconds", 30))),
            "output_folder": tk.StringVar(value=c.get("output_folder", "")),
            "intro": tk.StringVar(value=c.get("intro", "")),
            "start_phrase": tk.StringVar(value=c.get("start_phrase", "Good morning")),
            "service_start": tk.StringVar(value=c.get("service_start", prelude.MODES[0])),
            "end_phrase": tk.StringVar(value=c.get("end_phrase", prelude.END_PHRASE)),
            "end_answer_phrase": tk.StringVar(value=c.get("end_answer_phrase", prelude.END_ANSWER_PHRASE)),
        }
        self.folders = list(c.get("song_folders") or [])
        on = set(c.get("patriotic_holidays", churchyear.HOLIDAYS))
        self.holidays = {h: tk.BooleanVar(value=h in on) for h in HOLIDAY_LABELS}

    def collect(self):
        """The settings as typed, or raise ValueError with a message for the person."""
        c = dict(self.cfg)
        name = self.v["broadcast_name"].get().strip()
        if not name or any(ch in name for ch in '\\/:*?"<>|'):
            raise ValueError('The broadcast name is used in the file name: it cannot be empty or '
                             'contain \\ / : * ? " < > |')
        try:
            minutes, tol = int(self.v["target_minutes"].get()), int(self.v["tolerance_seconds"].get())
        except ValueError:
            raise ValueError("The broadcast length and the allowed extra time must be whole numbers.")
        if not 5 <= minutes <= 300 or not 0 <= tol <= 600:
            raise ValueError("The broadcast length must be 5 to 300 minutes, the extra time 0 to 600 seconds.")
        intro = self.v["intro"].get().strip()
        if intro and not os.path.isfile(intro):
            raise ValueError(f"The intro file was not found:\n{intro}")
        c.update(broadcast_name=name, target_minutes=minutes, tolerance_seconds=tol,
                 output_folder=self.v["output_folder"].get().strip(), intro=intro,
                 song_folders=list(self.folders),
                 start_phrase=self.v["start_phrase"].get().strip(),
                 service_start=self.v["service_start"].get(),
                 end_phrase=self.v["end_phrase"].get().strip(),
                 end_answer_phrase=self.v["end_answer_phrase"].get().strip(),
                 patriotic_holidays=[h for h, var in self.holidays.items() if var.get()])
        return c

    # ---- navigation ---------------------------------------------------------------------
    def go(self, page):
        if not 0 <= page < len(self.pages):
            return
        for child in self.body.winfo_children():
            child.destroy()
        self.page = page
        self.pages[page]()
        last = page == len(self.pages) - 1
        self.back_btn.state(["!disabled"] if page > (0 if self.first_run else 1) else ["disabled"])
        self.next_btn.state(["disabled"] if last else ["!disabled"])
        if self.first_run:
            self.finish_btn.config(text="Finish")
            self.finish_btn.state(["!disabled"] if last and self.done_ok else ["disabled"])
        else:
            self.finish_btn.config(text="Save")
        self.step_label.config(text=f"Step {page + 1} of {len(self.pages)}: {self.titles[page]}")

    def heading(self, text, sub=""):
        ttk.Label(self.body, text=text, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        if sub:
            ttk.Label(self.body, text=sub, wraplength=620, justify="left").pack(anchor="w", pady=(4, 10))

    def row(self, label, var, width=40, hint=""):
        f = ttk.Frame(self.body)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, width=24).pack(side="left")
        e = ttk.Entry(f, textvariable=var, width=width)
        e.pack(side="left")
        if hint:
            ttk.Label(f, text=hint, foreground="#555555").pack(side="left", padx=6)
        return f

    # ---- pages --------------------------------------------------------------------------
    def page_welcome(self):
        self.heading("Welcome", "This app makes your radio broadcast from the week's service recording: "
                     "your intro, the service (with the organ prelude and the end cut off), and songs "
                     "that fill the time. These few steps set it up for your church. You can change "
                     "everything later with the Settings... button.")

    def page_broadcast(self):
        self.heading("Your broadcast", "The name is used for the MP3 file and its title, "
                     'for example "St. John Radio 2026-11-15.mp3". Use your station\'s or '
                     "program's name.")
        self.row("Broadcast name:", self.v["broadcast_name"], 20)
        self.row("Length (minutes):", self.v["target_minutes"], 6)
        self.row("May run over by (seconds):", self.v["tolerance_seconds"], 6, "songs never go past this")
        f = self.row("Save the MP3 in:", self.v["output_folder"], 40)
        ttk.Button(f, text="Browse...", command=lambda: self.pick_folder(self.v["output_folder"])).pack(side="left", padx=6)
        ttk.Label(self.body, text="Leave it empty to save the MP3 next to the service recording.",
                  foreground="#555555").pack(anchor="w", pady=(2, 0))

    def pick_folder(self, var):
        d = filedialog.askdirectory(parent=self.win)
        if d:
            var.set(os.path.normpath(d))

    def page_intro(self):
        self.heading("Your intro", "The intro plays first, before the service. Leave it empty if you "
                     "have no intro.")
        f = self.row("Intro file:", self.v["intro"], 52)
        b = ttk.Frame(self.body)
        b.pack(anchor="w", pady=6)
        ttk.Button(b, text="Browse...", command=self.pick_intro).pack(side="left")
        ttk.Button(b, text="Play", command=lambda: self.play(self.v["intro"].get())).pack(side="left", padx=6)
        ttk.Button(b, text="No intro", command=lambda: self.v["intro"].set("")).pack(side="left")
        del f

    def pick_intro(self):
        f = filedialog.askopenfilename(parent=self.win, filetypes=AUDIO)
        if f:
            self.v["intro"].set(os.path.normpath(f))

    def play(self, path):
        if path and os.path.isfile(path):
            try:
                songs_window.play(path)
            except OSError as e:
                messagebox.showerror("Play", str(e), parent=self.win)

    def page_songs(self):
        self.heading("Your songs", "Songs from these folders (and the folders inside them) fill the "
                     "time after the service. The app picks songs for the church season and avoids "
                     "repeats. You can turn songs on or off, rename them and set their seasons later "
                     "with Songs....")
        f = ttk.Frame(self.body)
        f.pack(fill="both", expand=True)
        self.folder_list = tk.Listbox(f, height=8)
        self.folder_list.pack(side="left", fill="both", expand=True)
        for d in self.folders:
            self.folder_list.insert("end", d)
        b = ttk.Frame(f)
        b.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(b, text="Add folder...", command=self.add_folder).pack(fill="x")
        ttk.Button(b, text="Remove", command=self.remove_folder).pack(fill="x", pady=4)
        self.folder_note = ttk.Label(self.body, text="", foreground="#555555")
        self.folder_note.pack(anchor="w", pady=(6, 0))
        self.count_songs()

    def add_folder(self):
        d = filedialog.askdirectory(parent=self.win, title="A folder with songs")
        if d and os.path.normpath(d) not in self.folders:
            self.folders.append(os.path.normpath(d))
            self.folder_list.insert("end", os.path.normpath(d))
            self.count_songs()

    def remove_folder(self):
        for i in reversed(self.folder_list.curselection()):
            self.folder_list.delete(i)
            del self.folders[i]
        self.count_songs()

    def count_songs(self):
        import catalog
        n = len(catalog.scan([d for d in self.folders if os.path.isdir(d)]))
        missing = [d for d in self.folders if not os.path.isdir(d)]
        self.folder_note.config(text=f"{n} song file(s) found." +
                                (f"  Not found: {', '.join(missing)}" if missing else ""))

    def page_service(self):
        self.heading("Service words", "The app listens for these words to cut the recording. Type "
                     "them as your pastor and congregation say them.")
        self.row("The service starts with:", self.v["start_phrase"], 30, 'e.g. "Good morning"')
        f = ttk.Frame(self.body)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text="Before those words:", width=24).pack(side="left")
        ttk.Combobox(f, values=prelude.MODES, state="readonly", width=12,
                     textvariable=self.v["service_start"]).pack(side="left")
        ttk.Label(f, text="Auto = cut the organ prelude but keep a choir song", foreground="#555555").pack(side="left", padx=6)
        self.row("The pastor's last words:", self.v["end_phrase"], 30, 'e.g. "Go now in peace"')
        self.row("The congregation answers:", self.v["end_answer_phrase"], 30, "the cut is right after this")
        ttk.Label(self.body, text="Leave the answer empty if your congregation does not answer; the "
                  "cut is then a few seconds after the pastor's last words.", foreground="#555555",
                  wraplength=620, justify="left").pack(anchor="w", pady=(2, 10))
        box = ttk.LabelFrame(self.body, text="Patriotic songs play only on the weekend of:")
        box.pack(fill="x")
        for h, label in HOLIDAY_LABELS.items():
            ttk.Checkbutton(box, text=label, variable=self.holidays[h]).pack(anchor="w", padx=10)

    def page_models(self):
        self.heading("Speech models", f"The app uses two speech-recognition models (about {MODELS_MB} MB) "
                     "to find the start and end of the service. They download once and are then used "
                     "offline. Download them now, or they download during the first build.")
        folder = prelude._models_dir(self.cfg.get("models_folder", ""))
        ready = all(prelude._model_ready(folder, m) for m in (prelude.MODEL_NAME, prelude.END_MODEL_NAME))
        self.model_note = ttk.Label(self.body, text=("The models are already on this PC." if ready else
                                                     f"Not downloaded yet. They go to {folder}"), wraplength=620)
        self.model_note.pack(anchor="w", pady=6)
        self.bar = ttk.Progressbar(self.body, maximum=MODELS_MB, length=500)
        self.bar.pack(anchor="w", pady=6)
        self.dl_btn = ttk.Button(self.body, text="Download now", command=lambda: self.start_download(folder))
        self.dl_btn.pack(anchor="w")
        if ready:
            self.bar["value"] = MODELS_MB
            self.dl_btn.state(["disabled"])
        elif self.download and self.download["thread"].is_alive():
            self.dl_btn.state(["disabled"])
            self.watch_download(folder)

    def start_download(self, folder):
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
        self.dl_btn.state(["disabled"])
        self.watch_download(folder)

    def watch_download(self, folder):
        if not self.win.winfo_exists() or self.page != self.pages.index(self.page_models):
            return
        mb = folder_size_mb(folder)
        if self.download["thread"].is_alive():
            self.bar["value"] = min(mb, MODELS_MB * 0.99)
            self.model_note.config(text=f"Downloading ... {mb:.0f} MB of about {MODELS_MB} MB")
            self.win.after(700, lambda: self.watch_download(folder))
        elif self.download["error"]:
            self.model_note.config(text=f"Download failed: {self.download['error']}\n"
                                        "Check the internet connection and try again.")
            self.dl_btn.state(["!disabled"])
        else:
            self.bar["value"] = MODELS_MB
            self.model_note.config(text="The models are on this PC. They are used offline from now on.")

    def page_done(self):
        self.done_ok = False
        try:
            c = self.collect()
        except ValueError as e:
            self.heading("Almost done", "Please go back and fix this:")
            ttk.Label(self.body, text=str(e), foreground="#b00020", wraplength=620).pack(anchor="w")
            return
        self.done_ok = True
        self.heading("All set", "Click Finish to save. Then drop the service recording on the window "
                     "to make the broadcast.")
        lines = [f"Broadcast: {c['broadcast_name']}, {c['target_minutes']} minutes",
                 f"Intro: {c['intro'] or '(none)'}",
                 f"Song folders: {len(c['song_folders'])}",
                 f'Service starts at "{c["start_phrase"]}" and ends after "{c["end_answer_phrase"] or c["end_phrase"]}"',
                 f"MP3 saved in: {c['output_folder'] or 'the folder of the service recording'}"]
        for line in lines:
            ttk.Label(self.body, text="•  " + line, wraplength=620).pack(anchor="w", pady=1)
        if not c["song_folders"]:
            ttk.Label(self.body, text="No song folders: no songs will be added after the service.",
                      foreground="#b00020").pack(anchor="w", pady=(8, 0))

    # ---- save / cancel ------------------------------------------------------------------
    def finish(self):
        try:
            c = self.collect()
        except ValueError as e:
            messagebox.showerror("Settings", str(e), parent=self.win)
            return
        c["setup_done"] = True
        try:
            builder.save_config(c)
        except OSError as e:
            messagebox.showerror("Settings", f"Could not save the settings:\n{e}", parent=self.win)
            return
        self.win.destroy()
        if self.on_done:
            self.on_done(c)

    def cancel(self):
        if self.first_run and not messagebox.askyesno(
                "Set up", "Stop the setup? It opens again the next time you start the app.", parent=self.win):
            return
        self.win.destroy()
