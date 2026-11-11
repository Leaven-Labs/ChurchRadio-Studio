<p align="center">
  <img src="assets/icon-256.png" width="128" alt="ChurchRadio Studio icon">
</p>

# ChurchRadio Studio

**Turn your Sunday service recording into a finished radio broadcast — in one drop.**

ChurchRadio Studio is a free Windows app for churches that put their service on the radio (or a
podcast or website). Drop the week's recording on the window and it makes one ready-to-air MP3:

**your intro → the service → songs that fill the rest of the hour**

- **Cuts the organ prelude** (but keeps a choir anthem) by listening for your opening words, such
  as *"Good morning"*.
- **Ends the service at the congregation's answer** to the dismissal: *"Go now in peace." —
  "Thanks be to God."*
- **Shortens long silences**, and plays the songs **back to back with no gaps**.
- **Fills the time** to your broadcast length (never more than 30 seconds over) with your own songs
  that **fit the church year** — Advent through Pentecost, plus patriotic songs on national holiday
  weekends. Songs used in recent weeks go last.
- **Evens out the sound** with a broadcast compressor and limiter.

Everything runs **on your own PC**. The speech recognition is downloaded once and then works
offline. Nothing about your services leaves the PC; the only thing that ever does is a song's title,
when you click **Public domain...** to look songs up.

