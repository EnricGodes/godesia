# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A location-based historical expedition through 19th-century Barcelona, tracing the Godes Caballeria family. Static HTML, no build system.

## Project Structure

```
/
├── index.html                         — Landing page (entry point)
├── experiencia/                       — Historical expedition stops (from Stitch)
│   ├── navegacion-1.html              — Walking directions to Fonollar 20
│   ├── carrer-fonollar-20.html        — Carrer del Fonollar 20 stop
│   ├── navegacion-2.html              — Walking directions to Mestres Casals i Martorell 14
│   ├── claveguera-14.html             — Claveguera 14 stop (1860-1864)
│   ├── navegacion-3.html              — Walking directions to Plaça de Sant Agustí Vell 19
│   ├── cronologia.html                — Visual timeline of family houses and events
│   └── restaurant.html                — GPS navigation to Restaurant La Fonda (final destination)
├── navegacion/                        — GPS navigation app
│   ├── destino.html                   — Destination input with geocoding
│   └── ruta.html                      — Step-by-step turn-by-turn navigation
└── docs/                             — Documentation
    ├── design-system.md               — L'Eixample Chronology design system
    └── README.md
```

### User flow
`index.html` → `experiencia/navegacion-1.html` → `experiencia/carrer-fonollar-20.html` → `experiencia/navegacion-2.html` → `experiencia/claveguera-14.html` → `experiencia/navegacion-3.html` → ... → `experiencia/restaurant.html`

## Local Development

To serve the site locally, use Python's built-in HTTP server:

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000 in your browser.

## Git Workflow

This project uses GitHub (EnricGodes/cases-godes) for version control. **As work is completed, commit changes to git with clean, descriptive commit messages and push to GitHub.** This ensures we never lose work and maintain a clear history of changes. Each commit message should explain what changed and why, making it easy to understand the project's evolution.

## Key Constraints

- Static HTML only — no build process or transpilation needed
- No package.json or npm dependencies
- Changes are immediately visible when the HTML files are modified
