#!/usr/bin/env python3
"""Netlist parity: do two schematics wire the same pins together?

Usage: python tools/netlist_parity.py A B

A and B are each a .kicad_sch (its netlist is exported with kicad-cli, found through the KICAD_CLI
environment variable or on PATH) or a kicadxml netlist (.xml or .net). Each net is compared by its
members, the (reference, pin) pairs on it; net names are ignored, so a renamed net still matches.
Use it to show that two board variants of one device, which differ only in footprints and part
numbers, have identical connectivity.
Exit 0 when every net matches, 1 with the differences listed, 2 when a netlist can't be read or
exported.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


class ParityError(Exception):
    pass


def kicad_cli():
    """The kicad-cli to run: the KICAD_CLI file if that is set, else the one on PATH, else None."""
    env = os.environ.get("KICAD_CLI")
    if env:
        return env if Path(env).is_file() else None
    return shutil.which("kicad-cli")


def export_netlist(sch: Path, out: Path) -> None:
    cli = kicad_cli()
    if not cli:
        raise ParityError(f"{sch}: no kicad-cli: put it on PATH or set KICAD_CLI to its file")
    try:
        r = subprocess.run([cli, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out), str(sch)],
                           capture_output=True, text=True)
    except OSError as e:
        raise ParityError(f"{sch}: cannot run kicad-cli: {e}")
    if r.returncode != 0 or not out.is_file():
        raise ParityError(f"{sch}: kicad-cli netlist export failed: {(r.stderr or r.stdout).strip()}")


def read_nets(path: Path) -> dict:
    """{net name: frozenset of (ref, pin)} from a kicadxml netlist."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise ParityError(f"{path}: cannot parse netlist: {e}")
    nets = {}
    for n in root.findall("./nets/net"):
        nets[n.get("name", "")] = frozenset((node.get("ref", ""), node.get("pin", "")) for node in n.findall("node"))
    return nets


def load(path: Path, tmp: Path) -> dict:
    if not path.is_file():
        raise ParityError(f"{path}: not found")
    if path.suffix == ".kicad_sch":
        out = tmp / f"{len(list(tmp.iterdir()))}.xml"
        export_netlist(path, out)
        return read_nets(out)
    return read_nets(path)


def _fmt(members) -> str:
    return " ".join(f"{r}.{p}" for r, p in sorted(members))


def compare(a: dict, b: dict, a_label="A", b_label="B") -> list:
    """The differences between two {name: members} maps, compared by members only."""
    a_sets, b_sets = {}, {}
    for name, m in a.items():
        a_sets.setdefault(m, []).append(name)
    for name, m in b.items():
        b_sets.setdefault(m, []).append(name)
    diffs = []
    for m in sorted(set(a_sets) - set(b_sets), key=_fmt):
        diffs.append(f"only in {a_label}: net {', '.join(a_sets[m])}: {_fmt(m)}")
    for m in sorted(set(b_sets) - set(a_sets), key=_fmt):
        diffs.append(f"only in {b_label}: net {', '.join(b_sets[m])}: {_fmt(m)}")
    return diffs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("a", help="first schematic (.kicad_sch) or kicadxml netlist")
    ap.add_argument("b", help="second schematic (.kicad_sch) or kicadxml netlist")
    args = ap.parse_args(argv)
    a, b = Path(args.a), Path(args.b)
    try:
        with tempfile.TemporaryDirectory() as t:
            na, nb = load(a, Path(t)), load(b, Path(t))
    except ParityError as e:
        print(e, file=sys.stderr)
        return 2
    diffs = compare(na, nb, str(a), str(b))
    for d in diffs:
        print(d)
    if diffs:
        return 1
    print(f"{len(na)} nets match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
