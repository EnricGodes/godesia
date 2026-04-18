"""SQLite database for Godesia — schema, connection, and query helpers."""

import re
import sqlite3
import unicodedata
from datetime import date, timedelta
from pathlib import Path

def _normalize_accent(text: str) -> str:
    """Normalize text by removing accents and lowercasing for accent-insensitive search."""
    if not text:
        return ""
    # Strip accents using NFD normalization
    normalized = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return normalized.lower()


MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

MONTHS_SPANISH = {
    1: "ene.", 2: "feb.", 3: "mar.", 4: "abr.", 5: "may.", 6: "jun.",
    7: "jul.", 8: "ago.", 9: "sept.", 10: "oct.", 11: "nov.", 12: "dic.",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    given_name TEXT,
    surname TEXT,
    nickname TEXT,
    sex TEXT,
    birth_date TEXT,
    birth_day INTEGER,
    birth_month INTEGER,
    birth_year INTEGER,
    birth_place TEXT,
    birth_note TEXT,
    death_date TEXT,
    death_year INTEGER,
    death_place TEXT,
    death_cause TEXT,
    death_note TEXT,
    death_age TEXT,
    is_alive INTEGER DEFAULT 0,
    father_id TEXT,
    mother_id TEXT,
    father_name TEXT,
    mother_name TEXT,
    photo_file TEXT,
    photo_count INTEGER DEFAULT 0,
    baptism_date TEXT,
    baptism_place TEXT,
    godparents TEXT
);

CREATE TABLE IF NOT EXISTS marriages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person1_id TEXT,
    person2_id TEXT,
    date TEXT,
    place TEXT,
    divorce_date TEXT,
    divorce_place TEXT,
    divorce_note TEXT
);

CREATE TABLE IF NOT EXISTS partnerships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person1_id TEXT,
    person2_id TEXT,
    date TEXT
);

CREATE TABLE IF NOT EXISTS children (
    parent_id TEXT,
    child_id TEXT,
    PRIMARY KEY (parent_id, child_id)
);

CREATE TABLE IF NOT EXISTS occupations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    title TEXT,
    date TEXT,
    place TEXT
);

CREATE TABLE IF NOT EXISTS residences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    address TEXT,
    address2 TEXT,
    city TEXT,
    country TEXT,
    date TEXT
);

CREATE TABLE IF NOT EXISTS burial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    place_detail TEXT,
    date TEXT,
    place TEXT
);

CREATE TABLE IF NOT EXISTS military (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    description TEXT,
    date TEXT,
    place TEXT
);

CREATE TABLE IF NOT EXISTS anecdotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    description TEXT,
    date TEXT,
    place TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    tag TEXT,
    type TEXT,
    description TEXT,
    date TEXT,
    place TEXT,
    age TEXT,
    note TEXT,
    cause TEXT,
    address TEXT,
    email TEXT,
    www TEXT
);

-- NOTA: Las tablas photos, photo_tags, albums son gestionadas por scripts/sync_catalog.py
-- El script crea el nuevo esquema (actual):
-- CREATE TABLE photos (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     filename TEXT NOT NULL UNIQUE,
--     url TEXT, filesize INTEGER, title TEXT, date TEXT, place TEXT,
--     photo_rin TEXT, album_id TEXT,
--     is_cutout INTEGER DEFAULT 0, is_parent_photo INTEGER DEFAULT 0,
--     is_personal_photo INTEGER DEFAULT 0, is_prim_cutout INTEGER DEFAULT 0,
--     parent_photo_id INTEGER, position TEXT, is_downloaded INTEGER DEFAULT 0,
--     inserted_at TEXT, updated_at TEXT
-- );
-- CREATE TABLE photo_tags (
--     photo_id, person_id, is_primary, is_prim_cutout, position, source, PRIMARY KEY (photo_id, person_id)
-- );
-- CREATE TABLE albums (gedcom_id PRIMARY KEY, title TEXT);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    content TEXT
);

