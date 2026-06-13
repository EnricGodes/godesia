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
    COMPOUND_RULES,
    COUNT_LIST_FAMILIES,
    COUNT_WORDS,
    COUSINS_TOKENS,
    FAMILIES,
    GLOBAL_CEDE,
    LEADING_FILLER,
    MODIFIERS,
    RULES,
    TRAILING_FILLER,
    TRAILING_PHRASES,
)


def _strip_trailing_phrases(toks):
    for phrase in TRAILING_PHRASES:
        if len(toks) > len(phrase) and toks[-len(phrase):] == phrase:
            return toks[:-len(phrase)]
    return toks

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
    def __init__(self, name_tokens=None):
        # Conjunto de tokens que aparecen en nombres reales del árbol. Se usa para
        # el guard de prefijo: si delante de la relación hay un nombre (p.ej. "¿Era
        # Francesc abuelo de Y?") cedemos; los preámbulos coloquiales ("me podrías
        # decir", "a ver", "según consta") no son nombres y se ignoran solos.
        self.name_tokens = name_tokens or set()

    def _subject(self, toks, rel_tokens) -> Optional[str]:
        """Sujeto = lo que sigue al último token de relación, sin relleno; None si
        delante de la relación hay un nombre del árbol, o si el sujeto queda vacío
        o es una pareja 'X y Y'."""
        rel_idx = [i for i, t in enumerate(toks) if t in rel_tokens]
        if not rel_idx:
            return None
        prefix = toks[:min(rel_idx)]
        if any(t in self.name_tokens and t not in ALLOWED_PREFIX for t in prefix):
            return None
        tail = toks[max(rel_idx) + 1:]
        while tail and tail[0] in LEADING_FILLER:
            tail.pop(0)
        # Quita coletillas de cola ("…a lo largo de su vida") y adverbios sueltos.
        for phrase in TRAILING_PHRASES:
            if len(tail) > len(phrase) and tail[-len(phrase):] == phrase:
                tail = tail[:-len(phrase)]
                break
        while tail and tail[-1] in TRAILING_FILLER:
            tail.pop()
        if not tail or "y" in tail or "e" in tail:
            return None
        return " ".join(tail)

    def classify(self, question: str) -> Optional[Tuple[str, str]]:
        """Devuelve (handler_name, pregunta_canonica) o None si cede al router."""
        toks = _tokens(question)
        if not toks:
            return None
        # Quita coletillas de cola ANTES de detectar familias, para que p.ej.
        # "…por parte de padre" no cuente 'padre' como familia (cadena falsa).
        toks = _strip_trailing_phrases(toks)
        tokset = set(toks)

        # Compuestos (tío abuelo, sobrino nieto) ANTES del guard de familias.
        for any_a, any_b, handler, template in COMPOUND_RULES:
            if (any_a & tokset) and (any_b & tokset):
                subject = self._subject(toks, any_a | any_b)
                if subject:
                    return handler, template.format(s=subject)
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

        # Guardas globales (conteos, extremos, lugar/fecha…): cede. Excepción: una
        # pregunta de SOLO conteo ("cuántos nietos…") sobre una familia sin handler
        # de conteo se responde listando (no cede).
        cede_hits = [t for t in tokset if t in GLOBAL_CEDE]
        if cede_hits:
            only_count = all(t in COUNT_WORDS for t in cede_hits)
            if not (only_count and family in COUNT_LIST_FAMILIES):
                return None

        rules = RULES.get(family)
        if not rules:
            return None
        chosen = None
        for req_all, req_any, forbids, handler, template in rules:
            if not (req_all <= tokset):
                continue
            if req_any and not (req_any & tokset):
                continue
            if forbids & tokset:
                continue
            chosen = (handler, template)
            break
        if not chosen:
            return None
        handler, template = chosen

        # Sujeto tras la relación (el helper aplica el guard de prefijo: si delante
        # hay un nombre, p.ej. "¿Era X abuelo de Y?", cede).
        subject = self._subject(toks, set(FAMILIES) | MODIFIERS)
        if subject is None:
            return None
        return handler, template.format(s=subject)
