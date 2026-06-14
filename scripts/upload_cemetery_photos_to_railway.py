#!/usr/bin/env python3
"""
Sube las fotos de nichos (data/cemetery_photos) al volumen de Railway vía el
endpoint admin. El endpoint salta las que ya existen, así re-ejecutar es seguro.

En Railway, data/ es un volumen persistente que tapa lo que venga del repo, por
eso estas fotos NO llegan por git: hay que subirlas directamente aquí.

Uso:
    python3 scripts/upload_cemetery_photos_to_railway.py             # solo las que faltan
    python3 scripts/upload_cemetery_photos_to_railway.py --all       # todas
"""

import argparse
import sys
import requests
from pathlib import Path

BASE_URL = "https://godesia.up.railway.app"
ENDPOINT = f"{BASE_URL}/api/admin/upload-cemetery-photos"
LIST_ENDPOINT = f"{BASE_URL}/api/admin/list-cemetery-photos"
PHOTOS_DIR = Path(__file__).parent.parent / "data" / "cemetery_photos"
EXTS = (".jpg", ".jpeg", ".png", ".webp")
BATCH_SIZE = 10


def get_all_photos() -> list[Path]:
    if not PHOTOS_DIR.exists():
        return []
    return sorted(p for p in PHOTOS_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS)


def get_new_photos() -> list[Path]:
    r = requests.get(LIST_ENDPOINT, timeout=60)
    r.raise_for_status()
    remote = set(r.json()["files"])
    return [p for p in get_all_photos() if p.name not in remote]


def upload_batch(paths: list[Path]) -> dict:
    files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in paths]
    r = requests.post(ENDPOINT, files=files, timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Subir todas (no solo las que faltan)")
    args = parser.parse_args()

    photos = get_all_photos() if args.all else get_new_photos()
    if not photos:
        print("No hay fotos de nichos para subir (Railway ya las tiene).")
        return

    print(f"Fotos de nichos a subir: {len(photos)}")
    total_saved = total_skipped = 0
    for i in range(0, len(photos), BATCH_SIZE):
        batch = photos[i:i + BATCH_SIZE]
        end = min(i + BATCH_SIZE, len(photos))
        print(f"  Lote {i+1}-{end} / {len(photos)} ...", end=" ", flush=True)
        try:
            res = upload_batch(batch)
            total_saved += res["saved"]
            total_skipped += res["skipped"]
            print(f"ok ({res['saved']} guardadas, {res['skipped']} ya existían)")
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    print(f"\nFinalizado: {total_saved} subidas, {total_skipped} ya existían.")


if __name__ == "__main__":
    main()
