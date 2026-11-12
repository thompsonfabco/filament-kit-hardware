#!/usr/bin/env python3
"""Checked protoboard drawings for the DIY builds on the ElectroCookie full board.

A placement file (devices/<device>/protoboard/<hand>.xml) says which hole each part pin sits in, which wire
links are fitted and which rail bridges are fitted. This tool builds the board's connectivity from its copper
(strips, rails, the rails' edge traces), the bridges, the wires and the part pins, and compares it with the
device's KiCad netlist: every net must be one connected group, no group may join two nets, every pin of an
on-board part must be placed, and no hole may hold two leads. It also checks the drawing rules: each wire is
straight or has one bend, never runs over a used hole, a part body, a mounting hole or another wire, and is
labelled with the net it really carries.

    python tools/protoboard.py check  devices/printer-station/protoboard/power-left.xml [--netlist N.xml]
    python tools/protoboard.py render devices/printer-station/protoboard/power-left.xml [--pdf]

check exits 0 when the board matches the netlist, 1 with each problem named, 2 when a file can't be read
or the netlist can't be exported. render runs the check first and writes <hand>-top.svg, <hand>-solder.svg
and <hand>-steps.md beside the placement file; --pdf also writes <hand>-a4.pdf and <hand>-letter.pdf
(needs Microsoft Edge or Chrome). The netlist comes from the schematic named in the placement file,
exported with kicad-cli (KICAD_CLI or PATH), unless --netlist gives a kicadxml netlist.

Board model (top view, mm from the board's top-left corner). Holes are named as printed on the board: a letter
A-J and a number 1-30, so C12 is letter C, number 12.
- The numbers 1-30 run left to right; number k is at x = 7.67 + 2.54 (k - 1).
- Letters J I H G F are the top half (J nearest the top edge) and E D C B A the bottom half. At each number,
  holes F-J are joined by one copper strip and A-E by another. A 7.62 mm channel with no copper separates F and E.
- Four rails of 30 holes, one at each number: top - (outer), top + (inner), bottom - (inner), bottom + (outer).
- The two + rails are joined by an unmarked edge trace at the number 1 end and the two - rails by one at the
  number 30 end. Each trace is broken at a pair of pads beside the M3 hole (+ on the left, - on the right),
  so a rail's top and bottom halves are joined only when a wire link bridges that pad pair.
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------------------------- board

BOARD_W, BOARD_H = 89.0, 52.0
PITCH = 2.54
NCOLS = 30
TOP_ROWS = "JIHGF"      # top to bottom
BOTTOM_ROWS = "EDCBA"   # top to bottom
ROW_Y = {"J": 12.03, "I": 14.57, "H": 17.11, "G": 19.65, "F": 22.19,
         "E": 29.81, "D": 32.35, "C": 34.89, "B": 37.43, "A": 39.97}
RAIL_Y = {"T-": 3.4, "T+": 5.9, "B-": 46.7, "B+": 49.0}
RAIL_TEXT = {"T-": "top − rail", "T+": "top + rail", "B-": "bottom − rail", "B+": "bottom + rail"}
# Bridge pad pairs beside the M3 holes: the + path's pads on the left, the - path's on the right.
PADS = {"PL1": (5.1, 24.7), "PL2": (5.1, 27.3), "PR1": (86.6, 24.7), "PR2": (86.6, 27.3)}
PAD_TEXT = {"PL1": "left link pad, upper", "PL2": "left link pad, lower",
            "PR1": "right link pad, upper", "PR2": "right link pad, lower"}
# Edge traces: each pad belongs to the rail half it is wired to.
PAD_RAIL = {"PL1": "T+", "PL2": "B+", "PR1": "T-", "PR2": "B-"}
BRIDGE_PADS = {"+": ("PL1", "PL2"), "-": ("PR1", "PR2")}
M3_HOLES = [(7.75, 26.0), (81.25, 26.0)]
M2_HOLES = [(5.375, 8.25), (83.625, 8.25), (5.375, 43.75), (83.625, 43.75)]
M3_KEEPOUT = 2.9    # screw head radius plus margin
M2_KEEPOUT = 2.0
HOLE_R = 0.9        # copper ring radius, for "passes over a hole"
DRILL_R = 0.6
# A hole beside a part body still takes a lead (a 0.64 mm wire) while its centre is clear of the body: a
# JST-XH body covers 0.41-0.51 mm of the 1.2 mm drill on its shallow side and at its ends, leaving 0.69 mm.
LEAD_CLEAR = 0.05
WIRE_R = 0.15       # a wire may lie against a part body but not over it
PAD_STUB = 0.7      # the length of wire over its own pad, where it may touch a neighbouring body edge


def col_x(k: int) -> float:
    return 7.67 + PITCH * (k - 1)


@dataclass(frozen=True)
class Hole:
    name: str
    x: float
    y: float
    conductor: str      # copper the hole belongs to before any wire or bridge

    @property
    def text(self) -> str:
        """The hole as a builder reads it: "C12", "top + rail at number 12", "left link pad, upper"."""
        if self.name[:2] in RAIL_Y:
            return f"{RAIL_TEXT[self.name[:2]]} at number {self.name[2:]}"
        if self.name in PAD_TEXT:
            return PAD_TEXT[self.name]
        return self.name


def build_holes() -> dict[str, Hole]:
    holes: dict[str, Hole] = {}
    for k in range(1, NCOLS + 1):
        x = col_x(k)
        for r in TOP_ROWS:
            holes[f"{r}{k}"] = Hole(f"{r}{k}", x, ROW_Y[r], f"strip {k} F-J")
        for r in BOTTOM_ROWS:
            holes[f"{r}{k}"] = Hole(f"{r}{k}", x, ROW_Y[r], f"strip {k} A-E")
        for rail, y in RAIL_Y.items():
            holes[f"{rail}{k}"] = Hole(f"{rail}{k}", x, y, f"rail {rail}")
    for name, (x, y) in PADS.items():
        holes[name] = Hole(name, x, y, f"rail {PAD_RAIL[name]}")
    return holes


HOLES = build_holes()
GRID = {(round(h.x, 2), round(h.y, 2)): h for h in HOLES.values()}

# ---------------------------------------------------------------------------------------------- parts


class PlacementError(Exception):
    pass


@dataclass
class Part:
    ref: str
    kind: str
    value: str
    pins: dict[str, str]                    # pin number -> hole name
    attrs: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)   # pin number -> pin name shown on the drawing

    def xy(self, pin: str) -> tuple[float, float]:
        h = HOLES[self.pins[pin]]
        return h.x, h.y


# Pin names, by kind, for the drawing. A JST's names come from the placement file (they are the net order).
C3_POWER_LEFT = {  # pad -> (name, side, index from the USB end); top view with USB up, power row on the left
    "9": ("5V", "L", 0), "10": ("G", "L", 1), "11": ("3V3", "L", 2), "12": ("4", "L", 3),
    "13": ("3", "L", 4), "14": ("2", "L", 5), "15": ("1", "L", 6), "16": ("0", "L", 7),
    "1": ("5", "R", 0), "2": ("6", "R", 1), "3": ("7", "R", 2), "4": ("8", "R", 3),
    "5": ("9", "R", 4), "6": ("10", "R", 5), "7": ("20", "R", 6), "8": ("21", "R", 7),
}
TO92_NAMES = {"1": "D", "2": "G", "3": "S"}
DIODE_NAMES = {"1": "K", "2": "A"}

DIRS = {"up": (0.0, -1.0), "down": (0.0, 1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}


def _unit(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n else (0.0, 0.0)


def _strip_of(hole: str) -> str:
    return HOLES[hole].conductor


def module_frame(part: Part) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """For the C3 module: (USB direction, power-row side direction, centre). Raises on a bad or mirrored placement.

    In the module's own top view (USB up) the power row is on the left for a power-left module. Pins i
    (0 = USB end) of each row sit at 2.54 mm steps away from the USB end; the rows are 15.24 mm apart.
    """
    hand = part.attrs.get("hand", "")
    if hand != "power-left":
        raise PlacementError(f"{part.ref}: only hand=\"power-left\" C3 modules are drawn so far")
    need = set(C3_POWER_LEFT)
    if set(part.pins) != need:
        raise PlacementError(f"{part.ref}: the C3 module needs pins 1-16, got {sorted(part.pins, key=int)}")
    p = {n: part.xy(n) for n in need}
    l0, l7, r0 = p["9"], p["16"], p["1"]
    usb = _unit(l0[0] - l7[0], l0[1] - l7[1])          # from the far end toward the USB end
    left = _unit(l0[0] - r0[0], l0[1] - r0[1])          # from the right row toward the power row
    # Check every pin against the rigid model.
    for n, (_, side, i) in C3_POWER_LEFT.items():
        base = l0 if side == "L" else r0
        ex = (base[0] - usb[0] * PITCH * i, base[1] - usb[1] * PITCH * i)
        if math.dist(ex, p[n]) > 0.05:
            raise PlacementError(f"{part.ref}: pin {n} ({C3_POWER_LEFT[n][0]}) is in {part.pins[n]}, "
                                 f"which doesn't fit a C3 module on two 1x8 rows")
    if abs(math.dist(l0, r0) - 6 * PITCH) > 0.05:
        raise PlacementError(f"{part.ref}: the two pin rows must be 15.24 mm (6 holes) apart")
    # Handedness: seen from above with USB up, the power row must be on the left. "Up" is usb; the viewer's
    # left of "up" in y-down screen coordinates is (usb.y, -usb.x).
    viewer_left = (usb[1], -usb[0])
    if viewer_left[0] * left[0] + viewer_left[1] * left[1] < 0.9:
        raise PlacementError(f"{part.ref}: these pin holes describe a mirrored module: with USB up the power "
                             "row would be on the right, which is the power-right module")
    cx = (l0[0] + l7[0] + r0[0] + p["8"][0]) / 4
    cy = (l0[1] + l7[1] + r0[1] + p["8"][1]) / 4
    return usb, left, (cx, cy)


def body_shapes(part: Part) -> list[tuple]:
    """Board-level bodies, as ("rect", corners...) polygons in board mm. The C3 module itself sits raised on
    its sockets and is not included; its two socket strips are."""
    k = part.kind
    shapes: list[tuple] = []
    if k == "c3-supermini":
        usb, left, _ = module_frame(part)
        for row in ("L", "R"):
            ends = [part.xy(n) for n, (_, s, i) in C3_POWER_LEFT.items() if s == row and i in (0, 7)]
            shapes.append(_rect_along(ends[0], ends[1], 1.27, 1.27, 1.27))
    elif k == "jst-xh":
        pins = sorted(part.pins, key=int)
        a, b = part.xy(pins[0]), part.xy(pins[-1])
        latch = DIRS[part.attrs["latch"]]
        shapes.append(_rect_along(a, b, 2.45, 2.35, 3.4, latch))
    elif k == "to92":
        a, b = part.xy("1"), part.xy("3")
        flat = DIRS[part.attrs["flat"]]
        shapes.append(_rect_along(a, b, 0.25, 2.45, 1.75, flat))
    elif k in ("resistor", "diode"):
        a, b = part.xy("1"), part.xy("2")
        length, width = (6.3, 2.5) if k == "resistor" else (5.2, 2.7)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        u = _unit(b[0] - a[0], b[1] - a[1])
        half = length / 2
        p0 = (mx - u[0] * half, my - u[1] * half)
        p1 = (mx + u[0] * half, my + u[1] * half)
        shapes.append(_rect_along(p0, p1, 0.0, width / 2, width / 2))
    return shapes


def _rect_along(a, b, over, w_neg, w_pos, pos_dir=None):
    """Rectangle around the segment a-b, extended by `over` past each end, w_neg to one side and w_pos to the
    side `pos_dir` (default: the left-hand normal). Returns ("poly", [4 points])."""
    u = _unit(b[0] - a[0], b[1] - a[1])
    n = (-u[1], u[0])
    if pos_dir is not None and n[0] * pos_dir[0] + n[1] * pos_dir[1] < 0:
        n = (-n[0], -n[1])
    s = (a[0] - u[0] * over, a[1] - u[1] * over)
    e = (b[0] + u[0] * over, b[1] + u[1] * over)
    pts = [(s[0] - n[0] * w_neg, s[1] - n[1] * w_neg), (e[0] - n[0] * w_neg, e[1] - n[1] * w_neg),
           (e[0] + n[0] * w_pos, e[1] + n[1] * w_pos), (s[0] + n[0] * w_pos, s[1] + n[1] * w_pos)]
    return ("poly", pts)


def point_in_poly(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def dist_point_poly(pt, poly) -> float:
    """0 inside, else the distance to the polygon's edge."""
    if point_in_poly(pt, poly):
        return 0.0
    return min(dist_point_seg(pt, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def dist_point_seg(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def polys_overlap(P, Q) -> bool:
    if any(point_in_poly(a, Q) for a in P) or any(point_in_poly(a, P) for a in Q):
        return True
    return any(segs_intersect(P[i], P[(i + 1) % len(P)], Q[j], Q[(j + 1) % len(Q)])
               for i in range(len(P)) for j in range(len(Q)))


def hole_blocked(x: float, y: float, poly) -> bool:
    """A hole under a part body can't take a lead."""
    return dist_point_poly((x, y), poly) < LEAD_CLEAR


def wire_hits_body(a, b, poly) -> bool:
    """A wire leg a-b, less the stub over each end's own pad, comes within WIRE_R of a body."""
    L = math.dist(a, b)
    if L <= 2 * PAD_STUB:
        return False
    u = _unit(b[0] - a[0], b[1] - a[1])
    a2 = (a[0] + u[0] * PAD_STUB, a[1] + u[1] * PAD_STUB)
    b2 = (b[0] - u[0] * PAD_STUB, b[1] - u[1] * PAD_STUB)
    return seg_hits_poly(a2, b2, poly, WIRE_R)


def seg_hits_poly(a, b, poly, clearance=0.0) -> bool:
    if point_in_poly(a, poly) or point_in_poly(b, poly):
        return True
    n = len(poly)
    for i in range(n):
        if segs_intersect(a, b, poly[i], poly[(i + 1) % n]):
            return True
    if clearance > 0:
        return any(dist_point_seg(v, a, b) < clearance for v in poly) or \
            min(dist_point_poly(a, poly), dist_point_poly(b, poly)) < clearance
    return False


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segs_intersect(p1, p2, q1, q2) -> bool:
    d1, d2 = _orient(q1, q2, p1), _orient(q1, q2, p2)
    d3, d4 = _orient(p1, p2, q1), _orient(p1, p2, q2)
    if ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and \
            ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9)):
        return True
    return False


def collinear_overlap(p1, p2, q1, q2, tol=0.3) -> bool:
    """Two segments lying on one line (within tol) and sharing more than a point."""
    if abs(_orient(p1, p2, q1)) > tol * math.dist(p1, p2) or abs(_orient(p1, p2, q2)) > tol * math.dist(p1, p2):
        return False
    u = _unit(p2[0] - p1[0], p2[1] - p1[1])
    t = lambda p: (p[0] - p1[0]) * u[0] + (p[1] - p1[1]) * u[1]
    a0, a1 = 0.0, math.dist(p1, p2)
    b0, b1 = sorted((t(q1), t(q2)))
    return min(a1, b1) - max(a0, b0) > 0.3


# ---------------------------------------------------------------------------------------------- placement file


@dataclass
class Wire:
    net: str
    a: str
    b: str
    route: str = ""         # "" straight, "hv" horizontal then vertical, "vh" vertical then horizontal

    def points(self) -> list[tuple[float, float]]:
        ha, hb = HOLES[self.a], HOLES[self.b]
        if self.route == "hv":
            return [(ha.x, ha.y), (hb.x, ha.y), (hb.x, hb.y)]
        if self.route == "vh":
            return [(ha.x, ha.y), (ha.x, hb.y), (hb.x, hb.y)]
        return [(ha.x, ha.y), (hb.x, hb.y)]

    def segments(self):
        pts = self.points()
        return list(zip(pts, pts[1:]))

    @property
    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in self.segments())


