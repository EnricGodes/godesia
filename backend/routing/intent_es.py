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
    FULL_SIBLING_CUES,
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
# Verbos posesivos: habilitan la inversión "¿Tenía X <relación>?".
_POSSESSOR = {"tenia", "tenian", "tuvo", "tuvieron", "tiene", "tienen"}
# Partículas de apellido ("Company DE Renzi", "Espinosa DE LOS Monteros",
# "Mestre I Farràs"). Tienen menos de 3 letras, así que nunca son name_tokens y
# partían el sujeto en dos tiradas: la pregunta se cedía al router de patrones y
# acababa sin respuesta. Solo unen ENTRE nombres, así que "tías de Emili" sigue
# partiendo donde debe. La "y" queda fuera a propósito: separa dos personas.
_PARTICLES = {"de", "del", "d", "da", "das", "dos", "la", "las", "los",
              "van", "von", "der", "den", "i", "y", "ma"}


def _strip_accents(text: str) -> str:
    # "ª/º" pasan a a/o para que "Mª" sea un token ("ma") y no se parta el nombre.
    text = (text or "").replace("\u00aa", "a").replace("\u00ba", "o")
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(_strip_accents((text or "").lower()))


def _tokens_raw(text: str) -> Optional[List[str]]:
    """Los mismos tokens que `_tokens`, pero tal cual venían en la pregunta.

    Sirve para que el sujeto de la pregunta canónica conserve tildes y mayúsculas
    ("María", no "maria"): sin ellas no se puede distinguir a María Hurtado Rusca
    de Marià Hurtado Rusca. Quitar tildes no cambia la longitud del texto (son
    caracteres precompuestos), así que los tramos encajan; si alguna vez no
    encajaran, devuelve None y se sigue con la versión sin tildes.
    """
    low = (text or "").lower()
    flat = _strip_accents(low)
    if len(flat) != len(low):
        return None
    return [text[m.start():m.end()] for m in _TOKEN_RE.finditer(flat)]


class IntentRouter:
    def __init__(self, name_tokens=None):
        # Tokens (≥3 letras) que aparecen en nombres reales del árbol.
        self.name_tokens = name_tokens or set()

    def _name_runs(self, toks):
        """Tiradas contiguas de tokens-nombre, como (índice_inicio, texto)."""
        def _is_name(tok):
            return tok in self.name_tokens and tok not in NON_NAME_TOKENS

        def _extends(tok):
            """Un token de la lista negra puede CONTINUAR un nombre si además es
            nombre real del árbol ("Ruaix Mas"); nunca empezarlo."""
            return tok in self.name_tokens

        runs, cur, start = [], [], None
        for i, t in enumerate(toks):
            is_name = _is_name(t)
            is_year = bool(_YEAR_RE.fullmatch(t))
            if is_name or (is_year and cur) or (cur and _extends(t)):
                if not cur:
                    start = i
                cur.append(t)
            elif cur and (t in _PARTICLES or (len(t) == 1 and t.isalpha())):
                # Además de las partículas, las iniciales ("Josep N. Godes").
                # Absorbe la partícula (o la cadena "de los") solo si detrás
                # sigue habiendo nombre; si no, cierra la tirada aquí.
                j = i
                while j < len(toks) and (toks[j] in _PARTICLES
                                         or (len(toks[j]) == 1 and toks[j].isalpha())):
                    j += 1
                if j < len(toks) and (_is_name(toks[j]) or _extends(toks[j])):
                    cur.append(t)
                else:
                    runs.append((start, " ".join(cur)))
                    cur = []
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
        raw = _tokens_raw(question)
        tokset = set(toks)
        runs = self._name_runs(toks)
        run_starts = [s for s, _ in runs]
        if raw and len(raw) == len(toks):
            run_texts = [" ".join(raw[st:st + len(txt.split())]) for st, txt in runs]
        else:
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
        if owning_fams:
            if len(owning_fams) != 1:
                return None
            family = next(iter(owning_fams))
            own_idx = owning[0][0]
            # Cadena real solo si la relación previa es de OTRA familia ("padre de
            # la madre de X"). Misma familia antes = sinónimo ("tíos y tías",
            # "nicho…descansa"), no es cadena.
            if any(i < own_idx and fam != family for i, fam in non_owning):
                return None
        else:
            # Inversión con verbo posesivo: "¿Tenía X primas segundas?" (nombre
            # ANTES de la relación). Aceptamos si hay 1 familia, 1 nombre y un
            # "tenía/tuvo/tiene" en la pregunta.
            all_fams = {f for _, f in fam_pos}
            if len(all_fams) == 1 and len(runs) == 1 and (_POSSESSOR & tokset):
                family = next(iter(all_fams))
            else:
                return None

        # Hermanos de doble vínculo: la pregunta nombra al padre y a la madre (o
        # dice "completos"), pero no pregunta por ellos → cede al patrón propio.
        if any(family_of(t) == "siblings" for t in toks) and (
                (FULL_SIBLING_CUES & tokset) or {"padre", "madre"} <= tokset):
            return None

        # Desambiguadores globales (conteos→*_count, extremos, lugar/fecha): cede.
        # Excepción: SOLO conteo sobre familia sin handler de conteo → listar.
        # Los tokens que forman parte del SUJETO no cuentan: en "José Ruaix Mas"
        # el apellido "Mas" no es el "más" comparativo (los nombres ganan).
        name_idx = {i for st, txt in runs for i in range(st, st + len(txt.split()))}
        outside = [t for i, t in enumerate(toks) if i not in name_idx]
        cede_hits = [t for t in outside if t in GLOBAL_CEDE]
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
