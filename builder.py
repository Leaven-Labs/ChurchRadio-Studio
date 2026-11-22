"""Build one broadcast: intro + the service (prelude, end and long silences cut) + songs that fill the time = one MP3."""
import csv
import datetime as dt
import json
import os
import re
import sys
import tempfile

import audio
import catalog
import paths
import churchyear
import picker
import prelude

DEFAULT_NAME = "Church Radio"  # used in the MP3 name until the setup wizard sets broadcast_name


def data_dir():
    """The user's folder (settings, song catalog, history). See paths.py."""
    return paths.data_dir()


def bundled_dir():
    return paths.bundled_dir()


def copy_out_default(name, overwrite=False):
    """Copy a bundled default file into the user's folder if it is not there yet.

    Never replaces a file the user already has (unless overwrite). Returns the destination
    path when it copied the file, or "" when there was nothing to copy or the user's file was kept."""
    src = os.path.join(bundled_dir(), name)
    dst = os.path.join(data_dir(), name)
    if not os.path.exists(src) or src == dst:
        return ""
    if os.path.exists(dst) and not overwrite:
        return ""  # keep the user's edited copy
    with open(src, "rb") as fh:
        data = fh.read()
    with open(dst, "wb") as fh:
        fh.write(data)
    return dst


def ensure_user_files(log=print):
    """First run: put an editable config.json / song catalog in the user's folder. Never overwrites."""
    for name in ("config.json", "songs.csv"):
        dst = copy_out_default(name)
        if dst:
            log(f"Created {dst} (edit it there).")


def load_config():
    ensure_user_files()
    with open(os.path.join(data_dir(), "config.json"), encoding="utf-8") as fh:
        return json.load(fh)


def save_config(cfg):
    """Write the user's config.json (the setup wizard and Settings use this)."""
    path = os.path.join(data_dir(), "config.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)  # never a half-written config


# How the service date is written in the MP3's file name and title (date_format in config.json),
# as the Settings page offers them: short ones (numbers only) and long ones (the month as a word).
# In a format: YYYY 2026, YY 26, MMMM November, MMM Nov, MM 11, M 11 (no zero before it),
# DD 05, D 5, dddd Sunday, ddd Sun. Everything else is written as it is.
DATE_FORMAT = "YYYY-MM-DD"
DATE_FORMATS = (("Short", ("YYYY-MM-DD", "MM-DD-YYYY", "DD-MM-YYYY", "MM.DD.YYYY", "DD.MM.YYYY", "YYYY.MM.DD",
                           "MM-DD-YY", "YYYYMMDD")),
                ("Long", ("MMMM D, YYYY", "D MMMM YYYY", "dddd, MMMM D, YYYY", "dddd D MMMM YYYY",
                          "MMM D, YYYY", "D MMM YYYY", "ddd, MMM D, YYYY")))
EXAMPLE_DATE = dt.date(2026, 11, 15)  # the date the formats are shown with (day and month can't be mixed up)
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
NOT_IN_FILE_NAMES = '\\/:*?"<>|'


def format_date(date, fmt=DATE_FORMAT):
    """The date written as the format says: format_date(d, "MMM D, YYYY") -> "Nov 15, 2026"."""
    parts = {"YYYY": f"{date.year:04d}", "YY": f"{date.year % 100:02d}", "MMMM": MONTHS[date.month - 1],
             "MMM": MONTHS[date.month - 1][:3], "MM": f"{date.month:02d}", "M": str(date.month),
             "DD": f"{date.day:02d}", "D": str(date.day), "dddd": WEEKDAYS[date.weekday()],
             "ddd": WEEKDAYS[date.weekday()][:3]}
    return re.sub("YYYY|YY|MMMM|MMM|MM|M|DD|D|dddd|ddd", lambda m: parts[m.group()], fmt)


def date_format(cfg):
    """The date format of the settings; the usual one if none is set or it holds no date."""
    fmt = str(cfg.get("date_format") or "").strip()
    return fmt if fmt and format_date(EXAMPLE_DATE, fmt) != fmt else DATE_FORMAT


def date_style(fmt):
    """ "Short" or "Long": the group of DATE_FORMATS a format is in (one typed in config.json: by its month)."""
    return next((style for style, formats in DATE_FORMATS if fmt in formats), "Long" if "MMM" in fmt else "Short")


def output_title(cfg, date):
    """The MP3's title, for example "Church Radio Broadcast 2026-11-15"."""
    name = (cfg.get("broadcast_name") or DEFAULT_NAME).strip()
    return f"{name} Broadcast {format_date(date, date_format(cfg))}"


def output_name(cfg, date):
    """The MP3 file name, for example "Church Radio 2026-11-15.mp3". Signs that a file name
    cannot hold (a format typed in config.json, such as MM/DD/YYYY) become "-"."""
    name = (cfg.get("broadcast_name") or DEFAULT_NAME).strip()
    day = "".join("-" if ch in NOT_IN_FILE_NAMES else ch for ch in format_date(date, date_format(cfg)))
    return f"{name} {day}.mp3"


def songs_csv():
    return os.path.join(data_dir(), "songs.csv")


# Even loudness (see audio.LOUDNESS_REFERENCE): the target the whole MP3 is brought to, in LUFS
# (loudness_lufs in config.json; null = not evened out, as before 1.6.0).
LOUDNESS_LUFS = -16


def loudness_target(cfg):
    """The loudness the MP3 is brought to (LUFS), or None when it is not evened out."""
    value = cfg.get("loudness_lufs", LOUDNESS_LUFS)
    if value is None or value is False:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return LOUDNESS_LUFS
    return value if -40 <= value <= -5 else LOUDNESS_LUFS


# The cue sheet: a CSV next to the MP3 that lists what plays when (cue_sheet in config.json), for
# the station and for license reports. utf-8-sig, like songs.csv, so Excel shows it correctly.
CUE_FIELDS = ["Starts at", "Ends at", "Length", "Part", "Title", "File", "May broadcast", "Permission", "Note"]


def cue_time(sec):
    """A time in the cue sheet: 0:00:00 (hours, minutes, seconds)."""
    sec = int(round(max(0.0, sec)))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}"


