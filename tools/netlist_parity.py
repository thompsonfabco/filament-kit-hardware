#!/usr/bin/env python3
"""Netlist parity: do two schematics wire the same pins together?

Usage: python tools/netlist_parity.py A B [--exceptions FILE]

A and B are each a .kicad_sch (its netlist is exported with kicad-cli, found through the KICAD_CLI
environment variable or on PATH) or a kicadxml netlist (.xml or .net). Each net is compared by its
members, the (reference, pin) pairs on it; net names are ignored, so a renamed net still matches.
Use it to show that two board variants of one device, which differ only in footprints and part
numbers, have identical connectivity.

An exceptions file covers a block that one variant builds differently, for example a module that
the other variant replaces with a chip and its parts. It lists the references of that block and,
for each side, every net that holds one of them, in full:

    # comment
    refs U2 C2
    a U1.7 U2.1
    b U1.7 U2.14
    b U1.9 U2.7 C2.1

One line per net: "a" or "b" for the side, then the net's members as REF.PIN.

On each side the nets that hold an excepted reference must be exactly the listed nets. Then the
excepted references are taken out of every net on both sides, and what is left must match exactly.
Exit 0 when every net matches, 1 with the differences listed, 2 when a netlist or the exceptions
file can't be read or exported.
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


def read_exceptions(path: Path):
    """(excepted refs, listed A nets, listed B nets) from an exceptions file; nets as frozensets of (ref, pin)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise ParityError(f"{path}: cannot read exceptions: {e}")
    refs, nets = set(), {"a": [], "b": []}
    for n, line in enumerate(lines, 1):
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        key, rest = words[0], words[1:]
        if not rest:
            raise ParityError(f"{path}:{n}: '{key}' with nothing after it")
        if key == "refs":
            refs.update(rest)
        elif key in nets:
            members = []
            for w in rest:
                ref, dot, pin = w.rpartition(".")
                if not dot or not ref or not pin:
                    raise ParityError(f"{path}:{n}: '{w}' is not REF.PIN")
                members.append((ref, pin))
            if len(set(members)) != len(members):
                raise ParityError(f"{path}:{n}: a member is listed twice")
            nets[key].append(frozenset(members))
        else:
            raise ParityError(f"{path}:{n}: unknown line type '{key}' (expected refs, a or b)")
    if not refs:
        raise ParityError(f"{path}: no 'refs' line")
    for side in nets:
        for m in nets[side]:
            if not any(r in refs for r, _ in m):
                raise ParityError(f"{path}: listed {side} net {_fmt(m)} holds no excepted reference")
    return refs, nets["a"], nets["b"]


def apply_exceptions(net_map: dict, refs: set, listed: list, label: str):
    """Check one side's excepted nets against the listed ones, then strip the excepted refs.

    Returns (problems, {name: members} without the excepted refs, with emptied nets dropped)."""
    held = {m: name for name, m in net_map.items() if any(r in refs for r, _ in m)}
    problems = []
    for m in sorted(set(held) - set(listed), key=_fmt):
        problems.append(f"only in {label}: excepted net {held[m]} not in the exceptions file: {_fmt(m)}")
    for m in sorted(set(listed) - set(held), key=_fmt):
        problems.append(f"exceptions file: no net in {label} is exactly: {_fmt(m)}")
    stripped = {}
    for name, m in net_map.items():
        rest = frozenset((r, p) for r, p in m if r not in refs)
        if rest:
            stripped[name] = rest
    return problems, stripped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("a", help="first schematic (.kicad_sch) or kicadxml netlist")
    ap.add_argument("b", help="second schematic (.kicad_sch) or kicadxml netlist")
    ap.add_argument("--exceptions", help="exceptions file: a block wired differently on purpose (see above)")
    args = ap.parse_args(argv)
    a, b = Path(args.a), Path(args.b)
    try:
        exc = read_exceptions(Path(args.exceptions)) if args.exceptions else None
        with tempfile.TemporaryDirectory() as t:
            na, nb = load(a, Path(t)), load(b, Path(t))
    except ParityError as e:
        print(e, file=sys.stderr)
        return 2
    problems = []
    if exc:
        refs, la, lb = exc
        seen = {r for m in list(na.values()) + list(nb.values()) for r, _ in m}
        problems += [f"exceptions file: ref {r} is in neither netlist" for r in sorted(refs - seen)]
        pa, na = apply_exceptions(na, refs, la, str(a))
        pb, nb = apply_exceptions(nb, refs, lb, str(b))
        problems += pa + pb
    diffs = problems + compare(na, nb, str(a), str(b))
    for d in diffs:
        print(d)
    if diffs:
        return 1
    if exc:
        print(f"{len(na)} nets match outside the exceptions; {len(exc[1])} + {len(exc[2])} excepted nets "
              f"(refs {' '.join(sorted(exc[0]))}) match {args.exceptions}")
    else:
        print(f"{len(na)} nets match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
