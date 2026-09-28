# -*- coding: utf-8 -*-
"""QA scan (report only): krzaki + proper-name gaps in quests.

Does NOT edit the pack. Writes TSV reports under cache/qa_*.

Priority sheets only (not all 616 DataCenter folders):
  - encoding: WorkObject, UI, NPC, BuyMenu, Creature nameplate-ish
  - quests: StrSheet_Quest (+ optional QuestDialog sample)

Usage:
  python qa_pack_issues.py
  python qa_pack_issues.py --root \"C:/.../FRA TRANSLATED DATABASE/DataCenter_Final_EUR\"
  python qa_pack_issues.py --ci   # scan repo output/
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
LIVE = Path(r"C:\Users\wikto\Desktop\FRA TRANSLATED DATABASE\DataCenter_Final_EUR")
CACHE = ROOT / "cache"
CREATURE_NAMES = CACHE / "en_creature_names.txt"

# UI/world labels: numeric &# breaks because # = color in TERA
UNICODE_SHEETS = (
    "StrSheet_WorkObject",
    "StrSheet_UI",
    "StrSheet_Npc",
    "StrSheet_BuyMenu",
    "StrSheet_ZoneName",
    "StrSheet_Region",
)

# Quest objectives / titles — proper names matter most here
QUEST_SHEETS = ("StrSheet_Quest",)

ENTITY_RAW = re.compile(r"(?:&amp;)?#(\d{2,6});")
REPLACEMENT = "\ufffd"
# typical mojibake / broken UTF-8 leftovers
MOJIBAKE = re.compile(
    r"(?:Ã.|Â.|â€™|â€œ|â€|ðŸ|Ã¡|Ã©|Ã­|Ã³|Ãº|Ã±|Â¿|Â¡)"
)
# Spanish animal calques that often hide EN creature names in objectives
CALQUE_HINTS = re.compile(
    r"\b(?:"
    r"jabal[ií](?:es)?|jabalíes|"
    r"depredador(?:es)?|"
    r"revolucionari[oa]s?|"
    r"vulcano?s?|volcanes|"
    r"sabueso?s?|"
    r"ladr[oó]n(?:es)?|"
    r"guerrero?s?|"
    r"explorador(?:es)?|"
    r"bandido?s?|"
    r"saqueador(?:es)?"
    r")\b",
    re.I,
)
COMBAT_ES = re.compile(
    r"^(?:Elimina|Derrota|Mata|Caza|Destruye|Acaba con)\b",
    re.I,
)
ATTR = re.compile(r'\b(id|string|name|toolTip)="([^"]*)"')
STRING_LINE = re.compile(r"<String\b", re.I)


def log(msg: str) -> None:
    print(msg, flush=True)


def resolve_root(ci: bool, root: Path | None) -> Path:
    if root is not None:
        return root
    if ci:
        return ROOT / "output"
    if LIVE.is_dir():
        return LIVE
    out = ROOT / "output"
    if out.is_dir():
        return out
    raise SystemExit("No pack root found (pass --root or use --ci with output/)")


def iter_xml(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.xml*"))


def load_creature_names() -> set[str]:
    if not CREATURE_NAMES.is_file():
        return set()
    names: set[str] = set()
    for line in CREATURE_NAMES.read_text(encoding="utf-8", errors="replace").splitlines():
        n = line.strip()
        if n and not n.startswith("#"):
            names.add(n)
    return names


def scan_encoding(pack: Path, out_tsv: Path) -> int:
    rows: list[str] = ["sheet\tfile\tid\tkind\tsnippet"]
    count = 0
    for sheet in UNICODE_SHEETS:
        for path in iter_xml(pack / sheet):
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if not STRING_LINE.search(line) and 'name="' not in line:
                    continue
                attrs = dict(ATTR.findall(line))
                blob = attrs.get("string") or attrs.get("name") or attrs.get("toolTip") or ""
                if not blob:
                    continue
                kinds: list[str] = []
                if ENTITY_RAW.search(blob):
                    kinds.append("numeric_entity")
                if REPLACEMENT in blob:
                    kinds.append("replacement_char")
                if MOJIBAKE.search(blob):
                    kinds.append("mojibake")
                if not kinds:
                    continue
                iid = attrs.get("id", f"line{i}")
                snip = blob[:140].replace("\t", " ")
                rows.append(
                    f"{sheet}\t{path.name}\t{iid}\t{'+'.join(kinds)}\t{snip}"
                )
                count += 1
    out_tsv.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return count


def scan_quest_proper_names(
    pack: Path, out_tsv: Path, creatures: set[str], sheets: tuple[str, ...]
) -> int:
    """Flag combat-like ES lines that look like they lost EN creature names."""
    rows: list[str] = ["sheet\tfile\tid\treason\tstring"]
    count = 0
    creature_list = sorted(creatures, key=len, reverse=True) if creatures else []

    for sheet in sheets:
        for path in iter_xml(pack / sheet):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if not STRING_LINE.search(line):
                    continue
                attrs = dict(ATTR.findall(line))
                s = attrs.get("string", "")
                if not s:
                    continue
                plain = (
                    s.replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&amp;", "&")
                    .replace("<br>", " ")
                    .replace("<BR>", " ")
                )
                plain = re.sub(r"<[^>]+>", "", plain)
                plain = re.sub(r"\{@[^}]+\}", " ", plain)
                plain = re.sub(r"\s+", " ", plain).strip()
                if len(plain) < 8 or len(plain) > 180:
                    continue
                if not COMBAT_ES.search(plain):
                    continue

                reasons: list[str] = []
                if ENTITY_RAW.search(s) or MOJIBAKE.search(s) or REPLACEMENT in s:
                    reasons.append("garble")
                if CALQUE_HINTS.search(plain):
                    has_en = (
                        any(c in plain for c in creature_list[:5000])
                        if creature_list
                        else False
                    )
                    if not has_en:
                        reasons.append("calque_no_en_creature")
                if not reasons:
                    continue
                iid = attrs.get("id", "")
                rows.append(
                    f"{sheet}\t{path.name}\t{iid}\t{'+'.join(reasons)}\t{plain[:160]}"
                )
                count += 1
    out_tsv.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="Report-only QA for pack issues")
    ap.add_argument("--root", type=Path, default=None, help="Pack root to scan")
    ap.add_argument("--ci", action="store_true", help="Scan repo output/")
    ap.add_argument(
        "--with-questdialog",
        action="store_true",
        help="Also scan QuestDialog (slower; off by default)",
    )
    args = ap.parse_args()

    pack = resolve_root(args.ci, args.root)
    CACHE.mkdir(parents=True, exist_ok=True)
    log(f"QA root: {pack}")

    quest_sheets: tuple[str, ...] = QUEST_SHEETS
    if args.with_questdialog:
        quest_sheets = ("StrSheet_Quest", "QuestDialog")

    creatures = load_creature_names()
    log(f"EN creature names loaded: {len(creatures)}")

    enc_tsv = CACHE / "qa_encoding_garble.tsv"
    quest_tsv = CACHE / "qa_quest_proper_names.tsv"

    n_enc = scan_encoding(pack, enc_tsv)
    n_quest = scan_quest_proper_names(pack, quest_tsv, creatures, quest_sheets)

    log(f"encoding/garble hits: {n_enc} -> {enc_tsv}")
    log(f"quest proper-name suspects: {n_quest} -> {quest_tsv}")
    log("Report only — no files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
