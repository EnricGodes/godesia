"""Reescritura determinista de preguntas no-españolas a español.

Se interpone en QueryRouter.route() justo tras _clean_question(): si la pregunta
está en otro idioma de la plataforma, la traduce a español canónico para que las
dos capas de matching existentes (IntentRouter + patrones) la resuelvan sin
cambios → paridad total con el español por construcción.

Los NOMBRES de persona nunca se traducen: se detectan (reutilizando los
name_tokens que ya construye QueryRouter) y se sustituyen por centinelas antes
de traducir, restaurándolos al final con sus acentos y mayúsculas originales.

Añadir un idioma = añadir un módulo de datos rewrite_XX con este contrato:
    MARKERS_STRONG, MARKERS_WEAK : set          (detección; tokens sin acento)
    PRE_SPLIT     : list[(pattern, repl)]       (contracciones apóstrofo; PRE-protección)
    NAME_CONNECTORS : set                       (partículas que unen nombres: de, i…)
    NON_NAME_TOKENS : set                       (keywords que nunca inician nombre)
    PRE_RULES     : list[(pattern, repl)]       (post-protección; dels→de los…)
    PHRASE_RULES  : list[(pattern, repl))]      (reordenaciones estructurales)
    PERIPHRASIS   : dict[str, (sing, plur)]     (va/van + infinitiu → pretérito)
    MULTIWORD_MAP : list[(pattern, repl)]       (n-gramas)
    TOKEN_MAP     : dict[str, str]              (palabra→palabra; claves sin acento)
El motor de este archivo es genérico: no conoce ningún idioma en concreto.
"""

from __future__ import annotations

import re
import unicodedata

from .langdetect import detect_lang, DEFAULT_LANG

# Registro de módulos de idioma disponibles (import perezoso y tolerante).
_LANG_MODULES = {}
for _code in ("ca", "en", "fr", "de"):
    try:
        _LANG_MODULES[_code] = __import__(f"routing.rewrite_{_code}", fromlist=["*"])
    except Exception:
        try:
            _LANG_MODULES[_code] = __import__(f"backend.routing.rewrite_{_code}", fromlist=["*"])
        except Exception:
            pass

LANG_MARKERS = {
    code: (getattr(mod, "MARKERS_STRONG", set()), getattr(mod, "MARKERS_WEAK", set()),
           getattr(mod, "CHAR_MARKERS", set()))
    for code, mod in _LANG_MODULES.items()
}

