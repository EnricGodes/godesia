"""Oráculo de verificación para el QA automático del QueryRouter.

Calcula la respuesta correcta de una pregunta estructurada DIRECTAMENTE desde
las tablas (people.father_id/mother_id, children, marriages) con SQL propio,
independiente del código del router, y la compara con los IDs que el router
devolvió en `people_mentioned`. Así un PASS significa "el router coincide con
la verdad de la base de datos", no solo "la respuesta no ha cambiado".

Tipos no estructurados (estadísticas, rankings, preguntas libres) devuelven
UNVERIFIABLE: para esos se usa la línea base congelada, no el oráculo.
"""

from __future__ import annotations

import re
import unicodedata

PASS = "pass"
FAIL = "fail"
UNVERIFIABLE = "unverifiable"


def _strip(text):
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _ids(rows):
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Clasificación del tipo de pregunta (solo tipos verificables)
# ---------------------------------------------------------------------------

# Orden importa: tipos específicos (primos/sobrinos/nietos/abuelos paterno…)
# ANTES de los genéricos (hermanos/padre/madre) para no clasificar mal
# "primos hermanos de X" como hermanos. (regex sobre texto sin acentos) -> tipo.
_TYPE_PATTERNS = [
    (r"\babuelo\s+paterno\b", "paternal_grandfather"),
    (r"\babuela\s+materna\b", "maternal_grandmother"),
    (r"\babuelos?\s+de\b", "grandparents"),
    (r"\bprim[oa]s?(?:\s+herman[oa]s?)?\s+(?:de|tuvo|tenia|tiene|salieron|le\s+sal)\b", "first_cousins"),
    (r"\bsobrin[oa]s?\s+de\b", "nephews"),
    (r"\bniet[oa]s?\s+de\b", "grandchildren"),
    (r"\bpadres\s+de\b|\bprogenitores\s+de\b", "parents"),
    (r"\bpadre\s+de\b", "father"),
    (r"\bmadre\s+de\b", "mother"),
    (r"\bhermanos?\s+de\b|\bhermanos?\s+(?:tenia|tuvo)\b", "siblings"),
    (r"\bhijos\s+de\b|\bhijos\b.*\b(?:tuvo|tiene|tenia)\b", "children"),
    (r"\bconyuge\s+de\b|\bcon\s+quien\s+se\s+caso\b|\bpareja\s+de\b|\bcaso\s+o\s+emparejo\b", "spouse"),
    (r"\bdonde\s+nacio\b|\blugar\s+de\s+nacimiento\b", "birth_place"),
    (r"\bdonde\s+(?:fallecio|murio)\b|\blugar\s+de\s+(?:fallecimiento|defuncion)\b", "death_place"),
]

# Preguntas compuestas / ambiguas: el oráculo NO debe verificarlas (van a línea
# base). P.ej. "padres y los hijos de X", "matrimonio de A y B", "padre de la
# madre de X" (anidada), "cuántos hijos … y …".
_COMPOUND_GUARDS = [
    r"\by\s+(?:los?\s+|las?\s+)?(?:hijos|hijas|nietos|padres|madre)\b",
    r"\bmatrimonio\s+de\b",
    r"\bde\s+(?:el\s+|la\s+)?(?:padre|madre)\s+de\b",   # "… de la madre de X"
    r"\bcuant[oa]s\b",                                    # conteos: respuesta numérica
    r"\bparentesco\b|\brelacion\s+tenia\b",
    r"\bmayor\b.*\bo\b",                                  # "quién es mayor, A o B"
    # Parentescos compuestos que el oráculo no calcula (van a línea base):
    r"\bt[ií]os?\s+abuelos?\b|\bsobrin[oa]s?\s+niet[oa]s?\b|\bprimos?\s+segundos?\b",
    r"\bbisabuel|\btatara|\bbisniet|\bbisabuela\b",
    # Preguntas con filtro o pareja sobre hijos:
    r"\bhijos?\b.*\b(?:nacieron|murieron|fallecieron|llegaron|adulta?|sobrevivi)\b",
    r"\bnacieron\s+en\b|\bdentro\s+de\s+los\s+hijos\b",
    r"\bla\s+pareja\b|\bque\s+se\s+caso\s+en\b|\bpareja\s+(?:que|formada)\b",
]
_GUARD_RX = re.compile("|".join(_COMPOUND_GUARDS), re.I)

