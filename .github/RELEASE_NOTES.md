ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, and now Mac and Linux too.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed on Windows? Run the new installer: it updates in place and keeps your settings, songs and history.

## What's new

- **Mac and Linux.** ChurchRadio Studio now runs on Macs with Apple silicon and on 64-bit Linux, with the same features as on Windows. `--build` works there too, with launchd or cron: see [On a Mac or Linux](https://github.com/Leaven-Labs/ChurchRadio-Studio#on-a-mac-or-linux-launchd-cron).
- **Make the broadcast automatically with Windows Task Scheduler.** `ChurchRadio-Studio.exe --build "D:\OBS Recordings"` makes the broadcast from the newest recording in the folder, with no window. It skips a recording that's already done or still being written, writes a log of each run, and tells Task Scheduler whether it worked. See [Making it automatically](https://github.com/Leaven-Labs/ChurchRadio-Studio#making-it-automatically-task-scheduler) for the set-up.
- **Songs you may broadcast.** A song under copyright can still be cleared for the air. The public-domain check now shows **Allowed** for songs with a Creative Commons license on Wikidata, and **Permission...** lets you record your own permission, such as a CCLI Streaming License or the writer's OK. New **Show** filters list the songs that are allowed to broadcast and the ones that need permission.
- **Identify many songs at once.** **Identify...** can now scan the selected songs, every song without a title, or all your songs, and keeps the titles and seasons you already set.
- **Public-domain check while adding or identifying songs.** Add songs and Identify can look each song up as they go, and save the answer with the song. The button in the Songs window is now called **Check public domain...**.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
