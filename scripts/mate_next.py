#!/usr/bin/env python3
"""Siguiente tanda del traspaso Maté → Godes (ver mate_transfer_plan.py).

Para cada alta pendiente muestra sus padres, cónyuges e hijos en Maté con el ID
que ya tienen en Godes (emparejados en plan.json o creados en progress.json),
para colgarla del pariente adecuado: padres > hijos > cónyuge > hermano.

Uso:  python3 scripts/mate_next.py [N]          (altas pendientes, por defecto 20)
      python3 scripts/mate_next.py --updates    (cambios pendientes en personas existentes)
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import mate_transfer_plan as T  # noqa: E402

WORK = BASE / "data" / "mate_transfer"


def mh(gid):
    """@I501614@ → 5501614 (rootIndividualID / indID del árbol Godes)."""
    return "5" + gid.strip("@I").zfill(6) if gid else None


def main():
    plan = json.loads((WORK / "plan.json").read_text())
    prog = json.loads((WORK / "progress.json").read_text())
    m2g = {m["mate_id"]: m["godes_id"] for m in plan["matched"]}
    m2g.update({k: v["godes_id"] for k, v in prog["new"].items() if v.get("godes_id")})
    mate = T.load_tree(T.MATE_GED)

    if "--updates" in sys.argv:
        for u in plan["updates"]:
            if u["godes_id"] in prog["updates"]:
                continue
            print(f'## {u["name"]} {u["godes_id"]} indID={mh(u["godes_id"])}')
            for c in u["changes"]:
                print("   ", json.dumps(c, ensure_ascii=False)[:400])
        for c in plan.get("marriages", []):
            print("## MATRIMONIO", json.dumps(c, ensure_ascii=False)[:400])
        return

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    shown = 0
    for p in plan["new_people"]:
        mid = p["mate_id"]
        if mid in prog["new"]:
            continue
        mp = mate["people"][mid]
        fam = mate["fams"].get(mp["famc"]) or {}
        # Solo personas "listas": sus padres en Maté ya existen en Godes. Si no,
        # MyHeritage crearía un progenitor vacío y luego saldría duplicado.
        if any(x and x not in m2g for x in (fam.get("husb"), fam.get("wife"))):
            continue

        def ref(x):
            if not x:
                return "—"
            nm = mate["people"][x]["name"] or "(sin nombre)"
            g = m2g.get(x)
            return f'{nm} [{g} {mh(g)}]' if g else f'{nm} [pendiente {x}]'

        spouses, kids = [], []
        for fs in mp["fams"]:
            f = mate["fams"].get(fs) or {}
            o = f.get("wife") if f.get("husb") == mid else f.get("husb")
            if o:
                ff = "; ".join(T.fmt_fact(x) for x in f.get("facts", []))
                spouses.append(ref(o) + (f" {{{ff}}}" if ff else ""))
            kids += [ref(c) for c in f.get("chil", [])]
        print(f'### {mid} {p["name"]} · sexo {p["sex"]} · {p["by"] or "?"}–{p["dy"] or "?"}'
              f' · vive={"no" if any(f["tag"] == "DEAT" for f in mp["facts"]) else "sí/?"}')
        print(f'   given="{p["given"]}" surname="{p["surname"]}"')
        print(f'   padres: {ref(fam.get("husb"))} + {ref(fam.get("wife"))}')
        if spouses:
            print(f'   cónyuges: {"; ".join(spouses)}')
        if kids:
            print(f'   hijos: {"; ".join(kids)}')
        for f in p["facts"]:
            print("   ·", T.fmt_fact(f), json.dumps(f.get("extra", {}), ensure_ascii=False)[:200] if f.get("extra") else "")
        shown += 1
        if shown >= n:
            break
    print(f"\nPendientes: {sum(1 for p in plan['new_people'] if p['mate_id'] not in prog['new'])} altas")


if __name__ == "__main__":
    main()
