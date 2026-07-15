"""Datos de reescritura inglés → español para el QuestionRewriter.

A diferencia del catalán (mapeo casi palabra a palabra), el inglés cambia el
orden de las palabras y usa auxiliares ("did … have", "was … born"), así que el
grueso del trabajo lo hacen las PHRASE_RULES de reordenación. Los nombres van
protegidos como centinelas antes de aplicarlas, de modo que cada regla captura
el nombre con un grupo y lo recoloca en la posición española.
"""

# ── Detección de idioma ──────────────────────────────────────────────────────
# Palabras inglesas que no son español válido. Se excluyen las ambiguas ("a",
# "no", "son", "en", "de", "la", "el" aparecen en el contenido español mixto).
MARKERS_STRONG = {
    "who", "what", "where", "when", "which", "whom", "whose", "did", "does",
    "were", "was", "born", "die", "died", "marry", "married", "have", "had",
    "children", "child", "siblings", "sibling", "parents", "parent", "father",
    "mother", "grandparents", "grandmother", "grandfather", "cousins", "cousin",
    "uncles", "aunts", "nephews", "nieces", "grandchildren", "spouse", "husband",
    "wife", "brother", "sister", "the", "of", "how", "many", "people", "tree",
    "recorded", "associated", "with", "their", "they", "surname", "descendants",
    "relationship", "old", "married", "born", "first", "percentage", "approximately",
    "average", "generation", "survived", "rank", "branch", "couple",
    # "ranking" NO: es préstamo usado también en español ("ranking de descendencia").
    "birth", "name", "occupation", "activity", "residence", "address", "documented",
    "year", "years",  # inglés puro; útil en preguntas casi españolas ("más years")
}
MARKERS_WEAK = {"are", "is", "and", "or", "in", "that", "was", "for"}
CHAR_MARKERS = set()  # el inglés no tiene caracteres propios

# Genitivo sajón "X's <rel>": se marca el apóstrofo posesivo ANTES de proteger
# el nombre (así "Ballart's" no rompe la protección) con un token "zzgen" que
# luego una PHRASE_RULE usa para reordenar a "<rel> de X".
PRE_SPLIT = [(r"([a-zà-ÿ])'s\b", r"\1 zzgen")]
NAME_CONNECTORS = {"de", "del", "la"}
NON_NAME_TOKENS = {
    "who", "what", "where", "when", "which", "did", "does", "were", "was",
    "are", "is", "the", "of", "and", "or", "in", "with", "how", "many",
    "have", "had", "born", "die", "died", "marry", "married", "children",
    "siblings", "parents", "father", "mother", "grandparents", "cousins",
    "uncles", "aunts", "people", "their", "they", "first", "de", "la", "el",
    "en", "que", "y",
    # "more" es palabra inglesa frecuente en las preguntas ("had more children")
    # pero también apellido real ("More"): nunca la tratamos como nombre.
    "more",
}
NAME_CONTINUATION_ONLY = set()

PRE_RULES = []

