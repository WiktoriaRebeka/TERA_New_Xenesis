# -*- coding: utf-8 -*-
"""Strip leftover French from repo output/ (report + fix).

Keeps EN proper names (places, creatures, skills). Spanish body stays.
Does NOT call Gemini.

Usage:
  python fix_output_fr.py              # fix output/
  python fix_output_fr.py --dry-run    # count only
  python fix_output_fr.py --ci         # same as default (output/)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"

# Longer first. FR → EN proper name or Spanish phrase.
REPLACEMENTS: list[tuple[str, str]] = [
    # Dungeons / places
    ("Labyrinthe de la Terreur", "Labyrinth of Terror"),
    ("Labyrinthe de la terreur", "Labyrinth of Terror"),
    ("Labyrinthe d'Azarel", "Azarel's Labyrinth"),
    ("Labyrinthe d'or", "Golden Labyrinth"),
    ("Labyrinthe d'Or", "Golden Labyrinth"),
    ("Labyrinthe d'or", "Golden Labyrinth"),
    ("Halls des Ombres", "Halls of Shadow"),
    ("Halls des ombres", "Halls of Shadow"),
    ("Lac des Larmes", "Lake of Tears"),
    ("Lac des larmes", "Lake of Tears"),
    ("Jardin de Seren", "Seren's Garden"),
    ("Station du Reliquaire", "Reliquary Station"),
    ("Tour d'ébène", "Ebon Tower"),
    ("Tour d'&amp;#233;b&amp;#232;ne", "Ebon Tower"),
    ("Tour d&#233;bène", "Ebon Tower"),
    ("Bâton de Killian", "Staff of Killian"),
    ("B&amp;#226;ton de Killian", "Staff of Killian"),
    ("Forteresse d'Essenia", "Essenia Fortress"),
    ("Grotte des pirates", "Pirate Grotto"),
    ("Grotte des Pirates", "Pirate Grotto"),
    ("Cavernes affamées", "Hungry Caverns"),
    ("Porte des dimensions", "Dimensional Gate"),
    ("Cage of Solitude", "Cage of Solitude"),
    # Creatures (FR labels in LinkCreature)
    ("phacoch&amp;#232;res longues-d&amp;#233;fenses", "Longtusk Warthogs"),
    ("phacoch&amp;#232;re longues-d&amp;#233;fenses", "Longtusk Warthog"),
    ("phacochères longues-défenses", "Longtusk Warthogs"),
    ("phacochère longues-défenses", "Longtusk Warthog"),
    ("phacoch&amp;#232;res baykuns", "Baykun Warthogs"),
    ("phacochères baykuns", "Baykun Warthogs"),
    ("phacoch&amp;#232;re brute", "Brute Warthog"),
    ("phacochère brute", "Brute Warthog"),
    ("phacoch&amp;#232;re", "Warthog"),
    ("phacochère", "Warthog"),
    ("fouaille-tripes", "Gutrend"),
    ("assommeur ca&amp;#239;man azur", "Azure Caiman Thumper"),
    ("assommeur caïman azur", "Azure Caiman Thumper"),
    ("t&amp;#233;l&amp;#233;portail", "Teleportal"),
    ("téléportail", "Teleportal"),
    ("téléportail de l'entrée du labyrinthe", "Golden Labyrinth entrance teleportal"),
    # Common FR leftover phrases → ES (LATAM tú)
    ("Une requête spéciale de la Fédération Valkyon.", "Una solicitud especial de la Valkyon Federation."),
    ("Une requ&amp;#234;te sp&amp;#233;ciale de la F&amp;#233;d&amp;#233;ration Valkyon.", "Una solicitud especial de la Valkyon Federation."),
    ("Affûtez vos compétences", "Afina tus habilidades"),
    ("Aff&amp;#251;tez vos comp&amp;#233;tences", "Afina tus habilidades"),
    ("Fédération Valkyon", "Valkyon Federation"),
    ("F&amp;#233;d&amp;#233;ration Valkyon", "Valkyon Federation"),
    ("Fédération", "Federación"),
    ("F&amp;#233;d&amp;#233;ration", "Federaci&amp;#243;n"),
    ("L'artisanat dans l'effort de guerre", "La artesanía en el esfuerzo de guerra"),
    ("Soutenez la Fédération", "Apoya a la Federación"),
    ("Avez-vous ouvert la Porte des dimensions", "¿Has abierto el Dimensional Gate"),
    ("Je savais que vous étiez destiné", "Sabía que estabas destinado"),
    ("Je vais retourner à Veli", "Voy a volver a Veli"),
    ("{@gender:press&amp;#233;/press&amp;#233;e}", "{@gender:ocupado/ocupada}"),
    ("{@gender:pressé/pressée}", "{@gender:ocupado/ocupada}"),
    ("révolutionnaire", "revolucionaria"),
    ("l'Intrépide", "Intrepid"),
    ("Tuez-en suffisamment pour", "Elimina suficientes para"),
    ("recevoir des augmentations de puissance spéciales", "recibir aumentos de potencia especiales"),
    ("brillant d'une lueur dorée", "brillando con un resplandor dorado"),
    ("Combat rapproché", "Close Quarters"),
    ("Combate rapproché", "Close Quarters"),
    ("Trait de rupture", "Breakaway Bolt"),
    ("Volonté", "Willpower"),
    ("Volont&amp;#233;", "Willpower"),
    ("enragés", "enojados"),
    ("enrag&amp;#233;s", "enojados"),
    ("Coup renversant", "Overhand Strike"),
    ("Portée d'attaque", "Attack range"),
    ("Port&amp;#233;e d'attaque", "Attack range"),
]

# Sheets under output/ (folder names without _Translated)
SKIP = {
    "AbuseLetterList",
    "ResourceSummary",
    "AnimationData",
    "SkillData",
    "BasicActionData",
    "StrSheet_Abnormality",
    "StrSheet_AbnormalityKind",
}


def apply_all(text: str) -> tuple[str, int]:
    n = 0
    for a, b in REPLACEMENTS:
        if a in text:
            c = text.count(a)
            text = text.replace(a, b)
            n += c
    # entity-encoded Labyrinthe variants
    text2, c = re.subn(
        r"Labyrinthe d(?:'|&#39;|&apos;)[Oo]r",
        "Golden Labyrinth",
        text,
        flags=re.I,
    )
    n += c
    text = text2
    text2, c = re.subn(
        r"Labyrinthe d(?:'|&#39;|&apos;)Azarel",
        "Azarel's Labyrinth",
        text,
        flags=re.I,
    )
    n += c
    return text2, n


def iter_xml(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            # flat output/StrSheet_UI-00000_Translated.xml
            if folder.suffix.lower() in {".xml"} or folder.name.endswith(".xml"):
                files.append(folder)
            continue
        if folder.name in SKIP:
            continue
        files.extend(sorted(folder.glob("*.xml*")))
    # also top-level Translated
    files.extend(sorted(root.glob("*_Translated.xml")))
    # dedupe
    seen: set[Path] = set()
    out: list[Path] = []
    for p in files:
        rp = p.resolve()
        if rp in seen or not p.is_file():
            continue
        seen.add(rp)
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ci", action="store_true", help="same as default root=output/")
    args = ap.parse_args()
    root = OUT if args.ci else args.root
    print(f"Fix FR in: {root}", flush=True)
    total = 0
    files_n = 0
    for path in iter_xml(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        new, n = apply_all(text)
        if n:
            files_n += 1
            total += n
            if not args.dry_run:
                path.write_text(new, encoding="utf-8", newline="\n")
    print(f"replacements={total} files={files_n} dry_run={args.dry_run}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
