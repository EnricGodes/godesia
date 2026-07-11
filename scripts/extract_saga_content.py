#!/usr/bin/env python3
"""Prepara las páginas de saga para i18n.

Para cada saga de frontend/ añade atributos data-content="clave" a los bloques
de prosa (título, subtítulo, párrafos, cronología, captions, cards...) y vuelca
el contenido español a frontend/locales/sagas/{página}.es.json.

El HTML sigue siendo la versión española (fallback); para otros idiomas,
i18n.js sustituye el innerHTML de cada [data-content] desde
window.__I18N_CONTENT__ (inyectado por el backend desde
locales/sagas/{página}.{lang}.json). Las claves ausentes quedan en español,
así se puede traducir saga a saga.

La inserción del atributo es quirúrgica (posiciones de origen del parser):
el resto del HTML queda byte a byte igual. Idempotente: si el elemento ya
lleva data-content se reescribe su valor.
    python3 scripts/extract_saga_content.py
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent.parent
FRONTEND = BASE / "frontend"
OUT_DIR = FRONTEND / "locales" / "sagas"

SAGAS = [
    "cabestany_godes", "garrido_godes", "godes_caballeria", "godes_diago",
    "godes_faura", "godes_ferrer", "godes_guell", "godes_hospital",
    "godes_hurtado", "godes_mate", "godes_molina", "godes_schmid",
    "godes_segura", "godes_terrats", "mestre_godes", "millan_godes",
    "nolla_godes", "puig_godes", "pujol_godes", "pujol_perez",
]

# (selector, prefijo de clave, contenido como lista de <li>)
TARGETS = [
    (".saga-title", "title", False),
    (".saga-subtitle", "subtitle", False),
    (".saga-hero-figure figcaption", "hero_caption", False),
    (".saga-prose > p", "prose", False),
    (".saga-section-title", "section_title", False),
    (".saga-section-subtitle", "subsection", False),
    (".saga-origin-card", "origin", False),
    (".saga-timeline", "timeline", True),
    (".saga-gallery figcaption", "caption", False),
    (".saga-child-kicker", "child_kicker", False),
    (".saga-child-body > p", "child_p", False),
    (".saga-branch-link", "branch_link", False),
    (".saga-living", "living", False),
]

DATA_CONTENT_RE = re.compile(r'\s*data-content="[^"]*"')


def inner_html(el):
    return el.decode_contents().strip()


def start_tag_end(text: str, start: int) -> int:
    """Índice del '>' que cierra la etiqueta de apertura que empieza en start."""
    in_quote = None
    for i in range(start, len(text)):
        ch = text[i]
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
        elif ch == ">":
            return i
    raise ValueError(f"Etiqueta sin cerrar en el offset {start}")


def process(page: Path):
    text = page.read_text(encoding="utf-8")
    lines_offsets = [0]
    for line in text.splitlines(keepends=True):
        lines_offsets.append(lines_offsets[-1] + len(line))

    soup = BeautifulSoup(text, "html.parser")
    content = {}
    insertions = []  # (offset_del_tag, clave)

    def element_offset(el):
        return lines_offsets[el.sourceline - 1] + el.sourcepos

    claimed = []  # offsets de elementos ya seleccionados (para evitar anidados)

    def has_selected_ancestor(el):
        parent = el.parent
        while parent is not None:
            if id(parent) in claimed:
                return True
            parent = parent.parent
        return False

    for selector, prefix, as_list in TARGETS:
        elements = [el for el in soup.select(selector) if not has_selected_ancestor(el)]
        for i, el in enumerate(elements, 1):
            key = prefix if len(elements) == 1 else f"{prefix}.{i}"
            claimed.append(id(el))
            insertions.append((element_offset(el), key))
            if as_list:
                content[key] = [inner_html(li) for li in el.find_all("li", recursive=False)]
            else:
                content[key] = inner_html(el)

    # Subtítulo de sidebar único por saga (los genéricos llevan data-i18n)
    sub = soup.select_one(".sidebar-subtitle:not([data-i18n])")
    if sub is not None:
        claimed.append(id(sub))
        insertions.append((element_offset(sub), "sidebar_subtitle"))
        content["sidebar_subtitle"] = inner_html(sub)

    # Insertar de atrás hacia delante para no desplazar offsets
    for offset, key in sorted(insertions, key=lambda x: -x[0]):
        end = start_tag_end(text, offset)
        tag = DATA_CONTENT_RE.sub("", text[offset:end])  # idempotencia
        tag += f' data-content="{key}"'
        text = text[:offset] + tag + text[end:]

    page.write_text(text, encoding="utf-8")
    out = OUT_DIR / f"{page.stem}.es.json"
    out.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(content)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for name in SAGAS:
        page = FRONTEND / f"{name}.html"
        if not page.exists():
            print(f"  ⚠ falta {page.name}")
            continue
        n = process(page)
        total += n
        print(f"  ✓ {page.name}: {n} bloques")
    print(f"Total: {total} bloques de contenido")


if __name__ == "__main__":
    sys.exit(main())
