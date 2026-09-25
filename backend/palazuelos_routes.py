"""Palazuelos → Godes synchronization: matching, photo discovery, download."""

import codecs
import json
import re
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from admin_routes import (
    _canonicalize_person_name,
    _ged_year,
    _build_ged_index,
    _NAME_VARIANTS,
)

router = APIRouter(prefix="/api/admin/palazuelos", tags=["palazuelos"])


def _fix_encoding(text: str) -> str:
    """Repair mojibake: text was UTF-8 bytes read as latin-1."""
    if not text:
        return text
    try:
        fixed = text.encode('latin-1').decode('utf-8')
        return fixed if fixed != text else text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

_db_conn = None
_base_dir: Optional[Path] = None


def init_palazuelos(db_conn, base_dir: Path):
    global _db_conn, _base_dir
    _db_conn = db_conn
    _base_dir = base_dir


def _db():
    if not _db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return _db_conn


def _volume_ged_path() -> Path:
    """Copia en el volumen persistente de Railway (docs/ no se sube al repo:
    el GEDCOM lleva datos personales de 20k personas). /photos/_gedcom → 403."""
    return _base_dir / "data" / "photos" / "_gedcom" / "palazuelos.ged"


def _default_ged_path() -> Path:
    vol = _volume_ged_path()
    local = _base_dir / "docs" / "palazuelos.ged"
    if vol.exists() and (not local.exists() or vol.stat().st_mtime >= local.stat().st_mtime):
        return vol
    return local if local.exists() else vol


# Caché del GEDCOM Palazuelos parseado (19,5k INDI: parsearlo por petición
# tarda segundos). Se invalida cuando cambia el mtime del fichero.
_palaz_cache = {"mtime": None, "data": None}


def _palaz_data() -> dict:
    ged_path = _default_ged_path()
    if not ged_path.exists():
        raise HTTPException(404, "palazuelos.ged no trobat")
    mtime = ged_path.stat().st_mtime
    if _palaz_cache["data"] is None or _palaz_cache["mtime"] != mtime:
        from gedcom_parser import parse_gedcom
        _palaz_cache["data"] = parse_gedcom(str(ged_path))
        _palaz_cache["mtime"] = mtime
    return _palaz_cache["data"]


# ── MyHeritage: enlaces directos a una persona en cada árbol ─────────────────
# Ambos árboles viven en el mismo sitio MyHeritage; el número del xref GEDCOM
# (@I1543@) es el RIN de MyHeritage (1 RIN MH:I1543). El ID de individuo que
# acepta la URL del árbol es {treeId}{RIN a 6 cifras}: Artur @I16@ en el árbol
# Godes (5) → rootIndividualID=5000016 (verificado 21/09/2026). Plantilla e IDs
# de árbol son ajustes (settings) editables en admin → Configuración.
MH_DEFAULTS = {
    "mh_tree_url": "https://www.myheritage.es/family-trees/arbol-familiar-palazuelos-salvado/"
                   "OYYV7S4KDS66QHEY2TNYYNVUPL3FOZY?familyTreeID={tree}&rootIndividualID={indiv}",
    "mh_tree_id_palazuelos": "3",
    "mh_tree_id_godes": "5",
}


def _mh_setting(key: str) -> str:
    from database import get_setting
    return get_setting(_db(), key, MH_DEFAULTS[key]) or MH_DEFAULTS[key]


def _mh_person_url(tree_key: str, xref: Optional[str]) -> Optional[str]:
    if not xref:
        return None
    rin = re.sub(r"\D", "", xref)
    if not rin:
        return None
    tree = _mh_setting(tree_key)
    indiv = f"{tree}{int(rin):06d}"
    return (_mh_setting("mh_tree_url").replace("{tree}", tree)
            .replace("{indiv}", indiv).replace("{rin}", rin))


# ---------------------------------------------------------------------------
# GEDCOM photo parser (gedcom_parser.py doesn't parse OBJE details)
# ---------------------------------------------------------------------------

def _extract_hash(filename: str) -> Optional[str]:
    """Extract the middle hash from filenames like '501608_5688393sa3d55ckq98h01e_R.jpg'."""
    m = re.match(r'^\d+_([a-z0-9]+)_[A-Z]+\.\w+$', filename, re.IGNORECASE)
    return m.group(1) if m else None


