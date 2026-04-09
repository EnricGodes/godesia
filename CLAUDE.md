# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Godesia is a genealogical chatbot for the Godes family. It answers natural language questions (in Catalan, Spanish, and English) about a family tree of 922 people spanning the 19th and 20th centuries, primarily in Barcelona.

The app uses a two-tier query system:
1. **QueryRouter** — regex-based pattern matching that resolves questions directly from SQLite (free, instant)
2. **QueryEngine** — LLM fallback (Claude Haiku) for complex questions that can't be pattern-matched (requires ANTHROPIC_API_KEY, costs ~0.3 cents/query, needs user confirmation)

## Project Structure

```
/
├── backend/
│   ├── app.py                    — FastAPI server, API routes
│   ├── database.py               — SQLite schema, connection, query helpers
│   ├── query_router.py           — Regex-based query routing (~20 patterns)
│   ├── query_engine.py           — LLM query engine with context reduction
│   ├── gedcom_parser.py          — GEDCOM file parser
│   ├── migrate_json_to_sqlite.py — JSON → SQLite migration script
│   ├── sync_photos.py            — Regenerate profile photos from photo metadata
│   └── requirements.txt
├── frontend/
│   ├── index.html                — Chat interface
│   ├── app.js                    — Frontend logic
│   ├── style.css                 — Styling
│   ├── tree.html                 — Family tree visualization
│   └── tree.js                   — Tree rendering logic
├── data/
│   ├── godesia.db                — SQLite database (922 people, 306 marriages)
│   ├── family_tree.json          — Source data (1.3MB, gitignored)
│   └── photos/                   — 1000+ JPEG images (gitignored)
├── docs/
│   └── *.ged                     — GEDCOM source file
└── scripts/
    └── download_photos.py        — Photo download utility
```

## Local Development

```bash
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn app:app --port 8000
```

Then open http://localhost:8000 in your browser.

For LLM-powered queries, set `ANTHROPIC_API_KEY` in your environment before starting.

## Database

SQLite with WAL mode. Tables: `people`, `marriages`, `children`, `occupations`, `residences`, `photos`, `notes`.

To rebuild the database from source JSON:
```bash
cd backend
python3 migrate_json_to_sqlite.py
```

## API Endpoints

- `POST /api/query` — Main query endpoint (routes to DB or asks for LLM confirmation)
- `POST /api/query/confirm` — Execute LLM query after user confirms
- `GET /api/search?q=<name>` — Search people by name (autocomplete)
- `GET /api/tree/{person_id}` — Genealogical tree data centered on a person
- `GET /api/birthdays` — Birthdays in the next 7 days
- `GET /api/stats` — Total people and families count

## Key Constraints

- The QueryRouter handles Catalan, Spanish, and English question patterns
- Name matching uses case-insensitive SQL LIKE with `%` wildcards
- GEDCOM dates have special formats (ABT, BEF, AFT, BET...AND, FROM...TO)
- People born after 1900 with no death record are marked as `is_alive`
- The LLM engine builds reduced context (only relevant people + 2 generations of relatives) to keep costs low

## Profile Photo Selection Algorithm

Each person's profile photo is selected from the `photos` table using a 5-level priority algorithm. This is implemented in `database.py:update_all_photo_files()` and ensures photos are consistently assigned.

**Selection priority:**
1. `photo_tags.is_primary = 1` (highest priority — official MyHeritage primary)
2. `photos.is_prim_cutout = 1 AND photos.is_personal_photo = 1` (personal primary cutout)
3. `photos.is_prim_cutout = 1` (any primary cutout)
4. `photos.is_cutout = 1` (any cutout)
5. Any non-PDF photo (fallback)

**GEDCOM source flags:**
- `_PRIM Y`: Official MyHeritage primary photo (→ `photo_tags.is_primary`)
- `_PRIM_CUTOUT Y`: Official MyHeritage primary cutout (→ `photos.is_prim_cutout`)
- `_PERSONALPHOTO Y`: Personal photo (→ `photos.is_personal_photo`)

**Examples:**
- **I16** (Artur Godes Hurtado): `000132_9993585rac49e6n59h867t_V.jpg` (has `_PRIM_CUTOUT Y` + `_PERSONALPHOTO Y`)
- **I118** (Enric Godes Maté): `500437_181219rgo60418u59d7hk6_A.jpg` (has `_PRIM Y`)
- **I11** (Ernest Godes Hurtado): `000065_7080186cj59ek8u954c93m_V.jpg` (has `_PRIM_CUTOUT Y` + `_PERSONALPHOTO Y`)

### Ensuring Profile Photos Are Never Lost

**Critical architecture:** `people.photo_file` is derived from photo metadata and MUST be regenerated whenever the `photos` or `photo_tags` tables are updated. Three ways this happens:

1. **After full GEDCOM import:** `python3 migrate_json_to_sqlite.py` automatically calls `update_all_photo_files()`
2. **Manual resync:** `python3 sync_photos.py` (standalone script, no arguments needed)
3. **Via API:** `POST /api/admin/sync-photos` (programmatic access)

**If profile photos ever disappear:**
- Run `python3 backend/sync_photos.py` from the project root
- This regenerates `people.photo_file` for all 362+ people with photos
- The dossier page will immediately show correct photos again

**Never run just photo metadata updates without syncing.** Always follow with one of the three options above to ensure `people.photo_file` is regenerated.

## Face Detection Boxes (Green Overlays)

When viewing the photo gallery (Memoria Visual), green rectangles appear over the central person's face in photos where they're detected. These are called **face boxes**.

**How it works:**
- Each person tagged in a photo has a `_POSITION` coordinate in GEDCOM: `x1 y1 x2 y2` (pixel boundaries of their face)
- This position is stored **per-person** in the `photo_tags` table (NOT globally in photos)
- The frontend JavaScript function `applyFaceBox()` renders the green overlay box when the image loads
- Each person only sees their own face boxes, not other people's positions in group photos

**Example:**
- Photo `500012_545576g614boe6078m35n3_R.jpg` is a group photo
- I16 (Artur) in that photo has position `483 370 566 481` → green box at those coordinates for I16
- Other people in the same photo have different positions → their face boxes only appear when viewing their own dossier

**Critical:** Position data is stored in `photo_tags.position` (linked to person_id), not in `photos.position`. If face boxes show random people or wrong positions, verify that the query in `database.py` uses `photo_tags.position` not `photos.position`.

## Git Workflow

This project uses GitHub (EnricGodes/godesia) for version control. As work is completed, commit changes with clean, descriptive commit messages and push to GitHub.
