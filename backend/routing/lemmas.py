"""Vocabulario controlado castellano para la capa de intención (modelo por INCLUSIÓN).

La idea (pedida por el usuario): de cada pregunta nos quedamos con DOS cosas y el
resto se ignora *por no ser ninguna de ellas*, sin diccionarios de relleno:

  1. el NOMBRE  → la tirada de tokens que coinciden con nombres reales del árbol
                  (`name_tokens`, lo extrae `intent_es._find_name_runs`).
  2. la INTENCIÓN → un token cuya RAÍZ está en `INTENT_ROOTS` ("herman", "dedic"…).

Las raíces cubren todas las formas verbales sin enumerarlas ("trabaj" → trabaja /
trabajaba / trabajó / trabajo) y se casan por prefijo de la MÁS LARGA a la más
corta, para resolver inclusiones (`tatarabuel` > `bisabuel` > `abuel`). Los nombres
ganan a las raíces: un token que es un nombre real nunca se interpreta como intención.

Lo que SÍ se conserva (no es ruido, cambia la intención): los MODIFICADORES
(paterno/materno, segundos) y los DESAMBIGUADORES (`GLOBAL_CEDE`: conteos→*_count,
extremos mayor/primer/último, lugar/fecha) que redirigen a otro handler.
"""

from __future__ import annotations

# --- Raíces de intención (root, familia) -----------------------------------
# Se ordenan por longitud descendente en _ROOTS_SORTED; para un token se toma la
# raíz más larga que sea prefijo suyo. Sin acentos y en minúsculas.
INTENT_ROOTS = [
    # parentescos verticales (¡orden importa por inclusión!)
    ("padres", "parents"), ("progenitor", "parents"),
    ("padrin", "godparents"), ("madrin", "godparents"), ("apadrin", "godparents"),
    ("padr", "father"), ("papa", "father"),
    ("madre", "mother"), ("mama", "mother"),
    ("hij", "children"),
    ("herman", "siblings"),
    ("tatarabuel", "ggparents"), ("bisabuel", "greatgrandparents"),
    ("abuel", "grandparents"), ("avi", "grandparents"),
    ("tataraniet", "ggchildren"), ("bisniet", "greatgrandchildren"),
    ("niet", "grandchildren"),
    # colaterales / políticos
    ("primo", "cousins"), ("prima", "cousins"), ("cosi", "cousins"),
    ("tio", "uncles"), ("tia", "uncles"), ("oncle", "uncles"),
    ("sobrin", "nephews"), ("nebot", "nephews"),
    ("consuegr", "inlaw"), ("suegr", "inlaw"),
    ("nuera", "inlaw"), ("yern", "inlaw"), ("cunad", "inlaw"),
    # atributos de persona
    ("trabaj", "occupation"), ("oficio", "occupation"), ("profesion", "occupation"),
    ("ocupacion", "occupation"), ("emple", "occupation"), ("dedic", "occupation"),
    ("residenci", "residence"), ("residi", "residence"), ("domicili", "residence"),
    ("direccion", "residence"), ("vivi", "residence"), ("vive", "residence"),
    ("viven", "residence"), ("casa", "residence"), ("morada", "residence"),
    ("matrimoni", "marriage"), ("casam", "marriage"), ("casar", "marriage"),
    ("casad", "marriage"), ("casab", "marriage"), ("caso", "marriage"),
    ("boda", "marriage"), ("conyug", "marriage"), ("espos", "marriage"),
    ("marid", "marriage"), ("pareja", "marriage"), ("companer", "marriage"),
    # atributos de evento / ficha
    ("bauti", "baptism"),
    ("militar", "military"),
    ("evento", "events"), ("acontec", "events"),
    ("educac", "education"), ("estudi", "education"),
    ("enterrad", "burial"), ("sepult", "burial"), ("sepulcr", "burial"),
    ("tumba", "burial"), ("nicho", "burial"), ("descansa", "burial"),
    ("nota", "notes"), ("observ", "notes"), ("anotacion", "notes"),
    ("apunte", "notes"), ("comentario", "notes"),
]
# Raíz más larga primero: garantiza que "bisabuel" gane a "abuel", etc.
_ROOTS_SORTED = sorted(INTENT_ROOTS, key=lambda rf: -len(rf[0]))


