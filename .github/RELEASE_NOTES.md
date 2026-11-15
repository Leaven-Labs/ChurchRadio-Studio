ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.4.0

- **Zoom into the recording.** Under the picture of the recording: **+** and **−** (or hold **Ctrl** and turn the mouse wheel), **Start cut** and **End cut** to look at a cut from near, and **Whole recording**. Zoomed in, a bar under the picture moves along the recording, and a marker can be dragged to a fraction of a second.
- **Type a cut's time.** The **Start** and **End** boxes under the picture show where the cuts are. Type a time (`9:02`, `9:02.4`, `1:08:15`) and press Enter to put a cut there; empty the box to cut nothing. The app still finds both cuts by itself first, as before.
- **How much is kept at the end.** **Settings → Service words** has two new numbers: the seconds kept after the pastor's last words (5 at first) and after the congregation's answer (0.5 at first).
- **Updates from inside the app.** When the app starts it asks GitHub whether there is a newer version, and the Broadcast page offers **Update now**. On Windows and Linux the new version is downloaded, checked against its checksum and installed over this one, and the app opens again; on a Mac the download is opened for you to drag onto Applications. **About → Check for updates** looks when you ask. To turn the check at the start off: **Settings → Your broadcast → Look for a new version when the app starts**. Only the app's version number is sent.

The first update that can be done from inside the app is the one after 1.4.0: install this version by hand once more. The long date in the file name (`November 15, 2026`) is under **Settings → Your broadcast → Date in the file name → Long**, as since 1.3.0.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
