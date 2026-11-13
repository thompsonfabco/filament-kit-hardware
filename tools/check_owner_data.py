"""Scan the repository's tracked files for owner data before a push.

Generic patterns catch private network addresses, local hostnames, email addresses and printer-serial-like strings.
Owner-specific words (names, hostnames, account ids) can't be listed in a committed file, so they are read from
`tools/owner-terms.local`, one per line, which git ignores. Zip-based files (.FCStd, .3mf, .zip) are opened and each
text member is scanned too, since authors' names and emails hide in their compressed metadata; XML character entities
are decoded per line before matching (archive members and .xml, .svg, .model files) so `&lt;` and `&#64;` can't hide
an address. Member names are scanned too; FreeCAD geometry members (.Map.txt, .brp, .brep) are skipped because their
topological-naming strings look like IP addresses. Findings inside an archive read `path!member:line`. An archive that
can't be read (or a file with an archive extension that isn't a readable zip) and a member too large to scan are
findings. A listed path that is missing or a dangling symlink is a finding; a symlink's target text is
scanned too. PDFs are scanned as their uncompressed parts (metadata) plus each FlateDecode stream inflated, since random
bytes in compressed data look like addresses; a stream that won't inflate is scanned raw. The text a PDF page draws is
scanned as well: KiCad writes it as Type3 glyph codes, so the Tj/TJ strings are mapped through each font's ToUnicode
CMap (a font with no map is read as Latin-1; findings read `path!textN:line`, N being the page content object; only
owner terms, email addresses and Windows user paths are checked in it, since neighbouring words run together; terms
are also matched with whitespace removed). Exit status 1 means something was found.

The project's public account name, when it is one of the terms, is excused only where it forms the account part of
its own github.com and ko-fi.com links (or the bare owner/repo form tools use), or is the holder in a copyright notice
(a marker "(c)", the copyright sign or "Copyright" with an optional "(c)" or sign, one year or a range or list of
years, then the name, with spaces or tabs between); everywhere else it is a hit like any other owner term. The
allowance applies to that one term only: every other term, including a part of the account name, is matched exactly as
without it. The forms are matched on text lower-cased for A-Z only, and a link form with whitespace inside is none;
a mention split over PDF text runs is excused only as part of a link form, never as a notice.

Environment: FK_OWNER_BANS names an extra terms file (one term per line, or a JSON object whose `plain`, `code_plain`
and `ota_plain` lists hold terms) used in addition to `tools/owner-terms.local`; A terms file that is
named but missing, unreadable, malformed or empty makes the scan exit 2 (the message names the path and the reason,
never a term). FK_REQUIRE_OWNER_BANS=1 also needs at least one term from FK_OWNER_BANS (when set) or else from
`tools/owner-terms.local`. Neither set and no local file: only a note, generic patterns still run.

    python -I tools/check_owner_data.py
"""
from __future__ import annotations

import codecs
import html
import json
import os
import pathlib
import re
import string
import subprocess
import sys
import unicodedata
import zipfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TERMS = ROOT / "tools" / "owner-terms.local"

PATTERNS = {
    "private IPv4 address": re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
                                       r"|\b192\.168\.\d{1,3}\.\d{1,3}\b"
                                       r"|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"),
    "local hostname": re.compile(r"\b[\w-]+\.(?:local|lan|home|internal)\b", re.I),
    "email address": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "printer-serial-like string": re.compile(r"\b(?=[0-9A-Z]*\d)(?=[0-9A-Z]*[A-Z])[0-9A-Z]{15}\b"),
    "Windows user path": re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+", re.I),
}
ALLOWED = {"example.com", "example.net", "example.org",  # documentation domains
           "owner-terms.local"}  # a file name, not a host
