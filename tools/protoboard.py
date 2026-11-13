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

Part kinds: c3-supermini (hand power-left or power-right), module (a plug-in board on a 1xN female header; pins
with on="module" sit on the board itself, such as a screw terminal), jst-xh, to92, resistor, diode, cap-radial and
leads (a schematic connector placed as loose wires of an off-board device, each soldered into any free hole,
letter or rail; it needs label="<device>" and has no body).
Any part may carry dnp="<when to fit it>": its holes are kept and drawn, and it is listed apart from the build
steps. A wire is straight, has one bend (route hv or vh) or runs along the centre channel (route channel, y=mm).
<protoboard style="callouts"> picks the drawing style: wire links carry no label, every on-board part and every
wire of an off-board device carries a number in a callout, and a legend under the board lists the numbers. The
default, style="labels", puts a net tag and a build-step number on every wire link.

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
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
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
WIRE_M3_KEEPOUT = 3.5   # a wire's centreline stays this far from an M3 hole centre: an M3 pan head is 5.5 mm across
M2_KEEPOUT = 2.0
HOLE_R = 0.9        # copper ring radius, for "passes over a hole"
DRILL_R = 0.6
# A hole beside a part body still takes a lead (a 0.64 mm wire) while its centre is clear of the body: a
# JST-XH body covers 0.41-0.51 mm of the 1.2 mm drill on its shallow side and at its ends, leaving 0.69 mm.
LEAD_CLEAR = 0.05
WIRE_R = 0.15       # a wire may lie against a part body but not over it
PAD_STUB = 0.7      # the length of wire over its own pad, where it may touch a neighbouring body edge
# A "channel" wire drops from its first hole into the centre channel (no copper), runs along it at a set y and
# rises to its second hole: two bends. Its run stays at least a hole's ring away from rows F and E.
CHANNEL_Y = (round(22.19 + HOLE_R + 0.1, 2), round(29.81 - HOLE_R - 0.1, 2))


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
    # Pins on the module itself, not in a board hole (a module's screw terminal): pin number -> (along, out) in
    # mm from pin 1, along the pin row and out toward the side the module extends to.
    module_pins: dict[str, tuple[float, float]] = field(default_factory=dict)

    def xy(self, pin: str) -> tuple[float, float]:
        h = HOLES[self.pins[pin]]
        return h.x, h.y

    @property
    def dnp(self) -> str:
        """The "fit only if" note of a part whose holes are kept but which is not fitted at first, else ""."""
        return self.attrs.get("dnp", "")


