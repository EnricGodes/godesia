#!/usr/bin/env python3
"""
Limpieza puntual: elimina la persona fantasma de MyHeritage "Unassociated photos"
(@I88888888@) y sus fotos huérfanas.

MyHeritage exporta un INDI de sistema que agrupa todas las fotos no vinculadas a ninguna
persona real. Este script:

  1. Identifica las fotos huérfanas PURAS (solo etiquetadas a la persona fantasma).
  2. Borra esas fotos de la BD y sus archivos .jpg del disco.
  3. Quita el tag falso del resto de fotos (las que también están en personas reales,
     que se conservan).
  4. Borra la persona fantasma.
  5. Recalcula photo_file / photo_count.

Es idempotente: si ya está limpio, no hace nada y reporta 0.

Uso:
    python3 scripts/remove_unassociated_photos.py
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from database import update_all_photo_files  # noqa: E402

DB_PATH = ROOT / "data" / "godesia.db"
PHOTOS_DIR = ROOT / "data" / "photos"

FAKE_PERSON_ID = "@I88888888@"


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    cur = conn.cursor()

    people_before = cur.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    photos_before = cur.execute("SELECT COUNT(*) FROM photos").fetchone()[0]

    # 1. Fotos huérfanas puras: su único tag apunta a la persona fantasma.
    orphans = cur.execute(
        """
        SELECT ph.id, ph.filename
        FROM photos ph
        WHERE EXISTS (
                SELECT 1 FROM photo_tags pt
                WHERE pt.photo_id = ph.id AND pt.person_id = ?
            )
          AND NOT EXISTS (
                SELECT 1 FROM photo_tags pt2
                WHERE pt2.photo_id = ph.id AND pt2.person_id <> ?
            )
        """,
        (FAKE_PERSON_ID, FAKE_PERSON_ID),
    ).fetchall()

    orphan_ids = [r["id"] for r in orphans]
    orphan_files = [r["filename"] for r in orphans if r["filename"]]
    print(f"Fotos huérfanas a borrar: {len(orphan_ids)}")

    # 2. Borrar archivos .jpg del disco.
    files_deleted = 0
    for fname in orphan_files:
        fpath = PHOTOS_DIR / fname
        try:
            if fpath.exists():
                fpath.unlink()
                files_deleted += 1
        except OSError as e:
            print(f"  ! No se pudo borrar {fpath}: {e}")
    print(f"Archivos borrados del disco: {files_deleted}")

    # 3. Borrar filas en la BD para esas fotos huérfanas (tablas auxiliares + photos).
    if orphan_ids:
        ph_marks = ",".join("?" * len(orphan_ids))
        fn_marks = ",".join("?" * len(orphan_files)) if orphan_files else None

        cur.execute(f"DELETE FROM photo_tags WHERE photo_id IN ({ph_marks})", orphan_ids)
        cur.execute(
            f"DELETE FROM photo_dedup_keep_pairs "
            f"WHERE photo_id_a IN ({ph_marks}) OR photo_id_b IN ({ph_marks})",
            orphan_ids + orphan_ids,
        )
        cur.execute(
            f"DELETE FROM dedup_candidates "
            f"WHERE kept_photo_id IN ({ph_marks}) OR drop_photo_id IN ({ph_marks})",
            orphan_ids + orphan_ids,
        )
        cur.execute(
            f"DELETE FROM palazuelos_imports WHERE godes_photo_id IN ({ph_marks})",
            orphan_ids,
        )
        if fn_marks:
            cur.execute(
                f"DELETE FROM photo_classifications WHERE filename IN ({fn_marks})",
                orphan_files,
            )
            cur.execute(
                f"DELETE FROM photo_dedup_blocklist WHERE filename IN ({fn_marks})",
                orphan_files,
            )
        cur.execute(f"DELETE FROM photos WHERE id IN ({ph_marks})", orphan_ids)

    # 4. Quitar el tag falso de las fotos compartidas (se conservan por sus otros tags)
    #    y borrar la persona fantasma.
    removed_tags = cur.execute(
        "DELETE FROM photo_tags WHERE person_id = ?", (FAKE_PERSON_ID,)
    ).rowcount
    removed_person = cur.execute(
        "DELETE FROM people WHERE id = ?", (FAKE_PERSON_ID,)
    ).rowcount
    print(f"Tags falsos restantes eliminados: {removed_tags}")
    print(f"Persona fantasma eliminada: {removed_person}")

    conn.commit()

    # 5. Recalcular fotos de perfil / contadores.
    update_all_photo_files(conn)
    conn.commit()

    people_after = cur.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    photos_after = cur.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    conn.close()

    print("\nResumen:")
    print(f"  Personas: {people_before} → {people_after}")
    print(f"  Fotos:    {photos_before} → {photos_after}")


if __name__ == "__main__":
    main()
