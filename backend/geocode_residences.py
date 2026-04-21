"""One-time script: geocode residences via Nominatim and store lat/lng in DB."""

import sqlite3
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "godesia.db"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "Godesia Genealogy App (genealogia familiar, uso privado)"}


def nominatim_geocode(query: str):
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"  ERROR: {e}")
    return None


def geocode_residence(address, city, country):  # returns (lat, lng) or (None, None)
    attempts = []
    if address and city:
        attempts.append(f"{address}, {city}, {country or 'España'}")
    if city:
        attempts.append(f"{city}, {country or 'España'}")
    if city:
        attempts.append(f"{city}, España")

    for query in attempts:
        result = nominatim_geocode(query)
        time.sleep(1)
        if result:
            return result
    return None, None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Add columns if they don't exist
    cols = [r[1] for r in conn.execute("PRAGMA table_info(residences)").fetchall()]
    if "lat" not in cols:
        conn.execute("ALTER TABLE residences ADD COLUMN lat REAL")
        print("Added column: lat")
    if "lng" not in cols:
        conn.execute("ALTER TABLE residences ADD COLUMN lng REAL")
        print("Added column: lng")
    conn.commit()

    rows = conn.execute(
        "SELECT id, address, city, country FROM residences WHERE lat IS NULL"
    ).fetchall()

    total = len(rows)
    print(f"Residencias a geocodificar: {total}")

    resolved = 0
    for i, row in enumerate(rows, 1):
        rid, address, city, country = row["id"], row["address"], row["city"], row["country"]
        label = city or address or f"id={rid}"
        lat, lng = geocode_residence(address, city, country)
        if lat:
            conn.execute("UPDATE residences SET lat=?, lng=? WHERE id=?", (lat, lng, rid))
            conn.commit()
            resolved += 1
            print(f"[{i}/{total}] {label} → {lat:.4f}, {lng:.4f}")
        else:
            print(f"[{i}/{total}] {label} → NO ENCONTRADO")

    total_saved = conn.execute("SELECT COUNT(*) FROM residences WHERE lat IS NOT NULL").fetchone()[0]
    print(f"\nFINAL: {resolved} nuevas geocodificadas. Total con coords: {total_saved}/313")
    conn.close()


if __name__ == "__main__":
    main()