@dataclass
class Placement:
    path: Path
    device: str
    hand: str
    schematic: Path | None
    offboard: dict[str, str]
    parts: list[Part]
    wires: list[Wire]
    bridges: list[str]
    title: str = ""


def load_placement(path: Path) -> Placement:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as e:
        raise PlacementError(f"{path}: cannot read: {e}")
    if root.tag != "protoboard":
        raise PlacementError(f"{path}: the root element must be <protoboard>")
    sch = root.find("netlist")
    schematic = (path.parent / sch.get("schematic")).resolve() if sch is not None and sch.get("schematic") else None
    offboard = {e.get("ref"): (e.text or "").strip() for e in root.findall("offboard")}
    parts = []
    for e in root.findall("part"):
        pins = {}
        names = {}
        for p in e.findall("pin"):
            n, h = p.get("n"), p.get("hole")
            if h not in HOLES:
                raise PlacementError(f"{path}: {e.get('ref')} pin {n}: no hole named {h!r}")
            if n in pins:
                raise PlacementError(f"{path}: {e.get('ref')} pin {n} is listed twice")
            pins[n] = h
            if p.get("name"):
                names[n] = p.get("name")
        attrs = {k: v for k, v in e.attrib.items() if k not in ("ref", "kind", "value")}
        parts.append(Part(e.get("ref"), e.get("kind"), e.get("value", ""), pins, attrs, names))
    wires = []
    for e in root.findall("wire"):
        a, b = e.get("from"), e.get("to")
        for h in (a, b):
            if h not in HOLES:
                raise PlacementError(f"{path}: wire {a} to {b}: no hole named {h!r}")
        route = e.get("route", "")
        if route not in ("", "hv", "vh"):
            raise PlacementError(f"{path}: wire {a} to {b}: route must be hv or vh")
        wires.append(Wire(e.get("net", ""), a, b, route))
    bridges = []
    for e in root.findall("bridge"):
        r = e.get("rail")
        if r not in BRIDGE_PADS:
            raise PlacementError(f"{path}: bridge rail must be + or -, got {r!r}")
        bridges.append(r)
    return Placement(path, root.get("device", ""), root.get("hand", ""), schematic, offboard, parts, wires,
                     bridges, root.get("title", ""))


# ---------------------------------------------------------------------------------------------- netlist


def kicad_cli() -> str | None:
    env = os.environ.get("KICAD_CLI")
    if env:
        return env if Path(env).is_file() else None
    return shutil.which("kicad-cli")


def load_netlist(xml_path: Path) -> dict[str, set[tuple[str, str]]]:
    """Net name (leading "/" dropped) -> {(ref, pin)}."""
    try:
        root = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError) as e:
        raise PlacementError(f"{xml_path}: cannot read netlist: {e}")
    nets: dict[str, set[tuple[str, str]]] = {}
    for n in root.iter("net"):
        name = n.get("name", "").lstrip("/")
        nets[name] = {(x.get("ref"), x.get("pin")) for x in n.iter("node")}
    if not nets:
        raise PlacementError(f"{xml_path}: no nets in the netlist")
    return nets


