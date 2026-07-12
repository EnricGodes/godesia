"""Detección del idioma de una pregunta (es/ca/en/fr/de).

Determina en qué idioma está escrita la pregunta para decidir si hay que
reescribirla a español antes del matching. Es independiente del idioma de la
interfaz (ui_lang), que solo actúa como desempate cuando la señal es débil: un
usuario con la web en catalán puede preguntar en español y viceversa.

Reglas de diseño:
  · Se puntúa por MARCADORES que son tokens (palabras completas), no substrings.
  · Los marcadores fuertes son palabras que NO son español válido (qui, pare,
    germans, neixer…) y valen 2; los débiles/ambiguos valen 1.
  · Los tokens que son nombres reales del árbol (name_tokens) se excluyen del
    conteo: un apellido como "Vila" o "Mora" no debe puntuar como catalán.
  · Si ningún idioma no-español supera el umbral, se devuelve 'es' (garantía de
    que las preguntas españolas nunca se reescriben → 0 regresiones).
"""

from __future__ import annotations

import re
import unicodedata

_TOKEN_RE = re.compile(r"[a-zà-ÿ0-9']+")
DEFAULT_LANG = "es"
_THRESHOLD = 2  # puntuación mínima para aceptar un idioma no-español


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def _tokens(text: str) -> list:
    return _TOKEN_RE.findall(_strip_accents((text or "").lower()))


_ORIG_TOKEN_RE = re.compile(r"[a-zà-ÿ0-9'·]+")


def detect_lang(question: str, ui_lang: str = "es", name_tokens=None,
                lang_markers=None) -> str:
    """Devuelve el código de idioma de la pregunta.

    lang_markers: {lang: (strong:set, weak:set, chars:set)}. `chars` son
    caracteres propios del idioma (p.ej. à/è/ò/ç catalanes, que el español no
    usa); su presencia en un token que no es nombre es señal fuerte.
    """
    if not lang_markers:
        return DEFAULT_LANG
    name_tokens = name_tokens or set()
    lower = (question or "").lower()
    toks = [t for t in _tokens(lower) if t not in name_tokens]
    # Tokens originales (con acentos) que no son nombres, para detectar chars.
    orig = [t for t in _ORIG_TOKEN_RE.findall(lower)
            if _strip_accents(t) not in name_tokens]
    if not toks:
        return DEFAULT_LANG
    tokset = set(toks)

    scores = {}
    for lang, markers in lang_markers.items():
        strong, weak = markers[0], markers[1]
        chars = markers[2] if len(markers) > 2 else set()
        score = 2 * len(tokset & strong) + len(tokset & weak)
        if chars and any(any(c in chars for c in t) for t in orig):
            score += 2
        if score:
            scores[lang] = score
    if not scores:
        return DEFAULT_LANG

    best_lang = max(scores, key=lambda l: (scores[l], l == ui_lang))
    best_score = scores[best_lang]

    if best_score >= _THRESHOLD:
        return best_lang
    # Señal débil (un solo marcador ambiguo): confiar en la UI si aporta señal.
    if ui_lang in scores and ui_lang != DEFAULT_LANG:
        return ui_lang
    return DEFAULT_LANG
