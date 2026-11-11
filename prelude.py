"""Find where a spoken phrase (default "Good morning") starts, to cut the prelude before it.

Uses faster-whisper speech recognition on the start of the file. The models live in a
fixed folder per PC (``C:\\ProgramData\\ChurchRadio Studio\\models`` on Windows);
``models_folder`` in config.json overrides that. On first run the models are downloaded
once (about 620 MB) and then loaded offline with no network call.
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
from difflib import SequenceMatcher

import numpy as np

SEARCH_MINUTES = 30   # only the start of the file is searched
PAD_SEC = 0.3         # keep a little audio before the first word
MODEL_NAME = "base.en"
RATE = 16000

# Choir detection (organ prelude -> short pause -> choir song -> "Good morning")
FRAME_SEC = 0.1        # level is measured in 100 ms frames
GAP_MIN_SEC = 1.0      # a pause must be at least this long
GAP_DROP_DB = 25.0     # a pause is this much quieter than the loud parts (or below -45 dB)
SONG_MIN_SEC = 20.0    # a part shorter than this is a transition, not a song or prelude
SONG_MIN_WORDS = 8     # a sung part has at least this many recognised words ...
SONG_MIN_RATE = 4.0    # ... and at least this many words per minute
WORD_MIN_PROB = 0.4    # ignore words the recogniser is not sure of (music noise)
SPREAD_SEC = 10.0      # sung words must be spread over the part: it is split in 10 s windows ...
SONG_MIN_WINDOWS = 3   # ... and at least this many windows have words ...
SONG_MIN_COVER = 0.25  # ... and at least this part of the windows (talk near the microphone is one short burst)
HITS_AFTER_SEC = 120.0  # after the first "Good morning", later ones this close are only written to the log
START_MIN_SURE = 0.75   # a "Good morning" the recogniser is less sure of is chatter, not the pastor ...
START_SKIP_SEC = 300.0  # ... so a surer one up to this long after the first one is used instead
LOOKBACK_SEC = 15 * 60  # only look this far back from "Good morning"

MODES = ("Auto", "Organ start", "Keep start")

# Service end: the pastor's last words are "Go now in peace" and the congregation answers
# "Thanks be to God": the cut is right after that answer. If the answer is not heard, the cut is
# after "and we will" if it is heard right after the dismissal, else end_after_seconds after
# "Go now in peace". Only when "Go now in peace" is not heard at all does the old rule apply.
END_PHRASE = "Go now in peace"
END_ANSWER_PHRASE = "Thanks be to God"  # the congregation's answer: the real end of the service
END_ANSWER_WINDOW = 20.0  # the answer counts only if it starts this long after "Go now in peace"
END_ANSWER_PAD = 0.5      # keep a little audio after the answer
END_AFTER_SEC = 5.0        # if "and we will" is not heard, cut this long after "Go now in peace"
END_ALT_PHRASE = "and we will"   # the congregation's answer, cut right after these words
END_ALT_WINDOW = 20.0     # "and we will" counts only if it starts this long after the dismissal
END_ALT_PAD = 0.5         # keep a little audio after "and we will"
END_PHRASE_FALLBACK = "Thanks be to God"  # old rule, only when "Go now in peace" is not heard
END_SEARCH_MINUTES = 10  # only the end of the file is searched
END_MODEL_NAME = "small.en"  # more exact than base.en (hears the quiet answer), about 480 MB
END_PAD_SEC = 1.0        # keep a little audio after the last word
DISMISSAL_PHRASE = "Serve the Lord"  # the pastor: "Go in peace. Serve the Lord."
DISMISSAL_OTHER = "Go in peace"
ANSWER_OTHER = ("Thank you God", "Peace be to God")  # how the recogniser sometimes hears the answer
ANSWER_SEC = 4.0         # if the answer is not heard, cut this long after the dismissal
ANSWER_WAIT_SEC = 10.0   # the answer starts at most this long after the dismissal
GOES_ON_SEC = 1.5        # more words this soon after "Serve the Lord": it is not the dismissal ...
PEACE_BEFORE_SEC = 15.0  # ... unless "Go in peace" is this short time before it (the blessing follows at once)
END_PIECE_SEC = 30.0     # the end is heard in short pieces: in one long pass the recogniser skips quiet parts
END_OVERLAP_SEC = 5.0    # pieces overlap, so a phrase on the border is heard whole
MATCH_MIN = 0.85         # how close the heard words must be to the phrase (1.0 = exact)

_models = {}
_logged_models = set()
_model_lock = threading.Lock()


def _norm(word):
    return re.sub(r"[^a-z0-9]", "", word.lower())


def match_phrase(words, phrase):
    """words: iterable of (text, start_sec). Returns start of the first match, or None.

    Matching ignores case, spaces and punctuation, so "Good morning," and
    "Goodmorning" both match "good morning".
    """
    target = "".join(_norm(w) for w in phrase.split())
    if not target:
        return None
    window = []
    for text, start in words:
        t = _norm(text)
        if not t:
            continue
        window = (window + [(t, start)])[-len(target):]
        joined = ""
        for t_i, s_i in reversed(window):
            joined = t_i + joined
            if joined == target:
                return s_i
            if len(joined) >= len(target):
                break
    return None


def cut_point(found, pad=PAD_SEC):
    return None if found is None else max(0.0, found - pad)


def phrase_matches(words, phrase, min_ratio=MATCH_MIN):
    """words: iterable of (text, start_sec, end_sec). Returns every match as (start, end).

    Case, spaces and punctuation are ignored. Small errors of the speech recogniser
    are allowed ("Thank be to God", "Thanks to God"): the heard words must be at
    least min_ratio alike to the phrase. end is the end of the last word of the match.
    """
    target = "".join(_norm(w) for w in phrase.split())
    if not target:
        return []
    words = [(t, s, e) for t, s, e in ((_norm(w[0]), w[1], w[2]) for w in words) if t]
    n = len(phrase.split())

    def best_at(i):
        """(ratio, number of words) of the best match that starts at word i, or None."""
        best = None
        for k in range(max(1, n - 2), n + 3):
            if i + k > len(words):
                break
            heard = "".join(w[0] for w in words[i:i + k])
            if len(heard) < 0.8 * len(target):  # a part of the phrase ("Thanks be to") is not a match
                continue
            r = SequenceMatcher(None, heard, target).ratio()
            if r >= min_ratio and (best is None or r >= best[0]):
                best = (r, k)
        return best

    found, i = [], 0
    while i < len(words):
        best = best_at(i)
        nxt = best_at(i + 1) if best else None
        if best and not (nxt and nxt[0] > best[0]):  # a better match starts at the next word
            found.append((words[i][1], words[i + best[1] - 1][2]))
            i += best[1]
        else:
            i += 1
    return found


def snappy_cut(cut, words):
    """Move a cut point so it does not fall in the middle of a word: to the end of that word."""
    return next((w[2] for w in words if w[1] <= cut < w[2]), cut)


def choose_end(dismissal, words=(), alt=(), after=END_AFTER_SEC, alt_window=END_ALT_WINDOW,
               alt_pad=END_ALT_PAD, thanks=(), peace=(), answer=(), answer_window=END_ANSWER_WINDOW,
               answer_pad=END_ANSWER_PAD):
    """(cut point or None, note).

    dismissal: the "Go now in peace" matches as (start, end) (the last one is used).
    words: all words heard as (text, start, end).
    answer: the "Thanks be to God" matches as (start, end). The first one that starts within
    answer_window after "Go now in peace" is the end of the service: cut answer_pad after it.
    alt: the "and we will" matches as (start, end), used when the answer is not heard.
    after: cut this long after "Go now in peace" ends when "and we will" is not heard.
    alt_window: "and we will" counts only if it starts within this long after the dismissal.
    alt_pad: keep this much audio after "and we will".
    thanks / peace: only used by the fallback (the old rule), when "Go now in peace" is not heard.

    Rule: the end is the congregation's "Thanks be to God" right after "Go now in peace". If it
    is not heard: right after "and we will" if that is heard shortly after "Go now in peace", else
    `after` seconds after "Go now in peace" ends. Only when "Go now in peace" is not heard at all
    does the old rule run (the last "Thanks be to God", or the last "Serve the Lord").
    """
    d = dismissal[-1] if dismissal else None
    if d is not None:
        t = next((m for m in answer if d[1] - 0.5 <= m[0] <= d[1] + answer_window), None)
        if t:
            cut = snappy_cut(t[1] + answer_pad, words)
            return cut, f'"{END_ANSWER_PHRASE}" right after "{END_PHRASE}" ({_fmt(d[1])}), cut right after it'
        a = next((m for m in alt if d[1] - 0.5 <= m[0] <= d[1] + alt_window), None)
        if a:
            cut = snappy_cut(a[1] + alt_pad, words)   # never cut in the middle of a word
            return cut, (f'"{END_ANSWER_PHRASE}" not heard; "and we will" right after "{END_PHRASE}" '
                         f'({_fmt(d[1])}), cut right after it')
        cut = d[1] + after
        cut = snappy_cut(cut, words)
        return cut, f'"{END_ANSWER_PHRASE}" not heard; cut {after:g} s after "{END_PHRASE}" ({_fmt(d[1])})'
    return _choose_end_old(thanks, dismissal, words=words, peace=peace)


def _choose_end_old(thanks, dismissal, words=(), peace=()):
    """Old rule (fallback): the end is the last "Thanks be to God", or after the last "Serve the Lord".

    A "Thanks be to God" after a reading is not used: only the last one, after the dismissal.
    If the answer is too quiet it is not heard: then the cut is ANSWER_SEC after the pastor's
    "Serve the Lord", but only if the pastor stops there (no more talk at once).
    """
    d = dismissal[-1] if dismissal else None
    if d is None:
        return (thanks[-1][1], f'the last "{END_PHRASE_FALLBACK}"') if thanks else (None, "")
    t = next((m for m in thanks if d[1] - 0.5 <= m[0] <= d[1] + ANSWER_WAIT_SEC), None)
    if t:
        return t[1], f'the answer to "{DISMISSAL_PHRASE}" ({_fmt(d[1])})'
    nxt = next((w[1] for w in words if w[2] > d[1] and w[1] >= d[1] - 0.05 and _norm(w[0])), None)
    if nxt is not None and nxt - d[1] < GOES_ON_SEC:
        if any(d[0] - PEACE_BEFORE_SEC <= p[0] < d[0] for p in peace):
            cut = d[1] + ANSWER_SEC
            cut = snappy_cut(cut, words)
            return cut, f'"Go in peace, {DISMISSAL_PHRASE}" at {_fmt(d[1])}, no answer, so cut {ANSWER_SEC:g} s after it'
        return None, (f'"{DISMISSAL_PHRASE}" at {_fmt(d[1])} is not the dismissal (the talk goes on) '
                      f'and "{END_PHRASE_FALLBACK}" is not heard after it')
    return d[1] + ANSWER_SEC, f'not heard after "{DISMISSAL_PHRASE}" ({_fmt(d[1])}), so cut {ANSWER_SEC:g} s after it'


def _fmt(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def end_point(found, total, pad=0.0):
    """Where the kept audio ends: never after the file end.

    pad: the new rules cut right at the chosen word ("Go now in peace" + the seconds, or
    "and we will" + the small pad) so pad is 0. The old fallback keeps END_PAD_SEC (1 s).
    """
    return total if found is None else min(total, found + pad)


def frame_levels(audio, frame=int(RATE * FRAME_SEC)):
    """dBFS level of each frame of float mono audio."""
    n = len(audio) // frame
    if n == 0:
        return np.zeros(0)
    rms = np.sqrt(np.mean(audio[:n * frame].reshape(n, frame) ** 2, axis=1))
    return 20 * np.log10(np.maximum(rms, 1e-6))


def find_gaps(levels, end_sec, frame_sec=FRAME_SEC):
    """Pauses (start_sec, end_sec) before end_sec, at least GAP_MIN_SEC long."""
    stop = min(len(levels), int(end_sec / frame_sec))
    lv = levels[:stop]
    if not len(lv):
        return []
    loud = np.percentile(lv, 90)
    quiet = lv < max(-45.0, loud - GAP_DROP_DB)
    gaps, run = [], None
    for i, q in enumerate(np.append(quiet, False)):
        if q and run is None:
            run = i
        elif not q and run is not None:
            if (i - run) * frame_sec >= GAP_MIN_SEC:
                gaps.append((run * frame_sec, i * frame_sec))
            run = None
    return gaps


def is_sung(a, b, times):
    """True if the word times in part a..b look like a song: many words, spread over the part."""
    times = [t for t in times if a <= t < b]
    dur = b - a
    if len(times) < SONG_MIN_WORDS or len(times) / (dur / 60) < SONG_MIN_RATE:
        return False
    windows = len({int((t - a) // SPREAD_SEC) for t in times})
    return windows >= SONG_MIN_WINDOWS and windows >= SONG_MIN_COVER * dur / SPREAD_SEC


def choose_start(gm, gaps, words):
    """Where the kept audio starts, and a note for the log.

    gm: time of "Good morning". gaps: pauses before it. words: (text, start, prob)
    heard before it. The audio between pauses is split into parts. Going back from
    "Good morning", sung parts (many words, spread over the part) and short
    transitions are kept. The first long part that is not sung is the organ
    prelude: the cut is at its end.
    """
    cut = cut_point(gm)
    gaps = [g for g in gaps if gm - LOOKBACK_SEC <= g[0] and g[1] <= gm]
    times = [w[1] for w in words if _norm(w[0]) and w[2] >= WORD_MIN_PROB]
    edges = [max(0.0, gm - LOOKBACK_SEC)] + [g[1] for g in gaps]
    stops = [g[0] for g in gaps] + [gm]
    keep_from = None
    for a, b in reversed(list(zip(edges, stops))):
        if b - a < SONG_MIN_SEC:
            continue
        if is_sung(a, b, times):
            keep_from = a
            continue
        break
    if keep_from is None:
        return cut, "No choir found before it."
    start = max(0.0, keep_from - PAD_SEC)
    return start, "Choir (sung words) found before it. Keeping the song."


def fixed_models_dir():
    """The one model folder per PC, shared by every app version and copy of the .exe.

    On Windows: ``C:\\ProgramData\\ChurchRadio Studio\\models``.
    On a Mac: ``/Users/Shared/ChurchRadio Studio/models`` (every account on the Mac can use it).
    On Linux: ``~/.cache/churchradio-studio/models`` ($XDG_CACHE_HOME if set). Created on first use.
    """
    from paths import APP_NAME, APP_SLUG
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), APP_NAME, "models")
    if system == "Darwin":
        return os.path.join("/Users/Shared", APP_NAME, "models")
    cache = (os.environ.get("XDG_CACHE_HOME") or "").strip() or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(cache, APP_SLUG, "models")


def _app_base_dir():
    from paths import program_dir
    return program_dir()


def _copy_models_across(src_root, fixed):
    """Copy model folders from ``src_root`` that ``fixed`` does not have yet. Never deletes or
    overwrites anything. Only sub-directories are copied: a plain file would raise in copytree,
    and a model always arrives as a folder (the faster-whisper cache layout)."""
    if not (os.path.isdir(src_root) and os.access(src_root, os.R_OK)):
        return
    for entry in sorted(os.listdir(src_root)):
        src = os.path.join(src_root, entry)
        if os.path.isdir(src) and not os.path.exists(os.path.join(fixed, entry)):
            shutil.copytree(src, os.path.join(fixed, entry))


def _models_dir(models_folder=""):
    """Where the models are read from: always the fixed per-PC folder.

    ``models_folder`` from config.json and a ``models`` folder next to the app are one-time
    sources: any model they hold that the fixed folder does not is copied across (no
    download). The source is never changed or deleted, and a model already in the fixed
    folder is never overwritten. If the copy fails, a usable ``models_folder`` is used as is.
    """
    fixed = fixed_models_dir()
    os.makedirs(fixed, exist_ok=True)
    try:
        if models_folder and os.path.abspath(models_folder) != os.path.abspath(fixed):
            _copy_models_across(models_folder, fixed)
        _copy_models_across(os.path.join(_app_base_dir(), "models"), fixed)
    except OSError:
        if models_folder and os.path.isdir(models_folder):
            return models_folder
        raise
    return fixed


def _model_path(folder, name):
    """Path of a model already downloaded under ``folder`` (a faster-whisper cache), or None.

    faster-whisper (via huggingface_hub) downloads into ``<root>/models--<org>--faster-whisper-<name>/``
    and keeps the usable files in ``.../snapshots/<hash>/`` (holding ``model.bin`` + ``config.json``).
    Return that snapshot dir, or fall back to a plain ``<folder>/<name>`` layout if it is used.
    """
    pattern = "faster-whisper-" + name
    if os.path.isdir(os.path.join(folder, name)) and os.path.isfile(os.path.join(folder, name, "model.bin")):
        return os.path.join(folder, name)
    for dirpath, _dirnames, filenames in os.walk(folder):
        if pattern in dirpath and "model.bin" in filenames:
            return dirpath
    return None


def _model_ready(folder, name):
    """True if ``folder`` already holds a usable copy of the model (no download needed)."""
    return _model_path(folder, name) is not None


def _get_model(models_folder="", name=MODEL_NAME, log=None):
    """Load a model, downloading only on first run.

    If the model files are already in the folder it is loaded straight from disk
    (no network); otherwise it is downloaded once to the fixed per-PC folder.
    ``log`` receives one line: "loaded from <path>" or "downloading to <path> (first run only)".
    """
    folder = _models_dir(models_folder)
    path = _model_path(folder, name)  # existing model (no download) or None
    if name not in _models:
        with _model_lock:
            if name not in _models:
                try:
                    from faster_whisper import WhisperModel
                except ImportError:
                    raise RuntimeError("Speech recognition is not installed. Run: pip install faster-whisper")
                threads = max(1, (os.cpu_count() or 4) - 1)
                if path:
                    _models[name] = WhisperModel(path, device="cpu",
                                                 compute_type="int8", cpu_threads=threads)
                else:
                    _models[name] = WhisperModel(name, device="cpu", compute_type="int8",
                                                 cpu_threads=threads, download_root=folder)
    if log and name not in _logged_models:  # one line per model, not one per piece of audio
        _logged_models.add(name)
        if path:
            log(f"Model {name}: loaded from {path}")
        else:
            log(f"Model {name}: downloading to {folder} (first run only)")
    return _models[name]


def find_start(src, phrase="Good morning", mode="Auto", search_minutes=SEARCH_MINUTES, models_folder="", log=None,
               min_sure=START_MIN_SURE, skip_sec=START_SKIP_SEC):
    """(gm_sec or None, start_sec, note). start_sec is where the kept audio begins."""
    if mode == "Keep start":
        return None, 0.0, "Keep start: nothing cut at the start."
    gm, audio, words = analyse(src, phrase, search_minutes, models_folder, log=log,
                               min_sure=min_sure, skip_sec=skip_sec)
    if gm is None:
        return None, 0.0, ""
    if mode == "Organ start":
        return gm, cut_point(gm), "Organ start: no choir check."
    return (gm,) + choose_start(gm, find_gaps(frame_levels(audio), gm), words)


def _read_audio(src, start=0.0, length=None, louder=False):
    """Mono 16 kHz float audio of src from start (s), length s or to the end.

    louder: make quiet speech (the congregation far from the microphone) as loud as the rest.
    """
    from audio import NO_WINDOW, find_tool
    seek = ["-ss", f"{start:.3f}"] if start > 0 else []
    span = ["-t", f"{length:.3f}"] if length else []
    r = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-nostdin"] + seek + span +
                       ["-i", src, "-map", "0:a:0", "-vn"] + (["-af", "dynaudnorm=f=200:g=11"] if louder else []) +
                       ["-f", "s16le", "-ar", str(RATE), "-ac", "1", "-"],
                       capture_output=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("Could not read audio for the phrase search.")
    return np.frombuffer(r.stdout, "<i2").astype(np.float32) / 32768.0


def _transcribe(audio, models_folder="", name=MODEL_NAME, log=None, **extra):
    # No VAD filter: it drops speech over organ music. No conditioning: avoids loops in music.
    opts = dict(language="en", vad_filter=False, word_timestamps=True,
                condition_on_previous_text=False, beam_size=1)
    opts.update(extra)
    return _get_model(models_folder, name, log=log).transcribe(audio, **opts)[0]


def choose_hit(hits, min_sure=START_MIN_SURE, skip_sec=START_SKIP_SEC):
    """Which "Good morning" is the pastor's. hits: (start, end, sure) in time order.

    Chatter near the microphone during the prelude is sometimes heard as "Good morning",
    but the recogniser is much less sure of it than of the pastor at the microphone
    (11/1/2026: chatter 50 %, the pastor 95 %). So the first hit that is at least min_sure
    is used, looking at most skip_sec past the first hit (a later "Good morning", for
    example at the children's sermon, is never used). If no hit there is sure enough,
    the surest one there is used. Returns the chosen hit, or None.
    """
    if not hits:
        return None
    near = [h for h in hits if h[0] <= hits[0][0] + skip_sec]
    return next((h for h in near if h[2] >= min_sure), None) or max(near, key=lambda h: h[2])


def _hits(heard, phrase):
    """Every exact "Good morning" in heard (text, start, prob, end) as (start, end, sure)."""
    out = []
    for a, b in phrase_matches([(w[0], w[1], w[3]) for w in heard], phrase, min_ratio=1.0):
        inside = [w for w in heard if a <= w[1] <= b]
        out.append((a, b, sum(w[2] for w in inside) / len(inside) if inside else 0.0))
    return out


def analyse(src, phrase, search_minutes=SEARCH_MINUTES, models_folder="", log=None,
            min_sure=START_MIN_SURE, skip_sec=START_SKIP_SEC):
    """(phrase time or None, audio, words heard before it as (text, start, prob))."""
    audio = _read_audio(src, 0.0, search_minutes * 60)
    segs = _transcribe(audio, models_folder, log=log)

    heard = []
    state = {"gm": None}
    listen = max(skip_sec, HITS_AFTER_SEC)

    def words():
        for s in segs:
            for w in s.words or []:
                heard.append((w.word, w.start, w.probability, w.end))
                if state["gm"] is not None and w.start > state["gm"] + listen:
                    return
                yield w.word, w.start

    # Find the first "Good morning", then keep listening a while: a surer one soon after it
    # is the pastor's, and the first was chatter (see choose_hit). Every hit is logged.
    stream = words()
    first = match_phrase(stream, phrase)
    state["gm"] = first
    if first is None:
        return None, audio, [w[:3] for w in heard]
    for _ in stream:
        pass
    hits = _hits(heard, phrase)
    chosen = choose_hit(hits, min_sure, skip_sec)
    gm = chosen[0] if chosen else first
    if log:
        _log_hits(heard, phrase, hits, chosen, min_sure, log)
    return gm, audio, [w[:3] for w in heard if w[1] < gm]


def _log_hits(heard, phrase, hits, chosen, min_sure, log):
    """One log line per "Good morning" heard (time, sureness, the words around it, used or not)."""
    for k, h in enumerate(hits, 1):
        a, b, prob = h
        before = " ".join(w[0].strip() for w in heard if a - 8 <= w[1] < a)
        after = " ".join(w[0].strip() for w in heard if b <= w[1] <= b + 8)
        if h == chosen:
            tag = "USED"
        elif chosen and a < chosen[0]:
            tag = f"skipped, less than {min_sure:.0%} sure" if prob < min_sure else "skipped"
        else:
            tag = "not used"
        log(f'"{phrase}" heard #{k} at {_fmt(a)} (sure {prob:.0%}, {tag}): ...{before} [{phrase}] {after}...')
    if chosen and chosen[2] < min_sure:
        log(f'No "{phrase}" was {min_sure:.0%} sure; used the surest one.')


WORDS_PIECE_SEC = 30.0          # to find songs with no words, listen to 30 s ...
WORDS_AT = (0.25, 0.5, 0.75)    # ... at these points of the song (an intro has no words)


def count_words(src, duration, models_folder="", log=None):
    """How many words the recogniser is sure of in a song (few or none = instrumental)."""
    if duration <= WORDS_PIECE_SEC * len(WORDS_AT):
        spans = [(0.0, None)]
    else:
        spans = [(duration * f - WORDS_PIECE_SEC / 2, WORDS_PIECE_SEC) for f in WORDS_AT]
    n = 0
    for start, length in spans:
        for s in _transcribe(_read_audio(src, start, length), models_folder, log=log):
            n += sum(1 for w in s.words or [] if _norm(w.word) and w.probability >= WORD_MIN_PROB)
    return n


def _hear_in_pieces(audio, offset, models_folder="", log=None):
    """Words (text, start, end, sure) of audio, heard in short overlapping pieces.

    Each word is kept from the piece where it is not in the overlap at the end
    (the next piece hears it with more context).
    """
    words, step, n = [], END_PIECE_SEC - END_OVERLAP_SEC, len(audio)
    a = 0.0
    while a * RATE < n:
        piece = audio[int(a * RATE):int((a + END_PIECE_SEC) * RATE)]
        last = (a + END_PIECE_SEC) * RATE >= n
        segs = _transcribe(piece, models_folder, END_MODEL_NAME, log=log,
                           no_speech_threshold=None, beam_size=5)
        for s in segs:
            for w in s.words or []:
                if words and a + w.start < words[-1][1] - offset + 0.05:
                    continue  # already kept from the piece before
                if not last and w.start >= step:
                    continue  # the next piece keeps it
                words.append((w.word, offset + a + w.start, offset + a + w.end, w.probability))
        if last:
            break
        a += step
    return words


def find_end(src, total, phrase=END_PHRASE, after=0.0, search_minutes=END_SEARCH_MINUTES, models_folder="",
              words_file=None, end_after=END_AFTER_SEC, alt_phrase=END_ALT_PHRASE,
              alt_window=END_ALT_WINDOW, alt_pad=END_ALT_PAD, answer_phrase=END_ANSWER_PHRASE,
              answer_window=END_ANSWER_WINDOW, answer_pad=END_ANSWER_PAD, log=None):
    """(phrase end or None, end_sec, note). Searches the last search_minutes of the file.

    The end is the congregation's answer to "Go now in peace": right after "Thanks be to God"
    (answer_phrase) if it is heard within answer_window after it; else right after "and we will"
    if it is heard shortly after, else end_after seconds after "Go now in peace". Only when
    "Go now in peace" is not heard does the old "Thanks be to God" rule apply (fallback).
    total: length of the file (s). after: never look before this time (the service start).
    words_file: if given, the words heard are written there (to check a wrong cut).
    If nothing is found, end_sec is total (nothing cut at the end).
    """
    if not phrase.strip() or not total:
        return None, total, ""
    offset = max(0.0, after, total - search_minutes * 60)
    if offset >= total:
        return None, total, ""
    # Quiet parts are not skipped (no_speech_threshold=None): the answer is quiet and short.
    # No hotwords: with them the recogniser "hears" the phrases in the music after the service.
    words = _hear_in_pieces(_read_audio(src, offset, total - offset, louder=True), offset,
                            models_folder, log=log)
    if words_file:
        try:
            with open(words_file, "w", encoding="utf-8") as f:
                f.write(f"Words heard from {_fmt(offset)} to the end ({_fmt(total)}):\n")
                f.writelines(f"{_fmt(w[1])}  {w[0].strip()}  (sure {w[3]:.0%})\n" for w in words)
        except OSError:
            pass
    dismissal = sorted(phrase_matches(words, phrase))
    alt = sorted(phrase_matches(words, alt_phrase)) if alt_phrase.strip() else []
    answers = ((answer_phrase,) + ANSWER_OTHER) if answer_phrase.strip() else ()
    answer = sorted(m for p in answers for m in phrase_matches(words, p))
    if dismissal and log:
        _log_answers(words, dismissal[-1], answer, answer_window, log)
    if dismissal:
        # The cut is right at the chosen words ("Thanks be to God" or "and we will" + the small
        # pad, or "Go now in peace" + the seconds). No extra pad -- "5 s" means 5 s after.
        found, note = choose_end(dismissal, words, alt, after=end_after, alt_window=alt_window,
                                 alt_pad=alt_pad, answer=answer, answer_window=answer_window,
                                 answer_pad=answer_pad)
        pad = 0.0
    else:
        # "Go now in peace" not heard: fall back to the old "Thanks be to God" rule (1 s pad).
        thanks = sorted(m for p in (END_PHRASE_FALLBACK,) + ANSWER_OTHER for m in phrase_matches(words, p))
        peace = phrase_matches(words, DISMISSAL_OTHER)
        serve = sorted(phrase_matches(words, DISMISSAL_PHRASE) + peace)
        found, note = _choose_end_old(thanks, serve, words, peace)
        if found is not None:
            note = f'no "{phrase}" heard, old rule: ' + note
        pad = END_PAD_SEC
    if found is None:
        return None, total, note
    return found, end_point(found, total, pad), note


def _log_answers(words, d, answer, window, log):
    """One log line per "Thanks be to God" heard soon after "Go now in peace", with how sure
    the recogniser was of it (for checking a wrong cut; the cut does not depend on it)."""
    for a, b in answer:
        if d[1] - 0.5 <= a <= d[1] + window:
            inside = [w for w in words if a <= w[1] <= b and len(w) > 3]
            sure = sum(w[3] for w in inside) / len(inside) if inside else 0.0
            log(f'"{END_ANSWER_PHRASE}" heard at {_fmt(a)}, {a - d[1]:.1f} s after "{END_PHRASE}" '
                f'(sure {sure:.0%}): ' + " ".join(w[0].strip() for w in words if a <= w[1] <= b))
