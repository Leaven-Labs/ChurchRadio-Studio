"""ffmpeg steps: read lengths, cut long silences, join parts into one MP3."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

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


def _run(args):
    p = subprocess.run(args, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
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
    p = subprocess.run([ff, "-hide_banner", "-nostats"] + seek + ["-i", src, "-vn", "-af",
                        f"silencedetect=noise={noise_db}dB:d={max_silence}", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
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
    p = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_sec}", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read {os.path.basename(path)}")
    return edges_from(p.stderr, total)


# Broadcast compression: 4:1 above -18 dBFS, 20 ms attack, 250 ms release,
# +6 dB make-up gain, then a peak limiter at -1 dBFS so nothing clips.
COMPRESSION = {"enabled": True, "ratio": 4, "threshold_db": -18, "attack_ms": 20,
               "release_ms": 250, "makeup_db": 6, "limit_db": -1}


def _lin(db):
    return 10 ** (db / 20)


def compression_filter(comp=None):
    """ffmpeg filter text for the final compressor + limiter, or "" when off."""
    c = {**COMPRESSION, **(comp or {})}
    if not c["enabled"]:
        return ""
    return (f"acompressor=threshold={_lin(c['threshold_db']):.6f}:ratio={c['ratio']}"
            f":attack={c['attack_ms']}:release={c['release_ms']}"
            f":makeup={max(1.0, _lin(c['makeup_db'])):.4f}:detection=rms:link=maximum,"
            f"alimiter=limit={min(1.0, max(0.0625, _lin(c['limit_db']))):.4f}:attack=5:release=50:level=0")


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
    """Run ffmpeg and call on_seconds(seconds written) as it works. Errors as _run."""
    with tempfile.TemporaryFile() as err:  # (a pipe nobody reads would fill up and stop ffmpeg)
        p = subprocess.Popen(args[:1] + ["-nostats", "-progress", "pipe:1"] + args[1:], stdout=subprocess.PIPE,
                             stderr=err, text=True, errors="replace", creationflags=NO_WINDOW)
        with p.stdout:
            for line in p.stdout:
                sec = progress_seconds(line)
                if sec is not None:
                    try:
                        on_seconds(sec)
                    except Exception:  # noqa: BLE001  the window's trouble must not stop the MP3
                        pass
        p.wait()
        if p.returncode != 0:
            err.seek(0)
            raise RuntimeError(f"{os.path.basename(args[0])} failed:\n"
                               f"{err.read().decode(errors='replace')[-1500:]}")


def join_to_mp3(parts, dst, bitrate="192k", meta=None, compression=None, progress=None):
    """Join audio files in order into one MP3 (44.1 kHz stereo).

    parts: paths, or (path, start, end) to use only start..end seconds of that file (end None =
    to the end): the silence at the start and end of a song is cut so the parts play back to back.
    compression: dict that changes COMPRESSION (for example {"enabled": False}).
    progress(seconds): called while ffmpeg works with the seconds of the MP3 written so far.
    """
    ff = find_tool("ffmpeg")
    args = [ff, "-y", "-hide_banner"]
    for p in parts:
        args += ["-i", p if isinstance(p, str) else p[0]]
    chains = "".join(f"[{i}:a:0]{_trim_filter(p)}aresample=44100,"
                     f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];"
                     for i, p in enumerate(parts))
    inputs = "".join(f"[a{i}]" for i in range(len(parts)))
    comp = compression_filter(compression)
    args += ["-filter_complex", f"{chains}{inputs}concat=n={len(parts)}:v=0:a=1"
             + (f",{comp}" if comp else "") + "[out]",
             "-map", "[out]", "-c:a", "libmp3lame", "-b:a", bitrate]
    for k, v in (meta or {}).items():
        args += ["-metadata", f"{k}={v}"]
    if progress:
        _run_with_progress(args + [dst], progress)
    else:
        _run(args + [dst])
    return duration(dst)


def cut_clip(src, dst, start, seconds):
    """Write `seconds` of the recording from `start` as a small WAV (to play it in the window)."""
    _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-nostdin", "-ss", f"{max(0.0, start):.3f}", "-t",
          f"{seconds:.3f}", "-i", src, "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", dst])
    return dst


def loudness_outline(path, buckets=600, rate=2000):
    """How loud the recording is along its length, for drawing it: `buckets` numbers from 0 to 1.

    ffmpeg plays the sound out as mono at a low sample rate; each number is the loudness (RMS) of
    one equal slice of it, scaled so that the loud parts of the recording are near 1."""
    import numpy as np
    p = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-nostdin", "-i", path, "-vn", "-ac", "1",
                        "-ar", str(rate), "-f", "s16le", "-"], capture_output=True, creationflags=NO_WINDOW)
    data = p.stdout[:len(p.stdout) // 2 * 2]
    if p.returncode != 0 or len(data) < 2 * buckets:
        raise RuntimeError("ffmpeg could not read the sound:\n" + p.stderr.decode(errors="replace")[-1500:])
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    per = len(samples) // buckets
    loud = np.sqrt((samples[:per * buckets].reshape(buckets, per) ** 2).mean(axis=1))
    top = float(np.percentile(loud, 98))
    return np.clip(loud / top, 0.0, 1.0).tolist() if top > 0 else [0.0] * buckets


def fmt(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"
