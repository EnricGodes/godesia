#!/usr/bin/env python3
"""Rellena desde el GEDCOM los datos que el importador dejaba caer.

Hoy: fecha, lugar y nota del divorcio (marriages.divorce_*).

sync_catalog.py leía "1 DIV Y" pero descartaba sus subetiquetas (2 DATE / 2 PLAC
/ 2 NOTE), así que esas tres columnas quedaban vacías y el router no podía
responder por los divorcios. Ya está corregido allí; este script aplica el dato
a la BD en uso sin tener que reimportar el catálogo entero.

    python3 scripts/backfill_gedcom_gaps.py docs/<fichero>.ged [--dry-run]
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "backend"))
from database import convert_date_to_spanish        # noqa: E402


def parse_divorces(ged_path):
    """{fam_id: {date, place, note}} para cada familia con divorcio."""
    lines = Path(ged_path).read_text(encoding="utf-8", errors="replace").splitlines()
    out, fam = {}, None
    for i, line in enumerate(lines):
        m = re.match(r"^0\s+(@F\w+@)\s+FAM", line)
        if m:
            fam = m.group(1)
            continue
        if fam and line.startswith("1 DIV"):
            div = {"date": None, "place": None, "note": None}
            j = i + 1
            while j < len(lines) and lines[j].startswith("2"):
                sub = lines[j]
                if "DATE" in sub and not div["date"]:
                    div["date"] = sub.split("DATE", 1)[1].strip()
                elif "PLAC" in sub and not div["place"]:
                    div["place"] = sub.split("PLAC", 1)[1].strip()
                elif "NOTE" in sub and not div["note"]:
                    div["note"] = sub.split("NOTE", 1)[1].strip()
                j += 1
            out[fam] = div
    return out


def fam_spouses(ged_path):
    """{fam_id: (husb, wife)} para localizar el matrimonio en la BD."""
    lines = Path(ged_path).read_text(encoding="utf-8", errors="replace").splitlines()
    out, fam, husb, wife = {}, None, None, None
    for line in lines:
        m = re.match(r"^0\s+(@F\w+@)\s+FAM", line)
        if m:
            if fam:
                out[fam] = (husb, wife)
            fam, husb, wife = m.group(1), None, None
            continue
        if fam and line.startswith("1 HUSB"):
            husb = re.search(r"@I\w+@", line).group(0)
        elif fam and line.startswith("1 WIFE"):
            wife = re.search(r"@I\w+@", line).group(0)
    if fam:
        out[fam] = (husb, wife)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gedcom")
    ap.add_argument("--db", default=str(BASE / "data" / "godesia.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    divorces, spouses = parse_divorces(args.gedcom), fam_spouses(args.gedcom)
    conn = sqlite3.connect(args.db)
    applied = skipped = 0
    for fam, div in divorces.items():
        husb, wife = spouses.get(fam, (None, None))
        if not (husb and wife):
            continue
        date = convert_date_to_spanish(div["date"]) if div["date"] else None
        row = conn.execute(
            "SELECT id FROM marriages WHERE (person1_id=? AND person2_id=?) "
            "OR (person1_id=? AND person2_id=?)", (husb, wife, wife, husb)).fetchone()
        if not row:
            print(f"  {fam}: sin matrimonio en la BD ({husb} × {wife})")
            skipped += 1
            continue
        print(f"  {fam} ({husb} × {wife}): fecha={date!r} lugar={div['place']!r}")
        if not args.dry_run:
            conn.execute(
                "UPDATE marriages SET divorce_date=?, divorce_place=?, "
                "divorce_note=COALESCE(?, divorce_note, 'Y') WHERE id=?",
                (date, div["place"], div["note"], row[0]))
        applied += 1
    if not args.dry_run:
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print(f"\n{applied} divorcios {'a aplicar' if args.dry_run else 'aplicados'}, {skipped} sin matrimonio en la BD")
    conn.close()


if __name__ == "__main__":
    main()
