#!/usr/bin/env python3
"""
Upload all local photos to the Railway volume via the admin endpoint.
The endpoint skips files that already exist, so re-running is safe.

Usage:
    python3 scripts/upload_photos_to_railway.py           # sube todas las fotos
    python3 scripts/upload_photos_to_railway.py --new-only  # solo las no trackeadas por git
"""

import argparse
import subprocess
import sys
import requests
from pathlib import Path

BASE_URL = "https://godesia.up.railway.app"
ENDPOINT = f"{BASE_URL}/api/admin/upload-photos"
PHOTOS_DIR = Path(__file__).parent.parent / "data" / "photos"
BATCH_SIZE = 10  # conservador para no exceder límites de tamaño de request


def get_all_photos() -> list[Path]:
    return sorted(p for p in PHOTOS_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))


def get_new_photos() -> list[Path]:
    """Return only photos not yet tracked by git."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "data/photos/"],
        capture_output=True, text=True,
        cwd=PHOTOS_DIR.parent.parent
    )
    return [PHOTOS_DIR.parent.parent / p.strip() for p in result.stdout.splitlines() if p.strip()]


def upload_batch(paths: list[Path]) -> dict:
    files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in paths]
    r = requests.post(ENDPOINT, files=files, timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-only", action="store_true", help="Solo fotos no trackeadas por git")
    args = parser.parse_args()

    photos = get_new_photos() if args.new_only else get_all_photos()
    if not photos:
        print("No hay fotos para subir.")
        return

    print(f"Fotos a subir: {len(photos)}")
    total_saved = 0
    total_skipped = 0

    for i in range(0, len(photos), BATCH_SIZE):
        batch = photos[i:i + BATCH_SIZE]
        end = min(i + BATCH_SIZE, len(photos))
        print(f"  Lote {i+1}-{end} / {len(photos)} ...", end=" ", flush=True)
        try:
            result = upload_batch(batch)
            total_saved += result["saved"]
            total_skipped += result["skipped"]
            print(f"ok ({result['saved']} guardadas, {result['skipped']} ya existían)")
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    print(f"\nFinalizado: {total_saved} subidas, {total_skipped} ya existían.")


if __name__ == "__main__":
    main()