# Pin names, by kind, for the drawing. A JST's names come from the placement file (they are the net order).
C3_POWER_LEFT = {  # pad -> (name, side, index from the USB end); top view with USB up, power row on the left
    "9": ("5V", "L", 0), "10": ("G", "L", 1), "11": ("3V3", "L", 2), "12": ("4", "L", 3),
    "13": ("3", "L", 4), "14": ("2", "L", 5), "15": ("1", "L", 6), "16": ("0", "L", 7),
    "1": ("5", "R", 0), "2": ("6", "R", 1), "3": ("7", "R", 2), "4": ("8", "R", 3),
    "5": ("9", "R", 4), "6": ("10", "R", 5), "7": ("20", "R", 6), "8": ("21", "R", 7),
}
HANDS = ("power-left", "power-right")
STYLES = ("labels", "callouts")
# Build order of the part kinds, lowest parts first; the callout numbers follow it too.
PART_ORDER = {"resistor": 0, "diode": 1, "to92": 2, "cap-radial": 2.5, "c3-supermini": 3, "module": 3.5, "jst-xh": 4,
              "leads": 5}
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

    In the module's own top view (USB up) the power row is on the left for a power-left module and on the right for
    a power-right one; the pads keep their numbers (9-16 the power row, 1-8 GPIO 5 to 21). Pins i
    (0 = USB end) of each row sit at 2.54 mm steps away from the USB end; the rows are 15.24 mm apart.
    """
    hand = part.attrs.get("hand", "")
    if hand not in HANDS:
        raise PlacementError(f"{part.ref}: hand must be \"power-left\" or \"power-right\", got {hand!r}")
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
    # Handedness: seen from above with USB up, the power row must be on the module's own side. "Up" is usb; the
    # viewer's left of "up" in y-down screen coordinates is (usb.y, -usb.x).
    viewer_left = (usb[1], -usb[0])
    want = 1.0 if hand == "power-left" else -1.0
    if want * (viewer_left[0] * left[0] + viewer_left[1] * left[1]) < 0.9:
        other = "power-right" if hand == "power-left" else "power-left"
        side = "right" if hand == "power-left" else "left"
        raise PlacementError(f"{part.ref}: these pin holes describe a mirrored module: with USB up the power "
                             f"row would be on the {side}, which is the {other} module")
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
    elif k == "module":
        pins = sorted(part.pins, key=int)
        shapes.append(_rect_along(part.xy(pins[0]), part.xy(pins[-1]), 1.27, 1.27, 1.27))
    elif k == "cap-radial":
        shapes.append(("poly", cap_outline(part)))
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
    route: str = ""         # "" straight, "hv" horizontal then vertical, "vh" vertical then horizontal,
    lane: float = 0.0       # "channel": down (or up) into the centre channel, along it at y = lane, and out

    def points(self) -> list[tuple[float, float]]:
        ha, hb = HOLES[self.a], HOLES[self.b]
        if self.route == "hv":
            return [(ha.x, ha.y), (hb.x, ha.y), (hb.x, hb.y)]
        if self.route == "vh":
            return [(ha.x, ha.y), (ha.x, hb.y), (hb.x, hb.y)]
        if self.route == "channel":
            return [(ha.x, ha.y), (ha.x, self.lane), (hb.x, self.lane), (hb.x, hb.y)]
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
    style: str = "labels"       # or "callouts", see the module docstring


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
        on_module = {}
        for p in e.findall("pin"):
            n, h = p.get("n"), p.get("hole")
            if n in pins or n in on_module:
                raise PlacementError(f"{path}: {e.get('ref')} pin {n} is listed twice")
            if p.get("on") == "module":
                try:
                    along, out = (float(v) for v in p.get("at", "").split(","))
                except ValueError:
                    raise PlacementError(f"{path}: {e.get('ref')} pin {n}: an on-module pin needs at=\"along,out\" in mm")
                on_module[n] = (along, out)
            else:
                if h not in HOLES:
                    raise PlacementError(f"{path}: {e.get('ref')} pin {n}: no hole named {h!r}")
                pins[n] = h
            if p.get("name"):
                names[n] = p.get("name")
        attrs = {k: v for k, v in e.attrib.items() if k not in ("ref", "kind", "value")}
        parts.append(Part(e.get("ref"), e.get("kind"), e.get("value", ""), pins, attrs, names, on_module))
    wires = []
    for e in root.findall("wire"):
        a, b = e.get("from"), e.get("to")
        for h in (a, b):
            if h not in HOLES:
                raise PlacementError(f"{path}: wire {a} to {b}: no hole named {h!r}")
        route = e.get("route", "")
        if route not in ("", "hv", "vh", "channel"):
            raise PlacementError(f"{path}: wire {a} to {b}: route must be hv, vh or channel")
        lane = 0.0
        if route == "channel":
            try:
                lane = float(e.get("y", ""))
            except ValueError:
                raise PlacementError(f"{path}: wire {a} to {b}: a channel wire needs y=\"mm\", its run across the channel")
            if not CHANNEL_Y[0] < lane < CHANNEL_Y[1]:
                raise PlacementError(f"{path}: wire {a} to {b}: y={lane} is not inside the channel "
                                     f"({CHANNEL_Y[0]}-{CHANNEL_Y[1]} mm)")
        wires.append(Wire(e.get("net", ""), a, b, route, lane))
    bridges = []
    for e in root.findall("bridge"):
        r = e.get("rail")
        if r not in BRIDGE_PADS:
            raise PlacementError(f"{path}: bridge rail must be + or -, got {r!r}")
        bridges.append(r)
    style = root.get("style", "labels")
    if style not in STYLES:
        raise PlacementError(f"{path}: style must be {' or '.join(STYLES)}, got {style!r}")
    return Placement(path, root.get("device", ""), root.get("hand", ""), schematic, offboard, parts, wires,
                     bridges, root.get("title", ""), style)


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

    # The placement's hand is U1's hand.
    for p in pl.parts:
        if p.kind == "c3-supermini" and p.attrs.get("hand", "") != pl.hand:
            err(f"{p.ref}: its hand is {p.attrs.get('hand', '')!r} but the placement's hand is {pl.hand!r}")

    # Every pin of a placed part is placed, and no placed pin is unknown.
    node_net: dict[tuple[str, str], str] = {}
    for name, members in nets.items():
        for m in members:
            node_net[m] = name
    for p in pl.parts:
        want = {pin for (ref, pin) in node_net if ref == p.ref} - set(p.module_pins)
        for pin in sorted(want - set(p.pins)):
            err(f"{p.ref} pin {pin} (net {node_net[(p.ref, pin)]}): not placed")
        for pin in sorted((set(p.pins) | set(p.module_pins)) - want - set(p.module_pins)):
            err(f"{p.ref} pin {pin}: placed but not in the netlist")
        for pin in sorted(p.module_pins):
            if (p.ref, pin) not in node_net:
                err(f"{p.ref} pin {pin}: listed on the module but not in the netlist")
            elif p.kind != "module":
                err(f"{p.ref} pin {pin}: only a plug-in module (kind=\"module\") has pins on the module itself")

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
    bad_geometry = set()
    for p in pl.parts:
        try:
            _check_part_geometry(p)
        except PlacementError as e:
            err(str(e))
            bad_geometry.add(p.ref)
        except KeyError as e:
            err(f"{p.ref}: pin {e.args[0]} has no hole, so the part can't be drawn")
            bad_geometry.add(p.ref)

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

    if bad_geometry:
        rep.notes.append("drawing rules not checked: " + ", ".join(sorted(bad_geometry)) + " can't be placed as given")
    else:
        _check_drawing(pl, rep)
    rep.stats.update(wires=len(pl.wires), bridges=len(pl.bridges), parts=len(pl.parts),
                     nets=sum(1 for n, m in nets.items() if any(r in placed for r, _ in m)))
    return rep


def _check_part_geometry(p: Part) -> None:
    k = p.kind
    if k == "c3-supermini":
        module_frame(p)
        return
    if k == "leads":
        if not p.attrs.get("label"):
            raise PlacementError(f"{p.ref}: a leads part needs label=\"<device>\", the device its wires go to")
        for n, h in p.pins.items():
            if h in PADS:
                raise PlacementError(f"{p.ref} pin {n}: a wire can't be soldered into the {HOLES[h].text}")
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
        # The real part fixes which end pin 1 is on: seen from above with the latch (the deep side of the body,
        # 3.4 mm from the pins against 2.35 mm) toward you, pin 1 is on the left (KiCad Connector_JST
        # JST_XH_BnB-XH-A_1xNN_P2.50mm_Vertical: pad 1 at x 0, the next pads at +x, the body from y -2.35 to +3.4).
        if u[0] * lat[1] - u[1] * lat[0] < 0.5:
            raise PlacementError(f"{p.ref}: pin 1 is on the wrong end for latch=\"{p.attrs['latch']}\": with the latch "
                                 "side toward you a JST-XH header has pin 1 on the left, so this header can't be "
                                 "fitted as drawn (turn the latch round or reverse the pin order)")
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
    if k == "module":
        n = len(p.pins)
        if p.attrs.get("extends") not in DIRS:
            raise PlacementError(f"{p.ref}: a module needs extends=\"up|down|left|right\", the side its board lies on")
        pts = [p.xy(str(i)) for i in range(1, n + 1)]
        _check_in_line(p, pts, "a module's header pins must sit in one row of adjacent holes, in pin order")
        u = _unit(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        ext = DIRS[p.attrs["extends"]]
        if abs(u[0] * ext[0] + u[1] * ext[1]) > 0.01:
            raise PlacementError(f"{p.ref}: extends must point across the pin row, not along it")
        x0, y0, x1, y1 = _bbox(generic_module_outline(p))
        if x0 < 0 or y0 < 0 or x1 > BOARD_W or y1 > BOARD_H:
            raise PlacementError(f"{p.ref}: the module's board reaches past the edge of the protoboard")
        return
    if k == "cap-radial":
        a, b = p.xy("1"), p.xy("2")
        span = math.dist(a, b)
        if abs(a[0] - b[0]) > 0.01 and abs(a[1] - b[1]) > 0.01:
            raise PlacementError(f"{p.ref}: put its two leads along a letter or a number, not diagonally")
        if not 2.0 <= span <= 5.2:
            raise PlacementError(f"{p.ref}: its leads are {span:.2f} mm apart; a radial capacitor's leads bend to "
                                 "2.0-5.2 mm")
        try:
            float(p.attrs.get("d", ""))
        except ValueError:
            raise PlacementError(f"{p.ref}: a radial capacitor needs d=\"mm\", its body diameter")
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


def open_rail_links(pl: Placement, nets: dict | None) -> list[tuple[str, str, str]]:
    """The rails whose link must stay unfitted: no bridge, and the top and bottom halves both carry a part pin on
    two different nets. Each is (rail, top net, bottom net); a link there would join the two nets."""
    if not nets:
        return []
    node_net = {m: n for n, ms in nets.items() for m in ms}
    uf = connectivity(pl)
    carried: dict[str, set[str]] = {}
    for p in pl.parts:
        for n in p.pins:
            if (p.ref, n) in node_net:
                carried.setdefault(uf.find(f"{p.ref}.{n}"), set()).add(node_net[(p.ref, n)])
    out = []
    for r, (top, bottom) in BRIDGE_PADS.items():
        if r in pl.bridges:
            continue
        a = carried.get(uf.find(HOLES[top].conductor), set())
        b = carried.get(uf.find(HOLES[bottom].conductor), set())
        if a and b and a != b:
            out.append((r, " + ".join(sorted(a)), " + ".join(sorted(b))))
    return out


def _check_drawing(pl: Placement, rep: Report) -> None:
    err = rep.errors.append
    used = used_holes(pl)
    bodies = [(p.ref, s) for p in pl.parts for s in body_shapes(p)]
    # Part bodies must not overlap each other.
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            if bodies[i][0] != bodies[j][0] and polys_overlap(bodies[i][1][1], bodies[j][1][1]):
                err(f"{bodies[i][0]} and {bodies[j][0]}: their bodies overlap")
    # A plug-in module's board is raised on its header: only flat parts (resistors and wires) may lie under it, and
    # two raised modules may not overlap.
    raised = [(p.ref, raised_outline(p)) for p in pl.parts if raised_outline(p) is not None]
    for p in pl.parts:
        if p.kind != "module":
            continue
        mod = generic_module_outline(p)
        for ref, (_, poly) in bodies:
            kind = next(q.kind for q in pl.parts if q.ref == ref)
            if ref != p.ref and kind not in ("resistor",) and polys_overlap(mod, poly):
                err(f"{ref}: its body sits under {p.ref}'s raised module board")
        for ref, poly in raised:
            if ref != p.ref and polys_overlap(mod, poly):
                err(f"{p.ref} and {ref}: their raised module boards overlap")
    # No body may sit on a mounting hole's screw head (U1's sockets included; U1 itself is raised above them).
    for ref, (_, poly) in bodies:
        for (mx, my) in M3_HOLES:
            if dist_point_poly((mx, my), poly) < M3_KEEPOUT:
                err(f"{ref}: its body covers an M3 mounting hole's screw head")
        for (mx, my) in M2_HOLES:
            if dist_point_poly((mx, my), poly) < M2_KEEPOUT:
                err(f"{ref}: its body covers an M2 mounting hole")
    by_ref = {p.ref: p for p in pl.parts}
    # A loose wire's hole can't lie under a raised board (the wire would have to pass through it).
    for p in pl.parts:
        if p.kind != "leads":
            continue
        for n, h in sorted(p.pins.items()):
            for ref, poly in raised:
                if point_in_poly((HOLES[h].x, HOLES[h].y), poly):
                    err(f"{p.ref} pin {n}: hole {HOLES[h].text} is under {ref}'s raised board, so a wire can't be "
                        "soldered there")
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
                if dist_point_seg((mx, my), a, b) < WIRE_M3_KEEPOUT:
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
        if raised_outline(p) is not None:
            poly = raised_outline(p)
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


def generic_module_outline(p: Part):
    """A plug-in module's board, raised on its female header: from `over` mm before pin 1 to `over` mm past the
    last pin, and from `back` mm behind the pin row to `reach` mm on the side it extends to."""
    pins = sorted(p.pins, key=int)
    a, b = p.xy(pins[0]), p.xy(pins[-1])
    ext = DIRS[p.attrs["extends"]]
    over = float(p.attrs.get("over", 1.28))
    return _rect_along(a, b, over, float(p.attrs.get("back", 1.27)), float(p.attrs.get("reach", 18.03)), ext)[1]


def raised_outline(p: Part):
    """The outline of a module that sits raised on sockets (U1 or a plug-in module), else None."""
    if p.kind == "c3-supermini":
        return module_outline(p)
    if p.kind == "module":
        return generic_module_outline(p)
    return None


def module_point(p: Part, along: float, out: float):
    """Board mm of a point on a plug-in module: `along` mm from pin 1 toward the last pin, `out` mm toward extends."""
    pins = sorted(p.pins, key=int)
    a, b = p.xy(pins[0]), p.xy(pins[-1])
    u = _unit(b[0] - a[0], b[1] - a[1])
    ext = DIRS[p.attrs["extends"]]
    return a[0] + u[0] * along + ext[0] * out, a[1] + u[1] * along + ext[1] * out


def cap_outline(p: Part, sides: int = 20):
    a, b = p.xy("1"), p.xy("2")
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    r = float(p.attrs.get("d", 8.0)) / 2
    return [(cx + r * math.cos(2 * math.pi * i / sides), cy + r * math.sin(2 * math.pi * i / sides))
            for i in range(sides)]


def _bbox(poly):
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    return min(xs), min(ys), max(xs), max(ys)


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
    # Intake panel (its schematic names the supplies +5V and +3V3).
    "+5V": ("#D55E00", "5V", "power"),
    "+3V3": ("#CC79A7", "3V3", "power"),
    "I2S_BCLK": ("#009E73", "BCLK", "signal"),
    "I2S_LRC": ("#E69F00", "LRC", "signal"),
    "I2S_DIN": ("#B8A100", "DIN", "signal"),
    "AMP_SD": ("#7F7F7F", "SD", "signal"),
    "BTN_HOLD": ("#C9A400", "HOLD", "signal"),
    "BTN_DISCARD": ("#E15759", "DISC", "signal"),
    "LAMP_HOLD": ("#8CB33E", "LAMP Y", "signal"),
    "LAMP_DISCARD": ("#F28E2B", "LAMP R", "signal"),
    "Q1_G": ("#76B7B2", "GATE Y", "signal"),
    "Q2_G": ("#B07AA1", "GATE R", "signal"),
    "HOLD_LAMP-": ("#6A3D9A", "LED− Y", "signal"),
    "DISCARD_LAMP-": ("#A50F15", "LED− R", "signal"),
}
NET_TEXT = {
    "GND": "ground", "5V": "USB 5 V", "3V3": "3.3 V from the C3", "SDA": "I2C data, GPIO 5",
    "SCL": "I2C clock, GPIO 6", "ENC_CLK": "encoder A, GPIO 3", "ENC_DT": "encoder B, GPIO 4",
    "ENC_SW": "encoder switch, GPIO 1", "BUZZER": "buzzer drive, GPIO 0", "BZ_G": "Q1 gate",
    "BZ-": "buzzer \u2212 / Q1 drain",
    "+5V": "USB 5 V", "+3V3": "3.3 V from the C3", "I2S_BCLK": "amplifier bit clock, GPIO 10",
    "I2S_LRC": "amplifier word select, GPIO 20", "I2S_DIN": "amplifier data, GPIO 21",
    "AMP_SD": "amplifier SD (on/off)", "BTN_HOLD": "yellow button, GPIO 3", "BTN_DISCARD": "red button, GPIO 4",
    "LAMP_HOLD": "yellow lamp drive, GPIO 1", "LAMP_DISCARD": "red lamp drive, GPIO 7", "Q1_G": "Q1 gate",
    "Q2_G": "Q2 gate", "HOLD_LAMP-": "yellow lamp − / Q1 drain", "DISCARD_LAMP-": "red lamp − / Q2 drain",
}
RES_BANDS = {"220": ["#d62728", "#d62728", "#7f4f24", "#c9a227"],
             "4.7k": ["#f2d000", "#7b2cbf", "#d62728", "#c9a227"],
             "10k": ["#7f4f24", "#111111", "#e67e22", "#c9a227"],
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
        self.boxes: list[tuple] = []     # (x0, y0, x1, y1) of each text and mark drawn so far, for the callouts
        self.keep: list[tuple] = []      # the boxes of texts no callout may cover at any level (draw_late_names)

    def add(self, s: str):
        self.out.append(s)

    def text(self, x, y, t, size=1.6, anchor="middle", weight="normal", fill="#1a1a1a", extra=""):
        w = 0.62 * size * len(t)
        x0 = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
        self.boxes.append((x0, y - 0.8 * size, x0 + w, y + 0.25 * size))
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" fill="{fill}" {extra}>{esc(t)}</text>')


class View:
    """Maps board mm to sheet mm; the solder view mirrors left to right."""

    def __init__(self, solder: bool, callouts: bool = False):
        self.solder = solder
        self.callouts = callouts        # the "callouts" style: parts carry numbers, not names

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
    if p.kind == "leads":
        # Per wire: the name= given in the placement file, else its net's name, else its pin number.
        return {n: p.names.get(n) or (net_style(node_net[(p.ref, n)])[1] if (p.ref, n) in node_net else n)
                for n in p.pins}
    if p.kind == "module":
        return dict(p.names)
    if p.kind == "cap-radial":
        return {"1": "+", "2": "\u2212"}
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


def draw_open_links(svg: Svg, v: View, links: list, used_xy: list | None = None):
    """A red X between the two pads of each rail link that must stay unfitted, with "leave open" beside it in the
    nearest board margin (the + pads sit at the left edge, the - pads at the right). The X goes on the pads over a
    light backing, after the parts; its text moves up or down along the margin to a spot clear of other marks."""
    for r, _, _ in links:
        a, b = BRIDGE_PADS[r]
        bx, by = HOLES[a].x, (HOLES[a].y + HOLES[b].y) / 2
        x, y, d = v.x(bx), v.y(by), 0.65
        left = bx < BOARD_W / 2
        edge = v.x(0 if left else BOARD_W)
        out = -1 if x < v.x(BOARD_W / 2) else 1
        svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{d + 0.5:.2f}" fill="#ffffff" opacity="0.85"/>')
        svg.add(f'<path d="M{x - d:.2f},{y - d:.2f} L{x + d:.2f},{y + d:.2f} M{x - d:.2f},{y + d:.2f} '
                f'L{x + d:.2f},{y - d:.2f}" stroke="#c0392b" stroke-width="0.45" stroke-linecap="round" fill="none"/>')
        svg.boxes.append((x - d, y - d, x + d, y + d))
        tx = edge + out * 1.26
        w = 0.62 * 1.2 * len("leave open")
        x0 = tx - w if out < 0 else tx
        dy = 0.0
        for k in range(0, 8):
            dy = ((k + 1) // 2) * 2.2 * (1 if k % 2 else -1)
            box = (x0, y + dy - 0.96, x0 + w, y + dy + 0.3)
            if not any(bb[0] < box[2] and box[0] < bb[2] and bb[1] < box[3] and box[1] < bb[3] for bb in svg.boxes)                     and not any(box[0] - 0.5 < hx < box[2] + 0.5 and box[1] - 0.5 < hy < box[3] + 0.5
                                for hx, hy in (used_xy or [])):
                break
        else:
            dy = 0.0
        svg.add(f'<line x1="{x - out * 0.4:.2f}" y1="{y:.2f}" x2="{edge + out * 0.9:.2f}" y2="{y:.2f}" '
                'stroke="#c0392b" stroke-width="0.25"/>')
        if dy:
            svg.add(f'<line x1="{edge + out * 0.9:.2f}" y1="{y:.2f}" x2="{tx:.2f}" y2="{y + dy - 0.4:.2f}" '
                    'stroke="#c0392b" stroke-width="0.25"/>')
        svg.text(tx, y + dy + 0.4, "leave open", 1.2, anchor="end" if out < 0 else "start", weight="bold",
                 fill="#c0392b")


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
    if v.solder or v.callouts:
        return
    for p in pl.parts:
        polys = [module_outline(p)] if p.kind == "c3-supermini" else [poly for _, poly in body_shapes(p)]
        if p.kind == "c3-supermini":
            # Raised on its sockets: labels may sit over its outline, not over its pins or its caption.
            usb, _, (cx, _) = module_frame(p)
            mx, my = v.p((cx - usb[0] * 4.2, 26.0))
            placed.append((mx - 6.6, my - 2.2, mx + 6.6, my + 2.1))
            continue
        for poly in polys:
            xs = [v.x(a) for a, _ in poly]
            ys = [v.y(b) for _, b in poly]
            placed.append((min(xs), min(ys), max(xs), max(ys)))
    for w in pl.wires:
        col, label, _ = net_style(w.net)
        segs = w.segments()
        if w.length < 15:
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
        else:
            _end_tags(svg, v, w, segs, col, label, placed, used_xy)
        _step_number(svg, v, w, segs, steps, placed, used_xy)


def _end_tags(svg, v, w, segs, col, label, placed, used_xy):
    """A net label near each end of the wire, stepping sideways off the wire when the spot is taken."""
    for end in (0, 1):
        seg = segs[0] if end == 0 else segs[-1]
        a, b = (seg[0], seg[1]) if end == 0 else (seg[1], seg[0])
        L = math.dist(a, b)
        u = _unit(b[0] - a[0], b[1] - a[1])
        done = False
        nrm = (-u[1], u[0])
        cands = [(d, 0.0) for d in (2.7, 3.6, 4.6, 1.9, 5.8, 7.0)] + \
            [(d, k) for d in (2.7, 3.6, 4.6) for k in (2.0, -2.0)]
        for d, k in cands:
            if d > L / 2 and len(segs) == 1:
                continue
            if d > L - 0.9:
                continue
            cx, cy = v.p((a[0] + u[0] * d + nrm[0] * k, a[1] + u[1] * d + nrm[1] * k))
            wdt = 0.72 * 1.25 * len(label) + 0.9
            box = (cx - wdt / 2, cy - 0.93, cx + wdt / 2, cy + 0.93)
            if _free(box, placed, used_xy):
                tag(svg, cx, cy, label, col, placed)
                done = True
                break
        if not done and len(segs) > 1:
            # Every spot on the end leg is taken (by a part, its caption or another label): try along the others.
            for s0, s1 in (segs[1:] if end == 0 else segs[-2::-1]):
                L2 = math.dist(s0, s1)
                u2 = _unit(s1[0] - s0[0], s1[1] - s0[1])
                for f in (0.5, 0.3, 0.7):
                    cx, cy = v.p((s0[0] + u2[0] * L2 * f, s0[1] + u2[1] * L2 * f))
                    wdt = 0.72 * 1.25 * len(label) + 0.9
                    if _free((cx - wdt / 2, cy - 0.93, cx + wdt / 2, cy + 0.93), placed, used_xy):
                        tag(svg, cx, cy, label, col, placed)
                        done = True
                        break
                if done:
                    break
        if not done and end == 0:
            mid = (a[0] + u[0] * L / 2, a[1] + u[1] * L / 2)
            cx, cy = v.p(mid)
            tag(svg, cx, cy, label, col, placed)


def _step_number(svg, v, w, segs, steps, placed, used_xy):
    """The build step's number in a circle near the middle of the longest leg."""
    seg = max(segs, key=lambda s: math.dist(*s))
    a, b = seg
    L = math.dist(a, b)
    u = _unit(b[0] - a[0], b[1] - a[1])
    n = steps.get(id(w))
    if n is None:
        return
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


