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


# The project's public account name is allowed only inside its own github.com / ko-fi.com links. Built in two parts so
# this file does not trip the owner scan itself.
NAME = "thompson" + "fabco"
BS = chr(92)
HOST_LINKS = [f"github.com/{NAME}", f"ko-fi.com/{NAME}", f"{NAME}/filament-kit", f"{NAME}/filament-library",
              f"{NAME}/filament-kit-hardware"]


@pytest.mark.parametrize("line", [
    f"github.com/{NAME}",
    f"GitHub.com/{NAME.upper()}/Some-Repo",
    f"Ko-Fi.com/{NAME.title()}",
    f"https://github.com/{NAME}/filament-kit-hardware",
    f"https://www.github.com/{NAME}",
    f"https://ko-fi.com/{NAME}",
    f"[Support](https://ko-fi.com/{NAME})",
    f"[repo](https://github.com/{NAME}/x) and more",
    f'<a href="https://github.com/{NAME}">x</a>',
    f"see https://github.com/{NAME}.",
    f"see github.com/{NAME} now",
    f"see github.com/{NAME}\tnow",
    f"clone {NAME}/filament-kit",
    f"clone {NAME.upper()}/FILAMENT-LIBRARY please",
    f"uses {NAME}/filament-kit-hardware.",
    f'"{NAME}/filament-kit"',
    f"({NAME}/filament-kit)",
])
def test_account_name_inside_its_own_links_passes(line):
    assert cod.scan_text("f", line, [NAME]) == []


def term_hits(text, words):
    """Owner-term findings only (the generic e-mail, host and path patterns also fire on some of these lines)."""
    return [f for f in cod.scan_text("f", text, words) if "owner term" in f]


@pytest.mark.parametrize("line", [
    f"made by {NAME}",
    f"user@{NAME}.com",
    f"{NAME}.local",
    f"{NAME}.github.io",
    f"/home/{NAME}/filament-kit",
    f"C:{BS}Users{BS}{NAME}",
    f"notgithub.com/{NAME}/x",
    f"github.com.example.org/{NAME}",
    f"github.com/{NAME}-x/repo",
    f"github.com/{NAME}x",
    f"github.com/{NAME}_x",
    f"api.github.com/repos/{NAME}/x",
    f"raw.githubusercontent.com/{NAME}/x",
    f"sub.github.com/{NAME}",
    f"x-github.com/{NAME}",
    f"ko-fi.com.example.org/{NAME}",
    f"mko-fi.com/{NAME}",
    f"github.com/{NAME}/x and {NAME}",
    f"{NAME} and https://ko-fi.com/{NAME}",
    f"github.com/other/{NAME}",
    f"github.com/{NAME[:-1]}/x {NAME}",
    f"x{NAME}/filament-kit",
    f"-{NAME}/filament-kit",
    f".{NAME}/filament-kit",
    f"/{NAME}/filament-kit",
    f"{BS}{NAME}{BS}filament-kit",
    f"a@{NAME}/filament-kit",
    f"{NAME}/other-repo",
    f"{NAME}/filament",
    f"{NAME}x/filament-kit",
])
def test_account_name_elsewhere_stays_a_hit(line):
    assert term_hits(line, [NAME]) == ["f:1: owner term #1"]


def test_longer_repository_name_with_an_allowed_prefix_is_covered():
    assert cod.scan_text("f", f"{NAME}/filament-kitchen-sink", [NAME]) == []


def test_another_term_in_an_allowed_link_is_still_a_hit():
    words = [NAME, "zzqpath", f"github.com/{NAME}", f"com/{NAME[:5]}", f"{NAME[3:]}/z"]
    line = f"https://github.com/{NAME}/zzqpath"
    assert term_hits(line, words) == ["f:1: owner term #2", "f:1: owner term #3", "f:1: owner term #4",
                                      "f:1: owner term #5"]
    assert cod.scan_text("f", f"https://github.com/{NAME}/x", [NAME, "zzqpath"]) == []


def test_term_that_is_part_of_the_account_name_is_never_excused():  # L1
    for words in ([NAME[:8]], [NAME[2:6]], [NAME[:-1]]):
        assert cod.scan_text("f", f"github.com/{NAME}/x", words) == ["f:1: owner term #1"]
    assert cod.scan_text("f", f"github.com/{NAME}/x", [NAME[:8], NAME]) == ["f:1: owner term #1"]


def test_dotted_capital_i_term_is_matched_as_without_the_allowance():  # L2
    for line in ("İzmir", "i̇zmir", "see İZMIR here"):
        assert cod.scan_text("f", line, ["İzmir", NAME]) == ["f:1: owner term #1"], line
    assert cod.scan_text("f", f"github.com/{NAME} İzmir", ["İzmir", NAME]) == ["f:1: owner term #1"]


@pytest.mark.parametrize("line", [
    f"~{NAME}/filament-kit",
    f"C:{NAME}/filament-kit",
    f"nas:{NAME}/filament-kit",
    f"HOME={NAME}/filament-kit",
    f"x_github.com/{NAME}",
    f"_ko-fi.com/{NAME}",
    f"İgithub.com/{NAME}",
    f"égithub.com/{NAME}",
    f"x{NAME}/filament-library",
])
def test_boundary_before_a_link_form_is_a_whitelist(line):  # L3
    assert term_hits(line, [NAME]) == ["f:1: owner term #1"]


@pytest.mark.parametrize("line", [
    f"gıthub.com/{NAME}",
    f"{NAME}/fılament-kit",
    f"ko-fı.com/{NAME}",
])
def test_dotless_i_does_not_complete_a_link_form(line):  # L4
    assert term_hits(line, [NAME]) == ["f:1: owner term #1"]


@pytest.mark.parametrize("line", [
    f"github.com/{NAME}.local",
    f"github.com/{NAME}@x",
    f"github.com/{NAME}.x",
    f"github.com/{NAME}..",
    f"ko-fi.com/{NAME}.com",
    f"https://github.com/{NAME}&x",
])
def test_what_follows_the_account_name_in_a_host_form_is_a_whitelist(line):  # L5
    assert term_hits(line, [NAME]) == ["f:1: owner term #1"]


@pytest.mark.parametrize("line", [
    f"github.com/{NAME}.", f"github.com/{NAME}. next", f"github.com/{NAME}.)", f"github.com/{NAME}, ok",
    f"(github.com/{NAME}).", f"github.com/{NAME}?x", f"github.com/{NAME}#top", f"see ko-fi.com/{NAME}!",
    f"`{NAME}/filament-kit`", f"<{NAME}/filament-kit>", f"[{NAME}/filament-kit]",
])
def test_usual_punctuation_around_a_link_is_excused(line):
    assert cod.scan_text("f", line, [NAME]) == []


def test_dotless_i_forms_are_hits_and_plain_forms_are_not():  # L4 (exact strings)
    assert term_hits(f"gıthub.com/{NAME}", [NAME]) == ["f:1: owner term #1"]
    assert term_hits(f"{NAME}/fılament-kit", [NAME]) == ["f:1: owner term #1"]
    assert term_hits(f"github.com/{NAME}", [NAME]) == []


