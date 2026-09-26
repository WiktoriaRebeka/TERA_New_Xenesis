"""Flag leftover French in extra attrs (tooltip/msg/desc, not string=)."""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from translate_extra import EXTRA_ATTRS, NAME_FOLDERS, remaining_folders

FR = re.compile(r"[àèêëîïôûœçÀÈÊËÎÏÔÛŒÇ]")
ATTR = re.compile(
    r"\b(" + "|".join(EXTRA_ATTRS + ("name",)) + r')="([^"]*)"'
)


def dec(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = html.unescape(text)
    return text


def check_root(root: Path, include_name: bool) -> tuple[int, int]:
    if not root.exists():
        print(f"Output not found yet: {root}")
        return 0, 0
    files = sorted(root.glob("*.xml")) if root.is_dir() else [root]
    problems = 0
    strings = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in ATTR.finditer(text):
            attr, value = match.group(1), match.group(2)
            if attr == "name" and not include_name:
                continue
            if not value:
                continue
            strings += 1
            plain = dec(value)
            if "[EN]" in plain or "[ES]" in plain or FR.search(plain):
                problems += 1
                if problems <= 15:
                    print(f"{path.name} {attr}: {plain[:140]}")
    return strings, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("translated", nargs="?", default="output")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    all_mode = args.all or args.translated in {"output", "all", "source"}
    total_s = total_p = 0
    if all_mode:
        folders = remaining_folders(Path("source"))
        for folder in folders:
            out = Path("output") / folder.name
            strings, problems = check_root(out, folder.name in NAME_FOLDERS)
            if strings or problems:
                print(f"{folder.name}: extra={strings} flagged={problems}")
            total_s += strings
            total_p += problems
        print(f"TOTAL extra={total_s} flagged={total_p}")
        return 1 if total_p else 0
    root = Path(args.translated)
    include = root.name in NAME_FOLDERS
    strings, problems = check_root(root, include)
    print(f"extra={strings} flagged={problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
