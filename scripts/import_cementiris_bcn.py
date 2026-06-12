#!/usr/bin/env python3
"""
import_cementiris_bcn.py — Importa _resources/CementirisBCN.xlsx a la sección
Cementerios (tablas cemeteries / niches / niche_people).

Uso:
  python3 scripts/import_cementiris_bcn.py            # dry-run: resumen + informe, no toca la BD
  python3 scripts/import_cementiris_bcn.py --apply    # escribe en la BD

El Excel tiene una pestaña BBDD por cementerio de Barcelona con registros de
enterramientos (índices FamilySearch del GEDCOM Palazuelos). El script:
1. Da de alta cada cementerio (nombre oficial, descripción, coordenadas vía
   Nominatim con fallback hardcodeado).
2. Crea los nichos agrupando filas por (nínxol nº + agrupación de la pestaña),
   con título "Família X" según el apellido dominante y el titular en notas.
   Los ubica en una cuadrícula determinista por agrupación alrededor del
   centro del cementerio (a refinar a mano en el gestor).
3. Asigna a cada nicho las personas que existen en la BD: match exacto por
   nombre normalizado, o variante segura catalán/castellano con año de
   defunción compatible. El resto va al informe para revisión manual.

Re-ejecutable sin duplicar. Informe: _resources/CementirisBCN_informe.md
"""

import argparse
import datetime
import difflib
import math
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from database import get_connection  # noqa: E402
from geocode_utils import nominatim_search  # noqa: E402

XLSX = BASE_DIR / "_resources" / "CementirisBCN.xlsx"
DB_PATH = BASE_DIR / "data" / "godesia.db"
REPORT = BASE_DIR / "_resources" / "CementirisBCN_informe.md"

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Pestaña → (sheet xml, nombre oficial, descripción, coords fallback)
CEMETERIES = [
    ("sheet2.xml", "Cementiri de Collserola",
     "Cementiri metropolità de Collserola, conegut també com a Cementiri del Nord (1972).",
     (41.4216, 2.1417)),
    ("sheet3.xml", "Cementiri de Montjuïc",
     "Cementiri del Sud-oest, a la muntanya de Montjuïc (1883). El més gran de Barcelona.",
     (41.3589, 2.1487)),
    ("sheet4.xml", "Cementiri de les Corts",
     "Cementiri municipal de les Corts (1845), entre la Travessera i el Camp Nou.",
     (41.3837, 2.1248)),
    ("sheet5.xml", "Cementiri de Sant Gervasi",
     "Cementiri de Sant Gervasi de Cassoles (1853), a la falda del Putget.",
     (41.4106, 2.1330)),
    ("sheet6.xml", "Cementiri de Sarrià",
     "Cementiri de l'antiga vila de Sarrià (1845).",
     (41.4030, 2.1118)),
    ("sheet7.xml", "Cementiri de Sants",
     "Cementiri de Sants (1846), a la muntanya de Sant Pere Màrtir.",
     (41.3702, 2.1278)),
    ("sheet8.xml", "Cementiri de Sant Andreu",
     "Cementiri de Sant Andreu de Palomar (1839), un dels més antics de la ciutat.",
     (41.4434, 2.1918)),
    ("sheet9.xml", "Cementiri d'Horta",
     "Cementiri de Sant Joan d'Horta (1867).",
     (41.4438, 2.1656)),
    ("sheet10.xml", "Cementiri de Poblenou",
     "Cementiri de l'Est o de Poblenou (1775), el primer cementiri modern de Barcelona.",
     (41.3877, 2.1989)),
]

