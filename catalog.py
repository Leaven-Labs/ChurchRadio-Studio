"""Song catalog: a CSV file the user can edit in Excel.

Columns: file, title, duration, seasons, enabled, words
- title: song name, for people to read.
- seasons: words from churchyear.SEASONS (or 'patriotic') split by ';'. Empty = general (any time).
- enabled: 'yes' or 'no'.
- words: how many words the speech model heard in the song (empty = not checked yet).
- start_silence / end_silence: seconds of silence at the start / end of the song. They are cut
  when the song is played, so there is no gap between songs (empty = not measured yet).
- public_domain: yes / allowed / no / check / unknown from the public-domain lookup (pdlookup.py);
  empty = not looked up yet. pd_note says why.
- permission: why the church may broadcast a song that is not in the public domain, typed by the
  person (e.g. "CCLI Streaming License 123456", "letter from the writer"). Empty = none. The
  lookup never changes it.
New songs found in the song folders are added with a guessed season. The Songs window in
the app edits this file too.

Import song list (import_csv): a separate CSV, from a template the app saves (write_template),
adds songs to this list or changes their title, seasons and on/off in one go.
"""
import csv
import os

import churchyear

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
FIELDS = ["file", "title", "duration", "seasons", "enabled", "words", "start_silence", "end_silence",
          "public_domain", "pd_note", "permission"]
MIN_WORDS = 6  # a song with fewer words heard than this has no words (instrumental): turned off once
OFF = ("no", "n", "0", "false")


def scan(folders):
    found = []
    for folder in folders:
        for root, _dirs, files in os.walk(folder):
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in AUDIO_EXT:
                    found.append(os.path.join(root, f))
    return found


def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return {row["file"]: row for row in csv.DictReader(fh)}
    except UnicodeDecodeError:  # saved by Excel in the Windows encoding
        with open(path, newline="", encoding="cp1252") as fh:
            return {row["file"]: row for row in csv.DictReader(fh)}


def save(path, rows):
    """Write the catalog. utf-8-sig so Excel shows accents and curly quotes correctly."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for key in sorted(rows):
            w.writerow({k: rows[key].get(k, "") for k in FIELDS})


def update(path, folders, get_duration, log=print, get_edges=None):
    """Add new songs, drop missing ones, fill in missing durations. Returns rows.

    get_edges(file) -> (start silence, end silence) in seconds; measured once per song."""
    rows = load(path)
    files = scan(folders)
    present = set(files)
    for f in files:
        row = rows.setdefault(f, {"file": f, "duration": "", "seasons": None, "enabled": "yes"})
        if row["seasons"] is None:
            row["seasons"] = ";".join(sorted(churchyear.guess_seasons(f)))
            log(f"New song: {os.path.basename(f)} -> {row['seasons'] or 'general'}")
        if not row.get("duration"):
            try:
                row["duration"] = f"{get_duration(f):.1f}"
            except Exception as e:  # noqa: BLE001
                log(f"Cannot read length of {f}: {e}")
                row["duration"] = "0"
        if get_edges and not (row.get("start_silence") or "").strip() and _duration(row) > 0:
            try:
                lead, tail = get_edges(f)
                row["start_silence"], row["end_silence"] = f"{lead:.2f}", f"{tail:.2f}"
            except Exception as e:  # noqa: BLE001  tried again next time
                log(f"Cannot measure the silence in {f}: {e}")
    # A song folder that cannot be reached (moved, or a drive not connected) keeps its songs,
    # so titles, seasons and on/off settings typed in are not lost.
    reachable = [os.path.normcase(os.path.join(os.path.abspath(f), "")) for f in folders if os.path.isdir(f)]
    for gone in set(rows) - present:
        if not any(os.path.normcase(os.path.abspath(gone)).startswith(r) for r in reachable):
            continue
        log(f"Song no longer found, removed from catalog: {gone}")
        del rows[gone]
    save(path, rows)
    return rows


def is_on(row):
    return (row.get("enabled") or "yes").strip().lower() not in OFF


def cleared(row):
    """True if the song may be broadcast: public domain, a free license, or the church's permission."""
    return ((row.get("public_domain") or "").strip().lower() in ("yes", "allowed")
            or bool((row.get("permission") or "").strip()))


