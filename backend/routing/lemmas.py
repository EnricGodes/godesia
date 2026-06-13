"""Vocabulario controlado castellano para la capa de intención.

Modelo: cada nombre de parentesco pertenece a una FAMILIA. La pregunta debe
mencionar UNA sola familia; si menciona dos (p.ej. "padre de la madre de X") es
una cadena/compuesto y cedemos al router de patrones. Dentro de la familia, unas
REGLAS ordenadas con modificadores (paterno/materno, segundos…) eligen el handler.

Se mapean TOKENS COMPLETOS (no prefijos), de modo que una entrada cubre todas las
formas verbales sin enumerarlas y sin colisiones de raíz (`cas`->casa, `prim`->primero).

Añadir una intención = registrar sus tokens en FAMILIES y una regla en RULES.
"""

# --- Familia de relación por token (vocabulario MAESTRO) -------------------
# Incluye también familias SIN reglas todavía (spouse, inlaw…): así el guard de
# "una sola familia" detecta cadenas y cedemos limpiamente.
FAMILIES = {
    # parentescos con reglas (migrados)
    "padres": "parents", "progenitores": "parents",
    "padre": "father", "papa": "father",
    "madre": "mother", "mama": "mother",
    "hijos": "children", "hijas": "children",
    "hermanos": "siblings", "hermanas": "siblings",
    "abuelo": "grandparents", "abuela": "grandparents",
    "abuelos": "grandparents", "abuelas": "grandparents",
    "avi": "grandparents", "avia": "grandparents", "avis": "grandparents", "avies": "grandparents",
    "primo": "cousins", "prima": "cousins", "primos": "cousins", "primas": "cousins",
    "cosi": "cousins", "cosins": "cousins", "cosina": "cousins", "cosines": "cousins",
    "tio": "uncles", "tia": "uncles", "tios": "uncles", "tias": "uncles",
    "oncle": "uncles", "oncles": "uncles",
    "sobrino": "nephews", "sobrina": "nephews", "sobrinos": "nephews", "sobrinas": "nephews",
    "nebot": "nephews", "nebots": "nephews",
    "nieto": "grandchildren", "nieta": "grandchildren", "nietos": "grandchildren", "nietas": "grandchildren",
    "bisabuelo": "greatgrandparents", "bisabuela": "greatgrandparents",
    "bisabuelos": "greatgrandparents", "bisabuelas": "greatgrandparents",
    # atributos de persona (no parentescos). Tokens COMPLETOS: "casa" (residencia)
    # y "caso/casarse" (matrimonio) NO colisionan, que era justo el problema de
    # usar la raíz cruda.
    "trabajo": "occupation", "trabaja": "occupation", "trabajaba": "occupation",
    "trabajaban": "occupation", "trabajaron": "occupation", "trabajar": "occupation",
    "oficio": "occupation", "oficios": "occupation",
    "profesion": "occupation", "profesiones": "occupation",
    "ocupacion": "occupation", "ocupaciones": "occupation",
    "empleo": "occupation", "empleos": "occupation",
    "dedicaba": "occupation", "dedicaban": "occupation", "dedico": "occupation",
    "vivia": "residence", "vivian": "residence", "vivio": "residence",
    "vivieron": "residence", "vive": "residence", "viven": "residence", "vivido": "residence",
    "residia": "residence", "residio": "residence",
    "residencia": "residence", "residencias": "residence",
    "domicilio": "residence", "domicilios": "residence",
    "direccion": "residence", "direcciones": "residence",
    "casa": "residence", "casas": "residence", "morada": "residence",
    "caso": "marriage", "casar": "marriage", "casarse": "marriage",
    "casado": "marriage", "casada": "marriage", "casados": "marriage", "casadas": "marriage",
    "casaron": "marriage", "casaban": "marriage", "casamiento": "marriage",
    "boda": "marriage", "bodas": "marriage", "matrimonio": "marriage", "matrimonios": "marriage",
    "esposo": "marriage", "esposa": "marriage", "esposos": "marriage", "esposas": "marriage",
    "conyuge": "marriage", "conyuges": "marriage", "marido": "marriage", "maridos": "marriage",
    "pareja": "marriage", "parejas": "marriage", "companera": "marriage", "companero": "marriage",
    # familias SIN reglas (solo para el guard de cadenas; cederán al router)
    "suegro": "inlaw", "suegra": "inlaw", "suegros": "inlaw", "suegras": "inlaw",
    "consuegro": "inlaw", "consuegros": "inlaw",
    "nuera": "inlaw", "nueras": "inlaw", "yerno": "inlaw", "yernos": "inlaw",
    "cunado": "inlaw", "cunada": "inlaw", "cunados": "inlaw", "cunadas": "inlaw",
    "padrino": "godparents", "padrinos": "godparents", "madrina": "godparents", "madrinas": "godparents",
    "bisnieto": "greatgrandchildren", "bisnieta": "greatgrandchildren",
    "bisnietos": "greatgrandchildren", "bisnietas": "greatgrandchildren",
    "tatarabuelo": "ggparents", "tatarabuela": "ggparents",
    "tatarabuelos": "ggparents", "tatarabuelas": "ggparents",
    "tataranieto": "ggchildren", "tataranietos": "ggchildren",
}