def family_of(token: str) -> str | None:
    """Familia de intención de un token por su raíz (más larga que sea prefijo).
    Devuelve None si ninguna raíz encaja. (Los nombres se filtran fuera en el
    llamador: un nombre real nunca llega aquí como intención.)"""
    for root, fam in _ROOTS_SORTED:
        if token.startswith(root):
            return fam
    return None


# "primos hermanos" = primos de primer grado: con 'primos', 'hermanos' es
# modificador, no la familia siblings.
COUSINS_TOKENS = {"primo", "prima", "primos", "primas", "cosi", "cosins", "cosina", "cosines"}

# Sustantivos de cónyuge: disparan la rama "cónyuge" del matrimonio.
SPOUSE_NOUNS = {
    "esposo", "esposa", "esposos", "esposas", "conyuge", "conyuges",
    "marido", "maridos", "companera", "companero",
}


# --- Reglas por familia (ordenadas, la primera que encaja gana) -------------
# Tupla: (req_all, req_any, forbids, handler, plantilla canónica con {s}).
# Operan sobre el conjunto de tokens LITERALES de la pregunta.
RULES = {
    "parents":  [(set(), set(), set(), "handle_parents", "padres de {s}")],
    "father":   [(set(), set(), set(), "handle_father", "padre de {s}")],
    "mother":   [(set(), set(), set(), "handle_mother", "madre de {s}")],
    "children": [(set(), set(), set(), "handle_children", "hijos de {s}")],
    "siblings": [(set(), set(), set(), "handle_siblings", "hermanos de {s}")],
    "grandparents": [
        ({"paterno"}, set(), set(), "handle_paternal_grandfather", "abuelo paterno de {s}"),
        ({"paterna"}, set(), set(), "handle_paternal_grandmother", "abuela paterna de {s}"),
        ({"materna"}, set(), set(), "handle_maternal_grandmother", "abuela materna de {s}"),
        ({"materno"}, set(), set(), "handle_maternal_grandfather", "abuelo materno de {s}"),
        (set(), set(), {"paterno", "paterna", "materno", "materna"}, "handle_grandparents_names", "abuelos de {s}"),
    ],
    "cousins": [
        ({"segundos"}, set(), set(), "handle_second_cousins", "primos segundos de {s}"),
        ({"segundas"}, set(), set(), "handle_second_cousins", "primos segundos de {s}"),
        (set(), set(), {"segundos", "segundas"}, "handle_first_cousins", "primos de {s}"),
    ],
    "uncles":       [(set(), set(), set(), "handle_uncles", "tios de {s}")],
    "nephews":      [(set(), set(), set(), "handle_nephews_nieces", "sobrinos de {s}")],
    "grandchildren": [(set(), set(), set(), "handle_grandchildren", "nietos de {s}")],
    "inlaw": [
        (set(), {"suegro", "suegra", "suegros", "suegras"}, set(), "handle_parents_in_law", "suegros de {s}"),
        (set(), {"consuegro", "consuegros"}, set(), "handle_consuegros", "consuegros de {s}"),
        (set(), {"cunado", "cunados"}, set(), "handle_brothers_in_law", "cuñados de {s}"),
        (set(), {"cunada", "cunadas"}, set(), "handle_sisters_in_law", "cuñada de {s}"),
        (set(), {"nuera", "nueras"}, set(), "handle_daughters_in_law", "nueras de {s}"),
        (set(), {"yerno", "yernos"}, set(), "handle_sons_in_law", "yernos de {s}"),
    ],
    "greatgrandparents": [
        (set(), {"rama"}, set(), "handle_great_grandparents", "bisabuelos de {s}"),
        (set(), set(), {"paterno", "paterna", "materno", "materna"}, "handle_great_grandparents", "bisabuelos de {s}"),
    ],
    "greatgrandchildren": [(set(), set(), set(), "handle_great_grandchildren", "bisnietos de {s}")],
    "ggchildren": [(set(), set(), set(), "handle_has_great_great_grandchildren", "tataranietos de {s}")],
    # --- atributos ---
    "occupation": [(set(), set(), set(), "handle_occupation_natural", "de que trabajaba {s}")],
    "residence":  [(set(), set(), set(), "handle_last_residence", "donde vivia {s}")],
    "marriage": [
        (set(), {"donde", "lugar", "iglesia", "sitio"}, set(), "handle_marriage_date_place", "donde se caso {s}"),
        (set(), {"cuando", "fecha", "ano", "dia"}, set(), "handle_marriage_date_place", "cuando se caso {s}"),
        (set(), {"pareja", "parejas"}, set(), "handle_spouse_or_partner", "con quien formo pareja {s}"),
        (set(), SPOUSE_NOUNS, set(), "handle_spouse", "conyuge de {s}"),
        (set(), {"quien", "quienes", "persona", "personas"}, set(), "handle_spouse_or_partner", "con quien se caso {s}"),
    ],
    "baptism": [
        (set(), {"donde", "lugar", "iglesia"}, set(), "handle_baptism_place", "se bautizo {s}"),
        (set(), set(), set(), "handle_baptism", "bautismo de {s}"),
    ],
    "military":   [(set(), set(), set(), "handle_military", "datos militares de {s}")],
    "events":     [(set(), set(), set(), "handle_events", "eventos de {s}")],
    "education":  [(set(), set(), set(), "handle_education", "estudios de {s}")],
    "burial":     [(set(), set(), set(), "handle_burial", "sepultura de {s}")],
    "notes":      [(set(), set(), set(), "handle_notes_field", "notas de {s}")],
    "godparents": [(set(), set(), set(), "handle_godparents", "padrinos de {s}")],
}


