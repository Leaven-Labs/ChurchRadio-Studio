"""Makes the pictures of the app that the README shows (docs/screenshots), with made-up data.

    python tools/screenshots.py

No recording, models or internet are needed: the windows are made off screen, as --uitest does,
and filled with an example church's settings, songs and history. Every picture is made in the
light and in the dark look (name.png, name-dark.png). Run it again after the look of
the app changes.
"""
import csv
import datetime as dt
import json
import math
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "screenshots")
DATA = os.path.join(OUT, "_data")
RADIO = os.path.join(DATA, "Radio")  # made-up files (the History page looks whether an MP3 is there)
SHOWN = "/home/stjohn/Radio"  # the folder the pictures name
os.makedirs(os.path.join(RADIO, "Broadcasts"), exist_ok=True)
os.environ["CHURCHRADIO_DATA_DIR"] = os.path.join(DATA, "settings")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")  # sharp pictures
sys.path.insert(0, ROOT)

SONGS = (  # title, seasons, seconds, on, public domain, note
    ("A Mighty Fortress Is Our God", "", 228, "yes", "yes", "Published 1529."),
    ("Abide with Me", "", 254, "yes", "yes", "Published 1847."),
    ("All Glory, Laud and Honor", "holyweek", 197, "yes", "yes", "Published 1851."),
    ("Amazing Grace", "", 262, "yes", "yes", "Published 1779."),
    ("America the Beautiful", "patriotic", 201, "yes", "yes", "Published 1910."),
    ("Beautiful Savior", "", 187, "yes", "yes", "Published 1873."),
    ("Christ the Lord Is Risen Today", "easter", 176, "yes", "yes", "Published 1739."),
    ("Come, Thou Long-Expected Jesus", "advent", 164, "yes", "yes", "Published 1744."),
    ("Great Is Thy Faithfulness", "", 243, "yes", "yes", "Published 1923."),
    ("Holy, Holy, Holy", "", 215, "yes", "yes", "Published 1826."),
    ("How Great Thou Art", "", 276, "yes", "check", "The original is from 1885, the English version from 1949."),
    ("In Christ Alone", "", 268, "yes", "no", "Published 2001."),
    ("Joy to the World", "christmas", 142, "yes", "yes", "Published 1719."),
    ("Now Thank We All Our God", "", 171, "yes", "yes", "Published 1636."),
    ("O Come, O Come, Emmanuel", "advent", 233, "yes", "yes", "Published 1851."),
    ("O Sacred Head, Now Wounded", "lent;holyweek", 249, "yes", "yes", "Published 1656."),
    ("Prelude in G (organ)", "", 312, "no", "", ""),
    ("Silent Night", "christmas", 203, "yes", "yes", "Published 1818."),
    ("Spirit of God, Descend upon My Heart", "pentecost", 221, "yes", "yes", "Published 1854."),
    ("What a Friend We Have in Jesus", "", 192, "yes", "yes", "Published 1855."),
)


def example_data():
    """An example church's settings, song list and history."""
    import builder
    import catalog
    songs = SHOWN + "/Songs"
    cfg = builder.load_config()
    cfg.update(setup_done=True, broadcast_name="St. John Radio", theme="light", song_folders=[songs],
               intro=SHOWN + "/Intro.mp3", output_folder=SHOWN + "/Broadcasts")
    builder.save_config(cfg)
    files = {}
    with open(builder.songs_csv(), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=catalog.FIELDS)
        w.writeheader()
        for title, seasons, sec, on, pd, note in SONGS:
            files[title] = songs + "/" + title + ".mp3"
            w.writerow({"file": files[title], "title": title, "duration": sec, "seasons": seasons, "enabled": on,
                        "words": "0" if on == "no" else "64", "start_silence": "0.4", "end_silence": "1.2",
                        "public_domain": pd, "pd_note": note,
                        "permission": "CCLI Streaming License 123456" if pd == "no" else ""})
    history = []
    weeks = (("2026-10-18", ("Holy, Holy, Holy", "Abide with Me")),
             ("2026-10-25", ("A Mighty Fortress Is Our God", "Now Thank We All Our God", "Beautiful Savior")),
             ("2026-11-01", ("Amazing Grace", "Great Is Thy Faithfulness")),
             ("2026-11-08", ("America the Beautiful", "What a Friend We Have in Jesus", "In Christ Alone")),
             ("2026-11-15", ("Beautiful Savior", "Holy, Holy, Holy")))
    for day, titles in weeks:
        out = os.path.join(RADIO, "Broadcasts", f"St. John Radio {day}.mp3")
        open(out, "wb").close()
        history.append({"date": day, "output": out, "songs": [files[t] for t in titles]})
    with open(os.path.join(os.environ["CHURCHRADIO_DATA_DIR"], "history.json"), "w", encoding="utf-8") as fh:
        json.dump(history, fh)
    return history[-1]["output"]


