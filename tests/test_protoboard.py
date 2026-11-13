import math
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


LEADS_NETS = {"GND": [("J1", "1")], "3V3": [("J1", "2")], "SDA": [("J1", "3")], "SCL": [("J1", "4")],
              "N": [("R1", "1")], "M": [("R1", "2")]}
LEADS = '''<protoboard device="t" hand="power-left" title="T">
  <part ref="R1" kind="resistor" value="1k"><pin n="1" hole="C10"/><pin n="2" hole="C14"/></part>
  <part ref="J1" kind="leads" label="OLED">
    <pin n="1" hole="B28"/><pin n="2" hole="T+9"/><pin n="3" hole="J28"/><pin n="4" hole="I3"/>
  </part>
</protoboard>
'''


def test_leads_on_scattered_holes_including_a_rail_pass(tmp_path, capsys):
    code, out = check_text(tmp_path, LEADS, LEADS_NETS, capsys)
    assert code == 0, out
    assert "OK board.xml: 2 parts" in out


def test_lead_under_the_c3_is_refused(tmp_path, capsys):
    u1 = c3("IE", 25)
    pins = "".join(f'<pin n="{n}" hole="{h}"/>' for n, h in u1.pins.items())
    nets = dict(LEADS_NETS, **{f"P{n}": [("U1", n)] for n in u1.pins})
    c3_xml = f'  <part ref="U1" kind="c3-supermini" value="C3" hand="power-left">{pins}</part>\n'
    ok = LEADS.replace("</protoboard>", c3_xml + "</protoboard>")
    code, out = check_text(tmp_path, ok, nets, capsys)
    assert code == 0, out
    code, out = check_text(tmp_path, ok.replace("J28", "G21"), nets, capsys)
    assert code == 1
    assert "J1 pin 3: hole G21 is under U1's raised board" in out


def test_two_leads_in_one_hole_are_refused(tmp_path, capsys):
    code, out = check_text(tmp_path, LEADS.replace('hole="I3"', 'hole="B28"'), LEADS_NETS, capsys)
    assert code == 1
    assert "hole B28: used twice" in out


def test_leads_need_a_label(tmp_path, capsys):
    code, out = check_text(tmp_path, LEADS.replace(' label="OLED"', ""), LEADS_NETS, capsys)
    assert code == 1
    assert "J1: a leads part needs label" in out


