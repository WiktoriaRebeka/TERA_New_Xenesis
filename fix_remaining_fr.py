# -*- coding: utf-8 -*-
"""Fix remaining FR leftovers in output/ using ID restore map + phrase map.

Uses data/fr_restore_map.json (SE/EN values by sheet+id+attr).
Then applies dialog/place phrase replacements.
No Gemini.

Usage:
  python fix_remaining_fr.py
  python fix_remaining_fr.py --ci
  python fix_remaining_fr.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
MAP_PATH = ROOT / "data" / "fr_restore_map.json"

# Dialog / inline leftovers (longer first)
PHRASES: list[tuple[str, str]] = [
    ("Palissade du B&amp;#251;cheron", "Woodcutter Palisade"),
    ("Palissade du Bûcheron", "Woodcutter Palisade"),
    ("Palissade du Bucheron", "Woodcutter Palisade"),
    ("Teleportal de l'entr&amp;#233;e du labyrinthe", "Golden Labyrinth entrance teleportal"),
    ("Teleportal de l'entrée du labyrinthe", "Golden Labyrinth entrance teleportal"),
    ("téléportail de l'entrée du labyrinthe", "Golden Labyrinth entrance teleportal"),
    ("Cavernes affam&amp;#233;es", "Hungry Caverns"),
    ("Cavernes affamées", "Hungry Caverns"),
    ("Cage de la Solitude", "Cage of Solitude"),
    ("seigneurs de guerre baykuns", "Baykun Warlords"),
    ("seigneurs de guerre", "Warlords"),
    ("brillant d'une lueur dor&amp;#233;e", "brillando con un resplandor dorado"),
    ("brillant d'une lueur dorée", "brillando con un resplandor dorado"),
    ("une fois la quête acceptée", "una vez aceptada la misión"),
    ("une fois la qu&amp;#234;te accept&amp;#233;e", "una vez aceptada la misi&amp;#243;n"),
    ("Nécromanciens", "Necromancers"),
    ("N&amp;#233;cromanciens", "Necromancers"),
    ("Cheval de guerre des ombres", "Shadow Warhorse"),
    ("Guerre de guilde", "Guild War"),
    ("Repaire d'Akasha", "Akasha's Hideout"),
    ("Forteresse de T&amp;#233;n&amp;#233;bris", "Bastion of Darkness"),
    ("Forteresse de Ténébris", "Bastion of Darkness"),
    ("Akasha cauchemardesque", "Nightmare Akasha"),
    ("Kaylus cauchemardesque", "Nightmare Kalligar"),
    ("Darniv cauchemardesque", "Nightmare Darkan"),
    ("Thalweg cauchemardesque", "Nightmare Thalweg"),
    ("Krakatox cauchemardesque", "Nightmare Krakatox"),
    ("cauchemardesque", "Nightmare"),
    ("Combat rapproch&amp;#233;", "Close Quarters"),
    ("Combat rapproché", "Close Quarters"),
    ("combat rapproch&amp;#233;", "Close Quarters"),
    ("combat rapproché", "Close Quarters"),
    ("Contre-attaque finale", "Final Counterattack"),
    ("Implosion &amp;#233;lectrique", "Electric Implosion"),
    ("Implosion électrique", "Electric Implosion"),
    ("Danse des ombres", "Shadow Dance"),
    ("Attaque finale", "Final Attack"),
    ("Tir pour effet", "Fire for Effect"),
    ("Port&#233;e d'attaque&#160;: courte", "Attack range: short"),
    ("Port&#233;e d'attaque&#160;: combat rapproch&#233;", "Attack range: melee"),
    ("Port&#233;e d'attaque&#160;: moyenne", "Attack range: medium"),
    ("Port&#233;e d'attaque&#160;: longue", "Attack range: long"),
    ("Portée d'attaque", "Attack range"),
    ("Port&amp;#233;e d'attaque", "Attack range"),
    ("[Enchaînement]", "[Combo]"),
    ("[Encha&amp;#238;nement]", "[Combo]"),
    ("[Enchaînement possible]", "[Combo]"),
    ("[Encha&amp;#238;nement possible]", "[Combo]"),
    ("Enchaînement possible", "Combo"),
    ("Encha&amp;#238;nement possible", "Combo"),
    ("Glyphe d'enchaînement de puissance", "Powerlinked Glyph"),
    ("Glyphe d'encha&#238;nement de puissance", "Powerlinked Glyph"),
    ("enrag&#233;s", "enojados"),
    ("enragés", "enojados"),
    ("Malaise del d&#233;sespoir", "Despair Debuff"),
    ("Malaise del désespoir", "Despair Debuff"),
    ("d&#233;sespoir", "despair"),
    ("désespoir", "despair"),
    ("Volont&#233; de fer", "Iron Will"),
    ("Volonté de fer", "Iron Will"),
    ("Noble volont&#233;", "Noble Willpower"),
    ("Noble volonté", "Noble Willpower"),
    ("Volont&#233; du commandant", "Commander's Willpower"),
    ("Volonté du commandant", "Commander's Willpower"),
    ("Volont&#233;", "Willpower"),
    ("Volonté", "Willpower"),
    ("[Gemme]", "[Gem]"),
    ("Phacoch&#232;re longues-d&#233;fenses", "Longtusk Warthog"),
    ("Phacochère longues-défenses", "Longtusk Warthog"),
    ("flammebois", "flamewood"),
    ("Flammebois", "Flamewood"),
    ("Grotte des pirates", "Pirate Grotto"),
    ("Grotte des Pirates", "Pirate Grotto"),
]

SHEET_DIRS = {
    "StrSheet_HeroSkin": "StrSheet_HeroSkin",
    "StrSheet_Quest": "StrSheet_Quest",
    "StrSheet_Passivity": "StrSheet_Passivity",
    "StrSheet_MonsterBehavior": "StrSheet_MonsterBehavior",
    "StrSheet_Achievement": "StrSheet_Achievement",
    "StrSheet_UserSkill": "StrSheet_UserSkill",
    "StrSheet_Tutorial": "StrSheet_Tutorial",
    "StrSheet_Item": "StrSheet_Item",
    "StrSheet_Crest": "StrSheet_Crest",
    "StrSheet_EpPerkData": "StrSheet_EpPerkData",
    "StrSheet_HeroSkill": "StrSheet_HeroSkill",
    "StrSheet_Card": "StrSheet_Card",
    "StrSheet_DungeonRank": "StrSheet_DungeonRank",
    "StrSheet_LoadingImage": "StrSheet_LoadingImage",
    "StrSheet_SkillPolishingEffect": "StrSheet_SkillPolishingEffect",
}


def escape_attr(val: str) -> str:
    """Value already XML-attr escaped in map; ensure quotes safe."""
    return val.replace('"', "&quot;")


def replace_attr_in_tag(tag_body: str, attr: str, new_val: str) -> tuple[str, bool]:
    """Replace attr=\"...\" inside an open-tag body. Handles toolTip/tooltip."""
    alts = [attr]
    if attr.lower() == "tooltip":
        alts = ["toolTip", "tooltip", "ToolTip"]
    for a in alts:
        pat = re.compile(rf'(\b{re.escape(a)}=")([^"]*)(")')
        m = pat.search(tag_body)
        if m:
            return pat.sub(rf'\1{escape_attr(new_val)}\3', tag_body, count=1), True
    return tag_body, False


