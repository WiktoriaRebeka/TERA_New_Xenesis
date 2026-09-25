"""
Translate TERA StrSheet_UserSkill tooltip attributes from French to Latin American Spanish. name= is restored from the English dump.
using the same Gemini pipeline as translate_tooltips.py.

UserSkill XML differs from Item XML:
- attribute is tooltip= (lowercase), not toolTip=
- the visible name is name=, not string=  (left in English)
- extra attributes gender, race, class stay untouched
- the same id can appear once per class

Install:
    pip install google-genai

Usage:
    python translate_userskill.py source/StrSheet_UserSkill
    python translate_userskill.py source/StrSheet_UserSkill --start 0 --count 0
    python translate_userskill.py source/StrSheet_UserSkill/StrSheet_UserSkill-00000.xml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import translate_tooltips as item

# --- dopasowanie do StrSheet_UserSkill --------------------------------------

item.TOOLTIP_RE = re.compile(r'tooltip="([^"]*)"')

item.HEADINGS_ES = {
    **item.HEADINGS_ES,
    "[PvP]": "[JcJ]",
    "[Skill Usage]": "[Uso de habilidad]",
}

item.KEEP_ENGLISH = item.KEEP_ENGLISH + ("Focus", "Rage")


def to_ascii_entities_for_tera(text: str) -> str:
    """ASCII-only XML, but entities must survive Novadrop decoding.

    &amp;#243; in the file becomes &#243; after XML parse, which the
    TERA HTML tooltip renderer displays as an accented letter.
    A single &#243; is decoded to UTF-8 before packing and shows as krzaki.
    """
    return "".join(c if ord(c) < 128 else f"&amp;#{ord(c)};" for c in text)


item.to_ascii_entities = to_ascii_entities_for_tera

item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG skill tooltips from French to Latin American Spanish. The source is French. Write Spanish only. The French client uses PV and PM: write HP and MP.

Understand combat terminology and localize it in context: damage, cooldowns, chaining, charging, MP, HP, PvP, mounts, summons, buffs and debuffs.
Keep the tone appropriate for a high fantasy action MMORPG.
Translate meaning naturally; prefer established Spanish MMO phrasing over literal calques.
Keep proper names (Kelsaik, Valkyon, Bahaar, Kaia, Elin, Castanic, Popori, Baraka, Amani, etc.) unchanged unless a well-known Spanish TERA name already exists.
Skill names, mount names and buff names stay in English so the player can match them to the English skill bar. Examples: Combo Attack, Penetrating Arrow, Radiant Arrow, Decoy Jutsu, Leaping Slash, Focus, Rage, Squawk, Regal Frostlion.
Class names that appear as proper labels stay in English: Warrior, Lancer, Berserker, Slayer, Sorcerer, Archer, Priest, Mystic, Reaper, Gunner, Brawler, Ninja, Valkyrie, Assassin, Elementalist, Engineer, Fighter, Glaiver, Soulless.
Anything inside square brackets is copied in English exactly as written - the local script will swap known headings such as [Effect] afterwards. Never invent extra bracket labels.
Preserve numbers, percentages, distances (18m), and UI labels.
Placeholders like __TAG0__, __TAG1__, __TAG2__ are protected markup and game variables. Copy EVERY one of them into the Spanish text, in the same relative positions, with the exact same numbers. Never translate, merge, renumber or delete them. The output must contain exactly the same placeholders as the input, no more and no fewer.
GLOSSARY - follow it exactly, it overrides your own preferences:
- Keep these words in English, spelled exactly as in the source, even inside Spanish sentences: MP, HP, Feedstock, Battle Solution, Spellbind, Alkahest, Noctenium, Everful Nostrum, Etching, Crystal, Emerald, Diamond, Talent, Focus, Rage.
- Never write PM, PH or "mana" for MP. Never write PV or PS for HP.
- Endurance is always "resistencia". Never "aguante".
- Power is "poder". Crit Power is "poder de golpe critico".
- "times" as a multiplier is "veces" - never leave the English word.
- Use the Spanish decimal comma: +1,42 not +1.42.
- The audience is Latin American, not Spain. Write neutral Latin American Spanish: address the player as "tu", never use "vosotros" or its verb forms, and avoid Spain-only vocabulary. Use "lentes" not "gafas", "saco" or "blazer" not "americana", "computadora" not "ordenador".
- Never use the verb "coger" in any form - it is vulgar in most of Latin America. Use "tomar", "agarrar", "recoger" or "conseguir" instead.
- Skill, mount, emote, quest, dungeon, NPC and UI-menu names stay in English. Write "el cooldown de Leaping Slash", never invent a Spanish skill name.

Do not add explanations, notes, quotes, or extra punctuation that was not implied by the source.
Do not include the English source text in your output.
Translate EVERY sentence. A long tooltip may contain many sentences separated by __TAGn__ line breaks - each one must be rendered in Spanish. Never copy an English sentence unchanged into your output, not even a technical one about MP, cooldowns, percentages or durations.
Never use raw line breaks inside the JSON strings you return.
Return ONLY valid JSON: an array of Spanish strings, same length and order as the input array.
""".strip()

DEFAULT_CACHE = "cache/userskill_translation_cache.json"

# Re-export so check_userskill.py always sees the UserSkill regex and glossary.
CREDIT = item.CREDIT
FORBIDDEN_ES = item.FORBIDDEN_ES
KEEP_ENGLISH = item.KEEP_ENGLISH
ORPHAN_TAG_RE = item.ORPHAN_TAG_RE
TOOLTIP_RE = item.TOOLTIP_RE
describe_problems = item.describe_problems
engine_vars = item.engine_vars
looks_untranslated = item.looks_untranslated


