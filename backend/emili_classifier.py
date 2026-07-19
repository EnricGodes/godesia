"""Pipeline de clasificación asistida del archivo fotográfico de Emili Godes.

Escanea el archivo local (_resources/emili-godes/archivo), envía lotes a Claude
Sonnet 4.6 vía Batch API (−50%) para sugerir proyecto/categoría/fecha/lugar/descripción,
y al aprobar optimiza+renombra+archiva cada imagen en data/photos/emili-godes/.

La fuente de verdad es la tabla `emili_photos` en godesia.db. Todo el trabajo con la API
de Anthropic se hace de forma perezosa (import dentro de las funciones) para que el
servidor arranque sin la key y sin la SDK.
"""

import base64
import io
import json
import re
import unicodedata
from pathlib import Path

MODEL = "claude-sonnet-4-6"

# Batch API = 50% del precio estándar de Sonnet ($3/M in, $15/M out).
PRICE_IN_PER_TOKEN = 1.5 / 1_000_000
PRICE_OUT_PER_TOKEN = 7.5 / 1_000_000

IMGS_PER_REQUEST = 8          # imágenes de la misma serie por petición
IMG_MAX_PX = 1024             # reducción antes de enviar
IMG_QUALITY = 80

# Heurística de coste (tokens aprox.)
TOK_PER_IMAGE_IN = 1300
TOK_SYSTEM_IN = 2600          # digest + instrucciones (se cachea, pero se cuenta full la 1ª vez)
TOK_PER_IMAGE_OUT = 320

CATEGORIES = [
    "creación artística",
    "encargo profesional",
    "documentación industrial y urbana",
    "fotografía científica y médica",
    "reproducción y difusión del arte",
    "fotografía y cine",
    "experimentación técnica y visual",
]

# Carpetas del archivo dentro del alcance (no recursivo → excluye "Fotos familiares").
SCAN_FOLDERS = ("IEFC", "MNAC")
IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

def archive_dir(base_dir: Path) -> Path:
    return Path(base_dir) / "_resources" / "emili-godes" / "archivo"


def dest_root(base_dir: Path) -> Path:
    return Path(base_dir) / "data" / "photos" / "emili-godes"


def digest_path(base_dir: Path) -> Path:
    return Path(base_dir) / "data" / "emili" / "tfg_digest.md"


def archive_available(base_dir: Path) -> bool:
    d = archive_dir(base_dir)
    return d.is_dir() and any((d / f).is_dir() for f in SCAN_FOLDERS)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def slugify(text: str, maxlen: int = 60) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:maxlen].strip("-")


def _parse_name(carpeta: str, filename: str):
    """Devuelve (serie, serie_num, catalog_no) a partir del nombre de fichero."""
    stem = re.sub(r"\s*\(\d+\)$", "", Path(filename).stem)  # quita "(1)" de duplicados
    if carpeta == "MNAC":
        m = re.match(r"^(\d{6}-\d{3})", stem)
        catalog = m.group(1) if m else None
        return "MNAC", None, catalog
    # IEFC: ACP-23-14, ACM-23-3, FCP-23-76 ...
    m = re.match(r"^([A-Z]{2,4}-\d+)-(\d+)", stem)
    if m:
        return m.group(1), int(m.group(2)), None
    return carpeta, None, None


def image_path(base_dir: Path, carpeta: str, orig_filename: str) -> Path:
    return archive_dir(base_dir) / carpeta / orig_filename


def _downscale_jpeg_b64(path: Path, max_px: int = IMG_MAX_PX, quality: int = IMG_QUALITY) -> str:
    from PIL import Image, ImageOps  # noqa: PLC0415
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Escaneo
# ---------------------------------------------------------------------------

