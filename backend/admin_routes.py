"""Admin API routes for the Godesia management panel."""

import collections
import contextlib
import io
import json
import logging
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, Body, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin", tags=["admin"])

# doc_classifier is imported lazily inside endpoints so the server starts even
# if open_clip / torch are not yet installed.
_doc_classifier_mod = None


def _get_doc_classifier():
    global _doc_classifier_mod
    if _doc_classifier_mod is None:
        import doc_classifier as _m  # noqa: PLC0415
        _doc_classifier_mod = _m
    return _doc_classifier_mod

# Shared state — set by init_admin() called from app.py startup
_db_conn = None
_base_dir: Optional[Path] = None
_startup_time = datetime.now()


def init_admin(db_conn, base_dir: Path):
    global _db_conn, _base_dir
    _db_conn = db_conn
    _base_dir = base_dir


def _db():
    if not _db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return _db_conn


# ---------------------------------------------------------------------------
# Log ring buffer
# ---------------------------------------------------------------------------

class _RingHandler(logging.Handler):
    def __init__(self, capacity=500):
        super().__init__()
        self._buf = collections.deque(maxlen=capacity)

    def emit(self, record):
        try:
            self._buf.append({
                "level": record.levelname,
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "message": self.format(record),
            })
        except Exception:
            pass

    def get_logs(self, n=100):
        buf = list(self._buf)
        return buf[-n:] if n else buf


_ring = _RingHandler(capacity=500)