def export_netlist(sch: Path, out: Path) -> None:
    cli = kicad_cli()
    if not cli:
        raise PlacementError(f"{sch}: no kicad-cli: put it on PATH or set KICAD_CLI to its file")
    r = subprocess.run([cli, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out), str(sch)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.is_file():
        raise PlacementError(f"{sch}: kicad-cli netlist export failed: {r.stderr.strip() or r.stdout.strip()}")


def netlist_for(pl: Placement, netlist: Path | None) -> dict[str, set[tuple[str, str]]]:
    if netlist is not None:
        return load_netlist(netlist)
    if pl.schematic is None:
        raise PlacementError(f"{pl.path}: no <netlist schematic=...> and no --netlist given")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "net.xml"
        export_netlist(pl.schematic, out)
        return load_netlist(out)


# ---------------------------------------------------------------------------------------------- check


class UnionFind:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, a: str) -> str:
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def connectivity(pl: Placement) -> UnionFind:
    """Union-find over conductor names and "ref.pin" nodes."""
    uf = UnionFind()
    for h in HOLES.values():
        uf.find(h.conductor)
    for r in pl.bridges:
        a, b = BRIDGE_PADS[r]
        uf.union(HOLES[a].conductor, HOLES[b].conductor)
    for w in pl.wires:
        uf.union(HOLES[w.a].conductor, HOLES[w.b].conductor)
    for p in pl.parts:
        for n, h in p.pins.items():
            uf.union(f"{p.ref}.{n}", HOLES[h].conductor)
    return uf


def check(pl: Placement, nets: dict[str, set[tuple[str, str]]]) -> Report:
    rep = Report()
    err = rep.errors.append
    placed = {p.ref: p for p in pl.parts}
    refs_in_netlist = {ref for members in nets.values() for ref, _ in members}

    # Every netlist part is either placed or declared off-board, and never both.
    for ref in sorted(refs_in_netlist):
        if ref not in placed and ref not in pl.offboard:
            err(f"{ref}: in the netlist but neither placed nor listed as <offboard>")
        if ref in placed and ref in pl.offboard:
            err(f"{ref}: both placed and listed as <offboard>")
    for ref in placed:
        if ref not in refs_in_netlist:
            err(f"{ref}: placed but not in the netlist")
    for ref in pl.offboard:
        if ref not in refs_in_netlist:
            err(f"{ref}: listed as <offboard> but not in the netlist")

    # Every pin of a placed part is placed, and no placed pin is unknown.
    node_net: dict[tuple[str, str], str] = {}
    for name, members in nets.items():
        for m in members:
            node_net[m] = name
    for p in pl.parts:
        want = {pin for (ref, pin) in node_net if ref == p.ref}
        for pin in sorted(want - set(p.pins)):
            err(f"{p.ref} pin {pin} (net {node_net[(p.ref, pin)]}): not placed")
        for pin in sorted(set(p.pins) - want):
            err(f"{p.ref} pin {pin}: placed but not in the netlist")

    # Holes: each holds at most one lead (a part pin, a wire end or a bridge end).
    use: dict[str, list[str]] = {}
    for p in pl.parts:
        for n, h in p.pins.items():
            use.setdefault(h, []).append(f"{p.ref} pin {n}")
    for i, w in enumerate(pl.wires, 1):
        for h in (w.a, w.b):
            use.setdefault(h, []).append(f"wire {i} ({w.net}, {w.a}-{w.b})")
        if w.a == w.b:
            err(f"wire {i} ({w.net}): both ends in {w.a}")
    for r in pl.bridges:
        for h in BRIDGE_PADS[r]:
            use.setdefault(h, []).append(f"{r} rail link")
    for h, users in sorted(use.items()):
        if len(users) > 1:
            err(f"hole {HOLES[h].text}: used twice ({'; '.join(users)})")

    # Part geometry (module handedness, pin rows, lead spans).
    for p in pl.parts:
        try:
            _check_part_geometry(p)
        except PlacementError as e:
            err(str(e))

    # Connectivity against the netlist.
    uf = connectivity(pl)
    group_nets: dict[str, set[str]] = {}
    for p in pl.parts:
        for n in p.pins:
            net = node_net.get((p.ref, n))
            if net is not None:
                group_nets.setdefault(uf.find(f"{p.ref}.{n}"), set()).add(net)
    for g, gnets in group_nets.items():
        if len(gnets) > 1:
            err(f"short: nets {', '.join(sorted(gnets))} are joined on the board")
    for name, members in sorted(nets.items()):
        on = [(r, pn) for r, pn in members if r in placed and pn in placed[r].pins]
        groups = {uf.find(f"{r}.{pn}") for r, pn in on}
        if len(groups) > 1:
            parts_by_group: dict[str, list[str]] = {}
            for r, pn in sorted(on):
                parts_by_group.setdefault(uf.find(f"{r}.{pn}"), []).append(f"{r}.{pn}")
            split = " | ".join(" ".join(v) for v in parts_by_group.values())
            err(f"open: net {name} is split into {len(groups)} groups: {split}")

    # Each wire carries the net it is labelled with; no wire or rail half leads nowhere.
    for i, w in enumerate(pl.wires, 1):
        g = uf.find(HOLES[w.a].conductor)
        gnets = group_nets.get(g, set())
        if not gnets:
            err(f"wire {i} ({w.net}, {w.a}-{w.b}): joins copper that carries no part pin")
        elif w.net not in gnets:
            err(f"wire {i} ({w.a}-{w.b}): labelled {w.net} but carries {', '.join(sorted(gnets))}")
    for r in pl.bridges:
        g = uf.find(HOLES[BRIDGE_PADS[r][0]].conductor)
        if not group_nets.get(g):
            err(f"{r} rail link: bridges rails that carry no part pin")

    _check_drawing(pl, rep)
    rep.stats.update(wires=len(pl.wires), bridges=len(pl.bridges), parts=len(pl.parts),
                     nets=sum(1 for n, m in nets.items() if any(r in placed for r, _ in m)))
    return rep


