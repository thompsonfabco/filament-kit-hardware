import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import paper_check as pc  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tree(tmp_path):
    """A writable copy of the fixture devices and kit: returns (devices_root, kit)."""
    shutil.copytree(FIXTURES / "devices", tmp_path / "devices")
    shutil.copytree(FIXTURES / "kit", tmp_path / "kit")
    return tmp_path / "devices", tmp_path / "kit"


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def dev(tree):
    return tree[0] / "demo-panel"


def test_clean_device_passes(tree):
    assert pc.check_device(dev(tree), tree[1]) == []


def test_pin_missing_in_firmware_reported(tree):
    edit(dev(tree) / "catalogue.xml", "</pins>",
         '<pin gpio="7" constant="PIN_GHOST" role="x"/></pins>')
    problems = pc.check_device(dev(tree), tree[1])
    assert any(p.startswith("demo-panel") and "PIN_GHOST" in p for p in problems)


def test_firmware_pin_missing_in_catalogue_reported(tree):
    edit(dev(tree) / "catalogue.xml", '<pin gpio="0" constant="PIN_BUZZER" role="buzzer"/>', "")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("PIN_BUZZER" in p for p in problems)


def test_gpio_mismatch_reported(tree):
    edit(dev(tree) / "catalogue.xml", 'gpio="5"', 'gpio="4"')
    problems = pc.check_device(dev(tree), tree[1])
    assert any("PIN_SDA" in p and "4" in p and "5" in p for p in problems)


@pytest.mark.parametrize("gpio", [2, 8, 9, 18, 19])
def test_strapping_pin_rejected(tree, gpio):
    edit(dev(tree) / "catalogue.xml", 'gpio="5"', f'gpio="{gpio}"')
    edit(tree[1] / "station/panel/src/main.cpp", "PIN_SDA = 5", f"PIN_SDA = {gpio}")
    edit(dev(tree) / "guide.md", "| PIN_SDA | 5 |", f"| PIN_SDA | {gpio} |")
    problems = pc.check_device(dev(tree), tree[1])
    assert any(f"GPIO {gpio}" in p and "reserved" in p for p in problems)


def test_duplicate_gpio_rejected(tree):
    edit(dev(tree) / "catalogue.xml", 'gpio="6"', 'gpio="5"')
    problems = pc.check_device(dev(tree), tree[1])
    assert any("duplicate" in p and "5" in p for p in problems)


def test_hello_name_must_appear_in_source(tree):
    edit(tree[1] / "station/panel/src/main.cpp", "HELLO demo-panel", "HELLO other-panel")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("HELLO demo-panel" in p for p in problems)


def test_chip_token_must_appear_in_source(tree):
    edit(tree[1] / "station/panel/src/main.cpp", "esp32c3", "esp32s3")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("esp32c3" in p for p in problems)


def test_chip_token_not_required_without_hello(tree):
    edit(dev(tree) / "catalogue.xml", ' hello="demo-panel"', "")
    edit(tree[1] / "station/panel/src/main.cpp", "esp32c3", "esp32s3")
    problems = pc.check_device(dev(tree), tree[1])
    assert not any("chip token" in p for p in problems)


@pytest.mark.parametrize("attr", ["vmax", "imax", "datasheet"])
def test_active_part_needs_vmax_imax_datasheet(tree, attr):
    text = (dev(tree) / "catalogue.xml").read_text(encoding="utf-8")
    import re
    text = re.sub(rf' {attr}="[^"]*"', "", text)
    (dev(tree) / "catalogue.xml").write_text(text, encoding="utf-8")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("Q1" in p and attr in p for p in problems)


def test_guide_table_mismatch_reported(tree):
    edit(dev(tree) / "guide.md", "| PIN_SCL | 6 |", "| PIN_SCL | 7 |")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("guide" in p and "PIN_SCL" in p for p in problems)


