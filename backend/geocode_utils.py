"""Shared geocoding utilities: normalize, geocache, Nominatim."""

import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "Godesia Genealogy App (genealogia familiar, uso privado)"}

GEOCODEABLE_TAGS = frozenset(["RESI", "EMIG", "CENS"])
GEOCODEABLE_TYPES = frozenset(["Mudanza", "Emigración", "Residencia", "Padrón", "Censo"])

# Part is purely floor/apt/door info → discard
_FLOOR_ONLY = re.compile(
    r'^(?:'
    r'\d{1,2}\s*[oaºª°][\doaºª°\s]*(?:izda?|dcha?|esc\s*\w*)?'  # "4o 1a", "6o 2a" (≤2 digits = floor num)
    r'|esc\s+\w*\s*\d*[oaºª°]?\s*\d*[oaºª°]?'                    # "esc izq 6o1a"
    r'|(?:izda?|dcha?|pral|ent|bajo|bajos|bis)'                    # standalone door label
    r')$',
    re.IGNORECASE,
)

# Strip floor/apt/door info from address parts.
# Does NOT consume trailing space ([\doaºª°]* no spaces) so "30 4º Barcelona"
# becomes "30 Barcelona" not "30Barcelona".
_FLOOR_SUFFIX = re.compile(
    r'\s+\d{1,2}[oaºª°][\doaºª°]*(?:\s+\d{1,2}[oaºª°][\doaºª°]*)?(?:\s+(?:izda?|dcha?|esc\s*\w*))?'
    r'|\s+(?:izda?|dcha?|pral|ent|bajo|bajos|bis|planta\s*\w+)$'
    r'|\s+p\b$',
    re.IGNORECASE,
)

COUNTRY_ES = {
    "spain": "España",
    "france": "Francia",
    "usa": "Estados Unidos",
    "united states": "Estados Unidos",
    "u.s.a.": "Estados Unidos",
    "england": "Inglaterra",
    "uk": "Reino Unido",
    "united kingdom": "Reino Unido",
    "germany": "Alemania",
    "italy": "Italia",
    "portugal": "Portugal",
    "cuba": "Cuba",
    "argentina": "Argentina",
    "mexico": "México",
    "méxico": "México",
}

_CITY_HINT = re.compile(
    r'\b(barcelona|madrid|pamplona|burgos|logro[ñn]o|palencia|c[oó]rdoba|sevilla|'
    r'valencia|zaragoza|paris|london|habana|cuba|puentes\s+grandes|parets|georgia)\b',
    re.IGNORECASE,
)
_COUNTRY_HINT = re.compile(
    r'\b(espa[ñn]a|france|francia|estados\s+unidos|usa|england|inglaterra|'
    r'alemania|germany|argentina|m[eé]xico|m[eé]xico|italia|italy|portugal|cuba|'
    r'ireland|irlanda|colombia|venezuela|chile|per[uú]|ecuador|bolivia|uruguay|'
    r'suiza|switzerland|belgique|b[eé]lgica|netherlands|holanda|'
    r'ee\.?\s*uu\.?|u\.?s\.?a\.?)\b',
    re.IGNORECASE,
)


def normalize_place(raw: str) -> str:
    """Canonicalize a place string for use as a geocache key.

    - Strips floor/apt notation ("4o 1a", "esc izq", "izda"…)
    - Removes duplicate city/province parts ("Córdoba, Córdoba" → "Córdoba")
    - Translates country names to Spanish ("Spain" → "España")
    """
    if not raw or not raw.strip():
        return ""

    clean_parts = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        if _FLOOR_ONLY.match(p):
            continue
        p = _FLOOR_SUFFIX.sub("", p).strip().rstrip(",").strip()
        if not p:
            continue
        # If a city name is embedded mid-part (e.g. "15 Barcelona"), split it out
        # so "Banys Vells, 15 Barcelona" and "Banys Vells, 15, Barcelona, España"
        # both produce the same canonical key.
        m = _CITY_HINT.search(p)
        if m and m.start() > 0:
            before = p[:m.start()].strip().rstrip(",").strip()
            city   = p[m.start():].strip()
            if before:
                clean_parts.append(before)
            clean_parts.append(city)
        else:
            clean_parts.append(p)

    # Deduplicate case-insensitive, translate countries
    seen: set = set()
    result = []
    for p in clean_parts:
        key = p.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        result.append(COUNTRY_ES.get(key, p))

    return ", ".join(result)