def _check_part_geometry(p: Part) -> None:
    k = p.kind
    if k == "c3-supermini":
        module_frame(p)
        return
    if k == "jst-xh":
        n = len(p.pins)
        if p.attrs.get("latch") not in DIRS:
            raise PlacementError(f"{p.ref}: a JST-XH needs latch=\"up|down|left|right\"")
        pts = [p.xy(str(i)) for i in range(1, n + 1)]
        _check_in_line(p, pts, "a JST-XH's pins must sit in one row of adjacent holes, in pin order")
        u = _unit(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        lat = DIRS[p.attrs["latch"]]
        if abs(u[0] * lat[0] + u[1] * lat[1]) > 0.01:
            raise PlacementError(f"{p.ref}: latch must face across the pin row, not along it")
        return
    if k == "to92":
        if p.attrs.get("flat") not in DIRS:
            raise PlacementError(f"{p.ref}: a TO-92 needs flat=\"up|down|left|right\"")
        pts = [p.xy(str(i)) for i in (1, 2, 3)]
        _check_in_line(p, pts, "a TO-92's three legs must sit in adjacent holes in one row")
        f = DIRS[p.attrs["flat"]]
        right = (f[1], -f[0])       # the right hand of someone facing the flat face
        d = (pts[2][0] - pts[0][0], pts[2][1] - pts[0][1])
        if d[0] * right[0] + d[1] * right[1] <= 0:
            raise PlacementError(f"{p.ref}: with the flat face {p.attrs['flat']}, legs 1-2-3 must run left to right "
                                 "as seen facing the flat face")
        return
    if k in ("resistor", "diode"):
        a, b = p.xy("1"), p.xy("2")
        span = math.dist(a, b)
        if abs(a[0] - b[0]) > 0.01 and abs(a[1] - b[1]) > 0.01:
            raise PlacementError(f"{p.ref}: lay it along a letter or a number, not diagonally")
        if span < 7.6:
            raise PlacementError(f"{p.ref}: its leads are {span:.2f} mm apart; the body needs at least 7.62")
        return
    raise PlacementError(f"{p.ref}: unknown kind {k!r}")


def _check_in_line(p: Part, pts, msg: str) -> None:
    for a, b in zip(pts, pts[1:]):
        if abs(math.dist(a, b) - PITCH) > 0.05:
            raise PlacementError(f"{p.ref}: {msg}")
    if len(pts) > 2 and any(abs(_orient(pts[0], pts[-1], q)) > 0.05 for q in pts):
        raise PlacementError(f"{p.ref}: {msg}")


def used_holes(pl: Placement) -> set[str]:
    s = {h for p in pl.parts for h in p.pins.values()}
    s |= {h for w in pl.wires for h in (w.a, w.b)}
    s |= {h for r in pl.bridges for h in BRIDGE_PADS[r]}
    return s


def bridge_points(r: str):
    a, b = BRIDGE_PADS[r]
    return [(HOLES[a].x, HOLES[a].y), (HOLES[b].x, HOLES[b].y)]


def _check_drawing(pl: Placement, rep: Report) -> None:
    err = rep.errors.append
    used = used_holes(pl)
    bodies = [(p.ref, s) for p in pl.parts for s in body_shapes(p)]
    # Part bodies must not overlap each other.
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            if bodies[i][0] != bodies[j][0] and polys_overlap(bodies[i][1][1], bodies[j][1][1]):
                err(f"{bodies[i][0]} and {bodies[j][0]}: their bodies overlap")
    # No body may sit on a mounting hole's screw head (U1's sockets included; U1 itself is raised above them).
    for ref, (_, poly) in bodies:
        for (mx, my) in M3_HOLES:
            if dist_point_poly((mx, my), poly) < M3_KEEPOUT:
                err(f"{ref}: its body covers an M3 mounting hole's screw head")
        for (mx, my) in M2_HOLES:
            if dist_point_poly((mx, my), poly) < M2_KEEPOUT:
                err(f"{ref}: its body covers an M2 mounting hole")
    by_ref = {p.ref: p for p in pl.parts}
    # A hole squeezed between two bodies, each covering part of it, can't take a lead either.
    for h in used:
        hh = HOLES[h]
        others = [poly for ref, (_, poly) in bodies if h not in by_ref[ref].pins.values()]
        cover = sum(max(0.0, DRILL_R - dist_point_poly((hh.x, hh.y), poly)) for poly in others)
        if cover > 2 * DRILL_R - 0.65 and not any(hole_blocked(hh.x, hh.y, poly) for poly in others):
            err(f"hole {hh.text}: squeezed between two part bodies, too little of it is open for a lead")
    # Holes under a part body can't take a lead.
    for ref, (_, poly) in bodies:
        own = set(next(p for p in pl.parts if p.ref == ref).pins.values())
        for h in used - own:
            if hole_blocked(HOLES[h].x, HOLES[h].y, poly):
                err(f"hole {HOLES[h].text}: under {ref}'s body, so it can't take a lead")
    # The leads and body of a resistor or diode run from pin to pin and must not cover another lead's hole.
    for p in pl.parts:
        if p.kind in ("resistor", "diode"):
            a, b = p.xy("1"), p.xy("2")
            for h in used - set(p.pins.values()):
                hh = HOLES[h]
                if dist_point_seg((hh.x, hh.y), a, b) < HOLE_R:
                    err(f"{p.ref}: its lead or body runs over hole {hh.text}, which is in use")
    segs = []
    for i, w in enumerate(pl.wires, 1):
        for s in w.segments():
            segs.append((i, w, s))
        ends = {w.a, w.b}
        for a, b in w.segments():
            for h in used - ends:
                hh = HOLES[h]
                if dist_point_seg((hh.x, hh.y), a, b) < HOLE_R:
                    err(f"wire {i} ({w.net}, {w.a}-{w.b}): runs over hole {hh.text}, which is in use")
            for ref, (_, poly) in bodies:
                if wire_hits_body(a, b, poly):
                    err(f"wire {i} ({w.net}, {w.a}-{w.b}): runs over {ref}'s body")
            for (mx, my) in M3_HOLES:
                if dist_point_seg((mx, my), a, b) < M3_KEEPOUT:
                    err(f"wire {i} ({w.net}, {w.a}-{w.b}): runs over an M3 mounting hole's screw head")
            for (mx, my) in M2_HOLES:
                if dist_point_seg((mx, my), a, b) < M2_KEEPOUT:
                    err(f"wire {i} ({w.net}, {w.a}-{w.b}): runs over an M2 mounting hole")
            if a[0] != b[0] and a[1] != b[1]:
                err(f"wire {i} ({w.net}, {w.a}-{w.b}): a leg runs diagonally; use a straight run or one bend")
    for r in pl.bridges:
        a, b = bridge_points(r)
        segs.append((f"{r} link", None, (a, b)))
    crossings = 0
    for x in range(len(segs)):
        for y in range(x + 1, len(segs)):
            i, wi, (a, b) = segs[x]
            j, wj, (c, d) = segs[y]
            if i == j:
                continue
            if collinear_overlap(a, b, c, d):
                err(f"wires {i} and {j}: lie on top of each other")
            elif segs_intersect(a, b, c, d):
                crossings += 1
    under = 0
    for p in pl.parts:
        if p.kind == "c3-supermini":
            poly = module_outline(p)
            for i, w in enumerate(pl.wires, 1):
                if any(seg_hits_poly(a, b, poly) for a, b in w.segments()):
                    under += 1
    rep.stats["crossings"] = crossings
    rep.stats["wires_under_module"] = under
    if crossings:
        rep.notes.append(f"{crossings} wire crossing(s): insulated wire, one lies over the other")


def module_outline(p: Part):
    """The C3 Super Mini's outline in board mm: 18 x 22.52 mm, the USB-C end 3.5 mm past the end pins."""
    usb, left, (cx, cy) = module_frame(p)
    l0 = p.xy("9")
    l7 = p.xy("16")
    mid_usb = ((l0[0] + p.xy("1")[0]) / 2, (l0[1] + p.xy("1")[1]) / 2)
    mid_far = ((l7[0] + p.xy("8")[0]) / 2, (l7[1] + p.xy("8")[1]) / 2)
    a = (mid_far[0] - usb[0] * 1.24, mid_far[1] - usb[1] * 1.24)
    b = (mid_usb[0] + usb[0] * 3.5, mid_usb[1] + usb[1] * 3.5)
    return _rect_along(a, b, 0.0, 9.0, 9.0)[1]


# ---------------------------------------------------------------------------------------------- cli


def cmd_check(args) -> int:
    try:
        pl = load_placement(Path(args.placement))
        nets = netlist_for(pl, Path(args.netlist) if args.netlist else None)
    except PlacementError as e:
        print(e, file=sys.stderr)
        return 2
    rep = check(pl, nets)
    for e in rep.errors:
        print(f"ERROR {e}")
    for n in rep.notes:
        print(f"note  {n}")
    s = rep.stats
    verdict = "FAIL" if rep.errors else "OK"
    print(f"{verdict} {pl.path.name}: {s.get('parts', 0)} parts, {s.get('wires', 0)} wires, "
          f"{s.get('bridges', 0)} rail links, {s.get('nets', 0)} nets checked, {len(rep.errors)} problems")
    return 1 if rep.errors else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("placement")
    c.add_argument("--netlist")
    r = sub.add_parser("render")
    r.add_argument("placement")
    r.add_argument("--netlist")
    r.add_argument("--pdf", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    return cmd_render(args)


# ---------------------------------------------------------------------------------------------- drawing

# One colour per net (Okabe-Ito based, colour-blind safe), with power and ground drawn thicker.
NET_STYLE = {
    "GND": ("#000000", "GND", "ground"),
    "5V": ("#D55E00", "5V", "power"),
    "3V3": ("#CC79A7", "3V3", "power"),
    "SDA": ("#0072B2", "SDA", "signal"),
    "SCL": ("#56B4E9", "SCL", "signal"),
    "ENC_CLK": ("#009E73", "CLK", "signal"),
    "ENC_DT": ("#E69F00", "DT", "signal"),
    "ENC_SW": ("#B8A100", "SW", "signal"),
    "BUZZER": ("#8C564B", "BUZ", "signal"),
    "BZ_G": ("#7F7F7F", "GATE", "signal"),
    "BZ-": ("#6A3D9A", "BZ\u2212", "signal"),
}
NET_TEXT = {
    "GND": "ground", "5V": "USB 5 V", "3V3": "3.3 V from the C3", "SDA": "I2C data, GPIO 5",
    "SCL": "I2C clock, GPIO 6", "ENC_CLK": "encoder A, GPIO 3", "ENC_DT": "encoder B, GPIO 4",
    "ENC_SW": "encoder switch, GPIO 1", "BUZZER": "buzzer drive, GPIO 0", "BZ_G": "Q1 gate",
    "BZ-": "buzzer \u2212 / Q1 drain",
}
RES_BANDS = {"220": ["#d62728", "#d62728", "#7f4f24", "#c9a227"],
             "100k": ["#7f4f24", "#111111", "#f2d000", "#c9a227"]}
SHEET_W = 128.0
BX, BY = 19.5, 36.0      # board origin on the sheet


def net_style(net: str):
    return NET_STYLE.get(net, ("#555555", net, "signal"))


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self):
        self.out: list[str] = []

    def add(self, s: str):
        self.out.append(s)

    def text(self, x, y, t, size=1.6, anchor="middle", weight="normal", fill="#1a1a1a", extra=""):
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" fill="{fill}" {extra}>{esc(t)}</text>')


class View:
    """Maps board mm to sheet mm; the solder view mirrors left to right."""

    def __init__(self, solder: bool):
        self.solder = solder

    def x(self, bx: float) -> float:
        return BX + (BOARD_W - bx if self.solder else bx)

    def y(self, by: float) -> float:
        return BY + by

    def p(self, pt):
        return self.x(pt[0]), self.y(pt[1])


def part_label(p: Part) -> str:
    return p.attrs.get("label", "")


def pin_names(p: Part, node_net: dict) -> dict[str, str]:
    if p.kind == "c3-supermini":
        return {n: v[0] for n, v in C3_POWER_LEFT.items()}
    if p.kind == "to92":
        return dict(TO92_NAMES)
    if p.kind == "diode":
        return dict(DIODE_NAMES)
    if p.kind == "jst-xh":
        return {n: net_style(node_net.get((p.ref, n), ""))[1] for n in p.pins}
    return {}


def draw_board(svg: Svg, v: View, pl: Placement, uf: UnionFind, used: set[str]):
    x0, x1 = v.x(0), v.x(BOARD_W)
    left = min(x0, x1)
    svg.add(f'<rect x="{left:.2f}" y="{v.y(0):.2f}" width="{BOARD_W}" height="{BOARD_H}" rx="2.5" '
            f'fill="#f3efe4" stroke="#3b3b3b" stroke-width="0.35"/>')
    # Copper: strips and rails, faint on the top view, strong on the solder side.
    op = 0.85 if v.solder else 0.35
    copper = "#c98b3a"
    for k in range(1, NCOLS + 1):
        for rows in (TOP_ROWS, BOTTOM_ROWS):
            ya, yb = ROW_Y[rows[0]], ROW_Y[rows[-1]]
            x = v.x(col_x(k))
            svg.add(f'<rect x="{x - 0.8:.2f}" y="{v.y(min(ya, yb)) - 0.8:.2f}" width="1.6" '
                    f'height="{abs(yb - ya) + 1.6:.2f}" rx="0.8" fill="{copper}" opacity="{op}"/>')
    rail_col = {"T-": "#4a6fa5", "T+": "#c0392b", "B-": "#4a6fa5", "B+": "#c0392b"}
    for rail, y in RAIL_Y.items():
        xa, xb = v.x(col_x(1)), v.x(col_x(NCOLS))
        svg.add(f'<rect x="{min(xa, xb) - 0.8:.2f}" y="{v.y(y) - 0.7:.2f}" width="{abs(xb - xa) + 1.6:.2f}" '
                f'height="1.4" rx="0.7" fill="{rail_col[rail]}" opacity="{0.55 if v.solder else 0.3}"/>')
    # Edge traces (unmarked on the real board): + at the column 1 end, - at the column 30 end.
    for rail_top, rail_bot, (pa, pb_), xe in (("T+", "B+", ("PL1", "PL2"), 1.6), ("T-", "B-", ("PR1", "PR2"), 87.4)):
        col = rail_col[rail_top]
        for ry, pad in ((RAIL_Y[rail_top], pa), (RAIL_Y[rail_bot], pb_)):
            cx = 1 if xe < 40 else NCOLS
            pts = [(col_x(cx), ry), (xe, ry), (xe, PADS[pad][1]), PADS[pad]]
            d = " ".join(f"{v.x(a):.2f},{v.y(b):.2f}" for a, b in pts)
            svg.add(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="0.45" '
                    f'stroke-dasharray="1.2,0.7" opacity="0.8"/>')
    for (mx, my) in M3_HOLES:
        svg.add(f'<circle cx="{v.x(mx):.2f}" cy="{v.y(my):.2f}" r="1.6" fill="#ffffff" stroke="#777" stroke-width="0.3"/>')
        svg.text(v.x(mx), v.y(my) + 3.4, "M3", 1.1, fill="#777")
    for (mx, my) in M2_HOLES:
        svg.add(f'<circle cx="{v.x(mx):.2f}" cy="{v.y(my):.2f}" r="1.1" fill="#ffffff" stroke="#777" stroke-width="0.3"/>')
    # Holes.
    for h in HOLES.values():
        r_ring = 0.78
        stroke = "#a66d24"
        svg.add(f'<circle cx="{v.x(h.x):.2f}" cy="{v.y(h.y):.2f}" r="{r_ring}" fill="#d9a55a" stroke="{stroke}" stroke-width="0.12"/>')
        svg.add(f'<circle cx="{v.x(h.x):.2f}" cy="{v.y(h.y):.2f}" r="0.42" fill="#ffffff"/>')
    # Row letters and column numbers, as printed on the board.
    for r, y in ROW_Y.items():
        svg.text(v.x(-1.9), v.y(y) + 0.6, r, 1.7, weight="bold", fill="#333")
        svg.text(v.x(BOARD_W + 1.9), v.y(y) + 0.6, r, 1.7, weight="bold", fill="#333")
    for k in range(1, NCOLS + 1):
        svg.text(v.x(col_x(k)), v.y(-1.2), str(k), 1.35, fill="#333")
        svg.text(v.x(col_x(k)), v.y(BOARD_H + 2.4), str(k), 1.35, fill="#333")
    for rail, y in RAIL_Y.items():
        sym = "+" if rail[1] == "+" else "\u2212"
        for bx in (-1.9, BOARD_W + 1.9):
            svg.text(v.x(bx), v.y(y) + 0.65, sym, 2.0, weight="bold", fill=rail_col[rail])


def tag(svg: Svg, x, y, label, color, placed: list, size=1.25):
    w = 0.72 * size * len(label) + 0.9
    h = size + 0.6
    placed.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    svg.add(f'<rect x="{x - w / 2:.2f}" y="{y - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" rx="0.5" '
            f'fill="#ffffff" stroke="{color}" stroke-width="0.3"/>')
    svg.text(x, y + size * 0.36, label, size, weight="bold", fill="#111" if color in ("#B8A100", "#E69F00", "#56B4E9") else color)


def _free(box, placed, holes_xy):
    x0, y0, x1, y1 = box
    for a in placed:
        if not (x1 < a[0] or x0 > a[2] or y1 < a[1] or y0 > a[3]):
            return False
    for (hx, hy) in holes_xy:
        if x0 - 0.5 < hx < x1 + 0.5 and y0 - 0.5 < hy < y1 + 0.5:
            return False
    return True


def draw_wires(svg: Svg, v: View, pl: Placement, steps: dict, placed: list, used_xy: list):
    # Halos first, then wires, then joints, then labels on top.
    for w in pl.wires:
        pts = " ".join(f"{a:.2f},{b:.2f}" for a, b in (v.p(q) for q in w.points()))
        col, _, kind = net_style(w.net)
        width = 1.0 if kind != "signal" else 0.7
        if v.solder:
            svg.add(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="0.35" '
                    f'stroke-dasharray="1,0.8" opacity="0.55"/>')
            continue
        svg.add(f'<polyline points="{pts}" fill="none" stroke="#ffffff" stroke-width="{width + 0.7:.2f}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>')
        svg.add(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{width}" '
                f'stroke-linejoin="round" stroke-linecap="round"/>')
        if kind == "ground":
            svg.add(f'<polyline points="{pts}" fill="none" stroke="#ffffff" stroke-width="0.22" '
                    f'stroke-dasharray="0.6,0.9" stroke-linejoin="round"/>')
    for r in pl.bridges:
        a, b = (v.p(q) for q in bridge_points(r))
        net = "3V3" if r == "+" else "GND"
        col = "#c0392b" if r == "+" else "#4a6fa5"
        svg.add(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#ffffff" stroke-width="1.6"/>')
        svg.add(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="{col}" stroke-width="0.9"/>')
    for w in pl.wires:
        col = net_style(w.net)[0]
        for h in (w.a, w.b):
            x, y = v.p((HOLES[h].x, HOLES[h].y))
            svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.62" fill="{col}" stroke="#ffffff" stroke-width="0.18"/>')
    if v.solder:
        return
    for p in pl.parts:
        polys = [module_outline(p)] if p.kind == "c3-supermini" else [poly for _, poly in body_shapes(p)]
        if p.kind == "c3-supermini":
            continue        # raised on its sockets: labels may sit over its outline, not over its pins
        for poly in polys:
            xs = [v.x(a) for a, _ in poly]
            ys = [v.y(b) for _, b in poly]
            placed.append((min(xs), min(ys), max(xs), max(ys)))
    for w in pl.wires:
        col, label, _ = net_style(w.net)
        segs = w.segments()
        if w.length < 10:
            seg = max(segs, key=lambda s_: math.dist(*s_))
            a, b = seg
            u = _unit(b[0] - a[0], b[1] - a[1])
            L = math.dist(a, b)
            nrm = (-u[1], u[0])
            for q in [(a[0] + u[0] * L * f, a[1] + u[1] * L * f) for f in (0.5, 0.38, 0.62)] +                      [(a[0] + u[0] * L * 0.5 + nrm[0] * k * 2.6, a[1] + u[1] * L * 0.5 + nrm[1] * k * 2.6) for k in (1, -1)]:
                cx, cy = v.p(q)
                wdt = 0.72 * 1.25 * len(label) + 0.9
                box = (cx - wdt / 2, cy - 0.93, cx + wdt / 2, cy + 0.93)
                if _free(box, placed, used_xy):
                    break
            tag(svg, cx, cy, label, col, placed)
            continue
        for end in (0, 1):
            seg = segs[0] if end == 0 else segs[-1]
            a, b = (seg[0], seg[1]) if end == 0 else (seg[1], seg[0])
            L = math.dist(a, b)
            u = _unit(b[0] - a[0], b[1] - a[1])
            done = False
            for d in (2.7, 3.6, 4.6, 1.9, 5.8, 7.0):
                if d > L - 1.0 and len(segs) == 1 and end == 1:
                    break
                if d > L - 0.9:
                    continue
                cx, cy = v.p((a[0] + u[0] * d, a[1] + u[1] * d))
                wdt = 0.72 * 1.25 * len(label) + 0.9
                box = (cx - wdt / 2, cy - 0.93, cx + wdt / 2, cy + 0.93)
                if _free(box, placed, used_xy):
                    tag(svg, cx, cy, label, col, placed)
                    done = True
                    break
            if not done and end == 0:
                mid = (a[0] + u[0] * L / 2, a[1] + u[1] * L / 2)
                cx, cy = v.p(mid)
                tag(svg, cx, cy, label, col, placed)
        # Step number in a circle near the middle of the longest leg.
        seg = max(segs, key=lambda s: math.dist(*s))
        a, b = seg
        L = math.dist(a, b)
        u = _unit(b[0] - a[0], b[1] - a[1])
        n = steps.get(id(w))
        if n is None:
            continue
        nrm = (-u[1], u[0])
        spots = [(a[0] + u[0] * L * f, a[1] + u[1] * L * f) for f in (0.5, 0.35, 0.65, 0.2, 0.8)]
        side_spots = [(q[0] + nrm[0] * s_ * 1.9, q[1] + nrm[1] * s_ * 1.9) for q in spots[:3] for s_ in (1, -1)]
        cands = side_spots + spots if L < 10 else spots + side_spots
        for i, spot in enumerate(cands):
            cx, cy = v.p(spot)
            box = (cx - 1.05, cy - 1.05, cx + 1.05, cy + 1.05)
            if _free(box, placed, used_xy) or i == len(cands) - 1:
                placed.append(box)
                svg.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="1.05" fill="#111" stroke="#fff" stroke-width="0.2"/>')
                svg.text(cx, cy + 0.45, str(n), 1.25, weight="bold", fill="#fff")
                break


def draw_parts(svg: Svg, v: View, pl: Placement, node_net: dict, placed: list):
    ghost = v.solder
    for p in pl.parts:
        names = pin_names(p, node_net)
        if p.kind == "c3-supermini":
            _draw_module(svg, v, p, names, ghost)
            continue
        for _, poly in body_shapes(p):
            pts = " ".join(f"{a:.2f},{b:.2f}" for a, b in (v.p(q) for q in poly))
            if ghost:
                svg.add(f'<polygon points="{pts}" fill="none" stroke="#555" stroke-width="0.25" stroke-dasharray="0.8,0.6"/>')
        if not ghost:
            if p.kind == "jst-xh":
                _draw_jst(svg, v, p, names)
            elif p.kind == "to92":
                _draw_to92(svg, v, p, names)
            elif p.kind in ("resistor", "diode"):
                _draw_axial(svg, v, p, names)
        # Leads / joints.
        for n, h in p.pins.items():
            x, y = v.p((HOLES[h].x, HOLES[h].y))
            svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.55" fill="#9a9a9a" stroke="#333" stroke-width="0.15"/>')
        _part_caption(svg, v, p, placed)


def _part_caption(svg, v, p, placed):
    polys = [poly for _, poly in body_shapes(p)] if p.kind != "c3-supermini" else [module_outline(p)]
    xs = [v.x(a) for poly in polys for a, _ in poly]
    ys = [v.y(b) for poly in polys for _, b in poly]
    cx = (min(xs) + max(xs)) / 2
    side = p.attrs.get("caption", "below")
    if v.solder and side in ("left", "right"):
        side = {"left": "right", "right": "left"}[side]
    text1 = p.ref + (f" {p.value}" if p.value and p.kind != "c3-supermini" else "")
    text2 = part_label(p)
    if p.kind in ("c3-supermini", "jst-xh"):
        return
    lines = [text1] + ([text2] if text2 else [])
    wmax = max(len(t) for t in lines) * 0.95 + 1
    if side == "above":
        y = min(ys) - 0.9 - (1.7 if text2 else 0)
    elif side == "inside":
        y = (min(ys) + max(ys)) / 2 + 0.5
    elif side in ("left", "right"):
        y = (min(ys) + max(ys)) / 2 + 0.5 - (0.85 if text2 else 0)
        cx = min(xs) - wmax / 2 - 0.6 if side == "left" else max(xs) + wmax / 2 + 0.6
    else:
        y = max(ys) + 2.0
    box = (cx - wmax / 2, y - 1.6, cx + wmax / 2, y + 1.7 * (len(lines) - 1) + 0.5)
    placed.append(box)
    svg.add(f'<rect x="{box[0]:.2f}" y="{box[1]:.2f}" width="{box[2] - box[0]:.2f}" height="{box[3] - box[1]:.2f}" '
            f'rx="0.4" fill="#ffffff" opacity="0.85"/>')
    svg.text(cx, y, text1, 1.55, weight="bold")
    if text2:
        svg.text(cx, y + 1.7, text2, 1.3, fill="#444")


def _draw_jst(svg, v, p, names):
    _, poly = body_shapes(p)[0]
    pts = " ".join(f"{a:.2f},{b:.2f}" for a, b in (v.p(q) for q in poly))
    svg.add(f'<polygon points="{pts}" fill="#f7f1e1" stroke="#222" stroke-width="0.35"/>')
    n = len(p.pins)
    a, b = p.xy("1"), p.xy(str(n))
    u = _unit(b[0] - a[0], b[1] - a[1])
    lat = DIRS[p.attrs["latch"]]
    # Inner wall and the latch ramp on the latch side.
    s = (a[0] - u[0] * 1.6, a[1] - u[1] * 1.6)
    e = (b[0] + u[0] * 1.6, b[1] + u[1] * 1.6)
    wall = [(s[0] + lat[0] * 2.7, s[1] + lat[1] * 2.7), (e[0] + lat[0] * 2.7, e[1] + lat[1] * 2.7)]
    (x1, y1), (x2, y2) = (v.p(q) for q in wall)
    svg.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#222" stroke-width="0.25"/>')
    mid = ((a[0] + b[0]) / 2 + lat[0] * 3.05, (a[1] + b[1]) / 2 + lat[1] * 3.05)
    rx, ry = v.p(mid)
    wdt = 2.6
    if abs(lat[1]) > 0.5:
        svg.add(f'<rect x="{rx - wdt / 2:.2f}" y="{ry - 0.35:.2f}" width="{wdt}" height="0.7" fill="#222"/>')
    else:
        svg.add(f'<rect x="{rx - 0.35:.2f}" y="{ry - wdt / 2:.2f}" width="0.7" height="{wdt}" fill="#222"/>')
    # Pin 1 marker: a red dot just past pin 1's end of the body.
    p1 = p.xy("1")
    end1 = (p1[0] - u[0] * 1.75, p1[1] - u[1] * 1.75)
    tx, ty = v.p(end1)
    svg.add(f'<circle cx="{tx:.2f}" cy="{ty:.2f}" r="0.45" fill="#c0392b"/>')
    for k, h in p.pins.items():
        hx, hy = HOLES[h].x, HOLES[h].y
        lx, ly = v.p((hx - lat[0] * 1.55, hy - lat[1] * 1.55))
        svg.text(lx, ly + 0.36, names.get(k, k), 0.95, weight="bold", fill="#222")
    mid2 = ((a[0] + b[0]) / 2 + lat[0] * 1.75, (a[1] + b[1]) / 2 + lat[1] * 1.75)
    cx2, cy2 = v.p(mid2)
    svg.text(cx2, cy2 + 0.5, f"{p.ref} {part_label(p)}", 1.35, weight="bold", fill="#1a1a1a")


def _draw_to92(svg, v, p, names):
    a, c = p.xy("1"), p.xy("3")
    m = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
    f = DIRS[p.attrs["flat"]]
    u = _unit(c[0] - a[0], c[1] - a[1])
    # D-shape: flat face 1.75 mm toward `flat`, round back 2.45 mm the other way.
    pts = []
    for i in range(0, 181, 10):
        t = math.radians(i)
        r = 2.55
        px = m[0] + u[0] * r * math.cos(t) - f[0] * 2.45 * math.sin(t)
        py = m[1] + u[1] * r * math.cos(t) - f[1] * 2.45 * math.sin(t)
        pts.append((px, py))
    pts = [(m[0] - u[0] * 2.55 + f[0] * 1.75, m[1] - u[1] * 2.55 + f[1] * 1.75)] + pts[::-1] + \
          [(m[0] + u[0] * 2.55 + f[0] * 1.75, m[1] + u[1] * 2.55 + f[1] * 1.75)]
    d = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in pts))
    svg.add(f'<polygon points="{d}" fill="#3a3a3a" stroke="#111" stroke-width="0.3"/>')
    fa = v.p((m[0] - u[0] * 2.55 + f[0] * 1.75, m[1] - u[1] * 2.55 + f[1] * 1.75))
    fb = v.p((m[0] + u[0] * 2.55 + f[0] * 1.75, m[1] + u[1] * 2.55 + f[1] * 1.75))
    svg.add(f'<line x1="{fa[0]:.2f}" y1="{fa[1]:.2f}" x2="{fb[0]:.2f}" y2="{fb[1]:.2f}" stroke="#f1c40f" stroke-width="0.45"/>')
    lx, ly = v.p((m[0] + f[0] * 2.6, m[1] + f[1] * 2.6))
    svg.text(lx, ly + 0.45, "flat", 1.0, fill="#7a6400")
    for k, h in p.pins.items():
        hx, hy = HOLES[h].x, HOLES[h].y
        x, y = v.p((hx - f[0] * 1.35, hy - f[1] * 1.35))
        svg.text(x, y + 0.45, names[k], 1.15, weight="bold", fill="#ffffff")


def _draw_axial(svg, v, p, names):
    a, b = p.xy("1"), p.xy("2")
    u = _unit(b[0] - a[0], b[1] - a[1])
    L = 6.3 if p.kind == "resistor" else 5.2
    wdt = 2.4 if p.kind == "resistor" else 2.6
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    s = (m[0] - u[0] * L / 2, m[1] - u[1] * L / 2)
    e = (m[0] + u[0] * L / 2, m[1] + u[1] * L / 2)
    for q, r in ((a, s), (b, e)):
        (x1, y1), (x2, y2) = v.p(q), v.p(r)
        svg.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#8a8a8a" stroke-width="0.45"/>')
    _, poly = _rect_along(s, e, 0.0, wdt / 2, wdt / 2)
    d = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in poly))
    if p.kind == "resistor":
        svg.add(f'<polygon points="{d}" fill="#cfe0ef" stroke="#2c3e50" stroke-width="0.3"/>')
        bands = RES_BANDS.get(p.value.replace(" \u03a9", "").replace("\u03a9", "").strip(), [])
        for i, colr in enumerate(bands):
            t = -L / 2 + 1.0 + i * 1.25 if i < 3 else L / 2 - 1.0
            c = (m[0] + u[0] * t, m[1] + u[1] * t)
            _, bp = _rect_along((c[0] - u[0] * 0.3, c[1] - u[1] * 0.3), (c[0] + u[0] * 0.3, c[1] + u[1] * 0.3), 0, wdt / 2, wdt / 2)
            bd = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in bp))
            svg.add(f'<polygon points="{bd}" fill="{colr}"/>')
    else:
        svg.add(f'<polygon points="{d}" fill="#222" stroke="#111" stroke-width="0.3"/>')
        # Cathode band at pin 1 (K).
        c = (m[0] - u[0] * (L / 2 - 0.8), m[1] - u[1] * (L / 2 - 0.8))
        _, bp = _rect_along((c[0] - u[0] * 0.4, c[1] - u[1] * 0.4), (c[0] + u[0] * 0.4, c[1] + u[1] * 0.4), 0, wdt / 2, wdt / 2)
        bd = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in bp))
        svg.add(f'<polygon points="{bd}" fill="#d9d9d9"/>')
        for k, q in (("1", a), ("2", b)):
            off = (q[0] + (-u[0] if k == "1" else u[0]) * 0.0, q[1])
            x, y = v.p(q)
            nx, ny = -u[1], u[0]
            svg.text(x + nx * 1.6, y + ny * 1.6 + 0.45, names[k], 1.1, weight="bold", fill="#222")


