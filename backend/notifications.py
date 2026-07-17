"""Avisos por email al administrador (nuevos registros y aportaciones).

El email de destino se configura en el panel admin (setting `notify_email`,
guardado en godesia.db). Envío best-effort en segundo plano vía `mailer` (Resend):
nunca bloquea ni rompe la petición que lo dispara. Si no hay email configurado o
Resend no está configurado, no hace nada.
"""

import html as _html
import os
import threading

from database import get_setting
from mailer import is_configured, send_email

DEFAULT_NOTIFY_EMAIL = "egodes@vasava.es"

_db_conn = None


def init_notifications(db_conn):
    global _db_conn
    _db_conn = db_conn


def notify_email():
    """Dirección a la que enviar los avisos (setting configurable, con defecto)."""
    if _db_conn is None:
        return os.environ.get("NOTIFY_EMAIL", DEFAULT_NOTIFY_EMAIL)
    return (get_setting(_db_conn, "notify_email", DEFAULT_NOTIFY_EMAIL) or "").strip()


def _admin_url():
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}/admin/" if base else "/admin/"


def _send_async(subject, html):
    """Envía en un hilo aparte para no bloquear la petición (best-effort)."""
    to = notify_email()
    if not to or not is_configured():
        if not is_configured():
            print("[notify] Resend no configurado; aviso NO enviado")
        return

    def _do():
        try:
            send_email(to, subject, html)
        except Exception as e:
            print(f"[notify] Fallo enviando aviso: {e}")

    threading.Thread(target=_do, daemon=True).start()


def notify_new_registration(name, email):
    subject = f"Nuevo registro en Godesia — {name}"
    html = (
        f"<p>Nuevo registro pendiente de aprobación en Godesia:</p>"
        f"<ul>"
        f"<li><strong>Nombre:</strong> {_html.escape(name or '')}</li>"
        f"<li><strong>Email:</strong> {_html.escape(email or '')}</li>"
        f"</ul>"
        f'<p>Apruébalo o recházalo en el panel admin → Usuarios:</p>'
        f'<p><a href="{_admin_url()}">{_admin_url()}</a></p>'
    )
    _send_async(subject, html)


def notify_new_suggestion(name, email, type_, person_id, message):
    who = name or "Anónimo"
    subject = f"Nueva aportación en Godesia — {who}"
    rows = [
        ("Remitente", who),
        ("Email", email or "—"),
        ("Tipo", type_ or "—"),
        ("Persona", person_id or "—"),
    ]
    items = "".join(
        f"<li><strong>{k}:</strong> {_html.escape(str(v))}</li>" for k, v in rows)
    msg = _html.escape((message or "").strip())
    html = (
        f"<p>Nueva aportación desde la página Colaborar:</p>"
        f"<ul>{items}</ul>"
        f"<p><strong>Mensaje:</strong><br>{msg or '—'}</p>"
        f'<p>Gestiónala en el panel admin → Aportaciones:</p>'
        f'<p><a href="{_admin_url()}">{_admin_url()}</a></p>'
    )
    _send_async(subject, html)
