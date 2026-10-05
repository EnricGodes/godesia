#!/usr/bin/env python3
"""Plan de traspaso del árbol Maté (cuenta Enric) al árbol Godes (cuenta Ignasi).

Compara el GEDCOM exportado de Maté con el último godes.ged y calcula, sin tocar
nada, la cola de trabajo que luego se ejecuta a mano/navegador en MyHeritage:

  - personas emparejadas (Maté ↔ Godes), estricto: los casos dudosos NO se
    emparejan, van a una lista para revisar;
  - personas nuevas, cada una con su ancla (pariente ya en Godes o creado antes
    en la cola) y la relación con la que se añade;
  - cambios por persona emparejada (manda Maté): datos básicos y todos los
    hechos (EDUC, EVEN, EMIG, OCCU, RESI, NOTE…);
  - fotos nuevas (y etiquetas que faltan en fotos que Godes ya tiene).

Esther Maté Ramos (Godes @I107@) es "solo ancla": nunca genera cambios.

Uso:  python3 scripts/mate_transfer_plan.py [--download]
Salida (gitignored): data/mate_transfer/plan.json y report.md
"""

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "backend"))
from admin_routes import _canonicalize_person_name, _ged_year  # noqa: E402

WORK = BASE / "data" / "mate_transfer"
MATE_GED = WORK / "mate.ged"
PHOTOS = WORK / "photos"

ESTHER_GODES = "@I107@"
# Contenedor de MyHeritage para las fotos sin etiquetar: no es una persona.
UNASSOCIATED = "@I88888888@"
# Tags de nivel 1 que no son "datos" a copiar (metadatos MyHeritage, vínculos).
SKIP_TAGS = {"_UPD", "RIN", "_UID", "FAMC", "FAMS", "OBJE", "NAME", "SEX",
             "_PHOTO_RIN", "_PRIM", "_PRIM_CUTOUT", "_PERSONALPHOTO"}
# Hechos de un solo valor: si difieren, se sobrescriben (manda Maté).
SINGLE = {"BIRT", "DEAT"}


# ── GEDCOM genérico (conserva todas las subetiquetas) ────────────────────────

