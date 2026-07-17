"""Envío de emails transaccionales vía Resend (https://resend.com).

Solo stdlib (urllib): funciona en Railway sin instalar `requests`. Best-effort:
nunca lanza excepción, devuelve True/False y registra los fallos.

Variables de entorno:
- RESEND_API_KEY : obligatoria para enviar (si falta, no se envía nada).
- RESEND_FROM    : remitente, p.ej. "Godesia <no-reply@tudominio.com>".
                   Por defecto usa el dominio de pruebas de Resend
                   (onboarding@resend.dev), que SOLO entrega al email de la
                   cuenta de Resend; para producción hay que verificar un dominio.
"""

import json
import os
import urllib.error
import urllib.request

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "Godesia <onboarding@resend.dev>"


def is_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY"))


def send_email(to: str, subject: str, html: str) -> bool:
    """Envía un email HTML. Devuelve True si Resend lo aceptó."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("[mailer] RESEND_API_KEY no configurada; email NO enviado")
        return False
    sender = os.environ.get("RESEND_FROM", DEFAULT_FROM)
    payload = json.dumps({
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL, data=payload, method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # La API de Resend está tras Cloudflare, que bloquea el User-Agent
            # por defecto de urllib ("Python-urllib/x.y") con error 1010. Con un
            # User-Agent propio la petición pasa.
            "User-Agent": "Godesia-Mailer/1.0 (+https://godes.org)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"[mailer] Resend devolvió {e.code}: {body}")
        return False
    except Exception as e:
        print(f"[mailer] Envío falló: {e}")
        return False
