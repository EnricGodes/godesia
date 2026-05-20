"""Detect duplicate photos within each person and score which copy to keep.

Writes results to the `dedup_candidates` table (dropped & recreated each run).
Usage:
    python3 dedup_detect.py [--person @I500141@] [--dry-run]
"""

import argparse
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "data" / "godesia.db"

# Hamming-distance thresholds on 64-bit dHash
PHASH_AUTO = 3       # auto-apply when also same dimensions (re-encoded duplicates)
PHASH_BUCKET_B = 6   # ~90% similar
PHASH_BUCKET_C = 10  # ~85% similar


def phash_hamming(a: str, b: str) -> int:
    """Hamming distance between two hex pHash strings."""
    if not a or not b:
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return 999


def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = unicodedata.normalize("NFD", title)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)       # remove [Defunción] etc
    t = re.sub(r"\b(18|19|20)\d{2}\b", " ", t)  # strip 4-digit years
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def year_of(date_str: str) -> str:
    if not date_str:
        return ""
    m = re.search(r"\b(18|19|20)\d{2}\b", date_str)
    return m.group(0) if m else ""


def _position_is_meaningful(p) -> bool:
    """Return True if photo.position is a real face/object box, not a self-cover.
    A position covering ~the whole image (>80% area) adds no information."""
    pos = p["position"]
    if not pos:
        return False
    try:
        x1, y1, x2, y2 = (int(v) for v in pos.split())
    except (ValueError, AttributeError):
        return False
    w, h = p["width"], p["height"]
    if not w or not h:
        return True  # cannot judge → trust the position
    box_area = max(0, x2 - x1) * max(0, y2 - y1)
    img_area = w * h
    if img_area <= 0:
        return True
    return (box_area / img_area) < 0.80


def score_photo(p, has_primary_tag: bool) -> int:
    """Higher = more metadata = keep."""
    s = 0
    if p["date"]:
        s += 3
    if p["place"]:
        s += 2
    if p["photo_rin"]:
        s += 2
    for field in ("title", "note", "transcription"):
        if p[field]:
            s += 1
    if _position_is_meaningful(p):
        s += 1
    if p["is_document"] and p["doc_type"]:
        s += 3
    if p["doc_origin"] == "human":
        s += 2
    if p["parent_photo_id"]:
        s += 1
    if has_primary_tag:
        s += 1
    return s


def pick_winner(rows, primary_map):
    """Among >=2 rows, return (winner_id, [(loser_id, ..._info), ...]).

    primary_map: {photo_id: bool} — true if that photo has is_primary or is_prim_cutout tag.
    """
    # Build (score, row) list with tiebreakers
    doc_majority = sum(1 for r in rows if r["is_document"]) > len(rows) / 2

    def key(r):
        is_pdf = (r["filename"] or "").lower().endswith(".pdf")
        format_pref = 1 if (is_pdf == doc_majority) else 0
        dims = (r["width"] or 0) * (r["height"] or 0)
        # Resolution tier: bigger image wins. Pixel-count is the primary
        # signal of quality; metadata score breaks ties within the same tier.
        # Tier buckets bias toward "clearly bigger" rather than tiny pixel
        # differences so two similar-sized photos still compete on metadata.
        if dims == 0:
            dim_tier = 0          # PDFs, missing dims
        elif dims < 50_000:       # < ~220x220 — thumbnail
            dim_tier = 1
        elif dims < 250_000:      # < ~500x500 — small
            dim_tier = 2
        elif dims < 1_000_000:    # < ~1000x1000 — medium
            dim_tier = 3
        else:                     # >= ~1000x1000 — large
            dim_tier = 4
        return (
            dim_tier,
            score_photo(r, primary_map.get(r["id"], False)),
            format_pref,
            dims,
            r["filesize"] or 0,
            -r["id"],
        )

    sorted_rows = sorted(rows, key=key, reverse=True)
    winner = sorted_rows[0]
    losers = sorted_rows[1:]
    return winner, losers


