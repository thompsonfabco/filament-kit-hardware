#!/usr/bin/env python3
"""Paper check: each device's catalogue.xml against its guide and the firmware source.

Usage: python tools/paper_check.py [--kit PATH_TO_FILAMENT_KIT] [--devices DIR]

Devices are the directories under devices/ that hold a catalogue.xml. Kit-built devices
(those with a <firmware> element) are also checked against the source in the kit checkout.
Exit 0 when clean, 1 with problems, 2 for a bad --kit or a kit device with no --kit.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# ESP32-C3 strapping pins (2, 8, 9) and the USB pair (18, 19).
C3_RESERVED = {2, 8, 9, 18, 19}
ACTIVE_ATTRS = ("vmax", "imax", "datasheet")

_PIN_CONST = re.compile(r"static\s+const\s+(?:uint8_t|int|gpio_num_t)\s+(PIN_\w+)\s*=\s*(\d+)\s*;")
_PIN_DEFINE = re.compile(r"^\s*#\s*define\s+(PIN_\w+)\s+(\d+)\b", re.M)
# A string literal (kept whole, so "//" inside it is not a comment) or a comment.
_TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"|//[^\n]*|/\*.*?\*/', re.S)
_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


class CatalogueError(Exception):
    def __init__(self, path, message):
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


@dataclass
class Pin:
    gpio: int
    constant: str
    role: str


@dataclass
class Part:
    ref: str
    name: str
    kind: str
    vmax: str
    imax: str
    datasheet: str


@dataclass
class Catalogue:
    id: str
    chip: str = ""
    hello: str = ""
    firmware_source: str = ""
    family: str = ""
    pins: list = field(default_factory=list)
    parts: list = field(default_factory=list)


def load_catalogue(path: Path) -> Catalogue:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise CatalogueError(path, f"cannot parse: {e}")
    if root.tag != "device" or not root.get("id"):
        raise CatalogueError(path, "root must be <device id=...>")
    board = root.find("board")
    link = root.find("link")
    fw = root.find("firmware")
    family = board.get("family", "") if board is not None else ""
    cat = Catalogue(
        id=root.get("id"),
        family=family,
        # The chip token is the board family with the dash dropped: esp32-c3 -> esp32c3.
        chip=family.replace("-", ""),
        hello=link.get("hello", "") if link is not None else "",
        firmware_source=fw.get("source", "") if fw is not None else "",
    )
    for p in root.findall("./pins/pin"):
        try:
            gpio = int(p.get("gpio", ""))
        except ValueError:
            raise CatalogueError(path, f"pin {p.get('constant')!r} has a non-integer gpio")
        cat.pins.append(Pin(gpio, p.get("constant", ""), p.get("role", "")))
    for p in root.findall("./parts/part"):
        cat.parts.append(Part(p.get("ref", ""), p.get("name", ""), p.get("kind", ""),
                              p.get("vmax", ""), p.get("imax", ""), p.get("datasheet", "")))
    return cat


def strip_comments(text: str) -> str:
    """Remove // and /* */ comments (newlines kept so line structure survives); strings are untouched."""
    def blank(m):
        s = m.group(0)
        return s if s.startswith('"') else re.sub(r"[^\n]", " ", s)
    return _TOKEN.sub(blank, text)


def firmware_pins(source: Path) -> dict:
    """PIN_* constants in code, not comments: `static const uint8_t|int|gpio_num_t PIN_X = N;` and `#define PIN_X N`."""
    text = strip_comments(source.read_text(encoding="utf-8", errors="replace"))
    pins = {m.group(1): int(m.group(2)) for m in _PIN_DEFINE.finditer(text)}
    pins.update({m.group(1): int(m.group(2)) for m in _PIN_CONST.finditer(text)})
    return pins


def guide_pins(guide: Path) -> dict:
    """PIN_* -> GPIO from markdown tables with `Constant` and `C3 GPIO` header cells (by name)."""
    pins = {}
    cols = None
    for line in guide.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            cols = None
            continue
        cells = [c.strip().strip("`") for c in s.strip("|").split("|")]
        if cols is None:
            if "Constant" in cells and "C3 GPIO" in cells:
                cols = (cells.index("Constant"), cells.index("C3 GPIO"))
            continue
        if cols[0] >= len(cells) or cols[1] >= len(cells):
            continue
        name, gpio = cells[cols[0]], cells[cols[1]]
        if name.startswith("PIN_") and gpio.isdigit():
            pins[name] = int(gpio)
    return pins


