ChurchRadio Studio turns your Sunday service recording into a finished radio broadcast: your intro, the service with the organ prelude and the end trimmed, and songs from your own collection that fit the church year and fill the rest of the hour. Everything runs on your own computer: Windows, Mac and Linux.

## Install

The first start downloads the speech-recognition models once (about 620 MB); after that the app works offline. ffmpeg is included.

- **Windows 10 or 11 (64-bit):** download **ChurchRadio-Studio-Setup.exe** below and run it. Windows may say "Windows protected your PC" because the installer is not code-signed yet: click **More info → Run anyway**.
- **Mac with Apple silicon (M1 or newer), macOS 14 (Sonoma) or newer:** download **ChurchRadio-Studio-macOS.dmg**, open it and drag ChurchRadio Studio onto Applications. The app is not signed with an Apple developer ID yet, so the first time macOS says it can't check it: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.
- **Linux, 64-bit (Ubuntu 22.04 or newer, or similar):** download **ChurchRadio-Studio-Linux-x86_64.tar.gz**, unpack it and run `ChurchRadio-Studio/install.sh`. It installs for you only, no `sudo` needed, and adds the app to your applications menu.

Already installed? Install the new version over the old one: it keeps your settings, songs, history and the speech models.

## What's new in 1.5.2

- **The look of the website, in the app.** Its gradient of navy, blue and green, with gold for a spark, is on a line along the top of the window, the main buttons, the switches of the Songs page, the progress bar and the page titles, and the headings are in the website's typeface. Where things are and what they do has not changed.
- **A soft glow** under the main buttons and under the card of the finished broadcast.
- **Small animations.** A page fades in and a band of gold light crosses its title; the menu's marker slides; The hour fills once behind a gold needle; and a light runs along the top line while a broadcast is being made.
- **Settings → Small animations** switches them off for a still window (`motion` in config.json). Nothing moves while the window is not shown.

The new look passed the automated tests but has not yet been seen on a real Windows PC or Mac. Please report anything that looks wrong or feels slow.

See the [README](https://github.com/Leaven-Labs/ChurchRadio-Studio#readme) for how to use it. `SHA256SUMS.txt` holds the checksums of the three downloads.
