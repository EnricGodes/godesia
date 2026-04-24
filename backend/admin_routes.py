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
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin", tags=["admin"])

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
              "suggestions", "occupations", "residences", "anecdotes",
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


def _log_job(msg: str):
    with _job_lock:
        _job["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    print(msg)


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


def _run_full_import(ged_path: str, base_dir: Path, skip_download: bool):
    try:
        cmd = [
            "python3",
            str(base_dir / "scripts" / "sync_catalog.py"),
            "--gedcom", ged_path,
        ]
        if skip_download:
            cmd.append("--skip-download")
        _log_job(f"Ejecutando: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(base_dir / "backend"),
        )
        timeout_at = datetime.now().timestamp() + 600  # 10 min
        for line in proc.stdout:
            _log_job(line.rstrip())
            if datetime.now().timestamp() > timeout_at:
                proc.kill()
                raise RuntimeError("Timeout: sync_catalog.py tardó más de 10 minutos")
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"sync_catalog.py terminó con código {proc.returncode}")

        with _job_lock:
            _job["status"] = "done"
            _job["finished_at"] = datetime.now().isoformat()
        _log_job("✓ Importación completa finalizada.")
    except Exception as e:
        with _job_lock:
            _job["status"] = "error"
            _job["error"] = str(e)
            _job["finished_at"] = datetime.now().isoformat()
        _log_job(f"ERROR: {e}")


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


@router.get("/anecdotes")
async def list_anecdotes(search: str = ""):
    items = _read_anecdotas()
    if search:
        q = search.lower()
        items = [a for a in items if q in (a.get("titulo") or "").lower() or q in (a.get("texto") or "").lower()]
    return {"items": [{"index": i, **a} for i, a in enumerate(items)], "total": len(items)}


class AnecdoteBody(BaseModel):
    titulo: str = ""
    texto: str = ""
    cta: str = ""


@router.post("/anecdotes")
async def create_anecdote(body: AnecdoteBody):
    items = _read_anecdotas()
    items.append({"titulo": body.titulo, "texto": body.texto, "cta": body.cta})
    _write_anecdotas(items)
    return {"index": len(items) - 1, "status": "ok"}


@router.put("/anecdotes/{anecdote_index}")
async def update_anecdote(anecdote_index: int, body: AnecdoteBody):
    items = _read_anecdotas()
    if anecdote_index < 0 or anecdote_index >= len(items):
        raise HTTPException(status_code=404, detail="Anècdota no trobada")
    items[anecdote_index] = {"titulo": body.titulo, "texto": body.texto, "cta": body.cta}
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
            from database import get_connection
            _db_conn.close()
            _db_conn = get_connection(str(_base_dir / "data" / "godesia.db"))
            return {"status": "ok", "message": "Connexió a la BD reiniciada correctament."}
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