def cue_sheet_path(mp3):
    """Where the cue sheet of this MP3 is saved: beside it, "<name> cue sheet.csv"."""
    return os.path.splitext(mp3)[0] + " cue sheet.csv"


def cue_rows(intro, intro_len, service, svc_len, chosen, rows):
    """The lines of the cue sheet: the intro, the service and each song, with their times in the MP3.
    chosen: the songs as catalog.songs_for gives them; rows: the song list (for title and permission)."""
    lines, t = [], 0.0

    def add(part, length, title, path, row=None):
        nonlocal t
        row = row or {}
        lines.append({"Starts at": cue_time(t), "Ends at": cue_time(t + length), "Length": cue_time(length),
                      "Part": part, "Title": title, "File": os.path.basename(path),
                      "May broadcast": (catalog.broadcast_label(row) or "Not looked up") if part == "Song" else "",
                      "Permission": (row.get("permission") or "").strip(),
                      "Note": (row.get("pd_note") or "").strip()})
        t += length

    if intro:
        add("Intro", intro_len, "Intro", intro)
    add("Service", svc_len, "The service", service)
    for song in chosen:
        row = rows.get(song["path"], {})
        title = song.get("title") or row.get("title") or os.path.splitext(os.path.basename(song["path"]))[0]
        add("Song", song["duration"], title, song["path"], row)
    return lines


def write_cue_sheet(path, lines):
    """Save the cue sheet (never half written: under another name first)."""
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=CUE_FIELDS)
        w.writeheader()
        w.writerows(lines)
    os.replace(tmp, path)


def _loudness_cache_path():
    return os.path.join(data_dir(), "loudness.json")


def _loudness_key(path, start, end):
    st = os.stat(path)
    return f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}|{start or 0:.2f}|" \
           + ("" if end is None else f"{end:.2f}")


def part_loudness(parts, log=print, keep=None):
    """The loudness (LUFS, None = silent) of each part, (path, start, end) or a path. A part whose
    path is in keep (the intro and the songs) is measured once and remembered in loudness.json."""
    keep = set(keep or [])
    try:
        with open(_loudness_cache_path(), encoding="utf-8") as fh:
            cache = json.load(fh)
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError):
        cache = {}
    found, changed = [], False
    for part in parts:
        path, start, end = (part, 0.0, None) if isinstance(part, str) else part
        key = _loudness_key(path, start, end) if path in keep else None
        if key and key in cache:
            found.append(cache[key])
            continue
        value = audio.loudness(path, start, end)
        found.append(value)
        if key:
            cache[key] = value
            changed = True
    if changed:
        # Forget files that are gone, so the list does not grow for ever.
        cache = {k: v for k, v in cache.items() if os.path.exists(k.split("|")[0])}
        tmp = _loudness_cache_path() + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(cache, fh, indent=0)
            os.replace(tmp, _loudness_cache_path())
        except OSError as e:
            log(f"Could not remember the loudness of the songs ({e}); they are measured again next time.")
    return found


