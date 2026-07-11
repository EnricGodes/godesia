"""Plantillas de respuesta del QueryRouter por idioma.

Las frases viven en backend/answers/answers_{lang}.json con placeholders
{a}, {b}, ... (generadas por scripts/externalize_router_strings.py; el español
es la fuente). Cadena de fallback: idioma pedido → español → la propia clave.

La sustitución de placeholders es por regex (no str.format) para que el texto
de las plantillas pueda contener llaves sin escapar.
"""

import json
import re
from pathlib import Path

DEFAULT_LANG = "es"
_DIR = Path(__file__).parent / "answers"
_cache = {}
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _load(lang):
    if lang not in _cache:
        path = _DIR / f"answers_{lang}.json"
        try:
            _cache[lang] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _cache[lang] = {}
    return _cache[lang]


def render(key, lang=DEFAULT_LANG, **kwargs):
    template = _load(lang).get(key)
    if template is None and lang != DEFAULT_LANG:
        template = _load(DEFAULT_LANG).get(key)
    if template is None:
        # No debería ocurrir: las claves se generan junto al código
        return key
    if kwargs:
        template = _PLACEHOLDER_RE.sub(
            lambda m: str(kwargs[m.group(1)]) if m.group(1) in kwargs else m.group(0),
            template,
        )
    return template


def available_langs():
    return sorted(p.stem.replace("answers_", "") for p in _DIR.glob("answers_*.json"))


def invalidate_cache():
    _cache.clear()
