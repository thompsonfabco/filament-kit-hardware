"""Build the release assets from enclosures/.

Every folder under enclosures/ that holds files directly is a device. Each
device gives one zip of its STEP files, and each 3MF in it is copied out as its
own asset.

Zip layout: one top-level folder named after the device slug, holding the STEP
files, plus LICENSE (a copy of enclosures/LICENSE). Entries are sorted and
carry a fixed timestamp, so two builds of the same commit are byte-identical.

Asset names are lowercase slugs with the version at the end:
  <device-slug>-step-<version>.zip
  <3mf-name-slug>-<version>.3mf

    python -I tools/make_release.py --version vX.Y.Z --out <dir>
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def find_devices(enclosures):
    """Folders under enclosures/ that hold files directly, sorted by path."""
    return sorted(
        d
        for d in [enclosures, *enclosures.rglob("*")]
        if d.is_dir() and d != enclosures and any(f.is_file() for f in d.iterdir())
    )


def write_zip(path, folder, step_files, license_file):
    entries = {f"{folder}/{f.name}": f for f in step_files}
    entries[f"{folder}/LICENSE"] = license_file
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, entries[name].read_bytes())


def build(enclosures, version, out):
    """Write the assets into out and return their paths."""
    license_file = enclosures / "LICENSE"
    if not license_file.is_file():
        raise SystemExit(f"missing {license_file}")
    out.mkdir(parents=True, exist_ok=True)
    assets = []
    for device in find_devices(enclosures):
        name = slug("-".join(device.relative_to(enclosures).parts))
        steps = sorted(
            f for f in device.iterdir() if f.is_file() and f.suffix.lower() in (".step", ".stp")
        )
        if not steps:
            raise SystemExit(f"{device}: no STEP files")
        zip_path = out / f"{name}-step-{version}.zip"
        write_zip(zip_path, name, steps, license_file)
        assets.append(zip_path)
        for f in sorted(device.iterdir()):
            if f.is_file() and f.suffix.lower() == ".3mf":
                dest = out / f"{slug(f.stem)}-{version}.3mf"
                dest.write_bytes(f.read_bytes())
                assets.append(dest)
    return assets


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--enclosures", type=Path, default=ROOT / "enclosures")
    args = ap.parse_args()
    for asset in build(args.enclosures, args.version, args.out):
        print(asset)


if __name__ == "__main__":
    sys.exit(main())
