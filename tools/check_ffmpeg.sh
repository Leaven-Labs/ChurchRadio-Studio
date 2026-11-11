#!/bin/bash
# Check an ffmpeg build before it is shipped (run by release.yml for Linux and macOS; the Windows
# job does the same in PowerShell): LGPL (no GPL parts), can write MP3, has the filters the app uses.
#   tools/check_ffmpeg.sh path/to/ffmpeg
set -euo pipefail
ff=$1
cfg=$("$ff" -hide_banner -buildconf 2>&1)
grep -q -- "enable-gpl" <<<"$cfg" && { echo "This ffmpeg build is GPL, not LGPL. Not shipping it."; exit 1; }
grep -q -- "enable-libmp3lame" <<<"$cfg" || { echo "This ffmpeg build cannot write MP3 (no libmp3lame)."; exit 1; }
filters=$("$ff" -hide_banner -filters 2>&1)
for f in silencedetect aselect acompressor alimiter dynaudnorm atrim concat; do
    grep -qE "\s$f\s" <<<"$filters" || { echo "ffmpeg is missing the $f filter."; exit 1; }
done
t=$(mktemp -d)
"$ff" -v error -y -f lavfi -i "sine=d=2" -c:a libmp3lame -b:a 192k "$t/t.mp3" || { echo "ffmpeg could not write a test MP3."; exit 1; }
rm -rf "$t"
echo "ffmpeg OK: LGPL, MP3, filters."
