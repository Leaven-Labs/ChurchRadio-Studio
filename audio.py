"""ffmpeg steps: read lengths, cut long silences, join parts into one MP3."""
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


_tools = {}


# Where ffmpeg is usually installed by hand, tried after PATH. A Mac app started from the Dock
# does not get the Terminal's PATH, so Homebrew's folders are listed here too.
OTHER_PLACES = {"win32": [r"C:\ffmpeg\bin"], "darwin": ["/opt/homebrew/bin", "/usr/local/bin"],
                "linux": ["/usr/bin", "/usr/local/bin"]}
INSTALL_HINT = {"win32": "Install a full ffmpeg build in C:\\ffmpeg\\bin.",
                "darwin": "Install ffmpeg with Homebrew: brew install ffmpeg",
                "linux": "Install ffmpeg with your package manager, e.g. sudo apt install ffmpeg"}


def _platform():
    return "win32" if sys.platform == "win32" else "darwin" if sys.platform == "darwin" else "linux"


def find_tool(name):
    """Find a working ffmpeg/ffprobe: the one installed with the app (ffmpeg folder), the app
    folder, PATH, then the usual places for this system (OTHER_PLACES). Checked once, then
    remembered."""
    if name in _tools:
        return _tools[name]
    from paths import program_dir, resources_dir
    here, res = program_dir(), resources_dir()
    exe = name + (".exe" if sys.platform == "win32" else "")
    cands = [os.path.join(res, "ffmpeg", exe), os.path.join(here, "ffmpeg", exe), os.path.join(here, exe),
             shutil.which(name)] + [os.path.join(p, exe) for p in OTHER_PLACES[_platform()]]
    for cand in dict.fromkeys(c for c in cands if c):
        if cand and os.path.exists(cand):
            try:
                subprocess.run([cand, "-version"], capture_output=True, timeout=20,
                               creationflags=NO_WINDOW, check=True)
                _tools[name] = cand
                return cand
            except Exception:  # noqa: BLE001  broken copy, try the next one
                continue
    raise RuntimeError(f"{name} not found. {INSTALL_HINT[_platform()]}")


# ---- stopping the work (Cancel in the window) ---------------------------------------------------
class Stopped(BaseException):
    """The person stopped the work. Not an Exception: the places that log a file's trouble and go on
    to the next file (`except Exception`) must not go on."""


class Stopper:
    """Stops the work of one thread: stop() ends the ffmpeg that is running for it, and the work
    then ends with Stopped at its next step. See stoppable()."""

    def __init__(self):
        self._stopped, self._lock, self._procs = threading.Event(), threading.Lock(), set()

    def stopped(self):
        return self._stopped.is_set()

    def stop(self):
        self._stopped.set()
        with self._lock:
            procs = list(self._procs)
        for p in procs:
            try:
                p.kill()
            except OSError:
                pass  # it had just ended

    def check(self):
        if self._stopped.is_set():
            raise Stopped("Stopped.")

    def watch(self, proc):
        with self._lock:
            self._procs.add(proc)
        if self._stopped.is_set():  # stopped between check() and here
            self.stop()

    def forget(self, proc):
        with self._lock:
            self._procs.discard(proc)


_local = threading.local()


@contextlib.contextmanager
def stoppable(stopper):
    """The work done by this thread inside the `with` can be stopped with stopper.stop()."""
    _local.stopper = stopper
    try:
        yield stopper
    finally:
        _local.stopper = None


def check_stop():
    """Raise Stopped if this thread's work was stopped (called between the steps of long work)."""
    stopper = getattr(_local, "stopper", None)
    if stopper:
        stopper.check()


def run_tool(args, text=True):
    """Run ffmpeg or ffprobe to its end and return what it wrote (.returncode, .stdout, .stderr).
    Raises Stopped when the work was stopped: before it, while it ran (it is ended) or after it."""
    stopper = getattr(_local, "stopper", None)
    if stopper:
        stopper.check()
    how = {"text": True, "errors": "replace"} if text else {}
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW, **how)
    if stopper:
        stopper.watch(p)
    try:
        out, err = p.communicate()
    finally:
        if stopper:
            stopper.forget(p)
    if stopper:
        stopper.check()
    return subprocess.CompletedProcess(args, p.returncode, out, err)


def _run(args):
    p = run_tool(args)
    if p.returncode != 0:
        raise RuntimeError(f"{os.path.basename(args[0])} failed:\n{p.stderr[-1500:]}")
    return p


def duration(path):
    p = _run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", path])
    return float(p.stdout.strip())


def parse_silences(stderr):
    """Read (start, end) pairs from ffmpeg silencedetect output."""
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", stderr)]
    return [(max(0.0, s), e) for s, e in zip(starts, ends)]


