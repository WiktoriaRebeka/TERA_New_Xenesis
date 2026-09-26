"""
Translate leftover player-facing attrs that StrSheet all skipped.

string= was already milled. This pass does tooltip/toolTip/msg/desc/memo and
HeroSkin lore. Chat channel names use name=. Skill/item/creature names stay
English and are not in this attr list.

Reads existing output/*_Translated.xml when present so Spanish string= stays.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

import translate_tooltips as item

FR_LETTERS = re.compile(r"[àèêëîïôûœçÀÈÊËÎÏÔÛŒÇ]")
FR_WORDS = re.compile(
    r"\b(vous|votre|vos|c'est|n'est|quête|quetes|guilde|donjon|monstre|"
    r"équipement|dégâts|puissance|régénération)\b",
    re.I,
)

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

# UI labels in name=, not skill/NPC/item names.
NAME_FOLDERS = {
    "StrSheet_ChatChannelName",
    "StrSheet_SlashCommand",
}

EXTRA_ATTRS = (
    "tooltip",
    "toolTip",
    "tooltip1",
    "tooltip2",
    "msg",
    "desc",
    "memo",
    "description",
    "heroStoryDescription",
    "heroStoryTitle",
    "title",
    "attackDistance",
)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
OUTPUT = ROOT / "output"

item.OUTPUT_TEMPLATE = "{spanish}"
item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG player-facing text from French to Latin American Spanish. The source is French. Write Spanish only. Write HP and MP, never PV or PM.

Translate the visible meaning into natural Latin American Spanish. Keep the tone of high fantasy TERA.
Keep proper names unchanged: NPCs, places, dungeons, items, skills, classes, races and monster names. Place names stay English: Velika, Elleon, Island of Dawn, Oblivion Woods, Fey Forest.
Class and race names stay English: Warrior, Lancer, Elin, Castanic.
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


def attr_pattern(include_name: bool) -> re.Pattern[str]:
    names = EXTRA_ATTRS + (("name",) if include_name else ())
    return re.compile(r"\b(" + "|".join(names) + r')="([^"]*)"')


def needs_translation(value: str) -> bool:
    if not value or item.is_already_bilingual(value):
        return False
    plain = html.unescape(value)
    return bool(FR_LETTERS.search(plain) or FR_WORDS.search(plain))


def collect_unique_uncached(lines: list[str], cache: dict[str, str]) -> list[str]:
    unique: list[str] = []
    seen = set(cache.keys())
    pattern = item.TOOLTIP_RE
    for line in lines:
        for match in pattern.finditer(line):
            original = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(1)
            if original in seen or not needs_translation(original):
                continue
            seen.add(original)
            unique.append(original)
    return unique


def encode_attr(value: str) -> str:
    parts: list[str] = []
    for char in html.unescape(value):
        code = ord(char)
        if char == "&":
            parts.append("&amp;")
        elif char == "<":
            parts.append("&lt;")
        elif char == ">":
            parts.append("&gt;")
        elif char == '"':
            parts.append("&quot;")
        elif code >= 128:
            parts.append(f"&amp;#{code};")
        else:
            parts.append(char)
    return "".join(parts)


def rewrite_lines(
    lines: list[str],
    cache: dict[str, str],
    ascii_safe: bool = True,
) -> tuple[list[str], dict[str, int]]:
    pattern = item.TOOLTIP_RE
    stats = {
        "applied": 0,
        "already_bilingual": 0,
        "empty": 0,
        "no_tooltip": 0,
        "left_original": 0,
    }
    output_lines: list[str] = []
    for line in lines:
        matches = list(pattern.finditer(line))
        if not matches:
            output_lines.append(line)
            stats["no_tooltip"] += 1
            continue
        new_line = line
        for match in reversed(matches):
            original = match.group(2)
            if original == "":
                stats["empty"] += 1
                continue
            if not needs_translation(original) and original not in cache:
                stats["already_bilingual"] += 1
                continue
            spanish = cache.get(original)
            if spanish is None:
                stats["left_original"] += 1
                continue
            start, end = match.span(2)
            new_value = item.bilingual_tooltip(original, spanish)
            if ascii_safe:
                new_value = encode_attr(new_value)
            new_line = new_line[:start] + new_value + new_line[end:]
            stats["applied"] += 1
        output_lines.append(new_line)
    return output_lines, stats


def translated_name(path: Path) -> str:
    if path.stem.endswith("_Translated"):
        return path.name
    return f"{path.stem}_Translated{path.suffix}"


def input_files(folder: Path) -> list[Path]:
    out_dir = OUTPUT / folder.name
    done = sorted(out_dir.glob("*_Translated.xml"))
    if done:
        return done
    return sorted(p for p in folder.glob("*.xml") if p.name != "StrSheet_Dungeon-00000.xml")


def process_folder(
    folder: Path,
    cache_path: Path,
    batch_size: int,
    ascii_safe: bool,
) -> int:
    files = input_files(folder)
    if not files:
        print(f"No XML in {folder}", flush=True)
        return 1
    include_name = folder.name in NAME_FOLDERS
    item.TOOLTIP_RE = attr_pattern(include_name)
    item.collect_unique_uncached = collect_unique_uncached
    item.rewrite_lines = rewrite_lines

    output_dir = OUTPUT / folder.name
    cache = item.load_cache(cache_path)
    print(f"Cache: {cache_path} ({len(cache)} entries)", flush=True)

    loaded: list[tuple[Path, list[str]]] = []
    unique: list[str] = []
    seen = set(cache.keys())
    for path in files:
        with path.open("r", encoding="utf-8", newline="") as handle:
            lines = handle.readlines()
        loaded.append((path, lines))
        for original in collect_unique_uncached(lines, cache):
            if original in seen:
                continue
            seen.add(original)
            unique.append(original)

    print(
        f"{folder.name}: {len(loaded)} files, {len(unique)} leftover extra-attr strings",
        flush=True,
    )
    quota_hit = False
    new_translations = 0
    if unique:
        client = item.build_client()
        try:
            new_translations = item.fill_cache_in_batches(
                unique, client, cache, cache_path, batch_size
            )
        except item.DailyQuotaExceeded:
            quota_hit = True
    else:
        print("  nothing left with French extra attrs.", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    applied = 0
    for path, lines in loaded:
        out_lines, stats = rewrite_lines(lines, cache, ascii_safe)
        dest = output_dir / translated_name(path)
        with dest.open("w", encoding="utf-8", newline="") as handle:
            handle.writelines(out_lines)
        applied += stats["applied"]
        print(f"  wrote {dest.name} applied={stats['applied']}", flush=True)
    item.save_cache(cache_path, cache)
    print(f"  new API {new_translations}, applied {applied}", flush=True)
    if quota_hit:
        raise SystemExit(0)
    return 0


def folder_has_work(folder: Path) -> bool:
    pattern = attr_pattern(folder.name in NAME_FOLDERS)
    for path in input_files(folder):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            if needs_translation(match.group(2)):
                return True
    return False


def remaining_folders(source_root: Path) -> list[Path]:
    folders: list[Path] = []
    if not source_root.is_dir():
        return folders
    for path in sorted(source_root.iterdir()):
        if not path.is_dir() or not path.name.lower().startswith("strsheet"):
            continue
        if path.name in SKIP:
            continue
        if folder_has_work(path) or path.name in {"StrSheet_UserSkill"}:
            folders.append(path)
    return folders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate leftover tooltip/msg/desc attrs to Spanish."
    )
    parser.add_argument(
        "input_path",
        help="all = every leftover extra-attr folder. Or source/StrSheet_Card",
    )
    parser.add_argument("--cache", default="cache/extra_translation_cache.json")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--no-ascii-entities", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = args.input_path.strip()
    name = Path(raw).name
    batch = args.batch_size if args.batch_size > 0 else 20
    ascii_safe = not args.no_ascii_entities
    cache_path = Path(args.cache)

    if name.lower() in {"all", "source"} or raw in {".", "source"}:
        folders = remaining_folders(SOURCE)
        folders = folders[max(args.start, 0) :]
        if args.count > 0:
            folders = folders[: args.count]
        if not folders:
            print("No extra-attr folders in source/.", file=sys.stderr)
            return 1
        print(
            "Extra-attr mill: " + ", ".join(p.name for p in folders),
            flush=True,
        )
        rc = 0
        for folder in folders:
            result = process_folder(folder, cache_path, batch, ascii_safe)
            if result:
                rc = result
        return rc

    if name in SKIP:
        print(f"{name} stays English or is not shipped.", file=sys.stderr)
        return 1
    folder = Path(raw)
    if not folder.exists():
        folder = SOURCE / name
    return process_folder(folder, cache_path, batch, ascii_safe)


if __name__ == "__main__":
    raise SystemExit(main())