def sorted_pins(p: Part):
    """The part's (pin number, hole) pairs in pin order."""
    return sorted(p.pins.items(), key=lambda t: int(t[0]) if t[0].isdigit() else 0)


def lead_row(p: Part):
    """The (pin number, hole) pairs of a leads part whose pins, in pin order, sit in adjacent holes on one straight
    line, else None."""
    pins = sorted_pins(p)
    if len(pins) < 2:
        return None
    rails = {h[:2] for _, h in pins if h[:2] in RAIL_Y}
    if rails and (len(rails) > 1 or any(h[:2] not in RAIL_Y for _, h in pins)):
        return None
    pts = [(HOLES[h].x, HOLES[h].y) for _, h in pins]
    if any(abs(math.dist(a, b) - PITCH) > 0.05 for a, b in zip(pts, pts[1:])):
        return None
    if len(pts) > 2 and any(abs(_orient(pts[0], pts[-1], q)) > 0.05 for q in pts):
        return None
    return pins


def _lead_ring(svg: Svg, hx, hy, col, dnp, r, halo=1.1, width=0.55):
    dash = ' stroke-dasharray="0.8,0.5"' if dnp else ""
    svg.add(f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="{r}" fill="none" stroke="#ffffff" stroke-width="{halo}"/>')
    svg.add(f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="{r}" fill="none" stroke="{col}" stroke-width="{width}"{dash}/>')


def _row_outline(v: View, row):
    """The sheet box (x0, y0, x1, y1) round a row's holes."""
    pts = [v.p((HOLES[h].x, HOLES[h].y)) for _, h in row]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs) - 1.6, min(ys) - 1.6, max(xs) + 1.6, max(ys) + 1.6


def draw_leads(svg: Svg, v: View, pl: Placement, node_net: dict, placed: list, used_xy: list):
    """Loose wires of an off-board device: a ring in the net's colour round each hole. The default style adds a tag
    "DEVICE NAME" to each; the callouts style leaves the number to draw_callouts and puts a thin outline round a
    straight row of adjacent holes."""
    for p in pl.parts:
        if p.kind != "leads":
            continue
        names = pin_names(p, node_net)
        row = lead_row(p) if v.callouts else None
        if row:
            box = _row_outline(v, row)
            svg.add(f'<rect x="{box[0]:.2f}" y="{box[1]:.2f}" width="{box[2] - box[0]:.2f}" '
                    f'height="{box[3] - box[1]:.2f}" rx="1.0" fill="none" stroke="#333" stroke-width="0.3"/>')
        for n, h in sorted_pins(p):
            hx, hy = v.p((HOLES[h].x, HOLES[h].y))
            col = net_style(node_net.get((p.ref, n), ""))[0]
            if v.callouts:
                _lead_ring(svg, hx, hy, col, p.dnp, LEAD_RING_R, 0.9, 0.5)
                svg.add(f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="0.5" fill="{col}"/>')
                continue
            _lead_ring(svg, hx, hy, col, p.dnp, 1.3)
            svg.add(f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="0.55" fill="{col}"/>')
            label = f"{part_label(p)} {names[n]}"
            wdt = 0.72 * 1.25 * len(label) + 0.9
            cands = ([(0.0, -2.6), (0.0, 2.6), (0.0, -3.9), (0.0, 3.9)]
                     + [(s_ * (wdt / 2 + 1.6), dy) for dy in (0.0, -1.4, 1.4) for s_ in (1, -1)]
                     + [(0.0, -5.2), (0.0, 5.2)])
            spot = None
            for dx, dy in cands:
                cx, cy = hx + dx, hy + dy
                if _free((cx - wdt / 2, cy - 0.93, cx + wdt / 2, cy + 0.93), placed, used_xy):
                    spot = (cx, cy)
                    break
            if spot is None:
                spot = (hx + cands[0][0], hy + cands[0][1])
            svg.add(f'<line x1="{hx:.2f}" y1="{hy:.2f}" x2="{spot[0]:.2f}" y2="{spot[1]:.2f}" stroke="{col}" '
                    'stroke-width="0.3"/>')
            tag(svg, spot[0], spot[1], label, col, placed)


# ---------------------------------------------------------------------------------------------- callouts

CALLOUT_R = 1.3         # a callout is 2.6 mm across
LEAD_RING_R = 1.05      # the ring round a device wire's hole in the callouts style
# Parts whose callout may sit on the body: the others are small, with marks that show how to fit them.
ON_BODY = ("c3-supermini", "module", "jst-xh", "cap-radial")


def callout_numbers(pl: Placement):
    """(number by part ref, number by (leads ref, pin)): the on-board parts in build order, then each device's
    wires in pin order, device by device."""
    n = 0
    parts, leads = {}, {}
    for p in sorted(pl.parts, key=lambda p: (PART_ORDER[p.kind], p.ref)):
        if p.kind == "leads":
            continue
        n += 1
        parts[p.ref] = n
    for p in sorted((p for p in pl.parts if p.kind == "leads"), key=lambda p: p.ref):
        for pin, _ in sorted_pins(p):
            n += 1
            leads[(p.ref, pin)] = n
    return parts, leads


def _spans(p: Part) -> str:
    """"D1-D8, H1-H8": the holes of a part's header rows."""
    rows = {}
    for n, h in p.pins.items():
        rows.setdefault(h[0], []).append(int(h[1:]))
    return ", ".join(f"{r}{min(c)}-{r}{max(c)}" for r, c in sorted(rows.items()))


def part_holes(p: Part) -> str:
    """Where a part sits, as the legend and the hole table say it."""
    if p.kind == "c3-supermini":
        return _spans(p)
    pins = sorted_pins(p)
    if p.kind == "module":
        return f"{p.pins[pins[0][0]]}-{p.pins[pins[-1][0]]}"
    return ", ".join(HOLES[h].text for _, h in pins)


def _closest_on_poly(pt, poly):
    best = None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / L2))
        q = (a[0] + t * dx, a[1] + t * dy)
        if best is None or math.dist(pt, q) < math.dist(pt, best):
            best = q
    return best


def _seg_hits_rect(a, b, r, margin: float) -> bool:
    """Whether the segment a-b touches the rectangle r grown by margin."""
    x0, y0, x1, y1 = r[0] - margin, r[1] - margin, r[2] + margin, r[3] + margin
    t0, t1 = 0.0, 1.0
    for p, q, lo, hi in ((a[0], b[0], x0, x1), (a[1], b[1], y0, y1)):
        d = q - p
        if abs(d) < 1e-12:
            if p < lo or p > hi:
                return False
            continue
        s, e = (lo - p) / d, (hi - p) / d
        if s > e:
            s, e = e, s
        t0, t1 = max(t0, s), min(t1, e)
        if t0 > t1:
            return False
    return True


def _shape_hits_rect(c, square: bool, r, margin: float) -> bool:
    """Whether a callout centred at c (a square with rounded corners, else a circle) comes within margin of the
    rectangle r."""
    R = CALLOUT_R + margin
    if square:
        return r[0] - R < c[0] < r[2] + R and r[1] - R < c[1] < r[3] + R
    return math.hypot(max(r[0] - c[0], 0, c[0] - r[2]), max(r[1] - c[1], 0, c[1] - r[3])) < R


def _shape_hits_seg(c, square: bool, a, b, margin: float) -> bool:
    """Whether the segment a-b comes within margin of a callout centred at c."""
    if square:
        return _seg_hits_rect(a, b, (c[0] - CALLOUT_R, c[1] - CALLOUT_R, c[0] + CALLOUT_R, c[1] + CALLOUT_R), margin)
    return dist_point_seg(c, a, b) < CALLOUT_R + margin


def _callouts_touch(c1, sq1: bool, c2, sq2: bool, gap: float) -> bool:
    """Whether two callouts come within gap of each other."""
    if sq1 and sq2:
        return max(abs(c1[0] - c2[0]), abs(c1[1] - c2[1])) < 2 * CALLOUT_R + gap
    if sq1 or sq2:
        c, o = (c2, c1) if sq1 else (c1, c2)       # c: the round one, o: the square one
        return _shape_hits_rect(c, False, (o[0] - CALLOUT_R, o[1] - CALLOUT_R, o[0] + CALLOUT_R, o[1] + CALLOUT_R), gap)
    return math.dist(c1, c2) < 2 * CALLOUT_R + gap


class _CalloutSpace:
    """What a callout must keep clear of, in sheet mm, and the callouts placed so far."""

    def __init__(self, svg: Svg, v: View, pl: Placement):
        x0, x1 = sorted((v.x(0), v.x(BOARD_W)))
        self.bounds = (x0 + 0.4, v.y(0) + 0.4, x1 - 0.4, v.y(BOARD_H) - 0.4)
        lead_holes = {h for p in pl.parts if p.kind == "leads" for h in p.pins.values()}
        self.holes = [(*v.p((HOLES[h].x, HOLES[h].y)), LEAD_RING_R + 0.2 if h in lead_holes else 0.9)
                      for h in used_holes(pl)]
        self.holes += [(*v.p(m), 1.8) for m in M3_HOLES] + [(*v.p(m), 1.3) for m in M2_HOLES]
        self.rings = {(p.ref, n): v.p((HOLES[h].x, HOLES[h].y)) for p in pl.parts if p.kind == "leads"
                      for n, h in p.pins.items()}
        self.boxes = list(svg.boxes)
        self.keep = list(svg.keep)
        self.wires = [(v.p(a), v.p(b)) for w in pl.wires for a, b in w.segments()]
        self.wires += [tuple(v.p(q) for q in bridge_points(r)) for r in pl.bridges]
        self.bodies = {}
        for p in pl.parts:
            if p.kind == "c3-supermini":
                polys = [module_outline(p)]
            elif p.kind == "module":
                polys = [generic_module_outline(p)]
            elif p.kind == "leads":
                continue
            else:
                polys = [poly for _, poly in body_shapes(p)]
            self.bodies[p.ref] = [[v.p(q) for q in poly] for poly in polys]
        self.raised = {p.ref for p in pl.parts if p.kind in ("c3-supermini", "module")}
        self.placed: list[tuple] = []       # (centre, square) of the callouts so far
        self.leaders: list[tuple] = []      # their leader lines

    def clear(self, c, level: int, own: str | None, square: bool = False) -> bool:
        """Whether a callout centred at c covers nothing it must not. Level 0 keeps clear of wires and texts too,
        level 1 only keeps its centre off a wire, level 2 only of holes in use and other callouts. Another part's
        body counts at every level; a module's raised board does not. The protected texts (keep) and the other
        callouts count with the callout's real shape."""
        R = CALLOUT_R + 0.1
        x0, y0, x1, y1 = self.bounds
        if not (x0 + R <= c[0] <= x1 - R and y0 + R <= c[1] <= y1 - R):
            return False
        if square:
            if any(math.hypot(max(abs(c[0] - hx) - CALLOUT_R, 0), max(abs(c[1] - hy) - CALLOUT_R, 0)) < hr - 0.1
                   for hx, hy, hr in self.holes):
                return False
        elif any(math.dist(c, (hx, hy)) < R + hr for hx, hy, hr in self.holes):
            return False
        if any(_callouts_touch(c, square, q, sq, 0.3) for q, sq in self.placed):
            return False
        if any(_shape_hits_seg(c, square, a, b, 0.2) for a, b in self.leaders):
            return False
        for ref, polys in self.bodies.items():
            if ref != own and ref not in self.raised and any(dist_point_poly(c, pg) < R for pg in polys):
                return False
        if any(_shape_hits_rect(c, square, b, 0.1) for b in self.keep):
            return False
        if level >= 2:
            return True
        if level == 0 and any(_shape_hits_rect(c, square, b, -0.1) for b in self.boxes):
            return False
        lim = R + 0.7 if level == 0 else 0.6
        return not any(dist_point_seg(c, a, b) < lim for a, b in self.wires)

    def leader_cost(self, c, end) -> float | None:
        """None when the line c-end passes a hole in use, a callout, a protected text or another leader, else a cost
        for each wire it crosses."""
        for hx, hy, hr in self.holes:
            if math.dist((hx, hy), end) >= 1.0 and dist_point_seg((hx, hy), c, end) < (hr if hr > 1.0 else 0.8) + 0.1:
                return None
        if any(_shape_hits_seg(q, sq, c, end, 0.2) for q, sq in self.placed):
            return None
        u = _unit(end[0] - c[0], end[1] - c[1])
        tip = (end[0] - u[0] * (LEAD_RING_R + 0.3), end[1] - u[1] * (LEAD_RING_R + 0.3))     # where the line stops
        if any(_seg_hits_rect(c, tip, b, 0.1) for b in self.keep):
            return None
        if any(segs_intersect(c, end, a, b) for a, b in self.leaders):
            return None
        return 3.0 * sum(segs_intersect(c, end, a, b) for a, b in self.wires)


def _candidates(space: _CalloutSpace, key, polys, on_body: bool, ring, win: float, strict: bool = True):
    """Every spot (cost, centre, leader end) on a 0.5 mm grid within win mm of the part's body or the wire's ring,
    cheapest first. The end is None when no leader is needed."""
    xs = [q[0] for pg in polys for q in pg] if polys else [ring[0]]
    ys = [q[1] for pg in polys for q in pg] if polys else [ring[1]]
    mid = (sum(xs) / len(xs), sum(ys) / len(ys))
    R = CALLOUT_R
    x0, y0 = min(xs) - win, min(ys) - win
    others = [pg for ref, pgs in space.bodies.items() if ref != key and ref not in space.raised for pg in pgs]
    cands = []
    for i in range(int((max(xs) + win - x0) / 0.5) + 1):
        for j in range(int((max(ys) + win - y0) / 0.5) + 1):
            c = (x0 + i * 0.5, y0 + j * 0.5)
            if ring is not None:
                d = math.dist(c, ring)
                if math.hypot(max(abs(c[0] - ring[0]) - R, 0), max(abs(c[1] - ring[1]) - R, 0)) < LEAD_RING_R + 0.1:
                    continue
                end = ring if d > R + LEAD_RING_R + 1.5 else None
                # The callout sits nearer its own ring than any other (a leader's callout may, if strict is off).
                near_other = any(math.dist(c, q) < d + (0.4 if end is None else 0.1) for k, q in space.rings.items()
                                 if k != key)
                if near_other and (strict or end is None):
                    continue
                cands.append((d - R - LEAD_RING_R + (6.0 if near_other else 0.0), c, end))
                continue
            d = min(dist_point_poly(c, pg) for pg in polys)
            if d == 0:
                if on_body:
                    cands.append((0.02 * math.dist(c, mid), c, None))
            elif d >= R + 0.1:
                if d <= R + 0.9:
                    # Close to its own body, so it must be closer to it than to any other part's.
                    if any(dist_point_poly(c, pg) < d + 0.4 for pg in others):
                        continue
                    end = None
                else:
                    end = min((_closest_on_poly(c, pg) for pg in polys), key=lambda q: math.dist(c, q))
                cands.append(((1.0 if on_body else 0.0) + d - R, c, end))
    cands.sort(key=lambda t: t[0])
    return cands


def _place_callout(space: _CalloutSpace, key, polys, on_body: bool, ring=None, name=None):
    """The best (centre, leader end) for one callout; the end is None when none is needed. A part's callout sits on
    the body (if its kind allows) or beside it, a device wire's beside its ring; the nearest clear spot wins, and
    a spot off the body or the ring gets a leader line to it."""
    # A spot nearer its own ring than any other comes first; a leader's callout nearer another ring is the last resort.
    for strict, level, win in [(s, *lw) for s in (True, False) for lw in
                               ((0, 5), (0, 9), (1, 9), (0, 16), (1, 16), (2, 30))]:
        found = []
        for cost, c, end in _candidates(space, key, polys, on_body, ring, win, strict):
            if not space.clear(c, level, None if ring is not None else key, ring is not None):
                continue
            lc = 0.0 if end is None else space.leader_cost(c, end)
            if lc is None:
                continue
            found.append((cost + lc, c, end))
            if len(found) >= 6:
                break
        if found:
            return min(found, key=lambda t: t[0])[1:]
        if ring is None and not strict:
            break
    raise PlacementError(f"no room for the callout of {name or key}")


def _callout_shape(svg: Svg, c, no: int, square: bool):
    x, y = c
    if square:
        shape = (f'<rect x="{x - CALLOUT_R:.2f}" y="{y - CALLOUT_R:.2f}" width="{2 * CALLOUT_R:.2f}" '
                 f'height="{2 * CALLOUT_R:.2f}" rx="0.6" fill="#ffffff" stroke="#222222" stroke-width="0.3"/>')
    else:
        shape = (f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{CALLOUT_R}" fill="#ffffff" stroke="#222222" '
                 'stroke-width="0.3"/>')
    svg.add(f'<g class="callout-{"lead" if square else "part"}" data-no="{no}">{shape}'
            f'<text x="{x:.2f}" y="{y + 0.58:.2f}" font-size="1.7" text-anchor="middle" font-weight="bold" '
            f'fill="#111111">{no}</text></g>')


def draw_callouts(svg: Svg, v: View, pl: Placement, node_net: dict | None = None):
    """The numbers: a round callout on or beside each on-board part, a square one beside each device wire's ring.
    None covers a hole in use, a wire end, another callout or a ring; one that sits off its part gets a thin leader."""
    parts_no, leads_no = callout_numbers(pl)
    space = _CalloutSpace(svg, v, pl)
    todo = []
    for p in sorted(pl.parts, key=lambda p: (PART_ORDER[p.kind], p.ref)):
        if p.kind != "leads":
            todo.append((parts_no[p.ref], p.ref, space.bodies[p.ref], p.kind in ON_BODY, None, p.ref))
    wires = []
    for p in sorted((p for p in pl.parts if p.kind == "leads"), key=lambda p: p.ref):
        for pin, _ in sorted_pins(p):
            wires.append((leads_no[(p.ref, pin)], (p.ref, pin), [], False, space.rings[(p.ref, pin)],
                          f"{part_label(p) or p.ref} {pin_names(p, node_net or {})[pin]} at {HOLES[p.pins[pin]].text}"))
    # The device wires with the fewest clear spots beside their rings are placed first.
    def spots(item):
        _, key, _, _, ring, _ = item
        return sum(1 for _, c, end in _candidates(space, key, [], False, ring, 4.5)
                   if end is None and space.clear(c, 0, None, True))
    todo += sorted(wires, key=spots)
    drawn = []
    for no, key, polys, on_body, ring, name in todo:
        c, end = _place_callout(space, key, polys, on_body, ring, name)
        space.placed.append((c, ring is not None))
        if end is not None:
            space.leaders.append((c, end))
        drawn.append((no, c, end, ring is not None))
    for no, c, end, square in drawn:
        if end is not None:
            u = _unit(end[0] - c[0], end[1] - c[1])
            a = (c[0] + u[0] * CALLOUT_R, c[1] + u[1] * CALLOUT_R)
            if square:
                end = (end[0] - u[0] * (LEAD_RING_R + 0.3), end[1] - u[1] * (LEAD_RING_R + 0.3))
            svg.add(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{end[0]:.2f}" y2="{end[1]:.2f}" stroke="#222222" '
                    'stroke-width="0.25"/>')
    for no, c, end, square in drawn:
        _callout_shape(svg, c, no, square)


def draw_parts(svg: Svg, v: View, pl: Placement, node_net: dict, placed: list):
    ghost = v.solder
    for p in pl.parts:
        names = pin_names(p, node_net)
        if p.kind == "c3-supermini":
            _draw_module(svg, v, p, names, ghost)
            continue
        if p.kind == "module":
            _draw_plug_module(svg, v, p, names, ghost, placed)
            continue
        if p.kind == "leads":
            continue        # drawn after the wires, see draw_leads
        if p.dnp and not ghost:
            svg.add('<g opacity="0.5">')
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
            elif p.kind == "cap-radial":
                _draw_cap(svg, v, p)
        if p.dnp and not ghost:
            svg.add('</g>')
            for _, poly in body_shapes(p):
                pts = " ".join(f"{a:.2f},{b:.2f}" for a, b in (v.p(q) for q in poly))
                svg.add(f'<polygon points="{pts}" fill="none" stroke="#c0392b" stroke-width="0.3" '
                        'stroke-dasharray="0.9,0.6"/>')
        # Leads / joints: an empty red ring for a part fitted only when needed.
        for n, h in p.pins.items():
            x, y = v.p((HOLES[h].x, HOLES[h].y))
            if p.dnp:
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.55" fill="#ffffff" stroke="#c0392b" stroke-width="0.25"/>')
            else:
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.55" fill="#9a9a9a" stroke="#333" stroke-width="0.15"/>')
        if not v.callouts:
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
    if p.dnp:
        text2 = "DNP"
    if side in ("left", "right") and p.value and not text2:
        text1, text2 = p.ref, p.value
    if p.kind in ("c3-supermini", "jst-xh", "module"):
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
        svg.text(cx, y + 1.7, text2, 1.3, fill="#c0392b" if p.dnp else "#444", weight="bold" if p.dnp else "normal")



def _draw_cap(svg, v, p):
    """A radial electrolytic seen from above: its can, a stripe on the - side and a + by the + lead."""
    poly = cap_outline(p, 36)
    d = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in poly))
    svg.add(f'<polygon points="{d}" fill="#2c3e50" stroke="#111" stroke-width="0.3"/>')
    a, b = p.xy("1"), p.xy("2")
    u = _unit(b[0] - a[0], b[1] - a[1])
    r = float(p.attrs.get("d", 8.0)) / 2
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    nrm = (-u[1], u[0])
    s0 = (m[0] + u[0] * r * 0.62 + nrm[0] * r * 0.75, m[1] + u[1] * r * 0.62 + nrm[1] * r * 0.75)
    s1 = (m[0] + u[0] * r * 0.62 - nrm[0] * r * 0.75, m[1] + u[1] * r * 0.62 - nrm[1] * r * 0.75)
    (x0, y0), (x1, y1) = v.p(s0), v.p(s1)
    svg.add(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" stroke="#d9d9d9" stroke-width="1.0"/>')
    svg.boxes.append((min(x0, x1) - 0.5, min(y0, y1) - 0.5, max(x0, x1) + 0.5, max(y0, y1) + 0.5))
    px, py = v.p((m[0] - u[0] * r * 0.55, m[1] - u[1] * r * 0.55))
    svg.text(px, py + 0.6, "+", 1.8, weight="bold", fill="#ffffff")


def _plug_pin_names(svg, v, p, names, draw: bool = True) -> list:
    """A plug-in module's pin names on their backings, along its header; returns their boxes (which, if draw, are
    in svg.boxes too)."""
    boxes = []
    for n in sorted(p.pins, key=int):
        x, y = v.p(module_point(p, (int(n) - 1) * PITCH, 1.75))
        nm = names.get(n, n)
        w = 0.62 * len(nm) + 0.6
        boxes.append((x - w / 2, y - 0.7, x + w / 2, y + 0.6))
        if draw:
            svg.add(f'<rect x="{x - w / 2:.2f}" y="{y - 0.7:.2f}" width="{w:.2f}" height="1.3" rx="0.3" fill="#f1eaf7"/>')
            svg.text(x, y + 0.38, nm, 0.95, weight="bold", fill="#4a2370")
            svg.boxes.append(boxes[-1])
    return boxes


def _draw_plug_module(svg, v, p, names, ghost, placed):
    """A plug-in module on a 1xN female header: the socket, the raised board's outline, the pin names, any pins on
    the module itself (a screw terminal) and the caption."""
    for _, sp in body_shapes(p):
        sd = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in sp))
        svg.add(f'<polygon points="{sd}" fill="#2b2b2b" opacity="{0.25 if ghost else 0.8}"/>')
    poly = generic_module_outline(p)
    d = " ".join(f"{x:.2f},{y:.2f}" for x, y in (v.p(q) for q in poly))
    svg.add(f'<polygon points="{d}" fill="#6a3d9a" fill-opacity="0.07" stroke="#6a3d9a" stroke-width="0.4" '
            f'stroke-dasharray="1.6,0.8"/>')
    for n, h in p.pins.items():
        x, y = v.p((HOLES[h].x, HOLES[h].y))
        svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.55" fill="#9a9a9a" stroke="#333" stroke-width="0.15"/>')
    pins = sorted(p.pins, key=int)
    if not ghost:
        # The callouts style draws these names after the wires, see draw_late_names.
        placed += _plug_pin_names(svg, v, p, names, draw=not v.callouts)
    # Pins on the module itself, such as a screw terminal: one block around them, each pin named.
    if p.module_pins:
        pts = [module_point(p, al, out) for al, out in p.module_pins.values()]
        xs = [v.x(q[0]) for q in pts]
        ys = [v.y(q[1]) for q in pts]
        x0, x1, y0, y1 = min(xs) - 2.2, max(xs) + 2.2, min(ys) - 2.0, max(ys) + 2.0
        svg.add(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{x1 - x0:.2f}" height="{y1 - y0:.2f}" rx="0.5" '
                f'fill="#2e8b57" fill-opacity="{0.2 if ghost else 0.85}" stroke="#1d5c3a" stroke-width="0.3"/>')
        if not ghost:
            for n, q in zip(p.module_pins, pts):
                x, y = v.p(q)
                svg.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.8" fill="#d9d9d9" stroke="#1d5c3a" stroke-width="0.2"/>')
                svg.text(x, y + 0.42, names.get(n, n), 1.2, weight="bold", fill="#1d5c3a")
            label = p.attrs.get("terminal", "")
            if label:
                svg.text((x0 + x1) / 2, y0 - 0.6, label, 1.2, weight="bold", fill="#1d5c3a")
            placed.append((x0, y0 - 1.8, x1, y1))
            svg.boxes.append(placed[-1])
    if v.callouts:
        return
    # Caption on the raised board, between the pin names and the far edge.
    mx, my = v.p(module_point(p, (len(pins) - 1) * PITCH / 2, float(p.attrs.get("caption_at", 5.5))))
    halo = 'stroke="#ffffff" stroke-width="0.55" paint-order="stroke" stroke-linejoin="round"'
    svg.text(mx, my, f"{p.ref} {p.value}", 1.5, weight="bold", fill="#4a2370", extra=halo)
    if part_label(p):
        svg.text(mx, my + 1.8, part_label(p), 1.2, fill="#4a2370", extra=halo)
    w = 0.85 * len(f"{p.ref} {p.value}") + 1
    placed.append((mx - w / 2, my - 1.5, mx + w / 2, my + (2.3 if part_label(p) else 0.5)))

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
    if v.callouts:
        return
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
    if not v.callouts:
        _to92_letters(svg, v, p, names)


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
        bands = RES_BANDS.get(p.value.replace("\u03a9", "").replace(" ", ""), [])
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
    ups = [v.p(q) for q in up]
    svg.boxes.append((min(q[0] for q in ups), min(q[1] for q in ups), max(q[0] for q in ups), max(q[1] for q in ups)))
    ux, uy = v.p(mu)
    # In the callouts style a red "leave open" X may sit on link pads under the receptacle: the caption moves up.
    under = v.callouts and any(min(q[0] for q in up) < px < max(q[0] for q in up)
                               and min(q[1] for q in up) - 1 < py < max(q[1] for q in up) + 1 for px, py in PADS.values())
    svg.text(ux, uy + 0.5 - (2.4 if under else 0), "USB-C", 1.3, weight="bold", fill="#1f4e79")
    bx, by = v.p((cx - usb[0] * 4.2, 26.0))
    if not v.callouts:
        svg.add(f'<rect x="{bx - 6.6:.2f}" y="{by - 2.2:.2f}" width="13.2" height="4.3" rx="0.6" fill="#ffffff" opacity="0.92"/>')
    if not ghost and not v.callouts:
        _module_pin_names(svg, v, p, names)


