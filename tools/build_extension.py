#!/usr/bin/env python3
"""Empaqueta la extensión para Chrome y para Firefox en dist/ (los dos zips comparten el mismo código).

    python tools/build_extension.py

Chrome: dist/focus-relay-chrome-<versión>.zip   (manifest.json, service worker)
Firefox: dist/focus-relay-firefox-<versión>.zip (manifest.firefox.json como manifest.json, scripts de fondo)
"""
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "extension")
OUT = os.path.join(ROOT, "dist")
SKIP = {"manifest.json", "manifest.firefox.json", "README.md", "THIRD_PARTY_NOTICES.md"}


def build(target, manifest_name):
    with open(os.path.join(SRC, manifest_name), encoding="utf-8") as f:
        manifest = json.load(f)
    version = manifest["version"]
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f"focus-relay-{target}-{version}.zip")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for name in sorted(os.listdir(SRC)):
            if name not in SKIP and os.path.isfile(os.path.join(SRC, name)):
                z.write(os.path.join(SRC, name), name)
    return dest


if __name__ == "__main__":
    a = json.load(open(os.path.join(SRC, "manifest.json"), encoding="utf-8"))["version"]
    b = json.load(open(os.path.join(SRC, "manifest.firefox.json"), encoding="utf-8"))["version"]
    if a != b:
        raise SystemExit(f"Las versiones no coinciden: Chrome {a} / Firefox {b}")
    for target, name in (("chrome", "manifest.json"), ("firefox", "manifest.firefox.json")):
        print(build(target, name))
