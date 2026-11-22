# Notes for Claude

## Remind the maintainer: planned for 1.0.6

At the start of any session that works toward the 1.0.6 release, remind the maintainer about this
item. Remove it from this file once it is built.

- **Option C, recording copyright warning (from file tags).** When songs are added, identified or
  imported, read the copyright and year tags of the file (e.g. ID3 `TCOP` "℗ 2015 Some Label", `TDRC`;
  MP4 `cprt`; Vorbis `COPYRIGHT`). `identify.read_tags` already reads tags. Use them only to *warn*
  ("this recording looks copyrighted"), never to confirm public domain: a public-domain hymn in a
  modern recording or arrangement is still protected, and tags are often missing or wrong. Goes with
  the public-domain lookup (option D, an online lookup), which judges the song, not the recording.

## Release plan (decided November 2026)

- **1.1.0 (released): the windows are Qt (PySide6), on the same Python code.** `ui.py` holds the look
  (light and dark), `mainwindow.py` the main window; `--uitest` makes every window once, off screen,
  and the release workflow runs it on the installed program. Tkinter, tkinterdnd2 and sv-ttk are gone.
- **1.1.1 (released): stage 1 of the new look (below).**
- **1.2.0 (released): stages 2 and 3 of the new look (below).**
- **1.3.0: Cancel, the result card, close-ups of the cuts, the date format, no half-written MP3.**
  `.github/RELEASE_NOTES.md` and the workflow's default tag are set for it. To release: merge, then
  run the Release workflow (or push `v1.3.0`).
  - Cancel: `audio.Stopper` / `audio.stoppable` stop the work of the build's thread; every ffmpeg run
    goes through `audio.run_tool` so it can be ended, and the speech loops call `audio.check_stop`.
    `audio.Stopped` is a BaseException on purpose (see its docstring). New ffmpeg calls in the build
    must use `run_tool`, not `subprocess.run`.
  - Date format: `date_format` in config.json, `builder.DATE_FORMATS` / `format_date`. It is used for
    the MP3's file name and title only (not the log, the History page or the recording's file name).
  - Close-ups: `ui.CloseUp`, fed by `audio.loudness_picture` (the outline and 20 numbers a second).
- **The new look (a mockup the maintainer gave, November 2026) was built in three stages.** Stage 1
  (released in 1.1.1): one window with a menu at the left, the Songs table, "The hour" bar and the
  progress list (`builder.build(tell=...)` gives the numbers). Stages 2 and 3 (1.2.0): the card "Where the service is cut" (`audio.loudness_outline`, `ui.Waveform`) with cuts
  that are dragged or nudged; "Play from start cut" / "Play to end cut"; "Check the cuts before the
  MP3 is written" (`review_cuts` in config.json; `builder.find_cuts`, then
  `builder.build(cuts=...)`; `cli.py` still builds in one pass); and the time left while the MP3 is
  written (`audio.join_to_mp3(progress=...)`).
  - Playing uses no Qt sound module, to keep the download small: `player.py` has ffmpeg cut a WAV
    and plays it with winsound (Windows), afplay (Mac) or paplay / pw-play / aplay / ffplay (Linux).
    Not yet heard on a real Windows PC or Mac.
  - Not built: the notes in the mockup's cut labels ("choir kept", the words found), and marks for
    the long silences cut out of the middle.
- **1.4.0: zoom, typed cut times, the end timing in Settings, updates from inside the app.**
  `.github/RELEASE_NOTES.md` and the workflow's default tag are set for it. To release: merge, then
  run the Release workflow (or push `v1.4.0`).
  - Zoom: `ui.Waveform.view` (None = the whole recording), `zoom` / `zoom_to` / `show_part`; drawn from
    the 20-a-second numbers when closer than the outline. Typed times: `ui.parse_clock`,
    `Waveform.place`, `MainWindow.cut_typed`.
  - End timing: `end_after_seconds` and `end_answer_pad` are fields of the Settings page now
    (`end_alt_pad` follows `end_answer_pad` unless config.json gives it its own value).
  - Updates: `updates.py` (no Qt), `mainwindow.UpdateBanner`. The check at the start is ON unless
    `check_updates` is false (the maintainer asked for it, November 2026); it is skipped from source
    and in dev builds (`updates.is_release`). Only this repository's release files are taken, and
    only if they match `SHA256SUMS.txt`: keep the asset names in `updates.ASSETS` and the release
    workflow the same. Windows runs Setup with `/SILENT /RELAUNCH=1` (`installer.iss` starts the app
    again); Linux runs the download's `install.sh`; the Mac only opens the DMG.
  - Not yet tried on a real Windows PC, Mac or installed Linux: the install step (`updates.install`).
    The download, the checksum and the Linux unpack-and-install are covered by tests.
