import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import protoboard as pb  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "protoboard"
NET = FIX / "net.xml"


def run_check(tmp_path, text: str, capsys):
    p = tmp_path / "board.xml"
    p.write_text(text, encoding="utf-8")
    code = pb.main(["check", str(p), "--netlist", str(NET)])
    return code, capsys.readouterr().out


def base() -> str:
    return (FIX / "board.xml").read_text(encoding="utf-8")


def test_matching_board_passes(tmp_path, capsys):
    code, out = run_check(tmp_path, base(), capsys)
    assert code == 0, out
    assert "OK board.xml: 3 parts, 1 wires" in out


def test_missing_link_fails(tmp_path, capsys):
    text = base().replace('  <wire net="GND" from="D13" to="D6"/>\n', "")
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert "open: net GND is split into 2 groups" in out


def test_wrong_net_link_fails(tmp_path, capsys):
    # The GND wire lands on strip 9 (net B) instead of strip 6.
    text = base().replace('to="D6"', 'to="D9"')
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert "short: nets B, GND are joined on the board" in out
    assert "open: net GND" in out


def test_rail_half_without_its_link_fails(tmp_path, capsys):
    # GND strip 6 goes to the bottom - rail and GND strip 13 to the top - rail: the halves only join
    # through the - link beside the right M3 hole.
    rails = ('  <wire net="GND" from="A6" to="B-6"/>\n'
             '  <wire net="GND" from="E13" to="T-13"/>\n')
    text = base().replace('  <wire net="GND" from="D13" to="D6"/>\n', rails)
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert "open: net GND is split into 2 groups" in out
    linked = text.replace("</protoboard>", '  <bridge rail="-"/>\n</protoboard>')
    code, out = run_check(tmp_path, linked, capsys)
    assert code == 0, out


def test_wire_labelled_with_the_wrong_net_fails(tmp_path, capsys):
    text = base().replace('net="GND"', 'net="A"')
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert "labelled A but carries GND" in out


def test_hole_used_twice_fails(tmp_path, capsys):
    text = base().replace('from="D13"', 'from="A13"')
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert "hole A13: used twice" in out


def test_part_not_placed_fails(tmp_path, capsys):
    start = base().index('  <part ref="R2"')
    end = base().index("</part>", start) + len("</part>\n")
    text = base()[:start] + base()[end:]
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert "R2: in the netlist but neither placed nor listed as <offboard>" in out


def c3(rows: tuple[str, str], usb_col_end: int) -> pb.Part:
    """A power-left C3 with USB toward the column-30 end: power row in row rows[0]."""
    pins = {}
    for pad, (_, side, i) in pb.C3_POWER_LEFT.items():
        pins[pad] = f"{rows[0] if side == 'L' else rows[1]}{usb_col_end - i}"
    return pb.Part("U1", "c3-supermini", "", pins, {"hand": "power-left"})


def test_c3_power_left_accepted_and_mirror_rejected():
    pb.module_frame(c3(("I", "E"), 25))          # USB right, power row on top: correct
    with pytest.raises(pb.PlacementError, match="mirrored"):
        pb.module_frame(c3(("E", "I"), 25))      # power row on the bottom with USB right: the other hand


def test_render_writes_sized_svg_and_steps():
    pl = pb.load_placement(FIX / "board.xml")
    nets = pb.load_netlist(NET)
    top = pb.render_sheet(pl, nets, False)
    solder = pb.render_sheet(pl, nets, True)
    assert top.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="128.0mm"')
    assert "SOLDER SIDE (mirrored)" in solder and "SOLDER SIDE" not in top
    md = pb.steps_markdown(pl)
    assert "| 1 | wire GND | D13 to D6 |" in md
    assert "R1 1k" in md