# ── Reglas de frase (reordenación), de más específica a más genérica ─────────
PHRASE_RULES = [
    # --- estructuras del banco GEDCOM (genitivo sajón, "did X have", "recorded
    #     for X") + eventos/vitales ---
    (r"\bwho (?:was|were) (.+?) zzgen (.+?)\s*$", r"\2 de \1"),   # X's <rel>
    (r"\b(?:which|what) (.+?) did (?!the couple)(.+?) have\s*$", r"que \1 tuvo \2"),
    # vitales específicas ANTES de la genérica "recorded for"
    (r"\bwhat death date is recorded for (.+?)\s*$", r"en que fecha murio \1"),
    (r"\bwhat birth date is recorded for (.+?)\s*$", r"en que fecha nacio \1"),
    (r"\bwhat marriage place is recorded for (.+?)\s*$", r"donde se caso \1"),
    (r"\bwhat marriage date is recorded for (.+?)\s*$", r"en que fecha se caso \1"),
    (r"\bwhat partners? (?:is|are) recorded for (.+?)\s*$", r"con quien se caso \1"),
    (r"\b(?:what|which) (.+?) (?:is|are) recorded for (.+?)\s*$", r"que \1 constan para \2"),
    (r"\bwhere was (.+?) originally from\b", r"de donde era \1"),
    (r"\bat what age did (.+?) die\b", r"a que edad murio \1"),
    (r"\bwhere did (.+?) study\b", r"donde estudio \1"),
    (r"\bwhere did (.+?) move to\b", r"a donde se mudo \1"),
    (r"\bon what date did (.+?) get married\b", r"en que fecha se caso \1"),
    (r"\bwhere was (.+?) confirmed\b", r"donde se confirmo \1"),
    (r"\bwhere was (.+?) (?:baptized|baptised)\b", r"donde se bautizo \1"),
    (r"\bat what institution did (.+?) study\b", r"en que centro estudio \1"),
    (r"\bwho was (.+?) married to\b", r"con quien se caso \1"),
    (r"\bin what place did (.+?) die\b", r"donde murio \1"),
    (r"\bwhere was (.+?) buried\b", r"donde fue enterrado \1"),
    (r"\bwhere did (.+?) die\b", r"donde murio \1"),
    (r"\bwhere does (.+?) appear in the census\b", r"donde aparece censado \1"),
    (r"\bon what date was (.+?) (?:baptized|baptised)\b", r"en que fecha se bautizo \1"),
    (r"\bon what date was (.+?) buried\b", r"en que fecha fue enterrado \1"),
    (r"\bwhen did (.+?) get married\b", r"cuando se caso \1"),
    (r"\bwhere did (.+?) get married\b", r"donde se caso \1"),
    (r"\bin what place was (.+?) born\b", r"en que lugar nacio \1"),
    (r"\bin what place was (.+?) (?:baptized|baptised)\b", r"en que lugar se bautizo \1"),
    (r"\bin what place did (.+?) get married\b", r"en que lugar se caso \1"),
    (r"\bat (?:which|what) addresses did (.+?) live\b", r"en que domicilios vivio \1"),
    (r"\bwhere did (.+?) live\b", r"donde vivio \1"),
    (r"\bwhen is (.+?) recorded as having been born\b", r"cuando nacio \1"),
    (r"\bwhat did (.+?) do for a living\b", r"de que trabajaba \1"),
    (r"\bwhat partner is recorded for (.+?)\s*$", r"con quien se caso \1"),
    (r"\b(.+?) zzgen (.+?)\s*$", r"\2 de \1"),   # genitivo residual
    # --- preguntas COMPUESTAS (base + coletilla): van primero porque el español
    #     las resuelve con un handler específico distinto al de la base ---
    (r"\bhow old was (.+?) when their first child was born,? and is that above or below average\b",
     r"que edad tenia \1 cuando nacio su primer hijo y esta por encima o por debajo de la media"),
    (r"\bhow many siblings did (.+?) have,? and how does that compare with the rest of their generation\b",
     r"cuantos hermanos tenia \1 y como se compara con el resto de su generacion"),
    (r"\bwhat relationship did (.+?) have with (.+?),? and which of the two was older\b",
     r"que parentesco tenia \1 con \2 y cual de los dos era mayor"),
    (r"\bhow many people died in (.+?),? and what relevance does that place have among recorded deaths\b",
     r"cuantas personas murieron en \1 y que relevancia tiene ese lugar en las defunciones registradas"),
    (r"\bwhich people were born and died in (.+)$", r"que personas nacieron y murieron en \1"),
    (r"\bwhich people have a compound name like (.+)$", r"que personas tienen un nombre compuesto como \1"),
    (r"\bhow many children did (.+?) have compared with the tree average\b",
     r"cuantos hijos tuvo \1 en comparacion con la media del arbol"),
    (r"\bwhat rank does (.+?) hold in the descendant ranking\b",
     r"en que puesto del ranking de descendencia se situa \1"),
    (r"\bwhich couple had exactly (\d+) children,? and where do they rank by family size\b",
     r"que pareja tuvo exactamente \1 hijos y en que posicion queda por tamano familiar"),
    (r"\bhow many people have a known birth date compared with those who do not\b",
     "cuantas personas tienen fecha de nacimiento conocida frente a las que no la tienen"),
    (r"\bwhich branch had more children ?: the one formed by (.+?) and (.+?),? or the next couple in the ranking\b",
     r"que rama tuvo mas hijos: la formada por \1 y \2 o la siguiente pareja en el ranking"),
    (r"\bwhich birthplace has more spelling variants ?: (.+?),? or another place\b",
     r"que lugar de nacimiento tiene mas variantes de escritura: \1 u otro lugar"),
    (r"\bin what birth order position among siblings was (.+)$", r"en que posicion entre sus hermanos nacio \1"),
    (r"\bwhat children did the couple formed by (.+?) and (.+?), who married in (.+), have$",
     r"que hijos tuvo la pareja que se caso en \3 formada por \1 y \2"),
    # artefacto del banco: "Was Era X a grandfather or grandmother of Y" (doble verbo)
    (r"\bwas era (.+?) a grandfather or grandmother of (.+)$", r"era \1 abuelo o abuela de \2"),
    (r"\bwho did (.+?) marry,? and on what date was the wedding\b", r"con quien se caso \1 y en que fecha fue la boda"),
    (r"\bwhich marriage had the most documented descendants\b", "que matrimonio tuvo mas descendencia documentada"),
    (r"\bwho is the person with the most recorded children in the whole tree\b", "cual es la persona con mas hijos registrados en todo el arbol"),
    (r"\bwhat trade was (.+?) dedicated to\b", r"a que oficio se dedico \1"),
    (r"\bat what age did (.+?) marry\b", r"a que edad se caso \1"),
    (r"\bhow long did (.+?) live\b", r"cuanto tiempo vivio \1"),
    # --- eventos con auxiliar "did/was" ---
    (r"\bwho did (.+?) marry\b", r"con quien se caso \1"),
    (r"\bwhat children did (.+?) have\b", r"que hijos tuvo \1"),
    (r"\bhow many children did the marriage of (.+?) and (.+?) have\b", r"cuantos hijos tuvo el matrimonio de \1 y \2"),
    (r"\bhow many children did (.+?) have\b", r"cuantos hijos tuvo \1"),
    (r"\bhow many siblings did (.+?) have\b", r"cuantos hermanos tuvo \1"),
    (r"\bhow many children survived (.+)$", r"cuantos hijos sobrevivieron a \1"),
    (r"\bwhere did (.+?) die\b", r"donde murio \1"),
    (r"\bwhere and when did (.+?) die\b", r"donde y cuando murio \1"),
    (r"\bwhere was (.+?) born\b", r"donde nacio \1"),
    (r"\bwhen was (.+?) born\b", r"cuando nacio \1"),
    (r"\bwho was born in\b", "quien nacio en"),
    (r"\bwho was born on\b", "quien nacio el"),
    (r"\bwas born before\b", "nacio antes"), (r"\bwas born first\b", "nacio primero"),
    (r"\bedad married\b", "edad se caso"),
    (r"\bwhich people were born in\b", "que personas nacieron en"),
    (r"\bwho were born in\b", "quienes nacieron en"),
    (r"\bhow many people were born in\b", "cuantas personas nacieron en"),
    (r"\bwhich people died in\b", "que personas murieron en"),
    (r"\bhow many people died in\b", "cuantas personas murieron en"),
    (r"\bwhich couples married in\b", "que parejas se casaron en"),
    (r"\bwho lived the longest\b", "quien vivio mas anos"),
    (r"\bwho is older ?,? (.+?) or (.+)$", r"quien es mayor, \1 o \2"),
    # "which" + cópula = "cuál" (no "qué"): "Which es la media" → "cuál es la media".
    (r"\bwhich (is|was|were|es|era|eran)\b", r"cual \1"),
    # --- edad / primer hijo / matrimonio ---
    (r"\bhow old was (.+?) when their first child\b.*?\bwas born\b", r"a que edad tuvo su primer hijo \1"),
    (r"\bhow old was (.+?) when they married\b", r"a que edad se caso \1"),
    (r"\bhow old did (.+?) live\b", r"que edad vivio \1"),
    # --- atributos ---
    (r"\bwhich people have (.+?) as their first surname\b", r"que personas tienen \1 como primer apellido"),
    (r"\bwhat occupation or activity is recorded for (.+)$", r"que ocupacion o actividad figura registrada para \1"),
    (r"\bat what residence or address is (.+?) documented\b", r"en que residencia o direccion aparece documentado \1"),
    (r"\bwhat biographical notes are associated with (.+)$", r"que notas biograficas hay asociadas a \1"),
    (r"\bdid (.+?) have descendants\b", r"tiene descendencia \1"),
    (r"\bfrom which marriage or couple was (.+?) born\b", r"de que matrimonio o pareja nacio \1"),
    (r"\bwhich people in the tree have a given name starting with (.+)$", r"que personas del arbol tienen un nombre de pila que empieza por \1"),
    (r"\bapproximately what percentage of the tree corresponds to people whose first surname is (.+)$", r"que porcentaje aproximado del arbol corresponde a personas con primer apellido \1"),
    (r"\bwho were the parents and children of (.+)$", r"quienes fueron los padres y los hijos de \1"),
    (r"\bwho were the parents and siblings of (.+)$", r"quienes fueron los padres y los hermanos de \1"),
    (r"\bhow many births are recorded in the (\d{3})0s\b", r"cuantos nacimientos hay en la decada de \g<1>0"),
    (r"\bhow many deaths are recorded in the (\d{3})0s\b", r"cuantos fallecimientos hay en la decada de \g<1>0"),
    (r"\bwho died on (.+)$", r"quien murio el \1"),
    # --- relaciones entre dos personas ---
    (r"\bwhat relationship did (.+?) have with (.+)$", r"que relacion tenia \1 con \2"),
    (r"\bwhat was the relationship between (.+?) and (.+)$", r"que parentesco hay entre \1 y \2"),
    (r"\bwere (.+?) and (.+?) first cousins\b", r"eran primos \1 y \2"),
    (r"\bwhich came first ?: the birth of (.+?) or that of (.+)$", r"cual fue antes: el nacimiento de \1 o el de \2"),
    (r"\bwho was older when they married ?: (.+?) or (.+)$", r"quien era mayor cuando se casaron: \1 o \2"),
    # --- relaciones "who were/are/was the REL of X" (genéricas al final) ---
    (r"\bwho were the (.+?) of (.+)$", r"quienes eran los \1 de \2"),
    (r"\bwho are the (.+?) of (.+)$", r"quienes son los \1 de \2"),
    (r"\bwho was the (.+?) of (.+)$", r"quien era el \1 de \2"),
    (r"\bwho is the (.+?) of (.+)$", r"quien es el \1 de \2"),
    # "was born" adyacente (al FINAL: las reglas específicas de nacimiento y de
    # "primer hijo … was born" ya se han aplicado antes).
    (r"\bwas born\b", "nacio"),
]

