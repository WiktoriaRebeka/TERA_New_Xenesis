"""
Translate TERA QuestDialog parchment pages (NPC quest speech).

XML uses <Page>inner text</Page>, not string=. Spanish only, no [EN]/[ES], no credit.
Monster, place, NPC and item names stay English.

Usage:
    python translate_questdialog.py source/QuestDialog
    python translate_questdialog.py source/QuestDialog --start 0 --count 0
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

import translate_tooltips as item

# Self-closing <Page ... /> must not match: [^>]* would eat the slash and then
# (.*?) would swallow the next Text nodes until the first real </Page>.
PAGE_RE = re.compile(r"(<Page\b(?![^>]*/>)[^>]*>)(.*?)(</Page>)", re.DOTALL)
BUTTON_RE = re.compile(
    r"(&lt;(NEXTPAGEBUTTON|PREVPAGEBUTTON|CLOSEPAGEBUTTON|TEXTBUTTON|EVENTPAGEBUTTON)&gt;)"
    r"(.*?)"
    r"(&lt;/\2&gt;)",
    re.DOTALL | re.IGNORECASE,
)
BOLD_RE = re.compile(r"(&lt;B&gt;)(.*?)(&lt;/B&gt;)", re.DOTALL | re.IGNORECASE)
# F-row is UI chrome: #NNNN is a color. Numeric entities in the button
# truncate the label and spawn @ui:undefined.
BUTTON_PUNCT = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u00a0": " ",
}
LEAKED_KEY_RE = re.compile(r"</Text>|<Text\b")
LEAKED_PAGE_RE = re.compile(r"<Page\b[^>]*>", re.IGNORECASE)
PLACE_NAME_FIXES = (
    ("el Cuartel General de la Federaci&amp;#243;n Valkyon", "Valkyon Federation Headquarters"),
    ("Cuartel General de la Federaci&amp;#243;n Valkyon", "Valkyon Federation Headquarters"),
    ("el Cuartel General de la Federación Valkyon", "Valkyon Federation Headquarters"),
    ("Cuartel General de la Federación Valkyon", "Valkyon Federation Headquarters"),
    ("Bienvenido al Cuartel General de Allemantheia", "Bienvenido a Allemantheia Headquarters"),
    ("al Cuartel General de Allemantheia", "a Allemantheia Headquarters"),
    ("el Cuartel General de Allemantheia", "Allemantheia Headquarters"),
    ("Cuartel General de Allemantheia", "Allemantheia Headquarters"),
    ("entrar en el Cuartel General", "entrar en Headquarters"),
    ("al Cuartel General", "a Headquarters"),
    ("el Cuartel General", "Headquarters"),
    ("Cuartel General", "Headquarters"),
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
FORGE_HINT_EN = (
    "Press &lt;img src='img://__Icon_KeyboardShape.Keyboard_t' "
    "width='21' height='21' vspace='-6'/&gt; key to open the Forge "
    "and use Relic Fragments and gold to enchant your weapon."
)
FORGE_HINT_ES = (
    "Pulsa la tecla &lt;img src='img://__Icon_KeyboardShape.Keyboard_t' "
    "width='21' height='21' vspace='-6'/&gt; para abrir el Forge "
    "y usar Relic Fragments y oro para encantar tu arma."
)

item.OUTPUT_TEMPLATE = "{spanish}"

item.to_ascii_entities = item.to_tera_html_entities


item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG NPC quest dialogue from French to Latin American Spanish. The source is French. Write Spanish only. Write HP and MP, never PV or PM.

These are parchment speeches when accepting or turning in a quest. Translate meaning naturally into Latin American Spanish. Keep the tone of high fantasy TERA.
Keep proper names unchanged: NPCs, places, dungeons, items, skills, classes, races, AND monster names (Argon Predator, Slinking Sabertooth). Write "Derrota a los Argon Predator", never a Spanish creature name.
Place names stay English: Isolated Town, Island of Dawn, Velika, Fey Forest, Maon's Cabin, Valkyon Federation Headquarters.
Class and race names stay English.
Placeholders like __TAG0__ and markup must be copied unchanged, same spelling and relative position.
Translate the words inside NEXTPAGEBUTTON and <B>...</B>. Keep the tags themselves unchanged. F-button text is Spanish. Never put numeric &# entities inside a button.
GLOSSARY:
- Keep MP, HP in English. Never PM, PH, mana, PV, PS.
- Endurance is "resistencia". Never "aguante".
- Latin American Spanish: "tu", never "vosotros". Never "coger". Use "tomar", "agarrar", "recoger" or "conseguir".
- Decimal comma: +1,42 not +1.42.

Do not add explanations. Do not include the English source in your output.
Translate EVERY sentence.
Never use raw line breaks inside the JSON strings you return.
Return ONLY valid JSON: an array of Spanish strings, same length and order as the input array.
""".strip()

