"""
Translate TERA StrSheet_Quest strings (titles, journal text, NPC quest lines)
to Spanish-only via the same Gemini pipeline as items. Source text is French.

Quest XML uses id= + string= (no toolTip). Hundreds of tiny files share
repeated lines, so this script translates a whole folder in one Gemini run
on a shared cache.

Usage:
    python translate_quest.py source/StrSheet_Quest
    python translate_quest.py source/StrSheet_Quest --start 0 --count 50
    python translate_quest.py source/StrSheet_Quest/StrSheet_Quest-00000.xml
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

import translate_tooltips as item

item.TOOLTIP_RE = re.compile(r'string="([^"]*)"')

QUEST_SKIP_EXACT = {
    "idle1",
    "idle2",
    "idle3",
    "talk1",
    "talk2",
    "talk3",
    "victory",
    "applaud",
    "request",
    "worry",
    "shy",
    "angry",
    "sob",
    "greet",
    "taunt",
    "propose",
    "attack",
    "pointing",
    "dance",
    "smile",
}

# Krotkie etykiety okna questa / promptu F / zablokowanych misji.
# [EN]<br>[ES] je rozsadza (Interact, Not Yet Unlocked, Required level, ...).
QUEST_UI_ENGLISH = {
    "Accept",
    "Decline",
    "None",
    "Solo",
    "Party",
    "Quest failed. Will automatically restart in a few moments.",
    "Quest failed. Teleport out to try again.",
    "Not Yet Unlocked",
    "Required level:",
    "Maximum level",
    "Required quest:",
    "You must first complete all preceding quests.",
    "You must first complete at least one preceding quest.",
    "This quest has no summary.",
    "Location Unknown",
    "Diminished quest reward for {QuestName}.",
    "[Full]",
    "[Your quest item space is full. Make room for more quest items by turning some in.]",
    "Quest Line:",
    "Recommended for: ",
    "Main location:",
    "Lv.",
    "Hunt",
    "Battlefield",
    "Crafting",
    "Find:",
    "Destination:",
    "Target:",
    "Target(s):",
    "Source:",
    "To:",
    "Escort:",
    "Protect:",
    "Guild Quest Reward Coordinator",
    "Interact",
    "Earning Points",
    "Successful Fishing",
    "Adventure Coin",
    "Production Point",
    "Order Complete",
    "Vanarch Guild",
    "Guild level",
    "Class",
    "Race",
    "Quest start:",
    "Use {Itemname}",
    "Received immediately",
    "Received from {NpcName}",
    "Already completed.",
    "Not completed.",
    "Urgent Orders from {TerritoryName}",
    "Guardian Legion Mission",
}


OBJECTIVE_START_RE = re.compile(
    r"^(?:"
    r"Talk to |Talk with |Speak with |Speak to |Go to |Go into |"
    r"Hunt |Defeat |Kill |Collect |Find |Meet |Meet with |"
    r"Report to |Return to |Deliver |Use |Read |Open |Gather |"
    r"Escort |Protect |Acquire |Purchase |Type |Enter |Clear |"
    r"Destroy |Rescue |Investigate |Search |Follow |Ask |"
    r"Bring |Pick up |Retrieve |Obtain |Visit |Approach |"
    r"Remove |Place |Activate |Battle with |Battle |"
    r"Show |Kill the |Defeat the |Hunt the |Collect the |"
    r"Find the |Help |Complete |Click |Press |Craft |"
    r"Gather the |Take \d"
    r")",
    re.I,
)

F_CHOICE_START_RE = re.compile(
    r"^(?:"
    r"I\b|I'm |I'll |I've |We\b|We've |My |You\b|"
    r"Yes|No\b|Okay|Ok\b|Right|Thanks|Thank |Happy |"
    r"Just |Well|Oh\b|Hey|What |Why |How |Really|"
    r"Sure |Please |Sorry|Wait|Fine |Of course|"
    r"Receive the |Go ask "
    r")",
    re.I,
)

SHORT_KILL_RE = re.compile(
    r"^(?:Defeat|Kill|Hunt|Destroy|Battle(?: with)?)(?: the)?\s+[A-Z][A-Za-z][A-Za-z' -]*\.$"
)


def decoded_plain(original: str) -> str:
    return decode_entities(original.replace("&quot;", '"')).strip()


def is_quoted_reply(original: str) -> bool:
    plain = decoded_plain(original)
    return len(plain) >= 2 and plain.startswith('"') and '"' in plain[1:]


def is_player_f_choice(original: str) -> bool:
    """Opcje przy F w pergaminie: cytaty i krotkie kwestie bez cudzyslowu."""
    if is_quoted_reply(original):
        return True
    plain = decoded_plain(original)
    if not plain or plain in QUEST_SKIP_EXACT:
        return False
    if plain in QUEST_UI_ENGLISH or plain in {"Accept", "Decline"}:
        return True
    lowered = original.lower()
    if "img://" in lowered or "&lt;br" in lowered or "<br" in lowered:
        return False
    if "{@" in original:
        return False
    if SHORT_KILL_RE.match(plain):
        return True
    if decoded_plain(original).rstrip(".") in creature_name_set():
        return True
    if OBJECTIVE_START_RE.match(plain):
        return False
    if len(plain) > 70:
        return False
    if F_CHOICE_START_RE.match(plain):
        return True
    return bool(re.match(r"^[A-Z][^?]{0,68}[.!?]$", plain) and plain.count(" ") <= 10)


def should_leave_english(original: str) -> bool:
    """Animacje zostaja. Przyciski F i Accept/Decline ida do tlumaczenia."""
    return original.strip() in QUEST_SKIP_EXACT


def is_quest_system_id(identifier: str) -> bool:
    """id < 1000 = chrome okna questa, nie dziennik."""
    try:
        number = int(identifier)
    except ValueError:
        return False
    return 0 < number < 1000


def is_quest_title_id(identifier: str) -> bool:
    try:
        number = int(identifier)
    except ValueError:
        return False
    if is_quest_system_id(identifier):
        return False
    return number >= 1000 and number % 1000 == 1


def is_quest_button_text(original: str) -> bool:
    return should_leave_english(original)


STRING_LINE_RE = re.compile(
    r'(<String id=")(\d+)(" string=")(.*?)(" />)',
    re.DOTALL,
)


def decode_entities(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = html.unescape(text)
    return text


def xml_attr(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def compact_title(english: str, spanish: str) -> str:
    """Tytul okna: English/Spanish, bez [EN], bez br, bez creditu."""
    en = decode_entities(english).strip()
    es = decode_entities(spanish).strip()
    if not es or es == en:
        return xml_attr(en)
    return xml_attr(f"{en}/{es}")


ES_TITLE_RE = re.compile(
    r"\[ES\]\s*(.*?)(?:\s*(?:&lt;br&gt;|<br>)\s*&lt;font|\s*$)",
    re.DOTALL | re.IGNORECASE,
)

CREDIT_TAIL_RE = re.compile(
    r"(?:&lt;br&gt;|<br>)\s*&lt;font color='#555555'&gt;"
    r"Transcription by TERA New Xenesis 2026"
    r"&lt;/font&gt;",
    re.IGNORECASE,
)


def strip_quest_credit(xml_text: str) -> str:
    """Usuwa credit z tracker/opisow questa (za duzo miejsca)."""
    return CREDIT_TAIL_RE.sub("", xml_text)


# Hiszpanskie kalki nazw miejsc -> angielski oryginal.
PLACE_NAME_FIXES = (
    ("el Cuartel General de la Federaci&amp;#243;n Valkyon", "Valkyon Federation Headquarters"),
    ("Cuartel General de la Federaci&amp;#243;n Valkyon", "Valkyon Federation Headquarters"),
    ("el Cuartel General de la Federación Valkyon", "Valkyon Federation Headquarters"),
    ("Cuartel General de la Federación Valkyon", "Valkyon Federation Headquarters"),
    ("el Campamento del Baluarte", "Bulwark Camp"),
    ("Campamento del Baluarte", "Bulwark Camp"),
    ("Campamento Baluarte", "Bulwark Camp"),
    ("el Bosque del Olvido", "Oblivion Woods"),
    ("Bosque del Olvido", "Oblivion Woods"),
    ("la Isla del Amanecer", "Island of Dawn"),
    ("Isla del Amanecer", "Island of Dawn"),
    ("La Island of Dawn", "Island of Dawn"),
    ("la Island of Dawn", "Island of Dawn"),
    ("Ciudad aislada", "Isolated Town"),
)


def restore_place_names(xml_text: str) -> str:
    for spanish, english in PLACE_NAME_FIXES:
        xml_text = xml_text.replace(spanish, english)
    return xml_text


CREATURE_DIR = Path(
    r"C:\Users\wikto\Desktop\TERA BAZA DANYCH\Output\Output\DataCenter_Final_EUR\StrSheet_Creature"
)
_CREATURE_NAMES: list[str] | None = None
_CREATURE_SET: set[str] | None = None
CREATURE_NAME_ATTR_RE = re.compile(r'\bname="([^"]+)"')


def creature_names() -> list[str]:
    global _CREATURE_NAMES, _CREATURE_SET
    if _CREATURE_NAMES is not None:
        return _CREATURE_NAMES
    found: set[str] = set()
    if CREATURE_DIR.is_dir():
        for path in CREATURE_DIR.glob("*.xml*"):
            text = path.read_text(encoding="utf-8")
            for match in CREATURE_NAME_ATTR_RE.finditer(text):
                name = decode_entities(match.group(1)).strip()
                if len(name) >= 3:
                    found.add(name)
    _CREATURE_NAMES = sorted(found, key=len, reverse=True)
    _CREATURE_SET = set(_CREATURE_NAMES)
    return _CREATURE_NAMES


def creature_name_set() -> set[str]:
    if _CREATURE_SET is None:
        creature_names()
    return _CREATURE_SET or set()


WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+")
ARTICLE_SPAN_RE_CACHE: dict[int, re.Pattern[str]] = {}


def article_span_re(word_count: int) -> re.Pattern[str]:
    compiled = ARTICLE_SPAN_RE_CACHE.get(word_count)
    if compiled is None:
        compiled = re.compile(
            r"(?i)((?:al|a los|a las|contra(?: el| los| las| la)?|del|de los|"
            r"de las|de la|el|la|los|las)\s+)?"
            r"((?:[^\s<>]+)(?:\s+[^\s<>]+){%d})" % (word_count - 1)
        )
        ARTICLE_SPAN_RE_CACHE[word_count] = compiled
    return compiled


_CREATURES_BY_FIRST: dict[str, list[str]] | None = None
SABER_CALQUE_RE = re.compile(
    r"(?i)((?:al|a los|a las|los|las|el|la|del|de)\s+)?"
    r"(?:tigres?\s+(?:de\s+)?)?"
    r"dientes\s+de\s+sable"
)
PREDATOR_CALQUE_RE = re.compile(
    r"(?i)((?:al|a los|a las|los|las|el|la|de)\s+)?"
    r"(?:mekonari\s+)?depredador(?:es)?(?:\s+mekonari)?"
)
SABER_TAIL_STOP = {
    "en",
    "y",
    "para",
    "cerca",
    "con",
    "del",
    "a",
    "al",
    "que",
    "se",
    "por",
    "amenazan",
    "amenaza",
    "proteger",
    "protegen",
    "recolecta",
    "mata",
    "caza",
    "derrota",
    "elimina",
    "habla",
    "informa",
}
COMBAT_NEAR_RE = re.compile(
    r"(?i)(?:caza|mata|derrot|destruy|elimin|vence|enfr[eé]nt)"
)


def replace_saber_calque(spanish: str, surface: str) -> tuple[str, bool]:
    match = SABER_CALQUE_RE.search(spanish)
    if not match:
        return spanish, False
    end = match.end()
    consumed = 0
    extra_words = 0
    for token in re.findall(r"\s+[^\s]+", spanish[end:]):
        word = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ]", "", token).lower()
        if not word or word in SABER_TAIL_STOP:
            break
        consumed += len(token)
        extra_words += 1
        if extra_words >= 4:
            break
    prefix = match.group(1) or ""
    replaced = spanish[: match.start()] + prefix + surface + spanish[end + consumed :]
    return replaced, True


_CREATURES_BY_LAST: dict[str, list[str]] | None = None
NAME_SURFACE_RE_CACHE: dict[str, re.Pattern[str]] = {}


def name_surface_re(name: str) -> re.Pattern[str]:
    compiled = NAME_SURFACE_RE_CACHE.get(name)
    if compiled is None:
        compiled = re.compile(r"(?i)\b" + re.escape(name) + r"(?:'s|s)?\b")
        NAME_SURFACE_RE_CACHE[name] = compiled
    return compiled


def surface_form(english: str, name: str) -> str:
    match = name_surface_re(name).search(english)
    return match.group(0) if match else name


def already_has_name(text: str, name: str) -> bool:
    return name_surface_re(name).search(text) is not None


def _creature_indexes() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    global _CREATURES_BY_FIRST, _CREATURES_BY_LAST
    if _CREATURES_BY_FIRST is None or _CREATURES_BY_LAST is None:
        by_first: dict[str, list[str]] = {}
        by_last: dict[str, list[str]] = {}
        for name in creature_names():
            parts = name.split()
            by_first.setdefault(parts[0].lower(), []).append(name)
            by_last.setdefault(parts[-1].lower(), []).append(name)
        _CREATURES_BY_FIRST = by_first
        _CREATURES_BY_LAST = by_last
    return _CREATURES_BY_FIRST, _CREATURES_BY_LAST


def creatures_mentioned(english: str) -> list[str]:
    by_first, by_last = _creature_indexes()
    found: list[str] = []
    seen: set[str] = set()
    words = WORD_RE.findall(english)
    lowered = [word.lower().replace("'s", "").rstrip("'") for word in words]
    for word in words:
        key = word.lower().replace("'s", "").rstrip("'")
        for name in by_first.get(key, ()):
            if name in seen:
                continue
            if already_has_name(english, name):
                seen.add(name)
                found.append(name)
    for index, word in enumerate(lowered):
        keys = {word}
        if word.endswith("s") and len(word) > 3:
            keys.add(word[:-1])
        window = set(lowered[max(0, index - 5) : index + 1])
        specific: list[str] = []
        generic: list[str] = []
        for key in keys:
            for name in by_last.get(key, ()):
                if name in seen:
                    continue
                parts = [part.lower() for part in name.split()]
                last = parts[-1]
                if last != word and last + "s" != word and last != key:
                    continue
                others = parts[:-1]
                if others:
                    if all(part in window for part in others):
                        specific.append(name)
                else:
                    generic.append(name)
        for name in specific or generic[:1]:
            if name not in seen:
                seen.add(name)
                found.append(name)
    found.sort(key=len, reverse=True)
    return found


def inject_creature_names(english: str, spanish: str) -> str:
    """Wstawia angielskie nazwy mobow tam, gdzie ES je przetlumaczylo."""
    if not spanish:
        return spanish
    en_words = {w.lower() for w in WORD_RE.findall(english) if len(w) > 2}
    for name in creatures_mentioned(english):
        if already_has_name(spanish, name):
            continue
        words = name.split()
        count = len(words)
        if count == 1 and len(name) < 8:
            continue
        surface = surface_form(english, name)
        lowered_name = name.lower()
        if "sabertooth" in lowered_name:
            spanish, hits = replace_saber_calque(spanish, surface)
            if hits:
                continue
        if "predator" in lowered_name or "depredator" in lowered_name:
            updated, hits = PREDATOR_CALQUE_RE.subn(
                lambda match: (match.group(1) or "") + surface, spanish, count=1
            )
            if hits:
                spanish = updated
                continue
        best: tuple[int, int, str] | None = None
        best_score: float | None = None
        for n_words in range(count, min(count + 4, 7)):
            for match in article_span_re(n_words).finditer(spanish):
                chunk = match.group(2)
                if "<" in chunk or name.lower() in chunk.lower():
                    continue
                chunk_words = [w.lower() for w in WORD_RE.findall(chunk)]
                long_words = [w for w in chunk_words if len(w) > 2]
                if not long_words:
                    continue
                overlap = sum(1 for w in long_words if w in en_words)
                if overlap * 2 > len(long_words):
                    continue
                has_article = bool(match.group(1))
                accent = any(ord(c) > 127 for c in chunk)
                lowerish = sum(1 for c in chunk if c.islower())
                nearby = spanish[max(0, match.start() - 24) : match.start()]
                combat = bool(COMBAT_NEAR_RE.search(nearby))
                score = (
                    (10.0 if has_article else 0.0)
                    + (12.0 if combat else 0.0)
                    + (5.0 if accent else 0.0)
                    + lowerish * 0.1
                    - abs(n_words - count)
                    - overlap * 3
                )
                if best_score is None or score > best_score:
                    best_score = score
                    prefix = match.group(1) or ""
                    best = (match.start(), match.end(), prefix + surface)
        if best is not None and best_score is not None and best_score >= 5:
            start, end, text = best
            spanish = spanish[:start] + text + spanish[end:]
            continue
        stripped = spanish.strip().rstrip(".")
        if stripped and stripped.count(" ") + 1 <= count + 2:
            suffix = "." if english.rstrip().endswith(".") else ""
            spanish = surface + suffix
    return spanish


BILINGUAL_SPLIT_RE = re.compile(
    r"(\[EN\] )(.*?)((?:&lt;br&gt;|<br>)\[ES\] )(.*)$",
    re.DOTALL | re.IGNORECASE,
)


def restore_creature_names(xml_text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        value = match.group(4)
        split = BILINGUAL_SPLIT_RE.match(value)
        if not split:
            return match.group(0)
        english = decode_entities(split.group(2))
        spanish = decode_entities(split.group(4))
        new_spanish = inject_creature_names(english, spanish)
        if new_spanish == spanish:
            return match.group(0)
        encoded = to_tera_html_entities(xml_attr(new_spanish))
        new_val = f"{split.group(1)}{split.group(2)}{split.group(3)}{encoded}"
        return f"{match.group(1)}{match.group(2)}{match.group(3)}{new_val}{match.group(5)}"

    return STRING_LINE_RE.sub(repl, xml_text)


def extract_spanish_from_bilingual(value: str) -> str:
    match = ES_TITLE_RE.search(value)
    if match:
        return match.group(1).strip()
    return ""


def restore_titles_and_buttons(
    xml_text: str,
    source_by_id: dict[str, str],
    spanish_titles: dict[str, str] | None = None,
) -> tuple[str, int, int]:
    """Tytuly i przyciski F zostaja po hiszpansku. Nie przywracamy francuskiego."""
    del source_by_id, spanish_titles
    return xml_text, 0, 0


_orig_collect = item.collect_unique_uncached


def collect_unique_uncached(lines: list[str], cache: dict[str, str]) -> list[str]:
    unique = _orig_collect(lines, cache)
    return [text for text in unique if not should_leave_english(text)]


item.collect_unique_uncached = collect_unique_uncached


def quest_string(original_attr: str, spanish_escaped: str) -> str:
    """Journal, przyciski F i Accept/Decline: sam hiszpanski."""
    if should_leave_english(original_attr):
        return original_attr
    english = item.balance_font_tags(item.sanitize(original_attr))
    spanish = item.localize_headings(item.balance_font_tags(item.sanitize(spanish_escaped)))
    return item.OUTPUT_TEMPLATE.format(english=english, spanish=spanish)


item.bilingual_tooltip = quest_string

# Tracker po prawej jest ciasny: bez creditu. Item tooltipy zostaja z credit.
item.OUTPUT_TEMPLATE = "{spanish}"


def to_tera_html_entities(text: str) -> str:
    return "".join(c if ord(c) < 128 else f"&amp;#{ord(c)};" for c in text)


item.to_ascii_entities = to_tera_html_entities

item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG quest text from French to Latin American Spanish. The source is French. Write Spanish only, including Accept/Decline and F-button replies. Write HP and MP, never PV or PM.

These strings are quest titles, journal summaries, objectives and short NPC lines from the quest flow. Translate meaning naturally into Latin American Spanish. Keep the tone of high fantasy TERA.
Keep proper names unchanged: NPCs, places, dungeons, items, skills, classes, races, AND monster/creature names (Argon Predator, Argon Soldier, Slinking Sabertooths, Spectral Spider, etc.). Write "Derrota a los Argon Predator", never "Depredador Argon" or "tigres de dientes de sable".
Place names stay English: Isolated Town, Island of Dawn, Velika, Allemantheia, Kaiator, Oblivion Woods, Bulwark Camp, Valkyon Federation Headquarters, Lumbertown, Crescentia, Tamarang. Never write Isla del Amanecer, Ciudad aislada, Bosque del Olvido. Write "en Island of Dawn".
Class and race names used as labels stay in English: Warrior, Lancer, Elin, Castanic, Popori, Baraka, Amani.
Anything inside square brackets is copied in English exactly as written, except known headings the local script will swap.
Preserve numbers, punctuation and placeholders like __TAG0__, {QuestName}, {Itemname}, {NpcName}, {TerritoryName}. Copy EVERY placeholder into the Spanish text, same spelling and relative position.
GLOSSARY - follow it exactly:
- Keep MP, HP in English. Never PM, PH, mana, PV, PS.
- Endurance is "resistencia". Never "aguante".
- Latin American Spanish: "tu", never "vosotros". Never "coger". Use "tomar", "agarrar", "recoger" or "conseguir".
- Decimal comma: +1,42 not +1.42.

Do not add explanations. Do not include the English source in your output.
Translate EVERY sentence.
Never use raw line breaks inside the JSON strings you return.
Return ONLY valid JSON: an array of Spanish strings, same length and order as the input array.
""".strip()

