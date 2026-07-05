"""
brief_visuals.py — fpdf2-native map and trendline drawing for the periodic
(monthly + fortnightly) strategic brief PDFs.

The dashboard map (frontend NERMap.js) is a Leaflet React component and cannot
render server-side; this module re-renders the same DATA — the NER state
polygons (assets/ner-states.geojson, copied from frontend/public) and the
LOCATION_COORDS gazetteer (ported from NERMap.js) — using fpdf2 primitives.

Provides:
  geocode_place(name)          — gazetteer lookup with state-centroid fallback
  geocode_points(items)        — geocode a list of intel items → map points
  draw_paoi_map(pdf, ...)      — per-PAOI map: state outlines + severity dots,
                                 green ring = current period, brown = previous
  draw_paoi_trendline(pdf, ..) — faultline-score line chart across 3+ periods
"""
import json
import math
from pathlib import Path

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


# ── GeoJSON state outlines ────────────────────────────────────────────────────

_geo_cache: dict = {}


def _load_state_rings(max_ring_points: int = 120) -> list[list[tuple]]:
    """Load + downsample NER state polygon rings as [(lat, lon), ...] lists."""
    if "rings" in _geo_cache:
        return _geo_cache["rings"]
    rings: list[list[tuple]] = []
    path = _ASSETS / "ner-states.geojson"
    try:
        gj = json.loads(path.read_text(encoding="utf-8"))
        for feat in gj.get("features", []):
            geom = feat.get("geometry") or {}
            polys = []
            if geom.get("type") == "Polygon":
                polys = [geom.get("coordinates", [])]
            elif geom.get("type") == "MultiPolygon":
                polys = geom.get("coordinates", [])
            for poly in polys:
                if not poly:
                    continue
                outer = poly[0]  # outer ring only — holes are visual noise here
                if len(outer) < 12:
                    continue     # skip tiny islands
                step = max(1, len(outer) // max_ring_points)
                ring = [(pt[1], pt[0]) for pt in outer[::step]]  # (lat, lon)
                rings.append(ring)
    except Exception:
        rings = []
    _geo_cache["rings"] = rings
    return rings


# ── Map drawing ───────────────────────────────────────────────────────────────

# Fixed NER theatre bounds (lon 88–97.5, lat 21.5–29.5) so every PAOI map has
# the same frame regardless of which points it contains.
_MAP_BOUNDS = {"lon_min": 88.0, "lon_max": 97.5, "lat_min": 21.5, "lat_max": 29.5}


def _project(lat: float, lon: float, x: float, y: float, w: float, h: float) -> tuple:
    """Equirectangular projection of lat/lon into the (x, y, w, h) mm box."""
    b = _MAP_BOUNDS
    px = x + (lon - b["lon_min"]) / (b["lon_max"] - b["lon_min"]) * w
    py = y + (b["lat_max"] - lat) / (b["lat_max"] - b["lat_min"]) * h
    return px, py


def _in_bounds(lat: float, lon: float) -> bool:
    b = _MAP_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def draw_paoi_map(pdf, current_points: list[dict], previous_points: list[dict],
                  x: float, y: float, w: float = 120, h: float = 82,
                  unresolved: list[str] | None = None) -> float:
    """
    Draw a PAOI situation map at (x, y): NER state outlines with severity-
    coloured dots — green ring = current period, brown ring = previous period.
    Returns the y coordinate below the map + legend.
    """
    # Frame + background
    pdf.set_fill_color(247, 250, 245)
    pdf.set_draw_color(150, 160, 145)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, w, h, "DF")

    # State outlines
    pdf.set_draw_color(165, 175, 160)
    pdf.set_line_width(0.2)
    for ring in _load_state_rings():
        pts = [_project(lat, lon, x, y, w, h) for lat, lon in ring
               if _in_bounds(lat, lon)]
        for i in range(1, len(pts)):
            (x1, y1), (x2, y2) = pts[i - 1], pts[i]
            # Skip long jump segments created by bounds clipping
            if abs(x2 - x1) < w * 0.15 and abs(y2 - y1) < h * 0.15:
                pdf.line(x1, y1, x2, y2)

    def _plot(points: list[dict], ring_rgb: tuple):
        seen: dict[tuple, int] = {}
        labelled: set = set()
        for p in points:
            if not _in_bounds(p["lat"], p["lon"]):
                continue
            px, py = _project(p["lat"], p["lon"], x, y, w, h)
            # Deterministic jitter for stacked markers at one location
            key = (round(px, 1), round(py, 1))
            n = seen.get(key, 0)
            seen[key] = n + 1
            if n:
                ang = n * 2.4  # golden-angle spiral
                px += 2.2 * math.cos(ang) * (1 + n * 0.15)
                py += 2.2 * math.sin(ang) * (1 + n * 0.15)
            # Ring (period indicator)
            pdf.set_draw_color(*ring_rgb)
            pdf.set_line_width(0.55)
            pdf.circle(px, py, 2.1, "D")
            # Severity dot
            fill = SEV_FILL.get(p["severity"], (110, 110, 110))
            pdf.set_fill_color(*fill)
            pdf.set_draw_color(255, 255, 255)
            pdf.set_line_width(0.2)
            pdf.circle(px, py, 1.25, "DF")
            # Label each distinct place once
            if p["label"] not in labelled and len(labelled) < 10:
                labelled.add(p["label"])
                pdf.set_font("Helvetica", "", 5.5)
                pdf.set_text_color(70, 75, 65)
                pdf.set_xy(px + 2.6, py - 1.2)
                pdf.cell(24, 2.4, p["label"][:20])

    _plot(previous_points or [], RING_PREVIOUS)   # previous under current
    _plot(current_points or [], RING_CURRENT)

    # Legend
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
