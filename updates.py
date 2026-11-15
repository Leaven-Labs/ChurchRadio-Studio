"""Updates: ask GitHub for the newest release, download this computer's installer, check it and
start it.

    update = updates.check()                   # None: this is the newest version
    path = updates.download(update, progress)  # the file, checked against SHA256SUMS.txt
    text = updates.install(path)               # starts it; the app then closes

The app asks only for the release's number and notes (one request to api.github.com). Nothing
about the services, songs or settings is sent. `check_updates` in config.json turns the check at
the start of the app off; About can still look when asked.

What install() does:
- Windows: runs the installer with /SILENT /RELAUNCH=1: it shows its progress, installs over
  this version (Windows may ask for permission) and starts the app again (see installer.iss).
- Linux, installed with install.sh: unpacks the download, runs its install.sh and starts the
  new program.
- Mac: opens the disk image; the person drags the app onto Applications, as for the first
  install. (The app does not replace itself: not tried on a real Mac yet.)

Only files of this project's releases on github.com are downloaded, and a file is used only if
its SHA-256 is the one in the release's SHA256SUMS.txt. That guards against a broken or swapped
download; it is not a signature (the installers are not code-signed yet).
"""
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request

import paths

REPO = "Leaven-Labs/ChurchRadio-Studio"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOADS = f"https://github.com/{REPO}/releases/download/"  # the only place a file is taken from
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSETS = {"win32": "ChurchRadio-Studio-Setup.exe", "darwin": "ChurchRadio-Studio-macOS.dmg",
          "linux": "ChurchRadio-Studio-Linux-x86_64.tar.gz"}
SUMS = "SHA256SUMS.txt"
TIMEOUT = 20
MAX_BYTES = 2 * 1024 ** 3  # no download of the app is near this: a wrong size is refused


class UpdateError(Exception):
    """Told to the person as it is."""


class Cancelled(Exception):
    """The person stopped the download."""


def _platform():
    return "win32" if sys.platform == "win32" else "darwin" if sys.platform == "darwin" else "linux"


def version_tuple(text):
    """(1, 3, 1) for "1.3.1" or "v1.3.1"; None for anything else (a development build)."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(n) for n in m.groups()) if m else None


def is_release():
    """True if this is a released build: only those are compared with the newest release."""
    return version_tuple(paths.version()) is not None


def linux_installed_dir():
    """Where tools/linux/install.sh puts the program."""
    data = (os.environ.get("XDG_DATA_HOME") or "").strip() or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(data, paths.APP_SLUG)


def can_install():
    """True if install() can put a new version in place here: the installed program on Windows
    and Linux, the app on a Mac. Not from source, and not from an unpacked Linux folder."""
    if not getattr(sys, "frozen", False):
        return False
    if sys.platform == "win32":
        return True
    if sys.platform == "darwin":
        return paths.mac_app()
    return os.path.realpath(paths.program_dir()) == os.path.realpath(linux_installed_dir())


def folder():
    """Where an update is downloaded to (in the settings folder)."""
    return os.path.join(paths.data_dir(), "update")


def clean():
    """Remove the downloads of earlier updates."""
    shutil.rmtree(folder(), ignore_errors=True)


# ---- the internet ---------------------------------------------------------------------------
def _context():
    """The computer's own list of trusted sites, where Python can use it (truststore)."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001  not installed, or not for this system
        return ssl.create_default_context()


def _open(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": f"ChurchRadioStudio/{paths.version()}",
                                               "Accept": accept})
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=_context())


