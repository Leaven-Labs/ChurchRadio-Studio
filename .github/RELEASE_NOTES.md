ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own Windows PC.

## Install

Download **ChurchRadio-Studio-Setup.exe** below and run it. Windows 10 or 11 (64-bit). The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.

Already installed? Run the new installer: it updates in place and keeps your settings, songs and history.

## What's new

- **Make the broadcast automatically with Windows Task Scheduler.** `ChurchRadio-Studio.exe --build "D:\OBS Recordings"` makes the broadcast from the newest recording in the folder, with no window. It skips a recording that's already done or still being written, writes a log of each run, and tells Task Scheduler whether it worked. See [Making it automatically](https://github.com/Leaven-Labs/ChurchRadio-Studio#making-it-automatically-task-scheduler) for the set-up.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the installer's checksum.
