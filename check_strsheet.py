"""Quality check for a generic string= sheet. Flags [EN]/[ES] and French-only letters."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

FR = re.compile(r"[àèêëîïôûœçÀÈÊËÎÏÔÛŒÇ]")
ATTR = re.compile(r'\bstring="([^"]*)"')


def dec(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = html.unescape(text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("translated")
    args = parser.parse_args()
    root = Path(args.translated)
    if not root.exists():
        print(f"Output not found yet: {root}")
        return 0
    files = sorted(root.glob("*.xml")) if root.is_dir() else [root]
    problems = 0
    strings = 0
    for path in files:
        for match in ATTR.finditer(path.read_text(encoding="utf-8")):
            strings += 1
            plain = dec(match.group(1))
            if "[EN]" in plain or "[ES]" in plain or FR.search(plain):
                problems += 1
                if problems <= 20:
                    print(f"{path.name}: {plain[:140]}")
    print(f"strings={strings} flagged={problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
