#!/usr/bin/env python3
"""Paper check: each device's catalogue.xml against its guide and the firmware source.

Usage: python tools/paper_check.py [--kit PATH_TO_FILAMENT_KIT] [--devices DIR]

Devices are the directories under devices/ that hold a catalogue.xml. A device with a
kicad/*.kicad_sch project is checked from its exported netlist (kicad-cli, found on PATH or
through the KICAD_CLI environment variable); any other device from its catalogue pins and parts.
Kit-built devices (those with a <firmware> element) are also checked against the source in the
kit checkout.
Exit 0 when clean, 1 with problems, 2 for a bad --kit, a kit device with no --kit, or a KiCad
project with no kicad-cli.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# ESP32-C3 strapping pins (2, 8, 9) and the USB pair (18, 19).
C3_RESERVED = {2, 8, 9, 18, 19}
ACTIVE_ATTRS = ("vmax", "imax", "datasheet")
# Reference prefixes of active parts in a schematic: ICs and modules, transistors, diodes,
# amplifiers and assemblies, power supplies, displays, relays. Any symbol with a Vmax property
# is active too.
ACTIVE_PREFIXES = ("U", "Q", "D", "IC", "A", "PS", "DS", "K")

_PIN_CONST = re.compile(r"static\s+const\s+(?:uint8_t|int|gpio_num_t)\s+(PIN_\w+)\s*=\s*(\d+)\s*;")
_PIN_DEFINE = re.compile(r"^\s*#\s*define\s+(PIN_\w+)\s+(\d+)\b", re.M)
# A string literal (kept whole, so "//" inside it is not a comment) or a comment.
_TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"|//[^\n]*|/\*.*?\*/', re.S)
_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
# A U1 pin name in the netlist: the GPIO name plus the pad number, as in GPIO5_1.
_GPIO_PIN = re.compile(r"^GPIO(\d+)_\d+$")


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
    link_type: str = ""
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
        link_type=link.get("type", "") if link is not None else "",
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


def kicad_projects(dir: Path) -> list:
    """The root schematic of each KiCad project in dir/kicad: <name>.kicad_sch beside <name>.kicad_pro.

    Sub-sheets and _autosave-* files are never the root, so they are not listed."""
    k = dir / "kicad"
    if not k.is_dir():
        return []
    return sorted(s for pro in k.glob("*.kicad_pro") if (s := pro.with_suffix(".kicad_sch")).is_file())


def kicad_cli():
    """The kicad-cli to run: the KICAD_CLI file if that is set, else the one on PATH, else None."""
    env = os.environ.get("KICAD_CLI")
    if env:
        return env if Path(env).is_file() else None
    return shutil.which("kicad-cli")


def export_netlist(sch: Path, out: Path) -> None:
    """Export the schematic's netlist (kicadxml) to out with kicad-cli."""
    try:
        r = subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadxml",
                            "-o", str(out), str(sch)], capture_output=True, text=True)
    except (OSError, TypeError) as e:
        raise CatalogueError(sch, f"cannot run kicad-cli: {e}")
    if r.returncode != 0 or not out.is_file():
        raise CatalogueError(sch, f"kicad-cli netlist export failed: {(r.stderr or r.stdout).strip()}")


