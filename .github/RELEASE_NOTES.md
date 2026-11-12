ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.2.0

- **See where the service is cut.** The Broadcast page draws the recording by its loudness, with the start and the end cut marked: the bright part is broadcast, the dim parts before and after are cut off.
- **Hear the cuts.** **Play from start cut** and **Play to end cut** play the 12 seconds the service will start and end with.
- **Fix a cut that is wrong.** Drag a marker in the picture, or use the small buttons under it (−5 s, −1 s, +1 s, +5 s), then click **Make the broadcast again**. The MP3 is made again with your cuts, without listening for the words a second time, and replaces the first one.
- **Check first, if you like.** Tick **Check the cuts before the MP3 is written** and the app finds the cuts and waits for you to click **Make the broadcast**. It is off unless you tick it, and the tick is remembered.
- **Time left.** While the MP3 is written, the bar fills and Progress says about how long is left.
- The Broadcast page scrolls on a low screen. The line that explains **Start** is hidden once a recording is chosen; it is still the tooltip of the Start box.
- **Linux:** the play buttons use `paplay`, `pw-play`, `aplay` or `ffplay`, whichever is installed (most desktops have one).

Nothing changes in your settings and song list, or in `--build` for Task Scheduler, cron and launchd: scheduled runs never wait for a check.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
