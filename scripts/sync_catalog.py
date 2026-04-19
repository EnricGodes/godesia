#!/usr/bin/env python3
"""
sync_catalog.py — Sincroniza árbol genealógico completo desde GEDCOM a SQLite.

Uso:
  python3 sync_catalog.py [--gedcom RUTA]
  python3 sync_catalog.py --gedcom docs/archivo.ged --dry-run
  python3 sync_catalog.py --skip-download

El script:
1. Parsea INDI/FAM del GEDCOM → people, marriages, children, occupations, residences, notes
2. Parsea OBJE del GEDCOM → fotos con metadatos completos + posición facial (_POSITION)
3. Resuelve relaciones padre-hijo entre fotos (cutouts)
4. Propaga tags entre fotos padre e hijas
5. UPSERT people (preserva ediciones manuales)
6. DROP+RECREATE tablas de fotos (autoridad única: GEDCOM)
"""

import argparse
import hashlib
import re
import shutil
import sqlite3
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Import note cleaning from the main parser
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from gedcom_parser import clean_note_html
from database import convert_date_to_spanish


DOC_TYPES = [
    ("bautisme",     r"bautis|bateig|baptis"),
    ("matrimoni",    r"matrimon|matrimoni|casament(?!.*foto)|boda(?!.*foto)"),
    ("defuncio",     r"defunci|defuncion|obituari|esquela|sepultur|obituar"),
    ("naixement",    r"naix[ae]ment|nasciment|partida.*naix|nacimiento"),
    ("certificat",   r"certific|solteria|llicencia|licencia"),
    ("padro",        r"padro\b|padron\b|empadron|cens\b"),
    ("testament",    r"testament"),
    ("arbre",        r"arbre.*geneal|árbol.*geneal"),
    ("transcripcio", r"transcripci"),
    ("poema",        r"poema|poem"),
    ("invitacio",    r"invitaci|convit"),
    ("carta",        r"\bcarta\b"),
    ("dibuix",       r"dibuix|dibujo|drawing|croquis|esbo[çz]|sketch|plànol|plano"),
    ("biografia",    r"AI Biography|biography\b"),
    ("document",     r"partida\b|acta\b|expedient|expediente|registre(?!.*foto)"),
]

def classify_document(title):
    """Returns (is_document, doc_type) based on title patterns."""
    if not title:
        return 0, None
    for doc_type, pattern in DOC_TYPES:
        if re.search(pattern, title, re.IGNORECASE):
            return 1, doc_type
    return 0, None


def strip_html(text):
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return None
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'&[a-z]+;', ' ', clean)
    clean = ' '.join(clean.split())
    return clean if len(clean) > 10 else None


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
        self.parent_photo_id = None
        self.tagged_people = {}  # person_id -> {is_primary, is_prim_cutout, position, source}

    def add_tag(self, person_id, is_primary=False, is_prim_cutout=False, position=None, source="direct"):
        if person_id not in self.tagged_people:
            self.tagged_people[person_id] = {
                "is_primary": is_primary,
                "is_prim_cutout": is_prim_cutout,
                "position": position,
                "source": source
            }


def find_gedcom(base_dir):
    """Busca el GEDCOM más reciente en docs/."""
    docs_dir = base_dir / "docs"
    ged_files = list(docs_dir.glob("*.ged"))
    if not ged_files:
        return None
    return max(ged_files, key=lambda p: p.stat().st_mtime)


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
    """Parsea INDI → OBJE records con _POSITION. Retorna (dict de fotos, dict de INDI → OBJE blocks)."""
    photos = {}
    indi_obje_blocks = defaultdict(list)

    i = 0
    current_indi = None

    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1

        match = re.match(r"^0\s+(@I\w+@)\s+INDI", line)
        if match:
            current_indi = match.group(1)
            continue

        if current_indi:
            match = re.match(r"^1\s+OBJE\s*$", line)
            if match:
                obje = {
                    "url": None, "filename": None, "format": None, "filesize": None,
                    "title": None, "date": None, "place": None, "photo_rin": None,
                    "album_id": None, "is_cutout": False, "is_parent_photo": False,
                    "is_personal_photo": False, "is_prim": False, "is_prim_cutout": False,
                    "position": None
                }

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

    for indi_id, obje_list in indi_obje_blocks.items():
        for obje in obje_list:
            fname = obje["filename"]
            if fname not in photos:
                photos[fname] = PhotoRecord(fname, obje["url"])

            photo = photos[fname]
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

            photo.add_tag(indi_id, is_primary=obje["is_prim"], is_prim_cutout=obje["is_prim_cutout"],
                         position=obje["position"], source="direct")

    return photos, indi_obje_blocks


