import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import strip_check as sc  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "strips"
BOARD = FIXTURES / "board.xml"


def footprint(ref, x, y, pads, rot=None, lib="Test:Part", board_pads=None):
    """A footprint block; pads are (number, dx, dy, net or None)."""
    at = f"{x} {y}" + (f" {rot}" if rot is not None else "")
    out = [f'\t(footprint "{lib}"\n\t\t(layer "F.Cu")\n\t\t(at {at})\n'
           f'\t\t(property "Reference" "{ref}"\n\t\t\t(at 0 0 0)\n\t\t)']
    if board_pads is not None:
        out.append(f'\t\t(property "Board_pads" "{board_pads}"\n\t\t\t(at 0 0 0)\n\t\t)')
    for number, dx, dy, net in pads:
        netpart = f'\n\t\t\t(net "{net}")' if net else ""
        out.append(f'\t\t(pad "{number}" thru_hole circle\n\t\t\t(at {dx} {dy})'
                   f'\n\t\t\t(size 1.6 1.6){netpart}\n\t\t)')
    return "\n".join(out) + "\n\t)\n"


def pcb(tmp_path, *footprints):
    path = tmp_path / "t.kicad_pcb"
    path.write_text('(kicad_pcb\n\t(version 20260101)\n' + "".join(footprints) + ")\n", encoding="utf-8")
    return path


def run(tmp_path, *footprints, tolerance=0.5, max_distance=1.6):
    holes = sc.load_board(BOARD)
    return sc.check_pads(sc.read_pads(pcb(tmp_path, *footprints)), holes, tolerance, max_distance)


def test_two_nets_in_one_strip_fail(tmp_path):
    conflicts, warnings, errors = run(tmp_path,
                              footprint("J1", 10, 10, [("1", 0, 0, "SDA")]),
                              footprint("J2", 10, 12.54, [("1", 0, 0, "BUZZER")]))
    assert warnings == []
    assert len(conflicts) == 1
    assert "strip 1-FJ" in conflicts[0] and "SDA (J1.1)" in conflicts[0] and "BUZZER (J2.1)" in conflicts[0]


def test_same_net_in_one_strip_passes(tmp_path):
    conflicts, warnings, errors = run(tmp_path,
                              footprint("J1", 10, 10, [("1", 0, 0, "GND")]),
                              footprint("J2", 10, 12.54, [("1", 0, 0, "GND")]))
    assert (conflicts, warnings, errors) == ([], [], [])


def test_rotated_footprint(tmp_path):
    # Pad 2 sits 2.54 mm to the right of pad 1 unrotated. Turned 90 degrees counter-clockwise on
    # screen (angle 90 in KiCad, y down) it lands 2.54 mm above, so it moves from strip 2-FJ to
    # the hole above F1, which does not exist here; at 270 it lands on G1 (strip 1-FJ) with pad 1.
    pads = [("1", 0, 0, "A"), ("2", 2.54, 0, "B")]
    ok, w, _ = run(tmp_path, footprint("U1", 10, 10, pads))
    assert ok == [] and w == []
    conflicts, warnings, errors = run(tmp_path, footprint("U1", 10, 10, pads, rot=270))
    assert len(conflicts) == 1 and "strip 1-FJ" in conflicts[0]
    conflicts, warnings, errors = run(tmp_path, footprint("U1", 10, 10, pads, rot=90))
    # 2.54 mm from the nearest hole (F1): assigned there anyway, and an error
    assert len(errors) == 1 and "U1.2" in errors[0]
    assert len(conflicts) == 1


def test_off_grid_pad_warns_only(tmp_path):
    conflicts, warnings, errors = run(tmp_path, footprint("J1", 10, 11.27, [("1", 0, 0, "SDA")]))
    assert conflicts == []
    assert len(warnings) == 1
    assert "off-grid" in warnings[0] and "J1.1" in warnings[0] and "1.27 mm" in warnings[0]
    # a wider tolerance silences the warning
    conflicts, warnings, errors = run(tmp_path, footprint("J1", 10, 11.27, [("1", 0, 0, "SDA")]), tolerance=1.5)
    assert warnings == []