MAX_MEMBER = 20 * 1024 * 1024  # archive members larger than this (uncompressed) are skipped
ENTITY_SUFFIXES = {".xml", ".svg", ".model"}
ARCHIVE_SUFFIXES = {".fcstd", ".3mf", ".zip"}
GEOMETRY_SUFFIXES = (".map.txt", ".brp", ".brep")  # FreeCAD shape data, not metadata
PDF_STREAM = re.compile(rb"(?<!end)stream\r?\n(.*?)\r?\n?endstream", re.S)
PDF_OBJECT = re.compile(rb"(?<!\d)(\d+)\s+\d+\s+obj\b(.*?)endobj", re.S)
PDF_REF = rb"(\d+)\s+\d+\s+R"
DRAWN_PATTERNS = ("email address", "Windows user path")  # generic patterns applied to decoded PDF text
BAN_KEYS = ("plain", "code_plain", "ota_plain")  # string lists in the JSON form of a bans file
# The project's public account name, allowed only as the account part of these link forms (host/account, or the bare
# account/repo form tools use). Hosts are matched whole (github.com, www.github.com, ko-fi.com; no subdomain).
PUBLIC_ACCOUNT_LINKS = ("github.com/thompsonfabco", "www.github.com/thompsonfabco", "ko-fi.com/thompsonfabco",
                        "thompsonfabco/filament-kit", "thompsonfabco/filament-library")
PUBLIC_ACCOUNT = PUBLIC_ACCOUNT_LINKS[0].split("/", 1)[1]
HOST_BEFORE = "_.-"  # with letters, digits and combining marks: what makes a host part of a longer name
BARE_BEFORE = "\"'([<`"  # with whitespace: the only characters (besides the line start) that may precede the bare form
NAME_END = ")]}>\"',;:!?#/`"  # with whitespace: what may follow the account name in a host form
DOT_END = ")]}>\"'`"  # with whitespace: what may follow a full stop that follows the account name
ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)  # no str.lower(): U+212A is not a k here
# A copyright notice naming the account as holder: "(c) 2026 name", "copyright 2024-2026 name", or with the sign in
# place of "(c)" ("copyright (c) 2026 name" is the "(c)" form after a space). Matched on one line of ASCII-lowered
# text; the name ends as in a host form except that "/", "?" and "#" straight after it are hits.
YEAR = r"(?:19|20)[0-9]{2}"
NOTICE_END = re.escape("".join(c for c in NAME_END if c not in "/?#"))
NOTICE = re.compile(
    r"(?<![^\s\"'(\[<`])(?:\(c\)|\u00a9|copyright)"  # marker after line start or one of these
    rf"[ \t]+{YEAR}(?:[-\u2013]{YEAR}|, {YEAR})*[ \t]+"
    + rf"({re.escape(PUBLIC_ACCOUNT)})(?=\Z|[\s{NOTICE_END}]|\.(?:\Z|[\s{re.escape(DOT_END)}]))")


def tracked() -> list[pathlib.Path]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout
    return [ROOT / line for line in out.splitlines() if line]