def _with_backing(svg, back):
    """The box of the text just drawn, grown to cover its backing too."""
    b = svg.boxes[-1]
    svg.boxes[-1] = (min(b[0], back[0]), min(b[1], back[1]), max(b[2], back[2]), max(b[3], back[3]))


def _module_pin_names(svg, v, p, names):
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
        _with_backing(svg, (x - 1.4, y - 0.75, x + 1.4, y + 0.55))


def _to92_letters(svg, v, p, names, pill: bool = False):
    """The D G S letters on a TO-92's body; with pill, each on its own dark backing, for drawing over a ring."""
    f = DIRS[p.attrs["flat"]]
    for k, h in p.pins.items():
        hx, hy = HOLES[h].x, HOLES[h].y
        x, y = v.p((hx - f[0] * 1.35, hy - f[1] * 1.35))
        if pill:
            svg.add(f'<rect x="{x - 0.85:.2f}" y="{y - 0.85:.2f}" width="1.7" height="1.7" rx="0.4" fill="#3a3a3a" '
                    'stroke="#ffffff" stroke-width="0.2"/>')
        svg.text(x, y + 0.45, names[k], 1.15, weight="bold", fill="#ffffff")
        if pill:
            _with_backing(svg, (x - 0.85, y - 0.85, x + 0.85, y + 0.85))


