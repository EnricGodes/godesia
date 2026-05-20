"""Backfill SHA256 + perceptual hash + dimensions for every photo on disk.

Run once after the schema migration. Idempotent: skips rows already filled.
Usage:
    cd backend && python3 dedup_backfill_hashes.py [--force] [--limit N]
"""

import argparse
import hashlib
import sqlite3
import sys
import time
from pathlib import Path

try:
    from PIL import Image
    import imagehash
except ImportError as e:
    print(f"Missing dependency: {e}. Run: pip3 install Pillow imagehash")
    sys.exit(1)

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "data" / "godesia.db"
PHOTOS_DIR = BASE / "data" / "photos"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def phash_and_dims(path: Path):
    """Return (phash_str, width, height) or (None, None, None) if not image / unreadable."""
    if path.suffix.lower() == ".pdf":
        return None, None, None
    try:
        with Image.open(path) as img:
            w, h = img.size
            ph = str(imagehash.dhash(img, hash_size=8))
        return ph, w, h
    except Exception:
        return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Recompute even if hash already present")
    ap.add_argument("--limit", type=int, default=0,
                    help="Process at most N rows (0 = all)")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.force:
        rows = conn.execute("SELECT id, filename FROM photos").fetchall()
    else:
        rows = conn.execute(
            "SELECT id, filename FROM photos WHERE sha256 IS NULL OR (phash IS NULL AND filename NOT LIKE '%.pdf')"
        ).fetchall()

    if args.limit:
        rows = rows[: args.limit]

    total = len(rows)
    print(f"Photos to process: {total}")
    if not total:
        return

    t0 = time.time()
    done = missing = errors = 0
    cur = conn.cursor()
    for i, row in enumerate(rows, 1):
        fpath = PHOTOS_DIR / row["filename"]
        if not fpath.exists():
            missing += 1
            continue
        try:
            sha = sha256_of(fpath)
            ph, w, h = phash_and_dims(fpath)
            cur.execute(
                "UPDATE photos SET sha256=?, phash=?, width=?, height=? WHERE id=?",
                (sha, ph, w, h, row["id"]),
            )
            done += 1
        except Exception as exc:
            errors += 1
            print(f"  ERR {row['filename']}: {exc}")
        if i % 500 == 0:
            conn.commit()
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed else 0
            eta = (total - i) / rate if rate else 0
            print(f"  {i}/{total}  done={done} missing={missing} err={errors}  "
                  f"rate={rate:.0f}/s  eta={eta:.0f}s")

    conn.commit()
    conn.close()
    elapsed = time.time() - t0
    print(f"\nFinished in {elapsed:.1f}s — done={done} missing={missing} errors={errors}")


if __name__ == "__main__":
    main()
