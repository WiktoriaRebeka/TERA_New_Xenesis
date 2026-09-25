"""
Translate leftover TERA StrSheet folders that use string= attributes.

Spanish only. One run can take ALL remaining folders in source/.
Region, ZoneName, Creature, Abnormality and sheets with their own Action
are skipped.

Usage:
    python translate_strsheet.py all
    python translate_strsheet.py source/StrSheet_Achievement
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import translate_string_sheet as sheet
import translate_tooltips as item

# Stay English / not shipped / wrong XML shape.
SKIP = {
    "StrSheet_Region",
    "StrSheet_ZoneName",
    "StrSheet_Creature",
    "StrSheet_Abnormality",
    "StrSheet_AbnormalityKind",
    "StrSheet_Species",
    "StrSheet_CollectionLoc",
    "StrSheet_TerritoryLoc",
    "StrSheet_NpcLoc",
    "StrSheet_NpcLocManual",
    "StrSheet_WorkObjectLoc",
    "StrSheet_EventDialog",
}

# Already have a dedicated GitHub Action.
OWN_ACTION = {
    "StrSheet_Item",
    "StrSheet_Npc",
    "StrSheet_Quest",
    "StrSheet_UI",
    "StrSheet_UserSkill",
    "StrSheet_Dungeon",
    "StrSheet_Tutorial",
    "StrSheet_SystemMessage",
    "StrSheet_Passivity",
}

BLOCKED = SKIP | OWN_ACTION

item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG player-facing text from French to Latin American Spanish. The source is French. Write Spanish only. Write HP and MP, never PV or PM.

Translate the visible meaning into natural Latin American Spanish. Keep the tone of high fantasy TERA.
Keep proper names unchanged: NPCs, places, dungeons, items, skills, classes, races and monster names. Place names stay English: Velika, Elleon, Island of Dawn, Oblivion Woods.
Class and race names stay English.
Keep these terms in English: HP, MP, Feedstock, Battle Solution, Prime Battle Solution, Spellbind, Alkahest, Noctenium, Everful Nostrum, Etching, Crystal, Emerald, Diamond, Talent, Focus, Rage, Runemarks, Bravery Potion, Masterwork.
Copy every __TAGn__ placeholder, HTML tag, {@...} tag and {Token} unchanged, same spelling and relative position.
GLOSSARY:
- Keep MP, HP in English. Never PM, PH, mana, PV, PS.
- Endurance is "resistencia". Never "aguante".
- Guild is "gremio". Never "hermandad".
- Latin American Spanish: "tu", never "vosotros". Never "coger". Use "tomar", "agarrar", "recoger" or "conseguir".
- Decimal comma: +1,42 not +1.42.

Do not add explanations. Do not include the French source in your output.
Translate EVERY sentence.
Return ONLY valid JSON: an array of Spanish strings, same length and order as the input array.
""".strip()


def folder_name(input_path: str) -> str:
    return Path(input_path).name


def remaining_folders(source_root: Path) -> list[Path]:
    folders: list[Path] = []
    if not source_root.is_dir():
        return folders
    for path in sorted(source_root.iterdir()):
        if not path.is_dir():
            continue
        if not path.name.lower().startswith("strsheet"):
            continue
        if path.name in BLOCKED:
            continue
        xmls = list(path.glob("*.xml"))
        if xmls:
            folders.append(path)
    return folders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate leftover string= StrSheet folders."
    )
    parser.add_argument(
        "input_path",
        help="all = every leftover folder in source/. Or source/StrSheet_Guild",
    )
    parser.add_argument("-o", "--output-dir", default="")
    parser.add_argument("--cache", default="")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--no-ascii-entities", action="store_true")
    return parser.parse_args()


def run_one(
    folder: Path,
    args: argparse.Namespace,
    file_start: int,
    file_count: int,
) -> int:
    name = folder.name
    if name in BLOCKED:
        print(f"{name} skipped (own Action or stays English).", flush=True)
        return 0
    output_dir = Path(args.output_dir or f"output/{name}")
    slug = re.sub(r"[^A-Za-z0-9]+", "", name).lower()
    cache = Path(args.cache or f"cache/{slug}_translation_cache.json")
    print(f"\n== {name} -> {output_dir} ==", flush=True)
    return sheet.run_sheet(
        folder,
        output_dir,
        cache,
        f"{name}-*.xml",
        args.batch_size if args.batch_size > 0 else 20,
        not args.no_ascii_entities,
        file_start,
        file_count,
    )


def main() -> int:
    args = parse_args()
    raw = args.input_path.strip()
    name = folder_name(raw)
    if name.lower() in {"all", "source"} or raw in {".", "source"}:
        folders = remaining_folders(Path("source"))
        start = max(args.start, 0)
        folders = folders[start:]
        if args.count > 0:
            folders = folders[: args.count]
        if not folders:
            print("No leftover StrSheet folders in source/.", file=sys.stderr)
            return 1
        print(
            f"Translating {len(folders)} folders: "
            + ", ".join(p.name for p in folders),
            flush=True,
        )
        rc = 0
        for folder in folders:
            result = run_one(folder, args, 0, 0)
            if result:
                rc = result
        return rc

    if name in BLOCKED:
        print(f"{name} stays English or has its own Action.", file=sys.stderr)
        return 1
    input_path = Path(raw)
    if not input_path.exists():
        input_path = Path("source") / name
    return run_one(input_path, args, args.start, args.count)


if __name__ == "__main__":
    raise SystemExit(main())