def test_every_occurrence_counts_once_per_line():
    line = f"github.com/{NAME} ko-fi.com/{NAME}"
    assert cod.scan_text("f", line, [NAME]) == []
    assert cod.scan_text("f", f"{line} {NAME} {NAME}", [NAME]) == ["f:1: owner term #1"]
    assert cod.scan_text("f", f"{line}\n{line}\nplain {NAME}", [NAME]) == ["f:3: owner term #1"]


def test_account_links_in_svg_text_after_entity_unescape(tmp_path):
    p = tmp_path / "a.svg"
    p.write_text(f"<svg><text>https:&#47;&#47;github.com&#47;{NAME}&gt;</text>\n"
                 f"<text>ko-fi.com&#x2F;{NAME}&quot;</text></svg>", encoding="utf-8")
    assert cod.scan_file(p, "a.svg", [NAME]) == []
    p.write_text(f"<svg><text>user&#64;{NAME}.com</text></svg>", encoding="utf-8")
    assert cod.scan_file(p, "a.svg", [NAME]) == ["a.svg:1: owner term #1"] or \
        any("owner term #1" in f for f in cod.scan_file(p, "a.svg", [NAME]))


def test_account_links_in_archive_member(tmp_path):
    p = make_zip(tmp_path / "a.3mf", {"Metadata/info.txt": f"Source: https://github.com/{NAME}/x\nko-fi.com/{NAME}"})
    assert cod.scan_file(p, "a.3mf", [NAME]) == []
    p = make_zip(tmp_path / "b.3mf", {"Metadata/info.txt": f"ok github.com/{NAME}\nDesigner: {NAME}"})
    assert cod.scan_file(p, "b.3mf", [NAME]) == ["b.3mf!Metadata/info.txt:2: owner term #1"]


def type3_font_cmap(chars):
    lines = [f"<{i:02X}> <{ord(c):04X}>" for i, c in enumerate(sorted(set(chars)), 1)]
    return (b"1 begincodespacerange <00> <FF> endcodespacerange\n"
            + f"{len(lines)} beginbfchar {' '.join(lines)} endbfchar\n".encode())


def drawn(tmp_path, first, second):
    """A PDF whose page draws `first` in an unmapped font and then `second` through a ToUnicode font."""
    chars = sorted(set(second))
    codes = "".join(f"{chars.index(c) + 1:02X}" for c in second)
    shown = f"BT /F2 9 Tf ({first}) Tj ET BT /F1 9 Tf <{codes}> Tj ET".encode()
    return make_type3_pdf(tmp_path / "k.pdf", shown, type3_font_cmap(second))


def test_account_links_in_pdf_text_split_over_runs(tmp_path):
    for first, second in [(f"see github.com/{NAME[:6]}", f"{NAME[6:]}/x)"),
                          (f"see Ko-Fi.com/{NAME[:6]}", f"{NAME[6:]}"),
                          (f"clone {NAME[:6]}", f"{NAME[6:]}/filament-kit"),
                          (f"https://github.com/{NAME[:6]}", f"{NAME[6:]}.")]:
        p = drawn(tmp_path, first, second)
        assert [t for _, t in cod.pdf_text(p.read_bytes())] == [[first, second]]
        assert cod.scan_file(p, "k.pdf", [NAME]) == [], (first, second)
    for first, second in [(f"see {NAME[:6]}", f"{NAME[6:]}"),
                          (f"notgithub.com/{NAME[:6]}", f"{NAME[6:]}/x"),
                          (f"github.com/{NAME[:6]}", f"{NAME[6:]}x/y"),
                          (f"user@{NAME[:6]}", f"{NAME[6:]}.com")]:
        out = cod.scan_file(drawn(tmp_path, first, second), "k.pdf", [NAME])
        assert out == ["k.pdf!text4:joined: owner term #1"], (first, second)


def test_bare_mention_next_to_a_pdf_link_is_a_hit(tmp_path):
    p = drawn(tmp_path, f"github.com/{NAME[:6]}", f"{NAME[6:]} and {NAME}")
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:2: owner term #1"]


def test_account_links_in_pdf_text_with_whitespace_removed(tmp_path):
    p = drawn(tmp_path, f"see github.com/ {NAME[:6]}", f"{NAME[6:]} / x")  # a space inside the link text is not a link
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:joined: owner term #1"]
    p = drawn(tmp_path, f"see ko-fi.com/{NAME[:6]}", f"{NAME[6:]} ")
    assert cod.scan_file(p, "k.pdf", [NAME]) == []
    p = drawn(tmp_path, f"see {NAME[:6]}", f" {NAME[6:]}")  # plain prose with the space dropped between runs
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:joined: owner term #1"]
    p = drawn(tmp_path, f"see x github.com/{NAME[:6]}", f"{NAME[6:]} x")
    assert cod.scan_file(p, "k.pdf", [NAME]) == []
    p = drawn(tmp_path, f"see xgithub.com/{NAME[:6]}", f"{NAME[6:]} x")
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:joined: owner term #1"]


def test_account_forms_in_the_default_links_all_pass_together():
    assert cod.scan_text("f", "\n".join(HOST_LINKS), [NAME]) == []


def drawn_runs(tmp_path, runs):
    """A PDF whose page draws each text in `runs` in a font of its own, alternating an unmapped and a mapped font."""
    mapped = "".join(r for k, r in enumerate(runs) if k % 2)
    chars = sorted(set(mapped))
    parts = []
    for k, r in enumerate(runs):
        if k % 2:
            parts.append(f"BT /F1 9 Tf <{''.join(f'{chars.index(c) + 1:02X}' for c in r)}> Tj ET")
        else:
            parts.append(f"BT /F2 9 Tf ({r}) Tj ET")
    return make_type3_pdf(tmp_path / "k.pdf", " ".join(parts).encode(), type3_font_cmap(mapped or "a"))


@pytest.mark.parametrize("runs", [
    [f"github.com/{NAME} see {NAME[:6]}", NAME[6:]],
    [f"github.com/{NAME}", f"(c) {NAME[:6]}", NAME[6:]],
    [NAME[:6], f"{NAME[6:]} github.com/{NAME}"],
    [f"see {NAME[:6]}", f"{NAME[6:]}", f"https://github.com/{NAME}/x"],
    [f"{NAME[:6]}", f"{NAME[6:]}"],
])
def test_split_mention_is_reported_even_beside_a_whole_mention_in_a_link(tmp_path, runs):  # M
    p = drawn_runs(tmp_path, runs)
    assert [t for _, t in cod.pdf_text(p.read_bytes())] == [runs]
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:joined: owner term #1"]


@pytest.mark.parametrize("runs", [
    [f"github.com/{NAME}"],
    [f"github.com/{NAME} and ko-fi.com/{NAME}"],
    [f"github.com/{NAME} ", f"ko-fi.com/{NAME} ", f"{NAME}/filament-kit"],
])
def test_whole_mentions_only_inside_links_report_nothing_in_a_pdf(tmp_path, runs):
    assert cod.scan_file(drawn_runs(tmp_path, runs), "k.pdf", [NAME]) == []


def test_whole_mention_outside_a_link_is_reported_once_in_a_pdf(tmp_path):
    p = drawn_runs(tmp_path, [f"github.com/{NAME}", f"by {NAME} {NAME[:6]}", NAME[6:]])
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:2: owner term #1"]
    p = drawn_runs(tmp_path, ["x ", f"made by {NAME}"])
    assert cod.scan_file(p, "k.pdf", [NAME]) == ["k.pdf!text4:2: owner term #1"]


