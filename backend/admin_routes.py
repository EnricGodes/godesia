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


def _strip_nickname(text: str) -> str:
    """Remove quoted and parenthetical nicknames from a given name.
    'Dolores "Lolita"' → 'Dolores', 'Josep (Pepe)' → 'Josep'."""
    import re
    if not text:
        return text
    # Remove "..." and (...)  (also handles unicode “ ” ‘ ’ quotes)
    text = re.sub(r'["“”][^"“”]*["“”]', '', text)
    text = re.sub(r"['‘’][^'‘’]*['‘’]", '', text)
    text = re.sub(r'\([^)]*\)', '', text)
    return " ".join(text.split())


# Catalan ↔ Spanish given-name variants. Each form maps to a single canonical
# key so equivalent names collide in the index. Includes common diminutives.
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
}
_NAME_VARIANTS: dict = {}
for _a, _b in _NAME_VARIANT_PAIRS:
    _NAME_VARIANTS[_a] = _a
    _NAME_VARIANTS[_b] = _a
_NAME_VARIANTS.update(_NAME_DIMINUTIVES)

# Tokens dropped during canonicalization (Catalan/Spanish surname connectors,
# articles, and similar fillers between surnames).
_NAME_STOPWORDS = {"i", "y", "de", "del", "la", "el", "les", "los", "da", "do"}


