"""Servido localizado de páginas públicas: /{lang}/pagina.html.

El frontend es HTML estático (español = idioma base y fallback). Este módulo
inyecta server-side todo lo que debe estar en el HTML inicial:
  - <html lang="..."> correcto
  - canonical + hreflang (incl. x-default) + Open Graph básico
  - las traducciones de UI inline (window.__I18N__) para que t() sea síncrona
  - el contenido de saga por idioma (window.__I18N_CONTENT__) si existe
  - <title>/<meta description> traducidos si el JSON de UI los define
  - reescritura de enlaces internos *.html con el prefijo de idioma

Las URLs sin prefijo redirigen 302 según cookie -> Accept-Language -> español.
Los assets (JS/CSS/fotos) se sirven sin prefijo por los mounts de StaticFiles.
"""

import json
import os
import re
import time
from pathlib import Path

from fastapi.responses import HTMLResponse, RedirectResponse

DEFAULT_LANG = "es"
LANG_COOKIE = "godesia_lang"

# Idiomas por defecto si settings no define active_languages.
# Se incluyen los 5 con traducciones de UI (ui.{code}.json); los contenidos sin
# traducir degradan a español. Robusto ante deploys: godesia.db se sobrescribe en
# cada despliegue, así que el valor por defecto (no la fila de settings) es lo que
# realmente manda en producción salvo que el admin lo cambie y se haga "Publicar".
DEFAULT_LANGUAGES = [
    {"code": "es", "label": "Español"},
    {"code": "ca", "label": "Català"},
    {"code": "en", "label": "English"},
    {"code": "fr", "label": "Français"},
    {"code": "de", "label": "Deutsch"},
]

# Páginas internas: se sirven sin prefijo, sin i18n y fuera del sitemap
EXCLUDED_PAGES = {
    "admin_geocoder.html",
    "index-css-backup.html",
    "preview.html",
    "preview_incremental.html",
    "test_router.html",
}

_conn = None
_frontend_dir = None
_locales_dir = None
_sagas_dir = None

# Caché de idiomas activos (TTL corto; invalidada al guardar settings)
_langs_cache = {"value": None, "ts": 0.0}
_LANGS_TTL = 30.0

# Caché de HTML localizado: (page, lang) -> {"mtimes": (...), "html": str}
_html_cache = {}


def init_i18n(conn, base_dir: Path):
    global _conn, _frontend_dir, _locales_dir, _sagas_dir
    _conn = conn
    _frontend_dir = base_dir / "frontend"
    _locales_dir = _frontend_dir / "locales"
    _sagas_dir = _locales_dir / "sagas"


def invalidate_languages_cache():
    _langs_cache["value"] = None
    _langs_cache["ts"] = 0.0


def get_active_languages():
    """Idiomas activos desde settings (clave active_languages), con caché."""
    now = time.time()
    if _langs_cache["value"] is not None and now - _langs_cache["ts"] < _LANGS_TTL:
        return _langs_cache["value"]
    langs = DEFAULT_LANGUAGES
    if _conn is not None:
        try:
            from database import get_setting
            raw = get_setting(_conn, "active_languages", "")
            if raw:
                parsed = json.loads(raw)
                if (isinstance(parsed, list) and parsed
                        and all(isinstance(l, dict) and l.get("code") for l in parsed)):
                    langs = parsed
        except Exception:
            pass
    # es es obligatorio y va primero
    if not any(l["code"] == DEFAULT_LANG for l in langs):
        langs = [{"code": DEFAULT_LANG, "label": "Español"}] + langs
    _langs_cache["value"] = langs
    _langs_cache["ts"] = now
    return langs


def active_codes():
    return [l["code"] for l in get_active_languages()]


def parse_accept_language(header: str, codes):
    """Mejor idioma activo según Accept-Language; None si ninguno encaja."""
    if not header:
        return None
    candidates = []
    for part in header.split(","):
        piece = part.strip()
        if not piece:
            continue
        q = 1.0
        if ";" in piece:
            piece, _, params = piece.partition(";")
            m = re.search(r"q=([0-9.]+)", params)
            if m:
                try:
                    q = float(m.group(1))
                except ValueError:
                    q = 0.0
        code = piece.strip().lower().split("-")[0]
        candidates.append((q, code))
    candidates.sort(key=lambda c: -c[0])
    for _, code in candidates:
        if code in codes:
            return code
    return None


