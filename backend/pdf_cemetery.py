"""Cemetery visitor-guide PDF generator.

Produces a self-guided visit document:
  • Cover page with cemetery info and stats
  • Overview OSM map with numbered markers in nearest-neighbour route order
  • One page per enabled niche: street-context map (zoom 16), all fields, people list

Zoom levels:
  Overview map  — auto-fit to bounding box of reliable-geo niches (min zoom 17)
  Per-niche map — zoom 16 (~2.5 km radius), shows street names and neighbourhood
                  context so the visitor can navigate to the niche

Route: niches marked NO GEO / GEO NO are appended at the end (their coordinates
are unreliable and would distort the nearest-neighbour path).
"""

import io
import math
import os
from datetime import date

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
from staticmap import StaticMap, CircleMarker

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_REG  = os.path.join(FONT_DIR, "DejaVuSans.ttf")
_FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
TILE_URL   = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_SIZE  = 256

_GREEN       = (23, 52, 30)
_GREEN_LIGHT = (235, 245, 237)
_RED         = (200, 50, 50)
_WHITE       = (255, 255, 255)

_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _today_es():
    d = date.today()
    return f"{d.day} de {_MONTHS_ES[d.month - 1]} de {d.year}"


def _is_good_geo(niche):
    """True if niche has reliable coordinates (no NO GEO / GEO NO tag)."""
    t = (niche.get("title") or "").upper()
    return ("NO GEO" not in t and "GEO NO" not in t
            and niche.get("lat") is not None)


# ---------------------------------------------------------------------------
# Route optimisation
# ---------------------------------------------------------------------------

def _haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def optimize_route(niches):
    """Greedy nearest-neighbour route. NO GEO niches appended at the end."""
    good  = [n for n in niches if _is_good_geo(n)]
    nogeo = [n for n in niches if not _is_good_geo(n)]
    if not good:
        return niches
    start = max(good, key=lambda n: n["lat"])
    route, rem = [start], [n for n in good if n is not start]
    while rem:
        last    = route[-1]
        nearest = min(rem, key=lambda n: _haversine_m(last["lat"], last["lng"],
                                                       n["lat"], n["lng"]))
        route.append(nearest)
        rem.remove(nearest)
    return route + nogeo


def _route_distance_m(niches):
    total = 0.0
    for i in range(len(niches) - 1):
        a, b = niches[i], niches[i + 1]
        if _is_good_geo(a) and _is_good_geo(b):
            total += _haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])
    return total


# ---------------------------------------------------------------------------
# Static map helpers (OSM tiles + PIL drawing)
# ---------------------------------------------------------------------------

def _lon_to_x(lon, zoom):
    return ((lon + 180.0) / 360) * (2 ** zoom)


