"""Cupo mensual de tokens del respaldo Gemini, por usuario y global.

Persistente en el volumen (`PHOTOS_DIR/_contrib/contrib.db`, ver
`contributions.py`): sobrevive a deploys.

- Cada usuario tiene `gemini_user_monthly_tokens` al mes (≈ 10 preguntas), o
  la excepción de `llm_user_budget`. Agotado → espera al día 1 del mes
  siguiente (mes natural en hora del Este de EE. UU., donde están los usuarios).
- `gemini_pool_monthly_tokens` es la bolsa gratuita global que se vigila en
  el admin (gastado vs total). Si se agota, nadie puede preguntar ese mes.
- Se comprueba el cupo ANTES de llamar y se descuenta el uso REAL de
  `usageMetadata` después. Un 429 o un error de red no descuenta nada.
"""

import sqlite3
from datetime import datetime, timezone

import contributions
from database import get_setting

DEFAULTS = {
    "gemini_enabled": "1",
    "gemini_model": "gemini-flash-lite-latest",
    "gemini_user_monthly_tokens": "40000",   # ≈ 10 preguntas de ~4 000 tokens
    "gemini_pool_monthly_tokens": "3000000",
}
FALLBACK_TOKENS_PER_QUESTION = 4000

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/New_York")
except Exception:  # sin tzdata → UTC
    _TZ = timezone.utc


def _now():
    return datetime.now(_TZ)


def current_month():
    return _now().strftime("%Y-%m")


def next_reset(month=None):
    y, m = map(int, (month or current_month()).split("-"))
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return "%04d-%02d-01" % (y, m)


def _db():
    db = contributions._db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS llm_usage ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, month TEXT, user_id TEXT, "
        "user_name TEXT, question TEXT, lang TEXT, model TEXT, prompt_tokens INTEGER DEFAULT 0, "
        "output_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, "
        "anonymized INTEGER DEFAULT 0, status TEXT, error TEXT)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_month ON llm_usage(month, user_id)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS llm_user_budget ("
        "user_id TEXT PRIMARY KEY, monthly_tokens INTEGER NOT NULL, updated_at TEXT)"
    )
    return db


def setting(conn, key):
    return get_setting(conn, key, DEFAULTS[key])


def _int_setting(conn, key):
    try:
        return max(0, int(float(setting(conn, key))))
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def is_enabled(conn):
    return str(setting(conn, "gemini_enabled")).strip() not in ("0", "false", "")


def user_key(user):
    """(user_id, user_name) a partir de request.state.user (None → anon)."""
    if not user:
        return "anon", "Sin sesión"
    return str(user.get("id")), user.get("name") or user.get("email") or str(user.get("id"))


def user_budget(conn, user_id, db=None):
    own = db or _db()
    try:
        row = own.execute("SELECT monthly_tokens FROM llm_user_budget WHERE user_id = ?",
                          (user_id,)).fetchone()
    finally:
        if db is None:
            own.close()
    return int(row["monthly_tokens"]) if row else _int_setting(conn, "gemini_user_monthly_tokens")


def tokens_per_question(db):
    row = db.execute(
        "SELECT AVG(total_tokens) FROM (SELECT total_tokens FROM llm_usage "
        "WHERE status = 'ok' AND total_tokens > 0 ORDER BY id DESC LIMIT 50)").fetchone()
    return int(row[0]) if row and row[0] else FALLBACK_TOKENS_PER_QUESTION


def status(conn, user):
    """Estado del cupo del usuario para el mes en curso."""
    uid, _ = user_key(user)
    month = current_month()
    db = _db()
    try:
        used = db.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM llm_usage WHERE month = ? AND user_id = ?",
            (month, uid)).fetchone()[0]
        pool_used = db.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM llm_usage WHERE month = ?",
            (month,)).fetchone()[0]
        budget = user_budget(conn, uid, db)
        per_q = tokens_per_question(db)
    finally:
        db.close()
    pool = _int_setting(conn, "gemini_pool_monthly_tokens")
    remaining = max(0, min(budget - used, pool - pool_used))
    return {
        "month": month,
        "used_tokens": int(used),
        "budget_tokens": int(budget),
        "remaining_tokens": int(remaining),
        "remaining_questions_est": int(remaining // per_q) if per_q else 0,
        "tokens_per_question_est": per_q,
        "resets_on": next_reset(month),
        "pool_exhausted": pool_used >= pool,
        # Se deja preguntar si queda al menos media pregunta media.
        "can_ask": remaining >= per_q // 2 and remaining > 0,
    }


def record(conn, user, question, lang, model, usage, status_, error=None, anonymized=0):
    uid, uname = user_key(user)
    usage = usage or {}
    db = _db()
    try:
        db.execute(
            "INSERT INTO llm_usage (ts, month, user_id, user_name, question, lang, model, "
            "prompt_tokens, output_tokens, total_tokens, anonymized, status, error) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_now().isoformat(timespec="seconds"), current_month(), uid, uname, question[:1000],
             lang, usage.get("model_version") or model, usage.get("prompt", 0),
             usage.get("output", 0), usage.get("total", 0), anonymized, status_,
             (error or "")[:500] or None))
        db.commit()
    finally:
        db.close()