- **1.5.0: the play marker, Play / Pause and the space bar; the close-ups are removed.**
  `.github/RELEASE_NOTES.md` and the workflow's default tag are set for it. To release: merge, then
  run the Release workflow (or push `v1.5.0`).
  - The maintainer asked for the close-ups (`ui.CloseUp`, 1.3.0) to go: they cluttered the window
    and the zoom replaces them. Do not bring them back unasked.
  - `ui.Waveform.playhead` / `sought`: a click or drag beside the cuts puts the play marker (a drag
    no longer moves the zoomed picture). `MainWindow.play_line` plays from it in pieces of
    `LINE_SECONDS` (60 s), one after the other, with the same `player.py` (no Qt sound module);
    `follow_line` moves the marker by the clock. Pause is stop-and-remember. `start_playing` /
    `stop_playing` / `play_count` make sure only the newest piece asked for plays.
  - Known limits: no sound while the marker is dragged (it plays from where it is let go), and a
    short gap about once a minute where the next piece starts. Not yet heard on real hardware.
- **1.5.1: the new icon and the www.leavenlabs.org address, nothing else.** `.github/RELEASE_NOTES.md`
  and the workflow's default tag are set for it. To release: merge, then run the Release workflow (or
  push `v1.5.1`). No Python code is changed. Not yet seen on a real Windows PC or Mac: the icon.
- **1.6.0 (planned November 2026, asked for by the maintainer): four parts, in this order.** Part 1
  can slip to 1.6.1 alone if the Windows build is stubborn; it changes no Python code.
  1. **ffmpeg built from source for Windows and Linux, as on the Mac.** `tools/build_ffmpeg.sh` builds
     the same pinned ffmpeg and LAME as the Mac job (versions and SHA-256 in the script; the test
     `FfmpegBuild` keeps them equal). Every decoder, demuxer and filter is kept (any recording opens);
     of the encoders and muxers only MP3, WAV, raw s16le and null (the Mac job still has all of them).
     ffmpeg.org is refused from the cloud sessions' network: the script falls back to Ubuntu's copy of
     the same tarball (same SHA-256). Wine does not run in the cloud sessions, so the .exe is only
     tried on the Windows runner (its checks, then the installed app's test broadcast). Linux is built on the Linux job's Ubuntu;
     Windows is cross-built with mingw-w64 in its own Linux job and handed to the Windows job.
     Both are cached by the script's hash. Replaces BtbN's `latest`, which was neither pinned nor
     checked. Built and tested in a cloud session (November 2026): Linux and Windows both build
     (about 4 minutes), the unit tests pass with the Linux build, MKV/MP4 (H.264, AAC, Opus) and
     WMA/FLAC/Ogg/M4A/WAV/MP3 read; the .exe needs only Windows' own DLLs. Then look at why the
     Linux download is 308 MB (Windows 164, Mac 122).
  2. **Even loudness for the whole MP3**: ffmpeg `loudnorm` to a target set in Settings.
  3. **A cue sheet next to the MP3**: what played, when, titles, permissions (for stations, CCLI).
  4. **Cuts remembered per recording** (name, size, time saved; in the settings folder; old ones
     cleared after a few months; "Listen again" button; `--build` uses them), and **keys for the
     cuts**: click or Tab chooses the cut, arrows move it 1 s (Shift 5 s), S / E put the start / end
     cut at the play marker (also buttons "Start cut here" / "End cut here"). Not while typing in a
     time box.
- **2.0.0: a port to Rust with Tauri (a web interface) is held for then.** Do not start it unasked.
  The cut rules in `prelude.py` are tuned to faster-whisper's word times and sureness; another
  Whisper engine (whisper.cpp) will need them tuned again against real recordings.
- **The website (`docs/`) and the icon (November 2026).** The site has the look of www.leavenlabs.org
  (Fraunces and Instrument Sans, kept in `docs/fonts` so nothing is loaded from another server; gradient
  panels; ruled lists) in the app's own colours. The icon is a radio set with a cross for its dial;
  `assets/icon.ico` holds a thicker drawing for 40 pixels and smaller. Leaven Labs' address is
  `https://www.leavenlabs.org` (with the `www`).
- **Motion on the three websites (November 2026).** The maintainer chose these from a mockup: the glow
  behind the big screenshot (`.halo`), the band of light on the gradient word (`.gradtext`) and the step
  numbers, the hour that fills once in the hero (this site), the download panel's glows that drift, the
  button's glow that breathes, and the reading line at the top (`.progress`). One script at the end of the
  page gives each `data-scroll` piece `--p` (how far it has gone through the window); with "reduce motion"
  all stays still. Turned down as too much, do not add unasked: gradient rules drawn over lists, and a
  glowing comet round a card's edge.
- **1.5.2: the app in the website's look (below), nothing else.** `.github/RELEASE_NOTES.md` and the
  workflow's default tag are set for it. To release: merge, then run the Release workflow (or push
  `v1.5.2`).