def keep_ranges(total, silences, max_silence, keep=1.0):
    """Ranges to keep when every silence longer than max_silence is shortened to `keep` s."""
    out, pos = [], 0.0
    for s, e in silences:
        if e - s <= max_silence:
            continue
        cut_from = s + keep / 2
        cut_to = e - keep / 2
        if cut_from > pos:
            out.append((pos, cut_from))
        pos = cut_to
    if total > pos:
        out.append((pos, total))
    return out


def trim_service(src, dst, max_silence=5.0, noise_db=-40, log=print, start_sec=0.0, end_sec=None):
    """Make a WAV of the service with long silences cut, from start_sec to end_sec. Returns its length."""
    ff = find_tool("ffmpeg")
    end = duration(src) if end_sec is None else end_sec
    total = max(0.0, end - start_sec)
    seek = (["-ss", f"{start_sec:.3f}"] if start_sec > 0 else []) + \
        (["-t", f"{total:.3f}"] if end_sec is not None else [])
    p = run_tool([ff, "-hide_banner", "-nostats"] + seek + ["-i", src, "-vn", "-af",
                  f"silencedetect=noise={noise_db}dB:d={max_silence}", "-f", "null", "-"])
    ranges = keep_ranges(total, parse_silences(p.stderr), max_silence)
    cut = total - sum(b - a for a, b in ranges)
    log(f"Service: {fmt(total)}, cutting {cut:.1f} s of silence")
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges) or "1"
    _run([ff, "-y", "-hide_banner"] + seek + ["-i", src, "-vn", "-af",
          f"aselect='{expr}',asetpts=N/SR/TB", "-ar", "44100", "-ac", "2", dst])
    return duration(dst)


EDGE_SILENCE_DB = -50   # quieter than this at the start or end of a song counts as silence
EDGE_MIN_SEC = 0.1      # shorter silences are not cut


