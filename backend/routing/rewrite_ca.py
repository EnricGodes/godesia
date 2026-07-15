"""Datos de reescritura catalán → español para el QuestionRewriter.

El motor genérico (rewriter.py) consume estas tablas. Todas las claves y
patrones se comparan sobre texto en minúsculas y SIN acentos (el motor hace
strip de acentos tras proteger los nombres), por eso aquí se escriben sin
tildes: neixer, mes, nasque…
"""

# ── Detección de idioma (tokens sin acento) ──────────────────────────────────
# Fuertes: palabras que no son español válido → señal inequívoca de catalán.
MARKERS_STRONG = {
    "qui", "quins", "quines", "quin", "quina", "quants", "quantes", "quant",
    "on", "amb", "els", "eren", "neixer", "nasque", "fills", "fill", "filla",
    "filles", "germans", "germa", "germana", "germanes", "cosins", "cosi",
    "cosina", "cosines", "avis", "avia", "oncles", "oncle", "nebots", "nebot",
    "neboda", "nets", "besnet", "besavi", "besavia", "besavis", "rebesavi",
    "pare", "mare", "tenir", "persones", "casament", "bateig", "muller",
    "marit", "sogre", "sogra", "sogres", "gendre", "gendres", "cunyat",
    "cunyats", "cunyada", "cunyades", "nores", "parella", "parelles",
    "matrimoni", "parentiu", "relacio", "mitjana", "malnom", "esglesia",
    "cementiri", "nascut", "nascuda", "nascudes", "nascuts", "mori",
    "batejat", "anomenada", "anomenat", "cognom", "cognoms", "avia",
    # vocabulario distintivo catalán (no válido en español) para robustecer la
    # detección: trabajo, mujer/hombre, edad/años, lugar, posesivos, periféstico…
    "treballar", "treballava", "treballa", "feina", "ofici", "dona", "dones",
    "edat", "anys", "lloc", "viure", "visque", "quan", "seva", "seves", "seu",
    "seus", "vaig", "varen", "mudanca", "enterrat", "domicili",
    "avantpassats", "ascendents", "descendents", "rebesnets", "besnets",
    "naixement", "defuncio", "baptisme", "empadronat", "consogres",
}
# Débiles/ambiguos: cuentan 1. "que" NO entra (colisiona con el "qué" español);
# el "què" catalán ya se detecta por su acento grave (CHAR_MARKERS).
MARKERS_WEAK = {"mes", "les", "seva", "seves", "seu", "tambe", "aquest",
                "aquesta", "quan"}
# Caracteres propios del catalán que el español nunca usa (acento grave y ç);
# su presencia en una palabra que no es nombre delata una pregunta catalana
# aunque no tenga ninguna palabra-marcador ("Última residència de…").
CHAR_MARKERS = set("àèòç")

# ── Contracciones con apóstrofo (ANTES de proteger nombres) ──────────────────
PRE_SPLIT = [
    (r"\bd'", "de "),
    (r"\bl'", "el "),
    (r"\bs'", "se "),
    (r"\bn'", "ne "),
]

# Partículas que unen dos tokens-nombre ("Maria dels Àngels", "de la Creu").
# OJO: "i"/"y" NO son conectores aquí — separan dos personas en las preguntas de
# pareja/primos ("X i Y"); las convertimos a "y". (Hay 12 apellidos con "i"
# intercalada tipo "Mestre i Campi"; se aceptan como coste menor.)
NAME_CONNECTORS = {"de", "del", "dels", "la"}

# Keywords catalanas que nunca inician una tirada de nombre (espejo de
# lemmas.NON_NAME_TOKENS para el idioma).
NON_NAME_TOKENS = {
    "qui", "quins", "quines", "quin", "quina", "quants", "quantes", "quant",
    "quan", "on", "amb", "els", "les", "eren", "era", "es", "va", "van",
    "neixer", "fills", "fill", "filla", "filles", "germans", "germa",
    "germana", "germanes", "cosins", "cosi", "cosina", "cosines", "avis",
    "avi", "avia", "oncles", "oncle", "nebots", "nebot", "pare", "pares",
    "mare", "tenir", "persones", "casament", "bateig", "mes",
    "que", "de", "la", "el", "en", "i", "y", "com",
}

# Apellidos que también son término común: solo se protegen como nombre si
# continúan una tirada ("Salvadó Petit"), no si la inician ("més petit").
NAME_CONTINUATION_ONLY = {"petit", "gran"}