def detect_for_person(conn, person_id):
    """Return list of (bucket, kept_row, drop_row, kept_score, drop_score, metric)."""
    rows = conn.execute("""
        SELECT p.*, pt.is_primary, pt.is_prim_cutout AS tag_prim_cutout
        FROM photos p
        JOIN photo_tags pt ON pt.photo_id = p.id
        WHERE pt.person_id = ?
    """, (person_id,)).fetchall()

    if len(rows) < 2:
        return []

    primary_map = {r["id"]: bool(r["is_primary"] or r["tag_prim_cutout"]) for r in rows}

    def excluded_pair(a, b):
        """True if (a,b) should never be considered duplicates."""
        # Direct parent-cutout relation
        if a["parent_photo_id"] == b["id"] or b["parent_photo_id"] == a["id"]:
            return True
        # One is a cutout, other is not — different roles in the photo hierarchy
        if bool(a["is_cutout"]) != bool(b["is_cutout"]):
            return True
        return False

    # Bucket A: identical SHA256 — exact bytes
    by_sha = defaultdict(list)
    for r in rows:
        if r["sha256"]:
            by_sha[r["sha256"]].append(r)
    groups_a = [g for g in by_sha.values() if len(g) > 1]

    handled = set()  # photo IDs already assigned to a bucket A group
    results = []
    for grp in groups_a:
        # Filter group: only keep mutually non-excluded members
        # Simple approach: drop exclusion-related members from the group entirely
        clean = [r for r in grp
                 if not any(excluded_pair(r, other) for other in grp if other["id"] != r["id"])]
        if len(clean) < 2:
            continue
        winner, losers = pick_winner(clean, primary_map)
        ws = score_photo(winner, primary_map.get(winner["id"], False))
        for loser in losers:
            ls = score_photo(loser, primary_map.get(loser["id"], False))
            results.append(("A", winner, loser, ws, ls, "sha256_exact"))
            handled.add(loser["id"])
        handled.add(winner["id"])

    # Bucket A extension: visually identical re-encodes (phash <= PHASH_AUTO
    # AND same width AND same height). Treated the same as SHA256-exact:
    # auto-applied by the endpoint, since the image content is effectively the same.
    candidates = [r for r in rows if r["id"] not in handled and r["phash"] and r["width"] and r["height"]]
    for i, ra in enumerate(candidates):
        if ra["id"] in handled:
            continue
        for rb in candidates[i + 1:]:
            if rb["id"] in handled:
                continue
            if excluded_pair(ra, rb):
                continue
            if ra["width"] != rb["width"] or ra["height"] != rb["height"]:
                continue
            dist = phash_hamming(ra["phash"], rb["phash"])
            if dist > PHASH_AUTO:
                continue
            winner, losers = pick_winner([ra, rb], primary_map)
            loser = losers[0]
            ws = score_photo(winner, primary_map.get(winner["id"], False))
            ls = score_photo(loser, primary_map.get(loser["id"], False))
            results.append(("A", winner, loser, ws, ls, f"phash_visual_d{dist}"))
            handled.add(loser["id"])
            handled.add(winner["id"])
            break  # winner consumed; move on

    # Remaining rows for B/C analysis (skip already-grouped)
    remaining = [r for r in rows if r["id"] not in handled]

    # Bucket B/C: pHash similarity + metadata corroboration
    # Quadratic pairwise — fine for per-person sets (typically <50 photos)
    seen_pair = set()
    for i, ra in enumerate(remaining):
        for rb in remaining[i + 1:]:
            if excluded_pair(ra, rb):
                continue
            if not ra["phash"] or not rb["phash"]:
                # Fall through to title-only check for PDFs/non-images
                title_match = (
                    normalize_title(ra["title"]) == normalize_title(rb["title"])
                    and normalize_title(ra["title"])
                    and year_of(ra["date"]) == year_of(rb["date"])
                )
                if title_match:
                    bucket = "C"
                    metric = "title+year"
                else:
                    continue
            else:
                dist = phash_hamming(ra["phash"], rb["phash"])
                title_norm_match = (
                    normalize_title(ra["title"]) == normalize_title(rb["title"])
                    and normalize_title(ra["title"])
                )
                size_a = ra["filesize"] or 0
                size_b = rb["filesize"] or 0
                size_close = size_a and size_b and abs(size_a - size_b) / max(size_a, size_b) < 0.10
                year_match = year_of(ra["date"]) == year_of(rb["date"]) and year_of(ra["date"])

                if dist <= PHASH_BUCKET_B and (title_norm_match or (size_close and year_match)):
                    bucket = "B"
                    metric = f"phash_d{dist}"
                elif dist <= PHASH_BUCKET_C or (title_norm_match and year_match):
                    bucket = "C"
                    metric = f"phash_d{dist}" if dist <= PHASH_BUCKET_C else "title+year"
                else:
                    continue

            winner, losers = pick_winner([ra, rb], primary_map)
            loser = losers[0]
            pair_key = (min(winner["id"], loser["id"]), max(winner["id"], loser["id"]))
            if pair_key in seen_pair:
                continue
            seen_pair.add(pair_key)
            ws = score_photo(winner, primary_map.get(winner["id"], False))
            ls = score_photo(loser, primary_map.get(loser["id"], False))
            results.append((bucket, winner, loser, ws, ls, metric))

    return results