# Equivalencias de nombre de pila catalán ↔ castellano (normalizadas)
GIVEN_VARIANTS = [
    {"jose", "josep", "pepe"}, {"maria"}, {"juan", "joan"}, {"antonio", "antoni"},
    {"emilio", "emili"}, {"felipe", "felip"}, {"guillermo", "guillem"},
    {"ana", "anna", "anita"}, {"dolores", "dolors", "lola"}, {"pedro", "pere"},
    {"francisco", "francesc", "paco"}, {"jaime", "jaume"}, {"genaro", "genar"},
    {"amadeo", "amadeu"}, {"arturo", "artur"}, {"ernesto", "ernest"},
    {"enrique", "enric"}, {"jorge", "jordi"}, {"pablo", "pau"},
    {"vicente", "vicenc", "vicens"}, {"lorenzo", "llorenc"}, {"miguel", "miquel"},
    {"rosario", "roser"}, {"montserrat", "montse"}, {"esteban", "esteve"},
    {"alberto", "albert"}, {"ramon", "ramona"}, {"angel", "angela", "angelina"},
    {"carmen", "carme"}, {"eulalia", "laia"}, {"isabel", "elisabet"},
    {"joaquin", "joaquim", "quim"}, {"luis", "lluis"}, {"margarita", "margarida"},
    {"mercedes", "merce"}, {"narciso", "narcis"}, {"rafael", "rafel"},
    {"salvador", "salvado"}, {"sebastian", "sebastia"}, {"teresa", "tereseta"},
]
_VARIANT_MAP = {}
for group in GIVEN_VARIANTS:
    for name in group:
        _VARIANT_MAP[name] = group

PARTICLES = {"de", "del", "dels", "la", "les", "los", "las", "i", "y", "d"}


def norm(s):
    """minúsculas, sin acentos, espacios colapsados, Mª/Mº → maria."""
    s = (s or "").strip()
    s = re.sub(r"\bm[ªº]\.?", "maria", s, flags=re.IGNORECASE)
    s = re.sub(r"\bm\.\s", "maria ", s, flags=re.IGNORECASE)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def split_given_surnames(name):
    """Separa nombre de pila y apellidos de forma heurística: el primer token
    (más 'maria' compuesto) es el nombre; el resto, apellidos."""
    tokens = norm(name).split()
    if not tokens:
        return "", []
    given = [tokens[0]]
    rest = tokens[1:]
    # nombres compuestos habituales: "jose maria", "maria carmen", "josep anton"…
    while rest and (rest[0] in _VARIANT_MAP or given[-1] == "maria") and len(rest) >= 2:
        # solo absorbe un segundo nombre si quedan ≥2 tokens para apellidos
        given.append(rest.pop(0))
        break
    return " ".join(given), rest


def first_surname(name):
    """Primer apellido (saltando partículas), capitalizado, desde el nombre original."""
    raw_tokens = re.sub(r"\s+", " ", (name or "").strip()).split()
    _, surnames_norm = split_given_surnames(name)
    if not surnames_norm:
        return ""
    target = surnames_norm[0]
    i = 0
    while i < len(surnames_norm) and surnames_norm[i] in PARTICLES:
        i += 1
    if i < len(surnames_norm):
        target = surnames_norm[i]
    for t in raw_tokens:
        if norm(t) == target:
            return t
    return target.capitalize()


def given_compatible(g1, g2):
    """¿Son equivalentes los nombres de pila? (variante CA/ES o muy similares)"""
    if g1 == g2:
        return True
    t1, t2 = g1.split(), g2.split()
    # "maria dolores" ↔ "dolores": el prefijo María se omite a menudo
    if len(t1) != len(t2):
        if len(t1) > len(t2) and t1[0] == "maria":
            t1 = t1[1:]
        elif len(t2) > len(t1) and t2[0] == "maria":
            t2 = t2[1:]
    if len(t1) != len(t2):
        return False
    for a, b in zip(t1, t2):
        if a == b:
            continue
        if _VARIANT_MAP.get(a) is _VARIANT_MAP.get(b) and _VARIANT_MAP.get(a) is not None:
            continue
        if difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
            continue
        return False
    return True


# ---------------------------------------------------------------------------
# Lectura del xlsx (stdlib)
# ---------------------------------------------------------------------------

def load_shared_strings(z):
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(M + "t")) for si in root.iter(M + "si")]


