ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.5.3

- **Silences in the service, on the Settings page.** Under "Service words" you can now say how long a silence must be before it is shortened ("Shorten silences longer than", 5 seconds unless you change it) and how quiet counts as silence. The second is a list in plain words, from "Only complete silence" to "Soft sounds too, such as a murmur or soft organ", with "A quiet room" as the usual choice. If quiet prayers or soft music are cut short, choose a line further up the list.
- **Songs with or without their silence.** A new box under "Songs", "Remove the silence at the start and end of each song", is ticked as before. Untick it to play each song whole.

These three were settings in config.json before; what they do has not changed, and your own values are kept.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