# El punt volat "·" (ela geminada catalana, p.ej. "Estil·les") forma parte de la
# palabra: se incluye en el token para no partir apellidos ni exponer "les".
_WORD_RE = re.compile(r"[a-zà-ÿ0-9·]+")
_TOKEN_SPAN_RE = re.compile(r"\(\d{4}\)|[a-zà-ÿ0-9'·]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"\(\d{4}\)")


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def _strip_catalan_marks(text: str) -> str:
    """Quita SOLO las marcas propias del catalán (acento grave à/è/ò y cedilla ç),
    conservando el acento agudo y la ñ/ü del español. Así el contenido que el
    usuario dejó en español ("profesión", "años", "más") llega intacto a los
    patrones (que a veces exigen esa tilde), mientras que las grafías catalanas
    ("residència"→"residencia") se normalizan. Los nombres van protegidos."""
    out = []
    for ch in text or "":
        d = unicodedata.normalize("NFD", ch)
        if any(c in ("̀", "̧") for c in d):  # grave o cedilla
            out.append("".join(c for c in d if unicodedata.category(c) != "Mn"))
        else:
            out.append(ch)
    return "".join(out)


def _norm(tok: str) -> str:
    return _strip_accents((tok or "").lower())


def _normalize_typography(text: str) -> str:
    text = re.sub(r"[’‘`´]", "'", text or "")
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Incluye acentos de es/ca/fr (grave, agudo, circunflejo, diéresis) para que las
# reglas escritas sin tilde casen cualquier variante.
_ACCENT_CLASS = {"a": "[aàáâä]", "e": "[eèéêë]", "i": "[iíìïî]", "o": "[oòóôö]",
                 "u": "[uúùûü]", "c": "[cç]", "n": "[nñ]", "y": "[yÿ]"}


def _accent_insensitive(pattern: str) -> str:
    """Hace insensibles a acentos las vocales/ç/ñ *literales* del patrón (para
    que reglas escritas sin tilde casen 'més', 'néixer'…), respetando la sintaxis
    regex: no toca caracteres escapados (\\d) ni el interior de clases [...]."""
    out, i, n, in_class = [], 0, len(pattern), False
    while i < n:
        ch = pattern[i]
        if ch == "\\" and i + 1 < n:
            out.append(pattern[i:i + 2]); i += 2; continue
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        out.append(_ACCENT_CLASS[ch] if (not in_class and ch in _ACCENT_CLASS) else ch)
        i += 1
    return "".join(out)


def _compile_pairs(pairs):
    return [(re.compile(_accent_insensitive(p), re.IGNORECASE), r)
            for p, r in (pairs or [])]


class QuestionRewriter:
    def __init__(self, name_tokens):
        self.name_tokens = name_tokens or set()
        # Compilar patrones de cada módulo una sola vez.
        self._pre_split, self._pre_rules, self._phrase = {}, {}, {}
        self._multiword = {}
        for code, mod in _LANG_MODULES.items():
            self._pre_split[code] = _compile_pairs(getattr(mod, "PRE_SPLIT", []))
            self._pre_rules[code] = _compile_pairs(getattr(mod, "PRE_RULES", []))
            self._phrase[code] = _compile_pairs(getattr(mod, "PHRASE_RULES", []))
            self._multiword[code] = _compile_pairs(getattr(mod, "MULTIWORD_MAP", []))

    # ── API ────────────────────────────────────────────────────────────────
    def rewrite(self, question: str, ui_lang: str = "es"):
        """Devuelve (pregunta_es, lang_detectado). Si es español, intacta."""
        q = _normalize_typography(question)
        lang = detect_lang(q, ui_lang=ui_lang, name_tokens=self.name_tokens,
                           lang_markers=LANG_MARKERS)
        if lang == DEFAULT_LANG or lang not in _LANG_MODULES:
            return question, DEFAULT_LANG
        mod = _LANG_MODULES[lang]

        # 1. Contracciones apóstrofo antes de proteger (d'Artur → de Artur).
        for pat, repl in self._pre_split[lang]:
            q = pat.sub(repl, q)

        # 2. Proteger nombres reales → centinelas ascii.
        connectors = getattr(mod, "NAME_CONNECTORS", set())
        non_name = getattr(mod, "NON_NAME_TOKENS", set())
        cont_only = getattr(mod, "NAME_CONTINUATION_ONLY", set())
        ambiguous = getattr(mod, "NAME_AMBIGUOUS", set())
        q, names = self._protect_names(q, connectors, non_name, cont_only, ambiguous)

        # 3. Minúsculas, PERO conservando acentos: las palabras que no se
        #    traducen (contenido ya español: "años", "qué"…) deben llegar
        #    intactas a los patrones españoles, que a veces exigen la tilde.
        q = q.lower()

        # 4. Reglas por capas.
        for pat, repl in self._pre_rules[lang]:
            q = pat.sub(repl, q)
        for pat, repl in self._phrase[lang]:
            q = pat.sub(repl, q)
        q = self._apply_periphrasis(q, getattr(mod, "PERIPHRASIS", {}))
        for pat, repl in self._multiword[lang]:
            q = pat.sub(repl, q)
        q = self._apply_token_map(q, getattr(mod, "TOKEN_MAP", {}))

        # 5. Normalizar grafía catalana residual (grave/ç) y restaurar nombres.
        q = _strip_catalan_marks(q)
        out = self._restore_names(q, names)
        return out, lang

    # ── Protección de nombres ────────────────────────────────────────────────
    def _protect_names(self, text, connectors, non_name, cont_only=frozenset(),
                       ambiguous=frozenset()):
        """Sustituye tiradas de tokens-nombre (con conectores intermedios) por
        centinelas. Espejo de intent_es._name_runs + partículas conectoras.

        La "i"/"y" es ambigua: une apellidos ("Farràs i Ribas") pero también
        separa dos personas ("X i Y"). Se resuelve por lookahead: glue solo si
        le sigue UN único token-nombre (continuación de apellido); si le siguen
        dos o más (segunda persona completa) es separador y NO se une.

        cont_only: palabras que son apellido pero también término común
        ("Petit", "Gran"): solo se protegen si CONTINÚAN un nombre (apellido
        precedido de otro nombre), nunca si lo inician ("més petit" = comparación)."""
        spans = [(m.group(0), m.start(), m.end()) for m in _TOKEN_SPAN_RE.finditer(text)]
        info = []  # (norm, start, end, is_name, is_year)
        for idx, (tok, s, e) in enumerate(spans):
            n = _norm(tok)
            is_name = n in self.name_tokens and n not in non_name
            # Tokens ambiguos (p.ej. "Marie"/"Pere" = nombre propio Y keyword francés
            # père/marié): se protegen como nombre SOLO si el token siguiente también
            # es nombre ("Marie Zimmer" sí; "père de X"/"s'est marié(e)" no).
            if (not is_name and n in ambiguous and n in self.name_tokens
                    and idx + 1 < len(spans)):
                n2 = _norm(spans[idx + 1][0])
                if n2 in self.name_tokens and n2 not in non_name:
                    is_name = True
            info.append((n, s, e, is_name, bool(_YEAR_RE.fullmatch(tok))))

        def names_after(j):
            c = 0
            for k in range(j + 1, len(info)):
                if info[k][3]:
                    c += 1
                else:
                    break
            return c

        runs = []
        cur_start = cur_end = None
        pending = None
        for j, (n, s, e, is_name, is_year) in enumerate(info):
            # "Petit"/"Gran": solo protegen si continúan un nombre ya abierto.
            starts_here = is_name and not (cur_start is None and n in cont_only)
            if starts_here or (is_year and cur_start is not None):
                if cur_start is None:
                    cur_start = s
                cur_end = e
                pending = None
            elif cur_start is not None and pending is None and (
                    n in connectors or
                    (n in ("i", "y") and names_after(j) == 1)):
                pending = e  # conector tentativo (o "i" de apellido, 1 nombre detrás)
            else:
                if cur_start is not None:
                    runs.append((cur_start, cur_end))
                cur_start = cur_end = None
                pending = None
        if cur_start is not None:
            runs.append((cur_start, cur_end))

        # Sustituir de atrás hacia delante para no mover offsets. Sin padding de
        # espacios: el centinela ocupa exactamente el hueco del nombre, así se
        # conserva la puntuación original adyacente ("Bertran, 67", '"Manen"').
        names = {}
        for k, (s, e) in enumerate(reversed(runs)):
            idx = len(runs) - 1 - k
            names[idx] = text[s:e]
            text = text[:s] + f"qzx{idx}xzq" + text[e:]
        return text, names

    def _restore_names(self, text, names):
        for idx, original in names.items():
            text = text.replace(f"qzx{idx}xzq", original)
        return re.sub(r"\s+", " ", text).strip()

    # ── Perífrasis va/van + infinitiu ────────────────────────────────────────
    def _apply_periphrasis(self, text, table):
        if not table:
            return text
        def repl(m):
            num, inf = m.group(1), m.group(2)
            forms = table.get(_norm(inf))
            if not forms:
                return f"{m.group(1)} {inf}"  # sin cambios: no es perífrasis conocida
            return forms[1] if num == "van" else forms[0]
        return re.sub(r"\b(va|van) ([a-zà-ÿ]+)\b", repl, text)

    # ── Barrido palabra a palabra ────────────────────────────────────────────
    def _apply_token_map(self, text, token_map):
        if not token_map:
            return text
        # Clave = palabra sin acento; las no mapeadas se conservan tal cual
        # (con sus acentos), para no romper el contenido ya español.
        return _WORD_RE.sub(
            lambda m: token_map.get(_norm(m.group(0)), m.group(0)), text)
