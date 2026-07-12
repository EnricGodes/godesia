#!/usr/bin/env python3
"""Harness de paridad es↔lang para el QueryRouter multiidioma.

Para cada caso (emparejado por id) rutea EN VIVO la pregunta española (lang=es)
y la traducida (lang=<lang>), y compara people_mentioned + unresolved. El
objetivo es 100%: la reescritura debe resolver a las mismas personas que el
español. Independiente de los snapshots del banco (que pueden estar obsoletos).

    python3 scripts/parity_check.py --lang ca [--limit N] [--show 40]
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "backend"))

from database import get_connection            # noqa: E402
from query_router import QueryRouter           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ca")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--show", type=int, default=40, help="máx. desajustes a listar")
    ap.add_argument("--filter", default="", help="substring para filtrar preguntas es")
    args = ap.parse_args()

    es_cases = json.loads((BASE / "data" / "test_bank.json").read_text())["cases"]
    lang_cases = {c["id"]: c for c in
                  json.loads((BASE / f"data/test_bank.{args.lang}.json").read_text())["cases"]}

    conn = get_connection(str(BASE / "data" / "godesia.db"))
    router = QueryRouter(conn)

    total = mism = 0
    es_res_total = es_res_mism = 0     # solo casos que el español SÍ resuelve
    es_unres_ca_res = 0                # es no resuelve pero ca sí (bonus, no fallo)
    mismatches = []
    hard = []                          # fallos reales (es resuelto, ca difiere)
    handler_diffs = Counter()
    for c in es_cases:
        q_es = c["question"]
        lc = lang_cases.get(c["id"])
        if not lc:
            continue
        q_lang = lc["question"]
        if args.filter and args.filter.lower() not in q_es.lower():
            continue
        total += 1
        if args.limit and total > args.limit:
            total -= 1
            break

        r_es = router.route(q_es, lang="es")
        det_es = getattr(router, "_detected_lang", "es")
        r_lang = router.route(q_lang, lang=args.lang)
        rewritten = _last_rewrite(router, q_lang, args.lang)

        p_es = r_es.get("people_mentioned", [])
        p_lang = r_lang.get("people_mentioned", [])
        ue, ul = r_es.get("unresolved"), r_lang.get("unresolved")
        ok = (p_es == p_lang) and (ue == ul)
        if det_es != "es":       # el español no debe reescribirse nunca
            ok = False
        rec = {"id": c["id"], "es": q_es, "lang": q_lang, "rewritten": rewritten,
               "people_es": p_es, "people_lang": p_lang,
               "unres_es": ue, "unres_lang": ul, "es_detected": det_es}
        # Métrica dura: SOLO los casos que el español resuelve son objetivo de
        # paridad (donde el español no responde, no hay verdad que replicar).
        if not ue:
            es_res_total += 1
            if not ok:
                es_res_mism += 1
                hard.append(rec)
        elif not ul:
            es_unres_ca_res += 1
        if not ok:
            mism += 1
            mismatches.append(rec)

    hard_pct = 100*(es_res_total-es_res_mism)/es_res_total if es_res_total else 100
    print(f"\n=== Paridad {args.lang} ===")
    print(f"  DURA (casos que el español resuelve): "
          f"{es_res_total-es_res_mism}/{es_res_total} ({hard_pct:.1f}%) — "
          f"{es_res_mism} fallos reales")
    print(f"  bruta (todos): {total-mism}/{total} ({100*(total-mism)/total:.1f}%)")
    print(f"  es no resuelve pero ca sí (bonus, no fallo): {es_unres_ca_res}\n")
    mismatches = hard  # mostrar solo fallos reales
    for m in mismatches[:args.show]:
        print(f"[{m['id']}] es_detect={m['es_detected']}")
        print(f"  ES : {m['es']}")
        print(f"  {args.lang.upper()} : {m['lang']}")
        print(f"  ->  {m['rewritten']}")
        print(f"  people es={m['people_es']} | {args.lang}={m['people_lang']}"
              f" | unres es={m['unres_es']}/{m['unres_lang']}")
        print()

    # patrones de fallo: primeras palabras de la reescritura fallida
    if mismatches:
        heads = Counter(" ".join(m["rewritten"].split()[:4]) for m in mismatches)
        print("--- cabeceras de reescritura más frecuentes en fallos ---")
        for h, n in heads.most_common(15):
            print(f"  {n:3d}  {h}")


def _last_rewrite(router, q, lang):
    try:
        from query_router import _clean_question
        out, _ = router._rewriter.rewrite(_clean_question(q), ui_lang=lang)
        return out
    except Exception as e:
        return f"(rewrite error: {e})"


if __name__ == "__main__":
    main()
