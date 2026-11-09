#!/usr/bin/env python3
"""Strip check: no two nets may share a copper strip of the ElectroCookie board.

Usage: python tools/strip_check.py [--board XML] [--tolerance MM] [--max-distance MM] [PCB ...]

Reads kicad/electrocookie_full.xml (the strips and holes of the board) and each .kicad_pcb
(default: devices/*/kicad/*.kicad_pcb). Every through-hole pad of a part other than the board is
assigned to its nearest hole (a footprint field Board_pads such as "1-7" or "1-3,5" limits a part
to the pads that enter the board), whatever the distance (a real lead always goes into some hole), and
each strip is checked for pads of different nets. A pad with no net counts as a net of its own.
Prints strip conflicts; "off-grid" warnings for pads more than the tolerance from their hole (bent
leads of 2.5 mm and 1.27 mm pitch parts, TO-92); and "no hole near enough" errors for pads more
than the maximum distance from every hole. Warnings do not fail the check.
Exit 0 when clean, 1 with conflicts or errors, 2 for unreadable input.
"""
import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOARD_XML = REPO / "kicad" / "electrocookie_full.xml"
BOARD_FOOTPRINT = "ElectroCookie_Full"
BOARD_REF = "PCB1"
TOLERANCE_MM = 0.5
MAX_DISTANCE_MM = 1.6

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([()])|([^\s()"]+)')


class StripError(Exception):
    pass


def parse_sexpr(text: str) -> list:
    """Parse KiCad S-expression text into nested lists; atoms and strings are str."""
    stack = [[]]
    for m in _TOKEN.finditer(text):
        if m.group(2) == "(":
            stack.append([])
        elif m.group(2) == ")":
            if len(stack) < 2:
                raise StripError("unbalanced ')'")
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(m.group(1) if m.group(1) is not None else m.group(3))
    if len(stack) != 1:
        raise StripError("unbalanced '('")
    return stack[0]


def _children(node: list, name: str):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def _at(node: list):
    """(x, y, angle) of a node's (at ...) child; zeros when absent."""
    found = _children(node, "at")
    if not found:
        return 0.0, 0.0, 0.0
    v = [float(a) for a in found[0][1:4]]
    return v[0], v[1], (v[2] if len(v) > 2 else 0.0)


@dataclass
class Pad:
    ref: str
    number: str
    x: float
    y: float
    net: str

    @property
    def label(self) -> str:
        return f"{self.ref}.{self.number}"


@dataclass
class Hole:
    id: str
    x: float
    y: float
    strip: str


def load_board(path: Path) -> list:
    try:
        root = ET.parse(path).getroot()
        holes = [Hole(h.get("id"), float(h.get("x")), float(h.get("y")), h.get("strip"))
                 for h in root.iter("hole")]
    except (OSError, ET.ParseError, TypeError, ValueError) as e:
        raise StripError(f"{path}: {e}")
    if not holes:
        raise StripError(f"{path}: no <hole> elements")
    declared = {s.get("id") for s in root.iter("strip")}
    for h in holes:
        if h.strip not in declared:
            raise StripError(f"{path}: hole {h.id} names undeclared strip {h.strip}")
    return holes


def _reference(fp: list) -> str:
    for p in _children(fp, "property"):
        if len(p) > 2 and p[1] == "Reference":
            return p[2]
    for t in _children(fp, "fp_text"):
        if len(t) > 2 and t[1] == "reference":
            return t[2]
    return "?"


def _board_pads(fp: list, ref: str):
    """Pad numbers named by the footprint's Board_pads field, or None without the field."""
    for p in _children(fp, "property"):
        if len(p) > 2 and p[1] == "Board_pads":
            value = p[2]
            break
    else:
        return None
    numbers = set()
    for part in value.split(","):
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not m or (m.group(2) and int(m.group(2)) < int(m.group(1))):
            raise StripError(f"{ref}: malformed Board_pads value {value!r}")
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        numbers.update(str(n) for n in range(lo, hi + 1))
    return numbers


def _net_name(pad: list):
    n = _children(pad, "net")
    if not n or len(n[0]) < 2:
        return None
    name = n[0][-1]
    return name or None


def read_pads(path: Path) -> list:
    """Through-hole pads of every footprint except the board, at absolute board positions.

    A footprint with a Board_pads field (e.g. "1-3,5") contributes only the pads it lists.
    """
    try:
        tree = parse_sexpr(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, StripError) as e:
        raise StripError(f"{path}: {e}")
    if not tree or not isinstance(tree[0], list) or not tree[0] or tree[0][0] != "kicad_pcb":
        raise StripError(f"{path}: not a kicad_pcb file")
    pads = []
    for fp in _children(tree[0], "footprint"):
        ref = _reference(fp)
        lib = fp[1] if len(fp) > 1 else ""
        if ref == BOARD_REF or lib.split(":")[-1] == BOARD_FOOTPRINT:
            continue
        listed = _board_pads(fp, ref)
        if listed is not None:
            missing = listed - {p[1] for p in _children(fp, "pad") if len(p) > 1}
            if missing:
                raise StripError(f"{path}: {ref}: Board_pads lists pads that do not exist: "
                                 f"{', '.join(sorted(missing, key=int))}")
        fx, fy, rot = _at(fp)
        back = any(l[1] == "B.Cu" for l in _children(fp, "layer") if len(l) > 1)
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for pad in _children(fp, "pad"):
            if len(pad) < 3 or pad[2] != "thru_hole":
                continue
            px, py, _ = _at(pad)
            if back:
                px = -px
            number = pad[1]
            if listed is not None and number not in listed:
                continue
            # KiCad's y axis points down, so a positive angle turns counter-clockwise on screen.
            x = fx + px * c + py * s
            y = fy - px * s + py * c
            net = _net_name(pad) or f"unconnected-({ref}-Pad{number})"
            pads.append(Pad(ref, number, x, y, net))
    return pads


def check_pads(pads: list, holes: list, tolerance: float = TOLERANCE_MM,
               max_distance: float = MAX_DISTANCE_MM):
    """Return (conflicts, warnings, errors): lists of message strings.

    Every pad goes to its nearest hole. Beyond the tolerance it also warns; beyond the maximum
    distance it is an error as well.
    """
    strips = {}
    warnings = []
    errors = []
    for pad in pads:
        best = min(holes, key=lambda h: math.hypot(h.x - pad.x, h.y - pad.y))
        d = math.hypot(best.x - pad.x, best.y - pad.y)
        where = (f"{pad.label} ({pad.net}) at ({pad.x:.2f}, {pad.y:.2f}) is {d:.2f} mm from "
                 f"the nearest hole {best.id} (strip {best.strip})")
        if d > max_distance:
            errors.append(f"no hole near enough: {where}")
        elif d > tolerance:
            warnings.append(f"off-grid: {where}")
        strips.setdefault(best.strip, {}).setdefault(pad.net, []).append(pad.label)
    conflicts = []
    for strip in sorted(strips):
        nets = strips[strip]
        if len(nets) > 1:
            parts = "; ".join(f"{n} ({', '.join(p)})" for n, p in sorted(nets.items()))
            conflicts.append(f"strip {strip}: {len(nets)} nets share it: {parts}")
    return conflicts, warnings, errors


def default_pcbs() -> list:
    return sorted((REPO / "devices").glob("*/kicad/*.kicad_pcb"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pcb", nargs="*", help=".kicad_pcb files (default: devices/*/kicad/*.kicad_pcb)")
    ap.add_argument("--board", default=str(BOARD_XML), help="board strip model XML")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE_MM,
                    help="max pad-to-hole distance in mm (default %(default)s)")
    ap.add_argument("--max-distance", type=float, default=MAX_DISTANCE_MM,
                    help="pads farther than this from every hole are errors (default %(default)s)")
    args = ap.parse_args(argv)
    try:
        holes = load_board(Path(args.board))
        pcbs = [Path(p) for p in args.pcb] or default_pcbs()
        failed = False
        for pcb in pcbs:
            conflicts, warnings, errors = check_pads(read_pads(pcb), holes, args.tolerance,
                                                     args.max_distance)
            for w in warnings:
                print(f"{pcb}: warning: {w}")
            for e in errors:
                print(f"{pcb}: error: {e}")
            for c in conflicts:
                print(f"{pcb}: {c}")
            failed = failed or bool(conflicts or errors)
    except StripError as e:
        print(e, file=sys.stderr)
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
