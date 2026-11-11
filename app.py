"""ChurchRadio Studio window. Drop a service recording on it to make the broadcast MP3."""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import audio
import builder
import churchyear
import datepicker
import paths
import prelude
import setup_wizard
import songs_window

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # drag and drop not installed: Browse still works
    TkinterDnD = None

MEDIA = (("Service recordings", "*.mkv *.mp4 *.wav *.mp3 *.m4a"), ("All files", "*.*"))


def set_icon(win):
    """The ChurchRadio Studio icon in the title bar and taskbar (all windows of the app)."""
    try:
        if sys.platform == "win32" and os.path.isfile(paths.asset("icon.ico")):
            win.iconbitmap(default=paths.asset("icon.ico"))
        elif os.path.isfile(paths.asset("icon-256.png")):
            win.iconphoto(True, tk.PhotoImage(file=paths.asset("icon-256.png")))
    except tk.TclError:
        pass  # no icon is better than no window


CREDIT = "Created by Aaron Steger. Published by Leaven Labs."


def about(parent):
    """Who made the app, its version and license, and where the third-party licenses are."""
    dlg = tk.Toplevel(parent)
    dlg.title(f"About {paths.APP_NAME}")
    dlg.transient(parent)
    dlg.resizable(False, False)
    dlg.minsize(340, 0)
    try:
        img = tk.PhotoImage(file=paths.asset("icon-256.png")).subsample(2)
        lbl = ttk.Label(dlg, image=img)
        lbl.image = img
        lbl.pack(pady=(16, 6))
    except tk.TclError:
        pass
    ttk.Label(dlg, text=paths.APP_NAME, font=("Segoe UI", 14, "bold")).pack()
    ttk.Label(dlg, text=f"Version {paths.version()}", foreground="#555555").pack()
    ttk.Label(dlg, text=CREDIT, wraplength=380, justify="center").pack(padx=20, pady=(10, 6))
    ttk.Label(dlg, text="Free software under the MIT License.\nCopyright (c) 2026 Aaron Steger",
              justify="center").pack(padx=30, pady=(0, 10))
    btns = ttk.Frame(dlg)
    btns.pack(pady=(0, 14))

    def licenses():
        folder = os.path.join(paths.program_dir(), "licenses")
        target = folder if os.path.isdir(folder) else os.path.join(paths.program_dir(), "LICENSE")
        try:
            songs_window.play(target)  # opens the folder / file in Windows
        except OSError as e:
            messagebox.showerror("About", str(e), parent=dlg)

    ttk.Button(btns, text="Licenses", command=licenses).pack(side="left", padx=4)
    ttk.Button(btns, text="Close", command=dlg.destroy).pack(side="left", padx=4)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    dlg.grab_set()
    return dlg