def _draw_module(svg, v, p, names, ghost):
    usb, left, (cx, cy) = module_frame(p)
    poly = module_outline(p)
    d = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in poly))
    # Socket strips (female headers).
    for _, sp in body_shapes(p):
        sd = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in sp))
        svg.add(f'<polygon points="{sd}" fill="#2b2b2b" opacity="{0.25 if ghost else 0.8}"/>')
    svg.add(f'<polygon points="{d}" fill="#1f4e79" fill-opacity="0.08" stroke="#1f4e79" stroke-width="0.4" '
            f'stroke-dasharray="1.6,0.8"/>')
    # USB-C receptacle at the USB end.
    l0, r0 = p.xy("9"), p.xy("1")
    mu = ((l0[0] + r0[0]) / 2 + usb[0] * 2.6, (l0[1] + r0[1]) / 2 + usb[1] * 2.6)
    _, up = _rect_along((mu[0] - usb[0] * 1.7, mu[1] - usb[1] * 1.7), (mu[0] + usb[0] * 1.6, mu[1] + usb[1] * 1.6), 0, 4.45, 4.45)
    ud = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in up))
    svg.add(f'<polygon points="{ud}" fill="#bdc3c7" stroke="#1f4e79" stroke-width="0.3"/>')
    ux, uy = v.p(mu)
    svg.text(ux, uy + 0.5, "USB-C", 1.3, weight="bold", fill="#1f4e79")
    # Caption inside the outline, in the channel, shifted toward the far (antenna) end so it stays clear of
    # the M3 hole beside the USB end and of the outline itself.
    ch = (cx - usb[0] * 4.2, 26.0)
    mx, my = v.p(ch)
    arrow = "→" if (usb[0] > 0) != v.solder else "←"
    svg.add(f'<rect x="{mx - 6.6:.2f}" y="{my - 2.2:.2f}" width="13.2" height="4.3" rx="0.6" fill="#ffffff" opacity="0.92"/>')
    svg.text(mx, my - 0.45, "U1 ESP32-C3", 1.5, weight="bold", fill="#1f4e79")
    line2 = f"{arrow} USB-C end" if arrow == "←" else f"USB-C end {arrow}"
    svg.text(mx, my + 1.45, line2, 1.25, fill="#1f4e79")
    if not ghost:
        for n, h in p.pins.items():
            hx, hy = HOLES[h].x, HOLES[h].y
            # Name toward the channel for the row beside it, otherwise away from the module.
            toward_channel = 26.0 - hy
            if abs(toward_channel) < 5:
                d = 1.0 if toward_channel > 0 else -1.0
            else:
                d = -1.0 if toward_channel > 0 else 1.0
            x, y = v.p((hx, hy + d * 1.75))
            svg.add(f'<rect x="{x - 1.4:.2f}" y="{y - 0.75:.2f}" width="2.8" height="1.3" rx="0.3" fill="#eaf1f8"/>')
            svg.text(x, y + 0.4, names[n], 1.1, weight="bold", fill="#1f4e79")