DEFAULT_CACHE = "cache/quest_translation_cache.json"

CREDIT = item.CREDIT
FORBIDDEN_ES = item.FORBIDDEN_ES
KEEP_ENGLISH = item.KEEP_ENGLISH
ORPHAN_TAG_RE = item.ORPHAN_TAG_RE
TOOLTIP_RE = item.TOOLTIP_RE
describe_problems = item.describe_problems
engine_vars = item.engine_vars
looks_untranslated = item.looks_untranslated


def list_quest_files(root: Path, start: int, count: int) -> list[Path]:
    files = sorted(root.rglob("StrSheet_Quest-*.xml"))
    if not files:
        files = sorted(
            p
            for p in root.rglob("*.xml")
            if not p.name.endswith("_Translated.xml")
        )
    if start < 0:
        start = 0
    files = files[start:]
    if count > 0:
        files = files[:count]
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate TERA StrSheet_Quest files in packs (one Gemini run, shared cache)."
    )
    parser.add_argument(
        "input_path",
        help="Folder with StrSheet_Quest-*.xml, or a single XML file",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="output/StrSheet_Quest",
        help="Folder na przetlumaczone XML (default: output/StrSheet_Quest)",
    )
    parser.add_argument(
        "--cache",
        default=DEFAULT_CACHE,
        help=f"Shared quest cache (default: {DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Unique strings per Gemini request (default: 20)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Skip the first N files in the sorted folder (default: 0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Ile plikow w tej paczce. 0 = caly folder od --start (default: 0)",
    )
    parser.add_argument(
        "--no-ascii-entities",
        action="store_true",
        help="Zapisz akcenty jako zwykle znaki UTF-8 zamiast encji",
    )
    return parser.parse_args()