def edges_from(stderr, total, near=0.05, eof=0.5):
    """(lead, tail): seconds of silence at the start and the end, from silencedetect output.

    lead: a silence that starts at the very start. tail: a silence that runs to the end of the
    file (ffmpeg either prints no silence_end for it, or one at the file end).
    """
    starts = [max(0.0, float(x)) for x in re.findall(r"silence_start: (-?[\d.]+)", stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", stderr)]
    lead = tail = 0.0
    if starts and starts[0] <= near:
        lead = ends[0] if ends else total
    if starts and (len(starts) > len(ends) or ends[-1] >= total - eof):
        tail = max(0.0, total - starts[-1])
    if lead + tail >= total:  # all silence (or nearly): cut nothing
        return 0.0, 0.0
    return lead, tail


def edge_silence(path, noise_db=EDGE_SILENCE_DB, min_sec=EDGE_MIN_SEC):
    """Seconds of silence at the start and at the end of a file: (lead, tail)."""
    total = duration(path)
    p = run_tool([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
                  f"silencedetect=noise={noise_db}dB:d={min_sec}", "-f", "null", "-"])
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read {os.path.basename(path)}")
    return edges_from(p.stderr, total)


# Broadcast compression: 4:1 above -18 dBFS, 20 ms attack, 250 ms release,
# +6 dB make-up gain, then a peak limiter at -1 dBFS so nothing clips.
COMPRESSION = {"enabled": True, "ratio": 4, "threshold_db": -18, "attack_ms": 20,
               "release_ms": 250, "makeup_db": 6, "limit_db": -1}


def _lin(db):
    return 10 ** (db / 20)


def compression_filter(comp=None, limit=True):
    """ffmpeg filter text for the final compressor + limiter, or "" when off.
    limit=False: the compressor alone (the limiter comes later, see limiter_filter)."""
    c = {**COMPRESSION, **(comp or {})}
    if not c["enabled"]:
        return ""
    text = (f"acompressor=threshold={_lin(c['threshold_db']):.6f}:ratio={c['ratio']}"
            f":attack={c['attack_ms']}:release={c['release_ms']}"
            f":makeup={max(1.0, _lin(c['makeup_db'])):.4f}:detection=rms:link=maximum")
    return text + ("," + limiter_filter(c["limit_db"]) if limit else "")


def limiter_filter(limit_db=COMPRESSION["limit_db"]):
    """ffmpeg filter text for the peak limiter: nothing goes above limit_db (dBFS)."""
    return f"alimiter=limit={min(1.0, max(0.0625, _lin(limit_db))):.4f}:attack=5:release=50:level=0"


# Even loudness (loudness_lufs in config.json). Each part (intro, service, song) is first brought
# to LOUDNESS_REFERENCE, so the compressor works on all of them alike; then the whole broadcast is
# measured once more and brought to the target, and the limiter keeps the peaks under limit_db.
# LUFS: loudness as stations and podcast apps measure it (EBU R128 / ITU-R BS.1770).
LOUDNESS_REFERENCE = -20.0
MAX_BOOST_DB = 12.0   # a part is never turned up more than this (a quiet recording would hiss)
MAX_CUT_DB = 24.0
SILENT_LUFS = -60.0   # quieter than this, a part is taken as silence and left as it is


def integrated_loudness(stderr):
    """The integrated loudness (LUFS) in the summary ffmpeg's ebur128 filter writes, or None."""
    found = re.findall(r"^\s*I:\s+(-?(?:inf|[\d.]+))\s+LUFS", stderr, re.M)
    if not found:
        return None
    value = float(found[-1])
    return value if value > SILENT_LUFS else None


def loudness(path, start=0.0, end=None):
    """Integrated loudness (LUFS) of path, or of start..end seconds of it. None = silent."""
    trim = _trim_filter((path, start, end))
    p = run_tool([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-nostdin", "-i", path, "-vn",
                  "-af", f"{trim}ebur128=framelog=quiet", "-f", "null", "-"])
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg could not measure the loudness of {os.path.basename(path)}:\n"
                           + p.stderr[-1500:])
    return integrated_loudness(p.stderr)


def level_gain(lufs, want=LOUDNESS_REFERENCE):
    """dB that bring a part measured at lufs to want, within the limits above. 0 for silence."""
    if lufs is None:
        return 0.0
    return round(min(MAX_BOOST_DB, max(-MAX_CUT_DB, want - lufs)), 2)


def _trim_filter(part):
    """atrim text for a part given as (path, start, end), or "" for a plain path / nothing to cut."""
    if isinstance(part, str):
        return ""
    _path, start, end = part
    cut = ([f"start={start:.3f}"] if start and start > 0 else []) + ([f"end={end:.3f}"] if end else [])
    return f"atrim={':'.join(cut)},asetpts=PTS-STARTPTS," if cut else ""


def progress_seconds(line):
    """Seconds of sound written so far, from a line of ffmpeg's -progress output, or None."""
    key, _eq, value = line.strip().partition("=")
    if key in ("out_time_us", "out_time_ms"):  # (both are microseconds, in every ffmpeg so far)
        try:
            return max(0.0, int(value) / 1e6)
        except ValueError:
            return None
    return None


def _run_with_progress(args, on_seconds):
    """Run ffmpeg and call on_seconds(seconds written) as it works. Errors and Stopped as _run.
    Returns what ffmpeg wrote to stderr."""
    stopper = getattr(_local, "stopper", None)
    if stopper:
        stopper.check()
    with tempfile.TemporaryFile() as err:  # (a pipe nobody reads would fill up and stop ffmpeg)
        p = subprocess.Popen(args[:1] + ["-nostats", "-progress", "pipe:1"] + args[1:], stdout=subprocess.PIPE,
                             stderr=err, text=True, errors="replace", creationflags=NO_WINDOW)
        if stopper:
            stopper.watch(p)
        try:
            with p.stdout:
                for line in p.stdout:
                    sec = progress_seconds(line)
                    if sec is not None:
                        try:
                            on_seconds(sec)
                        except Exception:  # noqa: BLE001  the window's trouble must not stop the MP3
                            pass
            p.wait()
        finally:
            if stopper:
                stopper.forget(p)
        if stopper:
            stopper.check()
        err.seek(0)
        text = err.read().decode(errors="replace")
        if p.returncode != 0:
            raise RuntimeError(f"{os.path.basename(args[0])} failed:\n{text[-1500:]}")
        return text


def _graph(parts, gains, comp, final_db, limit_db, measure=False):
    """The filter graph that joins the parts: each one trimmed, turned up or down by its gain,
    made 44.1 kHz stereo; then the compressor, the final level and the limiter. measure=True: the
    graph up to the final level, ending in the loudness meter (to work out final_db)."""
    gains = gains or [0.0] * len(parts)
    chains = "".join(f"[{i}:a:0]{_trim_filter(p)}" + (f"volume={g:+.2f}dB," if g else "")
                     + f"aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];"
                     for i, (p, g) in enumerate(zip(parts, gains)))
    inputs = "".join(f"[a{i}]" for i in range(len(parts)))
    steps = [f"concat=n={len(parts)}:v=0:a=1"]
    if final_db is None and not measure:  # as before even loudness: compressor and limiter together
        steps.append(compression_filter(comp))
    else:
        steps.append(compression_filter(comp, limit=False))
        if measure:
            steps.append("ebur128=framelog=quiet")
        else:
            steps += [f"volume={final_db:+.2f}dB" if final_db else "", limiter_filter(limit_db)]
    return f"{chains}{inputs}" + ",".join(x for x in steps if x) + "[out]"


def _inputs(parts):
    args = []
    for p in parts:
        args += ["-i", p if isinstance(p, str) else p[0]]
    return args


def measure_joined(parts, gains=None, compression=None, progress=None):
    """Integrated loudness (LUFS) of the parts joined, with their gains and the compressor, before
    the final level (see join_to_mp3). None = silent. progress(seconds) as in join_to_mp3."""
    ff = find_tool("ffmpeg")
    args = [ff, "-hide_banner", "-nostdin"] + _inputs(parts) + [
        "-filter_complex", _graph(parts, gains, compression, None, None, measure=True),
        "-map", "[out]", "-f", "null", "-"]
    if progress:
        err = _run_with_progress(args, progress)
    else:
        err = _run(args).stderr
    return integrated_loudness(err)


def join_to_mp3(parts, dst, bitrate="192k", meta=None, compression=None, progress=None,
                gains=None, final_db=None):
    """Join audio files in order into one MP3 (44.1 kHz stereo).

    parts: paths, or (path, start, end) to use only start..end seconds of that file (end None =
    to the end): the silence at the start and end of a song is cut so the parts play back to back.
    compression: dict that changes COMPRESSION (for example {"enabled": False}).
    progress(seconds): called while ffmpeg works with the seconds of the MP3 written so far.
    gains: dB for each part (even loudness, see level_gain); final_db: dB for the whole after
    the compressor, before the limiter (None = no even loudness: no final level, and no limiter
    when the compressor is off).

    The MP3 is written under another name (dst + ".part") and gets its own name only when it is
    whole: a run that fails or is stopped leaves no half MP3 that looks like a finished broadcast.
    """
    ff = find_tool("ffmpeg")
    comp = {**COMPRESSION, **(compression or {})}
    args = [ff, "-y", "-hide_banner"] + _inputs(parts)
    args += ["-filter_complex", _graph(parts, gains, comp, final_db, comp["limit_db"]),
             "-map", "[out]", "-c:a", "libmp3lame", "-b:a", bitrate]
    for k, v in (meta or {}).items():
        args += ["-metadata", f"{k}={v}"]
    part = dst + ".part"
    try:
        if progress:
            _run_with_progress(args + ["-f", "mp3", part], progress)
        else:
            _run(args + ["-f", "mp3", part])
        try:
            os.replace(part, dst)
        except PermissionError:  # Windows: the MP3 made before is open in a player
            raise RuntimeError(f"Could not replace {dst}\nIt is open in another program (a music player?). "
                               "Close it there and make the broadcast again.") from None
    finally:
        try:
            os.remove(part)  # only there when it failed or was stopped
        except OSError:
            pass
    return duration(dst)


def cut_clip(src, dst, start, seconds):
    """Write `seconds` of the recording from `start` as a small WAV (to play it in the window)."""
    _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-nostdin", "-ss", f"{max(0.0, start):.3f}", "-t",
          f"{seconds:.3f}", "-i", src, "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", dst])
    return dst