def scan(conn, base_dir: Path) -> dict:
    """Registra las imágenes del archivo (no recursivo, solo SCAN_FOLDERS) en emili_photos."""
    root = archive_dir(base_dir)
    added = skipped = 0
    for carpeta in SCAN_FOLDERS:
        folder = root / carpeta
        if not folder.is_dir():
            continue
        for p in sorted(folder.iterdir()):
            if not p.is_file() or p.suffix.lower() not in IMG_EXTS:
                continue
            serie, num, catalog = _parse_name(carpeta, p.name)
            proyecto = f"MNAC {catalog}" if catalog else None
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO emili_photos
                       (orig_filename, carpeta, serie, serie_num, proyecto, status)
                       VALUES (?, ?, ?, ?, ?, 'pendiente')""",
                    (p.name, carpeta, serie, num, proyecto),
                )
                if cur.rowcount:
                    added += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
    conn.commit()
    return {"added": added, "skipped": skipped}


def stats(conn) -> dict:
    rows = conn.execute(
        "SELECT status, COUNT(*) n FROM emili_photos GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}
    total = sum(by_status.values())
    coste = conn.execute(
        "SELECT COALESCE(SUM(coste_estimado),0) c FROM emili_batches"
    ).fetchone()["c"]
    return {"total": total, "by_status": by_status, "coste_acumulado": round(coste or 0, 4)}


# ---------------------------------------------------------------------------
# Estimación de coste
# ---------------------------------------------------------------------------

def estimate_cost(n_imgs: int) -> float:
    if n_imgs <= 0:
        return 0.0
    n_requests = (n_imgs + IMGS_PER_REQUEST - 1) // IMGS_PER_REQUEST
    tok_in = n_imgs * TOK_PER_IMAGE_IN + n_requests * TOK_SYSTEM_IN
    tok_out = n_imgs * TOK_PER_IMAGE_OUT
    return round(tok_in * PRICE_IN_PER_TOKEN + tok_out * PRICE_OUT_PER_TOKEN, 4)


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------

def _system_blocks(base_dir: Path):
    dp = digest_path(base_dir)
    digest = dp.read_text(encoding="utf-8") if dp.exists() else ""
    cats = "\n".join(f"- {c}" for c in CATEGORIES)
    instr = (
        "Eres archivero especialista en la obra del fotógrafo Emili Godes (Barcelona, "
        "1895–1970). Recibes imágenes de su archivo, normalmente en series contiguas del "
        "mismo reportaje. Para CADA imagen devuelves una ficha de catalogación.\n\n"
        "Reglas:\n"
        "- `categoria` debe ser EXACTAMENTE una de esta lista:\n" + cats + "\n"
        "- `proyecto`: nombre del reportaje/serie si lo reconoces del digest o del contenido "
        "(p. ej. 'Residencia señorial', 'Laboratorios del Dr. Esteve', 'Reportaje de Córdoba'); "
        "si no, propón uno descriptivo. Las imágenes contiguas de una serie suelen compartir proyecto.\n"
        "- `fecha_estimada`: como 'c. 1935', '1957' o 'por determinar'. `fecha_certeza`: "
        "'exacta' | 'estimada' | 'por determinar'.\n"
        "- `lugar`: topónimo concreto si es deducible, si no 'por determinar'.\n"
        "- `descripcion`: en castellano, objetiva y detallada de lo que se ve.\n"
        "- `confianza`: 0.0–1.0. `razonamiento`: 1–2 frases con las pistas usadas.\n"
        "- No inventes datos. Ante la duda, usa 'por determinar'.\n\n"
        "SALIDA: responde EXCLUSIVAMENTE con un array JSON, un objeto por imagen, con las "
        "claves exactas: orig_filename, proyecto, categoria, fecha_estimada, fecha_certeza, "
        "lugar, descripcion, confianza, razonamiento. Sin texto adicional ni markdown."
    )
    return [
        {"type": "text", "text": instr},
        {
            "type": "text",
            "text": "DIGEST DE REFERENCIA (TFG de Laia Foix + catálogos):\n\n" + digest,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _select_pending(conn, limit: int):
    """Pendientes ordenadas por serie y número → grupos contiguos del mismo reportaje."""
    q = ("SELECT * FROM emili_photos WHERE status='pendiente' "
         "ORDER BY carpeta, serie, serie_num, orig_filename")
    if limit and limit > 0:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def _group_rows(rows):
    """Agrupa filas contiguas de la misma serie en bloques de IMGS_PER_REQUEST."""
    groups, cur, cur_serie = [], [], None
    for r in rows:
        if r["serie"] != cur_serie or len(cur) >= IMGS_PER_REQUEST:
            if cur:
                groups.append(cur)
            cur, cur_serie = [], r["serie"]
        cur.append(r)
    if cur:
        groups.append(cur)
    return groups


def _build_requests(base_dir: Path, groups):
    """Construye los objetos Request del Batch API. Devuelve (requests, custom_id→[ids])."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming  # noqa: PLC0415
    from anthropic.types.messages.batch_create_params import Request  # noqa: PLC0415

    system = _system_blocks(base_dir)
    requests, mapping = [], {}
    for gi, group in enumerate(groups):
        content = []
        serie = group[0]["serie"]
        nums = [str(r["serie_num"]) for r in group if r["serie_num"] is not None]
        ctx = f"Serie {serie}" + (f", números {', '.join(nums)}" if nums else "") + \
              ". Analiza cada imagen; los números contiguos suelen ser el mismo reportaje."
        content.append({"type": "text", "text": ctx})
        for r in group:
            content.append({"type": "text", "text": f"Imagen orig_filename={r['orig_filename']}:"})
            b64 = _downscale_jpeg_b64(image_path(base_dir, r["carpeta"], r["orig_filename"]))
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })
        cid = f"g{gi}"
        mapping[cid] = [r["id"] for r in group]
        requests.append(Request(
            custom_id=cid,
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=3500,
                system=system,
                messages=[{"role": "user", "content": content}],
            ),
        ))
    return requests, mapping