def build_queries(normalized: str) -> list:
    """Return Nominatim query attempts ordered by specificity."""
    if not normalized:
        return []
    has_city    = bool(_CITY_HINT.search(normalized))
    has_country = bool(_COUNTRY_HINT.search(normalized))
    if has_city and not has_country:
        return [f"{normalized}, España", normalized]
    if has_city or has_country:
        return [normalized]
    # No explicit location hint: distinguish street addresses (have digits) from
    # place names (no digits). Streets default to Barcelona; place names try
    # as-is first so Nominatim can resolve foreign cities/countries correctly.
    has_number = bool(re.search(r'\d', normalized))
    if has_number:
        return [f"{normalized}, Barcelona, España", f"{normalized}, España", normalized]
    else:
        return [normalized, f"{normalized}, España", f"{normalized}, Barcelona, España"]


def build_residence_raw(address: str, city: str, country: str) -> str:
    """Combine residence fields into a single raw place string."""
    parts = [p for p in [address, city, country] if p and p.strip()]
    return ", ".join(parts)


_PLACE_COUNTRIES = frozenset({
    # Countries
    "españa", "espanya", "spain",
    "france", "francia",
    "italia", "italy",
    "estados unidos", "usa", "eeuu", "u.s.a.", "united states",
    "reino unido", "uk", "united kingdom", "england", "inglaterra",
    "alemania", "germany", "portugal", "cuba", "argentina",
    "mexico", "méxico",
    # Autonomous communities / regions (not cities)
    "catalunya", "cataluña", "catalonia",
    "euskadi", "país vasco", "basque country",
    "andalucía", "andalucia",
    "comunidad de madrid",
    "galicia",
})


def extract_city_from_place(raw: str) -> str:
    """Extract just the city/town name from a freeform GEDCOM PLAC string.

    Uses normalize_place() to strip floor/apt notations and split embedded
    city names (e.g. "30 4º Barcelona" → "30, Barcelona"). Then returns the
    last non-country, non-numeric segment.

    No external API calls — purely local, ~0 ms per call.

    Examples:
      "Fonollar, 30 4º Barcelona"     → "Barcelona"
      "Jaume Giralt, 3 1º, Barcelona" → "Barcelona"
      "Castellón de la Plana"         → "Castellón de la Plana"
      "Barcelona"                     → "Barcelona"
      "Bertran, 67 Barcelona"         → "Barcelona"
    """
    if not raw or not raw.strip():
        return ""
    normalized = normalize_place(raw)
    if not normalized:
        return raw.strip()

    parts = [p.strip() for p in normalized.split(",") if p.strip()]
    if not parts:
        return ""

    city_parts = [
        p for p in parts
        if p.lower() not in _PLACE_COUNTRIES and not re.match(r"^\d+$", p)
    ]
    if not city_parts:
        return parts[-1] if parts else raw.strip()

    # If the original has digits it's a street address → prefer a known city name
    if any(c.isdigit() for c in normalized):
        # Prefer the last part that is an exact _CITY_HINT match (most reliable)
        hint_parts = [p for p in city_parts if _CITY_HINT.fullmatch(p)]
        if hint_parts:
            return hint_parts[-1]
        # Fallback: last non-country, non-numeric part
        return city_parts[-1]

    # No digits → already a plain place name, return as-is
    return normalized


# ---------------------------------------------------------------------------
# Nominatim
# ---------------------------------------------------------------------------