def draw_late_names(svg: Svg, v: View, pl: Placement, node_net: dict):
    """Callouts style: U1's and a plug-in module's pin names and a TO-92's letters, drawn after the lead rings so no ring covers them, and
    before the callouts so the callouts keep clear of them (their texts are in svg.boxes)."""
    if v.solder:
        return
    first = len(svg.boxes)
    for p in pl.parts:
        if p.kind == "c3-supermini":
            _module_pin_names(svg, v, p, pin_names(p, node_net))
        elif p.kind == "to92":
            _to92_letters(svg, v, p, pin_names(p, node_net), True)
        elif p.kind == "module":
            _plug_pin_names(svg, v, p, pin_names(p, node_net))
    svg.keep += svg.boxes[first:]



def _module_caption(svg, v, p):
    """U1's caption text inside its outline, in the channel, shifted toward the far (antenna) end so it stays clear
    of the M3 hole beside the USB end and of the outline itself. Drawn after the wires, with a white halo, so a wire
    under U1 can't hide it; its backing box is drawn with the module, under the wires and labels."""
    usb, _, (cx, _) = module_frame(p)
    mx, my = v.p((cx - usb[0] * 4.2, 26.0))
    arrow = "→" if (usb[0] > 0) != v.solder else "←"
    halo = 'stroke="#ffffff" stroke-width="0.55" paint-order="stroke" stroke-linejoin="round"'
    svg.text(mx, my - 0.45, "U1 ESP32-C3", 1.5, weight="bold", fill="#1f4e79", extra=halo)
    line2 = f"{arrow} USB-C end" if arrow == "←" else f"USB-C end {arrow}"
    svg.text(mx, my + 1.45, line2, 1.25, fill="#1f4e79", extra=halo)

