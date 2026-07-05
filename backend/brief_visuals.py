"""
brief_visuals.py — district-level map and trendline rendering for the
periodic (monthly + fortnightly) strategic brief PDFs.

The dashboard map (frontend NERMap.js) is a Leaflet React component and
cannot render server-side. The situation map here is a real geographic
render instead: actual district polygons for the NER states, North Bengal,
and Bangladesh (assets/ner_districts.geojson — geoBoundaries ADM2, ODbL /
CC-BY, see assets/DISTRICT_DATA_LICENSE.txt) rasterized with Pillow, plus
the LOCATION_COORDS gazetteer (ported from NERMap.js) for plotting items.
Pillow was chosen over matplotlib after matplotlib's compiled font extension
failed to load in this environment; Pillow needs no font file (Pillow's
scalable `ImageFont.load_default(size=...)`) and is already a proven,
widely-deployed dependency.

Provides:
  geocode_place(name)          — gazetteer lookup with state-centroid fallback
  geocode_points(items)        — geocode a list of intel items → map points
  draw_paoi_map(pdf, ...)      — per-PAOI map: real district outlines +
                                 severity dots, green ring = current period,
                                 brown ring = previous period
  draw_paoi_trendline(pdf, ..) — faultline-score line chart across 3+ periods
"""
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_ASSETS = Path(__file__).parent / "assets"

