"""
Translate one TERA StrSheet folder that uses string= attributes.

Spanish only. Names of people, places, items, skills, classes and races stay English.
Region, ZoneName, Creature and Abnormality are not translated here.

Usage:
    python translate_strsheet.py StrSheet_Guild
    python translate_strsheet.py source/StrSheet_Guild --start 0 --count 0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import translate_string_sheet as sheet
import translate_tooltips as item

SKIP = {
    "StrSheet_Region",
    "StrSheet_ZoneName",
    "StrSheet_Creature",
    "StrSheet_Abnormality",
    "StrSheet_AbnormalityKind",
}

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate one TERA string= sheet folder.")
    parser.add_argument("input_path", help="source/StrSheet_Guild or the folder name")
    parser.add_argument("-o", "--output-dir", default="")
    parser.add_argument("--cache", default="")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--no-ascii-entities", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = args.input_path
    name = folder_name(raw)
    if name in SKIP:
        print(f"{name} stays English or is not shipped. Not translating.", file=sys.stderr)
        return 1
    input_path = Path(raw)
    if not input_path.exists():
        input_path = Path("source") / name
    output_dir = Path(args.output_dir or f"output/{name}")
    slug = re.sub(r"[^A-Za-z0-9]+", "", name).lower()
    cache = Path(args.cache or f"cache/{slug}_translation_cache.json")
    return sheet.run_sheet(
        input_path,
        output_dir,
        cache,
        f"{name}-*.xml",
        args.batch_size if args.batch_size > 0 else 20,
        not args.no_ascii_entities,
        args.start,
        args.count,
    )


if __name__ == "__main__":
    raise SystemExit(main())
