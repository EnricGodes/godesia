"""Migración: family_tree.json → SQLite (data/godesia.db)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database import get_connection, init_db, parse_gedcom_date


def migrate(json_path, db_path):
    print(f"Leyendo {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"  {data['total_people']} personas, {data['total_families']} familias")

    # Drop and recreate
    conn = get_connection(db_path)
    for table in ["notes", "photos", "residences", "occupations", "children", "marriages", "people"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    init_db(conn)

    print("Insertando personas...")
    for person in data["people"]:
        # Parse birth date
        birth_date = person.get("birth", {}).get("date", "")
        b_day, b_month, b_year = parse_gedcom_date(birth_date)

        # Parse death date
        death = person.get("death", {})
        death_date = death.get("date", "")
        _, _, d_year = parse_gedcom_date(death_date)

        # Determine if alive: has birth, no death, born after 1900
        is_alive = 0
        if b_year and b_year > 1900 and not death_date:
            is_alive = 1

        # Primary photo
        photos = person.get("photos", [])
        primary_photo = None
        for p in photos:
            if p.get("primary") and p.get("local_file"):
                primary_photo = p["local_file"]
                break
        if not primary_photo:
            for p in photos:
                if p.get("local_file"):
                    primary_photo = p["local_file"]
                    break

        conn.execute(
            "INSERT INTO people (id, name, given_name, surname, sex, "
            "birth_date, birth_day, birth_month, birth_year, birth_place, "
            "death_date, death_year, death_place, death_cause, death_note, death_age, "
            "is_alive, father_id, mother_id, father_name, mother_name, "
            "photo_file, photo_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                person["id"], person.get("name", ""), person.get("given_name", ""),
                person.get("surname", ""), person.get("sex", ""),
                birth_date, b_day, b_month, b_year,
                person.get("birth", {}).get("place", ""),
                death_date, d_year, death.get("place", ""),
                death.get("cause", ""), death.get("note", ""), death.get("age", ""),
                is_alive,
                person.get("father_id", ""), person.get("mother_id", ""),
                person.get("father", ""), person.get("mother", ""),
                primary_photo, len(photos),
            )
        )

        # Children
        for child in person.get("children", []):
            conn.execute(
                "INSERT OR IGNORE INTO children (parent_id, child_id) VALUES (?,?)",
                (person["id"], child["id"])
            )

        # Marriages
        for spouse in person.get("spouses", []):
            # Only insert if person1_id < person2_id to avoid duplicates
            p1, p2 = sorted([person["id"], spouse["id"]])
            existing = conn.execute(
                "SELECT id FROM marriages WHERE person1_id = ? AND person2_id = ?",
                (p1, p2)
            ).fetchone()
            if not existing:
                marriage = spouse.get("marriage", {})
                conn.execute(
                    "INSERT INTO marriages (person1_id, person2_id, date, place) VALUES (?,?,?,?)",
                    (p1, p2, marriage.get("date", ""), marriage.get("place", ""))
                )

        # Occupations
        for occ in person.get("occupations", []):
            conn.execute(
                "INSERT INTO occupations (person_id, title, date, place) VALUES (?,?,?,?)",
                (person["id"], occ.get("title", ""), occ.get("date", ""), occ.get("place", ""))
            )

        # Residences
        for res in person.get("residences", []):
            conn.execute(
                "INSERT INTO residences (person_id, address, address2, city, country, date) "
                "VALUES (?,?,?,?,?,?)",
                (person["id"], res.get("address", ""), res.get("address2", ""),
                 res.get("city", ""), res.get("country", ""), res.get("date", ""))
            )

        # Photos: Ahora gestionadas por scripts/sync_photo_catalog.py
        # No insertar fotos aquí — el script de sync crea el esquema correcto
        # con metadatos completos, relaciones padre-hijo, y etiquetado múltiple

        # Notes
        for note in person.get("notes", []):
            conn.execute(
                "INSERT INTO notes (person_id, content) VALUES (?,?)",
                (person["id"], note)
            )

    conn.commit()

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    alive = conn.execute("SELECT COUNT(*) FROM people WHERE is_alive = 1").fetchone()[0]
    with_bday = conn.execute(
        "SELECT COUNT(*) FROM people WHERE birth_month IS NOT NULL AND birth_day IS NOT NULL"
    ).fetchone()[0]
    marriages = conn.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
    children_count = conn.execute("SELECT COUNT(*) FROM children").fetchone()[0]

    print(f"\nMigración completada:")
    print(f"  Personas: {count}")
    print(f"  Vivas (estimado): {alive}")
    print(f"  Con fecha exacta de nacimiento: {with_bday}")
    print(f"  Matrimonios: {marriages}")
    print(f"  Relaciones padre-hijo: {children_count}")
    print(f"  BD guardada en: {db_path}")

    conn.close()


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    json_path = base / "data" / "family_tree.json"
    db_path = base / "data" / "godesia.db"
    migrate(str(json_path), str(db_path))
