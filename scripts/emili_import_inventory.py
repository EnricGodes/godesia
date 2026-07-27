"""Importa la obra de Emili Godes desde el inventario Excel curado a mano y
genera todo lo que consume el microsite (BD + imágenes + JSON).

Fuente:
  _resources/emili-godes/archivo/inventario_maestro_consolidado_traduccion.xlsx
  + fotos en _resources/emili-godes/archivo/{Filmoteca/imagenes, IEFC/_procesadas,
    MNAC, Museo Reina Sofia, Museo Universidad de Navarra/imagenes}

Hace, en un solo paso (idempotente, re-ejecutable):
  1. Lee el Excel y colapsa duplicados por nombre de archivo (columna `original`).
     - Duplicado = MISMO valor exacto en `original`. Nombre distinto = foto distinta, nunca se fusiona.
     - En conflicto gana la ÚLTIMA pasada, prefiriendo la fila con descripción no vacía.
     - `destacado` = OR de todas las copias.
  2. Resuelve la década (año más temprano de `fecha_estimada`) y traduce la categoría al catalán.
  3. Localiza el archivo físico (exacto → stem → normalizado sin sufijo `(n)`), lo reescala a
     lado largo 1000 px, JPEG calidad 60, y lo guarda en data/photos/emili-godes/ (carpeta plana).
  4. Rellena las tablas emili_works y emili_decades.
  5. Genera frontend/emili-godes/data/obra.json y destacadas.json (bilingües, con eje de fondo).
  6. Avisa (no aborta) de archivos físicos SIN ficha en el Excel (quedarían sin publicar).

Uso:  python3 scripts/emili_import_inventory.py [--force]
      --force  reescala también las imágenes ya existentes en el destino.
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from database import get_connection  # noqa: E402

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Falta Pillow: pip3 install Pillow")
try:
    import openpyxl
except ImportError:
    sys.exit("Falta openpyxl: pip3 install openpyxl")

BASE = Path(__file__).parent.parent
ARCHIVE = BASE / "_resources" / "emili-godes" / "archivo"
XLSX = ARCHIVE / "inventario_maestro_consolidado_traduccion.xlsx"
DB_PATH = BASE / "data" / "godesia.db"
OUT_IMG_DIR = BASE / "data" / "photos" / "emili-godes"
OUT_IMG_URL = "/photos/emili-godes"
OBRA_JSON = BASE / "frontend" / "emili-godes" / "data" / "obra.json"
DEST_JSON = BASE / "frontend" / "emili-godes" / "data" / "destacadas.json"

MAX_SIDE = 1000
JPEG_Q = 60

# fondo (columna del Excel) → carpeta relativa dentro de ARCHIVE
FOLDER = {
    "IEFC": "IEFC/_procesadas",
    "Filmoteca de Catalunya": "Filmoteca/imagenes",
    "MNAC": "MNAC",
    "Museo Reina Sofia": "Museo Reina Sofia",
    "Museo Universidad de Navarra": "Museo Universidad de Navarra/imagenes",
    "Arxiu Fotogràfic de Barcelona": "Arxiu Fotogràfic de Barcelona",
}

# categoría (ES, tal cual en el Excel) → (slug que YA existe en OBRA_TEXTS de emili.js, ES, CA)
CATS = {
    "Fotografía y cine": ("foto_fija_cine", "Fotografía y cine", "Fotografia i cinema"),
    "Fotografía industrial": ("fotografia_industrial", "Fotografía industrial", "Fotografia industrial"),
    "Ciencia y medicina": ("ciencia_medicina", "Ciencia y medicina", "Ciència i medicina"),
    "Arquitectura e instalaciones": ("arquitectura_instalaciones", "Arquitectura e instalaciones", "Arquitectura i instal·lacions"),
    "Reportajes urbanos y documentales": ("reportajes_urbanos_documentales", "Reportajes urbanos y documentales", "Reportatges urbans i documentals"),
    "Fotografía artística": ("fotografia_artistica", "Fotografía artística", "Fotografia artística"),
    "Publicidad y encargo": ("publicidad", "Publicidad y encargo", "Publicitat i encàrrec"),
    "Reproducción de obras de arte": ("reproduccion_arte", "Reproducción de obras de arte", "Reproducció d'obres d'art"),
    "Experimentación fotográfica": ("experimentacion_fotografica", "Experimentación fotográfica", "Experimentació fotogràfica"),
}
CAT_FALLBACK = ("sin_categoria", "Sin categoría", "Sense categoria")
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ""}


def s(v):
    """Normaliza a str limpiando; preserva saltos de línea internos."""
    if v is None:
        return ""
    return str(v).strip()


def slugify(text):
    t = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "sin-titulo"


def decade_of(fecha):
    """Década de inicio (año más temprano que aparezca en la cadena)."""
    yrs = [int(y) for y in re.findall(r"(1[89]\d\d|20\d\d)", fecha or "")]
    if not yrs:
        return None
    return (min(yrs) // 10) * 10


def build_folder_index():
    idx = {}
    for fondo, rel in FOLDER.items():
        d = ARCHIVE / rel
        byfull, bystem = {}, defaultdict(list)
        if d.is_dir():
            for fn in os.listdir(d):
                if fn.startswith("."):
                    continue
                fp = d / fn
                if not fp.is_file():
                    continue
                if fp.suffix.lower() not in IMG_EXT:
                    continue
                byfull[fn.lower()] = fn
                bystem[os.path.splitext(fn)[0].lower()].append(fn)
        idx[fondo] = (byfull, bystem, d)
    return idx


def locate_file(idx, fondo, orig):
    """Localiza el archivo físico. Emparejamiento ESTRICTO: nombre exacto (ci) o, cuando al Excel
    le falta la extensión, stem exacto (ci) si es inequívoco. Nunca fuzzy (no colapsa sufijos)."""
    if fondo not in idx:
        return None
    byfull, bystem, d = idx[fondo]
    o = orig.lower()
    if o in byfull:                       # nombre completo exacto
        return d, byfull[o]
    stem = os.path.splitext(o)[0]
    cands = bystem.get(stem)              # stem exacto (p. ej. Excel sin extensión)
    if cands and len(cands) == 1:
        return d, cands[0]
    return None


_KEYVAL = re.compile(r"^[\wÀ-ÿ .·/]{1,20}:")            # "Autor:", "Copyright:", "Núm. del catàleg:"
_DIM_ONLY = re.compile(r"^(m\.i\.\s*)?[\d.,]+\s*[x×]\s*[\d.,]+\s*(cm|mm)?\.?$", re.IGNORECASE)


def _truncate(line):
    line = line.strip()
    return line[:88].rstrip() + "…" if len(line) > 90 else line


def _is_caption(line):
    """True si la línea parece una frase real (no un par 'Clave: valor' ni una medida)."""
    if len(line) < 15 or " " not in line or _KEYVAL.match(line) or _DIM_ONLY.match(line):
        return False
    return bool(re.match(r"^[A-Za-zÀ-ÿ¿¡]", line))


def titulo_from(desc, proyecto):
    """Título legible: 1) el contenido de una línea 'Descripció:/Descripción:'; 2) la primera
    línea que parezca una frase real; 3) el nombre del proyecto (fallback siempre válido)."""
    proyecto = (proyecto or "").strip()
    for raw in (desc or "").split("\n"):
        m = re.match(r"^\s*(?:descripci[óo]n?|descripció)\s*:\s*(.+)$", raw, re.IGNORECASE)
        if m and m.group(1).strip():
            return _truncate(m.group(1))
    # solo la PRIMERA línea con texto cuenta como caption libre (estilo IEFC); si es metadato
    # (museo/filmoteca empiezan por "m.i."/"Clave:"), se usa el nombre del proyecto.
    for raw in (desc or "").split("\n"):
        line = raw.strip()
        if line:
            return _truncate(line) if _is_caption(line) else proyecto
    return proyecto


def rescale(src, dst, force=False):
    if dst.exists() and not force:
        return "skip"
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))  # no amplía; lado largo ≤ 1000
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=JPEG_Q, optimize=True)
    return "done"


# ── 1. Leer Excel + colapsar duplicados ───────────────────────────────────────
def read_and_resolve():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Inventario"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = list(rows[0])
    col = {h: i for i, h in enumerate(hdr)}

    def g(r, name):
        return r[col[name]] if col.get(name) is not None else None

    groups = defaultdict(list)  # original → [(row_index, row)]
    for i, r in enumerate(rows[1:], start=2):
        orig = s(g(r, "original"))
        if not orig:
            continue
        groups[orig].append((i, r))

    records = []
    for orig, items in groups.items():
        # gana la última pasada, prefiriendo descripción no vacía
        with_desc = [(i, r) for i, r in items if s(g(r, "descripcion_es"))]
        pool = with_desc if with_desc else items
        _, win = max(pool, key=lambda t: t[0])

        cat = g(win, "categoría")
        if cat is None:  # hereda de otra copia del grupo con categoría
            for _, r in sorted(items, key=lambda t: -t[0]):
                if g(r, "categoría") is not None:
                    cat = g(r, "categoría")
                    break
        cat_slug, cat_es, cat_ca = CATS.get(cat, CAT_FALLBACK)

        destacado = 1 if any(g(r, "Destacado") == 1 for _, r in items) else 0
        fecha = s(g(win, "fecha_estimada"))
        records.append({
            "orig": orig,
            "fondo": s(g(win, "fondo")),
            "categoria_slug": cat_slug,
            "categoria_es": cat_es,
            "categoria_ca": cat_ca,
            "proyecto_es": s(g(win, "proyecto_es")) or "(sin proyecto)",
            "proyecto_ca": s(g(win, "proyecto_ca")) or s(g(win, "proyecto_es")) or "(sense projecte)",
            # descripciones: se conservan TAL CUAL (con saltos de línea)
            "descripcion_es": s(g(win, "descripcion_es")),
            "descripcion_ca": s(g(win, "descripcion_ca")),
            "lugar_es": s(g(win, "lugar_es")),
            "lugar_ca": s(g(win, "lugar_ca")),
            "fecha": fecha,
            "decada": decade_of(fecha),
            "destacado": destacado,
        })
    return records


# ── 2. Imágenes ───────────────────────────────────────────────────────────────
def process_images(records, idx, force=False):
    stats = Counter()
    used_real = defaultdict(set)  # fondo → {realname} (para cobertura inversa)
    kept = []
    for rec in records:
        loc = locate_file(idx, rec["fondo"], rec["orig"])
        if not loc:
            stats["sin_archivo"] += 1
            print(f"  [SIN ARCHIVO] {rec['fondo']}: {rec['orig']}")
            continue
        d, realname = loc
        used_real[rec["fondo"]].add(realname)
        out_name = os.path.splitext(rec["orig"])[0] + ".jpg"
        try:
            res = rescale(d / realname, OUT_IMG_DIR / out_name, force=force)
            stats[res] += 1
        except Exception as exc:
            stats["error"] += 1
            print(f"  [ERROR imagen] {rec['orig']}: {exc}")
            continue
        rec["image"] = f"{OUT_IMG_URL}/{out_name}"
        rec["titulo_es"] = titulo_from(rec["descripcion_es"], rec["proyecto_es"])
        rec["titulo_ca"] = titulo_from(rec["descripcion_ca"], rec["proyecto_ca"])
        kept.append(rec)
    return kept, stats, used_real


def reverse_coverage(idx, used_real):
    """Archivos físicos que NO tienen ficha en el Excel (quedarían sin publicar)."""
    orphans = []
    for fondo, (byfull, bystem, d) in idx.items():
        for realname in byfull.values():
            if realname not in used_real.get(fondo, set()):
                orphans.append((fondo, realname))
    return sorted(set(orphans))


# ── 4. BD ─────────────────────────────────────────────────────────────────────
def fill_db(records):
    conn = get_connection(str(DB_PATH))  # crea las tablas vía el loop de migración
    conn.execute("DELETE FROM emili_works")
    conn.execute("DELETE FROM emili_decades")
    for r in records:
        conn.execute(
            """INSERT INTO emili_works
               (orig_filename, image_file, fondo, categoria_es, categoria_ca, categoria_slug,
                proyecto_es, proyecto_ca, proyecto_slug, descripcion_es, descripcion_ca,
                lugar_es, lugar_ca, fecha_estimada, decada_start, destacado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["orig"], r["image"], r["fondo"], r["categoria_es"], r["categoria_ca"],
             r["categoria_slug"], r["proyecto_es"], r["proyecto_ca"], slugify(r["proyecto_es"]),
             r["descripcion_es"], r["descripcion_ca"], r["lugar_es"], r["lugar_ca"],
             r["fecha"], r["decada"], r["destacado"]),
        )
    dec_counts = Counter(r["decada"] for r in records if r["decada"] is not None)
    for dec, n in sorted(dec_counts.items()):
        conn.execute(
            "INSERT INTO emili_decades (decade_start, decade_end, label, num_works) VALUES (?,?,?,?)",
            (dec, dec + 10, f"{dec}–{dec + 10}", n),
        )
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


