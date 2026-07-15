"""Datos de reescritura francés → español para el QuestionRewriter.

El francés combina reordenación (como el inglés) con contracciones de apóstrofo
(como el catalán) y una peculiaridad del banco: el traductor conservó ambos
géneros en las inversiones ("est-il/elle né(e)", "a-t-il/elle eus"). Por eso el
grueso son PHRASE_RULES que absorben esas inversiones y recolocan el nombre
(protegido como centinela).
"""

# ── Detección de idioma ──────────────────────────────────────────────────────
MARKERS_STRONG = {
    "qui", "quel", "quelle", "quels", "quelles", "ou", "quand", "comment",
    "combien", "etaient", "etait", "sont", "avec", "enfants", "enfant",
    "freres", "surs", "soeurs", "frere", "parents", "pere", "mere",
    "grands", "grand", "cousins", "cousines", "oncles", "tantes", "neveux",
    "nieces", "conjoint", "epoux", "epouse", "petits", "belle", "beau",
    "naissance", "naissances", "mariage", "decede", "decedee", "ne", "nee",
    "eus", "avait", "lorsqu", "lequel", "laquelle", "rang", "classement",
    "descendance", "arbre", "moyenne", "generation", "survecu", "annees",
    "residence", "adresse", "documente", "profession", "activite",
    "enregistree", "enregistrees", "biographiques", "associees", "posterieur",
    "anterieur", "parente", "lien", "nom", "famille", "personnes", "ans",
}
MARKERS_WEAK = {"les", "des", "aux", "leur", "leurs", "est", "sont", "dans",
                "par", "rapport", "comme", "entre"}
# Caracteres propios del francés que ni el español ni el catalán usan: acento
# circunflejo (â/ê/î/ô/û), la ù y la ligadura œ.
CHAR_MARKERS = set("âêîôûùœ")

# ── Contracciones con apóstrofo (ANTES de proteger nombres) ──────────────────
PRE_SPLIT = [
    (r"\bd'", "de "), (r"\bl'", "le "), (r"\bqu'", "que "),
    (r"\bs'", "se "), (r"\bn'", "ne "), (r"\bj'", "je "),
    (r"\bc'", "ce "), (r"\bm'", "me "), (r"\bt'", "te "),
    (r"\blorsqu'", "cuando "),
]

NAME_CONNECTORS = {"de", "del", "la"}
NON_NAME_TOKENS = {
    "qui", "quel", "quelle", "quels", "quelles", "ou", "quand", "comment",
    "combien", "etaient", "etait", "sont", "est", "avec", "enfants", "freres",
    "surs", "soeurs", "parents", "pere", "mere", "grands", "grand", "cousins",
    "oncles", "tantes", "les", "des", "le", "la", "de", "en", "que", "y",
    "et", "ne", "nee", "grande", "grandes", "petits", "petites", "beaux", "belles",
    # participios que colisionan con nombres reales (p.ej. "marié"→"Marie"):
    # nunca deben protegerse como nombre.
    "marie", "mariee", "maries", "mariees", "decede", "decedee", "decedes",
    "documente", "documentee", "enregistre", "enregistree",
}
NAME_CONTINUATION_ONLY = set()
# Tokens que son a la vez nombre propio y keyword francés ("Marie"→marié,
# "Pere"→père): se protegen como nombre solo si el token siguiente es nombre.
NAME_AMBIGUOUS = {"marie", "mariee", "pere", "mere"}

# ── Reglas post-protección ───────────────────────────────────────────────────
PRE_RULES = [
    (r"\bde le\b", "del"),
]