# "primos hermanos" = primos hermanos (primer grado): cuando hay 'primos', el
# token 'hermanos' es modificador, no la familia 'siblings'.
COUSINS_TOKENS = {"primo", "prima", "primos", "primas", "cosi", "cosins", "cosina", "cosines"}

# Modificadores: no cuentan como familia y se saltan al extraer el sujeto.
MODIFIERS = {"paterno", "paterna", "materno", "materna", "segundos", "segundas", "hermanos", "hermanas"}


# Sustantivos de cónyuge: disparan la rama "quién" del matrimonio.
SPOUSE_NOUNS = {
    "esposo", "esposa", "esposos", "esposas", "conyuge", "conyuges",
    "marido", "maridos", "pareja", "parejas", "companera", "companero",
}

# --- Reglas por familia (ordenadas, la primera que encaja gana) -------------
# Tupla: (req_all: tokens que deben estar TODOS,
#         req_any: si no está vacío, al menos UNO debe estar,
#         forbids: tokens que NO deben estar,
#         handler, plantilla canónica con {s})
# Sin regla (o ninguna encaja) => None => cede al router de 163 patrones.
RULES = {
    "parents":  [(set(), set(), set(), "handle_parents", "padres de {s}")],
    "father":   [(set(), set(), set(), "handle_father", "padre de {s}")],
    "mother":   [(set(), set(), set(), "handle_mother", "madre de {s}")],
    "children": [(set(), set(), set(), "handle_children", "hijos de {s}")],
    "siblings": [(set(), set(), set(), "handle_siblings", "hermanos de {s}")],
    "grandparents": [
        ({"paterno"}, set(), set(), "handle_paternal_grandfather", "abuelo paterno de {s}"),
        ({"materna"}, set(), set(), "handle_maternal_grandmother", "abuela materna de {s}"),
        # General SOLO si no hay lado: "abuelo materno"/"abuela paterna" no tienen
        # handler propio → ninguna regla encaja → cede.
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
    # Bisabuelos solo en general: "bisabuela materna"/"bisabuelo paterno" no
    # tienen handler propio → cede (igual que abuelos).
    "greatgrandparents": [
        (set(), set(), {"paterno", "paterna", "materno", "materna"}, "handle_great_grandparents", "bisabuelos de {s}"),
    ],
    # --- atributos ---
    "occupation": [(set(), set(), set(), "handle_occupation_natural", "de que trabajaba {s}")],
    "residence":  [(set(), set(), set(), "handle_last_residence", "donde vivia {s}")],
    "marriage": [
        # lugar
        (set(), {"donde", "lugar", "iglesia", "sitio"}, set(), "handle_marriage_date_place", "donde se caso {s}"),
        # fecha
        (set(), {"cuando", "fecha", "ano", "dia"}, set(), "handle_marriage_date_place", "cuando se caso {s}"),
        # cónyuge (sustantivo)
        (set(), SPOUSE_NOUNS, set(), "handle_spouse", "conyuge de {s}"),
        # "con quién se casó"
        (set(), {"quien", "quienes"}, set(), "handle_spouse_or_partner", "con quien se caso {s}"),
        # "matrimonio/boda de X" a secas es ambiguo → ninguna regla → cede.
    ],
}


# --- Guardas globales: si aparece cualquiera, cedemos al router de patrones --
# Redirigen a handlers más específicos (conteos, extremos) o a intenciones no
# migradas (lugar/fecha, matrimonio). Garantía de cero regresiones.
GLOBAL_CEDE = {
    # conteos / cantidad -> handlers *_count
    "cuantos", "cuantas", "cuanta", "cuanto", "numero", "cantidad",
    "muchos", "muchas", "pocos", "pocas", "bastantes", "numerosos", "numerosas",
    # extremos / orden de nacimiento (ordinales en singular)
    "mayor", "menor", "mayores", "primer", "primera", "primero",
    "ultimo", "ultima", "segundo", "segunda",
    # listas por lugar / fecha
    "nacio", "nacieron", "nacida", "nacido", "nacimiento",
    "murio", "murieron", "fallecio", "fallecieron", "muerte", "defuncion",
    "enterrado", "enterrada", "sepultado", "sepultada",
    # residencia con submodo (última/primer/al final) → handler con su lógica
    "final",
    # agregados / descendencia
    "descendencia", "descendientes", "vivos", "vivas", "longeva", "longevo",
}


# Relleno que se elimina del PRINCIPIO del sujeto, tras la frase de relación.
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

# Palabras admitidas ANTES del término de relación. El sujeto de "REL de SUJETO"
# va siempre DESPUÉS de la relación; si delante hay algo que no sea palabra
# función o muletilla (p.ej. un nombre propio), es otra estructura —típicamente
# "¿Era X abuelo de Y?" (sí/no)— y cedemos al router de patrones.
ALLOWED_PREFIX = LEADING_FILLER | {
    "dime", "dame", "digame", "nombrame", "nombra", "nombres", "nombre",
    "me", "nos", "puedes", "podrias", "decir", "sacas", "saca",
    "conoces", "sabes", "recuerdas", "indica", "indicame",
    "lista", "enumera", "menciona", "familia", "grupo",
    # interrogativos de atributo: "a/en qué trabajaba", "dónde vivía",
    # "con quién/dónde/cuándo se casó"
    "a", "en", "con", "donde", "cuando",
}