# ---------------------------------------------------------------------------
# Envío y recogida de batches
# ---------------------------------------------------------------------------

def submit_batch(conn, base_dir: Path, limit: int, log=print):
    import anthropic  # noqa: PLC0415
    rows = _select_pending(conn, limit)
    if not rows:
        raise RuntimeError("No hay imágenes pendientes.")
    groups = _group_rows(rows)
    log(f"Preparando {len(rows)} imágenes en {len(groups)} peticiones…")
    requests, mapping = _build_requests(base_dir, groups)

    client = anthropic.Anthropic(timeout=120.0)
    batch = client.messages.batches.create(requests=requests)
    coste = estimate_cost(len(rows))

    cur = conn.execute(
        "INSERT INTO emili_batches (anthropic_batch_id, status, num_imgs, coste_estimado) "
        "VALUES (?, 'in_progress', ?, ?)",
        (batch.id, len(rows), coste),
    )
    batch_db_id = cur.lastrowid
    all_ids = [pid for ids in mapping.values() for pid in ids]
    conn.executemany(
        "UPDATE emili_photos SET status='en_lote', batch_id=?, updated_at=datetime('now') WHERE id=?",
        [(batch_db_id, pid) for pid in all_ids],
    )
    # Guardamos el mapping custom_id→ids en la fila del batch (columna sugerencia reutilizada
    # no existe aquí; lo recomputamos al ingerir por orig_filename, así que no hace falta).
    conn.commit()
    log(f"Batch enviado: {batch.id} ({len(rows)} imgs, ~${coste}).")
    return {"batch_db_id": batch_db_id, "anthropic_batch_id": batch.id,
            "num_imgs": len(rows), "coste_estimado": coste}


def _extract_json_array(text: str):
    a, b = text.find("["), text.rfind("]")
    if a == -1 or b == -1 or b < a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except Exception:
        return None