DEFAULT_CACHE = "cache/questdialog_translation_cache.json"
CREDIT = item.CREDIT
FORBIDDEN_ES = item.FORBIDDEN_ES
KEEP_ENGLISH = item.KEEP_ENGLISH
ORPHAN_TAG_RE = item.ORPHAN_TAG_RE
describe_problems = item.describe_problems
engine_vars = item.engine_vars
looks_untranslated = item.looks_untranslated


def list_dialog_files(root: Path, start: int, count: int) -> list[Path]:
    files = sorted(root.glob("QuestDialog-*.xml"))
    if start < 0:
        start = 0
    files = files[start:]
    if count > 0:
        files = files[:count]
    return files


def pages_in_text(xml_text: str) -> list[str]:
    found: list[str] = []
    for match in PAGE_RE.finditer(xml_text):
        inner = match.group(2)
        if inner.strip():
            found.append(inner)
    return found


def _after_last_escaped_page(spanish: str) -> str:
    lower = spanish.lower()
    start = lower.rfind("&lt;page")
    if start < 0:
        return spanish.lstrip()
    end = spanish.find("&gt;", start)
    if end < 0:
        return spanish.lstrip()
    return spanish[end + 4 :].lstrip()


def salvage_leaked_cache(cache: dict[str, str]) -> int:
    """Recover page translations when an old regex ate neighboring XML."""
    leaked_keys = [key for key in cache if LEAKED_KEY_RE.search(key)]
    extras: dict[str, str] = {}
    for english in leaked_keys:
        spanish = cache[english]
        opens = list(LEAKED_PAGE_RE.finditer(english))
        if not opens:
            continue
        clean_en = english[opens[-1].end() :].strip()
        if not clean_en:
            continue
        extras[clean_en] = _after_last_escaped_page(spanish)
    for key in leaked_keys:
        del cache[key]
    added = 0
    for english, spanish in extras.items():
        if english in cache:
            continue
        cache[english] = spanish
        added += 1
    return added


def restore_tagged(english: str, spanish: str, pattern: re.Pattern[str]) -> str:
    originals = [match.group(2) for match in pattern.finditer(english)]
    index = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal index
        if index < len(originals):
            inner = originals[index]
            index += 1
            return f"{match.group(1)}{inner}{match.group(3)}"
        return match.group(0)

    return pattern.sub(repl, spanish)