def read_sheet(z, shared, path):
    """Devuelve lista de dicts {cabecera: valor} usando la primera fila como cabecera."""
    root = ET.fromstring(z.read("xl/" + path))
    raw_rows = []
    for row in root.iter(M + "row"):
        cells = {}
        for c in row.iter(M + "c"):
            ref = c.get("r") or ""
            col = "".join(ch for ch in ref if ch.isalpha())
            t = c.get("t")
            v = c.find(M + "v")
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(M + "t"))
            else:
                val = v.text if v is not None else ""
            cells[col] = (val or "").strip()
        raw_rows.append(cells)
    if not raw_rows:
        return []
    header = {col: name for col, name in raw_rows[0].items() if name}
    out = []
    for cells in raw_rows[1:]:
        row = {header[col]: val for col, val in cells.items() if col in header}
        if any(v for v in row.values()):
            out.append(row)
    return out


def read_cells(z, shared, path):
    """Celdas crudas de una hoja: {ref: valor} (p.ej. {'F12': 'Pasqual Godes'})."""
    root = ET.fromstring(z.read("xl/" + path))
    cells = {}
    for row in root.iter(M + "row"):
        for c in row.iter(M + "c"):
            ref = c.get("r") or ""
            t = c.get("t")
            v = c.find(M + "v")
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            else:
                val = v.text if v is not None else ""
            cells[ref] = (val or "").strip()
    return cells


def read_hyperlinks(z, sheet_xml):
    """Hyperlinks de una hoja: [(ref_celda, url)]."""
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    try:
        rels = ET.fromstring(z.read(f"xl/worksheets/_rels/{sheet_xml}.rels"))
    except KeyError:
        return []
    relmap = {rel.get("Id"): rel.get("Target") for rel in rels}
    root = ET.fromstring(z.read(f"xl/worksheets/{sheet_xml}"))
    out = []
    for h in root.iter(M + "hyperlink"):
        url = relmap.get(h.get(R + "id"), "")
        if url:
            out.append((h.get("ref") or "", url))
    return out


def load_fs_person_links(z, shared):
    """Pestaña 1: filas índice con NOM (col F) cuyo hyperlink (en col A/B/C de la
    misma fila) apunta a la imagen exacta de su página del registro.
    Devuelve {nombre_normalizado: url}."""
    cells = read_cells(z, shared, "worksheets/sheet1.xml")
    links = {}
    for ref, url in read_hyperlinks(z, "sheet1.xml"):
        if "familysearch" not in url:
            continue
        rownum = "".join(ch for ch in ref if ch.isdigit())
        nom = cells.get("F" + rownum, "")
        if nom:
            links.setdefault(norm(nom), url)
    return links


def _norm_island(s):
    """Normaliza ILLA/ISLA para casar pestaña 10 con la 11."""
    n = norm(s).replace("illa", "isla").replace("int o centro", "interior centro")
    return re.sub(r"\s+", " ", n).strip()


def load_poblenou_volumes(z, shared):
    """Pestaña 11: volúmenes del registro de Poble Nou por (isla, dept, rango de nº).
    Devuelve [(isla_norm, dept_digits, desde, hasta, url)]."""
    cells = read_cells(z, shared, "worksheets/sheet11.xml")
    url_by_row = {}
    for ref, url in read_hyperlinks(z, "sheet11.xml"):
        if "familysearch" in url:
            url_by_row["".join(ch for ch in ref if ch.isdigit())] = url
    vols = []
    row = 2
    while f"A{row}" in cells or f"B{row}" in cells:
        isla = cells.get(f"B{row}", "")
        desde, hasta = cells.get(f"D{row}", ""), cells.get(f"E{row}", "")
        url = url_by_row.get(str(row))
        if url and isla and desde.isdigit() and hasta.isdigit():
            dept = re.sub(r"\D", "", cells.get(f"C{row}", ""))
            vols.append((_norm_island(isla), dept, int(desde), int(hasta), url))
        row += 1
    return vols