def ensure_candidates_table(conn):
    conn.execute("DROP TABLE IF EXISTS dedup_candidates")
    conn.execute("""
        CREATE TABLE dedup_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT NOT NULL,
            bucket TEXT NOT NULL,
            kept_photo_id INTEGER NOT NULL,
            drop_photo_id INTEGER NOT NULL,
            kept_score INTEGER,
            drop_score INTEGER,
            metric TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", help="Only process a single person_id (e.g. @I500141@)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print results without writing dedup_candidates")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Exclude pairs the user has previously decided to keep both
    keep_pairs = set()
    try:
        for a, b in conn.execute("SELECT photo_id_a, photo_id_b FROM photo_dedup_keep_pairs"):
            keep_pairs.add((min(a, b), max(a, b)))
    except sqlite3.OperationalError:
        pass

    if args.person:
        persons = [args.person]
    else:
        persons = [row[0] for row in conn.execute(
            "SELECT DISTINCT person_id FROM photo_tags ORDER BY person_id"
        )]

    if not args.dry_run:
        ensure_candidates_table(conn)

    total_pairs = 0
    by_bucket = defaultdict(int)
    cur = conn.cursor()

    for pid in persons:
        pairs = detect_for_person(conn, pid)
        for bucket, winner, loser, ws, ls, metric in pairs:
            pair_key = (min(winner["id"], loser["id"]), max(winner["id"], loser["id"]))
            if pair_key in keep_pairs:
                continue
            total_pairs += 1
            by_bucket[bucket] += 1
            if args.dry_run or args.person:
                print(f"  [{bucket}] {pid}  drop=#{loser['id']} '{(loser['title'] or '')[:50]}' "
                      f"(score {ls}) ↔ keep=#{winner['id']} '{(winner['title'] or '')[:50]}' "
                      f"(score {ws})  {metric}")
            if not args.dry_run:
                cur.execute("""
                    INSERT INTO dedup_candidates
                    (person_id, bucket, kept_photo_id, drop_photo_id, kept_score, drop_score, metric)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (pid, bucket, winner["id"], loser["id"], ws, ls, metric))

    if not args.dry_run:
        conn.commit()

    conn.close()
    print(f"\nTotal pairs: {total_pairs}  (A={by_bucket['A']} B={by_bucket['B']} C={by_bucket['C']})")


if __name__ == "__main__":
    main()
