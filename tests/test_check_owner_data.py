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


def make_type3_pdf(path, shown, cmap, glued_streams=False):
    """A PDF like KiCad's: Type3 glyph codes drawn from a page content stream, text only in the ToUnicode CMap."""
    objs = {
        1: b"<< /Type /Pages /Kids [2 0 R] /Count 1 >>",
        2: b"<< /Type /Page /Parent 1 0 R /Resources << /Font 3 0 R >> /Contents 4 0 R >>",
        3: b"<< /F1 5 0 R /F2 7 0 R >>",
        5: b"<< /Type /Font /Subtype /Type3 /ToUnicode 6 0 R >>",
        7: b"<< /Type /Font /Subtype /Type3 >>",
    }
    streams = {4: shown, 6: cmap}
    body = b"%PDF-1.5\n"
    for n in sorted(set(objs) | set(streams)):
        if n in streams:
            data = zlib.compress(streams[n])
            body += f"{n} 0 obj\n<< /Filter /FlateDecode >>\nstream\n".encode() + data
            body += b"endstream\nendobj\n" if glued_streams else b"\nendstream\nendobj\n"
        else:
            body += f"{n} 0 obj\n".encode() + objs[n] + b"\nendobj\n"
    path.write_bytes(body + b"%%EOF\n")
    return path


CMAP = (b"1 begincodespacerange <00> <FF> endcodespacerange\n"
        b"2 beginbfchar <01> <007A> <02> <0071> endbfchar\n"      # z q
        b"1 beginbfrange <03> <05> <0061> endbfrange\n")           # a b c
SHOWN = b"BT /F1 9 Tf (\001\001\002\003) Tj ET BT /F1 9 Tf [(\004) -20 <05>] TJ ET"  # zzqabc


def test_type3_drawn_text_is_found_through_tounicode(tmp_path):
    p = make_type3_pdf(tmp_path / "k.pdf", SHOWN, CMAP)
    assert b"zzqabc" not in zlib.decompress(p.read_bytes().split(b"stream\n")[1].split(b"\nendstream")[0])
    out = cod.scan_file(p, "k.pdf", ["zzqabc"])
    assert len(out) == 1 and out[0].startswith("k.pdf!text4:") and "owner term #1" in out[0]
    assert cod.scan_file(p, "k.pdf", ["zzqabd"]) == []


def test_drawn_text_email_is_found(tmp_path):
    cmap = b"1 begincodespacerange <00> <FF> endcodespacerange\n2 beginbfchar <01> <0040> <02> <0061> <03> <002E> endbfchar\n"
    p = make_type3_pdf(tmp_path / "k.pdf", b"BT /F1 9 Tf (\002\001\002\003\002) Tj ET", cmap)
    assert any("email address" in f for f in cod.scan_file(p, "k.pdf", []))


def test_term_split_over_two_fonts_is_found(tmp_path):
    shown = b"BT /F1 9 Tf (\001) Tj ET BT /F1 9 Tf (\002) Tj ET"
    p = make_type3_pdf(tmp_path / "k.pdf", shown, CMAP)
    assert cod.pdf_text(p.read_bytes()) == [("text4", ["zq"])]
    shown = b"BT /F1 9 Tf (\001) Tj ET BT /F2 9 Tf (\002) Tj ET BT /F1 9 Tf (\003) Tj ET"  # F2 has no map
    assert cod.pdf_text(make_type3_pdf(tmp_path / "k2.pdf", shown, CMAP).read_bytes()) == [("text4", ["z", "a"])]
    out = cod.scan_file(make_type3_pdf(tmp_path / "k3.pdf", b"BT /F1 9 Tf (\001) Tj ET BT /F1 9 Tf (\002) Tj ET"
                                       b" BT /F2 9 Tf (\003) Tj ET", CMAP), "k3.pdf", ["zq"])
    assert out == ["k3.pdf!text4:1: owner term #1"]


def test_unmapped_glyph_pdf_without_term_passes(tmp_path):
    p = make_type3_pdf(tmp_path / "k.pdf", SHOWN, CMAP)
    assert cod.scan_file(p, "k.pdf", []) == []


def test_stream_without_newline_before_endstream_does_not_swallow_the_next(tmp_path):
    p = make_type3_pdf(tmp_path / "k.pdf", SHOWN, CMAP, glued_streams=True)
    data = p.read_bytes()
    assert len(cod.PDF_STREAM.findall(data)) == 2
    assert len(cod.scan_file(p, "k.pdf", ["zzqabc"])) == 1


def test_bans_file_from_environment_is_used(tmp_path, monkeypatch, capsys):
    bans = tmp_path / "bans.txt"
    bans.write_text("# c\nzzqterm\n", encoding="utf-8")
    (tmp_path / "f.txt").write_text("made by ZZQTerm", encoding="utf-8")
    monkeypatch.setattr(cod, "ROOT", tmp_path)
    monkeypatch.setattr(cod, "TERMS", tmp_path / "no-terms-file")
    monkeypatch.setattr(cod, "tracked", lambda: [tmp_path / "f.txt"])
    monkeypatch.delenv("FK_OWNER_BANS", raising=False)
    assert cod.main() == 0
    monkeypatch.setenv("FK_OWNER_BANS", str(bans))
    assert cod.main() == 1
    assert "f.txt:1: owner term #1" in capsys.readouterr().out


def test_json_bans_file_plain_lists_are_read(tmp_path):
    bans = tmp_path / "bans.json"
    bans.write_text('{"plain": ["zzqone"], "code_plain": ["zzqtwo"], "fingerprints": ["0123456789abcdef"], "salt": "x"}',
                    encoding="utf-8")
    assert cod.read_terms(bans) == ["zzqone", "zzqtwo"]


