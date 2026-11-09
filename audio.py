"""ffmpeg steps: read lengths, cut long silences, join parts into one MP3."""
import os
import re
import shutil
import subprocess
import sys

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


_tools = {}


def find_tool(name):
    """Find a working ffmpeg/ffprobe: the one installed with the app (ffmpeg folder), the app
    folder, PATH, then C:\\ffmpeg\\bin. Checked once, then remembered."""
    if name in _tools:
        return _tools[name]
    from paths import program_dir
    here = program_dir()
    exe = name + (".exe" if sys.platform == "win32" else "")
    for cand in (os.path.join(here, "ffmpeg", exe), os.path.join(here, exe), shutil.which(name),
                 os.path.join(r"C:\ffmpeg\bin", exe)):
        if cand and os.path.exists(cand):
            try:
                subprocess.run([cand, "-version"], capture_output=True, timeout=20,
                               creationflags=NO_WINDOW, check=True)
                _tools[name] = cand
                return cand
            except Exception:  # noqa: BLE001  broken copy, try the next one
                continue
    raise RuntimeError(f"{name} not found. Install a full ffmpeg build in C:\\ffmpeg\\bin.")


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


def join_to_mp3(parts, dst, bitrate="192k", meta=None, compression=None):
    """Join audio files in order into one MP3 (44.1 kHz stereo).

    parts: paths, or (path, start, end) to use only start..end seconds of that file (end None =
    to the end): the silence at the start and end of a song is cut so the parts play back to back.
    compression: dict that changes COMPRESSION (for example {"enabled": False}).
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
    _run(args + [dst])
    return duration(dst)


def fmt(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"
