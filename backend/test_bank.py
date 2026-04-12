"""Test bank para regression testing del QueryRouter de Godesia.

Gestiona un banco persistente de test cases en JSON:
- Añadir preguntas en batch
- Ejecutar y comparar respuestas
- Detectar regresiones vs snapshots aprobados
- Bootstrap automático desde patrones del router
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


BANK_PATH = Path(__file__).parent.parent / "data" / "test_bank.json"
MAX_HISTORY = 25


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    answer: str
    handler: str
    people_mentioned: list
    status: int
    ran_at: str
    run_id: str


@dataclass
class Snapshot:
    answer: str
    handler: str
    people_mentioned: list
    approved_at: str


@dataclass
class TestCase:
    id: str
    question: str
    tags: list
    verdict: str  # pending | approved | rejected
    created_at: str
    updated_at: str
    approved_snapshot: Optional[dict] = None
    last_run: Optional[dict] = None
    history: list = field(default_factory=list)


def _normalize_answer(text: str) -> str:
    """Normalize answer for comparison: strip HTML, collapse whitespace, lowercase."""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _classify_case(case: dict) -> str:
    """Classify a test case into: regression, stable, pending, rejected, new, improvement."""
    verdict = case.get("verdict", "pending")
    last_run = case.get("last_run")
    snapshot = case.get("approved_snapshot")

    # Rejected cases: either "improvement" (if last_run shows valid answer) or "rejected"
    if verdict == "rejected":
        if last_run and not case.get("improvement_reviewed"):
            answer = last_run.get("answer", "")
            if answer and "No he sabido responder" not in answer:
                return "improvement"  # Rejected case that now works!
        return "rejected"  # Always rejected if not an improvement

    if verdict == "approved" and snapshot and last_run:
        old = _normalize_answer(snapshot.get("answer", ""))
        new = _normalize_answer(last_run.get("answer", ""))
        if old != new or last_run.get("status") != 200:
            return "regression"
        return "stable"

    if not last_run:
        return "new"

    return "pending"


# ---------------------------------------------------------------------------
# Bank I/O
# ---------------------------------------------------------------------------

def _load_bank() -> dict:
    if BANK_PATH.exists():
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cases": [], "last_run_id": None, "last_run_at": None}


def _save_bank(bank: dict):
    BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)


def _normalized_question(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_bank() -> dict:
    """Return the full bank with classification for each case."""
    bank = _load_bank()
    for case in bank["cases"]:
        case["_classification"] = _classify_case(case)
    return bank


def get_stats() -> dict:
    """Return summary statistics."""
    bank = _load_bank()
    stats = {"total": 0, "stable": 0, "regression": 0, "pending": 0,
             "rejected": 0, "new": 0, "last_run_id": bank.get("last_run_id"),
             "last_run_at": bank.get("last_run_at")}
    for case in bank["cases"]:
        cls = _classify_case(case)
        stats["total"] += 1
        stats[cls] = stats.get(cls, 0) + 1
    return stats


def add_questions(questions: List[str], tags: List[str] = None) -> dict:
    """Add questions in batch. Skip duplicates. Return counts."""
    bank = _load_bank()
    existing = {_normalized_question(c["question"]) for c in bank["cases"]}
    added = 0
    skipped = 0
    now = datetime.now().isoformat()

    for q in questions:
        q = q.strip()
        if not q:
            continue
        nq = _normalized_question(q)
        if nq in existing:
            skipped += 1
            continue
        case = {
            "id": f"tc_{uuid.uuid4().hex[:8]}",
            "question": q,
            "tags": tags or [],
            "verdict": "pending",
            "created_at": now,
            "updated_at": now,
            "approved_snapshot": None,
            "last_run": None,
            "history": [],
        }
        bank["cases"].append(case)
        existing.add(nq)
        added += 1

    _save_bank(bank)
    return {"added": added, "skipped": skipped, "total": len(bank["cases"])}


def set_verdict(case_id: str, verdict: str) -> dict:
    """Set verdict for a case: approved, rejected, or pending."""
    bank = _load_bank()
    now = datetime.now().isoformat()

    for case in bank["cases"]:
        if case["id"] == case_id:
            old_classification = _classify_case(case)
            case["verdict"] = verdict
            case["updated_at"] = now

            # If rejecting a case that was marked as "improvement", flag it as reviewed
            if verdict == "rejected" and old_classification == "improvement":
                case["improvement_reviewed"] = True
            # Clear the improvement_reviewed flag when approving
            elif verdict == "approved" and case.get("improvement_reviewed"):
                case.pop("improvement_reviewed", None)

            if verdict == "approved" and case.get("last_run"):
                case["approved_snapshot"] = {
                    "answer": case["last_run"]["answer"],
                    "handler": case["last_run"]["handler"],
                    "people_mentioned": case["last_run"]["people_mentioned"],
                    "approved_at": now,
                }
            _save_bank(bank)
            case["_classification"] = _classify_case(case)
            return case

    return None


def delete_cases(case_ids: List[str]) -> int:
    """Delete cases by IDs. Return count deleted."""
    bank = _load_bank()
    before = len(bank["cases"])
    bank["cases"] = [c for c in bank["cases"] if c["id"] not in set(case_ids)]
    deleted = before - len(bank["cases"])
    _save_bank(bank)
    return deleted


def run_tests(router, mode: str = "all", case_ids: List[str] = None) -> dict:
    """Execute tests. mode: all | new | regressions | selected.
    Returns run summary."""
    bank = _load_bank()
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    executed = 0
    regressions = 0

    for case in bank["cases"]:
        # Filter which cases to run
        cls = _classify_case(case)
        if mode == "new" and case.get("last_run"):
            continue
        if mode == "regressions" and cls != "regression":
            continue
        if mode == "selected" and case_ids and case["id"] not in case_ids:
            continue

        # Execute
        try:
            result = router.route(case["question"])
            answer = result.get("answer", "") if result else ""
            handler = result.get("_handler", "") if result else ""
            people = result.get("people_mentioned", []) if result else []
            status = 200
        except Exception as e:
            answer = f"ERROR: {e}"
            handler = ""
            people = []
            status = 500

        run_result = {
            "answer": answer,
            "handler": handler,
            "people_mentioned": people,
            "status": status,
            "ran_at": now,
            "run_id": run_id,
        }

        # Update history
        if case.get("last_run"):
            case.setdefault("history", []).insert(0, case["last_run"])
            case["history"] = case["history"][:MAX_HISTORY]

        case["last_run"] = run_result
        case["updated_at"] = now
        executed += 1

        # Check regression
        new_cls = _classify_case(case)
        if new_cls == "regression":
            regressions += 1

    bank["last_run_id"] = run_id
    bank["last_run_at"] = now
    _save_bank(bank)

    return {
        "run_id": run_id,
        "executed": executed,
        "regressions": regressions,
        "total": len(bank["cases"]),
    }


def bootstrap_from_router(router) -> dict:
    """Auto-generate test cases from the router's pattern list.
    Uses real person names from the database."""
    conn = router.conn

    # Get diverse sample of real names
    rows = conn.execute("""
        SELECT name FROM people
        WHERE name IS NOT NULL AND name != ''
        ORDER BY RANDOM() LIMIT 15
    """).fetchall()
    names = [r[0] for r in rows]
    if not names:
        return {"added": 0, "error": "No people in database"}

    # Get a couple name for couple-related patterns
    couple_row = conn.execute("""
        SELECT p1.name, p2.name FROM marriages m
        JOIN people p1 ON p1.id = m.person1_id
        JOIN people p2 ON p2.id = m.person2_id
        WHERE p1.name IS NOT NULL AND p2.name IS NOT NULL
        LIMIT 1
    """).fetchone()
    couple = (couple_row[0], couple_row[1]) if couple_row else (names[0], names[1] if len(names) > 1 else names[0])

    # Get a place
    place_row = conn.execute(
        "SELECT birth_place FROM people WHERE birth_place IS NOT NULL AND birth_place != '' LIMIT 1"
    ).fetchone()
    place = place_row[0] if place_row else "Barcelona"

    # Get a surname
    surname_row = conn.execute(
        "SELECT surname FROM people WHERE surname IS NOT NULL AND surname != '' LIMIT 1"
    ).fetchone()
    surname = surname_row[0].split()[0] if surname_row else "Godes"

    questions = []
    name = names[0]
    name2 = names[1] if len(names) > 1 else names[0]

    # Generate questions based on common pattern categories
    templates = [
        # Family
        f"Quienes eran los padres de {name}?",
        f"Quien era el padre de {name}?",
        f"Quien era la madre de {name}?",
        f"Que hermanos tenia {name}?",
        f"Cuantos hermanos tenia {name}?",
        f"Que hijos tuvo {name}?",
        f"Cuantos hijos tuvo {name}?",
        f"Con quien se caso {name}?",
        # Extended family
        f"Quienes eran los abuelos de {name}?",
        f"Quien era el abuelo paterno de {name}?",
        f"Quien era la abuela materna de {name}?",
        f"Quienes eran los bisabuelos de {name}?",
        f"Tios y tias de {name}",
        f"Primos hermanos de {name}",
        # In-laws
        f"Suegros de {name}",
        f"Nueras de {name}",
        f"Yernos de {name}",
        f"Cunados de {name}",
        # Life events
        f"Donde nacio {name}?",
        f"Cuando murio {name}?",
        f"Donde murio {name}?",
        f"En que trabajaba {name}?",
        f"Donde vivia {name}?",
        f"Ultima residencia de {name}",
        f"Notas biograficas de {name}",
        # Relationship
        f"Que parentesco hay entre {name} y {name2}?",
        f"Quien es mayor, {name} o {name2}?",
        # Stats
        f"Que persona tuvo mas hijos?",
        f"Quien vivio mas anos?",
        f"Cual es la media de hijos?",
        f"Hay mas hombres o mujeres en el arbol?",
        # Search
        f"Que personas nacieron en {place}?",
        f"Quien nacio en 1920?",
        f"Que personas tienen {surname} como primer apellido?",
        f"Cuantas personas se llaman {name.split()[0]}?",
        # Couple
        f"Cuantos hijos tuvieron {couple[0]} y {couple[1]}?",
        # Age
        f"A que edad se caso {name}?",
        f"A que edad tuvo su primer hijo {name}?",
        f"Ranking de longevidad de {name}",
        # Descendants
        f"Tiene descendencia documentada {name}?",
        f"Ranking de descendencia de {name}",
    ]

    # Add more names for variety
    for n in names[2:8]:
        templates.extend([
            f"Hijos de {n}",
            f"Padres de {n}",
            f"Donde nacio {n}?",
        ])

    questions = templates
    result = add_questions(questions, tags=["bootstrap"])

    # Now run them all
    if result["added"] > 0:
        run_result = run_tests(router, mode="new")
        result["run"] = run_result

    return result


def export_bank() -> dict:
    """Export the full bank for download."""
    return _load_bank()


def import_bank(data: dict) -> dict:
    """Import a bank from uploaded JSON. Merges with existing."""
    bank = _load_bank()
    existing = {_normalized_question(c["question"]) for c in bank["cases"]}
    added = 0

    for case in data.get("cases", []):
        nq = _normalized_question(case.get("question", ""))
        if nq and nq not in existing:
            bank["cases"].append(case)
            existing.add(nq)
            added += 1

    _save_bank(bank)
    return {"added": added, "total": len(bank["cases"])}
