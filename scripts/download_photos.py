"""Descarga fotos del GEDCOM a carpeta local y actualiza el JSON."""

from typing import Optional
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def download_photo(url: str, photos_dir: Path) -> Optional[str]:
    """Descarga una foto y devuelve el nombre del archivo local."""
    # Generate filename from URL hash to avoid duplicates
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    # Extract extension from URL
    ext = "jpg"
    if ".png" in url.lower():
        ext = "png"
    elif ".gif" in url.lower():
        ext = "gif"
    filename = f"{url_hash}.{ext}"
    filepath = photos_dir / filename

    if filepath.exists():
        return filename

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            if len(data) < 100:  # Too small, likely an error
                return None
            with open(filepath, "wb") as f:
                f.write(data)
        return filename
    except Exception as e:
        print(f"  Error descargando {url[:80]}...: {e}")
        return None


def main():
    base = Path(__file__).parent.parent
    json_path = base / "data" / "family_tree.json"
    photos_dir = base / "data" / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Collect all unique URLs and their references
    url_to_refs = {}  # url -> [(person_index, photo_index), ...]
    for pi, person in enumerate(data["people"]):
        for phi, photo in enumerate(person.get("photos", [])):
            url = photo.get("url")
            if url:
                if url not in url_to_refs:
                    url_to_refs[url] = []
                url_to_refs[url].append((pi, phi))

    total = len(url_to_refs)
    print(f"Descargando {total} fotos únicas...")

    downloaded = 0
    failed = 0
    skipped = 0

    def do_download(url):
        return url, download_photo(url, photos_dir)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(do_download, url): url for url in url_to_refs}
        for i, future in enumerate(as_completed(futures), 1):
            url, filename = future.result()
            if filename:
                # Update all references to this URL
                for pi, phi in url_to_refs[url]:
                    data["people"][pi]["photos"][phi]["local_file"] = filename
                downloaded += 1
            else:
                failed += 1
            if i % 50 == 0 or i == total:
                print(f"  Progreso: {i}/{total} ({downloaded} OK, {failed} errores)")

    # Save updated JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nCompletado: {downloaded} descargadas, {failed} errores")
    print(f"JSON actualizado en {json_path}")


if __name__ == "__main__":
    main()