def test_guide_pins_matches_columns_by_header(tmp_path):
    g = tmp_path / "g.md"
    g.write_text("| Wire | C3 GPIO | Constant |\n|---|---|---|\n| a | 3 | PIN_A |\n| b | x | PIN_B |\n",
                 encoding="utf-8")
    assert pc.guide_pins(g) == {"PIN_A": 3}


def test_firmware_pins_accepts_define_and_int(tmp_path):
    f = tmp_path / "m.cpp"
    f.write_text("static const int PIN_A = 3;\n#define PIN_B 4\nstatic const gpio_num_t PIN_C=5;\n",
                 encoding="utf-8")
    assert pc.firmware_pins(f) == {"PIN_A": 3, "PIN_B": 4, "PIN_C": 5}


def test_bought_device_needs_no_kit():
    assert pc.check_device(FIXTURES / "devices" / "bought-sensor", None) == []


def test_malformed_xml_reported_and_others_still_checked(tree, capsys):
    bad = tree[0] / "broken"
    bad.mkdir()
    (bad / "catalogue.xml").write_text("<device id='broken'", encoding="utf-8")
    edit(dev(tree) / "catalogue.xml", 'gpio="5"', 'gpio="4"')
    code = pc.main(["--kit", str(tree[1]), "--devices", str(tree[0])])
    out = capsys.readouterr().out
    assert code == 1
    assert "broken" in out
    assert "demo-panel" in out and "PIN_SDA" in out


def test_main_clean_exits_0(tree):
    assert pc.main(["--kit", str(tree[1]), "--devices", str(tree[0])]) == 0


def test_missing_kit_path_exits_2(tree, tmp_path):
    assert pc.main(["--kit", str(tmp_path / "nope"), "--devices", str(tree[0])]) == 2


def test_kit_device_without_kit_exits_2(tree):
    assert pc.main(["--devices", str(tree[0])]) == 2


def test_hello_in_a_comment_does_not_count(tree):
    src = tree[1] / "station/panel/src/main.cpp"
    src.write_text('// "HELLO demo-panel <version> esp32c3"\n'
                   + src.read_text(encoding="utf-8").replace("HELLO demo-panel", "HELLO other-panel"),
                   encoding="utf-8")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("HELLO demo-panel" in p for p in problems)


def test_chip_in_a_comment_does_not_count(tree):
    src = tree[1] / "station/panel/src/main.cpp"
    src.write_text('/* "HELLO demo-panel <version> esp32c3" */\n'
                   + src.read_text(encoding="utf-8").replace("esp32c3", "esp32s3"),
                   encoding="utf-8")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("esp32c3" in p for p in problems)


def test_commented_out_pin_does_not_count(tree):
    src = tree[1] / "station/panel/src/main.cpp"
    src.write_text("// static const uint8_t PIN_OLD = 9;\n/* #define PIN_OLD2 8 */\n"
                   + src.read_text(encoding="utf-8"), encoding="utf-8")
    assert pc.check_device(dev(tree), tree[1]) == []


def test_missing_guide_reported(tree):
    (dev(tree) / "guide.md").unlink()
    assert "demo-panel: no guide.md" in pc.check_device(dev(tree), tree[1])


def test_bought_device_missing_guide_reported(tree):
    (tree[0] / "bought-sensor" / "guide.md").unlink()
    assert "bought-sensor: no guide.md" in pc.check_device(tree[0] / "bought-sensor", None)


def test_guide_pins_without_catalogue_pins_reported(tree):
    (tree[0] / "bought-sensor" / "guide.md").write_text(
        "| Constant | C3 GPIO |\n|---|---|\n| PIN_X | 3 |\n", encoding="utf-8")
    problems = pc.check_device(tree[0] / "bought-sensor", None)
    assert any("PIN_X" in p and "guide" in p for p in problems)


def test_missing_devices_folder_exits_2(tmp_path, capsys):
    assert pc.main(["--devices", str(tmp_path / "none")]) == 2
    assert "not found" in capsys.readouterr().err


