"""FastAPI server para Godesia - consulta genealógica en lenguaje natural."""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import (
    get_connection, get_tree_data, get_birthdays_this_week, search_people,
    get_dashboard_data,
)
from query_router import QueryRouter
from query_engine import QueryEngine

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


@app.on_event("startup")
async def startup():
    global db_conn, router, engine
    if not DB_PATH.exists():
        raise RuntimeError(f"No se encuentra {DB_PATH}. Ejecuta primero migrate_json_to_sqlite.py")
    db_conn = get_connection(str(DB_PATH))
    router = QueryRouter(db_conn)
    count = db_conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    print(f"SQLite cargado: {count} personas")

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


@app.post("/api/query")
async def query(req: QueryRequest):
    """Intenta responder desde SQLite. Si no puede, pide confirmación para usar LLM."""
    if not router:
        raise HTTPException(status_code=503, detail="Motor no inicializado")

    # Try direct DB answer
    result = router.route(req.question)
    if result:
        return result

    # Can't answer from DB — ask user to confirm LLM use
    estimated_cost = 0.3  # céntimos de euro (aproximado)
    return {
        "requires_llm": True,
        "estimated_cost": estimated_cost,
        "message": "Esta consulta necesita inteligencia artificial. Coste estimado: %.1f céntimos. ¿Quieres proceder?" % estimated_cost,
    }


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
async def search(q: str = Query(..., min_length=2)):
    """Buscar personas por nombre."""
    if not db_conn:
        raise HTTPException(status_code=503, detail="BD no inicializada")
    results = search_people(db_conn, q, limit=20)
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


# Serve photos
if PHOTOS_DIR.exists():
    app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")

# Serve frontend
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
