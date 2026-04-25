"""Parser GEDCOM → JSON estructurado para el árbol genealógico Godes."""

import html
import json
import re
import sys
from pathlib import Path


def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities (for simple fields, not notes)."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_note_html(raw: str) -> str:
    """Clean Draft.js HTML from biographical notes, preserving meaningful content.

    Preserves: line breaks, <b>, <i>, <strong>, <em>, <u>, <a href>, bare URLs.
    Removes: Draft.js divs/spans, CSS classes, inline styles, data-* attributes.
    """
    if not raw or not raw.strip():
        return ""

    # 1. Preserve <a> links — extract and replace with placeholders
    links = []
    def save_link(m):
        href = m.group(1)
        text = m.group(2)
        idx = len(links)
        links.append((href, text))
        return f"\x00LINK{idx}\x00"
    raw = re.sub(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', save_link, raw, flags=re.DOTALL | re.IGNORECASE)

    # 2. Preserve inline formatting with placeholders
    FORMAT_TAGS = {'b': 'B', 'i': 'I', 'strong': 'STRONG', 'em': 'EM', 'u': 'U'}
    for tag_name, placeholder in FORMAT_TAGS.items():
        raw = re.sub(rf'<{tag_name}\b[^>]*>', f'\x00O{placeholder}\x00', raw, flags=re.IGNORECASE)
        raw = re.sub(rf'</{tag_name}>', f'\x00C{placeholder}\x00', raw, flags=re.IGNORECASE)

    # 3. Convert block boundaries to newlines
    raw = re.sub(r'<br\b[^>]*/?\s*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<hr\b[^>]*/?\s*>', '\n---\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</(?:div|p|tr|blockquote)>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</t[dh]>', '  ', raw, flags=re.IGNORECASE)

    # 4. Strip all remaining HTML tags
    raw = re.sub(r'<[^>]*>', '', raw)

    # 5. Decode HTML entities (now that split entities are reunited)
    # Loop to handle double-encoded entities: &amp;lt; → &lt; → <
    prev = None
    while prev != raw:
        prev = raw
        raw = html.unescape(raw)
    # After full decoding, any newly-revealed tags must also be processed
    # Re-apply block boundary conversion and tag stripping on decoded content
    raw = re.sub(r'<br\b[^>]*/?\s*>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<hr\b[^>]*/?\s*>', '\n---\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</(?:div|p|tr|blockquote)>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</t[dh]>', '  ', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<[^>]*>', '', raw)

    # 6. Clean up whitespace
    raw = raw.replace('\u00a0', ' ')           # &nbsp; → regular space
    raw = re.sub(r'[ \t]+', ' ', raw)          # collapse horizontal whitespace
    raw = re.sub(r' *\n *', '\n', raw)         # trim spaces around newlines
    raw = re.sub(r'\n{3,}', '\n\n', raw)       # max 2 consecutive newlines

    # 7. Restore inline formatting placeholders
    for tag_name, placeholder in FORMAT_TAGS.items():
        raw = raw.replace(f'\x00O{placeholder}\x00', f'<{tag_name}>')
        raw = raw.replace(f'\x00C{placeholder}\x00', f'</{tag_name}>')

    # 8. Restore links with target="_blank"
    for idx, (href, text) in enumerate(links):
        # Strip any HTML tags inside link text (e.g. <bdi style="...">, <span style="...">)
        clean_text = re.sub(r'<[^>]*>', '', text).strip()
        raw = raw.replace(f'\x00LINK{idx}\x00', f'<a href="{href}" target="_blank" rel="noopener">{clean_text}</a>')

    # 9. Detect bare URLs not already in <a> tags and wrap them
    raw = re.sub(
        r'(?<!["\'>])(https?://[^\s<]+)',
        r'<a href="\1" target="_blank" rel="noopener">\1</a>',
        raw
    )

    # 10. Strip and check if empty
    raw = raw.strip()
    # Skip notes that are empty or only whitespace/nbsp
    if not raw or re.match(r'^[\s\u00a0]*$', raw):
        return ""

    return raw


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
    # Track raw note accumulation for the current INDI
    _in_note_block = False  # True when inside a 1 NOTE block

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        i += 1

        # Parse level, tag, value
        match = re.match(r"^(\d+)\s+(@\w+@)?\s*(\w+)\s*(.*)?$", line)
        if not match:
            # Non-standard line: if inside a NOTE block, it's a raw HTML continuation
            if _in_note_block and current_record == "INDI" and current_id:
                indi = individuals[current_id]
                if indi.get("_raw_notes"):
                    indi["_raw_notes"][-1] += line
            continue

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3)
        value = (match.group(4) or "").strip()

        if level == 0:
            current_level1 = None
            current_level2 = None
            _in_note_block = False
            if tag == "INDI":
                current_id = xref
                current_record = "INDI"
                individuals[current_id] = {
                    "id": current_id,
                    "name": "",
                    "given_name": "",
                    "surname": "",
                    "nickname": "",
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
                    "_raw_notes": [],
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
                    "partnership": {},
                }
            else:
                current_record = None
                current_id = None
            continue

        if current_record == "INDI" and current_id:
            indi = individuals[current_id]
            if level == 1:
                if tag != "NOTE":
                    _in_note_block = False
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
                    if value.upper() == "Y":
                        indi["death"]["confirmed"] = True
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
                    indi["_raw_notes"].append(value)
                    _in_note_block = True
                elif tag == "OBJE":
                    _in_note_block = False
                    current_level1 = "OBJE"
                    indi["photos"].append({})

            elif level == 2:
                current_level2 = tag
                if current_level1 == "NAME":
                    if tag == "GIVN":
                        indi["given_name"] = value
                    elif tag == "SURN":
                        indi["surname"] = value
                    elif tag == "NICK":
                        indi["nickname"] = value
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
                        if indi.get("_raw_notes"):
                            # Use raw match group (not stripped) — CONC joins at arbitrary byte boundaries
                            raw_value = match.group(4) or ""
                            indi["_raw_notes"][-1] += raw_value

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
                    if value == "Y":
                        fam["divorce"]["confirmed"] = True
                elif tag == "EVEN":
                    current_level1 = "EVEN"
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
            elif level == 2 and current_level1 == "EVEN":
                if tag == "TYPE" and value == "MYHERITAGE:REL_PARTNERS":
                    # Mark this as a partnership family
                    fam["partnership"]["type"] = "partners"
                elif tag == "DATE":
                    fam["partnership"]["date"] = value

    # Post-processing: clean accumulated raw notes
    for indi in individuals.values():
        cleaned = []
        for raw in indi.pop("_raw_notes", []):
            result = clean_note_html(raw)
            if result:
                cleaned.append(result)
        indi["notes"] = cleaned

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
            "nickname": indi["nickname"] or None,
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
                    if fam["partnership"]:
                        spouse_entry["partnership"] = fam["partnership"]
                    spouses.append(spouse_entry)
            elif indi["sex"] == "F" and fam["husband"]:
                spouse_name = get_name(fam["husband"])
                if spouse_name:
                    spouse_entry = {"name": spouse_name, "id": fam["husband"]}
                    if fam["marriage"]:
                        spouse_entry["marriage"] = fam["marriage"]
                    if fam["divorce"]:
                        spouse_entry["divorce"] = fam["divorce"]
                    if fam["partnership"]:
                        spouse_entry["partnership"] = fam["partnership"]
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
