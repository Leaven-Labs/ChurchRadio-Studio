ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.1.1

- **One window, with a menu at the left.** Broadcast, Songs, History and Settings are now pages of the main window. Songs and Settings no longer open as separate windows. (The setup wizard of the first start still does.)
- **Broadcast page.** **Progress** ticks off each step and shows where the start and the end were cut and how much silence was taken out. **The hour** shows the intro, the service and the chosen songs as one bar, to scale, with the songs and their lengths. The log is under **Show the details**; it opens by itself if a broadcast fails.
- **Songs page.** A switch turns a song on or off, a round button plays it, and the **May broadcast** column says **Public domain**, **Allowed**, **Needs permission**, **Check** or **Not found** (before: Yes, Allowed, No, Check, ?). Select a song to see its file, the words heard and the reason under the list, with **Rename**, **Seasons**, **Identify** and **Add permission**. A right-click on the list has every action. The **Words** and **File** columns are gone from the table.
- **History page (new).** The broadcasts you made, with their songs: **Play** one or **Show in folder**.
- **Settings page.** All settings on one page; click **Save** at the top.
- Songs and Settings are shut while a broadcast is being made.

Nothing changes in how the broadcast is made, in your settings and song list, or in `--build` for Task Scheduler, cron and launchd.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
