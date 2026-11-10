"""Build one broadcast: intro + the service (prelude, end and long silences cut) + songs that fill the time = one MP3."""
import datetime as dt
import json
import os
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


def output_name(cfg, date):
    """The MP3 file name, for example "Church Radio 2026-11-15.mp3"."""
    name = (cfg.get("broadcast_name") or DEFAULT_NAME).strip()
    return f"{name} {date:%Y-%m-%d}.mp3"


def songs_csv():
    return os.path.join(data_dir(), "songs.csv")


def _history_path():
    return os.path.join(data_dir(), "history.json")


def recent_songs(weeks):
    try:
        with open(_history_path(), encoding="utf-8") as fh:
            hist = json.load(fh)
    except (OSError, ValueError):
        return set()
    hist = hist[-weeks:] if weeks > 0 else []
    return {s for entry in hist for s in entry.get("songs", [])}


def save_history(date, songs, output):
    try:
        with open(_history_path(), encoding="utf-8") as fh:
            hist = json.load(fh)
    except (OSError, ValueError):
        hist = []
    hist.append({"date": date.isoformat(), "output": output, "songs": songs})
    with open(_history_path(), "w", encoding="utf-8") as fh:
        json.dump(hist[-52:], fh, indent=1)


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
          compress=True):
    """Make the broadcast MP3. Returns the output path.

    warn(msg) is called when the result needs a manual edit (too long).
    cut_end: cut everything after the congregation's "Thanks be to God" (see find_service_end).
    compress: put the broadcast compressor on the final MP3.
    """
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
        start = find_service_start(service, cfg, start_mode or cfg.get("service_start", "Auto"), log)
        end = find_service_end(service, cfg, start, log) if cut_end else None
        if not cut_end:
            log("Service end: nothing cut at the end.")
        log("Cutting long silences from the service ...")
        svc = os.path.join(tmp, "service.wav")
        svc_len = audio.trim_service(service, svc, cfg.get("max_silence_seconds", 5),
                                     cfg.get("silence_level_db", -40), log, start, end)
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

        chosen = []
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
                                              recent=recent_songs(cfg.get("avoid_repeat_weeks", 4)))
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

        comp = {**audio.COMPRESSION, **cfg.get("compression", {})}
        comp["enabled"] = comp["enabled"] and compress
        if comp["enabled"]:
            log(f"Writing MP3 with compression {comp['ratio']}:1 above {comp['threshold_db']} dB, "
                f"limit {comp['limit_db']} dB ...")
        else:
            log("Writing MP3 (no compression) ...")
        parts = ([intro] if intro else []) + [(svc, 0.0, svc_end)] + \
            [(s["path"], s["start"], s["end"]) for s in chosen]
        name = (cfg.get("broadcast_name") or DEFAULT_NAME).strip()
        length = audio.join_to_mp3(parts, out,
                                   cfg.get("mp3_bitrate", "192k"),
                                   {"title": f"{name} Broadcast {date:%m/%d/%Y}"}, comp)
    save_history(date, [s["path"] for s in chosen], out)
    log(f"Done: {out} ({audio.fmt(length)})")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python builder.py <service file> [YYYY-MM-DD]")
    d = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    build(sys.argv[1], date=d)
