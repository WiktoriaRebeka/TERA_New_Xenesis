"""
Translate TERA StrSheet_Dungeon floating banners (consumable tips, boss shouts).

string= is Spanish only. StrSheet_Dungeon-00000 is copied from the English dump and is not translated.

Usage:
    python translate_dungeon.py source/StrSheet_Dungeon
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

import translate_tooltips as item
import translate_string_sheet as sheet

EN_DUNGEON = Path(
    r"C:\Users\wikto\Desktop\TERA BAZA DANYCH\Output\Output\DataCenter_Final_EUR"
    r"\StrSheet_Dungeon\StrSheet_Dungeon-00000.xml"
)
FR_DUNGEON = Path("source/StrSheet_Dungeon/StrSheet_Dungeon-00000.xml")
PLACE_NAME_FILE = EN_DUNGEON
_PLACE_NAMES: set[str] | None = None


def _names_by_id(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        id_match = re.search(r'\bid="(\d+)"', line)
        string_match = sheet.ATTR_RE.search(line)
        if id_match and string_match:
            found[id_match.group(1)] = string_match.group(1)
    return found


_PLACE_MAP: dict[str, str] | None = None


def french_to_english_places() -> dict[str, str]:
    global _PLACE_MAP
    if _PLACE_MAP is not None:
        return _PLACE_MAP
    french = _names_by_id(FR_DUNGEON)
    english = _names_by_id(EN_DUNGEON)
    mapping: dict[str, str] = {}
    for key, fr_name in french.items():
        en_name = english.get(key)
        if not en_name:
            continue
        mapping[fr_name] = en_name
        mapping[_fully_unescape(fr_name)] = en_name
    _PLACE_MAP = mapping
    return mapping


def replace_place(original: str) -> str | None:
    mapping = french_to_english_places()
    return mapping.get(original) or mapping.get(_fully_unescape(original))


def load_place_names() -> set[str]:
    global _PLACE_NAMES
    if _PLACE_NAMES is not None:
        return _PLACE_NAMES
    names: set[str] = set()
    if PLACE_NAME_FILE.is_file():
        text = PLACE_NAME_FILE.read_text(encoding="utf-8")
        for match in sheet.ATTR_RE.finditer(text):
            original = match.group(1)
            if original:
                names.add(original)
                names.add(html.unescape(original))
                names.add(_fully_unescape(original))
    _PLACE_NAMES = names
    return names


def _fully_unescape(text: str) -> str:
    prev = None
    cur = text
    while cur != prev:
        prev = cur
        cur = html.unescape(cur)
    return cur.strip()


def should_leave_english(original: str) -> bool:
    raw = _fully_unescape(original)
    if not raw:
        return True
    names = load_place_names()
    if raw in names or original in names:
        return True
    if re.fullmatch(r"\d+", raw):
        return True
    return False


sheet.LEAVE_ENGLISH_FN = should_leave_english
sheet.REPLACE_EXACT = replace_place

item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG dungeon floating banners from French to Latin American Spanish. The source is French. Write Spanish only. Write HP and MP, never PV or PM.

These are red/yellow overlay lines in dungeons: consumable reminders, boon timers, boss taunts. Translate meaning naturally into Latin American Spanish.
Keep item names, monster names, place names and skill names in English: Prime Battle Solution, Bravery Potion, Noctenium Infusions, Soulcrusher, Murdranak, Lok.
Copy every __TAGn__ placeholder, HTML tag (img, font) and $token unchanged, same spelling and relative position.
GLOSSARY:
- Keep MP, HP, Battle Solution, Noctenium in English.
- Endurance is "resistencia". Never "aguante".
- Latin American Spanish: "tu", never "vosotros". Never "coger".
- Decimal comma: +1,42 not +1.42.

Do not add explanations. Do not include the English source in your output.
Translate EVERY sentence.
Return ONLY valid JSON: an array of Spanish strings, same length and order as the input array.
""".strip()

DEFAULT_CACHE = "cache/dungeon_translation_cache.json"
describe_problems = item.describe_problems
looks_untranslated = item.looks_untranslated
ATTR_RE = sheet.ATTR_RE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate TERA StrSheet_Dungeon banners to bilingual EN/ES."
    )
    parser.add_argument("input_path")
    parser.add_argument("-o", "--output-dir", default="output/StrSheet_Dungeon")
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--no-ascii-entities", action="store_true")
    return parser.parse_args()


def copy_instance_sheet(output_dir: Path) -> None:
    if not EN_DUNGEON.is_file():
        print(f"EN dungeon instances not found: {EN_DUNGEON}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EN_DUNGEON, output_dir / "StrSheet_Dungeon-00000.xml")
    print("Copied English StrSheet_Dungeon-00000.xml", flush=True)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_path).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    if input_path.name == "StrSheet_Dungeon-00000.xml":
        copy_instance_sheet(output_dir)
        return 0
    code = sheet.run_sheet(
        input_path,
        output_dir,
        Path(args.cache).expanduser(),
        "StrSheet_Dungeon-*.xml",
        args.batch_size if args.batch_size > 0 else 20,
        not args.no_ascii_entities,
        args.start,
        args.count,
    )
    copy_instance_sheet(output_dir)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