# ── Reglas de frase (inversiones + reordenación), específicas → genéricas ────
# Nota: los patrones se compilan insensibles a acentos y a mayúsculas; "\(e\)",
# "\(a\)" y "il/elle" son los artefactos de doble género del banco.
# inversión sujeto: "-il", "-il/elle", "-t-il", "-t-il/elle" (el banco mezcla)
_INV = r"(?:-t)?-il(?:/elle)?"
_INVO = r"(?:(?:-t)?-il(?:/elle)?)?"   # inversión opcional (a veces el sujeto va antes)
_QUELLE = r"quel(?:le)?(?:/quelle)?"   # "quel", "quelle", "quel/quelle"
PHRASE_RULES = [
    # --- estructuras del banco GEDCOM: "recorded for", entierro, censo ---
    # "quels X sont indiqués pour Y" / "quelle X est indiqué(e) pour Y" → "que X consta para Y"
    (r"\bquel(?:le|s|les)? (.+?) (?:sont|est) indique(?:e)?s? pour (.+?)\s*\??$",
     r"que \1 consta para \2"),
    (r"\bou (.+?) a" + _INV + r" ete (?:inhume|enterre)\(e\)", r"donde fue enterrado \1"),
    (r"\ba quel age (.+?) est" + _INV + r" (?:mort|decede)\(e\)", r"a que edad murio \1"),
    (r"\bou (.+?) a" + _INV + r" etudie\b", r"donde estudio \1"),
    (r"\bquelle descendance directe (.+?) a" + _INV + r" eue?\b", r"que descendencia directa tuvo \1"),
    (r"\ba quelle date (.+?) a" + _INV + r" ete inhume\(e\)", r"en que fecha fue enterrado \1"),
    (r"\ba quelle date (.+?) a" + _INV + r" ete baptise\(e\)", r"en que fecha se bautizo \1"),
    (r"\bdans quel lieu (.+?) est" + _INV + r" ne\(e\)", r"en que lugar nacio \1"),
    (r"\bdans quel lieu (.+?) a" + _INV + r" ete baptise\(e\)", r"en que lugar se bautizo \1"),
    (r"\bdans quel lieu (.+?) est" + _INV + r" decede\(e\)", r"en que lugar murio \1"),
    (r"\bquand (.+?) se est" + _INV + r" marie\(e\)", r"cuando se caso \1"),
    (r"\bdans quel lieu (.+?) se est" + _INV + r" marie\(e\)", r"en que lugar se caso \1"),
    (r"\ba quelles adresses (.+?) a" + _INV + r" (?:reside|vecu|habite)", r"en que domicilios vivio \1"),
    (r"\bou (.+?) a" + _INV + r" (?:reside|vecu|habite)", r"donde vivio \1"),
    (r"\bou (.+?) apparait" + _INV + r" recense\(e\)", r"donde aparece censado \1"),
    (r"\bdans quel lieu (.+?) figure" + _INV + r" dans le recensement", r"en que lugar aparece censado \1"),
    (r"\bou (.+?) a" + _INV + r" emigre\b", r"a donde emigro \1"),
    (r"\bou (.+?) a" + _INV + r" demenage\b", r"a donde se mudo \1"),
    (r"\bou (.+?) est" + _INV + r" arrive\(e\)", r"donde llego \1"),
    (r"\bquand est" + _INV + r" indique que (.+?) est" + _INV + r" ne\(e\)", r"cuando nacio \1"),
    # "quels <REL> <nombre> avait-il/elle" (inversión) → "que <REL> tuvo <nombre>".
    # \2 anclado al centinela de nombre para no partir "frères et sœurs <nombre>".
    (r"\bquel(?:le|s|les)? (.+?) (qzx\d+xzq) avait" + _INV + r"\s*\??$", r"que \1 tuvo \2"),
    # --- compuestas (base + coletilla) primero ---
    (r"\bquel age avait (.+?) a la naissance de son premier enfant, (.+?), et est-ce au-dessus ou en dessous de la moyenne\b",
     r"cuantos anos tenia \1 cuando nacio su primer hijo, \2, y esta por encima o por debajo de la media"),
    (r"\bquel age avait (.+?) a la naissance de son premier enfant, et est-ce au-dessus ou en dessous de la moyenne\b",
     r"que edad tenia \1 cuando nacio su primer hijo y esta por encima o por debajo de la media"),
    (r"\bquel age avait (.+?) a la naissance de son premier enfant, (.+)$",
     r"cuantos anos tenia \1 cuando nacio su primer hijo, \2"),
    (r"\ba quel age (.+?) a" + _INV + r" eu son premier enfant\b",
     r"a que edad tuvo su primer hijo \1"),
    (r"\bcombien de freres et s(?:oe|œ|)urs (.+?) avait" + _INV + r", et comment cela se compare" + _INV + r" au reste de sa generation\b",
     r"cuantos hermanos tenia \1 y como se compara con el resto de su generacion"),
    (r"\bcombien de enfants (.+?) a" + _INV + r" eus par rapport a la moyenne del arbre\b",
     r"cuantos hijos tuvo \1 en comparacion con la media del arbol"),
    (r"\bquel lien de parente (.+?) avait" + _INV + r" avec (.+?), et lequel des deux etait le plus age\b",
     r"que parentesco tenia \1 con \2 y cual de los dos era mayor"),
    (r"\bcombien de naissances sont enregistrees dans les annees (\d{3})0\b",
     r"cuantos nacimientos hay en la decada de \g<1>0"),
    (r"\bcombien de deces sont enregistres dans les annees (\d{3})0\b",
     r"cuantos fallecimientos hay en la decada de \g<1>0"),
    (r"\bquelles personnes ont (.+?) comme premier nom de famille\b",
     r"que personas tienen \1 como primer apellido"),
    (r"\bquel pourcentage approximatif del arbre correspond aux personnes ayant (.+?) comme premier nom de famille\b",
     r"que porcentaje aproximado del arbol corresponde a personas con primer apellido \1"),
    (r"\ba quel rang du classement de descendance se situe (.+)$",
     r"en que puesto del ranking de descendencia se situa \1"),
    (r"\ba quelle position de naissance parmi ses freres et s(?:oe|œ|)urs se trouvait (.+)$",
     r"en que posicion entre sus hermanos nacio \1"),
    (r"\bquelle branche a eu le plus de enfants ?: celle formee par (.+?) et (.+?),? ou le couple suivant du classement\b",
     r"que rama tuvo mas hijos: la formada por \1 y \2 o la siguiente pareja en el ranking"),
    (r"\bquel lieu de naissance a le plus de variantes de ecriture ?: (.+?),? ou un autre toponyme del arbre\b",
     r"que lugar de nacimiento tiene mas variantes de escritura: \1 u otro toponimo del arbol"),
    # --- eventos con inversión ---
    (r"\bavec qui (.+?) se est" + _INV + r" marie\(e\), et a quelle date a eu lieu le mariage\b",
     r"con quien se caso \1 y en que fecha fue la boda"),
    (r"\bavec qui (.+?) se est" + _INV + r" marie\(e\)", r"con quien se caso \1"),
    (r"\bavec qui (.+?) se sont-ils maries\b", r"con quien se caso \1"),
    # "de quel mariage ou couple X est né(e)" ANTES que "où X est né(e)" (si no,
    # el "ou couple X est né(e)" cae en la regla genérica de nacimiento).
    (r"\bde quel mariage ou couple (.+?) est" + _INV + r" ne\(e\)", r"de que matrimonio o pareja nacio \1"),
    # Marcos mixtos del banco (contenido en español: fecha/sitio/momento) + verbo fr.
    (r"\bou et en " + _QUELLE + r" fecha est" + _INVO + r" decede\(e\) (.+)$", r"donde y en que fecha fallecio \1"),
    (r"\bou se est marie\(e\) (.+)$", r"donde se caso \1"),
    (r"\ben " + _QUELLE + r" momento est" + _INVO + r" ne\(e\) (.+)$", r"en que momento nacio \1"),
    (r"\ben " + _QUELLE + r" sitio est" + _INVO + r" decede\(e\) (.+)$", r"en que sitio fallecio \1"),
    (r"\bou (.+?) est" + _INV + r" ne\(e\)", r"donde nacio \1"),
    (r"\bou (.+?) est" + _INV + r" decede\(e\)", r"donde murio \1"),
    (r"\bqui est ne\(e\)", "quien nacio"),
    (r"\bcombien de personnes sont nees (?:a|en|dans) (.+?),? et quelle importance ce lieu a" + _INV + r" parmi les naissances enregistrees\b",
     r"cuantas personas nacieron en \1 y que relevancia tiene ese lugar en los nacimientos registrados"),
    (r"\bcombien de personnes sont decedees (?:a|en|dans) (.+?),? et quelle importance ce lieu a" + _INV + r" parmi les deces enregistres\b",
     r"cuantas personas murieron en \1 y que relevancia tiene ese lugar en las defunciones registradas"),
    (r"\bquelles personnes sont nees (?:a|en|dans) (.+)$", r"que personas nacieron en \1"),
    (r"\bquelles personnes sont decedees (?:a|en|dans) (.+)$", r"que personas murieron en \1"),
    (r"\bcombien de personnes sont nees (?:a|en|dans) (.+)$", r"cuantas personas nacieron en \1"),
    (r"\bcombien de personnes sont decedees (?:a|en|dans) (.+)$", r"cuantas personas murieron en \1"),
    (r"\bquels couples se sont maries (?:a|en|dans) (.+)$", r"que parejas se casaron en \1"),
    (r"\b(.+?) avait" + _INV + r" une descendance\b", r"tenia descendencia \1"),
    (r"\ben " + _QUELLE + r" annee est" + _INVO + r" ne\(e\) (.+)$", r"en que ano nacio \1"),
    (r"\ben " + _QUELLE + r" annee est" + _INVO + r" decede\(e\) (.+)$", r"en que ano murio \1"),
    (_QUELLE + r" es la media de enfants\b", "cual es la media de hijos"),
    # Marcos mixtos "combien de frères et sœurs" + cola española con dativo "le"
    # (que el token map convertiría en "el"): se resuelven antes.
    (r"\bcombien de freres et s(?:oe|œ|)urs (?:le salieron|se le conocen) a (.+)$", r"cuantos hermanos tuvo \1"),
    (r"\bqui est le/la plus age\(e\), (.+?) ou (.+)$", r"quien es mayor, \1 o \2"),
    (r"\bqui a vecu le plus longtemps\b", "quien vivio mas anos"),
    (r"\bcombien de temps (.+?) a" + _INV + r" vecu au total\b", r"cuanto tiempo vivio \1 en total"),
    (r"\ba quel metier (.+?) se est" + _INV + r" consacre\(e\)", r"a que oficio se dedico \1"),
    (r"\ba " + _QUELLE + r" edad se est marie\(e\) (.+)$", r"a que edad se caso \1"),
    (r"\bquien est" + _INVO + r" decede\(e\) (el .+)$", r"quien murio \1"),
    (r"\best" + _INVO + r" ne\(e\) antes\b", "nacio antes"),
    (r"\bqui est decede\(e\) en (\d{4})\b", r"quien murio en \1"),
    (r"\bqui est decede\(e\) le (.+)$", r"quien murio el \1"),
    (r"\bquelles personnes del arbre ont un prenom qui commence par (.+)$",
     r"que personas del arbol tienen un nombre de pila que empieza por \1"),
    (r"\bquelles personnes ont un (?:nom|prenom) compose comme (.+)$",
     r"que personas tienen un nombre compuesto como \1"),
    (r"\bquelles personnes sont nees et decedees (?:a|en|dans) (.+)$",
     r"que personas nacieron y murieron en \1"),
    (r"\bquels enfants le couple forme par (.+?) et (.+?), marie (?:a|en) (.+?), a" + _INV + r" eus\b",
     r"que hijos tuvo la pareja que se caso en \3 formada por \1 y \2"),
    (r"\bquels enfants (.+?) a" + _INV + r" eus\b", r"que hijos tuvo \1"),
    (r"\bcombien de enfants le mariage de (.+?) et (.+?) a" + _INV + r" eus\b",
     r"cuantos hijos tuvo el matrimonio de \1 y \2"),
    (r"\bcombien de enfants (.+?) a" + _INV + r" eus\b", r"cuantos hijos tuvo \1"),
    (r"\bcombien de enfants ont survecu a (.+)$", r"cuantos hijos sobrevivieron a \1"),
    (r"\bqui est decede\(e\) (?:a|en|dans) (.+)$", r"quien murio en \1"),
    (r"\bdans quelle residence ou a quelle adresse (.+?) est" + _INV + r" documente\(e\)",
     r"en que residencia o direccion aparece documentado \1"),
    (r"\bquelle profession ou activite est enregistree pour (.+)$",
     r"que ocupacion o actividad figura registrada para \1"),
    (r"\bquelles notes biographiques sont associees a (.+)$",
     r"que notas biograficas hay asociadas a \1"),
    (r"\bquel age avait (.+?) (?:lorsque|cuando)(?: il/elle)? se est marie\(e\)", r"que edad tenia \1 cuando se caso"),
    (r"\bquel age avait (.+?) lorsque se est" + _INV + r" marie\(e\)", r"a que edad se caso \1"),
    (r"\ble mariage ou couple duquel est ne\(e\) (.+)$", r"de que matrimonio o pareja nacio \1"),
    (r"\bde quel mariage ou couple est ne\(e\) (.+)$", r"de que matrimonio o pareja nacio \1"),
    (r"\bquel couple a eu exactement (\d+) enfants,? et a quel rang se situe" + _INV + r" par taille (?:de famille|familiale)\b",
     r"que pareja tuvo exactamente \1 hijos y en que posicion queda por tamano familiar"),
    (r"\bqui a eu exactement (\d+) enfants,? et a quelle position se classe" + _INV + r" par taille de famille\b",
     r"que pareja tuvo exactamente \1 hijos y en que posicion queda por tamano familiar"),
    (r"\bcombien de personnes ont une date de naissance connue par rapport a celles qui ne en ont pas\b",
     "cuantas personas tienen fecha de nacimiento conocida frente a las que no la tienen"),
    (r"\bquelle est la personne ayant le plus de enfants enregistres dans tout le arbre\b",
     "cual es la persona con mas hijos registrados en todo el arbol"),
    (r"\bquelle est la personne ayant le moins de enfants enregistres dans tout le arbre\b",
     "cual es la persona con menos hijos registrados en todo el arbol"),
    (r"\bquel mariage a eu la descendance documentee la plus nombreuse\b",
     "que matrimonio tuvo mas descendencia documentada"),
    (r"\blequel est anterieur ?: la naissance de (.+?) ou celle de (.+)$",
     r"cual fue antes: el nacimiento de \1 o el de \2"),
    (r"\bqui etait le plus age (?:lorsqu.ils|cuando ils) se sont maries ?: (.+?) ou (.+)$",
     r"quien era mayor cuando se casaron: \1 o \2"),
    (r"\bera (.+?) etait" + _INV + r" grand-pere ou grand-mere de (.+)$",
     r"era \1 abuelo o abuela de \2"),
    (r"\b(.+?) et (.+?) etaient(?:-t)?-ils?(?:/elles?)? cousins germains\b", r"eran primos \1 y \2"),
    # --- relaciones "qui étai(en)t/sont le/la/les REL de X" (genéricas) ---
    (r"\bqui etaient les (.+?) et les (.+?) de (.+)$", r"quienes fueron los \1 y los \2 de \3"),
    (r"\bqui etaient les (.+?) de (.+)$", r"quienes eran los \1 de \2"),
    (r"\bqui sont les (.+?) de (.+)$", r"quienes son los \1 de \2"),
    (r"\bqui etait le (.+?) de (.+)$", r"quien era el \1 de \2"),
    (r"\bqui etait la (.+?) de (.+)$", r"quien era la \1 de \2"),
    (r"\bquel etait le lien de parente entre (.+?) et (.+)$", r"que parentesco hay entre \1 y \2"),
    (r"\bquel lien de parente (.+?) avait" + _INV + r" avec (.+)$", r"que relacion tenia \1 con \2"),
    (r"\bquel lien (.+?) avait" + _INV + r" avec (.+)$", r"que relacion tenia \1 con \2"),
]

