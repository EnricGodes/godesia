#!/usr/bin/env python3
"""Harness de regresión del QueryRouter contra el banco GEDCOM de verdad.

Enruta las 1000 preguntas de `data/gedcom_test_bank_es.json` (que traen la
respuesta correcta y metacampos) y las clasifica en PASS / FAIL / UNRESOLVED
comparando la salida del router con la respuesta del banco según `answer_type`:

  · person_list (trae answer_entity_ids): match EXACTO de IDs
        set(answer_entity_ids) == people_mentioned − {person_id}
  · place / place_list : contención normalizada de cada valor esperado
  · date               : a nivel de AÑO (el router reduce fechas GEDCOM a año)
  · text / text_list / age : contención normalizada

Congela un baseline (`data/gedcom_regression_baseline.json`, {id: estado}) y en
cada ejecución reporta REGRESIONES (baseline pass → ahora no) y MEJORAS (fail →
pass). Uso al crear patrones nuevos: implementar → correr → 0 regresiones →
`--update-baseline` → commit.

    python3 scripts/regression_check.py [--category X] [--type X] [--show N]
                                        [--update-baseline] [--only-regressions]

Sale con código ≠ 0 si hay regresiones (uso tipo CI).
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "backend"))

from database import get_connection            # noqa: E402
from query_router import QueryRouter           # noqa: E402

BANK_PATH = BASE / "data" / "gedcom_test_bank_es.json"
BASELINE_PATH = BASE / "data" / "gedcom_regression_baseline.json"

PASS, FAIL, UNRESOLVED = "pass", "fail", "unresolved"

_TAG_RE = re.compile(r"<[^>]+>")
_YEAR_RE = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def _plain(html):
    return _TAG_RE.sub("", html or "")


def _norm(s):
    """Minúsculas, sin acentos, solo alfanumérico separado por espacios."""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _years(s):
    return set(_YEAR_RE.findall(str(s)))


def _as_list(v):
    return v if isinstance(v, list) else [v]


def classify(case, result):
    """Devuelve PASS / FAIL / UNRESOLVED para un caso ya enrutado."""
    if result.get("unresolved"):
        return UNRESOLVED
    at = case.get("answer_type")
    plain = _plain(result.get("answer", ""))

    # Personas: verdad por IDs (independiente del texto).
    if case.get("answer_entity_ids") is not None:
        got = set(result.get("people_mentioned") or []) - {case.get("person_id")}
        return PASS if got == set(case["answer_entity_ids"]) else FAIL

    if at == "date":
        exp = _years(case["answer"])
        return PASS if exp and exp <= _years(plain) else FAIL

    if at in ("place", "place_list", "text", "text_list", "age"):
        nplain = _norm(plain)
        # Cada valor esperado (recortado a un prefijo estable) debe aparecer.
        for e in _as_list(case["answer"]):
            e = str(e).strip()
            if not e:
                continue
            needle = _norm(e)
            if not needle:
                continue
            if needle[:25] not in nplain:
                return FAIL
        return PASS

    return FAIL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="", help="filtra por category del banco")
    ap.add_argument("--type", default="", help="filtra por answer_type")
    ap.add_argument("--show", type=int, default=25, help="máx. fallos a listar")
    ap.add_argument("--update-baseline", action="store_true",
                    help="recongela el baseline con el estado actual")
    ap.add_argument("--only-regressions", action="store_true",
                    help="lista solo las regresiones")
    ap.add_argument("--lang", default="es",
                    help="idioma del banco/enrutado (es|ca|en|fr); usa gedcom_test_bank_<lang>.json")
    ap.add_argument("--parity", action="store_true",
                    help="mide si <lang> resuelve IGUAL que es (people_mentioned+unresolved), "
                         "ignorando el idioma del texto de la respuesta. Métrica correcta "
                         "para validar los reescritores ca/en/fr.")
    args = ap.parse_args()

    if args.parity and args.lang != "es":
        _run_parity(args)
        return

    bank_path = (BANK_PATH if args.lang == "es"
                 else BASE / "data" / f"gedcom_test_bank_{args.lang}.json")
    baseline_path = (BASELINE_PATH if args.lang == "es"
                     else BASE / "data" / f"gedcom_regression_baseline_{args.lang}.json")
    bank = json.loads(bank_path.read_text())
    baseline = {}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text())

    conn = get_connection(str(BASE / "data" / "godesia.db"))
    router = QueryRouter(conn)

    states = {}
    by_cat = defaultdict(lambda: {"pass": 0, "fail": 0, "unresolved": 0})
    regressions, improvements, fails = [], [], []
    for c in bank:
        if args.category and c.get("category") != args.category:
            continue
        if args.type and c.get("answer_type") != args.type:
            continue
        res = router.route(c["question"], lang=args.lang)
        st = classify(c, res)
        states[c["id"]] = st
        by_cat[c["category"]][st] += 1
        rec = {"id": c["id"], "q": c["question"], "cat": c["category"],
               "at": c["answer_type"], "expected": c["answer"],
               "answer": _plain(res.get("answer", ""))[:100],
               "exp_ids": c.get("answer_entity_ids"),
               "got_ids": sorted(set(res.get("people_mentioned") or [])
                                 - {c.get("person_id")}),
               "state": st}
        prev = baseline.get(c["id"])
        if prev == PASS and st != PASS:
            regressions.append(rec)
        elif prev is not None and prev != PASS and st == PASS:
            improvements.append(rec)
        if st != PASS:
            fails.append(rec)

    total = len(states)
    npass = sum(1 for s in states.values() if s == PASS)
    nunres = sum(1 for s in states.values() if s == UNRESOLVED)
    print(f"\n=== Regresión banco GEDCOM ({total} preguntas) ===")
    print(f"  PASS {npass}/{total} ({100*npass//max(total,1)}%) | "
          f"FAIL {total-npass-nunres} | UNRESOLVED {nunres}")
    print(f"  vs baseline: REGRESIONES={len(regressions)} MEJORAS={len(improvements)}"
          + ("  (sin baseline)" if not baseline else ""))

    print("\n--- por categoría (pass/total, unresolved) ---")
    for cat in sorted(by_cat):
        d = by_cat[cat]
        t = d["pass"] + d["fail"] + d["unresolved"]
        flag = "" if d["pass"] == t else "  <--"
        print(f"  {cat:28s} {d['pass']:3d}/{t:<3d}  unres={d['unresolved']}{flag}")

    if regressions:
        print(f"\n### REGRESIONES ({len(regressions)}) ###")
        for r in regressions[:args.show]:
            _show(r)

    if not args.only_regressions and improvements:
        print(f"\n### MEJORAS ({len(improvements)}) ###")
        for r in improvements[:args.show]:
            print(f"  [{r['cat']}] {r['q'][:70]}")

    if not args.only_regressions and fails and not regressions:
        print(f"\n--- ejemplos de FAIL/UNRESOLVED ({len(fails)}) ---")
        for r in fails[:args.show]:
            _show(r)

    if args.update_baseline:
        # Fusiona (no pierde estados de casos filtrados por --category/--type).
        merged = dict(baseline)
        merged.update(states)
        baseline_path.write_text(json.dumps(merged, ensure_ascii=False, indent=0))
        print(f"\n✓ baseline actualizado → {baseline_path.name} ({len(merged)} casos)")

    sys.exit(1 if regressions else 0)


def _run_parity(args):
    """Compara el enrutado de <lang> contra es sobre el banco GEDCOM: mismos
    people_mentioned y mismo estado unresolved. Inmune al idioma del texto."""
    from collections import Counter
    es = {c["id"]: c for c in json.loads((BASE / "data" / "gedcom_test_bank_es.json").read_text())}
    lang_bank = json.loads((BASE / "data" / f"gedcom_test_bank_{args.lang}.json").read_text())
    conn = get_connection(str(BASE / "data" / "godesia.db"))
    router = QueryRouter(conn)
    same = 0
    diff_cat = Counter()
    diffs = []
    for c in lang_bank:
        e = es.get(c["id"])
        if not e:
            continue
        if args.category and c.get("category") != args.category:
            continue
        rl = router.route(c["question"], lang=args.lang)
        re_ = router.route(e["question"], lang="es")
        ok = (set(rl.get("people_mentioned") or []) == set(re_.get("people_mentioned") or [])
              and rl.get("unresolved") == re_.get("unresolved"))
        if ok:
            same += 1
        else:
            diff_cat[c["category"]] += 1
            diffs.append((c["category"], c["question"], e["question"]))
    total = sum(1 for c in lang_bank if c["id"] in es)
    print(f"\n=== Paridad {args.lang}↔es (banco GEDCOM, {total} preguntas) ===")
    print(f"  {args.lang} resuelve IGUAL que es: {same}/{total} ({100*same//max(total,1)}%)"
          f"  | difieren: {total - same}")
    print("\n--- categorías donde difieren ---")
    for k, n in diff_cat.most_common():
        print(f"  {k:26s} {n}")
    for cat, q, eq in diffs[:args.show]:
        print(f"  [{cat}] {args.lang}: {q[:60]}")


def _show(r):
    print(f"  [{r['state']}][{r['cat']}/{r['at']}] {r['q'][:66]}")
    print(f"      esperado: {str(r['expected'])[:80]}")
    if r["exp_ids"] is not None:
        print(f"      ids esp={r['exp_ids']} | got={r['got_ids']}")
    else:
        print(f"      router  : {r['answer']}")


if __name__ == "__main__":
    main()
