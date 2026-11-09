"""Where the app's files live.

- program_dir(): the installed program (read-only under Program Files).
- bundled_dir(): files shipped with the program (default config.json, hymns.csv, the icon).
- data_dir(): the user's files -- config.json, songs.csv, history.json, end_words.txt, and an
  optional hymns.csv. On Windows %APPDATA%\\ChurchRadio Studio, elsewhere
  ~/.config/churchradio-studio. CHURCHRADIO_DATA_DIR overrides it (for tests, or to keep
  everything in one portable folder).
The speech models live in their own per-PC folder (see prelude.fixed_models_dir).
"""
import os
import sys

APP_NAME = "ChurchRadio Studio"
APP_SLUG = "churchradio-studio"


def program_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundled_dir():
    """A frozen program keeps its bundled files in _MEIPASS (the _internal folder); from
    source they sit next to the code."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return program_dir()


def version():
    """The version of this build (written by the release workflow), or "development"."""
    try:
        with open(os.path.join(bundled_dir(), "version.txt"), encoding="utf-8") as fh:
            return fh.read().strip() or "development"
    except OSError:
        return "development"


def asset(name):
    """A file from the assets folder (the icon)."""
    return os.path.join(bundled_dir(), "assets", name)


def _user_root():
    if sys.platform == "win32":
        return os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(os.path.expanduser("~"), ".config")


def _folder(root, name, slug):
    return os.path.join(root, name if sys.platform == "win32" else slug)


def data_dir():
    """The user's folder for settings and the song catalog. Created on first use."""
    d = (os.environ.get("CHURCHRADIO_DATA_DIR") or "").strip()
    if d:
        os.makedirs(d, exist_ok=True)
        return d
    d = _folder(_user_root(), APP_NAME, APP_SLUG)
    os.makedirs(d, exist_ok=True)
    return d
