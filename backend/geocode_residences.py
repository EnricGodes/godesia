"""Geocode residences via Nominatim with geocache support.

Run this after the initial import to fill lat/lng for all residences.
On subsequent runs it only processes new/unresolved entries.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database import get_connection
from geocode_utils import (
    build_residence_raw, build_queries, geocode_with_cache, normalize_place
)

DB_PATH = Path(__file__).parent.parent / "data" / "godesia.db"


def backfill_geocache(conn):
    """Seed geocache from existing residences that already have lat/lng."""
    rows = conn.execute(
        "SELECT address, city, country, lat, lng FROM residences WHERE lat IS NOT NULL"
    ).fetchall()
    inserted = 0
    for row in rows:
        raw = build_residence_raw(row[0] or "", row[1] or "", row[2] or "")
        if not raw:
            continue
        normalized = normalize_place(raw)
        queries = build_queries(normalized)
        if not queries:
            continue
        # Only seed the most specific query; don't overwrite existing entries
        q = queries[0]
        existing = conn.execute(
            "SELECT 1 FROM geocache WHERE query=?", (q,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO geocache (query, lat, lng, raw_place) VALUES (?,?,?,?)",
                (q, row[3], row[4], raw),
            )
            inserted += 1
    conn.commit()
    print(f"Backfill geocache: {inserted} entradas nuevas desde residencias existentes")


def seed_birth_places(conn):
    """Insert birth_place values from people into geocache as pending only when
    no resolved geocache entry exists for that place.

    Matching strategy (in order):
    1. Exact match on any query variant from build_queries(normalized)
    2. Fallback: geocache CONTAINS the first comma-part of the raw address
       (catches 'Fonollar, Barcelona, España' when birth_place is 'Fonollar, 30 4° Barcelona')
    """
    birth_places = [row[0] for row in conn.execute(
        "SELECT DISTINCT birth_place FROM people WHERE birth_place IS NOT NULL AND birth_place != ''"
    ).fetchall()]

    # Wipe all existing pending birth-place entries so we start clean
    cleaned = 0
    for raw in birth_places:
        normalized = normalize_place(raw)
        if not normalized:
            continue
        for q in build_queries(normalized):
            cleaned += conn.execute(
                "DELETE FROM geocache WHERE query=? AND lat IS NULL", (q,)
            ).rowcount
    if cleaned:
        conn.commit()
        print(f"Nacimientos: {cleaned} entradas pendientes antiguas eliminadas")

    inserted = 0
    for raw in birth_places:
        normalized = normalize_place(raw)
        if not normalized:
            continue
        queries = build_queries(normalized)
        if not queries:
            continue

        # 1. Exact query match against resolved entries
        resolved = any(
            conn.execute(
                "SELECT 1 FROM geocache WHERE query=? AND lat IS NOT NULL", (q,)
            ).fetchone()
            for q in queries
        )

        # 2. Fallback: check if geocache has an entry whose key CONTAINS the
        #    first comma-part of the raw address (street or city name).
        #    This handles 'Fonollar, Barcelona, España' vs 'Fonollar, 30 4° Barcelona'.
        if not resolved:
            first_part = raw.split(",")[0].strip()
            if len(first_part) >= 4:
                resolved = bool(conn.execute(
                    "SELECT 1 FROM geocache WHERE query LIKE ? AND lat IS NOT NULL",
                    (f"%{first_part}%",)
                ).fetchone())

        if not resolved:
            conn.execute(
                "INSERT OR IGNORE INTO geocache (query, lat, lng, raw_place) "
                "VALUES (?, NULL, NULL, ?)",
                (queries[0], raw),
            )
            inserted += 1

    conn.commit()
    print(f"Nacimientos: {inserted} nuevas entradas pendientes en geocache")


def main():
    conn = get_connection(str(DB_PATH))

    print("Poblando geocache desde datos existentes...")
    backfill_geocache(conn)
    seed_birth_places(conn)

    rows = conn.execute(
        "SELECT id, address, city, country FROM residences WHERE lat IS NULL"
    ).fetchall()
    total = len(rows)
    print(f"\nResidencias a geocodificar: {total}")

    resolved = 0
    for i, row in enumerate(rows, 1):
        raw = build_residence_raw(row[1] or "", row[2] or "", row[3] or "")
        label = raw or f"id={row[0]}"
        lat, lng = geocode_with_cache(conn, raw, cache_only=False)
        if lat is not None:
            conn.execute(
                "UPDATE residences SET lat=?,lng=? WHERE id=?", (lat, lng, row[0])
            )
            conn.commit()
            resolved += 1
            print(f"[{i}/{total}] {label} -> {lat:.4f}, {lng:.4f}")
        else:
            print(f"[{i}/{total}] {label} -> NO ENCONTRADO (pendiente en geocache)")

    total_done = conn.execute(
        "SELECT COUNT(*) FROM residences WHERE lat IS NOT NULL"
    ).fetchone()[0]
    total_all = conn.execute("SELECT COUNT(*) FROM residences").fetchone()[0]
    print(f"\nFINAL: {resolved} nuevas. Total con coords: {total_done}/{total_all}")
    conn.close()


if __name__ == "__main__":
    main()
