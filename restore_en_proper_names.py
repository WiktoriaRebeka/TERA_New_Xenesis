# -*- coding: utf-8 -*-
"""Bulk-restore EN creature names in Spanish quest sheets (by EN string id).

Designed for GitHub Actions + local packs.

1. Short combat objectives (Defeat/Kill/…) missing EN Creature names
   → rewrite as ``Elimina a los {EN object}.``
2. LinkCreature labels from optional EN Creature dump (local) or skipped in CI.
3. Deshazte de → Elimina a.

Creature name list: cache/en_creature_names.txt (committed) or EN DataCenter.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
EN_QUEST = ROOT / "source" / "StrSheet_Quest"
CACHE_NAMES = ROOT / "cache" / "en_creature_names.txt"
CACHE_QUEST = ROOT / "cache" / "en_quest_by_id.tsv"
EN_DC = Path(r"C:\Users\wikto\Desktop\TERA BAZA DANYCH\Output\Output\DataCenter_Final_EUR")
FR_DC = Path(
    r"C:\Users\wikto\Desktop\TERA_DATABASE_FRA\outputfrances\output\DataCenter_Final_EUR"
)
# Prefer TERA_Translation EN source when present (local).
_TR_EN = Path(r"C:\Users\wikto\Desktop\TERA_Translation\source\StrSheet_Quest")
if _TR_EN.is_dir():
    EN_QUEST = _TR_EN

STRING_RE = re.compile(r'<String\b[^>]*\bid="(\d+)"[^>]*\bstring="([^"]*)"', re.I)
STRING_RE2 = re.compile(r'<String\b[^>]*\bstring="([^"]*)"[^>]*\bid="(\d+)"', re.I)
STRING_WRITE_RE = re.compile(
    r'(<String\b[^>]*\bid=")(\d+)("\s+string=")([^"]*)(")', re.I
)
LINK_RE = re.compile(r"\{@([Ll]ink[Cc]reature):(\d+)#(\d+)#([^}]*)\}")
NAME_ATTR_RE = re.compile(r'\bname="([^"]+)"')
HZ_RE = re.compile(
    r'<HuntingZone\b[^>]*\bid="(\d+)"[^>]*>(.*?)</HuntingZone>', re.S | re.I
)
COMBAT_EN = re.compile(
    r"^(?:Defeat|Eliminate|Kill|Destroy|Hunt|Slay)\s+(?:the\s+)?(.+?)\.?$", re.I
)
DESHAZTE_DE = re.compile(r"\b([Dd])eshazte de\b")
DESHAZTE = re.compile(r"\b([Dd])eshazte\b")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
HTMLISH = re.compile(r"[<{\\]|&#|&lt;|&gt;|<br", re.I)

SKIP = {
    "Guard",
    "Soldier",
    "Villager",
    "Merchant",
    "Patrol",
    "Slave",
    "Exit Teleportal",
    "Mission Board",
    "Teleportal",
    "Dummy",
    "None",
    "Test",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def decode(s: str) -> str:
    return (
        s.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )


def load_strings(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if CACHE_QUEST.is_file():
        for line in CACHE_QUEST.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip() or "\t" not in line:
                continue
            qid, en = line.split("\t", 1)
            out[qid] = decode(en)
        if out:
            return out
    if not folder.exists():
        return out
    for p in folder.glob("*.xml*"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for m in STRING_RE.finditer(t):
            out[m.group(1)] = decode(m.group(2))
        for m in STRING_RE2.finditer(t):
            out[m.group(2)] = decode(m.group(1))
    return out


def load_creature_names() -> tuple[set[str], dict[str, list[str]]]:
    found: set[str] = set()
    if CACHE_NAMES.is_file():
        for line in CACHE_NAMES.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if len(name) >= 4 and name not in SKIP:
                if " " in name or len(name) >= 6:
                    found.add(name)
    elif (EN_DC / "StrSheet_Creature").is_dir():
        for p in (EN_DC / "StrSheet_Creature").glob("*.xml*"):
            for m in NAME_ATTR_RE.finditer(p.read_text(encoding="utf-8", errors="replace")):
                name = decode(m.group(1)).strip()
                if len(name) < 4 or name in SKIP:
                    continue
                if " " not in name and len(name) < 6:
                    continue
                found.add(name)
    by_first: dict[str, list[str]] = defaultdict(list)
    for n in sorted(found, key=len, reverse=True):
        by_first[n.split()[0]].append(n)
    return found, dict(by_first)


def load_creatures_by_id(dc: Path) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    d = dc / "StrSheet_Creature"
    if not d.exists():
        return out
    for p in d.glob("*.xml*"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for hz in HZ_RE.finditer(t):
            zid, body = hz.group(1), hz.group(2)
            for m in re.finditer(
                r'<String\b[^>]*\bname="([^"]*)"[^>]*\btemplateId="(\d+)"', body
            ):
                out[(zid, m.group(2))] = decode(m.group(1)).strip()
            for m in re.finditer(
                r'<String\b[^>]*\btemplateId="(\d+)"[^>]*\bname="([^"]*)"', body
            ):
                out[(zid, m.group(1))] = decode(m.group(2)).strip()
    return out


def find_creature(text: str, name_set: set[str], by_first: dict[str, list[str]]) -> str | None:
    if text in name_set:
        return text
    if text.endswith("s") and text[:-1] in name_set:
        return text[:-1]
    lower = text.lower()
    best: str | None = None
    seen: set[str] = set()
    for w in WORD_RE.findall(text):
        for variant in {w, w.title(), (w[:1].upper() + w[1:]) if w else w}:
            if variant in seen:
                continue
            seen.add(variant)
            for cand in by_first.get(variant, ()):
                if cand.lower() in lower and (best is None or len(cand) > len(best)):
                    best = cand
    return best


def is_short_clean(s: str, limit: int = 80) -> bool:
    return len(s) <= limit and not HTMLISH.search(s)


def style_deshazte(s: str) -> str:
    s = DESHAZTE_DE.sub(
        lambda m: ("Elimina" if m.group(1).isupper() else "elimina") + " a", s
    )
    s = DESHAZTE.sub(lambda m: "Elimina" if m.group(1).isupper() else "elimina", s)
    return s


def rewrite_combat(
    en: str, es: str, name_set: set[str], by_first: dict[str, list[str]]
) -> str | None:
    en_s = en.strip()
    if not is_short_clean(en_s, 100):
        return None
    me = COMBAT_EN.match(en_s)
    if not me:
        return None
    en_obj = me.group(1).strip().rstrip(".")
    name = find_creature(en_obj, name_set, by_first)
    if not name or len(name) < 5:
        return None
    if name in es or name.lower() in es.lower():
        return None
    core = re.sub(r"^(?:the\s+)", "", en_obj, flags=re.I)
    if not (
        core.lower() == name.lower()
        or core.lower() == name.lower() + "s"
        or core.lower().startswith(name.lower())
        or len(name) * 2 >= len(core)
    ):
        return None
    return f"Elimina a los {en_obj}."


def apply_string(
    qid: str,
    spanish: str,
    en_map: dict[str, str],
    name_set: set[str],
    by_first: dict[str, list[str]],
) -> str:
    en = en_map.get(qid, "")
    out = spanish
    if en:
        rewritten = rewrite_combat(en, out, name_set, by_first)
        if rewritten is not None:
            return style_deshazte(rewritten)
    return style_deshazte(out)


def fix_quest_file(
    path: Path,
    en_map: dict[str, str],
    name_set: set[str],
    by_first: dict[str, list[str]],
) -> int:
    raw = path.read_text(encoding="utf-8", errors="replace")
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        qid, val = m.group(2), m.group(4)
        new = apply_string(qid, val, en_map, name_set, by_first)
        if new != val:
            n += 1
            return f"{m.group(1)}{qid}{m.group(3)}{new}{m.group(5)}"
        return m.group(0)

    new_raw = STRING_WRITE_RE.sub(repl, raw)
    if n:
        path.write_text(new_raw, encoding="utf-8", newline="\n")
    return n


def fix_links(path: Path, creatures: dict[tuple[str, str], str]) -> int:
    if not creatures:
        return 0
    raw = path.read_text(encoding="utf-8", errors="replace")
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        tag, zid, tid, label = m.group(1), m.group(2), m.group(3), m.group(4)
        en_name = creatures.get((zid, tid))
        if en_name and label != en_name:
            n += 1
            return "{@" + f"{tag}:{zid}#{tid}#{en_name}" + "}"
        return m.group(0)

    new_raw = LINK_RE.sub(repl, raw)
    if n:
        path.write_text(new_raw, encoding="utf-8", newline="\n")
    return n


def default_quest_dirs() -> list[Path]:
    dirs: list[Path] = []
    out = ROOT / "output" / "StrSheet_Quest"
    if out.is_dir():
        dirs.append(out)
    for p in (
        Path(r"C:\Users\wikto\Desktop\FRA TRANSLATED DATABASE\DataCenter_Final_EUR\StrSheet_Quest"),
        Path(r"C:\Users\wikto\Desktop\TERA_DATABASE_TRANSLATION\StrSheet_Quest"),
        Path(r"C:\Users\wikto\Desktop\TERA_DATABASE_FRA_TRANSLATION\StrSheet_Quest"),
    ):
        if p.is_dir() and p not in dirs:
            dirs.append(p)
    return dirs


def default_dialog_dirs() -> list[Path]:
    dirs: list[Path] = []
    for name in ("QuestDialog", "VillagerDialog"):
        out = ROOT / "output" / name
        if out.is_dir():
            dirs.append(out)
        for base in (
            Path(r"C:\Users\wikto\Desktop\FRA TRANSLATED DATABASE\DataCenter_Final_EUR"),
            Path(r"C:\Users\wikto\Desktop\TERA_DATABASE_TRANSLATION"),
            Path(r"C:\Users\wikto\Desktop\TERA_DATABASE_FRA_TRANSLATION"),
        ):
            d = base / name
            if d.is_dir() and d not in dirs:
                dirs.append(d)
    return dirs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quest-dir", action="append", type=Path, default=None)
    ap.add_argument("--ci", action="store_true", help="Only touch repo output/")
    args = ap.parse_args()

    log("Load Creature names…")
    name_set, by_first = load_creature_names()
    log(f"  names={len(name_set)}")
    en_ids = load_creatures_by_id(EN_DC) if EN_DC.is_dir() and not args.ci else {}
    log(f"  creature ids={len(en_ids)}")

    log("Load EN quest…")
    en_map = load_strings(EN_QUEST)
    log(f"  en={len(en_map)}")

    quest_dirs = args.quest_dir or (
        [ROOT / "output" / "StrSheet_Quest"] if args.ci else default_quest_dirs()
    )
    for qdir in quest_dirs:
        if not qdir.is_dir():
            log(f"SKIP {qdir}")
            continue
        qn = sum(
            fix_quest_file(p, en_map, name_set, by_first) for p in qdir.glob("*.xml*")
        )
        log(f"{qdir}: quest fixes={qn}")

    dialog_dirs = (
        [
            ROOT / "output" / "QuestDialog",
            ROOT / "output" / "VillagerDialog",
        ]
        if args.ci
        else default_dialog_dirs()
    )
    for d in dialog_dirs:
        if not d.is_dir():
            continue
        links = sum(fix_links(p, en_ids) for p in d.glob("*.xml*"))
        log(f"{d.name}: link_fixes={links}")

    log("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