def find_volume_url(volumes, illa, dept, num):
    """URL del volumen de Poble Nou para un nicho, si hay candidato único."""
    if not num or not str(num).strip().isdigit():
        return None
    n = int(str(num).strip())
    isla_n = _norm_island(illa)
    dept_n = re.sub(r"\D", "", dept or "")
    cands = {url for v_isla, v_dept, desde, hasta, url in volumes
             if v_isla == isla_n and desde <= n <= hasta
             and (not dept_n or not v_dept or v_dept == dept_n)}
    return cands.pop() if len(cands) == 1 else None


def parse_burial_date(data_str):
    """DATA puede ser 'dd/mm/yyyy' o serial Excel.
    Devuelve (texto dd/mm/yyyy o original, año o None)."""
    s = (data_str or "").strip()
    if not s or s.startswith("#"):
        return "", None
    m = re.search(r"(\d{4})", s)
    if "/" in s and m:
        return s, int(m.group(1))
    try:
        serial = float(s)
        if 1 < serial < 80000:
            d = datetime.date(1899, 12, 30) + datetime.timedelta(days=serial)
            return d.strftime("%-d/%-m/%Y"), d.year
    except ValueError:
        pass
    return s, None


def parse_burial_year(data_str):
    return parse_burial_date(data_str)[1]


def clean(value):
    """Valores de celda: '#VALUE!' y similares → vacío."""
    v = (value or "").strip()
    return "" if v.startswith("#") else v


# ---------------------------------------------------------------------------
# Nichos: clave, nombre y cuadrícula
# ---------------------------------------------------------------------------

def niche_key_and_name(row):
    """Construye la clave de agrupación y el nombre legible según las columnas presentes."""
    num = row.get("NINXOL Nº", "")
    tipo = row.get("TIPO", "")
    via = row.get("VIA", "")
    agrup = row.get("AGRUP.", "") or row.get("AGRP.", "")
    illa = row.get("ILLA", "") or row.get("ISLA", "")
    dept = row.get("DEPT.", "") or row.get("DPT.", "")

    if via or tipo:  # Montjuïc
        parts = [f"{tipo or 'Nínxol'} {num}".strip()]
        if via and norm(via) not in ("sin via", "sense via"):
            parts.append(f"Via {via}")
        if agrup:
            parts.append(f"Agrupació {agrup}")
        group = f"{via}|{agrup}"
    elif illa:  # Poble Nou / Sarrià
        parts = [f"Nínxol {num}", illa]
        if dept:
            parts.append(f"Dept. {dept}")
        group = f"{illa}|{dept}"
    else:
        parts = [f"Nínxol {num}"]
        if dept:
            parts.append(f"Dept. {dept}")
        if agrup:
            parts.append(f"Agrup. {agrup}")
        group = f"{dept}|{agrup}"

    name = ", ".join(p for p in parts if p and p.strip())
    key = (num, tipo, via, agrup, illa, dept)
    return key, name, group


