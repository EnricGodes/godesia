"""Parser GEDCOM → JSON estructurado para el árbol genealógico Godes."""

import html
import json
import re
import sys
from pathlib import Path


def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def translate_event_type(event_type: str) -> str:
    """Translate event type names from English to Spanish."""
    translation_map = {
        "Employer": "Trabajo",
        "Award": "Premio",
        "Illness": "Enfermedad",
        "Funeral": "Funeral",
        "Membership": "Afiliación",
        "Military Enlistment": "Alistamiento Militar",
        "Military Service": "Servicio Militar",
        "Move": "Mudanza",
        "Family Reunion": "Reunión Familiar",
        "Obituary": "Obituario",
        "Event-Misc": "Evento",
        "Custom event": "Evento Personalizado",
        "Language spoken": "Idioma",
        "Reference Number": "Número de Referencia",
        "Anecdote": "Anécdota",
    }
    return translation_map.get(event_type, event_type)


def parse_gedcom(filepath: str) -> dict:
    """Parsea un archivo GEDCOM y devuelve un dict con personas y familias."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    individuals = {}
    families = {}
    current_record = None
    current_id = None
    current_level1 = None
    current_level2 = None

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1

        # Parse level, tag, value
        match = re.match(r"^(\d+)\s+(@\w+@)?\s*(\w+)\s*(.*)?$", line)
        if not match:
            continue

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3)
        value = (match.group(4) or "").strip()

        if level == 0:
            current_level1 = None
            current_level2 = None
            if tag == "INDI":
                current_id = xref
                current_record = "INDI"
                individuals[current_id] = {
                    "id": current_id,
                    "name": "",
                    "given_name": "",
                    "surname": "",
                    "sex": "",
                    "birth": {},
                    "death": {},
                    "baptism": {},
                    "burial": [],
                    "occupations": [],
                    "residences": [],
                    "military": [],
                    "anecdotes": [],
                    "events": [],
                    "notes": [],
                    "photos": [],
                    "family_spouse": [],
                    "family_child": None,
                    "immigration": {},
                }
            elif tag == "FAM":
                current_id = xref
                current_record = "FAM"
                families[current_id] = {
                    "id": current_id,
                    "husband": None,
                    "wife": None,
                    "children": [],
                    "marriage": {},
                    "divorce": {},
                }
            else:
                current_record = None
                current_id = None
            continue

        if current_record == "INDI" and current_id:
            indi = individuals[current_id]
            if level == 1:
                current_level1 = tag
                current_level2 = None

                if tag == "NAME":
                    indi["name"] = value.replace("/", "").strip()
                elif tag == "SEX":
                    indi["sex"] = value
                elif tag == "BIRT":
                    current_level1 = "BIRT"
                elif tag == "DEAT":
                    current_level1 = "DEAT"
                elif tag == "BURI":
                    indi["burial"].append({"place_detail": value} if value else {})
                    current_level1 = "BURI"
                elif tag == "RESI":
                    indi["residences"].append({})
                    current_level1 = "RESI"
                elif tag == "OCCU":
                    indi["occupations"].append({"title": value})
                    current_level1 = "OCCU"
                # Capture ALL event tags as events with their type
                elif tag in ("CENS", "EDUC", "BAPM", "CHR", "CONF", "FCOM", "EMIG", "IMMI", "NATI", "RELI", "DSCR"):
                    event_type_map = {
                        "CENS": "Censo", "EDUC": "Educación", "BAPM": "Bautismo", "CHR": "Bautizo",
                        "CONF": "Confirmación", "FCOM": "Primera Comunión", "EMIG": "Emigración",
                        "IMMI": "Inmigración", "NATI": "Nacionalidad", "RELI": "Religión", "DSCR": "Descripción"
                    }
                    indi["events"].append({"tag": tag, "type": event_type_map.get(tag, tag), "description": value})
                    current_level1 = tag
                elif tag == "IMMI":
                    if value:
                        indi["immigration"]["event"] = value
                    indi["events"].append({"tag": "IMMI", "type": "Inmigración", "description": value})
                    current_level1 = "IMMI"
                elif tag == "EVEN":
                    indi["events"].append({"tag": "EVEN", "description": value})
                    current_level1 = "EVEN"
                elif tag == "FAMS":
                    indi["family_spouse"].append(value)
                elif tag == "FAMC":
                    indi["family_child"] = value
                elif tag == "NOTE":
                    clean = clean_html(value)
                    if clean:
                        indi["notes"].append(clean)
                elif tag == "OBJE":
                    current_level1 = "OBJE"
                    indi["photos"].append({})

            elif level == 2:
                current_level2 = tag
                if current_level1 == "NAME":
                    if tag == "GIVN":
                        indi["given_name"] = value
                    elif tag == "SURN":
                        indi["surname"] = value
                elif current_level1 == "BIRT":
                    if tag == "DATE":
                        indi["birth"]["date"] = value
                    elif tag == "PLAC":
                        indi["birth"]["place"] = value
                    elif tag == "NOTE":
                        clean = clean_html(value)
                        indi["birth"]["note"] = clean
                elif current_level1 == "DEAT":
                    if tag == "DATE":
                        indi["death"]["date"] = value
                    elif tag == "PLAC":
                        indi["death"]["place"] = value
                    elif tag == "CAUS":
                        indi["death"]["cause"] = value
                    elif tag == "AGE":
                        indi["death"]["age"] = value
                    elif tag == "NOTE":
                        clean = clean_html(value)
                        indi["death"]["note"] = clean
                elif current_level1 == "BAPM":
                    if tag == "DATE":
                        indi["baptism"]["date"] = value
                        # Also update the BAPM event
                        for evt in reversed(indi["events"]):
                            if evt.get("tag") == "BAPM":
                                evt["date"] = value
                                break
                    elif tag == "PLAC":
                        indi["baptism"]["place"] = value
                        # Also update the BAPM event
                        for evt in reversed(indi["events"]):
                            if evt.get("tag") == "BAPM":
                                evt["place"] = value
                                break
                    elif tag == "NOTE":
                        indi["baptism"]["note"] = value
                        # Also update the BAPM event
                        for evt in reversed(indi["events"]):
                            if evt.get("tag") == "BAPM":
                                evt["note"] = value
                                break
                elif current_level1 == "CHR":
                    if tag == "DATE":
                        indi["baptism"]["date"] = value
                        # Also update the CHR event
                        for evt in reversed(indi["events"]):
                            if evt.get("tag") == "CHR":
                                evt["date"] = value
                                break
                    elif tag == "PLAC":
                        indi["baptism"]["place"] = value
                        # Also update the CHR event
                        for evt in reversed(indi["events"]):
                            if evt.get("tag") == "CHR":
                                evt["place"] = value
                                break
                    elif tag == "NOTE":
                        indi["baptism"]["note"] = value
                        # Also update the CHR event
                        for evt in reversed(indi["events"]):
                            if evt.get("tag") == "CHR":
                                evt["note"] = value
                                break
                        # Extract godparents from NOTE if present
                        if "Godparents:" in value:
                            godparents_text = value.split("Godparents:")[-1].strip()
                            if godparents_text:
                                indi["baptism"]["godparents"] = godparents_text
                elif current_level1 == "BURI" and indi["burial"]:
                    buri = indi["burial"][-1]
                    if tag == "DATE":
                        buri["date"] = value
                    elif tag == "PLAC":
                        buri["place"] = value
                elif current_level1 == "OCCU" and indi["occupations"]:
                    occ = indi["occupations"][-1]
                    if tag == "DATE":
                        occ["date"] = value
                    elif tag == "PLAC":
                        occ["place"] = value
                elif current_level1 == "RESI" and indi["residences"]:
                    res = indi["residences"][-1]
                    if tag == "DATE":
                        res["date"] = value
                    elif tag == "ADDR":
                        current_level2 = "ADDR"
                elif current_level1 == "IMMI":
                    if tag == "DATE":
                        indi["immigration"]["date"] = value
                    elif tag == "PLAC":
                        indi["immigration"]["place"] = value
                # Capture fields for ALL event tags
                elif current_level1 in ("CENS", "EDUC", "BAPM", "CHR", "CONF", "FCOM", "EMIG", "NATI", "RELI", "DSCR", "EVEN"):
                    if indi["events"] and indi["events"][-1].get("tag") == current_level1 or (current_level1 == "EVEN" and indi["events"][-1].get("tag") == "EVEN"):
                        evt = indi["events"][-1]
                        if tag == "DATE":
                            evt["date"] = value
                        elif tag == "PLAC":
                            evt["place"] = value
                        elif tag == "AGE":
                            evt["age"] = value
                        elif tag == "NOTE":
                            evt["note"] = value
                        elif tag == "CAUS":
                            evt["cause"] = value
                        elif tag == "ADDR":
                            evt["address"] = value
                        elif tag == "EMAIL":
                            evt["email"] = value
                        elif tag == "WWW":
                            evt["www"] = value
                        elif tag == "TYPE":
                            # For EVEN events, capture the TYPE as the event type
                            evt["type"] = translate_event_type(value)
                elif current_level1 == "NOTE":
                    if tag == "CONC":
                        clean = clean_html(value)
                        if indi["notes"] and clean:
                            indi["notes"][-1] += " " + clean

            elif level == 3:
                if current_level1 == "RESI" and current_level2 == "ADDR" and indi["residences"]:
                    res = indi["residences"][-1]
                    if tag == "ADR1":
                        res["address"] = value
                    elif tag == "ADR2":
                        res["address2"] = value
                    elif tag == "CITY":
                        res["city"] = value
                    elif tag == "CTRY":
                        res["country"] = value

        elif current_record == "FAM" and current_id:
            fam = families[current_id]
            if level == 1:
                current_level1 = tag
                if tag == "HUSB":
                    fam["husband"] = value
                elif tag == "WIFE":
                    fam["wife"] = value
                elif tag == "CHIL":
                    fam["children"].append(value)
                elif tag == "MARR":
                    current_level1 = "MARR"
                elif tag == "DIV":
                    current_level1 = "DIV"
            elif level == 2 and current_level1 == "MARR":
                if tag == "DATE":
                    fam["marriage"]["date"] = value
                elif tag == "PLAC":
                    fam["marriage"]["place"] = value
            elif level == 2 and current_level1 == "DIV":
                if tag == "DATE":
                    fam["divorce"]["date"] = value
                elif tag == "PLAC":
                    fam["divorce"]["place"] = value
                elif tag == "NOTE":
                    fam["divorce"]["note"] = value

    return {"individuals": individuals, "families": families}


def resolve_relationships(data: dict) -> list:
    """Resuelve las relaciones y genera una lista limpia de personas."""
    individuals = data["individuals"]
    families = data["families"]

    def get_name(ref):
        if ref and ref in individuals:
            return individuals[ref]["name"]
        return None

    people = []
    for indi_id, indi in individuals.items():
        person = {
            "id": indi_id,
            "name": indi["name"],
            "given_name": indi["given_name"],
            "surname": indi["surname"],
            "sex": indi["sex"],
        }

        # Birth, death, etc.
        if indi["birth"]:
            person["birth"] = indi["birth"]
        if indi["death"]:
            person["death"] = indi["death"]
        if indi["baptism"]:
            person["baptism"] = indi["baptism"]
        if indi["burial"]:
            person["burial"] = indi["burial"]
        if indi["occupations"]:
            person["occupations"] = indi["occupations"]
        if indi["residences"]:
            person["residences"] = indi["residences"]

        # Extract military events from generic events and remove from events array
        military_events = []
        remaining_events = []
        for evt in indi["events"]:
            if evt.get("type") in ("Alistamiento Militar", "Servicio Militar"):
                mil_entry = {
                    "description": evt.get("description", ""),
                    "date": evt.get("date", ""),
                    "place": evt.get("place", "")
                }
                military_events.append(mil_entry)
            else:
                remaining_events.append(evt)

        indi["military"].extend(military_events)
        indi["events"] = remaining_events

        if indi["military"]:
            person["military"] = indi["military"]
        if indi["anecdotes"]:
            person["anecdotes"] = indi["anecdotes"]
        if indi["events"]:
            person["events"] = indi["events"]
        if indi["immigration"]:
            person["immigration"] = indi["immigration"]
        if indi["notes"]:
            person["notes"] = indi["notes"]

        # Photos - only keep ones with URLs
        photos = [p for p in indi["photos"] if "url" in p]
        if photos:
            person["photos"] = photos

        # Resolve parents
        if indi["family_child"] and indi["family_child"] in families:
            fam = families[indi["family_child"]]
            father = get_name(fam["husband"])
            mother = get_name(fam["wife"])
            if father:
                person["father"] = father
                person["father_id"] = fam["husband"]
            if mother:
                person["mother"] = mother
                person["mother_id"] = fam["wife"]

        # Resolve spouses and children
        spouses = []
        children = []
        for fam_ref in indi["family_spouse"]:
            if fam_ref not in families:
                continue
            fam = families[fam_ref]
            # Spouse
            if indi["sex"] == "M" and fam["wife"]:
                spouse_name = get_name(fam["wife"])
                if spouse_name:
                    spouse_entry = {"name": spouse_name, "id": fam["wife"]}
                    if fam["marriage"]:
                        spouse_entry["marriage"] = fam["marriage"]
                    if fam["divorce"]:
                        spouse_entry["divorce"] = fam["divorce"]
                    spouses.append(spouse_entry)
            elif indi["sex"] == "F" and fam["husband"]:
                spouse_name = get_name(fam["husband"])
                if spouse_name:
                    spouse_entry = {"name": spouse_name, "id": fam["husband"]}
                    if fam["marriage"]:
                        spouse_entry["marriage"] = fam["marriage"]
                    if fam["divorce"]:
                        spouse_entry["divorce"] = fam["divorce"]
                    spouses.append(spouse_entry)
            # Children
            for child_ref in fam["children"]:
                child_name = get_name(child_ref)
                if child_name:
                    children.append({"name": child_name, "id": child_ref})

        if spouses:
            person["spouses"] = spouses
        if children:
            person["children"] = children

        # Clean empty dicts
        person = {k: v for k, v in person.items() if v or v == 0}
        people.append(person)

    return people


def build_family_tree_json(gedcom_path: str, output_path: str):
    """Parsea GEDCOM y guarda JSON estructurado."""
    print(f"Parseando {gedcom_path}...")
    data = parse_gedcom(gedcom_path)
    print(f"  {len(data['individuals'])} individuos, {len(data['families'])} familias")

    print("Resolviendo relaciones...")
    people = resolve_relationships(data)

    result = {
        "total_people": len(people),
        "total_families": len(data["families"]),
        "people": people,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"JSON guardado en {output_path}")
    print(f"  Tamaño: {output.stat().st_size / 1024:.1f} KB")
    return result


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    # Use the most recent GEDCOM file (excluding site380341641-tree5-20260324_signed.ged which is outdated)
    docs_dir = base / "docs"
    ged_files = [f for f in sorted(docs_dir.glob("*.ged"), key=lambda x: x.stat().st_mtime, reverse=True)
                 if not f.name.startswith("site380341641-tree5-20260324")]
    if not ged_files:
        print("ERROR: No GEDCOM file found (site380341641-tree5-20260324_signed.ged is too old, use a recent export)")
        sys.exit(1)
    gedcom = ged_files[0]
    output = base / "data" / "family_tree.json"
    build_family_tree_json(str(gedcom), str(output))