def _history_path():
    return os.path.join(data_dir(), "history.json")


def load_history():
    """The broadcasts made so far, oldest first: [{"date", "output", "songs"}, ...]."""
    try:
        with open(_history_path(), encoding="utf-8") as fh:
            hist = json.load(fh)
    except (OSError, ValueError):
        return []
    return [e for e in hist if isinstance(e, dict)] if isinstance(hist, list) else []


def recent_songs(weeks, not_output=None):
    """The songs of the last broadcasts. not_output: leave out the broadcast saved there (it is
    being made again: its own songs may be chosen again)."""
    hist = [e for e in load_history() if not not_output or e.get("output") != not_output]
    hist = hist[-weeks:] if weeks > 0 else []
    return {s for entry in hist for s in entry.get("songs", [])}


def save_history(date, songs, output):
    hist = [e for e in load_history() if e.get("output") != output]  # made again: one line, not two
    hist.append({"date": date.isoformat(), "output": output, "songs": songs})
    with open(_history_path(), "w", encoding="utf-8") as fh:
        json.dump(hist[-52:], fh, indent=1)


# Cuts remembered per recording (cuts.json in the user's folder): choosing the same recording again
# does not listen again. A recording is known by its name, size and the time it was saved, so a
# recording that is replaced (or copied again) is new. Cuts the person moved are always used; cuts
# the app found are used only while the Start mode, the end cut and the service-words settings are
# the same as when they were found. Entries older than CUTS_KEEP_DAYS go.
CUTS_KEEP_DAYS = 120


def _cuts_path():
    return os.path.join(data_dir(), "cuts.json")


def recording_key(path):
    st = os.stat(path)
    return f"{os.path.basename(path)}|{st.st_size}|{int(st.st_mtime)}"


def cut_settings(cfg, mode, cut_end):
    """What the app's own cuts depend on: the Start mode, the end cut, and the settings of the words
    it listens for (start_* and end_* in config.json)."""
    mode = mode or cfg.get("service_start", "Auto")
    words = {k: v for k, v in cfg.items() if k.startswith(("start_", "end_"))}
    return json.dumps([mode, bool(cut_end), words], sort_keys=True, default=str)


def _load_cuts():
    try:
        with open(_cuts_path(), encoding="utf-8") as fh:
            saved = json.load(fh)
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def remember_cuts(path, start, end, by, settings=None, today=None):
    """Remember the cuts of a recording. by: "app" (found by listening; settings: cut_settings) or
    "hand" (moved by the person). Returns False if they could not be saved (only not remembered)."""
    today = today or dt.date.today()
    try:
        key = recording_key(path)
    except OSError:
        return False
    saved = _load_cuts()
    oldest = (today - dt.timedelta(days=CUTS_KEEP_DAYS)).isoformat()
    saved = {k: v for k, v in saved.items() if isinstance(v, dict) and str(v.get("saved", "")) >= oldest}
    saved[key] = {"start": float(start or 0.0), "end": None if end is None else float(end), "by": by,
                  "settings": settings if by == "app" else None, "saved": today.isoformat()}
    tmp = _cuts_path() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(saved, fh, indent=1)
        os.replace(tmp, _cuts_path())
    except OSError:
        return False
    return True


def remembered_cuts(path, settings):
    """The cuts remembered for this recording that may be used, or None:
    {"start", "end", "by" ("app" or "hand"), "saved" (YYYY-MM-DD)}."""
    try:
        entry = _load_cuts().get(recording_key(path))
    except OSError:
        return None
    if not isinstance(entry, dict) or entry.get("by") not in ("app", "hand"):
        return None
    if entry["by"] == "app" and entry.get("settings") != settings:
        return None  # found with other settings: listen again
    try:
        start = float(entry.get("start") or 0.0)
        end = None if entry.get("end") is None else float(entry["end"])
    except (TypeError, ValueError):
        return None
    return {"start": start, "end": end, "by": entry["by"], "saved": str(entry.get("saved", ""))}


def remembered_text(found):
    """What the log and the window say about remembered cuts."""
    try:
        day = dt.date.fromisoformat(found["saved"]).strftime("%m/%d/%Y")
    except ValueError:
        day = "before"
    how = "moved by hand" if found["by"] == "hand" else "found by listening"
    return f"Cuts from last time ({how}, {day})"


