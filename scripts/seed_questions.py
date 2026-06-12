#!/usr/bin/env python3
"""
seed_questions.py — Puebla y revisa el banco de preguntas del QueryRouter.

Hace tres cosas:
  1. Carga las preguntas GENUINAS de _resources/preguntas_reales_godes_500_*.md,
     filtrando las meta-preguntas absurdas ("¿qué devolvería el sistema si…?",
     "¿cómo desambiguarías…?", etc.).
  2. Genera preguntas nuevas desde la BD (todos los parentescos y datos vitales,
     solo para personas que realmente tienen esos datos → respuesta verificable).
  3. Ejecuta el QA automático (auto_review): corre todo y verifica contra el
     oráculo de la BD, aprobando lo correcto y marcando los fallos reales.

Uso:
  python3 scripts/seed_questions.py            # carga + genera + auto-review
  python3 scripts/seed_questions.py --no-file  # solo generar desde BD + review
  python3 scripts/seed_questions.py --review-only
"""

import argparse
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

import database  # noqa: E402
import test_bank  # noqa: E402
from query_router import QueryRouter  # noqa: E402

QUESTIONS_MD = BASE_DIR / "_resources" / "preguntas_reales_godes_500_sin_repeticiones.md"
DB_PATH = BASE_DIR / "data" / "godesia.db"

# Patrones de meta-preguntas absurdas (un usuario real no las haría): hablan del
# SISTEMA, de desambiguación o de "qué registros competirían", no del árbol.
META_PATTERNS = [
    r"qu[eé]\s+devolver[ií]a\s+el\s+sistema",
    r"qu[eé]\s+deber[ií]a\s+responder\s+el\s+sistema",
    r"c[oó]mo\s+(?:deber[ií]a\s+)?(?:desambiguar|resolver|diferenciar|responder)",
    r"qu[eé]\s+estrategia\s+usar[ií]as",
    r"qu[eé]\s+registros?\s+competir[ií]an",
    r"qu[eé]\s+registro\s+corresponde\s+a",
    r"a\s+cu[aá]l\s+de\s+las\s+personas",
    r"qu[eé]\s+resultado\s+deber[ií]a\s+priorizarse",
    r"es\s+la\s+misma\s+persona",
    r"son\s+homónimos",
    r"sin\s+m[aá]s\s+contexto",
    r"qu[eé]\s+personas\s+podr[ií]an\s+coincidir",
    r"mejor\s+coincidencia\s+para",
    r"se\s+debe\s+considerar\s+igual",
    r"si\s+(?:pregunto|busco|consulto)\s+por\s+«",
    r"usando\s+a[ñn]o,?\s+lugar\s+o\s+familiares",
    r"si\s+no\s+se\s+especifica\s+a[ñn]o",
    r"a\s+qu[eé]\s+\w+\s+te\s+refieres",
    r"si\s+alguien\s+pregunta\s+«",
    r"cu[aá]l\s+de\s+los?\s+\w+.*podr[ií]a\s+ser",
    r"qu[eé]\s+personas\s+encajan",
]
_META_RX = re.compile("|".join(META_PATTERNS), re.I)


def load_file_questions():
    if not QUESTIONS_MD.exists():
        print(f"(no se encuentra {QUESTIONS_MD})")
        return [], 0
    genuine, filtered = [], 0
    for line in QUESTIONS_MD.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        q = re.sub(r"^\d+\.\s*", "", line).strip()
        if not q or len(q) < 8:
            continue
        if _META_RX.search(q):
            filtered += 1
            continue
        genuine.append(q)
    return genuine, filtered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-file", action="store_true", help="no cargar el .md")
    ap.add_argument("--review-only", action="store_true", help="solo auto-review")
    args = ap.parse_args()

    conn = database.get_connection(str(DB_PATH))
    router = QueryRouter(conn)

    if not args.review_only:
        if not args.no_file:
            genuine, filtered = load_file_questions()
            res = test_bank.add_questions(genuine, tags=["fichero"])
            print(f"Fichero: {len(genuine)} genuinas, {filtered} meta filtradas "
                  f"→ añadidas {res['added']}, duplicadas {res['skipped']}")
        gen = test_bank.generate_questions(conn)
        res = test_bank.add_questions(gen, tags=["generated"])
        print(f"Generadas desde BD: {len(gen)} → añadidas {res['added']}, duplicadas {res['skipped']}")

    print("\nEjecutando QA automático (run + oráculo)…")
    s = test_bank.auto_review(router)
    print(f"  Total casos:         {s['total']}")
    print(f"  Verificadas OK:      {s['verified_ok']}")
    print(f"  Fallos del oráculo:  {len(s['oracle_fail'])}  (bugs reales del router)")
    print(f"  Línea base:          {s['baseline']}")
    print(f"  No verificables:     {s['unverifiable']}")
    print(f"  Regresiones:         {s['regressions']}")
    if s["oracle_fail"]:
        print("\nPrimeros fallos del oráculo:")
        for f in s["oracle_fail"][:15]:
            print(f"  · {f['question'][:60]}")
            print(f"      {f['reason'][:120]}")


if __name__ == "__main__":
    main()
