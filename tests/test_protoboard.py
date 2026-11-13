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


def test_jst_pin_1_must_match_the_latch_side(tmp_path, capsys):
    # With the latch (deep) side toward the viewer, a JST-XH header's pin 1 is on the left (KiCad footprint).
    code, out = run_check(tmp_path, base(), capsys)
    assert code == 0, out                       # latch down, pin 1 at the left (C5), pin 2 at C6
    mirrored = base().replace('latch="down"', 'latch="up"')
    code, out = run_check(tmp_path, mirrored, capsys)
    assert code == 1
    assert "J1: pin 1 is on the wrong end" in out
    swapped = base().replace('hole="C5"', 'hole="@"').replace('hole="C6"', 'hole="C5"').replace('hole="@"', 'hole="C6"')
    code, out = run_check(tmp_path, swapped, capsys)
    assert code == 1
    assert "J1: pin 1 is on the wrong end" in out


def c3_hand(hand: str, rows: tuple[str, str], usb_col_end: int) -> pb.Part:
    """A C3 with USB toward the column-30 end: power row (pads 9-16) in rows[0], GPIO row (pads 1-8) in rows[1]."""
    part = c3(rows, usb_col_end)
    part.attrs["hand"] = hand
    return part


def test_c3_power_right_accepted_and_mirror_rejected():
    # USB toward number 30 means "up" is +x; the viewer's right of that is the bottom half (rows A-E).
    pb.module_frame(c3_hand("power-right", ("E", "I"), 25))      # power row on the bottom: power-right
    with pytest.raises(pb.PlacementError, match="mirrored.*power-left module"):
        pb.module_frame(c3_hand("power-right", ("I", "E"), 25))
    with pytest.raises(pb.PlacementError, match="mirrored.*power-right module"):
        pb.module_frame(c3_hand("power-left", ("E", "I"), 25))
    with pytest.raises(pb.PlacementError, match="hand must be"):
        pb.module_frame(c3_hand("left", ("I", "E"), 25))


@pytest.mark.parametrize("hand,rows,side,other", [("power-left", ("I", "E"), "LEFT", "power-right"),
                                                  ("power-right", ("E", "I"), "RIGHT", "power-left")])
def test_sheet_texts_follow_the_hand(hand, rows, side, other):
    pl = pb.load_placement(FIX / "board.xml")
    nets = pb.load_netlist(NET)
    pl.parts = [p for p in pl.parts if p.ref != "J1"] + [c3_hand(hand, rows, 25)]
    top = pb.render_sheet(pl, nets, False)
    assert f"For a C3 {hand.upper()} module only" in top
    assert f"three pins of the {side} row. A {other} module here" in top
    assert f">{side}</text>" in top                       # the hand picture's "power on the LEFT/RIGHT"
    md = pb.steps_markdown(pl)
    assert f"after checking it is a {hand} module." in md


def test_unknown_hand_is_reported_not_raised(tmp_path, capsys):
    u1 = "".join(f'    <pin n="{n}" hole="{r}{k}"/>\n' for n, r, k in
                 [(str(i + 1), "H", 20 + i) for i in range(8)] + [(str(i + 9), "D", 20 + i) for i in range(8)])
    text = base().replace("</protoboard>", f'  <part ref="U1" kind="c3-supermini" value="C3" hand="power-up">\n{u1}'
                                           "  </part>\n</protoboard>")
    code, out = run_check(tmp_path, text, capsys)
    assert code == 1
    assert 'U1: hand must be "power-left" or "power-right"' in out


def netlist(tmp_path, nets: dict) -> Path:
    """A minimal kicadxml netlist: {net: [(ref, pin), ...]}."""
    body = "".join(f'<net name="{n}">' + "".join(f'<node ref="{r}" pin="{p}"/>' for r, p in m) + "</net>"
                   for n, m in nets.items())
    path = tmp_path / "net.xml"
    path.write_text(f"<export><nets>{body}</nets></export>", encoding="utf-8")
    return path


def check_text(tmp_path, text: str, nets: dict, capsys):
    p = tmp_path / "board.xml"
    p.write_text(text, encoding="utf-8")
    code = pb.main(["check", str(p), "--netlist", str(netlist(tmp_path, nets))])
    return code, capsys.readouterr().out