def _canonicalize_person_name(text: str) -> str:
    """Canonical form for matching genealogy people across GEDCOM ↔ DB.
    Steps: strip nicknames → NFD/lowercase → drop connectors (i/y/de/...) →
    drop 1-char tokens → map Catalan↔Spanish variants → reorder alphabetically
    so 'surname given' and 'given surname' collide."""
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
                  db_burials: list, db_events: list, db_photos: list,
                  db_marriages: list, db_children: list,
                  ged: dict, families: dict, individuals: dict) -> tuple:
    """Compare one DB person against one GEDCOM individual.
    Returns (diff_types_list, diff_details_dict)."""
    diff_types = []
    details = {}

    # ── Dates ─────────────────────────────────────────────────────────────
    # Flag when GEDCOM brings information the DB lacks: empty DB date, or
    # year-only DB vs full GEDCOM date. Skip cross-format comparison
    # (Spanish 'abr.' vs GEDCOM 'APR') — they would produce too many false
    # positives without language-aware month parsing.
    date_diffs = []
    db_birth_year = db_person.get("birth_year")
    db_birth_date = (db_person.get("birth_date") or "").strip()
    ged_birth = ged.get("birth") or {}
    ged_birth_date = (ged_birth.get("date") or "").strip()
    db_birth_is_year_only = bool(db_birth_year) and (
        not db_birth_date or db_birth_date == str(db_birth_year)
    )
    if ged_birth_date and not db_birth_date and not db_birth_year:
        date_diffs.append(f"Naixement: BD no té data, GEDCOM té '{ged_birth_date}'")
    elif db_birth_is_year_only and _ged_has_full_date(ged_birth_date):
        date_diffs.append(f"Naixement: BD té '{db_birth_date or db_birth_year}', GEDCOM té '{ged_birth_date}'")

    db_death_year = db_person.get("death_year")
    db_death_date = (db_person.get("death_date") or "").strip()
    ged_death = ged.get("death") or {}
    ged_death_date = (ged_death.get("date") or "").strip()
    db_death_is_year_only = bool(db_death_year) and (
        not db_death_date or db_death_date == str(db_death_year)
    )
    if ged_death_date and not db_death_date and not db_death_year:
        date_diffs.append(f"Defunció: BD no té data, GEDCOM té '{ged_death_date}'")
    elif db_death_is_year_only and _ged_has_full_date(ged_death_date):
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
    if ged_bp and (not db_bp or (ged_bp.lower() != db_bp.lower() and len(ged_bp) > len(db_bp))):
        place_diffs.append(f"Lloc neix.: BD '{db_bp or '—'}' → GEDCOM '{ged_bp}'")

    db_dp = (db_person.get("death_place") or "").strip()
    ged_dp = (ged_death.get("place") or "").strip()
    if ged_dp and (not db_dp or (ged_dp.lower() != db_dp.lower() and len(ged_dp) > len(db_dp))):
        place_diffs.append(f"Lloc def.: BD '{db_dp or '—'}' → GEDCOM '{ged_dp}'")

    ged_bapt_place = (ged_bapt.get("place") or "").strip()
    db_bapt_place  = (db_person.get("baptism_place") or "").strip()
    if ged_bapt_place and (not db_bapt_place or (ged_bapt_place.lower() != db_bapt_place.lower() and len(ged_bapt_place) > len(db_bapt_place))):
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
    # Compare full normalized note text (case + whitespace insensitive) and
    # send the entire content to the frontend so the user can read it whole.
    ged_notes = ged.get("notes") or []
    db_notes_norm = {_normalize_name(n) for n in db_notes if n}
    new_notes = [n for n in ged_notes if n and _normalize_name(n) not in db_notes_norm]
    if new_notes:
        diff_types.append("notes")
        details["notes"] = [f"Nova nota: {n}" for n in new_notes]

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
        _normalize_name(f"{r.get('city', '')} {r.get('date', '')}") for r in db_res
    }
    new_res = [
        r for r in ged_res
        if _normalize_name(f"{r.get('city', '')} {r.get('date', '')}") not in db_res_keys
    ]
    if new_res:
        diff_types.append("residences")
        details["residences"] = [
            f"Residència: {r.get('address', '')} {r.get('city', '')} ({r.get('date', '')})".strip()
            for r in new_res
        ]

    # ── Photos & documents ────────────────────────────────────────────────
    # Match GEDCOM ↔ DB photos by MyHeritage `_PHOTO_RIN`, the only stable id
    # both sides share. Photos in the GEDCOM with a RIN we don't have, or
    # without a RIN at all (rarer), surface as new. PDF attachments surface
    # under a separate `documents` category since the user cares about them.
    ged_photos_all = ged.get("photos") or []
    db_rin_set = {p["photo_rin"] for p in db_photos if p.get("photo_rin")}
    new_photos: list = []
    new_docs: list = []
    for p in ged_photos_all:
        rin = p.get("photo_rin")
        if rin and rin in db_rin_set:
            continue
        url = p.get("url") or ""
        is_document = (p.get("form") or "").lower() == "pdf" or url.lower().split("?")[0].endswith(".pdf")
        label_parts = []
        if p.get("title"):
            label_parts.append(p["title"])
        if rin:
            label_parts.append(f"[{rin}]")
        if not label_parts and url:
            label_parts.append(url.rsplit("/", 1)[-1].split("?")[0])
        label = " ".join(label_parts) or "(sense títol)"
        if is_document:
            new_docs.append(f"Document: {label}" + (f" — {url}" if url else ""))
        else:
            new_photos.append(f"Foto: {label}" + (f" — {url}" if url else ""))
    if new_photos:
        diff_types.append("photos")
        details["photos"] = new_photos
    if new_docs:
        diff_types.append("documents")
        details["documents"] = new_docs

    # ── Sex ───────────────────────────────────────────────────────────────
    db_sex  = (db_person.get("sex") or "").strip().upper()
    ged_sex = (ged.get("sex") or "").strip().upper()
    if ged_sex and db_sex and ged_sex != db_sex:
        diff_types.append("sex")
        details["sex"] = [f"Sexe: BD '{db_sex}' vs GEDCOM '{ged_sex}'"]
    elif ged_sex and not db_sex:
        diff_types.append("sex")
        details["sex"] = [f"Sexe: BD buit, GEDCOM '{ged_sex}'"]

    # ── Parents ───────────────────────────────────────────────────────────
    parent_diffs = []
    fam_child_ref = ged.get("family_child")
    ged_father_canon = ged_mother_canon = ""
    ged_father_name = ged_mother_name = ""
    if fam_child_ref and fam_child_ref in families:
        fam = families[fam_child_ref]
        if fam.get("husband") and fam["husband"] in individuals:
            ged_father_name = individuals[fam["husband"]].get("name") or ""
            ged_father_canon = _canonicalize_person_name(ged_father_name)
        if fam.get("wife") and fam["wife"] in individuals:
            ged_mother_name = individuals[fam["wife"]].get("name") or ""
            ged_mother_canon = _canonicalize_person_name(ged_mother_name)
    db_father_canon = _canonicalize_person_name(db_person.get("father_name") or "")
    db_mother_canon = _canonicalize_person_name(db_person.get("mother_name") or "")
    if ged_father_canon and db_father_canon and ged_father_canon != db_father_canon:
        parent_diffs.append(f"Pare: BD '{db_person.get('father_name')}' vs GEDCOM '{ged_father_name}'")
    elif ged_father_canon and not db_father_canon:
        parent_diffs.append(f"Pare al GEDCOM: '{ged_father_name}' (BD no té)")
    if ged_mother_canon and db_mother_canon and ged_mother_canon != db_mother_canon:
        parent_diffs.append(f"Mare: BD '{db_person.get('mother_name')}' vs GEDCOM '{ged_mother_name}'")
    elif ged_mother_canon and not db_mother_canon:
        parent_diffs.append(f"Mare al GEDCOM: '{ged_mother_name}' (BD no té)")
    if parent_diffs:
        diff_types.append("parents")
        details["parents"] = parent_diffs

    # ── Marriages / spouses ───────────────────────────────────────────────
    marriage_diffs = []
    db_spouses_canon = {_canonicalize_person_name(m.get("spouse_name") or "") for m in db_marriages}
    db_spouses_canon.discard("")
    ged_spouses_canon: set = set()
    for fam_ref in (ged.get("family_spouse") or []):
        if fam_ref not in families:
            continue
        fam = families[fam_ref]
        for role in ("husband", "wife"):
            ref = fam.get(role)
            if not ref or ref == ged.get("id"):
                continue
            if ref not in individuals:
                continue
            sp_name = individuals[ref].get("name") or ""
            sp_canon = _canonicalize_person_name(sp_name)
            if not sp_canon:
                continue
            ged_spouses_canon.add(sp_canon)
            if sp_canon not in db_spouses_canon:
                marr = fam.get("marriage") or {}
                bits = [f"Cònjuge nou al GEDCOM: '{sp_name}'"]
                if marr.get("date"):
                    bits.append(f"data {marr['date']}")
                if marr.get("place"):
                    bits.append(f"lloc {marr['place']}")
                marriage_diffs.append(" — ".join(bits))
    if marriage_diffs:
        diff_types.append("marriage")
        details["marriage"] = marriage_diffs

    # ── Children ──────────────────────────────────────────────────────────
    child_diffs = []
    db_children_canon = {_canonicalize_person_name(c.get("name") or "") for c in db_children}
    db_children_canon.discard("")
    seen_children: set = set()
    for fam_ref in (ged.get("family_spouse") or []):
        if fam_ref not in families:
            continue
        fam = families[fam_ref]
        for child_ref in fam.get("children") or []:
            if child_ref not in individuals:
                continue
            ch_name = individuals[child_ref].get("name") or ""
            ch_canon = _canonicalize_person_name(ch_name)
            if not ch_canon or ch_canon in seen_children:
                continue
            seen_children.add(ch_canon)
            if ch_canon not in db_children_canon:
                child_diffs.append(f"Fill/a nou al GEDCOM: '{ch_name}'")
    if child_diffs:
        diff_types.append("children")
        details["children"] = child_diffs

    # ── Name differences ──────────────────────────────────────────────────
    # Compare on canonical form so Joan/Juan, "Mestre i Campi"/"Mestre Campi"
    # and accent variants don't show up as false-positive differences.
    name_diffs = []
    db_given_c   = _canonicalize_person_name(db_person.get("given_name") or "")
    ged_given_c  = _canonicalize_person_name(ged.get("given_name") or "")
    db_surname_c = _canonicalize_person_name(db_person.get("surname") or "")
    ged_surname_c= _canonicalize_person_name(ged.get("surname") or "")
    db_nick      = _normalize_name(db_person.get("nickname") or "")
    ged_nick     = _normalize_name(ged.get("nickname") or "")

    if db_given_c and ged_given_c and db_given_c != ged_given_c:
        name_diffs.append(f"Nom: BD '{db_person.get('given_name')}' vs GEDCOM '{ged.get('given_name')}'")
    if db_surname_c and ged_surname_c and db_surname_c != ged_surname_c:
        name_diffs.append(f"Cognom: BD '{db_person.get('surname')}' vs GEDCOM '{ged.get('surname')}'")
    if ged_nick and not db_nick:
        name_diffs.append(f"Malnom al GEDCOM: '{ged.get('nickname')}'")

    if name_diffs:
        diff_types.append("name")
        details["name"] = name_diffs

    return diff_types, details