def find_service_start(service, cfg, mode, log=print):
    """Seconds to skip at the start of the service (the organ prelude)."""
    phrase = cfg.get("start_phrase", "Good morning").strip()
    if mode == "Keep start" or not phrase:
        log("Service start: nothing cut at the start.")
        return 0.0
    log(f'Searching for "{phrase}" in the first {prelude.SEARCH_MINUTES} min (takes about 30 s) ...')
    found, start, note = prelude.find_start(
        service, phrase, mode, models_folder=cfg.get("models_folder", ""), log=log,
        min_sure=cfg.get("start_min_sure", prelude.START_MIN_SURE),
        skip_sec=cfg.get("start_skip_minutes", prelude.START_SKIP_SEC / 60) * 60)
    if found is None:
        log(f'"{phrase}" not found. Nothing cut at the start.')
        return 0.0
    log(f'Found "{phrase}" at {audio.fmt(found)}. {note} Cutting everything before {audio.fmt(start)}.')
    return start


def find_service_end(service, cfg, start, log=print):
    """Where the service ends: after the congregation's answer to "Go now in peace".

    Cut right after "Thanks be to God" if it is heard shortly after the dismissal; if not, after
    "and we will", else a few seconds after "Go now in peace". If "Go now in peace" is not heard, the old "Thanks be to God"
    rule is the fallback (and the log says so).
    """
    total = audio.duration(service)
    phrase = cfg.get("end_phrase", prelude.END_PHRASE).strip()
    if not phrase:
        log("Service end: nothing cut at the end.")
        return None
    minutes = cfg.get("end_search_minutes", prelude.END_SEARCH_MINUTES)
    log(f'Searching for "{phrase}" in the last {minutes} min (takes 1 to 3 min) ...')
    words_file = os.path.join(data_dir(), "end_words.txt")
    found, end, note = prelude.find_end(service, total, phrase, after=start, search_minutes=minutes,
                                        models_folder=cfg.get("models_folder", ""), words_file=words_file,
                                        end_after=cfg.get("end_after_seconds", prelude.END_AFTER_SEC),
                                        alt_phrase=cfg.get("end_alt_phrase", prelude.END_ALT_PHRASE),
                                        alt_window=cfg.get("end_alt_window", prelude.END_ALT_WINDOW),
                                        alt_pad=cfg.get("end_alt_pad", prelude.END_ALT_PAD),
                                        answer_phrase=cfg.get("end_answer_phrase", prelude.END_ANSWER_PHRASE),
                                        answer_window=cfg.get("end_answer_window", prelude.END_ANSWER_WINDOW),
                                        answer_pad=cfg.get("end_answer_pad", prelude.END_ANSWER_PAD),
                                        log=log)
    if found is None:
        why = note or f'"{phrase}" and "{prelude.END_PHRASE_FALLBACK}" not found'
        log(f"{why}. Nothing cut at the end. The words heard are in {words_file}")
        return None
    log(f'"{phrase}": {note}, ending at {audio.fmt(found)}. Cutting everything after {audio.fmt(end)} '
        f"({audio.fmt(total - end)} removed).")
    return end


def find_cuts(service, cfg=None, start_mode=None, cut_end=True, log=print, tell=None):
    """Listen for where the service starts and ends. Returns (start, end): seconds into the
    recording; end None = nothing is cut at the end. tell: as in build."""
    tell = tell or (lambda what, value: None)
    cfg = cfg or load_config()
    start = find_service_start(service, cfg, start_mode or cfg.get("service_start", "Auto"), log)
    tell("start", start)
    end = find_service_end(service, cfg, start, log) if cut_end else None
    if not cut_end:
        log("Service end: nothing cut at the end.")
    tell("end", end)
    remember_cuts(service, start, end, "app", cut_settings(cfg, start_mode, cut_end))
    return start, end


def overlong_warning(intro_len, svc_len, target=3600, tol=30):
    """Warning text when intro + service is longer than target + tol, else None."""
    over = intro_len + svc_len - target
    if over <= tol:
        return None
    msg = (f"Intro + service is {audio.fmt(intro_len + svc_len)}, which is {audio.fmt(over)} "
           f"longer than {target // 60} min. No songs were added.")
    if svc_len > target:
        msg += f" The service alone is {audio.fmt(svc_len)}, more than {target // 60} min."
    return msg + (" Please open the MP3 in Audacity and cut it to length by hand "
                  "(for example a hymn verse, the prelude, or the postlude).")