def module_hand(pl: Placement) -> str:
    """The C3 module's hand, from U1's placement (the placement file's own hand if it has no C3)."""
    for p in pl.parts:
        if p.kind == "c3-supermini":
            return p.attrs.get("hand", pl.hand)
    return pl.hand


def hand_words(pl: Placement) -> dict[str, str]:
    """The texts that name the module's hand: this hand, its power row side and the other hand."""
    left = module_hand(pl) != "power-right"
    return {"HAND": "POWER-LEFT" if left else "POWER-RIGHT", "hand": "power-left" if left else "power-right",
            "SIDE": "LEFT" if left else "RIGHT", "other": "power-right" if left else "power-left"}


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
    hw = hand_words(pl)
    svg.text(6, y0 + 3.6, f"For a C3 {hw['HAND']} module only", 2.3, anchor="start", weight="bold", fill="#c0392b")
    for i, t in enumerate(["Hold the module USB up, chip facing you: 5V, G and 3V3 must be the top",
                           f"three pins of the {hw['SIDE']} row. A {hw['other']} module here puts 5 V on a",
                           "GPIO pin and can destroy it. Check before you plug U1 in."]):
        svg.text(6, y0 + 6.6 + i * 2.5, t, 1.75, anchor="start", fill="#5a1a12")
    _hand_picture(svg, SHEET_W - 24, y0 + 0.8, hw["SIDE"] == "LEFT")


def _hand_picture(svg: Svg, x, y, power_left: bool = True):
    w, h = 9.0, 11.3
    svg.add(f'<rect x="{x:.2f}" y="{y + 1.6:.2f}" width="{w}" height="{h}" rx="0.8" fill="#1f4e79"/>')
    svg.add(f'<rect x="{x + w / 2 - 2.0:.2f}" y="{y + 0.6:.2f}" width="4.0" height="1.6" rx="0.5" fill="#bdc3c7"/>')
    svg.text(x + w / 2, y + 0.3, "USB up", 1.05, weight="bold", fill="#1f4e79")
    power = ["5V", "G", "3V3", "4", "3", "2", "1", "0"]
    px, ox = (x + 0.9, x + w - 0.9) if power_left else (x + w - 0.9, x + 0.9)
    for i, t in enumerate(power):
        yy = y + 2.8 + i * 1.3
        hi = i < 3
        svg.add(f'<circle cx="{px:.2f}" cy="{yy:.2f}" r="0.35" fill="{"#f1c40f" if hi else "#d9d9d9"}"/>')
        svg.add(f'<circle cx="{ox:.2f}" cy="{yy:.2f}" r="0.35" fill="#d9d9d9"/>')
        if power_left:
            svg.text(x - 0.5, yy + 0.38, t, 1.05, anchor="end", weight="bold" if hi else "normal",
                     fill="#c0392b" if hi else "#333")
        else:
            svg.text(x + w + 0.5, yy + 0.38, t, 1.05, anchor="start", weight="bold" if hi else "normal",
                     fill="#c0392b" if hi else "#333")
    if power_left:
        tx, anchor, side = x + w + 1.2, "start", "LEFT"
    else:
        tx, anchor, side = x - 1.2, "end", "RIGHT"
    svg.text(tx, y + 4.5, "power", 1.1, anchor=anchor, fill="#c0392b")
    svg.text(tx, y + 5.9, "on the", 1.1, anchor=anchor, fill="#c0392b")
    svg.text(tx, y + 7.3, side, 1.3, anchor=anchor, weight="bold", fill="#c0392b")


def callout_legend(pl: Placement, node_net: dict):
    """The callout legend's blocks, each a list of (callout number or None, shape, text lines) that stays in one
    column: one block per part (the first led by the heading "Parts"), then one per device (the first led by the
    heading "Device wires") with the device's name above its wires."""
    parts_no, leads_no = callout_numbers(pl)
    blocks = []
    for p in sorted(pl.parts, key=lambda p: (PART_ORDER[p.kind], p.ref)):
        if p.kind == "leads":
            continue
        what = f"{p.ref} {p.value}".strip()
        if part_label(p):
            what += f" {part_label(p)}" if p.value else f" ({part_label(p)})"
        text = f"{what}: {part_holes(p)}" + (f"; fit only if {p.dnp}" if p.dnp else "")
        blocks.append([(None, "head", ["Parts"])] if not blocks else [])
        blocks[-1].append((parts_no[p.ref], "round", textwrap.wrap(text, 37) or [text]))
    for i, p in enumerate(sorted((p for p in pl.parts if p.kind == "leads"), key=lambda p: p.ref)):
        names = pin_names(p, node_net)
        group = [(None, "head", ["Device wires"])] if i == 0 else []
        group.append((None, "sub", [part_label(p)]))
        for n, h in sorted_pins(p):
            group.append((leads_no[(p.ref, n)], "square", textwrap.wrap(f"{names[n]}: {HOLES[h].text}", 37)))
        blocks.append(group)
    return blocks


def draw_callout_legend(svg: Svg, pl: Placement, node_net: dict, y0: float) -> float:
    """The callouts legend in three columns under the board: every part, then every device's wires. A block (a
    part, or a device with its wires) stays in one column."""
    LH = 2.6

    def height(entries):
        return sum(LH + 0.4 if shape == "head" else LH * len(lines) for _, shape, lines in entries)
    units = callout_legend(pl, node_net)
    cap = sum(height(u) for u in units) / 3 + LH
    cols, used = [[]], 0.0
    for entries in units:
        if used and used + height(entries) > cap and len(cols) < 3:
            cols.append([])
            used = 0.0
        cols[-1].append(entries)
        used += height(entries)
    colw = (SHEET_W - 8) / 3
    bottom = y0
    for ci, col in enumerate(cols):
        x = 4 + ci * colw
        y = y0
        for entries in col:
            for no, shape, lines in entries:
                if shape in ("head", "sub") and y > y0:
                    y += 1.2 if shape == "head" else 0.8
                if shape == "head":
                    svg.text(x, y, lines[0], 1.9, anchor="start", weight="bold")
                    y += LH + 0.4
                elif shape == "sub":
                    svg.text(x, y, lines[0], 1.5, anchor="start", weight="bold", fill="#333")
                    y += LH
                else:
                    if shape == "square":
                        svg.add(f'<rect x="{x:.2f}" y="{y - 1.4:.2f}" width="2.4" height="2.4" rx="0.55" fill="#ffffff" '
                                'stroke="#222222" stroke-width="0.28"/>')
                    else:
                        svg.add(f'<circle cx="{x + 1.2:.2f}" cy="{y - 0.2:.2f}" r="1.2" fill="#ffffff" stroke="#222222" '
                                'stroke-width="0.28"/>')
                    svg.text(x + 1.2, y + 0.38, str(no), 1.5, weight="bold", fill="#111")
                    for k, line in enumerate(lines):
                        svg.text(x + 3.4, y + k * LH, line, 1.4, anchor="start", fill="#333")
                    y += LH * len(lines)
        bottom = max(bottom, y)
    return bottom + 1.5