def apply_id_restores(root: Path, items: list[dict], dry: bool) -> tuple[int, int]:
    by_sheet: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_sheet[it["sheet"]].append(it)

    files_n = 0
    hits = 0
    # Match any tag that has id="N"
    tag_re = re.compile(
        r"<(String|HuntingZone|Quest|StoryGroup|Skill|Passivity|Crest|Card|"
        r"Rank|Msg|HeroSkill|Perk|Effect|Tutorial|Item|Npc)\b([^>]*?)/?>",
        re.I | re.S,
    )

    for sheet, rows in by_sheet.items():
        # HeroSkill reuses the same id across templateId skins — phrases only.
        if sheet == "StrSheet_HeroSkill":
            print("  skip id-restore StrSheet_HeroSkill (duplicate ids)", flush=True)
            continue
        folder_name = SHEET_DIRS.get(sheet, sheet)
        paths: list[Path] = []
        d = root / folder_name
        if d.is_dir():
            paths.extend(sorted(d.glob("*.xml*")))
        paths.extend(sorted(root.glob(f"{folder_name}*_Translated.xml")))
        paths.extend(sorted(root.glob(f"{folder_name}*.xml")))
        # dedupe
        seen: set[Path] = set()
        uniq: list[Path] = []
        for p in paths:
            rp = p.resolve()
            if rp in seen or not p.is_file() or p.name.endswith(".xsd"):
                continue
            seen.add(rp)
            uniq.append(p)

        want: dict[str, list[dict]] = defaultdict(list)
        for it in rows:
            want[it["id"]].append(it)

        for path in uniq:
            text = path.read_text(encoding="utf-8", errors="replace")
            changed = 0

            def repl(m: re.Match[str]) -> str:
                nonlocal changed
                body = m.group(2)
                idm = re.search(r'\bid="(\d+)"', body)
                if not idm:
                    return m.group(0)
                iid = idm.group(1)
                if iid not in want:
                    return m.group(0)
                new_body = body
                for it in want[iid]:
                    new_body, ok = replace_attr_in_tag(new_body, it["attr"], it["value"])
                    if ok:
                        changed += 1
                return m.group(0).replace(body, new_body, 1)

            new_text = tag_re.sub(repl, text)
            if changed and new_text != text:
                files_n += 1
                hits += changed
                if not dry:
                    path.write_text(new_text, encoding="utf-8", newline="\n")
                print(f"  id-restore {path.relative_to(root)}: {changed}", flush=True)
    return files_n, hits