def init_log_capture():
    _ring.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    for name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging.getLogger(name).addHandler(_ring)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def admin_status():
    db = _db()
    tables = ["people", "marriages", "photos", "photo_tags", "albums",
              "suggestions", "occupations", "residences",
              "geocache", "notes", "events"]
    counts = {}
    for t in tables:
        try:
            counts[t] = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            counts[t] = 0

    last_import = None
    try:
        row = db.execute("SELECT MAX(updated_at) FROM people").fetchone()
        last_import = row[0] if row else None
    except Exception:
        pass

    ged_file = ""
    if _base_dir:
        ged_files = sorted(
            (_base_dir / "docs").glob("*.ged"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if ged_files:
            ged_file = ged_files[0].name

    uptime = int((datetime.now() - _startup_time).total_seconds())
    restart_cmd = ""
    if _base_dir:
        restart_cmd = (
            f"pkill -f 'uvicorn app:app' && sleep 1 && "
            f"cd {_base_dir}/backend && uvicorn app:app --port 8000 &"
        )

    return {
        "uptime_seconds": uptime,
        "db_row_counts": counts,
        "last_import": last_import,
        "gedcom_file": ged_file,
        "server_time": datetime.now().isoformat(),
        "restart_command": restart_cmd,
    }


@router.get("/logs")
async def admin_logs(lines: int = 100):
    return {"logs": _ring.get_logs(lines)}


# ---------------------------------------------------------------------------
# GEDCOM Import
# ---------------------------------------------------------------------------

_job = {
    "status": "idle",
    "log": [],
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_job_lock = threading.Lock()


_real_stdout = sys.stdout


def _log_job(msg: str):
    with _job_lock:
        _job["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    _real_stdout.write(msg + "\n")
    _real_stdout.flush()


class _StdoutCapture(io.TextIOBase):
    """Redirects print() output from called modules into the job log."""
    def write(self, s):
        stripped = s.rstrip()
        if stripped:
            _log_job(f"  {stripped}")
        return len(s)
    def flush(self): pass


def _fmt_dur(secs: float) -> str:
    if secs < 1: return f"{secs*1000:.0f}ms"
    return f"{secs:.1f}s"


def _run_fast_import(ged_path: str, db_path: str):
    t_start = time.time()
    try:
        backend_dir = str(Path(db_path).parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from gedcom_parser import build_family_tree_json
        from migrate_json_to_sqlite import migrate
        from database import update_all_photo_files, get_connection

        db_path_obj = Path(db_path)
        json_path = str(db_path_obj.parent.parent / "data" / "family_tree.json")
        ged_size = Path(ged_path).stat().st_size
        _log_job(f"── Importació ràpida ──")
        _log_job(f"GEDCOM: {Path(ged_path).name} ({ged_size // 1024} KB)")
        _log_job(f"DB: {db_path_obj.name}")

        # Step 1: Parse GEDCOM → JSON
        _log_job(f"")
        _log_job(f"[1/4] Parsejant GEDCOM…")
        t1 = time.time()
        with contextlib.redirect_stdout(_StdoutCapture()):
            build_family_tree_json(ged_path, json_path)
        json_size = Path(json_path).stat().st_size
        _log_job(f"  ✓ Parsejat en {_fmt_dur(time.time()-t1)} → {json_size // 1024} KB de JSON")

        # Step 2: Migrate JSON → SQLite
        _log_job(f"")
        _log_job(f"[2/4] Migrant JSON a SQLite…")
        t2 = time.time()
        with contextlib.redirect_stdout(_StdoutCapture()):
            migrate(json_path, db_path)
        _log_job(f"  ✓ Migració completada en {_fmt_dur(time.time()-t2)}")

        # Step 3: Count rows inserted
        _log_job(f"")
        _log_job(f"[3/4] Verificant dades importades…")
        fresh = get_connection(db_path)
        tables = ["people", "marriages", "photos", "photo_tags", "albums",
                  "occupations", "residences", "notes", "events"]
        for tbl in tables:
            try:
                n = fresh.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                _log_job(f"  {tbl}: {n} files")
            except Exception as e:
                _log_job(f"  {tbl}: ERROR — {e}")

        # Step 4: Sync profile photos
        _log_job(f"")
        _log_job(f"[4/4] Sincronitzant fotos de perfil…")
        t4 = time.time()
        n_photos = update_all_photo_files(fresh)
        fresh.close()
        _log_job(f"  ✓ {n_photos} fotos de perfil actualitzades en {_fmt_dur(time.time()-t4)}")

        # Re-sincronitza el mapa de Palazuelos amb els nous individus importats,
        # perquè la pestanya Palazuelos mostri els que cal revisar sense haver de
        # llançar el rebuild a mà.
        try:
            from palazuelos_routes import trigger_build_map  # noqa: PLC0415
            if trigger_build_map():
                _log_job(f"")
                _log_job(f"↻ Mapa Palazuelos: rebuild llançat en segon pla (revisa la pestanya Palazuelos)")
        except Exception as e:
            _log_job(f"  · Palazuelos: no s'ha pogut re-sincronitzar ({e})")

        total = _fmt_dur(time.time() - t_start)
        _log_job(f"")
        _log_job(f"✓ Importació completa en {total}")

        with _job_lock:
            _job["status"] = "done"
            _job["finished_at"] = datetime.now().isoformat()
    except Exception as e:
        with _job_lock:
            _job["status"] = "error"
            _job["error"] = str(e)
            _job["finished_at"] = datetime.now().isoformat()
        _log_job(f"")
        _log_job(f"✗ ERROR: {e}")
        _log_job(traceback.format_exc())


def _upload_new_photos(base_dir: Path):
    """Log photo count after GEDCOM import.

    In Railway, data/photos/ IS the volume — photos downloaded during import
    are already there. No HTTP upload needed.
    """
    photos_dir = base_dir / "data" / "photos"
    if not photos_dir.exists():
        _log_job("📷 Directori de fotos no trobat.")
        return
    count = sum(1 for p in photos_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    _log_job(f"📷 Volum de fotos: {count} fitxers.")


def _run_full_import(ged_path: str, base_dir: Path, skip_download: bool):
    import select as _select
    MAX_SECS = 600  # 10 min hard limit
    HEARTBEAT = 15  # log a line every N seconds of silence
    t_start = time.time()
    try:
        cmd = [
            "python3",
            str(base_dir / "scripts" / "sync_catalog.py"),
            "--gedcom", ged_path,
        ]
        if skip_download:
            cmd.append("--skip-download")
        _log_job(f"Executant: {' '.join(cmd)}")
        _log_job(f"Timeout màxim: {MAX_SECS // 60} minuts")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(base_dir / "backend"),
        )

        last_output_t = time.time()
        last_heartbeat_t = time.time()

        while True:
            elapsed = time.time() - t_start
            if elapsed > MAX_SECS:
                proc.kill()
                raise RuntimeError(
                    f"Timeout: sync_catalog.py no ha acabat en {MAX_SECS // 60} minuts. "
                    f"Prova el mode Ràpida."
                )

            if proc.poll() is not None:
                # Process ended — drain remaining output
                remaining = proc.stdout.read()
                for ln in remaining.splitlines():
                    if ln.strip():
                        _log_job(ln)
                break

            # Non-blocking poll — 1s select timeout so we can check elapsed / heartbeat
            ready = _select.select([proc.stdout], [], [], 1.0)[0]
            if ready:
                line = proc.stdout.readline()
                if not line:  # EOF
                    break
                stripped = line.rstrip()
                if stripped:
                    _log_job(stripped)
                last_output_t = time.time()
                last_heartbeat_t = time.time()
            else:
                # No output — emit heartbeat periodically
                silent = time.time() - last_output_t
                if time.time() - last_heartbeat_t >= HEARTBEAT:
                    _log_job(
                        f"  (processant… {int(elapsed)}s transcorreguts, "
                        f"{int(silent)}s sense output)"
                    )
                    last_heartbeat_t = time.time()

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                f"sync_catalog.py ha acabat amb codi {proc.returncode}"
            )

        with _job_lock:
            _job["status"] = "done"
            _job["finished_at"] = datetime.now().isoformat()
        _log_job(f"✓ Importació completa en {_fmt_dur(time.time() - t_start)}")
        _upload_new_photos(base_dir)
        try:
            from palazuelos_routes import trigger_build_map  # noqa: PLC0415
            if trigger_build_map():
                _log_job(f"↻ Mapa Palazuelos: rebuild llançat en segon pla (revisa la pestanya Palazuelos)")
        except Exception as e:
            _log_job(f"  · Palazuelos: no s'ha pogut re-sincronitzar ({e})")
    except Exception as e:
        with _job_lock:
            _job["status"] = "error"
            _job["error"] = str(e)
            _job["finished_at"] = datetime.now().isoformat()
        _log_job(f"✗ ERROR: {e}")
        _log_job(traceback.format_exc())


@router.post("/import/gedcom")
async def import_gedcom(
    file: Optional[UploadFile] = File(default=None),
    mode: str = Form(default="fast"),
    delete_old_photos: bool = Form(default=False),
):
    with _job_lock:
        if _job["status"] == "running":
            raise HTTPException(status_code=409, detail="Ya hay una importación en curso")
        _job.update({
            "status": "running",
            "log": [],
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "error": None,
        })

    base_dir = _base_dir
    data_dir = base_dir / "data"
    db_path = str(data_dir / "godesia.db")
    photos_dir = data_dir / "photos"

    # Determine GEDCOM source
    if file and file.filename:
        uploads_dir = data_dir / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        ged_path = str(uploads_dir / file.filename)
        content = await file.read()
        with open(ged_path, "wb") as f:
            f.write(content)
        _log_job(f"GEDCOM subido: {file.filename} ({len(content):,} bytes)")
    else:
        ged_files = sorted(
            (base_dir / "docs").glob("*.ged"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not ged_files:
            with _job_lock:
                _job.update({"status": "error", "error": "No hay GEDCOM en docs/"})
            raise HTTPException(status_code=400, detail="No hay GEDCOM en docs/")
        ged_path = str(ged_files[0])
        _log_job(f"Usando GEDCOM: {ged_files[0].name}")

    # Delete old photos if requested
    if delete_old_photos and photos_dir.exists():
        _log_job("Eliminando fotos antiguas…")
        shutil.rmtree(photos_dir)
        photos_dir.mkdir()
        _log_job("Fotos eliminadas.")

    if mode == "fast":
        t = threading.Thread(target=_run_fast_import, args=(ged_path, db_path), daemon=True)
    else:
        skip_dl = (mode != "full_with_download")
        t = threading.Thread(target=_run_full_import, args=(ged_path, base_dir, skip_dl), daemon=True)
    t.start()

    return {"status": "started", "mode": mode}


@router.get("/import/status")
async def import_status():
    with _job_lock:
        return dict(_job)


@router.delete("/import/job")
async def reset_import_job():
    with _job_lock:
        if _job["status"] == "running":
            raise HTTPException(status_code=409, detail="Importación en curso")
        _job.update({"status": "idle", "log": [], "started_at": None, "finished_at": None, "error": None})
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# GEDCOM Comparison
# ---------------------------------------------------------------------------

_cmp_job = {
    "status": "idle",
    "progress": 0,
    "total": 0,
    "log": [],
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_cmp_job_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Document Classifier job state
# ---------------------------------------------------------------------------

_clip_job = {
    "status": "idle",   # idle | running | done | error
    "progress": 0,
    "total": 0,
    "log": [],
    "auto_doc": 0,
    "auto_photo": 0,
    "pending": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_clip_job_lock = threading.Lock()


def _clip_log(msg: str):
    with _clip_job_lock:
        _clip_job["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def _run_clip_scan(db_path: Path, photos_dir: Path, limit: int, rescan_pending: bool = False):
    """Background thread: CLIP-classify unprocessed photos and update doc_origin/doc_confidence."""
    import sqlite3 as _sqlite3  # noqa: PLC0415

    dc = _get_doc_classifier()

    conn = _sqlite3.connect(str(db_path))
    conn.row_factory = _sqlite3.Row

    try:
        origin_filter = "doc_origin IS NULL OR doc_origin = 'clip_pending'" if rescan_pending else "doc_origin IS NULL"
        query = f"""
            SELECT id, filename, is_document FROM photos
            WHERE ({origin_filter})
              AND is_downloaded = 1
              AND filename NOT LIKE '%.pdf'
        """
        if limit and limit > 0:
            query += f" LIMIT {int(limit)}"
        rows = conn.execute(query).fetchall()

        with _clip_job_lock:
            _clip_job["total"] = len(rows)
            _clip_job["progress"] = 0
            _clip_job["auto_doc"] = 0
            _clip_job["auto_photo"] = 0
            _clip_job["pending"] = 0

        _clip_log(f"Iniciant classificació de {len(rows)} fotos…")

        # Warm up CLIP once before the loop
        try:
            dc._get_clip()
            _clip_log("Model CLIP carregat.")
        except ImportError:
            raise RuntimeError("open-clip-torch no instal·lat. Executa: pip install open-clip-torch")

        for i, row in enumerate(rows):
            path = str(photos_dir / row["filename"])
            score = dc.classify_image(path)

            if score is None:
                origin, is_doc = None, None
            elif score >= dc.THRESH_AUTO_DOC:
                origin, is_doc = "clip_auto", 1
            elif row["is_document"] == 1:
                # Title classifier said "document" but CLIP isn't confident → manual review.
                # Don't auto-deny; keep is_document=1 and flag for human review.
                origin, is_doc = "clip_pending", None
            elif score <= dc.THRESH_REVIEW_LOW:
                origin, is_doc = "clip_auto", 0
            else:
                origin, is_doc = "clip_pending", 0

            if origin is not None:
                conn.execute(
                    "UPDATE photos SET doc_origin=?, doc_confidence=?, is_document=COALESCE(?,is_document) WHERE id=?",
                    (origin, score, is_doc, row["id"]),
                )
                conn.execute(
                    """INSERT INTO photo_classifications (filename, is_document, doc_type, doc_origin, doc_confidence, updated_at)
                       VALUES (?, ?, NULL, ?, ?, datetime('now'))
                       ON CONFLICT(filename) DO UPDATE SET
                           is_document=excluded.is_document, doc_origin=excluded.doc_origin,
                           doc_confidence=excluded.doc_confidence, updated_at=excluded.updated_at""",
                    (row["filename"], row["is_document"] if is_doc is None else (is_doc or 0), origin, score),
                )

            with _clip_job_lock:
                _clip_job["progress"] = i + 1
                if origin == "clip_auto" and is_doc == 1:
                    _clip_job["auto_doc"] += 1
                elif origin == "clip_auto" and is_doc == 0:
                    _clip_job["auto_photo"] += 1
                elif origin == "clip_pending":
                    _clip_job["pending"] += 1

            if (i + 1) % 50 == 0:
                conn.commit()
                _clip_log(f"{i + 1}/{len(rows)} processades…")

        conn.commit()
        with _clip_job_lock:
            _clip_job["status"] = "done"
            _clip_job["finished_at"] = datetime.now().isoformat()
        auto_doc = _clip_job["auto_doc"]
        auto_photo = _clip_job["auto_photo"]
        pending = _clip_job["pending"]
        _clip_log(f"Completat. Documents auto: {auto_doc} | No-doc auto: {auto_photo} | Revisió: {pending}")

    except Exception as exc:
        conn.rollback()
        with _clip_job_lock:
            _clip_job["status"] = "error"
            _clip_job["error"] = str(exc)
            _clip_job["finished_at"] = datetime.now().isoformat()
        _clip_log(f"ERROR: {exc}")
    finally:
        conn.close()


def _cmp_log(msg: str):
    with _cmp_job_lock:
        _cmp_job["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def _normalize_name(text: str) -> str:
    """NFD + strip combining chars + lowercase + collapse spaces."""
    import unicodedata as _ud
    if not text:
        return ""
    nfd = _ud.normalize("NFD", text)
    stripped = "".join(c for c in nfd if _ud.category(c) != "Mn")
    return " ".join(stripped.lower().split())


_PLACE_NOISE = frozenset({
    "espana", "spain", "espagne", "espanya",
    "france", "franca", "francia",
    "italia", "italy",
    "alemania", "germany", "deutschland",
    "portugal", "mexico", "argentina",
    "s", "sp", "span",   # truncated "Spain" / "España"
})


def _place_components(place: str) -> list:
    """Split a place string into significant normalized components (comma or parens)."""
    import re as _re
    parts = _re.split(r"[,()]", place)
    result = []
    for p in parts:
        t = _normalize_name(p).strip()
        if t and t not in _PLACE_NOISE and len(t) > 1:
            result.append(t)
    return result


def _places_match(a: str, b: str) -> bool:
    """Lenient place equality.
      'Murcia'                  ~ 'Murcia, España'                ← prefix
      'Murcia'                  ~ 'Región de Murcia, España'      ← suffix of 1st component
      'Benabarre (Huesca)'      ~ 'Benabarre, Huesca, Aragón, …'  ← multi-component subset
      'San Antolín, Murcia, ES' ~ 'Murcia, San Antolín, …'       ← token-set equality
    Does NOT match 'Barcelona' ~ 'Badalona, Barcelona, España'.
    """
    if not a or not b:
        return False
    na = _normalize_name(a)
    nb = _normalize_name(b)
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)

    # Case 1: shorter is a prefix of longer (comma/space separator)
    if longer.startswith(shorter) and (
        len(longer) == len(shorter) or longer[len(shorter)] in ", "
    ):
        return True

    # Case 2: shorter is a word-boundary suffix of the FIRST comma component
    # e.g. "murcia" ~ "region de murcia, espana"
    first = longer.split(",")[0].strip()
    s = shorter
    if first.endswith(s) and (len(first) == len(s) or first[-(len(s) + 1)] == " "):
        return True

    # Case 3: multi-component subset matching (both sides have ≥2 components)
    # e.g. "benabarre (huesca)" ~ "benabarre, huesca, aragon, espana"
    # e.g. "san antolin, murcia, es" ~ "murcia, san antolin, murcia, span"
    comps_a = _place_components(a)
    comps_b = _place_components(b)
    if len(comps_a) >= 2 and len(comps_b) >= 2:
        set_a, set_b = set(comps_a), set(comps_b)
        short_s = set_a if len(set_a) <= len(set_b) else set_b
        long_s  = set_a if len(set_a) >  len(set_b) else set_b
        if short_s and short_s.issubset(long_s):
            return True

    return False


def _strip_nickname(text: str) -> str:
    """Remove quoted and parenthetical nicknames from a given name.
    'Dolores "Lolita"' → 'Dolores', 'Josep (Pepe)' → 'Josep'."""
    import re
    if not text:
        return text
    # Remove "..." and (...)
    text = re.sub(r'"[^"]*"', '', text)
    text = re.sub(r'\([^)]*\)', '', text)
    return " ".join(text.split())


_NAME_VARIANT_PAIRS = [
    ("joan", "juan"), ("joana", "juana"),
    ("anna", "ana"),
    ("pere", "pedro"),
    ("jordi", "jorge"),
    ("carme", "carmen"),
    ("josep", "jose"), ("josepa", "josefa"),
    ("francesc", "francisco"), ("francesca", "francisca"),
    ("antoni", "antonio"), ("antonia", "antonia"),
    ("miquel", "miguel"),
    ("lluis", "luis"), ("lluisa", "luisa"),
    ("joaquim", "joaquin"), ("joaquima", "joaquina"),
    ("merce", "mercedes"),
    ("concepcio", "concepcion"),
    ("dolors", "dolores"),
    ("cristofol", "cristobal"),
    ("esteve", "esteban"),
    ("vicens", "vicente"),
    ("bernat", "bernardo"),
    ("narcis", "narciso"),
    ("isidre", "isidro"),
    ("marti", "martin"),
    ("domenec", "domingo"),
    ("agusti", "agustin"),
    ("rafel", "rafael"),
    ("jaume", "jaime"),
    ("guillem", "guillermo"),
    ("felip", "felipe"),
    ("ferran", "fernando"),
    ("llorenc", "lorenzo"),
    ("blai", "blas"),
    ("raimon", "raimundo"),
    ("enric", "enrique"),
    ("salvador", "salvador"),
    ("magdalena", "magdalena"),
    ("teresa", "teresa"),
    ("artur", "arturo"),
    ("elisabet", "elisabeth"),
    ("ester", "esther"),
    ("alex", "alexandre"),
    ("pau", "pablo"),
    ("ernest", "ernesto"),
    ("ignacia", "ignasia"),
]
_NAME_DIMINUTIVES = {
    "pep": "josep", "pepe": "josep",
    "paco": "francesc", "cisco": "francesc", "kiko": "francesc", "fco": "francesc",
    "toni": "antoni", "tonet": "antoni",
    "quim": "joaquim",
    "montse": "montserrat",
    "tere": "teresa",
    "lola": "dolors", "lolita": "dolors",
    "concha": "concepcio", "conxita": "concepcio",
    "lluiseta": "lluis",
    "ma": "maria", "m": "maria",
    "mª": "maria",
    "nacho": "ignacio",
    "nacha": "ignacia",
    "alejandro": "alex",
    "vicenc": "vicens",
}
_NAME_VARIANTS: dict = {}
for _a, _b in _NAME_VARIANT_PAIRS:
    _NAME_VARIANTS[_a] = _a
    _NAME_VARIANTS[_b] = _a
_NAME_VARIANTS.update(_NAME_DIMINUTIVES)

_NAME_STOPWORDS = {"i", "y", "de", "del", "la", "el", "les", "los", "da", "do"}


def _canonicalize_person_name(text: str) -> str:
    """Canonical form for matching: strip nicknames → NFD/lowercase → drop
    connectors (i/y/de/…) → drop 1-char tokens → map Catalan↔Spanish variants."""
    if not text:
        return ""
    raw = _strip_nickname(text)
    base = _normalize_name(raw)
    if not base:
        return ""
    out_tokens = []
    for tok in base.split():
        if len(tok) <= 1:
            continue
        if tok in _NAME_STOPWORDS:
            continue
        out_tokens.append(_NAME_VARIANTS.get(tok, tok))
    if not out_tokens:
        return ""
    return " ".join(out_tokens)


def _ged_year(date_str: str) -> Optional[int]:
    """Extract 4-digit year from a raw GEDCOM date string like '15 APR 1824'."""
    if not date_str:
        return None
    for part in reversed(date_str.strip().split()):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def _ged_has_full_date(date_str: str) -> bool:
    """True if the GEDCOM date has day + month + year (3 tokens, ignoring ABT/BEF/etc.)."""
    if not date_str:
        return False
    s = date_str.strip()
    for prefix in ("ABT", "BEF", "AFT", "EST", "CAL", "FROM", "TO", "BET"):
        if s.upper().startswith(prefix):
            s = s[len(prefix):].strip()
    return len(s.split()) == 3


def _compute_diff(db_person: dict, db_notes: list, db_occs: list, db_res: list,
                  db_burials: list, db_events: list, ged: dict) -> tuple:
    """Compare one DB person against one GEDCOM individual.
    Returns (diff_types_list, diff_details_dict)."""
    diff_types = []
    details = {}

    # ── Dates ─────────────────────────────────────────────────────────────
    date_diffs = []
    db_birth_year = db_person.get("birth_year")
    db_birth_date = (db_person.get("birth_date") or "").strip()
    ged_birth = ged.get("birth") or {}
    ged_birth_date = (ged_birth.get("date") or "").strip()
    db_birth_is_year_only = bool(db_birth_year) and (
        not db_birth_date or db_birth_date == str(db_birth_year)
    )
    if db_birth_is_year_only and _ged_has_full_date(ged_birth_date):
        date_diffs.append(f"Naixement: BD té '{db_birth_date or db_birth_year}', GEDCOM té '{ged_birth_date}'")

    db_death_year = db_person.get("death_year")
    db_death_date = (db_person.get("death_date") or "").strip()
    ged_death = ged.get("death") or {}
    ged_death_date = (ged_death.get("date") or "").strip()
    db_death_is_year_only = bool(db_death_year) and (
        not db_death_date or db_death_date == str(db_death_year)
    )
    if db_death_is_year_only and _ged_has_full_date(ged_death_date):
        date_diffs.append(f"Defunció: BD té '{db_death_date or db_death_year}', GEDCOM té '{ged_death_date}'")

    # ── Baptism date ──────────────────────────────────────────────────────
    ged_bapt = ged.get("baptism") or {}
    ged_bapt_date = (ged_bapt.get("date") or "").strip()
    db_bapt_date  = (db_person.get("baptism_date") or "").strip()
    if ged_bapt_date and not db_bapt_date:
        date_diffs.append(f"Baptisme: BD no té data, GEDCOM té '{ged_bapt_date}'")
    elif ged_bapt_date and db_bapt_date and _ged_has_full_date(ged_bapt_date) and not _ged_has_full_date(db_bapt_date):
        date_diffs.append(f"Baptisme: BD té '{db_bapt_date}', GEDCOM té '{ged_bapt_date}'")

    # ── Burial date ───────────────────────────────────────────────────────
    ged_burials = ged.get("burial") or []
    if isinstance(ged_burials, dict):
        ged_burials = [ged_burials]
    if ged_burials and not db_burials:
        for gb in ged_burials:
            gb_date = (gb.get("date") or "").strip()
            gb_place = (gb.get("place") or gb.get("place_detail") or "").strip()
            if gb_date or gb_place:
                date_diffs.append(f"Enterrament: BD no té dades, GEDCOM té '{(gb_date + ' ' + gb_place).strip()}'")

    if date_diffs:
        diff_types.append("dates")
        details["dates"] = date_diffs

    # ── Places ────────────────────────────────────────────────────────────
    place_diffs = []
    db_bp = (db_person.get("birth_place") or "").strip()
    ged_bp = (ged_birth.get("place") or "").strip()
    if ged_bp and (not db_bp or (not _places_match(ged_bp, db_bp) and len(ged_bp) > len(db_bp))):
        place_diffs.append(f"Lloc neix.: BD '{db_bp or '—'}' → GEDCOM '{ged_bp}'")

    db_dp = (db_person.get("death_place") or "").strip()
    ged_dp = (ged_death.get("place") or "").strip()
    if ged_dp and (not db_dp or (not _places_match(ged_dp, db_dp) and len(ged_dp) > len(db_dp))):
        place_diffs.append(f"Lloc def.: BD '{db_dp or '—'}' → GEDCOM '{ged_dp}'")

    ged_bapt_place = (ged_bapt.get("place") or "").strip()
    db_bapt_place  = (db_person.get("baptism_place") or "").strip()
    if ged_bapt_place and (not db_bapt_place or (not _places_match(ged_bapt_place, db_bapt_place) and len(ged_bapt_place) > len(db_bapt_place))):
        place_diffs.append(f"Lloc baptisme: BD '{db_bapt_place or '—'}' → GEDCOM '{ged_bapt_place}'")

    if ged_burials and not db_burials:
        for gb in ged_burials:
            gb_place = (gb.get("place") or gb.get("place_detail") or "").strip()
            if gb_place:
                place_diffs.append(f"Lloc enterrament: BD no té, GEDCOM té '{gb_place}'")
    elif ged_burials and db_burials:
        db_bur_places = {_normalize_name(b.get("place") or "") for b in db_burials}
        for gb in ged_burials:
            gb_place = _normalize_name(gb.get("place") or gb.get("place_detail") or "")
            if gb_place and gb_place not in db_bur_places:
                place_diffs.append(f"Lloc enterrament nou al GEDCOM: '{gb.get('place') or gb.get('place_detail')}'")

    if place_diffs:
        diff_types.append("places")
        details["places"] = place_diffs

    # ── Events ────────────────────────────────────────────────────────────
    ged_events = ged.get("events") or []
    # Build a set of (tag, type, description) already in DB to detect new events
    db_events_keys = {
        (e.get("tag", ""), _normalize_name(e.get("type") or e.get("description") or ""))
        for e in db_events
    }
    new_ged_events = []
    for ge in ged_events:
        if ge.get("type") == "_UPD":  # last-update timestamp — not genealogically relevant
            continue
        key = (ge.get("tag", ""), _normalize_name(ge.get("type") or ge.get("description") or ""))
        if key not in db_events_keys:
            label = ge.get("type") or ge.get("tag") or "Esdeveniment"
            parts = [label]
            if ge.get("date"):
                parts.append(ge["date"])
            if ge.get("place"):
                parts.append(ge["place"])
            if ge.get("description") and ge.get("description") != label:
                parts.append(ge["description"])
            new_ged_events.append(": ".join(parts))
    if new_ged_events:
        diff_types.append("events")
        details["events"] = new_ged_events

    # ── Death cause ───────────────────────────────────────────────────────
    ged_death_cause = (ged_death.get("cause") or "").strip()
    db_death_cause  = (db_person.get("death_cause") or "").strip()
    if ged_death_cause and not db_death_cause:
        if "events" not in diff_types:
            diff_types.append("events")
            details["events"] = []
        details.setdefault("events", []).append(f"Causa defunció al GEDCOM: '{ged_death_cause}'")

    # ── Notes ─────────────────────────────────────────────────────────────
    ged_notes = ged.get("notes") or []
    db_notes_set = {n.strip()[:120] for n in db_notes}
    new_notes = [n for n in ged_notes if n.strip()[:120] not in db_notes_set]
    if new_notes:
        diff_types.append("notes")
        details["notes"] = [f"Nova nota: {n[:300]}" for n in new_notes]

    # ── Occupations ───────────────────────────────────────────────────────
    ged_occs = ged.get("occupations") or []
    db_occ_titles = {_normalize_name(o.get("title") or "") for o in db_occs}
    new_occs = [o for o in ged_occs if _normalize_name(o.get("title") or "") not in db_occ_titles]
    if new_occs:
        diff_types.append("occupations")
        details["occupations"] = [
            f"Ocupació: {o.get('title', '')} ({o.get('date', '')} {o.get('place', '')})".strip()
            for o in new_occs
        ]

    # ── Residences ────────────────────────────────────────────────────────
    ged_res = ged.get("residences") or []
    db_res_keys = {
        _normalize_name(f"{r.get('city') or ''} {r.get('date') or ''}") for r in db_res
    }
    new_res = [
        r for r in ged_res
        if _normalize_name(f"{r.get('city') or ''} {r.get('date') or ''}") not in db_res_keys
    ]
    if new_res:
        diff_types.append("residences")
        details["residences"] = [
            f"Residència: {r.get('address', '')} {r.get('city', '')} ({r.get('date', '')})".strip()
            for r in new_res
        ]

    # ── Photos ────────────────────────────────────────────────────────────
    ged_photos = [p for p in (ged.get("photos") or []) if p.get("url")]
    if ged_photos:
        diff_types.append("photos")
        details["photos"] = [
            f"Foto al GEDCOM: {p.get('title') or p.get('url', '')}"
            for p in ged_photos[:5]
        ]

    # ── Name differences ──────────────────────────────────────────────────
    name_diffs = []
    db_given   = _normalize_name(db_person.get("given_name") or "")
    ged_given  = _normalize_name(ged.get("given_name") or "")
    db_surname = _normalize_name(db_person.get("surname") or "")
    ged_surname= _normalize_name(ged.get("surname") or "")
    db_nick    = _normalize_name(db_person.get("nickname") or "")
    ged_nick   = _normalize_name(ged.get("nickname") or "")

    if db_given and ged_given and db_given != ged_given:
        name_diffs.append(f"Nom: BD '{db_person.get('given_name')}' vs GEDCOM '{ged.get('given_name')}'")
    if db_surname and ged_surname and db_surname != ged_surname:
        name_diffs.append(f"Cognom: BD '{db_person.get('surname')}' vs GEDCOM '{ged.get('surname')}'")
    if ged_nick and not db_nick:
        name_diffs.append(f"Malnom al GEDCOM: '{ged.get('nickname')}'")

    if name_diffs:
        diff_types.append("name")
        details["name"] = name_diffs

    return diff_types, details


def _maria_suffix(canon_given: str) -> str:
    """If a canonical given name starts with 'maria ' (compound female name),
    return the rest. E.g. 'maria carmen' → 'carmen'. Otherwise empty string."""
    if canon_given.startswith("maria "):
        return canon_given[len("maria "):]
    return ""


def _build_ged_index(individuals: dict) -> dict:
    """Build canonical name → [ged_id, ...] lookup from all GEDCOM individuals."""
    index: dict = {}
    for ged_id, indi in individuals.items():
        candidates = set()
        given   = indi.get("given_name") or ""
        surname = indi.get("surname") or ""
        full    = indi.get("name") or ""

        canon_given   = _canonicalize_person_name(given)
        canon_surname = _canonicalize_person_name(surname)
        canon_full    = _canonicalize_person_name(full)
        if canon_full:
            candidates.add(canon_full)
        if canon_given and canon_surname:
            candidates.add(f"{canon_given} {canon_surname}")
            candidates.add(f"{canon_surname} {canon_given}")
            given_tokens = canon_given.split()
            # Index each individual given-name token (handles "Niceto Enrique" → "Enrique")
            for tok in given_tokens:
                if tok != canon_given:
                    candidates.add(f"{tok} {canon_surname}")
                    candidates.add(f"{canon_surname} {tok}")
            # For compound "María X" names, also index without the "maría" prefix
            # so "Mª Carmen Godes" matches a DB record with just "Carmen Godes"
            suffix = _maria_suffix(canon_given)
            if suffix:
                candidates.add(f"{suffix} {canon_surname}")
                candidates.add(f"{canon_surname} {suffix}")
        # When GEDCOM has no given name (placeholder entry), also index by surname alone
        if not canon_given and canon_surname:
            candidates.add(canon_surname)
        for name in candidates:
            index.setdefault(name, []).append(ged_id)
    return index


def _match_person(db_person: dict, individuals: dict, ged_index: dict) -> tuple:
    """Find best GEDCOM match for a DB person. Returns (ged_id | None, score 0-100)."""
    db_given_canon   = _canonicalize_person_name(db_person.get("given_name") or "")
    db_surname_canon = _canonicalize_person_name(db_person.get("surname") or "")
    db_full_canon    = _canonicalize_person_name(db_person.get("name") or "")
    db_year          = db_person.get("birth_year")

    probes = [db_full_canon]
    if db_given_canon and db_surname_canon:
        probes.append(f"{db_given_canon} {db_surname_canon}")
        probes.append(f"{db_surname_canon} {db_given_canon}")
        # Probe each individual given-name token (handles "Niceto Enrique" → "Enrique")
        for tok in db_given_canon.split():
            if tok != db_given_canon:
                probes.append(f"{tok} {db_surname_canon}")
                probes.append(f"{db_surname_canon} {tok}")
        # For compound "María X" names, also probe without the "maría" prefix
        suffix = _maria_suffix(db_given_canon)
        if suffix:
            probes.append(f"{suffix} {db_surname_canon}")
            probes.append(f"{db_surname_canon} {suffix}")
    # Last-resort probe: surname alone (handles GEDCOM entries with no given name)
    if db_surname_canon:
        probes.append(db_surname_canon)

    # Loose probes: given name + FIRST surname token only. Handles a trailing
    # extra surname in the DB, e.g. "de la Cruz Ventura" (DB) vs "de la Cruz"
    # (GEDCOM). These are accepted only under strict guards below.
    loose_probes: list = []
    if db_given_canon and db_surname_canon:
        first_sur = db_surname_canon.split()[0]
        if first_sur and first_sur != db_surname_canon:
            loose_probes.append(f"{db_given_canon} {first_sur}")
            loose_probes.append(f"{first_sur} {db_given_canon}")

    candidates: set = set()
    for name in probes:
        if not name:
            continue
        for gid in ged_index.get(name, []):
            candidates.add(gid)

    loose_candidates: set = set()
    for name in loose_probes:
        for gid in ged_index.get(name, []):
            if gid not in candidates:
                loose_candidates.add(gid)

    if not candidates and not loose_candidates:
        return None, 0

    multiple = len(candidates) > 1
    best_gid, best_score = None, 0

    # Strict candidates: original scoring.
    for gid in candidates:
        ged  = individuals[gid]
        ged_year = _ged_year((ged.get("birth") or {}).get("date") or "")
        ged_full_canon = _canonicalize_person_name(ged.get("name") or "")
        canon_match = bool(ged_full_canon) and ged_full_canon == db_full_canon

        if db_year and ged_year:
            year_delta = abs(db_year - ged_year)
            if year_delta <= 2:
                score = 100 if canon_match else 92
            elif year_delta <= 5:
                score = 90 if canon_match else 80
            else:
                score = 65 if not multiple else 0
        else:
            if multiple:
                score = 78 if canon_match else 60
            else:
                score = 88 if canon_match else 75

        if score > best_score:
            best_score, best_gid = score, gid

    # Loose candidates (partial-surname): only accept with birth-year
    # corroboration (±2) AND a token-subset relationship, to avoid matching the
    # wrong namesake in the very large Palazuelos tree.
    db_tokens = set(db_full_canon.split())
    for gid in loose_candidates:
        ged = individuals[gid]
        ged_year = _ged_year((ged.get("birth") or {}).get("date") or "")
        if not (db_year and ged_year and abs(db_year - ged_year) <= 2):
            continue
        ged_full_canon = _canonicalize_person_name(ged.get("name") or "")
        ged_tokens = set(ged_full_canon.split())
        if not (db_tokens and ged_tokens and (db_tokens <= ged_tokens or ged_tokens <= db_tokens)):
            continue
        score = 85 if ged_full_canon == db_full_canon else 70
        if score > best_score:
            best_score, best_gid = score, gid

    if best_score == 0:
        return None, 0
    return best_gid, best_score


def _run_comparison(ged_path: str, db_path: str, use_palazuelos_map: bool = False):
    """Background thread: parse GEDCOM, compare with DB, save results. Never modifies people data."""
    import sys as _sys
    t_start = time.time()
    conn = None
    try:
        backend_dir = str(Path(db_path).parent)
        if backend_dir not in _sys.path:
            _sys.path.insert(0, backend_dir)

        from gedcom_parser import parse_gedcom
        from database import get_connection as _get_conn

        _cmp_log(f"Iniciant comparació: {Path(ged_path).name}"
                 + (" [mapa Palazuelos]" if use_palazuelos_map else ""))

        # 1. Parse GEDCOM (read-only, no DB touch)
        _cmp_log("[1/4] Parsejant GEDCOM…")
        data = parse_gedcom(ged_path)
        individuals = data["individuals"]
        _cmp_log(f"  {len(individuals):,} individus al GEDCOM")

        # 2. Build name index — always, so map-mode can fall back to name
        # matching for people without a usable map entry.
        _cmp_log("[2/4] Construint índex de noms…")
        ged_index = _build_ged_index(individuals)
        _cmp_log(f"  {len(ged_index):,} entrades a l'índex")
        # Fallback index: (first_surname_canon, birth_year) → [ged_id]
        ged_surname_year: dict = {}
        for gid, indi in individuals.items():
            sur = _canonicalize_person_name(indi.get("surname") or "")
            first_sur = sur.split()[0] if sur else ""
            yr = _ged_year((indi.get("birth") or {}).get("date") or "")
            if first_sur and yr:
                ged_surname_year.setdefault((first_sur, yr), []).append(gid)

        # 3. Load all DB people + pre-fetch related tables (3 queries, not N×3)
        _cmp_log("[3/4] Carregant dades de la BD…")
        conn = _get_conn(db_path)
        db_people = conn.execute(
            "SELECT id, name, given_name, surname, nickname, "
            "birth_date, birth_year, birth_place, "
            "death_date, death_year, death_place, death_cause, "
            "baptism_date, baptism_place "
            "FROM people ORDER BY birth_year"
        ).fetchall()

        all_notes: dict = {}
        for r in conn.execute("SELECT person_id, content FROM notes").fetchall():
            all_notes.setdefault(r["person_id"], []).append(r["content"])

        all_occs: dict = {}
        for r in conn.execute("SELECT person_id, title, date, place FROM occupations").fetchall():
            all_occs.setdefault(r["person_id"], []).append(dict(r))

        all_res: dict = {}
        for r in conn.execute(
            "SELECT person_id, address, city, country, date FROM residences"
        ).fetchall():
            all_res.setdefault(r["person_id"], []).append(dict(r))

        all_burials: dict = {}
        for r in conn.execute("SELECT person_id, place, place_detail, date FROM burial").fetchall():
            all_burials.setdefault(r["person_id"], []).append(dict(r))

        all_events: dict = {}
        for r in conn.execute(
            "SELECT person_id, tag, type, description, date, place FROM events"
        ).fetchall():
            all_events.setdefault(r["person_id"], []).append(dict(r))

        total = len(db_people)
        with _cmp_job_lock:
            _cmp_job["total"] = total
        _cmp_log(f"  {total} persones a la BD")

        # Load palazuelos_map if needed
        palazuelos_map_data: dict = {}
        if use_palazuelos_map:
            try:
                map_rows = conn.execute(
                    "SELECT godes_id, palaz_id, confidence, match_type FROM palazuelos_map"
                ).fetchall()
                for mr in map_rows:
                    palazuelos_map_data[mr[0]] = {
                        "palaz_id": mr[1], "confidence": mr[2], "match_type": mr[3]
                    }
                _cmp_log(f"  {len(palazuelos_map_data):,} entrades al mapa Palazuelos")
            except Exception as e:
                _cmp_log(f"  Avís: no s'ha pogut carregar el mapa ({e}), fent servir matching per nom")
                use_palazuelos_map = False

        # Ensure dismiss table exists and load current dismissals
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compare_dismissed (
                db_person_id TEXT PRIMARY KEY,
                diff_types   TEXT,
                dismissed_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        dismissed_map: dict = {}
        for dr in conn.execute(
            "SELECT db_person_id, diff_types FROM compare_dismissed"
        ).fetchall():
            dismissed_map[dr[0]] = set((dr[1] or "").split(","))

        # Clear previous results
        conn.execute("DELETE FROM compare_results")
        conn.commit()

        # 4. Compare each DB person
        _cmp_log("[4/4] Comparant persona a persona…")
        meaningful = 0
        cnt_map = cnt_name = cnt_nomatch = 0
        for i, db_row in enumerate(db_people):
            with _cmp_job_lock:
                _cmp_job["progress"] = i + 1

            db_person = dict(db_row)
            pid = db_person["id"]

            ged_id, score = None, 0
            matched_via_map = False

            if use_palazuelos_map:
                # --- Map-based matching (authoritative) ---
                palaz_entry = palazuelos_map_data.get(pid)
                if palaz_entry is not None and palaz_entry["match_type"] == "rejected":
                    # Explicitly confirmed as absent from Palazuelos → skip entirely
                    continue
                if (palaz_entry and palaz_entry.get("palaz_id")
                        and palaz_entry["palaz_id"] in individuals):
                    ged_id = palaz_entry["palaz_id"]
                    score = palaz_entry.get("confidence") or 100
                    matched_via_map = True

            # --- Name-based matching ---
            # Primary path in name-mode; fallback in map-mode for people without
            # a usable map entry (no entry, or palaz_id absent from the GEDCOM).
            if ged_id is None:
                ged_id, score = _match_person(db_person, individuals, ged_index)
                # Second pass: first surname + birth year (score=50)
                if ged_id is None and db_person.get("birth_year"):
                    db_sur0 = (_canonicalize_person_name(db_person.get("surname") or "") or "").split()
                    if db_sur0:
                        candidates2 = ged_surname_year.get((db_sur0[0], db_person["birth_year"]), [])
                        if len(candidates2) == 1:
                            ged_id, score = candidates2[0], 50

            if ged_id is None:
                diff_types = ["nomatch"]
                diff_details = {"nomatch": ["Persona no trobada al GEDCOM"]}
            elif not matched_via_map and score <= 55:
                diff_types, diff_details = _compute_diff(
                    db_person, all_notes.get(pid, []), all_occs.get(pid, []),
                    all_res.get(pid, []), all_burials.get(pid, []),
                    all_events.get(pid, []), individuals[ged_id],
                )
                if "possible_match" not in diff_types:
                    diff_types = ["possible_match"] + diff_types
                    diff_details["possible_match"] = [
                        f"Coincidència per primer cognom + any de naixement. Nom GEDCOM: '{individuals[ged_id].get('name')}'"
                    ]
            else:
                diff_types, diff_details = _compute_diff(
                    db_person,
                    all_notes.get(pid, []),
                    all_occs.get(pid, []),
                    all_res.get(pid, []),
                    all_burials.get(pid, []),
                    all_events.get(pid, []),
                    individuals[ged_id],
                )

            if ged_id is None:
                cnt_nomatch += 1
            elif matched_via_map:
                cnt_map += 1
            else:
                cnt_name += 1

            if diff_types:
                # Skip if these exact diffs (or a subset) were previously dismissed
                prev_dismissed = dismissed_map.get(pid)
                if prev_dismissed is not None:
                    new_types_set = set(diff_types)
                    if new_types_set.issubset(prev_dismissed):
                        continue  # Same or fewer diffs → still dismissed
                    # New diff types appeared → remove the dismissal so it reappears
                    conn.execute(
                        "DELETE FROM compare_dismissed WHERE db_person_id = ?", (pid,)
                    )
                    del dismissed_map[pid]

                conn.execute(
                    "INSERT INTO compare_results "
                    "(db_person_id, db_person_name, ged_person_id, ged_person_name, "
                    "match_score, diff_types, diff_details) VALUES (?,?,?,?,?,?,?)",
                    (
                        pid,
                        db_person.get("name"),
                        ged_id,
                        individuals[ged_id].get("name") if ged_id else None,
                        score,
                        ",".join(diff_types),
                        json.dumps(diff_details, ensure_ascii=False),
                    ),
                )
                meaningful += 1
                if meaningful % 100 == 0:
                    conn.commit()

        conn.commit()

        elapsed = _fmt_dur(time.time() - t_start)
        _cmp_log(f"✓ Completat: {meaningful} diferències de {total} persones en {elapsed}")
        _cmp_log(f"  Emparellament: {cnt_map} via mapa · {cnt_name} per nom · {cnt_nomatch} no trobades")

        with _cmp_job_lock:
            _cmp_job["status"] = "done"
            _cmp_job["finished_at"] = datetime.now().isoformat()
            _cmp_job["progress"] = total
            _cmp_job["match_stats"] = {
                "via_map": cnt_map, "via_name": cnt_name, "nomatch": cnt_nomatch,
            }

    except Exception as exc:
        with _cmp_job_lock:
            _cmp_job["status"] = "error"
            _cmp_job["error"] = str(exc)
            _cmp_job["finished_at"] = datetime.now().isoformat()
            _cmp_job["log"].append(f"ERROR: {exc}")
            _cmp_job["log"].append(traceback.format_exc())
    finally:
        if conn:
            conn.close()


@router.post("/compare/start-palazuelos")
async def compare_start_palazuelos():
    """Start comparison using docs/palazuelos.ged + palazuelos_map (no upload needed)."""
    with _cmp_job_lock:
        if _cmp_job["status"] == "running":
            raise HTTPException(status_code=409, detail="Comparació ja en curs")
        _cmp_job.update({
            "status": "running", "progress": 0, "total": 0,
            "log": [], "started_at": datetime.now().isoformat(),
            "finished_at": None, "error": None,
        })

    ged_path = str(_base_dir / "docs" / "palazuelos.ged")
    if not Path(ged_path).exists():
        with _cmp_job_lock:
            _cmp_job["status"] = "idle"
        raise HTTPException(404, "docs/palazuelos.ged no trobat. Exporta el GEDCOM des de MyHeritage.")

    db_path = str(_base_dir / "data" / "godesia.db")
    threading.Thread(target=_run_comparison, args=(ged_path, db_path, True), daemon=True).start()
    return {"status": "started"}


@router.post("/compare/start")
async def compare_start(file: UploadFile = File(...)):
    """Upload a GEDCOM file and launch async comparison. Read-only — never modifies DB people."""
    with _cmp_job_lock:
        if _cmp_job["status"] == "running":
            raise HTTPException(status_code=409, detail="Comparació ja en curs")
        _cmp_job.update({
            "status": "running", "progress": 0, "total": 0,
            "log": [], "started_at": datetime.now().isoformat(),
            "finished_at": None, "error": None,
        })

    uploads_dir = _base_dir / "data" / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename or "compare.ged").name
    ged_path = str(uploads_dir / safe_name)
    content = await file.read()
    with open(ged_path, "wb") as fh:
        fh.write(content)

    db_path = str(_base_dir / "data" / "godesia.db")
    threading.Thread(target=_run_comparison, args=(ged_path, db_path), daemon=True).start()
    return {"status": "started"}


@router.get("/compare/status")
async def compare_status():
    with _cmp_job_lock:
        return dict(_cmp_job)


@router.get("/compare/results")
async def compare_results_list():
    db = _db()
    try:
        rows = db.execute(
            "SELECT id, db_person_id, db_person_name, ged_person_id, ged_person_name, "
            "match_score, diff_types, diff_details, created_at "
            "FROM compare_results ORDER BY match_score ASC, id ASC"
        ).fetchall()
        last_run = db.execute("SELECT MAX(created_at) FROM compare_results").fetchone()[0]
        return {"rows": [dict(r) for r in rows], "total_count": len(rows), "last_run": last_run}
    except Exception:
        return {"rows": [], "total_count": 0, "last_run": None}


@router.delete("/compare/results/all")
async def compare_delete_all():
    db = _db()
    deleted = db.execute("SELECT COUNT(*) FROM compare_results").fetchone()[0]
    db.execute("DELETE FROM compare_results")
    db.commit()
    with _cmp_job_lock:
        _cmp_job.update({
            "status": "idle", "progress": 0, "total": 0,
            "log": [], "started_at": None, "finished_at": None, "error": None,
        })
    return {"status": "ok", "deleted": deleted}


@router.delete("/compare/result/{result_id}")
async def compare_delete_result(result_id: int):
    db = _db()
    db.execute("DELETE FROM compare_results WHERE id = ?", (result_id,))
    db.commit()
    return {"status": "ok"}


@router.post("/compare/result/{result_id}/dismiss")
async def compare_dismiss_result(result_id: int):
    """Mark a comparison result as dismissed: hides it until new diffs appear."""
    db = _db()
    row = db.execute(
        "SELECT db_person_id, diff_types FROM compare_results WHERE id = ?", (result_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Result not found")
    db.execute("""
        CREATE TABLE IF NOT EXISTS compare_dismissed (
            db_person_id TEXT PRIMARY KEY,
            diff_types   TEXT,
            dismissed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        "INSERT OR REPLACE INTO compare_dismissed (db_person_id, diff_types) VALUES (?, ?)",
        (row["db_person_id"], row["diff_types"]),
    )
    db.execute("DELETE FROM compare_results WHERE id = ?", (result_id,))
    db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

@router.get("/suggestions")
async def list_suggestions():
    db = _db()
    try:
        rows = db.execute(
            "SELECT s.id, s.name, s.email, s.type, s.person_id, "
            "p.name AS person_name, "
            "s.message, s.files_count, s.submission_dir, s.created_at, s.resolved_at "
            "FROM suggestions s "
            "LEFT JOIN people p ON s.person_id = p.id "
            "ORDER BY s.created_at DESC"
        ).fetchall()
    except Exception:
        rows = db.execute(
            "SELECT s.id, s.name, s.email, s.type, s.person_id, "
            "NULL AS person_name, "
            "s.message, s.files_count, s.submission_dir, s.created_at "
            "FROM suggestions s ORDER BY s.created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/suggestions/{suggestion_id}/files")
async def suggestion_files(suggestion_id: str):
    if ".." in suggestion_id:
        raise HTTPException(status_code=400, detail="Path inválido")
    base = _base_dir / "data" / "suggestions" / suggestion_id
    if not base.exists():
        raise HTTPException(status_code=404, detail="Submission no encontrada")
    files = []
    for f in base.iterdir():
        if f.name != "submission.json":
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "url": f"/api/admin/suggestions/{suggestion_id}/file/{f.name}",
            })
    return files


@router.get("/suggestions/{suggestion_id}/file/{filename}")
async def suggestion_file(suggestion_id: str, filename: str):
    if ".." in suggestion_id or ".." in filename:
        raise HTTPException(status_code=400, detail="Path inválido")
    path = _base_dir / "data" / "suggestions" / suggestion_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(path))


@router.post("/suggestions/{suggestion_id}/resolve")
async def resolve_suggestion(suggestion_id: str):
    db = _db()
    now = datetime.now().isoformat()
    try:
        db.execute("UPDATE suggestions SET resolved_at=? WHERE id=?", (now, suggestion_id))
        db.commit()
    except Exception:
        pass
    return {"status": "ok", "resolved_at": now}


@router.delete("/suggestions/{suggestion_id}")
async def delete_suggestion(suggestion_id: str):
    if ".." in suggestion_id:
        raise HTTPException(status_code=400, detail="Path inválido")
    db = _db()
    db.execute("DELETE FROM suggestions WHERE id=?", (suggestion_id,))
    db.commit()
    sub_dir = _base_dir / "data" / "suggestions" / suggestion_id
    if sub_dir.exists():
        shutil.rmtree(sub_dir)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Unresolved Queries
# ---------------------------------------------------------------------------

def _queries_path() -> Path:
    return _base_dir / "data" / "unresolved_queries.jsonl"


@router.get("/queries")
async def list_queries():
    path = _queries_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    result = []
    for i, line in enumerate(reversed(lines)):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            entry["index"] = len(lines) - 1 - i
            result.append(entry)
        except Exception:
            pass
    return result


class DeleteQueriesRequest(BaseModel):
    indices: list


@router.delete("/queries")
async def delete_queries(req: DeleteQueriesRequest):
    path = _queries_path()
    if not path.exists():
        return {"deleted": 0, "remaining": 0}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    to_delete = set(req.indices)
    kept = [l for i, l in enumerate(lines) if i not in to_delete and l.strip()]
    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return {"deleted": len(lines) - len(kept), "remaining": len(kept)}


@router.delete("/queries/all")
async def delete_all_queries():
    path = _queries_path()
    count = 0
    if path.exists():
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        count = len(lines)
        path.write_text("", encoding="utf-8")
    return {"deleted": count}


# ---------------------------------------------------------------------------
# Anecdotes — stored in data/anecdotas.json (permanent, survives GEDCOM imports)
# Format: [{titulo, texto, cta}, ...]
# ---------------------------------------------------------------------------

def _anecdotas_path() -> Path:
    return _base_dir / "data" / "anecdotas.json"


def _read_anecdotas() -> list:
    path = _anecdotas_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_anecdotas(data: list):
    _anecdotas_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _lang_text(value, lang="es"):
    """Texto de un campo multiidioma {es: ..., ca: ...} (o string legado)."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("es") or ""
    return value or ""


def _as_lang_dict(value):
    """Normaliza un campo del body a dict por idioma (acepta string legado)."""
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if isinstance(v, str) and v}
    return {"es": value} if value else {}


@router.get("/anecdotes")
async def list_anecdotes(search: str = ""):
    items = _read_anecdotas()
    # Assign real file indices BEFORE filtering, so DELETE/PUT target the correct row.
    indexed = [{"index": i, **a} for i, a in enumerate(items)]
    if search:
        q = search.lower()
        def _matches(a):
            for field in ("titulo", "texto"):
                value = a.get(field)
                texts = value.values() if isinstance(value, dict) else [value or ""]
                if any(q in (t or "").lower() for t in texts):
                    return True
            return False
        indexed = [a for a in indexed if _matches(a)]
    return {"items": indexed, "total": len(indexed)}


class AnecdoteBody(BaseModel):
    # Campos multiidioma: {"es": "...", "ca": "..."}. Acepta string legado.
    titulo: Union[dict, str] = {}
    texto: Union[dict, str] = {}
    cta: Union[dict, str] = {}


@router.post("/anecdotes")
async def create_anecdote(body: AnecdoteBody):
    items = _read_anecdotas()
    items.append({"titulo": _as_lang_dict(body.titulo), "texto": _as_lang_dict(body.texto),
                  "cta": _as_lang_dict(body.cta)})
    _write_anecdotas(items)
    return {"index": len(items) - 1, "status": "ok"}


@router.put("/anecdotes/{anecdote_index}")
async def update_anecdote(anecdote_index: int, body: AnecdoteBody):
    items = _read_anecdotas()
    if anecdote_index < 0 or anecdote_index >= len(items):
        raise HTTPException(status_code=404, detail="Anècdota no trobada")
    items[anecdote_index] = {"titulo": _as_lang_dict(body.titulo), "texto": _as_lang_dict(body.texto),
                             "cta": _as_lang_dict(body.cta)}
    _write_anecdotas(items)
    return {"status": "ok"}


@router.delete("/anecdotes/{anecdote_index}")
async def delete_anecdote(anecdote_index: int):
    items = _read_anecdotas()
    if anecdote_index < 0 or anecdote_index >= len(items):
        raise HTTPException(status_code=404, detail="Anècdota no trobada")
    items.pop(anecdote_index)
    _write_anecdotas(items)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Minibios
# ---------------------------------------------------------------------------

def _minibios_path() -> Path:
    return _base_dir / "data" / "minibios.json"


def _read_minibios() -> list:
    path = _minibios_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_minibios(data: list):
    _minibios_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@router.get("/minibios")
async def list_minibios():
    return {"items": _read_minibios()}


class MinibioBody(BaseModel):
    id: str
    nombre: str = ""
    # {"es": "...", "ca": "..."}; acepta bio_es/bio_ca legados
    bio: Optional[dict] = None
    bio_es: str = ""
    bio_ca: str = ""


def _minibio_bio(body: MinibioBody) -> dict:
    if body.bio is not None:
        return _as_lang_dict(body.bio)
    bio = {}
    if body.bio_es:
        bio["es"] = body.bio_es
    if body.bio_ca:
        bio["ca"] = body.bio_ca
    return bio


@router.post("/minibios")
async def create_minibio(body: MinibioBody):
    items = _read_minibios()
    if any(m["id"] == body.id for m in items):
        raise HTTPException(status_code=400, detail="ID ja existeix")
    items.append({"id": body.id, "nombre": body.nombre, "bio": _minibio_bio(body)})
    _write_minibios(items)
    return {"status": "ok"}


@router.put("/minibios/{person_id}")
async def update_minibio(person_id: str, body: MinibioBody):
    items = _read_minibios()
    for m in items:
        if m["id"] == person_id:
            m["nombre"] = body.nombre
            m["bio"] = _minibio_bio(body)
            m.pop("bio_es", None)
            m.pop("bio_ca", None)
            _write_minibios(items)
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="No trobat")


@router.delete("/minibios/{person_id}")
async def delete_minibio(person_id: str):
    items = _read_minibios()
    new_items = [m for m in items if m["id"] != person_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="No trobat")
    _write_minibios(new_items)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Server control
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    action: str


@router.post("/server/action")
async def server_action(req: ActionRequest):
    if req.action == "restart":
        cmd = (
            f"sleep 2 && pkill -f 'uvicorn app:app' && sleep 1 && "
            f"cd {str(_base_dir)}/backend && python3 -m uvicorn app:app --port 8000 "
            f"> /tmp/godesia_server.log 2>&1"
        )
        subprocess.Popen(["bash", "-c", cmd], start_new_session=True, close_fds=True)
        return {"status": "ok", "message": "Servidor reiniciant en 2 s…"}
    elif req.action == "stop":
        cmd = "sleep 2 && pkill -f 'uvicorn app:app'"
        subprocess.Popen(["bash", "-c", cmd], start_new_session=True, close_fds=True)
        return {"status": "ok", "message": "Servidor aturant-se en 2 s…"}
    else:
        raise HTTPException(status_code=400, detail="Acció no vàlida: usa restart o stop")


# ---------------------------------------------------------------------------
# Database control (SQLite)
# ---------------------------------------------------------------------------

@router.post("/db/action")
async def db_action(req: ActionRequest):
    global _db_conn
    if req.action == "checkpoint":
        try:
            _db_conn.execute("PRAGMA wal_checkpoint(FULL)")
            _db_conn.commit()
            return {"status": "ok", "message": "WAL checkpoint completat. Dades al fitxer principal."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    elif req.action == "reconnect":
        try:
            from database import get_connection  # noqa: PLC0415
            db_path = _base_dir / "data" / "godesia.db"
            _db_conn.close()
            new_conn = get_connection(str(db_path))
            _db_conn = new_conn
            import app as _app  # noqa: PLC0415
            _app.db_conn = new_conn
            return {"status": "ok", "message": "Connexió BD reiniciada. Ara es veuen tots els canvis."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    elif req.action == "vacuum":
        try:
            _db_conn.execute("VACUUM")
            return {"status": "ok", "message": "VACUUM completat. BD compactada."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Acció no vàlida: usa checkpoint, reconnect o vacuum")


@router.post("/deploy")
async def deploy_to_railway():
    """Publica los datos manuales (BD SQLite + fotos de nicho) en GitHub para que
    Railway sirva la versión actual: checkpoint WAL → git add → commit → push.

    Solo tiene sentido ejecutándose en local (el Mac, con git y credenciales). En
    Railway no hay repo con permiso de push, así que allí devolvería error de push.
    """
    if not _base_dir:
        raise HTTPException(status_code=500, detail="base_dir no inicializado")
    repo = str(_base_dir)
    steps = []

    # 1. Volcar el WAL al fichero principal para que el .db commiteado esté completo.
    try:
        _db_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        _db_conn.commit()
        steps.append("WAL checkpoint")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkpoint WAL falló: {e}")

    def git(*args, timeout=120):
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, timeout=timeout
        )

    # 2. Preparar la BD (único dato que Railway lee del repo). Las fotos de nicho
    #    están gitignored: viajan al volumen de Railway aparte (upload_photos_to_railway.py).
    add = git("add", "data/godesia.db")
    if add.returncode != 0:
        raise HTTPException(status_code=500, detail=f"git add falló: {add.stderr or add.stdout}")

    # 3. ¿Hay algo staged? Si no, no hay nada que publicar.
    if git("diff", "--cached", "--quiet").returncode == 0:
        return {"status": "nochange", "message": "No hay cambios que publicar.", "steps": steps}

    # 4. Commit.
    commit = git("commit", "-m", "cementerios: actualizar datos manuales (edición admin)")
    if commit.returncode != 0:
        raise HTTPException(status_code=500, detail=f"git commit falló: {commit.stderr or commit.stdout}")
    steps.append("commit")

    # 5. Push.
    try:
        push = git("push", "origin", "HEAD", timeout=120)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="git push agotó el tiempo (¿credenciales o red?). El commit local sí se hizo.")
    if push.returncode != 0:
        raise HTTPException(status_code=500, detail=f"git push falló: {push.stderr or push.stdout}. El commit local sí se hizo.")
    steps.append("push")

    return {
        "status": "ok",
        "message": "Publicado en GitHub ✓. Railway redesplegará en 1-2 min.",
        "steps": steps,
    }


@router.get("/deploy/status")
async def deploy_status():
    """Indica si hay datos de cementerios/BD pendientes de publicar (para el botón)."""
    if not _base_dir:
        return {"pending": False, "detail": "base_dir no inicializado"}
    repo = str(_base_dir)
    wal = _base_dir / "data" / "godesia.db-wal"
    wal_size = wal.stat().st_size if wal.exists() else 0
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/godesia.db"],
            cwd=repo, capture_output=True, text=True, timeout=30,
        )
        dirty = bool(r.stdout.strip())
    except Exception:
        dirty = False
    return {"pending": dirty or wal_size > 0, "wal_size": wal_size, "dirty": dirty}


@router.get("/db/info")
async def db_info():
    db_path = _base_dir / "data" / "godesia.db"
    wal_path = db_path.with_suffix(".db-wal")
    shm_path = db_path.with_suffix(".db-shm")
    return {
        "db_size": db_path.stat().st_size if db_path.exists() else 0,
        "wal_size": wal_path.stat().st_size if wal_path.exists() else 0,
        "shm_size": shm_path.stat().st_size if shm_path.exists() else 0,
        "db_path": str(db_path),
        "last_modified": datetime.fromtimestamp(db_path.stat().st_mtime).isoformat() if db_path.exists() else None,
    }


# ---------------------------------------------------------------------------
# Document Classifier endpoints
# ---------------------------------------------------------------------------

@router.get("/classifier/stats")
async def classifier_stats():
    db = _db()
    total = db.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    is_document = db.execute("SELECT COUNT(*) FROM photos WHERE is_document=1").fetchone()[0]

    origins = {}
    for row in db.execute(
        "SELECT COALESCE(doc_origin,'unprocessed') as o, COUNT(*) as n FROM photos GROUP BY o"
    ).fetchall():
        origins[row["o"]] = row["n"]
    pending = db.execute(
        "SELECT COUNT(*) FROM photos WHERE doc_origin IS NULL OR doc_origin='clip_pending' OR (is_document=1 AND (doc_type IS NULL OR doc_type='') AND doc_origin != 'human')"
    ).fetchone()[0]

    dc = _get_doc_classifier()
    model_exists = dc.MODEL_PATH.exists()
    clip_ok = dc.clip_available()

    return {
        "total": total,
        "is_document": is_document,
        "by_origin": origins,
        "pending_review": pending,
        "model_exists": model_exists,
        "clip_available": clip_ok,
    }


@router.get("/classifier/pending")
async def classifier_pending(limit: int = 20, offset: int = 0):
    db = _db()
    _pending_where = """
        p.doc_origin IS NULL
        OR p.doc_origin = 'clip_pending'
        OR (p.is_document = 1 AND (p.doc_type IS NULL OR p.doc_type = '') AND p.doc_origin != 'human')
    """
    total = db.execute(f"SELECT COUNT(*) FROM photos p WHERE {_pending_where}").fetchone()[0]
    rows = db.execute(
        f"""
        SELECT p.id, p.filename, p.title, p.doc_confidence, p.doc_origin, p.is_document, p.doc_type,
               GROUP_CONCAT(pe.name, ', ') as persons
        FROM photos p
        LEFT JOIN photo_tags pt ON pt.photo_id = p.id
        LEFT JOIN people pe ON pe.id = pt.person_id
        WHERE {_pending_where}
        GROUP BY p.id
        ORDER BY p.is_document DESC, ABS(COALESCE(p.doc_confidence, 0.5) - 0.5) ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return {
        "total": total,
        "items": [dict(r) for r in rows],
    }


class ReviewBody(BaseModel):
    photo_id: int
    is_document: int
    doc_type: Optional[str] = None


class BatchReviewBody(BaseModel):
    decisions: list[ReviewBody]


def _save_classification(db, photo_id: int, is_document: int, doc_type, doc_origin: str, doc_confidence=None):
    """Write to both photos and the persistent photo_classifications table."""
    row = db.execute("SELECT filename FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        return
    filename = row["filename"]
    db.execute(
        "UPDATE photos SET is_document=?, doc_type=?, doc_origin=?, doc_confidence=? WHERE id=?",
        (is_document, doc_type, doc_origin, doc_confidence, photo_id),
    )
    db.execute(
        """INSERT INTO photo_classifications (filename, is_document, doc_type, doc_origin, doc_confidence, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(filename) DO UPDATE SET
               is_document=excluded.is_document, doc_type=excluded.doc_type,
               doc_origin=excluded.doc_origin, doc_confidence=excluded.doc_confidence,
               updated_at=excluded.updated_at""",
        (filename, is_document, doc_type, doc_origin, doc_confidence),
    )


@router.post("/classifier/review")
async def classifier_review(body: ReviewBody):
    db = _db()
    _save_classification(db, body.photo_id, body.is_document, body.doc_type, "human")
    db.commit()
    return {"ok": True}


@router.post("/classifier/review/batch")
async def classifier_review_batch(body: BatchReviewBody):
    db = _db()
    for d in body.decisions:
        _save_classification(db, d.photo_id, d.is_document, d.doc_type, "human")
    db.commit()
    return {"updated": len(body.decisions)}


class ClipRunBody(BaseModel):
    limit: int = 0
    rescan_pending: bool = False


@router.post("/classifier/run-clip")
async def classifier_run_clip(body: ClipRunBody):
    with _clip_job_lock:
        if _clip_job["status"] == "running":
            raise HTTPException(status_code=409, detail="Classificació ja en curs")
        _clip_job.update({
            "status": "running",
            "progress": 0,
            "total": 0,
            "log": [],
            "auto_doc": 0,
            "auto_photo": 0,
            "pending": 0,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "error": None,
        })

    db_path = _base_dir / "data" / "godesia.db"
    photos_dir = _base_dir / "data" / "photos"
    t = threading.Thread(
        target=_run_clip_scan,
        args=(db_path, photos_dir, body.limit, body.rescan_pending),
        daemon=True,
    )
    t.start()
    return {"status": "started"}


@router.get("/classifier/status")
async def classifier_status():
    with _clip_job_lock:
        return dict(_clip_job)


@router.post("/classifier/train")
async def classifier_train():
    db = _db()
    photos_dir = _base_dir / "data" / "photos"
    dc = _get_doc_classifier()
    result = dc.train_finetuned(db, photos_dir)
    return result


@router.post("/classifier/reclassify-tags")
async def classifier_reclassify_tags():
    sys.path.insert(0, str(_base_dir / "scripts"))
    try:
        from sync_catalog import classify_document  # noqa: PLC0415
    except ImportError:
        raise HTTPException(status_code=500, detail="sync_catalog.py no trobat a scripts/")

    db = _db()
    # Re-tag photos not yet human-reviewed; also resolve clip_pending when title matches clearly
    rows = db.execute(
        "SELECT id, title FROM photos WHERE title IS NOT NULL AND title != ''"
        " AND (doc_origin IS NULL OR doc_origin = 'tag' OR doc_origin = 'clip_pending')"
    ).fetchall()
    updated = 0
    for row in rows:
        is_doc, doc_type = classify_document(row["title"])
        if is_doc:
            db.execute(
                "UPDATE photos SET is_document=1, doc_type=?, doc_origin='tag' WHERE id=?",
                (doc_type, row["id"]),
            )
            db.execute(
                """INSERT INTO photo_classifications (filename, is_document, doc_type, doc_origin, doc_confidence)
                   SELECT filename, 1, ?, 'tag', NULL FROM photos WHERE id=?
                   ON CONFLICT(filename) DO UPDATE SET
                     is_document=1, doc_type=excluded.doc_type, doc_origin='tag', updated_at=datetime('now')
                   WHERE photo_classifications.doc_origin = 'tag' OR photo_classifications.doc_origin IS NULL""",
                (doc_type, row["id"]),
            )
            updated += 1
    db.commit()
    return {"updated": updated, "total_checked": len(rows)}


# ---------------------------------------------------------------------------
# Photo volume upload utility
# ---------------------------------------------------------------------------

@router.get("/list-photos")
async def list_photos():
    """Return the set of photo filenames present on the volume (for upload diff)."""
    photos_dir = _base_dir / "data" / "photos"
    if not photos_dir.exists():
        return {"count": 0, "files": []}
    files = [p.name for p in photos_dir.iterdir()
             if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    return {"count": len(files), "files": files}


@router.post("/upload-photos")
async def upload_photos(files: list[UploadFile] = File(...)):
    """Bulk upload photos to the data/photos directory (for volume sync)."""
    photos_dir = _base_dir / "data" / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    skipped = []
    for f in files:
        dest = photos_dir / f.filename
        if dest.exists():
            skipped.append(f.filename)
        else:
            content = await f.read()
            dest.write_bytes(content)
            saved.append(f.filename)

    return {"saved": len(saved), "skipped": len(skipped), "files": saved}


# ---------------------------------------------------------------------------
# Dedup of duplicate photos (Godes ↔ Palazuelos merge artifacts)
# ---------------------------------------------------------------------------


def _delete_photo_record(db, photo_id: int, kept_filename: str, person_id: str, reason: str,
                         kept_photo_id: Optional[int] = None):
    """Remove a duplicate photo: DB rows, physical file, register in blocklist.
    If kept_photo_id is given, reparent any cutouts that pointed to photo_id and
    transfer any photo_tags from the loser to the winner (preserving tags from
    people only present on the loser's record)."""
    row = db.execute("SELECT filename, sha256 FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        return False
    filename = row["filename"]
    sha = row["sha256"]
    if kept_photo_id:
        db.execute(
            "UPDATE photos SET parent_photo_id=? WHERE parent_photo_id=?",
            (kept_photo_id, photo_id),
        )
        # Transfer tags from loser to winner (PK is (photo_id, person_id), so
        # INSERT OR IGNORE keeps the winner's existing tag for any overlap).
        db.execute(
            """INSERT OR IGNORE INTO photo_tags
                   (photo_id, person_id, is_primary, is_prim_cutout, position, source)
               SELECT ?, person_id, is_primary, is_prim_cutout, position, source
               FROM photo_tags WHERE photo_id=?""",
            (kept_photo_id, photo_id),
        )
    db.execute("DELETE FROM photo_tags WHERE photo_id=?", (photo_id,))
    db.execute("DELETE FROM photos WHERE id=?", (photo_id,))
    db.execute(
        """INSERT INTO photo_dedup_blocklist (filename, sha256, kept_filename, person_id, reason)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(filename) DO UPDATE SET
               sha256=excluded.sha256, kept_filename=excluded.kept_filename,
               person_id=excluded.person_id, reason=excluded.reason,
               decided_at=datetime('now')""",
        (filename, sha, kept_filename, person_id, reason),
    )
    fpath = _base_dir / "data" / "photos" / filename
    try:
        fpath.unlink(missing_ok=True)
    except Exception:
        pass
    return True


@router.post("/dedup/run")
async def dedup_run():
    """Run detection across all people. Auto-apply Bucket A (sha256-exact).
    Bucket B/C land in dedup_candidates for manual review."""
    try:
        from dedup_detect import detect_for_person, ensure_candidates_table  # noqa: PLC0415
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"dedup_detect import failed: {e}")

    db = _db()
    keep_pairs = set()
    for a, b in db.execute("SELECT photo_id_a, photo_id_b FROM photo_dedup_keep_pairs"):
        keep_pairs.add((min(a, b), max(a, b)))

    ensure_candidates_table(db)

    persons = [r[0] for r in db.execute("SELECT DISTINCT person_id FROM photo_tags")]
    auto_applied = 0
    pending = 0
    by_bucket = {"A": 0, "B": 0, "C": 0}

    for pid in persons:
        pairs = detect_for_person(db, pid)
        for bucket, winner, loser, ws, ls, metric in pairs:
            pair_key = (min(winner["id"], loser["id"]), max(winner["id"], loser["id"]))
            if pair_key in keep_pairs:
                continue
            by_bucket[bucket] += 1
            if bucket == "A":
                # Auto-apply byte-identical or visually-identical duplicates
                reason = "sha256_exact" if metric == "sha256_exact" else f"auto_{metric}"
                if _delete_photo_record(db, loser["id"], winner["filename"], pid,
                                        reason, kept_photo_id=winner["id"]):
                    auto_applied += 1
            else:
                db.execute("""
                    INSERT INTO dedup_candidates
                    (person_id, bucket, kept_photo_id, drop_photo_id, kept_score, drop_score, metric)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (pid, bucket, winner["id"], loser["id"], ws, ls, metric))
                pending += 1

    db.commit()

    # Re-sync profile photos in case a deleted photo was someone's avatar
    if auto_applied:
        try:
            from database import update_all_photo_files  # noqa: PLC0415
            update_all_photo_files(db)
        except Exception:
            pass

    return {
        "ok": True,
        "auto_applied_sha256": auto_applied,
        "pending_review": pending,
        "buckets": by_bucket,
    }


@router.get("/dedup/pending")
async def dedup_pending(person_id: Optional[str] = None, limit: int = 200):
    """List pending duplicate candidates for manual review."""
    db = _db()
    fields = (
        "id, filename, title, date, place, filesize, is_document, doc_type, "
        "doc_origin, photo_rin, width, height, sha256, phash, is_cutout, "
        "parent_photo_id, note, transcription"
    )
    where = "WHERE c.status='pending'"
    params: list = []
    if person_id:
        where += " AND c.person_id=?"
        params.append(person_id)
    params.append(limit)
    rows = db.execute(f"""
        SELECT c.id AS cid, c.person_id, c.bucket, c.metric, c.kept_score, c.drop_score,
               c.kept_photo_id, c.drop_photo_id
        FROM dedup_candidates c
        {where}
        ORDER BY c.bucket, c.person_id, c.id
        LIMIT ?
    """, params).fetchall()

    def photo_dict(pid):
        r = db.execute(f"SELECT {fields} FROM photos WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

    person_name = db.execute(
        "SELECT id, name FROM people"
    ).fetchall()
    name_map = {r["id"]: r["name"] for r in person_name}

    out = []
    for r in rows:
        out.append({
            "candidate_id": r["cid"],
            "person_id": r["person_id"],
            "person_name": name_map.get(r["person_id"], ""),
            "bucket": r["bucket"],
            "metric": r["metric"],
            "kept_score": r["kept_score"],
            "drop_score": r["drop_score"],
            "keep": photo_dict(r["kept_photo_id"]),
            "drop": photo_dict(r["drop_photo_id"]),
        })
    return {"pairs": out, "count": len(out)}


class DedupDecideBody(BaseModel):
    candidate_id: int
    action: str  # "confirm" | "reject" | "swap"


@router.post("/dedup/decide")
async def dedup_decide(body: DedupDecideBody):
    """Confirm a deletion, reject (keep both), or swap which one to drop."""
    db = _db()
    row = db.execute(
        "SELECT person_id, kept_photo_id, drop_photo_id, status FROM dedup_candidates WHERE id=?",
        (body.candidate_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="candidate not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"already {row['status']}")

    kept_id = row["kept_photo_id"]
    drop_id = row["drop_photo_id"]
    person_id = row["person_id"]

    if body.action == "swap":
        kept_id, drop_id = drop_id, kept_id

    if body.action in ("confirm", "swap"):
        kept_row = db.execute("SELECT filename FROM photos WHERE id=?", (kept_id,)).fetchone()
        if not kept_row:
            raise HTTPException(status_code=410, detail="kept photo no longer exists")
        ok = _delete_photo_record(db, drop_id, kept_row["filename"], person_id,
                                  "manual_review", kept_photo_id=kept_id)
        db.execute("UPDATE dedup_candidates SET status='applied' WHERE id=?", (body.candidate_id,))
        db.commit()
        # Refresh profile photos
        try:
            from database import update_all_photo_files  # noqa: PLC0415
            update_all_photo_files(db)
        except Exception:
            pass
        return {"ok": ok, "action": body.action, "deleted_photo_id": drop_id}

    elif body.action == "reject":
        a, b = min(kept_id, drop_id), max(kept_id, drop_id)
        db.execute(
            """INSERT OR IGNORE INTO photo_dedup_keep_pairs (photo_id_a, photo_id_b, person_id)
               VALUES (?, ?, ?)""",
            (a, b, person_id),
        )
        db.execute("UPDATE dedup_candidates SET status='rejected' WHERE id=?", (body.candidate_id,))
        db.commit()
        return {"ok": True, "action": "reject"}

    raise HTTPException(status_code=400, detail="invalid action")


@router.get("/dedup/stats")
async def dedup_stats():
    """Summary counts for the admin UI."""
    db = _db()
    try:
        pending = db.execute(
            "SELECT bucket, COUNT(*) FROM dedup_candidates WHERE status='pending' GROUP BY bucket"
        ).fetchall()
        blocked = db.execute("SELECT COUNT(*) FROM photo_dedup_blocklist").fetchone()[0]
        kept = db.execute("SELECT COUNT(*) FROM photo_dedup_keep_pairs").fetchone()[0]
    except Exception:
        return {"pending": {}, "blocked": 0, "kept_pairs": 0}
    return {
        "pending": {r[0]: r[1] for r in pending},
        "blocked": blocked,
        "kept_pairs": kept,
    }


# ---------------------------------------------------------------------------
# Cemeteries & niches (manual data, survives GEDCOM re-imports)
# ---------------------------------------------------------------------------


class CemeteryBody(BaseModel):
    name: str
    city: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    description: str = ""


def _cemetery_photos_dir() -> Path:
    # Las fotos de nichos viven en data/photos/ (el ÚNICO volumen persistente de
    # Railway), igual que las GEDCOM/Palazuelos. Así llegan a producción con el
    # mismo script (upload_photos_to_railway.py) y NO por git. Tienen prefijo
    # "niche_", no colisionan con las GEDCOM, y no están en la tabla `photos`.
    d = _base_dir / "data" / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


_niche_photo_seq = 0


def _save_niche_photo(db, niche_id: int, kind: str, upload: UploadFile) -> str:
    """Save an uploaded niche/registry photo optimized for the web (EXIF rotation
    baked in, max 1800px, JPEG quality 85). Registers it in niche_photos."""
    global _niche_photo_seq
    from PIL import Image, ImageOps
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {ext}")
    out_ext = ".png" if ext == ".png" else ".jpg"
    _niche_photo_seq += 1
    filename = f"niche_{niche_id}_{kind}_{int(time.time())}_{_niche_photo_seq}{out_ext}"
    dest = _cemetery_photos_dir() / filename
    raw = upload.file.read()
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)  # bake EXIF orientation into the pixels
        if max(img.size) > 1800:
            img.thumbnail((1800, 1800))
        if out_ext == ".jpg":
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dest, "JPEG", quality=85, optimize=True)
        else:
            img.save(dest, optimize=True)
    except HTTPException:
        raise
    except Exception:
        dest.write_bytes(raw)  # keep the original bytes if Pillow can't process them
    db.execute("INSERT INTO niche_photos (niche_id, filename, kind) VALUES (?, ?, ?)",
               (niche_id, filename, kind))
    # En local, empuja la foto al volumen de Railway en segundo plano.
    from photo_sync import push_photos_to_railway  # noqa: PLC0415
    push_photos_to_railway(_cemetery_photos_dir(), [filename])
    return filename


def _delete_niche_files(db, niche_id: int):
    rows = db.execute("SELECT filename FROM niche_photos WHERE niche_id = ?", (niche_id,)).fetchall()
    for r in rows:
        (_cemetery_photos_dir() / r["filename"]).unlink(missing_ok=True)
    db.execute("DELETE FROM niche_photos WHERE niche_id = ?", (niche_id,))


def _norm_person_id(person_id: str) -> str:
    return person_id if person_id.startswith("@") else f"@{person_id}@"


@router.post("/cemeteries")
async def create_cemetery(body: CemeteryBody):
    db = _db()
    cur = db.execute(
        "INSERT INTO cemeteries (name, city, lat, lng, description) VALUES (?, ?, ?, ?, ?)",
        (body.name.strip(), body.city.strip(), body.lat, body.lng, body.description.strip()),
    )
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


@router.put("/cemeteries/{cemetery_id}")
async def update_cemetery(cemetery_id: int, body: CemeteryBody):
    db = _db()
    cur = db.execute(
        "UPDATE cemeteries SET name=?, city=?, lat=?, lng=?, description=?, updated_at=datetime('now') WHERE id=?",
        (body.name.strip(), body.city.strip(), body.lat, body.lng, body.description.strip(), cemetery_id),
    )
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    return {"ok": True}


@router.delete("/cemeteries/{cemetery_id}")
async def delete_cemetery(cemetery_id: int, force: int = 0):
    db = _db()
    niche_ids = [r[0] for r in db.execute(
        "SELECT id FROM niches WHERE cemetery_id = ?", (cemetery_id,)).fetchall()]
    if niche_ids and not force:
        raise HTTPException(status_code=409, detail=f"El cementerio tiene {len(niche_ids)} nichos. Usa force=1 para borrar todo.")
    for nid in niche_ids:
        _delete_niche_files(db, nid)
        db.execute("DELETE FROM niche_people WHERE niche_id = ?", (nid,))
    db.execute("DELETE FROM niches WHERE cemetery_id = ?", (cemetery_id,))
    cur = db.execute("DELETE FROM cemeteries WHERE id = ?", (cemetery_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    return {"ok": True, "niches_deleted": len(niche_ids)}


@router.post("/cemeteries/{cemetery_id}/niches")
async def create_niche(
    cemetery_id: int,
    name: str = Form(...),
    title: str = Form(""),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    notes: str = Form(""),
    fs_url: str = Form(""),
    photos: Optional[list[UploadFile]] = File(None),
    record_photos: Optional[list[UploadFile]] = File(None),
):
    db = _db()
    if not db.execute("SELECT 1 FROM cemeteries WHERE id = ?", (cemetery_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    cur = db.execute(
        "INSERT INTO niches (cemetery_id, name, title, lat, lng, notes, fs_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cemetery_id, name.strip(), title.strip() or None, lat, lng, notes.strip(), fs_url.strip() or None),
    )
    niche_id = cur.lastrowid
    for f in (photos or []):
        if f.filename:
            _save_niche_photo(db, niche_id, "photo", f)
    for f in (record_photos or []):
        if f.filename:
            _save_niche_photo(db, niche_id, "record", f)
    db.commit()
    return {"ok": True, "id": niche_id}


@router.put("/niches/{niche_id}")
async def update_niche(
    niche_id: int,
    name: str = Form(...),
    title: str = Form(""),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    notes: str = Form(""),
    fs_url: str = Form(""),
    photos: Optional[list[UploadFile]] = File(None),
    record_photos: Optional[list[UploadFile]] = File(None),
):
    db = _db()
    row = db.execute("SELECT * FROM niches WHERE id = ?", (niche_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Nicho no encontrado")
    db.execute(
        "UPDATE niches SET name=?, title=?, lat=?, lng=?, notes=?, fs_url=?, updated_at=datetime('now') WHERE id=?",
        (name.strip(), title.strip() or None, lat, lng, notes.strip(), fs_url.strip() or None, niche_id),
    )
    for f in (photos or []):
        if f.filename:
            _save_niche_photo(db, niche_id, "photo", f)
    for f in (record_photos or []):
        if f.filename:
            _save_niche_photo(db, niche_id, "record", f)
    db.commit()
    return {"ok": True}


class NicheEnabledBody(BaseModel):
    enabled: bool


@router.patch("/niches/{niche_id}/enabled")
async def set_niche_enabled(niche_id: int, body: NicheEnabledBody):
    """Habilita/deshabilita un nicho. Deshabilitado = no se muestra en la app."""
    db = _db()
    cur = db.execute(
        "UPDATE niches SET enabled = ?, updated_at = datetime('now') WHERE id = ?",
        (1 if body.enabled else 0, niche_id),
    )
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Nicho no encontrado")
    return {"ok": True, "enabled": body.enabled}


@router.get("/cemeteries")
async def admin_cemeteries_list():
    """Como /api/cemeteries pero incluye nichos deshabilitados (para el gestor)."""
    from database import get_cemeteries_summary  # noqa: PLC0415
    return get_cemeteries_summary(_db(), include_disabled=True)


@router.get("/cemeteries/{cemetery_id}/detail")
async def admin_cemetery_detail(cemetery_id: int):
    """Detalle del cementerio con nichos deshabilitados incluidos (para el gestor)."""
    from database import get_cemetery_detail  # noqa: PLC0415
    data = get_cemetery_detail(_db(), cemetery_id, include_disabled=True)
    if not data:
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    return data


@router.delete("/niche-photos/{photo_id}")
async def delete_niche_photo(photo_id: int):
    db = _db()
    row = db.execute("SELECT filename FROM niche_photos WHERE id = ?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    (_cemetery_photos_dir() / row["filename"]).unlink(missing_ok=True)
    db.execute("DELETE FROM niche_photos WHERE id = ?", (photo_id,))
    db.commit()
    return {"ok": True}


@router.delete("/niches/{niche_id}")
async def delete_niche(niche_id: int):
    db = _db()
    _delete_niche_files(db, niche_id)
    db.execute("DELETE FROM niche_people WHERE niche_id = ?", (niche_id,))
    cur = db.execute("DELETE FROM niches WHERE id = ?", (niche_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Nicho no encontrado")
    return {"ok": True}


class NichePersonBody(BaseModel):
    person_id: str


@router.post("/niches/{niche_id}/people")
async def assign_niche_person(niche_id: int, body: NichePersonBody):
    db = _db()
    if not db.execute("SELECT 1 FROM niches WHERE id = ?", (niche_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Nicho no encontrado")
    person_id = _norm_person_id(body.person_id)
    if not db.execute("SELECT 1 FROM people WHERE id = ?", (person_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    db.execute("INSERT OR IGNORE INTO niche_people (niche_id, person_id) VALUES (?, ?)",
               (niche_id, person_id))
    db.commit()
    return {"ok": True}


@router.delete("/niches/{niche_id}/people/{person_id}")
async def remove_niche_person(niche_id: int, person_id: str):
    db = _db()
    cur = db.execute("DELETE FROM niche_people WHERE niche_id = ? AND person_id = ?",
                     (niche_id, _norm_person_id(person_id)))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    return {"ok": True}


@router.get("/cemeteries/{cemetery_id}/burial-suggestions")
async def burial_suggestions(cemetery_id: int):
    """People whose GEDCOM burial place matches this cemetery's name or city,
    excluding those already assigned to one of its niches."""
    db = _db()
    cem = db.execute("SELECT name, city FROM cemeteries WHERE id = ?", (cemetery_id,)).fetchone()
    if not cem:
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    # Match by the distinctive part of the name: the same cemetery appears in
    # burial.place as "Cementerio Poble Nou" and "Cementiri de Poble Nou".
    core = cem["name"].strip()
    core_low = core.lower()
    for prefix in ("cementiri municipal", "cementerio municipal", "cementiri", "cementerio", "cemetery"):
        if core_low.startswith(prefix):
            core = core[len(prefix):].strip()
            core_low = core.lower()
            break
    for article in ("de la ", "de les ", "de los ", "dels ", "del ", "de "):
        if core_low.startswith(article):
            core = core[len(article):].strip()
            break
    core = core or cem["name"].strip()
    rows = db.execute("""
        SELECT DISTINCT b.person_id, p.name, p.birth_year, p.death_year, p.photo_file,
               b.place, b.place_detail, b.date
        FROM burial b
        JOIN people p ON p.id = b.person_id
        WHERE REPLACE(NORMALIZE(b.place), ' ', '') LIKE '%' || REPLACE(NORMALIZE(?), ' ', '') || '%'
          AND b.person_id NOT IN (
              SELECT np.person_id FROM niche_people np
              JOIN niches n ON n.id = np.niche_id
              WHERE n.cemetery_id = ?)
        ORDER BY p.name
    """, (core, cemetery_id)).fetchall()
    return {"suggestions": [dict(r) for r in rows]}


class NicheRecordBody(BaseModel):
    name: str
    person_id: str = ""
    burial_date: str = ""
    death_day: str = ""
    civil_status: str = ""
    spouse: str = ""
    age: str = ""
    origin: str = ""
    profession: str = ""
    address: str = ""
    parish: str = ""
    court: str = ""
    titular: str = ""
    notes: str = ""
    fs_url: str = ""


def _record_person_id(db, raw: str):
    """Valida y normaliza el person_id de un registro; '' → None."""
    pid = (raw or "").strip()
    if not pid:
        return None
    pid = _norm_person_id(pid)
    if not db.execute("SELECT 1 FROM people WHERE id = ?", (pid,)).fetchone():
        raise HTTPException(status_code=404, detail=f"Persona no encontrada: {pid}")
    return pid


@router.post("/niches/{niche_id}/records")
async def create_niche_record(niche_id: int, body: NicheRecordBody):
    db = _db()
    if not db.execute("SELECT 1 FROM niches WHERE id = ?", (niche_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Nicho no encontrado")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    cur = db.execute(
        "INSERT INTO niche_records (niche_id, person_id, name, burial_date, death_day, "
        "civil_status, spouse, age, origin, profession, address, parish, court, titular, notes, fs_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (niche_id, _record_person_id(db, body.person_id), body.name.strip(),
         body.burial_date.strip(), body.death_day.strip(), body.civil_status.strip(),
         body.spouse.strip(), body.age.strip(), body.origin.strip(), body.profession.strip(),
         body.address.strip(), body.parish.strip(), body.court.strip(),
         body.titular.strip(), body.notes.strip(), body.fs_url.strip()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


@router.put("/niche-records/{record_id}")
async def update_niche_record(record_id: int, body: NicheRecordBody):
    db = _db()
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    cur = db.execute(
        "UPDATE niche_records SET person_id=?, name=?, burial_date=?, death_day=?, "
        "civil_status=?, spouse=?, age=?, origin=?, profession=?, address=?, parish=?, "
        "court=?, titular=?, notes=?, fs_url=? WHERE id=?",
        (_record_person_id(db, body.person_id), body.name.strip(),
         body.burial_date.strip(), body.death_day.strip(), body.civil_status.strip(),
         body.spouse.strip(), body.age.strip(), body.origin.strip(), body.profession.strip(),
         body.address.strip(), body.parish.strip(), body.court.strip(),
         body.titular.strip(), body.notes.strip(), body.fs_url.strip(), record_id))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"ok": True}


@router.delete("/niche-records/{record_id}")
async def delete_niche_record(record_id: int):
    db = _db()
    cur = db.execute("DELETE FROM niche_records WHERE id = ?", (record_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"ok": True}