def draw_legend(svg: Svg, pl: Placement, y0: float, nets_used: list[str], solder: bool,
                open_links: list | None = None) -> float:
    callouts = pl.style == "callouts"
    svg.text(4, y0, "Nets (wire colours)" if callouts else "Nets (each wire end is labelled too)", 1.9, anchor="start",
             weight="bold")
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
    if not callouts:
        svg.add(f'<circle cx="38" cy="{y - 0.5:.2f}" r="1.05" fill="#111"/>')
        svg.text(38, y - 0.05, "3", 1.25, weight="bold", fill="#fff")
        svg.text(39.8, y, "build step", 1.45, anchor="start", fill="#444")
    svg.add(f'<rect x="58" y="{y - 1.3:.2f}" width="1.6" height="1.6" rx="0.8" fill="#c98b3a" opacity="0.6"/>')
    svg.text(60.4, y, "copper strip: its holes are joined", 1.45, anchor="start", fill="#444")
    if callouts:
        y += 3.4
        svg.add(f'<circle cx="5.2" cy="{y - 0.5:.2f}" r="1.2" fill="#ffffff" stroke="#222222" stroke-width="0.28"/>')
        svg.text(5.2, y - 0.1, "4", 1.4, weight="bold", fill="#111")
        svg.text(7.4, y, "a part on the board (see Parts)", 1.45, anchor="start", fill="#444")
        svg.add(f'<rect x="58" y="{y - 1.7:.2f}" width="2.4" height="2.4" rx="0.55" fill="#ffffff" stroke="#222222" '
                'stroke-width="0.28"/>')
        svg.text(59.2, y - 0.1, "9", 1.4, weight="bold", fill="#111")
        svg.text(62, y, "a wire of an off-board device (see Device wires)", 1.45, anchor="start", fill="#444")
    y += 3.2
    svg.add(f'<line x1="4" y1="{y - 0.5:.2f}" x2="10" y2="{y - 0.5:.2f}" stroke="#c0392b" stroke-width="0.45" stroke-dasharray="1.2,0.7"/>')
    svg.text(11, y, "unmarked edge trace, broken at the link pads beside the M3 holes; the links join the halves",
             1.4, anchor="start", fill="#444")
    if callouts and open_links:
        y += 3.2
        svg.add(f'<path d="M4.2,{y - 1.3:.2f} L5.8,{y + 0.3:.2f} M4.2,{y + 0.3:.2f} L5.8,{y - 1.3:.2f}" '
                'stroke="#c0392b" stroke-width="0.45" stroke-linecap="round" fill="none"/>')
        svg.text(7.5, y, "leave open: fitting a link here would join two rail halves that carry different nets (see the build steps)",
                 1.4, anchor="start", fill="#444")
    if any(p.dnp for p in pl.parts):
        y += 3.2
        svg.add(f'<circle cx="5" cy="{y - 0.5:.2f}" r="0.55" fill="#ffffff" stroke="#c0392b" stroke-width="0.25"/>')
        svg.add(f'<rect x="7" y="{y - 1.5:.2f}" width="4" height="2" fill="none" stroke="#c0392b" stroke-width="0.3" '
                'stroke-dasharray="0.9,0.6"/>')
        svg.text(12.5, y, "DNP: a part fitted only when needed (see the build list); keep its holes free", 1.4,
                 anchor="start", fill="#444")
    if any(w.route == "channel" for w in pl.wires):
        y += 3.2
        svg.add(f'<polyline points="4,{y - 1.4:.2f} 4,{y - 0.3:.2f} 10,{y - 0.3:.2f} 10,{y - 1.4:.2f}" fill="none" '
                'stroke="#555" stroke-width="0.6"/>')
        svg.text(11, y, "a wire laid along the centre channel (no copper there), under U1 where drawn", 1.4,
                 anchor="start", fill="#444")
    y += 3.6
    svg.add(f'<line x1="4" y1="{y:.2f}" x2="24" y2="{y:.2f}" stroke="#111" stroke-width="0.4"/>')
    for xx in (4, 24):
        svg.add(f'<line x1="{xx}" y1="{y - 0.8:.2f}" x2="{xx}" y2="{y + 0.8:.2f}" stroke="#111" stroke-width="0.4"/>')
    svg.text(26, y + 0.5, "20 mm: printed at 100 % (actual size) this bar measures 20 mm and the board is real size",
             1.4, anchor="start", fill="#444")
    return y + 3


def build_steps(pl: Placement, nets: dict | None = None):
    """Build order, lowest parts first: links and wires, resistors, diode, transistor, sockets, headers, loose
    wires. nets (the netlist) names each loose wire; without it the placement file's pin names are used. Each step
    is (kind, text, item, holes, number); the number is the callout number(s) of a step in the callouts style."""
    node_net = {m: n for n, ms in (nets or {}).items() for m in ms}
    callouts = pl.style == "callouts"
    parts_no, leads_no = callout_numbers(pl)
    steps = []
    wire_steps = {}
    for r in pl.bridges:
        a, b = BRIDGE_PADS[r]
        sym = "+" if r == "+" else "−"
        steps.append(("link", f"Rail link ({sym}): wire from the {HOLES[a].text} to the {HOLES[b].text}. It joins "
                              f"the top and bottom {sym} rails.", f"{sym} rail link", f"{HOLES[a].text} to {HOLES[b].text}"))

    def wkey(w):
        under = any(seg_hits_poly(a, b, raised_outline(p)) for p in pl.parts if raised_outline(p) is not None
                    for a, b in w.segments())
        return (0 if under else 1, -w.length)
    for w in sorted(pl.wires, key=wkey):
        label = net_style(w.net)[1]
        shape = {"": "straight", "channel": "two bends, along the centre channel"}.get(w.route, "one bend")
        steps.append(("wire", f"Wire {label}: {HOLES[w.a].text} to {HOLES[w.b].text} ({shape}, {w.length:.0f} mm).",
                      f"wire {label}", f"{HOLES[w.a].text} to {HOLES[w.b].text}" +
                      {"": "", "channel": " (along the channel)"}.get(w.route, " (one bend)")))
        wire_steps[id(w)] = len(steps)
    for p in sorted(pl.parts, key=lambda p: (PART_ORDER[p.kind], p.ref)):
        if p.dnp:
            continue
        pins = sorted(p.pins.items(), key=lambda t: int(t[0]) if t[0].isdigit() else 0)
        first = len(steps)
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
            spans = _spans(p)
            steps.append(("part", f"U1 sockets: two 1x8 female headers in {spans}. Plug U1 in while soldering to keep "
                                  "them square, then take it out.", "U1 sockets", spans))
        elif p.kind == "jst-xh":
            names = ", ".join(f"{n} {p.pins[n]}" for n, _ in pins)
            steps.append(("part", f"{p.ref} ({part_label(p)}, JST-XH {len(pins)}-pin): pin 1 in {p.pins['1']}, "
                                  f"latch side toward the {_dir_word(p.attrs['latch'])}.",
                          f"{p.ref} {part_label(p)}", "pin " + names))
        elif p.kind == "module":
            span = f"{p.pins[pins[0][0]]}-{p.pins[pins[-1][0]]}"
            steps.append(("part", f"{p.ref} socket: a 1x{len(pins)} female header in {span}. Plug {p.ref} in while "
                                  "soldering to keep it square, then take it out.", f"{p.ref} socket", span))
        elif p.kind == "leads":
            pin_names_ = pin_names(p, node_net)
            if callouts:
                nos = [leads_no[(p.ref, n)] for n, _ in pins]
                span = f"{nos[0]}-{nos[-1]}" if len(nos) > 1 else str(nos[0])
                listing = ", ".join(f"{leads_no[(p.ref, n)]} {pin_names_[n]} in {HOLES[h].text}" for n, h in pins)
                steps.append(("part", f"Device wire{'s' if len(nos) > 1 else ''} {span}, {part_label(p)}: "
                                      f"{listing}. Solder each wire from the top, then tie the bundle to the board "
                                      "edge.", f"{part_label(p)} wires",
                              ", ".join(f"{leads_no[(p.ref, n)]} {pin_names_[n]} {HOLES[h].text}" for n, h in pins),
                              span))
                continue
            listing = ", ".join(f"{pin_names_[n]} in {HOLES[h].text}" for n, h in pins)
            steps.append(("part", f"{part_label(p)} wires ({p.ref}): {listing}. Solder each wire from the top, then "
                                  "tie the bundle to the board edge.",
                          f"{p.ref} {part_label(p)} wires",
                          ", ".join(f"{pin_names_[n]} {HOLES[h].text}" for n, h in pins)))
        elif p.kind == "cap-radial":
            steps.append(("part", f"{p.ref} ({p.value}): + lead in {HOLES[p.pins['1']].text}, − lead (the striped "
                                  f"side) in {HOLES[p.pins['2']].text}.", f"{p.ref} {p.value}",
                          f"+ {HOLES[p.pins['1']].text}, − {HOLES[p.pins['2']].text}"))
        if callouts and len(steps) > first:
            kind, text, item, holes = steps[-1]
            steps[-1] = (kind, f"Part {parts_no[p.ref]}, {text}", item, holes, str(parts_no[p.ref]))
    plug = "".join(f" Plug {p.ref} in {p.attrs['fit']}." for p in pl.parts if p.kind == "module" and p.attrs.get("fit"))
    leave = ""
    for r, top, bottom in open_rail_links(pl, nets):
        sym = "+" if r == "+" else "−"
        leave += (f"Leave the {sym} rail link pads beside the {'left' if r == '+' else 'right'} M3 hole open: the "
                  f"top {sym} rail is {net_style(top)[1]} and the bottom {sym} rail is {net_style(bottom)[1]}. "
                  f"Joining them would short {net_style(top)[1]} to {net_style(bottom)[1]}. ")
    pairs = "".join(f", no short from {net_style(top)[1]} to {net_style(bottom)[1]}"
                    for _, top, bottom in open_rail_links(pl, nets))
    steps.append(("check", leave + f"Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND{pairs}. Then plug U1 in, USB-C "
                           f"toward the board edge as drawn, after checking it is a {hand_words(pl)['hand']} module."
                  + plug, "", ""))
    return [s if len(s) == 5 else s + ("",) for s in steps], wire_steps