# Tipos cuya verdad es un conjunto de personas (comparación por IDs)
_PERSON_SET_TYPES = {
    "parents", "father", "mother", "grandparents", "paternal_grandfather",
    "maternal_grandmother", "siblings", "first_cousins", "nephews",
    "grandchildren", "children", "spouse",
}


def classify_question(question):
    q = _strip(question)
    if _GUARD_RX.search(q):
        return None  # compuesta/ambigua → línea base, no oráculo
    for rx, t in _TYPE_PATTERNS:
        if re.search(rx, q):
            return t
    return None


# ---------------------------------------------------------------------------
# Conjunto esperado de IDs por tipo (SQL independiente)
# ---------------------------------------------------------------------------

def _person(conn, pid):
    row = conn.execute(
        "SELECT id, father_id, mother_id, birth_place, birth_city, death_place, death_city "
        "FROM people WHERE id = ?", (pid,)).fetchone()
    return dict(row) if row else None


def _children_of(conn, parent_ids):
    parent_ids = [p for p in parent_ids if p]
    if not parent_ids:
        return set()
    ph = ",".join("?" * len(parent_ids))
    return _ids(conn.execute(
        f"SELECT DISTINCT child_id FROM children WHERE parent_id IN ({ph})", parent_ids).fetchall())


def _siblings_of(conn, pid):
    p = _person(conn, pid)
    if not p:
        return set()
    sibs = _children_of(conn, [p["father_id"], p["mother_id"]])
    sibs.discard(pid)
    return sibs


def _spouses_of(conn, pid):
    rows = conn.execute(
        "SELECT CASE WHEN person1_id=? THEN person2_id ELSE person1_id END "
        "FROM marriages WHERE person1_id=? OR person2_id=? "
        "UNION SELECT CASE WHEN person1_id=? THEN person2_id ELSE person1_id END "
        "FROM partnerships WHERE person1_id=? OR person2_id=?",
        (pid, pid, pid, pid, pid, pid)).fetchall()
    return _ids(rows)


def expected_ids(conn, qtype, subject_id):
    """Conjunto de person_ids correctos según la BD, o None si no aplica."""
    p = _person(conn, subject_id)
    if not p:
        return None
    if qtype == "parents":
        return {x for x in (p["father_id"], p["mother_id"]) if x}
    if qtype == "father":
        return {p["father_id"]} if p["father_id"] else set()
    if qtype == "mother":
        return {p["mother_id"]} if p["mother_id"] else set()
    if qtype == "children":
        return _children_of(conn, [subject_id])
    if qtype == "siblings":
        return _siblings_of(conn, subject_id)
    if qtype == "spouse":
        return _spouses_of(conn, subject_id)
    if qtype == "grandchildren":
        return _children_of(conn, _children_of(conn, [subject_id]))
    if qtype == "nephews":
        return _children_of(conn, _siblings_of(conn, subject_id))
    if qtype == "grandparents":
        gp = set()
        for parent in (p["father_id"], p["mother_id"]):
            pp = _person(conn, parent) if parent else None
            if pp:
                gp |= {x for x in (pp["father_id"], pp["mother_id"]) if x}
        return gp
    if qtype == "paternal_grandfather":
        f = _person(conn, p["father_id"]) if p["father_id"] else None
        return {f["father_id"]} if f and f["father_id"] else set()
    if qtype == "maternal_grandmother":
        m = _person(conn, p["mother_id"]) if p["mother_id"] else None
        return {m["mother_id"]} if m and m["mother_id"] else set()
    if qtype == "first_cousins":
        # hijos de los hermanos de los padres, excluyendo a los hermanos del sujeto
        aunts_uncles = set()
        for parent in (p["father_id"], p["mother_id"]):
            aunts_uncles |= _siblings_of(conn, parent) if parent else set()
        cousins = _children_of(conn, aunts_uncles)
        cousins -= _siblings_of(conn, subject_id)
        cousins.discard(subject_id)
        return cousins
    return None