def read_terms(path: pathlib.Path = TERMS) -> list[str]:
    """Usable terms in a terms file; a ValueError says why the file can't be used (never quoting its content)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ValueError("file does not exist") from None
    except OSError:
        raise ValueError("file cannot be read") from None
    except UnicodeDecodeError:
        raise ValueError("file is not valid UTF-8") from None
    if text.lstrip().startswith("{"):  # structured bans file: only its plain-text lists can be matched here
        try:
            data = json.loads(text)
        except ValueError:
            raise ValueError("file is not valid JSON") from None
        if not isinstance(data, dict) or any(k in data and not isinstance(data[k], list) for k in BAN_KEYS):
            raise ValueError("JSON file does not have the expected lists")
        return [w.strip() for k in BAN_KEYS for w in data.get(k, []) if isinstance(w, str) and w.strip()]
    return [w.strip() for w in text.splitlines() if w.strip() and not w.startswith("#")]


def load_terms() -> tuple[list[str], str | None]:
    """Terms from the local file and from FK_OWNER_BANS, and the first problem with a file that should be used.

    The local file is used when it exists; FK_OWNER_BANS must exist, parse and hold at least one term. With
    FK_REQUIRE_OWNER_BANS=1 the file that must hold a term is FK_OWNER_BANS when set, else the local file."""
    words: list[str] = []
    problem = None
    bans = os.environ.get("FK_OWNER_BANS")
    required = os.environ.get("FK_REQUIRE_OWNER_BANS") == "1"
    paths = [(TERMS, False)] if TERMS.exists() else []
    if bans:
        paths.append((pathlib.Path(bans), True))
    elif required and not paths:
        problem = "FK_REQUIRE_OWNER_BANS=1 but there is no terms file (tools/owner-terms.local or FK_OWNER_BANS)"
    for p, must_have_terms in paths:
        try:
            got = read_terms(p)
        except ValueError as e:
            problem = problem or f"terms file {p} cannot be used: {e}"
            continue
        if not got and (must_have_terms or required):
            problem = problem or f"terms file {p} cannot be used: it holds no terms"
        words += [w for w in got if w not in words]
    return words, problem


def glue(runs: list[str]) -> tuple[str, list[bool], list[int]]:
    """The runs joined with nothing between them and whitespace removed; for each index (and the end) whether whitespace
    was dropped just before it; and for each character the run it came from."""
    kept, gap, run_of, pending = [], [], [], True
    for r, text in enumerate(runs):
        for c in text:
            if c.isspace():
                pending = True
                continue
            kept.append(c)
            gap.append(pending)
            run_of.append(r)
            pending = False
    gap.append(pending)
    return "".join(kept), gap, run_of


def account_starts(low: str, gap: list[bool]) -> set[int]:
    """Indexes where the public account name starts inside an allowed link form, in text lower-cased for A-Z only (`gap`
    marks where whitespace was dropped, see glue; it counts as a boundary like the start or end of the line, but a form
    with whitespace dropped inside it is not a form)."""
    def host_ok(i: int, end: int) -> bool:  # host starting at i, name ending at end
        before = low[i - 1] if i and not gap[i] else ""
        if before and (before.isalnum() or before in HOST_BEFORE or unicodedata.category(before).startswith("M")):
            return False
        if end >= len(low) or gap[end] or low[end].isspace() or low[end] in NAME_END:
            return True
        return low[end] == "." and (end + 1 >= len(low) or gap[end + 1] or low[end + 1].isspace()
                                    or low[end + 1] in DOT_END)

    def bare_ok(i: int) -> bool:
        return i == 0 or gap[i] or low[i - 1].isspace() or low[i - 1] in BARE_BEFORE

    starts = set()
    for link in PUBLIC_ACCOUNT_LINKS:
        host = "." in link.split("/", 1)[0]
        offset = link.index("/") + 1 if host else 0
        i = low.find(link)
        while i >= 0:
            end = i + offset + len(PUBLIC_ACCOUNT)
            if (host_ok(i, end) if host else bare_ok(i)) and not any(gap[i + 1:i + len(link)]):
                starts.add(i + offset)
            i = low.find(link, i + 1)
    return starts


def only_in_links(text: str) -> bool:
    """Whether the public account name occurs in text, and every time as the account part of an allowed link form or
    as the holder in a copyright notice."""
    low = text.translate(ASCII_LOWER)
    starts = account_starts(low, [False] * (len(low) + 1)) | {m.start(1) for m in NOTICE.finditer(low)}
    i = low.find(PUBLIC_ACCOUNT)
    if i < 0:
        return False
    while i >= 0:
        if i not in starts:
            return False
        i = low.find(PUBLIC_ACCOUNT, i + 1)
    return True


def split_mentions_in_links(runs: list[str]) -> bool | None:
    """Whether every mention of the public account name that the per-run scan did not judge (it crosses a run edge, or
    whitespace was dropped inside it) is the account part of an allowed link form in the runs glued together; None when
    the glued text holds no mention at all. A mention inside one run is the per-run scan's to judge."""
    compact, gap, run_of = glue(runs)
    low = compact.translate(ASCII_LOWER)
    starts = account_starts(low, gap)
    last = len(PUBLIC_ACCOUNT) - 1
    i = low.find(PUBLIC_ACCOUNT)
    if i < 0:
        return None
    while i >= 0:
        whole = run_of[i] == run_of[i + last] and not any(gap[i + 1:i + last + 1])
        if not whole and i not in starts:
            return False
        i = low.find(PUBLIC_ACCOUNT, i + 1)
    return True


