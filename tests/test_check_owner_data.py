import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import check_owner_data as cod  # noqa: E402

EMAIL = "person@" + "mail.test"


def make_zip(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


def test_email_inside_fcstd_document_xml_is_found(tmp_path):
    xml = f'<Property name="CreatedBy"><String value="Some One &lt;{EMAIL.replace("@", "&#64;")}&gt;"/></Property>'
    p = make_zip(tmp_path / "part.FCStd", {"Document.xml": xml})
    out = cod.scan_file(p, "part.FCStd", [])
    assert len(out) == 1
    assert out[0].startswith("part.FCStd!Document.xml:1: email address: ") and EMAIL in out[0]


def test_owner_term_inside_3mf_is_found(tmp_path):
    terms = tmp_path / "terms"
    terms.write_text("# c\nzzqterm\n", encoding="utf-8")
    p = make_zip(tmp_path / "m.3mf", {"3D/3dmodel.model": '<model>\n<metadata name="Designer">ZZQTerm</metadata></model>'})
    words = cod.read_terms(terms)
    out = cod.scan_file(p, "m.3mf", words)
    assert out == ["m.3mf!3D/3dmodel.model:2: owner term #1"]


def test_binary_member_is_skipped(tmp_path):
    p = make_zip(tmp_path / "a.zip", {"thumb.png": b"\x00\x01 " + EMAIL.encode()})
    assert cod.scan_file(p, "a.zip", []) == []


def test_corrupt_archive_is_reported(tmp_path):
    p = tmp_path / "a.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_STORED) as z:
        z.writestr("x.txt", "hello hello hello")
    data = bytearray(p.read_bytes())
    data[data.index(b"hello") + 1] ^= 0xFF  # flip a stored byte so the CRC no longer matches
    p.write_bytes(bytes(data))
    assert cod.scan_file(p, "a.zip", []) == ["a.zip: cannot read archive"]


def test_clean_archive_passes(tmp_path):
    p = make_zip(tmp_path / "a.3mf", {"3D/3dmodel.model": '<model><metadata name="Title">Bracket</metadata></model>'})
    assert cod.scan_file(p, "a.3mf", []) == []


def test_entity_escaped_email_in_plain_svg_is_found(tmp_path):
    p = tmp_path / "a.svg"
    p.write_text(f"<svg><desc>x &lt;{EMAIL.replace('@', '&#64;')}&gt;</desc></svg>", encoding="utf-8")
    out = cod.scan_file(p, "a.svg", [])
    assert len(out) == 1 and "email address" in out[0]