# --- KiCad netlist path -------------------------------------------------------------------------

@pytest.fixture
def ktree(tmp_path):
    """A device with a KiCad project and a canned netlist: returns (device_dir, kit, export)."""
    shutil.copytree(FIXTURES / "kicad" / "demo-panel", tmp_path / "demo-panel")
    shutil.copytree(FIXTURES / "kit", tmp_path / "kit")
    netlist = tmp_path / "canned.xml"
    shutil.copy(FIXTURES / "kicad" / "netlist.xml", netlist)

    def export(sch, out):
        shutil.copy(netlist, out)
    export.netlist = netlist
    return tmp_path / "demo-panel", tmp_path / "kit", export


def kcheck(ktree):
    return pc.check_device(ktree[0], ktree[1], export=ktree[2])


def test_netlist_matching_is_clean(ktree):
    assert kcheck(ktree) == []


def test_netlist_catalogue_pin_gpio_mismatch_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'gpio="5"', 'gpio="4"')
    problems = kcheck(ktree)
    assert any("PIN_SDA" in p and "catalogue" in p and "4" in p and "5" in p for p in problems)


def test_netlist_catalogue_part_imax_mismatch_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'imax="1.0"', 'imax="2.0"')
    assert any("U1" in p and "imax" in p and "2.0" in p for p in kcheck(ktree))


def test_netlist_active_part_missing_ratings_in_catalogue_reported(ktree):
    edit(ktree[0] / "catalogue.xml", ' imax="1.0"', "")
    assert any("U1" in p and "catalogue lacks imax" in p for p in kcheck(ktree))


def test_usb_serial_firmware_needs_hello(tree):
    edit(dev(tree) / "catalogue.xml", ' hello="demo-panel"', "")
    problems = pc.check_device(dev(tree), tree[1])
    assert any("usb-serial" in p and "HELLO rule" in p for p in problems)


def test_renamed_gpio_net_reported(ktree):
    edit(ktree[2].netlist, 'name="/SDA"', 'name="/SDA_RENAMED"')
    problems = kcheck(ktree)
    assert any("PIN_SDA_RENAMED" in p and "firmware" in p for p in problems)
    assert any("PIN_SDA" in p and "guide" in p for p in problems)


def test_net_on_wrong_gpio_reported(ktree):
    edit(ktree[2].netlist, "GPIO5_1", "GPIO4_1")
    problems = kcheck(ktree)
    assert any("PIN_SDA" in p and "4" in p and "5" in p for p in problems)


@pytest.mark.parametrize("gpio", [2, 8, 9, 18, 19])
def test_netlist_strapping_pin_rejected(ktree, gpio):
    edit(ktree[2].netlist, "GPIO5_1", f"GPIO{gpio}_1")
    edit(ktree[1] / "station/panel/src/main.cpp", "PIN_SDA = 5", f"PIN_SDA = {gpio}")
    edit(ktree[0] / "guide.md", "| PIN_SDA | 5 |", f"| PIN_SDA | {gpio} |")
    problems = kcheck(ktree)
    assert any(f"GPIO {gpio}" in p and "reserved" in p for p in problems)


def test_unconnected_strapping_pin_is_fine(ktree):
    assert "GPIO2_14" in ktree[2].netlist.read_text(encoding="utf-8")
    assert not any("reserved" in p for p in kcheck(ktree))


@pytest.mark.parametrize("attr", ["Vmax", "Imax", "Datasheet"])
def test_netlist_active_part_needs_vmax_imax_datasheet(ktree, attr):
    import re
    text = ktree[2].netlist.read_text(encoding="utf-8")
    text = re.sub(rf'<field name="{attr}">[^<]*</field>\s*', "", text, count=2)
    if attr == "Datasheet":
        text = re.sub(r"<datasheet>[^<]*</datasheet>", "<datasheet/>", text)
    ktree[2].netlist.write_text(text, encoding="utf-8")
    problems = kcheck(ktree)
    assert any("Q1" in p and attr.lower() in p for p in problems)