def draw_header(svg: Svg, pl: Placement, solder: bool):
    title = f"{pl.title or pl.device} \u2014 protoboard"
    svg.text(4, 6, title, 3.0, anchor="start", weight="bold")
    if solder:
        svg.add(f'<rect x="4" y="8.5" width="{SHEET_W - 8}" height="6.2" rx="1" fill="#111"/>')
        svg.text(SHEET_W / 2, 13.2, "SOLDER SIDE (mirrored): number 1 is on the RIGHT", 3.1, weight="bold", fill="#ffffff")
    else:
        svg.text(4, 12.5, "TOP VIEW (component side), real size", 2.6, anchor="start", weight="bold", fill="#333")
    # Hand warning with the identification picture.
    y0 = 16.5
    svg.add(f'<rect x="4" y="{y0}" width="{SHEET_W - 8}" height="15" rx="1" fill="#fff4f2" stroke="#c0392b" stroke-width="0.5"/>')
    svg.text(6, y0 + 3.6, "For a C3 POWER-LEFT module only", 2.3, anchor="start", weight="bold", fill="#c0392b")
    for i, t in enumerate(["Hold the module USB up, chip facing you: 5V, G and 3V3 must be the top",
                           "three pins of the LEFT row. A power-right module here puts 5 V on a",
                           "GPIO pin and can destroy it. Check before you plug U1 in."]):
        svg.text(6, y0 + 6.6 + i * 2.5, t, 1.75, anchor="start", fill="#5a1a12")
    _hand_picture(svg, SHEET_W - 24, y0 + 0.8)


