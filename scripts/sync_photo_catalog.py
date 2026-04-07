#!/usr/bin/env python3
"""
sync_photo_catalog.py — Sincroniza fotos del GEDCOM a SQLite con metadatos completos.

Uso:
  python3 sync_photo_catalog.py
  python3 sync_photo_catalog.py --dry-run
  python3 sync_photo_catalog.py --skip-download

El script:
1. Parsea GEDCOM directamente
2. Resuelve relaciones padre-hijo entre fotos
3. Renombra archivos hash → GEDCOM names
4. Descarga fotos nuevas
5. Reemplaza tabla `photos` con nuevo esquema
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


class PhotoRecord:
    """Representa una foto única (por filename)."""
    def __init__(self, filename, url):
        self.filename = filename
        self.url = url
        self.filesize = None
        self.title = None
        self.date = None
        self.place = None
        self.photo_rin = None
        self.album_id = None
        self.is_cutout = False
        self.is_parent_photo = False
        self.is_personal_photo = False
        self.is_prim_cutout = False
        self.position = None
        self.parent_photo_id = None  # Will be set after resolving relationships
        self.tagged_people = {}  # person_id -> {is_primary, is_prim_cutout, source}

    def add_tag(self, person_id, is_primary=False, is_prim_cutout=False, position=None, source="direct"):
        if person_id not in self.tagged_people:
            self.tagged_people[person_id] = {
                "is_primary": is_primary,
                "is_prim_cutout": is_prim_cutout,
                "position": position,
                "source": source
            }

    def to_dict(self):
        return {
            "filename": self.filename,
            "url": self.url,
            "filesize": self.filesize,
            "title": self.title,
            "date": self.date,
            "place": self.place,
            "photo_rin": self.photo_rin,
            "album_id": self.album_id,
            "is_cutout": self.is_cutout,
            "is_parent_photo": self.is_parent_photo,
            "is_personal_photo": self.is_personal_photo,
            "position": self.position,
            "tagged_people": self.tagged_people
        }


def parse_gedcom_albums(lines):
    """Parsea ALBUM records del GEDCOM."""
    albums = {}
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1
        match = re.match(r"^0\s+(@A\w+@)\s+ALBUM\s*(.*)$", line)
        if match:
            album_id = match.group(1)
            title = None
            while i < len(lines):
                next_line = lines[i].rstrip("\n")
                if next_line and next_line[0] not in "123456789":
                    break
                match2 = re.match(r"^1\s+TITL\s+(.*)$", next_line)
                if match2:
                    title = match2.group(1)
                    i += 1
                    break
                i += 1
            albums[album_id] = {"title": title}
    return albums


def parse_gedcom_photos(lines):
    """Parsea INDI → OBJE records. Retorna (dict de fotos, dict de INDI → OBJE blocks)."""
    photos = {}  # filename -> PhotoRecord
    indi_photos = defaultdict(list)  # indi_id -> [OBJEs in order]

    i = 0
    current_indi = None
    indi_obje_blocks = defaultdict(list)

    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1

        # Detectar INDI
        match = re.match(r"^0\s+(@I\w+@)\s+INDI", line)
        if match:
            current_indi = match.group(1)
            continue

        # Detectar OBJE bajo INDI
        if current_indi:
            match = re.match(r"^1\s+OBJE\s*$", line)
            if match:
                obje = {
                    "url": None,
                    "filename": None,
                    "format": None,
                    "filesize": None,
                    "title": None,
                    "date": None,
                    "place": None,
                    "photo_rin": None,
                    "album_id": None,
                    "is_cutout": False,
                    "is_parent_photo": False,
                    "is_personal_photo": False,
                    "is_prim": False,
                    "is_prim_cutout": False,
                    "position": None
                }

                # Parsear level 2 tags del OBJE
                while i < len(lines):
                    next_line = lines[i].rstrip("\n")
                    if not next_line or next_line[0] != "2":
                        break
                    match2 = re.match(r"^2\s+(\w+)\s+(.*)$", next_line)
                    if match2:
                        tag, value = match2.group(1), match2.group(2)
                        if tag == "FILE" and value.startswith("http"):
                            obje["url"] = value
                            obje["filename"] = value.split("/")[-1]
                        elif tag == "FORM":
                            obje["format"] = value
                        elif tag == "TITL":
                            obje["title"] = value
                        elif tag == "_DATE":
                            obje["date"] = value
                        elif tag == "_PLACE":
                            obje["place"] = value
                        elif tag == "_FILESIZE":
                            try:
                                obje["filesize"] = int(value)
                            except:
                                pass
                        elif tag == "_PHOTO_RIN":
                            obje["photo_rin"] = value
                        elif tag == "_ALBUM":
                            obje["album_id"] = value
                        elif tag == "_CUTOUT" and value == "Y":
                            obje["is_cutout"] = True
                        elif tag == "_PARENTPHOTO" and value == "Y":
                            obje["is_parent_photo"] = True
                        elif tag == "_PERSONALPHOTO" and value == "Y":
                            obje["is_personal_photo"] = True
                        elif tag == "_PRIM" and value == "Y":
                            obje["is_prim"] = True
                        elif tag == "_PRIM_CUTOUT" and value == "Y":
                            obje["is_prim_cutout"] = True
                        elif tag == "_POSITION":
                            obje["position"] = value
                    i += 1

                if obje["filename"]:
                    indi_obje_blocks[current_indi].append(obje)

    # Construir registro de fotos deduplicado
    for indi_id, obje_list in indi_obje_blocks.items():
        for obje in obje_list:
            fname = obje["filename"]
            if fname not in photos:
                photos[fname] = PhotoRecord(fname, obje["url"])

            photo = photos[fname]
            # Tomar metadata del primer occurrence
            if not photo.title and obje["title"]:
                photo.title = obje["title"]
            if not photo.date and obje["date"]:
                photo.date = obje["date"]
            if not photo.place and obje["place"]:
                photo.place = obje["place"]
            if not photo.photo_rin and obje["photo_rin"]:
                photo.photo_rin = obje["photo_rin"]
            if not photo.album_id and obje["album_id"]:
                photo.album_id = obje["album_id"]
            if not photo.filesize and obje["filesize"]:
                photo.filesize = obje["filesize"]
            if not photo.position and obje["position"]:
                photo.position = obje["position"]

            photo.is_cutout = photo.is_cutout or obje["is_cutout"]
            photo.is_parent_photo = photo.is_parent_photo or obje["is_parent_photo"]
            photo.is_personal_photo = photo.is_personal_photo or obje["is_personal_photo"]
            photo.is_prim_cutout = photo.is_prim_cutout or obje["is_prim_cutout"]

            # Añadir tag
            photo.add_tag(indi_id, is_primary=obje["is_prim"], is_prim_cutout=obje["is_prim_cutout"], position=obje["position"], source="direct")

    return photos, indi_obje_blocks


def resolve_parent_child(photos, indi_obje_blocks):
    """Resuelve relaciones padre-hijo dentro de cada INDI."""
    for indi_id, obje_list in indi_obje_blocks.items():
        # Encontrar parent photo en este INDI
        parent_filename = None
        for obje in obje_list:
            if obje["is_parent_photo"] and not obje["is_cutout"]:
                parent_filename = obje["filename"]
                break

        if parent_filename:
            parent_photo = photos.get(parent_filename)
            # Asignar cutouts como hijos
            for obje in obje_list:
                if obje["is_cutout"] and obje["filename"] != parent_filename:
                    child_photo = photos.get(obje["filename"])
                    if child_photo:
                        child_photo.parent_photo_id = parent_filename


def propagate_tags(photos):
    """Propaga tags y metadata entre padres e hijos."""
    # Crear índice filename → photo para acceso rápido
    fname_to_photo = {p.filename: p for p in photos.values()}

    # Padres heredan tagged_people de hijos
    for photo in photos.values():
        if photo.is_parent_photo:
            # Encontrar todos los cutouts que apunten a esta foto
            children = [p for p in photos.values() if p.parent_photo_id == photo.filename]
            for child in children:
                # Heredar tags de hijo
                for person_id, tag_info in child.tagged_people.items():
                    if person_id not in photo.tagged_people:
                        photo.add_tag(person_id, source="child_cutout_propagation")

        # Hijos heredan metadata de padres
        if photo.parent_photo_id:
            parent = fname_to_photo.get(photo.parent_photo_id)
            if parent:
                if not photo.title and parent.title:
                    photo.title = parent.title
                if not photo.date and parent.date:
                    photo.date = parent.date
                if not photo.place and parent.place:
                    photo.place = parent.place
                if not photo.album_id and parent.album_id:
                    photo.album_id = parent.album_id


def download_photo(url, photos_dir, gedcom_filename):
    """Descarga una foto. Retorna (filename, success)."""
    filepath = photos_dir / gedcom_filename
    if filepath.exists():
        return gedcom_filename, True

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            if len(data) < 100:
                return gedcom_filename, False
            with open(filepath, "wb") as f:
                f.write(data)
        return gedcom_filename, True
    except Exception as e:
        print(f"    Error: {e}")
        return gedcom_filename, False


def check_and_rename_existing(photos, photos_dir, db_conn):
    """Detecta fotos existentes por hash, renombra a GEDCOM name."""
    renamed_count = 0
    for filename, photo in photos.items():
        # Calcular hash del URL
        url_hash = hashlib.md5(photo.url.encode()).hexdigest()[:12]
        hash_filename = f"{url_hash}.jpg"
        hash_path = photos_dir / hash_filename
        gedcom_path = photos_dir / filename

        if not gedcom_path.exists() and hash_path.exists():
            try:
                shutil.move(str(hash_path), str(gedcom_path))
                renamed_count += 1
                print(f"  Renombrado: {hash_filename} → {filename}")
            except Exception as e:
                print(f"  Error renombrando {hash_filename}: {e}")

    return renamed_count


def main():
    parser = argparse.ArgumentParser(description="Sincroniza catálogo de fotos del GEDCOM")
    parser.add_argument("--dry-run", action="store_true", help="Parse pero no escribir en DB")
    parser.add_argument("--skip-download", action="store_true", help="No descargar fotos, solo DB")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    # Use the most recent GEDCOM file (excluding site380341641-tree5-20260324_signed.ged which is outdated)
    docs_dir = base / "docs"
    ged_files = [f for f in sorted(docs_dir.glob("*.ged"), key=lambda x: x.stat().st_mtime, reverse=True)
                 if not f.name.startswith("site380341641-tree5-20260324")]
    if not ged_files:
        print("ERROR: No GEDCOM file found (site380341641-tree5-20260324_signed.ged is too old, use a recent export)")
        sys.exit(1)
    gedcom_path = ged_files[0]
    db_path = base / "data" / "godesia.db"
    photos_dir = base / "data" / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== Sincronización de Catálogo de Fotos ===\n")

    # Fase 1: Parsear GEDCOM
    print("Fase 1: Parseando GEDCOM...")
    with open(gedcom_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    albums = parse_gedcom_albums(lines)
    photos, indi_obje_blocks = parse_gedcom_photos(lines)
    print(f"  Fotos únicas: {len(photos)}")
    print(f"  Álbumes: {len(albums)}")

    # Fase 2: Resolver padre-hijo
    print("\nFase 2: Resolviendo relaciones padre-hijo...")
    resolve_parent_child(photos, indi_obje_blocks)
    cutout_count = sum(1 for p in photos.values() if p.is_cutout)
    parent_count = sum(1 for p in photos.values() if p.is_parent_photo)
    print(f"  Recortes (cutouts): {cutout_count}")
    print(f"  Fotos madre (parent): {parent_count}")

    # Fase 3: Propagar metadata y tags
    print("\nFase 3: Propagando metadata...")
    propagate_tags(photos)

    # Fase 4: Detectar descargas
    print("\nFase 4: Revisando descargas...")
    db_conn = sqlite3.connect(db_path)
    db_conn.row_factory = sqlite3.Row

    need_download = []
    skip_count = 0
    for filename, photo in photos.items():
        gedcom_path_file = photos_dir / filename
        if not gedcom_path_file.exists():
            need_download.append((filename, photo.url))
        else:
            skip_count += 1

    print(f"  Existentes: {skip_count}")
    print(f"  Por descargar: {len(need_download)}")

    # Fase 5: Renombrar hash → GEDCOM
    if not args.dry_run and not args.skip_download:
        print("\nFase 5: Renombrando archivos hash...")
        renamed = check_and_rename_existing(photos, photos_dir, db_conn)
        print(f"  Renombrados: {renamed}")
        # Actualizar need_download
        need_download = [(f, p.url) for f, p in photos.items() if not (photos_dir / f).exists()]

    # Fase 6: Descargar nuevas
    if need_download and not args.skip_download:
        print(f"\nFase 6: Descargando {len(need_download)} fotos...")
        downloaded = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(download_photo, url, photos_dir, filename): (filename, url)
                for filename, url in need_download
            }
            for i, future in enumerate(as_completed(futures), 1):
                filename, success = future.result()
                if success:
                    downloaded += 1
                else:
                    failed += 1
                if i % 50 == 0 or i == len(futures):
                    print(f"  Progreso: {i}/{len(futures)} ({downloaded} OK, {failed} errores)")

        print(f"  Completado: {downloaded} descargadas, {failed} errores")

    # Fase 7: Escribir en DB
    if not args.dry_run:
        print("\nFase 7: Escribiendo en base de datos...")

        # Crear tablas nuevas
        cursor = db_conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS photo_tags")
        cursor.execute("DROP TABLE IF EXISTS albums")
        cursor.execute("DROP TABLE IF EXISTS photos")

        cursor.execute("""
            CREATE TABLE photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                url TEXT,
                filesize INTEGER,
                title TEXT,
                date TEXT,
                place TEXT,
                photo_rin TEXT,
                album_id TEXT,
                is_cutout INTEGER DEFAULT 0,
                is_prim_cutout INTEGER DEFAULT 0,
                is_personal_photo INTEGER DEFAULT 0,
                is_parent_photo INTEGER DEFAULT 0,
                parent_photo_id INTEGER,
                position TEXT,
                is_downloaded INTEGER DEFAULT 0,
                inserted_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE photo_tags (
                photo_id INTEGER NOT NULL,
                person_id TEXT NOT NULL,
                is_primary INTEGER DEFAULT 0,
                position TEXT,
                source TEXT,
                PRIMARY KEY (photo_id, person_id),
                FOREIGN KEY (photo_id) REFERENCES photos(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE albums (
                gedcom_id TEXT PRIMARY KEY,
                title TEXT
            )
        """)

        # Insertar fotos
        parent_id_map = {}  # filename -> photo.id
        for filename, photo in photos.items():
            is_downloaded = 1 if (photos_dir / filename).exists() else 0
            cursor.execute("""
                INSERT INTO photos
                (filename, url, filesize, title, date, place, photo_rin, album_id,
                 is_cutout, is_prim_cutout, is_personal_photo, is_parent_photo, position, is_downloaded)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                filename, photo.url, photo.filesize, photo.title, photo.date,
                photo.place, photo.photo_rin, photo.album_id, photo.is_cutout,
                photo.is_prim_cutout, photo.is_personal_photo, photo.is_parent_photo, photo.position, is_downloaded
            ))
            parent_id_map[filename] = cursor.lastrowid

        # Actualizar parent_photo_id
        for filename, photo in photos.items():
            if photo.parent_photo_id:
                parent_id = parent_id_map.get(photo.parent_photo_id)
                if parent_id:
                    cursor.execute(
                        "UPDATE photos SET parent_photo_id = ? WHERE filename = ?",
                        (parent_id, filename)
                    )

        # Insertar photo_tags
        for filename, photo in photos.items():
            photo_id = parent_id_map[filename]
            for person_id, tag_info in photo.tagged_people.items():
                cursor.execute("""
                    INSERT INTO photo_tags (photo_id, person_id, is_primary, position, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (photo_id, person_id, tag_info["is_primary"], tag_info.get("position"), tag_info["source"]))

        # Insertar álbumes
        for album_id, album_info in albums.items():
            cursor.execute(
                "INSERT INTO albums (gedcom_id, title) VALUES (?, ?)",
                (album_id, album_info["title"])
            )

        db_conn.commit()

        # Actualizar people.photo_file y photo_count
        cursor.execute("""
            UPDATE people SET
                photo_file = (
                    SELECT p.filename FROM photos p
                    JOIN photo_tags pt ON pt.photo_id = p.id
                    WHERE pt.person_id = people.id AND pt.is_primary = 1
                    ORDER BY p.is_parent_photo ASC
                    LIMIT 1
                ),
                photo_count = (
                    SELECT COUNT(*) FROM photo_tags pt
                    WHERE pt.person_id = people.id
                )
        """)
        db_conn.commit()

        print("  Base de datos actualizada")

    db_conn.close()

    # Estadísticas finales
    print("\n=== Resumen ===")
    print(f"Fotos únicas: {len(photos)}")
    print(f"Personas etiquetadas: {sum(len(p.tagged_people) for p in photos.values())}")
    print(f"Relaciones padre-hijo: {sum(1 for p in photos.values() if p.parent_photo_id)}")
    print("\nListo. Ejecutar:")
    print("  cd backend && python3 -m uvicorn app:app --port 8000")
    print()


if __name__ == "__main__":
    main()