def hello_prints(text: str) -> list:
    """Joined string literals of each HELLO print in code (comments stripped first).

    A HELLO print starts on a line with a print/printf/println call whose literals include "HELLO ",
    and runs through the next line holding println or printf (at most 6 lines), so a print split over
    several Serial.print calls reads as one string. The version between the pieces is not a literal."""
    lines = strip_comments(text).splitlines()
    out = []
    for i, line in enumerate(lines):
        if re.search(r"print\w*\s*\(", line) and re.search(r'"HELLO ', line):
            seq = []
            for l in lines[i:i + 6]:
                seq.append(l)
                if re.search(r"println|printf", l):
                    break
            out.append("".join(_STRING.findall("\n".join(seq))))
    return out


def check_device(dir: Path, kit) -> list:
    try:
        cat = load_catalogue(dir / "catalogue.xml")
    except CatalogueError as e:
        return [f"{dir.name}: {e.message}"]
    out = []

    def bad(msg):
        out.append(f"{cat.id}: {msg}")

    seen = {}
    for p in cat.pins:
        if p.gpio in seen:
            bad(f"duplicate GPIO {p.gpio} ({seen[p.gpio]} and {p.constant})")
        seen[p.gpio] = p.constant
        if cat.family == "esp32-c3" and p.gpio in C3_RESERVED:
            bad(f"{p.constant} uses GPIO {p.gpio}, reserved on the ESP32-C3 (strapping or USB)")

    for part in cat.parts:
        if part.kind == "active":
            for a in ACTIVE_ATTRS:
                if not getattr(part, a):
                    bad(f"active part {part.ref} lacks {a}")

    cat_pins = {p.constant: p.gpio for p in cat.pins}
    guide = dir / "guide.md"
    if not guide.is_file():
        bad("no guide.md")
    else:
        gp = guide_pins(guide)
        for name, gpio in cat_pins.items():
            if name not in gp:
                bad(f"{name} is not in the guide's pin table")
            elif gp[name] != gpio:
                bad(f"{name} is GPIO {gpio} in the catalogue but {gp[name]} in the guide")
        for name in gp:
            if name not in cat_pins:
                bad(f"{name} is in the guide's pin table but not the catalogue")

    if cat.firmware_source:
        if kit is None:
            bad("firmware is declared but no kit was given")
            return out
        src = kit / cat.firmware_source
        if not src.is_file():
            bad(f"firmware source {cat.firmware_source} not found in the kit")
            return out
        fw = firmware_pins(src)
        for name, gpio in cat_pins.items():
            if name not in fw:
                bad(f"{name} is not in the firmware")
            elif fw[name] != gpio:
                bad(f"{name} is GPIO {gpio} in the catalogue but {fw[name]} in the firmware")
        for name in fw:
            if name not in cat_pins:
                bad(f"{name} is in the firmware but not the catalogue")
        hellos = hello_prints(src.read_text(encoding="utf-8", errors="replace"))
        if cat.hello and not any(re.search(r"HELLO\s+" + re.escape(cat.hello), h) for h in hellos):
            bad(f"HELLO {cat.hello} not found in the firmware's HELLO print")
        if cat.chip and not any(cat.chip in h for h in hellos):
            bad(f"chip token {cat.chip} not found in the firmware's HELLO print")
    return out


def _needs_firmware(dir: Path) -> bool:
    try:
        return bool(load_catalogue(dir / "catalogue.xml").firmware_source)
    except CatalogueError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kit", help="checkout of filament-kit, for firmware checks")
    ap.add_argument("--devices", default=str(REPO / "devices"), help="devices directory")
    args = ap.parse_args(argv)
    if not Path(args.devices).is_dir():
        print(f"devices folder {args.devices} not found", file=sys.stderr)
        return 2
    devices = sorted(d for d in Path(args.devices).iterdir() if (d / "catalogue.xml").is_file())
    kit = None
    if args.kit is not None:
        kit = Path(args.kit)
        if not kit.is_dir():
            print(f"--kit {args.kit} is not a directory", file=sys.stderr)
            return 2
    elif any(_needs_firmware(d) for d in devices):
        print("a device needs firmware: pass --kit PATH", file=sys.stderr)
        return 2
    problems = []
    for d in devices:
        problems += check_device(d, kit)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
