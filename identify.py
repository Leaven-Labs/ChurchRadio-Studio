"""Identify a song: its title and church seasons, from its tags, its lyrics, or its file name.

1. Tags in the file (title / artist), read with ffprobe. Generic tags ("Track 03") are ignored.
2. Lyrics: the speech model listens to the start of the song, and the words are matched against
   a hymn list (hymns.csv: title, first line, another line such as the refrain, seasons). A
   church can add its own songs in hymns.csv in the user's folder. The shipped list has lyric
   lines only for public-domain hymns; songs still under copyright have just their title, which
   is matched when it is sung (often in the refrain).
3. The file name, cleaned up ("1-03_Amazing_Grace.mp3" -> "Amazing Grace").
Seasons come from the matched hymn, else from season words in the title or file name.
Every result says how it was found and how sure it is; the person confirms it before saving.
"""
import csv
import json
import os
import re
import subprocess
from difflib import SequenceMatcher

import churchyear

LISTEN_SEC = 150.0       # listen to this much of the start of the song (the first verse)
LINE_MIN = 0.80          # a heard line must be this alike to a hymn line to count
TITLE_MIN = 0.90         # the title sung in the song must be this alike ...
TITLE_MIN_CHARS = 9      # ... and be long enough not to match by chance ("He Lives" is too short)
GENERIC_TAG = re.compile(r"^\s*(track|audio|untitled|unknown|new recording|recording|title)?[\s_\-#]*\d*\s*$", re.I)


def _norm(word):
    return re.sub(r"[^a-z0-9]", "", word.lower())


def tokens(text):
    return [t for t in (_norm(w) for w in re.split(r"\s+", text or "")) if t]


# ---- 1. tags -----------------------------------------------------------------------------
def read_tags(path):
    """{'title': ..., 'artist': ..., 'album': ...} from the file's tags (missing keys left out)."""
    from audio import NO_WINDOW, find_tool
    p = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format_tags",
                        "-of", "json", path], capture_output=True, text=True, errors="replace",
                       creationflags=NO_WINDOW)
    if p.returncode != 0:
        return {}
    try:
        tags = json.loads(p.stdout or "{}").get("format", {}).get("tags", {}) or {}
    except ValueError:
        return {}
    low = {k.lower(): str(v).strip() for k, v in tags.items()}
    return {k: low[k] for k in ("title", "artist", "album", "genre") if low.get(k)}


def useful_title(tag):
    return bool(tag) and not GENERIC_TAG.match(tag)


# ---- 3. file name ------------------------------------------------------------------------
def title_from_filename(path):
    """'1-03_Amazing_Grace (live).mp3' -> 'Amazing Grace (live)'."""
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r"[_]+", " ", name)
    name = re.sub(r"^\s*(\d+[\s.\-]*)+", "", name)          # leading track numbers: "03 - ", "1-03 "
    name = re.sub(r"\s+", " ", name).strip(" -.")
    return name or os.path.splitext(os.path.basename(path))[0]


# ---- 2. lyrics -> hymn list --------------------------------------------------------------
def load_hymns(*paths):
    """Hymns from the CSV files (later files add to and replace earlier ones by title)."""
    out = {}
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        try:
            with open(p, newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
        except UnicodeDecodeError:
            with open(p, newline="", encoding="cp1252") as fh:
                rows = list(csv.DictReader(fh))
        for r in rows:
            title = (r.get("title") or "").strip()
            if not title:
                continue
            lines = [(r.get("first_line") or "").strip(), (r.get("also") or "").strip()]
            seasons = [s.strip().lower() for s in (r.get("seasons") or "").split(";") if s.strip()]
            out[title.lower()] = {"title": title, "lines": [tokens(x) for x in lines if tokens(x)],
                                  "title_tokens": tokens(title), "seasons": seasons}
    return list(out.values())


def _best_window(heard, line):
    """How alike the best run of heard words is to the line (0..1)."""
    n = len(line)
    if n == 0 or not heard:
        return 0.0
    if len(set(line) & set(heard)) < max(1, n // 2):   # quick check: most of its words must be heard
        return 0.0
    target, best = "".join(line), 0.0
    opening = set(line[:3])  # a match starts at one of the line's first words (one may be misheard)
    starts = [i for i, w in enumerate(heard) if w in opening] or [0]
    for size in {max(1, n - 1), n, n + 1}:
        for i in starts:
            r = SequenceMatcher(None, "".join(heard[i:i + size]), target).ratio()
            if r > best:
                best = r
                if best == 1.0:
                    return best
    return best


def match_hymn(heard_text, hymns):
    """(hymn, how sure 0..1, which line matched) for the best match in the heard words, or
    (None, 0.0, "")."""
    heard = tokens(heard_text)
    best = (None, 0.0, "")
    for h in hymns:
        for line in h["lines"]:
            if len(line) < 3:
                continue
            r = _best_window(heard, line)
            if r >= LINE_MIN and r > best[1]:
                best = (h, r, " ".join(line))
        if len(h["title_tokens"]) >= 2 and len("".join(h["title_tokens"])) >= TITLE_MIN_CHARS:
            r = _best_window(heard, h["title_tokens"])
            if r >= TITLE_MIN and r * 0.95 > best[1]:   # the title sung in the song: a little less sure
                best = (h, r * 0.95, " ".join(h["title_tokens"]))
    return best


def heard_words(path, duration, models_folder="", log=None):
    """The words the speech model hears in the start of the song (text), and how many it was sure of."""
    import prelude
    length = min(LISTEN_SEC, duration) if duration else LISTEN_SEC
    segs = prelude._transcribe(prelude._read_audio(path, 0.0, length), models_folder, log=log)
    words, sure = [], 0
    for s in segs:
        for w in s.words or []:
            if _norm(w.word):
                words.append(w.word.strip())
                sure += w.probability >= prelude.WORD_MIN_PROB
    return " ".join(words), sure


# ---- all together ------------------------------------------------------------------------
def identify(path, hymns, tags=None, heard="", known_title=""):
    """Suggested title and seasons for a song.

    tags: from read_tags. heard: words heard in the song (heard_words). known_title: a title the
    person already typed (kept unless empty). Returns a dict: title, seasons (list), how (text
    for the person), sure (0..1), hymn (title of the matched hymn or "").
    """
    tags = tags or {}
    hymn, score, line = match_hymn(heard, hymns) if heard else (None, 0.0, "")
    if known_title:
        title, how, sure = known_title, "title you typed", 1.0
    elif useful_title(tags.get("title", "")):
        title, how, sure = tags["title"], "tags in the file", 0.9
        if hymn and _best_window(tokens(title), hymn["title_tokens"]) >= TITLE_MIN:
            how, sure = f"tags in the file + lyrics ({score:.0%})", max(0.95, score)
    elif hymn:
        title, how, sure = hymn["title"], f'lyrics: "{line}" ({score:.0%} alike)', score
    else:
        title, how, sure = title_from_filename(path), "file name", 0.3
    if hymn and (not known_title or _best_window(tokens(known_title), hymn["title_tokens"]) >= TITLE_MIN):
        seasons = list(hymn["seasons"])
    else:
        seasons = sorted(churchyear.guess_seasons(" ".join([title, path, tags.get("album", "")])))
    return {"title": title, "seasons": seasons, "how": how, "sure": round(sure, 2),
            "hymn": hymn["title"] if hymn else ""}
