"""IntentRouter: clasificación de intención por familia + reglas (castellano).

Tokeniza la pregunta, detecta la familia de parentesco (debe ser única; dos
familias = cadena/compuesto → cede), elige el handler con las reglas de
modificadores de esa familia, extrae el sujeto y devuelve `(handler, pregunta
canónica)` para delegar en el QueryRouter. Conservador: ante cualquier
ambigüedad devuelve None y cede al router de patrones.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

from .lemmas import (
    ALLOWED_PREFIX,
    COUSINS_TOKENS,
    FAMILIES,
    GLOBAL_CEDE,
    LEADING_FILLER,
    MODIFIERS,
    RULES,
    TRAILING_FILLER,
)

# Conserva la pista de año "(1900)" como token propio para desambiguar por año.
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

        # Familia(s) presentes. Con 'primos', el token 'hermanos' es modificador
        # ("primos hermanos"), no la familia siblings.
        has_cousins = any(t in COUSINS_TOKENS for t in toks)
        families = set()
        for t in toks:
            fam = FAMILIES.get(t)
            if fam is None:
                continue
            if has_cousins and fam == "siblings":
                continue
            families.add(fam)
        # Cero familias o varias (cadena/compuesto): cedemos.
        if len(families) != 1:
            return None
        family = next(iter(families))

        # Guardas globales (conteos, extremos, lugar/fecha, matrimonio…): cede.
        if any(t in GLOBAL_CEDE for t in toks):
            return None

        # El sujeto va DESPUÉS de la relación: si delante del primer término de
        # relación hay algo que no sea palabra función (un nombre propio), es una
        # pregunta sí/no del tipo "¿Era X abuelo de Y?" → cedemos.
        rel_idx = [i for i, t in enumerate(toks) if t in FAMILIES or t in MODIFIERS]
        if any(toks[i] not in ALLOWED_PREFIX for i in range(min(rel_idx))):
            return None

        rules = RULES.get(family)
        if not rules:
            return None
        tokset = set(toks)
        chosen = None
        for requires, forbids, handler, template in rules:
            if requires <= tokset and not (forbids & tokset):
                chosen = (handler, template)
                break
        if not chosen:
            return None
        handler, template = chosen

        # Sujeto = lo que sigue al último token de relación/modificador, sin
        # relleno al principio/final.
        tail = toks[max(rel_idx) + 1:]
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
        return handler, template.format(s=subject)
