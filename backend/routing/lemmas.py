"""Vocabulario controlado castellano para la capa de intención.

Mapea TOKENS COMPLETOS (no prefijos) a una intención canónica. Así una sola
entrada cubre todas las formas verbales sin enumerarlas (`tuvo`/`tenia`/`tiene`
disparan lo mismo) y se evitan las colisiones de raíz que tendría un stemmer
ciego (`cas`->casa, `prim`->primero).

Para añadir una intención nueva: registrar sus tokens-núcleo en CORE_LEMMAS y su
plantilla canónica en CANONICAL. Lo demás (extracción de sujeto, guardas) es común.
"""

from enum import Enum


class Intent(str, Enum):
    PARENTS = "parents"
    FATHER = "father"
    MOTHER = "mother"
    CHILDREN = "children"
    SIBLINGS = "siblings"


# Token-núcleo -> intención. Solo formas en plural para hijos/hermanos: el
# singular con modificador ("primer hijo", "hijo mayor") es OTRA intención y
# debe cederse al router de patrones.
CORE_LEMMAS = {
    "padres": Intent.PARENTS,
    "progenitores": Intent.PARENTS,
    "padre": Intent.FATHER,
    "papa": Intent.FATHER,
    "madre": Intent.MOTHER,
    "mama": Intent.MOTHER,
    "hijos": Intent.CHILDREN,
    "hijas": Intent.CHILDREN,
    "hermanos": Intent.SIBLINGS,
    "hermanas": Intent.SIBLINGS,
}


# Plantilla canónica por intención. Se sintetiza una pregunta mínima que el
# handler EXISTENTE ya sabe resolver, de modo que la respuesta es idéntica a la
# aprobada en el banco. {s} = sujeto extraído.
CANONICAL = {
    Intent.PARENTS: ("handle_parents", "padres de {s}"),
    Intent.FATHER: ("handle_father", "padre de {s}"),
    Intent.MOTHER: ("handle_mother", "madre de {s}"),
    Intent.CHILDREN: ("handle_children", "hijos de {s}"),
    Intent.SIBLINGS: ("handle_siblings", "hermanos de {s}"),
}


# Si aparece CUALQUIERA de estos tokens, la pregunta pertenece a una intención
# todavía no migrada (otro parentesco, cónyuge, lista por lugar/fecha, conteo,
# extremos…): devolvemos None y deja que actúe el router de 163 patrones. Es la
# garantía de cero regresiones mientras migramos por lotes.
OUT_OF_SCOPE = {
    # otros parentescos verticales
    "abuelo", "abuela", "abuelos", "abuelas", "avi", "avia", "avis", "avies",
    "bisabuelo", "bisabuela", "bisabuelos", "bisabuelas",
    "tatarabuelo", "tatarabuela", "tatarabuelos", "tatarabuelas",
    "nieto", "nieta", "nietos", "nietas",
    "bisnieto", "bisnieta", "bisnietos", "bisnietas",
    "tataranieto", "tataranieta", "tataranietos", "tataranietas",
    # colaterales / políticos
    "primo", "prima", "primos", "primas", "cosi", "cosins", "cosina", "cosines",
    "tio", "tia", "tios", "tias", "oncle", "oncles",
    "sobrino", "sobrina", "sobrinos", "sobrinas", "nebot", "nebots",
    "suegro", "suegra", "suegros", "suegras", "consuegro", "consuegros",
    "nuera", "nueras", "yerno", "yernos",
    "cunado", "cunada", "cunados", "cunadas",
    "padrino", "padrinos", "madrina", "madrinas",
    # cónyuge / pareja
    "esposo", "esposa", "conyuge", "marido", "mujer", "pareja",
    "caso", "casar", "casarse", "casado", "casada", "casaron", "boda", "matrimonio",
    # listas por lugar / fecha
    "nacio", "nacieron", "nacida", "nacido", "nacimiento",
    "murio", "murieron", "fallecio", "fallecieron", "muerte", "defuncion",
    "enterrado", "enterrada", "sepultado", "sepultada",
    # extremos / orden de nacimiento
    "mayor", "menor", "mayores", "primer", "primera", "primero",
    "ultimo", "ultima", "segundo", "segunda",
    # conteos / cantidad (van a los handlers *_count, más específicos)
    "cuantos", "cuantas", "cuanta", "cuanto", "numero", "cantidad",
    "muchos", "muchas", "pocos", "pocas", "bastantes", "numerosos", "numerosas",
    # agregados / descendencia
    "descendencia", "descendientes", "vivos", "vivas", "longeva", "longevo",
}


# Relleno que se elimina del PRINCIPIO del sujeto, tras el token-núcleo.
LEADING_FILLER = {
    "de", "del", "la", "las", "los", "el", "l", "d",
    "tenia", "tenian", "tuvo", "tuvieron", "tiene", "tienen", "tener",
    "fueron", "eran", "era", "fue", "son", "es",
    "que", "quien", "quienes", "cual", "cuales", "como",
    "se", "llamaba", "llamaban", "llaman", "hay", "habia",
    "documentados", "documentadas", "documentado", "documentada",
    "registrados", "registradas", "todos", "todas", "sus", "su",
}


# Adverbios de cola que romperían el LIKE de resolución de nombre.
TRAILING_FILLER = {
    "exactamente", "realmente", "exacto", "exacta",
    "aproximadamente", "aprox", "concretamente",
}
