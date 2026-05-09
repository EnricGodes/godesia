"""Seed and geocode birth/death/marriage/burial places via Nominatim."""

import sqlite3
from pathlib import Path

from geocode_utils import geocode_with_cache, normalize_place, build_queries, propagate_geocache


def seed_vital_places(conn: sqlite3.Connection) -> int:
    """Insert vital places into geocache as pending entries (no Nominatim calls).

    Returns number of new pending entries created.
    """
    places = set()

    for row in conn.execute("SELECT birth_place FROM people WHERE birth_place IS NOT NULL AND birth_place != ''"):
        places.add(row[0])
    for row in conn.execute("SELECT death_place FROM people WHERE death_place IS NOT NULL AND death_place != ''"):
        places.add(row[0])
    for row in conn.execute("SELECT place FROM marriages WHERE place IS NOT NULL AND place != ''"):
        places.add(row[0])
    for row in conn.execute("SELECT place FROM burial WHERE place IS NOT NULL AND place != ''"):
        places.add(row[0])

    seeded = 0
    for place in places:
        norm = normalize_place(place)
        queries = build_queries(norm)
        if not queries:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO geocache (query, lat, lng, raw_place) VALUES (?,NULL,NULL,?)",
            (queries[0], place),
        )
        if cur.rowcount:
            seeded += 1

    conn.commit()
    return seeded


def geocode_vital_places(conn: sqlite3.Connection, limit: int = 0) -> int:
    """Geocode all pending geocache entries via Nominatim.

    Args:
        limit: max entries to process (0 = all)
    Returns:
        Number of entries successfully geocoded.
    """
    rows = conn.execute(
        "SELECT query, raw_place FROM geocache WHERE lat IS NULL ORDER BY query"
    ).fetchall()
    if limit:
        rows = rows[:limit]

    resolved = 0
    for i, (query, raw_place) in enumerate(rows):
        raw = raw_place or query
        lat, lng = geocode_with_cache(conn, raw, cache_only=False)
        if lat is not None:
            resolved += 1
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(rows)} processats, {resolved} geocodificats...")
        conn.commit()

    return resolved


def main():
    base = Path(__file__).parent.parent
    db_path = base / "data" / "godesia.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print("Sembrant llocs vitals al geocache...")
    seeded = seed_vital_places(conn)
    print(f"  {seeded} nous llocs pendents afegits")

    pending = conn.execute("SELECT COUNT(*) FROM geocache WHERE lat IS NULL").fetchone()[0]
    print(f"  Total pendents: {pending}")

    if pending == 0:
        print("No hi ha res a geocodificar.")
        conn.close()
        return

    print(f"\nGeocodificant {pending} llocs via Nominatim (~{pending*1.1:.0f}s)...")
    resolved = geocode_vital_places(conn)
    print(f"\nGeocodificats: {resolved}/{pending}")

    print("Propagant coordenades a residences/events...")
    updated = propagate_geocache(conn)
    print(f"  {updated} files actualitzades")

    conn.close()


if __name__ == "__main__":
    main()