def test_other_terms_in_a_pdf_are_checked_as_without_the_allowance(tmp_path):
    p = drawn_runs(tmp_path, [f"github.com/{NAME} zzq", "first", "last"])
    assert cod.scan_file(p, "k.pdf", [NAME, "zzqfirstlast"]) == ["k.pdf!text4:joined: owner term #2"]
    p = drawn_runs(tmp_path, ["x ", f"github.com/{NAME} {NAME[:6]}", NAME[6:]])
    assert cod.scan_file(p, "k.pdf", [NAME[:8]]) == ["k.pdf!text4:2: owner term #1"]


def pdf_hits(tmp_path, runs, words=None):
    p = drawn_runs(tmp_path, runs)
    assert [t for _, t in cod.pdf_text(p.read_bytes())] == [runs]
    return cod.scan_file(p, "k.pdf", words or [NAME])


JOINED = ["k.pdf!text4:joined: owner term #1"]
TWO_WORDS = f"{NAME[:8].title()} {NAME[8:].title()}"  # the name spelled as two words


@pytest.mark.parametrize("runs", [
    ["See", f"github.com/{NAME}"],
    [f"github.com/{NAME}", "Support"],
    [f"ko-fi.com/{NAME}", "and more"],
    ["clone", f"{NAME}/filament-kit"],
    ["x", f"https://github.com/{NAME}/filament-kit-hardware", "y"],
    [f"github.com/{NAME[:6]}", f"{NAME[6:]}/filament-kit"],
    [f"github.com/{NAME[:6]}", NAME[6:]],
    [f"{NAME[:6]}", f"{NAME[6:]}/filament-kit"],
    [f"ko-fi.com/{NAME} ", f"github.com/{NAME[:4]}", f"{NAME[4:]}/x"],
])
def test_whole_link_in_a_run_of_its_own_next_to_a_run_without_a_space_reports_nothing(tmp_path, runs):  # M
    assert pdf_hits(tmp_path, runs) == []


@pytest.mark.parametrize("runs", [
    [NAME[:6], NAME[6:]],
    [f"github.com/{NAME}", f"(c) {NAME[:6]}", NAME[6:]],
    [f"github.com/{NAME[:6]}", f"{NAME[6:]}x"],
    [f"seegithub.com/{NAME[:6]}", f"{NAME[6:]}"],
    [NAME[:6], f"{NAME[6:]}", f"ko-fi.com/{NAME}"],
    [f"x{NAME[:6]}", f"{NAME[6:]}/filament-kit"],
])
def test_split_mention_without_spaces_is_still_reported(tmp_path, runs):  # M
    assert pdf_hits(tmp_path, runs) == JOINED


@pytest.mark.parametrize("runs", [
    [f"Contact: github.com/ {TWO_WORDS}"],
    ["see github.com/", TWO_WORDS],
    [f"github.com/{NAME[:8].title()}", f" {NAME[8:].title()}"],
    [f"github.com/{NAME[:8]} {NAME[8:]}"],
    [f"ko-fi.com/ {NAME[:6]}", NAME[6:]],
    [f"github.com/{NAME[:6]} ", f" {NAME[6:]}"],
    [f"github.com/ {NAME[:6]}", f"{NAME[6:]}"],
    [f"{NAME[:6]} ", f"{NAME[6:]}/filament-kit"],
    [f"{NAME[:6]}", f" {NAME[6:]}/filament-kit"],
    ["x ", NAME[:6], f"{NAME[6:]}/filament -kit"],
])
def test_whitespace_inside_a_link_form_is_not_a_link(tmp_path, runs):  # L1
    assert pdf_hits(tmp_path, runs) == JOINED


def test_whitespace_before_the_name_in_one_run_is_reported_by_the_run_scan(tmp_path):  # L1
    assert pdf_hits(tmp_path, ["x", f"github.com/ {NAME}"]) == ["k.pdf!text4:2: owner term #1"]


def test_account_term_listed_twice_prints_the_lines_it_printed_before(tmp_path):  # L3
    assert pdf_hits(tmp_path, ["x", f"by {NAME}"], [NAME, NAME]) == ["k.pdf!text4:2: owner term #1"] * 2
    assert pdf_hits(tmp_path, [f"github.com/{NAME}", "x"], [NAME, NAME]) == []
    assert pdf_hits(tmp_path, [NAME[:6], NAME[6:]], [NAME, NAME]) == [
        "k.pdf!text4:joined: owner term #1", "k.pdf!text4:joined: owner term #2"]
    assert pdf_hits(tmp_path, ["x", f"by {NAME}", NAME[:6], NAME[6:]], [NAME, "zzq", NAME]) == [
        "k.pdf!text4:2: owner term #1"] * 2


def test_a_mention_the_glued_text_does_not_hold_is_judged_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(cod, "split_mentions_in_links", lambda runs: None)
    assert pdf_hits(tmp_path, [NAME[:6], NAME[6:]]) == JOINED
    assert pdf_hits(tmp_path, [f"github.com/{NAME}", "x"]) == []


@pytest.mark.parametrize("line", [
    f"Ko-fi.com/{NAME}",
    f"KO-FI.COM/{NAME}",
    f"{NAME}/filament-Kit",
    f"{NAME}/filament-KIT",
    f"gİthub.com/{NAME}",
    f"gıthub.com/{NAME}",
    f"github.com/{NAME}ſ",
    f"github.com/{NAME}K",
    f"ſ{NAME}/filament-kit",
    f"K{NAME}/filament-kit",
    f"github.com/{NAME}/x K{NAME}",
])
def test_non_ascii_letters_do_not_complete_or_surround_a_link_form(line):  # L2
    assert term_hits(line, [NAME]) == ["f:1: owner term #1"]


def test_non_ascii_letters_do_not_complete_a_link_form_in_a_pdf(tmp_path):  # L2
    assert pdf_hits(tmp_path, ["x", "see Ko-fi.com/" + NAME[:6], NAME[6:]]) == JOINED
    assert pdf_hits(tmp_path, [NAME[:6], f"{NAME[6:]}/filament-Kit"]) == JOINED


@pytest.mark.parametrize("line", [
    f"`github.com/{NAME}`",
    f"`https://ko-fi.com/{NAME}`",
    f"`github.com/{NAME}.`",
    f"`{NAME}/filament-kit`",
])
def test_a_backtick_around_a_link_is_excused(line):  # L4
    assert term_hits(line, [NAME]) == []


PRINTABLE = [chr(c) for c in range(32, 127)]
HOSTS = ["github.com", "www.github.com", "ko-fi.com"]
BARES = [f"{NAME}/filament-kit", f"{NAME}/filament-library"]
# every character a form accepts at each position; the tests below assert a hit for every other printable ASCII character
BEFORE_HOST_OK = " !\"#$%&'()*+,/:;<=>?@[\\]^`{|}~"  # all but letters, digits and _ . -
AFTER_NAME_OK = " )]}>\"',;:!?#/`."  # a "." is excused at the end of the line; AFTER_DOT_OK is what may follow it
AFTER_DOT_OK = " )]}>\"'`"
BEFORE_BARE_OK = " \"'([<`"