MODULE_NETS = {"A": [("U9", "1"), ("R1", "1")], "B": [("U9", "2"), ("R1", "2")], "C": [("U9", "3")],
               "SPK": [("U9", "4"), ("LS9", "1")]}
MODULE = '''<protoboard device="t" hand="power-left" title="T">
  <offboard ref="LS9">speaker</offboard>
  <part ref="U9" kind="module" value="AMP" extends="up" terminal="SPEAKER">
    <pin n="1" hole="G10" name="X"/><pin n="2" hole="G11" name="Y"/><pin n="3" hole="G12" name="Z"/>
    <pin n="4" on="module" at="2.54,12.7" name="+"/>
  </part>
  <part ref="R1" kind="resistor" value="1k"><pin n="1" hole="C10"/><pin n="2" hole="C14"/></part>
  <wire net="B" from="F11" to="D14" route="channel" y="26"/>
</protoboard>
'''


def test_module_with_a_pin_on_the_module_and_a_channel_wire(tmp_path, capsys):
    code, out = check_text(tmp_path, MODULE.replace('<wire net="B"', '<wire net="A" from="F10" to="E10"/>\n  <wire net="B"'),
                           MODULE_NETS, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    md = pb.steps_markdown(pl)
    assert "U9 socket: a 1x3 female header in G10-G12" in md
    assert "two bends, along the centre channel" in md
    top = pb.render_sheet(pl, pb.load_netlist(tmp_path / "net.xml"), False)
    assert "SPEAKER" in top and "U9 AMP" in top


def test_module_pin_on_the_module_must_be_declared(tmp_path, capsys):
    text = MODULE.replace('    <pin n="4" on="module" at="2.54,12.7" name="+"/>\n', "")
    code, out = check_text(tmp_path, text, MODULE_NETS, capsys)
    assert code == 1
    assert "U9 pin 4 (net SPK): not placed" in out


def test_no_tall_part_under_a_raised_module(tmp_path, capsys):
    nets = dict(MODULE_NETS, A=[("U9", "1"), ("R1", "1"), ("J9", "1")], C=[("U9", "3"), ("J9", "2")])
    text = MODULE.replace("</protoboard>", '  <part ref="J9" kind="jst-xh" value="XH-2" latch="down">'
                          '<pin n="1" hole="I10"/><pin n="2" hole="I12"/></part>\n</protoboard>')
    text = text.replace('hole="I12"', 'hole="I11"')
    code, out = check_text(tmp_path, text, nets, capsys)
    assert code == 1
    assert "J9: its body sits under U9's raised module board" in out


def test_channel_wire_must_run_inside_the_channel(tmp_path, capsys):
    with pytest.raises(pb.PlacementError, match="not inside the channel"):
        p = tmp_path / "b.xml"
        p.write_text(MODULE.replace('y="26"', 'y="21"'), encoding="utf-8")
        pb.load_placement(p)


CAP = '''<protoboard device="t" hand="power-left" title="T">
  <part ref="C9" kind="cap-radial" value="470 uF" d="8" dnp="the supply sags">
    <pin n="1" hole="B+15"/><pin n="2" hole="B-15"/></part>
  <part ref="R1" kind="resistor" value="1k"><pin n="1" hole="B20"/><pin n="2" hole="B-20"/></part>
</protoboard>
'''


def test_radial_capacitor_and_dnp(tmp_path, capsys):
    nets = {"P": [("C9", "1")], "N": [("C9", "2"), ("R1", "2")], "Q": [("R1", "1")]}
    code, out = check_text(tmp_path, CAP, nets, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    md = pb.steps_markdown(pl)
    assert "C9 (470 uF)" not in md.split("Parts fitted only when needed")[0]
    assert ("- C9 (470 uF), bottom + rail at number 15 and bottom − rail at number 15: fit it only if the "
            "supply sags.") in md
    top = pb.render_sheet(pl, pb.load_netlist(tmp_path / "net.xml"), False)
    assert "DNP" in top
    code, out = check_text(tmp_path, CAP.replace('hole="B-15"', 'hole="B-17"'), nets, capsys)
    assert code == 1 and "C9: put its two leads along a letter or a number" in out
