# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ChurchRadio Studio (one-folder, windowed app).
#
# Built by .github/workflows/release.yml on Windows, Linux and macOS. Run:
#   pyinstaller ChurchRadio-Studio.spec
# Windows: dist\ChurchRadio-Studio\ (the .exe + an _internal folder). installer.iss
#   (Inno Setup) packs that folder and ffmpeg into one ChurchRadio-Studio-Setup.exe.
# Linux:   dist/ChurchRadio-Studio/ (the program + _internal). The workflow adds ffmpeg and
#   tools/linux/install.sh and packs it into ChurchRadio-Studio-Linux-x86_64.tar.gz.
# macOS:   dist/ChurchRadio Studio.app as well. The workflow adds ffmpeg and the licenses to
#   Contents/Resources, signs it ad hoc and packs it into ChurchRadio-Studio-macOS.dmg.
# One folder instead of one file: it starts much faster (nothing is unpacked on each start)
# and antivirus programs flag it less often.
#
# Notes:
# - faster-whisper / ctranslate2 libraries are bundled. The Whisper *models* are NOT
#   bundled: on first run they download once to one fixed folder per PC
#   (C:\ProgramData\ChurchRadio Studio\models, or config.json models_folder if set),
#   then load from disk with no network. The README says where they live.
# - tkinterdnd2 ships a PyInstaller hook (__pyinstaller/hook-tkinterdnd2.py) that pulls
#   in the platform `tkdnd/` Tk extension. We also list the data defensively so a
#   version bump in the hook can't silently drop it.
# - ffmpeg / ffprobe are not in this folder: the installer adds an LGPL ffmpeg build in
#   {app}\ffmpeg (see release.yml). audio.find_tool() looks there first, then the app folder,
#   PATH, and C:\ffmpeg\bin.
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

# tkinterdnd2 platform data (Tk extension: .tcl files + platform lib/dll).
tkinterdnd2_data = collect_data_files("tkinterdnd2")
# faster-whisper ships ctranslate2 binaries and assets; collect their data files.
faster_whisper_data = collect_data_files("faster_whisper")
# ctranslate2 native libraries (the actual inference engine).
ctranslate2_libs = []
try:
    ctranslate2_libs = collect_dynamic_libs("ctranslate2")
except Exception:
    pass
# tokenizers / huggingface_hub are pulled in by faster-whisper at import time; PyInstaller
# follows them. We collect their data (sentencepiece vocab, etc.) to be safe.
tokenizers_data = collect_data_files("tokenizers")
huggingface_data = collect_data_files("huggingface_hub")

# App defaults that travel with the program so first-run copy-out works.
# copy_out_default() copies these into the user's folder on first run, never overwriting.
app_defaults = []
for name in ("config.json", "songs.csv"):
    if os.path.exists(name):
        app_defaults.append((name, "."))

# The hymn list used to identify songs from their lyrics (read in place, not copied out).
app_defaults.append(("hymns.csv", "."))
# The version of this build (written by the release workflow; missing when built by hand).
if os.path.exists("version.txt"):
    app_defaults.append(("version.txt", "."))
# The icon, for the window title bar and taskbar.
app_defaults += [("assets/icon.ico", "assets"), ("assets/icon-256.png", "assets")]

datas = []
for d in (tkinterdnd2_data, faster_whisper_data, tokenizers_data, huggingface_data):
    datas.extend(d)
datas.extend(app_defaults)

binaries = []
for lib in ctranslate2_libs:
    binaries.append(lib)

hiddenimports = (
    collect_submodules("faster_whisper")
    + collect_submodules("ctranslate2")
    + collect_submodules("tokenizers")
    + collect_submodules("huggingface_hub")
    + ["tkinterdnd2", "tkinterdnd2.TkinterDnD"]
)

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6"],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ChurchRadio-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed, no console
    # Windows: the .ico. macOS: PyInstaller makes the .icns from the PNG (needs Pillow).
    icon="assets/icon.ico" if sys.platform == "win32" else "assets/icon-256.png",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ChurchRadio-Studio",
)

if sys.platform == "darwin":
    version = open("version.txt").read().strip() if os.path.exists("version.txt") else "0.0.0"
    app = BUNDLE(
        coll,
        name="ChurchRadio Studio.app",
        icon="assets/icon-256.png",
        bundle_identifier="org.leavenlabs.churchradio-studio",
        version=version,
        info_plist={
            "CFBundleName": "ChurchRadio Studio",
            "CFBundleDisplayName": "ChurchRadio Studio",
            "CFBundleShortVersionString": version,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "NSHumanReadableCopyright": "Copyright (c) 2026 Aaron Steger. MIT License.",
        },
    )
