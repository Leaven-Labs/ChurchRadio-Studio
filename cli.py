"""Make the broadcast with no window, for Windows Task Scheduler (or a script).

    ChurchRadio-Studio.exe --build "C:\\OBS Recordings"
    ChurchRadio-Studio.exe --build "C:\\OBS Recordings\\service 11.15.2026.mkv" --date 2026-11-15

--build takes a recording, or a folder: then the newest recording in it is used, unless its
broadcast MP3 is already there (nothing to do) or it is still being written (try again later).
The settings are the ones chosen in the app (Settings); the options below change one run only.

Nothing is shown on screen. Each run writes a log in the settings folder (logs\\) and ends with
an exit code that Task Scheduler shows as the "Last Run Result":
    0  done, or nothing to do
    1  failed (the log says why)
    2  done, but the broadcast is too long: edit it by hand (the log says by how much)
"""
import argparse
import datetime as dt
import os
import sys
import time

import builder
import churchyear
import paths
import prelude

MEDIA_EXT = {".mkv", ".mp4", ".wav", ".mp3", ".m4a"}
SETTLE_MINUTES = 10  # a recording changed more recently than this may still be recording or copying
KEEP_LOGS = 30
LOCK_STALE_HOURS = 4  # a lock older than this was left by a run that crashed
DONE, FAILED, TOO_LONG = 0, 1, 2


def build_args(argv):
    """True if these command-line words ask for a headless build."""
    return any(a == "--build" or a.startswith("--build=") for a in argv)


class UsageError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    """Bad options become a logged error (exit 1), not argparse's exit 2, which means "too long"."""

    def error(self, message):
        raise UsageError(message)


def parser():
    p = Parser(
        prog="ChurchRadio-Studio.exe", description="Make the radio broadcast with no window.",
        epilog="Exit codes: 0 done or nothing to do, 1 failed, 2 done but too long (edit it by hand).")
    p.add_argument("--build", required=True, metavar="RECORDING_OR_FOLDER",
                   help="the service recording, or a folder: the newest recording in it")
    p.add_argument("--date", metavar="YYYY-MM-DD",
                   help="the service date (default: the date in the file name, else the day it was recorded)")
    p.add_argument("--start", choices=prelude.MODES, help="where the service starts (default: as in Settings)")
    p.add_argument("--keep-end", action="store_true", help="keep everything after the end of the service")
    p.add_argument("--no-compress", action="store_true", help="save the MP3 without the broadcast compressor")
    p.add_argument("--force", action="store_true", help="make the broadcast again even if its MP3 is already there")
    p.add_argument("--dry-run", action="store_true", help="only say which recording and date would be used")
    p.add_argument("--settle", type=float, default=SETTLE_MINUTES, metavar="MINUTES",
                   help=f"skip a recording changed in the last MINUTES minutes (default {SETTLE_MINUTES})")
    p.add_argument("--log", metavar="FILE", help="write the log here (default: logs\\ in the settings folder)")
    return p


# ---- choosing the recording and date ----------------------------------------------------------
def recordings(folder):
    """The recordings in a folder (not its sub folders), newest first."""
    found = [os.path.join(folder, f) for f in os.listdir(folder)
             if os.path.splitext(f)[1].lower() in MEDIA_EXT and os.path.isfile(os.path.join(folder, f))]
    return sorted(found, key=os.path.getmtime, reverse=True)


def recording_date(path):
    """The service date: from the file name, else the day the file was last written (the end of
    the recording; copying a file in Windows keeps that date)."""
    return churchyear.date_from_filename(os.path.basename(path)) or \
        dt.date.fromtimestamp(os.path.getmtime(path))


def still_writing(path, minutes, now=None):
    return (now or time.time()) - os.path.getmtime(path) < minutes * 60


def output_path(cfg, service, date):
    out_dir = cfg.get("output_folder") or os.path.dirname(os.path.abspath(service))
    return os.path.join(out_dir, builder.output_name(cfg, date))