PERIPHRASIS = {}

# ── N-gramas (antes del barrido token a token) ───────────────────────────────
MULTIWORD_MAP = [
    (r"\bwith whom\b", "con quien"),
    # ── relaciones compuestas y con género (banco GEDCOM) ────────────────────
    # las "... and ..." y las maternal/paternal ANTES que las formas simples
    (r"\bgreat-uncles and great-aunts\b", "tios abuelos"),
    (r"\b(?:maternal-branch|maternal) grandparents\b", "abuelos maternos"),
    (r"\b(?:paternal-branch|paternal) grandparents\b", "abuelos paternos"),
    (r"\bmaternal-branch uncles and aunts\b", "tios maternos"),
    (r"\bpaternal-branch uncles and aunts\b", "tios paternos"),
    (r"\bdirect descendants\b", "descendencia directa"),
    (r"\bmaternal uncles and aunts\b", "tios maternos"),
    (r"\bpaternal uncles and aunts\b", "tios paternos"),
    (r"\buncles and aunts\b", "tios"),
    (r"\bgreat-great-grandchildren\b", "tataranietos"),
    (r"\bgreat-grandchildren\b", "bisnietos"),
    (r"\bdeath date\b", "fecha de defuncion"),
    (r"\bbirth date\b", "fecha de nacimiento"),
    (r"\bgreat-nephews and great-nieces\b", "sobrinos nietos"),
    (r"\bnephews and nieces\b", "sobrinos"),
    (r"\bsons- and daughters-in-law\b", "hijos politicos"),
    (r"\bco-parents-in-law\b", "consuegros"),
    (r"\bsiblings-in-law\b", "cunados"),
    (r"\bparents-in-law\b", "suegros"),
    (r"\bmaternal grandparents\b", "abuelos maternos"),
    (r"\bpaternal grandparents\b", "abuelos paternos"),
    (r"\bknown ancestors\b", "antepasados conocidos"),
    (r"\bknown descendants\b", "descendientes conocidos"),
    (r"\bfull siblings\b", "hermanos completos"),
    (r"\bhalf-siblings\b", "medios hermanos"),
    (r"\bmale cousins\b", "primos varones"), (r"\bfemale cousins\b", "primas"),
    (r"\bbiographical detail\b", "dato biografico"),
    (r"\bcause of death\b", "causa de muerte"),
    (r"\bdivorce date\b", "fecha de divorcio"),
    (r"\bfirst communion\b", "primera comunion"),
    # "brothers and sisters" = hermanos (ambos), ANTES de "brothers"→varones
    (r"\bbrothers and sisters\b", "hermanos"),
    # gendered plurales (tras los compuestos "... and ...")
    (r"\bgrandmothers\b", "abuelas"), (r"\bgrandfathers\b", "abuelos varones"),
    (r"\bgrandsons\b", "nietos varones"), (r"\bgranddaughters\b", "nietas"),
    (r"\bbrothers\b", "hermanos varones"), (r"\bsons\b", "hijos varones"),
    (r"\bdaughters\b", "hijas"),
    (r"\bnephews\b", "sobrinos varones"), (r"\buncles\b", "tios varones"),
    (r"\bspouses\b", "conyuges"), (r"\bancestors\b", "antepasados"),
    (r"\bmother-in-law or father-in-law\b", "suegra o el suegro"),
    (r"\bmother-in-law\b", "suegra"), (r"\bfather-in-law\b", "suegro"),
    (r"\bsister-in-law\b", "cunada"), (r"\bbrother-in-law\b", "cunado"),
    (r"\bmaternal great-great-grandmother\b", "tatarabuela materna"),
    (r"\bpaternal great-great-grandmother\b", "tatarabuela paterna"),
    (r"\bmaternal great-great-grandfather\b", "tatarabuelo materno"),
    (r"\bpaternal great-great-grandfather\b", "tatarabuelo paterno"),
    (r"\bgreat-great-grandmother\b", "tatarabuela"),
    (r"\bgreat-great-grandfather\b", "tatarabuelo"),
    (r"\bgiven name\b", "nombre de pila"),
    (r"\bof the\b", "del"), (r"\bin the\b", "en el"),
    (r"\bhow many\b", "cuantos"),
    # los compuestos maternal/paternal ANTES que las formas simples (que si no
    # los consumen y dejan "maternal" sin traducir)
    (r"\bmaternal great-grandmother\b", "bisabuela materna"),
    (r"\bpaternal great-grandmother\b", "bisabuela paterna"),
    (r"\bmaternal great-grandfather\b", "bisabuelo materno"),
    (r"\bpaternal great-grandfather\b", "bisabuelo paterno"),
    (r"\bmaternal grandmother\b", "abuela materna"),
    (r"\bpaternal grandmother\b", "abuela paterna"),
    (r"\bmaternal grandfather\b", "abuelo materno"),
    (r"\bpaternal grandfather\b", "abuelo paterno"),
    (r"\bgreat-great-grandparents\b", "tatarabuelos"),
    (r"\bgreat-grandparents\b", "bisabuelos"),
    (r"\bgreat-grandmother\b", "bisabuela"),
    (r"\bgreat-grandfather\b", "bisabuelo"),
    (r"\bsecond cousins\b", "primos segundos"),
    (r"\bfirst cousins\b", "primos"),
    (r"\bfirst surname\b", "primer apellido"),
]

