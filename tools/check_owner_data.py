"""Scan the repository's tracked files for owner data before a push.

Generic patterns catch private network addresses, local hostnames, email addresses and printer-serial-like strings.
Owner-specific words (names, hostnames, account ids) can't be listed in a committed file, so they are read from
`tools/owner-terms.local`, one per line, which git ignores. Zip-based files (.FCStd, .3mf, .zip) are opened and each
text member is scanned too, since authors' names and emails hide in their compressed metadata; XML character entities
are decoded first (archive members and .xml, .svg, .model files) so `&lt;` and `&#64;` can't hide an address. Findings
inside an archive read `path!member:line`; an archive that can't be read is itself a finding. Exit status 1 means
something was found.

    python -I tools/check_owner_data.py
"""
from __future__ import annotations

import pathlib
import html
import re
import subprocess
import sys
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


def tracked() -> list[pathlib.Path]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout
    return [ROOT / line for line in out.splitlines() if line]


def read_terms(path: pathlib.Path = TERMS) -> list[str]:
    if not path.exists():
        return []
    return [w.strip() for w in path.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]


def scan_text(label: str, text: str, words: list[str]) -> list[str]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for why, rx in PATTERNS.items():
            for m in rx.finditer(line):
                if not any(a in m.group(0) for a in ALLOWED):
                    out.append(f"{label}:{n}: {why}: {m.group(0)}")
        low = line.lower()
        for w in words:
            if w.lower() in low:
                out.append(f"{label}:{n}: owner term #{words.index(w) + 1}")
    return out


def scan_archive(path: pathlib.Path, rel: str, words: list[str]) -> list[str]:
    out = []
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir() or info.file_size > MAX_MEMBER:
                    continue
                data = z.read(info)
                if b"\x00" in data[:8192]:
                    continue
                text = html.unescape(data.decode("utf-8", errors="replace"))
                out += scan_text(f"{rel}!{info.filename}", text, words)
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError, OSError):
        return [f"{rel}: cannot read archive"]
    return out


def scan_file(path: pathlib.Path, rel: str, words: list[str]) -> list[str]:
    if zipfile.is_zipfile(path):
        return scan_archive(path, rel, words)
    text = path.read_bytes().decode("utf-8", errors="replace")
    if path.suffix.lower() in ENTITY_SUFFIXES:
        text = html.unescape(text)
    return scan_text(rel, text, words)


def main() -> int:
    words = read_terms()
    found = 0
    for path in tracked():
        if path == TERMS:
            continue
        for line in scan_file(path, path.relative_to(ROOT).as_posix(), words):
            print(line)
            found += 1
    if not words:
        print("note: tools/owner-terms.local is missing, so owner-specific words were not checked", file=sys.stderr)
    print(f"{found} finding(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
