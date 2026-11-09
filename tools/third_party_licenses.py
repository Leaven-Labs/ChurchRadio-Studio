"""Write THIRD-PARTY-LICENSES.txt: the licenses of everything the installed app includes.

Run by the release workflow after the dependencies are installed:
    python tools/third_party_licenses.py build/licenses/THIRD-PARTY-LICENSES.txt
It walks the dependency tree of the packages in requirements.txt (only what the program can
load, not the build tools), copies each package's license and notice files, and adds Python's
and Tcl/Tk's licenses and a note on the speech models. ffmpeg's license ships in its own folder.
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


def python_and_tk():
    parts = []
    for p in (os.path.join(sys.base_prefix, "LICENSE.txt"),
              os.path.join(sys.base_prefix, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "LICENSE.txt")):
        if os.path.isfile(p):
            parts.append((f"Python {sys.version.split()[0]} (PSF License)", open(p, encoding="utf-8", errors="replace").read()))
            break
    try:
        import tkinter
        lib = tkinter.Tcl().eval("info library")
        for name, folder in (("Tcl", lib), ("Tk", lib.replace("tcl8", "tk8"))):
            p = os.path.join(folder, "license.terms")
            if os.path.isfile(p):
                parts.append((f"{name} (BSD-style license)", open(p, encoding="utf-8", errors="replace").read()))
    except Exception:  # noqa: BLE001  no Tk in this Python: nothing to add
        pass
    return parts


def main(out_path):
    dists = walk(roots())
    lines = ["ChurchRadio Studio includes the following third-party software.",
             "ChurchRadio Studio itself is MIT licensed: see LICENSE.txt in this folder.",
             "ffmpeg (LGPL) is in the ffmpeg folder, with its own license and README.",
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
    for title, text in python_and_tk():
        lines += ["", "=" * 78, title, "=" * 78, text.strip()]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{len(dists)} packages written to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "THIRD-PARTY-LICENSES.txt")