def _hand_picture(svg: Svg, x, y):
    w, h = 9.0, 11.3
    svg.add(f'<rect x="{x:.2f}" y="{y + 1.6:.2f}" width="{w}" height="{h}" rx="0.8" fill="#1f4e79"/>')
    svg.add(f'<rect x="{x + w / 2 - 2.0:.2f}" y="{y + 0.6:.2f}" width="4.0" height="1.6" rx="0.5" fill="#bdc3c7"/>')
    svg.text(x + w / 2, y + 0.3, "USB up", 1.05, weight="bold", fill="#1f4e79")
    left = ["5V", "G", "3V3", "4", "3", "2", "1", "0"]
    for i, t in enumerate(left):
        yy = y + 2.8 + i * 1.3
        hi = i < 3
        svg.add(f'<circle cx="{x + 0.9:.2f}" cy="{yy:.2f}" r="0.35" fill="{"#f1c40f" if hi else "#d9d9d9"}"/>')
        svg.add(f'<circle cx="{x + w - 0.9:.2f}" cy="{yy:.2f}" r="0.35" fill="#d9d9d9"/>')
        svg.text(x - 0.5, yy + 0.38, t, 1.05, anchor="end", weight="bold" if hi else "normal",
                 fill="#c0392b" if hi else "#333")
    svg.text(x + w + 1.2, y + 4.5, "power", 1.1, anchor="start", fill="#c0392b")
    svg.text(x + w + 1.2, y + 5.9, "on the", 1.1, anchor="start", fill="#c0392b")
    svg.text(x + w + 1.2, y + 7.3, "LEFT", 1.3, anchor="start", weight="bold", fill="#c0392b")