def loudness(length, start, end, per_second):
    """A made-up recording: an organ prelude, the service (speech and hymns), then talk and organ."""
    rnd = random.Random(7)
    hymns = [(start + a, start + a + 200) for a in (420, 1500, 2700, 3300)]
    out = []
    for i in range(int(length * per_second)):
        t = i / per_second
        if t < start - 25 or t > end + 40:  # organ
            v = 0.55 + 0.25 * math.sin(t / 9) * math.sin(t / 2.3) + rnd.uniform(-0.08, 0.08)
        elif t < start - 1 or t > end + 1:  # people finding their seats, talk after the service
            v = rnd.uniform(0.02, 0.12)
        elif any(a <= t < b for a, b in hymns):
            v = 0.6 + 0.2 * math.sin(t / 5) + rnd.uniform(-0.1, 0.1)
        else:  # speech: words and the pauses between them
            v = (0.45 + 0.3 * rnd.random()) if math.sin(t * 2.1) + math.sin(t * 0.63) > -0.7 else rnd.uniform(0, 0.06)
        out.append(max(0.0, min(1.0, v)))
    return out


def main():
    import builder
    import mainwindow
    import paths
    import ui

    mp3 = example_data()
    paths.version = lambda: "1.3.1"  # (from the source code it says "development")
    app = ui.start_app(["screenshots"], "light")
    for theme in ("light", "dark"):  # every picture twice: name.png and name-dark.png
        cfg = builder.load_config()
        cfg["theme"] = theme  # (so the Settings page shows it too)
        builder.save_config(cfg)
        window = mainwindow.MainWindow()
        ui.apply_theme(app, theme)
        pictures(app, window, mp3, "" if theme == "light" else "-dark")
        window.close()
    shutil.rmtree(DATA, ignore_errors=True)  # the made-up settings and files


def pictures(app, window, mp3, ending):
    import builder
    import setup_wizard
    from PySide6.QtCore import QRect

    def save(widget, name, crop=None):
        for _ in range(5):
            app.processEvents()
        picture = widget.grab(crop) if crop else widget.grab()
        picture.save(os.path.join(OUT, name + ending + ".png"))
        print(name + ending, picture.width(), "x", picture.height())

    window.resize(1180, 1010)
    window.show()
    length, start, end, per = 4440.0, 542.3, 4095.6, 20
    detail = loudness(length, start, end, per)
    step = len(detail) // 600
    window.drop.set_file(SHOWN + "/Recordings/2026-11-15 10-28-41.mkv", length)
    window.job = {"path": window.drop.path, "made": True}
    window.wave_card.show()
    window.wave.set_levels([min(1.0, 1.25 * sum(detail[i * step:(i + 1) * step]) / step) for i in range(600)], detail, per)
    window.wave.set_length(length)
    window.told("start", start)
    window.told("end", end)
    window.told("silence", 41.5)
    window.told("hour", {"intro": 32.0, "service": 3164.0, "target": 3600,
                         "songs": [("Beautiful Savior", 187.0), ("Holy, Holy, Holy", 215.0)]})
    for row in window.steps.values():
        row.set("done")
    window.status.setText("Done.")
    window.show_cut_controls(make=False)
    window.result.show_result(SHOWN + "/Broadcasts/" + os.path.basename(mp3), 3598.0)
    save(window, "broadcast")
    card = window.wave_card
    save(window, "cuts", QRect(card.mapTo(window, card.rect().topLeft()), card.size()).adjusted(-12, -12, 12, 12))

    window.resize(1180, 850)
    window.show_page("songs", models=False)
    window.songs_page.table.selectRow(10)
    window.songs_page.table.scrollToTop()
    save(window, "songs")
    window.resize(1180, 600)
    window.show_page("history", models=False)
    window.history_page.table.selectRow(0)
    save(window, "history")
    window.resize(1180, 760)
    window.show_page("settings", models=False)
    save(window, "settings")

    wizard = setup_wizard.SetupWizard(window, builder.load_config(), first_run=True)
    wizard.show()
    wizard.form.go(wizard.form.pages.index(wizard.form.page_service))
    save(wizard, "wizard")
    wizard.done(0)


if __name__ == "__main__":
    main()
