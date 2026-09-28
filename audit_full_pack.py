# -*- coding: utf-8 -*-
"""Full pack audit: every XML line in every sheet (report only).

Scans the whole DataCenter folder for:
  - leftover French (player-facing text attrs)
  - &# numeric entities in world/UI label sheets (krzaki)
  - mojibake / U+FFFD

Does NOT edit files. Writes:
  cache/audit_fr.tsv
  cache/audit_encoding.tsv
  cache/audit_summary.txt

Usage:
  python audit_full_pack.py
  python audit_full_pack.py --root \"C:/.../DataCenter_Final_SE\"
  python audit_full_pack.py --ci          # repo output/
  python audit_full_pack.py --ci --root output
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
LIVE_SE = Path(r"C:\Users\wikto\Desktop\FRA TRANSLATED DATABASE\DataCenter_Final_SE")
CACHE = ROOT / "cache"

# Skip non-player / binary-ish path noise (asset names, swear filter lists)
SKIP_DIRS = {
    "AbuseLetterList",
    "ResourceSummary",
    "AnimationData",
    "SkillData",
    "BasicActionData",
    "StrSheet_Abnormality",
    "StrSheet_AbnormalityKind",
}

# Sheets where #NNN in labels breaks TERA color parsing
UNICODE_SHEETS = {
    "StrSheet_WorkObject",
    "StrSheet_UI",
    "StrSheet_Npc",
    "StrSheet_BuyMenu",
    "StrSheet_ZoneName",
    "StrSheet_Region",
    "StrSheet_Dungeon",
    "KeyMapLocalized",
}

# Real French markers — word-boundary Quête so Spanish "paquete" is NOT a hit
FR = re.compile(
    r"(?:"
    r"\bLabyrinthe\b|"
    r"\bFor[eê]t\b|"
    r"\bCath[eé]drale\b|"
    r"\bPalissade\b|"
    r"\bflammebois\b|"
    r"Lac des larmes|"
    r"Cavernes affam|"
    r"Cheval de guerre|"
    r"\bQu[eê]te\b|"
    r"s'active|"
    r"Faites en sorte|"
    r"Attaque finale|"
    r"Annuler l'|"
    r"Port&#233;e d'attaque|"
    r"Portée d'attaque|"
    r"Combat rapproch|"
    r"Coup renversant|"
    r"\benragés\b|"
    r"enrag&#233;s|"
    r"renvers&#233;/renvers|"
    r"\{@gender:renvers|"
    r"\bVolonté\b|"
    r"Volont&#233;|"
    r"d&#233;sespoir|"
    r"\bdésespoir\b|"
    r"seigneurs? de guerre|"
    r"force est dans|"
    r"En route pour|"
    r"Pour la Féd|"
    r"Parés pour|"
    r"Noyé dans|"
    r"Tir pour effet|"
    r"\bFédération\b|"
    r"l'obscurité|"
    r"l'offensive|"
    r"l'Intrépide|"
    r"\bcrépuscule\b|"
    r"Cuisiner avec|"
    r"\b[Pp]hacoch|"
    r"\bhy[eè]nes?\b|"
    r"\bB[uû]cheron\b|"
    r"\bf[eé]erique\b|"
    r"J'ai besoin|"
    r"quelle fleur|"
    r"\bcauchemardesque\b|"
    r"Il d&#233;clenche|"
    r"r&#233;sistance aux renvers|"
    r"\bTuez\b|"
    r"\bParlez-|"
    r"\bCollectez\b|"
    r"\bÉliminez\b|"
    r"\bEliminez\b|"
    r"appareil inconnu|"
    r"\bune lueur\b|"
    r"dans la vallée|"
    r"dans la fournaise|"
    r"\bdes ombres\b|"
    r"\bdes Pirates\b|"
    r"\bdu Bûcheron\b|"
    r"\bdu Bucheron\b"
    r")",
    re.I,
)

ENTITY = re.compile(r"(?:&amp;)?#(\d{2,6});")
MOJIBAKE = re.compile(
    r"(?:Ã.|Â.|â€™|â€œ|â€|ðŸ|Ã¡|Ã©|Ã­|Ã³|Ãº|Ã±|Â¿|Â¡|\ufffd)"
)
ATTR = re.compile(
    r'\b(id|string|name|toolTip|tooltip|dec|msg|description|'
    r"attackRange|attackDistance|classConcept|title)="
    r'"([^"]*)"'
)


def log(msg: str) -> None:
    print(msg, flush=True)


def resolve_root(ci: bool, root: Path | None) -> Path:
    if root is not None:
        return root
    if ci:
        return ROOT / "output"
    if LIVE_SE.is_dir():
        return LIVE_SE
    out = ROOT / "output"
    if out.is_dir():
        return out
    raise SystemExit("No pack root (pass --root or use --ci with output/)")


def iter_xml(pack: Path) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for folder in sorted(pack.iterdir()):
        if not folder.is_dir() or folder.name in SKIP_DIRS:
            continue
        # skip schema-only
        for path in sorted(folder.glob("*.xml")):
            rows.append((folder.name, path))
        for path in sorted(folder.glob("*.xml.xml")):
            rows.append((folder.name, path))
    return rows


def scan(pack: Path) -> tuple[list[str], list[str], Counter[str], Counter[str], int]:
    fr_rows = ["sheet\tfile\tid\tattr\tsnippet"]
    enc_rows = ["sheet\tfile\tid\tkind\tsnippet"]
    fr_by: Counter[str] = Counter()
    enc_by: Counter[str] = Counter()
    files = 0
    page_re = re.compile(
        r'<Page\b[^>]*>(.*?)</Page>|<Page\b[^>]*/>',
        re.I | re.S,
    )
    tag_attr_re = re.compile(
        r'<(?:String|HuntingZone|Quest|StoryGroup)\b([^>]*?)/?>',
        re.I | re.S,
    )

    def consider(sheet: str, fname: str, idv: str, key: str, blob: str) -> None:
        nonlocal fr_rows, enc_rows
        if not blob:
            return
        if FR.search(blob):
            fr_by[sheet] += 1
            fr_rows.append(
                f"{sheet}\t{fname}\t{idv}\t{key}\t{blob[:180].replace(chr(9), ' ').replace(chr(10), ' ')}"
            )
        kinds: list[str] = []
        if sheet in UNICODE_SHEETS and ENTITY.search(blob):
            kinds.append("entity")
        if MOJIBAKE.search(blob):
            kinds.append("mojibake")
        if kinds:
            enc_by[sheet] += 1
            enc_rows.append(
                f"{sheet}\t{fname}\t{idv}\t{'+'.join(kinds)}\t{blob[:180].replace(chr(9), ' ').replace(chr(10), ' ')}"
            )

    for sheet, path in iter_xml(pack):
        files += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        fname = path.name

        for m in tag_attr_re.finditer(text):
            body = m.group(1)
            attrs = dict(ATTR.findall(" " + body))
            idv = attrs.get("id", "")
            for key, blob in attrs.items():
                if key == "id":
                    continue
                consider(sheet, fname, idv, key, blob)

        for m in page_re.finditer(text):
            body = m.group(1) or ""
            if body:
                consider(sheet, fname, "", "page", body)

    return fr_rows, enc_rows, fr_by, enc_by, files


def main() -> int:
    ap = argparse.ArgumentParser(description="Full DataCenter FR/encoding audit")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--ci", action="store_true", help="Scan repo output/")
    args = ap.parse_args()

    pack = resolve_root(args.ci, args.root)
    CACHE.mkdir(parents=True, exist_ok=True)
    log(f"Audit root: {pack}")

    fr_rows, enc_rows, fr_by, enc_by, files = scan(pack)
    fr_n = len(fr_rows) - 1
    enc_n = len(enc_rows) - 1

    fr_tsv = CACHE / "audit_fr.tsv"
    enc_tsv = CACHE / "audit_encoding.tsv"
    summary = CACHE / "audit_summary.txt"
    fr_tsv.write_text("\n".join(fr_rows) + "\n", encoding="utf-8", newline="\n")
    enc_tsv.write_text("\n".join(enc_rows) + "\n", encoding="utf-8", newline="\n")

    lines = [
        f"root={pack}",
        f"xml_files_scanned={files}",
        f"fr_hits={fr_n}",
        f"encoding_hits={enc_n}",
        "",
        "FR by sheet:",
    ]
    for k, v in fr_by.most_common():
        lines.append(f"  {v:5d}  {k}")
    lines.append("")
    lines.append("Encoding by sheet:")
    for k, v in enc_by.most_common():
        lines.append(f"  {v:5d}  {k}")
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    log(f"XML files scanned: {files}")
    log(f"FR hits: {fr_n} -> {fr_tsv}")
    log(f"encoding hits: {enc_n} -> {enc_tsv}")
    log(f"summary -> {summary}")
    if fr_by:
        log("Top FR sheets:")
        for k, v in fr_by.most_common(15):
            log(f"  {v:5d}  {k}")
    log("Report only — no files were modified.")
    # CI: fail if FR or encoding in unicode sheets
    if args.ci and (fr_n > 0 or enc_n > 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