def check_words(path, rows, count_words, min_words=MIN_WORDS, log=print):
    """Listen once to every song not checked yet and count the words heard.

    A song with fewer than min_words words has no words (instrumental) and is turned off.
    This runs only once per song (the count is kept in the 'words' column), so a song
    turned back on by hand stays on. count_words(path, duration) returns the count.
    Returns the songs that were turned off.
    """
    todo = [r for r in rows.values() if not (r.get("words") or "").strip()
            and _duration(r) > 0 and os.path.exists(r["file"])]
    if not todo:
        return []
    log(f"Listening to {len(todo)} new song(s) for words (once per song, a few seconds each) ...")
    off = []
    for r in todo:
        try:
            n = count_words(r["file"], _duration(r))
        except Exception as e:  # noqa: BLE001
            log(f"Cannot check words in {os.path.basename(r['file'])}: {e}")
            continue
        r["words"] = str(n)
        if n < min_words and is_on(r):
            r["enabled"] = "no"
            off.append(r)
            log(f"No words heard in {r.get('title') or os.path.basename(r['file'])}: turned off "
                "(turn it back on in Songs if it is a good song)")
        save(path, rows)  # keep the progress if the build stops
    return off


def _duration(row):
    try:
        return float(row.get("duration") or 0)
    except ValueError:
        return 0.0


def _num(row, key):
    try:
        return max(0.0, float(row.get(key) or 0))
    except ValueError:
        return 0.0


def songs_for(rows, season, patriotic=False, trim=True):
    """Songs that may play in this church season: its seasonal songs plus general songs.
    Patriotic songs are allowed (and preferred) only when `patriotic` is True.

    trim: cut the silence at the start and end of each song. 'duration' is then the length
    that is played, and 'start' / 'end' say which part of the file to play."""
    allowed = set(churchyear.allowed_seasons(season))
    if patriotic:
        allowed.add(churchyear.PATRIOTIC)
    out = []
    for r in rows.values():
        if not is_on(r):
            continue
        tags = {t.strip().lower() for t in (r.get("seasons") or "").split(";") if t.strip()}
        tags.discard("general")
        if tags and not tags & allowed:
            continue
        dur = _duration(r)
        lead, tail = (_num(r, "start_silence"), _num(r, "end_silence")) if trim else (0.0, 0.0)
        if lead + tail >= dur:
            lead = tail = 0.0
        out.append({"path": r["file"], "title": r.get("title") or "", "duration": dur - lead - tail,
                    "start": lead, "end": dur - tail if tail else None, "seasonal": bool(tags)})
    return out


# ---- import a song list ---------------------------------------------------------------------
IMPORT_FIELDS = ["file", "title", "seasons", "enabled", "permission"]
TEMPLATE_ROWS = [
    {"file": r"C:\Church Songs\A Mighty Fortress.mp3", "title": "A Mighty Fortress Is Our God",
     "seasons": "", "enabled": "yes", "permission": ""},
    {"file": "Joy to the World.mp3", "title": "Joy to the World", "seasons": "christmas", "enabled": "yes",
     "permission": ""},
    {"file": "In Christ Alone.mp3", "title": "In Christ Alone", "seasons": "", "enabled": "yes",
     "permission": "CCLI Streaming License 123456"},
]
# Season names people may type in the import file, as well as the season words themselves.
SEASON_ALIASES = {"holy week": "holyweek", "general": "", "any": "", "all": ""}
YES = ("yes", "y", "1", "true", "on")


def write_template(path):
    """Save a starting import file: the columns and a few example rows to replace."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=IMPORT_FIELDS)
        w.writeheader()
        w.writerows(TEMPLATE_ROWS)


def _read_any(path):
    """Rows of a CSV, with headers made lower case and trimmed (Excel files say 'Title ')."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, newline="", encoding=enc) as fh:
                reader = csv.DictReader(fh)
                rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in reader]
                return [k.strip().lower() for k in (reader.fieldnames or [])], rows
        except UnicodeDecodeError:
            continue
    raise ValueError("The file is not a text CSV file.")


