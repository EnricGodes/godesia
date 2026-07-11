#!/usr/bin/env python3
"""Genera frontend/locales/ui.es.json a partir del código.

Inventaria:
  - atributos data-i18n / data-i18n-html / data-i18n-placeholder /
    data-i18n-title / data-i18n-aria-label / data-i18n-alt en los HTML públicos
  - llamadas t('clave', params, 'fallback') en los JS públicos
    (t, _i18nT, _pmT) y en scripts inline
  - <title> de cada página pública como pages.{página}.meta_title

Conserva los valores ya existentes en ui.es.json (no pisa ediciones manuales)
y avisa de claves que desaparecen del código. Ejecutar tras añadir textos:
    python3 scripts/extract_ui_strings.py
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent.parent
FRONTEND = BASE / "frontend"
OUT = FRONTEND / "locales" / "ui.es.json"

EXCLUDED_PAGES = {
    "admin_geocoder.html", "index-css-backup.html",
    "preview.html", "preview_incremental.html", "test_router.html",
}
PUBLIC_JS = [
    "nav.js", "footer.js", "dashboard.js", "app.js", "dossier.js",
    "arbol2.js", "albums.js", "docs.js", "cementerios.js",
    "photo-modal.js", "mention-autocomplete.js",
]

ATTR_SOURCES = {
    "data-i18n": "text",
    "data-i18n-html": "html",
    "data-i18n-placeholder": "placeholder",
    "data-i18n-title": "title",
    "data-i18n-aria-label": "aria-label",
    "data-i18n-alt": "alt",
}

# t('key', null|{...}, 'fallback')  — fallback entre comillas simples con escapes
T_CALL = re.compile(
    r"(?:\b_i18nT|\b_pmT|\bt)\(\s*'([^']+)'\s*,\s*(?:null|\{[^{}]*\})\s*,\s*"
    r"'((?:[^'\\]|\\.)*)'\s*\)"
)

# Entradas que no se pueden extraer por regex (fallbacks no literales)
MANUAL = {
    "dates.months": ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
                      "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "dates.months_short": ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
                            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
    "pages.dossier.quay_labels": ["No fiable", "Cuestionable", "Evidencia secundaria",
                                   "Evidencia directa", "Primaria y directa"],
}


def set_nested(d, dotted, value):
    parts = dotted.split(".")
    node = d
    for p in parts[:-1]:
        node = node.setdefault(p, {})
        if not isinstance(node, dict):
            raise ValueError(f"Conflicto de claves en {dotted}: {p} no es objeto")
    node.setdefault(parts[-1], value)


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def collect():
    entries = {}  # dotted key -> es value

    for page in sorted(FRONTEND.glob("*.html")):
        if page.name in EXCLUDED_PAGES:
            continue
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")

        title = soup.find("title")
        if title and title.get_text(strip=True):
            entries.setdefault(f"pages.{page.stem}.meta_title", title.get_text(strip=True))

        for attr, source in ATTR_SOURCES.items():
            for el in soup.select(f"[{attr}]"):
                key = el.get(attr)
                if not key:
                    continue
                if source == "text":
                    value = el.get_text(strip=True)
                elif source == "html":
                    value = el.decode_contents().strip()
                else:
                    value = el.get(source, "")
                if key in entries and entries[key] != value:
                    print(f"  ⚠ {key}: valores distintos ('{entries[key][:40]}' vs '{value[:40]}' en {page.name})")
                entries.setdefault(key, value)

        # t() en scripts inline de la página
        for m in T_CALL.finditer(page.read_text(encoding="utf-8")):
            entries.setdefault(m.group(1), m.group(2).replace("\\'", "'"))

    for js in PUBLIC_JS:
        path = FRONTEND / js
        if not path.exists():
            continue
        for m in T_CALL.finditer(path.read_text(encoding="utf-8")):
            key, value = m.group(1), m.group(2).replace("\\'", "'")
            if key in entries and entries[key] != value:
                print(f"  ⚠ {key}: valores distintos ('{entries[key][:40]}' vs '{value[:40]}' en {js})")
            entries.setdefault(key, value)

    entries.update({k: v for k, v in MANUAL.items() if k not in entries})
    return entries


def main():
    entries = collect()

    existing = {}
    if OUT.exists():
        try:
            existing = flatten(json.loads(OUT.read_text(encoding="utf-8")))
        except Exception:
            pass
    existing.pop("_meta.lang", None)
    existing.pop("_meta.version", None)

    result = {"_meta": {"lang": "es", "version": 1}}
    for key in sorted(entries):
        # el valor existente (posible edición manual) tiene prioridad
        value = existing.get(key, entries[key])
        set_nested(result, key, value)

    stale = sorted(set(existing) - set(entries))
    stale = [k for k in stale if existing.get(k)]
    if stale:
        print(f"  ℹ {len(stale)} claves en ui.es.json ya no aparecen en el código:")
        for k in stale[:20]:
            print(f"    - {k}")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ {OUT.relative_to(BASE)}: {len(entries)} claves")


if __name__ == "__main__":
    sys.exit(main())
