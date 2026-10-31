"""Cliente mínimo de la API de Gemini (Google AI Studio), solo stdlib.

Se usa como respaldo cuando el QueryRouter no sabe responder. Pensado para el
TIER GRATUITO: Google puede usar los datos enviados, así que el llamante
(`llm_anonymizer`) se encarga de que los vivos vayan anonimizados.

Variables de entorno:
- GEMINI_API_KEY : obligatoria. En local se lee también del `.env` de la raíz
                   del repo (gitignored) si no está en el entorno.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-flash-lite-latest"   # alias del Flash Lite vigente
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class GeminiError(Exception):
    """Fallo de la llamada (red, respuesta vacía, error de la API)."""


class GeminiRateLimited(GeminiError):
    """429: límite del tier gratuito (por minuto o por día)."""


def api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key or not _ENV_FILE.exists():
        return key
    try:
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def is_configured():
    return bool(api_key())


def _thinking_config(model):
    # Los 2.x usan thinkingBudget; los 3.x (y los alias *-latest) thinkingLevel.
    if model.startswith("gemini-2."):
        return {"thinkingBudget": 0}
    return {"thinkingLevel": "minimal"}


def generate(system, contents, model=DEFAULT_MODEL, max_output_tokens=800, timeout=60):
    """Llama a generateContent. `contents` = [{"role": "user"|"model", "text": ...}].

    Devuelve (texto, usage) con usage = {prompt, output, total} en tokens.
    """
    key = api_key()
    if not key:
        raise GeminiError("GEMINI_API_KEY no configurada")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": c["role"], "parts": [{"text": c["text"]}]} for c in contents],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
            "thinkingConfig": _thinking_config(model),
        },
    }
    req = urllib.request.Request(
        API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
            # urllib sin User-Agent propio lo bloquean algunos frentes (Cloudflare 1010).
            "User-Agent": "Godesia/1.0 (+https://godes.org)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code == 429:
            raise GeminiRateLimited(detail or "rate limited")
        raise GeminiError(f"HTTP {e.code}: {detail[:300]}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GeminiError(f"red: {e}")

    meta = data.get("usageMetadata") or {}
    usage = {
        "prompt": int(meta.get("promptTokenCount") or 0),
        "output": int(meta.get("candidatesTokenCount") or 0) + int(meta.get("thoughtsTokenCount") or 0),
        "total": int(meta.get("totalTokenCount") or 0),
        "model_version": data.get("modelVersion") or model,
    }
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except (KeyError, IndexError, TypeError):
        reason = (data.get("promptFeedback") or {}).get("blockReason") or "respuesta vacía"
        err = GeminiError(f"sin respuesta: {reason}")
        err.usage = usage
        raise err
    return text, usage
