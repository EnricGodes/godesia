#!/usr/bin/env python3
"""Extract NICK and _AKA fields from GEDCOM and update people table."""

import re
from pathlib import Path
from database import get_connection

def extract_nicknames_from_gedcom(gedcom_path):
    """Parse GEDCOM and extract NICK/_AKA for each person."""
    nicknames = {}

    with open(gedcom_path, 'r', encoding='utf-8', errors='replace') as f:
        current_person = None
        for line in f:
            line = line.rstrip('\r\n')

            # Detect person ID (0 @I123@ INDI)
            match = re.match(r'^0\s+(@I\d+@)\s+INDI', line)
            if match:
                current_person = match.group(1)
                nicknames[current_person] = None
                continue

            if not current_person:
                continue

            # Extract NICK or _AKA (1 or 2 level NICK value or 1 or 2 level _AKA value)
            match = re.match(r'^[12]\s+(?:NICK|_AKA)\s+(.+)$', line)
            if match:
                nickname = match.group(1).strip()
                if nickname:
                    nicknames[current_person] = nickname

    return nicknames

def update_nicknames_in_db(nicknames):
    """Update people table with nicknames."""
    conn = get_connection('data/godesia.db')
    updated = 0

    for person_id, nickname in nicknames.items():
        if nickname:
            conn.execute(
                "UPDATE people SET nickname = ? WHERE id = ?",
                (nickname, person_id)
            )
            updated += 1

    conn.commit()
    conn.close()

    return updated

if __name__ == '__main__':
    # Find the main GEDCOM file
    gedcom_path = Path('docs/site380341641-tree5-20260324_signed.ged')

    if not gedcom_path.exists():
        print(f"GEDCOM file not found: {gedcom_path}")
        exit(1)

    print(f"Reading nicknames from {gedcom_path}...")
    nicknames = extract_nicknames_from_gedcom(gedcom_path)

    nicknames_with_values = {k: v for k, v in nicknames.items() if v}
    print(f"Found {len(nicknames_with_values)} people with nicknames")

    if nicknames_with_values:
        print(f"Updating database...")
        updated = update_nicknames_in_db(nicknames)
        print(f"Updated {updated} people with nicknames")
    else:
        print("No nicknames found")