# ── Reglas post-protección (dels→de los…) ────────────────────────────────────
PRE_RULES = [
    (r"\bdels\b", "de los"),
    (r"\bals\b", "a los"),
    (r"\bpels\b", "por los"),
    (r"\bpel\b", "por el"),
]

# ── Reglas de frase (reordenación/formas fijas), en orden ────────────────────
PHRASE_RULES = [
    # Artefacto del banco: sufijo de género con barra ("empadronat/ada",
    # "enterrat/ada", "casat/ada") → se queda la forma masculina.
    (r"/ada\b", ""),
    # eventos reflexivos "es va <inf>" → "se <pretérito>"
    (r"\bes va confirmar\b", "se confirmo"), (r"\bes van confirmar\b", "se confirmaron"),
    (r"\bes va batejar\b", "se bautizo"), (r"\bes van batejar\b", "se bautizaron"),
    (r"\bes va mudar\b", "se mudo"), (r"\bes van mudar\b", "se mudaron"),
    # "qui" catalán es invariable; el número lo da el verbo. Algunos patrones
    # españoles exigen "quiénes" plural literal → generarlo ante verbo plural.
    (r"\bqui (eren|son|van|varen|havien|foren|tenien)\b", r"quienes \1"),
    # "quin/quina + verbo copulativo" = "cuál" (no "qué"): "Quina és la mitjana"
    # → "cuál es la media", "Quin és el primer domicili" → "cuál es…".
    (r"\bquin(?:a|s|es)? (es|era|eran|fue|fou|va ser|sera|seria)\b", r"cual \1"),
    (r"\bquin(a|s|es)? (fue|va ser) antes\b", "cual fue antes"),
    (r"\bes van casar\b", "se casaron"),
    (r"\bes va casar\b", "se caso"),
    (r"\bmes gran\b", "mayor"),
    (r"\bmes grans\b", "mayores"),
    (r"\bmes petit\b", "menor"),
    (r"\bmes petita\b", "menor"),
    (r"\bmes jove\b", "menor"),
    (r"\bhi havia\b", "habia"),
    (r"\bhi ha\b", "hay"),
    (r"\bva ser\b", "fue"),
    (r"\bvan ser\b", "fueron"),
]

# ── Perífrasis va/van + infinitiu → pretérito (sing, plur) ───────────────────
PERIPHRASIS = {
    "neixer": ("nacio", "nacieron"),
    "morir": ("murio", "murieron"),
    "tenir": ("tuvo", "tuvieron"),
    "viure": ("vivio", "vivieron"),
    "treballar": ("trabajo", "trabajaron"),
    "estudiar": ("estudio", "estudiaron"),
    "arribar": ("llego", "llegaron"),
    "emigrar": ("emigro", "emigraron"),
    "fer": ("hizo", "hicieron"),
    "provocar": ("provoco", "provocaron"),
    "estar": ("estuvo", "estuvieron"),
}

