import sys
import zipfile
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import check_owner_data as cod  # noqa: E402

EMAIL = "person@" + "mail.test"
JUNK = b"h@" + b"D.Nx"  # bytes that look like an address


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


def test_truncated_archive_is_reported(tmp_path):
    p = make_zip(tmp_path / "a.FCStd", {"Document.xml": "<a/>" * 200, "b.txt": "x" * 500})
    full = p.read_bytes()
    for keep in (len(full) // 2, len(full) * 9 // 10):
        p.write_bytes(full[:keep])
        assert cod.scan_file(p, "a.FCStd", []) == ["a.FCStd: cannot read archive"]


def test_zero_byte_3mf_is_reported(tmp_path):
    p = tmp_path / "a.3mf"
    p.write_bytes(b"")
    assert cod.scan_file(p, "a.3mf", []) == ["a.3mf: cannot read archive"]


def test_freecad_geometry_member_is_skipped_but_document_is_scanned(tmp_path):
    p = make_zip(tmp_path / "a.FCStd", {"PartShape.Map.txt": ";:H10.6.241.248\n", "Document.xml": f"<a>{EMAIL}</a>"})
    out = cod.scan_file(p, "a.FCStd", [])
    assert len(out) == 1 and out[0].startswith("a.FCStd!Document.xml:1: email address")


def test_entity_newline_does_not_shift_line_numbers(tmp_path):
    p = tmp_path / "a.svg"
    p.write_text(f"<svg>\n<desc>&#10;&#10;{EMAIL}</desc></svg>", encoding="utf-8")
    assert cod.scan_file(p, "a.svg", [])[0].startswith("a.svg:2: email address")


def test_utf16_member_is_scanned(tmp_path):
    p = make_zip(tmp_path / "a.zip", {"m.txt": ("﻿" + EMAIL).encode("utf-16-le")})
    assert len(cod.scan_file(p, "a.zip", [])) == 1


def test_member_name_is_scanned(tmp_path):
    p = make_zip(tmp_path / "a.zip", {f"{EMAIL}.txt": "ok"})
    assert any("email address" in f for f in cod.scan_file(p, "a.zip", []))


def test_oversized_member_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(cod, "MAX_MEMBER", 10)
    p = make_zip(tmp_path / "a.zip", {"big.txt": "x" * 100})
    assert cod.scan_file(p, "a.zip", []) == ["a.zip!big.txt: skipped, too large"]


def test_encrypted_archive_is_reported(tmp_path):
    p = make_zip(tmp_path / "a.zip", {"x.txt": "secret"})
    data = bytearray(p.read_bytes())
    data[6] |= 1  # local header: encrypted flag
    data[data.index(b"PK\x01\x02") + 8] |= 1  # central directory entry
    p.write_bytes(bytes(data))
    assert cod.scan_file(p, "a.zip", []) == ["a.zip: cannot read archive"]


def test_directory_in_listed_paths_is_skipped(tmp_path, monkeypatch, capsys):
    (tmp_path / "folder").mkdir()
    monkeypatch.setattr(cod, "ROOT", tmp_path)
    monkeypatch.setattr(cod, "tracked", lambda: [tmp_path / "folder"])
    assert cod.main() == 0
    assert "0 finding(s)" in capsys.readouterr().out


def test_missing_listed_file_is_a_finding(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cod, "ROOT", tmp_path)
    monkeypatch.setattr(cod, "tracked", lambda: [tmp_path / "gone.txt"])
    assert cod.main() == 1
    assert "gone.txt: listed but missing" in capsys.readouterr().out


def test_dangling_symlink_with_user_path_is_a_finding(tmp_path, monkeypatch, capsys):
    try:
        (tmp_path / "link").symlink_to("C:/" + "Users/RealName/secret.txt")
    except (OSError, NotImplementedError):
        pytest.skip("this account cannot create symlinks on this system")
    monkeypatch.setattr(cod, "ROOT", tmp_path)
    monkeypatch.setattr(cod, "tracked", lambda: [tmp_path / "link"])
    assert cod.main() == 1
    out = capsys.readouterr().out
    assert "link:1: Windows user path" in out
    assert "link: dangling symlink" in out


def make_pdf(path, stream_text=b"", raw_stream=None):
    body = zlib.compress(stream_text) if raw_stream is None else raw_stream
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Producer (Skia/PDF) /Filter /FlateDecode >>\nstream\n" + body
                     + b"\nendstream\nendobj\ntrailer\n%%EOF\n")
    return path


def test_pdf_email_inside_compressed_stream_is_found(tmp_path):
    p = make_pdf(tmp_path / "a.pdf", b"BT (Contact " + EMAIL.encode() + b") Tj ET")
    assert EMAIL.encode() not in p.read_bytes()  # the old raw-byte scan could not see it
    out = cod.scan_file(p, "a.pdf", [])
    assert len(out) == 1 and "email address" in out[0] and EMAIL in out[0]


def test_pdf_owner_term_inside_compressed_stream_is_found(tmp_path):
    p = make_pdf(tmp_path / "a.pdf", b"BT (Made by ZZQTerm) Tj ET")
    assert cod.scan_file(p, "a.pdf", ["zzqterm"]) == ["a.pdf!stream1:1: owner term #1"]


def test_pdf_email_like_compressed_bytes_are_not_flagged(tmp_path):
    # a valid stream followed by bytes that look like an address but are not part of the inflated text
    p = make_pdf(tmp_path / "a.pdf", raw_stream=zlib.compress(b"BT (hello) Tj ET") + JUNK)
    assert JUNK in p.read_bytes()
    assert cod.scan_file(p, "a.pdf", []) == []


def test_pdf_stream_that_will_not_inflate_is_scanned_raw(tmp_path):
    p = make_pdf(tmp_path / "a.pdf", raw_stream=b"not zlib " + EMAIL.encode())
    out = cod.scan_file(p, "a.pdf", [])
    assert len(out) == 1 and out[0].startswith("a.pdf!stream1:1: email address")


def test_pdf_metadata_outside_streams_is_scanned(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4\n<< /Author (" + EMAIL.encode() + b") >>\n%%EOF\n")
    out = cod.scan_file(p, "a.pdf", [])
    assert len(out) == 1 and out[0].startswith("a.pdf:2: email address")


def test_repo_schematic_pdfs_scan_clean():
    pdfs = list(cod.ROOT.glob("devices/*/images/*.pdf"))
    assert pdfs
    for p in pdfs:
        assert cod.scan_file(p, p.name, []) == [], p