def test_require_owner_bans(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cod, "ROOT", tmp_path)
    monkeypatch.setattr(cod, "TERMS", tmp_path / "no-terms-file")
    monkeypatch.setattr(cod, "tracked", lambda: [])
    monkeypatch.delenv("FK_OWNER_BANS", raising=False)
    monkeypatch.setenv("FK_REQUIRE_OWNER_BANS", "1")
    assert cod.main() == 2
    assert "FK_REQUIRE_OWNER_BANS" in capsys.readouterr().err
    (tmp_path / "t").write_text("zzqterm\n", encoding="utf-8")
    monkeypatch.setenv("FK_OWNER_BANS", str(tmp_path / "t"))
    assert cod.main() == 0
    monkeypatch.delenv("FK_REQUIRE_OWNER_BANS")
    monkeypatch.delenv("FK_OWNER_BANS")
    assert cod.main() == 0  # without the variables a missing terms file is only a note


def run_main(tmp_path, monkeypatch, bans=None, require=False, local=None):
    monkeypatch.setattr(cod, "ROOT", tmp_path)
    monkeypatch.setattr(cod, "TERMS", tmp_path / "local-terms")
    monkeypatch.setattr(cod, "tracked", lambda: [])
    monkeypatch.delenv("FK_OWNER_BANS", raising=False)
    monkeypatch.delenv("FK_REQUIRE_OWNER_BANS", raising=False)
    if local is not None:
        (tmp_path / "local-terms").write_bytes(local)
    if bans is not None:
        monkeypatch.setenv("FK_OWNER_BANS", str(bans))
    if require:
        monkeypatch.setenv("FK_REQUIRE_OWNER_BANS", "1")
    return cod.main()


def test_named_bans_file_missing_is_an_error(tmp_path, monkeypatch, capsys):
    gone = tmp_path / "gone.txt"
    assert run_main(tmp_path, monkeypatch, bans=gone, local=b"zzqlocal\n") == 2
    err = capsys.readouterr().err
    assert str(gone) in err and "does not exist" in err and "zzqlocal" not in err


@pytest.mark.parametrize("content,reason", [
    (b"{ zzqsecret", "not valid JSON"),
    (b'{"plain": "zzqsecret"}', "expected lists"),
    (b"\xff\xfe\x00zzqsecret", "UTF-8"),
    (b"", "no terms"),
    (b"# only a comment\n\n", "no terms"),
    (b'{"plain": [], "salt": "zzqsecret"}', "no terms"),
])
def test_named_bans_file_unusable_is_an_error(tmp_path, monkeypatch, capsys, content, reason):
    bans = tmp_path / "bans"
    bans.write_bytes(content)
    assert run_main(tmp_path, monkeypatch, bans=bans) == 2
    err = capsys.readouterr().err
    assert str(bans) in err and reason in err and "zzqsecret" not in err


def test_named_bans_directory_is_an_error(tmp_path, monkeypatch, capsys):
    assert run_main(tmp_path, monkeypatch, bans=tmp_path) == 2
    assert "cannot be read" in capsys.readouterr().err


def test_require_with_empty_or_broken_local_file_is_an_error(tmp_path, monkeypatch, capsys):
    assert run_main(tmp_path, monkeypatch, require=True, local=b"") == 2
    assert run_main(tmp_path, monkeypatch, require=True, local=b"{ zzqsecret") == 2
    assert run_main(tmp_path, monkeypatch, local=b"{ zzqsecret") == 2  # a present local file must parse
    assert "zzqsecret" not in capsys.readouterr().err
    assert run_main(tmp_path, monkeypatch, require=True, local=b"zzqlocal\n") == 0


def test_require_checks_the_named_file_not_the_local_one(tmp_path, monkeypatch, capsys):
    gone = tmp_path / "gone.txt"
    assert run_main(tmp_path, monkeypatch, bans=gone, require=True, local=b"zzqlocal\n") == 2
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    assert run_main(tmp_path, monkeypatch, bans=empty, require=True, local=b"zzqlocal\n") == 2


def test_neither_variable_and_no_local_file_is_only_a_note(tmp_path, monkeypatch, capsys):
    assert run_main(tmp_path, monkeypatch) == 0
    assert "note:" in capsys.readouterr().err


def test_term_split_across_tj_elements_in_font_without_tounicode_is_found(tmp_path):
    shown = b"BT /F2 9 Tf [(zzqf) -250 (ir) 30 (st)] TJ ET"
    p = make_type3_pdf(tmp_path / "k.pdf", shown, CMAP)
    assert cod.pdf_text(p.read_bytes()) == [("text4", ["zzqfirst"])]
    out = cod.scan_file(p, "k.pdf", ["zzqfirst"])
    assert len(out) == 1 and out[0].startswith("k.pdf!text4:") and "owner term #1" in out[0]


def test_two_word_term_drawn_as_positioned_tj_without_space_is_found(tmp_path):
    shown = b"BT /F2 9 Tf (ZZQFirst) Tj 1 0 0 1 90 20 Tm (Last) Tj ET"
    p = make_type3_pdf(tmp_path / "k.pdf", shown, CMAP)
    assert cod.scan_file(p, "k.pdf", ["zzqfirst last"]) == ["k.pdf!text4:joined: owner term #1"]
    assert cod.scan_file(p, "k.pdf", ["zzqfirst other"]) == []