def parse_gedcom_people(lines):
    """Parsea INDI records. Retorna dict de person_id -> person_data."""
    people = {}
    occupations = defaultdict(list)
    residences = defaultdict(list)
    notes = defaultdict(list)
    marriages = {}
    children = defaultdict(list)

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1

        match = re.match(r"^0\s+(@I\w+@)\s+INDI", line)
        if match:
            person_id = match.group(1)
            person = {
                "id": person_id, "name": "", "given_name": "", "surname": "",
                "sex": None, "birth_date": None, "birth_day": None, "birth_month": None,
                "birth_year": None, "birth_place": None, "death_date": None, "death_year": None,
                "death_place": None, "death_cause": None, "death_note": None, "death_age": None,
                "is_alive": 0, "_has_deat": False, "father_id": None, "mother_id": None, "photo_file": None, "photo_count": 0
            }

            while i < len(lines):
                next_line = lines[i].rstrip("\n")
                if not next_line or next_line[0] == "0":
                    break

                match1 = re.match(r"^1\s+(\w+)(.*)", next_line)
                if match1:
                    tag, rest = match1.group(1), match1.group(2).strip()
                    if tag == "NAME":
                        person["name"] = rest.replace("/", " ").strip()
                        # Buscar GIVN/SURN subordinados
                        j = i + 1
                        while j < len(lines) and lines[j].startswith("2"):
                            name_line = lines[j].rstrip("\n")
                            if "GIVN" in name_line:
                                person["given_name"] = name_line.split("GIVN", 1)[1].strip()
                            elif "SURN" in name_line:
                                person["surname"] = name_line.split("SURN", 1)[1].strip()
                            j += 1
                    elif tag == "SEX":
                        person["sex"] = rest if rest in ("M", "F") else None
                    elif tag == "FAMC":
                        match_parent = re.search(r"@F(\w+)@", rest)
                        if match_parent:
                            pass  # Procesado al final con familias
                    elif tag == "FAMS":
                        match_spouse = re.search(r"@F(\w+)@", rest)
                        if match_spouse:
                            pass  # Procesado al final con familias
                    elif tag == "BIRT":
                        j = i + 1
                        while j < len(lines) and lines[j].startswith("2"):
                            birt_line = lines[j].rstrip("\n")
                            if "DATE" in birt_line:
                                person["birth_date"] = birt_line.split("DATE", 1)[1].strip()
                                day, month, year = _parse_date(person["birth_date"])
                                person["birth_day"], person["birth_month"], person["birth_year"] = day, month, year
                            elif "PLAC" in birt_line:
                                person["birth_place"] = birt_line.split("PLAC", 1)[1].strip()
                            j += 1
                    elif tag == "DEAT":
                        person["_has_deat"] = True
                        j = i + 1
                        while j < len(lines) and lines[j].startswith("2"):
                            deat_line = lines[j].rstrip("\n")
                            if "DATE" in deat_line:
                                person["death_date"] = deat_line.split("DATE", 1)[1].strip()
                                _, _, year = _parse_date(person["death_date"])
                                person["death_year"] = year
                            elif "PLAC" in deat_line:
                                person["death_place"] = deat_line.split("PLAC", 1)[1].strip()
                            elif "CAUS" in deat_line:
                                person["death_cause"] = deat_line.split("CAUS", 1)[1].strip()
                            elif "NOTE" in deat_line:
                                person["death_note"] = deat_line.split("NOTE", 1)[1].strip()
                            elif "AGE" in deat_line:
                                person["death_age"] = deat_line.split("AGE", 1)[1].strip()
                            j += 1
                        person["is_alive"] = 0
                    elif tag == "OCCU":
                        j = i + 1
                        occu_data = {"title": rest, "date": None, "place": None}
                        while j < len(lines) and lines[j].startswith("2"):
                            occu_line = lines[j].rstrip("\n")
                            if "DATE" in occu_line:
                                occu_data["date"] = occu_line.split("DATE", 1)[1].strip()
                            elif "PLAC" in occu_line:
                                occu_data["place"] = occu_line.split("PLAC", 1)[1].strip()
                            j += 1
                        occupations[person_id].append(occu_data)
                    elif tag == "RESI":
                        j = i + 1
                        resi_data = {"address": None, "address2": None, "city": None, "country": None, "date": None}
                        while j < len(lines) and lines[j].startswith("2"):
                            resi_line = lines[j].rstrip("\n")
                            if "DATE" in resi_line:
                                resi_data["date"] = resi_line.split("DATE", 1)[1].strip()
                            elif "ADDR" in resi_line:
                                resi_data["address"] = resi_line.split("ADDR", 1)[1].strip()
                            elif "ADR2" in resi_line:
                                resi_data["address2"] = resi_line.split("ADR2", 1)[1].strip()
                            elif "CITY" in resi_line:
                                resi_data["city"] = resi_line.split("CITY", 1)[1].strip()
                            elif "CTRY" in resi_line:
                                resi_data["country"] = resi_line.split("CTRY", 1)[1].strip()
                            j += 1
                        residences[person_id].append(resi_data)
                    elif tag == "NOTE":
                        # Accumulate raw content including non-CONC continuation lines
                        note_content = rest
                        j = i + 1
                        while j < len(lines):
                            raw_line = lines[j].rstrip("\n")
                            conc_match = re.match(r"^2\s+CONC\s?(.*)", raw_line)
                            if conc_match:
                                note_content += conc_match.group(1)
                                j += 1
                            elif re.match(r"^\d+\s+", raw_line) and not raw_line.startswith("2 CONC"):
                                break  # New GEDCOM record — stop
                            else:
                                # Raw HTML continuation line (no level prefix)
                                note_content += raw_line
                                j += 1
                        i = j - 1  # Rewind so outer loop processes next record
                        cleaned = clean_note_html(note_content)
                        if cleaned:
                            notes[person_id].append(cleaned)
                i += 1

            people[person_id] = person

    # Parse FAM records
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1

        match = re.match(r"^0\s+(@F\w+@)\s+FAM", line)
        if match:
            fam_id = match.group(1)
            husb_id = None
            wife_id = None
            marr_data = {"date": None, "place": None}
            chil_list = []

            while i < len(lines):
                next_line = lines[i].rstrip("\n")
                if not next_line or next_line[0] == "0":
                    break

                if "HUSB" in next_line:
                    m = re.search(r"@I(\w+)@", next_line)
                    if m:
                        husb_id = "@I" + m.group(1) + "@"
                elif "WIFE" in next_line:
                    m = re.search(r"@I(\w+)@", next_line)
                    if m:
                        wife_id = "@I" + m.group(1) + "@"
                elif "CHIL" in next_line:
                    m = re.search(r"@I(\w+)@", next_line)
                    if m:
                        chil_list.append("@I" + m.group(1) + "@")
                elif "MARR" in next_line:
                    j = i + 1
                    while j < len(lines) and lines[j].startswith("2"):
                        marr_line = lines[j].rstrip("\n")
                        if "DATE" in marr_line:
                            marr_data["date"] = marr_line.split("DATE", 1)[1].strip()
                        elif "PLAC" in marr_line:
                            marr_data["place"] = marr_line.split("PLAC", 1)[1].strip()
                        j += 1

                i += 1

            if husb_id and wife_id:
                marriages[fam_id] = {"husb": husb_id, "wife": wife_id, "date": marr_data["date"], "place": marr_data["place"]}
                if husb_id in people:
                    people[husb_id]["father_id"] = None
                if wife_id in people:
                    people[wife_id]["mother_id"] = None

            for chil_id in chil_list:
                children[fam_id].append(chil_id)
                if chil_id in people:
                    if husb_id:
                        people[chil_id]["father_id"] = husb_id
                    if wife_id:
                        people[chil_id]["mother_id"] = wife_id

    return people, marriages, children, occupations, residences, notes


