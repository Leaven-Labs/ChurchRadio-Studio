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

## Suggested work, not yet scheduled (from the November 2026 code review)

The maintainer asked to hold these for later. Do not start on them unasked; offer the list when
the maintainer asks what to build next. Remove an item once it is built.

### Fixes

- **Partial MP3 blocks scheduled runs.** `audio.join_to_mp3` writes straight to the final path; if
  ffmpeg dies partway, the leftover file makes `cli.choose` say "already made". Write to a temporary
  name and `os.replace` on success.
- **Public-domain status does not affect what is broadcast.** `catalog.songs_for` ignores
  `catalog.cleared()`. Add a setting "only use songs that are allowed to broadcast", or say in the
  README that the status is only a guide.
- Pin the build inputs: versions in `requirements.txt`, the BtbN ffmpeg build (verify its hash), and
  the GitHub Actions by commit.
- `builder.recent_songs` counts history entries, not weeks: filter by date. Write `history.json`
  atomically, as `save_config` does.
- `audio.trim_service` does not check that the silence-detect pass worked.
- `SECURITY.md` speaks only of Windows.
- The fallback end phrases in `prelude.py` ("Serve the Lord", "Go in peace", `END_PHRASE_FALLBACK`)
  cannot be changed in Settings.
- Unused `sys` import in `prelude.py`; no tests for `setup_wizard`, `add_songs`, `datepicker`; no
  CONTRIBUTING file or issue templates; code signing for Windows and Mac.

### Features

1. Recording copyright warning from file tags (option C above).
2. Preview the start and end cuts before building, with playback around each and a nudge control.
3. Loudness normalisation to a target (ffmpeg `loudnorm`, e.g. -16 LUFS) for the songs and service.
4. A playlist / cue sheet saved next to the MP3 (what played, when, titles, permissions), for
   stations and license reports such as CCLI's.
5. A notice (email or desktop) when a scheduled run fails or is too long.
6. Outro and station-ID slots (a closing announcement; a short ID between service and songs).
7. Auto-fit when too long: offer a fade-out at the target length.
8. Other languages and liturgies: multilingual speech models, holidays outside the US.
9. Optional update check in About (off by default, to keep the offline promise).
10. Podcast output: chapter marks, cover art, optionally an RSS feed entry.
