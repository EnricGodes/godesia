"""Localización de fechas por idioma.

La BD almacena las fechas ya formateadas en español (migrate_json_to_sqlite
convierte el GEDCOM al importar: "19 ago. 1917", "Aprox. 1900", "De X a Y").
Para servir en otro idioma este módulo traduce esas cadenas por tokens
(meses abreviados + palabras de calificador), y también puede formatear
fechas GEDCOM crudas directamente en el idioma pedido.

localize_dates_deep() recorre una respuesta de la API y localiza in situ los
valores de las claves de fecha conocidas — así los endpoints solo necesitan
una llamada cuando lang != "es".
"""

import re

DEFAULT_LANG = "es"

# Meses abreviados por idioma, indexados 1-12 (mismo criterio que
# MONTHS_SPANISH en database.py, que es la forma almacenada en la BD)
MONTHS_ABBR = {
    "es": ["", "ene.", "feb.", "mar.", "abr.", "may.", "jun.",
            "jul.", "ago.", "sept.", "oct.", "nov.", "dic."],
    "ca": ["", "gen.", "febr.", "març", "abr.", "maig", "juny",
            "jul.", "ag.", "set.", "oct.", "nov.", "des."],
    "en": ["", "Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.",
            "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."],
}

# Palabras de calificador tal y como las escribe convert_date_to_spanish
QUALIFIERS = {
    "es": {"approx": "Aprox.", "estimated": "Estimado", "calculated": "Calculado",
            "before": "Antes de", "after": "Después de", "interpreted": "Interpretado",
            "from": "Desde", "to": "Hasta",
            "range_from": "De", "range_to": "a", "between": "Entre", "and": "y"},
    "ca": {"approx": "Aprox.", "estimated": "Estimat", "calculated": "Calculat",
            "before": "Abans de", "after": "Després de", "interpreted": "Interpretat",
            "from": "Des de", "to": "Fins a",
            "range_from": "De", "range_to": "a", "between": "Entre", "and": "i"},
    "en": {"approx": "Approx.", "estimated": "Estimated", "calculated": "Calculated",
            "before": "Before", "after": "After", "interpreted": "Interpreted",
            "from": "From", "to": "Until",
            "range_from": "From", "range_to": "to", "between": "Between", "and": "and"},
}

GEDCOM_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Claves de la API cuyos valores son fechas formateadas en español
DATE_KEY_RE = re.compile(r"(^|_)date$|^gedcom_date$|^updated_at_display$|^date_label$")


def _tables(lang):
    months = MONTHS_ABBR.get(lang, MONTHS_ABBR[DEFAULT_LANG])
    quals = QUALIFIERS.get(lang, QUALIFIERS[DEFAULT_LANG])
    return months, quals


def format_gedcom_date(date_str, lang=DEFAULT_LANG):
    """Fecha GEDCOM cruda ('5 APR 1824', 'ABT 1900', 'BET X AND Y') → idioma."""
    if not date_str:
        return ""
    months, q = _tables(lang)
    s = str(date_str).strip()

    if "FROM" in s and "TO" in s:
        start = s.split("FROM")[1].split("TO")[0].strip()
        end = s.split("TO")[1].strip()
        return f"{q['range_from']} {format_gedcom_date(start, lang)} {q['range_to']} {format_gedcom_date(end, lang)}"
    if "BET" in s and "AND" in s:
        start = s.split("BET")[1].split("AND")[0].strip()
        end = s.split("AND")[1].strip()
        return f"{q['between']} {format_gedcom_date(start, lang)} {q['and']} {format_gedcom_date(end, lang)}"

    prefix_map = {
        "FROM": q["from"], "TO": q["to"], "ABT": q["approx"], "EST": q["estimated"],
        "CAL": q["calculated"], "BEF": q["before"], "AFT": q["after"],
        "INT": q["interpreted"],
    }
    for prefix, translation in prefix_map.items():
        if s.startswith(prefix + " "):
            rest = s[len(prefix):].strip()
            return f"{translation} {format_gedcom_date(rest, lang)}"

    parts = s.split()
    if len(parts) == 3:
        try:
            day = int(parts[0])
            month = GEDCOM_MONTHS.get(parts[1].upper())
            year = int(parts[2])
            if month:
                return f"{day} {months[month]} {year}"
        except (ValueError, KeyError):
            pass
    elif len(parts) == 2:
        if parts[0].isdigit():
            return parts[0]
        month = GEDCOM_MONTHS.get(parts[0].upper())
        try:
            year = int(parts[1])
            if month:
                return f"{months[month]} {year}"
        except ValueError:
            pass
    elif len(parts) == 1 and parts[0].isdigit():
        return parts[0]
    return date_str


def _build_token_map(lang):
    """Tokens españoles (como en la BD) → idioma destino."""
    es_months, es_q = _tables("es")
    months, q = _tables(lang)
    mapping = {}
    for i in range(1, 13):
        mapping[es_months[i]] = months[i]
        # variante sin punto ("ago" además de "ago.")
        mapping[es_months[i].rstrip(".")] = months[i]
    # Multipalabra primero (se aplican por orden de longitud)
    for key in ("before", "after", "from", "to", "approx", "estimated",
                "calculated", "interpreted", "between", "and",
                "range_from", "range_to"):
        mapping[es_q[key]] = q[key]
    return mapping


_token_maps = {}


def localize_spanish_date(date_es, lang=DEFAULT_LANG):
    """Fecha ya formateada en español (formato BD) → idioma destino."""
    if not date_es or lang == DEFAULT_LANG:
        return date_es
    if lang not in _token_maps:
        _token_maps[lang] = _build_token_map(lang)
    mapping = _token_maps[lang]
    result = str(date_es)
    # Sustituir tokens más largos primero para no partir "Antes de" en "de"
    for token in sorted(mapping, key=len, reverse=True):
        target = mapping[token]
        if token == target:
            continue
        # Límite de palabra a ambos lados. Si el token no acaba en punto,
        # excluir también el punto en el lookahead para que la variante sin
        # punto ("abr") no re-empareje dentro de la forma con punto ("abr.").
        tail = r"(?![\wÀ-ÿ])" if token.endswith(".") else r"(?![\wÀ-ÿ.])"
        result = re.sub(rf"(?<![\wÀ-ÿ]){re.escape(token)}{tail}", target, result)
    return result


def localize_dates_deep(obj, lang):
    """Localiza in situ los valores de claves de fecha en una respuesta API."""
    if lang == DEFAULT_LANG:
        return obj
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and value and DATE_KEY_RE.search(key):
                obj[key] = localize_spanish_date(value, lang)
            elif isinstance(value, (dict, list)):
                localize_dates_deep(value, lang)
    elif isinstance(obj, list):
        for item in obj:
            localize_dates_deep(item, lang)
    return obj


def validate_lang(lang, active_codes=None):
    """Normaliza el parámetro lang de la API (fallback es)."""
    if not lang or not re.fullmatch(r"[a-z]{2,3}", lang):
        return DEFAULT_LANG
    if active_codes is not None and lang not in active_codes:
        return DEFAULT_LANG
    return lang