def nominatim_geocode(query: str):
    """Single geocode query → (lat, lng) or None."""
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    req = urllib.request.Request(f"{NOMINATIM_URL}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"  Nominatim ERROR: {e}")
    return None


def nominatim_search(query: str) -> list:
    """Search Nominatim and return up to 5 candidates (for the CMS)."""
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 5, "addressdetails": 1}
    )
    req = urllib.request.Request(f"{NOMINATIM_URL}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Cache-aware geocoding
# ---------------------------------------------------------------------------

def geocode_with_cache(conn: sqlite3.Connection, raw_place: str, cache_only: bool = False):
    """Geocode raw_place using geocache-first strategy.

    Returns (lat, lng) or (None, None).
    cache_only=True → never calls Nominatim (safe during DB import).
    On full failure → registers as pending in geocache (lat=NULL).
    """
    if not raw_place or not raw_place.strip():
        return None, None

    normalized = normalize_place(raw_place)
    queries = build_queries(normalized)
    if not queries:
        return None, None

    # 1. Check cache (resolved entries only)
    for q in queries:
        row = conn.execute(
            "SELECT lat, lng FROM geocache WHERE query=? AND lat IS NOT NULL", (q,)
        ).fetchone()
        if row:
            return row[0], row[1]

    if cache_only:
        return None, None

    # 2. Try Nominatim
    for q in queries:
        result = nominatim_geocode(q)
        time.sleep(1.1)
        if result:
            lat, lng = result
            conn.execute(
                "INSERT OR REPLACE INTO geocache (query, lat, lng, raw_place) VALUES (?,?,?,?)",
                (q, lat, lng, raw_place),
            )
            conn.commit()
            return lat, lng

    # 3. Fallback: search by raw_place (key may have changed after normalization update)
    row = conn.execute(
        "SELECT lat, lng FROM geocache WHERE raw_place = ? AND lat IS NOT NULL LIMIT 1",
        (raw_place,)
    ).fetchone()
    if row:
        conn.execute(
            "INSERT OR IGNORE INTO geocache (query, lat, lng, raw_place) VALUES (?,?,?,?)",
            (queries[0], row[0], row[1], raw_place),
        )
        conn.commit()
        return row[0], row[1]

    # 4. Register as pending so CMS can pick it up
    conn.execute(
        "INSERT OR IGNORE INTO geocache (query, lat, lng, raw_place) VALUES (?,NULL,NULL,?)",
        (queries[0], raw_place),
    )
    conn.commit()
    return None, None


def normalize_geocache_keys(conn: sqlite3.Connection) -> int:
    """Re-normalize all geocache query keys to current canonical form.

    Safe to run on every startup — idempotent, fast for ~300 entries.
    Ensures that changes to normalize_place() don't leave stale keys.
    Returns number of entries renamed or merged.
    """
    rows = conn.execute(
        "SELECT query, raw_place, lat, lng, validated FROM geocache"
    ).fetchall()
    updated = 0
    for row in rows:
        source = row["raw_place"] or row["query"]
        canonical = build_queries(normalize_place(source))
        if not canonical:
            continue
        new_key = canonical[0]
        if new_key == row["query"]:
            continue
        existing = conn.execute(
            "SELECT lat, lng, validated FROM geocache WHERE query=?", (new_key,)
        ).fetchone()
        if existing:
            if row["lat"] is not None and existing[0] is None:
                conn.execute(
                    "UPDATE geocache SET lat=?,lng=?,validated=? WHERE query=?",
                    (row["lat"], row["lng"], row["validated"], new_key),
                )
            conn.execute("DELETE FROM geocache WHERE query=?", (row["query"],))
        else:
            conn.execute(
                "UPDATE geocache SET query=? WHERE query=?", (new_key, row["query"])
            )
        updated += 1
    conn.commit()
    return updated


def _get_validated_cache(conn: sqlite3.Connection, raw: str):
    """Return (lat, lng, is_validated) from geocache if found, else (None, None, False)."""
    normalized = normalize_place(raw)
    queries = build_queries(normalized)
    for q in queries:
        row = conn.execute(
            "SELECT lat, lng, validated FROM geocache WHERE query=? AND lat IS NOT NULL", (q,)
        ).fetchone()
        if row:
            return row[0], row[1], bool(row[2])
    return None, None, False


def propagate_geocache(conn: sqlite3.Connection) -> int:
    """Push geocache lat/lng to residences and events.

    Rules:
    - Always update rows where lat IS NULL.
    - Also update rows where lat/lng differ from geocache AND the geocache entry
      is validated (validated=1). This corrects stale coords set by old scripts.

    Returns number of rows updated.
    """
    updated = 0

    # Residences
    rows = conn.execute(
        "SELECT id, address, city, country, lat, lng FROM residences"
    ).fetchall()
    for row in rows:
        raw = build_residence_raw(row["address"] or "", row["city"] or "", row["country"] or "")
        c_lat, c_lng, is_validated = _get_validated_cache(conn, raw)
        if c_lat is None:
            continue
        current_lat = row["lat"]
        needs_update = (current_lat is None) or (
            is_validated and round(current_lat, 5) != round(c_lat, 5)
        )
        if needs_update:
            conn.execute(
                "UPDATE residences SET lat=?,lng=? WHERE id=?", (c_lat, c_lng, row["id"])
            )
            updated += 1

    # Events (geocodeable tags/types only)
    rows = conn.execute(
        "SELECT id, place, lat FROM events "
        "WHERE place IS NOT NULL AND place != '' "
        "AND (tag IN ('RESI','EMIG','CENS') "
        "     OR type IN ('Mudanza','Emigración','Residencia','Padrón','Censo'))"
    ).fetchall()
    for row in rows:
        c_lat, c_lng, is_validated = _get_validated_cache(conn, row["place"])
        if c_lat is None:
            continue
        current_lat = row["lat"]
        needs_update = (current_lat is None) or (
            is_validated and round(current_lat, 5) != round(c_lat, 5)
        )
        if needs_update:
            conn.execute(
                "UPDATE events SET lat=?,lng=? WHERE id=?", (c_lat, c_lng, row["id"])
            )
            updated += 1

    conn.commit()
    return updated
