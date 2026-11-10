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