# ── Gazetteer (ported from frontend/src/components/NERMap.js LOCATION_COORDS) ─
# [lat, lon]
LOCATION_COORDS = {
    # Assam
    "Guwahati": [26.144, 91.736], "Silchar": [24.827, 92.798],
    "Dibrugarh": [27.480, 94.912], "Jorhat": [26.747, 94.206],
    "Tezpur": [26.633, 92.793], "Tinsukia": [27.488, 95.361],
    "Nagaon": [26.348, 92.686], "Sivasagar": [26.984, 94.637],
    "Karimganj": [24.869, 92.355], "Barpeta": [26.321, 91.005],
    "Goalpara": [26.170, 90.623], "Kokrajhar": [26.399, 90.269],
    "Dhubri": [26.015, 89.975], "Hailakandi": [24.682, 92.562],
    "Haflong": [25.165, 93.021], "Tingkhong": [27.211, 95.015],
    "Numaligarh": [26.668, 93.693], "Bongaigaon": [26.477, 90.558],
    "Lakhimpur": [27.234, 94.101],
    # RAS stations not in the frontend gazetteer
    "Narangi": [26.190, 91.828], "Narengi": [26.190, 91.828],
    "Misamari": [26.793, 92.605], "Missamari": [26.793, 92.605],
    "Likabali": [27.660, 94.720], "Lekabali": [27.660, 94.720],
    "Panitola": [27.457, 95.257],
    "Masimpur": [24.793, 92.850], "Mashimpur": [24.793, 92.850],
    # Manipur
    "Imphal": [24.818, 93.944], "Moreh": [24.241, 94.272],
    "Churachandpur": [24.337, 93.682], "Senapati": [25.262, 94.015],
    "Ukhrul": [25.130, 94.365], "Bishnupur": [24.620, 93.762],
    "Thoubal": [24.639, 93.999], "Chandel": [24.221, 94.027],
    "Tamenglong": [24.979, 93.498], "Jiribam": [24.798, 93.115],
    "Kangpokpi": [25.146, 93.953],
    # Mizoram
    "Aizawl": [23.727, 92.718], "Lunglei": [22.888, 92.735],
    "Champhai": [23.457, 93.326], "Serchhip": [23.311, 92.843],
    "Lawngtlai": [22.517, 92.897], "Kolasib": [24.225, 92.683],
    # Nagaland
    "Kohima": [25.675, 94.109], "Dimapur": [25.906, 93.728],
    "Mokokchung": [26.327, 94.519], "Tuensang": [26.272, 94.821],
    "Wokha": [26.103, 94.262], "Zunheboto": [26.013, 94.520],
    "Phek": [25.669, 94.466], "Mon": [26.726, 95.017],
    # Arunachal Pradesh
    "Itanagar": [27.085, 93.609], "Naharlagun": [27.104, 93.696],
    "Tawang": [27.586, 91.867], "Bomdila": [27.264, 92.422],
    "Pasighat": [28.063, 95.325], "Ziro": [27.541, 93.833],
    "Along": [28.160, 94.800], "Tezu": [27.916, 96.172],
    "Khonsa": [27.014, 95.516], "Changlang": [27.129, 95.746],
    "Dibang Valley": [28.500, 95.500], "Anjaw": [28.200, 96.800],
    "Namsai": [27.680, 95.832], "Longding": [26.930, 95.568],
    # Meghalaya
    "Shillong": [25.574, 91.882], "Tura": [25.513, 90.216],
    "Jowai": [25.451, 92.202], "Nongstoin": [25.519, 91.264],
    "Baghmara": [25.197, 90.635], "Resubelpara": [25.884, 90.726],
    # Tripura
    "Agartala": [23.836, 91.279], "Dharmanagar": [24.374, 92.168],
    "Udaipur": [23.538, 91.487], "Sabroom": [23.007, 91.715],
    "Belonia": [23.254, 91.451], "Kailashahar": [24.332, 92.010],
    "Khowai": [24.072, 91.614],
    # Sikkim / West Bengal (Siliguri Corridor)
    "Gangtok": [27.339, 88.612], "Siliguri": [26.717, 88.429],
    "Jalpaiguri": [26.542, 88.729], "Cooch Behar": [26.324, 89.446],
    "Alipurduar": [26.486, 89.526], "Darjeeling": [27.036, 88.263],
    "Kalimpong": [27.059, 88.469], "Kurseong": [26.886, 88.278],
    "Raiganj": [25.621, 88.124], "Islampur": [26.260, 88.184],
    "Siliguri Corridor": [26.717, 88.429],
    "Chicken's Neck": [26.5, 88.5], "Chickens Neck": [26.5, 88.5],
    "Terai": [26.8, 88.6],
    # Bangladesh
    "Dhaka": [23.810, 90.413], "Chittagong": [22.335, 91.834],
    "Sylhet": [24.899, 91.872], "Cox's Bazar": [21.428, 92.005],
    "Coxs Bazar": [21.428, 92.005], "Bandarban": [22.195, 92.219],
    "Teknaf": [20.861, 92.303], "Khulna": [22.845, 89.540],
    "Rajshahi": [24.374, 88.602], "Rangpur": [25.746, 89.252],
    "Mymensingh": [24.747, 90.407], "Jessore": [23.163, 89.208],
    "Comilla": [23.461, 91.180], "Bogra": [24.848, 89.372],
    "Barisal": [22.701, 90.370], "Narayanganj": [23.623, 90.499],
    "Rangamati": [22.644, 92.201], "Khagrachhari": [23.122, 91.950],
    # Myanmar
    "Naypyidaw": [19.745, 96.129], "Yangon": [16.867, 96.195],
    "Mandalay": [21.978, 96.084], "Tamu": [24.213, 94.301],
    "Sagaing": [21.877, 95.979], "Chin State": [22.500, 93.700],
    "Sagaing Region": [23.500, 95.000], "Rakhine": [20.000, 93.500],
    "Kayah": [19.500, 97.500], "Kachin": [25.500, 96.500],
    # Generic NE
    "Brahmaputra": [27.200, 93.500], "Barak Valley": [24.800, 92.800],
    "Lushai Hills": [23.200, 92.800], "Naga Hills": [25.700, 94.300],
}

STATE_CENTERS = {
    "Arunachal Pradesh": [28.0, 94.5], "Assam": [26.2, 92.5],
    "Nagaland": [26.0, 94.5], "Manipur": [24.8, 93.9],
    "Meghalaya": [25.5, 91.3], "Tripura": [23.8, 91.7],
    "Mizoram": [23.2, 92.8], "Sikkim": [27.5, 88.5],
    "West Bengal": [24.5, 88.0], "Bangladesh": [23.7, 90.3],
    "Myanmar": [21.5, 96.5],
}

_LOCATION_COORDS_LOWER = {k.lower(): v for k, v in LOCATION_COORDS.items()}

