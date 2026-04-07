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

Each person's profile photo is selected from GEDCOM `OBJE` records based on these flags:
- `_PRIM Y`: Official MyHeritage primary photo (marked as primary in MyHeritage)
- `_PRIM_CUTOUT Y`: Official MyHeritage primary cutout/profile photo  
- `_PERSONALPHOTO Y`: Personal photo (marked as belonging to the individual)

**Selection priority** (in `backend/migrate_json_to_sqlite.py`):
1. `photo_tags.is_primary = 1` (highest priority)
2. `photos.is_prim_cutout = 1 AND photos.is_personal_photo = 1` (personal primary cutout)
3. `photos.is_prim_cutout = 1` (any primary cutout)
4. `photos.is_cutout = 1` (any cutout)
5. Any non-PDF photo (fallback)

**Examples:**
- **I16** (Artur Godes Hurtado): `000132_9993585rac49e6n59h867t_V.jpg` (has `_PRIM_CUTOUT Y` + `_PERSONALPHOTO Y`)
- **I118** (Enric Godes Maté): `500437_181219rgo60418u59d7hk6_A.jpg` (has `_PRIM Y` + `_CUTOUT Y`)
- **I11** (Ernest Godes Hurtado): `000065_7080186cj59ek8u954c93m_V.jpg` (has `_PRIM_CUTOUT Y` + `_PERSONALPHOTO Y`, not `500017` which only has `_PRIM_CUTOUT Y`)

The `sync_photo_catalog.py` script extracts these flags from GEDCOM and stores them in the `photos` table:
- `is_prim_cutout INTEGER` (from `_PRIM_CUTOUT Y`)
- `is_personal_photo INTEGER` (from `_PERSONALPHOTO Y`)

These columns must always exist in the `photos` table schema.

## Git Workflow

This project uses GitHub (EnricGodes/godesia) for version control. As work is completed, commit changes with clean, descriptive commit messages and push to GitHub.