def build(service, cfg=None, date=None, log=print, start_mode=None, warn=None, cut_end=True,
          compress=True, tell=None, cuts=None, listen_again=False):
    """Make the broadcast MP3. Returns the output path.

    warn(msg) is called when the result needs a manual edit (too long).
    cut_end: cut everything after the congregation's "Thanks be to God" (see find_service_end).
    compress: put the broadcast compressor on the final MP3.
    cuts: (start, end) in seconds into the recording, set by the person in the window (end None =
    nothing cut at the end). The app then does not listen for the start and end itself
    (start_mode and cut_end are not used). With cuts None, the cuts remembered for this recording
    are used (see remembered_cuts), unless listen_again.
    tell(what, value) is called with the numbers the window shows as they become known:
    "start" and "end" (the cuts, seconds into the recording; end None = nothing cut), "silence"
    (seconds of long silences cut), "remembered" (the cuts remembered from last time are used:
    a dict, see remembered_cuts), "hour" (a dict: the lengths of the intro and the service,
    the songs as (title, seconds), and the target) and "mp3" (how much of the MP3 is written, 0 to 1).
    """
    tell = tell or (lambda what, value: None)
    cfg = cfg or load_config()
    intro = (cfg.get("intro") or "").strip()
    if intro and not os.path.exists(intro):
        raise RuntimeError(f"Intro file not found: {intro}\nChoose it again in Settings.")
    date = date or churchyear.date_from_filename(os.path.basename(service)) or dt.date.today()
    season = churchyear.season(date)
    log(f"Service date {date:%m/%d/%Y}: season of {season.title()}")
    holiday = churchyear.patriotic_holiday(date, cfg.get("patriotic_holidays", churchyear.HOLIDAYS))
    if holiday:
        log(f"{holiday.title()} weekend: patriotic songs are used first")

    target = cfg.get("target_minutes", 60) * 60
    tol = cfg.get("tolerance_seconds", 30)
    out_dir = cfg.get("output_folder") or os.path.dirname(os.path.abspath(service))
    out = os.path.join(out_dir, output_name(cfg, date))

    with tempfile.TemporaryDirectory(prefix="churchradio_") as tmp:
        found = None if cuts is not None or listen_again else \
            remembered_cuts(service, cut_settings(cfg, start_mode, cut_end))
        if found:
            start, end = found["start"], found["end"]
            log(f"{remembered_text(found)}: the service starts at {audio.fmt(start)} and ends at "
                + (audio.fmt(end) if end is not None else "the end of the recording")
                + ". (Not listened to again.)")
            tell("remembered", found)
            tell("start", start)
            tell("end", end)
        elif cuts is None:
            start, end = find_cuts(service, cfg, start_mode, cut_end, log, tell)
        else:
            start, end = max(0.0, float(cuts[0] or 0.0)), cuts[1]
            if end is not None and end <= start:
                raise RuntimeError("The end cut is before the start cut.")
            log(f"Cuts set by hand: the service starts at {audio.fmt(start)} and ends at "
                + (audio.fmt(end) if end is not None else "the end of the recording") + ".")
            tell("start", start)
            tell("end", end)
        log("Cutting long silences from the service ...")
        svc = os.path.join(tmp, "service.wav")
        svc_len = audio.trim_service(service, svc, cfg.get("max_silence_seconds", 5),
                                     cfg.get("silence_level_db", -40), log, start, end)
        if end is not None:  # (with no end cut the uncut length is not known here)
            tell("silence", max(0.0, end - start - svc_len))
        trim = cfg.get("trim_song_silence", True)
        silence_db = cfg.get("song_silence_db", audio.EDGE_SILENCE_DB)
        svc_end = svc_len
        if trim:  # no silence between the end of the service and the first song
            tail = audio.edge_silence(svc, silence_db)[1]
            if tail > 0:
                svc_end = svc_len - tail
                log(f"Silence at the end of the service: {tail:.1f} s cut")
        svc_len = svc_end
        intro_len = audio.duration(intro) if intro else 0.0
        need = target - intro_len - svc_len
        log(f"Intro {audio.fmt(intro_len)} + service {audio.fmt(svc_len)}; "
            f"songs needed: {audio.fmt(max(need, 0))}")

        chosen, rows = [], {}
        if need > tol:
            log("Reading song catalog ...")
            if not cfg.get("song_folders"):
                log("No song folders are set (Settings): no songs added.")
            rows = catalog.update(songs_csv(), cfg.get("song_folders") or [], audio.duration, log,
                                  get_edges=(lambda f: audio.edge_silence(f, silence_db)) if trim else None)
            if cfg.get("check_song_words", True):
                catalog.check_words(
                    songs_csv(), rows,
                    lambda f, d: prelude.count_words(f, d, cfg.get("models_folder", ""), log=log),
                    cfg.get("song_min_words", catalog.MIN_WORDS), log)
            pool = catalog.songs_for(rows, season, patriotic=bool(holiday), trim=trim)
            seasonal = sum(s["seasonal"] for s in pool)
            label = season.title() + (" / patriotic" if holiday else "")
            log(f"{len(pool)} songs allowed ({seasonal} for {label}, "
                f"{len(pool) - seasonal} general)")
            chosen, total = picker.pick_songs(pool, need, tol,
                                              recent=recent_songs(cfg.get("avoid_repeat_weeks", 4), not_output=out))
            for s in chosen:
                folder = os.path.basename(os.path.dirname(s["path"]))
                title = f" - {s['title']}" if s.get("title") else ""
                log(f"  + {folder}\\{os.path.basename(s['path'])}{title} ({audio.fmt(s['duration'])})")
            if abs(total - need) > tol:
                log(f"WARNING: best fit is {abs(total - need):.0f} s from the target.")
        else:
            msg = overlong_warning(intro_len, svc_len, target, tol)
            if msg:
                log("WARNING: " + msg)
                if warn:
                    warn(msg)

        tell("hour", {"intro": intro_len, "service": svc_len, "target": target,
                      "songs": [(s.get("title") or os.path.splitext(os.path.basename(s["path"]))[0],
                                 s["duration"]) for s in chosen]})
        comp = {**audio.COMPRESSION, **cfg.get("compression", {})}
        comp["enabled"] = comp["enabled"] and compress
        parts = ([intro] if intro else []) + [(svc, 0.0, svc_end)] + \
            [(s["path"], s["start"], s["end"]) for s in chosen]
        whole = intro_len + svc_end + sum(s["duration"] for s in chosen)
        lufs = loudness_target(cfg)
        gains = final_db = None
        share = 0.0  # how much of the progress bar the loudness takes (the rest: writing the MP3)
        if lufs is not None:
            share = 0.3
            log(f"Evening out the loudness (to {lufs:g} LUFS) ...")
            levels = part_loudness(parts, log, keep=([intro] if intro else []) + [s["path"] for s in chosen])
            gains = [audio.level_gain(v) for v in levels]
            names = (["Intro"] if intro else []) + ["Service"] + \
                [s.get("title") or os.path.splitext(os.path.basename(s["path"]))[0] for s in chosen]
            for name, v, g in zip(names, levels, gains):
                log(f"  {name}: " + ("silent, left as it is" if v is None else f"{v:.1f} LUFS, {g:+.1f} dB"))
            joined = audio.measure_joined(
                parts, gains, comp,
                progress=(lambda sec: tell("mp3", share * min(1.0, sec / whole))) if whole > 0 else None)
            final_db = 0.0 if joined is None else round(min(audio.MAX_BOOST_DB, lufs - joined), 2)
            log(f"  The whole broadcast: {final_db:+.1f} dB to reach {lufs:g} LUFS")
        if comp["enabled"]:
            log(f"Writing MP3 with compression {comp['ratio']}:1 above {comp['threshold_db']} dB, "
                f"limit {comp['limit_db']} dB ...")
        else:
            log("Writing MP3 (no compression) ...")
        length = audio.join_to_mp3(
            parts, out, cfg.get("mp3_bitrate", "192k"), {"title": output_title(cfg, date)}, comp,
            progress=(lambda sec: tell("mp3", share + (1 - share) * min(1.0, sec / whole))) if whole > 0 else None,
            gains=gains, final_db=final_db)
        if cfg.get("cue_sheet", True):
            cue = cue_sheet_path(out)
            try:
                write_cue_sheet(cue, cue_rows(intro, intro_len, service, svc_end, chosen, rows))
                log(f"Cue sheet: {cue}")
            except OSError as e:  # (open in Excel, say): the broadcast itself is made
                log(f"WARNING: could not save the cue sheet {cue}: {e}")
    save_history(date, [s["path"] for s in chosen], out)
    log(f"Done: {out} ({audio.fmt(length)})")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python builder.py <service file> [YYYY-MM-DD]")
    d = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    build(sys.argv[1], date=d)
