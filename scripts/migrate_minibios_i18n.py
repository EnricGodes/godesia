#!/usr/bin/env python3
"""Migra minibios.json y anecdotas.json a estructura multiidioma.

  minibios:  {id, nombre, bio_es, bio_ca}        → {id, nombre, bio: {es, ca}}
  anecdotas: {titulo, texto, cta}                 → {titulo: {es}, texto: {es}, cta: {es}}

Idempotente: los registros ya migrados se dejan tal cual.
    python3 scripts/migrate_minibios_i18n.py
"""

import json
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


def migrate_minibios():
    path = DATA / "minibios.json"
    if not path.exists():
        print("  minibios.json no existe")
        return
    items = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for m in items:
        if isinstance(m.get("bio"), dict):
            continue
        bio = {}
        es = m.pop("bio_es", "")
        ca = m.pop("bio_ca", "")
        if es:
            bio["es"] = es
        if ca:
            bio["ca"] = ca
        m["bio"] = bio
        changed += 1
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  minibios.json: {changed} registros migrados de {len(items)}")


def migrate_anecdotas():
    path = DATA / "anecdotas.json"
    if not path.exists():
        print("  anecdotas.json no existe")
        return
    items = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for a in items:
        if isinstance(a.get("titulo"), dict):
            continue
        for field in ("titulo", "texto", "cta"):
            value = a.get(field, "")
            a[field] = {"es": value} if value else {}
        changed += 1
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  anecdotas.json: {changed} registros migrados de {len(items)}")


if __name__ == "__main__":
    migrate_minibios()
    migrate_anecdotas()
    sys.exit(0)
