"""FastAPI server para Godesia - consulta genealógica en lenguaje natural."""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import (
    get_connection, get_tree_data, get_birthdays_this_week, search_people,
    get_dashboard_data, get_documents, get_person_dossier, convert_date_to_spanish,
    update_all_photo_files, get_photo_details,
)
from query_router import QueryRouter
from query_engine import QueryEngine
import test_bank

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = DATA_DIR / "photos"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = DATA_DIR / "godesia.db"

app = FastAPI(title="Godesia", description="Consulta genealógica en lenguaje natural")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db_conn = None
router = None
engine = None
gedcom_export_date = None


@app.on_event("startup")
async def startup():
    global db_conn, router, engine, gedcom_export_date
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

    # Read GEDCOM export date from header
    gedcom_path = BASE_DIR / "docs" / "site380341641-tree5-20260324_signed.ged"
    if gedcom_path.exists():
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
    return dossier_data


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

@app.get("/api/tests/bank/export")
async def export_test_bank():
    return test_bank.export_bank()

@app.post("/api/tests/bank/import")
async def import_test_bank(req: ImportBankRequest):
    return test_bank.import_bank(req.data)


# Serve photos
if PHOTOS_DIR.exists():
    app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")

# Serve frontend
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