@pytest.mark.parametrize("host", HOSTS)
def test_every_character_before_a_host_form(host):  # L5
    for c in PRINTABLE:
        got = term_hits(f"{c}{host}/{NAME}", [NAME])
        assert got == ([] if c in BEFORE_HOST_OK else ["f:1: owner term #1"]), repr(c)
    assert term_hits(f"{host}/{NAME}", [NAME]) == []


@pytest.mark.parametrize("host", HOSTS)
def test_every_character_after_the_name_in_a_host_form(host):  # L5
    for c in PRINTABLE:
        got = term_hits(f"{host}/{NAME}{c}", [NAME])
        assert got == ([] if c in AFTER_NAME_OK else ["f:1: owner term #1"]), repr(c)
        got = term_hits(f"{host}/{NAME}{c}x", [NAME])
        assert got == ([] if c in AFTER_NAME_OK and c != "." else ["f:1: owner term #1"]), repr(c)


@pytest.mark.parametrize("host", HOSTS)
def test_every_character_after_the_full_stop_that_follows_the_name(host):  # L5
    for c in PRINTABLE:
        got = term_hits(f"{host}/{NAME}.{c}", [NAME])
        assert got == ([] if c in AFTER_DOT_OK else ["f:1: owner term #1"]), repr(c)
        got = term_hits(f"{host}/{NAME}.{c}x", [NAME])
        assert got == ([] if c in AFTER_DOT_OK else ["f:1: owner term #1"]), repr(c)
    assert term_hits(f"{host}/{NAME}.", [NAME]) == []


@pytest.mark.parametrize("bare", BARES)
def test_every_character_before_a_bare_form(bare):  # L5
    for c in PRINTABLE:
        got = term_hits(f"{c}{bare}", [NAME])
        assert got == ([] if c in BEFORE_BARE_OK else ["f:1: owner term #1"]), repr(c)
    assert term_hits(bare, [NAME]) == []


@pytest.mark.parametrize("term", [NAME.title(), NAME.upper(), NAME[:6] + NAME[6:].upper()])
def test_account_term_in_any_case_is_excused_only_in_links(term):  # L5
    for line in (f"github.com/{NAME}", f"Ko-Fi.com/{NAME.upper()}/x", f"{NAME}/filament-kit",
                 f"see {NAME.title()}/Filament-Kit"):
        assert cod.scan_text("f", line, [term]) == [], line
    assert term_hits(f"made by {NAME}", [term]) == ["f:1: owner term #1"]
    assert term_hits(f"made by {NAME.upper()} github.com/{NAME}", [term]) == ["f:1: owner term #1"]
    assert term_hits(f"made by {NAME}", [NAME.title(), NAME.upper()]) == ["f:1: owner term #1", "f:1: owner term #2"]
    assert term_hits(f"github.com/{NAME}", [NAME.title(), NAME.upper(), NAME]) == []


def head_hits(text, words):
    """The owner-term findings the scan printed before the account allowance: w.lower() in line.lower()."""
    return [f"f:{n}: owner term #{words.index(w) + 1}" for n, line in enumerate(text.splitlines(), 1)
            for w in words if w.lower() in line.lower()]


@pytest.mark.parametrize("line, words", [
    ("Ko", ["ko"]),
    ("Ko", ["k"]),
    ("ſ", ["s"]),
    ("ſo", ["so"]),
    ("ﬁlament-kit", ["filament-kit"]),
    ("filament-Kit", ["filament-kit"]),
    ("filament-Kit", ["filament-Kit"]),
    ("İzmir", ["izmir", "İzmir", "i̇zmir"]),
    ("i̇zmir ızmir", ["izmir", "İZMIR", "ızmir"]),
    ("straße", ["strasse", "STRAẞE"]),
    (f"github.com/{NAME} K", ["k", "github", NAME[:6], NAME[3:9]]),
    (f"Kſ {NAME.title()}", [NAME[:6], "ks", "ſ"]),
])
def test_other_terms_lower_case_exactly_as_before(line, words):  # L5
    assert term_hits(line, words) == head_hits(line, words)
    assert term_hits(line + "\n" + line, words) == head_hits(line + "\n" + line, words)


def test_other_terms_in_a_pdf_lower_case_exactly_as_before(tmp_path):  # L5
    assert pdf_hits(tmp_path, ["x", "zzqK", "o"], ["zzqko"]) == ["k.pdf!text4:joined: owner term #1"]
    assert pdf_hits(tmp_path, ["x", "zzqſ", "o"], ["zzqso"]) == []
    assert pdf_hits(tmp_path, ["x", "zzqﬁ", "lament"], ["zzqfilament"]) == []


@pytest.mark.parametrize("term", [NAME.title(), NAME.upper()])
def test_account_term_in_any_case_is_judged_the_same_in_a_pdf(tmp_path, term):  # L5
    assert pdf_hits(tmp_path, ["See", f"github.com/{NAME}"], [term]) == []
    assert pdf_hits(tmp_path, [f"github.com/{NAME}", f"(c) {NAME[:6]}", NAME[6:]], [term]) == JOINED
    assert pdf_hits(tmp_path, ["x", f"by {NAME}"], [term]) == ["k.pdf!text4:2: owner term #1"]


# A copyright notice "(c) <year> <account>" is excused too, as that line shape only.
SIGN = "\u00a9"
NBSP = "\u00a0"
NOTICE_BEFORE_OK = " \"'([<`"  # plus other whitespace; anything else before the marker is a hit
NOTICE_AFTER_OK = " )]}>\"',;:!`"  # a "." is excused at the end of the line or before one of AFTER_DOT_OK


@pytest.mark.parametrize("line", [
    f"Everything outside `enclosures/` is licensed under GPL-3.0-only (see `LICENSE`), (c) 2026 {NAME}.",
    f"The model files in this folder (STEP, 3MF) are (c) 2026 {NAME}.",
    f"(C) 2026 {NAME}",
    f"(c) 2026 {NAME.upper()}",
    f"Copyright 2026 {NAME}",
    f"COPYRIGHT 2026 {NAME.title()}",
    f"Copyright (c) 2024-2026 {NAME}.",
    f"Copyright (C) 2024\u20132026 {NAME}",
    f"copyright {SIGN} 2025, 2026 {NAME}",
    f"copyright   {SIGN}  2025, 2026, 2027\t{NAME}",
    f"{SIGN} 2026 {NAME}",
    f"Licensed by {SIGN} 2026 {NAME}",
    f"{SIGN} 2026 {NAME} and (c) 2027 {NAME}",
    f"1999 2026 (c) 1999 {NAME}",
    f"(c) 2019-2020, 2021-2022 {NAME}",
    f"(c)\t2026\t{NAME}",
    f"x (c) 2026 {NAME}",
    f'"(c) 2026 {NAME}"',
    f"((c) 2026 {NAME})",
    f"[(c) 2026 {NAME}]",
    f"<(c) 2026 {NAME}>",
    f"`(c) 2026 {NAME}`",
    f"{NBSP}(c) 2026 {NAME}",
    f"(c) 2026 {NAME}) next",
    f"(c) 2026 {NAME}, all rights",
    f"(c) 2026 {NAME}; see",
    f'(c) 2026 {NAME}" end',
    f"(c) 2026 {NAME}. Next sentence.",
    f"(c) 2026 {NAME}.)",
    f"(c) 2026 {NAME}:",
    f"github.com/{NAME} (c) 2026 {NAME}",
])
def test_copyright_notice_with_the_account_name_passes(line):
    assert cod.scan_text("f", line, [NAME]) == []


