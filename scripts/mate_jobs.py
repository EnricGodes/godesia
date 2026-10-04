#!/usr/bin/env python3
"""Genera los "trabajos" de alta para el navegador (traspaso Maté → Godes).

Para cada persona lista (padres ya en Godes) da: ancla (ID MyHeritage y nombre
tal como sale en la tarjeta), opción del menú, otro progenitor (select de la
madre/padre), nombre, sexo, viva/fallecida, fechas SIMPLES (año o día+mes+año)
y lugares de nacimiento/muerte, y tipo de relación + fecha/lugar de boda si es
pareja. Lo que no cabe en el formulario rápido va a "editor" (hechos extra,
fechas con calificador) para completarlo después en edit-profile.

Uso: python3 scripts/mate_jobs.py [N]   → JSON en stdout
"""
import json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import mate_transfer_plan as T  # noqa: E402

WORK = BASE / "data" / "mate_transfer"
MON = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}


def simple_date(s):
    """'1913' | '14 MAY 1952' | 'MAY 1952' → (día, mes, año); con calificador → None."""
    s = (s or "").strip().upper()
    if not s:
        return (0, 0, "")
    m = re.fullmatch(r"(?:(\d{1,2}) )?(?:([A-Z]{3}) )?(\d{3,4})", s)
    if not m or (m[2] and m[2] not in MON):
        return None
    return (int(m[1] or 0), MON.get(m[2], 0), m[3])


def mh(gid):
    return int("5" + gid.strip("@I").zfill(6))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    plan = json.loads((WORK / "plan.json").read_text())
    prog = json.loads((WORK / "progress.json").read_text())
    mate = T.load_tree(T.MATE_GED)
    godes = T.load_tree(T.latest_godes_ged())
    m2g = {m["mate_id"]: m["godes_id"] for m in plan["matched"]}
    m2g.update({k: v["godes_id"] for k, v in prog["new"].items() if v.get("godes_id")})

    def card_name(mid):
        g = m2g[mid]
        gp = godes["people"].get(g)
        p = gp or mate["people"][mid]
        nm = (p["given"] + " " + p["surname"]).strip()
        return nm or "Desconocido"

    # Parejas ya unidas en Godes: las del godes.ged + las formadas en esta sesión.
    couples = {tuple(sorted(c)) for c in prog.get("couples", [])}
    for f in godes["fams"].values():
        if f["husb"] and f["wife"]:
            couples.add(tuple(sorted((mh(f["husb"]), mh(f["wife"])))))
    jobs = []
    # 1) Conexiones: parejas de Maté con los dos miembros ya en Godes pero sin unir.
    for f in mate["fams"].values():
        h, w = f.get("husb"), f.get("wife")
        if h in m2g and w in m2g and tuple(sorted((mh(m2g[h]), mh(m2g[w])))) not in couples:
            if m2g[h] == "@I107@" or m2g[w] == "@I107@":
                pass  # Esther: se puede conectar (solo vínculos), sus datos no se tocan
            jobs.append({"type": "link", "a": mh(m2g[w]), "a_name": card_name(w), "b": mh(m2g[h]),
                         "b_name": card_name(h), "rel": "Divorced" if any(x["tag"] == "DIV" for x in f["facts"]) else "Married"})
    for p in plan["new_people"]:
        mid = p["mate_id"]
        if mid in prog["new"]:
            continue
        mp = mate["people"][mid]
        fam = mate["fams"].get(mp["famc"]) or {}
        pars = [x for x in (fam.get("husb"), fam.get("wife")) if x]
        if any(x not in m2g for x in pars):
            continue
        sex = mp["sex"] if mp["sex"] in ("M", "F") else "U"
        job = {"mate_id": mid, "name": p["name"], "fn": mp["given"], "ln": mp["surname"], "sex": sex,
               "dead": any(f["tag"] == "DEAT" for f in mp["facts"]), "editor": []}
        if pars:   # alta como hijo/a del padre (o madre) ya en Godes
            a = fam.get("husb") or fam.get("wife")
            other = fam.get("wife") if a == fam.get("husb") else None
            job.update(anchor=mh(m2g[a]), anchor_name=card_name(a),
                       menu={"M": "Agregar hijo", "F": "Agregar hija"}.get(sex, "Agregar hijo"),
                       other_parent=card_name(other) if other else None)
        else:      # alta como pareja (cónyuge que entra en la familia) o como padre/madre de un hijo
            sp = None
            for fs in mp["fams"]:
                f = mate["fams"].get(fs) or {}
                o = f.get("wife") if f.get("husb") == mid else f.get("husb")
                if o and o in m2g:
                    sp = (o, f)
                    break
            if sp:
                o, f = sp
                job.update(anchor=mh(m2g[o]), anchor_name=card_name(o), menu="pareja")
                marr = next((x for x in f["facts"] if x["tag"] == "MARR"), None)
                div = next((x for x in f["facts"] if x["tag"] == "DIV"), None)
                # Sin registro de matrimonio → casados igualmente (decisión del usuario 4-oct-2026:
                # "en esa época estaban todos casados").
                job["rel"] = "Divorced" if div else "Married"
                if marr:
                    d = simple_date(marr["date"])
                    if d is None:
                        job["editor"].append({"fam": "MARR", **marr})
                    else:
                        job["mdate"], job["mplace"] = d, marr["place"]
                for x in f["facts"]:
                    if x["tag"] not in ("MARR",):
                        job["editor"].append({"fam": x["tag"], **x})
            else:
                kid = next((c for fs in mp["fams"] for c in (mate["fams"].get(fs) or {}).get("chil", []) if c in m2g), None)
                if not kid:
                    continue
                job.update(anchor=mh(m2g[kid]), anchor_name=card_name(kid),
                           menu={"M": "Agregar padre", "F": "Agregar madre"}.get(sex, "Agregar padre"))
        for f in mp["facts"]:
            if f["tag"] in ("BIRT", "DEAT") and not job.get(f["tag"]):
                d = simple_date(f["date"])
                extra = {k: v for k, v in (f.get("extra") or {}).items()}
                if d is None or extra or f["value"] not in ("", "Y"):
                    job["editor"].append(f)          # calificador, nota, causa… → editor
                    if d is None:
                        d = (0, 0, "")
                job[f["tag"]] = {"d": d, "place": f["place"]}
            else:
                job["editor"].append(f)
        jobs.append(job)
        if len(jobs) >= n:
            break
    print(json.dumps(jobs, ensure_ascii=False))


if __name__ == "__main__":
    main()