PERIPHRASIS = {}

# ── N-gramas ─────────────────────────────────────────────────────────────────
MULTIWORD_MAP = [
    (r"\bcombien de\b", "cuantos"),  # tras las reglas de frase de "combien de enfants…"
    (r"\bquel/quelle\b", "que"), (r"\bquels/quelles\b", "que"),
    (r"\bgrand-pere maternel\b", "abuelo materno"),
    (r"\bgrand-pere paternel\b", "abuelo paterno"),
    (r"\bgrand-mere maternelle\b", "abuela materna"),
    (r"\bgrand-mere paternelle\b", "abuela paterna"),
    (r"\barriere-grand-mere maternelle\b", "bisabuela materna"),
    (r"\barriere-grand-pere paternel\b", "bisabuelo paterno"),
    (r"\barriere-arriere-grand-mere maternelle\b", "tatarabuela materna"),
    (r"\barriere-arriere-grands-parents\b", "tatarabuelos"),
    (r"\barriere-grands-parents\b", "bisabuelos"),
    (r"\barriere-grand-mere\b", "bisabuela"),
    (r"\barriere-grand-pere\b", "bisabuelo"),
    (r"\bgrands-parents\b", "abuelos"),
    # nietos por generación y género
    (r"\barriere-arriere-petits-enfants\b", "tataranietos"),
    (r"\barriere-petits-enfants\b", "bisnietos"),
    (r"\bpetits-neveux et petites-ni[eè]ces\b", "sobrinos nietos"),
    (r"\bpetits-fils\b", "nietos varones"), (r"\bpetites-filles\b", "nietas"),
    (r"\bpetits-enfants\b", "nietos"),
    (r"\bgrands-m[eè]res\b", "abuelas"), (r"\bgrands-p[eè]res\b", "abuelos varones"),
    # in-laws: consuegros (beaux-parents des enfants) antes de beaux-parents
    (r"\bbeaux-parents des enfants\b", "consuegros"),
    (r"\bbeaux-parents\b", "suegros"),
    (r"\bbeaux-freres et belles-s(?:oe|œ|)urs\b", "cunados"),
    # medios hermanos, primos varones, tíos abuelos, yernos y nueras
    (r"\bdemi-freres et demi-s(?:oe|œ|)urs\b", "medios hermanos"),
    (r"\bdemi-freres\b", "medios hermanos"), (r"\bdemi-s(?:oe|œ)urs\b", "medias hermanas"),
    (r"\bcousins masculins\b", "primos varones"),
    (r"\bgrands-oncles et grandes-tantes\b", "tios abuelos"),
    (r"\bgendres et brus\b", "hijos politicos"),
    # compuestos "... et ..." (ambos géneros) ANTES de las formas simples
    (r"\bfreres et s(?:oe|œ|)urs\b", "hermanos"),
    (r"\boncles et tantes\b", "tios"),
    (r"\bneveux et nieces\b", "sobrinos"),
    # gendered simples (para el filtro de sexo)
    (r"\bfreres\b", "hermanos varones"), (r"\bs(?:oe|œ)urs\b", "hermanas"),
    (r"\bfils\b", "hijos varones"), (r"\bneveux\b", "sobrinos varones"),
    (r"\boncles\b", "tios varones"),
    (r"\bancetres connus\b", "antepasados conocidos"),
    (r"\bdescendants connus\b", "descendientes conocidos"),
    (r"\bcause de deces\b", "causa de muerte"),
    (r"\bdate de deces\b", "fecha de defuncion"),
    (r"\bdate de naissance\b", "fecha de nacimiento"),
    (r"\bcousins issus de germains\b", "primos segundos"),
    (r"\bcousins germains\b", "primos hermanos"),
    (r"\bcousins/cousines\b", "primos"),
    (r"\bbelle-mere ou le beau-pere\b", "suegra o el suegro"),
    (r"\bbelle-mere\b", "suegra"), (r"\bbeau-pere\b", "suegro"),
    (r"\bbelle-s(?:oe|œ|)ur\b", "cunada"), (r"\bbeau-frere\b", "cunado"),
    (r"\bpremier nom de famille\b", "primer apellido"),
    (r"\bnom de famille\b", "apellido"),
    (r"\ba eu lieu\b", "tuvo lugar"),
    # "qui est né(e) à X" → "quien nacio" + "à X"→"a x"; el lugar quiere "en".
    (r"\bnacio a\b", "nacio en"), (r"\bnacieron a\b", "nacieron en"),
    (r"\bmurio a\b", "murio en"), (r"\bmurieron a\b", "murieron en"),
]