def _parse_palaz_photos(ged_path: str) -> dict:
    """Parse OBJE blocks per individual. Returns {palaz_id: [photo_dict, ...]}."""
    with open(ged_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        content = f.read().replace('\r\n', '\n').replace('\r', '\n')

    photos_by_indi: dict = {}
    current_indi: Optional[str] = None
    in_obje = False
    cur: dict = {}

    def _flush():
        if in_obje and cur.get('filename') and current_indi:
            photos_by_indi.setdefault(current_indi, []).append(dict(cur))

    for raw_line in content.split('\n'):
        line = raw_line.strip()
        parts = line.split(' ', 2)
        if len(parts) < 2:
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue
        tag = parts[1]
        value = parts[2] if len(parts) > 2 else ''

        if level == 0:
            _flush()
            in_obje = False
            cur = {}
            if tag.startswith('@I') and value == 'INDI':
                current_indi = tag  # keep "@I1543@" to match gedcom_parser keys
            elif tag.startswith('@') and value != 'INDI':
                current_indi = None

        elif level == 1:
            if tag == 'OBJE':
                _flush()
                in_obje = True
                cur = {}
            elif in_obje:
                _flush()
                in_obje = False
                cur = {}

        elif level == 2 and in_obje:
            if tag == 'FILE':
                m = re.search(r'(\d+_[a-z0-9]+_[A-Z]+\.(?:jpg|jpeg|pdf|png))', value, re.IGNORECASE)
                if m:
                    cur['filename'] = m.group(1)
                cur['url'] = value
            elif tag == 'TITL':
                cur['title'] = value
            elif tag == '_PHOTO_RIN':
                cur['photo_rin'] = value
            elif tag == '_PRIM':
                cur['is_prim'] = (value.strip() == 'Y')
            elif tag == '_PRIM_CUTOUT':
                cur['is_prim_cutout'] = (value.strip() == 'Y')
            elif tag == '_CUTOUT':
                cur['is_cutout'] = (value.strip() == 'Y')
            elif tag == '_PARENTPHOTO':
                cur['is_parent_photo'] = (value.strip() == 'Y')
            elif tag == '_PERSONALPHOTO':
                cur['is_personal_photo'] = (value.strip() == 'Y')
            elif tag == '_PARENTRIN':
                cur['parent_rin'] = value

    _flush()
    return photos_by_indi


# ---------------------------------------------------------------------------
# Matching algorithm
# ---------------------------------------------------------------------------

def _token_jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two canonical name strings."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union) if union else 0.0


def _year_pts(ya, yb, max_pts: int) -> int:
    if not ya or not yb:
        return 0
    d = abs(ya - yb)
    if d == 0:
        return max_pts
    if d <= 1:
        return int(max_pts * 0.80)
    if d <= 2:
        return int(max_pts * 0.60)
    if d <= 3:
        return int(max_pts * 0.35)
    if d <= 5:
        return int(max_pts * 0.15)
    return 0


def _score_pair(godes: dict, palaz: dict, palaz_fams: dict, palaz_indis: dict) -> int:
    """Score a Godes↔Palazuelos candidate pair. Returns 0-100."""
    # 1. Name (50 pts)
    gc = _canonicalize_person_name(godes.get('name') or '')
    pc = _canonicalize_person_name(palaz.get('name') or '')
    name_pts = int(_token_jaccard(gc, pc) * 50)

    # 2. Birth year (25 pts)
    gb = godes.get('birth_year')
    pb = _ged_year((palaz.get('birth') or {}).get('date') or '')
    birth_pts = _year_pts(gb, pb, 25)

    # 3. Death year (15 pts)
    gd = godes.get('death_year')
    pd = _ged_year((palaz.get('death') or {}).get('date') or '')
    death_pts = _year_pts(gd, pd, 15)

    # 4. Parental surnames (10 pts)
    family_pts = 0
    famc = palaz.get('family_child')
    if famc and famc in palaz_fams:
        fam = palaz_fams[famc]
        husb_id = fam.get('husband') or ''   # e.g. "@I290@" — keep as-is
        wife_id = fam.get('wife') or ''
        g_father_sn = _canonicalize_person_name(godes.get('father_surname') or '')
        g_mother_sn = _canonicalize_person_name(godes.get('mother_surname') or '')
        if husb_id and husb_id in palaz_indis and g_father_sn:
            p_sn = _canonicalize_person_name(palaz_indis[husb_id].get('surname') or '')
            if p_sn and g_father_sn == p_sn:
                family_pts += 5
        if wife_id and wife_id in palaz_indis and g_mother_sn:
            p_sn = _canonicalize_person_name(palaz_indis[wife_id].get('surname') or '')
            if p_sn and g_mother_sn == p_sn:
                family_pts += 5

    return min(name_pts + birth_pts + death_pts + family_pts, 100)


# ---------------------------------------------------------------------------
# Multi-person photo tagging helpers
# ---------------------------------------------------------------------------

def _build_rin_index(palaz_photos: dict) -> dict:
    """Build inverse index: {photo_rin → [palaz_id, ...]} from _parse_palaz_photos() output."""
    idx: dict = {}
    for palaz_id, photos in palaz_photos.items():
        for ph in photos:
            rin = ph.get("photo_rin")
            if rin:
                idx.setdefault(rin, []).append(palaz_id)
    return idx


def _load_palaz_map_dict(db) -> dict:
    """Return {palaz_id → godes_id} for all confirmed (non-rejected) matches."""
    try:
        rows = db.execute(
            "SELECT palaz_id, godes_id FROM palazuelos_map WHERE palaz_id IS NOT NULL AND match_type != 'rejected'"
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _auto_tag_all_matched(db, rin_index: dict, palaz_map: dict, photo_rin: str, photo_id: int) -> int:
    """Create photo_tags for all Godes persons that have photo_rin in their GEDCOM OBJE.

    Returns the number of new tags inserted.
    """
    palaz_ids = rin_index.get(photo_rin, [])
    tagged = 0
    for palaz_id in palaz_ids:
        godes_id = palaz_map.get(palaz_id)
        if not godes_id:
            continue
        cur = db.execute(
            "INSERT OR IGNORE INTO photo_tags (photo_id, person_id) VALUES (?,?)",
            (photo_id, godes_id)
        )
        if cur.rowcount:
            tagged += 1
    if tagged:
        db.commit()
    return tagged


# ---------------------------------------------------------------------------
# Background build-map job
# ---------------------------------------------------------------------------

_job: dict = {"status": "idle", "progress": 0, "total": 0, "log": [], "result": None}
_job_lock = threading.Lock()


def _jlog(msg: str):
    with _job_lock:
        _job["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# Un rechazado se reabre a revisión si AHORA puntúa al menos esto (nivel de
# auto-match) y por encima de cuando se rechazó. El resto sigue rechazado.
REJECTED_RESURFACE_MIN = 80


def _run_build_map(ged_path: str, db_path: str):
    import sys
    t0 = time.time()
    try:
        backend_dir = str(Path(db_path).parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from gedcom_parser import parse_gedcom
        from database import get_connection as _gc

        with _job_lock:
            _job.update({"status": "running", "progress": 0, "log": [], "result": None})

        _jlog(f"Parsejant {Path(ged_path).name}…")
        data = parse_gedcom(ged_path)
        palaz_indis = data["individuals"]
        palaz_fams = data["families"]
        _jlog(f"  {len(palaz_indis):,} individus Palazuelos, {len(palaz_fams):,} famílies")

        # Build name index for Palazuelos
        _jlog("Construint índex de noms…")
        palaz_index = _build_ged_index(palaz_indis)

        # Load Godes people with parent surnames
        _jlog("Carregant persones Godes…")
        conn = _gc(db_path)
        rows = conn.execute("""
            SELECT p.id, p.name, p.given_name, p.surname,
                   p.birth_year, p.death_year,
                   pf.surname AS father_surname,
                   pm.surname AS mother_surname
            FROM people p
            LEFT JOIN people pf ON p.father_id = pf.id
            LEFT JOIN people pm ON p.mother_id = pm.id
            ORDER BY p.id
        """).fetchall()
        godes_people = [dict(r) for r in rows]
        _jlog(f"  {len(godes_people)} persones Godes")

        # Decisiones del usuario. Las MANUALES se preservan siempre; las
        # RECHAZADAS se vuelven a puntuar (y resurgen a revisión solo si ahora
        # puntúan alto, ver más abajo).
        existing_manual = {}
        existing_rejected = {}
        existing_review = {}   # rechazados ya reabiertos, pendientes de decisión
        try:
            ex = conn.execute(
                "SELECT godes_id, palaz_id, palaz_name, confidence, match_type FROM palazuelos_map WHERE match_type IN ('manual','rejected','review')"
            ).fetchall()
            for row in ex:
                d = dict(row)
                mt = d["match_type"]
                bucket = existing_rejected if mt == "rejected" else existing_review if mt == "review" else existing_manual
                bucket[d["godes_id"]] = d
        except Exception:
            pass

        with _job_lock:
            _job["total"] = len(godes_people)

        matched_auto = 0
        needs_review = 0
        no_match = 0
        resurfaced = 0          # rechazados reabiertos a revisión por puntuar alto
        rows_to_upsert = []
        resurfaced_rows = []    # van con UPDATE explícito (el upsert protege rechazados)

        for i, gp in enumerate(godes_people):
            with _job_lock:
                _job["progress"] = i + 1

            godes_id = gp["id"]

            # Preserve manual decisions
            if godes_id in existing_manual:
                rows_to_upsert.append(existing_manual[godes_id])
                matched_auto += 1
                continue

            # Rechazados ya reabiertos: pegajosos en revisión hasta que el usuario
            # decida (no se re-puntúan, para no auto-confirmarlos en el build siguiente).
            if godes_id in existing_review:
                rows_to_upsert.append(existing_review[godes_id])
                needs_review += 1
                continue

            # Find top candidates
            gc = _canonicalize_person_name(gp.get("name") or "")
            gc_given = _canonicalize_person_name(gp.get("given_name") or "")
            gc_surn = _canonicalize_person_name(gp.get("surname") or "")

            # Candidate pool: from name index
            candidates: set = set()
            probes = [gc]
            if gc_given and gc_surn:
                probes += [f"{gc_given} {gc_surn}", f"{gc_surn} {gc_given}"]
                for tok in gc_given.split():
                    if tok != gc_given:
                        probes += [f"{tok} {gc_surn}", f"{gc_surn} {tok}"]
            for probe in probes:
                if probe:
                    for pid in palaz_index.get(probe, []):
                        candidates.add(pid)

            # Score candidates (cap at top 10 from index, then score all)
            scored = []
            for pid in candidates:
                s = _score_pair(gp, palaz_indis[pid], palaz_fams, palaz_indis)
                scored.append((s, pid))
            scored.sort(reverse=True)

            # Rechazados: re-puntuados. Resurgen a revisión SOLO si ahora puntúan
            # alto (≥ REJECTED_RESURFACE_MIN) y por encima de cuando se rechazaron
            # —así, al volver a rechazarlos no reaparecen (evita el bucle)—. El
            # resto sigue rechazado (no se pasan todos a "sin match").
            if godes_id in existing_rejected:
                rej = existing_rejected[godes_id]
                new_best = scored[0][0] if scored else 0
                stored = rej.get("confidence")
                stored = stored if stored is not None else -1
                if new_best >= REJECTED_RESURFACE_MIN and min(new_best, 79) > stored:
                    best_pid = scored[0][1]
                    resurfaced_rows.append({
                        "godes_id": godes_id,
                        "palaz_id": best_pid,
                        "palaz_name": palaz_indis[best_pid].get("name") or "",
                        "confidence": min(new_best, 79),
                    })
                    needs_review += 1
                    resurfaced += 1
                else:
                    rows_to_upsert.append(rej)
                continue

            if scored and scored[0][0] >= 80:
                best_score, best_pid = scored[0]
                palaz_name = palaz_indis[best_pid].get("name") or ""
                rows_to_upsert.append({
                    "godes_id": godes_id,
                    "palaz_id": best_pid,
                    "palaz_name": palaz_name,
                    "confidence": best_score,
                    "match_type": "auto",
                })
                matched_auto += 1
            elif scored and scored[0][0] >= 35:
                best_score, best_pid = scored[0]
                palaz_name = palaz_indis[best_pid].get("name") or ""
                rows_to_upsert.append({
                    "godes_id": godes_id,
                    "palaz_id": best_pid,
                    "palaz_name": palaz_name,
                    "confidence": best_score,
                    "match_type": "auto",
                })
                needs_review += 1
            else:
                rows_to_upsert.append({
                    "godes_id": godes_id,
                    "palaz_id": None,
                    "palaz_name": None,
                    "confidence": scored[0][0] if scored else 0,
                    "match_type": "auto",
                })
                no_match += 1

        # Save to DB
        _jlog("Desant correspondències a la BD…")
        # palazuelos_map vive en decisions.db (adjunta por get_connection)
        for row in rows_to_upsert:
            conn.execute("""
                INSERT INTO palazuelos_map (godes_id, palaz_id, palaz_name, confidence, match_type, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(godes_id) DO UPDATE SET
                    palaz_id=excluded.palaz_id,
                    palaz_name=excluded.palaz_name,
                    confidence=excluded.confidence,
                    match_type=excluded.match_type,
                    updated_at=excluded.updated_at
                WHERE palazuelos_map.match_type NOT IN ('manual', 'rejected', 'review')
            """, (row["godes_id"], row.get("palaz_id"), row.get("palaz_name"),
                  row.get("confidence", 0), row.get("match_type", "auto")))
        # Resurgidos: forzar 'rejected' → 'review' (estado propio, pegajoso; el
        # upsert protege los rechazados, por eso van con UPDATE explícito).
        for row in resurfaced_rows:
            conn.execute(
                "UPDATE palazuelos_map SET palaz_id=?, palaz_name=?, confidence=?, "
                "match_type='review', updated_at=datetime('now') WHERE godes_id=?",
                (row["palaz_id"], row["palaz_name"], row["confidence"], row["godes_id"]),
            )
        conn.commit()
        conn.close()

        elapsed = round(time.time() - t0, 1)
        result = {
            "matched_auto": matched_auto,
            "needs_review": needs_review,
            "no_match": no_match,
            "resurfaced": resurfaced,
            "total": len(godes_people),
        }
        _jlog(f"Fet en {elapsed}s — auto:{matched_auto}, revisió:{needs_review}, sense match:{no_match}, rebutjats reoberts:{resurfaced}")
        _export_map_json()
        with _job_lock:
            _job.update({"status": "done", "result": result})

    except Exception as exc:
        import traceback
        _jlog(f"ERROR: {exc}")
        _jlog(traceback.format_exc())
        with _job_lock:
            _job["status"] = "error"


# ---------------------------------------------------------------------------
# JSON backup helpers
# ---------------------------------------------------------------------------

def _export_map_json():
    """Export manual+rejected entries to data/palazuelos_map.json as a permanent backup seed."""
    if not _db_conn or not _base_dir:
        return
    try:
        rows = _db_conn.execute("""
            SELECT godes_id, palaz_id, palaz_name, confidence, match_type, transferred_at
            FROM palazuelos_map
            WHERE match_type IN ('manual', 'rejected') OR transferred_at IS NOT NULL
            ORDER BY godes_id
        """).fetchall()
        entries = [dict(r) for r in rows]
        json_path = _base_dir / "data" / "palazuelos_map.json"
        json_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass  # best-effort — never break the main operation


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class UpdateMapRequest(BaseModel):
    palaz_id: Optional[str] = None
    palaz_name: Optional[str] = None
    match_type: str = "manual"
    confidence: Optional[int] = None


class DownloadPhotoRequest(BaseModel):
    photo_rin: str
    url: str
    filename: str
    title: Optional[str] = None
    palaz_person_id: str
    godes_person_id: str
    is_document: Optional[bool] = None
    doc_type: Optional[str] = None


@router.post("/build-map")
async def build_map():
    with _job_lock:
        if _job["status"] == "running":
            raise HTTPException(409, "Ja hi ha una tasca en curs")

    ged_path = _default_ged_path()
    if not ged_path.exists():
        raise HTTPException(404, f"No s'ha trobat {ged_path}")

    db = _db()
    db_path = str(_base_dir / "data" / "godesia.db")

    t = threading.Thread(target=_run_build_map, args=(str(ged_path), db_path), daemon=True)
    t.start()
    return {"status": "started"}


def trigger_build_map() -> bool:
    """Lanza el rebuild del mapa Palazuelos en segundo plano. Idempotente: si ya
    hay una tarea en curso o no existe el .ged, no hace nada. Pensado para
    invocarlo automáticamente tras una importación GEDCOM. Devuelve True si lanzó."""
    try:
        ged_path = _default_ged_path()
        if not ged_path.exists():
            return False
        with _job_lock:
            if _job["status"] == "running":
                return False
        db_path = str(_base_dir / "data" / "godesia.db")
        threading.Thread(target=_run_build_map, args=(str(ged_path), db_path), daemon=True).start()
        return True
    except Exception:
        return False


@router.post("/export-map")
async def export_map():
    """Export manual+rejected entries to data/palazuelos_map.json."""
    _export_map_json()
    json_path = _base_dir / "data" / "palazuelos_map.json"
    count = 0
    if json_path.exists():
        import json as _json
        count = len(_json.loads(json_path.read_text(encoding="utf-8")))
    return {"ok": True, "entries": count, "path": str(json_path)}


@router.get("/build-map/status")
async def build_map_status():
    with _job_lock:
        return {
            "status": _job["status"],
            "progress": _job["progress"],
            "total": _job["total"],
            "log": list(_job["log"]),
            "result": _job["result"],
        }


@router.get("/ged-status")
async def ged_status():
    """Qué palazuelos.ged usa el servidor (para el botón de subida del admin)."""
    p = _default_ged_path()
    if not p.exists():
        return {"present": False}
    st = p.stat()
    return {"present": True, "path": str(p.relative_to(_base_dir)), "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "individuals": len(_palaz_data()["individuals"])}


@router.post("/upload-ged")
async def upload_ged(file: UploadFile = File(...)):
    """Sube palazuelos.ged al volumen persistente (sobrescribe la copia anterior)."""
    head = await file.read(64)
    if not head.lstrip(codecs.BOM_UTF8).startswith(b"0 HEAD"):
        raise HTTPException(400, "No parece un fichero GEDCOM (debe empezar por '0 HEAD')")
    dest = _volume_ged_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".ged.tmp")
    with tmp.open("wb") as out:
        out.write(head)
        while chunk := await file.read(1 << 20):
            out.write(chunk)
    tmp.replace(dest)
    _palaz_cache["data"] = None
    return await ged_status()


@router.get("/map")
async def get_map(status_filter: Optional[str] = None):
    db = _db()
    try:
        rows = db.execute("""
            SELECT pm.godes_id, pm.palaz_id, pm.palaz_name, pm.confidence, pm.match_type, pm.updated_at,
                   pm.transferred_at,
                   p.name AS godes_name, p.birth_year, p.death_year
            FROM palazuelos_map pm
            JOIN people p ON pm.godes_id = p.id
            ORDER BY
                CASE pm.match_type WHEN 'rejected' THEN 3 WHEN 'auto' THEN 1 ELSE 2 END,
                pm.confidence DESC
        """).fetchall()
    except Exception:
        return {"entries": []}

    entries = []
    for r in rows:
        d = dict(r)
        if status_filter:
            if status_filter == 'confirmed' and d['confidence'] < 80:
                continue
            elif status_filter == 'review' and (d['confidence'] >= 80 or d['match_type'] in ('manual', 'rejected')):
                continue
            elif status_filter == 'nomatch' and d['palaz_id']:
                continue
        entries.append(d)
    return {"entries": entries, "total": len(entries)}


@router.patch("/map/{godes_id}")
async def update_map(godes_id: str, body: UpdateMapRequest):
    db = _db()
    db.execute("""
        INSERT INTO palazuelos_map (godes_id, palaz_id, palaz_name, confidence, match_type, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(godes_id) DO UPDATE SET
            palaz_id=excluded.palaz_id,
            palaz_name=excluded.palaz_name,
            confidence=COALESCE(excluded.confidence, palazuelos_map.confidence),
            match_type=excluded.match_type,
            updated_at=excluded.updated_at
    """, (godes_id, body.palaz_id, body.palaz_name,
          body.confidence, body.match_type))
    db.commit()
    _export_map_json()
    return {"ok": True}


@router.get("/candidates")
async def search_candidates(q: str = "", limit: int = 15):
    """Search Palazuelos individuals by name for the manual typeahead."""
    indis = _palaz_data()["individuals"]

    q_canon = _canonicalize_person_name(q)
    results = []

    for pid, indi in indis.items():
        name = indi.get("name") or ""
        canon = _canonicalize_person_name(name)
        score = _token_jaccard(q_canon, canon) * 100
        if score > 0 or (q and q.lower() in name.lower()):
            birth_y = _ged_year((indi.get("birth") or {}).get("date") or "")
            death_y = _ged_year((indi.get("death") or {}).get("date") or "")
            results.append({
                "palaz_id": pid,
                "name": name,
                "birth_year": birth_y,
                "death_year": death_y,
                "score": round(score),
            })

    results.sort(key=lambda x: -x["score"])
    return {"candidates": results[:limit]}


# ---------------------------------------------------------------------------
# Cabina de traspaso: campos lado a lado (Godes BD vs Palazuelos GEDCOM) con
# enlaces directos a MyHeritage, para copiar/pegar entre árboles.
# ---------------------------------------------------------------------------

_MONTH_ES = {"ene": "jan", "feb": "feb", "mar": "mar", "abr": "apr", "may": "may", "jun": "jun",
             "jul": "jul", "ago": "aug", "sep": "sep", "set": "sep", "oct": "oct", "nov": "nov",
             "dic": "dec", "des": "dec", "gen": "jan", "febr": "feb", "juny": "jun", "sept": "sep", "oct": "oct", "nov": "nov", "març": "mar", "abr": "apr", "maig": "may", "ag": "aug"}


_GED_DATE_RE = re.compile(r"^(?:ABT|EST|CAL|BEF|AFT|INT|FROM|TO|BET)\b|^\d{1,2} [A-Z]{3} \d{4}$|^[A-Z]{3} \d{4}$")


def _norm_val(v) -> str:
    """Comparación laxa: espacios, mayúsculas, meses es/ca vs GEDCOM y
    modificadores GEDCOM (BEF/AFT/ABT/BET…AND) traducidos como en la BD."""
    if v is None:
        return ""
    if isinstance(v, list):
        return " | ".join(_norm_val(x) for x in v)
    t = re.sub(r"\s+", " ", str(v)).strip()
    if _GED_DATE_RE.match(t):
        from database import convert_date_to_spanish
        try:
            t = convert_date_to_spanish(t)
        except Exception:
            pass
    t = t.lower().replace(".", "")
    return " ".join(_MONTH_ES.get(w, w) for w in t.split(" "))


def _ged_place_str(d: dict) -> str:
    return (d or {}).get("place") or ""


def _palaz_family(pid: str, data: dict) -> dict:
    indis, fams = data["individuals"], data["families"]
    indi = indis.get(pid) or {}
    name = lambda x: (indis.get(x) or {}).get("name") or x
    parents, spouses, children = [], [], []
    fc = indi.get("family_child")
    if fc and fc in fams:
        parents = [name(x) for x in (fams[fc].get("husband"), fams[fc].get("wife")) if x]
    for fs in indi.get("family_spouse") or []:
        f = fams.get(fs) or {}
        other = f.get("wife") if f.get("husband") == pid else f.get("husband")
        if other:
            spouses.append(name(other))
        children += [name(c) for c in f.get("children") or []]
    return {"parents": parents, "spouses": spouses, "children": children}


def _godes_family(pid: str, db) -> dict:
    row = db.execute("SELECT father_name, mother_name FROM people WHERE id=?", (pid,)).fetchone()
    parents = [x for x in (row or ()) if x]
    spouses = [r[0] for r in db.execute("""
        SELECT p.name FROM marriages m JOIN people p
          ON p.id = CASE WHEN m.person1_id=? THEN m.person2_id ELSE m.person1_id END
        WHERE m.person1_id=? OR m.person2_id=?""", (pid, pid, pid)).fetchall()]
    children = [r[0] for r in db.execute("""
        SELECT p.name FROM children c JOIN people p ON p.id=c.child_id
        WHERE c.parent_id=? ORDER BY p.birth_year""", (pid,)).fetchall()]
    return {"parents": parents, "spouses": spouses, "children": children}


def _transfer_list(db) -> list:
    """Parejas confirmadas (manual o conf>=80) ordenadas por nombre Godes."""
    rows = db.execute("""
        SELECT pm.godes_id FROM palazuelos_map pm JOIN people p ON p.id = pm.godes_id
        WHERE pm.palaz_id IS NOT NULL AND pm.match_type != 'rejected'
          AND (pm.match_type = 'manual' OR pm.confidence >= 80)
        ORDER BY p.name""").fetchall()
    return [r[0] for r in rows]


# Cola de la Cabina: parejas confirmadas CON diferencias, aún no traspasadas ni
# descartadas en el Comparador.
# Se cachea por (mtime del GEDCOM, última modificación del mapa, nº filas).
_queue_cache = {"key": None, "ids": None}


def _transfer_queue(db, data: dict) -> list:
    dismissed = _dismissed(db)
    key = (_palaz_cache["mtime"],
           tuple(db.execute("SELECT MAX(updated_at), MAX(transferred_at), COUNT(*) FROM palazuelos_map").fetchone()),
           tuple(sorted((k, tuple(sorted(v))) for k, v in dismissed.items())))
    if _queue_cache["ids"] is not None and _queue_cache["key"] == key:
        return _queue_cache["ids"]
    ids = []
    doubles = double_pairs(db)
    for gid in _transfer_list(db):
        pm = db.execute("SELECT palaz_id, transferred_at FROM palazuelos_map WHERE godes_id=?", (gid,)).fetchone()
        if pm["transferred_at"]:
            continue
        g = db.execute("SELECT * FROM people WHERE id=?", (gid,)).fetchone()
        pz = data["individuals"].get(pm["palaz_id"])
        if not g or not pz:
            continue
        types, _ = fields_to_diff(_transfer_fields(dict(g), pz, db, gid), doubles.get(gid), pm["palaz_id"])
        # Descartada con ✕ y sin tipos de diferencia nuevos → fuera (misma regla
        # que el Comparador al re-comparar).
        if types and not (gid in dismissed and set(types) <= dismissed[gid]):
            ids.append(gid)
    _queue_cache["key"], _queue_cache["ids"] = key, ids
    return ids


def _compare_queue(db, dtype: str = "") -> list:
    """Cola de la Cabina abierta desde el Comparador: sus mismas filas (sin
    descartadas ni traspasadas) y en su mismo orden, solo las que tienen pareja
    en palazuelos_map (sin pareja, o con una pareja que ya no está en el GEDCOM
    —pair_missing—, la Cabina no puede abrirse). `dtype` = filtro
    por tipo de diferencia activo en el Comparador (p. ej. double_pair)."""
    rows = db.execute("""
        SELECT cr.db_person_id FROM compare_results cr
        JOIN palazuelos_map pm ON pm.godes_id = cr.db_person_id
        LEFT JOIN compare_dismissed cd ON cd.db_person_id = cr.db_person_id
        WHERE cd.db_person_id IS NULL AND pm.transferred_at IS NULL
          AND pm.palaz_id IS NOT NULL AND pm.match_type != 'rejected'
          AND ',' || cr.diff_types || ',' NOT LIKE '%,pair_missing,%'
          AND (? = '' OR ',' || cr.diff_types || ',' LIKE '%,' || ? || ',%')
        ORDER BY cr.match_score ASC, cr.id ASC""", (dtype, dtype)).fetchall()
    return list(dict.fromkeys(r[0] for r in rows))


def _is_upd(etype, description) -> bool:
    """Marca de «última modificación» de MyHeritage (EVEN TYPE _UPD): no es un
    dato genealógico, nunca cuenta como diferencia."""
    return (etype or "") == "_UPD" or str(description or "").startswith("_UPD")


_YEAR_RE = re.compile(r"\b(1[0-9]\d\d|20\d\d)\b")
GRAVE_YEAR_GAP = 10
# Fechas aproximadas o de rango (GEDCOM y su traducción en la BD): «BEF 1912»
# frente a «Aprox. 1898» no se contradicen → nunca cuentan como graves.
_APPROX_RE = re.compile(r"\b(abt|bef|aft|bet|from|to|est|cal|int|aprox|antes|despu[eé]s|entre|hacia|desde|hasta|ca?)\b\.?", re.I)


def _is_grave(key: str, gv, pv) -> bool:
    """Contradicción que suele indicar una pareja mal emparejada más que un dato
    a copiar: sexo opuesto, o fechas exactas separadas por GRAVE_YEAR_GAP años o más."""
    if key == "sex":
        return {str(gv).upper(), str(pv).upper()} == {"M", "F"}
    if key in ("birth_date", "death_date", "baptism_date") and gv and pv:
        if _APPROX_RE.search(str(gv)) or _APPROX_RE.search(str(pv)):
            return False
        yg = {int(y) for y in _YEAR_RE.findall(str(gv))}
        yp = {int(y) for y in _YEAR_RE.findall(str(pv))}
        return bool(yg and yp) and min(abs(a - b) for a in yg for b in yp) >= GRAVE_YEAR_GAP
    return False


# Categoría de cada campo de la Cabina en el Comparador (mismos nombres que usa
# _compute_diff, para que los descartes ✕ antiguos sigan valiendo).
_FIELD_CATEGORY = {
    "given_name": "name", "surname": "name", "nickname": "name", "sex": "sex",
    "birth_date": "dates", "baptism_date": "dates", "death_date": "dates", "death_age": "dates",
    "birth_place": "places", "baptism_place": "places", "death_place": "places", "burial": "places",
    "death_cause": "events", "events": "events", "occupations": "occupations",
    "residences": "residences", "notes": "notes",
}


def double_pairs(db) -> dict:
    """{godes_id: [otras personas Godes emparejadas con SU misma persona Palazuelos]}.
    Una persona Palazuelos solo debería corresponder a una Godes: si hay dos, una
    de las parejas está mal (o hay un duplicado en Godes) y los datos a traspasar
    pueden ser de otra persona."""
    by_palaz = {}
    for gid, pid, name, mt in db.execute("""
            SELECT pm.godes_id, pm.palaz_id, p.name, pm.match_type
            FROM palazuelos_map pm JOIN people p ON p.id = pm.godes_id
            WHERE pm.palaz_id IS NOT NULL AND pm.palaz_id != '' AND pm.match_type != 'rejected'"""):
        by_palaz.setdefault(pid, []).append({"godes_id": gid, "name": name, "match_type": mt})
    out = {}
    for group in by_palaz.values():
        if len(group) > 1:
            for g in group:
                out[g["godes_id"]] = [o for o in group if o["godes_id"] != g["godes_id"]]
    return out


def fields_to_diff(fields: list, others: list = None, palaz_id: str = ""):
    """Diferencias de la Cabina en el formato del Comparador: (diff_types, diff_details).
    Es el ÚNICO criterio para parejas de palazuelos_map, en las dos pantallas.
    `others`: entrada de double_pairs() para esta persona (pareja doble)."""
    types, details = [], {}
    if others:
        types.append("double_pair")
        details["double_pair"] = [
            f"⚠ Palazuelos {palaz_id} también está emparejada con {' '.join((o['name'] or '').split())} "
            f"({o['godes_id']}, {o['match_type']})" for o in others]
    for f in fields:
        if f["same"]:
            continue
        cat = _FIELD_CATEGORY.get(f["key"], "events")
        if f["grave"]:
            cat_list = details.setdefault("conflict", [])
            if "conflict" not in types:
                types.insert(0, "conflict")
        else:
            cat_list = details.setdefault(cat, [])
        if cat not in types:
            types.append(cat)
        pv = f["palaz"]
        if isinstance(pv, list):
            have = {_norm_val(x) for x in f["godes"]}
            pv = " | ".join(x for x in pv if _norm_val(x) not in have)
        gv = " | ".join(f["godes"]) if isinstance(f["godes"], list) else f["godes"]
        cat_list.append(f"{'⚠ ' if f['grave'] else ''}{f['label']}: Godes '{gv or '—'}' → Palazuelos '{pv}'")
    return types, details


def _dismissed(db) -> dict:
    try:
        return {r[0]: set((r[1] or "").split(","))
                for r in db.execute("SELECT db_person_id, diff_types FROM compare_dismissed")}
    except Exception:
        return {}


def _transfer_fields(g: dict, pz: dict, db, godes_id: str) -> list:
    occ_g = [r[0] for r in db.execute("SELECT title FROM occupations WHERE person_id=?", (godes_id,))]
    res_g = [" ".join(x for x in (r[0], r[1], r[2], f"({r[3]})" if r[3] else "") if x) for r in db.execute(
        "SELECT address, city, country, date FROM residences WHERE person_id=?", (godes_id,))]
    bur_g = [" ".join(x for x in (r[0], r[1], f"({r[2]})" if r[2] else "") if x) for r in db.execute(
        "SELECT place, place_detail, date FROM burial WHERE person_id=?", (godes_id,))]
    ev_g = [" ".join(x for x in (r[0], r[1], r[2], f"({r[3]})" if r[3] else "") if x) for r in db.execute(
        "SELECT type, description, place, date FROM events WHERE person_id=?", (godes_id,))
        if not _is_upd(r[0], r[1])]
    notes_g = [r[0] for r in db.execute("SELECT content FROM notes WHERE person_id=?", (godes_id,)) if r[0]]

    res_p = [" ".join(x for x in (r.get("address"), r.get("place"), f"({r['date']})" if r.get("date") else "") if x)
             for r in pz.get("residences") or []]
    bur_p = [" ".join(x for x in (b.get("place"), b.get("place_detail"), f"({b['date']})" if b.get("date") else "") if x)
             for b in pz.get("burial") or []]
    ev_p = [" ".join(x for x in (e.get("type"), e.get("description"), e.get("place"), f"({e['date']})" if e.get("date") else "") if x)
            for e in pz.get("events") or [] if not _is_upd(e.get("type"), e.get("description"))]

    spec = [
        ("given_name", "Nombre", g.get("given_name"), pz.get("given_name")),
        ("surname", "Apellidos", g.get("surname"), pz.get("surname")),
        ("nickname", "Apodo", g.get("nickname"), pz.get("nickname")),
        ("sex", "Sexo", g.get("sex"), pz.get("sex")),
        ("birth_date", "Nacimiento · fecha", g.get("birth_date"), (pz.get("birth") or {}).get("date")),
        ("birth_place", "Nacimiento · lugar", g.get("birth_place"), _ged_place_str(pz.get("birth"))),
        ("baptism_date", "Bautismo · fecha", g.get("baptism_date"), (pz.get("baptism") or {}).get("date")),
        ("baptism_place", "Bautismo · lugar", g.get("baptism_place"), _ged_place_str(pz.get("baptism"))),
        ("death_date", "Defunción · fecha", g.get("death_date"), (pz.get("death") or {}).get("date")),
        ("death_place", "Defunción · lugar", g.get("death_place"), _ged_place_str(pz.get("death"))),
        ("death_cause", "Defunción · causa", g.get("death_cause"), (pz.get("death") or {}).get("cause")),
        ("death_age", "Defunción · edad", g.get("death_age"), (pz.get("death") or {}).get("age")),
        ("burial", "Enterramiento", bur_g, bur_p),
        ("occupations", "Ocupaciones", occ_g, [o.get("title") for o in pz.get("occupations") or []]),
        ("residences", "Residencias", res_g, res_p),
        ("events", "Eventos", ev_g, ev_p),
        ("notes", "Notas", notes_g, [n for n in pz.get("notes") or [] if n]),
    ]
    # El traspaso es Palazuelos → Godes: solo cuenta como diferencia lo que
    # Palazuelos APORTA (valor que Godes no tiene o distinto). Si Palazuelos
    # está vacío no hay nada que copiar → no es diferencia.
    out = []
    for key, label, gv, pv in spec:
        gv = [x for x in gv if x] if isinstance(gv, list) else (gv or "")
        pv = [x for x in pv if x] if isinstance(pv, list) else (pv or "")
        if not gv and not pv:
            continue
        if isinstance(pv, list):
            have = {_norm_val(x) for x in (gv if isinstance(gv, list) else [gv])}
            missing = [x for x in pv if _norm_val(x) not in have]
            same = not missing
        else:
            same = (not pv) or _norm_val(gv) == _norm_val(pv)
        out.append({"key": key, "label": label, "godes": gv, "palaz": pv, "same": same,
                    "grave": (not same) and _is_grave(key, gv, pv)})
    return out


@router.get("/transfer/{godes_id}")
async def transfer_detail(godes_id: str, scope: str = "", type: str = ""):
    db = _db()
    godes_id = "@" + godes_id.strip("@") + "@"
    pm = db.execute("SELECT palaz_id, transferred_at FROM palazuelos_map WHERE godes_id=?", (godes_id,)).fetchone()
    if not pm or not pm["palaz_id"]:
        raise HTTPException(404, "Aquesta persona no té parella a Palazuelos")
    g = db.execute("SELECT * FROM people WHERE id=?", (godes_id,)).fetchone()
    if not g:
        raise HTTPException(404, "Persona Godes no trobada")
    g = dict(g)
    data = _palaz_data()
    pz = data["individuals"].get(pm["palaz_id"])
    if not pz:
        raise HTTPException(404, f"{pm['palaz_id']} no és al GEDCOM Palazuelos")

    fields = _transfer_fields(g, pz, db, godes_id)

    # Navegación por la cola (con diferencias, pendientes). Si la persona actual
    # no está en la cola (ya hecha / sin diferencias), prev/next son los vecinos
    # más cercanos por orden alfabético. Desde el Comparador (scope=compare) la
    # cola es su propia lista: si no, «Hecho y siguiente» saltaba a parejas que
    # el Comparador no cuenta y su contador no bajaba.
    ids = _compare_queue(db, type) if scope == "compare" else _transfer_queue(db, data)
    if godes_id in ids:
        pos = ids.index(godes_id)
        prev_id = ids[pos - 1] if pos > 0 else None
        next_id = ids[pos + 1] if pos < len(ids) - 1 else None
        pos_label = pos + 1
    elif scope == "compare":
        prev_id, next_id, pos_label = None, (ids[0] if ids else None), None
    else:
        all_ids = _transfer_list(db)
        here = all_ids.index(godes_id) if godes_id in all_ids else -1
        before = [i for i in ids if i in all_ids and all_ids.index(i) < here]
        after = [i for i in ids if i in all_ids and all_ids.index(i) > here]
        prev_id, next_id, pos_label = (before[-1] if before else None), (after[0] if after else None), None
    nav = {"pos": pos_label, "total": len(ids), "prev_godes_id": prev_id, "next_godes_id": next_id}
    also = [dict(o, name=" ".join((o["name"] or "").split())) for o in double_pairs(db).get(godes_id, [])]

    return {
        "godes": {"id": godes_id, "name": g.get("name"), "mh_url": _mh_person_url("mh_tree_id_godes", godes_id)},
        "palaz": {"id": pm["palaz_id"], "name": pz.get("name"), "mh_url": _mh_person_url("mh_tree_id_palazuelos", pm["palaz_id"])},
        "fields": fields,
        "family": {"godes": _godes_family(godes_id, db), "palaz": _palaz_family(pm["palaz_id"], data)},
        "nav": nav,
        "also_paired": also,
        "transferred_at": pm["transferred_at"],
    }


@router.post("/transfer/{godes_id}/done")
async def transfer_done(godes_id: str):
    db = _db()
    godes_id = "@" + godes_id.strip("@") + "@"
    db.execute("UPDATE palazuelos_map SET transferred_at=datetime('now') WHERE godes_id=?", (godes_id,))
    # La fila del Comparador para esta persona queda descartada (como su ✕):
    # ya está traspasada, no tiene que seguir contando como "con diferencias".
    for r in db.execute("SELECT diff_types FROM compare_results WHERE db_person_id=?", (godes_id,)).fetchall():
        db.execute("INSERT OR REPLACE INTO compare_dismissed (db_person_id, diff_types) VALUES (?, ?)",
                   (godes_id, r[0]))
    db.execute("DELETE FROM compare_results WHERE db_person_id=?", (godes_id,))
    db.commit()
    _export_map_json()
    return {"ok": True}


@router.post("/transfer/{godes_id}/undo")
async def transfer_undo(godes_id: str):
    db = _db()
    godes_id = "@" + godes_id.strip("@") + "@"
    db.execute("UPDATE palazuelos_map SET transferred_at=NULL WHERE godes_id=?", (godes_id,))
    db.execute("DELETE FROM compare_dismissed WHERE db_person_id=?", (godes_id,))
    db.commit()
    _export_map_json()
    return {"ok": True}


@router.get("/thumb")
async def photo_thumb(url: str):
    """Proxy a Palazuelos CDN image through the backend (CDN requires auth the browser lacks)."""
    from fastapi.responses import Response as FastResponse
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.myheritage.es/",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
        return FastResponse(content=data, media_type=ct)
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, f"CDN error {e.code}")
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/pending-photos")
async def pending_photos():
    """Return photos in Palazuelos not yet in Godes DB, for confirmed pairs."""
    db = _db()
    ged_path = _default_ged_path()
    if not ged_path.exists():
        raise HTTPException(404, "palazuelos.ged no trobat")

    # Get confirmed pairs — skip synthetic/self-referential entries like @I88888888@
    try:
        pairs = db.execute("""
            SELECT pm.godes_id, pm.palaz_id, pm.palaz_name
            FROM palazuelos_map pm
            JOIN people p ON pm.godes_id = p.id
            WHERE pm.palaz_id IS NOT NULL
              AND pm.match_type != 'rejected'
              AND pm.palaz_id != pm.godes_id
              AND pm.godes_id NOT LIKE '@I8888%'
        """).fetchall()
    except Exception:
        return {"photos": []}

    if not pairs:
        return {"photos": []}

    # Build set of known photo hashes in Godes DB
    known_rows = db.execute("SELECT filename FROM photos").fetchall()
    known_hashes: set = set()
    for (fn,) in known_rows:
        h = _extract_hash(fn or "")
        if h:
            known_hashes.add(h)

    # Build set of already-imported filenames
    already_imported: set = set()
    try:
        imp_rows = db.execute("SELECT original_filename FROM palazuelos_imports").fetchall()
        already_imported = {r[0] for r in imp_rows if r[0]}
    except Exception:
        pass

    # Build set of dismissed photo_rins
    dismissed_rins: set = set()
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS palazuelos_dismissed (
                photo_rin TEXT PRIMARY KEY,
                godes_person_id TEXT,
                dismissed_at TEXT DEFAULT (datetime('now'))
            )
        """)
        dis_rows = db.execute("SELECT photo_rin FROM palazuelos_dismissed").fetchall()
        dismissed_rins = {r[0] for r in dis_rows}
    except Exception:
        pass

    # Parse Palazuelos photos
    palaz_photos = _parse_palaz_photos(str(ged_path))

    # Detect CDN URL expiry (all URLs share the same expiry timestamp)
    cdn_expired = False
    cdn_expiry_date = None
    for person_photos in palaz_photos.values():
        for ph in person_photos:
            url = ph.get("url", "")
            m = re.search(r'e=(\d+)', url)
            if not m:
                # Try base64-decoded segment
                try:
                    import base64 as _b64
                    seg = url.split("/")[5] if url.count("/") >= 5 else ""
                    decoded = _b64.b64decode(seg + "==").decode("latin-1")
                    m = re.search(r'e=(\d+)', decoded)
                except Exception:
                    pass
            if m:
                import time as _time
                expiry_ts = int(m.group(1))
                cdn_expiry_date = datetime.fromtimestamp(expiry_ts).strftime("%Y-%m-%d")
                cdn_expired = expiry_ts < _time.time()
            break
        if cdn_expiry_date:
            break

    pending = []
    for row in pairs:
        godes_id, palaz_id, palaz_name = row[0], row[1], row[2]
        photos = palaz_photos.get(palaz_id, [])
        for photo in photos:
            fn = photo.get("filename")
            if not fn:
                continue
            if fn in already_imported:
                continue
            rin = photo.get("photo_rin", "")
            # Clave de descarte: el RIN si existe; si no, el filename (siempre
            # presente). Así también se pueden descartar fotos sin RIN.
            if (rin and rin in dismissed_rins) or (fn in dismissed_rins):
                continue
            h = _extract_hash(fn)
            if h and h in known_hashes:
                continue

            pending.append({
                "filename": fn,
                "url": photo.get("url", ""),
                "title": photo.get("title", ""),
                "photo_rin": photo.get("photo_rin", ""),
                "palaz_person_id": palaz_id,
                "palaz_person_name": palaz_name,
                "godes_person_id": godes_id,
                "is_prim": photo.get("is_prim", False),
                "is_prim_cutout": photo.get("is_prim_cutout", False),
                "is_parent_photo": photo.get("is_parent_photo", False),
            })

    # Fetch existing photos from Godes DB per confirmed person
    godes_ids = list({row[0] for row in pairs})
    existing_by_person: dict = {}
    if godes_ids:
        placeholders = ",".join("?" * len(godes_ids))
        ex_rows = db.execute(f"""
            SELECT pt.person_id, p.id, p.filename, p.title, p.is_document
            FROM photo_tags pt
            JOIN photos p ON pt.photo_id = p.id
            WHERE pt.person_id IN ({placeholders})
              AND p.is_cutout = 0
            ORDER BY pt.person_id, p.id
        """, godes_ids).fetchall()
        for er in ex_rows:
            pid = er[0]
            existing_by_person.setdefault(pid, []).append({
                "photo_id": er[1],
                "filename": er[2],
                "title": er[3],
                "is_document": bool(er[4]),
            })

    return {
        "photos": pending,
        "total": len(pending),
        "existing_by_person": existing_by_person,
        "cdn_expired": cdn_expired,
        "cdn_expiry_date": cdn_expiry_date,
    }


class DismissPhotosRequest(BaseModel):
    godes_person_id: str
    photo_rins: list


@router.post("/dismiss-photos")
async def dismiss_photos(body: DismissPhotosRequest):
    db = _db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS palazuelos_dismissed (
            photo_rin TEXT PRIMARY KEY,
            godes_person_id TEXT,
            dismissed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    for rin in body.photo_rins:
        if rin:
            db.execute(
                "INSERT OR IGNORE INTO palazuelos_dismissed (photo_rin, godes_person_id) VALUES (?, ?)",
                (rin, body.godes_person_id),
            )
    db.commit()
    return {"dismissed": len(body.photo_rins)}


@router.post("/download-photo")
async def download_photo(body: DownloadPhotoRequest):
    db = _db()
    photos_dir = _base_dir / "data" / "photos"
    dest = photos_dir / body.filename
    body.title = _fix_encoding(body.title or "") or body.title

    if dest.exists():
        status = "skipped_exists"
        raw_data = dest.read_bytes()
    else:
        # Download
        try:
            req = urllib.request.Request(body.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_data = resp.read()
            dest.write_bytes(raw_data)
            status = "downloaded"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise HTTPException(410, "URL expirada — re-exporta el GEDCOM de Palazuelos a MyHeritage")
            raise HTTPException(502, f"Error HTTP {e.code} en descarregar {body.filename}")
        except Exception as exc:
            raise HTTPException(502, f"Error de xarxa: {exc}")

    # En local, empuja la foto al volumen de Railway en segundo plano (en Railway
    # ya está). Así no hace falta correr el script de subida a mano.
    try:
        from photo_sync import push_photos_to_railway  # noqa: PLC0415
        push_photos_to_railway(photos_dir, [body.filename])
    except Exception:
        pass

    # Save human-readable copy to docs/fotos-palazuelos/
    try:
        legible_dir = _base_dir / "docs" / "fotos-palazuelos"
        legible_dir.mkdir(exist_ok=True)
        # Extract year from title (first 4-digit number)
        year_m = re.search(r'\b(1[6-9]\d{2}|20\d{2})\b', body.title or "")
        year_str = year_m.group(1) if year_m else "0000"
        # Person name: look up godes person name
        person_name = ""
        try:
            row = _db_conn.execute("SELECT name FROM people WHERE id=?", (body.godes_person_id,)).fetchone()
            if row:
                person_name = (row[0] or "").strip().replace("/", "-").replace("\\", "-")
        except Exception:
            pass
        suffix = body.filename.rsplit(".", 1)[-1].lower()
        legible_name = f"{year_str}-{person_name}.{suffix}" if person_name else f"{year_str}-{body.filename}"
        legible_dest = legible_dir / legible_name
        # Avoid clobbering if multiple photos with same year+name
        if legible_dest.exists():
            stem = legible_dest.stem
            i = 2
            while legible_dest.exists():
                legible_dest = legible_dir / f"{stem}-{i}.{suffix}"
                i += 1
        legible_dest.write_bytes(raw_data)
    except Exception:
        pass  # legible copy is best-effort, don't fail the main download

    # Infer document classification from title
    is_document = body.is_document
    doc_type = body.doc_type
    if is_document is None and body.title:
        try:
            import importlib
            sc = importlib.import_module("scripts.sync_catalog")
            is_doc_val, dt = sc.classify_document(body.title)
            is_document = bool(is_doc_val)
            doc_type = dt
        except Exception:
            is_document = False

    # Insert into photos table if not already there
    existing = db.execute("SELECT id FROM photos WHERE filename=?", (body.filename,)).fetchone()
    if existing:
        photo_id = existing[0]
    else:
        cur = db.execute("""
            INSERT INTO photos (filename, title, is_document, doc_type, doc_origin, is_cutout, is_prim_cutout)
            VALUES (?, ?, ?, ?, 'clip_pending', 0, 0)
        """, (body.filename, body.title or "", 1 if is_document else 0, doc_type))
        photo_id = cur.lastrowid
        db.commit()

    # Link to Godes person in photo_tags (if not already linked)
    tag_exists = db.execute(
        "SELECT 1 FROM photo_tags WHERE photo_id=? AND person_id=?",
        (photo_id, body.godes_person_id)
    ).fetchone()
    if not tag_exists:
        db.execute(
            "INSERT OR IGNORE INTO photo_tags (photo_id, person_id) VALUES (?, ?)",
            (photo_id, body.godes_person_id)
        )
        db.commit()

    # Auto-tag all other matched Godes persons who share this photo in the GEDCOM
    if body.photo_rin:
        try:
            ged_path = _default_ged_path()
            if ged_path.exists():
                palaz_photos = _parse_palaz_photos(str(ged_path))
                rin_index = _build_rin_index(palaz_photos)
                palaz_map = _load_palaz_map_dict(db)
                _auto_tag_all_matched(db, rin_index, palaz_map, body.photo_rin, photo_id)
        except Exception:
            pass  # best-effort, don't fail the main download

    # Log import
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS palazuelos_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palaz_photo_rin TEXT,
                original_filename TEXT,
                palaz_person_id TEXT,
                godes_person_id TEXT,
                godes_photo_id INTEGER,
                title TEXT,
                downloaded_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'downloaded'
            )
        """)
        db.execute("""
            INSERT OR IGNORE INTO palazuelos_imports
                (palaz_photo_rin, original_filename, palaz_person_id, godes_person_id, godes_photo_id, title, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (body.photo_rin, body.filename, body.palaz_person_id,
              body.godes_person_id, photo_id, body.title or "", status))
        db.commit()
    except Exception:
        pass

    return {"photo_id": photo_id, "filename": body.filename, "status": status}


@router.post("/backfill-tags")
async def backfill_photo_tags():
    """Auto-tag all Godes persons for all already-imported photos that share a GEDCOM photo_rin."""
    db = _db()
    ged_path = _default_ged_path()
    if not ged_path.exists():
        raise HTTPException(404, "palazuelos.ged no trobat")

    palaz_photos = _parse_palaz_photos(str(ged_path))
    rin_index = _build_rin_index(palaz_photos)
    palaz_map = _load_palaz_map_dict(db)

    try:
        rows = db.execute(
            "SELECT DISTINCT palaz_photo_rin, godes_photo_id FROM palazuelos_imports WHERE godes_photo_id IS NOT NULL AND palaz_photo_rin IS NOT NULL"
        ).fetchall()
    except Exception:
        return {"tagged": 0, "processed": 0}

    total_tagged = 0
    for photo_rin, photo_id in rows:
        total_tagged += _auto_tag_all_matched(db, rin_index, palaz_map, photo_rin, photo_id)

    return {"tagged": total_tagged, "processed": len(rows)}