def scan_text(label: str, text: str, words: list[str], unescape: bool = False,
              patterns: tuple[str, ...] | None = None) -> list[str]:
    out = []
    lowered = [w.lower() for w in words]
    for n, line in enumerate(text.splitlines(), 1):
        if unescape:
            line = html.unescape(line)
        for why, rx in PATTERNS.items():
            if patterns is not None and why not in patterns:
                continue
            for m in rx.finditer(line):
                if not any(a in m.group(0) for a in ALLOWED):
                    out.append(f"{label}:{n}: {why}: {m.group(0)}")
        low = line.lower()
        for w, lw in zip(words, lowered):
            if lw in low and not (lw == PUBLIC_ACCOUNT and only_in_links(line)):
                out.append(f"{label}:{n}: owner term #{words.index(w) + 1}")
    return out


def scan_archive(path: pathlib.Path, rel: str, words: list[str]) -> list[str]:
    out = []
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                label = f"{rel}!{info.filename}"
                out += scan_text(label, info.filename, words, unescape=True)
                if info.is_dir() or info.filename.lower().endswith(GEOMETRY_SUFFIXES):
                    continue
                if info.file_size > MAX_MEMBER:
                    out.append(f"{label}: skipped, too large")
                    continue
                data = z.read(info)
                if data[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
                    text = data.decode("utf-16", errors="replace")
                elif b"\x00" in data[:8192]:
                    continue
                else:
                    text = data.decode("utf-8", errors="replace")
                out += scan_text(label, text, words, unescape=True)
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError, OSError):
        return [f"{rel}: cannot read archive"]
    return out


def scan_file(path: pathlib.Path, rel: str, words: list[str]) -> list[str]:
    if zipfile.is_zipfile(path):
        return scan_archive(path, rel, words)
    if path.suffix.lower() in ARCHIVE_SUFFIXES:
        return [f"{rel}: cannot read archive"]
    if path.suffix.lower() == ".pdf":
        return scan_pdf(path.read_bytes(), rel, words)
    text = path.read_bytes().decode("utf-8", errors="replace")
    return scan_text(rel, text, words, unescape=path.suffix.lower() in ENTITY_SUFFIXES)


def pdf_inflate(raw: bytes) -> bytes:
    try:
        return zlib.decompressobj().decompress(raw)
    except zlib.error:
        return raw


def balanced_dict(data: bytes) -> bytes:
    """The first `<< ... >>` in data, nested dictionaries included."""
    i = data.find(b"<<")
    if i < 0:
        return b""
    depth, j = 0, i
    while j < len(data) - 1:
        pair = data[j:j + 2]
        if pair == b"<<":
            depth, j = depth + 1, j + 2
        elif pair == b">>":
            depth, j = depth - 1, j + 2
            if depth == 0:
                return data[i:j]
        else:
            j += 1
    return data[i:]


def cmap_text(token: bytes) -> str:
    digits = re.sub(rb"[^0-9A-Fa-f]", b"", token).decode()
    return bytes.fromhex(digits + "0" * (len(digits) % 2)).decode("utf-16-be", errors="replace")


def parse_cmap(cmap: bytes) -> tuple[int, dict[int, str]]:
    """Code width in bytes and code -> text from a ToUnicode CMap (bfchar and bfrange)."""
    width, table = 1, {}
    m = re.search(rb"begincodespacerange\s*<([0-9A-Fa-f]+)>", cmap)
    if m:
        width = max(1, len(m.group(1)) // 2)
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", cmap, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f\s]*)>", block):
            table[int(src, 16)] = cmap_text(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", cmap, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f\s]*>|\[[^\]]*\])", block):
            lo, hi = int(lo, 16), int(hi, 16)
            if hi < lo or hi - lo > 0xFFFF:
                continue
            if dst.startswith(b"["):
                for code, item in zip(range(lo, hi + 1), re.findall(rb"<[0-9A-Fa-f\s]*>", dst)):
                    table[code] = cmap_text(item)
            else:
                base = cmap_text(dst)
                for k, code in enumerate(range(lo, hi + 1)):
                    table[code] = base[:-1] + chr(ord(base[-1]) + k) if base else ""
    return width, table