def grid_positions(center_lat, center_lng, groups):
    """Coloca cada grupo en un anillo alrededor del centro y sus nichos en
    cuadrícula. Determinista (grupos y nichos ordenados). Devuelve
    {(group, niche_key): (lat, lng)}."""
    pos = {}
    group_names = sorted(groups.keys())
    n_groups = max(len(group_names), 1)
    for gi, gname in enumerate(group_names):
        angle = 2 * math.pi * gi / n_groups
        radius = 0.0005 if n_groups > 1 else 0.0  # ~50 m
        g_lat = center_lat + radius * math.sin(angle)
        g_lng = center_lng + radius * math.cos(angle) / math.cos(math.radians(center_lat))
        keys = sorted(groups[gname], key=lambda k: (str(k),))
        cols = 5
        step = 0.00006  # ~6 m
        for ni, key in enumerate(keys):
            r, c = divmod(ni, cols)
            lat = g_lat + (r - (len(keys) / cols) / 2) * step
            lng = g_lng + (c - cols / 2) * step / math.cos(math.radians(center_lat))
            pos[(gname, key)] = (round(lat, 7), round(lng, 7))
    return pos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Escribir en la BD (por defecto: dry-run)")
    ap.add_argument("--no-geocode", action="store_true", help="No llamar a Nominatim (usar fallbacks)")
    args = ap.parse_args()

    z = zipfile.ZipFile(XLSX)
    shared = load_shared_strings(z)
    fs_links = load_fs_person_links(z, shared)
    pn_volumes = load_poblenou_volumes(z, shared)
    conn = get_connection(str(DB_PATH))

    # Índice de personas de la BD
    db_people = []
    for pid, name, death_year in conn.execute("SELECT id, name, death_year FROM people"):
        given, surnames = split_given_surnames(name)
        db_people.append({"id": pid, "name": name, "norm": norm(name),
                          "given": given, "surnames": surnames, "death_year": death_year})
    by_norm = defaultdict(list)
    by_surnames = defaultdict(list)
    for p in db_people:
        by_norm[p["norm"]].append(p)
        by_surnames[" ".join(p["surnames"])].append(p)

    report = {
        "cemeteries": [], "exact": [], "variant": [], "doubtful": [],
        "unmatched": [], "multi_niche": [], "no_niche_rows": [],
    }
    totals = Counter()
    person_niches = defaultdict(list)  # person_id → [(cemetery, niche_name)]

    for sheet, official_name, description, fallback in CEMETERIES:
        rows = read_sheet(z, shared, "worksheets/" + sheet)
        rows = [r for r in rows if (r.get("NOM") or "").strip()]

        # --- Cementerio ---
        existing = conn.execute("SELECT id, lat, lng FROM cemeteries WHERE name = ?",
                                (official_name,)).fetchone()
        if existing:
            cem_id, lat, lng = existing["id"], existing["lat"], existing["lng"]
            geo_src = "ya existía"
        else:
            lat, lng, geo_src = fallback[0], fallback[1], "fallback"
            if not args.no_geocode:
                cands = nominatim_search(f"{official_name}, Barcelona")
                good = [c for c in cands if c.get("class") in ("amenity", "landuse")
                        or "cemetery" in (c.get("type") or "")]
                pick = (good or cands)[:1]
                if pick:
                    nlat, nlng = float(pick[0]["lat"]), float(pick[0]["lon"])
                    # sanity check: dentro del área de Barcelona
                    if 41.30 < nlat < 41.50 and 2.05 < nlng < 2.25:
                        lat, lng, geo_src = nlat, nlng, "nominatim"
            cem_id = None
            if args.apply:
                cur = conn.execute(
                    "INSERT INTO cemeteries (name, city, lat, lng, description) VALUES (?, 'Barcelona', ?, ?, ?)",
                    (official_name, lat, lng, description))
                cem_id = cur.lastrowid
        report["cemeteries"].append((official_name, lat, lng, geo_src, len(rows)))
        totals["cemeteries"] += 1

        # --- Agrupar filas por nicho ---
        niches = defaultdict(list)   # key → [rows]
        niche_meta = {}              # key → (name, group)
        for r in rows:
            if not (r.get("NINXOL Nº") or "").strip():
                report["no_niche_rows"].append((official_name, r.get("NOM", "")))
                continue
            key, name, group = niche_key_and_name(r)
            niches[key].append(r)
            niche_meta[key] = (name, group)

        groups = defaultdict(list)
        for key, (name, group) in niche_meta.items():
            groups[group].append(key)
        positions = grid_positions(lat or fallback[0], lng or fallback[1], groups)

        # --- Crear nichos y asignar personas ---
        for key in sorted(niches.keys(), key=lambda k: str(k)):
            nrows = niches[key]
            name, group = niche_meta[key]
            nlat, nlng = positions[(group, key)]

            # título: apellido dominante (≥2) o primer apellido del titular
            surname_counts = Counter(
                fs for fs in (first_surname(r.get("NOM", "")) for r in nrows) if fs)
            title = None
            if surname_counts:
                top, cnt = surname_counts.most_common(1)[0]
                if cnt >= 2:
                    title = f"Família {top}"
            if not title:
                titulars = [r.get("TITULAR", "") for r in nrows if (r.get("TITULAR") or "").strip()]
                if titulars:
                    fs = first_surname(titulars[0])
                    if fs:
                        title = f"Família {fs}"

            titulars = sorted({(r.get("TITULAR") or "").strip() for r in nrows} - {""})
            notes = f"Titular de la concessió: {'; '.join(titulars)}" if titulars else ""

            # Enlace al volumen del registre (Poble Nou, pestaña 11)
            k_num, _, _, _, k_illa, k_dept = key
            niche_fs = find_volume_url(pn_volumes, k_illa, k_dept, k_num)
            if niche_fs:
                totals["niche_fs"] += 1

            niche_id = None
            if args.apply:
                row_db = conn.execute(
                    "SELECT id FROM niches WHERE cemetery_id = ? AND name = ?",
                    (cem_id, name)).fetchone()
                if row_db:
                    niche_id = row_db["id"]
                    conn.execute(
                        "UPDATE niches SET title = COALESCE(title, ?), notes = ?, "
                        "lat = COALESCE(lat, ?), lng = COALESCE(lng, ?), "
                        "fs_url = COALESCE(?, fs_url) WHERE id = ?",
                        (title, notes, nlat, nlng, niche_fs, niche_id))
                else:
                    cur = conn.execute(
                        "INSERT INTO niches (cemetery_id, name, title, lat, lng, notes, fs_url) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cem_id, name, title, nlat, nlng, notes, niche_fs))
                    niche_id = cur.lastrowid
                # El Excel es la fuente de verdad de los registros: reemplazo completo
                conn.execute("DELETE FROM niche_records WHERE niche_id = ?", (niche_id,))
            totals["niches"] += 1

            # Registros ordenados por fecha de enterramiento (sin fecha al final)
            def _sort_key(r):
                _, year = parse_burial_date(r.get("DATA", ""))
                return (year is None, year or 0)

            for r in sorted(nrows, key=_sort_key):
                nom = r.get("NOM", "").strip()
                burial_str, burial_year = parse_burial_date(r.get("DATA", ""))
                given, surnames = split_given_surnames(nom)
                surn_key = " ".join(surnames)
                match, level = None, None

                exact = by_norm.get(norm(nom), [])
                if len(exact) == 1:
                    match, level = exact[0], "exact"
                elif not exact:
                    cands = [p for p in by_surnames.get(surn_key, [])
                             if given_compatible(given, p["given"])]
                    # año compatible: defunción BD dentro de ±1 del año de enterramiento
                    cands = [p for p in cands
                             if p["death_year"] is None or burial_year is None
                             or abs(p["death_year"] - burial_year) <= 1]
                    if len(cands) == 1:
                        match, level = cands[0], "variant"
                    else:
                        sugg = by_surnames.get(surn_key, [])
                        if sugg:
                            report["doubtful"].append(
                                (official_name, name, nom, burial_year,
                                 [(p["id"], p["name"], p["death_year"]) for p in sugg[:4]]))
                        else:
                            report["unmatched"].append((official_name, nom))
                        totals["unmatched" if not sugg else "doubtful"] += 1
                else:
                    report["doubtful"].append(
                        (official_name, name, nom, burial_year,
                         [(p["id"], p["name"], p["death_year"]) for p in exact[:4]]))
                    totals["doubtful"] += 1

                # Registro completo del libro de enterraments (haya match o no)
                totals["records"] += 1
                fs_url = fs_links.get(norm(nom))
                if fs_url:
                    totals["record_fs"] += 1
                if args.apply:
                    conn.execute(
                        "INSERT INTO niche_records (niche_id, person_id, name, burial_date, "
                        "death_day, civil_status, spouse, age, origin, profession, address, "
                        "parish, court, titular, notes, fs_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (niche_id, match["id"] if match else None, nom, burial_str,
                         clean(r.get("DEF.")), clean(r.get("ESTAT")), clean(r.get("amb")),
                         clean(r.get("EDAT")), clean(r.get("ORIGEN")), clean(r.get("PROFESSIÓ")),
                         clean(r.get("ADREÇA")), clean(r.get("PARROQUIA")), clean(r.get("JUTJAT")),
                         clean(r.get("TITULAR")), clean(r.get("DESCRIPCIÓ")), fs_url))

                if not match:
                    continue
                report[level].append((official_name, name, nom, match["id"], match["name"]))
                totals[level] += 1
                person_niches[match["id"]].append((official_name, name))
                if args.apply:
                    conn.execute(
                        "INSERT OR IGNORE INTO niche_people (niche_id, person_id) VALUES (?, ?)",
                        (niche_id, match["id"]))

    if args.apply:
        conn.commit()

    # traslados: personas en más de un nicho
    for pid, places in sorted(person_niches.items()):
        if len(places) > 1:
            name = next(p["name"] for p in db_people if p["id"] == pid)
            report["multi_niche"].append((pid, name, places))

    write_report(report, totals, args.apply)

    mode = "APLICADO" if args.apply else "DRY-RUN (usa --apply para escribir)"
    print(f"\n=== {mode} ===")
    print(f"Cementerios: {totals['cemeteries']}")
    print(f"Nichos: {totals['niches']}")
    print(f"Registros de enterramiento: {totals['records']}")
    print(f"Registros con imagen FamilySearch enlazada: {totals['record_fs']}")
    print(f"Nichos con volumen FamilySearch (Poble Nou): {totals['niche_fs']}")
    print(f"Asignaciones exactas: {totals['exact']}")
    print(f"Asignaciones por variante: {totals['variant']}")
    print(f"Dudosos (revisar informe): {totals['doubtful']}")
    print(f"Sin match (Palazuelos no presente en BD): {totals['unmatched']}")
    print(f"Personas en varios nichos: {len(report['multi_niche'])}")
    print(f"Filas sin nº de nicho: {len(report['no_niche_rows'])}")
    print(f"Informe: {REPORT}")