class App:
    def __init__(self, root):
        self.root, self.q, self.busy, self.warning = root, queue.Queue(), False, None
        root.title(paths.APP_NAME)
        set_icon(root)
        root.geometry("760x530")
        self.drop = tk.Label(root, text="Drop the service recording here\n(MKV, MP4, WAV, MP3 or M4A)",
                             relief="ridge", bd=3, height=5, font=("Segoe UI", 14), bg="#eef3fb")
        self.drop.pack(fill="x", padx=12, pady=(12, 6))
        row = ttk.Frame(root)
        row.pack(fill="x", padx=12)
        ttk.Button(row, text="Browse...", command=self.browse).pack(side="left")
        ttk.Button(row, text="About", command=lambda: about(root)).pack(side="right", padx=(6, 0))
        self.settings_btn = ttk.Button(row, text="Settings...", command=self.settings)
        self.settings_btn.pack(side="right")
        self.songs_btn = ttk.Button(row, text="Songs...", command=self.songs)
        self.songs_btn.pack(side="right", padx=6)
        ttk.Label(row, text="   Service date:").pack(side="left", padx=(0, 4))
        self.date = datepicker.DateField(row)
        self.date.pack(side="left")
        row2 = ttk.Frame(root)
        row2.pack(fill="x", padx=12, pady=(6, 0))
        ttk.Label(row2, text="Service start:").pack(side="left")
        try:
            mode = builder.load_config().get("service_start", prelude.MODES[0])
        except (OSError, ValueError):
            mode = prelude.MODES[0]
        self.mode = tk.StringVar(value=mode if mode in prelude.MODES else prelude.MODES[0])
        ttk.Combobox(row2, values=prelude.MODES, state="readonly", width=12,
                     textvariable=self.mode).pack(side="left", padx=6)
        self.start_hint = ttk.Label(row2)
        self.start_hint.pack(side="left")
        row3 = ttk.Frame(root)
        row3.pack(fill="x", padx=12, pady=(6, 0))
        self.cut_end = tk.BooleanVar(value=True)
        self.end_check = ttk.Checkbutton(row3, variable=self.cut_end)
        self.end_check.pack(side="left")
        try:
            comp = {**audio.COMPRESSION, **builder.load_config().get("compression", {})}
        except (OSError, ValueError):
            comp = audio.COMPRESSION
        self.compress = tk.BooleanVar(value=bool(comp["enabled"]))
        ttk.Checkbutton(row3, text=f"Compress the final MP3 ({comp['ratio']}:1, for radio)",
                        variable=self.compress).pack(side="left", padx=(18, 0))
        self.status = ttk.Label(root, text="Ready.")
        self.status.pack(fill="x", padx=12, pady=4)
        self.text = tk.Text(root, height=16, font=("Consolas", 9))
        self.text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        if TkinterDnD:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", lambda e: self.start(root.tk.splitlist(e.data)[0]))
        else:
            self.drop.config(text="Click Browse to pick the service file\n(drag and drop needs tkinterdnd2)")
        self.show_settings()
        root.after(100, self.poll)

    def show_settings(self, cfg=None):
        """Put the church's own words and name in the window (after setup or Settings)."""
        try:
            cfg = cfg or builder.load_config()
        except (OSError, ValueError):
            cfg = {}
        name = (cfg.get("broadcast_name") or "").strip()
        self.root.title(f"{paths.APP_NAME} - {name}" if name else paths.APP_NAME)
        start = cfg.get("start_phrase") or "Good morning"
        self.start_hint.config(text=f'Auto = cut organ before "{start}", keep choir. '
                                    "Keep start = cut nothing (bell choir).")
        end = cfg.get("end_answer_phrase") or cfg.get("end_phrase") or prelude.END_PHRASE
        self.end_check.config(text=f'End the service at "{end}"')
        mode = cfg.get("service_start", prelude.MODES[0])
        self.mode.set(mode if mode in prelude.MODES else prelude.MODES[0])

    def settings(self, first_run=False):
        """Open the setup wizard (first start) or Settings."""
        if self.busy:
            return
        try:
            cfg = builder.load_config()
        except (OSError, ValueError) as e:
            messagebox.showerror("Settings", f"Could not read config.json:\n{e}")
            return
        setup_wizard.SetupWizard(self.root, cfg, on_done=self.show_settings, first_run=first_run)

    def browse(self):
        f = filedialog.askopenfilename(filetypes=MEDIA)
        if f:
            self.start(f)

    def songs(self):
        """Open the Songs window (turn songs on/off, rename, seasons, play)."""
        if self.busy:
            return
        try:
            cfg = builder.load_config()
        except (OSError, ValueError) as e:
            messagebox.showerror("Songs", f"Could not read config.json:\n{e}")
            return
        db = cfg.get("song_silence_db", audio.EDGE_SILENCE_DB)
        songs_window.SongsWindow(self.root, builder.songs_csv(), cfg.get("song_folders", []),
                                 cfg.get("song_min_words", songs_window.catalog.MIN_WORDS),
                                 get_edges=(lambda f: audio.edge_silence(f, db))
                                 if cfg.get("trim_song_silence", True) else None,
                                 models_folder=cfg.get("models_folder", ""),
                                 on_folders=self.save_song_folders)

    def save_song_folders(self, folders):
        """Add songs put songs in a new folder: remember it in the settings."""
        try:
            cfg = builder.load_config()
            cfg["song_folders"] = list(folders)
            builder.save_config(cfg)
        except (OSError, ValueError) as e:
            messagebox.showerror("Songs", f"Could not save the song folders:\n{e}")

    def log(self, msg):
        self.q.put(("log", msg))

    def start(self, path):
        if self.busy:
            return
        date = churchyear.service_date(self.date.get(), self.date.changed, os.path.basename(path))
        if date != self.date.get():
            self.date.set_date(date)  # show the date read from the file name
        self.busy, self.warning = True, None
        self.songs_btn.state(["disabled"])
        self.settings_btn.state(["disabled"])
        self.text.delete("1.0", "end")
        self.status.config(text=f"Working on {os.path.basename(path)} ...")
        threading.Thread(target=self.work, args=(path, date, self.mode.get(), self.cut_end.get(),
                                                       self.compress.get()),
                         daemon=True).start()

    def work(self, path, date, mode, cut_end, compress):
        try:
            self.q.put(("done", builder.build(path, date=date, log=self.log, start_mode=mode,
                                                   warn=self.set_warning, cut_end=cut_end,
                                                   compress=compress)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def set_warning(self, msg):
        self.warning = msg

    def poll(self):
        while not self.q.empty():
            kind, msg = self.q.get()
            if kind == "log":
                self.text.insert("end", msg + "\n")
                self.text.see("end")
            else:
                self.busy = False
                self.songs_btn.state(["!disabled"])
                self.settings_btn.state(["!disabled"])
                self.status.config(text="Done." if kind == "done" else "Failed.")
                self.text.insert("end", ("" if kind == "done" else "ERROR: ") + msg + "\n")
                if kind == "done" and self.warning:
                    self.status.config(text="Done, but the MP3 is too long. Edit it in Audacity.")
                    messagebox.showwarning(f"{paths.APP_NAME} - too long",
                                           f"MP3 saved:\n{msg}\n\n{self.warning}")
                else:
                    (messagebox.showinfo if kind == "done" else messagebox.showerror)(
                        paths.APP_NAME, ("MP3 saved:\n" if kind == "done" else "") + msg)
        self.root.after(100, self.poll)


def _selftest():
    """--selftest: only load the speech models (base.en + small.en) and exit. No window.

    For each model it prints the on-disk state *before* loading (the smoke test asserts on this)
    and then whether it loaded:
      "model base.en: PRESENT before load"   -> "model base.en: loaded from <path>"
      "model base.en: MISSING before load"   -> "model base.en: downloaded to <path> (first run only)"
    """
    models_folder = ""
    try:
        models_folder = builder.load_config().get("models_folder", "")
    except (OSError, ValueError):
        models_folder = ""

    root = prelude._models_dir(models_folder)
    print(f"selftest: {paths.APP_NAME} version {paths.version()}")
    print(f"selftest: program dir = {paths.program_dir()}")
    print(f"selftest: data dir = {builder.data_dir()}")
    try:
        print(f"selftest: ffmpeg = {audio.find_tool('ffmpeg')}")
        print(f"selftest: ffprobe = {audio.find_tool('ffprobe')}")
    except RuntimeError as e:
        print(f"selftest: ffmpeg NOT FOUND ({e})")
    print(f"selftest: models folder = {root}")
    ok = True
    for name in (prelude.MODEL_NAME, prelude.END_MODEL_NAME):
        # Check the on-disk state BEFORE loading: this is what the smoke test asserts on.
        before = prelude._model_ready(root, name)
        print(f"selftest: model {name}: {'PRESENT' if before else 'MISSING'} before load")
        try:
            prelude._get_model(models_folder, name)
            # Now it loaded. Report the true outcome (the before-check already proved
            # whether it had to download). For "loaded from" print the real model
            # directory (_model_path found it, e.g. the faster-whisper snapshot folder),
            # not a guessed <root>/<name> that may not exist.
            if before:
                real = prelude._model_path(root, name)
                print(f"selftest: model {name}: loaded from {real if real else root}")
            else:
                print(f"selftest: model {name}: downloaded to {root} (first run only)")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"selftest: model {name}: FAILED to load ({e})")
    print("selftest: OK" if ok else "selftest: FAILED")
    sys.exit(0 if ok else 1)


def main():
    builder.ensure_user_files()
    if "--selftest" in sys.argv:
        _selftest()
        return
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    app = App(root)
    try:
        first_run = not builder.load_config().get("setup_done")
    except (OSError, ValueError):
        first_run = True
    args = [a for a in sys.argv[1:] if a != "--selftest"]
    if first_run:
        root.after(200, lambda: app.settings(first_run=True))
    elif args:  # file dropped on the program icon
        root.after(300, lambda: app.start(args[0]))
    root.mainloop()


if __name__ == "__main__":
    main()