# Severity fill colours — matches the SEV_COLORS palette in brief_monthly PDF
SEV_FILL = {
    "critical": (200, 50, 50),
    "high": (200, 100, 30),
    "medium": (200, 170, 30),
    "low": (100, 160, 60),
}
RING_CURRENT = (30, 150, 60)    # green — current period
RING_PREVIOUS = (139, 90, 43)   # brown — previous period


# ── Geocoding ─────────────────────────────────────────────────────────────────

def geocode_place(name: str) -> list | None:
    """Exact (case-insensitive) gazetteer lookup, then state centroid."""
    if not name:
        return None
    coords = _LOCATION_COORDS_LOWER.get(name.strip().lower())
    if coords:
        return coords
    return STATE_CENTERS.get(name.strip().title())


def geocode_item(item: dict) -> tuple[list, str] | None:
    """
    Best-effort geolocation of an intel item.
    Order: NER entity locations → district → state centroid.
    Returns ([lat, lon], label) or None if nothing resolves.
    """
    for loc in (item.get("entities") or {}).get("locations", []) or []:
        coords = geocode_place(loc)
        if coords:
            return coords, loc
    district = item.get("district") or ""
    if district:
        coords = geocode_place(district)
        if coords:
            return coords, district
    state = item.get("state") or ""
    if state and state in STATE_CENTERS:
        return STATE_CENTERS[state], state
    return None


