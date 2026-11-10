import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import netlist_parity as np_  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "parity"


def test_matching_netlists_exit_0(capsys):
    # Same connectivity; the SMT netlist differs in footprints, fields, net order and one net name.
    assert np_.main([str(FIXTURES / "tht.xml"), str(FIXTURES / "smt.xml")]) == 0
    assert "4 nets match" in capsys.readouterr().out


def test_swapped_pins_exit_1_and_listed(tmp_path, capsys):
    text = (FIXTURES / "smt.xml").read_text(encoding="utf-8")
    # Swap J1 pins 1 and 2: GND and 3V3 change places on the connector.
    text = text.replace('ref="J1" pin="2"', 'ref="J1" pin="X"').replace('ref="J1" pin="1"', 'ref="J1" pin="2"')
    text = text.replace('ref="J1" pin="X"', 'ref="J1" pin="1"')
    bad = tmp_path / "bad.xml"
    bad.write_text(text, encoding="utf-8")
    assert np_.main([str(FIXTURES / "tht.xml"), str(bad)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 4
    assert any(l.startswith(f"only in {FIXTURES / 'tht.xml'}: net /GND: J1.1 U1.10") for l in out)
    assert any(l.startswith(f"only in {bad}: net /3V3: J1.1 U1.11") for l in out)


def test_missing_file_exit_2(tmp_path):
    assert np_.main([str(FIXTURES / "tht.xml"), str(tmp_path / "none.xml")]) == 2


def test_schematic_without_kicad_cli_exit_2(tmp_path, monkeypatch, capsys):
    sch = tmp_path / "x.kicad_sch"
    sch.write_text("(kicad_sch)", encoding="utf-8")
    monkeypatch.setenv("KICAD_CLI", str(tmp_path / "no-such-kicad-cli"))
    assert np_.main([str(sch), str(FIXTURES / "tht.xml")]) == 2
    assert "kicad-cli" in capsys.readouterr().err


# Exceptions: side A has module M1 on the signal (pins 1-3); side B replaces it with chip M1 (other pin numbers)
# plus a bypass capacitor C9.
def _netlist(path, nets):
    body = "".join(
        f'    <net code="{i}" name="{name}">\n'
        + "".join(f'      <node ref="{m.split(".")[0]}" pin="{m.split(".")[1]}"/>\n' for m in members)
        + "    </net>\n"
        for i, (name, members) in enumerate(nets, 1))
    path.write_text(f'<?xml version="1.0"?>\n<export version="E">\n  <nets>\n{body}  </nets>\n</export>\n',
                    encoding="utf-8")
    return str(path)


A_NETS = [("GND", ["U1.10", "J1.1", "M1.1"]), ("3V3", ["U1.11", "J1.2", "M1.2"]), ("SIG", ["U1.16", "M1.3"]),
          ("LED", ["U1.5", "J1.3"])]
B_NETS = [("GND", ["U1.10", "J1.1", "M1.4", "M1.9", "C9.2"]), ("3V3", ["U1.11", "J1.2", "M1.7", "C9.1"]),
          ("SIG", ["U1.16", "M1.12"]), ("LED", ["U1.5", "J1.3"]), ("unconnected-(M1-NC)", ["M1.5"])]
EXC = """# module M1 on A, chip M1 and C9 on B
refs M1 C9
a U1.10 J1.1 M1.1
a U1.11 J1.2 M1.2
a U1.16 M1.3
b U1.10 J1.1 M1.4 M1.9 C9.2
b U1.11 J1.2 M1.7 C9.1
b U1.16 M1.12
b M1.5
"""


def _run(tmp_path, a_nets=A_NETS, b_nets=B_NETS, exc=EXC):
    a = _netlist(tmp_path / "a.xml", a_nets)
    b = _netlist(tmp_path / "b.xml", b_nets)
    e = tmp_path / "exc.txt"
    e.write_text(exc, encoding="utf-8")
    return np_.main([a, b, "--exceptions", str(e)])


def test_exceptions_cover_a_replaced_block_exit_0(tmp_path, capsys):
    assert _run(tmp_path) == 0
    assert "4 nets match outside the exceptions; 3 + 4 excepted nets" in capsys.readouterr().out


def test_without_exceptions_the_replaced_block_fails(tmp_path):
    a = _netlist(tmp_path / "a.xml", A_NETS)
    b = _netlist(tmp_path / "b.xml", B_NETS)
    assert np_.main([a, b]) == 1


def test_difference_outside_the_exceptions_still_fails(tmp_path, capsys):
    # B moves the LED wire to another U1 pin: no excepted ref is on that net, so it must still match.
    b_nets = [n if n[0] != "LED" else ("LED", ["U1.6", "J1.3"]) for n in B_NETS]
    assert _run(tmp_path, b_nets=b_nets) == 1
    out = capsys.readouterr().out
    assert "net LED: J1.3 U1.5" in out and "net LED: J1.3 U1.6" in out


def test_excepted_pin_on_the_wrong_net_fails(tmp_path, capsys):
    # The chip's signal pin is wired to 3V3 instead of SIG: B's excepted nets no longer match the listed ones.
    b_nets = [("GND", ["U1.10", "J1.1", "M1.4", "M1.9", "C9.2"]), ("3V3", ["U1.11", "J1.2", "M1.7", "C9.1", "M1.12"]),
              ("SIG", ["U1.16"]), ("LED", ["U1.5", "J1.3"]), ("unconnected-(M1-NC)", ["M1.5"])]
    assert _run(tmp_path, b_nets=b_nets) == 1
    out = capsys.readouterr().out
    assert "not in the exceptions file: C9.1 J1.2 M1.12 M1.7 U1.11" in out
    assert "no net in" in out and "is exactly: M1.12 U1.16" in out


def test_excepted_ref_bridging_two_outside_nets_fails(tmp_path, capsys):
    # On B, C9 joins SIG to GND. Stripping the excepted refs alone would hide that; the listed nets catch it.
    b_nets = [("GND", ["U1.10", "J1.1", "M1.4", "M1.9", "C9.2", "U1.16", "M1.12"]),
              ("3V3", ["U1.11", "J1.2", "M1.7", "C9.1"]), ("LED", ["U1.5", "J1.3"]), ("unconnected-(M1-NC)", ["M1.5"])]
    assert _run(tmp_path, b_nets=b_nets) == 1


def test_unlisted_excepted_net_fails(tmp_path, capsys):
    exc = EXC.replace("b M1.5\n", "")
    assert _run(tmp_path, exc=exc) == 1
    assert "excepted net unconnected-(M1-NC) not in the exceptions file: M1.5" in capsys.readouterr().out


def test_ref_in_neither_netlist_fails(tmp_path, capsys):
    exc = EXC.replace("refs M1 C9", "refs M1 C9 C99")
    assert _run(tmp_path, exc=exc) == 1
    assert "ref C99 is in neither netlist" in capsys.readouterr().out


def test_bad_exceptions_file_exit_2(tmp_path, capsys):
    assert _run(tmp_path, exc="refs M1\nc U1.1 M1.1\n") == 2
    assert "unknown line type 'c'" in capsys.readouterr().err
    assert _run(tmp_path, exc="refs M1\na U1-1 M1.1\n") == 2
    assert _run(tmp_path, exc="a U1.16 M1.3\n") == 2              # no refs line
    assert _run(tmp_path, exc="refs M1\na U1.5 J1.3\n") == 2      # listed net holds no excepted ref
    assert np_.main([str(FIXTURES / "tht.xml"), str(FIXTURES / "smt.xml"), "--exceptions",
                     str(tmp_path / "none.txt")]) == 2
