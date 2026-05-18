#!/usr/bin/env python3
"""Upload untracked/new photos to the Railway volume via the admin endpoint."""

import sys
import subprocess
import requests
from pathlib import Path

BASE_URL = "https://godesia.up.railway.app"
ENDPOINT = f"{BASE_URL}/api/admin/upload-photos"
PHOTOS_DIR = Path(__file__).parent.parent / "data" / "photos"
BATCH_SIZE = 20  # files per request


def get_remote_files() -> set:
    """Fetch list of files already on Railway."""
    r = requests.get(f"{BASE_URL}/photos/", timeout=30)
    # Can't list static dir — we'll rely on the endpoint's skip logic
    return set()


def get_new_photos() -> list[Path]:
    """Return photos not yet tracked by git (untracked in data/photos/)."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "data/photos/"],
        capture_output=True, text=True,
        cwd=PHOTOS_DIR.parent.parent
    )
    files = [PHOTOS_DIR.parent.parent / p.strip() for p in result.stdout.splitlines() if p.strip()]
    return files


def upload_batch(paths: list[Path]) -> dict:
    files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in paths]
    r = requests.post(ENDPOINT, files=files, timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    photos = get_new_photos()
    if not photos:
        print("No hay fotos nuevas para subir.")
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