PDF_ESCAPES = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
PDF_TOKEN = re.compile(rb"/[^\s/<>\[\]()%]*|\(|<<|>>|<[0-9A-Fa-f\s]*>|\[|\]|%[^\r\n]*|[^\s/<>\[\]()%]+")


def pdf_literal(data: bytes, i: int) -> tuple[bytes, int]:
    """The literal string whose `(` is at data[i], and the index after its `)`."""
    out, depth = bytearray(), 1
    i += 1
    while i < len(data) and depth:
        c = data[i]
        if c == 0x5C and i + 1 < len(data):  # backslash
            i += 1
            c = data[i]
            if 0x30 <= c <= 0x37:
                j = i
                while j < len(data) and j < i + 3 and 0x30 <= data[j] <= 0x37:
                    j += 1
                out.append(int(data[i:j], 8) & 0xFF)
                i = j
                continue
            if c == 13 and data[i + 1:i + 2] == b"\n":  # line continuation
                i += 1
            elif c not in (10, 13):
                out.append(PDF_ESCAPES.get(c, c))
        elif c == 0x28:
            depth += 1
            out.append(c)
        elif c == 0x29:
            depth -= 1
            if depth:
                out.append(c)
        else:
            out.append(c)
        i += 1
    return bytes(out), i


def content_text(content: bytes, fonts: dict) -> list[str]:
    """The text a content stream draws, in drawing order, one entry per run in the same font (KiCad draws each
    word in a font of its own)."""
    runs, cur, font, name = [], [], None, b""
    strings: list[bytes] = []  # string operands since the last operator

    def show(raw: bytes):
        width, table = fonts.get(font) or (1, None)
        if table is None:  # no ToUnicode map: take the bytes as Latin-1, dropping control codes
            if text := "".join(c for c in raw.decode("latin-1") if c.isprintable()):
                cur.append(text)
            return
        for k in range(0, len(raw) - width + 1, width):
            cur.append(table.get(int.from_bytes(raw[k:k + width], "big"), ""))

    pos = 0
    while True:
        m = PDF_TOKEN.search(content, pos)
        if not m:
            break
        tok, pos = m.group(0), m.end()
        if tok == b"(":
            raw, pos = pdf_literal(content, m.start())
            strings.append(raw)
        elif tok[:1] == b"<" and tok != b"<<":
            hexed = re.sub(rb"\s", b"", tok[1:-1])
            strings.append(bytes.fromhex((hexed + b"0" * (len(hexed) % 2)).decode()))
        elif tok[:1] == b"/":
            name = tok
        elif tok == b"Tf":
            if font != name and cur:
                runs.append("".join(cur))
                cur.clear()
            font = name
            strings.clear()
        elif tok in (b"Tj", b"'", b'"', b"TJ"):
            for raw in strings:
                show(raw)
            strings.clear()
        elif tok[:1].isalpha() or tok in (b"'", b'"'):  # any other operator
            strings.clear()
    return runs + ["".join(cur)] if cur else runs