def read_netlist(path: Path):
    """(gpio_nets, parts) from a kicadxml netlist.

    gpio_nets maps net name (leading "/" dropped) to the set of GPIO numbers wired to it, for nets
    that touch a GPIOn pin and are not left unconnected. parts maps ref to a dict of lowercase
    field name to value, with the datasheet taken from the component's <datasheet> element."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise CatalogueError(path, f"cannot parse netlist: {e}")
    parts = {}
    for c in root.findall("./components/comp"):
        props = {f.get("name", "").lower(): (f.text or "").strip() for f in c.findall("./fields/field")}
        props["datasheet"] = (c.findtext("datasheet") or "").strip()
        parts[c.get("ref", "")] = props
    gpio_nets = {}
    for n in root.findall("./nets/net"):
        name = n.get("name", "")
        if name.startswith("unconnected-"):
            continue
        for node in n.findall("node"):
            m = _GPIO_PIN.match(node.get("pinfunction", ""))
            if m and "no_connect" not in node.get("pintype", ""):
                gpio_nets.setdefault(name.lstrip("/"), set()).add(int(m.group(1)))
    return gpio_nets, parts


def check_netlist(cat: Catalogue, bad, netlist: Path) -> dict:
    """Check a KiCad device from its netlist. Returns the {constant: gpio} the schematic wires."""
    try:
        gpio_nets, parts = read_netlist(netlist)
    except CatalogueError as e:
        bad(e.message)
        return {}
    pins = {}
    for net, gpios in sorted(gpio_nets.items()):
        if len(gpios) > 1:
            bad(f"net {net} joins GPIOs {sorted(gpios)}")
        gpio = min(gpios)
        if cat.family == "esp32-c3" and gpio in C3_RESERVED:
            bad(f"net {net} uses GPIO {gpio}, reserved on the ESP32-C3 (strapping or USB)")
        pins["PIN_" + net] = gpio
    by_gpio = {}
    for const, gpio in pins.items():
        by_gpio.setdefault(gpio, []).append(const)
    for gpio, consts in sorted(by_gpio.items()):
        if len(consts) > 1:
            bad(f"duplicate GPIO {gpio} ({' and '.join(sorted(consts))})")
    # Catalogue parts are matched to netlist symbols by ref, exactly. A range ref such as J1-J5 matches
    # nothing, which is fine: those are passive parts with no figures to compare.
    cat_parts = {p.ref: p for p in cat.parts}
    cat_gpio = {p.constant: p.gpio for p in cat.pins}
    for const in sorted(set(cat_gpio) | set(pins)):
        if const not in pins:
            bad(f"{const} is GPIO {cat_gpio[const]} in the catalogue but not in the schematic")
        elif const not in cat_gpio:
            bad(f"{const} is GPIO {pins[const]} in the schematic but not in the catalogue")
        elif cat_gpio[const] != pins[const]:
            bad(f"{const} is GPIO {cat_gpio[const]} in the catalogue but {pins[const]} in the schematic")
    for ref, props in sorted(parts.items()):
        prefix = re.match(r"[A-Za-z]*", ref).group(0)
        cp = cat_parts.get(ref)
        # A schematic part is active when its ref prefix is an active one or it carries a Vmax property.
        is_active = prefix in ACTIVE_PREFIXES or "vmax" in props
        if is_active:
            if cp is None:
                bad(f"active part {ref} is in the schematic but not in the catalogue")
            for a in ACTIVE_ATTRS:
                # "~" is KiCad's empty-datasheet placeholder; "UNCONFIRMED" stays allowed.
                if props.get(a, "") in ("", "~"):
                    bad(f"active part {ref} lacks {a}")
        if cp is not None:
            if is_active != (cp.kind == "active"):
                bad(f"part {ref} is {cp.kind or 'unmarked'} in the catalogue but "
                    f"{'active' if is_active else 'passive'} in the schematic")
            for a in ACTIVE_ATTRS:
                have = getattr(cp, a)
                if have and props.get(a, "") not in ("", "~") and have != props[a]:
                    bad(f"part {ref} {a} is {have} in the catalogue but {props[a]} in the schematic")
    # Every catalogue active part needs ratings and a schematic counterpart. A range ref such as J1-J5
    # has no counterpart, so it is exempt only while passive.
    for part in cat.parts:
        if part.kind != "active":
            continue
        if part.ref not in parts:
            bad(f"active part {part.ref} is in the catalogue but not in the schematic")
        for a in ACTIVE_ATTRS:
            if not getattr(part, a):
                bad(f"active part {part.ref}: the catalogue lacks {a}")
    return pins


def check_device(dir: Path, kit, export=export_netlist) -> list:
    try:
        cat = load_catalogue(dir / "catalogue.xml")
    except CatalogueError as e:
        return [f"{dir.name}: {e.message}"]
    out = []

    def bad(msg):
        out.append(f"{cat.id}: {msg}")

    # Refs are compared ignoring case, so q1 beside Q1 is a duplicate.
    refs = [p.ref for p in cat.parts]
    lowered = [r.lower() for r in refs]
    for ref in sorted({r for r in refs if lowered.count(r.lower()) > 1}):
        bad(f"duplicate part ref {ref} in the catalogue")
    for part in cat.parts:
        if part.kind not in ("active", "passive"):
            bad(f"part {part.ref} kind {part.kind!r} must be exactly active or passive")
        elif part.kind == "passive":
            for a in ACTIVE_ATTRS:
                if getattr(part, a):
                    bad(f"passive part {part.ref} carries {a}")

    schematics = kicad_projects(dir)
    if schematics:
        with tempfile.TemporaryDirectory() as tmp:
            netlist = Path(tmp) / "netlist.xml"
            try:
                export(schematics[0], netlist)
            except CatalogueError as e:
                return [f"{cat.id}: {e.message}"]
            cat_pins = check_netlist(cat, bad, netlist)
        source = "the schematic"
    else:
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
        source = "the catalogue"

    guide = dir / "guide.md"
    if not guide.is_file():
        bad("no guide.md")
    else:
        gp = guide_pins(guide)
        for name, gpio in cat_pins.items():
            if name not in gp:
                bad(f"{name} is not in the guide's pin table")
            elif gp[name] != gpio:
                bad(f"{name} is GPIO {gpio} in {source} but {gp[name]} in the guide")
        for name in gp:
            if name not in cat_pins:
                bad(f"{name} is in the guide's pin table but not {source}")

    if cat.link_type == "usb-serial" and cat.firmware_source and not cat.hello:
        bad("a usb-serial device with firmware needs a hello on its <link> (HELLO rule)")

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
                bad(f"{name} is GPIO {gpio} in {source} but {fw[name]} in the firmware")
        for name in fw:
            if name not in cat_pins:
                bad(f"{name} is in the firmware but not {source}")
        hellos = hello_prints(src.read_text(encoding="utf-8", errors="replace"))
        if cat.hello and not any(re.search(r"HELLO\s+" + re.escape(cat.hello), h) for h in hellos):
            bad(f"HELLO {cat.hello} not found in the firmware's HELLO print")
        if cat.hello and cat.chip and not any(cat.chip in h for h in hellos):
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
    if any(kicad_projects(d) for d in devices) and not kicad_cli():
        print("a device has a KiCad project: put kicad-cli on PATH or set KICAD_CLI to its file", file=sys.stderr)
        return 2
    problems = []
    for d in devices:
        problems += check_device(d, kit)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