# --- Desambiguadores globales: si aparece cualquiera, cedemos al router ------
# NO son ruido: redirigen a un handler más específico (conteos→*_count, extremos)
# o a una intención no migrada (lugar/fecha). Garantía de cero regresiones.
GLOBAL_CEDE = {
    "cuantos", "cuantas", "cuanta", "cuanto", "numero", "cantidad",
    "muchos", "muchas", "pocos", "pocas", "bastantes", "numerosos", "numerosas",
    "mayor", "menor", "mayores", "primer", "primera", "primero",
    "ultimo", "ultima", "segundo", "segunda",
    # edad → handlers de edad al casarse / al primer hijo (handle_age_*)
    "edad", "edades",
    # "parejas se casaron en X" (plural) → handle_marriages_place, no un cónyuge
    "casaron", "casaban", "casaren",
    # ficha "figura registrada / aparece documentado" → handlers *_field
    "registrada", "registrado", "documentado", "documentada",
    "nacio", "nacieron", "nacida", "nacido", "nacimiento",
    "murio", "murieron", "fallecio", "fallecieron", "muerte", "defuncion",
    "final",
    "descendencia", "descendientes", "vivos", "vivas", "longeva", "longevo",
    # comparaciones / superlativos ("vivió más años", "más hijos") → analítico
    "mas",
}

COUNT_WORDS = {
    "cuantos", "cuantas", "cuanta", "cuanto", "numero", "cantidad",
    "muchos", "muchas", "pocos", "pocas", "bastantes", "numerosos", "numerosas",
}

# Familias SIN handler de conteo propio: "cuántos nietos" se responde listándolos.
COUNT_LIST_FAMILIES = {"grandchildren", "nephews", "cousins", "uncles", "residence"}

# Tokens que, aun estando en name_tokens, no deben formar parte de la tirada de
# nombre porque son palabras-clave del modelo (evita falsos sujetos).
NON_NAME_TOKENS = GLOBAL_CEDE | COUNT_WORDS | COUSINS_TOKENS | {
    "paterno", "paterna", "materno", "materna", "segundos", "segundas",
    "hermanos", "hermanas", "rama", "pareja", "parejas",
}


# Compuestos de parentesco (dos palabras): requieren un token de cada grupo.
# Se comprueban ANTES del guard de familias (si no, "tío abuelo" = 2 familias).
COMPOUND_RULES = [
    ({"tio", "tios", "tia", "tias"}, {"abuelo", "abuela", "abuelos", "abuelas"},
     "handle_great_uncles", "tios abuelos de {s}"),
    ({"sobrino", "sobrinos", "sobrina", "sobrinas"}, {"nieto", "nieta", "nietos", "nietas"},
     "handle_grandnephews", "sobrinos nietos de {s}"),
]