def test_copyright_notice_in_entity_escaped_text_and_not_without_unescape():
    for line in (f"&#169; 2026 {NAME}", f"&#xA9; 2026 {NAME}", f"&copy; 2026 {NAME}", f"&#40;c&#41; 2026 {NAME}",
                 f"Copyright &copy; 2026 {NAME}"):
        assert cod.scan_text("f", line, [NAME], unescape=True) == [], line
        assert term_hits(line, [NAME]) == ["f:1: owner term #1"], line


def test_copyright_notice_in_files_and_archives(tmp_path):
    p = tmp_path / "a.svg"
    p.write_text(f"<svg><text> &#169; 2026 {NAME} </text>\n<text> (c) 2026 {NAME}. </text></svg>", encoding="utf-8")
    assert cod.scan_file(p, "a.svg", [NAME]) == []
    p = make_zip(tmp_path / "a.3mf", {"Metadata/info.txt": f"Copyright {SIGN} 2026 {NAME}\n(c) 2026 {NAME}"})
    assert cod.scan_file(p, "a.3mf", [NAME]) == []
    p = make_zip(tmp_path / "b.3mf", {"Metadata/info.txt": f"(c) 2026 {NAME}\nDesigner: {NAME}"})
    assert cod.scan_file(p, "b.3mf", [NAME]) == ["b.3mf!Metadata/info.txt:2: owner term #1"]


def test_copyright_notice_in_one_drawn_pdf_run(tmp_path):
    assert pdf_hits(tmp_path, [f"Copyright (c) 2026 {NAME}.", "x"]) == []
    assert pdf_hits(tmp_path, ["x", f"{SIGN} 2026 {NAME}"]) == []
    assert pdf_hits(tmp_path, ["See", f"(c) 2024-2026 {NAME}", "github.com/" + NAME]) == []


@pytest.mark.parametrize("line", [
    f"(c) {NAME}",
    f"2026 {NAME}",
    f"(c) 2026 by {NAME}",
    f"(c) 2026, {NAME}",
    f"(c) 2026{NAME}",
    f"(c)2026 {NAME}",
    f"(c) 2026{NBSP}{NAME}",
    f"(c){NBSP}2026 {NAME}",
    f"copyright{NBSP}2026 {NAME}",
    f"(c)\u2003 2026 {NAME}",
    f"(c) 2026\u3000{NAME}",
    f"(c) 26 {NAME}",
    f"(c) 202 {NAME}",
    f"(c) 20266 {NAME}",
    f"(c) 3026 {NAME}",
    f"(c) 1899 {NAME}",
    f"(c) 2126 {NAME}",
    f"(c) {chr(0xFF12)}{chr(0xFF10)}{chr(0xFF12)}{chr(0xFF16)} {NAME}",
    f"(c) {chr(0x0662)}{chr(0x0660)}{chr(0x0662)}{chr(0x0666)} {NAME}",
    f"(c) 20{chr(0xFF12)}{chr(0xFF16)} {NAME}",
    f"(c) 20{chr(0x0662)}{chr(0x0666)} {NAME}",
    f"(c) 2024-20{chr(0xFF12)}{chr(0xFF16)} {NAME}",
    f"(c) 2024, 20{chr(0x0662)}{chr(0x0666)} {NAME}",
    f"(c) 2026 2027 {NAME}",
    f"(c) 2026 - 2027 {NAME}",
    f"(c) 2024 -2026 {NAME}",
    f"(c) 2024- 2026 {NAME}",
    f"(c) 2024,2026 {NAME}",
    f"(c) 2024,  2026 {NAME}",
    f"(c) 2024-26 {NAME}",
    f"(c) 2024-2026- {NAME}",
    f"(c) 2024,, 2026 {NAME}",
    f"x(c) 2026 {NAME}",
    f"\u00e9(c) 2026 {NAME}",
    f"nocopyright 2026 {NAME}",
    f"xcopyright 2026 {NAME}",
    f"x{SIGN} 2026 {NAME}",
    f"copy right 2026 {NAME}",
    f"copyr\u0131ght 2026 {NAME}",
    f"cop\u0443right 2026 {NAME}",
    f"copyr\u0130ght 2026 {NAME}",
    f"copyright(c) 2026 {NAME}",
    f"copyright (c)(c) 2026 {NAME}",
    f"((c)) 2026 {NAME}",
    f"(c 2026 {NAME}",
    f"c) 2026 {NAME}",
    f"[c] 2026 {NAME}",
    f"(r) 2026 {NAME}",
    f"(x) 2026 {NAME}",
    f"copyright: 2026 {NAME}",
    f"(c) 2024{chr(0x2014)}2026 {NAME}",
    f"{NAME} (c) 2026 {NAME}",
    f"(c) 2026 {NAME}.local",
    f"(c) 2026 {NAME}@example.org",
    f"(c) 2026 {NAME}-pc",
    f"(c) 2026 {NAME}_x",
    f"(c) 2026 {NAME}x",
    f"(c) 2026 {NAME}2",
    f"(c) 2026 {NAME}/secret",
    f"(c) 2026 {NAME}?x",
    f"(c) 2026 {NAME}#top",
    f"(c) 2026 {NAME}.x",
    f"(c) 2026 {NAME}..",
    f"(c) 2026 {NAME}&x",
    f"(c) 2026 {NAME}K",
    f"(c) 2026 {NAME}\u00e9",
    f"(c) 2026 x{NAME}",
])
def test_text_that_is_not_a_copyright_notice_stays_a_hit(line):
    assert term_hits(line, [NAME]) == ["f:1: owner term #1"]


@pytest.mark.parametrize("c", PRINTABLE + [NBSP, "\u2003", "\u00e9", "\u212a", "\ufeff"])
def test_every_character_before_a_notice_marker(c):
    for marker in ("(c)", "copyright", SIGN):  # not "copyright (c)": its "(c)" is a marker after a space
        ok = c in NOTICE_BEFORE_OK or c.isspace()
        assert term_hits(f"{c}{marker} 2026 {NAME}", [NAME]) == ([] if ok else ["f:1: owner term #1"]), (c, marker)


@pytest.mark.parametrize("marker", ["(c)", "copyright", SIGN, "copyright (c)", f"copyright {SIGN}"])
def test_every_character_after_the_name_in_a_notice(marker):
    for c in PRINTABLE:
        ok = c in NOTICE_AFTER_OK or c == "."
        assert term_hits(f"{marker} 2026 {NAME}{c}", [NAME]) == ([] if ok else ["f:1: owner term #1"]), repr(c)
        ok = c in NOTICE_AFTER_OK
        assert term_hits(f"{marker} 2026 {NAME}{c}x", [NAME]) == ([] if ok else ["f:1: owner term #1"]), repr(c)
        ok = c in AFTER_DOT_OK
        assert term_hits(f"{marker} 2026 {NAME}.{c}x", [NAME]) == ([] if ok else ["f:1: owner term #1"]), repr(c)
    assert term_hits(f"{marker} 2026 {NAME}", [NAME]) == []
    assert term_hits(f"{marker} 2026 {NAME}.", [NAME]) == []


