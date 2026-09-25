"""Build compact EN name tables for GitHub Actions (no full dump on CI)."""
from __future__ import annotations

import re
from pathlib import Path

EN = Path(r"C:\Users\wikto\Desktop\TERA BAZA DANYCH\Output\Output\DataCenter_Final_EUR")
OUT = Path(__file__).resolve().parent / "source_en"

ID_RE = re.compile(r'\bid="(\d+)"')
STR_RE = re.compile(r'\bstring="([^"]*)"')
NAME_RE = re.compile(r'\bname="([^"]*)"')
CLASS_RE = re.compile(r'\bclass="([^"]*)"')
GENDER_RE = re.compile(r'\bgender="([^"]*)"')
RACE_RE = re.compile(r'\brace="([^"]*)"')


def main() -> None:
    OUT.mkdir(exist_ok=True)
    seen: set[str] = set()
    rows = ["id\tstring"]
    for path in sorted((EN / "StrSheet_Item").glob("StrSheet_Item-*.xml*")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            ident = ID_RE.search(line)
            name = STR_RE.search(line)
            if not ident or not name or ident.group(1) in seen:
                continue
            seen.add(ident.group(1))
            rows.append(ident.group(1) + "\t" + name.group(1).replace("\t", " "))
    (OUT / "item_names.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("item names", len(seen), "bytes", (OUT / "item_names.tsv").stat().st_size)

    seen_k: set[tuple[str, str, str, str]] = set()
    rows = ["id\tclass\tgender\trace\tname"]
    for path in sorted((EN / "StrSheet_UserSkill").glob("StrSheet_UserSkill-*.xml*")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            ident = ID_RE.search(line)
            name = NAME_RE.search(line)
            if not ident or not name:
                continue
            cls = CLASS_RE.search(line)
            gender = GENDER_RE.search(line)
            race = RACE_RE.search(line)
            key = (
                ident.group(1),
                cls.group(1) if cls else "",
                gender.group(1) if gender else "",
                race.group(1) if race else "",
            )
            if key in seen_k:
                continue
            seen_k.add(key)
            rows.append(
                "\t".join((*key, name.group(1).replace("\t", " ")))
            )
    (OUT / "skill_names.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("skill names", len(seen_k), "bytes", (OUT / "skill_names.tsv").stat().st_size)


if __name__ == "__main__":
    main()