# ── 5. JSON del frontend ──────────────────────────────────────────────────────
def most_common(values):
    vals = [v for v in values if v]
    return Counter(vals).most_common(1)[0][0] if vals else ""


def photo_obj(r):
    return {
        "orig": r["orig"],
        "image": r["image"],
        "titulo_es": r["titulo_es"], "titulo_ca": r["titulo_ca"],
        "descripcion_es": r["descripcion_es"], "descripcion_ca": r["descripcion_ca"],
        "fecha": r["fecha"],
        "lugar_es": r["lugar_es"], "lugar_ca": r["lugar_ca"],
        "categoria_es": r["categoria_es"], "categoria_ca": r["categoria_ca"],
        "fondo": r["fondo"],
        "decada": str(r["decada"]) if r["decada"] is not None else "sf",
    }


def build_obra_json(records):
    # proyecto (por nombre ES) → works; el proyecto se asigna al ámbito mayoritario
    by_proj = defaultdict(list)
    for r in records:
        by_proj[r["proyecto_es"]].append(r)

    ambitos = defaultdict(lambda: {"projects": [], "_slugs": set()})
    for proj_name, works in by_proj.items():
        amb = Counter(w["categoria_slug"] for w in works).most_common(1)[0][0]
        works_sorted = sorted(works, key=lambda w: w["orig"])
        base_slug = slugify(proj_name)
        slug, n = base_slug, 2
        while slug in ambitos[amb]["_slugs"]:
            slug = f"{base_slug}-{n}"; n += 1
        ambitos[amb]["_slugs"].add(slug)
        decs = sorted({str(w["decada"]) for w in works if w["decada"] is not None})
        cover = next((w["image"] for w in works_sorted if w.get("image")), "")
        earliest = min(works, key=lambda w: (w["decada"] is None, w["decada"] or 0))
        # año numérico para ordenar cronológicamente (año más temprano de las fotos del proyecto)
        yrs = [y for w in works for y in re.findall(r"(1[89]\d\d|20\d\d)", w["fecha"] or "")]
        year = min(int(y) for y in yrs) if yrs else (earliest["decada"] or 9999)
        ambitos[amb]["projects"].append({
            "slug": slug,
            "nombre_es": proj_name,
            "nombre_ca": most_common([w["proyecto_ca"] for w in works]) or proj_name,
            "lugar_es": most_common([w["lugar_es"] for w in works]),
            "lugar_ca": most_common([w["lugar_ca"] for w in works]),
            "fecha": earliest["fecha"],
            "year": year,
            "decada": decs[0] if decs else "sf",
            "count": len(works),
            "cover": cover,
            "fondos": sorted({w["fondo"] for w in works if w["fondo"]}),
            "photos": [photo_obj(w) for w in works_sorted],
        })

    out_ambitos = {}
    for amb, data in ambitos.items():
        projs = sorted(data["projects"], key=lambda p: -p["count"])
        photos_total = sum(p["count"] for p in projs)
        decs = sorted({ph["decada"] for p in projs for ph in p["photos"] if ph["decada"] != "sf"})
        fondos = sorted({f for p in projs for f in p["fondos"]})
        out_ambitos[amb] = {"count": photos_total, "decades": decs, "fondos": fondos, "projects": projs}

    ambito_order = [a for a, _ in sorted(out_ambitos.items(), key=lambda kv: -kv[1]["count"])]
    decades = sorted({str(r["decada"]) for r in records if r["decada"] is not None})
    fondos_order = [f for f, _ in Counter(r["fondo"] for r in records if r["fondo"]).most_common()]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ambito_order": ambito_order,
        "ambitos": out_ambitos,
        "decades": decades,
        "fondos": fondos_order,
        "total": len(records),
    }