@pytest.mark.parametrize("c", ["/", "?", "#"])
def test_slash_question_mark_and_hash_after_a_notice_name_are_hits_where_a_link_allows_them(c):
    assert term_hits(f"github.com/{NAME}{c}x", [NAME]) == []
    assert term_hits(f"(c) 2026 {NAME}{c}x", [NAME]) == ["f:1: owner term #1"]


def test_notice_between_the_marker_and_the_name_takes_only_spaces_and_tabs():
    for sep in (" ", "  ", "\t", " \t "):
        assert term_hits(f"(c){sep}2026{sep}{NAME}", [NAME]) == []
    for c in PRINTABLE + [NBSP, "\u2003", "\u3000", "\u200b"]:
        if c in " \t":
            continue
        assert term_hits(f"(c){c}2026 {NAME}", [NAME]) == ["f:1: owner term #1"], repr(c)
        assert term_hits(f"(c) 2026{c}{NAME}", [NAME]) == ["f:1: owner term #1"], repr(c)


@pytest.mark.parametrize("year", ["1900", "1999", "2000", "2026", "2099", "1999-2026", "2024\u20132026", "2025, 2026",
                                  "2000-2010, 2020, 2022-2026"])
def test_notice_years_that_are_excused(year):
    assert term_hits(f"(c) {year} {NAME}", [NAME]) == []


@pytest.mark.parametrize("year", ["", "0", "26", "202", "20260", "1899", "2100", "3026", "0000", "x2026", "2026x", "2O26",
                                  "2026-", "-2026", "2026,", ",2026", "2026 ,2027", "2026,2027", "2026-27", "2026 2027",
                                  "2026-2027-", "2026,  2027", "2026, ", "2026;2027", "2026/2027", "20 26"])
def test_notice_years_that_are_not_excused(year):
    assert term_hits(f"(c) {year} {NAME}", [NAME]) == ["f:1: owner term #1"]


def test_notice_excuses_only_its_own_name_span():
    assert term_hits(f"(c) 2026 {NAME} and {NAME}", [NAME]) == ["f:1: owner term #1"]
    assert term_hits(f"{NAME} (c) 2026 {NAME}", [NAME]) == ["f:1: owner term #1"]
    assert term_hits(f"(c) 2026 {NAME}, github.com/{NAME} and (c) 2027 {NAME}.", [NAME]) == []
    assert term_hits(f"(c) 2026 {NAME}\n(c) 2026 by {NAME}\n(c) 2026 {NAME}", [NAME]) == ["f:2: owner term #1"]
    assert term_hits(f"(c) 2026 {NAME}-{NAME}", [NAME]) == ["f:1: owner term #1"]


def test_notice_excuses_only_the_account_name_term():
    holder = f"(c) 2026 {NAME}"
    assert term_hits(holder, [NAME, NAME[:6]]) == ["f:1: owner term #2"]
    assert term_hits(holder, [NAME[3:], NAME]) == ["f:1: owner term #1"]
    assert term_hits(holder, [f"2026 {NAME}"]) == ["f:1: owner term #1"]
    assert term_hits(holder, [f"(c) 2026 {NAME}"]) == ["f:1: owner term #1"]
    assert term_hits(holder, ["(c) 2026"]) == ["f:1: owner term #1"]
    assert term_hits(holder + " zzqterm", [NAME, "zzqterm", "zzq"]) == ["f:1: owner term #2", "f:1: owner term #3"]
    assert term_hits(holder, ["zzqterm"]) == []


@pytest.mark.parametrize("line, words", [
    ("(c) 2026 Some One", ["some one"]),
    ("Copyright 2026 zzq", ["zzq", "ZZQ"]),
    (f"(c) 2026 {NAME[:6]}", [NAME[:6], NAME[:8]]),
    (f"(c) 2026 {NAME[:6]}", [NAME]),
    (f"(c) 2026 by {NAME}", []),
    ("(c) 2026 K", ["k"]),
    (f"{SIGN} 2026 zzq github.com/{NAME}", ["zzq", "github"]),
])
def test_without_the_account_term_a_notice_changes_nothing(line, words):
    assert term_hits(line, words) == head_hits(line, words)


def test_notice_in_a_pdf_is_judged_per_run_never_by_the_joined_text(tmp_path):
    for runs in ([f"(c) 2026 {NAME[:6]}", NAME[6:]],
                 [f"Copyright 2026 {NAME[:6]}", NAME[6:]],
                 ["x", f"{SIGN} 2026 {NAME[:6]}", NAME[6:]],
                 [f"(c) 2026 {NAME[:6]}", f"{NAME[6:]}.", "y"]):
        assert pdf_hits(tmp_path, runs) == JOINED, runs
    assert pdf_hits(tmp_path, ["(c) 2026", NAME]) == ["k.pdf!text4:2: owner term #1"]
    assert pdf_hits(tmp_path, ["(c)", f"2026 {NAME}"]) == ["k.pdf!text4:2: owner term #1"]
    assert pdf_hits(tmp_path, [f"(c)2026{NAME}"]) == ["k.pdf!stream1:1: owner term #1"]
    assert pdf_hits(tmp_path, [f"(c) 2026 {NAME}", NAME[:6], NAME[6:]]) == JOINED
    assert pdf_hits(tmp_path, [f"(c) 2026 {NAME}", f"by {NAME}"]) == ["k.pdf!text4:2: owner term #1"]
    assert pdf_hits(tmp_path, [f"(c) 2026 {NAME}", NAME[:6], NAME[6:]], [NAME.upper()]) == JOINED
    assert cod.split_mentions_in_links([f"(c) 2026 {NAME[:6]}", NAME[6:]]) is False
    assert cod.split_mentions_in_links([f"(c) 2026 {NAME}"]) is True


# Embedded font programs: random font bytes can look like an address, so only the owner terms are searched in a stream
# that is provably a font program: a /FontFile2 or /FontFile3 key of a /FontDescriptor object, each object numbered once
# in the file, the reference with the stream's generation, no /Contents key naming the stream, and the stream starting
# like an sfnt or CFF font. Every doubtful case leaves the stream scanned with all patterns.
FONT_BYTES = (b"\x00\x01\x00\x00\nK@" + b"aJ.x\nC:/Us" + b"ers/someone/f\nAB12CD34" + b"EF56GH7\n\x00\x7f")  # split: this file is scanned
FONT_KINDS = {"email address", "Windows user path", "printer-serial-like string"}
DESCRIPTOR = b"<< /Type /FontDescriptor /FontFile2 6 0 R >>"
FLATE = b"<< /Filter /FlateDecode >>"


def make_objs_pdf(path, objs, raw=()):
    """objs: (number, dictionary or body bytes, stream bytes or None, generation) in file order. A stream is deflated
    unless its object number is in raw, and its dictionary gets a /Length unless it has one."""
    body = b"%PDF-1.5\n"
    for num, head, stream, gen in objs:
        data = b"" if stream is None else stream if num in raw else zlib.compress(stream)
        if stream is not None and b"/Length" not in head:
            head = head[:head.rindex(b">>")] + b"/Length %d >>" % len(data)
        body += f"{num} {gen} obj\n".encode() + head
        if stream is not None:
            body += b"\nstream\n" + data + b"\nendstream"
        body += b"\nendobj\n"
    path.write_bytes(body + b"%%EOF\n")
    return path


