import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import make_release as mr  # noqa: E402


@pytest.fixture
def enc(tmp_path):
    root = tmp_path / "enclosures"
    (root / "box").mkdir(parents=True)
    (root / "box" / "lid.step").write_text("lid")
    (root / "box" / "base.step").write_text("base")
    (root / "multi" / "Small Part").mkdir(parents=True)
    (root / "multi" / "Small Part" / "part one.step").write_text("p1")
    (root / "multi" / "Small Part" / "Print Plate.3mf").write_text("plate")
    (root / "LICENSE").write_text("licence text")
    return root


def names(assets):
    return sorted(a.name for a in assets)


def test_names_and_zip_contents(enc, tmp_path):
    assets = mr.build(enc, "v1.2.3", tmp_path / "out")
    assert names(assets) == [
        "box-step-v1.2.3.zip",
        "multi-small-part-step-v1.2.3.zip",
        "print-plate-v1.2.3.3mf",
    ]
    with zipfile.ZipFile(tmp_path / "out" / "box-step-v1.2.3.zip") as z:
        assert z.namelist() == ["box/LICENSE", "box/base.step", "box/lid.step"]
        assert z.read("box/LICENSE") == b"licence text"


def test_3mf_passthrough(enc, tmp_path):
    mr.build(enc, "v1", tmp_path / "out")
    assert (tmp_path / "out" / "print-plate-v1.3mf").read_bytes() == b"plate"


def test_reproducible(enc, tmp_path):
    a = mr.build(enc, "v1", tmp_path / "a")
    b = mr.build(enc, "v1", tmp_path / "b")
    for x, y in zip(a, b):
        assert x.read_bytes() == y.read_bytes()


def test_empty_device_fails(enc, tmp_path):
    (enc / "empty").mkdir()
    (enc / "empty" / "notes.txt").write_text("x")
    with pytest.raises(SystemExit, match="no STEP files"):
        mr.build(enc, "v1", tmp_path / "out")


def test_new_folder_picked_up(enc, tmp_path):
    (enc / "fresh").mkdir()
    (enc / "fresh" / "a.step").write_text("a")
    assets = mr.build(enc, "v1", tmp_path / "out")
    assert "fresh-step-v1.zip" in names(assets)
