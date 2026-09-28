# -*- coding: utf-8 -*-
"""Decode numeric &# entities to Unicode in world/UI-like sheets.

WorkObject / NPC / BuyMenu / UI: TERA treats #NNN as a color code, so
``piedra m&#225;gica`` breaks the floating nameplate. Use real ``mágica``.

Item/Quest parchment tips stay on &amp;#NNN; — this script does NOT touch them.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent

# Sheets where floating/world/UI labels must be Unicode (same rule as StrSheet_UI).
DEFAULT_SHEETS = (
    "StrSheet_WorkObject",
    "StrSheet_Npc",
    "StrSheet_BuyMenu",
    "StrSheet_UI",
)

ENTITY_RE = re.compile(r"&amp;#(\d+);|&#(\d+);")


def decode_entities(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        code = int(m.group(1) or m.group(2))
        if code >= 128:
            return chr(code)
        return m.group(0)

    prev = None
    cur = text
    # double-encoded &amp;amp;#225; etc.
    while prev != cur:
        prev = cur
        cur = ENTITY_RE.sub(repl, cur)
    return cur


def fix_file(path: Path) -> int:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if "&amp;#" not in raw and "&#" not in raw:
        return 0
    new = decode_entities(raw)
    if new == raw:
        return 0
    path.write_text(new, encoding="utf-8", newline="\n")
    return raw.count("&amp;#") + raw.count("&#")


def iter_targets(roots: list[Path], sheets: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        for sheet in sheets:
            d = root / sheet
            if d.is_dir():
                out.extend(sorted(d.glob("*.xml*")))
            # also flat output/StrSheet_UI-00000_Translated.xml style
            out.extend(sorted(root.glob(f"{sheet}*_Translated.xml")))
            out.extend(sorted(root.glob(f"{sheet}*.xml")))
    # dedupe
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in out:
        rp = p.resolve()
        if rp in seen or not p.is_file():
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        action="append",
        type=Path,
        help="Folder to scan (repeatable). Default: output/ + optional pack paths.",
    )
    args = ap.parse_args()
    roots = args.root or [ROOT / "output"]
    # always include known desktop packs when present (local runs)
    for extra in (
        Path(r"C:\Users\wikto\Desktop\FRA TRANSLATED DATABASE\DataCenter_Final_EUR"),
        Path(r"C:\Users\wikto\Desktop\TERA_DATABASE_TRANSLATION"),
        Path(r"C:\Users\wikto\Desktop\TERA_DATABASE_FRA_TRANSLATION"),
    ):
        if extra.exists() and extra not in roots:
            roots.append(extra)

    files = iter_targets(roots, DEFAULT_SHEETS)
    total = 0
    touched = 0
    for path in files:
        n = fix_file(path)
        if n:
            touched += 1
            total += n
            print(f"  fixed {n} entities in {path}", flush=True)
    print(f"Done: {touched} files, ~{total} entity hits", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