def test_bent_pad_still_assigned_and_conflicts(tmp_path):
    # 1.0 mm off hole F1 (toward G1 by 1.0, so 1.0 from F1 and 1.54 from G1): assigned to F1.
    conflicts, warnings, errors = run(tmp_path,
                                      footprint("J1", 10, 10, [("1", 0, 0, "SDA")]),
                                      footprint("J2", 11, 10, [("1", 0, 0, "BUZZER")]))
    assert errors == []
    assert len(conflicts) == 1 and "strip 1-FJ" in conflicts[0] and "J2.1" in conflicts[0]
    assert len(warnings) == 1 and "J2.1" in warnings[0] and "1.00 mm" in warnings[0]


def test_pad_with_no_hole_near_is_error(tmp_path, capsys):
    conflicts, warnings, errors = run(tmp_path, footprint("J1", 10, 15.5, [("1", 0, 0, "SDA")]))
    assert len(errors) == 1 and "no hole near enough" in errors[0] and "J1.1" in errors[0]
    path = pcb(tmp_path, footprint("J1", 10, 15.5, [("1", 0, 0, "SDA")]))
    assert sc.main(["--board", str(BOARD), str(path)]) == 1


def test_rail_conflict_fails(tmp_path):
    conflicts, warnings, errors = run(tmp_path,
                              footprint("U1", 10, 2, [("1", 0, 0, "+5V")]),
                              footprint("U2", 12.54, 2, [("1", 0, 0, "GND")]))
    assert warnings == []
    assert len(conflicts) == 1 and "strip rail" in conflicts[0]


def test_unconnected_pads_are_distinct_nets(tmp_path):
    conflicts, _, _ = run(tmp_path, footprint("U1", 10, 10, [("1", 0, 0, None), ("2", 0, 2.54, None)]))
    assert len(conflicts) == 1


def test_board_footprint_is_skipped(tmp_path):
    conflicts, warnings, errors = run(tmp_path,
                              footprint("PCB1", 0, 0, [("1", 10, 10, "A")], lib="filament-kit:ElectroCookie_Full"),
                              footprint("J1", 10, 12.54, [("1", 0, 0, "B")]))
    assert (conflicts, warnings, errors) == ([], [], [])


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


def _module_pads():
    # pads 8 and 9 sit 15 mm from any hole
    return [(str(n), 0, 0, "A") for n in range(1, 8)] + [("8", 0, 20, "B"), ("9", 2.54, 20, "C")]


def test_board_pads_ignores_unlisted_pads(tmp_path):
    holes = sc.load_board(BOARD)
    fp = footprint("U2", 10, 10, _module_pads(), board_pads="1-7,1")
    # pad 8 and 9 would be errors without the field
    _, _, errors = run(tmp_path, footprint("U2", 10, 10, _module_pads()))
    assert len(errors) == 2
    assert run(tmp_path, fp) == ([], [], [])


def test_board_pads_malformed_is_error(tmp_path, capsys):
    for bad in ("1-", "a", "7-3", ""):
        path = pcb(tmp_path, footprint("U2", 10, 10, _module_pads(), board_pads=bad))
        with pytest.raises(sc.StripError, match="U2"):
            sc.read_pads(path)
        assert sc.main(["--board", str(BOARD), str(path)]) == 2
    assert "malformed Board_pads" in capsys.readouterr().err


def test_board_pads_missing_pad_is_error(tmp_path, capsys):
    path = pcb(tmp_path, footprint("U2", 10, 10, _module_pads(), board_pads="1-7,10"))
    assert sc.main(["--board", str(BOARD), str(path)]) == 2
    assert "U2" in capsys.readouterr().err
