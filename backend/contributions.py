"""Aportaciones y consultas no resueltas: almacenamiento PERSISTENTE.

Viven en el volumen de Railway (PHOTOS_DIR/_contrib/), NUNCA en data/ del
repo: cada deploy sustituye data/godesia.db y data/*.jsonl por lo commiteado
y se perdía todo lo enviado desde el último deploy. Mismo patrón que auth.py.

    PHOTOS_DIR/_contrib/contrib.db              tabla suggestions
    PHOTOS_DIR/_contrib/suggestions/<id>/...    adjuntos + submission.json
    PHOTOS_DIR/_contrib/unresolved_queries.jsonl
"""

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

_dir: Path = None


def init(photos_dir):
    global _dir
    _dir = Path(photos_dir) / "_contrib"
    (_dir / "suggestions").mkdir(parents=True, exist_ok=True)
    db = _db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS suggestions ("
        "id TEXT PRIMARY KEY, name TEXT, email TEXT, type TEXT, person_id TEXT, "
        "message TEXT, files_count INTEGER DEFAULT 0, submission_dir TEXT, "
        "created_at TEXT DEFAULT (datetime('now')), resolved_at TEXT)"
    )
    db.commit()
    db.close()
    _seed_recovered()


# Aportaciones perdidas en el deploy del 21/09/2026 (antes vivían en data/ y
# cada deploy las borraba). Recuperadas de los emails de aviso; sin adjuntos.
# INSERT OR IGNORE → se crean una sola vez, luego es inocuo.
_RECOVERED = [
    ("20260920_000001_enric_cabestany", "Enric Cabestany", "enric.cabestany@gmail.com",
     "correccion", "@I500748@",
     "El Josep es el tiet de la Rita, El seu pare es el Miquel Angel Almela Casanova"),
    ("20260920_000002_ernesto_garrido_godes", "Ernesto Garrido Godes", "ernesto.garrido@planificats.com",
     "correccion", "@I500094@", "Eduardo falleció en 2023"),
]


def _seed_recovered():
    marker = _dir / ".seeded_20260921"
    if marker.exists():
        return  # ya sembradas (y quizá borradas a propósito desde el admin)
    for sid, name, email, type_, pid, msg in _RECOVERED:
        d = suggestions_dir() / sid
        if not d.exists():
            d.mkdir(parents=True)
            (d / "submission.json").write_text(json.dumps({
                "id": sid, "name": name, "email": email, "type": type_,
                "person_id": pid, "message": msg, "files": [],
                "context": {"note": "recuperada del email de aviso tras pérdida en deploy"},
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        add_suggestion(sid, name, email, type_, pid, msg, [], created_at="2026-09-20T00:00:00")
    marker.touch()


def _db():
    db = sqlite3.connect(_dir / "contrib.db")
    db.row_factory = sqlite3.Row
    return db


def suggestions_dir() -> Path:
    return _dir / "suggestions"


def queries_path() -> Path:
    return _dir / "unresolved_queries.jsonl"


# ── Suggestions ──────────────────────────────────────────────────────────────

def add_suggestion(submission_id, name, email, type_, person_id, message, files, created_at=None):
    db = _db()
    db.execute(
        "INSERT OR IGNORE INTO suggestions "
        "(id, name, email, type, person_id, message, files_count, submission_dir, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (submission_id, name, email, type_, person_id, message, len(files),
         str(suggestions_dir() / submission_id),
         created_at or datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    db.close()


def list_suggestions(people_db=None):
    """people_db: conexión a godesia.db para resolver el nombre de la persona."""
    db = _db()
    rows = [dict(r) for r in db.execute("SELECT * FROM suggestions ORDER BY created_at DESC")]
    db.close()
    for d in rows:
        d["person_name"] = None
        if d.get("person_id") and people_db is not None:
            pid = "@" + d["person_id"].strip("@") + "@"
            r = people_db.execute("SELECT name FROM people WHERE id=?", (pid,)).fetchone()
            if r:
                d["person_name"] = r[0]
        try:
            meta = json.loads((suggestions_dir() / d["id"] / "submission.json").read_text(encoding="utf-8"))
            d["context"] = meta.get("context") or {}
            d["files"] = meta.get("files") or []
        except Exception:
            d["context"], d["files"] = {}, []
    return rows


def resolve_suggestion(submission_id):
    now = datetime.now().isoformat()
    db = _db()
    db.execute("UPDATE suggestions SET resolved_at=? WHERE id=?", (now, submission_id))
    db.commit()
    db.close()
    return now


def delete_suggestion(submission_id):
    db = _db()
    db.execute("DELETE FROM suggestions WHERE id=?", (submission_id,))
    db.commit()
    db.close()
    sub_dir = suggestions_dir() / submission_id
    if sub_dir.exists():
        shutil.rmtree(sub_dir)


# ── Unresolved queries ───────────────────────────────────────────────────────

def log_query(question, lang="es", user=None):
    now = datetime.now()
    entry = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "question": question,
        "lang": lang,
        "user_name": (user or {}).get("name"),
        "user_email": (user or {}).get("email"),
    }
    with queries_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
