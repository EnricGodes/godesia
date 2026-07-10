"""FastAPI server para Godesia - consulta genealógica en lenguaje natural."""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import re
import shutil
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import (
    get_connection, get_tree_data, get_tree_data_flat, get_birthdays_this_week, search_people,
    get_dashboard_data, get_documents, get_person_dossier, convert_date_to_spanish,
    update_all_photo_files, update_all_city_fields, get_photo_details,
    get_albums_list, get_album_photos, get_photos_people_list,
    get_document_types, get_document_photos, get_document_albums, get_documents_people_list,
    get_setting, set_setting,
    get_cemeteries_summary, get_cemetery_detail, get_person_niche, get_cemeteries_overview,
)
from query_router import QueryRouter
from query_engine import QueryEngine
import i18n as i18n_pages
import test_bank
from admin_routes import router as admin_router, init_admin, init_log_capture
from palazuelos_routes import router as palazuelos_router, init_palazuelos
from geocode_utils import normalize_place, build_queries, geocode_with_cache

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = DATA_DIR / "photos"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = DATA_DIR / "godesia.db"
SUGGESTIONS_DIR = DATA_DIR / "suggestions"
CEMETERY_PHOTOS_DIR = DATA_DIR / "cemetery_photos"

app = FastAPI(title="Godesia", description="Consulta genealógica en lenguaje natural")
app.include_router(admin_router)
app.include_router(palazuelos_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.middleware("http")(i18n_pages.i18n_middleware)

db_conn = None
router = None
engine = None
gedcom_export_date = None


@app.on_event("startup")
async def startup():
    global db_conn, router, engine, gedcom_export_date
    init_log_capture()
    if not DB_PATH.exists():
        raise RuntimeError(f"No se encuentra {DB_PATH}. Ejecuta primero migrate_json_to_sqlite.py")
    db_conn = get_connection(str(DB_PATH))
    router = QueryRouter(db_conn)
    count = db_conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    print(f"SQLite cargado: {count} personas")

    # AUTO-HEAL: If any person has photos tagged but no photo_file set,
    # regenerate photo_file for everyone. This protects against photo loss
    # from any script that updates the people table without preserving photo_file.
    try:
        missing = db_conn.execute("""
            SELECT COUNT(DISTINCT p.id) FROM people p
            JOIN photo_tags pt ON pt.person_id = p.id
            WHERE (p.photo_file IS NULL OR p.photo_file = '')
        """).fetchone()[0]
        if missing > 0:
            print(f"⚠ Detectadas {missing} personas con fotos sin photo_file. Auto-reparando...")
            updated = update_all_photo_files(db_conn)
            print(f"✓ Fotos de perfil restauradas para {updated} personas")
    except Exception as e:
        print(f"  Auto-heal de fotos falló: {e}")

    # AUTO-HEAL: Push geocache lat/lng to residences/events if any rows have null coords.
    # sync_catalog.py wipes and re-inserts residences without lat/lng; this restores them.
    try:
        from geocode_utils import propagate_geocache as _propagate_geocache
        missing_geo = db_conn.execute(
            "SELECT COUNT(*) FROM residences WHERE lat IS NULL"
        ).fetchone()[0]
        if missing_geo > 0:
            propagated = _propagate_geocache(db_conn)
            if propagated:
                print(f"✓ Coordenadas restauradas en {propagated} residencias/eventos")
    except Exception as e:
        print(f"  Auto-heal de geocoordinadas falló: {e}")

    # AUTO-HEAL: Extract birth_city/death_city for people where they are NULL.
    try:
        missing_cities = db_conn.execute(
            "SELECT COUNT(*) FROM people "
            "WHERE (birth_city IS NULL AND birth_place IS NOT NULL) "
            "   OR (death_city IS NULL AND death_place IS NOT NULL)"
        ).fetchone()[0]
        if missing_cities > 0:
            city_updated = update_all_city_fields(db_conn)
            if city_updated:
                print(f"✓ Ciudades extraídas para {city_updated} personas")
    except Exception as e:
        print(f"  Auto-heal de ciudades falló: {e}")

    # Read GEDCOM export date from header (auto-detect most recent .ged file)
    ged_files = sorted((BASE_DIR / "docs").glob("*.ged"), key=lambda p: p.stat().st_mtime, reverse=True)
    gedcom_path = ged_files[0] if ged_files else None
    if gedcom_path and gedcom_path.exists():
        try:
            with open(gedcom_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("1 DATE"):
                        raw = line.strip().replace("1 DATE", "").strip()
                        gedcom_export_date = convert_date_to_spanish(raw)
                        print(f"Fecha GEDCOM: {gedcom_export_date}")
                        break
        except Exception as e:
            print(f"  Error leyendo fecha GEDCOM: {e}")

    init_admin(db_conn, BASE_DIR)
    init_palazuelos(db_conn, BASE_DIR)
    i18n_pages.init_i18n(db_conn, BASE_DIR)

    # LLM engine (optional, only if API key is set)
    if os.environ.get("ANTHROPIC_API_KEY"):
        engine = QueryEngine(db_conn)
        print("Motor LLM inicializado")
    else:
        print("ANTHROPIC_API_KEY no configurada. Solo consultas directas disponibles.")


class QueryRequest(BaseModel):
    question: str
    history: list = []


class ConfirmRequest(BaseModel):
    question: str
    history: list = []


def log_unresolved_query(question):
    """Log a query that could not be resolved."""
    unresolved_file = DATA_DIR / "unresolved_queries.jsonl"
    now = datetime.now()
    entry = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "question": question
    }
    try:
        with open(unresolved_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error logging unresolved query: {e}")


@app.post("/api/query")
async def query(req: QueryRequest):
    """Intenta responder desde SQLite. Si no puede, anota la consulta."""
    if not router:
        raise HTTPException(status_code=503, detail="Motor no inicializado")

    # Try direct DB answer
    result = router.route(req.question)

    # Check if router couldn't resolve the question
    if result and "No he sabido responder" in result.get("answer", ""):
        log_unresolved_query(req.question)

    return result


@app.post("/api/query/confirm")
async def query_confirm(req: ConfirmRequest):
    """Ejecuta consulta LLM tras confirmación del usuario."""
    if not engine:
        raise HTTPException(
            status_code=503,
            detail="Motor LLM no disponible. Configura ANTHROPIC_API_KEY."
        )
    result = engine.query(req.question, req.history)
    result["source"] = "llm"
    return result


@app.get("/api/birthdays")
async def birthdays():
    """Cumpleaños de esta semana."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return {"birthdays": get_birthdays_this_week(db_conn)}


@app.get("/api/tree/{person_id}")
async def tree(person_id: str, generations_up: int = 3, generations_down: int = 2):
    """Datos del árbol genealógico centrado en una persona."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    # Decode person_id: frontend sends I1 instead of @I1@
    if not person_id.startswith("@"):
        person_id = "@%s@" % person_id
    data = get_tree_data(db_conn, person_id, generations_up, generations_down)
    if not data:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return data


@app.get("/api/tree2/{person_id}")
async def tree2(person_id: str, up: int = 3, down: int = 3):
    """Datos del árbol en formato flat para family-chart (arbol2)."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    if not person_id.startswith("@"):
        person_id = f"@{person_id}@"
    data = get_tree_data_flat(db_conn, person_id, generations_up=up, generations_down=down)
    if not data:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    clean_id = person_id.replace("@", "")
    return {"nodes": data, "main_id": clean_id}


@app.get("/api/search")
async def search(q: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100)):
    """Buscar personas por nombre."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    results = search_people(db_conn, q, limit=limit)
    return {"results": [dict(r) for r in results]}


@app.get("/api/stats")
async def stats():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    total = db_conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    families = db_conn.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
    return {"total_people": total, "total_families": families}


@app.get("/api/dashboard")
async def dashboard():
    """All data needed for the dashboard landing page."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_dashboard_data(db_conn)


@app.get("/api/dossier/{person_id}")
async def dossier(person_id: str):
    """Complete dossier data for a person."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    # Decode person_id: frontend sends I16 instead of @I16@
    if not person_id.startswith("@"):
        person_id = "@%s@" % person_id
    dossier_data = get_person_dossier(db_conn, person_id)
    if not dossier_data:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person_updated_at = dossier_data.get("person", {}).get("updated_at", "")
    if person_updated_at:
        dossier_data["gedcom_date"] = convert_date_to_spanish(person_updated_at)
    else:
        dossier_data["gedcom_date"] = gedcom_export_date or ""
    dossier_data["vital_points"] = _build_vital_points(db_conn, dossier_data)
    return dossier_data


def _lookup_geocache(conn, raw_place: str):
    if not raw_place or not raw_place.strip():
        return None
    lat, lng = geocode_with_cache(conn, raw_place, cache_only=True)
    if lat is not None:
        return {"lat": lat, "lng": lng}
    return None


def _build_vital_points(conn, dossier_data: dict) -> list:
    person = dossier_data.get("person", {})
    points = []
    coords = _lookup_geocache(conn, person.get("birth_place"))
    if coords:
        points.append({"type": "birth", "label": person["birth_place"], **coords})
    seen_marriage = set()
    for sp in dossier_data.get("spouses", []):
        mp = sp.get("marriage_place")
        if mp and mp not in seen_marriage:
            seen_marriage.add(mp)
            coords = _lookup_geocache(conn, mp)
            if coords:
                points.append({"type": "marriage", "label": mp, **coords})
    coords = _lookup_geocache(conn, person.get("death_place"))
    if coords:
        points.append({"type": "death", "label": person["death_place"], **coords})
    for b in dossier_data.get("burial", []):
        bp = b.get("place")
        if bp:
            coords = _lookup_geocache(conn, bp)
            if coords:
                points.append({"type": "burial", "label": bp, **coords})
    return points


@app.get("/api/photo/{photo_id}")
async def photo_details(photo_id: int):
    """Get complete details for a photo (title, date, place, tagged people, notes, album)."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    photo_data = get_photo_details(db_conn, photo_id)
    if not photo_data:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return photo_data


@app.post("/api/admin/sync-photos")
async def sync_photos_endpoint():
    """
    Regenerate photo_file for all people using the 5-level selection algorithm.

    This ensures profile photos are correctly set after any photo table updates.
    Should be called after importing new GEDCOM or updating photo metadata.
    """
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    try:
        updated = update_all_photo_files(db_conn)
        return {
            "status": "ok",
            "message": f"Fotos sincronizadas para {updated} personas",
            "updated_count": updated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sincronizando fotos: {str(e)}")


# ---------------------------------------------------------------------------
# Test bank endpoints
# ---------------------------------------------------------------------------

class AddQuestionsRequest(BaseModel):
    questions: list
    tags: list = []

class RunTestsRequest(BaseModel):
    mode: str = "all"  # all | new | regressions | selected
    case_ids: list = []

class VerdictRequest(BaseModel):
    case_id: str
    verdict: str  # approved | rejected | pending

class DeleteCasesRequest(BaseModel):
    case_ids: list

class ImportBankRequest(BaseModel):
    data: dict


@app.get("/api/tests/bank")
async def get_test_bank():
    return test_bank.get_bank()

@app.get("/api/tests/stats")
async def get_test_stats():
    return test_bank.get_stats()

@app.post("/api/tests/bank/add")
async def add_test_questions(req: AddQuestionsRequest):
    return test_bank.add_questions(req.questions, req.tags)

@app.post("/api/tests/bank/run")
async def run_test_bank(req: RunTestsRequest):
    if not router:
        raise HTTPException(status_code=503, detail="Router no inicializado")
    return test_bank.run_tests(router, req.mode, req.case_ids)

@app.post("/api/tests/bank/verdict")
async def set_test_verdict(req: VerdictRequest):
    result = test_bank.set_verdict(req.case_id, req.verdict)
    if not result:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return result

@app.post("/api/tests/bank/delete")
async def delete_test_cases(req: DeleteCasesRequest):
    deleted = test_bank.delete_cases(req.case_ids)
    return {"deleted": deleted}

@app.post("/api/tests/bank/bootstrap")
async def bootstrap_test_bank():
    if not router:
        raise HTTPException(status_code=503, detail="Router no inicializado")
    return test_bank.bootstrap_from_router(router)

@app.post("/api/tests/bank/auto-review")
async def auto_review_test_bank():
    if not router:
        raise HTTPException(status_code=503, detail="Router no inicializado")
    return test_bank.auto_review(router)

@app.get("/api/tests/bank/export")
async def export_test_bank():
    return test_bank.export_bank()

@app.post("/api/tests/bank/import")
async def import_test_bank(req: ImportBankRequest):
    return test_bank.import_bank(req.data)


@app.get("/api/albums")
async def albums_list():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_albums_list(db_conn)


@app.get("/api/albums/people")
async def albums_people():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_photos_people_list(db_conn)


@app.get("/api/album/{album_id}/photos")
async def album_photos(
    album_id: str,
    q: str = Query(""),
    sort: str = Query("date"),
    person_id: str = Query(""),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    show_docs: bool = Query(False),
):
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    if album_id not in ("__unassigned__", "__all__") and not album_id.startswith("@"):
        album_id = f"@{album_id}@"
    if person_id and not person_id.startswith("@"):
        person_id = f"@{person_id}@"
    return get_album_photos(db_conn, album_id, q=q, sort=sort, person_id=person_id, page=page, limit=limit, show_docs=show_docs)


@app.get("/api/cemeteries")
async def cemeteries_list():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_cemeteries_summary(db_conn)


@app.get("/api/cemeteries/overview")
async def cemeteries_overview():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_cemeteries_overview(db_conn)


@app.get("/api/cemeteries/locate/{person_id}")
async def cemeteries_locate(person_id: str):
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    if not person_id.startswith("@"):
        person_id = "@%s@" % person_id
    niche = get_person_niche(db_conn, person_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Sin sepultura registrada")
    return niche


@app.get("/api/cemeteries/{cemetery_id}")
async def cemetery_detail(cemetery_id: int):
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    cemetery = get_cemetery_detail(db_conn, cemetery_id)
    if not cemetery:
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    return cemetery


@app.get("/api/admin/cemeteries/{cemetery_id}/pdf")
async def cemetery_pdf(cemetery_id: int):
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    data = get_cemetery_detail(db_conn, cemetery_id, include_disabled=False)
    if not data:
        raise HTTPException(status_code=404, detail="Cementerio no encontrado")
    from pdf_cemetery import generate_cemetery_pdf
    import io as _io
    pdf_bytes = generate_cemetery_pdf(data, photos_dir=str(PHOTOS_DIR))
    safe = data["name"].lower().replace(" ", "-")
    return StreamingResponse(
        _io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="guia-{safe}.pdf"'},
    )


@app.get("/api/documents")
async def documents_types():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_document_types(db_conn)


@app.get("/api/documents/people")
async def documents_people():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_documents_people_list(db_conn)


@app.get("/api/documents/albums")
async def documents_albums():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    return get_document_albums(db_conn)


@app.get("/api/documents/photos")
async def documents_photos(
    doc_type: str = Query("__all__"),
    q: str = Query(""),
    sort: str = Query("date"),
    person_id: str = Query(""),
    album_id: str = Query(""),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    if person_id and not person_id.startswith("@"):
        person_id = f"@{person_id}@"
    return get_document_photos(db_conn, doc_type=doc_type, q=q, sort=sort,
                               person_id=person_id, album_id=album_id, page=page, limit=limit)


# ---------------------------------------------------------------------------
# Admin geocoder endpoints
# ---------------------------------------------------------------------------

from geocode_utils import nominatim_search, propagate_geocache
from geocode_vital_places import seed_vital_places, geocode_vital_places as _geocode_vital_places


class GeoResolveRequest(BaseModel):
    query: str
    lat: float
    lng: float
    display_name: str = ""


class GeoSearchRequest(BaseModel):
    query: str


@app.get("/api/admin/geocoder/pending")
async def geocoder_pending():
    """List geocache entries that could not be geocoded (lat IS NULL)."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    rows = db_conn.execute(
        "SELECT query, raw_place, geocoded_at FROM geocache WHERE lat IS NULL ORDER BY geocoded_at DESC"
    ).fetchall()
    result = []
    for row in rows:
        query = row[0]
        raw_place = row[1] or ""
        # Count residences and events using this raw_place
        r_count = db_conn.execute(
            "SELECT COUNT(*) FROM residences WHERE lat IS NULL "
            "AND (address || ', ' || city || ', ' || country LIKE ?)",
            (f"%{raw_place[:30]}%",)
        ).fetchone()[0]
        e_count = db_conn.execute(
            "SELECT COUNT(*) FROM events WHERE lat IS NULL AND place=?",
            (raw_place,)
        ).fetchone()[0]
        result.append({
            "query": query,
            "raw_place": raw_place,
            "affected": r_count + e_count,
            "geocoded_at": row[2],
        })
    return result


@app.get("/api/admin/geocoder/resolved")
async def geocoder_resolved():
    """List geocache entries that have been successfully geocoded (lat IS NOT NULL)."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    rows = db_conn.execute(
        "SELECT query, raw_place, lat, lng, geocoded_at, display_name FROM geocache "
        "WHERE lat IS NOT NULL AND (validated IS NULL OR validated = 0) ORDER BY geocoded_at DESC"
    ).fetchall()
    return [
        {"query": row[0], "raw_place": row[1] or "", "lat": row[2],
         "lng": row[3], "geocoded_at": row[4], "display_name": row[5] or ""}
        for row in rows
    ]


@app.get("/api/admin/geocoder/validated")
async def geocoder_validated():
    """List geocache entries that have been validated by a human."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    rows = db_conn.execute(
        "SELECT query, raw_place, lat, lng, geocoded_at, display_name FROM geocache "
        "WHERE validated = 1 ORDER BY geocoded_at DESC"
    ).fetchall()
    return [
        {"query": row[0], "raw_place": row[1] or "", "lat": row[2],
         "lng": row[3], "geocoded_at": row[4], "display_name": row[5] or ""}
        for row in rows
    ]