def choose_lang(request, codes):
    cookie = request.cookies.get(LANG_COOKIE, "")
    if cookie in codes:
        return cookie
    matched = parse_accept_language(request.headers.get("accept-language", ""), codes)
    return matched or DEFAULT_LANG


def public_pages():
    """Páginas HTML públicas (para sitemap y validación)."""
    if not _frontend_dir:
        return []
    return sorted(
        p.name for p in _frontend_dir.glob("*.html") if p.name not in EXCLUDED_PAGES
    )


def _base_url(request):
    env = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if env:
        return env
    return f"{request.url.scheme}://{request.url.netloc}"


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _ui_json_path(lang):
    return _locales_dir / f"ui.{lang}.json"


def _saga_json_path(page, lang):
    return _sagas_dir / f"{Path(page).stem}.{lang}.json"


def _mtime(path: Path):
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _set_html_lang(html, lang, pending):
    """Fija lang en la etiqueta <html> y añade la clase i18n-pending si toca."""
    m = re.search(r"<html\b[^>]*>", html, flags=re.IGNORECASE)
    if not m:
        return html
    tag = m.group(0)
    if re.search(r'\blang="[^"]*"', tag):
        new_tag = re.sub(r'\blang="[^"]*"', f'lang="{lang}"', tag)
    else:
        new_tag = tag[:-1] + f' lang="{lang}">'
    if pending:
        if re.search(r'\bclass="[^"]*"', new_tag):
            new_tag = re.sub(r'\bclass="([^"]*)"', r'class="\1 i18n-pending"', new_tag)
        else:
            new_tag = new_tag[:-1] + ' class="i18n-pending">'
    return html.replace(tag, new_tag, 1)


def _page_url(page, lang):
    # index.html se canonicaliza como /{lang}/
    if page == "index.html":
        return f"__BASE__/{lang}/"
    return f"__BASE__/{lang}/{page}"


def _build_head_block(page, lang, ui, langs):
    page_key = Path(page).stem
    meta = (ui or {}).get("pages", {}).get(page_key, {})
    lines = [
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
        '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">',
        '<link rel="icon" href="/favicon.ico" sizes="any">',
        '<link rel="apple-touch-icon" href="/favicon-180.png">',
        f'<link rel="canonical" href="{_page_url(page, lang)}">',
    ]
    for l in langs:
        lines.append(
            f'<link rel="alternate" hreflang="{l["code"]}" href="{_page_url(page, l["code"])}">'
        )
    lines.append(
        f'<link rel="alternate" hreflang="x-default" href="{_page_url(page, DEFAULT_LANG)}">'
    )
    og_title = meta.get("meta_title", "")
    og_desc = meta.get("meta_description", "")
    lines.append(f'<meta property="og:url" content="{_page_url(page, lang)}">')
    lines.append(f'<meta property="og:locale" content="{lang}">')
    if og_title:
        lines.append(f'<meta property="og:title" content="{og_title}">')
    if og_desc:
        lines.append(f'<meta property="og:description" content="{og_desc}">')

    payload = (
        f"window.__I18N_LANG__={json.dumps(lang)};"
        f"window.__I18N__={json.dumps(ui or {}, ensure_ascii=False)};"
        f"window.__I18N_LANGS__={json.dumps(langs, ensure_ascii=False)};"
    )
    if lang != DEFAULT_LANG:
        content = _load_json(_saga_json_path(page, lang))
        if content:
            payload += f"window.__I18N_CONTENT__={json.dumps(content, ensure_ascii=False)};"
    lines.append(f"<script>{payload}</script>")
    lines.append('<script src="/i18n.js"></script>')
    lines.append('<script src="/footer.js" defer></script>')

    if lang != DEFAULT_LANG:
        # Anti-FOUC: ocultar hasta que i18n.js aplique las traducciones
        # (con timeout de seguridad por si i18n.js no carga)
        lines.append("<style>html.i18n-pending body{visibility:hidden}</style>")
        lines.append(
            "<script>setTimeout(function(){"
            "document.documentElement.classList.remove('i18n-pending')},300);</script>"
        )
    return "\n".join(lines)