def test_netlist_guide_mismatch_reported(ktree):
    edit(ktree[0] / "guide.md", "| PIN_SCL | 6 |", "| PIN_SCL | 7 |")
    assert any("guide" in p and "PIN_SCL" in p for p in kcheck(ktree))


def test_netlist_passive_part_needs_no_ratings(ktree):
    assert not any("R1" in p for p in kcheck(ktree))


def test_unreadable_netlist_reported(ktree):
    ktree[2].netlist.write_text("<export", encoding="utf-8")
    assert any("netlist" in p for p in kcheck(ktree))


def test_main_without_kicad_cli_exits_2(ktree, monkeypatch, capsys):
    monkeypatch.delenv("KICAD_CLI", raising=False)
    monkeypatch.setattr(pc.shutil, "which", lambda name: None)
    code = pc.main(["--kit", str(ktree[1]), "--devices", str(ktree[0].parent)])
    assert code == 2
    assert "kicad-cli" in capsys.readouterr().err


def test_netlist_tilde_datasheet_counts_as_missing(ktree):
    edit(ktree[2].netlist, "<datasheet>https://example.com/bs170.pdf</datasheet>", "<datasheet>~</datasheet>")
    assert any("Q1" in p and "datasheet" in p for p in kcheck(ktree))


def test_netlist_unconfirmed_values_are_allowed(ktree):
    edit(ktree[2].netlist, '<field name="Imax">0.5</field>', '<field name="Imax">UNCONFIRMED</field>')
    edit(ktree[0] / "catalogue.xml", 'vmax="60" imax="0.5"', 'vmax="60" imax="UNCONFIRMED"')
    assert kcheck(ktree) == []


@pytest.mark.parametrize("ref", ["A1", "PS1", "DS1", "K1", "IC1"])
def test_netlist_more_active_prefixes_need_ratings(ktree, ref):
    edit(ktree[2].netlist, "</components>", f'<comp ref="{ref}"><value>x</value></comp></components>')
    problems = kcheck(ktree)
    assert {a for a in ("vmax", "imax", "datasheet") if f"{ref} lacks {a}" in " ".join(problems)} ==         {"vmax", "imax", "datasheet"}


def test_netlist_part_with_vmax_is_active(ktree):
    edit(ktree[2].netlist, "</components>",
         '<comp ref="X1"><value>x</value><fields><field name="Vmax">5</field></fields></comp></components>')
    problems = kcheck(ktree)
    assert any("X1 lacks imax" in p for p in problems)
    assert any("X1 lacks datasheet" in p for p in problems)


def test_only_the_root_sheet_is_exported(ktree):
    seen = []

    def export(sch, out):
        seen.append(sch.name)
        shutil.copy(ktree[2].netlist, out)

    assert pc.check_device(ktree[0], ktree[1], export=export) == []
    assert seen == ["demo-panel.kicad_sch"]
    assert [s.name for s in pc.kicad_projects(ktree[0])] == ["demo-panel.kicad_sch"]


def test_bad_kicad_cli_path_exits_2(ktree, monkeypatch, capsys):
    monkeypatch.setenv("KICAD_CLI", str(ktree[1] / "nope" / "kicad-cli"))
    code = pc.main(["--kit", str(ktree[1]), "--devices", str(ktree[0].parent)])
    assert code == 2
    assert "KICAD_CLI" in capsys.readouterr().err


def test_netlist_part_kind_flip_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'name="10k" kind="passive"', 'name="10k" kind="active"')
    edit(ktree[0] / "catalogue.xml", 'name="BS170" kind="active"', 'name="BS170" kind="passive"')
    problems = kcheck(ktree)
    assert any("R1" in p and "active in the catalogue but passive" in p for p in problems)
    assert any("Q1" in p and "passive in the catalogue but active" in p for p in problems)