def poll_and_ingest(conn, base_dir: Path, batch_db_id: int, log=print) -> dict:
    """Comprueba el estado del batch; si ha terminado, ingiere resultados. Idempotente."""
    import anthropic  # noqa: PLC0415
    row = conn.execute("SELECT * FROM emili_batches WHERE id=?", (batch_db_id,)).fetchone()
    if not row:
        raise RuntimeError("Batch desconocido.")
    if row["status"] == "ended":
        return {"status": "ended", "ingested": 0}

    client = anthropic.Anthropic(timeout=120.0)
    b = client.messages.batches.retrieve(row["anthropic_batch_id"])
    if b.processing_status != "ended":
        return {"status": b.processing_status, "ingested": 0}

    ingested = errors = 0
    for res in client.messages.batches.results(row["anthropic_batch_id"]):
        if res.result.type != "succeeded":
            errors += 1
            continue
        blocks = res.result.message.content
        text = next((blk.text for blk in blocks if getattr(blk, "type", "") == "text"), "")
        arr = _extract_json_array(text)
        if not arr:
            errors += 1
            continue
        for item in arr:
            of = (item.get("orig_filename") or "").strip()
            if not of:
                continue
            cat = item.get("categoria")
            if cat not in CATEGORIES:
                cat = None
            conn.execute(
                """UPDATE emili_photos SET
                     status='analizada', origen='llm',
                     proyecto=COALESCE(?, proyecto), categoria=?,
                     fecha_estimada=?, fecha_certeza=?, lugar=?, descripcion=?,
                     confianza=?, razonamiento=?, sugerencia=?,
                     updated_at=datetime('now')
                   WHERE orig_filename=? AND batch_id=?""",
                (item.get("proyecto"), cat, item.get("fecha_estimada"),
                 item.get("fecha_certeza"), item.get("lugar"), item.get("descripcion"),
                 item.get("confianza"), item.get("razonamiento"),
                 json.dumps(item, ensure_ascii=False), of, batch_db_id),
            )
            ingested += 1
    conn.execute(
        "UPDATE emili_batches SET status='ended', ended_at=datetime('now') WHERE id=?",
        (batch_db_id,),
    )
    # Cualquier foto que quedara 'en_lote' sin resultado vuelve a pendiente.
    conn.execute(
        "UPDATE emili_photos SET status='pendiente' WHERE batch_id=? AND status='en_lote'",
        (batch_db_id,),
    )
    conn.commit()
    log(f"Ingeridas {ingested} fichas ({errors} errores).")
    return {"status": "ended", "ingested": ingested, "errors": errors}


# ---------------------------------------------------------------------------
# Aprobación: optimizar + renombrar + archivar
# ---------------------------------------------------------------------------

CATEGORY_DIR = {
    "creación artística": "01_creacion_artistica",
    "encargo profesional": "02_encargo_profesional",
    "documentación industrial y urbana": "03_industrial_urbana",
    "fotografía científica y médica": "04_ciencia_medicina",
    "reproducción y difusión del arte": "05_reproduccion_arte",
    "fotografía y cine": "06_cine",
    "experimentación técnica y visual": "07_experimentacion",
}


def _new_filename(row) -> str:
    fecha = slugify(row["fecha_estimada"] or "sf", 12) or "sf"
    proj = slugify(row["proyecto"] or "sin-proyecto", 30)
    desc = slugify(row["descripcion"] or "", 40)
    orig = Path(row["orig_filename"]).stem
    orig = re.sub(r"\s*\(\d+\)$", "", orig)
    parts = [p for p in (fecha, proj, desc, orig) if p]
    return "-".join(parts) + ".jpg"


def approve(conn, base_dir: Path, ids, log=print) -> dict:
    from PIL import Image, ImageOps  # noqa: PLC0415
    done = skipped = 0
    for pid in ids:
        row = conn.execute("SELECT * FROM emili_photos WHERE id=?", (pid,)).fetchone()
        if not row or row["status"] not in ("analizada", "aprobada"):
            skipped += 1
            continue
        cat_dir = CATEGORY_DIR.get(row["categoria"] or "", "00_sin_categoria")
        proj_dir = slugify(row["proyecto"] or "sin-proyecto", 40) or "sin-proyecto"
        dest_dir = dest_root(base_dir) / cat_dir / proj_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        new_name = _new_filename(row)
        dest = dest_dir / new_name

        src = image_path(base_dir, row["carpeta"], row["orig_filename"])
        try:
            img = Image.open(src)
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            if max(img.size) > 1600:
                img.thumbnail((1600, 1600))
            img.save(dest, "JPEG", quality=82, optimize=True)
        except Exception as e:  # noqa: BLE001
            log(f"Error optimizando {row['orig_filename']}: {e}")
            skipped += 1
            continue

        rel = str(dest.relative_to(dest_root(base_dir).parent.parent))  # relativo a data/
        conn.execute(
            "UPDATE emili_photos SET status='aprobada', new_filename=?, dest_path=?, "
            "updated_at=datetime('now') WHERE id=?",
            (new_name, rel, pid),
        )
        done += 1
    conn.commit()
    log(f"Aprobadas {done} imágenes ({skipped} omitidas).")
    return {"approved": done, "skipped": skipped}
