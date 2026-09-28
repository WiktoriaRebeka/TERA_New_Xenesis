"""
Translate TERA MovieScript cutscene subtitles FR/EN -> Spanish-only.

Keeps duration/startTime from the French skeleton (match FR client videos).
When EN has the same number of Script lines for a movie id, translate from EN;
otherwise translate from French.

Usage:
    python translate_moviescript.py source/MovieScript
    python translate_moviescript.py source/MovieScript --limit 5
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

import translate_tooltips as item

REPO = Path(__file__).resolve().parent
DEFAULT_FR = REPO / "source" / "MovieScript"
DEFAULT_EN = REPO / "source_en" / "MovieScript"
DEFAULT_OUT = REPO / "output" / "MovieScript"
DEFAULT_CACHE = REPO / "cache" / "moviescript_translation_cache.json"

SCRIPT_RE = re.compile(r'(<Script\b[^>]*\bstring=")([^"]*)(")')
ID_RE = re.compile(r'\bid="([^"]+)"')

item.SYSTEM_PROMPT = """
You are an expert video game localizer. Translate TERA MMORPG cutscene / cinematic subtitles into Latin American Spanish.

Source lines may be English or French. Output Spanish only.
Keep the tone cinematic and high-fantasy. Address the player as "tú" (never vosotros). Never use "coger".
Keep proper names unchanged: Elleon, Velik, Samael, Kaligar, Lok, Argons, Valkyon, Velika, Island of Dawn, and other NPC / place / dungeon names. Prefer English spellings used in TERA EN (Elleon not Élion) when the source is French.
Keep HP, MP in English. Endurance = resistencia (never aguante).
Copy every __TAGn__ placeholder and any markup unchanged.
Do not add explanations, quotes, or the source language text.
Translate EVERY line. Return ONLY valid JSON: an array of Spanish strings, same length and order as the input.
""".strip()

item.OUTPUT_TEMPLATE = "{spanish}"
# Subtitles: real Unicode accents (like FR dump), not &amp;#NNN;
item.to_ascii_entities = lambda text: text  # type: ignore[assignment]


def load_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def movie_id(text: str) -> str | None:
    m = ID_RE.search(text)
    return m.group(1) if m else None


def script_strings(text: str) -> list[str]:
    return [m.group(2) for m in SCRIPT_RE.finditer(text)]


def index_by_id(folder: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in folder.glob("MovieScript-*.xml"):
        mid = movie_id(p.read_text(encoding="utf-8", errors="replace"))
        if mid:
            out[mid] = p
    return out


def unescape_attr(s: str) -> str:
    return html.unescape(s)


def escape_attr(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def looks_spanish_already(s: str) -> bool:
    if "Translated by TERA" in s:
        return True
    fr = re.search(r"\b(je|vous|nous|qu'il|n'est|avec|pour|dans|les|des)\b", s, re.I)
    es = re.search(r"\b(que|está|están|tú|pero|porque|también)\b", s, re.I)
    return bool(es and not fr)


def build_user_prompt(texts: list[str]) -> str:
    payload = json.dumps(texts, ensure_ascii=False)
    return (
        "Translate this JSON array of TERA cutscene subtitle lines into Latin American Spanish.\n"
        "Return a JSON array of Spanish strings with the same length and order.\n"
        "Preserve every __TAGn__ placeholder exactly.\n\n"
        f"{payload}"
    )


item.build_user_prompt = build_user_prompt  # type: ignore[assignment]


def choose_source_lines(fr_lines: list[str], en_lines: list[str] | None) -> list[str]:
    if en_lines is not None and len(en_lines) == len(fr_lines) and fr_lines:
        return en_lines
    return fr_lines


def out_name(src_name: str) -> str:
    if src_name.endswith("_Translated.xml"):
        return src_name
    if src_name.endswith(".xml"):
        return src_name[:-4] + "_Translated.xml"
    return src_name + "_Translated.xml"


def translate_needed(client, sources: list[str], cache: dict[str, str], cache_path: Path) -> None:
    unique: list[str] = []
    seen = set(cache)
    for s in sources:
        plain = unescape_attr(s)
        if not plain.strip():
            cache.setdefault(s, "")
            continue
        if s in seen:
            continue
        if looks_spanish_already(plain):
            cache[s] = plain
            seen.add(s)
            continue
        unique.append(s)
        seen.add(s)

    if not unique:
        return

    batch = item.BATCH_SIZE if item.BATCH_SIZE > 0 else 40
    total = len(unique)
    print(f"Translating {total} unique subtitle lines…", flush=True)
    for i in range(0, total, batch):
        chunk = unique[i : i + batch]
        plains = [unescape_attr(x) for x in chunk]
        print(f"  batch {i // batch + 1}/{(total + batch - 1) // batch} ({len(chunk)})", flush=True)
        results = item.translate_chunk(client, plains)
        for raw, plain in zip(chunk, plains):
            es = results.get(plain)
            if es is None:
                print(f"  WARNING: missing translation for: {plain[:60]!r}", flush=True)
                continue
            cache[raw] = es.strip()
        save_cache(cache_path, cache)
        if i + batch < total:
            time.sleep(item.BATCH_DELAY)


def apply_file(fr_text: str, sources: list[str], cache: dict[str, str]) -> str:
    idx = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal idx
        src = sources[idx]
        idx += 1
        es = cache.get(src)
        if es is None:
            return m.group(0)
        return m.group(1) + escape_attr(es) + m.group(3)

    return SCRIPT_RE.sub(repl, fr_text)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Translate TERA MovieScript cutscene subtitles FR/EN -> Spanish-only."
    )
    p.add_argument(
        "input_dir",
        nargs="?",
        default=str(DEFAULT_FR),
        help="FR timing skeleton folder (default: source/MovieScript)",
    )
    p.add_argument(
        "--en-dir",
        default=str(DEFAULT_EN),
        help="EN MovieScript folder (default: source_en/MovieScript)",
    )
    p.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUT),
        help="Output folder (default: output/MovieScript)",
    )
    p.add_argument("--cache", default=str(DEFAULT_CACHE))
    p.add_argument("--limit", type=int, default=0, help="Only first N movie files (0 = all)")
    p.add_argument("--batch-size", type=int, default=40)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    fr_dir = Path(args.input_dir)
    en_dir = Path(args.en_dir)
    out_dir = Path(args.output_dir)
    cache_path = Path(args.cache)

    if not fr_dir.is_dir():
        print(f"FR MovieScript folder missing: {fr_dir}", file=sys.stderr)
        return 1

    item.BATCH_SIZE = max(1, int(args.batch_size))
    en_by_id = index_by_id(en_dir) if en_dir.is_dir() else {}
    files = sorted(fr_dir.glob("MovieScript-*.xml"))
    if args.limit > 0:
        files = files[: args.limit]
    if not files:
        print(f"No MovieScript-*.xml in {fr_dir}", file=sys.stderr)
        return 1

    jobs: list[tuple[Path, str, list[str]]] = []
    all_sources: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        fr_text = path.read_text(encoding="utf-8", errors="replace")
        mid = movie_id(fr_text) or path.stem
        fr_lines = script_strings(fr_text)
        dest = out_dir / out_name(path.name)
        if not fr_lines:
            dest.write_text(fr_text, encoding="utf-8")
            continue
        en_path = en_by_id.get(mid)
        en_lines = (
            script_strings(en_path.read_text(encoding="utf-8", errors="replace"))
            if en_path
            else None
        )
        sources = choose_source_lines(fr_lines, en_lines)
        jobs.append((path, fr_text, sources))
        all_sources.extend(sources)

    cache = load_cache(cache_path)
    client = item.build_client()
    translate_needed(client, all_sources, cache, cache_path)

    applied = 0
    for path, fr_text, sources in jobs:
        new_text = apply_file(fr_text, sources, cache)
        (out_dir / out_name(path.name)).write_text(new_text, encoding="utf-8")
        applied += 1
    print(f"Wrote {applied} files to {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