# ---------------------------------------------------------------------------
# Verificación de un caso
# ---------------------------------------------------------------------------

def _norm_id(i):
    return (i or "").strip("@")


def verify(router, case):
    """Devuelve (resultado, detalle). resultado: pass | fail | unverifiable."""
    qtype = classify_question(case["question"])
    if qtype is None:
        return UNVERIFIABLE, "tipo no estructurado"

    last = case.get("last_run") or {}
    if last.get("status") != 200 or not last.get("answer"):
        return FAIL, "el router no devolvió respuesta"
    _unres = last.get("unresolved") if "unresolved" in last \
        else ("No he sabido responder" in last.get("answer", ""))
    if _unres:
        return FAIL, "el router no resolvió la pregunta"

    # El sujeto de la pregunta es el primer people_mentioned (los handlers
    # siempre devuelven [person, ...]). Esto desacopla el oráculo del parseo de
    # nombre del router; verifica la LÓGICA de la relación, no la desambiguación
    # de homónimos. Fallback: extracción de texto.
    mentioned_ids = [_norm_id(i) for i in last.get("people_mentioned", [])]
    subject_id = None
    if mentioned_ids:
        cand = mentioned_ids[0]
        if _person(router.conn, f"@{cand}@"):
            subject_id = f"@{cand}@"
        elif _person(router.conn, cand):
            subject_id = cand
    if not subject_id:
        subject = router._extract_subject_name(case["question"])
        person = router._resolve_person(subject)[0] if subject else None
        if not person:
            return UNVERIFIABLE, "no se pudo identificar el sujeto"
        subject_id = person["id"]

    if qtype in _PERSON_SET_TYPES:
        expected = expected_ids(router.conn, qtype, subject_id)
        if expected is None:
            return UNVERIFIABLE, "sin verdad calculable"
        mentioned = {_norm_id(i) for i in last.get("people_mentioned", [])}
        mentioned.discard(_norm_id(subject_id))
        exp = {_norm_id(i) for i in expected}
        if not exp:
            # La BD no tiene esa relación: correcto si el router tampoco menciona
            # a nadie (aparte del propio sujeto, ya descartado).
            if not mentioned:
                return PASS, "sin relación en BD y el router no menciona a nadie"
            return FAIL, f"la BD no tiene esa relación pero el router devolvió {sorted(mentioned)}"
        missing = exp - mentioned
        extra = mentioned - exp
        if not missing and not extra:
            return PASS, f"{len(exp)} coinciden"
        return FAIL, f"esperados {sorted(exp)} | obtenidos {sorted(mentioned)} | faltan {sorted(missing)} | sobran {sorted(extra)}"

    # Datos vitales: comparar el campo de la BD contra el texto de la respuesta
    if qtype in ("birth_place", "death_place"):
        person = _person(router.conn, subject_id)
        field = "birth" if qtype == "birth_place" else "death"
        place = person.get(f"{field}_place") or person.get(f"{field}_city")
        if not place:
            return UNVERIFIABLE, "sin lugar en BD"
        answer = _strip(last.get("answer", ""))
        # comparar por la primera palabra significativa del lugar (ciudad)
        city = _strip(place).split(",")[0].strip()
        if city and city in answer:
            return PASS, f"lugar '{city}' presente"
        return FAIL, f"esperado lugar '{city}' no aparece en la respuesta"

    return UNVERIFIABLE, "tipo sin verificador"
