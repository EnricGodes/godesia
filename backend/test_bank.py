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


def generate_questions(conn, per_type: int = 40) -> List[str]:
    """Generate natural Spanish questions from real people who actually have the
    data the question asks about (so every question has a verifiable answer)."""

    def names_for(sql: str) -> list:
        rows = conn.execute(sql + f" ORDER BY RANDOM() LIMIT {per_type}").fetchall()
        return [r[0] for r in rows if r[0]]

    # Personas con padre/madre conocidos (para parentescos ascendentes y laterales)
    with_parents = names_for(
        "SELECT name FROM people WHERE name != '' AND (father_id IS NOT NULL OR mother_id IS NOT NULL)")
    with_father = names_for("SELECT name FROM people WHERE name != '' AND father_id IS NOT NULL")
    with_mother = names_for("SELECT name FROM people WHERE name != '' AND mother_id IS NOT NULL")
    # Personas con hijos (para hijos/nietos)
    with_children = names_for(
        "SELECT DISTINCT p.name FROM people p JOIN children c ON c.parent_id = p.id WHERE p.name != ''")
    # Abuelos conocidos: personas cuyo padre tiene padre
    with_grandparents = names_for("""
        SELECT p.name FROM people p
        JOIN people f ON f.id = p.father_id
        WHERE p.name != '' AND f.father_id IS NOT NULL""")
    # Personas casadas
    married = names_for("""
        SELECT p.name FROM people p WHERE p.name != '' AND p.id IN (
            SELECT person1_id FROM marriages UNION SELECT person2_id FROM marriages)""")
    # Con lugar de nacimiento / muerte
    with_birth = names_for("SELECT name FROM people WHERE name != '' AND birth_place IS NOT NULL AND birth_place != ''")
    with_death = names_for("SELECT name FROM people WHERE name != '' AND death_place IS NOT NULL AND death_place != ''")
    # Con tíos: personas cuyo padre/madre tiene hermanos → sirve para primos/sobrinos/tíos
    with_uncles = names_for("""
        SELECT p.name FROM people p JOIN children c1 ON c1.child_id = p.father_id
        JOIN children c2 ON c2.parent_id = c1.parent_id AND c2.child_id != p.father_id
        WHERE p.name != ''""")

    qs = []
    # Conjunto-de-personas (verificables por el oráculo)
    qs += [f"¿Quiénes eran los padres de {n}?" for n in with_parents]
    qs += [f"¿Quién era el padre de {n}?" for n in with_father[:per_type // 2]]
    qs += [f"¿Quién era la madre de {n}?" for n in with_mother[:per_type // 2]]
    qs += [f"¿Quiénes eran los hermanos de {n}?" for n in with_parents]
    qs += [f"¿Qué hijos tuvo {n}?" for n in with_children]
    qs += [f"¿Quiénes son los nietos de {n}?" for n in with_children[:per_type // 2]]
    qs += [f"¿Con quién se casó {n}?" for n in married]
    qs += [f"¿Quiénes eran los abuelos de {n}?" for n in with_grandparents]
    qs += [f"¿Quién era el abuelo paterno de {n}?" for n in with_grandparents[:per_type // 2]]
    qs += [f"¿Quiénes eran los tíos de {n}?" for n in with_uncles]
    qs += [f"¿Quiénes son los primos de {n}?" for n in with_uncles]
    qs += [f"¿Quiénes son los sobrinos de {n}?" for n in with_children[:per_type // 2]]
    # Datos vitales
    qs += [f"¿Dónde nació {n}?" for n in with_birth]
    qs += [f"¿Dónde murió {n}?" for n in with_death]
    return qs


def bootstrap_from_router(router) -> dict:
    """Auto-generate test cases from real DB people and run them."""
    questions = generate_questions(router.conn)
    if not questions:
        return {"added": 0, "error": "No people in database"}
    result = add_questions(questions, tags=["generated"])
    if result["added"] > 0:
        result["run"] = run_tests(router, mode="new")
    return result


def auto_review(router) -> dict:
    """Automated QA: run all cases, then verify each against the database oracle.
    - oracle PASS  → approve (snapshot from last_run), tag 'auto-verified'
    - oracle FAIL  → reject, store reason, tag 'oracle-fail' (real router bugs)
    - UNVERIFIABLE → baseline: approve as reference if it has a valid answer and
      wasn't already approved (frozen line, marked 'baseline-unverified'); keep
      regressions flagged.
    Returns a summary including the list of oracle failures.
    """
    import test_oracle

    run = run_tests(router, mode="all")
    bank = _load_bank()
    now = datetime.now().isoformat()
    summary = {"run_id": run["run_id"], "total": 0, "verified_ok": 0,
               "oracle_fail": [], "baseline": 0, "regressions": 0, "unverifiable": 0}

    for case in bank["cases"]:
        summary["total"] += 1
        # Estado de oráculo previo: se recalcula desde cero esta corrida
        case["tags"] = [t for t in case.get("tags", []) if t != "oracle-fail"]
        case.pop("oracle_reason", None)
        result, detail = test_oracle.verify(router, case)
        last = case.get("last_run") or {}

        def _approve(tag):
            case["verdict"] = "approved"
            case["updated_at"] = now
            case.pop("improvement_reviewed", None)
            case["approved_snapshot"] = {
                "answer": last.get("answer", ""),
                "handler": last.get("handler", ""),
                "people_mentioned": last.get("people_mentioned", []),
                "approved_at": now,
            }
            tags = [t for t in case.get("tags", []) if t != "oracle-fail"]
            if tag not in tags:
                tags.append(tag)
            case["tags"] = tags
            case.pop("oracle_reason", None)

        if result == test_oracle.PASS:
            _approve("auto-verified")
            summary["verified_ok"] += 1
        elif result == test_oracle.FAIL:
            case["verdict"] = "rejected"
            case["updated_at"] = now
            case["oracle_reason"] = detail
            if "oracle-fail" not in case.get("tags", []):
                case.setdefault("tags", []).append("oracle-fail")
            summary["oracle_fail"].append({"id": case["id"], "question": case["question"],
                                           "reason": detail})
        else:  # UNVERIFIABLE → línea base congelada (no hay verdad calculable)
            summary["unverifiable"] += 1
            answer = last.get("answer", "")
            valid = last.get("status") == 200 and answer and "No he sabido responder" not in answer
            if not valid:
                # Respuesta rota: si estaba aprobada es una regresión REAL a mirar
                if case.get("verdict") == "approved":
                    summary["regressions"] += 1
            elif case.get("verdict") == "approved":
                snap = _normalize_answer((case.get("approved_snapshot") or {}).get("answer", ""))
                if snap != _normalize_answer(answer):
                    _approve("baseline-refrozen")  # benigna: recongela la línea base
                    summary["baseline"] += 1
            else:
                _approve("baseline-unverified")
                summary["baseline"] += 1

    _save_bank(bank)
    return summary


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
