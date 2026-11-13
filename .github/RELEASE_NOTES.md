ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.3.0

- **Cancel.** A **Cancel** button next to the progress bar stops a broadcast that is being made, at once or after a few seconds. Nothing is saved, and cuts that were already found are kept.
- **The finished broadcast on the page.** Instead of a pop-up, a card shows the MP3 with its length and folder, with **Play** and **Show in folder**. If the broadcast is too long, the card says by how much.
- **Close-ups of the cuts.** Under the picture of the recording, each cut is shown from near (the 40 seconds around it). Click or drag there to put a cut in the pause between two words, exact to a tenth of a second.
- **The date in the file name.** **Settings → Your broadcast → Date in the file name**: choose **Short** (`2026-11-15`, `11-15-2026`, `15.11.2026`, `20261115` and more) or **Long** (`November 15, 2026`, `15 Nov 2026`, `Sunday, November 15, 2026` and more). The file name stays as it was until you change it.
- **The MP3's title now writes the date the same way as the file name**: `Church Radio Broadcast 2026-11-15`, where it was `11/15/2026`.
- **No half-written MP3.** The MP3 gets its name only when it is whole. A run that fails or is stopped leaves no file that a scheduled run would take for a finished broadcast, and does not damage the broadcast made before.

If the computer makes the broadcast by itself (`--build`): it knows a broadcast is made by its file name. After you change the date format, the next run makes the newest recording's broadcast once more, under the new name.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
