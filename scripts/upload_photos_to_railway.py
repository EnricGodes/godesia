#!/usr/bin/env python3
"""
Upload local photos to the Railway volume via the admin endpoint.
The endpoint skips files that already exist, so re-running is safe.

Usage:
    python3 scripts/upload_photos_to_railway.py                       # data/photos/ (nivel raíz)
    python3 scripts/upload_photos_to_railway.py --subdir emili-godes  # data/photos/emili-godes/
    python3 scripts/upload_photos_to_railway.py --subdir emili-godes --new-only  # solo las que faltan
"""

import argparse
import sys
import requests
from pathlib import Path

BASE_URL = "https://godesia.up.railway.app"
ENDPOINT = f"{BASE_URL}/api/admin/upload-photos"
LIST_ENDPOINT = f"{BASE_URL}/api/admin/list-photos"
PHOTOS_DIR = Path(__file__).parent.parent / "data" / "photos"
BATCH_SIZE = 10  # conservador para no exceder límites de tamaño de request
EXT = (".jpg", ".jpeg", ".png")


def local_dir(subdir: str) -> Path:
    return PHOTOS_DIR / subdir if subdir else PHOTOS_DIR


def get_all_photos(subdir: str) -> list[Path]:
    d = local_dir(subdir)
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in EXT)


def get_new_photos(subdir: str) -> list[Path]:
    """Return local photos not yet present on the Railway volume (asks the server)."""
    r = requests.get(LIST_ENDPOINT, params={"subdir": subdir} if subdir else None, timeout=60)
    r.raise_for_status()
    remote = set(r.json()["files"])
    return [p for p in get_all_photos(subdir) if p.name not in remote]


def upload_batch(paths: list[Path], subdir: str) -> dict:
    files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in paths]
    data = {"subdir": subdir} if subdir else None
    r = requests.post(ENDPOINT, files=files, data=data, timeout=180)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subdir", default="", help="Subcarpeta bajo data/photos/ (p. ej. emili-godes)")
    parser.add_argument("--new-only", action="store_true", help="Solo fotos que aún no están en Railway")
    args = parser.parse_args()

    photos = get_new_photos(args.subdir) if args.new_only else get_all_photos(args.subdir)
    where = f"data/photos/{args.subdir}" if args.subdir else "data/photos"
    if not photos:
        print(f"No hay fotos para subir en {where}.")
        return

    print(f"Fotos a subir desde {where}: {len(photos)}")
    total_saved = 0
    total_skipped = 0

    for i in range(0, len(photos), BATCH_SIZE):
        batch = photos[i:i + BATCH_SIZE]
        end = min(i + BATCH_SIZE, len(photos))
        print(f"  Lote {i+1}-{end} / {len(photos)} ...", end=" ", flush=True)
        try:
            result = upload_batch(batch, args.subdir)
            total_saved += result["saved"]
            total_skipped += result["skipped"]
            print(f"ok ({result['saved']} guardadas, {result['skipped']} ya existían)")
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    print(f"\nFinalizado: {total_saved} subidas, {total_skipped} ya existían.")


if __name__ == "__main__":
    main()