Created by **Aaron Steger** for **Bethany Lutheran Church**, Fredericksburg, Texas, and its weekly
radio broadcast, and shared so other congregations can use it. Published by
[Leaven Labs](https://leavenlabs.org) under the [MIT License](LICENSE). Developed with the help of
[Claude Code](https://claude.com/claude-code).

---

## Contents

- [Install](#install)
- [First start: the setup wizard](#first-start-the-setup-wizard)
- [Making the broadcast each week](#making-the-broadcast-each-week)
- [Making it automatically (Task Scheduler)](#making-it-automatically-task-scheduler)
- [How the cuts work](#how-the-cuts-work)
- [Your songs](#your-songs)
- [Settings](#settings)
- [Where your files are](#where-your-files-are)
- [Updating](#updating)
- [Troubleshooting](#troubleshooting)
- [For developers](#for-developers)
- [Third-party software](#third-party-software)
- [Reporting a security problem](#reporting-a-security-problem)
- [License and credits](#license-and-credits)

---

## Install

You need a 64-bit Windows 10 or 11 PC — nothing else (ffmpeg is included).

1. Download **`ChurchRadio-Studio-Setup.exe`** from the **[Releases](../../releases)** page.
2. Run it. Choose **Install for me only** if you are not an administrator on the PC.
3. **"Windows protected your PC"?** The installer isn't code-signed yet: click **More info** →
   **Run anyway**.

It adds the app to the Start menu (and the desktop, if you tick it) and an uninstaller under
**Settings → Apps**. The first start needs **internet once** to download the speech models (about
620 MB); after that the app works offline.

## First start: the setup wizard

A short wizard sets the app up for your church. You can change everything later in **Settings...**.

1. **Welcome.**
2. **Broadcast** — your program's name (used in the file name, e.g. `St. John Radio 2026-11-15.mp3`),
   the broadcast length, how far over it may run, and where to save the MP3 (empty = next to the
   recording).
3. **Intro** — the intro that plays first (with **Play**), or none.
4. **Songs** — the folders that hold your songs (folders inside them are included).
5. **Service words** — the opening words, the pastor's last words and the congregation's answer, as
   they are said in your church; and which national holidays get patriotic songs.
6. **Speech models** — download them now, or let the first broadcast do it.
7. **Done** — a summary. Click **Finish**.

## Making the broadcast each week

1. Start **ChurchRadio Studio**.
2. **Drop the recording on the window** (MKV, MP4, WAV, MP3 or M4A) or on the program's icon, or
   click **Browse...**.
3. Watch the log. It takes a few minutes: about 30 seconds to find the start, 1 to 3 minutes to find
   the end, then joining and compressing.
4. The app tells you where the MP3 was saved.

To have Windows do this every week with no one at the PC, see
[Making it automatically](#making-it-automatically-task-scheduler).

**The service date** sets the church season. The window shows the coming Sunday (today, on a
Sunday); click it to pick another date from a calendar. If you don't, a date in the file name is
used — `10.11.2026`, `10-11-2026` (month first) or `2026-10-11`.

**Options in the window:**
- **Service start** — **Auto** (cut the organ prelude, keep a choir anthem), **Organ start** (always
  cut at the opening words) or **Keep start** (cut nothing, e.g. for a bell-choir prelude).
- **End the service at "…"** — untick to keep everything after the service.
- **Compress the final MP3** — untick to skip the broadcast compressor.

**Too long?** If the intro and service alone are longer than the broadcast, no songs are added. The
MP3 is still saved, with a warning saying by how much, so you can trim it by hand (e.g. in Audacity).

## Making it automatically (Task Scheduler)

With `--build`, the app makes the broadcast with **no window**, so Windows Task Scheduler can run it:

```bat
"C:\Program Files\ChurchRadio Studio\ChurchRadio-Studio.exe" --build "D:\OBS Recordings"
```

`--build` takes a recording or a **folder**. With a folder it uses the newest recording, and does
nothing if that recording's MP3 is already made or it changed in the last 10 minutes (still recording
or copying — the next run picks it up). It uses your Settings, like the window.

**Service date:** the date in the file name, else the day it was recorded — so a Monday run still
uses Sunday's season and songs.

**Options** (for one run only):

| Option | What it does |
|---|---|
| `--date 2026-11-15` | Use this service date. |
| `--start "Keep start"` | `Auto`, `Organ start` or `Keep start`. |
| `--keep-end` | Keep everything after the end of the service. |
| `--no-compress` | Skip the broadcast compressor. |
| `--force` | Make the broadcast again even if its MP3 is already there. |
| `--dry-run` | Only log which recording and date it would use — for checking the set-up. |
| `--settle 30` | Skip a recording changed in the last 30 minutes (default 10). |
| `--log "D:\Radio\last run.log"` | Write the log here. |

**Results:** each run writes a log to `logs\` in [your settings folder](#where-your-files-are) (the
newest 30 are kept). Task Scheduler shows the exit code as **Last Run Result**: `0` done or nothing to
do, `1` failed (see the log), `2` done but too long — edit the MP3 by hand. Only one broadcast is made
at a time: a scheduled run stops (exit 1) if the window is making one, and the other way round.

**Set it up** (finish the app's setup first):

1. Open **Task Scheduler** → **Create Task...**.
2. **General:** a name such as *ChurchRadio Studio broadcast*, under **your own Windows account**
   (settings and songs are kept per account). *Run only when user is logged on* is simplest; with
   *Run whether user is logged on or not*, use `\\server\share` paths, not mapped drive letters.
3. **Triggers:** **Weekly**, e.g. **Sunday 2:00 PM**, after the recording has finished.
4. **Actions:** **Start a program** — *Program:* `C:\Program Files\ChurchRadio Studio\ChurchRadio-Studio.exe`,
   *Arguments:* `--build "D:\OBS Recordings"`.
5. **Settings:** tick **Stop the task if it runs longer than 2 hours**.

Or from a Command Prompt:

```bat
schtasks /Create /TN "ChurchRadio Studio broadcast" /SC WEEKLY /D SUN /ST 14:00 /TR "\"C:\Program Files\ChurchRadio Studio\ChurchRadio-Studio.exe\" --build \"D:\OBS Recordings\""
```

Test it with right-click → **Run**, then read the newest log. If you installed for yourself only, the
program is in `%LOCALAPPDATA%\Programs\ChurchRadio Studio\`.

## How the cuts work

Speech recognition ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)) finds the words that
start and end the service, allowing for small mistakes. The log lists every match heard, with its
time and how sure it was, so you can check a cut.

**Start.** The app searches the first 30 minutes for your opening words (default *"Good morning"*)
and cuts just before them.
- Chatter near the microphone during the prelude is sometimes heard as "Good morning", but less
  surely than the pastor at the microphone: an unsure match is skipped when a surer one follows
  within 5 minutes.
- In **Auto**, a choir piece that follows a short pause before the opening words is kept; only the
  organ before the pause is cut.
- If the words aren't heard, nothing is cut.

**End.** The app searches the last 10 minutes, with a more exact model, for the pastor's last words
(default *"Go now in peace"*) and the answer (default *"Thanks be to God"*), and cuts just after the
answer if it comes within 20 seconds — otherwise a few seconds after the pastor's words. An earlier
"Thanks be to God" (after a reading) is never used. The words heard are saved to `end_words.txt`.

**Silences.** Silences in the service longer than 5 seconds are shortened. Silence at the start and
end of each song, and at the end of the service, is removed, so there are no gaps.

## Your songs

**Songs...** lists every song with its title, seasons, length and how many words were heard in it.
Every change is saved at once.

- **On / off** — click the tick in the **On** column, or select several and click **Turn on** /
  **Turn off**. Songs that are off are never used.
- **Rename** — double-click the title.
- **Seasons** — double-click the seasons and tick when the song may play. None = **General** (any
  time). Holy Week also uses Lent songs. **Patriotic** songs play only on the weekend nearest a
  holiday you chose, and then come first.
- **Play** — opens the song in your music player.
- **Find** / **Show** — search by name, or show only songs that are on, off, have no words, are in
  the public domain, are allowed to broadcast (public domain, a free license or your permission),
  need permission, or haven't been looked up yet.
- **Look for new songs** — scan your song folders again.

### Add songs

**Songs... → Add songs...** and pick the files (from a USB stick, a download folder, anywhere). For
each one the app suggests a **title** and **seasons** from:

1. the file's **tags**, if they hold a real title (not "Track 03");
2. else the **lyrics** — it listens to the start of the song and matches the words against about 140
   well-known hymns and songs (first lines and refrains), even with a few words misheard;
3. else the **file name**.

A table shows each suggestion, how it was found and the words heard; unsure ones are orange. Correct
anything, untick songs you don't want, choose the folder for them, and click **Add**: the files are
copied there and added to your list.

The tick box **Also check whether each song is in the public domain** (on by default; needs the
internet) runs the [public-domain lookup](#public-domain) on each song as it is identified, shows the
answer in the table and saves it with the song. You can tick or untick it at any time: ticking it
looks up the songs already done too.

**Identify...** does the same for songs already in your list. Choose the songs: the ones you
selected, every song without a title, or **all songs** (a bulk scan). Two options:

- **Keep the titles and seasons songs already have** (on by default) — only songs with no title get a
  suggestion. The others are still listened to, and if their words sound like another hymn, the
  **Found by** column says so.
- **Also check whether each song is in the public domain** — the same tick box as in Add songs,
  for one song or many. If you rename a song in the table, it is looked up again. Offline, the scan
  carries on without it.

Listening takes a few seconds per song, so a bulk scan of a large list can take a while.

### Import a song list

**Songs... → Import list...** adds many songs at once from a CSV file, or changes the titles, seasons
and on/off of songs already in your list. Click **Download template...**, fill it in Excel (save as
CSV), then click **Import a file...**. Columns:

- `file` — the song's full path, or just its file name if it is in one of your song folders;
- `title` — the song name;
- `seasons` — [season words](#teach-it-your-own-songs) separated by `;` (`Holy Week` and `General`
  also work); empty or `general` = any time;
- `enabled` — `yes` or `no`;
- `permission` — why you may broadcast the song, if it isn't in the public domain (for example
  `CCLI Streaming License 123456`). See [Public domain](#public-domain).

For a song already in the list, an empty cell keeps what is there. A new song with no seasons gets
them guessed from its file and folder name. Files are not copied; they stay where they are. Lines that
can't be used (file not found, unknown season) are skipped and listed.

### Public domain

**Songs... → Public domain...** looks up each title on [Wikidata](https://www.wikidata.org) (free,
open data) and fills the **Public domain** column — for the selected songs, or with none selected,
every song not looked up yet. It needs the internet and takes a second or two per song; **Stop** keeps
the songs already done.

- **Yes** — public domain in the US: published before 1931 (the year moves on each January).
- **Allowed** — under copyright, but you may broadcast it: Wikidata lists a Creative Commons license
  for it (give the credit it asks for), or you gave a permission (below). A NonCommercial license
  shows **Check** instead, since it covers only non-commercial use.
- **No** — under copyright.
- **Check** — the original is old, but a newer version may be the one sung: "How Great Thou Art" is
  Swedish from 1885, but the English version is from 1949. Also shown when only an original in
  another language was found, when only part of the title matched ("Amazing Grace (My Chains Are
  Gone)"), or when Wikidata's dates disagree.
- **?** — not found, or no dates to go on.

**Permission...** — if you have permission to broadcast songs that are under copyright (a
streaming or radio license such as CCLI's, your station's ASCAP/BMI/SESAC licenses, or the writer's
OK), select them, click **Permission...** and type what it is (for example `CCLI Streaming License
123456`). They then show as **Allowed**, and the lookup never removes it. Leave it empty to take it
off. You can also fill the `permission` column in an [imported list](#import-a-song-list).

Click a song to see the reason under the list. Offline, songs in the app's own hymn list are still
marked (it holds lyrics only for public-domain hymns).

This is a guide, not legal advice. It judges the **song** (words and tune), not the **recording**: a
modern recording or arrangement of an old hymn is still protected.

### Songs with no words

Instrumentals don't usually suit the radio filler. The first time a song is used, the app counts the
words in it; a song with fewer than 6 is turned off, and the log says so. This happens once per song:
turn one back on and it stays on.

### Teach it your own songs

The app recognises songs from its hymn list, `hymns.csv`. To add your own — a choir piece, a local
favourite — create a `hymns.csv` in [your settings folder](#where-your-files-are):

```csv
title,first_line,also,seasons
Our Parish Song,We gather on the prairie wide,Alleluia to the Lord of harvest,
Lo How a Rose E'er Blooming,Lo how a rose e'er blooming,,advent;christmas
```

`also` is another line, such as the refrain. `seasons` uses the words below, separated by `;` (empty =
General). A song with the same title as one in the app's list replaces it. A song listed by title only
(empty `first_line` and `also`) is recognised when its title is sung, for example in the refrain.

The app's list has lyric lines only for public-domain hymns; newer songs are listed by title only.

**Season words:** `advent`, `christmas`, `epiphany`, `lent`, `holyweek`, `easter`, `pentecost`,
`patriotic`.

## Settings

Most settings are in **Settings...**. All of them are in `config.json` in your
[settings folder](#where-your-files-are); edit it in Notepad for the rest (close the app first).

| Setting | Default | What it does |
|---|---|---|
| `broadcast_name` | `Church Radio` | Name in the MP3 file name and title. |
| `intro` | (none) | The intro file. Empty = no intro. |
| `song_folders` | (none) | Folders with your songs (folders inside them are included). |
| `output_folder` | (none) | Where to save the MP3. Empty = next to the recording. |
| `target_minutes` | `60` | Broadcast length. |
| `tolerance_seconds` | `30` | The songs never make it more than this much longer. |
| `service_start` | `Auto` | `Auto`, `Organ start` or `Keep start`. |
| `start_phrase` | `Good morning` | Words that start the service. |
| `start_min_sure` | `0.75` | An earlier "Good morning" less sure than this (75 %) is skipped. `0` = always use the first. |
| `start_skip_minutes` | `5` | …but only if a surer one follows within this time. |
| `end_phrase` | `Go now in peace` | The pastor's last words. Empty = nothing cut at the end. |
| `end_answer_phrase` | `Thanks be to God` | The congregation's answer; the cut is right after it. Empty = no answer. |
| `end_answer_window` | `20` | The answer must start within this many seconds. |
| `end_answer_pad` | `0.5` | Seconds kept after the answer. |
| `end_alt_phrase` | `and we will` | If the answer isn't heard: cut right after these words, if heard soon after. |
| `end_alt_window` / `end_alt_pad` | `20` / `0.5` | As above, for `end_alt_phrase`. |
| `end_after_seconds` | `5` | If neither is heard: cut this long after the pastor's last words. |
| `end_search_minutes` | `10` | How much of the end is searched. |
| `max_silence_seconds` / `silence_level_db` | `5` / `-40` | Silences in the service longer and quieter than this are shortened. |
| `trim_song_silence` / `song_silence_db` | `true` / `-50` | Remove silence quieter than this at the start and end of songs. |
| `check_song_words` / `song_min_words` | `true` / `6` | Turn off songs with fewer words than this (once per song). |
| `avoid_repeat_weeks` | `4` | Songs used in this many recent broadcasts go last. |
| `patriotic_holidays` | `memorial`, `independence`, `veterans` | Weekends that get patriotic songs. `labor` is also possible. |
| `mp3_bitrate` | `192k` | MP3 quality. |
| `compression` | 4:1 above -18 dB, +6 dB, limit -1 dB | `enabled`, `ratio`, `threshold_db`, `attack_ms` (20), `release_ms` (250), `makeup_db`, `limit_db`. |
| `models_folder` | (none) | A folder that already holds the speech models. |
| `setup_done` | `false` | Set to `false` to see the setup wizard again. |

**Song list (`songs.csv`)** — edited by the Songs window, or open it in Excel. Columns: `file`,
`title`, `duration`, `seasons`, `enabled` (`yes`/`no`), `words` (empty = not checked yet),
`start_silence` / `end_silence` (seconds; empty = not measured yet), `public_domain`
(`yes`/`allowed`/`no`/`check`/`unknown`; empty = not looked up), `pd_note` (why) and `permission`
(why you may broadcast it; empty = none). If a song folder can't be
found (moved, or a drive not plugged in), its songs stay in the list with your edits.

## Where your files are

| What | Where |
|---|---|
| The program (and ffmpeg) | `C:\Program Files\ChurchRadio Studio` (or `%LOCALAPPDATA%\Programs\ChurchRadio Studio` if installed for you only) |
| Your settings, song list, history, `end_words.txt`, your `hymns.csv`, logs of scheduled runs (`logs\`) | `%APPDATA%\ChurchRadio Studio` |
| The speech models (one copy per PC) | `C:\ProgramData\ChurchRadio Studio\models` |

To open your settings folder, paste `%APPDATA%\ChurchRadio Studio` into the File Explorer address bar.
Uninstalling removes only the program; your settings and the models stay for a reinstall.

## Updating

Run the newest `ChurchRadio-Studio-Setup.exe` from the **[Releases](../../releases)** page. It updates
in place, keeps your settings, songs and history, and uses the speech models already on the PC.

## Troubleshooting

**The cut at the start or end is wrong.** The log lists every start and end phrase heard, with its
time and how sure it was. Check that your **Service words** (Settings) match what is actually said,
and the **Service start** mode. Send `end_words.txt` from your settings folder if you ask for help.

**The MP3 is too long.** The intro and service alone are longer than the broadcast, so no songs were
added. Trim it by hand, or raise the broadcast length.

**A song keeps being chosen that shouldn't be.** In **Songs...**, turn it off or change its seasons.

**The scheduled broadcast wasn't made.** Open the newest log in `%APPDATA%\ChurchRadio Studio\logs`:
- *Nothing to do* — the newest recording's MP3 was already there, the recording was still being
  written (the next run makes it), or the folder had no recordings: check the folder in the task.
- *Open ChurchRadio Studio once and finish the setup first* — the task runs under a different Windows
  account from the one you set the app up with. Use your own account.
- *Not found* — the folder can't be reached. Mapped drive letters may not exist when no one is
  logged on: use a `\\server\share` path, or *Run only when user is logged on*.
- *Another broadcast is being made right now* — the window was making one at the same time.
- **No new log at all** — the task didn't start: check its trigger and its **History** tab.

To check the set-up without making anything, run the task's command with `--dry-run` added.

**The speech models won't download.** The first start needs internet once (about 620 MB). On a PC
without internet, copy the `models` folder from another PC into `C:\ProgramData\ChurchRadio Studio\`,
or set `models_folder` to a folder that holds them.

**Check the installation without opening the window:**

```
"C:\Program Files\ChurchRadio Studio\ChurchRadio-Studio.exe" --selftest
```

It prints where the program, your files, ffmpeg and the models are, loads both models, and ends with
`selftest: OK`.

## For developers

Python 3.11+ with tkinter.

**Run from the source code**

```
pip install -r requirements.txt
python app.py
```

ffmpeg must be in an `ffmpeg` folder next to the code, on `PATH`, or in `C:\ffmpeg\bin`. Set
`CHURCHRADIO_DATA_DIR` to keep the settings in a test folder instead of your real one.

**Run the tests**

```
python -m unittest discover -s tests
```

**Build and release.** `.github/workflows/release.yml` runs on Windows for every pull request and
release: the tests, the program folder (PyInstaller, `ChurchRadio-Studio.spec`), an LGPL ffmpeg
build, and the installer (Inno Setup, `installer.iss`). It then installs it, self-tests it, makes a
headless test broadcast, tests an update from the previous release, and uninstalls it. The installer
is attached to the run. To publish, run the **Release** workflow from the Actions tab with a version
such as `v1.0.0` (or push a tag `v…`).

**Where things are**

| File | What it is |
|---|---|
| `app.py` | The main window (and `--build` / `--selftest` from the command line). |
| `cli.py` | `--build`: making the broadcast with no window, for Task Scheduler. |
| `datepicker.py` | The service date box and its pop-out calendar. |
| `setup_wizard.py` | The setup wizard, also used by **Settings...**. |
| `songs_window.py` | The Songs window. |
| `add_songs.py` | Add songs / Identify: the review table and saving. |
| `builder.py` | Makes one broadcast: intro + service + songs. |
| `prelude.py` | Speech recognition: finding the start and end of the service. |
| `audio.py` | ffmpeg: lengths, silence, trimming, joining, compression. |
| `picker.py` | Picks the songs that fill the time. |
| `catalog.py` | The song list (`songs.csv`), seasons, songs with no words, importing a song list. |
| `pdlookup.py` | The public-domain lookup (Wikidata, then the app's hymn list). |
| `identify.py` | Finds a song's title and seasons from tags, lyrics or file name. |
| `hymns.csv` | The hymn list used to recognise songs. |
| `churchyear.py` | The church year, patriotic holiday weekends, the default service date. |
| `paths.py` | Where the program, its defaults and the user's files are. |
| `config.json` | Default settings (copied to the user's folder on first start). |
| `assets/` | The icon (`icon.svg` is the source; `icon.ico` and `icon-256.png` are made from it). |
| `ChurchRadio-Studio.spec` | PyInstaller recipe. |
| `installer.iss` | Inno Setup recipe for the installer. |
| `ChurchRadio Studio.bat` | Starts the app from the source code on Windows. |
| `tools/third_party_licenses.py` | Collects the third-party licenses for the installer. |
| `LICENSE` | The MIT License. |
| `tests/` | The tests (`test_core.py`) and saved Wikidata answers they use. |

## Third-party software

The installer includes the software below. The full license texts are installed in the program's
`licenses` folder (**About → Licenses**), collected by `tools/third_party_licenses.py` at each build
from what the program actually includes.

- **[FFmpeg](https://ffmpeg.org)** — reading, trimming and encoding audio. An unchanged LGPL build
  (from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds)), with its license, in the
  `ffmpeg` folder; the app runs it as a separate program.
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** (MIT) with
  **[CTranslate2](https://github.com/OpenNMT/CTranslate2)** (MIT), and the **Whisper** speech models
  `base.en` and `small.en` (MIT), downloaded on first use.
- **[tkinterdnd2](https://github.com/Eliav2/tkinterdnd2)** (MIT) — drag and drop.
- **[NumPy](https://numpy.org)** (BSD), **[PyAV](https://github.com/PyAV-Org/PyAV)** (BSD), Hugging Face
  **huggingface_hub** and **tokenizers** (Apache 2.0), **ONNX Runtime** (MIT), and their dependencies.
- **Python** (PSF License) and **Tcl/Tk** (BSD-style), built into the program.

## Reporting a security problem

Please don't open a public issue. See [SECURITY.md](SECURITY.md) for how to report it privately.

## License and credits

Free software under the **[MIT License](LICENSE)**: anyone may use, copy, change and share it,
including for other churches, as long as the copyright notice and license are kept with it.

Copyright (c) 2026 **Aaron Steger**. Published by **[Leaven Labs](https://leavenlabs.org)**. The
app's **About** box shows the author, publisher, version and license.
