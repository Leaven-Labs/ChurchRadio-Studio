#!/bin/sh
# ChurchRadio Studio for Linux: install for this user (no root needed), or update in place.
#
#   ./install.sh               copy the program to ~/.local/share/churchradio-studio, add it to
#                              the applications menu and make ~/.local/bin/churchradio-studio
#   ./install.sh --uninstall   remove the program, the menu entry and the command
#
# Your settings, song list and history (~/.config/churchradio-studio) and the speech models
# (~/.cache/churchradio-studio/models) are never removed, so an update or reinstall keeps them.
set -eu

APP=churchradio-studio
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA/$APP"
BIN="$HOME/.local/bin"
DESKTOP="$DATA/applications/$APP.desktop"
ICON="$DATA/icons/hicolor/256x256/apps/$APP.png"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$DEST" "$DESKTOP" "$ICON" "$BIN/$APP"
    echo "ChurchRadio Studio removed. Your settings and the speech models were kept."
    exit 0
fi

if [ ! -x "$HERE/ChurchRadio-Studio" ]; then
    echo "Run install.sh from the unpacked ChurchRadio-Studio folder." >&2
    exit 1
fi

if [ "$HERE" != "$DEST" ]; then
    mkdir -p "$DATA"
    rm -rf "$DEST.new"
    cp -R "$HERE" "$DEST.new"
    rm -rf "$DEST"
    mv "$DEST.new" "$DEST"
fi

mkdir -p "$BIN" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
ln -sf "$DEST/ChurchRadio-Studio" "$BIN/$APP"
cp "$DEST/_internal/assets/icon-256.png" "$ICON"
cat > "$DESKTOP" <<DESKTOP_ENTRY
[Desktop Entry]
Type=Application
Name=ChurchRadio Studio
Comment=Turn your Sunday service recording into a finished radio broadcast
Exec="$DEST/ChurchRadio-Studio" %f
Icon=$APP
Terminal=false
Categories=AudioVideo;Audio;
MimeType=video/x-matroska;video/mp4;audio/x-wav;audio/wav;audio/mpeg;audio/mp4;
StartupWMClass=ChurchRadio-Studio
DESKTOP_ENTRY
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$DESKTOP")" >/dev/null 2>&1 || true

echo "ChurchRadio Studio is installed: find it in your applications menu."
echo "Program: $DEST"
echo "Command: $BIN/$APP (for cron: $BIN/$APP --build \"/path/to/recordings\")"