def font_pdf(tmp_path, ref=b"/FontFile2 6 0 R", stream=FONT_BYTES, stream_head=FLATE, extra=()):
    objs = [(5, b"<< /Type /FontDescriptor " + ref + b" >>", None, 0), (6, stream_head, stream, 0), *extra]
    return make_objs_pdf(tmp_path / "f.pdf", objs)


def finding_kinds(path, words=()):
    found = cod.scan_file(path, "f.pdf", list(words))
    return {f.split(": ")[1] if ": owner term" not in f else "owner term" for f in found}


def leaks(path):
    """The kinds of generic finding in a PDF whose only suspect bytes are FONT_BYTES (so FONT_KINDS = all reported)."""
    return {f.split(": ")[1] for f in cod.scan_file(path, "f.pdf", [])}


def test_pdf_font_program_gets_no_generic_finding(tmp_path):
    for ref in (b"/FontFile2 6 0 R", b"/FontFile3 6 0 R"):
        assert cod.scan_file(font_pdf(tmp_path, ref), "f.pdf", []) == [], ref


def test_a_type1_font_file_is_never_exempt(tmp_path):  # (a)
    assert leaks(font_pdf(tmp_path, b"/FontFile 6 0 R")) == FONT_KINDS


def test_pdf_font_program_rule_follows_the_reference_not_the_bytes(tmp_path):  # fails if every stream is exempt
    out = cod.scan_file(font_pdf(tmp_path, b"/FontFile2 99 0 R"), "f.pdf", [])
    assert {f.split(": ")[1] for f in out} == FONT_KINDS
    assert all(f.startswith("f.pdf!stream1:") for f in out)
    assert {f.split(": ")[1] for f in cod.scan_file(font_pdf(tmp_path, b"/Subtype /Type1"), "f.pdf", [])} == FONT_KINDS


def test_pdf_font_program_rule_exempts_the_pointed_at_stream(tmp_path):  # fails if the exemption is removed
    assert finding_kinds(font_pdf(tmp_path)) == set()
    two = font_pdf(tmp_path, extra=[(7, b"<< /Filter /FlateDecode >>", FONT_BYTES, 0)])
    assert {f.split(":")[0] for f in cod.scan_file(two, "f.pdf", [])} == {"f.pdf!stream2"}


def test_pdf_stream_with_length1_of_its_own_is_not_a_font_program(tmp_path):
    p = font_pdf(tmp_path, b"/Subtype /Type1", stream_head=b"<< /Length1 120 /Filter /FlateDecode >>")
    assert {f.split(": ")[1] for f in cod.scan_file(p, "f.pdf", [])} == FONT_KINDS


def test_pdf_stream_cannot_exempt_itself_or_another_by_its_content(tmp_path):
    own = font_pdf(tmp_path, b"/Subtype /Type1", stream_head=b"<< /FontFile2 6 0 R /Filter /FlateDecode >>")
    assert {f.split(": ")[1] for f in cod.scan_file(own, "f.pdf", [])} == FONT_KINDS
    inside = font_pdf(tmp_path, b"/Subtype /Type1", extra=[(7, b"<< /Filter /FlateDecode >>",
                                                           b"<< /FontFile2 6 0 R >>", 0)])
    assert {f.split(":")[0] for f in cod.scan_file(inside, "f.pdf", [])} == {"f.pdf!stream1"}


def test_owner_term_inside_a_font_program_is_still_found(tmp_path):
    p = font_pdf(tmp_path, stream=FONT_BYTES + b"ZZQTerm\n")
    assert cod.scan_file(p, "f.pdf", ["zzqterm"]) == ["f.pdf!stream1:5: owner term #1"]


def test_address_outside_a_font_program_is_still_found_next_to_one(tmp_path):
    info = (8, b"<< /Author (" + EMAIL.encode() + b") >>", None, 0)
    xmp = (9, b"<< /Type /Metadata /Filter /FlateDecode >>", b"<x:xmpmeta>" + EMAIL.encode() + b"</x:xmpmeta>", 0)
    page = (10, b"<< /Filter /FlateDecode >>", b"BT (" + EMAIL.encode() + b") Tj ET", 0)
    out = cod.scan_file(font_pdf(tmp_path, extra=[info, xmp, page]), "f.pdf", [])
    assert sorted(f.split(":")[0] for f in out) == ["f.pdf", "f.pdf!stream2", "f.pdf!stream3"]
    assert all("email address" in f for f in out)


@pytest.mark.parametrize("ref, gen", [(b"/FontFile2 6 3 R", 3), (b"/FontFile2\n6\r\n0\n R", 0),
                                      (b"/FontFile2   6   0   R", 0)])
def test_font_file_reference_with_generation_or_odd_whitespace_still_exempts(tmp_path, ref, gen):
    objs = [(5, b"<< /Type /FontDescriptor " + ref + b" >>", None, 0), (6, b"<< /Filter /FlateDecode >>", FONT_BYTES, gen)]
    assert cod.scan_file(make_objs_pdf(tmp_path / "g.pdf", objs), "g.pdf", []) == []


def test_font_file_name_must_be_whole(tmp_path):
    for ref in (b"/FontFile4 6 0 R", b"/FontFileX 6 0 R", b"/FontFile26 0 R"):
        assert cod.scan_file(font_pdf(tmp_path, ref), "f.pdf", []) != [], ref


EMBEDDED = b"<< /Type /EmbeddedFile >>"
INNER_PDF = b"%PDF-1.4\n5 0 obj\n" + DESCRIPTOR + b"\nendobj\n%%EOF"


def objs_pdf(tmp_path, objs, **kw):
    return make_objs_pdf(tmp_path / "f.pdf", objs, **kw)


@pytest.mark.parametrize("text", [INNER_PDF, b"BT (/FontFile2 6 0 R endobj) Tj ET",
                                  b"5 0 obj\n" + DESCRIPTOR + b"\nendobj"])
def test_reference_inside_uncompressed_stream_data_exempts_nothing(tmp_path, text):  # M1, (b)
    objs = [(4, EMBEDDED, text, 0), (6, FLATE, FONT_BYTES, 0)]
    assert leaks(objs_pdf(tmp_path, objs, raw={4})) == FONT_KINDS


def test_object_number_defined_inside_stream_data_counts(tmp_path):  # (c)
    objs = [(4, EMBEDDED, b"6 0 obj\n<< >>\nendobj", 0), (5, DESCRIPTOR, None, 0), (6, FLATE, FONT_BYTES, 0)]
    assert leaks(objs_pdf(tmp_path, objs, raw={4})) == FONT_KINDS


@pytest.mark.parametrize("gens", [(0, 0), (0, 1)])
def test_object_number_defined_twice_exempts_nothing(tmp_path, gens):  # M2, (c)
    objs = [(5, DESCRIPTOR, None, 0), (6, FLATE, FONT_BYTES, gens[0]), (6, FLATE, FONT_BYTES, gens[1])]
    out = cod.scan_file(objs_pdf(tmp_path, objs), "f.pdf", [])
    assert {f.split(":")[0] for f in out} == {"f.pdf!stream1", "f.pdf!stream2"}


