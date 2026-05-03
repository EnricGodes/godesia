"""Palazuelos → Godes synchronization: matching, photo discovery, download."""

import json
import re
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from admin_routes import (
    _canonicalize_person_name,
    _ged_year,
    _build_ged_index,
    _NAME_VARIANTS,
)

router = APIRouter(prefix="/api/admin/palazuelos", tags=["palazuelos"])

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


def _default_ged_path() -> Path:
    return _base_dir / "docs" / "palazuelos.ged"


# ---------------------------------------------------------------------------
# GEDCOM photo parser (gedcom_parser.py doesn't parse OBJE details)
# ---------------------------------------------------------------------------

def _extract_hash(filename: str) -> Optional[str]:
    """Extract the middle hash from filenames like '501608_5688393sa3d55ckq98h01e_R.jpg'."""
    m = re.match(r'^\d+_([a-z0-9]+)_[A-Z]+\.\w+$', filename, re.IGNORECASE)
    return m.group(1) if m else None


def _parse_palaz_photos(ged_path: str) -> dict:
    """Parse OBJE blocks per individual. Returns {palaz_id: [photo_dict, ...]}."""
    with open(ged_path, 'r', encoding='latin-1') as f:
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
# Background build-map job
# ---------------------------------------------------------------------------

_job: dict = {"status": "idle", "progress": 0, "total": 0, "log": [], "result": None}
_job_lock = threading.Lock()


def _jlog(msg: str):
    with _job_lock:
        _job["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


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

        # Load existing manual matches to preserve them
        existing_manual = {}
        try:
            ex = conn.execute(
                "SELECT godes_id, palaz_id, palaz_name, confidence, match_type FROM palazuelos_map WHERE match_type IN ('manual','rejected')"
            ).fetchall()
            for row in ex:
                existing_manual[row[0]] = dict(row)
        except Exception:
            pass

        with _job_lock:
            _job["total"] = len(godes_people)

        matched_auto = 0
        needs_review = 0
        no_match = 0
        rows_to_upsert = []

        for i, gp in enumerate(godes_people):
            with _job_lock:
                _job["progress"] = i + 1

            godes_id = gp["id"]

            # Preserve manual decisions
            if godes_id in existing_manual:
                rows_to_upsert.append(existing_manual[godes_id])
                matched_auto += 1
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS palazuelos_map (
                godes_id TEXT PRIMARY KEY,
                palaz_id TEXT,
                palaz_name TEXT,
                confidence INTEGER DEFAULT 0,
                match_type TEXT DEFAULT 'auto',
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
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
                WHERE palazuelos_map.match_type NOT IN ('manual', 'rejected')
            """, (row["godes_id"], row.get("palaz_id"), row.get("palaz_name"),
                  row.get("confidence", 0), row.get("match_type", "auto")))
        conn.commit()
        conn.close()

        elapsed = round(time.time() - t0, 1)
        result = {
            "matched_auto": matched_auto,
            "needs_review": needs_review,
            "no_match": no_match,
            "total": len(godes_people),
        }
        _jlog(f"Fet en {elapsed}s — auto:{matched_auto}, revisió:{needs_review}, sense match:{no_match}")
        with _job_lock:
            _job.update({"status": "done", "result": result})

    except Exception as exc:
        import traceback
        _jlog(f"ERROR: {exc}")
        _jlog(traceback.format_exc())
        with _job_lock:
            _job["status"] = "error"


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


@router.get("/map")
async def get_map(status_filter: Optional[str] = None):
    db = _db()
    try:
        rows = db.execute("""
            SELECT pm.godes_id, pm.palaz_id, pm.palaz_name, pm.confidence, pm.match_type, pm.updated_at,
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
    return {"ok": True}


@router.get("/candidates")
async def search_candidates(q: str = "", limit: int = 15):
    """Search Palazuelos individuals by name for the manual typeahead."""
    ged_path = _default_ged_path()
    if not ged_path.exists():
        raise HTTPException(404, "palazuelos.ged no trobat")

    from gedcom_parser import parse_gedcom
    data = parse_gedcom(str(ged_path))
    indis = data["individuals"]

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


@router.get("/pending-photos")
async def pending_photos():
    """Return photos in Palazuelos not yet in Godes DB, for confirmed pairs."""
    db = _db()
    ged_path = _default_ged_path()
    if not ged_path.exists():
        raise HTTPException(404, "palazuelos.ged no trobat")

    # Get confirmed pairs
    try:
        pairs = db.execute("""
            SELECT godes_id, palaz_id, palaz_name
            FROM palazuelos_map
            WHERE palaz_id IS NOT NULL AND match_type != 'rejected'
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

    # Parse Palazuelos photos
    palaz_photos = _parse_palaz_photos(str(ged_path))

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
            h = _extract_hash(fn)
            if h and h in known_hashes:
                continue
            # Skip cutouts (face crops) - only want full photos/documents
            if photo.get("is_cutout") and not photo.get("is_parent_photo"):
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

    return {"photos": pending, "total": len(pending)}


@router.post("/download-photo")
async def download_photo(body: DownloadPhotoRequest):
    db = _db()
    photos_dir = _base_dir / "data" / "photos"
    dest = photos_dir / body.filename

    if dest.exists():
        status = "skipped_exists"
    else:
        # Download
        try:
            req = urllib.request.Request(body.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest.write_bytes(data)
            status = "downloaded"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise HTTPException(410, "URL expirada — re-exporta el GEDCOM de Palazuelos a MyHeritage")
            raise HTTPException(502, f"Error HTTP {e.code} en descarregar {body.filename}")
        except Exception as exc:
            raise HTTPException(502, f"Error de xarxa: {exc}")

    # Infer document classification from title
    is_document = body.is_document
    doc_type = body.doc_type
    if is_document is None and body.title:
        from scripts.sync_catalog import classify_document  # type: ignore
        try:
            is_doc_val, dt = classify_document(body.title)
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
            VALUES (?, ?, ?, ?, 'palazuelos', 0, 0)
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
