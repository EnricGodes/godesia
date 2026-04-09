#!/usr/bin/env python3
"""
Synchronize photo metadata and update photo_file for all people.

This script:
1. Updates photo_count and photo_file for all people
2. Ensures profile photo selection algorithm is applied consistently
3. Should be run after any photos table updates

Usage:
    python3 sync_photos.py

This ensures profile photos are NEVER lost, regardless of how photos are updated.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database import get_connection, update_all_photo_files


def sync():
    """Synchronize all photo metadata."""
    db_path = Path(__file__).parent.parent / "data" / "godesia.db"

    print(f"Sincronizando fotos desde {db_path}...")
    conn = get_connection(str(db_path))

    try:
        updated = update_all_photo_files(conn)
        print(f"✓ Actualizadas fotos de perfil para {updated} personas")
    except Exception as e:
        print(f"✗ Error actualizando fotos: {e}")
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(sync())