def _build_ged_index(individuals: dict) -> dict:
    """Build canonical name → [ged_id, ...] lookup from all GEDCOM individuals.

    Each individual is indexed under several canonical forms so callers can
    probe whichever representation they have:
      - full canonical name
      - all given names + surname (and reversed)
      - first given name only + surname (handles 'Juan Francisco' vs 'Joan')
    """
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
            # First given name only (compound names like 'Juan Francisco'
            # often appear as just 'Joan' / 'Juan' on the other side).
            first_given = canon_given.split()[0]
            if first_given and first_given != canon_given:
                candidates.add(f"{first_given} {canon_surname}")
                candidates.add(f"{canon_surname} {first_given}")
        for name in candidates:
            index.setdefault(name, []).append(ged_id)
    return index


def _match_person(db_person: dict, individuals: dict, ged_index: dict) -> tuple:
    """Find best GEDCOM match for a DB person.
    Returns (ged_id | None, score 0-100).

    Strategy: build canonical forms (Catalan↔Spanish variants, drop "i"
    connectors, drop accents/case), look up candidates in the GEDCOM index,
    then disambiguate by birth year when more than one candidate matches the
    same canonical name."""
    db_given_canon   = _canonicalize_person_name(db_person.get("given_name") or "")
    db_surname_canon = _canonicalize_person_name(db_person.get("surname") or "")
    db_full_canon    = _canonicalize_person_name(db_person.get("name") or "")
    db_year          = db_person.get("birth_year")

    probes = [db_full_canon]
    if db_given_canon and db_surname_canon:
        probes.append(f"{db_given_canon} {db_surname_canon}")
        probes.append(f"{db_surname_canon} {db_given_canon}")
        # Also probe by first given name only — handles cases like DB
        # 'Juan Francisco' lookup against a GEDCOM 'Joan'.
        first_given = db_given_canon.split()[0] if db_given_canon else ""
        if first_given and first_given != db_given_canon:
            probes.append(f"{first_given} {db_surname_canon}")
            probes.append(f"{db_surname_canon} {first_given}")

    candidates: set = set()
    for name in probes:
        if not name:
            continue
        for gid in ged_index.get(name, []):
            candidates.add(gid)

    if not candidates:
        return None, 0

    multiple = len(candidates) > 1
    best_gid, best_score = None, 0
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
                # Years disagree by >5: only acceptable if name is unique here
                score = 65 if not multiple else 0
        else:
            # No birth year on at least one side: be more cautious if multiple
            # candidates share this name to avoid grabbing a homonym
            if multiple:
                score = 78 if canon_match else 60
            else:
                score = 88 if canon_match else 75

        if score > best_score:
            best_score, best_gid = score, gid

    if best_score == 0:
        return None, 0
    return best_gid, best_score


