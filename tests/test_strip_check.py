import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import strip_check as sc  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "strips"
BOARD = FIXTURES / "board.xml"


def footprint(ref, x, y, pads, rot=None, lib="Test:Part"):
    """A footprint block; pads are (number, dx, dy, net or None)."""
    at = f"{x} {y}" + (f" {rot}" if rot is not None else "")
    out = [f'\t(footprint "{lib}"\n\t\t(layer "F.Cu")\n\t\t(at {at})\n'
           f'\t\t(property "Reference" "{ref}"\n\t\t\t(at 0 0 0)\n\t\t)']
    for number, dx, dy, net in pads:
        netpart = f'\n\t\t\t(net "{net}")' if net else ""
        out.append(f'\t\t(pad "{number}" thru_hole circle\n\t\t\t(at {dx} {dy})'
                   f'\n\t\t\t(size 1.6 1.6){netpart}\n\t\t)')
    return "\n".join(out) + "\n\t)\n"


def pcb(tmp_path, *footprints):
    path = tmp_path / "t.kicad_pcb"
    path.write_text('(kicad_pcb\n\t(version 20260101)\n' + "".join(footprints) + ")\n", encoding="utf-8")
    return path


def run(tmp_path, *footprints, tolerance=0.5):
    holes = sc.load_board(BOARD)
    return sc.check_pads(sc.read_pads(pcb(tmp_path, *footprints)), holes, tolerance)


def test_two_nets_in_one_strip_fail(tmp_path):
    conflicts, warnings = run(tmp_path,
                              footprint("J1", 10, 10, [("1", 0, 0, "SDA")]),
                              footprint("J2", 10, 12.54, [("1", 0, 0, "BUZZER")]))
    assert warnings == []
    assert len(conflicts) == 1
    assert "strip 1-FJ" in conflicts[0] and "SDA (J1.1)" in conflicts[0] and "BUZZER (J2.1)" in conflicts[0]


def test_same_net_in_one_strip_passes(tmp_path):
    conflicts, warnings = run(tmp_path,
                              footprint("J1", 10, 10, [("1", 0, 0, "GND")]),
                              footprint("J2", 10, 12.54, [("1", 0, 0, "GND")]))
    assert (conflicts, warnings) == ([], [])


def test_rotated_footprint(tmp_path):
    # Pad 2 sits 2.54 mm to the right of pad 1 unrotated. Turned 90 degrees counter-clockwise on
    # screen (angle 90 in KiCad, y down) it lands 2.54 mm above, so it moves from strip 2-FJ to
    # the hole above F1, which is off-grid here; at 270 it lands on G1 (strip 1-FJ) with pad 1.
    pads = [("1", 0, 0, "A"), ("2", 2.54, 0, "B")]
    ok, w = run(tmp_path, footprint("U1", 10, 10, pads))
    assert ok == [] and w == []
    conflicts, warnings = run(tmp_path, footprint("U1", 10, 10, pads, rot=270))
    assert len(conflicts) == 1 and "strip 1-FJ" in conflicts[0]
    conflicts, warnings = run(tmp_path, footprint("U1", 10, 10, pads, rot=90))
    assert conflicts == [] and len(warnings) == 1 and "U1.2" in warnings[0]


def test_off_grid_pad_warns_only(tmp_path):
    conflicts, warnings = run(tmp_path, footprint("J1", 10, 11.27, [("1", 0, 0, "SDA")]))
    assert conflicts == []
    assert len(warnings) == 1
    assert "off-grid" in warnings[0] and "J1.1" in warnings[0] and "1.27 mm" in warnings[0]
    # a wider tolerance snaps it to the nearest hole
    conflicts, warnings = run(tmp_path, footprint("J1", 10, 11.27, [("1", 0, 0, "SDA")]), tolerance=1.5)
    assert warnings == []


def test_rail_conflict_fails(tmp_path):
    conflicts, warnings = run(tmp_path,
                              footprint("U1", 10, 2, [("1", 0, 0, "+5V")]),
                              footprint("U2", 12.54, 2, [("1", 0, 0, "GND")]))
    assert warnings == []
    assert len(conflicts) == 1 and "strip rail" in conflicts[0]


def test_unconnected_pads_are_distinct_nets(tmp_path):
    conflicts, _ = run(tmp_path, footprint("U1", 10, 10, [("1", 0, 0, None), ("2", 0, 2.54, None)]))
    assert len(conflicts) == 1


def test_board_footprint_is_skipped(tmp_path):
    conflicts, warnings = run(tmp_path,
                              footprint("PCB1", 0, 0, [("1", 10, 10, "A")], lib="filament-kit:ElectroCookie_Full"),
                              footprint("J1", 10, 12.54, [("1", 0, 0, "B")]))
    assert (conflicts, warnings) == ([], [])


def test_main_exit_codes(tmp_path, capsys):
    bad = pcb(tmp_path, footprint("J1", 10, 10, [("1", 0, 0, "A")]),
              footprint("J2", 10, 12.54, [("1", 0, 0, "B")]))
    assert sc.main(["--board", str(BOARD), str(bad)]) == 1
    assert "strip 1-FJ" in capsys.readouterr().out
    good = pcb(tmp_path, footprint("J1", 10, 10, [("1", 0, 0, "A")]))
    assert sc.main(["--board", str(BOARD), str(good)]) == 0
    assert sc.main(["--board", str(BOARD), str(tmp_path / "missing.kicad_pcb")]) == 2


def test_real_board_model():
    holes = sc.load_board(sc.BOARD_XML)
    assert len(holes) == 424
    assert len({h.strip for h in holes}) == 66
    by_id = {h.id: h for h in holes}
    assert by_id["F1"].strip == "1-FJ" and by_id["E1"].strip == "1-AE"
    assert (by_id["F1"].x, by_id["F1"].y) == (7.67, 22.19)
    assert by_id["A30"].x == pytest.approx(81.33)
