#!/usr/bin/env python3
"""Genera, desde la tabla emili_photos (aprobadas), el inventario maestro (.md) y el
obra.json del microsite de Emili Godes.

Uso:
  python3 scripts/emili_export.py            # abre data/godesia.db
  (o desde el admin vía POST /api/admin/emili/export, que llama a export(conn, base_dir))
"""

import json
import sqlite3
from pathlib import Path

# Mapa de las 7 categorías → los 9 ámbitos de obra.json del microsite. Revisable.
CATEGORY_TO_AMBITO = {
    "creación artística": "fotografia_artistica",
    "encargo profesional": "publicidad",
    "documentación industrial y urbana": "fotografia_industrial",
    "fotografía científica y médica": "ciencia_medicina",
    "reproducción y difusión del arte": "reproduccion_arte",
    "fotografía y cine": "foto_fija_cine",
    "experimentación técnica y visual": "experimentacion_fotografica",
}

# Overrides por palabra clave del proyecto (afinan urbano/arquitectura).
def _ambito_for(row) -> str:
    proj = (row["proyecto"] or "").lower()
    if any(k in proj for k in ("córdoba", "cordoba", "montjuïc", "montjuic", "puerto",
                                "calle", "ciudad", "urban")):
        return "reportajes_urbanos_documentales"
    if any(k in proj for k in ("residencia", "edificio", "instalac", "pabellón",
                                "pabellon", "pesquer")):
        return "arquitectura_instalaciones"
    return CATEGORY_TO_AMBITO.get(row["categoria"] or "", "fotografia_artistica")

AMBITO_KEYS = [
    "fotografia_artistica", "fotografia_industrial", "publicidad", "ciencia_medicina",
    "reproduccion_arte", "foto_fija_cine", "arquitectura_instalaciones",
    "reportajes_urbanos_documentales", "experimentacion_fotografica",
]


def export(conn, base_dir) -> dict:
    base_dir = Path(base_dir)
    rows = conn.execute(
        "SELECT * FROM emili_photos WHERE status='aprobada' "
        "ORDER BY proyecto, serie, serie_num, orig_filename"
    ).fetchall()

    # --- obra.json ---
    obra = {k: [] for k in AMBITO_KEYS}
    for i, r in enumerate(rows, 1):
        ambito = _ambito_for(r)
        titulo = (r["descripcion"] or r["proyecto"] or r["orig_filename"] or "").strip()
        if len(titulo) > 90:
            titulo = titulo[:87] + "…"
        image = "/" + r["dest_path"] if r["dest_path"] else None
        obra[ambito].append({
            "id": i,
            "orig": r["orig_filename"],
            "titulo_es": titulo,
            "titulo_ca": titulo,
            "fecha": r["fecha_estimada"],
            "lugar": r["lugar"],
            "proyecto": r["proyecto"],
            "descripcion_es": r["descripcion"],
            "institucion": "IEFC" if r["carpeta"] == "IEFC" else "MNAC",
            "estado": "publicada",
            "image": image,
        })

    obra_path = base_dir / "frontend" / "emili-godes" / "data" / "obra.json"
    obra_path.parent.mkdir(parents=True, exist_ok=True)
    obra_path.write_text(json.dumps(obra, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- inventario maestro (.md) ---
    lines = ["# Inventario maestro — archivo de Emili Godes",
             "",
             f"Generado automáticamente desde emili_photos ({len(rows)} imágenes aprobadas).",
             "",
             "| orig | nuevo_nombre | ruta | fecha | certeza | proyecto | categoría | lugar | descripción |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        cells = [r["orig_filename"], r["new_filename"] or "", r["dest_path"] or "",
                 r["fecha_estimada"] or "", r["fecha_certeza"] or "", r["proyecto"] or "",
                 r["categoria"] or "", r["lugar"] or "",
                 (r["descripcion"] or "").replace("|", "/").replace("\n", " ")]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    inv_path = base_dir / "data" / "emili" / "inventario_maestro.md"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = {k: len(v) for k, v in obra.items() if v}
    return {"aprobadas": len(rows), "obra_json": str(obra_path),
            "inventario": str(inv_path), "por_ambito": counts}


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    conn = sqlite3.connect(str(base / "data" / "godesia.db"))
    conn.row_factory = sqlite3.Row
    result = export(conn, base)
    print(json.dumps(result, ensure_ascii=False, indent=2))