def _why(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"GitHub answered {e.code} {e.reason}"
    return f"Could not reach GitHub ({getattr(e, 'reason', e)}). Check the internet connection."


def release_info(data, platform=None):
    """What the app needs from GitHub's answer for a release: {"version", "notes", "page", "name",
    "url", "size", "sums_url"}. url is "" if the release has no download for this computer, or
    no SHA256SUMS.txt to check it with."""
    name = ASSETS[platform or _platform()]
    assets = {}
    for a in data.get("assets") or []:
        if isinstance(a, dict):
            assets[str(a.get("name"))] = a
    url = str((assets.get(name) or {}).get("browser_download_url") or "")
    sums = str((assets.get(SUMS) or {}).get("browser_download_url") or "")
    ok = url.startswith(DOWNLOADS) and sums.startswith(DOWNLOADS)
    try:
        size = int((assets.get(name) or {}).get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    page = str(data.get("html_url") or "")
    return {"version": str(data.get("tag_name") or "").lstrip("v"), "notes": str(data.get("body") or ""),
            "page": page if page.startswith(f"https://github.com/{REPO}/") else RELEASES_PAGE,
            "name": name, "url": url if ok else "", "size": size, "sums_url": sums if ok else ""}


def whats_new(notes):
    """The "What's new" part of a release's notes as plain lines (the rest is how to install)."""
    m = re.search(r"^## What's new[^\n]*\n(.*?)(?=^## |\Z)", notes or "", re.S | re.M)
    lines = []
    for line in (m.group(1) if m else "").splitlines():
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line.strip())
        line = line.replace("**", "").replace("`", "")
        if line.startswith("- "):
            lines.append("•  " + line[2:])
        elif line and lines:
            break  # the bullets are over
    return lines


def check(current=None):
    """The newest release if it is newer than this version (see release_info), else None.
    Raises UpdateError when GitHub cannot be asked."""
    try:
        with _open(LATEST_URL, "application/vnd.github+json") as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(_why(e)) from e
    if not isinstance(data, dict):
        raise UpdateError("GitHub's answer could not be read.")
    info = release_info(data)
    latest, mine = version_tuple(info["version"]), version_tuple(current or paths.version())
    if latest is None:
        raise UpdateError("GitHub's answer could not be read.")
    return info if mine is None or latest > mine else None


# ---- the download ---------------------------------------------------------------------------
def expected_sum(sums_text, name):
    """The SHA-256 of `name` in the text of SHA256SUMS.txt ("<64 hex>  <name>" lines), or ""."""
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return ""


def download(update, progress=None, stopped=None):
    """Download the update's file into folder() and check it. Returns its path.
    progress(bytes so far, bytes in all) is called as it comes; stopped() true ends it (Cancelled)."""
    if not update.get("url") or not update.get("sums_url"):
        raise UpdateError("This release has no download for this computer.")
    if not (update["url"].startswith(DOWNLOADS) and update["sums_url"].startswith(DOWNLOADS)):
        raise UpdateError("The download is not from this project's releases: not used.")
    clean()
    os.makedirs(folder(), exist_ok=True)
    path = os.path.join(folder(), update["name"])
    digest, got = hashlib.sha256(), 0
    try:
        with _open(update["sums_url"]) as resp:
            want = expected_sum(resp.read(1024 * 1024).decode("utf-8", "replace"), update["name"])
        if not want:
            raise UpdateError(f"{SUMS} of this release does not list {update['name']}: the download is not used.")
        with _open(update["url"], "application/octet-stream") as resp, open(path + ".part", "wb") as fh:
            total = int(resp.headers.get("Content-Length") or update.get("size") or 0)
            while True:
                if stopped and stopped():
                    raise Cancelled()
                block = resp.read(256 * 1024)
                if not block:
                    break
                got += len(block)
                if got > MAX_BYTES:
                    raise UpdateError("The download is far larger than the app: not used.")
                fh.write(block)
                digest.update(block)
                if progress:
                    progress(got, total)
        if digest.hexdigest() != want:
            raise UpdateError("The download does not match its checksum (it is broken or was changed): "
                              "not used. Try again, or download it from the releases page.")
        os.replace(path + ".part", path)
    except (urllib.error.URLError, OSError, ValueError) as e:
        clean()
        raise UpdateError(_why(e) if isinstance(e, urllib.error.URLError) else f"The download failed: {e}") from e
    except BaseException:
        clean()
        raise
    return path


# ---- putting it in place --------------------------------------------------------------------
def install(path):
    """Start the downloaded update (a file download() returned). Returns what to tell the person;
    the app must then close, so that its files can be replaced."""
    if sys.platform == "win32":
        # ShellExecute, not CreateProcess: the installer may ask Windows for permission.
        os.startfile(path, arguments="/SILENT /RELAUNCH=1")  # noqa: S606  (the file was checked)
        return "The installer is starting. The app closes now and opens again when it is done."
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return ("The new version is open in the Finder. The app closes now: drag ChurchRadio Studio "
                "onto Applications (Replace), then start it again.")
    return _install_linux(path)


def _start(program):
    """Start a program that goes on when this one has closed."""
    subprocess.Popen([program], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def _install_linux(path):
    out = os.path.join(folder(), "unpacked")
    shutil.rmtree(out, ignore_errors=True)
    try:
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(out, filter="data")  # (no file outside the folder, no device files)
    except (tarfile.TarError, OSError) as e:
        raise UpdateError(f"The download could not be unpacked: {e}") from e
    script = os.path.join(out, "ChurchRadio-Studio", "install.sh")
    if not os.path.isfile(script):
        raise UpdateError("The download holds no install.sh: not installed.")
    p = subprocess.run(["sh", script], capture_output=True, text=True, errors="replace", timeout=600)
    if p.returncode != 0:
        raise UpdateError(f"install.sh failed:\n{(p.stderr or p.stdout)[-800:]}")
    program = os.path.join(linux_installed_dir(), "ChurchRadio-Studio")
    _start(program)
    shutil.rmtree(out, ignore_errors=True)
    return "The new version is installed and starting. This window closes now."