@app.post("/api/admin/geocoder/validate")
async def geocoder_validate(req: GeoSearchRequest):
    """Mark a geocache entry as validated (query field used as key)."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    db_conn.execute("UPDATE geocache SET validated=1 WHERE query=?", (req.query,))
    db_conn.commit()
    return {"status": "ok"}


@app.get("/api/admin/geocoder/reverse")
async def geocoder_reverse(lat: float, lng: float):
    """Reverse geocode a lat/lng via Nominatim and return a display_name."""
    from geocode_utils import nominatim_search
    results = nominatim_search(f"{lat}, {lng}")
    if results:
        name = results[0].get("display_name", "")
        # Also persist in geocache if we find the matching entry
        if db_conn and name:
            db_conn.execute(
                "UPDATE geocache SET display_name=? WHERE lat=? AND lng=? AND (display_name IS NULL OR display_name='')",
                (name, lat, lng)
            )
            db_conn.commit()
        return {"display_name": name}
    return {"display_name": ""}


@app.post("/api/admin/geocoder/search")
async def geocoder_search(req: GeoSearchRequest):
    """Search Nominatim for candidates (for the CMS)."""
    candidates = nominatim_search(req.query)
    return [
        {
            "display_name": c.get("display_name", ""),
            "lat": float(c["lat"]),
            "lng": float(c["lon"]),
            "type": c.get("type", ""),
            "class": c.get("class", ""),
        }
        for c in candidates
    ]


@app.post("/api/admin/geocoder/resolve")
async def geocoder_resolve(req: GeoResolveRequest):
    """Save a resolved lat/lng for a geocache entry and propagate to DB rows."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    db_conn.execute(
        "UPDATE geocache SET lat=?, lng=?, display_name=? WHERE query=?",
        (req.lat, req.lng, req.display_name or None, req.query)
    )
    db_conn.commit()
    updated = propagate_geocache(db_conn)
    return {"status": "ok", "propagated": updated}