def parse_seasons(text):
    """'Advent; Christmas' or 'lent, holy week' -> 'advent;christmas'. Raises ValueError for an
    unknown word. Empty or 'General' -> '' (any time)."""
    tags = []
    for part in text.replace(",", ";").split(";"):
        word = " ".join(part.lower().split())
        if not word:
            continue
        tag = SEASON_ALIASES.get(word, word.replace(" ", ""))
        if tag and tag not in churchyear.SEASONS and tag != churchyear.PATRIOTIC:
            raise ValueError(f'unknown season "{part.strip()}"')
        if tag and tag not in tags:
            tags.append(tag)
    return ";".join(tags)


def _find_file(name, folders):
    """A full path as it is, else a name (or a path inside a song folder) found in the song folders."""
    if os.path.isabs(name):
        return name if os.path.isfile(name) else None
    for folder in folders:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            return os.path.normpath(p)
    want = os.path.basename(name).lower()
    for f in scan(folders):
        if os.path.basename(f).lower() == want:
            return f
    return None


def import_csv(path, import_path, folders, get_duration, get_edges=None, log=print):
    """Add the songs in import_path to the song list at path, or update them if already there.

    Columns: file (a full path, or a file name in one of the song folders), title, seasons,
    enabled, permission. For a song already in the list an empty cell keeps what is there now; a new song
    with no seasons gets them guessed from its file name, as songs found in the folders do.
    Returns (rows, added, updated, problems): problems are lines for the person to read.
    """
    fields, data = _read_any(import_path)
    if "file" not in fields:
        raise ValueError('The file has no "file" column. Start from the template (Download template...).')
    rows = load(path)
    by_norm = {os.path.normcase(os.path.abspath(k)): k for k in rows}
    added = updated = 0
    problems = []
    for n, r in enumerate(data, start=2):  # line 1 is the header
        name = r.get("file", "")
        if not name and not any(r.values()):
            continue  # an empty line
        where = f"Line {n}"
        if not name:
            problems.append(f"{where}: no file name.")
            continue
        found = _find_file(name, folders)
        if not found:
            problems.append(f"{where}: song file not found: {name}")
            continue
        try:
            seasons = parse_seasons(r.get("seasons", "")) if r.get("seasons") else None
        except ValueError as e:
            problems.append(f"{where}: {e} (use {', '.join(churchyear.SEASONS)}, patriotic or general).")
            continue
        enabled = r.get("enabled", "").lower()
        if enabled and enabled not in YES + OFF:
            problems.append(f'{where}: enabled must be yes or no, not "{r.get("enabled")}".')
            continue
        key = by_norm.get(os.path.normcase(os.path.abspath(found)))
        if key is None:
            key = by_norm[os.path.normcase(os.path.abspath(found))] = found
            rows[key] = {"file": found, "duration": "", "enabled": "yes",
                         "seasons": ";".join(sorted(churchyear.guess_seasons(found)))}
            added += 1
        else:
            updated += 1
        row = rows[key]
        if r.get("title"):
            row["title"] = r["title"]
        if seasons is not None:
            row["seasons"] = seasons
        if enabled:
            row["enabled"] = "yes" if enabled in YES else "no"
        if r.get("permission"):
            row["permission"] = r["permission"]
        if not row.get("duration"):
            try:
                row["duration"] = f"{get_duration(found):.1f}"
            except Exception as e:  # noqa: BLE001
                log(f"Cannot read length of {found}: {e}")
                row["duration"] = "0"
        if get_edges and not (row.get("start_silence") or "").strip() and _duration(row) > 0:
            try:
                lead, tail = get_edges(found)
                row["start_silence"], row["end_silence"] = f"{lead:.2f}", f"{tail:.2f}"
            except Exception as e:  # noqa: BLE001  tried again by Look for new songs
                log(f"Cannot measure the silence in {found}: {e}")
    if added or updated:
        save(path, rows)
    return rows, added, updated, problems