def choose(target, cfg, date=None, settle=SETTLE_MINUTES, force=False, now=None):
    """(recording, date, None) to build, or (None, None, reason) when there is nothing to do.
    Raises ValueError when the recording or folder can't be used."""
    if os.path.isdir(target):
        found = recordings(target)
        if not found:
            return None, None, f"No recordings in {target}."
        service = found[0]
    elif os.path.isfile(target):
        service = target
    else:
        raise ValueError(f"Not found: {target}")
    if os.path.splitext(service)[1].lower() not in MEDIA_EXT:
        raise ValueError(f"Not a recording the app can use (MKV, MP4, WAV, MP3 or M4A): {service}")
    if still_writing(service, settle, now):
        return None, None, (f"{os.path.basename(service)} was changed in the last {settle:g} minutes: it may "
                            "still be recording or copying. Try again later.")
    date = date or recording_date(service)
    out = output_path(cfg, service, date)
    if os.path.exists(out) and not force:
        return None, None, f"The broadcast for {os.path.basename(service)} is already made: {out}"
    return service, date, None


# ---- one run at a time ------------------------------------------------------------------------
def lock_path():
    return os.path.join(paths.data_dir(), "build.lock")


def take_lock(who):
    """Mark that a broadcast is being made. False if another one is already being made."""
    p = lock_path()
    try:
        if time.time() - os.path.getmtime(p) > LOCK_STALE_HOURS * 3600:
            os.remove(p)  # left behind by a run that stopped without cleaning up
    except OSError:
        pass
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"{who} {dt.datetime.now():%Y-%m-%d %H:%M}\n")
    return True


def lock_owner():
    try:
        with open(lock_path(), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def drop_lock():
    try:
        os.remove(lock_path())
    except OSError:
        pass


# ---- the log ----------------------------------------------------------------------------------
class Log:
    """Writes each line to the log file, and to the console when there is one."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.fh = open(path, "a", encoding="utf-8")

    def __call__(self, msg):
        line = f"{dt.datetime.now():%H:%M:%S}  {msg}"
        self.fh.write(line + "\n")
        self.fh.flush()
        if sys.stdout is not None:  # the installed program has no console
            try:
                print(line, flush=True)
            except (OSError, ValueError):
                pass

    def close(self):
        self.fh.close()


def default_log_path():
    return os.path.join(paths.data_dir(), "logs", f"build {dt.datetime.now():%Y-%m-%d %H-%M-%S}.log")


def tidy_logs(folder, keep=KEEP_LOGS):
    """Keep only the newest logs."""
    try:
        logs = sorted((os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".log")),
                      key=os.path.getmtime, reverse=True)
    except OSError:
        return
    for f in logs[keep:]:
        try:
            os.remove(f)
        except OSError:
            pass


# ---- run --------------------------------------------------------------------------------------
def main(argv, build=None):
    """Run a headless build. Returns the exit code."""
    try:
        args = parser().parse_args(argv)
    except UsageError as e:
        log = Log(default_log_path())
        log(f"ERROR: {e}. Example: --build \"C:\\OBS Recordings\"")
        log.close()
        return FAILED
    build = build or builder.build
    log_path = args.log or default_log_path()
    log = Log(log_path)
    try:
        log(f"{paths.APP_NAME} {paths.version()}: {' '.join(argv)}")
        date = None
        if args.date:
            try:
                date = dt.date.fromisoformat(args.date)
            except ValueError:
                log(f"ERROR: --date must look like 2026-11-15, not {args.date}")
                return FAILED
        try:
            cfg = builder.load_config()
        except (OSError, ValueError) as e:
            log(f"ERROR: could not read config.json: {e}")
            return FAILED
        if not cfg.get("setup_done"):
            log("ERROR: open ChurchRadio Studio once and finish the setup first.")
            return FAILED
        try:
            service, date, reason = choose(args.build, cfg, date, args.settle, args.force)
        except (OSError, ValueError) as e:
            log(f"ERROR: {e}")
            return FAILED
        if reason:
            log(f"Nothing to do. {reason}")
            return DONE
        log(f"Recording: {service}")
        log(f"Service date: {date:%m/%d/%Y}")
        if args.dry_run:
            log(f"Dry run: would save {output_path(cfg, service, date)}")
            return DONE
        if not take_lock("scheduled build"):
            log(f"ERROR: another broadcast is being made right now ({lock_owner()}). Try again later.")
            return FAILED
        warned = []
        try:
            out = build(service, cfg=cfg, date=date, log=log, start_mode=args.start, warn=warned.append,
                        cut_end=not args.keep_end, compress=not args.no_compress)
        except Exception as e:  # noqa: BLE001  any failure ends up in the log
            log(f"ERROR: {e}")
            return FAILED
        finally:
            drop_lock()
        if warned:
            log("TOO LONG: " + warned[0])
            return TOO_LONG
        log(f"Saved: {out}")
        return DONE
    finally:
        log.close()
        if not args.log:
            tidy_logs(os.path.dirname(log_path))