def list_skill_files(root: Path, start: int, count: int) -> list[Path]:
    files = sorted(root.glob("StrSheet_UserSkill-*.xml"))
    if start < 0:
        start = 0
    files = files[start:]
    if count > 0:
        files = files[:count]
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate TERA UserSkill tooltips to Spanish-only via Gemini."
    )
    parser.add_argument(
        "input_xml",
        help="Folder source/StrSheet_UserSkill or one XML file",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output XML path when translating one file",
    )
    parser.add_argument(
        "--output-dir",
        default="output/StrSheet_UserSkill",
        help="Folder for translated XML when input is a folder",
    )
    parser.add_argument(
        "--cache",
        default=DEFAULT_CACHE,
        help=f"Shared UserSkill translation cache (default: {DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=item.BATCH_SIZE,
        help=f"Unique tooltips per Gemini request (default: {item.BATCH_SIZE})",
    )
    parser.add_argument("--start", type=int, default=0, help="Skip first N files in a folder")
    parser.add_argument("--count", type=int, default=0, help="How many files. 0 = all")
    parser.add_argument(
        "--no-ascii-entities",
        action="store_true",
        help="Zapisz akcenty jako zwykle znaki UTF-8 zamiast encji &#nnn;",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N lines of a single file - cheap test",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_xml).expanduser()
    cache_path = Path(args.cache).expanduser()
    batch_size = args.batch_size if args.batch_size > 0 else item.BATCH_SIZE
    ascii_safe = not args.no_ascii_entities
    limit = args.limit if args.limit > 0 else None

    if input_path.is_dir():
        files = list_skill_files(input_path, args.start, args.count)
        if not files:
            print(f"No StrSheet_UserSkill XML in {input_path}", file=sys.stderr)
            return 1
        print(f"Pack: {files[0].name} .. {files[-1].name} ({len(files)} files)", flush=True)
        output_dir = Path(args.output_dir).expanduser()
        item.process_files(files, output_dir, cache_path, batch_size, ascii_safe)
        for src in files:
            apply_en_skill_names(output_dir / f"{src.stem}_Translated{src.suffix}")
        return 0

    if not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output).expanduser()
    else:
        output_path = Path("output") / f"{input_path.stem}_Translated{input_path.suffix}"

    item.process_file(
        input_path,
        output_path,
        cache_path,
        batch_size,
        limit,
        ascii_safe,
    )
    apply_en_skill_names(output_path)
    return 0


EN_SKILL_DIR = Path(
    r"C:\Users\wikto\Desktop\TERA BAZA DANYCH\Output\Output\DataCenter_Final_EUR\StrSheet_UserSkill"
)
EN_SKILL_TSV = Path(__file__).resolve().parent / "source_en" / "skill_names.tsv"
_SKILL_NAMES: dict[tuple[str, str, str, str], str] | None = None


def load_en_skill_names() -> dict[tuple[str, str, str, str], str]:
    global _SKILL_NAMES
    if _SKILL_NAMES is not None:
        return _SKILL_NAMES
    names: dict[tuple[str, str, str, str], str] = {}
    if EN_SKILL_TSV.is_file():
        for line in EN_SKILL_TSV.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            names[(parts[0], parts[1], parts[2], parts[3])] = parts[4]
        _SKILL_NAMES = names
        return names
    if not EN_SKILL_DIR.is_dir():
        _SKILL_NAMES = names
        return names
    for sheet in EN_SKILL_DIR.glob("StrSheet_UserSkill-*.xml*"):
        for line in sheet.read_text(encoding="utf-8", errors="replace").splitlines():
            id_match = re.search(r'\bid="(\d+)"', line)
            name_match = re.search(r'\bname="([^"]*)"', line)
            if not id_match or not name_match:
                continue
            class_match = re.search(r'\bclass="([^"]*)"', line)
            gender_match = re.search(r'\bgender="([^"]*)"', line)
            race_match = re.search(r'\brace="([^"]*)"', line)
            key = (
                id_match.group(1),
                class_match.group(1) if class_match else "",
                gender_match.group(1) if gender_match else "",
                race_match.group(1) if race_match else "",
            )
            names[key] = name_match.group(1)
    _SKILL_NAMES = names
    return names


def apply_en_skill_names(path: Path) -> None:
    """name= stays the English skill name, matched by id, class, gender and race."""
    if not path.is_file():
        return
    names = load_en_skill_names()
    if not names:
        print("English skill name table missing - left French name=", flush=True)
        return
    updated: list[str] = []
    replaced = 0
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        id_match = re.search(r'\bid="(\d+)"', line)
        if id_match and 'name="' in line:
            class_match = re.search(r'\bclass="([^"]*)"', line)
            gender_match = re.search(r'\bgender="([^"]*)"', line)
            race_match = re.search(r'\brace="([^"]*)"', line)
            key = (
                id_match.group(1),
                class_match.group(1) if class_match else "",
                gender_match.group(1) if gender_match else "",
                race_match.group(1) if race_match else "",
            )
            english = names.get(key)
            if english is not None:
                new_line = re.sub(
                    r'\bname="[^"]*"',
                    'name="' + item.xml_attr_escape(english) + '"',
                    line,
                    count=1,
                )
                if new_line != line:
                    replaced += 1
                line = new_line
        updated.append(line)
    path.write_text("".join(updated), encoding="utf-8", newline="")
    print(f"English skill names restored: {replaced}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
