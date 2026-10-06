#!/usr/bin/env python3
"""Trabajos de fotos del traspaso Maté → Godes para el navegador.

Para cada foto pendiente (plan.json "photos" menos progress.json "photos" hechas)
da: fichero, título, fecha, lugar y etiquetas con el nombre tal como está en Godes,
el ID de MyHeritage esperado (5 + xref a 6 cifras) y el recuadro de la cara en Maté.

Uso:  python3 scripts/mate_photo_jobs.py [N]
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import mate_transfer_plan as T  # noqa: E402

WORK = BASE / "data" / "mate_transfer"


def mh(gid):
    return "5" + gid.strip("@I").zfill(6)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    plan = json.loads((WORK / "plan.json").read_text())
    prog = json.loads((WORK / "progress.json").read_text())
    godes = T.load_tree(T.latest_godes_ged())
    out = []
    for p in plan["photos"]:
        st = prog["photos"].get(p["file"], {})
        if st.get("done"):
            continue
        tags = []
        for t in p["tags"]:
            g = godes["people"].get(t["godes_id"]) or {}
            name = (g.get("name") or t["name"]).replace("/", "").strip()
            box = [int(v) for v in t["position"].split()] if t["position"] else None
            tags.append({"name": " ".join(name.split()), "id": mh(t["godes_id"]), "box": box})
        out.append({"file": p["file"], "slug": p["file"].rsplit(".", 1)[0].replace("_", "").lower(),
                    "mh": st.get("mh_photo"), "title": p["title"], "date": p["date"],
                    "place": p["place"], "tags": tags})
        if len(out) >= n:
            break
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