def apply_phrases(root: Path, dry: bool) -> tuple[int, int]:
    files_n = 0
    hits = 0
    targets: list[Path] = []
    for folder in (
        "QuestDialog",
        "VillagerDialog",
        "StrSheet_Quest",
        "StrSheet_Passivity",
        "StrSheet_UserSkill",
        "StrSheet_Tutorial",
        "StrSheet_Item",
        "StrSheet_Crest",
        "StrSheet_HeroSkin",
        "StrSheet_HeroSkill",
        "StrSheet_Achievement",
        "StrSheet_MonsterBehavior",
        "StrSheet_EpPerkData",
        "StrSheet_Card",
        "StrSheet_DungeonRank",
        "StrSheet_LoadingImage",
        "StrSheet_SkillPolishingEffect",
    ):
        d = root / folder
        if d.is_dir():
            targets.extend(sorted(d.glob("*.xml*")))
    targets.extend(sorted(root.glob("*_Translated.xml")))
    seen: set[Path] = set()
    for path in targets:
        rp = path.resolve()
        if rp in seen or not path.is_file():
            continue
        seen.add(rp)
        text = path.read_text(encoding="utf-8", errors="replace")
        n = 0
        new = text
        for a, b in PHRASES:
            if a in new:
                c = new.count(a)
                new = new.replace(a, b)
                n += c
        # labyrinthe leftover in link names (case)
        new2, c = re.subn(r"\blabyrinthe\b", "labyrinth", new, flags=re.I)
        n += c
        new = new2
        if n and new != text:
            files_n += 1
            hits += n
            if not dry:
                path.write_text(new, encoding="utf-8", newline="\n")
            print(f"  phrase {path.relative_to(root)}: {n}", flush=True)
    return files_n, hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=OUT)
    ap.add_argument("--ci", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--map", type=Path, default=MAP_PATH)
    args = ap.parse_args()
    root = OUT if args.ci else args.root
    print(f"Fix remaining FR in: {root}", flush=True)
    if not args.map.is_file():
        print(f"MISSING map: {args.map}", flush=True)
        return 1
    items = json.loads(args.map.read_text(encoding="utf-8"))
    print(f"map entries: {len(items)}", flush=True)
    f1, h1 = apply_id_restores(root, items, args.dry_run)
    print(f"id-restore files={f1} attrs={h1}", flush=True)
    f2, h2 = apply_phrases(root, args.dry_run)
    print(f"phrases files={f2} hits={h2}", flush=True)
    print(f"TOTAL files~={f1 + f2} changes~={h1 + h2} dry_run={args.dry_run}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