def draw_legend(svg: Svg, pl: Placement, y0: float, nets_used: list[str], solder: bool) -> float:
    svg.text(4, y0, "Nets (each wire end is labelled too)", 1.9, anchor="start", weight="bold")
    cols = 2
    colw = (SHEET_W - 8) / cols
    for i, net in enumerate(nets_used):
        col, label, kind = net_style(net)
        x = 4 + (i % cols) * colw
        y = y0 + 3 + (i // cols) * 2.9
        width = 1.0 if kind != "signal" else 0.7
        svg.add(f'<line x1="{x:.2f}" y1="{y - 0.5:.2f}" x2="{x + 7:.2f}" y2="{y - 0.5:.2f}" stroke="{col}" stroke-width="{width}"/>')
        if kind == "ground":
            svg.add(f'<line x1="{x:.2f}" y1="{y - 0.5:.2f}" x2="{x + 7:.2f}" y2="{y - 0.5:.2f}" stroke="#fff" stroke-width="0.22" stroke-dasharray="0.6,0.9"/>')
        svg.text(x + 8.5, y, f"{label}", 1.6, anchor="start", weight="bold", fill="#111")
        svg.text(x + 8.5 + 1.0 * len(label) + 1.6, y, f"{NET_TEXT.get(net, net)}" + (" (power)" if kind == "power" else ""),
                 1.45, anchor="start", fill="#444")
    y = y0 + 3 + ((len(nets_used) + 1) // cols) * 2.9 + 1.0
    svg.add(f'<circle cx="5" cy="{y - 0.5:.2f}" r="0.62" fill="#0072B2" stroke="#fff" stroke-width="0.18"/>')
    svg.text(6.6, y, "wire end: solder here", 1.45, anchor="start", fill="#444")
    svg.add(f'<circle cx="38" cy="{y - 0.5:.2f}" r="1.05" fill="#111"/>')
    svg.text(38, y - 0.05, "3", 1.25, weight="bold", fill="#fff")
    svg.text(39.8, y, "build step", 1.45, anchor="start", fill="#444")
    svg.add(f'<rect x="58" y="{y - 1.3:.2f}" width="1.6" height="1.6" rx="0.8" fill="#c98b3a" opacity="0.6"/>')
    svg.text(60.4, y, "copper strip: its holes are joined", 1.45, anchor="start", fill="#444")
    y += 3.2
    svg.add(f'<line x1="4" y1="{y - 0.5:.2f}" x2="10" y2="{y - 0.5:.2f}" stroke="#c0392b" stroke-width="0.45" stroke-dasharray="1.2,0.7"/>')
    svg.text(11, y, "unmarked edge trace, broken at the link pads beside the M3 holes; the links join the halves",
             1.4, anchor="start", fill="#444")
    y += 3.6
    svg.add(f'<line x1="4" y1="{y:.2f}" x2="24" y2="{y:.2f}" stroke="#111" stroke-width="0.4"/>')
    for xx in (4, 24):
        svg.add(f'<line x1="{xx}" y1="{y - 0.8:.2f}" x2="{xx}" y2="{y + 0.8:.2f}" stroke="#111" stroke-width="0.4"/>')
    svg.text(26, y + 0.5, "20 mm: printed at 100 % (actual size) this bar measures 20 mm and the board is real size",
             1.4, anchor="start", fill="#444")
    return y + 3


def build_steps(pl: Placement):
    """Build order, lowest parts first: links and wires, resistors, diode, transistor, sockets, headers."""
    steps = []
    wire_steps = {}
    for r in pl.bridges:
        a, b = BRIDGE_PADS[r]
        sym = "+" if r == "+" else "−"
        steps.append(("link", f"Rail link ({sym}): wire from the {HOLES[a].text} to the {HOLES[b].text}. It joins "
                              f"the top and bottom {sym} rails.", f"{sym} rail link", f"{HOLES[a].text} to {HOLES[b].text}"))

    def wkey(w):
        under = any(seg_hits_poly(a, b, module_outline(p)) for p in pl.parts if p.kind == "c3-supermini"
                    for a, b in w.segments())
        return (0 if under else 1, -w.length)
    for w in sorted(pl.wires, key=wkey):
        label = net_style(w.net)[1]
        shape = "straight" if not w.route else "one bend"
        steps.append(("wire", f"Wire {label}: {HOLES[w.a].text} to {HOLES[w.b].text} ({shape}, {w.length:.0f} mm).",
                      f"wire {label}", f"{HOLES[w.a].text} to {HOLES[w.b].text}" + (" (one bend)" if w.route else "")))
        wire_steps[id(w)] = len(steps)
    order = {"resistor": 0, "diode": 1, "to92": 2, "c3-supermini": 3, "jst-xh": 4}
    for p in sorted(pl.parts, key=lambda p: (order[p.kind], p.ref)):
        pins = sorted(p.pins.items(), key=lambda t: int(t[0]) if t[0].isdigit() else 0)
        if p.kind == "resistor":
            steps.append(("part", f"{p.ref} ({p.value}): {HOLES[pins[0][1]].text} to {HOLES[pins[1][1]].text}, "
                                  "lying flat.",
                          f"{p.ref} {p.value}", f"{HOLES[pins[0][1]].text} to {HOLES[pins[1][1]].text}"))
        elif p.kind == "diode":
            steps.append(("part", f"{p.ref} ({p.value}): banded end (K) in {HOLES[p.pins['1']].text}, "
                                  f"other end (A) in {HOLES[p.pins['2']].text}.",
                          f"{p.ref} {p.value}", f"K {HOLES[p.pins['1']].text}, A {HOLES[p.pins['2']].text}"))
        elif p.kind == "to92":
            steps.append(("part", f"{p.ref} ({p.value}): D in {p.pins['1']}, G in {p.pins['2']}, S in {p.pins['3']}, "
                                  f"flat face toward the {_dir_word(p.attrs['flat'])}.",
                          f"{p.ref} {p.value}", f"D {p.pins['1']}, G {p.pins['2']}, S {p.pins['3']}"))
        elif p.kind == "c3-supermini":
            rows = {}
            for n, h in p.pins.items():
                rows.setdefault(h[0], []).append(int(h[1:]))
            spans = ", ".join(f"{r}{min(c)}-{r}{max(c)}" for r, c in sorted(rows.items()))
            steps.append(("part", f"U1 sockets: two 1x8 female headers in {spans}. Plug U1 in while soldering to keep "
                                  "them square, then take it out.", "U1 sockets", spans))
        elif p.kind == "jst-xh":
            names = ", ".join(f"{n} {p.pins[n]}" for n, _ in pins)
            steps.append(("part", f"{p.ref} ({part_label(p)}, JST-XH {len(pins)}-pin): pin 1 in {p.pins['1']}, "
                                  f"latch side toward the {_dir_word(p.attrs['latch'])}.",
                          f"{p.ref} {part_label(p)}", "pin " + names))
    steps.append(("check", "Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C "
                           "toward the board edge as drawn, after checking it is a power-left module.", "", ""))
    return steps, wire_steps


def _dir_word(d: str) -> str:
    return {"up": "top edge (the J side)", "down": "bottom edge (the A side)", "left": "number 1 end",
            "right": "number 30 end"}[d]


def render_sheet(pl: Placement, nets: dict, solder: bool) -> str:
    node_net = {m: n for n, ms in nets.items() for m in ms}
    uf = connectivity(pl)
    used = used_holes(pl)
    v = View(solder)
    steps, wire_steps = build_steps(pl)
    svg = Svg()
    draw_header(svg, pl, solder)
    draw_board(svg, v, pl, uf, used)
    placed: list = []
    used_xy = [v.p((HOLES[h].x, HOLES[h].y)) for h in used]
    draw_parts(svg, v, pl, node_net, placed)
    draw_wires(svg, v, pl, wire_steps, placed, used_xy)
    nets_used = []
    for net in NET_STYLE:
        if any(w.net == net for w in pl.wires) or any(node_net.get((p.ref, n)) == net for p in pl.parts for n in p.pins):
            nets_used.append(net)
    hgt = draw_legend(svg, pl, BY + BOARD_H + 7.5, nets_used, solder)
    body = "\n".join(svg.out)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W}mm" height="{hgt:.1f}mm" '
            f'viewBox="0 0 {SHEET_W} {hgt:.1f}" font-family="Arial, Helvetica, sans-serif">\n'
            f'<rect x="0" y="0" width="{SHEET_W}" height="{hgt:.1f}" fill="#ffffff"/>\n{body}\n</svg>\n')


def steps_markdown(pl: Placement) -> str:
    steps, _ = build_steps(pl)
    out = ["Build order (lowest parts first; the numbers on the wires in the top view are these step numbers):", ""]
    for i, (_, text, _, _) in enumerate(steps, 1):
        out.append(f"{i}. {text}")
    out += ["", "| Step | Item | Holes |", "|---|---|---|"]
    for i, (kind, _, item, holes) in enumerate(steps, 1):
        if kind == "check":
            continue
        out.append(f"| {i} | {item} | {holes} |")
    return "\n".join(out) + "\n"


def edge_path() -> str | None:
    for c in (os.environ.get("EDGE"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", shutil.which("msedge"),
              shutil.which("chrome"), shutil.which("chromium"), shutil.which("google-chrome")):
        if c and Path(c).is_file():
            return c
    return None


def write_pdf(pl: Placement, top: str, solder: str, md: str, out: Path, page: str) -> None:
    browser = edge_path()
    if not browser:
        raise PlacementError("--pdf needs Microsoft Edge or Chrome (set EDGE to its file)")
    size = {"a4": "210mm 297mm", "letter": "8.5in 11in"}[page]

    def scaled(svg: str, k: float) -> str:
        import re
        w = float(re.search(r'width="([\d.]+)mm"', svg).group(1))
        h = float(re.search(r'height="([\d.]+)mm"', svg).group(1))
        return re.sub(r'width="[\d.]+mm" height="[\d.]+mm"', f'width="{w * k:.1f}mm" height="{h * k:.1f}mm"', svg, count=1)
    import html as _h
    rows = []
    for line in md.splitlines():
        if line.startswith("| ") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            tagname = "th" if cells[0] == "Step" else "td"
            rows.append("<tr>" + "".join(f"<{tagname}>{_h.escape(c)}</{tagname}>" for c in cells) + "</tr>")
    items = [f"<li>{_h.escape(l.split('. ', 1)[1])}</li>" for l in md.splitlines() if l[:1].isdigit()]
    warn = top[top.index("<svg"):]
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: {size}; margin: 8mm; }}
body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; }}
.page {{ page-break-after: always; text-align: center; }}
.page:last-child {{ page-break-after: auto; }}
h2 {{ font-size: 13pt; margin: 2mm 0; text-align: left; }}
p.note {{ font-size: 9pt; text-align: left; margin: 1mm 0 3mm; }}
ol {{ text-align: left; font-size: 8.5pt; margin: 0 0 3mm 5mm; padding-left: 4mm; }}
table {{ border-collapse: collapse; font-size: 8pt; text-align: left; width: 100%; }}
td, th {{ border: 0.2mm solid #999; padding: 0.6mm 1.2mm; }}
</style></head><body>
<div class="page"><h2>Top view, enlarged for reading</h2>{scaled(top, 1.45)}</div>
<div class="page"><h2>Solder side, enlarged for reading</h2>{scaled(solder, 1.45)}</div>
<div class="page"><h2>Real size (print at 100 %, "actual size"): lay the board on the drawing</h2>
<p class="note">Check the 20 mm bar with a ruler before you rely on the drawing.</p>{top}</div>
<div class="page"><h2>Real size, solder side</h2>{solder}</div>
<div class="page"><h2>Build order and hole table</h2>
<p class="note">For a C3 POWER-LEFT module only (USB up: 5V, G, 3V3 at the top of the LEFT row). A power-right module
in this layout puts 5 V on a GPIO pin and can destroy it.</p>
<ol>{''.join(items)}</ol><table>{''.join(rows)}</table></div>
</body></html>"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        hp = Path(td) / "sheet.html"
        hp.write_text(html, encoding="utf-8")
        prof = Path(td) / "profile"
        try:
            subprocess.run([browser, "--headless", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
                            "--no-pdf-header-footer", f"--print-to-pdf={out}", hp.as_uri()],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        except subprocess.TimeoutExpired:
            pass
        if not out.is_file():
            raise PlacementError(f"PDF not written: {out}")


def cmd_render(args) -> int:
    try:
        pl = load_placement(Path(args.placement))
        nets = netlist_for(pl, Path(args.netlist) if args.netlist else None)
    except PlacementError as e:
        print(e, file=sys.stderr)
        return 2
    rep = check(pl, nets)
    if rep.errors:
        for e in rep.errors:
            print(f"ERROR {e}")
        print("not rendered: the check failed")
        return 1
    base = pl.path.with_suffix("")
    top = render_sheet(pl, nets, False)
    solder = render_sheet(pl, nets, True)
    md = steps_markdown(pl)
    Path(f"{base}-top.svg").write_text(top, encoding="utf-8", newline="\n")
    Path(f"{base}-solder.svg").write_text(solder, encoding="utf-8", newline="\n")
    Path(f"{base}-steps.md").write_text(md, encoding="utf-8", newline="\n")
    print(f"wrote {base}-top.svg, {base}-solder.svg, {base}-steps.md")
    if args.pdf:
        for page in ("a4", "letter"):
            out = Path(f"{base}-{page}.pdf").resolve()
            try:
                write_pdf(pl, top, solder, md, out, page)
            except PlacementError as e:
                print(e, file=sys.stderr)
                return 2
            print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