def test_descriptor_number_defined_twice_exempts_nothing(tmp_path):  # (b)
    objs = [(5, b"<< /Type /Font >>", None, 0), (5, DESCRIPTOR, None, 0), (6, FLATE, FONT_BYTES, 0)]
    assert leaks(objs_pdf(tmp_path, objs)) == FONT_KINDS


@pytest.mark.parametrize("head", [
    b"<< /Type /FontDescriptor >> % /FontFile2 6 0 R",
    b"<< /Type /FontDescriptor % /FontFile2 6 0 R\n>>",
    b"<< /Type /FontDescriptor /Keywords (see /FontFile2 6 0 R) >>",
    b"<< /Type /FontDescriptor /Keywords (a \\) (b (c)) /FontFile2 6 0 R) >>",
    b"<< /Type /FontDescriptor /Keywords (/A /B /FontFile2 6 0 R) >>",
    b"<< /Type /Annot /FontFile2 6 0 R >>",
    b"<< /Type /Font /FontFile2 6 0 R >>",
    b"<< /FontFile2 6 0 R >>",
    b"<< /Type /FontDescriptor /Style << /FontFile2 6 0 R >> >>",
    b"<< /Type /FontDescriptor /Files [ /FontFile2 6 0 R ] >>",
    b"<< /Type /FontDescriptor /Type /Font /FontFile2 6 0 R >>",
    b"<< /Type /FontDescriptor /FontFile2 6 0 R /FontFile2 7 0 R >>",
    b"<< /Type /FontDescriptor /Note /FontFile2 6 0 R >>",
    b"<< /Type /FontDescriptor /FontFile2 6 0 R",
    b"<< /Type /FontDescriptor /FontFile2 6 0 R >> 7",
    b"[ << /Type /FontDescriptor /FontFile2 6 0 R >> ]",
])
def test_only_a_key_of_a_font_descriptor_dictionary_exempts(tmp_path, head):  # L3, (b)
    assert leaks(objs_pdf(tmp_path, [(5, head, None, 0), (6, FLATE, FONT_BYTES, 0)])) == FONT_KINDS


def test_descriptor_with_a_stream_of_its_own_exempts_nothing(tmp_path):  # (b)
    objs = [(5, DESCRIPTOR, b"x", 0), (6, FLATE, FONT_BYTES, 0)]
    assert leaks(objs_pdf(tmp_path, objs)) == FONT_KINDS


@pytest.mark.parametrize("ref, gen", [(b"6 5 R", 0), (b"6 0 R", 5)])
def test_reference_with_another_generation_exempts_nothing(tmp_path, ref, gen):  # L4, (a)
    objs = [(5, b"<< /Type /FontDescriptor /FontFile2 " + ref + b" >>", None, 0), (6, FLATE, FONT_BYTES, gen)]
    assert leaks(objs_pdf(tmp_path, objs)) == FONT_KINDS


@pytest.mark.parametrize("contents", [b"/Contents 6 0 R", b"/Contents [ 3 0 R 6 0 R ]", b"/Contents\n[6 0 R]"])
def test_page_content_stream_is_never_a_font_program(tmp_path, contents):  # L5, (e)
    objs = [(4, b"<< /Type /Page " + contents + b" >>", None, 0), (5, DESCRIPTOR, None, 0), (6, FLATE, FONT_BYTES, 0)]
    out = cod.scan_file(objs_pdf(tmp_path, objs), "f.pdf", [])
    assert {f.split(": ")[1] for f in out if f.startswith("f.pdf!stream1:")} == FONT_KINDS


def test_contents_naming_another_object_changes_nothing(tmp_path):  # (e)
    objs = [(4, b"<< /Type /Page /Contents [ 7 0 R ] >>", None, 0), (5, DESCRIPTOR, None, 0), (6, FLATE, FONT_BYTES, 0)]
    assert cod.scan_file(objs_pdf(tmp_path, objs), "f.pdf", []) == []


@pytest.mark.parametrize("sig", [b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf", b"\x01\x00\x04\x01",
                                 b"\x01\x00\x04\x02", b"\x01\x00\x04\x04"])
def test_sfnt_and_cff_signatures_are_font_programs(tmp_path, sig):  # (d)
    assert cod.scan_file(font_pdf(tmp_path, stream=sig + FONT_BYTES[4:]), "f.pdf", []) == []


@pytest.mark.parametrize("sig", [b"", b"\x00\x02\x00\x00", b"OTTP", b"TRUE", b"%!PS", b"\x01\x00\x04\x00",
                                 b"\x01\x00\x04\x05", b"\x01\x00\x03\x01", b"\x01\x01\x04\x01", b"\x02\x00\x04\x01",
                                 b"\n\x00\x01\x00\x00", b"ttc"])
def test_stream_without_a_font_signature_is_reported(tmp_path, sig):  # (d)
    assert leaks(font_pdf(tmp_path, stream=sig + FONT_BYTES[4:])) == FONT_KINDS


def test_font_program_stored_without_a_filter_is_exempt(tmp_path):  # (d)
    assert cod.scan_file(objs_pdf(tmp_path, [(5, DESCRIPTOR, None, 0), (6, b"<< >>", FONT_BYTES, 0)], raw={6}),
                         "f.pdf", []) == []


def test_font_program_before_its_descriptor_is_exempt(tmp_path):
    assert cod.scan_file(objs_pdf(tmp_path, [(6, FLATE, FONT_BYTES, 0), (5, DESCRIPTOR, None, 0)]), "f.pdf", []) == []


def test_reference_with_line_breaks_between_its_parts_exempts(tmp_path):  # (a)
    assert cod.scan_file(font_pdf(tmp_path, b"/FontFile3\r\n6\r\n0\r\nR"), "f.pdf", []) == []


@pytest.mark.parametrize("length", [b"/Length1 5", b"/Length 3", b"/Length 99999", b"/Length 9 0 R", b"/Length /N",
                                    b"/Length 1.5", b"/Length 9 0 R /Length 9 0 R"])
def test_stream_without_a_usable_length_exempts_nothing(tmp_path, length):
    objs = [(5, DESCRIPTOR, None, 0), (6, b"<< /Filter /FlateDecode " + length + b" >>", FONT_BYTES, 0),
            (9, b"5", None, 0)]
    assert leaks(objs_pdf(tmp_path, objs)) == FONT_KINDS


def test_indirect_length_is_followed(tmp_path):
    n = len(zlib.compress(FONT_BYTES))
    objs = [(5, DESCRIPTOR, None, 0), (6, b"<< /Filter /FlateDecode /Length 9 0 R >>", FONT_BYTES, 0),
            (9, str(n).encode(), None, 0)]
    assert cod.scan_file(objs_pdf(tmp_path, objs), "f.pdf", []) == []


def test_font_after_an_object_the_layout_does_not_explain_is_not_exempt(tmp_path):
    objs = [(3, b"<< /Length 3 >>", b"junk", 0), (5, DESCRIPTOR, None, 0), (6, FLATE, FONT_BYTES, 0)]
    assert leaks(objs_pdf(tmp_path, objs)) == FONT_KINDS
