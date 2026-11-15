ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.5.0

- **Listen anywhere in the recording.** Click in the picture of the recording to put a play marker there, or drag it along. **Play** under the picture plays from the marker and **Pause** stops it there; the marker moves as it plays, and a click somewhere else goes on from there. The time next to **Play** says where the marker is.
- **The space bar plays and pauses** on the Broadcast page.
- **The close-ups of the cuts are gone.** The two small pictures under the recording took room and are not needed since the picture itself zooms in (1.4.0): zoom in with **+**, **Start cut** or **End cut** to place a cut to a tenth of a second.
- Zoomed in, a drag in the picture now moves the play marker. To move along the recording, use the bar under the picture or hold **Shift** and turn the mouse wheel.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