def write_report(report, totals, applied):
    lines = [f"# Informe d'importació CementirisBCN.xlsx",
             f"",
             f"Mode: {'APLICAT' if applied else 'dry-run'} — generat {datetime.datetime.now():%Y-%m-%d %H:%M}",
             f""]
    lines.append("## Cementiris")
    for name, lat, lng, src, nrows in report["cemeteries"]:
        lines.append(f"- **{name}** — ({lat:.5f}, {lng:.5f}) [{src}] — {nrows} registres")
    lines.append("")
    lines.append(f"## Assignacions exactes ({len(report['exact'])})")
    for cem, niche, nom, pid, dbname in report["exact"]:
        lines.append(f"- {nom} → `{pid}` {dbname} — {niche} ({cem})")
    lines.append("")
    lines.append(f"## Assignacions per variant CA/ES ({len(report['variant'])})")
    for cem, niche, nom, pid, dbname in report["variant"]:
        lines.append(f"- {nom} → `{pid}` **{dbname}** — {niche} ({cem})")
    lines.append("")
    lines.append(f"## Dubtosos — revisar i assignar a mà al gestor ({len(report['doubtful'])})")
    for cem, niche, nom, year, cands in report["doubtful"]:
        cstr = "; ".join(f"`{pid}` {n} (†{dy or '?'})" for pid, n, dy in cands)
        lines.append(f"- {nom} (enterrat {year or '?'}) — {niche} ({cem}) — candidats: {cstr}")
    lines.append("")
    lines.append(f"## Persones en més d'un nínxol — trasllats ({len(report['multi_niche'])})")
    for pid, name, places in report["multi_niche"]:
        pstr = "; ".join(f"{n} ({c})" for c, n in places)
        lines.append(f"- `{pid}` {name}: {pstr}")
    lines.append("")
    lines.append(f"## Files sense número de nínxol ({len(report['no_niche_rows'])})")
    for cem, nom in report["no_niche_rows"]:
        lines.append(f"- {nom} ({cem})")
    lines.append("")
    lines.append(f"## Sense match a la BD ({len(report['unmatched'])})")
    for cem, nom in sorted(report["unmatched"]):
        lines.append(f"- {nom} ({cem})")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
