"""IntentRouter: clasificación de intención por lema (castellano).

Tokeniza la pregunta, localiza el token-núcleo de la relación, comprueba que no
haya señales de otra intención, extrae el sujeto y devuelve `(handler, pregunta
canónica)` para delegar en el QueryRouter. Es deliberadamente conservador: ante
cualquier ambigüedad devuelve None y cede al router de patrones.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

from .lemmas import (
    CANONICAL,
    CORE_LEMMAS,
    LEADING_FILLER,
    OUT_OF_SCOPE,
    TRAILING_FILLER,
)

# Conserva la pista de año "(1900)" como un token propio para que la resolución
# de nombre pueda desambiguar por año.
_TOKEN_RE = re.compile(r"\(\d{4}\)|[a-z0-9']+")


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(_strip_accents((text or "").lower()))


class IntentRouter:
    def classify(self, question: str) -> Optional[Tuple[str, str]]:
        """Devuelve (handler_name, pregunta_canonica) o None si cede al router."""
        toks = _tokens(question)
        if not toks:
            return None

        core = [(i, t) for i, t in enumerate(toks) if t in CORE_LEMMAS]
        if not core:
            return None

        # Más de una intención-núcleo distinta => cadena/ambiguo ("padre de la
        # madre de…"): cedemos.
        intents = {CORE_LEMMAS[t] for _, t in core}
        if len(intents) != 1:
            return None
        intent = next(iter(intents))

        # Cualquier token de otra intención (otro parentesco, cónyuge, conteo,
        # lugar/fecha, extremos…) => cedemos al router de patrones.
        if any(t in OUT_OF_SCOPE for t in toks):
            return None

        # Sujeto = lo que sigue al último núcleo, sin relleno al principio/final.
        tail = toks[core[-1][0] + 1:]
        while tail and tail[0] in LEADING_FILLER:
            tail.pop(0)
        while tail and tail[-1] in TRAILING_FILLER:
            tail.pop()
        if not tail:
            return None

        # Sujeto compuesto "X y Y" => pregunta de pareja: cedemos.
        if "y" in tail or "e" in tail:
            return None

        subject = " ".join(tail)
        handler_name, template = CANONICAL[intent]
        return handler_name, template.format(s=subject)
