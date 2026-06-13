"""IntentRouter (modelo por INCLUSIÓN).

De cada pregunta aísla solo dos cosas y descarta el resto por no ser ninguna:
  · SUJETO    = la tirada de tokens que son nombres reales del árbol (name_tokens).
  · INTENCIÓN = un token cuya raíz está en INTENT_ROOTS (los nombres ganan: un
                token que es nombre nunca se interpreta como intención).
Devuelve (handler, pregunta canónica) para delegar en el QueryRouter, o None para
ceder al router de patrones. No usa listas de muletillas/coletillas: lo que no es
nombre ni intención (ni modificador/desambiguador) simplemente no se mira.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

from .lemmas import (
    COMPOUND_RULES,
    COUNT_LIST_FAMILIES,
    COUNT_WORDS,
    COUSINS_TOKENS,
    GLOBAL_CEDE,
    NON_NAME_TOKENS,
    RULES,
    family_of,
)

# Tokeniza; conserva la pista de año "(1900)" como token propio.
_TOKEN_RE = re.compile(r"\(\d{4}\)|[a-z0-9']+")
_YEAR_RE = re.compile(r"\(\d{4}\)")


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(_strip_accents((text or "").lower()))


class IntentRouter:
    def __init__(self, name_tokens=None):
        # Tokens (≥3 letras) que aparecen en nombres reales del árbol.
        self.name_tokens = name_tokens or set()

    def _name_runs(self, toks):
        """Tiradas contiguas de tokens-nombre, como (índice_inicio, texto)."""
        runs, cur, start = [], [], None
        for i, t in enumerate(toks):
            is_name = t in self.name_tokens and t not in NON_NAME_TOKENS
            is_year = bool(_YEAR_RE.fullmatch(t))
            if is_name or (is_year and cur):
                if not cur:
                    start = i
                cur.append(t)
            elif cur:
                runs.append((start, " ".join(cur)))
                cur = []
        if cur:
            runs.append((start, " ".join(cur)))
        return runs

    def classify(self, question: str) -> Optional[Tuple[str, str]]:
        """Devuelve (handler_name, pregunta_canonica) o None si cede al router."""
        toks = _tokens(question)
        if not toks:
            return None
        tokset = set(toks)
        runs = self._name_runs(toks)
        run_starts = [s for s, _ in runs]
        run_texts = [t for _, t in runs]

        # Compuestos (tío abuelo, sobrino nieto) ANTES del guard de familias.
        for any_a, any_b, handler, template in COMPOUND_RULES:
            if (any_a & tokset) and (any_b & tokset):
                return (handler, template.format(s=run_texts[0])) if len(runs) == 1 else None

        # Posiciones de los tokens de relación (por raíz). Un nombre real nunca es
        # intención; con 'primos', 'hermanos' es modificador, no siblings.
        has_cousins = any(t in COUSINS_TOKENS for t in toks)
        fam_pos = []
        for i, t in enumerate(toks):
            if t in self.name_tokens:
                continue
            fam = family_of(t)
            if fam is None or (fam == "siblings" and has_cousins):
                continue
            fam_pos.append((i, fam))
        if not fam_pos:
            return None

        # La intención es la relación que POSEE el nombre (una tirada arranca tras
        # ella, antes de la siguiente relación). Una relación SIN nombre detrás es
        # un cualificador ("…por parte de padre", "…en su bautizo") → se ignora; si
        # va ANTES de la que posee el nombre, es una cadena ("padre de la madre de
        # X") → se cede.
        owning, non_owning = [], []
        for k, (i, fam) in enumerate(fam_pos):
            nxt = fam_pos[k + 1][0] if k + 1 < len(fam_pos) else len(toks)
            if any(i < rs < nxt for rs in run_starts):
                owning.append((i, fam))
            else:
                non_owning.append((i, fam))
        owning_fams = {f for _, f in owning}
        if len(owning_fams) != 1:
            return None
        family = next(iter(owning_fams))
        own_idx = owning[0][0]
        # Cadena real solo si la relación previa es de OTRA familia ("padre de la
        # madre de X"). Misma familia antes = sinónimo ("tíos y tías", "nicho…
        # descansa"), no es cadena.
        if any(i < own_idx and fam != family for i, fam in non_owning):
            return None

        # Desambiguadores globales (conteos→*_count, extremos, lugar/fecha): cede.
        # Excepción: SOLO conteo sobre familia sin handler de conteo → listar.
        cede_hits = [t for t in tokset if t in GLOBAL_CEDE]
        if cede_hits:
            only_count = all(t in COUNT_WORDS for t in cede_hits)
            if not (only_count and family in COUNT_LIST_FAMILIES):
                return None

        # El sujeto debe ser exactamente UNA persona. 0 = lugar/año/agregado;
        # 2 = dos entidades (parentesco/comparación/pareja). En ambos: cede.
        if len(runs) != 1:
            return None
        subject = run_texts[0]

        # Matrimonio compuesto ("con quién se casó X Y en qué fecha…"): pregunta
        # cónyuge + fecha/lugar a la vez → hay handler dedicado; cedemos.
        if family == "marriage":
            who = {"quien", "quienes"} & tokset
            when_where = {"fecha", "cuando", "donde", "lugar", "iglesia"} & tokset
            if who and when_where:
                return None

        rules = RULES.get(family)
        if not rules:
            return None
        for req_all, req_any, forbids, handler, template in rules:
            if not (req_all <= tokset):
                continue
            if req_any and not (req_any & tokset):
                continue
            if forbids & tokset:
                continue
            return handler, template.format(s=subject)
        return None
