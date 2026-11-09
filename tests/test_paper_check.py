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
