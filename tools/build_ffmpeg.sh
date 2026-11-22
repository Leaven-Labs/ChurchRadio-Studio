#!/bin/bash
# Build the LGPL ffmpeg shipped with the app on Windows and Linux, from the unchanged ffmpeg and
# LAME sources (LAME for MP3, linked in statically). Run on Ubuntu (release.yml does):
#   tools/build_ffmpeg.sh linux OUT_DIR    ffmpeg + ffprobe for Linux (glibc and zlib of the build system)
#   tools/build_ffmpeg.sh win64 OUT_DIR    ffmpeg.exe + ffprobe.exe, cross-built with mingw-w64,
#                                          needing no DLLs (apt: gcc-mingw-w64-x86-64)
# Needs gcc, make, nasm (and zlib1g-dev for linux). The Mac job in release.yml builds the same
# versions (a test in tests/test_core.py, FfmpegBuild, keeps the versions and checksums equal), but
# keeps all encoders and muxers. Left out here: ffplay, network, devices, outside libraries, and
# the encoders and muxers the app does not write with.
set -euo pipefail

FFMPEG_VERSION="7.1.1"
LAME_VERSION="3.100"
# SHA-256 of the two source downloads. With a new version above, put its SHA-256 here (and in the
# Mac job of release.yml).
FFMPEG_SHA256="733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1"
LAME_SHA256="ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"

target=${1:-}
out=${2:-}
case "$target" in linux|win64) ;; *) echo "usage: $0 linux|win64 OUT_DIR" >&2; exit 2 ;; esac
[ -n "$out" ] || { echo "usage: $0 linux|win64 OUT_DIR" >&2; exit 2; }
mkdir -p "$out"
out=$(cd "$out" && pwd)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
src="$work/src" pre="$work/prefix"
mkdir -p "$src" "$pre"
jobs=$(nproc)

cd "$src"
curl -fsSL --retry 5 -o lame.tar.gz "https://downloads.sourceforge.net/project/lame/lame/$LAME_VERSION/lame-$LAME_VERSION.tar.gz"
# Ubuntu's archive keeps the same file (its .orig.tar.xz is ffmpeg.org's tarball, byte for byte):
# used when ffmpeg.org cannot be reached. The checksum below decides either way.
curl -fsSL --retry 5 -o ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" ||
    curl -fsSL --retry 5 -o ffmpeg.tar.xz \
        "http://archive.ubuntu.com/ubuntu/pool/universe/f/ffmpeg/ffmpeg_$FFMPEG_VERSION.orig.tar.xz"
# Stop if a download is not the file that is expected.
printf '%s  %s\n' "$LAME_SHA256" lame.tar.gz "$FFMPEG_SHA256" ffmpeg.tar.xz | sha256sum -c -
tar -xzf lame.tar.gz && tar -xJf ffmpeg.tar.xz

if [ "$target" = win64 ]; then
    host=x86_64-w64-mingw32
    lame_host=(--host="$host")
    # -static: the mingw runtime goes into the .exe, so it runs without any DLL beside it.
    # No zlib on Windows (it is not part of Windows; the app's audio does not need it).
    ff_target=(--target-os=mingw32 --arch=x86_64 --cross-prefix="$host-" --extra-ldflags="-L$pre/lib -static")
    exe=.exe
else
    lame_host=()
    ff_target=(--enable-zlib --extra-ldflags="-L$pre/lib")
    exe=
fi

cd "lame-$LAME_VERSION"
./configure "${lame_host[@]}" --prefix="$pre" --disable-shared --enable-static --disable-frontend \
    --disable-dependency-tracking
make -j"$jobs" && make install

cd "../ffmpeg-$FFMPEG_VERSION"
# --disable-autodetect: nothing from the build system is linked in except what is named here.
# Every decoder, demuxer and filter is kept, so any recording opens and any filter can be used;
# only what the app writes is kept of the encoders and muxers: MP3, WAV, raw 16-bit (the speech
# reading) and null (measuring). The lavfi input makes the test tones of the checks.
./configure "${ff_target[@]}" --prefix="$pre" --disable-autodetect --enable-libmp3lame \
    --disable-ffplay --disable-doc --disable-debug --disable-network \
    --disable-encoders --enable-encoder=libmp3lame,pcm_s16le \
    --disable-muxers --enable-muxer=mp3,wav,pcm_s16le,null \
    --disable-devices --enable-indev=lavfi \
    --extra-cflags="-I$pre/include"
make -j"$jobs" && make install

cp "$pre/bin/ffmpeg$exe" "$pre/bin/ffprobe$exe" "$out/"
cp COPYING.LGPLv2.1 "$out/LICENSE-ffmpeg-LGPL-2.1.txt"
cp LICENSE.md "$out/LICENSE-ffmpeg.md"
cp "../lame-$LAME_VERSION/COPYING" "$out/LICENSE-lame-LGPL.txt"
printf '%s\n' \
    "ffmpeg is free software licensed under the GNU Lesser General Public License (LGPL) 2.1 or later." \
    "This copy was built for ChurchRadio Studio from the unchanged sources of ffmpeg $FFMPEG_VERSION" \
    "(https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz) and LAME $LAME_VERSION (LGPL, for MP3;" \
    "https://lame.sourceforge.io), with no GPL parts. The build steps are in tools/build_ffmpeg.sh of" \
    "https://github.com/Leaven-Labs/ChurchRadio-Studio." \
    "ChurchRadio Studio runs ffmpeg as a separate program; it is not changed." > "$out/README-ffmpeg.txt"
ls -l "$out"
