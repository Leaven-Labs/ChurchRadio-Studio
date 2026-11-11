ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.1.0

- **A new look.** Every window has been rebuilt: the main window, Songs, Add songs / Identify, and the setup wizard and Settings. The app does the same things in the same places, with the same button names.
- **Light and dark.** The app follows your computer's light or dark setting. To choose yourself, open **Settings...** and set **The app's look**.
- **You can see what it is doing.** While a broadcast is made, the window names the step (finding the start, finding the end, cutting silences, choosing the songs, writing the MP3) above the log, with a moving bar.
- **Songs list.** Tick boxes turn songs on and off, the public-domain answer is a coloured label (green Yes or Allowed, amber Check, red No), and a title is renamed right in its cell.
- **Service date.** The date box opens a standard month calendar. The "Next Sunday" and "Today" shortcuts of the old calendar are gone: the box already starts on the coming Sunday.
- **Dropping a recording** works on the whole window, not only on the drop area.

Nothing changes in how the broadcast is made, in your settings and song list, or in `--build` for Task Scheduler, cron and launchd.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