def parse_ged(path: Path) -> dict:
    recs, stack = {}, []
    with path.open(encoding="utf-8-sig", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = re.match(r"^(\d+) (?:(@[^@]+@) )?(\S+)(?: (.*))?$", line)
            if not m:
                continue
            lvl, xref, tag, val = int(m[1]), m[2], m[3], m[4] or ""
            if tag in ("CONC", "CONT") and lvl > 0 and len(stack) >= lvl:
                stack[lvl - 1]["value"] += ("\n" if tag == "CONT" else "") + val
                continue
            node = {"tag": tag, "value": val, "children": []}
            if lvl == 0:
                node["xref"] = xref
                stack = [node]
                if xref:
                    recs[xref] = node
                continue
            stack = stack[:lvl]
            if not stack:
                continue
            stack[-1]["children"].append(node)
            stack.append(node)
    return recs


def sub(node, tag, default=""):
    for c in node["children"]:
        if c["tag"] == tag:
            return c["value"]
    return default


def subs(node, tag):
    return [c for c in node["children"] if c["tag"] == tag]


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def resolve_note(recs, val):
    """NOTE puede ser texto o @N…@ (registro aparte)."""
    if val.startswith("@") and val in recs:
        return recs[val]["value"]
    return val


def fact_of(recs, n) -> dict:
    val = n["value"]
    if n["tag"] == "NOTE":
        val = resolve_note(recs, val)
    elif n["tag"] == "SOUR" and val in recs:      # IDs de fuente distintos en cada árbol
        val = sub(recs[val], "TITL") or val
    f = {"tag": n["tag"], "value": norm(val),
         "type": norm(sub(n, "TYPE")), "date": norm(sub(n, "DATE")), "place": norm(sub(n, "PLAC"))}
    extra = {}
    for c in n["children"]:
        if c["tag"] in ("TYPE", "DATE", "PLAC", "OBJE", "_UPD", "RIN", "_UID"):
            continue
        v = resolve_note(recs, c["value"]) if c["tag"] == "NOTE" else c["value"]
        if c["tag"] == "SOUR" and c["value"] in recs:
            v = sub(recs[c["value"]], "TITL") or c["value"]
        extra.setdefault(c["tag"], []).append(norm(v))
    if extra:
        f["extra"] = extra
    return f


def photos_of(node, out=None):
    """Todos los OBJE (a cualquier profundidad) de un registro."""
    out = [] if out is None else out
    for c in node["children"]:
        if c["tag"] == "OBJE":
            url = sub(c, "FILE")
            if url:
                out.append({"url": url, "file": url.rsplit("/", 1)[-1],
                            "title": norm(sub(c, "TITL")), "date": norm(sub(c, "_DATE")),
                            "place": norm(sub(c, "_PLACE")), "position": norm(sub(c, "_POSITION")),
                            "album": sub(c, "_ALBUM"), "rin": sub(c, "_PHOTO_RIN"),
                            "size": int(sub(c, "_FILESIZE") or 0)})
        else:
            photos_of(c, out)
    return out


def photo_hash(filename: str) -> str:
    m = re.match(r"^\d+_([a-z0-9]+)_[A-Z]+\.\w+$", filename, re.I)
    return m.group(1).lower() if m else filename.lower()


def load_tree(path: Path) -> dict:
    recs = parse_ged(path)
    people, fams = {}, {}
    for x, r in recs.items():
        if r["tag"] == "FAM":
            fams[x] = {"id": x, "husb": sub(r, "HUSB") or None, "wife": sub(r, "WIFE") or None,
                       "chil": [c["value"] for c in subs(r, "CHIL")],
                       "facts": [fact_of(recs, c) for c in r["children"]
                                 if c["tag"] not in {"HUSB", "WIFE", "CHIL"} | SKIP_TAGS],
                       "photos": photos_of(r)}
    for x, r in recs.items():
        if r["tag"] != "INDI":
            continue
        nm = next(iter(subs(r, "NAME")), None)
        name_raw = nm["value"] if nm else ""
        p = {"id": x, "name": norm(name_raw.replace("/", " ")),
             "given": norm(sub(nm, "GIVN")) if nm else "", "surname": norm(sub(nm, "SURN")) if nm else "",
             "sex": sub(r, "SEX"),
             "facts": [fact_of(recs, c) for c in r["children"] if c["tag"] not in SKIP_TAGS],
             "photos": photos_of(r),
             "famc": sub(r, "FAMC") or None, "fams": [c["value"] for c in subs(r, "FAMS")]}
        p["canon"] = _canonicalize_person_name(p["name"])
        p["by"] = _ged_year(next((f["date"] for f in p["facts"] if f["tag"] == "BIRT"), ""))
        p["dy"] = _ged_year(next((f["date"] for f in p["facts"] if f["tag"] == "DEAT"), ""))
        people[x] = p
    for p in people.values():
        f = fams.get(p["famc"]) or {}
        p["father"], p["mother"] = f.get("husb"), f.get("wife")
    return {"people": people, "fams": fams, "albums": {x: sub(r, "TITL") for x, r in recs.items()
                                                       if r["tag"] == "ALBUM"}}


def latest_godes_ged() -> Path:
    cands = []
    for p in (BASE / "docs").glob("*.ged"):
        head = p.open(encoding="utf-8-sig", errors="replace").read(2000)
        if re.search(r"^1 FILE Exported by MyHeritage\.com from Godes ", head, re.M):
            cands.append(p)
    if not cands:
        sys.exit("No encuentro el godes.ged (docs/*.ged exportado 'from Godes')")
    return max(cands, key=lambda p: p.stat().st_mtime)


# ── Emparejamiento estricto ──────────────────────────────────────────────────

def _years_ok(a, b) -> bool:
    return not a or not b or abs(a - b) <= 2


def _surn(t, pid):
    p = t["people"].get(pid) if pid else None
    return _canonicalize_person_name(p["surname"] or p["name"]).split()[:1] if p else []


def match_people(mate, godes):
    by_canon = defaultdict(list)
    for g in godes["people"].values():
        by_canon[g["canon"]].append(g)
    matched, doubtful = {}, []
    for m in mate["people"].values():
        if m["id"] == UNASSOCIATED:
            continue
        if not m["canon"]:
            continue  # hueco de estructura (hijo o cónyuge sin nombre): siempre es alta
        mt = set(m["canon"].split())
        cands = []
        for g in godes["people"].values():
            gt = set(g["canon"].split())
            exact = g["canon"] == m["canon"]
            # Nombre contenido (p. ej. "Esther Maté Ramos" ⊂ "María Esther Maté Ramos"),
            # con al menos nombre + un apellido en común.
            contained = len(mt & gt) >= 2 and (mt <= gt or gt <= mt) and g["sex"] in (m["sex"], "U", "")
            if not (exact or contained):
                continue
            if not (_years_ok(m["by"], g["by"]) and _years_ok(m["dy"], g["dy"])):
                continue
            # Padres: si los dos lados los tienen, el primer apellido debe coincidir.
            bad_parent = any(_surn(mate, getattr_) and _surn(godes, gg) and _surn(mate, getattr_) != _surn(godes, gg)
                             for getattr_, gg in ((m["father"], g["father"]), (m["mother"], g["mother"])))
            if bad_parent:
                continue
            strong = exact and (m["by"] == g["by"] or not (m["by"] and g["by"]))
            cands.append((strong, g))
        strongs = [g for s, g in cands if s]
        if len(cands) == 1 and strongs:
            matched[m["id"]] = {"godes_id": cands[0][1]["id"], "how": "exacto"}
        elif len(strongs) == 1:
            matched[m["id"]] = {"godes_id": strongs[0]["id"], "how": "exacto (había otros parecidos)"}
        elif cands:
            doubtful.append({"mate_id": m["id"], "name": m["name"], "by": m["by"], "dy": m["dy"],
                             "why": "varios candidatos" if len(cands) > 1 else "nombre o año no exacto",
                             "candidates": [{"godes_id": g["id"], "name": g["name"], "by": g["by"], "dy": g["dy"]}
                                            for _, g in cands]})
    # Hermanos anónimos idénticos (p. ej. 6 "Ramos Pinillos" sin nombre de pila,
    # mismos padres, sin datos): son intercambiables → se emparejan en orden.
    groups = defaultdict(list)
    for d in doubtful:
        ids = tuple(sorted(c["godes_id"] for c in d.get("candidates", [])))
        groups[ids].append(d)
    for ids, ds in groups.items():
        ms = [mate["people"][d["mate_id"]] for d in ds]
        if (ids and len(ids) == len(ds)
                and len({godes["people"][g]["name"] for g in ids} | {m["name"] for m in ms}) == 1
                and all(not m["facts"] and not m["photos"] for m in ms)
                and not any(g in [v["godes_id"] for v in matched.values()] for g in ids)):
            for d, gid in zip(sorted(ds, key=lambda d: d["mate_id"]), ids):
                matched[d["mate_id"]] = {"godes_id": gid, "how": "anónimo idéntico (intercambiable)"}
                doubtful.remove(d)
    # Una persona Godes solo puede recibir a una persona Maté.
    used = defaultdict(list)
    for mid, v in matched.items():
        used[v["godes_id"]].append(mid)
    for gid, mids in used.items():
        if len(mids) > 1:
            for mid in mids:
                m = mate["people"][mid]
                doubtful.append({"mate_id": mid, "name": m["name"], "by": m["by"], "dy": m["dy"],
                                 "why": f"comparte pareja Godes {gid} con otra persona Maté",
                                 "candidates": [{"godes_id": gid, "name": godes["people"][gid]["name"]}]})
                matched.pop(mid)
    return matched, doubtful


# ── Relaciones y anclas para las personas nuevas ────────────────────────────

REL = {  # (relación de la persona NUEVA respecto al ancla, sexo) → texto
    ("parent", "M"): "padre", ("parent", "F"): "madre",
    ("child", "M"): "hijo", ("child", "F"): "hija",
    ("spouse", "M"): "esposo", ("spouse", "F"): "esposa",
    ("sibling", "M"): "hermano", ("sibling", "F"): "hermana",
    ("parent", "U"): "padre/madre", ("child", "U"): "hijo/a",
    ("spouse", "U"): "cónyuge", ("sibling", "U"): "hermano/a",
}


def neighbours(mate, pid):
    """(vecino, relación de pid respecto al vecino)."""
    p, out = mate["people"][pid], []
    fam = mate["fams"].get(p["famc"]) or {}
    for par in (fam.get("husb"), fam.get("wife")):
        if par:
            out.append((par, "child"))                 # pid es hijo/a del padre
    for sib in fam.get("chil", []):
        if sib != pid:
            out.append((sib, "sibling"))
    for fs in p["fams"]:
        f = mate["fams"].get(fs) or {}
        other = f.get("wife") if f.get("husb") == pid else f.get("husb")
        if other:
            out.append((other, "spouse"))
        for ch in f.get("chil", []):
            out.append((ch, "parent"))                 # pid es padre/madre del hijo
    return out


PREF = {"child": 0, "parent": 1, "spouse": 2, "sibling": 3}


def plan_new_people(mate, matched, doubtful_ids):
    placed = {mid: ("godes", v["godes_id"]) for mid, v in matched.items()}
    queue, new_people = deque(placed), []
    while queue:
        anchor = queue.popleft()
        # Vecinos ordenados: padres e hijos antes que cónyuges y hermanos.
        for nb, _ in sorted(neighbours(mate, anchor), key=lambda x: PREF[x[1]]):
            if nb in placed or nb in doubtful_ids:
                continue
            # La relación del NUEVO (nb) respecto al ancla.
            rel = next(r for n2, r in neighbours(mate, nb) if n2 == anchor)
            p = mate["people"][nb]
            placed[nb] = ("new", nb)
            new_people.append({
                "mate_id": nb, "name": p["name"] or "(sin nombre)", "unnamed": not p["canon"],
                "given": p["given"], "surname": p["surname"],
                "sex": p["sex"], "by": p["by"], "dy": p["dy"],
                "anchor": {"kind": placed[anchor][0], "id": placed[anchor][1],
                           "name": mate["people"][anchor]["name"]},
                "relation": REL.get((rel, p["sex"] if p["sex"] in ("M", "F") else "U"), rel),
                "facts": p["facts"], "photos": [ph["file"] for ph in p["photos"]],
            })
            queue.append(nb)
    unreachable = [{"mate_id": x, "name": p["name"] or "(sin nombre)"} for x, p in mate["people"].items()
                   if x not in placed and x not in doubtful_ids and x != UNASSOCIATED]
    return new_people, unreachable


# ── Diferencias en personas emparejadas (manda Maté) ────────────────────────

def _fkey(f):
    return (f["tag"], f["type"].lower(), f["date"].lower())


def _fsig(f):
    return (f["tag"], f["type"].lower(), f["date"].lower(), f["place"].lower(), f["value"].lower(),
            json.dumps(f.get("extra", {}), sort_keys=True).lower())


def _plain(s) -> str:
    """Texto comparable: sin HTML, entidades ni puntuación final."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    return re.sub(r"\s+", " ", s).strip(" .;,").lower()


def merge_fact(mf, gf):
    """Fusiona un hecho Maté sobre uno Godes: manda Maté cuando los dos tienen
    valor y son distintos; lo que solo tiene Godes se conserva; si el texto de
    Godes ya contiene el de Maté, se queda el de Godes. Devuelve los campos a
    cambiar ({campo: (godes, maté)}) — vacío si no hay nada que hacer."""
    out = {}
    for k in ("value", "type", "date", "place"):
        mv, gv = mf.get(k, ""), gf.get(k, "")
        if mv and _plain(mv) not in _plain(gv):
            out[k] = (gv, mv)
    me, ge = mf.get("extra", {}), gf.get("extra", {})
    for k, mvals in me.items():
        gtxt = " | ".join(ge.get(k, []))
        for mv in mvals:
            if mv and _plain(mv) not in _plain(gtxt):
                out[k] = (gtxt, mv)
    return out


def _src_title(f):
    return _plain(f.get("value"))


def diff_person(m, g):
    changes = []
    if norm(m["given"]) != norm(g["given"]) or norm(m["surname"]) != norm(g["surname"]):
        changes.append({"op": "set", "field": "nombre", "godes": f'{g["given"]} / {g["surname"]}',
                        "mate": f'{m["given"]} / {m["surname"]}', "confirm": True})
    if m["sex"] and m["sex"] not in ("U", g["sex"]):
        changes.append({"op": "set", "field": "sexo", "godes": g["sex"], "mate": m["sex"], "confirm": True})
    gsingle = {f["tag"]: f for f in g["facts"] if f["tag"] in SINGLE}
    for f in m["facts"]:
        if f["tag"] in SINGLE and f["tag"] in gsingle:
            diff = merge_fact(f, gsingle[f["tag"]])
            if diff:
                changes.append({"op": "update", "fact": f, "godes": gsingle[f["tag"]], "fields": diff,
                                "confirm": any(k in ("value", "NOTE") and g for k, (g, _) in diff.items())})
            continue
        same = [x for x in g["facts"] if x["tag"] == f["tag"]]
        if f["tag"] in ("NOTE", "SOUR"):
            if any(_plain(x["value"]) == _plain(f["value"]) or
                   (_plain(f["value"]) and _plain(f["value"]) in _plain(x["value"])) for x in same):
                continue
            changes.append({"op": "add", "fact": f, "godes": None})
            continue
        # Hechos múltiples: misma etiqueta+tipo+fecha (con fecha) = el mismo hecho.
        twin = next((x for x in same if f["date"] and x["date"].lower() == f["date"].lower()
                     and x["type"].lower() == f["type"].lower()), None)
        if twin is None and not f["date"]:   # sin fecha: el mismo texto es el mismo hecho
            twin = next((x for x in same if not x["date"] and x["type"].lower() == f["type"].lower()
                         and _plain(x["value"]) == _plain(f["value"])), None)
        if twin is None:
            twin = next((x for x in same if not merge_fact(f, x)), None)  # ya está tal cual
            if twin is not None:
                continue
            changes.append({"op": "add", "fact": f, "godes": None})
            continue
        diff = merge_fact(f, twin)
        if diff:
            changes.append({"op": "update", "fact": f, "godes": twin, "fields": diff,
                            # Sobrescribir texto que solo tiene Godes: se enseña antes.
                            "confirm": any(k in ("value", "NOTE") and g for k, (g, _) in diff.items())})
    return changes


def missing_links(mate, godes, matched):
    """Vínculos entre dos personas ya emparejadas que en Godes no existen."""
    out, seen = [], set()
    m2g = {k: v["godes_id"] for k, v in matched.items()}
    for mid, gid in m2g.items():
        g = godes["people"][gid]
        gpar = {g["father"], g["mother"]}
        gsp = set()
        for fs in g["fams"]:
            f = godes["fams"].get(fs) or {}
            gsp |= {f.get("husb"), f.get("wife")}
        for nb, rel in neighbours(mate, mid):
            if nb not in m2g or rel == "sibling":
                continue
            gnb = m2g[nb]
            ok = (rel == "child" and gnb in gpar) or (rel == "spouse" and gnb in gsp) or rel == "parent"
            key = tuple(sorted((mid, nb))) + (rel if rel != "parent" else "child",)
            if not ok and key not in seen:
                seen.add(key)
                out.append({"mate_id": mid, "godes_id": gid, "name": g["name"], "relation": rel,
                            "other_godes_id": gnb, "other_name": godes["people"][gnb]["name"]})
    return out


def marriage_changes(mate, godes, matched):
    """Hechos de matrimonio (MARR/DIV…) entre parejas ya emparejadas."""
    m2g = {k: v["godes_id"] for k, v in matched.items()}
    gfam = {}
    for f in godes["fams"].values():
        gfam[frozenset(x for x in (f["husb"], f["wife"]) if x)] = f
    out = []
    for f in mate["fams"].values():
        if not (f["husb"] in m2g and f["wife"] in m2g):
            continue
        gf = gfam.get(frozenset((m2g[f["husb"]], m2g[f["wife"]])))
        if not gf:
            continue  # sin familia en Godes → sale en missing_links (spouse)
        gsigs = {_fsig(x) for x in gf["facts"]}
        for fact in f["facts"]:
            if _fsig(fact) not in gsigs:
                old = next((x for x in gf["facts"] if x["tag"] == fact["tag"]), None)
                out.append({"husb": m2g[f["husb"]], "wife": m2g[f["wife"]],
                            "names": f'{godes["people"][m2g[f["husb"]]]["name"]} + {godes["people"][m2g[f["wife"]]]["name"]}',
                            "op": "update" if old else "add", "fact": fact, "godes": old})
    return out


# ── Fotos ────────────────────────────────────────────────────────────────────

def plan_photos(mate, godes, matched):
    m2g = {k: v["godes_id"] for k, v in matched.items()}
    g_tags = defaultdict(set)              # hash → personas Godes etiquetadas
    for g in godes["people"].values():
        for ph in g["photos"]:
            g_tags[photo_hash(ph["file"])].add(g["id"])
    for f in godes["fams"].values():
        for ph in f["photos"]:
            g_tags[photo_hash(ph["file"])]
    photos = {}
    for p in mate["people"].values():
        for ph in p["photos"]:
            e = photos.setdefault(ph["file"], {**{k: ph[k] for k in ("url", "file", "title", "date", "place",
                                                                       "rin", "size")},
                                               "album_mate": mate["albums"].get(ph["album"], ""), "tags": []})
            if p["id"] == UNASSOCIATED:
                continue  # foto suelta: va al álbum sin etiquetar a nadie
            if not any(t["mate_id"] == p["id"] for t in e["tags"]):
                e["tags"].append({"mate_id": p["id"], "name": p["name"], "position": ph["position"],
                                  "godes_id": m2g.get(p["id"])})
    out = []
    for e in photos.values():
        h = photo_hash(e["file"])
        if h in g_tags:
            missing = [t for t in e["tags"] if not (t["godes_id"] and t["godes_id"] in g_tags[h])]
            if missing:
                out.append({**e, "status": "existe en Godes: faltan etiquetas", "tags_missing": missing})
        else:
            out.append({**e, "status": "nueva"})
    return out


def download(photos, godes_photo_dir: Path):
    PHOTOS.mkdir(parents=True, exist_ok=True)
    local_sha = {}
    cache = WORK / "godes_sha256.json"
    if cache.exists():
        local_sha = json.loads(cache.read_text())
    for f in godes_photo_dir.iterdir() if godes_photo_dir.exists() else []:
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png") and f.name not in local_sha:
            local_sha[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    cache.write_text(json.dumps(local_sha))
    sha_to_name = {v: k for k, v in local_sha.items()}
    ok = err = dup = 0
    for e in photos:
        if e["status"] != "nueva":
            continue
        dest = PHOTOS / e["file"]
        if not dest.exists():
            try:
                req = urllib.request.Request(e["url"], headers={"User-Agent": "Mozilla/5.0"})
                dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
                ok += 1
            except Exception as ex:  # noqa: BLE001
                e["download_error"] = str(ex)
                err += 1
                continue
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        e["sha256"], e["local"] = sha, str(dest.relative_to(BASE))
        if sha in sha_to_name:
            e["status"] = "existe en Godes con otro nombre"
            e["godes_file"] = sha_to_name[sha]
            dup += 1
    return ok, err, dup


# ── Informe ──────────────────────────────────────────────────────────────────

def fmt_fact(f):
    if not f:
        return "—"
    bits = [f["tag"]]
    if f.get("type"):
        bits.append(f'[{f["type"]}]')
    for k in ("date", "place", "value"):
        if f.get(k):
            bits.append(f[k][:120])
    return " · ".join(bits)


def write_report(plan):
    L = [f"# Traspaso Maté → Godes — plan ({plan['generated']})", "",
         f"- Maté: `{plan['sources']['mate']}` ({plan['counts']['mate_people']} personas)",
         f"- Godes: `{plan['sources']['godes']}` ({plan['counts']['godes_people']} personas)", "",
         "| | |", "|---|---|"]
    for k, v in plan["counts"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## Esther Maté Ramos (solo ancla, no se toca)", "", json.dumps(plan["esther"], ensure_ascii=False), ""]
    L += ["## Casos dudosos (revisar antes de escribir nada)", ""]
    for d in plan["doubtful"]:
        c = "; ".join(f'{x["godes_id"]} {x["name"]} ({x.get("by") or "?"}–{x.get("dy") or "?"})'
                      for x in d.get("candidates", []))
        L.append(f'- **{d["name"]}** `{d["mate_id"]}` ({d.get("by") or "?"}–{d.get("dy") or "?"}): {d["why"]}. {c}')
    L += ["", "## Vínculos que faltan entre personas que ya están en Godes", ""]
    for x in plan["missing_links"]:
        L.append(f'- {x["name"]} `{x["godes_id"]}` — {x["relation"]} de/con {x["other_name"]} `{x["other_godes_id"]}`')
    L += ["", "## Personas nuevas (en orden de alta)", ""]
    for i, n in enumerate(plan["new_people"], 1):
        L.append(f'{i}. **{n["name"]}** ({n["by"] or "?"}–{n["dy"] or "?"}) — añadir como **{n["relation"]}** de '
                 f'{n["anchor"]["name"]} ({"Godes " + n["anchor"]["id"] if n["anchor"]["kind"] == "godes" else "nueva"}) '
                 f'· {len(n["facts"])} datos · {len(n["photos"])} fotos')
    L += ["", "## Cambios en personas que ya están en Godes (manda Maté)", ""]
    for u in plan["updates"]:
        L.append(f'### {u["name"]} — Godes `{u["godes_id"]}` / Maté `{u["mate_id"]}`')
        for c in u["changes"]:
            if "field" in c:
                L.append(f'- {c["op"]} **{c["field"]}**: `{c["godes"]}` → `{c["mate"]}`')
            else:
                if c.get("fields"):
                    det = "; ".join(f'{k}: «{g[:80]}» → «{m[:80]}»' for k, (g, m) in c["fields"].items())
                    L.append(f'- update {c["fact"]["tag"]} ({c["fact"]["date"] or "sin fecha"}): {det}')
                else:
                    L.append(f'- add: {fmt_fact(c["fact"])}')
            if c.get("confirm"):
                L[-1] += "  **⚠ confirmar con el usuario**"
        L.append("")
    L += ["## Matrimonios con datos que cambian", ""]
    for c in plan["marriages"]:
        L.append(f'- {c["names"]}: {c["op"]} {fmt_fact(c["fact"])}' + (f'  _(Godes: {fmt_fact(c["godes"])})_' if c["godes"] else ""))
    L += ["", "## Fotos", ""]
    for p in plan["photos"]:
        tags = ", ".join(t["name"] for t in p.get("tags_missing", p["tags"]))
        L.append(f'- `{p["file"]}` — {p["status"]} — «{p["title"]}» {p["date"]} — etiquetar: {tags}')
    L += ["", "## Sin ancla (no conectan con nada que esté en Godes)", ""]
    for u in plan["unreachable"]:
        L.append(f'- {u["name"]} `{u["mate_id"]}`')
    (WORK / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="descargar las fotos nuevas a data/mate_transfer/photos")
    args = ap.parse_args()

    godes_path = latest_godes_ged()
    mate, godes = load_tree(MATE_GED), load_tree(godes_path)
    matched, doubtful = match_people(mate, godes)
    # Las altas hechas en MyHeritage (progress.json) son correspondencias seguras:
    # mandan sobre el emparejamiento por nombre (imprescindible para los sin nombre).
    prog_path = WORK / "progress.json"
    if prog_path.exists():
        prog = json.loads(prog_path.read_text())
        for mid, v in prog.get("new", {}).items():
            gid = v.get("godes_id")
            if gid in godes["people"] and mid in mate["people"]:
                matched[mid] = {"godes_id": gid, "how": "creado en el traspaso"}
        used = {v["godes_id"]: k for k, v in matched.items()}
        doubtful = [d for d in doubtful if d["mate_id"] not in matched]
        for mid in [k for k, v in matched.items() if v["how"] != "creado en el traspaso"
                    and used.get(v["godes_id"]) != k]:
            matched.pop(mid)
    doubtful_ids = {d["mate_id"] for d in doubtful}

    esther_mate = next((mid for mid, v in matched.items() if v["godes_id"] == ESTHER_GODES), None)
    new_people, unreachable = plan_new_people(mate, matched, doubtful_ids)

    updates = []
    for mid, v in matched.items():
        if v["godes_id"] in (ESTHER_GODES, UNASSOCIATED):
            continue  # Esther: solo ancla
        ch = diff_person(mate["people"][mid], godes["people"][v["godes_id"]])
        if ch:
            updates.append({"mate_id": mid, "godes_id": v["godes_id"], "name": mate["people"][mid]["name"],
                            "changes": ch})
    # Decisiones del usuario (data/mate_transfer/decisions.json): cambios que NO se aplican.
    dec_path = WORK / "decisions.json"
    keep = json.loads(dec_path.read_text())["keep_godes"] if dec_path.exists() else []

    def kept(gid, c):
        for k in keep:
            if k["godes_id"] != gid:
                continue
            if "field" in k and c.get("field") == k["field"]:
                return True
            f = c.get("fact") or {}
            if "tag" in k and f.get("tag") == k["tag"] and f.get("date", "").upper() == k.get("date", "").upper():
                return True
        return False

    for u in updates:
        u["changes"] = [c for c in u["changes"] if not kept(u["godes_id"], c)]
    updates = [u for u in updates if u["changes"]]
    links = missing_links(mate, godes, matched)
    # El matrimonio de Esther es un dato de su ficha: tampoco se toca.
    marriages = [c for c in marriage_changes(mate, godes, matched)
                 if ESTHER_GODES not in (c["husb"], c["wife"])]
    photos = plan_photos(mate, godes, matched)

    if args.download:
        ok, err, dup = download(photos, BASE / "data" / "photos")
        print(f"Fotos: {ok} descargadas, {err} errores, {dup} ya estaban en Godes con otro nombre")

    plan = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "sources": {"mate": str(MATE_GED.relative_to(BASE)), "godes": str(godes_path.relative_to(BASE))},
        "esther": {"godes_id": ESTHER_GODES, "mate_id": esther_mate,
                   "nota": "solo ancla: no se cambia ningún dato suyo"},
        "counts": {
            "mate_people": len(mate["people"]), "godes_people": len(godes["people"]),
            "emparejadas": len(matched), "dudosas": len(doubtful), "nuevas": len(new_people),
            "sin_ancla": len(unreachable), "con_cambios": len(updates),
            "cambios_total": sum(len(u["changes"]) for u in updates),
            "vinculos_que_faltan": len(links), "cambios_matrimonio": len(marriages),
            "fotos_nuevas": sum(1 for p in photos if p["status"] == "nueva"),
            "fotos_solo_etiquetas": sum(1 for p in photos if p["status"] != "nueva"),
        },
        "matched": [{"mate_id": k, "godes_id": v["godes_id"], "how": v["how"],
                     "name": mate["people"][k]["name"], "godes_name": godes["people"][v["godes_id"]]["name"]}
                    for k, v in matched.items()],
        "doubtful": doubtful, "new_people": new_people, "unreachable": unreachable,
        "updates": updates, "missing_links": links, "marriages": marriages, "photos": photos,
    }
    (WORK / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(plan)
    print(json.dumps(plan["counts"], ensure_ascii=False, indent=1))
    print(f"→ {WORK / 'report.md'}")


if __name__ == "__main__":
    main()