# ── Barrido palabra a palabra ────────────────────────────────────────────────
TOKEN_MAP = {
    "qui": "quien", "quel": "que", "quelle": "que", "quels": "que",
    "quelles": "que", "quand": "cuando", "comment": "como",
    "combien": "cuantos", "lequel": "cual", "laquelle": "cual",
    "etaient": "eran", "etait": "era", "sont": "son", "est": "es",
    "avec": "con", "les": "los", "des": "de", "le": "el", "leur": "su",
    "leurs": "sus", "et": "y",
    # "où" (dónde) se resuelve en las reglas de frase; el "ou" suelto es "o":
    "ou": "o",
    # parentescos
    "parents": "padres", "pere": "padre", "mere": "madre", "enfants": "hijos",
    "enfant": "hijo", "freres": "hermanos", "frere": "hermano",
    "cousins": "primos", "cousines": "primas", "oncles": "tios",
    "tantes": "tias", "neveux": "sobrinos", "nieces": "sobrinas",
    "conjoint": "conyuge", "epoux": "marido", "epouse": "esposa",
    "belle": "suegra", "grands": "abuelos",
    # sustantivos/función
    "personnes": "personas", "personne": "persona", "arbre": "arbol",
    "famille": "familia", "nom": "nombre", "naissance": "nacimiento",
    "mariage": "matrimonio", "profession": "profesion", "adresse": "direccion",
    "residence": "residencia", "moyenne": "media", "generation": "generacion",
    "descendance": "descendencia", "parente": "parentesco", "annee": "ano",
    "annees": "anos", "age": "edad", "date": "fecha", "lieu": "lugar",
    "rang": "puesto", "classement": "ranking", "couple": "pareja",
    "branche": "rama", "posterieur": "posterior", "anterieur": "anterior",
    # verbos/participios
    "ne": "nacido", "nee": "nacida", "decede": "murio", "decedee": "murio",
    "marie": "casado", "mariee": "casada", "survecu": "sobrevivieron",
    "enregistree": "registrada", "enregistrees": "registrados",
    "associees": "asociadas", "documente": "documentado", "avait": "tenia",
    "eus": "tuvo", "connue": "conocida",
    # otros
    "premier": "primer", "approximatif": "aproximado", "plus": "mas",
    "moins": "menos", "comme": "como", "ans": "anos", "prenom": "nombre de pila",
    # ── vocabulario ampliado (capacidades nuevas) ────────────────────────────
    "filles": "hijas", "fille": "hija", "conjoints": "conyuges",
    "epoux": "marido", "epouse": "esposa", "travail": "trabajo",
    "ancetres": "antepasados", "ancetre": "antepasado",
    "connus": "conocidos", "connu": "conocido", "connues": "conocidas",
    "descendants": "descendientes", "descendant": "descendiente",
    "cause": "causa", "deces": "muerte", "inhume": "enterrado",
    "inhumee": "enterrada", "recense": "censado", "recensee": "censada",
    "apparait": "aparece", "recensement": "censo",
    "immigration": "inmigracion", "emigration": "emigracion",
    "religion": "religion", "nationalite": "nacionalidad",
    "education": "educacion", "confirmation": "confirmacion",
    "sepulture": "sepultura", "domicile": "domicilio", "domiciles": "domicilios",
    "evenement": "evento", "fait": "hecho",
    "maternels": "maternos", "paternels": "paternos", "maternelles": "maternas",
    "paternelles": "paternas", "ascendants": "ascendientes",
    "ascendant": "ascendiente", "metier": "oficio", "figure": "figura",
    "formation": "formacion", "partenaires": "conyuges", "partenaire": "conyuge",
    "adresses": "domicilios", "paternelle": "paterna", "maternelle": "materna",
    "baptise": "bautizado", "baptisee": "bautizada",
}