def _lat_to_y(lat, zoom):
    lr = math.radians(lat)
    return (1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * (2 ** zoom)


def _to_px(lat, lng, zoom, clat, clng, w, h):
    cx, cy = _lon_to_x(clng, zoom), _lat_to_y(clat, zoom)
    px, py = _lon_to_x(lng, zoom),  _lat_to_y(lat, zoom)
    return (
        int(round((px - cx) * TILE_SIZE + w / 2)),
        int(round((py - cy) * TILE_SIZE + h / 2)),
    )


def _pick_zoom(lats, lngs, w, h, pad=70, min_zoom=13):
    if len(lats) <= 1:
        return max(17, min_zoom)
    dlat, dlng = max(lats) - min(lats), max(lngs) - min(lngs)
    for z in range(20, min_zoom - 1, -1):
        if (dlat / 360 * TILE_SIZE * 2 ** z * 1.5 < h - pad * 2
                and dlng / 360 * TILE_SIZE * 2 ** z < w - pad * 2):
            return z
    return min_zoom


def _load_pil_font(size):
    try:
        return ImageFont.truetype(_FONT_REG, size)
    except Exception:
        return ImageFont.load_default()


def build_overview_map(niches_ordered, w=570, h=370):
    """OSM map with numbered red markers. Bounding box uses reliable-geo niches only."""
    all_pts  = [(n["lat"], n["lng"], i)
                for i, n in enumerate(niches_ordered) if n.get("lat") is not None]
    good_pts = [(lat, lng, i)
                for lat, lng, i in all_pts if _is_good_geo(niches_ordered[i])]
    if not all_pts:
        return None

    bbox_pts = good_pts if good_pts else all_pts
    lats = [p[0] for p in bbox_pts]
    lngs = [p[1] for p in bbox_pts]
    clat = (min(lats) + max(lats)) / 2
    clng = (min(lngs) + max(lngs)) / 2
    zoom = _pick_zoom(lats, lngs, w, h, min_zoom=17)

    sm = StaticMap(w, h, url_template=TILE_URL)
    for lat, lng, _ in all_pts:
        sm.add_marker(CircleMarker((lng, lat), "#17341e", 1))
    image = sm.render(zoom=zoom)

    draw = ImageDraw.Draw(image)
    fnt  = _load_pil_font(11)

    for lat, lng, idx in all_pts:
        x, y = _to_px(lat, lng, zoom, clat, clng, w, h)
        r = 13
        draw.ellipse([(x - r - 1, y - r - 1), (x + r + 1, y + r + 1)], fill=_WHITE)
        draw.ellipse([(x - r,     y - r),     (x + r,     y + r)],     fill=_RED)
        label = str(idx + 1)
        bb    = draw.textbbox((0, 0), label, font=fnt)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((x - tw / 2, y - th / 2 - 1), label, fill=_WHITE, font=fnt)

    return image


def build_niche_map(niche, w=380, h=240):
    """Street-level OSM map centred on one niche (zoom 16, ~2.5 km context)."""
    if niche.get("lat") is None:
        return None
    lat, lng = niche["lat"], niche["lng"]
    sm = StaticMap(w, h, url_template=TILE_URL)
    sm.add_marker(CircleMarker((lng, lat), "#17341e", 1))
    image = sm.render(zoom=16)

    draw = ImageDraw.Draw(image)
    x, y = w // 2, h // 2
    draw.ellipse([(x - 8, y - 8), (x + 8, y + 8)], fill=_WHITE)
    draw.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=_RED)
    return image