def _run_comparison(ged_path: str, db_path: str):
    """Background thread: parse GEDCOM, compare with DB, save results. Never modifies people data."""
    import sys as _sys
    t_start = time.time()
    try:
        backend_dir = str(Path(db_path).parent)
        if backend_dir not in _sys.path:
            _sys.path.insert(0, backend_dir)

        from gedcom_parser import parse_gedcom
        from database import get_connection as _get_conn

        _cmp_log(f"Iniciant comparació: {Path(ged_path).name}")

        # 1. Parse GEDCOM (read-only, no DB touch)
        _cmp_log("[1/4] Parsejant GEDCOM…")
        data = parse_gedcom(ged_path)
        individuals = data["individuals"]
        _cmp_log(f"  {len(individuals):,} individus al GEDCOM")

        # 2. Build name index
        _cmp_log("[2/4] Construint índex de noms…")
        ged_index = _build_ged_index(individuals)
        _cmp_log(f"  {len(ged_index):,} entrades a l'índex")

        # 3. Load all DB people + pre-fetch related tables (one query each, not N×N)
        _cmp_log("[3/4] Carregant dades de la BD…")
        conn = _get_conn(db_path)
        db_people = conn.execute(
            "SELECT id, name, given_name, surname, nickname, sex, "
            "birth_date, birth_year, birth_place, "
            "death_date, death_year, death_place, death_cause, "
            "baptism_date, baptism_place, "
            "father_id, mother_id, father_name, mother_name "
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

        # Photos joined with their tags so we can index by person.
        all_photos: dict = {}
        for r in conn.execute(
            "SELECT pt.person_id, p.photo_rin, p.filename, p.title, "
            "       p.is_document, p.doc_type "
            "FROM photo_tags pt JOIN photos p ON pt.photo_id = p.id"
        ).fetchall():
            all_photos.setdefault(r["person_id"], []).append(dict(r))

        # Marriages: spouse name resolved via people table for both directions.
        all_marriages: dict = {}
        for r in conn.execute(
            "SELECT m.person1_id AS pid, m.person2_id AS spouse_id, "
            "       p.name AS spouse_name, m.date, m.place "
            "FROM marriages m LEFT JOIN people p ON p.id = m.person2_id"
        ).fetchall():
            all_marriages.setdefault(r["pid"], []).append(dict(r))
        for r in conn.execute(
            "SELECT m.person2_id AS pid, m.person1_id AS spouse_id, "
            "       p.name AS spouse_name, m.date, m.place "
            "FROM marriages m LEFT JOIN people p ON p.id = m.person1_id"
        ).fetchall():
            all_marriages.setdefault(r["pid"], []).append(dict(r))

        # Children of each parent, resolved to child name.
        all_children: dict = {}
        for r in conn.execute(
            "SELECT c.parent_id AS pid, c.child_id, p.name "
            "FROM children c LEFT JOIN people p ON p.id = c.child_id"
        ).fetchall():
            all_children.setdefault(r["pid"], []).append(dict(r))

        total = len(db_people)
        with _cmp_job_lock:
            _cmp_job["total"] = total
        _cmp_log(f"  {total} persones a la BD")

        # Clear previous results
        conn.execute("DELETE FROM compare_results")
        conn.commit()

        # 4. Compare each DB person
        _cmp_log("[4/4] Comparant persona a persona…")
        meaningful = 0
        for i, db_row in enumerate(db_people):
            with _cmp_job_lock:
                _cmp_job["progress"] = i + 1

            db_person = dict(db_row)
            pid = db_person["id"]

            # Skip MyHeritage placeholder "Unassociated photos" which holds
            # orphan photo metadata and would emit thousands of fake diffs.
            if (db_person.get("name") or "").strip().lower() == "unassociated photos":
                continue

            ged_id, score = _match_person(db_person, individuals, ged_index)

            if ged_id is None:
                diff_types = ["nomatch"]
                diff_details = {"nomatch": ["Persona no trobada al GEDCOM"]}
            else:
                diff_types, diff_details = _compute_diff(
                    db_person,
                    all_notes.get(pid, []),
                    all_occs.get(pid, []),
                    all_res.get(pid, []),
                    all_burials.get(pid, []),
                    all_events.get(pid, []),
                    all_photos.get(pid, []),
                    all_marriages.get(pid, []),
                    all_children.get(pid, []),
                    individuals[ged_id],
                    data.get("families") or {},
                    individuals,
                )

            if diff_types:
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
        conn.close()

        elapsed = _fmt_dur(time.time() - t_start)
        _cmp_log(f"✓ Completat: {meaningful} diferències de {total} persones en {elapsed}")

        with _cmp_job_lock:
            _cmp_job["status"] = "done"
            _cmp_job["finished_at"] = datetime.now().isoformat()
            _cmp_job["progress"] = total

    except Exception as exc:
        with _cmp_job_lock:
            _cmp_job["status"] = "error"
            _cmp_job["error"] = str(exc)
            _cmp_job["finished_at"] = datetime.now().isoformat()
            _cmp_job["log"].append(f"ERROR: {exc}")
            _cmp_job["log"].append(traceback.format_exc())


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
