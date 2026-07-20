#!/usr/bin/env python3
"""Publica el catálogo de Emili Godes: aprueba (optimiza+renombra+archiva) todas las
fichas 'analizada' y genera un obra.json estructurado (temática → proyecto → fotos, con
décadas) para el explorador del microsite, además del inventario maestro (.md).

Uso:
  python3 scripts/emili_export.py
  (o desde el admin: POST /api/admin/emili/export → export(conn, base_dir))
"""

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Mapa de las 7 categorías del clasificador → los 9 ámbitos del microsite. Revisable.
CATEGORY_TO_AMBITO = {
    "creación artística": "fotografia_artistica",
    "encargo profesional": "publicidad",
    "documentación industrial y urbana": "fotografia_industrial",
    "fotografía científica y médica": "ciencia_medicina",
    "reproducción y difusión del arte": "reproduccion_arte",
    "fotografía y cine": "foto_fija_cine",
    "experimentación técnica y visual": "experimentacion_fotografica",
}
AMBITO_ORDER = [
    "fotografia_artistica", "fotografia_industrial", "publicidad", "ciencia_medicina",
    "reproduccion_arte", "foto_fija_cine", "arquitectura_instalaciones",
    "reportajes_urbanos_documentales", "experimentacion_fotografica",
]


def _ambito_for(proyecto, categoria) -> str:
    proj = (proyecto or "").lower()
    if any(k in proj for k in ("córdoba", "cordoba", "montjuïc", "montjuic", "puerto",
                                "calle", "ciudad", "urban", "zoo", "tauri", "pesquer")):
        return "reportajes_urbanos_documentales"
    if any(k in proj for k in ("residencia", "edificio", "instalac", "pabellón", "pabellon",
                                "arquitect", "fachada")):
        return "arquitectura_instalaciones"
    return CATEGORY_TO_AMBITO.get(categoria or "", "fotografia_artistica")


def _decade(fecha) -> str:
    if not fecha:
        return "sf"
    years = [int(y) for y in re.findall(r"(1[89]\d\d)", fecha)]
    if not years:
        return "sf"
    return str((min(years) // 10) * 10)


def _titulo(descripcion, proyecto, orig) -> str:
    t = (descripcion or proyecto or orig or "").strip()
    if len(t) > 80:
        t = t[:77].rsplit(" ", 1)[0] + "…"
    return t


def export(conn, base_dir) -> dict:
    base_dir = Path(base_dir)
    sys.path.insert(0, str(base_dir / "backend"))
    import emili_classifier as ec  # noqa: PLC0415

    # 1) Publicar: aprobar todas las 'analizada' (optimiza+renombra+archiva a data/photos)
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM emili_photos WHERE status='analizada'")]
    approved = 0
    if ids:
        approved = ec.approve(conn, base_dir, ids, log=lambda m: None)["approved"]

    # 2) Construir el manifiesto rico desde todas las 'aprobada' con imagen.
    rows = conn.execute(
        "SELECT * FROM emili_photos WHERE status='aprobada' AND dest_path IS NOT NULL "
        "ORDER BY proyecto, serie, serie_num, orig_filename"
    ).fetchall()

    # Agrupar: ámbito → proyecto → fotos
    tree = {}
    all_decades = set()
    for r in rows:
        ambito = _ambito_for(r["proyecto"], r["categoria"])
        proj = (r["proyecto"] or "Sin proyecto").strip()
        dec = _decade(r["fecha_estimada"])
        all_decades.add(dec)
        photo = {
            "orig": r["orig_filename"],
            "image": "/" + r["dest_path"],
            "titulo": _titulo(r["descripcion"], r["proyecto"], r["orig_filename"]),
            "descripcion": r["descripcion"],
            "fecha": r["fecha_estimada"],
            "fecha_certeza": r["fecha_certeza"],
            "lugar": r["lugar"],
            "categoria": r["categoria"],
            "decada": dec,
            "confianza": r["confianza"],
        }
        tree.setdefault(ambito, {}).setdefault(proj, []).append(photo)

    ambitos = {}
    for ambito, projects in tree.items():
        plist = []
        for proj, photos in projects.items():
            decs = [p["decada"] for p in photos if p["decada"] != "sf"]
            lugares = [p["lugar"] for p in photos if p["lugar"] and p["lugar"] != "por determinar"]
            fechas = [p["fecha"] for p in photos if p["fecha"] and p["fecha"] != "por determinar"]
            cover = next((p["image"] for p in photos if p["image"]), None)
            plist.append({
                "slug": ec.slugify(proj, 50) or "sin-proyecto",
                "nombre": proj,
                "lugar": Counter(lugares).most_common(1)[0][0] if lugares else "",
                "fecha": Counter(fechas).most_common(1)[0][0] if fechas else "",
                "decada": Counter(decs).most_common(1)[0][0] if decs else "sf",
                "count": len(photos),
                "cover": cover,
                "photos": photos,
            })
        plist.sort(key=lambda p: (-p["count"], p["nombre"]))
        ambitos[ambito] = {
            "count": sum(p["count"] for p in plist),
            "decades": sorted({p["decada"] for p in plist if p["decada"] != "sf"}),
            "projects": plist,
        }

    manifest = {
        "generated_at": conn.execute("SELECT datetime('now')").fetchone()[0],
        "ambito_order": [a for a in AMBITO_ORDER if a in ambitos],
        "ambitos": ambitos,
        "decades": sorted(d for d in all_decades if d != "sf"),
        "total": len(rows),
    }
    obra_path = base_dir / "frontend" / "emili-godes" / "data" / "obra.json"
    obra_path.parent.mkdir(parents=True, exist_ok=True)
    obra_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3) Inventario maestro (.md)
    lines = ["# Inventario maestro — archivo de Emili Godes", "",
             f"Generado desde emili_photos ({len(rows)} imágenes publicadas).", "",
             "| orig | nuevo_nombre | ruta | fecha | proyecto | categoría | lugar | descripción |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        cells = [r["orig_filename"], r["new_filename"] or "", r["dest_path"] or "",
                 r["fecha_estimada"] or "", r["proyecto"] or "", r["categoria"] or "",
                 r["lugar"] or "", (r["descripcion"] or "").replace("|", "/").replace("\n", " ")]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    inv_path = base_dir / "data" / "emili" / "inventario_maestro.md"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"aprobadas_ahora": approved, "publicadas": len(rows),
            "ambitos": {k: v["count"] for k, v in ambitos.items()},
            "obra_json": str(obra_path), "inventario": str(inv_path)}


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    conn = sqlite3.connect(str(base / "data" / "godesia.db"))
    conn.row_factory = sqlite3.Row
    print(json.dumps(export(conn, base), ensure_ascii=False, indent=2))
