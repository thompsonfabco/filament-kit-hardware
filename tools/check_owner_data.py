"""Scan the repository's tracked files for owner data before a push.

Generic patterns catch private network addresses, local hostnames, email addresses and printer-serial-like strings.
Owner-specific words (names, hostnames, account ids) can't be listed in a committed file, so they are read from
`tools/owner-terms.local`, one per line, which git ignores. Exit status 1 means something was found.

    python -I tools/check_owner_data.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

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


def tracked() -> list[pathlib.Path]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout
    return [ROOT / line for line in out.splitlines() if line]


def terms() -> list[str]:
    if not TERMS.exists():
        return []
    return [w.strip() for w in TERMS.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]


def main() -> int:
    words = terms()
    found = 0
    for path in tracked():
        if path == TERMS:
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        rel = path.relative_to(ROOT).as_posix()
        for n, line in enumerate(text.splitlines(), 1):
            for why, rx in PATTERNS.items():
                for m in rx.finditer(line):
                    if not any(a in m.group(0) for a in ALLOWED):
                        print(f"{rel}:{n}: {why}: {m.group(0)}")
                        found += 1
            low = line.lower()
            for w in words:
                if w.lower() in low:
                    print(f"{rel}:{n}: owner term #{words.index(w) + 1}")
                    found += 1
    if not words:
        print("note: tools/owner-terms.local is missing, so owner-specific words were not checked", file=sys.stderr)
    print(f"{found} finding(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