def test_leads_render_with_label_and_come_last_in_the_steps(tmp_path, capsys):
    code, out = check_text(tmp_path, LEADS, LEADS_NETS, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    nets = pb.load_netlist(tmp_path / "net.xml")
    for solder in (False, True):
        assert "OLED SDA" in pb.render_sheet(pl, nets, solder)
    md = pb.steps_markdown(pl, nets)
    lines = [ln for ln in md.splitlines() if ln[:2].isdigit() or ln[:1].isdigit()]
    steps = [ln for ln in lines if ". " in ln[:4]]
    assert steps[-2].startswith("2. OLED wires (J1): GND in B28, 3V3 in top + rail at number 9, SDA in J28, "
                                "SCL in I3. Solder each wire from the top, then tie the bundle to the board edge.")
    assert steps[-1].startswith("3. Check with a meter")
    assert "| 2 | J1 OLED wires | GND B28, 3V3 top + rail at number 9, SDA J28, SCL I3 |" in md


ROW = LEADS.replace('hole="B28"', 'hole="J25"').replace('hole="T+9"', 'hole="J26"').replace('hole="J28"', 'hole="J27"') \
           .replace('hole="I3"', 'hole="J28"')


def test_leads_in_a_row_get_per_wire_tags_like_scattered_ones_in_the_default_style(tmp_path, capsys):
    code, out = check_text(tmp_path, ROW, LEADS_NETS, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    nets = pb.load_netlist(tmp_path / "net.xml")
    assert pb.lead_row(pl.parts[1]) is not None
    for solder in (False, True):
        svg = pb.render_sheet(pl, nets, solder)
        assert ">OLED wires<" not in svg
        assert "OLED GND" in svg and "OLED SDA" in svg
    md = pb.steps_markdown(pl, nets)
    assert ("OLED wires (J1): GND in J25, 3V3 in J26, SDA in J27, SCL in J28. Solder each wire from the top, then "
            "tie the bundle to the board edge.") in md
    assert "| J1 OLED wires | GND J25, 3V3 J26, SDA J27, SCL J28 |" in md


def test_scattered_leads_keep_per_wire_tags(tmp_path, capsys):
    code, out = check_text(tmp_path, LEADS, LEADS_NETS, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    assert pb.lead_row(pl.parts[1]) is None
    svg = pb.render_sheet(pl, pb.load_netlist(tmp_path / "net.xml"), False)
    assert "OLED SDA" in svg and ">OLED wires<" not in svg


def test_leads_in_reverse_pin_order_are_a_row_only_if_adjacent_in_order(tmp_path, capsys):
    swapped = ROW.replace('hole="J25"', 'hole="TMP"').replace('hole="J26"', 'hole="J25"').replace('hole="TMP"', 'hole="J26"')
    code, out = check_text(tmp_path, swapped, LEADS_NETS, capsys)
    assert code == 0, out
    assert pb.lead_row(pb.load_placement(tmp_path / "board.xml").parts[1]) is None


def test_lead_names_follow_name_attribute_else_net_in_drawing_and_steps(tmp_path, capsys):
    text = ROW.replace('<pin n="1" hole="J25"/>', '<pin n="1" hole="J25" name="ZQ"/>')
    code, out = check_text(tmp_path, text, LEADS_NETS, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    nets = pb.load_netlist(tmp_path / "net.xml")
    assert "ZQ in J25, 3V3 in J26, SDA in J27, SCL in J28." in pb.steps_markdown(pl, nets)
    svg = pb.render_sheet(pl, nets, False)
    assert "OLED ZQ" in svg and "OLED 3V3" in svg


def test_leads_with_a_non_numeric_pin_number_render(tmp_path, capsys):
    text = LEADS.replace('<pin n="4" hole="I3"/>', '<pin n="SH" hole="I3"/>')
    nets = dict(LEADS_NETS, SCL=[("J1", "SH")])
    code, out = check_text(tmp_path, text, nets, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    pb.render_sheet(pl, pb.load_netlist(tmp_path / "net.xml"), False)
    assert "SCL in I3" in pb.steps_markdown(pl, pb.load_netlist(tmp_path / "net.xml"))


def test_leads_steps_come_after_jst_steps(tmp_path, capsys):
    nets = dict(LEADS_NETS, **{"X": [("J9", "1")], "Y": [("J9", "2")]})
    jst = ('  <part ref="J9" kind="jst-xh" value="XH-2" label="PWR" latch="down">'
           '<pin n="1" hole="E5"/><pin n="2" hole="E6"/></part>\n')
    code, out = check_text(tmp_path, LEADS.replace("</protoboard>", jst + "</protoboard>"), nets, capsys)
    assert code == 0, out
    pl = pb.load_placement(tmp_path / "board.xml")
    steps, _ = pb.build_steps(pl, pb.load_netlist(tmp_path / "net.xml"))
    texts = [s[1] for s in steps]
    assert next(i for i, t in enumerate(texts) if t.startswith("J9 ")) < next(
        i for i, t in enumerate(texts) if t.startswith("OLED wires"))


def test_lead_under_a_module_board_is_refused(tmp_path, capsys):
    nets = dict(MODULE_NETS, **{"A": [("U9", "1"), ("R1", "1")], "W": [("J1", "1")]})
    text = MODULE.replace("</protoboard>", '  <part ref="J1" kind="leads" label="OLED"><pin n="1" hole="G20"/>'
                          '</part>\n</protoboard>')
    code, out = check_text(tmp_path, text.replace("G20", "H11"), nets, capsys)
    assert code == 1
    assert "J1 pin 1: hole H11 is under U9's raised board" in out


def test_leads_on_two_different_rails_are_not_a_row():
    two = pb.Part(ref="J1", kind="leads", value="", pins={"1": "T-10", "2": "T+10"})
    one = pb.Part(ref="J1", kind="leads", value="", pins={"1": "T+10", "2": "T+11"})
    assert pb.lead_row(two) is None
    assert pb.lead_row(one) is not None


CALLOUTS_NETS = dict(MODULE_NETS, P=[("C9", "1")], N=[("C9", "2")], W1=[("J1", "1")], W2=[("J1", "2")],
                     W3=[("J1", "3")], W4=[("J1", "4")])
CALLOUTS = '''<protoboard style="callouts" device="t" hand="power-left" title="T">
  <offboard ref="LS9">speaker</offboard>
  <part ref="U9" kind="module" value="AMP" label="amplifier" extends="up" terminal="SPEAKER">
    <pin n="1" hole="G10" name="X"/><pin n="2" hole="G11" name="Y"/><pin n="3" hole="G12" name="Z"/>
    <pin n="4" on="module" at="2.54,12.7" name="+"/>
  </part>
  <part ref="R1" kind="resistor" value="1k"><pin n="1" hole="C10"/><pin n="2" hole="C14"/></part>
  <part ref="C9" kind="cap-radial" value="470 uF" d="8" dnp="the supply sags">
    <pin n="1" hole="B+20"/><pin n="2" hole="B-20"/></part>
  <part ref="J1" kind="leads" label="OLED">
    <pin n="1" hole="J25"/><pin n="2" hole="J26"/><pin n="3" hole="J27"/><pin n="4" hole="J28"/>
  </part>
  <wire net="A" from="F10" to="E10"/>
  <wire net="B" from="F11" to="D14" route="channel" y="26"/>
</protoboard>
'''


def callouts_board(tmp_path, capsys, text=CALLOUTS):
    code, out = check_text(tmp_path, text, CALLOUTS_NETS, capsys)
    assert code == 0, out
    return pb.load_placement(tmp_path / "board.xml"), pb.load_netlist(tmp_path / "net.xml")


def test_an_unknown_style_is_refused(tmp_path, capsys):
    p = tmp_path / "board.xml"
    p.write_text(CALLOUTS.replace('style="callouts"', 'style="bold"'), encoding="utf-8")
    with pytest.raises(pb.PlacementError, match="style must be labels or callouts, got 'bold'"):
        pb.load_placement(p)
    assert pb.main(["check", str(p), "--netlist", str(netlist(tmp_path, CALLOUTS_NETS))]) == 2
    assert "style must be labels or callouts" in capsys.readouterr().err


def test_style_labels_is_the_default_style(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys, CALLOUTS.replace('style="callouts" ', ""))
    assert pl.style == "labels"
    explicit, _ = callouts_board(tmp_path, capsys, CALLOUTS.replace("callouts", "labels"))
    for solder in (False, True):
        assert pb.render_sheet(pl, nets, solder) == pb.render_sheet(explicit, nets, solder)
    assert pb.steps_markdown(pl, nets) == pb.steps_markdown(explicit, nets)


STEP_BADGE = 'r="1.05" fill="#111" stroke="#fff"'
NET_TAG = 'rx="0.5" fill="#ffffff" stroke='


def test_callouts_render_has_no_step_badges_and_no_wire_tags(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    default = callouts_board(tmp_path, capsys, CALLOUTS.replace('style="callouts" ', ""))[0]
    for solder in (False, True):
        svg = pb.render_sheet(pl, nets, solder)
        assert STEP_BADGE not in svg and NET_TAG not in svg
        assert "build step" not in svg and "each wire end is labelled" not in svg
        base_svg = pb.render_sheet(default, nets, solder)
        assert NET_TAG in base_svg                                  # the patterns do match the default style
        assert (STEP_BADGE in base_svg) == (not solder)
    # The names are off the board; what shows how to fit a part stays.
    top = pb.render_sheet(pl, nets, False)
    assert ">flat<" not in top and "SPEAKER" in top and ">X<" in top


def callout_centres(svg):
    import re
    out = {}
    for cls, body in re.findall(r'<g class="(callout-(?:part|lead))" data-no="\d+">(.*?)</g>', svg):
        no = int(re.search(r'>(\d+)</text>', body).group(1))
        m = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)"', body)
        if m:
            c = (float(m.group(1)), float(m.group(2)))
        else:
            m = re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', body)
            c = (float(m.group(1)) + float(m.group(3)) / 2, float(m.group(2)) + float(m.group(4)) / 2)
        out[no] = (cls, c)
    return out


def test_callouts_one_per_part_and_per_lead_with_unique_numbers(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    parts_no, leads_no = pb.callout_numbers(pl)
    # Build order: resistor, capacitor, module; then the device's wires in pin order.
    assert parts_no == {"R1": 1, "C9": 2, "U9": 3}
    assert leads_no == {("J1", "1"): 4, ("J1", "2"): 5, ("J1", "3"): 6, ("J1", "4"): 7}
    for solder in (False, True):
        found = callout_centres(pb.render_sheet(pl, nets, solder))
        assert sorted(found) == [1, 2, 3, 4, 5, 6, 7]
        assert [found[n][0] for n in sorted(found)] == ["callout-part"] * 3 + ["callout-lead"] * 4


def test_callouts_cover_no_hole_in_use_and_no_other_callout(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    lead_holes = {h for p in pl.parts if p.kind == "leads" for h in p.pins.values()}
    for solder in (False, True):
        v = pb.View(solder, True)
        found = callout_centres(pb.render_sheet(pl, nets, solder))
        for no, (_, c) in found.items():
            for h in pb.used_holes(pl):
                reach = pb.CALLOUT_R + (pb.LEAD_RING_R if h in lead_holes else 0.78)
                assert math.dist(c, v.p((pb.HOLES[h].x, pb.HOLES[h].y))) >= reach, (no, h, solder)
            for other, (_, d) in found.items():
                assert other == no or math.dist(c, d) >= 2 * pb.CALLOUT_R, (no, other, solder)


def test_callouts_legend_lists_every_part_and_device_wire(tmp_path, capsys):
    import re
    pl, nets = callouts_board(tmp_path, capsys)
    for solder in (False, True):
        svg = pb.render_sheet(pl, nets, solder)
        texts = re.findall(r"<text[^>]*>([^<]*)</text>", svg)
        for ref in ("R1", "C9", "U9"):
            assert any(t.startswith(f"{ref} ") for t in texts), ref
        assert "Parts" in texts and "Device wires" in texts and "OLED" in texts
        assert not any("J1" in t for t in texts)
        assert any(t.startswith("C9 470 uF") for t in texts) and "fit only if the supply sags" in " ".join(texts)
        assert [t for t in texts if t.startswith(("W1: ", "W2: ", "W3: ", "W4: "))] == \
            ["W1: J25", "W2: J26", "W3: J27", "W4: J28"]
        for n in range(1, 8):
            assert str(n) in texts
        assert "a part on the board (see Parts)" in texts


def test_callouts_row_of_leads_gets_a_thin_outline_only_in_callouts_style(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    assert pb.lead_row(pl.parts[3]) is not None
    default = callouts_board(tmp_path, capsys, CALLOUTS.replace('style="callouts" ', ""))[0]
    outline = 'rx="1.0" fill="none" stroke="#333" stroke-width="0.3"'
    assert pb.render_sheet(pl, nets, False).count(outline) == 1
    assert outline not in pb.render_sheet(default, nets, False)


def test_callouts_steps_are_unnumbered_and_start_with_the_callout_numbers(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    md = pb.steps_markdown(pl, nets)
    lines = md.splitlines()
    assert "Build order" in lines[0] and not any(ln[:2].isdigit() for ln in lines if not ln.startswith("|"))
    bullets = [ln for ln in lines[2:] if ln.startswith("- ")]
    assert bullets[0].startswith("- Wire B: F11 to D14") and bullets[1].startswith("- Wire A: F10 to E10")
    assert "- Part 1, R1 (1k): C10 to C14, lying flat." in bullets
    assert "- Part 3, U9 socket: a 1x3 female header in G10-G12." in " ".join(bullets)
    assert ("- Device wires 4-7, OLED: 4 W1 in J25, 5 W2 in J26, 6 W3 in J27, 7 W4 in J28. Solder each wire "
            "from the top, then tie the bundle to the board edge.") in bullets
    assert next(i for i, ln in enumerate(bullets) if "Part 3" in ln) < next(i for i, ln in enumerate(bullets)
                                                                           if "Device wires" in ln)
    assert "- Part 2, C9 (470 uF)" in md and "fit it only if the supply sags" in md
    assert "| No. | Item | Holes |" in md and "| Step |" not in md
    assert "|  | wire A | F10 to E10 |" in md
    assert "| 1 | R1 1k | C10 to C14 |" in md
    assert "| 2 | C9 470 uF (fit only if needed) |" in md
    assert "| 4-7 | OLED wires | 4 W1 J25, 5 W2 J26, 6 W3 J27, 7 W4 J28 |" in md


def wire_check(tmp_path, lane, capsys):
    text = ('<protoboard device="t" hand="none" title="T">\n'
            f'  <wire net="A" from="F2" to="E4" route="channel" y="{lane}"/>\n</protoboard>\n')
    return check_text(tmp_path, text, {"A": [("X1", "1")]}, capsys)[1]


def test_a_wire_keeps_3_5_mm_from_an_m3_hole_centre(tmp_path, capsys):
    # The run down from F2 to a lane at y=24 passes 3.17 mm from the M3 hole at (7.75, 26): under the screw head.
    screw = "runs over an M3 mounting hole's screw head"
    assert screw in wire_check(tmp_path, 24.0, capsys)
    assert screw not in wire_check(tmp_path, 23.4, capsys)          # 3.58 mm


def u1_text(hand: str) -> str:
    pins = "".join(f'<pin n="{n}" hole="{h}"/>' for n, h in c3(("I", "E"), 25).pins.items())
    return (f'<protoboard device="t" hand="{hand}" title="T">\n'
            f'  <part ref="U1" kind="c3-supermini" value="C3" hand="power-left">{pins}</part>\n</protoboard>\n')


def test_the_placement_hand_must_match_u1s_hand(tmp_path, capsys):
    out = check_text(tmp_path, u1_text("power-right"), U1_NETS, capsys)[1]
    assert "U1: its hand is 'power-left' but the placement's hand is 'power-right'" in out
    assert "its hand is" not in check_text(tmp_path, u1_text("power-left"), U1_NETS, capsys)[1]


U1_NETS = {f"P{i}": [("U1", str(i))] for i in range(1, 17)}
RING = 'r="1.05" fill="none" stroke="#ffffff"'


def late_board(tmp_path, capsys, extra: str, holes: list, nets: dict, style='style="callouts" '):
    """U1 on rows I and E, `extra` placement text, and a device J1 with its wires in `holes`."""
    pins = "".join(f'<pin n="{n}" hole="{h}"/>' for n, h in c3(("I", "E"), 25).pins.items())
    j1 = "".join(f'<pin n="{i}" hole="{h}"/>' for i, h in enumerate(holes, 1))
    text = (f'<protoboard {style}device="t" hand="power-left" title="T">\n'
            f'  <part ref="U1" kind="c3-supermini" value="C3" hand="power-left">{pins}</part>\n{extra}'
            f'  <part ref="J1" kind="leads" label="OLED">{j1}</part>\n</protoboard>\n')
    code, out = check_text(tmp_path, text, dict(U1_NETS, **nets), capsys)
    assert code == 0, out
    return pb.load_placement(tmp_path / "board.xml"), pb.load_netlist(tmp_path / "net.xml")


def test_callouts_draw_u1s_pin_names_after_the_lead_rings_and_keep_callouts_off_them(tmp_path, capsys):
    # The J row lies right beside the names of U1's I-row pins.
    # Each lead shares its strip with the I-row pin 9-12 below it, so it takes that pin's net.
    nets = {f"P{8 + i}": [("U1", str(8 + i)), ("J1", str(i))] for i in range(1, 5)}
    args = (tmp_path, capsys, "", ["J25", "J24", "J23", "J22"], nets)
    pl, nets_ = late_board(*args)
    top = pb.render_sheet(pl, nets_, False)
    assert top.rindex(RING) < top.index('fill="#eaf1f8"')
    names = pb.Svg()
    pb.draw_late_names(names, pb.View(False, True), pl, {})
    assert len(names.keep) == 16
    for no, (_, c) in callout_centres(top).items():
        for x0, y0, x1, y1 in names.keep:
            assert not (x0 - pb.CALLOUT_R < c[0] < x1 + pb.CALLOUT_R and y0 - pb.CALLOUT_R < c[1] < y1 + pb.CALLOUT_R), no
    # The labels style keeps its order: the names go down with U1, the leads' tags come after.
    pl, nets_ = late_board(*args, style="")
    labels = pb.render_sheet(pl, nets_, False)
    assert labels.index('fill="#eaf1f8"') < labels.index('r="1.3" fill="none" stroke="#ffffff"')
    assert labels.count('fill="#eaf1f8"') == 16


def test_callouts_draw_the_to92_letters_last_on_a_dark_pill(tmp_path, capsys):
    q1 = ('  <part ref="Q1" kind="to92" value="2N7000" flat="down">'
          '<pin n="1" hole="F2"/><pin n="2" hole="F3"/><pin n="3" hole="F4"/></part>\n')
    nets = {"D": [("Q1", "1"), ("J1", "1")], "G": [("Q1", "2"), ("J1", "2")], "S": [("Q1", "3"), ("J1", "3")],
            "W4": [("J1", "4")]}
    args = (tmp_path, capsys, q1, ["G2", "G3", "G4", "G5"], nets)
    pl, nets_ = late_board(*args)         # the lead rings lie on the letters
    top = pb.render_sheet(pl, nets_, False)
    pill = 'fill="#3a3a3a" stroke="#ffffff"'
    assert top.count(pill) == 3
    assert top.index(pill) > top.rindex(RING)
    pl, nets_ = late_board(*args, style="")
    assert pill not in pb.render_sheet(pl, nets_, False)


def test_a_callout_with_no_room_is_a_message_not_a_traceback(tmp_path, capsys, monkeypatch):
    callouts_board(tmp_path, capsys)

    def no_room(*a, **k):
        raise pb.PlacementError("no room for the callout of R1")
    monkeypatch.setattr(pb, "draw_callouts", no_room)
    code = pb.main(["render", str(tmp_path / "board.xml"), "--netlist", str(tmp_path / "net.xml")])
    assert code == 1 and "no room for the callout of R1" in capsys.readouterr().err


def test_callouts_name_a_device_by_its_label_alone(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    assert "J1" not in pb.steps_markdown(pl, nets)
    labels, _ = callouts_board(tmp_path, capsys, CALLOUTS.replace('style="callouts" ', ""))
    assert "OLED wires (J1)" in pb.steps_markdown(labels, nets)


def test_callouts_draw_a_plug_in_modules_pin_names_after_the_rings_and_keep_callouts_off_them(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    top = pb.render_sheet(pl, nets, False)
    assert top.index('fill="#f1eaf7"') > top.rindex(RING)
    assert top.count('fill="#f1eaf7"') == 3
    names = pb.Svg()
    pb.draw_late_names(names, pb.View(False, True), pl, {})
    assert len(names.keep) == 6                  # each name's text and its backing
    for no, (_, c) in callout_centres(top).items():
        assert not any(pb._shape_hits_rect(c, _.endswith("lead"), b, 0) for b in names.keep), no
    pl, nets = callouts_board(tmp_path, capsys, CALLOUTS.replace('style="callouts" ', ""))
    labels = pb.render_sheet(pl, nets, False)
    assert labels.index('fill="#f1eaf7"') < labels.index('r="1.3" fill="none" stroke="#ffffff"')


def test_callout_shapes_are_tested_by_their_real_outline():
    box = (10.0, 10.0, 14.0, 11.0)
    assert pb._shape_hits_rect((15.2, 12.2), True, box, 0.1) and not pb._shape_hits_rect((15.2, 12.2), False, box, 0.1)
    assert pb._shape_hits_rect((10.5, 12.3), True, box, 0.1) and not pb._shape_hits_rect((10.5, 12.5), True, box, 0.1)
    assert pb._seg_hits_rect((0, 10.5), (20, 10.5), box, 0) and not pb._seg_hits_rect((0, 9), (20, 9), box, 0.5)
    assert pb._callouts_touch((0, 0), True, (2.5, 2.5), True, 0.0)          # two squares overlap at a diagonal
    assert not pb._callouts_touch((0, 0), False, (2.5, 2.5), False, 0.0)    # two circles do not
    assert pb._callouts_touch((0, 0), True, (2.8, 0), False, 0.3) and not pb._callouts_touch((0, 0), True, (3.0, 0), False, 0.3)


def test_a_leader_keeps_off_protected_texts_other_callouts_and_other_leaders(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    space = pb._CalloutSpace(pb.Svg(), pb.View(False, True), pl)
    a, b = (60.0, 60.0), (70.0, 60.0)
    assert space.leader_cost(a, b) == 0.0
    space.keep.append((64.0, 59.0, 65.0, 61.0))
    assert space.leader_cost(a, b) is None
    space.keep.clear()
    space.placed.append(((65.0, 61.0), True))
    assert space.leader_cost(a, b) is None
    space.placed.clear()
    space.leaders.append(((65.0, 55.0), (65.0, 65.0)))
    assert space.leader_cost(a, b) is None


def test_a_callout_nearer_another_ring_is_refused_while_a_better_spot_exists(tmp_path, capsys):
    pl, nets = callouts_board(tmp_path, capsys)
    v = pb.View(False, True)
    space = pb._CalloutSpace(pb.Svg(), v, pl)
    key = ("J1", "1")
    ring = space.rings[key]
    for strict in (True, False):
        for _, c, end in pb._candidates(space, key, [], False, ring, 9, strict):
            d = math.dist(c, ring)
            near = any(math.dist(c, q) < d + 0.1 for k, q in space.rings.items() if k != key)
            assert strict is False or not near


def test_a_callout_with_no_room_names_the_device_and_wire(tmp_path, capsys, monkeypatch):
    pl, nets = callouts_board(tmp_path, capsys)
    asked = []
    real = pb._place_callout

    def spy(space, key, polys, on_body, ring=None, name=None):
        asked.append(name)
        return real(space, key, polys, on_body, ring, name)
    monkeypatch.setattr(pb, "_place_callout", spy)
    pb.render_sheet(pl, nets, False)
    assert "OLED W1 at J25" in asked and "R1" in asked
    space = pb._CalloutSpace(pb.Svg(), pb.View(False, True), pl)
    space.bounds = (0, 0, 1, 1)
    with pytest.raises(pb.PlacementError, match=r"no room for the callout of OLED W1 at J25$"):
        real(space, ("J1", "1"), [], False, space.rings[("J1", "1")], "OLED W1 at J25")


RAILS = '''<protoboard style="callouts" device="t" hand="none" title="T">
  <part ref="J1" kind="leads" label="PWR"><pin n="1" hole="J5"/><pin n="2" hole="J6"/></part>
  <wire net="A" from="J5" to="T+8"/>
  <wire net="B" from="J6" to="B+8"/>
  <wire net="B" from="I6" to="B-8"/>
</protoboard>
'''
RAILS_NETS = {"A": [("J1", "1")], "B": [("J1", "2")]}
LEAVE = "Leave the + rail link pads beside the left M3 hole open: the top + rail is A and the bottom + rail is B."


def rails_render(tmp_path, text):
    p = tmp_path / "rails.xml"
    p.write_text(text, encoding="utf-8")
    pl = pb.load_placement(p)
    return (pb.steps_markdown(pl, RAILS_NETS), pb.render_sheet(pl, RAILS_NETS, False),
            pb.render_sheet(pl, RAILS_NETS, True))


def test_a_rail_whose_halves_carry_different_nets_gets_leave_open_steps_and_mark(tmp_path):
    md, top, solder = rails_render(tmp_path, RAILS)
    assert LEAVE in md and "Joining them would short A to B." in md
    assert "- Leave the + rail" in md and "Leave the − rail" not in md     # the - rail has only one half in use
    for svg in (top, solder):
        assert svg.count("leave open") == 2        # the mark beside the board and the legend key
    labels = RAILS.replace('style="callouts" ', "")
    md, top, solder = rails_render(tmp_path, labels)
    assert f"1. {LEAVE}" not in md and LEAVE in md       # the steps line is part of the check step
    assert "leave open" not in top and "leave open" not in solder


def test_a_bridged_rail_or_one_unused_half_gets_no_leave_open(tmp_path):
    for text in (RAILS.replace("</protoboard>", '  <bridge rail="+"/>\n</protoboard>'),
                 RAILS.replace('  <wire net="B" from="J6" to="B+8"/>\n', "")):
        md, top, solder = rails_render(tmp_path, text)
        assert "Leave the" not in md
        assert "leave open" not in top and "leave open" not in solder


RAILS_MINUS = RAILS.replace("T+8", "T-8").replace("B+8", "B-8").replace(' <wire net="B" from="I6" to="B-8"/>', ' <wire net="B" from="I6" to="B-9"/>')
BOTH = RAILS.replace("</protoboard>", '  <wire net="C" from="J7" to="T-8"/>\n  <wire net="D" from="J8" to="B-8"/>\n</protoboard>'
                     ).replace('<pin n="2" hole="J6"/>', '<pin n="2" hole="J6"/><pin n="3" hole="J7"/><pin n="4" hole="J8"/>'
                               ).replace('  <wire net="B" from="I6" to="B-8"/>\n', "")


def open_marks(svg):
    """(x of the text, anchor) for each "leave open" text beside the board, not the legend key."""
    import re
    return [(float(m.group(1)), m.group(2)) for m in
            re.finditer(r'<text x="([\d.]+)" y="[\d.]+" font-size="1.20" text-anchor="(\w+)"[^>]*>leave open<', svg)]


def test_the_leave_open_mark_sits_at_the_pads_of_its_rail(tmp_path):
    nets = {"A": [("J1", "1")], "B": [("J1", "2")], "C": [("J1", "3")], "D": [("J1", "4")]}
    for text, want in ((RAILS, ["end"]), (RAILS_MINUS, ["start"]), (BOTH, ["end", "start"])):
        p = tmp_path / "r.xml"
        p.write_text(text, encoding="utf-8")
        pl = pb.load_placement(p)
        n = nets if text is BOTH else RAILS_NETS
        for solder in (False, True):
            svg = pb.render_sheet(pl, n, solder)
            marks = open_marks(svg)
            assert len(marks) == len(want), (text, solder, marks)
            assert len({m[0] for m in marks}) == len(marks)
            assert sorted(m[1] for m in marks) == sorted(want if not solder else [{"end": "start", "start": "end"}[a] for a in want])
            assert "different nets" in svg and "different supplies" not in svg
        md = pb.steps_markdown(pl, n)
        assert "no short from A to B" in md
        assert ("no short from C to D" in md) == (text is BOTH)