def build_destacadas_json(records):
    dest = [r for r in records if r["destacado"]]
    dest.sort(key=lambda r: (r["fondo"], r["orig"]))
    out = []
    for i, r in enumerate(dest, start=1):
        obj = photo_obj(r)
        # El título de la destacada es el nombre de la obra (proyecto), no la descripción.
        obj["titulo_es"] = r["proyecto_es"]
        obj["titulo_ca"] = r["proyecto_ca"]
        obj["ambito"] = r["categoria_slug"]
        obj["orden"] = i
        out.append(obj)
    return out


def main():
    force = "--force" in sys.argv
    if not XLSX.exists():
        sys.exit(f"No existe el Excel: {XLSX}")
    print(f"Leyendo {XLSX.name} …")
    records = read_and_resolve()
    print(f"  {len(records)} fotos únicas tras colapsar duplicados por nombre de archivo.")

    idx = build_folder_index()
    print("Reescalando imágenes (lado largo 1000 px, JPEG q60) …")
    kept, stats, used_real = process_images(records, idx, force=force)
    print(f"  imágenes: {stats['done']} nuevas, {stats['skip']} ya existían, "
          f"{stats['sin_archivo']} sin archivo, {stats['error']} con error.")

    orphans = reverse_coverage(idx, used_real)
    if orphans:
        print(f"\n⚠️  COBERTURA INVERSA: {len(orphans)} archivos físicos SIN ficha en el Excel "
              f"(quedan sin publicar):")
        for fondo, fn in orphans:
            print(f"     [{fondo}] {fn}")
        print("   → catalógalos en el Excel y relanza esta importación.\n")
    else:
        print("  cobertura inversa: OK, todos los archivos físicos tienen ficha.")

    print("Rellenando BD (emili_works, emili_decades) …")
    fill_db(kept)

    print("Generando obra.json y destacadas.json …")
    obra = build_obra_json(kept)
    OBRA_JSON.write_text(json.dumps(obra, ensure_ascii=False, indent=1), encoding="utf-8")
    dest = build_destacadas_json(kept)
    DEST_JSON.write_text(json.dumps(dest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nHecho. {len(kept)} fotos publicadas · {len(obra['ambito_order'])} categorías · "
          f"{len(obra['fondos'])} fondos · {len(dest)} destacadas.")
    print(f"  obra.json      → {OBRA_JSON}")
    print(f"  destacadas.json→ {DEST_JSON}")
    print(f"  imágenes       → {OUT_IMG_DIR}")


if __name__ == "__main__":
    main()