def _dir_word(d: str) -> str:
    return {"up": "top edge (the J side)", "down": "bottom edge (the A side)", "left": "number 1 end",
            "right": "number 30 end"}[d]


def render_sheet(pl: Placement, nets: dict, solder: bool) -> str:
    node_net = {m: n for n, ms in nets.items() for m in ms}
    uf = connectivity(pl)
    used = used_holes(pl)
    v = View(solder, pl.style == "callouts")
    steps, wire_steps = build_steps(pl, nets)
    svg = Svg()
    draw_header(svg, pl, solder)
    draw_board(svg, v, pl, uf, used)
    placed: list = []
    used_xy = [v.p((HOLES[h].x, HOLES[h].y)) for h in used]
    draw_parts(svg, v, pl, node_net, placed)
    draw_wires(svg, v, pl, wire_steps, placed, used_xy)
    draw_leads(svg, v, pl, node_net, placed, used_xy)
    open_links = open_rail_links(pl, nets)
    if v.callouts:
        draw_open_links(svg, v, open_links, used_xy)
        draw_late_names(svg, v, pl, node_net)
        draw_callouts(svg, v, pl, node_net)
    else:
        for p in pl.parts:
            if p.kind == "c3-supermini":
                _module_caption(svg, v, p)
    nets_used = []
    for net in NET_STYLE:
        if any(w.net == net for w in pl.wires) or any(node_net.get((p.ref, n)) == net for p in pl.parts for n in p.pins):
            nets_used.append(net)
    y0 = BY + BOARD_H + 7.5
    if v.callouts:
        y0 = draw_callout_legend(svg, pl, node_net, y0) + 2.0
    hgt = draw_legend(svg, pl, y0, nets_used, solder, open_links)
    body = "\n".join(svg.out)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W}mm" height="{hgt:.1f}mm" '
            f'viewBox="0 0 {SHEET_W} {hgt:.1f}" font-family="Arial, Helvetica, sans-serif">\n'
            f'<rect x="0" y="0" width="{SHEET_W}" height="{hgt:.1f}" fill="#ffffff"/>\n{body}\n</svg>\n')


def steps_markdown(pl: Placement, nets: dict | None = None) -> str:
    steps, _ = build_steps(pl, nets)
    callouts = pl.style == "callouts"
    if callouts:
        out = ["Build order (lowest parts first). The numbers are the callouts on the drawing; wire links carry "
               "no number:", ""]
        out += [f"- {text}" for _, text, _, _, _ in steps]
    else:
        out = ["Build order (lowest parts first; the numbers on the wires in the top view are these step numbers):",
               ""]
        for i, (_, text, _, _, _) in enumerate(steps, 1):
            out.append(f"{i}. {text}")
    dnp = [p for p in pl.parts if p.dnp]
    parts_no, _ = callout_numbers(pl)
    if dnp:
        out += ["", "Parts fitted only when needed (marked DNP on the drawing): leave their holes free.", ""]
        for p in sorted(dnp, key=lambda p: p.ref):
            holes = " and ".join(HOLES[h].text for _, h in sorted(p.pins.items()))
            no = f"Part {parts_no[p.ref]}, " if callouts else ""
            out.append(f"- {no}{p.ref} ({p.value}), {holes}: fit it only if {p.dnp}.")
    if callouts:
        rows = [(s[4], s[2], s[3]) for s in steps if s[0] != "check"]
        for p in dnp:
            rows.append((str(parts_no[p.ref]), f"{p.ref} {p.value} (fit only if needed)",
                         " and ".join(HOLES[h].text for _, h in sorted(p.pins.items()))))
        # Wire links first, then the numbered rows in number order.
        rows.sort(key=lambda r: int(r[0].split("-")[0]) if r[0] else 0)
        out += ["", "| No. | Item | Holes |", "|---|---|---|"]
        out += [f"| {no} | {item} | {holes} |" for no, item, holes in rows]
    else:
        out += ["", "| Step | Item | Holes |", "|---|---|---|"]
        for i, (kind, _, item, holes, _) in enumerate(steps, 1):
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


ENLARGED_WORDING = (
    ("TOP VIEW (component side), real size", "TOP VIEW (component side), enlarged, not to scale"),
    ("20 mm: printed at 100 % (actual size) this bar measures 20 mm and the board is real size",
     "This bar is NOT 20 mm on this enlarged page: measure on the real-size pages"),
)


def enlarged_text(svg: str) -> str:
    """The sheet's own claims of real size reworded for a copy drawn larger than real size. The scale bar's
    caption must be there; a claim that is left is refused rather than written into a page."""
    for old, new in ENLARGED_WORDING:
        found = esc(old) in svg
        if not found and old.startswith("20 mm"):
            raise PlacementError("the scale bar's caption was not found: the enlarged page would claim real size")
        svg = svg.replace(esc(old), esc(new))
    if "real size" in svg or "actual size" in svg:
        raise PlacementError("the enlarged page would still claim real size")
    return svg


def write_pdf(pl: Placement, top: str, solder: str, md: str, out: Path, page: str) -> None:
    browser = edge_path()
    if not browser:
        raise PlacementError("--pdf needs Microsoft Edge or Chrome (set EDGE to its file)")
    html = pdf_html(pl, top, solder, md, page)
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


def steps_html(md: str) -> str:
    """The steps file as HTML, every line in the file's order: paragraphs, runs of bullets, runs of numbered
    lines, and the table (its header row in <thead>, so a continuation page repeats it)."""
    import html as _h
    out: list[str] = []
    run: tuple[str, list[str]] | None = None   # (list tag, items) being collected
    table: list[str] | None = None             # rows of the open table; None until one starts
    table_done = False
    table_cols = 0

    def close_run():
        nonlocal run
        if run:
            out.append(f"<{run[0]}>" + "".join(f"<li>{_h.escape(i)}</li>" for i in run[1]) + f"</{run[0]}>")
        run = None

    def close_table():
        nonlocal table, table_done
        if table is not None:
            if len(table) < 2:
                raise PlacementError("the steps table has no rows under its header")
            out.append("<table><thead>" + table[0] + "</thead><tbody>" + "".join(table[1:]) + "</tbody></table>")
            table, table_done = None, True

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip("|").split("|")]

    for n, line in enumerate(md.splitlines(), 1):
        if not line.strip():
            close_run()
            close_table()
            continue
        if line.startswith("|"):
            close_run()
            if table is None:
                if table_done or not line.startswith("| "):
                    raise PlacementError(f"steps line {n}: a table row outside the one table: {line[:40]!r}")
                table = []
                head = cells(line)
                table.append("<tr>" + "".join(f"<th>{_h.escape(c)}</th>" for c in head) + "</tr>")
                table_cols = len(head)
            elif line.startswith("|---"):
                if len(table) != 1 or len(cells(line)) != table_cols:
                    raise PlacementError(f"steps line {n}: the table separator is not under the header")
            elif line.startswith("| ") and len(cells(line)) == table_cols:
                table.append("<tr>" + "".join(f"<td>{_h.escape(c)}</td>" for c in cells(line)) + "</tr>")
            else:
                raise PlacementError(f"steps line {n}: not a table row of {table_cols} cells: {line[:40]!r}")
            continue
        if table is not None:
            raise PlacementError(f"steps line {n}: text inside the table: {line[:40]!r}")
        m = re.match(r"(\d+)\. (.+)", line)
        if line.startswith("- ") and len(line) > 2:
            tag, text = "ul", line[2:]
        elif m:
            tag, text = "ol", m.group(2)
        elif re.match(r"[A-Za-z]", line):
            close_run()
            out.append(f'<p class="steps">{_h.escape(line)}</p>')
            continue
        else:
            raise PlacementError(f"steps line {n}: not a paragraph, bullet, numbered line or table row: {line[:40]!r}")
        if run and run[0] != tag:
            close_run()
        if run is None:
            run = (tag, [])
        run[1].append(text)
    close_run()
    close_table()
    return "\n".join(out)


def pdf_html(pl: Placement, top: str, solder: str, md: str, page: str) -> str:
    """The page blocks of the PDF: the top and the solder sheet enlarged, the same two at real size, the build list."""
    size = {"a4": "210mm 297mm", "letter": "8.5in 11in"}[page]

    def scaled(svg: str, k: float) -> str:
        w = float(re.search(r'width="([\d.]+)mm"', svg).group(1))
        h = float(re.search(r'height="([\d.]+)mm"', svg).group(1))
        return re.sub(r'width="[\d.]+mm" height="[\d.]+mm"', f'width="{w * k:.1f}mm" height="{h * k:.1f}mm"', enlarged_text(svg), count=1)
    import html as _h
    build = steps_html(md)
    # The enlarged pages scale the sheet to fit the page when a tall sheet (the callouts legend) needs it.
    page_h = {"a4": 297.0, "letter": 279.4}[page]
    height = float(re.search(r'height="([\d.]+)mm"', top).group(1))
    k = min(1.45, (page_h - 16 - 14) / height)
    warn = top[top.index("<svg"):]
    hw = hand_words(pl)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{_h.escape(pl.title or pl.device)}, protoboard build</title><style>
@page {{ size: {size}; margin: 8mm; }}
body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; }}
.page {{ page-break-after: always; text-align: center; }}
.page:last-child {{ page-break-after: auto; }}
h2 {{ font-size: 13pt; margin: 2mm 0; text-align: left; }}
p.note {{ font-size: 9pt; text-align: left; margin: 1mm 0 3mm; }}
ol, ul {{ text-align: left; font-size: 8.5pt; margin: 0 0 3mm 5mm; padding-left: 4mm; }}
table {{ border-collapse: collapse; font-size: 8pt; text-align: left; width: 100%; }}
td, th {{ border: 0.2mm solid #999; padding: 0.6mm 1.2mm; }}
tr {{ page-break-inside: avoid; }}
p.steps {{ font-size: 8.5pt; text-align: left; margin: 0 0 2mm; }}
</style></head><body>
<div class="page"><h2>Top view, enlarged for reading</h2>{scaled(top, k)}</div>
<div class="page"><h2>Solder side, enlarged for reading</h2>{scaled(solder, k)}</div>
<div class="page"><h2>Real size (print at 100 %, "actual size"): lay the board on the drawing</h2>
<p class="note">Check the 20 mm bar with a ruler before you rely on the drawing.</p>{top}</div>
<div class="page"><h2>Real size, solder side</h2>{solder}</div>
<div class="page"><h2>Build order and hole table</h2>
<p class="note">For a C3 {hw['HAND']} module only (USB up: 5V, G, 3V3 at the top of the {hw['SIDE']} row). A {hw['other']} module
in this layout puts 5 V on a GPIO pin and can destroy it.</p>
{build}</div>
</body></html>"""
    return html


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
    try:
        top = render_sheet(pl, nets, False)
        solder = render_sheet(pl, nets, True)
        md = steps_markdown(pl, nets)
    except PlacementError as e:
        print(e, file=sys.stderr)
        return 1
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