def _parse_date(date_str):
    """Parse GEDCOM date. Retorna (day, month, year)."""
    MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
    if not date_str:
        return None, None, None

    for prefix in ("ABT", "BEF", "AFT", "EST", "CAL", "BET", "FROM"):
        if date_str.startswith(prefix):
            date_str = date_str[len(prefix):].strip()

    if "AND" in date_str or "TO" in date_str:
        parts = re.split(r"\s+AND\s+|\s+TO\s+", date_str)
        date_str = parts[0].strip()

    parts = date_str.split()
    try:
        if len(parts) == 3:
            return int(parts[0]), MONTHS.get(parts[1]), int(parts[2])
        elif len(parts) == 2:
            return None, MONTHS.get(parts[0]), int(parts[1])
        elif len(parts) == 1 and parts[0].isdigit():
            return None, None, int(parts[0])
    except:
        pass
    return None, None, None


def resolve_parent_child(photos, indi_obje_blocks):
    """Resuelve relaciones padre-hijo dentro de cada INDI."""
    for indi_id, obje_list in indi_obje_blocks.items():
        parent_filename = None
        for obje in obje_list:
            if obje["is_parent_photo"] and not obje["is_cutout"]:
                parent_filename = obje["filename"]
                break

        if parent_filename:
            for obje in obje_list:
                if obje["is_cutout"] and obje["filename"] != parent_filename:
                    child_photo = photos.get(obje["filename"])
                    if child_photo:
                        child_photo.parent_photo_id = parent_filename


