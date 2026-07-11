#!/usr/bin/env python3
"""Snapshot de las respuestas del router para todo el banco de tests.

Ejecuta cada pregunta de data/test_bank.json contra el QueryRouter actual y
guarda {case_id: answer} en el archivo indicado. Sirve para verificar que el
refactor de externalización de plantillas (fase 6 i18n) produce salida
byte-idéntica en español:

    python3 scripts/baseline_router_answers.py /tmp/baseline_pre.json
    ... refactor ...
    python3 scripts/baseline_router_answers.py /tmp/baseline_post.json
    diff <(jq -S . /tmp/baseline_pre.json) <(jq -S . /tmp/baseline_post.json)
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "backend"))

from database import get_connection  # noqa: E402
from query_router import QueryRouter  # noqa: E402


def main(out_path):
    bank = json.loads((BASE / "data" / "test_bank.json").read_text(encoding="utf-8"))
    cases = bank.get("cases", bank if isinstance(bank, list) else [])
    conn = get_connection(str(BASE / "data" / "godesia.db"))
    router = QueryRouter(conn)

    results = {}
    errors = 0
    for case in cases:
        cid = case.get("id") or case.get("case_id")
        question = case.get("question", "")
        try:
            r = router.route(question)
            results[cid] = {"answer": r.get("answer", ""),
                            "people": r.get("people_mentioned", [])}
        except Exception as e:
            results[cid] = {"error": f"{type(e).__name__}: {e}"}
            errors += 1

    Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=1, sort_keys=True),
                              encoding="utf-8")
    print(f"✓ {len(results)} casos → {out_path} ({errors} errores)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/router_baseline.json")
