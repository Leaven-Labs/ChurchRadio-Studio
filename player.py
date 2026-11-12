"""Play a short piece of the recording from the window: the seconds after the start cut, or
before the end cut.

ffmpeg writes the piece as a small WAV (audio.cut_clip); it is played with what the system
already has, so nothing is added to the download: Windows itself (winsound), afplay on a Mac,
and on Linux the first of paplay, pw-play, aplay or ffplay that is installed.
"""
import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import time

import audio

LINUX_PLAYERS = (["paplay"], ["pw-play"], ["aplay", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"])


class NoPlayer(RuntimeError):
    """This computer has no program the app can play a sound with."""


def player_command():
    """The command that plays a WAV on a Mac or Linux (the file name is added). Raises NoPlayer."""
    if sys.platform == "darwin":
        return ["afplay"]
    for cmd in LINUX_PLAYERS:
        if shutil.which(cmd[0]):
            return cmd
    raise NoPlayer("No sound player was found. Install pulseaudio-utils (paplay) or alsa-utils (aplay).")


class Player:
    """Plays one piece at a time. play() stops the piece before; stop() is safe at any time."""

    def __init__(self):
        self.folder, self.proc, self.until, self.count = None, None, 0.0, 0
        atexit.register(self.close)

    def clip_path(self):
        """A new file name each time: Windows keeps the file it is playing open."""
        if self.folder is None:
            self.folder = tempfile.mkdtemp(prefix="churchradio_play_")
        for f in os.listdir(self.folder):  # the pieces played before
            try:
                os.remove(os.path.join(self.folder, f))
            except OSError:
                pass
        self.count += 1
        return os.path.join(self.folder, f"piece{self.count}.wav")

    def play(self, src, start, seconds):
        """Play `seconds` of the recording from `start`. Returns when the sound has started (the
        cutting takes a moment: call it from a background thread)."""
        self.stop()
        clip = audio.cut_clip(src, self.clip_path(), start, seconds)
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(clip, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        else:
            self.proc = subprocess.Popen(player_command() + [clip], stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
        self.until = time.time() + seconds

    def playing(self):
        if self.proc is not None and self.proc.poll() is not None:
            self.proc, self.until = None, 0.0
        return time.time() < self.until

    def stop(self):
        self.until = 0.0
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:  # noqa: BLE001  nothing was playing, or no sound device
                pass
        if self.proc is not None:
            try:
                self.proc.terminate()
            except OSError:
                pass
            self.proc = None

    def close(self):
        self.stop()
        if self.folder:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.folder = None