def _img_to_buf(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# PDF class (header / footer)
# ---------------------------------------------------------------------------

class _GuidePDF(FPDF):
    def __init__(self, cem_name):
        super().__init__()
        self._cem_name = cem_name
        self.add_font("dv",  style="",  fname=_FONT_REG)
        self.add_font("dv",  style="B", fname=_FONT_BOLD)
        self.alias_nb_pages()

    def header(self):
        if self.page_no() <= 2:
            return
        self.set_font("dv", "", 7)
        self.set_text_color(140, 140, 140)
        self.cell(0, 5, self._cem_name, align="L")
        self.set_draw_color(210, 210, 210)
        y = self.get_y() + 4
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(6)
        self.set_text_color(0, 0, 0)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_font("dv", "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, f"Página {self.page_no()} / {{nb}}", align="C")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _short_name(full_name):
    parts = full_name.split()
    if len(parts) <= 2:
        return full_name
    return f"{parts[0]} {parts[-1]}"


def _fmt_death(p):
    if p.get("death_date"):
        d = p["death_date"]
        for pfx in ("ABT ", "BEF ", "AFT ", "EST ", "FROM ", "BET "):
            d = d.replace(pfx, "c. ")
        return d[:12]
    return str(p["death_year"]) if p.get("death_year") else "—"


def _fit_text(pdf, text, max_w_mm):
    """Truncate text so it fits in max_w_mm, appending ellipsis if needed."""
    if pdf.get_string_width(text) <= max_w_mm:
        return text
    while text and pdf.get_string_width(text + "…") > max_w_mm:
        text = text[:-1]
    return text + "…"


# ---------------------------------------------------------------------------
# Main PDF builder
# ---------------------------------------------------------------------------

def generate_cemetery_pdf(data, photos_dir=None):
    """Return PDF bytes for a cemetery visitor guide."""
    niches_raw = [n for n in data.get("niches", []) if n.get("enabled", 1)]
    route      = optimize_route(niches_raw)
    dist_m     = _route_distance_m(route)
    cem_name   = data.get("name", "Cementerio")
    today      = _today_es()
    n_people   = sum(len(n.get("people", [])) for n in route)

    pdf = _GuidePDF(cem_name)
    pdf.set_auto_page_break(auto=True, margin=15)
    pw = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Cover ──────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*_GREEN)
    pdf.rect(0, 0, pdf.w, 72, style="F")

    pdf.set_y(16)
    pdf.set_font("dv", "B", 22)
    pdf.set_text_color(*_WHITE)
    pdf.cell(0, 11, cem_name, align="C", new_x="LMARGIN", new_y="NEXT")

    if data.get("city"):
        pdf.set_font("dv", "", 13)
        pdf.set_text_color(180, 210, 185)
        pdf.cell(0, 8, data["city"], align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("dv", "", 8)
    pdf.set_text_color(140, 185, 148)
    pdf.set_y(63)
    pdf.cell(0, 6, "GUÍA DE VISITA", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(82)
    pdf.set_font("dv", "", 11)
    pdf.set_text_color(*_GREEN)
    pdf.cell(0, 8, f"{len(route)} nichos  ·  {n_people} personas enterradas",
             align="C", new_x="LMARGIN", new_y="NEXT")

    if dist_m > 0:
        pdf.set_font("dv", "", 9)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, f"Distancia estimada del recorrido: {int(dist_m)} m",
                 align="C", new_x="LMARGIN", new_y="NEXT")

    if data.get("description"):
        pdf.set_y(110)
        pdf.set_font("dv", "", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(pw, 6, data["description"], align="C")

    pdf.set_y(-22)
    pdf.set_font("dv", "", 8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 6, f"Generado el {today}", align="C")

    # ── Overview map ────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("dv", "B", 14)
    pdf.set_text_color(*_GREEN)
    pdf.cell(0, 8, "Mapa del recorrido", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    overview_img = build_overview_map(route)
    if overview_img:
        buf      = _img_to_buf(overview_img)
        img_h_mm = min(105, overview_img.height * (pw / overview_img.width))
        img_w_mm = overview_img.width * (img_h_mm / overview_img.height)
        x_img    = pdf.l_margin + (pw - img_w_mm) / 2
        pdf.image(buf, x=x_img, y=None, w=img_w_mm, h=img_h_mm)
        pdf.ln(4)

    # Legend: 2 compact columns, text truncated to fit, no extra blank lines
    pdf.set_font("dv", "", 8)
    pdf.set_text_color(50, 50, 50)
    gap    = 4        # mm between columns
    col_w  = (pw - gap) / 2   # each column (~93 mm on A4)
    cell_h = 4.5

    for idx, n in enumerate(route):
        title  = n.get("title") or n.get("name", "")
        people = n.get("people") or []
        names  = ", ".join(_short_name(p["name"]) for p in people)
        line   = f"{idx + 1}. {title}"
        if names:
            line += f" — {names}"
        line = _fit_text(pdf, line, col_w - 1)

        col = idx % 2
        pdf.set_x(pdf.l_margin + col * (col_w + gap))
        if col == 0:
            pdf.cell(col_w, cell_h, line, new_x="RIGHT", new_y="TOP")
        else:
            pdf.cell(col_w, cell_h, line, new_x="LMARGIN", new_y="NEXT")

    if len(route) % 2 == 1:
        pdf.ln(cell_h)

    # ── Per-niche pages ─────────────────────────────────────────────────────
    for idx, niche in enumerate(route):
        pdf.add_page()
        title = niche.get("title") or niche.get("name", "")
        num   = idx + 1

        # Header band
        pdf.set_fill_color(*_GREEN)
        pdf.set_text_color(*_WHITE)
        pdf.set_font("dv", "B", 12)
        pdf.cell(0, 10, f"  {num}.  {title}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_text_color(0, 0, 0)

        y_start = pdf.get_y()
        left_w  = pw * 0.52
        right_w = pw - left_w - 4
        x_left  = pdf.l_margin
        x_right = pdf.l_margin + left_w + 4

        # ── Right column: map + photos ───────────────────────────────────
        y_right = y_start

        niche_img = build_niche_map(niche)
        if niche_img:
            map_h_mm = min(60, niche_img.height * (right_w / niche_img.width))
            map_w_mm = niche_img.width * (map_h_mm / niche_img.height)
            buf = _img_to_buf(niche_img)
            pdf.image(buf, x=x_right + (right_w - map_w_mm) / 2,
                      y=y_right, w=map_w_mm, h=map_h_mm)
            y_right += map_h_mm + 3

        # Record photos first, then niche photos (up to 3 total)
        record_photos = [ph["filename"] for ph in (niche.get("photos") or [])
                         if ph.get("kind") == "record"][:2]
        niche_photos  = [ph["filename"] for ph in (niche.get("photos") or [])
                         if ph.get("kind") == "photo"][:2]
        photo_files   = (record_photos + niche_photos)[:3]

        if photos_dir:
            for ph_f in photo_files:
                ph_path = os.path.join(photos_dir, ph_f)
                if os.path.exists(ph_path):
                    try:
                        with Image.open(ph_path) as im:
                            ph_h = min(50, im.height * (right_w / im.width))
                            ph_w = im.width * (ph_h / im.height)
                        pdf.image(ph_path, x=x_right, y=y_right, w=ph_w, h=ph_h)
                        y_right += ph_h + 2
                    except Exception:
                        pass

        # ── Left column (flowing text) ───────────────────────────────────
        def lx():
            pdf.set_x(x_left)

        # Physical location within cemetery
        location = niche.get("name", "")
        if location and location != title:
            lx()
            pdf.set_font("dv", "B", 8)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(22, 5, "Ubicación:", new_x="RIGHT", new_y="TOP")
            pdf.set_font("dv", "", 8)
            pdf.set_x(x_left + 22)
            pdf.multi_cell(left_w - 22, 5, location)
            pdf.ln(1)

        # Coordinates + Google Maps link
        if niche.get("lat") is not None:
            coord_str = f"{niche['lat']:.6f}, {niche['lng']:.6f}"
            gmaps     = f"https://maps.google.com/?q={niche['lat']},{niche['lng']}"
            lx()
            pdf.set_font("dv", "", 8)
            pdf.set_text_color(70, 70, 70)
            pdf.cell(left_w, 5, f"Coord: {coord_str}", new_x="LMARGIN", new_y="NEXT")
            lx()
            pdf.set_font("dv", "", 8)
            pdf.set_text_color(0, 80, 160)
            pdf.cell(left_w, 5, "Ver en Google Maps", link=gmaps,
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

        # Notes
        if niche.get("notes"):
            lx()
            pdf.set_font("dv", "", 7.5)
            pdf.set_text_color(90, 90, 90)
            pdf.multi_cell(left_w, 4.5, niche["notes"])
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

        # People table
        people = sorted(
            niche.get("people") or [],
            key=lambda p: (p.get("death_year") is None,
                           p.get("death_year") or 0,
                           p.get("name", "")),
        )
        if people:
            lx()
            pdf.set_font("dv", "B", 8)
            pdf.set_fill_color(*_GREEN_LIGHT)
            c1 = left_w * 0.54
            c2 = left_w * 0.20
            c3 = left_w * 0.26
            pdf.cell(c1, 5.5, "Persona", fill=True, border="B")
            pdf.cell(c2, 5.5, "Nacimiento", fill=True, border="B", align="C")
            pdf.cell(c3, 5.5, "Fallecimiento", fill=True, border="B",
                     align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("dv", "", 8)
            for p in people:
                lx()
                birth = str(p["birth_year"]) if p.get("birth_year") else "—"
                death = _fmt_death(p)
                pdf.cell(c1, 5, p.get("name", ""), border="B")
                pdf.cell(c2, 5, birth, border="B", align="C")
                pdf.cell(c3, 5, death, border="B", align="C",
                         new_x="LMARGIN", new_y="NEXT")

        y_after_left = pdf.get_y()
        pdf.set_y(max(y_after_left, y_right) + 4)

    return bytes(pdf.output())
