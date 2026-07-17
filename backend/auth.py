"""Autenticación de acceso a la web pública de Godesia.

Todo el contenido (páginas, fotos, APIs de datos) requiere una sesión de un
usuario APROBADO. El registro (nombre + email + contraseña) crea una cuenta en
estado 'pending' hasta que se aprueba desde el panel admin.

Los usuarios viven en una BD SQLite APARTE dentro del volumen persistente de
Railway (PHOTOS_DIR/_auth/auth.db), NUNCA en el repositorio: el repo es público
y data/godesia.db se commitea y se sobrescribe en cada deploy, así que publicar
los hashes ahí y perder las cuentas al desplegar no es opción. Solo stdlib.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

SESSION_COOKIE = "godesia_session"
SESSION_TTL_DAYS = 30
_PBKDF2_ITER = 200_000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PWD = 6

# Interruptor de emergencia (dev local / rescate): desactiva la puerta de acceso.
AUTH_DISABLED = os.getenv("AUTH_DISABLED") == "1"

_db_path = None  # Path a auth.db (se fija en init_auth)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at   TEXT,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


# ── Inicialización / conexión ────────────────────────────────────────────────
def init_auth(photos_dir):
    """Crea (si falta) el dir _auth dentro del volumen y la BD de usuarios."""
    global _db_path
    auth_dir = Path(photos_dir) / "_auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    _db_path = auth_dir / "auth.db"
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _connect():
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now(timezone.utc)


# ── Contraseñas (pbkdf2, stdlib) ─────────────────────────────────────────────
def _hash_password(pwd):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, _PBKDF2_ITER)
    return f"pbkdf2_sha256${_PBKDF2_ITER}${salt.hex()}${dk.hex()}"


def _verify_password(pwd, stored):
    try:
        _algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── Sesiones ─────────────────────────────────────────────────────────────────
def _create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    expires = (_now() + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, expires))
    conn.commit()
    return token


def get_session_user(token):
    """Usuario (dict) de una cookie de sesión válida y APROBADO, o None."""
    if not token or _db_path is None:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.name, u.email, u.status FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND s.expires_at > ?",
            (token, _now().isoformat())).fetchone()
        return dict(row) if (row and row["status"] == "approved") else None
    finally:
        conn.close()


def _revoke_user_sessions(conn, user_id):
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()


# ── Rate limit sencillo en memoria para /login ───────────────────────────────
_login_attempts = {}


def _rate_limited(ip):
    now = time.time()
    q = [t for t in _login_attempts.get(ip, []) if now - t < 300]
    _login_attempts[ip] = q
    return len(q) >= 10


def _record_attempt(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


# ── Rutas públicas de autenticación ──────────────────────────────────────────
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_kwargs(request):
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return dict(httponly=True, samesite="lax", secure=(proto == "https"),
                max_age=SESSION_TTL_DAYS * 86400, path="/")


@auth_router.post("/register")
async def register(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    pwd = payload.get("password") or ""
    if not name or not _EMAIL_RE.match(email):
        raise HTTPException(400, "Nombre o email no válidos.")
    if len(pwd) < _MIN_PWD:
        raise HTTPException(400, f"La contraseña debe tener al menos {_MIN_PWD} caracteres.")
    conn = _connect()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone():
            raise HTTPException(409, "Ya existe una cuenta con ese email.")
        conn.execute(
            "INSERT INTO users(name, email, password_hash, status) VALUES (?,?,?, 'pending')",
            (name, email, _hash_password(pwd)))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "status": "pending"}


@auth_router.post("/login")
async def login(request: Request, payload: dict = Body(...)):
    ip = request.client.host if request.client else "?"
    if _rate_limited(ip):
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
    email = (payload.get("email") or "").strip().lower()
    pwd = payload.get("password") or ""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, password_hash, status FROM users WHERE email = ? COLLATE NOCASE",
            (email,)).fetchone()
        if not row or not _verify_password(pwd, row["password_hash"]):
            _record_attempt(ip)
            raise HTTPException(401, "Email o contraseña incorrectos.")
        if row["status"] == "pending":
            raise HTTPException(403, "Tu acceso está pendiente de aprobación.")
        if row["status"] != "approved":
            raise HTTPException(403, "Tu acceso no está autorizado.")
        token = _create_session(conn, row["id"])
        conn.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, token, **_cookie_kwargs(request))
    return resp


@auth_router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token and _db_path is not None:
        conn = _connect()
        try:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@auth_router.get("/me")
async def me(request: Request):
    user = getattr(request.state, "user", None) or get_session_user(request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(401, "No autenticado.")
    return {"name": user["name"], "email": user["email"]}


# ── Gestión de usuarios (admin; sin protección, como el resto de /api/admin) ──
auth_admin_router = APIRouter(prefix="/api/admin", tags=["admin-users"])

_USER_COLS = "id, name, email, status, created_at, approved_at, last_login_at"


@auth_admin_router.get("/users")
async def list_users(status: str = ""):
    conn = _connect()
    try:
        if status:
            rows = conn.execute(
                f"SELECT {_USER_COLS} FROM users WHERE status = ? ORDER BY created_at DESC",
                (status,)).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_USER_COLS} FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@auth_admin_router.get("/users/pending-count")
async def pending_count():
    conn = _connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
        return {"count": n}
    finally:
        conn.close()


@auth_admin_router.post("/users/{uid}/approve")
async def approve_user(uid: int):
    conn = _connect()
    try:
        conn.execute("UPDATE users SET status = 'approved', approved_at = datetime('now') WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@auth_admin_router.post("/users/{uid}/reject")
async def reject_user(uid: int):
    conn = _connect()
    try:
        conn.execute("UPDATE users SET status = 'rejected' WHERE id = ?", (uid,))
        _revoke_user_sessions(conn, uid)   # revoca sesiones activas
    finally:
        conn.close()
    return {"ok": True}


@auth_admin_router.delete("/users/{uid}")
async def delete_user(uid: int):
    conn = _connect()
    try:
        _revoke_user_sessions(conn, uid)
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# ── Middleware de acceso (debe ejecutarse ANTES que el i18n → registrar último) ─
# Prefijos siempre accesibles sin sesión: auth, admin (decisión del usuario),
# i18n runtime y assets mínimos que la página de login/localización necesita.
_PUBLIC_PREFIXES = (
    "/api/auth/", "/admin", "/api/admin/", "/locales/",
    "/i18n.js", "/footer.js", "/nav.js", "/style.css", "/icons/", "/favicon",
    "/sitemap", "/robots.txt", "/manifest",
)


def _is_login_page(path):
    p = path.lstrip("/")
    parts = p.split("/", 1)
    return parts[0] == "login.html" or (len(parts) == 2 and parts[1] == "login.html")


def _wants_html(request, path):
    if path.endswith(".html") or path == "/":
        return True
    if "/" not in path.lstrip("/"):        # p.ej. "/es" (raíz de idioma sin barra)
        return True
    if path.rstrip("/").split("/")[-1] == "" or path.endswith("/"):
        return True
    return "text/html" in request.headers.get("accept", "")


async def auth_middleware(request, call_next):
    path = request.url.path
    # 1. La BD de auth vive en el volumen público de fotos → NUNCA descargable.
    if path.startswith("/photos/_auth") or path.startswith("/cemetery_photos/_auth"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if AUTH_DISABLED:
        return await call_next(request)
    # 2. Rutas públicas / página de login.
    if path.startswith(_PUBLIC_PREFIXES) or _is_login_page(path):
        return await call_next(request)
    # 3. Sesión válida y aprobada.
    user = get_session_user(request.cookies.get(SESSION_COOKIE))
    if user:
        request.state.user = user
        return await call_next(request)
    # 4. Sin acceso: página → redirige al login localizado; API/asset → 401.
    if _wants_html(request, path):
        try:
            from i18n import choose_lang, active_codes
            lang = choose_lang(request, active_codes())
        except Exception:
            lang = "es"
        return RedirectResponse(f"/{lang}/login.html", status_code=302)
    return JSONResponse({"error": "unauthorized"}, status_code=401)
