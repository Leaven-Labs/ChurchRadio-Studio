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