CREATE INDEX IF NOT EXISTS idx_people_birth_md ON people(birth_month, birth_day);
CREATE INDEX IF NOT EXISTS idx_people_name ON people(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_people_surname ON people(surname COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_people_father ON people(father_id);
CREATE INDEX IF NOT EXISTS idx_people_mother ON people(mother_id);
CREATE INDEX IF NOT EXISTS idx_children_parent ON children(parent_id);
CREATE INDEX IF NOT EXISTS idx_children_child ON children(child_id);
-- photo_tags indices created by scripts/sync_catalog.py:
-- CREATE INDEX IF NOT EXISTS idx_photo_tags_person ON photo_tags(person_id);
-- CREATE INDEX IF NOT EXISTS idx_photo_tags_photo ON photo_tags(photo_id);
CREATE INDEX IF NOT EXISTS idx_occupations_person ON occupations(person_id);
CREATE INDEX IF NOT EXISTS idx_residences_person ON residences(person_id);
CREATE INDEX IF NOT EXISTS idx_notes_person ON notes(person_id);
CREATE INDEX IF NOT EXISTS idx_burial_person ON burial(person_id);
"""


def parse_gedcom_date(date_str):
    """Parse GEDCOM date string. Returns (day, month, year) with None for unknown parts."""
    if not date_str:
        return None, None, None

    # Strip prefixes
    for prefix in ("ABT", "BEF", "AFT", "EST", "CAL"):
        if date_str.startswith(prefix):
            date_str = date_str[len(prefix):].strip()

    # Handle ranges: "BET 1860 AND 1865", "FROM 1865 TO 1868"
    if "AND" in date_str or "TO" in date_str:
        parts = re.split(r"\s+AND\s+|\s+TO\s+", date_str)
        date_str = parts[0].strip()
        for prefix in ("BET", "FROM"):
            if date_str.startswith(prefix):
                date_str = date_str[len(prefix):].strip()

    parts = date_str.split()
    if len(parts) == 3:  # "5 APR 1824"
        try:
            return int(parts[0]), MONTHS.get(parts[1]), int(parts[2])
        except ValueError:
            return None, None, None
    elif len(parts) == 2:  # "APR 1824"
        return None, MONTHS.get(parts[0]), int(parts[1]) if parts[1].isdigit() else None
    elif len(parts) == 1 and parts[0].isdigit():  # "1824"
        return None, None, int(parts[0])
    return None, None, None


def convert_date_to_spanish(date_str):
    """Convert GEDCOM/date string to Spanish format: '19 ago. 1917'"""
    if not date_str:
        return ""

    original = date_str

    # Handle ranges: "FROM APR 1925 TO 1935" or "BET 1860 AND 1865" or "TO 13 JUN 1958"
    if "FROM" in date_str and "TO" in date_str:
        # "FROM APR 1925 TO 1935" → convert "APR 1925"
        start = date_str.split("FROM")[1].split("TO")[0].strip()
        end = date_str.split("TO")[1].strip()
        start_spanish = convert_date_to_spanish(start)
        end_spanish = convert_date_to_spanish(end)
        return f"{start_spanish} - {end_spanish}"
    elif date_str.startswith("TO "):
        # "TO 13 JUN 1958" → convert "13 JUN 1958" and add prefix
        end_date = date_str[3:].strip()
        end_spanish = convert_date_to_spanish(end_date)
        return f"hasta {end_spanish}"
    elif "BET" in date_str and "AND" in date_str:
        # "BET 1860 AND 1865" → convert both
        start = date_str.split("BET")[1].split("AND")[0].strip()
        end = date_str.split("AND")[1].strip()
        start_spanish = convert_date_to_spanish(start)
        end_spanish = convert_date_to_spanish(end)
        return f"{start_spanish} - {end_spanish}"

    # Strip prefixes (ABT, BEF, AFT, etc.)
    for prefix in ("ABT", "BEF", "AFT", "EST", "CAL"):
        if date_str.startswith(prefix):
            date_str = date_str[len(prefix):].strip()
            break

    parts = date_str.split()

    if len(parts) == 3:  # "5 APR 1824"
        try:
            day = int(parts[0])
            month = MONTHS.get(parts[1].upper())
            year = int(parts[2])
            if month:
                return f"{day} {MONTHS_SPANISH[month]} {year}"
        except (ValueError, KeyError):
            pass
    elif len(parts) == 2:  # "APR 1824" o "1824"
        if parts[0].isdigit():  # "1824"
            return parts[0]
        else:  # "APR 1824"
            month = MONTHS.get(parts[0].upper())
            try:
                year = int(parts[1])
                if month:
                    return f"{MONTHS_SPANISH[month]} {year}"
            except ValueError:
                pass
    elif len(parts) == 1 and parts[0].isdigit():  # "1824"
        return parts[0]

    # Si no puede parsear, retorna el original
    return original


def get_connection(db_path):
    """Create a SQLite connection with row factory and custom functions."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # Register custom function for accent-insensitive search
    conn.create_function("NORMALIZE", 1, _normalize_accent)
    return conn


def init_db(conn):
    """Initialize the database schema."""
    conn.executescript(SCHEMA)
    conn.commit()


# --- Query helpers ---

def get_person(conn, person_id):
    """Get a person by ID."""
    return conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()


def search_people(conn, query, limit=20):
    """Search people by name fragment."""
    import re
    # Normalize spaces in query (single spaces, allow multiple in DB)
    normalized_query = re.sub(r'\s+', '%', query.strip())
    return conn.execute(
        "SELECT id, name, given_name, surname, nickname, birth_year, death_year, photo_file, is_alive "
        "FROM people WHERE NORMALIZE(name) LIKE '%' || NORMALIZE(?) || '%' ORDER BY name LIMIT ?",
        (query.strip(), limit)
    ).fetchall()


def find_person_by_name(conn, name_fragment):
    """Find best matching person(s) by name. Returns list of dicts."""
    rows = search_people(conn, name_fragment, limit=5)
    return [dict(r) for r in rows]


def get_parents(conn, person_id):
    """Get father and mother of a person."""
    person = get_person(conn, person_id)
    if not person:
        return None, None
    father = get_person(conn, person["father_id"]) if person["father_id"] else None
    mother = get_person(conn, person["mother_id"]) if person["mother_id"] else None
    return father, mother


def get_children(conn, person_id):
    """Get children of a person."""
    return conn.execute(
        "SELECT p.* FROM people p "
        "JOIN children c ON p.id = c.child_id "
        "WHERE c.parent_id = ? ORDER BY p.birth_year",
        (person_id,)
    ).fetchall()


def get_spouses(conn, person_id):
    """Get spouses of a person with marriage info."""
    rows = conn.execute(
        "SELECT m.*, "
        "CASE WHEN m.person1_id = ? THEN m.person2_id ELSE m.person1_id END AS spouse_id "
        "FROM marriages m "
        "WHERE m.person1_id = ? OR m.person2_id = ?",
        (person_id, person_id, person_id)
    ).fetchall()
    result = []
    for r in rows:
        spouse = get_person(conn, r["spouse_id"])
        if spouse:
            result.append({
                "person": dict(spouse),
                "marriage_date": r["date"],
                "marriage_place": r["place"],
            })
    return result


def get_birthdays_this_week(conn):
    """Get people with birthdays in the next 7 days."""
    today = date.today()
    results = []
    for delta in range(7):
        d = today + timedelta(days=delta)
        rows = conn.execute(
            "SELECT id, name, given_name, surname, birth_day, birth_month, birth_year, "
            "photo_file, is_alive FROM people "
            "WHERE birth_month = ? AND birth_day = ? ORDER BY name",
            (d.month, d.day)
        ).fetchall()
        for row in rows:
            age = d.year - row["birth_year"] if row["birth_year"] else None
            results.append({
                "id": row["id"],
                "name": row["name"],
                "given_name": row["given_name"],
                "surname": row["surname"],
                "birth_day": row["birth_day"],
                "birth_month": row["birth_month"],
                "birth_year": row["birth_year"],
                "age": age,
                "is_alive": bool(row["is_alive"]),
                "photo": row["photo_file"],
                "is_today": delta == 0,
                "date_label": d.strftime("%d/%m"),
            })
    return results


def get_tree_data(conn, person_id, generations_up=3, generations_down=2):
    """Build tree data centered on a person."""

    def build_ancestors(pid, gen_remaining):
        person = get_person(conn, pid)
        if not person:
            return None
        node = _person_to_node(person)
        if gen_remaining > 0:
            if person["father_id"]:
                node["father"] = build_ancestors(person["father_id"], gen_remaining - 1)
            if person["mother_id"]:
                node["mother"] = build_ancestors(person["mother_id"], gen_remaining - 1)
        return node

    def build_descendants(pid, gen_remaining):
        person = get_person(conn, pid)
        if not person:
            return None
        node = _person_to_node(person)
        if gen_remaining > 0:
            kids = get_children(conn, pid)
            if kids:
                node["children"] = [
                    build_descendants(c["id"], gen_remaining - 1) for c in kids
                ]
                node["children"] = [c for c in node["children"] if c]
        return node

    # Build the central node with ancestors and descendants
    root = build_ancestors(person_id, generations_up)
    if root:
        # Add descendants
        kids = get_children(conn, person_id)
        if kids:
            root["children"] = []
            for kid in kids:
                child_node = build_descendants(kid["id"], generations_down - 1)
                if child_node:
                    root["children"].append(child_node)

        # Add spouse info
        spouses = get_spouses(conn, person_id)
        if spouses:
            root["spouses"] = []
            for s in spouses:
                root["spouses"].append({
                    "id": s["person"]["id"],
                    "name": s["person"]["name"],
                    "given_name": s["person"].get("given_name"),
                    "surname": s["person"].get("surname"),
                    "nickname": s["person"].get("nickname"),
                    "birth_year": s["person"]["birth_year"],
                    "death_year": s["person"].get("death_year"),
                    "photo": s["person"]["photo_file"],
                    "marriage_date": s["marriage_date"],
                    "marriage_place": s["marriage_place"],
                })

    return root


def get_related_person_ids(conn, person_id, generations=2):
    """Get IDs of a person and their relatives (for LLM context reduction)."""
    ids = set()
    ids.add(person_id)

    def expand(pid, gen):
        if gen <= 0:
            return
        p = get_person(conn, pid)
        if not p:
            return
        # Parents
        if p["father_id"]:
            ids.add(p["father_id"])
            expand(p["father_id"], gen - 1)
        if p["mother_id"]:
            ids.add(p["mother_id"])
            expand(p["mother_id"], gen - 1)
        # Children
        for child in get_children(conn, pid):
            ids.add(child["id"])
            if gen > 1:
                expand(child["id"], gen - 1)
        # Spouses
        for spouse in get_spouses(conn, pid):
            ids.add(spouse["person"]["id"])

    expand(person_id, generations)
    return ids


def get_people_by_ids(conn, person_ids):
    """Get full person data for a list of IDs."""
    placeholders = ",".join("?" for _ in person_ids)
    rows = conn.execute(
        f"SELECT * FROM people WHERE id IN ({placeholders})",
        list(person_ids)
    ).fetchall()
    result = []
    for r in rows:
        person = dict(r)
        # Add related data
        person["occupations"] = [dict(o) for o in conn.execute(
            "SELECT title, date, place FROM occupations WHERE person_id = ?", (r["id"],)
        ).fetchall()]
        person["residences"] = [dict(res) for res in conn.execute(
            "SELECT address, city, date FROM residences WHERE person_id = ?", (r["id"],)
        ).fetchall()]
        person["notes"] = [row["content"] for row in conn.execute(
            "SELECT content FROM notes WHERE person_id = ?", (r["id"],)
        ).fetchall()]
        person["children_list"] = [dict(c) for c in get_children(conn, r["id"])]
        spouses = get_spouses(conn, r["id"])
        person["spouses_list"] = spouses
        result.append(person)
    return result


def get_siblings(conn, person_id):
    """Get siblings of a person (same parents, excluding self)."""
    person = get_person(conn, person_id)
    if not person:
        return []
    siblings = set()
    # Find siblings via father
    if person["father_id"]:
        rows = conn.execute(
            "SELECT child_id FROM children WHERE parent_id = ? AND child_id != ?",
            (person["father_id"], person_id)
        ).fetchall()
        siblings.update(r["child_id"] for r in rows)
    # Find siblings via mother
    if person["mother_id"]:
        rows = conn.execute(
            "SELECT child_id FROM children WHERE parent_id = ? AND child_id != ?",
            (person["mother_id"], person_id)
        ).fetchall()
        siblings.update(r["child_id"] for r in rows)
    return [get_person(conn, sid) for sid in siblings if get_person(conn, sid)]


def get_grandparents(conn, person_id):
    """Get grandparents (parents of parents)."""
    person = get_person(conn, person_id)
    if not person:
        return []
    result = []
    for parent_id in [person["father_id"], person["mother_id"]]:
        if parent_id:
            parent = get_person(conn, parent_id)
            if parent:
                if parent["father_id"]:
                    gp = get_person(conn, parent["father_id"])
                    if gp:
                        result.append({"person": gp, "via": parent["name"]})
                if parent["mother_id"]:
                    gp = get_person(conn, parent["mother_id"])
                    if gp:
                        result.append({"person": gp, "via": parent["name"]})
    return result


def get_grandchildren(conn, person_id):
    """Get grandchildren (children of children)."""
    result = []
    kids = get_children(conn, person_id)
    for kid in kids:
        grandkids = get_children(conn, kid["id"])
        for gk in grandkids:
            result.append({"person": gk, "via": kid["name"]})
    return result


def get_occupations(conn, person_id):
    """Get occupations for a person."""
    return conn.execute(
        "SELECT title, date, place FROM occupations WHERE person_id = ?",
        (person_id,)
    ).fetchall()


def get_residences(conn, person_id):
    """Get residences for a person."""
    return conn.execute(
        "SELECT address, address2, city, country, date FROM residences WHERE person_id = ?",
        (person_id,)
    ).fetchall()


def get_notes(conn, person_id):
    """Get notes for a person."""
    return conn.execute(
        "SELECT content FROM notes WHERE person_id = ?",
        (person_id,)
    ).fetchall()


def get_military(conn, person_id):
    """Get military records for a person."""
    return conn.execute(
        "SELECT description, date, place FROM military WHERE person_id = ?",
        (person_id,)
    ).fetchall()


def get_burial(conn, person_id):
    """Get burial records for a person."""
    return conn.execute(
        "SELECT place, place_detail, date FROM burial WHERE person_id = ?",
        (person_id,)
    ).fetchall()


def get_events(conn, person_id, event_type=None):
    """Get events for a person, optionally filtered by type."""
    if event_type:
        return conn.execute(
            "SELECT tag, type, description, date, place, note FROM events "
            "WHERE person_id = ? AND type LIKE ? COLLATE NOCASE ORDER BY date",
            (person_id, '%' + event_type + '%')
        ).fetchall()
    return conn.execute(
        "SELECT tag, type, description, date, place, note FROM events "
        "WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()


def get_all_photos(conn, person_id):
    """Get all photos for a person (from new schema with photo_tags)."""
    return conn.execute("""
        SELECT p.filename as local_file, p.title, p.date, pt.is_primary
        FROM photos p
        JOIN photo_tags pt ON pt.photo_id = p.id
        WHERE pt.person_id = ?
        ORDER BY pt.is_primary DESC, p.id ASC
    """, (person_id,)).fetchall()


def get_alive_people(conn):
    """Get all people marked as alive."""
    return conn.execute(
        "SELECT id, name, birth_year, birth_place, photo_file FROM people "
        "WHERE is_alive = 1 ORDER BY birth_year DESC"
    ).fetchall()


def get_born_in(conn, place, limit=30):
    """Get people born in a place."""
    return conn.execute(
        "SELECT id, name, birth_year, death_year, photo_file, is_alive FROM people "
        "WHERE birth_place LIKE ? COLLATE NOCASE ORDER BY birth_year LIMIT ?",
        (f"%{place}%", limit)
    ).fetchall()


def count_descendants(conn, person_id, memo=None):
    """Recursively count all descendants of a person."""
    if memo is None:
        memo = set()

    if person_id in memo:
        return 0
    memo.add(person_id)

    count = 1
    children = conn.execute(
        "SELECT child_id FROM children WHERE parent_id = ?",
        (person_id,)
    ).fetchall()

    for child in children:
        count += count_descendants(conn, child[0], memo)

    return count


def get_branch_descendants(conn, person_ids):
    """Count all descendants of a list of founding ancestors."""
    all_descendants = set()

    for person_id in person_ids:
        # Get all descendants from this ancestor
        to_visit = [person_id]
        while to_visit:
            current = to_visit.pop(0)
            all_descendants.add(current)
            children = conn.execute(
                "SELECT child_id FROM children WHERE parent_id = ?",
                (current,)
            ).fetchall()
            for child in children:
                if child[0] not in all_descendants:
                    to_visit.append(child[0])

    return len(all_descendants)


def get_dashboard_data(conn):
    """Return all data needed for the dashboard page in a single call."""
    # Stats
    total_people = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    total_families = conn.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
    alive_count = conn.execute("SELECT COUNT(*) FROM people WHERE is_alive = 1").fetchone()[0]

    # Photo stats
    photos_count = conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]

    # Last updated (from photos table)
    last_updated_str = conn.execute("SELECT MAX(updated_at) FROM photos").fetchone()[0]
    if last_updated_str:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            last_updated = dt.strftime("%b %Y")
        except:
            last_updated = "--"
    else:
        last_updated = "--"

    # Years span
    min_year = conn.execute("SELECT MIN(birth_year) FROM people WHERE birth_year IS NOT NULL").fetchone()[0]
    max_year = conn.execute("SELECT MAX(birth_year) FROM people WHERE birth_year IS NOT NULL").fetchone()[0]
    if min_year and max_year:
        years_span = f"{min_year}–{max_year}"
    else:
        years_span = "--"

    # Family branches with specific lineage counts
    branches_config = [
        {"surname": "Godes", "ancestors": None},  # All with surname Godes
        {"surname": "Godes Diago", "ancestors": ["@I10@", "@I17@"]},  # Emili Godes Hurtado & Antònia Diago Almuzara
        {"surname": "Godes Hospital", "ancestors": ["@I15@", "@I21@"]},  # Ramón Godes Hurtado & Ignacia Hospital Ruaix
        {"surname": "Godes Molina", "ancestors": ["@I11@", "@I18@"]},  # Ernest Godes Hurtado & Dolores Molina Beca
        {"surname": "Godes Schmid", "ancestors": ["@I16@", "@I22@"]},  # Artur Godes Hurtado & Carmen Schmid Tarrida
        {"surname": "Godes Terrats", "ancestors": ["@I7@", "@I9@"]},  # Pau Godes Caballeria & Anna Terrats Bertrán
        {"surname": "Pujol Godes", "ancestors": ["@I12@", "@I19@"]},  # Rosa Godes Hurtado & Joan Pujol Pont
    ]

    branches = []
    for config in branches_config:
        if config["ancestors"] is None:
            # Count all with this surname
            count = conn.execute(
                "SELECT COUNT(*) FROM people WHERE surname = ? COLLATE NOCASE",
                (config["surname"],)
            ).fetchone()[0]
        else:
            # Count all descendants (including spouses and their children)
            count = get_branch_descendants(conn, config["ancestors"])

        if count > 0:
            branches.append({"surname": config["surname"], "count": count})

    # Birthdays this week
    birthdays = get_birthdays_this_week(conn)

    # Family photos (random selection for gallery)
    photo_people = conn.execute("""
        SELECT DISTINCT p.id, p.name, p.birth_year, p.death_year, p.birth_place,
               ph.id as photo_id, ph.filename as local_file, ph.title, ph.date, ph.place
        FROM people p
        JOIN photo_tags pt ON pt.person_id = p.id
        JOIN photos ph ON ph.id = pt.photo_id
        WHERE ph.filename IS NOT NULL
        AND ph.filename NOT LIKE '%.pdf'
        AND ph.is_personal_photo = 0
        AND ph.is_cutout = 0
        ORDER BY RANDOM() LIMIT 8
    """).fetchall()

    # Recently "added" — people with most recent birth years (latest additions to tree)
    featured = conn.execute(
        "SELECT id, name, given_name, surname, birth_year, death_year, photo_file, is_alive, birth_place "
        "FROM people WHERE photo_file IS NOT NULL AND birth_year IS NOT NULL "
        "ORDER BY birth_year DESC LIMIT 4"
    ).fetchall()

    # Documents from archive
    documents = get_documents(conn, limit=1)

    return {
        "stats": {
            "total_people": total_people,
            "total_families": total_families,
            "alive": alive_count,
            "photos_count": photos_count,
            "last_updated": last_updated,
            "years_span": years_span,
        },
        "branches": [{"surname": b["surname"], "count": b["count"]} for b in branches],
        "birthdays": birthdays,
        "photos": [
            {
                "photo_id": p["photo_id"],
                "person_id": p["id"],
                "name": p["name"],
                "photo": p["local_file"],
                "title": p["title"],
                "date": p["date"],
                "place": p["place"],
            }
            for p in photo_people
        ],
        "featured": [dict(p) for p in featured],
        "documents": [dict(d) for d in documents],
    }


def get_person_dossier(conn, person_id):
    """Return complete dossier data for a person."""
    # Main person
    person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not person:
        return None

    person_dict = dict(person)

    # Parents
    father = None
    mother = None
    if person["father_id"]:
        father_row = conn.execute("SELECT * FROM people WHERE id = ?", (person["father_id"],)).fetchone()
        father = dict(father_row) if father_row else None
    if person["mother_id"]:
        mother_row = conn.execute("SELECT * FROM people WHERE id = ?", (person["mother_id"],)).fetchone()
        mother = dict(mother_row) if mother_row else None

    # Siblings (by both parents)
    siblings = []
    sibling_ids = set()
    if person["father_id"]:
        sibs = conn.execute(
            "SELECT * FROM people WHERE father_id = ? AND id != ? ORDER BY birth_year",
            (person["father_id"], person_id)
        ).fetchall()
        for s in sibs:
            sibling_ids.add(s["id"])
            siblings.append(dict(s))
    if person["mother_id"]:
        sibs = conn.execute(
            "SELECT * FROM people WHERE mother_id = ? AND id != ? ORDER BY birth_year",
            (person["mother_id"], person_id)
        ).fetchall()
        for s in sibs:
            if s["id"] not in sibling_ids:
                sibling_ids.add(s["id"])
                siblings.append(dict(s))

    # Sort by birth year
    siblings.sort(key=lambda x: x["birth_year"] or 0)

    # Spouses (all marriages with dates and places - exclude empty marriages)
    spouse = None
    spouses_list = []
    spouse_rows = conn.execute("""
        SELECT person2_id, date, place, divorce_date, divorce_place, divorce_note FROM marriages WHERE person1_id = ?
        UNION ALL
        SELECT person1_id, date, place, divorce_date, divorce_place, divorce_note FROM marriages WHERE person2_id = ?
        ORDER BY date
    """, (person_id, person_id)).fetchall()

    for row in spouse_rows:
        spouse_id = row[0]
        marriage_date = row[1]
        marriage_place = row[2]
        divorce_date = row[3]
        divorce_place = row[4]
        divorce_note = row[5]
        spouse_data = dict(conn.execute("SELECT * FROM people WHERE id = ?", (spouse_id,)).fetchone())
        spouse_data["marriage_date"] = marriage_date
        spouse_data["marriage_place"] = marriage_place
        if divorce_date:
            spouse_data["divorce"] = {
                "date": divorce_date,
                "place": divorce_place,
                "note": divorce_note
            }
        spouses_list.append(spouse_data)
        if not spouse:  # First spouse for backward compatibility
            spouse = spouse_data

    # Partnerships (non-marriage relationships)
    # Deduplicate: only add if not already in spouses_list (from marriages)
    partner_ids_in_list = {s["id"] for s in spouses_list}
    partnership_rows = conn.execute("""
        SELECT person2_id, date FROM partnerships WHERE person1_id = ?
        UNION ALL
        SELECT person1_id, date FROM partnerships WHERE person2_id = ?
        ORDER BY date
    """, (person_id, person_id)).fetchall()

    for row in partnership_rows:
        partner_id = row[0]
        partnership_date = row[1]
        if partner_id not in partner_ids_in_list:  # Skip if already in marriages
            partner_data = dict(conn.execute("SELECT * FROM people WHERE id = ?", (partner_id,)).fetchone())
            partner_data["partnership_date"] = partnership_date
            spouses_list.append(partner_data)

    # Children (with their marriages)
    children = conn.execute(
        "SELECT * FROM people WHERE father_id = ? OR mother_id = ? ORDER BY birth_year",
        (person_id, person_id)
    ).fetchall()
    children_list = []
    for c in children:
        child_dict = dict(c)
        # Get child's marriages (only with dates)
        marriages = conn.execute("""
            SELECT person2_id, date, place FROM marriages WHERE person1_id = ?
            UNION ALL
            SELECT person1_id, date, place FROM marriages WHERE person2_id = ?
            ORDER BY date
        """, (c["id"], c["id"])).fetchall()

        child_marriages = []
        for m in marriages:
            spouse_id = m[0]
            marriage_date = m[1]
            marriage_place = m[2]
            child_spouse_row = conn.execute("SELECT name, photo_file, nickname, given_name, surname FROM people WHERE id = ?", (spouse_id,)).fetchone()
            if child_spouse_row:
                child_marriages.append({
                    "spouse_name": child_spouse_row["name"],
                    "spouse_photo": child_spouse_row["photo_file"],
                    "spouse_nickname": child_spouse_row["nickname"],
                    "spouse_given_name": child_spouse_row["given_name"],
                    "spouse_surname": child_spouse_row["surname"],
                    "marriage_date": marriage_date,
                    "marriage_place": marriage_place
                })

        if child_marriages:
            child_dict["marriages"] = child_marriages

        # Get child's partnerships
        partnerships = conn.execute("""
            SELECT person2_id, date FROM partnerships WHERE person1_id = ?
            UNION ALL
            SELECT person1_id, date FROM partnerships WHERE person2_id = ?
            ORDER BY date
        """, (c["id"], c["id"])).fetchall()

        child_partnerships = []
        for p in partnerships:
            partner_id = p[0]
            partnership_date = p[1]
            partner_row = conn.execute("SELECT name, photo_file, nickname, given_name, surname FROM people WHERE id = ?", (partner_id,)).fetchone()
            if partner_row:
                child_partnerships.append({
                    "partner_name": partner_row["name"],
                    "partner_photo": partner_row["photo_file"],
                    "partner_nickname": partner_row["nickname"],
                    "partner_given_name": partner_row["given_name"],
                    "partner_surname": partner_row["surname"],
                    "partnership_date": partnership_date
                })

        if child_partnerships:
            child_dict["partnerships"] = child_partnerships

        children_list.append(child_dict)

    # Residences
    residences = conn.execute(
        "SELECT address, address2, city, country, date FROM residences WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()
    residences_list = [dict(r) for r in residences]

    # Occupations
    occupations = conn.execute(
        "SELECT title, date, place, 'Ocupación' as event_type FROM occupations WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()
    occupations_list = [dict(o) for o in occupations]

    # Work events (events with type = "Trabajo") — displayed in Trayectoria Profesional
    work_events = conn.execute(
        "SELECT description as title, date, place, 'Trabajo' as event_type FROM events WHERE person_id = ? AND type = 'Trabajo' ORDER BY date",
        (person_id,)
    ).fetchall()
    work_list = [dict(w) for w in work_events]

    # Combine occupations and work events for career section
    career_list = occupations_list + work_list
    career_list.sort(key=lambda x: x.get('date') or '')

    # Military
    military = conn.execute(
        "SELECT description, date, place FROM military WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()
    military_list = [dict(m) for m in military]

    # Anecdotes
    anecdotes = conn.execute(
        "SELECT description, date, place FROM anecdotes WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()
    anecdotes_list = [dict(a) for a in anecdotes]

    # ALL events (Bautismo, Emigración, Educación, Ocupación, Residencia, Censo, etc.)
    events = conn.execute(
        "SELECT tag, type, description, date, place, age, note, cause, address, email, www FROM events WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()
    events_list = [dict(e) for e in events]

    # Burial
    burial = conn.execute(
        "SELECT place_detail, date, place FROM burial WHERE person_id = ? ORDER BY date",
        (person_id,)
    ).fetchall()
    burial_list = [dict(b) for b in burial]

    # Notes
    notes = conn.execute(
        "SELECT content FROM notes WHERE person_id = ?",
        (person_id,)
    ).fetchall()
    notes_list = [n[0] for n in notes]

    # Get nickname from people table (imported from GEDCOM NICK/_AKA fields)
    nickname = person_dict.get('nickname')

    # Documents (fotos con título que contiene tags entre corchetes: [Defunción], [Nacimiento], etc.)
    documents = conn.execute("""
        SELECT ph.id, ph.filename, ph.title, ph.date, ph.place
        FROM photos ph
        JOIN photo_tags pt ON pt.photo_id = ph.id
        WHERE pt.person_id = ? AND ph.title IS NOT NULL AND ph.title LIKE '%[%]%'
        ORDER BY ph.date, ph.id
    """, (person_id,)).fetchall()
    documents_list = []
    for doc in documents:
        doc_dict = dict(doc)
        # Extract tag from title: "Title here [Tag]" -> tag = "Tag", title = "Title here"
        if '[' in doc_dict['title']:
            import re
            match = re.search(r'\[([^\]]+)\]$', doc_dict['title'])
            if match:
                doc_dict['tag'] = match.group(1)
                doc_dict['title_clean'] = doc_dict['title'][:match.start()].strip()
            else:
                doc_dict['tag'] = ''
                doc_dict['title_clean'] = doc_dict['title']
        documents_list.append(doc_dict)

    # Photos (all, no limit, excluding documents) — include id (for sorting), date fields, and position for face detection
    # Position is stored per person in photo_tags, not globally in photos
    photos = conn.execute("""
        SELECT ph.id, ph.filename, ph.title, ph.date, ph.place, pt.position
        FROM photos ph
        JOIN photo_tags pt ON pt.photo_id = ph.id
        WHERE pt.person_id = ? AND ph.filename NOT LIKE '%.pdf' AND (ph.title IS NULL OR ph.title NOT LIKE '%[%]%')
        ORDER BY ph.date DESC
    """, (person_id,)).fetchall()
    photos_list = [dict(p) for p in photos]

    return {
        "person": person_dict,
        "nickname": nickname,
        "father": father,
        "mother": mother,
        "siblings": siblings,
        "spouse": spouse,
        "spouses": spouses_list,
        "children": children_list,
        "residences": residences_list,
        "occupations": occupations_list,
        "career": career_list,
        "military": military_list,
        "anecdotes": anecdotes_list,
        "events": events_list,
        "burial": burial_list,
        "notes": notes_list,
        "documents": documents_list,
        "photos": photos_list,
    }


def get_documents(conn, limit=1):
    """Return documents (PDFs or tagged photos) for the home Arxiu section."""
    return conn.execute("""
        SELECT id, filename, title, date, place
        FROM photos
        WHERE filename LIKE '%.pdf' OR title LIKE '%[%]%'
        ORDER BY RANDOM() LIMIT ?
    """, (limit,)).fetchall()


def get_photo_details(conn, photo_id):
    """Return complete details for a photo including tagged people, notes, and album."""
    photo = conn.execute("""
        SELECT id, filename, title, date, place, album_id
        FROM photos
        WHERE id = ?
    """, (photo_id,)).fetchone()

    if not photo:
        return None

    photo_dict = dict(photo)

    # Tagged people in this photo (with nicknames)
    tagged_people = conn.execute("""
        SELECT pt.person_id, p.name, p.given_name, p.surname, p.nickname, p.photo_file, pt.position
        FROM photo_tags pt
        JOIN people p ON p.id = pt.person_id
        WHERE pt.photo_id = ?
        ORDER BY p.name
    """, (photo_id,)).fetchall()

    photo_dict["tagged_people"] = [dict(tp) for tp in tagged_people]

    # Album title and cover if album_id exists
    if photo_dict.get("album_id"):
        album = conn.execute("""
            SELECT title FROM albums WHERE gedcom_id = ?
        """, (photo_dict["album_id"],)).fetchone()
        photo_dict["album_title"] = album["title"] if album else None

        # Pick an album cover: photo with most tagged people (representative group photo)
        # If tied, prefer earlier photo (by date or ID)
        album_cover = conn.execute("""
            SELECT ph.filename
            FROM photos ph
            LEFT JOIN photo_tags pt ON pt.photo_id = ph.id
            WHERE ph.album_id = ? AND ph.filename NOT LIKE '%.pdf'
            GROUP BY ph.id
            ORDER BY COUNT(pt.person_id) DESC, ph.id ASC
            LIMIT 1
        """, (photo_dict["album_id"],)).fetchone()
        photo_dict["album_cover"] = album_cover["filename"] if album_cover else None
    else:
        photo_dict["album_title"] = None
        photo_dict["album_cover"] = None

    return photo_dict


def update_all_photo_files(conn):
    """
    Regenerate photo_file for all people using the 5-level selection algorithm.

    This should be called after photos table is updated to ensure profile photos are always correct.
    Selection priority (same as migrate_json_to_sqlite.py):
    1. is_primary = 1 (official primary photo)
    2. is_prim_cutout = 1 AND is_personal_photo = 1 (personal primary cutout)
    3. is_prim_cutout = 1 (any primary cutout)
    4. is_cutout = 1 (any cutout)
    5. Any non-PDF photo (fallback)
    """
    people = conn.execute("SELECT id FROM people").fetchall()
    updated = 0

    for person_row in people:
        person_id = person_row["id"]

        # Count all photos for this person
        photo_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM photos ph
            JOIN photo_tags pt ON pt.photo_id = ph.id
            WHERE pt.person_id = ?
        """, (person_id,)).fetchone()["cnt"]

        # Find profile photo using 5-level selection algorithm
        photo_file = None
        if photo_count > 0:
            # Priority 1: is_primary=1
            photo_row = conn.execute("""
                SELECT ph.filename FROM photos ph
                JOIN photo_tags pt ON pt.photo_id = ph.id
                WHERE pt.person_id = ? AND pt.is_primary = 1
                ORDER BY ph.id LIMIT 1
            """, (person_id,)).fetchone()

            # Priority 2: is_prim_cutout=1 AND is_personal_photo=1
            if not photo_row:
                photo_row = conn.execute("""
                    SELECT ph.filename FROM photos ph
                    JOIN photo_tags pt ON pt.photo_id = ph.id
                    WHERE pt.person_id = ? AND ph.is_prim_cutout = 1 AND ph.is_personal_photo = 1
                    ORDER BY ph.id LIMIT 1
                """, (person_id,)).fetchone()

            # Priority 3: is_prim_cutout=1
            if not photo_row:
                photo_row = conn.execute("""
                    SELECT ph.filename FROM photos ph
                    JOIN photo_tags pt ON pt.photo_id = ph.id
                    WHERE pt.person_id = ? AND ph.is_prim_cutout = 1
                    ORDER BY ph.id LIMIT 1
                """, (person_id,)).fetchone()

            # Priority 4: is_cutout=1
            if not photo_row:
                photo_row = conn.execute("""
                    SELECT ph.filename FROM photos ph
                    JOIN photo_tags pt ON pt.photo_id = ph.id
                    WHERE pt.person_id = ? AND ph.is_cutout = 1
                    ORDER BY ph.id LIMIT 1
                """, (person_id,)).fetchone()

            # Priority 5: any non-PDF photo
            if not photo_row:
                photo_row = conn.execute("""
                    SELECT ph.filename FROM photos ph
                    JOIN photo_tags pt ON pt.photo_id = ph.id
                    WHERE pt.person_id = ? AND ph.filename NOT LIKE '%.pdf'
                    ORDER BY ph.id LIMIT 1
                """, (person_id,)).fetchone()

            if photo_row:
                photo_file = photo_row["filename"]

        # Update person's photo info
        if photo_count > 0 or photo_file:
            conn.execute(
                "UPDATE people SET photo_count = ?, photo_file = ? WHERE id = ?",
                (photo_count, photo_file, person_id)
            )
            updated += 1

    conn.commit()
    return updated


def _person_to_node(person):
    """Convert a DB row to a tree node dict."""
    p = dict(person) if not isinstance(person, dict) else person
    return {
        "id": p["id"],
        "name": p["name"],
        "given_name": p.get("given_name"),
        "surname": p.get("surname"),
        "nickname": p.get("nickname"),
        "sex": p.get("sex"),
        "birth_year": p.get("birth_year"),
        "birth_place": p.get("birth_place"),
        "death_year": p.get("death_year"),
        "photo": p.get("photo_file"),
        "is_alive": bool(p.get("is_alive", 0)),
    }
