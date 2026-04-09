"""Migración: family_tree.json → SQLite (data/godesia.db)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database import get_connection, init_db, parse_gedcom_date, convert_date_to_spanish, update_all_photo_files


def migrate(json_path, db_path):
    print(f"Leyendo {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"  {data['total_people']} personas, {data['total_families']} familias")

    # Drop and recreate
    conn = get_connection(db_path)
    # Don't drop photos, photo_tags, albums - they're managed by sync_catalog.py
    for table in ["notes", "residences", "occupations", "military", "anecdotes", "events", "children", "marriages", "partnerships", "people", "burial"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    init_db(conn)

    print("Insertando personas...")
    for person in data["people"]:
        # Parse birth date
        birth_date_raw = person.get("birth", {}).get("date", "")
        birth_date = convert_date_to_spanish(birth_date_raw)
        b_day, b_month, b_year = parse_gedcom_date(birth_date_raw)

        # Parse death date
        death = person.get("death", {})
        death_date_raw = death.get("date", "")
        death_date = convert_date_to_spanish(death_date_raw)
        _, _, d_year = parse_gedcom_date(death_date_raw)

        # Determine if alive: has birth, no death, born after 1900
        is_alive = 0
        if b_year and b_year > 1900 and not death_date_raw:
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

        # Parse baptism data
        baptism = person.get("baptism", {})
        baptism_date_raw = baptism.get("date", "")
        baptism_date = convert_date_to_spanish(baptism_date_raw)
        baptism_place = baptism.get("place", "")
        godparents = baptism.get("godparents", "")

        conn.execute(
            "INSERT INTO people (id, name, given_name, surname, sex, "
            "birth_date, birth_day, birth_month, birth_year, birth_place, birth_note, "
            "death_date, death_year, death_place, death_cause, death_note, death_age, "
            "is_alive, father_id, mother_id, father_name, mother_name, "
            "photo_file, photo_count, baptism_date, baptism_place, godparents) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                person["id"], person.get("name", ""), person.get("given_name", ""),
                person.get("surname", ""), person.get("sex", ""),
                birth_date, b_day, b_month, b_year,
                person.get("birth", {}).get("place", ""),
                person.get("birth", {}).get("note", ""),
                death_date, d_year, death.get("place", ""),
                death.get("cause", ""), death.get("note", ""), death.get("age", ""),
                is_alive,
                person.get("father_id", ""), person.get("mother_id", ""),
                person.get("father", ""), person.get("mother", ""),
                primary_photo, len(photos),
                baptism_date, baptism_place, godparents,
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
                divorce = spouse.get("divorce", {})
                marriage_date = convert_date_to_spanish(marriage.get("date", ""))
                divorce_date = convert_date_to_spanish(divorce.get("date", "")) if divorce else ""
                conn.execute(
                    "INSERT INTO marriages (person1_id, person2_id, date, place, divorce_date, divorce_place, divorce_note) VALUES (?,?,?,?,?,?,?)",
                    (p1, p2, marriage_date, marriage.get("place", ""), divorce_date, divorce.get("place", ""), divorce.get("note", ""))
                )

            # Partnerships (non-marriage relationships)
            partnership = spouse.get("partnership", {})
            if partnership:
                p1, p2 = sorted([person["id"], spouse["id"]])
                existing = conn.execute(
                    "SELECT id FROM partnerships WHERE person1_id = ? AND person2_id = ?",
                    (p1, p2)
                ).fetchone()
                if not existing:
                    partnership_date = convert_date_to_spanish(partnership.get("date", ""))
                    conn.execute(
                        "INSERT INTO partnerships (person1_id, person2_id, date) VALUES (?,?,?)",
                        (p1, p2, partnership_date)
                    )

        # Occupations
        for occ in person.get("occupations", []):
            occ_date = convert_date_to_spanish(occ.get("date", ""))
            conn.execute(
                "INSERT INTO occupations (person_id, title, date, place) VALUES (?,?,?,?)",
                (person["id"], occ.get("title", ""), occ_date, occ.get("place", ""))
            )

        # Military
        for mil in person.get("military", []):
            mil_date = convert_date_to_spanish(mil.get("date", ""))
            conn.execute(
                "INSERT INTO military (person_id, description, date, place) VALUES (?,?,?,?)",
                (person["id"], mil.get("description", ""), mil_date, mil.get("place", ""))
            )

        # Anecdotes
        for anec in person.get("anecdotes", []):
            anec_date = convert_date_to_spanish(anec.get("date", ""))
            conn.execute(
                "INSERT INTO anecdotes (person_id, description, date, place) VALUES (?,?,?,?)",
                (person["id"], anec.get("description", ""), anec_date, anec.get("place", ""))
            )

        # ALL events (Bautismo, Emigración, Educación, Ocupación, Residencia, Censo, etc.)
        for evt in person.get("events", []):
            evt_date = convert_date_to_spanish(evt.get("date", ""))
            conn.execute(
                "INSERT INTO events (person_id, tag, type, description, date, place, age, note, cause, address, email, www) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    person["id"],
                    evt.get("tag", ""),
                    evt.get("type", ""),
                    evt.get("description", ""),
                    evt_date,
                    evt.get("place", ""),
                    evt.get("age", ""),
                    evt.get("note", ""),
                    evt.get("cause", ""),
                    evt.get("address", ""),
                    evt.get("email", ""),
                    evt.get("www", "")
                )
            )

        # Residences
        for res in person.get("residences", []):
            res_date = convert_date_to_spanish(res.get("date", ""))
            conn.execute(
                "INSERT INTO residences (person_id, address, address2, city, country, date) "
                "VALUES (?,?,?,?,?,?)",
                (person["id"], res.get("address", ""), res.get("address2", ""),
                 res.get("city", ""), res.get("country", ""), res_date)
            )

        # Burial
        for buri in person.get("burial", []):
            buri_date = convert_date_to_spanish(buri.get("date", ""))
            conn.execute(
                "INSERT INTO burial (person_id, place_detail, date, place) VALUES (?,?,?,?)",
                (person["id"], buri.get("place_detail", ""), buri_date, buri.get("place", ""))
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

    # Update photo_count and photo_file using the centralized selection algorithm
    try:
        updated_photos = update_all_photo_files(conn)
        if updated_photos > 0:
            print(f"\nActualizadas fotos para {updated_photos} personas")
    except Exception as e:
        # photos table might not exist if it hasn't been populated yet
        print(f"  (Saltando actualización de fotos: {e})")

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