_vital_geocoding_status = {"running": False, "resolved": 0, "total": 0, "done": False}

def _run_vital_geocoding():
    global _vital_geocoding_status
    _vital_geocoding_status = {"running": True, "resolved": 0, "total": 0, "done": False}
    try:
        seed_vital_places(db_conn)
        total = db_conn.execute("SELECT COUNT(*) FROM geocache WHERE lat IS NULL").fetchone()[0]
        _vital_geocoding_status["total"] = total
        resolved = _geocode_vital_places(db_conn)
        propagate_geocache(db_conn)
        _vital_geocoding_status["resolved"] = resolved
    finally:
        _vital_geocoding_status["running"] = False
        _vital_geocoding_status["done"] = True


@app.post("/api/admin/geocoder/run-vital")
async def geocoder_run_vital():
    from fastapi.concurrency import run_in_threadpool
    if _vital_geocoding_status.get("running"):
        return {"status": "already_running"}
    import threading
    threading.Thread(target=_run_vital_geocoding, daemon=True).start()
    return {"status": "started"}


@app.get("/api/admin/geocoder/vital-status")
async def geocoder_vital_status():
    return _vital_geocoding_status


@app.post("/api/suggestions")
async def submit_suggestion(
    name: str = Form(""),
    email: str = Form(""),
    type: str = Form(""),
    person_id: str = Form(""),
    message: str = Form(...),
    context: str = Form("{}"),
    files: list[UploadFile] = File(default=[]),
):
    """Save a user suggestion with optional file attachments."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]", "_", name.lower())[:20].strip("_") or "anonimo"
    submission_id = f"{ts}_{slug}"

    sub_dir = SUGGESTIONS_DIR / submission_id
    sub_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        if f.filename:
            safe_name = re.sub(r"[^\w.\-]", "_", f.filename)
            dest = sub_dir / safe_name
            with dest.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            saved_files.append(safe_name)

    try:
        ctx = json.loads(context)
    except Exception:
        ctx = {}

    payload = {
        "id": submission_id,
        "name": name,
        "email": email,
        "type": type,
        "person_id": person_id,
        "message": message,
        "files": saved_files,
        "context": ctx,
    }
    (sub_dir / "submission.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if db_conn:
        db_conn.execute(
            "INSERT OR IGNORE INTO suggestions "
            "(id, name, email, type, person_id, message, files_count, submission_dir) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (submission_id, name, email, type, person_id, message,
             len(saved_files), str(sub_dir)),
        )
        db_conn.commit()

    return {"status": "ok", "id": submission_id}


# ── Default photo ─────────────────────────────────────────────────────────────

def _default_photo_filename(sex: str, birth_year: Optional[int], death_year: Optional[int]) -> str:
    """Select the era-appropriate silhouette image based on sex and birth year."""
    current_year = datetime.now().year
    is_child = (
        (birth_year and death_year and (death_year - birth_year) < 15)
        or (birth_year and birth_year >= current_year - 15)
    )
    if birth_year:
        if birth_year < 1875:
            era = 1900
        elif birth_year < 1900:
            era = 1925
        elif birth_year < 1925:
            era = 1950
        elif birth_year < 1950:
            era = 1975
        elif birth_year < 1975:
            era = 2000
        else:
            era = 2025
    else:
        era = 2025
    if is_child:
        prefix = 'niño' if sex == 'M' else 'niña' if sex == 'F' else 'niño_neutro'
    else:
        prefix = 'hombre' if sex == 'M' else 'mujer' if sex == 'F' else 'adulto_neutro'
    # Handle missing files
    if prefix == 'niña' and era == 1900:
        era = 1925
    if prefix == 'adulto_neutro' and era == 2025:
        era = 2026
    return f"{prefix}_{era}.jpg"


@app.get("/api/default-photo")
async def api_default_photo(
    sex: Optional[str] = None,
    birth_year: Optional[int] = None,
    death_year: Optional[int] = None,
):
    filename = _default_photo_filename(sex or '', birth_year, death_year)
    return RedirectResponse(url=f"/img/{filename}", status_code=302)


@app.get("/api/minibio/{person_id}")
async def api_get_minibio(person_id: str):
    p = Path(__file__).parent.parent / "data" / "minibios.json"
    if not p.exists():
        return {}
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    for m in items:
        if m.get("id") == person_id:
            return m
    return {}


# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def api_get_settings():
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicialitzada")
    return {
        "tree_default_person": get_setting(db_conn, "tree_default_person", "I4"),
        "active_languages": i18n_pages.get_active_languages(),
    }


class SettingBody(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
async def api_post_settings(body: SettingBody):
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicialitzada")
    allowed_keys = {"tree_default_person", "active_languages"}
    if body.key not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"Clau no permesa: {body.key}")
    if body.key == "active_languages":
        try:
            langs = json.loads(body.value)
            assert isinstance(langs, list) and langs
            assert all(isinstance(l, dict) and re.fullmatch(r"[a-z]{2,3}", l.get("code", ""))
                       and l.get("label") for l in langs)
        except Exception:
            raise HTTPException(status_code=400, detail="active_languages debe ser una lista [{code,label}]")
        if not any(l["code"] == "es" for l in langs):
            raise HTTPException(status_code=400, detail="El español (es) no se puede eliminar")
    set_setting(db_conn, body.key, body.value)
    if body.key == "active_languages":
        i18n_pages.invalidate_languages_cache()
    return {"ok": True, "key": body.key, "value": body.value}


# ── i18n: idiomas activos, sitemap y robots ──────────────────────────────────

@app.get("/api/languages")
async def api_languages():
    """Idiomas activos para el selector del frontend."""
    return {"languages": i18n_pages.get_active_languages(), "default": i18n_pages.DEFAULT_LANG}


@app.get("/sitemap.xml")
async def sitemap(request: Request):
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/") or f"{request.url.scheme}://{request.url.netloc}"
    return Response(i18n_pages.build_sitemap(base), media_type="application/xml")


@app.get("/robots.txt")
async def robots(request: Request):
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/") or f"{request.url.scheme}://{request.url.netloc}"
    return PlainTextResponse(f"User-agent: *\nDisallow: /admin/\n\nSitemap: {base}/sitemap.xml\n")


# Serve photos
if PHOTOS_DIR.exists():
    app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")

# Serve niche/registry photos. Conviven con las GEDCOM en data/photos/ (el volumen
# persistente de Railway); la ruta /cemetery_photos/ se mantiene por compatibilidad.
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/cemetery_photos", StaticFiles(directory=str(PHOTOS_DIR)), name="cemetery_photos")

# Serve frontend
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