def test_catalogue_only_active_part_reported(ktree):
    edit(ktree[0] / "catalogue.xml", '    <part ref="R1"',
         '    <part ref="U9" name="ghost" kind="active" qty="1" use="none"/>\n    <part ref="R1"')
    problems = kcheck(ktree)
    assert any("U9" in p and "not in the schematic" in p for p in problems)
    assert any("U9" in p and "lacks vmax" in p for p in problems)


def test_catalogue_active_range_ref_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'ref="R1"', 'ref="R1-R2"')
    assert kcheck(ktree) == []
    edit(ktree[0] / "catalogue.xml", 'name="10k" kind="passive"', 'name="10k" kind="active"')
    assert any("R1-R2" in p and "not in the schematic" in p for p in kcheck(ktree))


def test_duplicate_catalogue_ref_reported(ktree):
    edit(ktree[0] / "catalogue.xml", '    <part ref="R1"',
         '    <part ref="Q1" name="bogus" kind="passive" qty="1" use="none"/>\n    <part ref="R1"')
    assert any("duplicate part ref Q1" in p for p in kcheck(ktree))


def test_duplicate_catalogue_ref_reported_without_schematic(tree):
    path = dev(tree) / "catalogue.xml"
    text = path.read_text()
    i = text.index("<part ")
    j = text.index("/>", i) + 2
    path.write_text(text[:j] + text[i:j] + text[j:])
    assert any("duplicate part ref" in p for p in pc.check_device(dev(tree), tree[1]))


def test_schematic_only_active_part_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'ref="Q1"', 'ref="Q1X"')
    assert any("Q1" in p and "in the schematic but not in the catalogue" in p for p in kcheck(ktree))


def test_schematic_active_part_renamed_in_case_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'ref="Q1" name="BS170" kind="active"', 'ref="q1" name="BS170" kind="passive"')
    assert any("Q1" in p and "in the schematic but not in the catalogue" in p for p in kcheck(ktree))


def test_schematic_active_part_in_passive_range_reported(ktree):
    edit(ktree[0] / "catalogue.xml", 'ref="Q1" name="BS170" kind="active"', 'ref="Q1-Q2" name="BS170" kind="passive"')
    assert any("Q1" in p and "in the schematic but not in the catalogue" in p for p in kcheck(ktree))


def test_duplicate_catalogue_ref_ignores_case(ktree):
    edit(ktree[0] / "catalogue.xml", '    <part ref="R1"',
         '    <part ref="q1" name="bogus" kind="passive" qty="1" use="none"/>\n    <part ref="R1"')
    assert any("duplicate part ref" in p and "q1" in p for p in kcheck(ktree))


@pytest.mark.parametrize("kind", ["Active", "ACTIVE", "", "other"])
def test_catalogue_kind_must_be_active_or_passive(ktree, kind):
    edit(ktree[0] / "catalogue.xml", 'name="10k" kind="passive"', f'name="10k" kind="{kind}"')
    assert any("R1" in p and "must be exactly active or passive" in p for p in kcheck(ktree))


@pytest.mark.parametrize("attr", ["vmax", "imax", "datasheet"])
def test_catalogue_passive_part_must_not_carry_ratings(ktree, attr):
    edit(ktree[0] / "catalogue.xml", 'name="10k" kind="passive"', f'name="10k" kind="passive" {attr}="9"')
    assert any("passive part R1 carries " + attr in p for p in kcheck(ktree))


def test_catalogue_kind_checked_without_schematic(tree):
    path = dev(tree) / "catalogue.xml"
    text = path.read_text()
    i = text.index('kind="')
    j = text.index('"', i + 6)
    path.write_text(text[:i] + 'kind="Active' + text[j:])
    assert any("must be exactly active or passive" in p for p in pc.check_device(dev(tree), tree[1]))