def geocode_points(items: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Geocode a list of intel items into map points.
    Returns (points, unresolved_titles) where each point is
    {lat, lon, label, severity, title}.
    """
    points, unresolved = [], []
    for it in items:
        res = geocode_item(it)
        if res:
            (lat, lon), label = res
            points.append({
                "lat": lat, "lon": lon, "label": label,
                "severity": (it.get("severity") or "medium").lower(),
                "title": (it.get("title") or "")[:120],
            })
        else:
            unresolved.append((it.get("title") or "")[:80])
    return points, unresolved


# ── GeoJSON district outlines (geoBoundaries ADM2, NER + North Bengal + BGD) ──

_geo_cache: dict = {}


def _load_districts() -> list[dict]:
    """Load district features once: [{name, country, polygons: [[(lon,lat),...]]}]."""
    if "districts" in _geo_cache:
        return _geo_cache["districts"]
    out: list[dict] = []
    path = _ASSETS / "ner_districts.geojson"
    try:
        gj = json.loads(path.read_text(encoding="utf-8"))
        for feat in gj.get("features", []):
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            polys = []
            if geom.get("type") == "Polygon":
                polys = [geom.get("coordinates", [])]
            elif geom.get("type") == "MultiPolygon":
                polys = geom.get("coordinates", [])
            rings = []
            for poly in polys:
                if not poly:
                    continue
                outer = poly[0]  # outer ring only — holes are visual noise at print size
                if len(outer) < 4:
                    continue
                rings.append([(pt[0], pt[1]) for pt in outer])  # (lon, lat)
            if rings:
                out.append({
                    "name": props.get("name", ""),
                    "country": props.get("country", "IND"),
                    "polygons": rings,
                })
    except Exception:
        out = []
    _geo_cache["districts"] = out
    return out


# ── Map drawing (Pillow raster, real district polygons) ───────────────────────

# Fixed NER theatre bounds (lon 88–97.5, lat 21.5–29.5) so every PAOI map has
# the same frame regardless of which points it contains.
_MAP_BOUNDS = {"lon_min": 88.0, "lon_max": 97.5, "lat_min": 21.5, "lat_max": 29.5}

_COUNTRY_STYLE = {
    "IND": {"fill": (223, 236, 214), "outline": (140, 158, 128)},
    "BGD": {"fill": (213, 228, 240), "outline": (120, 145, 168)},
}

_MM_TO_PX = 300 / 25.4   # render at 300 dpi print resolution
_SUPERSAMPLE = 3         # render 3x then downsample for anti-aliasing


def _in_bounds(lat: float, lon: float) -> bool:
    b = _MAP_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def _project_px(lat: float, lon: float, pw: int, ph: int) -> tuple:
    """Equirectangular projection of lat/lon into a pw x ph pixel canvas."""
    b = _MAP_BOUNDS
    px = (lon - b["lon_min"]) / (b["lon_max"] - b["lon_min"]) * pw
    py = (b["lat_max"] - lat) / (b["lat_max"] - b["lat_min"]) * ph
    return px, py


def _render_map_image(current_points: list[dict], previous_points: list[dict],
                      w_mm: float, h_mm: float) -> Image.Image:
    """Rasterize the district map + markers at print resolution with 3x
    supersampling for anti-aliased polygon edges and circles."""
    base_pw, base_ph = round(w_mm * _MM_TO_PX), round(h_mm * _MM_TO_PX)
    pw, ph = base_pw * _SUPERSAMPLE, base_ph * _SUPERSAMPLE

    img = Image.new("RGB", (pw, ph), (247, 250, 245))
    draw = ImageDraw.Draw(img)

    for dist in _load_districts():
        style = _COUNTRY_STYLE.get(dist["country"], _COUNTRY_STYLE["IND"])
        for ring in dist["polygons"]:
            pts = [_project_px(lat, lon, pw, ph) for lon, lat in ring
                   if _in_bounds(lat, lon)]
            if len(pts) >= 3:
                draw.polygon(pts, fill=style["fill"], outline=style["outline"], width=1 * _SUPERSAMPLE)

    def _plot(points: list[dict], ring_rgb: tuple, font):
        seen: dict[tuple, int] = {}
        labelled: set = set()
        for p in points:
            if not _in_bounds(p["lat"], p["lon"]):
                continue
            px, py = _project_px(p["lat"], p["lon"], pw, ph)
            key = (round(px / _SUPERSAMPLE, 0), round(py / _SUPERSAMPLE, 0))
            n = seen.get(key, 0)
            seen[key] = n + 1
            if n:
                ang = n * 2.4  # golden-angle spiral to de-clutter stacked markers
                px += 7 * _SUPERSAMPLE * math.cos(ang) * (1 + n * 0.15)
                py += 7 * _SUPERSAMPLE * math.sin(ang) * (1 + n * 0.15)
            ring_r = 6.5 * _SUPERSAMPLE
            draw.ellipse([px - ring_r, py - ring_r, px + ring_r, py + ring_r],
                        outline=ring_rgb, width=2 * _SUPERSAMPLE)
            dot_r = 3.6 * _SUPERSAMPLE
            fill = SEV_FILL.get(p["severity"], (110, 110, 110))
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r],
                        fill=fill, outline=(255, 255, 255), width=1 * _SUPERSAMPLE)
            if p["label"] not in labelled and len(labelled) < 10:
                labelled.add(p["label"])
                draw.text((px + ring_r + 3 * _SUPERSAMPLE, py - 8 * _SUPERSAMPLE),
                          p["label"][:20], fill=(60, 65, 55), font=font)

    label_font = ImageFont.load_default(size=15 * _SUPERSAMPLE)
    _plot(previous_points or [], RING_PREVIOUS, label_font)   # previous under current
    _plot(current_points or [], RING_CURRENT, label_font)

    draw.rectangle([0, 0, pw - 1, ph - 1], outline=(150, 160, 145), width=2 * _SUPERSAMPLE)

    return img.resize((base_pw, base_ph), Image.LANCZOS)


def draw_paoi_map(pdf, current_points: list[dict], previous_points: list[dict],
                  x: float, y: float, w: float = 120, h: float = 82,
                  unresolved: list[str] | None = None) -> float:
    """
    Draw a PAOI situation map at (x, y): real district polygons (NER states,
    North Bengal, Bangladesh) with severity-coloured dots — green ring =
    current period, brown ring = previous period. Returns the y coordinate
    below the map + legend.
    """
    img = _render_map_image(current_points or [], previous_points or [], w, h)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    pdf.image(buf, x=x, y=y, w=w, h=h)

    # Legend (vector text below the raster map — keeps file size down)
    ly = y + h + 2.5
    pdf.set_line_width(0.55)
    pdf.set_draw_color(*RING_CURRENT)
    pdf.circle(x + 3, ly + 1.4, 1.8, "D")
    pdf.set_fill_color(*SEV_FILL["critical"])
    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(0.2)
    pdf.circle(x + 3, ly + 1.4, 1.0, "DF")
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(60, 60, 60)
    pdf.set_xy(x + 6, ly)
    pdf.cell(48, 3, "Green ring = current period")

    pdf.set_line_width(0.55)
    pdf.set_draw_color(*RING_PREVIOUS)
    pdf.circle(x + 57, ly + 1.4, 1.8, "D")
    pdf.set_fill_color(*SEV_FILL["critical"])
    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(0.2)
    pdf.circle(x + 57, ly + 1.4, 1.0, "DF")
    pdf.set_xy(x + 60, ly)
    pdf.cell(50, 3, "Brown ring = previous period")

    pdf.set_xy(x + 112, ly)
    pdf.cell(0, 3, "Dot colour = severity")
    ly += 4

    if unresolved:
        pdf.set_font("Helvetica", "I", 5.5)
        pdf.set_text_color(130, 130, 130)
        pdf.set_xy(x, ly)
        pdf.cell(0, 3, f"Not plotted (no location resolved): {len(unresolved)} item(s)")
        ly += 3.5

    pdf.set_font("Helvetica", "I", 5)
    pdf.set_text_color(150, 150, 150)
    pdf.set_xy(x, ly)
    pdf.cell(0, 3, "District boundaries: geoBoundaries.org (ODbL / CC-BY)")
    ly += 3.2

    pdf.set_line_width(0.2)  # restore default-ish
    return ly + 1


# ── Trendline drawing ─────────────────────────────────────────────────────────

def draw_paoi_trendline(pdf, series: list[dict], x: float, y: float,
                        w: float = 120, h: float = 30) -> float:
    """
    Line chart of a PAOI's faultline score (0-100 concern scale) across
    periods. series = [{"label": "May 26", "score": 62.0, "level": "ELEVATED"}]
    ordered oldest → newest. Caller gates on len(series) >= 3.
    Returns the y coordinate below the chart.
    """
    scores = [s.get("score") for s in series if s.get("score") is not None]
    if len(scores) < 2:
        return y

    # Frame
    pdf.set_fill_color(250, 252, 248)
    pdf.set_draw_color(170, 180, 165)
    pdf.set_line_width(0.25)
    pdf.rect(x, y, w, h, "DF")

    pad_l, pad_r, pad_t, pad_b = 9, 3, 3, 6
    cx, cy = x + pad_l, y + pad_t
    cw, ch = w - pad_l - pad_r, h - pad_t - pad_b

    # Gridlines + y labels at 0/25/50/75/100 (concern scale, higher = worse)
    pdf.set_font("Helvetica", "", 5)
    pdf.set_text_color(120, 125, 115)
    pdf.set_draw_color(215, 222, 210)
    pdf.set_line_width(0.15)
    for gv in (0, 25, 50, 75, 100):
        gy = cy + ch - (gv / 100) * ch
        pdf.line(cx, gy, cx + cw, gy)
        pdf.set_xy(x + 1, gy - 1.2)
        pdf.cell(7, 2.4, str(gv), align="R")

    pts = []
    n = len(series)
    for i, s in enumerate(series):
        sc = s.get("score")
        if sc is None:
            continue
        px = cx + (i / (n - 1)) * cw if n > 1 else cx + cw / 2
        py = cy + ch - (max(0, min(100, sc)) / 100) * ch
        pts.append((px, py, s))

    # Polyline
    pdf.set_draw_color(150, 30, 30)
    pdf.set_line_width(0.45)
    for i in range(1, len(pts)):
        pdf.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])

    # Dots + period labels
    for i, (px, py, s) in enumerate(pts):
        lvl = (s.get("level") or "").upper()
        dot = (200, 50, 50) if lvl == "CRITICAL" else \
              (200, 100, 30) if lvl == "ELEVATED" else \
              (200, 170, 30) if lvl == "MONITOR" else (100, 160, 60)
        pdf.set_fill_color(*dot)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.2)
        pdf.circle(px, py, 0.9, "DF")
        # Label first, last, and alternating middles when crowded
        if i == 0 or i == len(pts) - 1 or (len(pts) <= 6 or i % 2 == 0):
            pdf.set_font("Helvetica", "", 5)
            pdf.set_text_color(90, 95, 85)
            pdf.set_xy(px - 8, y + h - pad_b + 1)
            pdf.cell(16, 2.4, str(s.get("label", ""))[:9], align="C")

    pdf.set_line_width(0.2)
    return y + h + 2