# ── N-gramas (largo→corto), antes del barrido token a token ──────────────────
# (Se ejecutan DESPUÉS de la perífrasis, así que ya hay "nacio/nacieron/murio".)
MULTIWORD_MAP = [
    (r"\ben quin any\b", "en que ano"),
    (r"\ben quina data\b", "en que fecha"),
    (r"\bde que treballava\b", "de que trabajaba"),
    (r"\bcom a\b", "como"),
    # posesivos "el seu/la seva…" → "su/sus"
    (r"\bel seu\b", "su"), (r"\bla seva\b", "su"),
    (r"\bels seus\b", "sus"), (r"\bles seves\b", "sus"),
    # preposición locativa catalana "a <lugar>" tras verbo de nacimiento/muerte
    (r"\bnacio a\b", "nacio en"), (r"\bnacieron a\b", "nacieron en"),
    (r"\bnacida a\b", "nacida en"), (r"\bnacido a\b", "nacido en"),
    (r"\bnacidas a\b", "nacidas en"), (r"\bnacidos a\b", "nacidos en"),
    # participio catalán "nascud- a <lugar>" (antes de que el token map lo pase
    # a "nacid-"): fija ya la preposición locativa española.
    (r"\bnascuda a\b", "nacida en"), (r"\bnascut a\b", "nacido en"),
    (r"\bnascudes a\b", "nacidas en"), (r"\bnascuts a\b", "nacidos en"),
    (r"\bmurio a\b", "murio en"), (r"\bmurieron a\b", "murieron en"),
    (r"\bcaso a\b", "caso en"), (r"\bcasaron a\b", "casaron en"),
    # artefacto del banco: "va néixer el <año/lugar>" → "nació en <…>".
    # OJO: una fecha completa DD/MM/AAAA conserva "el" (así lo espera el patrón
    # español de nacimiento por fecha), solo el año suelto o el lugar usan "en".
    (r"\bnacio el el\b", "nacio en el"),
    (r"\bnacio el (\d{4})\b", r"nacio en \1"),
    (r"\bnacio el (?=[a-zà-ÿ])", "nacio en "),
    (r"\bmurio el (\d{4})\b", r"murio en \1"),
    (r"\bmurio el (?=[a-zà-ÿ])", "murio en "),
    (r"\ba el arbre\b", "en el arbol"), (r"\bde l'arbre\b", "del arbol"),
    # "cosins segons" = primos segundos ("segons" suelto es "según", no se toca)
    # "la dona de X" / "la seva dona" = esposa (no "mujer" genérica)
    (r"\bdona de\b", "esposa de"), (r"\bseva dona\b", "esposa"),
    (r"\bcosins segons\b", "primos segundos"), (r"\bcosines segones\b", "primas segundas"),
    (r"\bnebots segons\b", "sobrinos segundos"),
    # "per a X" (catalán 'para') → "para X"; "consta/consten per a" muy frecuente
    (r"\bper a\b", "para"),
    # "mort" como sustantivo (causa/la mort) → "muerte" (no "fallecido")
    (r"\bcausa de mort\b", "causa de muerte"), (r"\bla mort de\b", "la muerte de"),
    (r"\bdata de mort\b", "fecha de defuncion"), (r"\bdata de defuncio\b", "fecha de defuncion"),
    # medios hermanos y dato biográfico (concordancia)
    (r"\bmig germans\b", "medios hermanos"), (r"\bmig germanes\b", "medias hermanas"),
    (r"\bdada biografica\b", "dato biografico"), (r"\bdades biografiques\b", "datos biograficos"),
]

