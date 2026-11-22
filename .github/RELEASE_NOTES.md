ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.6.0

- **Even loudness.** The intro, the service and each song are now made equally loud, so a quiet sermon and a loud CD play at the same level, and the whole MP3 is brought to the same level every week. **This is on for everyone, also when you update**: your MP3 comes out at −16 LUFS (the usual level for podcasts and web radio), which may be a little louder or quieter than before. To choose another level, or to turn it off, use **Loudness** on the Settings page: −14 (loud, like music streaming), −16, −18, −23 (the European broadcast standard, EBU R128), −24 (the US broadcast standard, ATSC A/85), or "Not evened out". Ask your station if it wants a level. Making the MP3 takes a little longer, because the broadcast is read once more before it is written; each song is measured only the first time it is used.
- **A cue sheet next to the MP3.** Each broadcast now also saves `<name> cue sheet.csv` beside the MP3. It opens in Excel and lists the intro, the service and each song: where it starts and ends in the MP3, its title and file, and whether the song may be broadcast, with the permission you typed for it. Give it to your station, or keep it for license reports such as CCLI's. The **Cue sheet** button on the finished broadcast opens it. If the folder you save MP3s in is one your station collects them from, the CSV will be there too; untick **Save a cue sheet next to the MP3** in Settings if you don't want it.
- **The cuts are remembered.** Choose the same recording again (after closing the app, say) and its cuts come back at once, without listening again. Cuts you moved by hand are always used, also by scheduled runs; **Listen again** forgets them and listens. For scheduled runs there is `--listen-again`.
- **Keys and buttons for the cuts.** Click a cut (or press Tab) and move it with ← and → (with Shift, 5 seconds). Press **S** or **E**, or click **Start cut here** / **End cut here**, to put a cut at the play marker: listen until the pastor starts, pause, and press **S**.
- **A smaller download.** ffmpeg is now built for the app from its source code on Windows and Linux too, with only what the app needs. The Windows installer is about 92 MB instead of 164 MB, and the Linux download about 208 MB instead of 308 MB.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
