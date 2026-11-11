"""Write THIRD-PARTY-LICENSES.txt: the licenses of everything the installed app includes.

Run by the release workflow after the dependencies are installed:
    python tools/third_party_licenses.py build/licenses/THIRD-PARTY-LICENSES.txt
It walks the dependency tree of the packages in requirements.txt (only what the program can
load, not the build tools), copies each package's license and notice files, and adds Python's
license and notes on Qt (LGPL) and the speech models. ffmpeg's license ships in its own folder.
"""
import importlib.metadata as md
import os
import re
import sys

from packaging.requirements import Requirement

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LICENSE_FILE = re.compile(r"(^|/)(LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$", re.I)


def roots():
    with open(os.path.join(HERE, "requirements.txt"), encoding="utf-8") as fh:
        return [Requirement(line).name for line in (raw.split("#")[0].strip() for raw in fh) if line]


def walk(names):
    """Every distribution needed at run time, by normalised name."""
    seen, todo = {}, list(names)
    while todo:
        key = re.sub(r"[-_.]+", "-", todo.pop()).lower()
        if key in seen:
            continue
        try:
            dist = md.distribution(key)
        except md.PackageNotFoundError:
            continue
        seen[key] = dist
        for req in dist.requires or []:
            r = Requirement(req)
            if r.marker and not r.marker.evaluate({"extra": ""}):
                continue  # optional extras and other platforms are not bundled
            todo.append(r.name)
    return seen


def license_name(dist):
    m = dist.metadata
    if m.get("License-Expression"):
        return m["License-Expression"]
    lic = (m.get("License") or "").strip()
    if lic and len(lic) < 80 and "\n" not in lic:
        return lic
    classes = [c.split("::")[-1].strip() for c in m.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classes) or "see the license text below"


def license_texts(dist):
    out = []
    for f in dist.files or []:
        if LICENSE_FILE.search(str(f).replace("\\", "/")):
            try:
                with open(f.locate(), encoding="utf-8", errors="replace") as fh:
                    text = fh.read().strip()
            except OSError:
                continue
            if text:
                out.append((str(f), text))
    return out


QT_NOTE = """Qt (the windows of the app) is used through PySide6 under the GNU Lesser General Public License
version 3 (LGPL-3.0). Qt is copyright (C) The Qt Company Ltd and other contributors.
The Qt and PySide6 libraries are separate files in the program folder (PySide6 and shiboken6 inside
_internal): you may replace them with your own builds of the same versions.
Source code: https://download.qt.io/official_releases/qt/ and
https://download.qt.io/official_releases/QtForPython/pyside6/
The license texts (LGPL-3.0 and the GPL-3.0 it refers to) are with the PySide6 packages below and at
https://www.gnu.org/licenses/lgpl-3.0.txt and https://www.gnu.org/licenses/gpl-3.0.txt
Qt also includes third-party parts under their own licenses: https://doc.qt.io/qt-6/licenses-used-in-qt.html"""


def python_license():
    parts = []
    for p in (os.path.join(sys.base_prefix, "LICENSE.txt"),
              os.path.join(sys.base_prefix, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "LICENSE.txt")):
        if os.path.isfile(p):
            parts.append((f"Python {sys.version.split()[0]} (PSF License)", open(p, encoding="utf-8", errors="replace").read()))
            break
    return parts


def main(out_path):
    dists = walk(roots())
    lines = ["ChurchRadio Studio includes the following third-party software.",
             "ChurchRadio Studio itself is MIT licensed: see LICENSE.txt in this folder.",
             "ffmpeg (LGPL) is in the ffmpeg folder, with its own license and README.",
             "", QT_NOTE, "",
             "The Whisper speech models (base.en, small.en; converted by SYSTRAN for faster-whisper)",
             "are MIT licensed and are downloaded on first use, not included in the installer.", ""]
    lines.append("Packages: " + ", ".join(f"{d.metadata['Name']} {d.version} ({license_name(d)})"
                                         for _k, d in sorted(dists.items())))
    for _k, d in sorted(dists.items()):
        lines += ["", "=" * 78, f"{d.metadata['Name']} {d.version}  --  {license_name(d)}",
                  d.metadata.get("Home-page") or "", "=" * 78]
        texts = license_texts(d)
        lines += [f"--- {name} ---\n{text}" for name, text in texts] or ["(no license file in the package; license: "
                                                                         + license_name(d) + ")"]
    for title, text in python_license():
        lines += ["", "=" * 78, title, "=" * 78, text.strip()]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{len(dists)} packages written to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "THIRD-PARTY-LICENSES.txt")