# ── Barrido palabra a palabra (claves sin acento) ────────────────────────────
TOKEN_MAP = {
    # interrogativos
    "qui": "quien", "quins": "que", "quines": "que", "quin": "que",
    "quina": "que", "quants": "cuantos", "quantes": "cuantas",
    "quant": "cuanto", "quan": "cuando", "on": "donde", "com": "como",
    # conectores/función
    "amb": "con", "els": "los", "les": "las", "eren": "eran", "mes": "mas",
    "es": "es", "tambe": "tambien", "sense": "sin", "fins": "hasta",
    "seva": "su", "seves": "sus", "seu": "su", "seus": "sus",
    "aquest": "este", "aquesta": "esta",
    # parentescos
    "pare": "padre", "pares": "padres", "mare": "madre",
    "fill": "hijo", "fills": "hijos", "filla": "hija", "filles": "hijas",
    "germa": "hermano", "germans": "hermanos", "germana": "hermana",
    "germanes": "hermanas", "avi": "abuelo", "avia": "abuela",
    "avis": "abuelos", "besavi": "bisabuelo", "besavia": "bisabuela",
    "besavis": "bisabuelos", "rebesavi": "tatarabuelo", "net": "nieto",
    "nets": "nietos", "neta": "nieta", "netes": "nietas",
    "besnet": "bisnieto", "besnets": "bisnietos", "oncle": "tio",
    "oncles": "tios", "cosi": "primo", "cosins": "primos", "cosina": "prima",
    "cosines": "primas", "nebot": "sobrino", "nebots": "sobrinos",
    "neboda": "sobrina", "nebodes": "sobrinas", "marit": "marido",
    "muller": "esposa", "sogre": "suegro", "sogra": "suegra",
    "gendre": "yerno", "gendres": "yernos", "nora": "nuera", "nores": "nueras",
    "cunyat": "cunado", "cunyats": "cunados", "cunyada": "cunada",
    "cunyades": "cunadas", "sogres": "suegros", "sogrs": "suegros",
    "padri": "padrino", "padrins": "padrinos", "padrina": "madrina",
    "fillol": "ahijado", "conjuge": "conyuge", "conjuges": "conyuges",
    "parentiu": "parentesco", "matrimoni": "matrimonio",
    "matrimonis": "matrimonios", "parella": "pareja", "parelles": "parejas",
    "relacio": "relacion",
    # modificadores
    "patern": "paterno", "paterna": "paterna", "matern": "materno",
    "materna": "materna", "segon": "segundo", "segona": "segunda",
    "politic": "politico", "gran": "mayor", "petit": "menor",
    # verbos/eventos
    "neixer": "nacer", "nasque": "nacio", "nascut": "nacido",
    "nascuda": "nacida", "mori": "murio", "mort": "fallecido",
    "morta": "fallecida", "tenir": "tener", "tingue": "tuvo",
    "tenien": "tenian", "treballava": "trabajaba", "casament": "matrimonio",
    "bateig": "bautizo", "batejat": "bautizado", "batejada": "bautizada",
    "enterrat": "enterrado", "enterrada": "enterrada", "descansa": "descansa",
    "viu": "vivo", "residia": "residia",
    # verbos auxiliares/estados
    "te": "tiene", "tenen": "tienen", "tenim": "tenemos",
    # sustantivos/función
    "persones": "personas", "edat": "edad", "anys": "anos", "any": "ano",
    "lloc": "lugar", "data": "fecha", "dia": "dia", "esglesia": "iglesia",
    "cementiri": "cementerio", "ofici": "oficio", "feina": "trabajo",
    "professio": "profesion", "estudis": "estudios", "malnom": "apodo",
    "cognom": "apellido", "cognoms": "apellidos", "nom": "nombre",
    "mitjana": "media", "homes": "hombres", "home": "hombre",
    "dones": "mujeres", "dona": "mujer", "arbre": "arbol",
    "anomenada": "llamada", "anomenat": "llamado",
    "anomenades": "llamadas", "anomenats": "llamados",
    "nascuda": "nacida", "nascudes": "nacidas", "nascuts": "nacidos",
    "notes": "notas", "biografiques": "biograficas", "biografic": "biografico",
    "i": "y",
    # meses
    "gener": "enero", "febrer": "febrero", "marc": "marzo", "maig": "mayo",
    "juny": "junio", "juliol": "julio", "agost": "agosto",
    "setembre": "septiembre", "novembre": "noviembre", "desembre": "diciembre",
    # ── vocabulario ampliado (capacidades nuevas del router) ──────────────
    # parentescos: femeninos plurales (para el filtro de sexo) y lado plural
    "ties": "tias", "avies": "abuelas",
    "rebesavis": "tatarabuelos", "rebesavia": "tatarabuela", "rebesavies": "tatarabuelas",
    "rebesnet": "tataranieto", "rebesnets": "tataranietos",
    "rebesneta": "tataranieta", "rebesnetes": "tataranietas",
    "materns": "maternos", "paterns": "paternos",
    "maternes": "maternas", "paternes": "paternas", "branca": "rama",
    "varons": "varones", "varo": "varon",
    # políticos (in-laws) y consuegros
    "politics": "politicos", "politiques": "politicas",
    "consogre": "consuegro", "consogres": "consuegros",
    # ancestros/descendientes conocidos
    "avantpassat": "antepasado", "avantpassats": "antepasados",
    "ascendent": "ascendiente", "ascendents": "ascendientes",
    "descendent": "descendiente", "descendents": "descendientes",
    "conegut": "conocido", "coneguts": "conocidos",
    "coneguda": "conocida", "conegudes": "conocidas",
    # eventos
    "baptisme": "bautismo", "batejar": "bautizar",
    "empadronat": "censado", "empadronada": "censada", "empadronats": "censados",
    "apareix": "aparece", "apareixen": "aparecen", "cens": "censo",
    "mudanca": "mudanza", "mudances": "mudanzas",
    "immigracio": "inmigracion", "immigracions": "inmigraciones",
    "emigracio": "emigracion", "arribar": "llegar",
    "defuncio": "defuncion", "treball": "trabajo",
    "enterrament": "entierro", "sepultura": "sepultura",
    "domicili": "domicilio", "domicilis": "domicilios",
    "confirmacio": "confirmacion", "comunio": "comunion",
    "nacionalitat": "nacionalidad", "religio": "religion",
    "educacio": "educacion", "formacio": "formacion",
    "malaltia": "enfermedad", "entitat": "entidad", "membre": "miembro",
    "consten": "constan", "viure": "vivir", "visque": "vivio",
    # evento genérico y campos
    "fet": "hecho", "documentat": "documentado", "documentada": "documentada",
    "dada": "dato", "dades": "datos", "esdeveniment": "evento",
    "esdeveniments": "eventos", "centre": "centro", "mig": "medio",
    "premi": "premio", "funeral": "funeral", "obituari": "obituario",
    "reunio": "reunion", "servei": "servicio", "allistament": "alistamiento",
}