# ── Barrido palabra a palabra ────────────────────────────────────────────────
TOKEN_MAP = {
    "who": "quien", "what": "que", "where": "donde", "when": "cuando",
    "which": "que", "whom": "quien", "were": "eran", "was": "era",
    "are": "son", "is": "es", "the": "el", "in": "en", "on": "en",
    "of": "de", "and": "y", "or": "o", "their": "su", "with": "con",
    "older": "mayor",
    # parentescos
    "children": "hijos", "child": "hijo", "siblings": "hermanos",
    "sibling": "hermano", "parents": "padres", "parent": "padre",
    "father": "padre", "mother": "madre", "grandparents": "abuelos",
    "grandmother": "abuela", "grandfather": "abuelo", "grandchildren": "nietos",
    "cousins": "primos", "cousin": "primo", "uncles": "tios", "aunts": "tias",
    "nephews": "sobrinos", "nieces": "sobrinas", "spouse": "conyuge",
    "husband": "marido", "wife": "esposa", "brother": "hermano",
    "sister": "hermana", "brothers": "hermanos", "sisters": "hermanas",
    "couples": "parejas", "births": "nacimientos", "deaths": "defunciones",
    "marriages": "matrimonios",
    # sustantivos/función
    "people": "personas", "tree": "arbol", "family": "familia",
    "name": "nombre", "surname": "apellido", "birth": "nacimiento",
    "occupation": "ocupacion", "activity": "actividad", "residence": "residencia",
    "address": "direccion", "descendants": "descendencia",
    "relationship": "relacion", "percentage": "porcentaje", "rank": "rango",
    "ranking": "ranking", "average": "media", "generation": "generacion",
    "branch": "rama", "couple": "pareja", "marriage": "matrimonio",
    # verbos/participios
    "born": "nacido", "died": "murio", "die": "morir", "married": "casado",
    "recorded": "registrada", "associated": "asociadas",
    "documented": "documentado", "survived": "sobrevivieron",
    # otros
    "first": "primer", "approximately": "aproximadamente",
    "percentage": "porcentaje", "date": "fecha", "wedding": "boda",
    "year": "ano", "years": "anos", "trade": "oficio", "whole": "todo",
    "most": "mas",
    # capacidades nuevas
    "census": "censo", "event": "evento", "buried": "enterrado",
    "baptized": "bautizado", "baptised": "bautizado", "grandmothers": "abuelas",
    "nieces": "sobrinas", "sisters": "hermanas", "aunts": "tias",
    "immigration": "inmigracion", "emigration": "emigracion",
    "religion": "religion", "nationality": "nacionalidad",
    "education": "educacion", "confirmation": "confirmacion",
    "move": "mudanza", "moved": "mudanza",
}