def restore_existing_pack(
    pack_dir: Path, source_root: Path | None = None
) -> tuple[int, int, int]:
    """Przywraca EN dla tytulow/F/mobow w juz przetlumaczonym folderze Questa."""
    source_root = source_root or Path("source/StrSheet_Quest")
    source_by_id = load_source_strings(source_root)
    names = creature_names()
    files = sorted(
        p
        for p in pack_dir.rglob("StrSheet_Quest-*")
        if ".xml" in p.name.lower()
    )
    print(
        f"Creature names: {len(names)}; pack files: {len(files)}",
        flush=True,
    )
    title_total = 0
    button_total = 0
    changed = 0
    for index, path in enumerate(files, start=1):
        raw = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in raw[:200] else b"\n"
        text = raw.decode("utf-8")
        new_text, titles, buttons = restore_titles_and_buttons(text, source_by_id)
        new_text = strip_quest_credit(new_text)
        new_text = restore_place_names(new_text)
        new_text = restore_creature_names(new_text)
        out = new_text.encode("utf-8")
        if newline == b"\r\n":
            out = out.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        if out != raw:
            path.write_bytes(out)
            changed += 1
        title_total += titles
        button_total += buttons
        if index % 200 == 0 or index == len(files):
            print(
                f"  {index}/{len(files)} files, {changed} changed",
                flush=True,
            )
    print(
        f"EN-only titles: {title_total}, EN-only buttons: {button_total}, "
        f"files rewritten: {changed}",
        flush=True,
    )
    return title_total, button_total, changed


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_path).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    cache_path = Path(args.cache).expanduser()
    batch_size = args.batch_size if args.batch_size > 0 else 20
    ascii_safe = not args.no_ascii_entities

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = list_quest_files(input_path, args.start, args.count)
        if not files:
            print(f"No quest XML files in {input_path}", file=sys.stderr)
            return 1
        last = files[-1].name
        print(
            f"Pack: {files[0].name} .. {last} ({len(files)} files, start={args.start})",
            flush=True,
        )
    else:
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    item.process_files(files, output_dir, cache_path, batch_size, ascii_safe)

    source_root = Path("source/StrSheet_Quest")
    if source_root.is_dir():
        source_by_id = load_source_strings(source_root)
        title_total = 0
        button_total = 0
        for out_path in sorted(output_dir.glob("StrSheet_Quest-*.xml")):
            raw = out_path.read_bytes()
            newline = b"\r\n" if b"\r\n" in raw[:200] else b"\n"
            new_text, titles, buttons = restore_titles_and_buttons(
                raw.decode("utf-8"), source_by_id
            )
            new_text = strip_quest_credit(new_text)
            new_text = restore_place_names(new_text)
            new_text = restore_creature_names(new_text)
            out = new_text.encode("utf-8")
            if newline == b"\r\n":
                out = out.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            out_path.write_bytes(out)
            title_total += titles
            button_total += buttons
        print(
            f"EN-only titles: {title_total}, EN-only buttons: {button_total}",
            flush=True,
        )
    return 0


def load_source_strings(source_root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in source_root.rglob("StrSheet_Quest-*.xml"):
        text = path.read_text(encoding="utf-8")
        for match in STRING_LINE_RE.finditer(text):
            mapping[match.group(2)] = match.group(4)
    return mapping


if __name__ == "__main__":
    raise SystemExit(main())