def pdf_text(data: bytes) -> list[tuple[str, list[str]]]:
    """(label, drawn text runs) for each page content stream, decoded through the page's fonts."""
    objs: dict[int, tuple[bytes, bytes | None]] = {}
    for m in PDF_OBJECT.finditer(data):
        body = m.group(2)
        s = PDF_STREAM.search(body)
        objs[int(m.group(1))] = (body[:s.start()], pdf_inflate(s.group(1))) if s else (body, None)

    cmaps: dict[int, tuple[int, dict[int, str]] | None] = {}

    def font_map(num: int):
        if num not in cmaps:
            cmaps[num] = None
            tu = re.search(rb"/ToUnicode\s+" + PDF_REF, objs.get(num, (b"", None))[0])
            if tu and objs.get(int(tu.group(1)), (b"", None))[1] is not None:
                cmaps[num] = parse_cmap(objs[int(tu.group(1))][1])
        return cmaps[num]

    def font_table(res: bytes) -> dict:
        fonts = {}
        m = re.search(rb"/Font(?![A-Za-z])", res)
        if not m:
            return fonts
        rest = res[m.end():]
        ref = re.match(rb"\s*" + PDF_REF, rest)
        sub = objs.get(int(ref.group(1)), (b"", None))[0] if ref else balanced_dict(rest)
        for fname, num in re.findall(rb"(/[^\s/<>\[\]()]+)\s+" + PDF_REF, sub):
            fm = font_map(int(num))
            if fm:
                fonts[fname] = fm
        return fonts

    every = {}  # every font name seen anywhere, for content streams no page claims
    for head, _ in objs.values():
        every.update(font_table(head))
    out, claimed = [], set()
    for head, _ in objs.values():
        if not re.search(rb"/Type\s*/Page\b", head):
            continue
        r = re.search(rb"/Resources", head)
        rref = re.match(rb"\s*" + PDF_REF, head[r.end():]) if r else None
        fonts = font_table(objs.get(int(rref.group(1)), (b"", None))[0] if rref else head[r.end():] if r else b"")
        c = re.search(rb"/Contents\s*(\[[^\]]*\]|" + PDF_REF + rb")", head)
        for ref in re.findall(PDF_REF, c.group(1)) if c else []:
            num = int(ref)
            if objs.get(num, (b"", None))[1] is not None:
                claimed.add(num)
                out.append((f"text{num}", content_text(objs[num][1], fonts)))
    for num, (_, body) in objs.items():
        if num not in claimed and body is not None and re.search(rb"\bT[jJ]\b", body):
            out.append((f"text{num}", content_text(body, every)))
    return out


def scan_pdf(data: bytes, rel: str, words: list[str]) -> list[str]:
    out = scan_text(rel, PDF_STREAM.sub(b"", data).decode("utf-8", errors="replace"), words)
    for n, m in enumerate(PDF_STREAM.finditer(data), 1):
        out += scan_text(f"{rel}!stream{n}", pdf_inflate(m.group(1)).decode("utf-8", errors="replace"), words)
    seen = {f.split(":", 1)[1] for f in out if "!stream" in f}  # "line: what" already reported from a raw stream
    for label, runs in pdf_text(data):
        drawn = scan_text(f"{rel}!{label}", "\n".join(runs), words, patterns=DRAWN_PATTERNS)
        out += [f for f in drawn if f.split(":", 1)[1] not in seen]
        # a term can span two runs ("First" "Last") or be drawn without its space, so the runs joined are checked
        # for terms alone, whitespace removed on both sides
        joined = re.sub(r"\s+", "", "".join(runs)).lower()
        for n, w in enumerate(words, 1):
            squeezed = re.sub(r"\s+", "", w).lower()
            if not squeezed or squeezed not in joined:
                continue
            covered = any(w.lower() in run.lower() for run in runs)
            if w.lower() == PUBLIC_ACCOUNT:  # a whole mention not in a link is already reported above
                covered = any(f.endswith(f": owner term #{words.index(w) + 1}") for f in drawn)
                if not covered:
                    split = split_mentions_in_links(runs)
                    covered = any(w.lower() in run.lower() for run in runs) if split is None else split
            if not covered:
                out.append(f"{rel}!{label}:joined: owner term #{n}")
    return out


def scan_path(path: pathlib.Path, rel: str, words: list[str]) -> list[str]:
    out = []
    if path.is_symlink():  # the link text is scanned, then the target if it exists
        out += scan_text(rel, os.readlink(path), words)
        if not path.exists():
            return out + [f"{rel}: dangling symlink"]
    elif not path.exists():
        return [f"{rel}: listed but missing"]
    if path.is_dir():  # e.g. an untracked folder; its files are listed separately
        return out
    try:
        return out + scan_file(path, rel, words)
    except OSError:
        return out + [f"{rel}: cannot read file"]


def main() -> int:
    words, problem = load_terms()
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    found = 0
    for path in tracked():
        if path == TERMS:
            continue
        for line in scan_path(path, path.relative_to(ROOT).as_posix(), words):
            print(line)
            found += 1
    if not words:
        print("note: tools/owner-terms.local is missing, so owner-specific words were not checked", file=sys.stderr)
    print(f"{found} finding(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