- **1.5.3: the silence settings on the Settings page, nothing else.** `.github/RELEASE_NOTES.md` and the
  workflow's default tag are set for it. `max_silence_seconds` and `silence_level_db` are in the
  "Service words" card (the level is a list in plain words, `setup_wizard.SILENCE_LEVELS`; a level typed
  in config.json is listed too), `trim_song_silence` is a box in the "Songs" card. `song_silence_db` was
  left in config.json on purpose: a song's silence is measured once and kept in songs.csv, so changing
  the level would do nothing for songs already measured.
- **The app in the website's look (November 2026, asked for by the maintainer; released in 1.5.2).**
  All of it is in `ui.py`: the gradient of navy, blue and green with gold (`g1` to `g3`, `spark`), the
  headings in Fraunces (`fraunces.py` carries the font as text, 22 KB, so no file is shipped and the spec
  is unchanged; its license goes into the license file through `tools/third_party_licenses.py`), a glow
  under the main buttons (`ui.primary(button)`, use it for new main buttons) and under the result card
  (`ui.Underglow`), and small animations: a page fades in (`ui.Curtain`), a gold light crosses its title
  (`ui.Title`), the menu's marker slides, The hour fills once behind a gold needle (`ui.HourBar`), and a
  light runs along the top line during a build (`ui.Beam`). The clocks run only while the window is
  shown (`ui.Moving`). `motion` in config.json (a box on the Settings page) turns the animations off.
  The same look is in Stream Scheduler (0.0.7) in its own colours. Not yet seen on a real Windows PC or
  Mac.
- Download size matters to the maintainer. The ffmpeg for Windows and Linux is being made smaller in
  1.6.0 (above).

## Suggested work, not yet scheduled (from the November 2026 code review)

The maintainer asked to hold these for later. Do not start on them unasked; offer the list when
the maintainer asks what to build next. Remove an item once it is built.

### Fixes

- **Public-domain status does not affect what is broadcast.** `catalog.songs_for` ignores
  `catalog.cleared()`. Add a setting "only use songs that are allowed to broadcast", or say in the
  README that the status is only a guide.
- `builder.recent_songs` counts history entries, not weeks: filter by date. Write `history.json`
  atomically, as `save_config` does.
- `audio.trim_service` does not check that the silence-detect pass worked.
- `SECURITY.md` asks for "your Windows version" only.
- The Mac update only opens the DMG. Replacing the app in place (mount, copy over, start again) needs
  a Mac to try it on. Code signing would also let the update be checked by signature, not only by
  the checksum from the same release.
- The fallback end phrases in `prelude.py` ("Serve the Lord", "Go in peace", `END_PHRASE_FALLBACK`)
  cannot be changed in Settings.
- No tests for `setup_wizard`, `add_songs`, `datepicker`; no
  CONTRIBUTING file or issue templates; code signing for Windows and Mac.

### Usability (offered in November 2026, after the new look; not yet asked for)

- Remember the window's size and position.
- Read the service fewer times in one build (the silence cut inside the MP3 step, no temporary WAV).
- Measure new songs in parallel in `catalog.update`.
- The progress bar fills by step; the remaining pop-ups become in-page banners.

### Features

1. Recording copyright warning from file tags (option C above).
2. A notice (email or desktop) when a scheduled run fails or is too long.
3. Outro and station-ID slots (a closing announcement; a short ID between service and songs).
4. Auto-fit when too long: offer a fade-out at the target length.
5. Other languages and liturgies: multilingual speech models, holidays outside the US.
6. Podcast output: chapter marks, cover art, optionally an RSS feed entry.
