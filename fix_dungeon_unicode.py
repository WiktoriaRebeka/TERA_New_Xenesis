# -*- coding: utf-8 -*-
"""Decode &# entities → Unicode in output/StrSheet_Dungeon banners.

Dungeon banners use the same color-# rule as UI: numeric &# breaks display.
LIVE SE pack is already Unicode; GitHub output still has &amp;#NNN;.

Also restores EN proper name Elleon (never Élion / Elion).

Does NOT touch StrSheet_Dungeon-00000 instance names beyond entity decode
(those stay English ASCII).

Usage:
  python fix_dungeon_unicode.py
  python fix_dungeon_unicode.py --ci
  python fix_dungeon_unicode.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "StrSheet_Dungeon"

ENTITY_RE = re.compile(r"&amp;#(\d+);|&#(\d+);")
ELION_RE = re.compile(r"(?<![A-Za-zÀ-ÿ])[EÉ]lion(?![A-Za-zÀ-ÿ])")


def decode_entities(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        code = int(m.group(1) or m.group(2))
        if code >= 128:
            return chr(code)
        return m.group(0)

    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = ENTITY_RE.sub(repl, cur)
    return cur


def fix_text(text: str) -> tuple[str, int]:
    n_ent = text.count("&amp;#") + len(re.findall(r"(?<!&amp;)&#\d+;", text))
    new = decode_entities(text)
    new2, n_elion = ELION_RE.subn("Elleon", new)
    # count how many entity replacements roughly happened
    changed = 0 if new2 == text else max(n_ent, 1) + n_elion
    return new2, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=OUT)
    ap.add_argument("--ci", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = OUT if args.ci else args.root
    print(f"Fix Dungeon Unicode in: {root}", flush=True)
    if not root.is_dir():
        print(f"MISSING: {root}", flush=True)
        return 1
    files_n = 0
    total = 0
    for path in sorted(root.glob("*.xml*")):
        if path.name.endswith(".xsd"):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if "&amp;#" not in raw and "&#" not in raw and not ELION_RE.search(raw):
            continue
        new, n = fix_text(raw)
        if new == raw:
            continue
        files_n += 1
        total += n
        if not args.dry_run:
            path.write_text(new, encoding="utf-8", newline="\n")
        print(f"  {path.name}: ~{n}", flush=True)
    print(f"files={files_n} replacements~={total} dry_run={args.dry_run}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
