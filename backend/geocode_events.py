"""Geocode event places (Mudanza, Emigración, Censo, RESI…) with geocache support."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database import get_connection
from geocode_utils import geocode_with_cache, GEOCODEABLE_TAGS, GEOCODEABLE_TYPES

DB_PATH = Path(__file__).parent.parent / "data" / "godesia.db"

TAGS_SQL = ",".join(f"'{t}'" for t in GEOCODEABLE_TAGS)
TYPES_SQL = ",".join(f"'{t}'" for t in GEOCODEABLE_TYPES)


def main():
    conn = get_connection(str(DB_PATH))

    rows = conn.execute(f"""
        SELECT id, person_id, tag, type, place
        FROM events
        WHERE (tag IN ({TAGS_SQL}) OR type IN ({TYPES_SQL}))
          AND place IS NOT NULL AND place != ''
          AND lat IS NULL
        ORDER BY id
    """).fetchall()

    total = len(rows)
    print(f"Eventos a geocodificar: {total}\n")

    resolved = 0
    for i, row in enumerate(rows, 1):
        lat, lng = geocode_with_cache(conn, row[4], cache_only=False)
        if lat is not None:
            conn.execute(
                "UPDATE events SET lat=?,lng=? WHERE id=?", (lat, lng, row[0])
            )
            conn.commit()
            resolved += 1
            print(f"[{i}/{total}] {row[1]} {row[2]}/{row[3]}: {row[4]!r} -> {lat:.4f}, {lng:.4f}")
        else:
            print(f"[{i}/{total}] {row[1]} {row[2]}/{row[3]}: {row[4]!r} -> NO ENCONTRADO")

    total_done = conn.execute(f"""
        SELECT COUNT(*) FROM events
        WHERE (tag IN ({TAGS_SQL}) OR type IN ({TYPES_SQL})) AND lat IS NOT NULL
    """).fetchone()[0]
    print(f"\nFINAL: {resolved} nuevas. Total con coords: {total_done}")
    conn.close()


if __name__ == "__main__":
    main()
