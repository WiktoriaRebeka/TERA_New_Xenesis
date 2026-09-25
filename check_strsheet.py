"""Quality check for generic string= sheets. Flags [EN]/[ES] and French-only letters."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from translate_strsheet import BLOCKED, remaining_folders

FR = re.compile(r"[àèêëîïôûœçÀÈÊËÎÏÔÛŒÇ]")
ATTR = re.compile(r'\bstring="([^"]*)"')


def dec(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = html.unescape(text)
    return text


def check_root(root: Path) -> tuple[int, int]:
    if not root.exists():
        print(f"Output not found yet: {root}")
        return 0, 0
    files = sorted(root.glob("*.xml")) if root.is_dir() else [root]
    problems = 0
    strings = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in ATTR.finditer(text):
            strings += 1
            plain = dec(match.group(1))
            if "[EN]" in plain or "[ES]" in plain or FR.search(plain):
                problems += 1
                if problems <= 20:
                    print(f"{path}: {plain[:140]}")
    return strings, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("translated")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check every leftover folder under output/",
    )
    args = parser.parse_args()
    root = Path(args.translated)
    all_mode = args.all or args.translated in {"output", "all", "source"}
    total_s = total_p = 0
    if all_mode:
        folders = remaining_folders(Path("source"))
        if not folders:
            print("No leftover folders to check.")
            return 0
        for folder in folders:
            out = Path("output") / folder.name
            strings, problems = check_root(out)
            print(f"{folder.name}: strings={strings} flagged={problems}")
            total_s += strings
            total_p += problems
        print(f"TOTAL strings={total_s} flagged={total_p}")
        return 1 if total_p else 0

    strings, problems = check_root(root)
    print(f"strings={strings} flagged={problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