def propagate_tags(photos):
    """Propaga tags entre padres e hijos."""
    fname_to_photo = {p.filename: p for p in photos.values()}

    for photo in photos.values():
        if photo.is_parent_photo:
            children = [p for p in photos.values() if p.parent_photo_id == photo.filename]
            for child in children:
                for person_id, tag_info in child.tagged_people.items():
                    if person_id not in photo.tagged_people:
                        photo.add_tag(person_id, source="child_cutout_propagation")

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
    """Descarga una foto."""
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


def main():
    parser = argparse.ArgumentParser(description="Sincroniza catálogo completo desde GEDCOM")
    parser.add_argument("--gedcom", type=str, default=None, help="Ruta al archivo GEDCOM (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true", help="Parse pero no escribir en DB")
    parser.add_argument("--skip-download", action="store_true", help="No descargar fotos")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    db_path = base / "data" / "godesia.db"
    photos_dir = base / "data" / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    gedcom_path = Path(args.gedcom) if args.gedcom else find_gedcom(base)
    if not gedcom_path or not gedcom_path.exists():
        print(f"Error: GEDCOM no encontrado. Ruta: {gedcom_path}")
        return

    print(f"\n=== Sincronización de Catálogo Genealógico ===\n")
    print(f"GEDCOM: {gedcom_path.name}")

    with open(gedcom_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    print("\nFase 1: Parseando GEDCOM (personas)...")
    people, marriages, children, occupations, residences, notes = parse_gedcom_people(lines)
    print(f"  Personas: {len(people)}")
    print(f"  Matrimonios: {len(marriages)}")
    print(f"  Ocupaciones: {sum(len(v) for v in occupations.values())}")
    print(f"  Residencias: {sum(len(v) for v in residences.values())}")
    print(f"  Notas: {sum(len(v) for v in notes.values())}")

    print("\nFase 2: Parseando GEDCOM (fotos)...")
    albums = parse_gedcom_albums(lines)
    photos, indi_obje_blocks = parse_gedcom_photos(lines)
    print(f"  Fotos únicas: {len(photos)}")
    print(f"  Álbumes: {len(albums)}")

    print("\nFase 3: Resolviendo relaciones padre-hijo...")
    resolve_parent_child(photos, indi_obje_blocks)
    cutout_count = sum(1 for p in photos.values() if p.is_cutout)
    parent_count = sum(1 for p in photos.values() if p.is_parent_photo)
    print(f"  Recortes (cutouts): {cutout_count}")
    print(f"  Fotos madre (parent): {parent_count}")

    print("\nFase 4: Propagando tags entre fotos...")
    propagate_tags(photos)

    print("\nFase 5: Revisando descargas...")
    db_conn = sqlite3.connect(db_path)
    db_conn.row_factory = sqlite3.Row

    need_download = []
    skip_count = 0
    for filename, photo in photos.items():
        if not (photos_dir / filename).exists():
            need_download.append((filename, photo.url))
        else:
            skip_count += 1

    print(f"  Existentes: {skip_count}")
    print(f"  Por descargar: {len(need_download)}")

    if need_download and not args.skip_download:
        print(f"\nFase 6: Descargando {len(need_download)} fotos...")
        downloaded = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(download_photo, url, photos_dir, filename): (filename, url)
                      for filename, url in need_download}
            for i, future in enumerate(as_completed(futures), 1):
                filename, success = future.result()
                if success:
                    downloaded += 1
                else:
                    failed += 1
                if i % 50 == 0 or i == len(futures):
                    print(f"  Progreso: {i}/{len(futures)} ({downloaded} OK, {failed} errores)")

        print(f"  Completado: {downloaded} descargadas, {failed} errores")

    if not args.dry_run:
        print("\nFase 7: Escribiendo en base de datos...")

        # Compute is_alive before UPSERT: born after 1900, no death record, no DEAT flag
        for person_id, person in people.items():
            if (person["birth_year"] and person["birth_year"] > 1900
                    and not person["death_date"] and not person["death_year"]
                    and not person["_has_deat"]):
                person["is_alive"] = 1

        # Convert GEDCOM dates to Spanish before writing to DB
        for person in people.values():
            person["birth_date"] = convert_date_to_spanish(person["birth_date"])
            person["death_date"] = convert_date_to_spanish(person["death_date"])
        for marr in marriages.values():
            marr["date"] = convert_date_to_spanish(marr["date"])
        for occs in occupations.values():
            for occ in occs:
                occ["date"] = convert_date_to_spanish(occ["date"])
        for ress in residences.values():
            for res in ress:
                res["date"] = convert_date_to_spanish(res["date"])

        cursor = db_conn.cursor()

        # UPSERT personas — preserves photo_file and photo_count (managed by sync_photos)
        for person_id, person in people.items():
            cursor.execute("""
                INSERT INTO people
                (id, name, given_name, surname, sex, birth_date, birth_day, birth_month,
                 birth_year, birth_place, death_date, death_year, death_place, death_cause,
                 death_note, death_age, is_alive, father_id, mother_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    given_name=excluded.given_name,
                    surname=excluded.surname,
                    sex=excluded.sex,
                    birth_date=excluded.birth_date,
                    birth_day=excluded.birth_day,
                    birth_month=excluded.birth_month,
                    birth_year=excluded.birth_year,
                    birth_place=excluded.birth_place,
                    death_date=excluded.death_date,
                    death_year=excluded.death_year,
                    death_place=excluded.death_place,
                    death_cause=excluded.death_cause,
                    death_note=excluded.death_note,
                    death_age=excluded.death_age,
                    is_alive=excluded.is_alive,
                    father_id=excluded.father_id,
                    mother_id=excluded.mother_id
            """, (person_id, person["name"], person["given_name"], person["surname"], person["sex"],
                  person["birth_date"], person["birth_day"], person["birth_month"], person["birth_year"],
                  person["birth_place"], person["death_date"], person["death_year"], person["death_place"],
                  person["death_cause"], person["death_note"], person["death_age"], person["is_alive"],
                  person["father_id"], person["mother_id"]))

        # DELETE + re-insert matrimonios (avoid duplicates with autoincrement PK)
        cursor.execute("DELETE FROM marriages")
        for fam_id, marr in marriages.items():
            cursor.execute("""
                INSERT INTO marriages (person1_id, person2_id, date, place)
                VALUES (?, ?, ?, ?)
            """, (marr["husb"], marr["wife"], marr["date"], marr["place"]))

        # DELETE + re-insert ocupaciones, residencias, notas (1-to-many)
        cursor.execute("DELETE FROM occupations")
        for person_id, occs in occupations.items():
            for occ in occs:
                cursor.execute("""
                    INSERT INTO occupations (person_id, title, date, place)
                    VALUES (?, ?, ?, ?)
                """, (person_id, occ["title"], occ["date"], occ["place"]))

        cursor.execute("DELETE FROM residences")
        for person_id, ress in residences.items():
            for res in ress:
                cursor.execute("""
                    INSERT INTO residences (person_id, address, address2, city, country, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (person_id, res["address"], res["address2"], res["city"], res["country"], res["date"]))

        cursor.execute("DELETE FROM notes")
        for person_id, note_list in notes.items():
            for note_content in note_list:
                cursor.execute("""
                    INSERT INTO notes (person_id, content)
                    VALUES (?, ?)
                """, (person_id, note_content))

        cursor.execute("DELETE FROM children")
        for fam_id, chil_list in children.items():
            for chil_id in chil_list:
                cursor.execute("""
                    INSERT INTO children (parent_id, child_id)
                    VALUES ((SELECT person1_id FROM marriages WHERE id IN (SELECT rowid FROM marriages WHERE person1_id || '|' || person2_id LIKE ?)), ?)
                """, (f"%{fam_id}%", chil_id))

        cursor.execute("DELETE FROM children")
        for fam_id, chil_list in children.items():
            if fam_id in marriages:
                husb = marriages[fam_id]["husb"]
                wife = marriages[fam_id]["wife"]
                for chil_id in chil_list:
                    cursor.execute("""
                        INSERT INTO children (parent_id, child_id)
                        VALUES (?, ?)
                    """, (husb, chil_id))
                    cursor.execute("""
                        INSERT INTO children (parent_id, child_id)
                        VALUES (?, ?)
                    """, (wife, chil_id))

        # DROP + recreate fotos
        cursor.execute("DROP TABLE IF EXISTS photo_tags")
        cursor.execute("DROP TABLE IF EXISTS albums")
        cursor.execute("DROP TABLE IF EXISTS photos")

        cursor.execute("""
            CREATE TABLE photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                url TEXT, filesize INTEGER, title TEXT, date TEXT, place TEXT,
                photo_rin TEXT, album_id TEXT,
                is_cutout INTEGER DEFAULT 0, is_parent_photo INTEGER DEFAULT 0,
                is_personal_photo INTEGER DEFAULT 0, is_prim_cutout INTEGER DEFAULT 0,
                is_document INTEGER DEFAULT 0, doc_type TEXT,
                parent_photo_id INTEGER, position TEXT, is_downloaded INTEGER DEFAULT 0,
                transcription TEXT,
                inserted_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE photo_tags (
                photo_id INTEGER NOT NULL,
                person_id TEXT NOT NULL,
                is_primary INTEGER DEFAULT 0,
                is_prim_cutout INTEGER DEFAULT 0,
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

        # Build transcription map from person notes
        transcription_map = {}
        for filename, photo in photos.items():
            if photo.tagged_people:
                transcriptions = []
                for person_id in photo.tagged_people.keys():
                    person_notes = notes.get(person_id, [])
                    for note in person_notes:
                        clean_note = strip_html(note)
                        if clean_note:
                            transcriptions.append(clean_note)
                if transcriptions:
                    transcription_map[filename] = " | ".join(transcriptions)

        parent_id_map = {}
        for filename, photo in photos.items():
            is_downloaded = 1 if (photos_dir / filename).exists() else 0
            is_document, doc_type = classify_document(photo.title)
            transcription = transcription_map.get(filename) if is_document else None
            cursor.execute("""
                INSERT INTO photos
                (filename, url, filesize, title, date, place, photo_rin, album_id,
                 is_cutout, is_parent_photo, is_personal_photo, is_prim_cutout, position, is_downloaded,
                 is_document, doc_type, transcription)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (filename, photo.url, photo.filesize, photo.title, photo.date,
                  photo.place, photo.photo_rin, photo.album_id, photo.is_cutout,
                  photo.is_parent_photo, photo.is_personal_photo, photo.is_prim_cutout,
                  photo.position, is_downloaded, is_document, doc_type, transcription))
            parent_id_map[filename] = cursor.lastrowid

        for filename, photo in photos.items():
            if photo.parent_photo_id:
                parent_id = parent_id_map.get(photo.parent_photo_id)
                if parent_id:
                    cursor.execute(
                        "UPDATE photos SET parent_photo_id = ? WHERE filename = ?",
                        (parent_id, filename)
                    )

        for filename, photo in photos.items():
            photo_id = parent_id_map[filename]
            for person_id, tag_info in photo.tagged_people.items():
                cursor.execute("""
                    INSERT INTO photo_tags (photo_id, person_id, is_primary, is_prim_cutout, position, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (photo_id, person_id, tag_info["is_primary"], tag_info["is_prim_cutout"],
                      tag_info["position"], tag_info["source"]))

        for album_id, album_info in albums.items():
            cursor.execute(
                "INSERT INTO albums (gedcom_id, title) VALUES (?, ?)",
                (album_id, album_info["title"])
            )

        # is_alive already computed per-person before UPSERT (respects DEAT Y flag)

        cursor.execute("""
            UPDATE people SET
                photo_file = (
                    SELECT p.filename FROM photos p
                    JOIN photo_tags pt ON pt.photo_id = p.id
                    WHERE pt.person_id = people.id
                    ORDER BY
                        pt.is_primary DESC,
                        p.is_personal_photo DESC,
                        pt.is_prim_cutout DESC,
                        p.is_parent_photo ASC,
                        p.id ASC
                    LIMIT 1
                ),
                photo_count = (
                    SELECT COUNT(*) FROM photo_tags pt
                    WHERE pt.person_id = people.id
                )
        """)

        db_conn.commit()
        print("  Base de datos actualizada")

        # CRITICAL: Regenerate people.photo_file using the centralized 5-level
        # selection algorithm. This MUST run after any photos/photo_tags update
        # to prevent profile photos from disappearing.
        print("\nFase 8: Sincronizando fotos de perfil...")
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
        from database import update_all_photo_files
        updated = update_all_photo_files(db_conn)
        print(f"  Fotos de perfil actualizadas: {updated} personas")

    db_conn.close()

    print("\n=== Resumen ===")
    print(f"Personas: {len(people)}")
    print(f"Fotos únicas: {len(photos)}")
    print(f"Personas etiquetadas: {sum(len(p.tagged_people) for p in photos.values())}")
    print(f"Relaciones padre-hijo: {sum(1 for p in photos.values() if p.parent_photo_id)}")
    print("\nListo para ejecutar:")
    print("  cd backend && python3 -m uvicorn app:app --port 8000")
    print()


if __name__ == "__main__":
    main()