DETAIL_PER_SECOND = 20  # the picture of the recording, zoomed in: this many loudness numbers for each second


def loudness_picture(path, buckets=600, per_second=DETAIL_PER_SECOND, rate=2000):
    """How loud the recording is along its length, for drawing it: (outline, detail).

    outline: `buckets` numbers from 0 to 1, each the loudness (RMS) of one equal slice of the
    whole recording, scaled so that its loud parts are near 1. detail: the same, but `per_second`
    numbers for every second (drawn when the picture is zoomed in). ffmpeg plays the sound out as mono at
    a low sample rate for it."""
    import numpy as np
    p = run_tool([find_tool("ffmpeg"), "-v", "error", "-nostdin", "-i", path, "-vn", "-ac", "1",
                  "-ar", str(rate), "-f", "s16le", "-"], text=False)
    data = p.stdout[:len(p.stdout) // 2 * 2]
    if p.returncode != 0 or len(data) < 2 * buckets:
        raise RuntimeError("ffmpeg could not read the sound:\n" + p.stderr.decode(errors="replace")[-1500:])
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)

    def rms(per):
        n = len(samples) // per
        return np.sqrt((samples[:n * per].reshape(n, per) ** 2).mean(axis=1))

    loud = rms(len(samples) // buckets)[:buckets]
    top = float(np.percentile(loud, 98))
    if top <= 0:
        return [0.0] * buckets, []
    fine = rms(max(1, rate // per_second))
    return np.clip(loud / top, 0.0, 1.0).tolist(), np.clip(fine / top, 0.0, 1.0).round(3).tolist()


def loudness_outline(path, buckets=600, rate=2000):
    """The outline of loudness_picture alone: `buckets` numbers from 0 to 1."""
    return loudness_picture(path, buckets, rate=rate)[0]


def fmt(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"