def set_user_budget(user_id, monthly_tokens):
    db = _db()
    try:
        if monthly_tokens is None:
            db.execute("DELETE FROM llm_user_budget WHERE user_id = ?", (user_id,))
        else:
            db.execute(
                "INSERT INTO llm_user_budget (user_id, monthly_tokens, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET monthly_tokens = excluded.monthly_tokens, "
                "updated_at = excluded.updated_at",
                (user_id, int(monthly_tokens), _now().isoformat(timespec="seconds")))
        db.commit()
    finally:
        db.close()


def usage_report(conn, month=None, users=None):
    """Resumen para el admin. `users` = lista de usuarios aprobados de auth.db."""
    month = month or current_month()
    db = _db()
    try:
        totals = db.execute(
            "SELECT SUM(status != 'blocked') AS n, COALESCE(SUM(total_tokens),0) AS total, "
            "COALESCE(SUM(prompt_tokens),0) AS prompt, COALESCE(SUM(output_tokens),0) AS output, "
            "SUM(status = 'ok') AS ok, SUM(status NOT IN ('ok', 'blocked')) AS failed "
            "FROM llm_usage WHERE month = ?", (month,)).fetchone()
        today = _now().strftime("%Y-%m-%d")
        today_n = db.execute("SELECT COUNT(*) FROM llm_usage WHERE ts LIKE ? AND status != 'blocked'",
                             (today + "%",)).fetchone()[0]
        per_user = {r["user_id"]: dict(r) for r in db.execute(
            "SELECT user_id, MAX(user_name) AS user_name, COUNT(*) AS questions, "
            "SUM(status = 'ok') AS ok, COALESCE(SUM(total_tokens),0) AS used, MAX(ts) AS last_ts "
            "FROM llm_usage WHERE month = ? GROUP BY user_id", (month,))}
        overrides = {r["user_id"]: r["monthly_tokens"] for r in db.execute(
            "SELECT user_id, monthly_tokens FROM llm_user_budget")}
        recent = [dict(r) for r in db.execute(
            "SELECT ts, user_name, question, model, prompt_tokens, output_tokens, total_tokens, "
            "anonymized, status, error FROM llm_usage WHERE month = ? ORDER BY id DESC LIMIT 50",
            (month,))]
        months = [r[0] for r in db.execute(
            "SELECT DISTINCT month FROM llm_usage ORDER BY month DESC LIMIT 24")]
        per_q = tokens_per_question(db)
    finally:
        db.close()
    default_budget = _int_setting(conn, "gemini_user_monthly_tokens")
    rows = []
    seen = set()
    for u in users or []:
        uid = str(u["id"])
        seen.add(uid)
        pu = per_user.get(uid, {})
        rows.append({"user_id": uid, "name": u.get("name") or u.get("email"),
                     "email": u.get("email"), "questions": pu.get("questions", 0),
                     "used": pu.get("used", 0), "last_ts": pu.get("last_ts"),
                     "budget": overrides.get(uid, default_budget),
                     "custom_budget": uid in overrides})
    for uid, pu in per_user.items():
        if uid not in seen:
            rows.append({"user_id": uid, "name": pu.get("user_name"), "email": None,
                         "questions": pu["questions"], "used": pu["used"], "last_ts": pu["last_ts"],
                         "budget": overrides.get(uid, default_budget),
                         "custom_budget": uid in overrides})
    rows.sort(key=lambda r: (-r["used"], (r["name"] or "").lower()))
    return {
        "month": month,
        "months": months if month in months else [month] + months,
        "resets_on": next_reset(month),
        "pool_tokens": _int_setting(conn, "gemini_pool_monthly_tokens"),
        "used_tokens": totals["total"],
        "prompt_tokens": totals["prompt"],
        "output_tokens": totals["output"],
        "questions": totals["n"] or 0,
        "ok": totals["ok"] or 0,
        "failed": totals["failed"] or 0,
        "requests_today": today_n,
        "tokens_per_question_est": per_q,
        "default_user_budget": default_budget,
        "settings": {k: setting(conn, k) for k in DEFAULTS},
        "users": rows,
        "recent": recent,
    }