def _apply_meta(html, page, ui):
    """Sustituye <title> y <meta name=description> si el JSON de UI los define."""
    page_key = Path(page).stem
    meta = (ui or {}).get("pages", {}).get(page_key, {})
    title = meta.get("meta_title", "")
    desc = meta.get("meta_description", "")
    if title:
        html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html,
                      count=1, flags=re.DOTALL)
    if desc:
        if re.search(r'<meta\s+name="description"', html):
            html = re.sub(
                r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
                f'<meta name="description" content="{desc}">', html, count=1)
        else:
            html = html.replace("</head>", f'<meta name="description" content="{desc}">\n</head>', 1)
    return html


_LINK_RE = re.compile(r'href="/([^/"]+\.html)([\"?#])')


def _rewrite_links(html, lang):
    return _LINK_RE.sub(lambda m: f'href="/{lang}/{m.group(1)}{m.group(2)}', html)


def localize_html(page: str, lang: str):
    """HTML localizado (con __BASE__ pendiente de sustituir). Cacheado por mtimes."""
    src = _frontend_dir / page
    ui_path = _ui_json_path(lang)
    saga_path = _saga_json_path(page, lang)
    mtimes = (_mtime(src), _mtime(ui_path), _mtime(saga_path))
    cached = _html_cache.get((page, lang))
    if cached and cached["mtimes"] == mtimes:
        return cached["html"]

    html = src.read_text(encoding="utf-8")
    ui = _load_json(ui_path)
    if ui is None and lang != DEFAULT_LANG:
        ui = _load_json(_ui_json_path(DEFAULT_LANG))
    langs = get_active_languages()

    html = _set_html_lang(html, lang, pending=(lang != DEFAULT_LANG))
    html = _apply_meta(html, page, ui)
    head_block = _build_head_block(page, lang, ui, langs)
    html = html.replace("</head>", head_block + "\n</head>", 1)
    html = _rewrite_links(html, lang)

    _html_cache[(page, lang)] = {"mtimes": mtimes, "html": html}
    return html


def _redirect(url, request):
    resp = RedirectResponse(url, status_code=302)
    resp.headers["Vary"] = "Accept-Language, Cookie"
    return resp


async def i18n_middleware(request, call_next):
    """Redirige URLs sin prefijo y sirve /{lang}/pagina.html localizada."""
    path = request.url.path
    if path.startswith(("/api/", "/admin", "/photos/", "/cemetery_photos/",
                        "/locales/")) or _frontend_dir is None:
        return await call_next(request)

    query = f"?{request.url.query}" if request.url.query else ""
    codes = active_codes()
    parts = path.lstrip("/").split("/", 1)
    first = parts[0] if parts else ""

    if first in codes:
        rest = parts[1] if len(parts) > 1 else ""
        page = rest or "index.html"
        if "/" not in page and page.endswith(".html") and page not in EXCLUDED_PAGES \
                and (_frontend_dir / page).is_file():
            html = localize_html(page, first)
            html = html.replace("__BASE__", _base_url(request))
            return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
        # Asset colado bajo el prefijo (enlace relativo): redirigir a la raíz
        if rest and (_frontend_dir / rest).is_file():
            return RedirectResponse(f"/{rest}{query}", status_code=302)
        return await call_next(request)

    # URL sin prefijo: redirigir páginas públicas al idioma del usuario
    page = path.lstrip("/") or "index.html"
    if path == "/" or ("/" not in path.lstrip("/") and path.endswith(".html")):
        if page not in EXCLUDED_PAGES and (_frontend_dir / page).is_file():
            lang = choose_lang(request, codes)
            target = f"/{lang}/" if path == "/" else f"/{lang}{path}"
            return _redirect(f"{target}{query}", request)

    return await call_next(request)


def build_sitemap(base_url: str) -> str:
    """sitemap.xml con alternates hreflang para todas las páginas públicas."""
    langs = get_active_languages()
    urls = []
    for page in public_pages():
        for l in langs:
            loc = _page_url(page, l["code"]).replace("__BASE__", base_url)
            alts = "".join(
                f'<xhtml:link rel="alternate" hreflang="{a["code"]}" '
                f'href="{_page_url(page, a["code"]).replace("__BASE__", base_url)}"/>'
                for a in langs
            )
            alts += (
                f'<xhtml:link rel="alternate" hreflang="x-default" '
                f'href="{_page_url(page, DEFAULT_LANG).replace("__BASE__", base_url)}"/>'
            )
            urls.append(f"<url><loc>{loc}</loc>{alts}</url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