def sanitize_button_inner(text: str) -> str:
    decoded = html.unescape(html.unescape(text))
    for src, dst in BUTTON_PUNCT.items():
        decoded = decoded.replace(src, dst)
    return (
        decoded.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def strip_f_buttons(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def repl(match: re.Match[str]) -> str:
        tag = match.group(2).upper()
        inner = sanitize_button_inner(match.group(3))
        found.append(f"&lt;{tag}&gt;{inner}&lt;/{tag}&gt;")
        return ""

    body = BUTTON_RE.sub(repl, text)
    body = re.sub(r"(?:&lt;br&gt;\s*)+$", "", body, flags=re.I).strip()
    return body, found


def compose_bilingual_page(english: str, spanish: str) -> str:
    """Spanish page. F-button text comes from the Spanish translation."""
    _en_body, en_buttons = strip_f_buttons(english)
    es_body, es_buttons = strip_f_buttons(spanish)
    buttons = es_buttons or en_buttons
    seen: set[str] = set()
    unique: list[str] = []
    for button in buttons:
        if button not in seen:
            seen.add(button)
            unique.append(button)
    return es_body + "".join(unique)


def polish_spanish(english: str, spanish: str) -> str:
    spanish = restore_tagged(english, spanish, BOLD_RE)
    spanish = spanish.replace(FORGE_HINT_EN, FORGE_HINT_ES)
    for calque, original in PLACE_NAME_FIXES:
        spanish = spanish.replace(calque, original)
    return spanish


def collect_unique(files: list[Path], cache: dict[str, str]) -> list[str]:
    unique: list[str] = []
    seen = set(cache.keys())
    for path in files:
        xml_text = path.read_text(encoding="utf-8")
        for original in pages_in_text(xml_text):
            if original in seen:
                continue
            if item.is_already_bilingual(original):
                continue
            seen.add(original)
            unique.append(original)
    return unique


def rewrite_dialog(xml_text: str, cache: dict[str, str], ascii_safe: bool) -> tuple[str, int]:
    applied = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal applied
        inner = match.group(2)
        if not inner.strip():
            return match.group(0)
        if item.is_already_bilingual(inner):
            return match.group(0)
        spanish_escaped = cache.get(inner)
        if spanish_escaped is None:
            return match.group(0)
        spanish_escaped = polish_spanish(inner, spanish_escaped)
        _en_body, en_buttons = strip_f_buttons(inner)
        es_body, es_buttons = strip_f_buttons(spanish_escaped)
        if ascii_safe:
            es_body = item.to_tera_html_entities(es_body)
        buttons = es_buttons or en_buttons
        seen: set[str] = set()
        unique: list[str] = []
        for button in buttons:
            if button not in seen:
                seen.add(button)
                unique.append(button)
        new_value = es_body + "".join(unique)
        applied += 1
        return f"{match.group(1)}{new_value}{match.group(3)}"

    return PAGE_RE.sub(repl, xml_text), applied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate TERA QuestDialog parchment pages to bilingual EN/ES."
    )
    parser.add_argument("input_path")
    parser.add_argument("-o", "--output-dir", default="output/QuestDialog")
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--no-ascii-entities", action="store_true")
    return parser.parse_args()


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
        files = list_dialog_files(input_path, args.start, args.count)
        if not files:
            print(f"No QuestDialog XML in {input_path}", file=sys.stderr)
            return 1
        print(
            f"Pack: {files[0].name} .. {files[-1].name} ({len(files)} files, start={args.start})",
            flush=True,
        )
    else:
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    cache = item.load_cache(cache_path)
    salvaged = salvage_leaked_cache(cache)
    if salvaged:
        print(f"Salvaged {salvaged} pages from leaked XML cache keys.", flush=True)
    unique = collect_unique(files, cache)
    print(f"Cache: {cache_path} ({len(cache)} known); missing {len(unique)}", flush=True)
    if unique:
        api_key = (item.GEMINI_API_KEY or "").strip() or os.environ.get(
            "GEMINI_API_KEY", ""
        ).strip()
        if api_key:
            client = item.build_client()
            item.fill_cache_in_batches(unique, client, cache, cache_path, batch_size)
        else:
            print("Leaving missing pages in English (no Gemini this pass).", flush=True)
    else:
        print("All non-empty pages are already in the cache.", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    applied_total = 0
    for path in files:
        raw = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in raw[:200] else b"\n"
        new_text, applied = rewrite_dialog(raw.decode("utf-8"), cache, ascii_safe)
        out = new_text.encode("utf-8")
        if newline == b"\r\n":
            out = out.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        dest = output_dir / f"{path.stem}_Translated{path.suffix}"
        dest.write_bytes(out)
        applied_total += applied
    item.save_cache(cache_path, cache)
    print(f"Wrote {len(files)} files, bilingual pages: {applied_total}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
