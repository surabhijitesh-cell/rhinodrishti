/**
 * NERMap — Leaflet-based intelligence situation map for the NER region.
 *
 * Layers (bottom → top):
 *  1. NASA Blue Marble satellite base (GIBS WMTS tiles)
 *  2. ESRI World Imagery as fallback / sharper detail layer
 *  3. Dark vignette / colour-temperature overlay (CSS)
 *  4. Semi-transparent GeoJSON state polygons coloured by severity
 *  5. Pulsating SVG markers for critical / high / medium intelligence items
 *  6. State name labels
 *
 * Props:
 *   stateStats  — { [regionName]: { count, critical, high } }
 *   items       — raw intelligence items array (for exact-location markers)
 *   onStateClick — (stateName) => void
 */
import { useEffect, useRef, useState, memo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// ─── Known NER / border-region locations ─────────────────────────────────────
// [lat, lon] — used to plot individual intelligence items at their mentioned location
const LOCATION_COORDS = {
  // ── Assam ──
  "Guwahati":      [26.144, 91.736],
  "Silchar":       [24.827, 92.798],
  "Dibrugarh":     [27.480, 94.912],
  "Jorhat":        [26.747, 94.206],
  "Tezpur":        [26.633, 92.793],
  "Tinsukia":      [27.488, 95.361],
  "Nagaon":        [26.348, 92.686],
  "Sivasagar":     [26.984, 94.637],
  "Karimganj":     [24.869, 92.355],
  "Barpeta":       [26.321, 91.005],
  "Goalpara":      [26.170, 90.623],
  "Kokrajhar":     [26.399, 90.269],
  "Dhubri":        [26.015, 89.975],
  "Hailakandi":    [24.682, 92.562],
  "Haflong":       [25.165, 93.021],
  "Tingkhong":     [27.211, 95.015],
  "Numaligarh":    [26.668, 93.693],
  "Bongaigaon":    [26.477, 90.558],
  "Lakhimpur":     [27.234, 94.101],
  // ── Manipur ──
  "Imphal":        [24.818, 93.944],
  "Moreh":         [24.241, 94.272],
  "Churachandpur": [24.337, 93.682],
  "Senapati":      [25.262, 94.015],
  "Ukhrul":        [25.130, 94.365],
  "Bishnupur":     [24.620, 93.762],
  "Thoubal":       [24.639, 93.999],
  "Chandel":       [24.221, 94.027],
  "Tamenglong":    [24.979, 93.498],
  "Jiribam":       [24.798, 93.115],
  "Kangpokpi":     [25.146, 93.953],
  // ── Mizoram ──
  "Aizawl":        [23.727, 92.718],
  "Lunglei":       [22.888, 92.735],
  "Champhai":      [23.457, 93.326],
  "Serchhip":      [23.311, 92.843],
  "Lawngtlai":     [22.517, 92.897],
  "Kolasib":       [24.225, 92.683],
  // ── Nagaland ──
  "Kohima":        [25.675, 94.109],
  "Dimapur":       [25.906, 93.728],
  "Mokokchung":    [26.327, 94.519],
  "Tuensang":      [26.272, 94.821],
  "Wokha":         [26.103, 94.262],
  "Zunheboto":     [26.013, 94.520],
  "Phek":          [25.669, 94.466],
  "Mon":           [26.726, 95.017],
  // ── Arunachal Pradesh ──
  "Itanagar":      [27.085, 93.609],
  "Naharlagun":    [27.104, 93.696],
  "Tawang":        [27.586, 91.867],
  "Bomdila":       [27.264, 92.422],
  "Pasighat":      [28.063, 95.325],
  "Ziro":          [27.541, 93.833],
  "Along":         [28.160, 94.800],
  "Tezu":          [27.916, 96.172],
  "Khonsa":        [27.014, 95.516],
  "Changlang":     [27.129, 95.746],
  "Dibang Valley": [28.500, 95.500],
  "Anjaw":         [28.200, 96.800],
  "Namsai":        [27.680, 95.832],
  "Longding":      [26.930, 95.568],
  // ── Meghalaya ──
  "Shillong":      [25.574, 91.882],
  "Tura":          [25.513, 90.216],
  "Jowai":         [25.451, 92.202],
  "Nongstoin":     [25.519, 91.264],
  "Baghmara":      [25.197, 90.635],
  "Resubelpara":   [25.884, 90.726],
  // ── Tripura ──
  "Agartala":      [23.836, 91.279],
  "Dharmanagar":   [24.374, 92.168],
  "Udaipur":       [23.538, 91.487],
  "Sabroom":       [23.007, 91.715],
  "Belonia":       [23.254, 91.451],
  "Kailashahar":   [24.332, 92.010],
  "Khowai":        [24.072, 91.614],
  // ── Sikkim ──
  "Gangtok":       [27.339, 88.612],
  // ── Bangladesh ──
  "Dhaka":         [23.810, 90.413],
  "Chittagong":    [22.335, 91.834],
  "Sylhet":        [24.899, 91.872],
  "Cox's Bazar":   [21.428, 92.005],
  "Coxs Bazar":    [21.428, 92.005],
  "Bandarban":     [22.195, 92.219],
  "Teknaf":        [20.861, 92.303],
  "Khulna":        [22.845, 89.540],
  "Rajshahi":      [24.374, 88.602],
  "Rangpur":       [25.746, 89.252],
  "Mymensingh":    [24.747, 90.407],
  "Jessore":       [23.163, 89.208],
  "Comilla":       [23.461, 91.180],
  "Bogra":         [24.848, 89.372],
  "Barisal":       [22.701, 90.370],
  "Narayanganj":   [23.623, 90.499],
  "Rangamati":     [22.644, 92.201],
  "Khagrachhari":  [23.122, 91.950],
  // ── Myanmar ──
  "Naypyidaw":     [19.745, 96.129],
  "Yangon":        [16.867, 96.195],
  "Mandalay":      [21.978, 96.084],
  "Tamu":          [24.213, 94.301],
  "Sagaing":       [21.877, 95.979],
  "Chin State":    [22.500, 93.700],
  "Sagaing Region":[23.500, 95.000],
  "Rakhine":       [20.000, 93.500],
  "Kayah":         [19.500, 97.500],
  "Kachin":        [25.500, 96.500],
  // ── Generic NE ──
  "Brahmaputra":   [27.200, 93.500],
  "Barak Valley":  [24.800, 92.800],
  "Lushai Hills":  [23.200, 92.800],
  "Naga Hills":    [25.700, 94.300],
};

// State centre coordinates for label / fallback markers
const STATE_CENTERS = {
  "Arunachal Pradesh": [28.0, 94.5],
  "Assam":             [26.2, 92.5],
  "Nagaland":          [26.0, 94.5],
  "Manipur":           [24.8, 93.9],
  "Meghalaya":         [25.5, 91.3],
  "Tripura":           [23.8, 91.7],
  "Mizoram":           [23.2, 92.8],
  "Sikkim":            [27.5, 88.5],
  "West Bengal":       [24.5, 88.0],
  "Bangladesh":        [23.7, 90.3],
  "Myanmar":           [21.5, 96.5],
};

// ─── Severity colours matching dashboard severity cards ───────────────────────
const SEV = {
  critical: { fill: "rgba(239,68,68,0.28)",    stroke: "#ef4444", strokeW: 2.0, glow: "#ef4444" },
  high:     { fill: "rgba(245,158,11,0.22)",   stroke: "#f59e0b", strokeW: 1.6, glow: "#f59e0b" },
  medium:   { fill: "rgba(234,179,8,0.14)",    stroke: "#eab308", strokeW: 1.0, glow: "#eab308" },
  none:     { fill: "rgba(255,255,255,0.03)",  stroke: "rgba(255,255,255,0.15)", strokeW: 0.5, glow: null },
};

function stateSeverity(stats) {
  if (!stats || stats.count === 0) return "none";
  if (stats.critical > 0)         return "critical";
  if (stats.high > 0)             return "high";
  return "medium";
}

// ─── Pulsating marker HTML ─────────────────────────────────────────────────────
function pulseMarkerHtml(severity, count) {
  const cfg = {
    critical: { outer: 22, inner: 10, color: "#ef4444", rings: 3, dur: 1.8 },
    high:     { outer: 18, inner:  8, color: "#f59e0b", rings: 2, dur: 2.2 },
    medium:   { outer: 12, inner:  6, color: "#eab308", rings: 1, dur: 3.0 },
  }[severity] || { outer: 10, inner: 5, color: "#6b7280", rings: 0, dur: 3 };

  const rings = Array.from({ length: cfg.rings }, (_, i) => `
    <div class="map-pulse-ring" style="
      position:absolute; border-radius:50%;
      width:${cfg.outer}px; height:${cfg.outer}px;
      top:0; left:0;
      border: 2px solid ${cfg.color};
      animation: map-pulse ${cfg.dur}s ${i * (cfg.dur / cfg.rings)}s ease-out infinite;
      opacity:0;
    "></div>
  `).join("");

  const label = count > 1
    ? `<span style="
        position:absolute; top:50%; left:50%;
        transform:translate(-50%,-50%);
        font:bold 8px/1 'JetBrains Mono',monospace;
        color:#fff; pointer-events:none;
      ">${count}</span>`
    : "";

  return `<div style="position:relative; width:${cfg.outer}px; height:${cfg.outer}px;">
    ${rings}
    <div style="
      position:absolute; top:50%; left:50%;
      transform:translate(-50%,-50%);
      width:${cfg.inner}px; height:${cfg.inner}px;
      background:${cfg.color};
      border-radius:50%;
      border:2px solid #fff;
      box-shadow:0 0 6px 2px ${cfg.color}88;
    "></div>
    ${label}
  </div>`;
}

// ─── CSS injected once ────────────────────────────────────────────────────────
const MAP_CSS = `
@keyframes map-pulse {
  0%   { transform: scale(1);   opacity: 0.8; }
  70%  { transform: scale(2.4); opacity: 0; }
  100% { transform: scale(2.4); opacity: 0; }
}
.leaflet-container { background: #0a0f0a !important; }
.map-pop { font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.map-pop b { color: #a3e635; font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; }
`;

function injectCSS(css) {
  if (document.getElementById("ner-map-css")) return;
  const el = document.createElement("style");
  el.id = "ner-map-css";
  el.textContent = css;
  document.head.appendChild(el);
}

// ─── Main component ───────────────────────────────────────────────────────────
const InteractiveNERMap = memo(function InteractiveNERMap({ stateStats = {}, items = [], onStateClick }) {
  const mapRef      = useRef(null);
  const leafletRef  = useRef(null);   // L.Map instance
  const markersRef  = useRef(null);   // L.LayerGroup for intel markers
  const geoLayerRef = useRef(null);   // L.GeoJSON state layer

  // ── Init map once ──────────────────────────────────────────────────────────
  useEffect(() => {
    injectCSS(MAP_CSS);
    if (!mapRef.current || leafletRef.current) return;

    const map = L.map(mapRef.current, {
      center: [25.0, 92.5],
      zoom: 6,
      minZoom: 5,
      maxZoom: 12,
      zoomControl: false,
      attributionControl: false,
    });
    leafletRef.current = map;

    // ── Layer 1: NASA Blue Marble (GIBS WMTS) ────────────────────────────────
    const nasaBlueMarble = L.tileLayer(
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/" +
      "BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg",
      { maxZoom: 8, opacity: 1.0, crossOrigin: true }
    );

    // ── Layer 2: ESRI World Imagery (higher zoom fallback) ───────────────────
    const esriImagery = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 12, opacity: 0, crossOrigin: true }
    );

    // Blend: show NASA Blue Marble at lower zoom, switch to ESRI detail when zoomed in
    nasaBlueMarble.addTo(map);
    esriImagery.addTo(map);

    map.on("zoomend", () => {
      const z = map.getZoom();
      nasaBlueMarble.setOpacity(z <= 7 ? 1.0 : 0.0);
      esriImagery.setOpacity(z >= 7 ? 1.0 : 0.0);
    });

    // ── Dark tactical vignette overlay ────────────────────────────────────────
    // A subtle scan-line grid pattern consistent with the app's military aesthetic
    const scanCanvas = document.createElement("canvas");
    scanCanvas.width = 4; scanCanvas.height = 4;
    const ctx = scanCanvas.getContext("2d");
    ctx.fillStyle = "rgba(0,0,0,0)";
    ctx.fillRect(0, 0, 4, 4);
    ctx.strokeStyle = "rgba(10,30,10,0.18)";
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(0, 2); ctx.lineTo(4, 2); ctx.stroke();

    L.imageOverlay(
      scanCanvas.toDataURL(),
      [[-90, -180], [90, 180]],
      { opacity: 1, crossOrigin: true, className: "ner-scan-overlay" }
    ).addTo(map);

    // ── Zoom control ───────────────────────────────────────────────────────────
    L.control.zoom({ position: "topright" }).addTo(map);

    // ── Marker layer group ─────────────────────────────────────────────────────
    markersRef.current = L.layerGroup().addTo(map);

    // ── Attribution ────────────────────────────────────────────────────────────
    L.control.attribution({ position: "bottomleft", prefix: false })
      .addAttribution('<span style="font-size:8px;opacity:0.4">NASA Blue Marble · ESRI</span>')
      .addTo(map);

    return () => {
      map.remove();
      leafletRef.current = null;
    };
  }, []);

  // ── Re-draw GeoJSON state layers when stateStats changes ───────────────────
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;

    if (geoLayerRef.current) {
      geoLayerRef.current.remove();
      geoLayerRef.current = null;
    }

    async function loadLayers() {
      try {
        const [nerRes, borderRes] = await Promise.all([
          fetch("/ner-states.geojson"),
          fetch("/border-countries.geojson"),
        ]);
        const nerGeo    = await nerRes.json();
        const borderGeo = await borderRes.json();

        const NER_STATES    = ["Assam","Meghalaya","Mizoram","Manipur","Arunachal Pradesh","Tripura","Nagaland","Sikkim"];
        const NEIGHBOR      = ["West Bengal"];
        const BORDER_NAMES  = ["Bangladesh","Myanmar"];

        function styleFor(name, isNER) {
          const sev = isNER
            ? stateSeverity(stateStats[name])
            : stateSeverity(stateStats[name]);
          const s = SEV[sev];
          return {
            fillColor:   s.fill,
            color:       s.stroke,
            weight:      s.strokeW,
            fillOpacity: 1,
            opacity:     1,
          };
        }

        const group = L.layerGroup().addTo(map);

        // Border countries with dashed stroke
        L.geoJSON(borderGeo, {
          style: (feat) => {
            const name = feat.properties.name;
            return { ...styleFor(name, true), dashArray: "6 3" };
          },
          onEachFeature: (feat, layer) => {
            const name = feat.properties.name;
            if (!BORDER_NAMES.includes(name)) return;
            layer.bindPopup(_popup(name, stateStats[name]));
            layer.on("click", () => onStateClick && onStateClick(name));
            layer.on("mouseover", () => layer.setStyle({ weight: layer.options.weight + 1, filter: "brightness(1.5)" }));
            layer.on("mouseout",  () => layer.setStyle({ weight: layer.options.weight - 1, filter: "" }));
          },
        }).addTo(group);

        // NER + neighbours
        L.geoJSON(nerGeo, {
          filter: (feat) => {
            const n = feat.properties.ST_NM;
            return NER_STATES.includes(n) || NEIGHBOR.includes(n);
          },
          style: (feat) => {
            const name = feat.properties.ST_NM;
            if (NEIGHBOR.includes(name)) {
              return { fillColor: "rgba(255,255,255,0.02)", color: "rgba(255,255,255,0.1)", weight: 0.4, fillOpacity: 1 };
            }
            return styleFor(name, true);
          },
          onEachFeature: (feat, layer) => {
            const name = feat.properties.ST_NM;
            if (!NER_STATES.includes(name)) return;
            layer.bindPopup(_popup(name, stateStats[name]));
            layer.on("click", () => onStateClick && onStateClick(name));
            layer.on("mouseover", () => layer.setStyle({ weight: (layer.options.weight || 1) + 0.8 }));
            layer.on("mouseout",  () => layer.setStyle({ weight: (layer.options.weight || 1) - 0.8 }));
          },
        }).addTo(group);

        // State name labels (DivIcon)
        Object.entries(STATE_CENTERS).forEach(([name, [lat, lon]]) => {
          const stats = stateStats[name];
          const count = stats?.count || 0;
          L.marker([lat, lon], {
            icon: L.divIcon({
              className: "",
              html: `<div style="
                font-family:'Barlow Condensed',sans-serif;
                font-size:10px; font-weight:700;
                color:rgba(255,255,255,0.75);
                text-transform:uppercase; letter-spacing:0.12em;
                text-shadow: 0 1px 3px rgba(0,0,0,0.9), 0 0 6px rgba(0,0,0,0.6);
                white-space:nowrap; pointer-events:none;
              ">${name}${count ? `<br/><span style="font-size:8px;opacity:0.55;letter-spacing:0.05em">${count} items</span>` : ""}</div>`,
              iconAnchor: [0, 0],
            }),
            interactive: false,
          }).addTo(group);
        });

        geoLayerRef.current = group;
      } catch (e) {
        console.error("NERMap GeoJSON load error:", e);
      }
    }

    loadLayers();
  }, [stateStats, onStateClick]);

  // ── Re-draw intelligence item markers when items change ────────────────────
  useEffect(() => {
    const mg = markersRef.current;
    if (!mg) return;
    mg.clearLayers();

    // Build a map: location string → best severity among items mentioning it
    const locationSev = {};   // "CityName" → { sev, count, title, state }

    items.forEach((item) => {
      const sev = item.severity;
      if (!["critical","high","medium"].includes(sev)) return;

      // Collect candidate location names: named entities + state name
      const candidates = [
        ...(item.entities?.locations || []),
        item.state,
      ].filter(Boolean);

      const matched = new Set();
      candidates.forEach((loc) => {
        // Exact match
        if (LOCATION_COORDS[loc]) {
          matched.add(loc);
          return;
        }
        // Partial match — find key that contains or is contained in loc
        Object.keys(LOCATION_COORDS).forEach((k) => {
          if (loc.toLowerCase().includes(k.toLowerCase()) || k.toLowerCase().includes(loc.toLowerCase())) {
            matched.add(k);
          }
        });
      });

      matched.forEach((locKey) => {
        if (!locationSev[locKey]) {
          locationSev[locKey] = { sev: "medium", count: 0, titles: [], state: item.state };
        }
        const existing = locationSev[locKey];
        // Escalate severity (critical > high > medium)
        const rank = { critical: 3, high: 2, medium: 1 };
        if ((rank[sev] || 0) > (rank[existing.sev] || 0)) existing.sev = sev;
        existing.count++;
        if (existing.titles.length < 3) existing.titles.push(item.title || "");
      });
    });

    // Place markers
    Object.entries(locationSev).forEach(([locKey, info]) => {
      const coords = LOCATION_COORDS[locKey];
      if (!coords) return;
      const { sev, count, titles, state } = info;
      const sz = { critical: 22, high: 18, medium: 12 }[sev] || 12;

      const icon = L.divIcon({
        className: "",
        html: pulseMarkerHtml(sev, count > 1 ? count : 0),
        iconSize: [sz, sz],
        iconAnchor: [sz / 2, sz / 2],
      });

      const popupHtml = `<div class="map-pop">
        <b>${locKey}</b>
        <div style="margin-top:4px; color:#6b7280; font-size:9px; text-transform:uppercase; letter-spacing:.08em">
          ${sev} severity · ${count} item${count > 1 ? "s" : ""}${state ? ` · ${state}` : ""}
        </div>
        ${titles.map(t => `<div style="margin-top:3px; color:#d4d4d4; font-size:10px; line-height:1.4">${t.slice(0,80)}${t.length>80?"…":""}</div>`).join("")}
      </div>`;

      L.marker(coords, { icon, zIndexOffset: sev === "critical" ? 1000 : sev === "high" ? 500 : 0 })
        .bindPopup(popupHtml, { maxWidth: 260, className: "ner-popup" })
        .addTo(mg);
    });
  }, [items]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }} data-testid="ner-map">
      {/* Title overlay */}
      <div style={{
        position: "absolute", top: 10, left: 10, zIndex: 1000,
        pointerEvents: "none",
      }}>
        <p style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 10, textTransform: "uppercase",
          letterSpacing: "0.2em", color: "rgba(255,255,255,0.45)",
          margin: 0, textShadow: "0 1px 3px rgba(0,0,0,0.8)",
        }}>
          NER + Border Threat Map
        </p>
      </div>

      {/* Legend */}
      <div style={{
        position: "absolute", bottom: 24, right: 8, zIndex: 1000,
        background: "rgba(0,0,0,0.65)", border: "1px solid rgba(255,255,255,0.1)",
        padding: "6px 8px", backdropFilter: "blur(4px)",
        pointerEvents: "none",
      }}>
        {[
          { sev: "critical", color: "#ef4444", label: "Critical" },
          { sev: "high",     color: "#f59e0b", label: "High" },
          { sev: "medium",   color: "#eab308", label: "Medium" },
        ].map(({ color, label, sev }) => (
          <div key={sev} style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 3 }}>
            <div style={{
              width: sev === "critical" ? 10 : sev === "high" ? 8 : 6,
              height: sev === "critical" ? 10 : sev === "high" ? 8 : 6,
              borderRadius: "50%", background: color,
              boxShadow: `0 0 5px ${color}`,
            }} />
            <span style={{
              fontFamily: "ui-monospace, monospace", fontSize: 8,
              color: "rgba(255,255,255,0.6)", textTransform: "uppercase", letterSpacing: "0.08em",
            }}>{label}</span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 2 }}>
          <div style={{ width: 10, height: 3, background: "rgba(255,255,255,0.2)", border: "1px dashed rgba(255,255,255,0.3)" }} />
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 8, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Border Region</span>
        </div>
      </div>

      {/* Leaflet map div */}
      <div
        ref={mapRef}
        style={{ width: "100%", height: "100%", minHeight: 380 }}
        data-testid="composable-map"
      />

      {/* Custom popup styles */}
      <style>{`
        .ner-popup .leaflet-popup-content-wrapper {
          background: rgba(10,15,10,0.92) !important;
          border: 1px solid rgba(255,255,255,0.15) !important;
          border-radius: 2px !important;
          color: #d4d4d4 !important;
          backdrop-filter: blur(6px);
        }
        .ner-popup .leaflet-popup-tip {
          background: rgba(10,15,10,0.92) !important;
        }
        .leaflet-zoom-animated { will-change: transform; }
      `}</style>
    </div>
  );
});

// ── Popup helper ─────────────────────────────────────────────────────────────
function _popup(name, stats) {
  const s = stats || { count: 0, critical: 0, high: 0 };
  return L.popup({ className: "ner-popup", maxWidth: 200 }).setContent(`
    <div class="map-pop">
      <b>${name}</b>
      <div style="margin-top:4px; font-size:9px; color:#6b7280; text-transform:uppercase; letter-spacing:.08em">
        ${s.count || 0} intelligence item${s.count !== 1 ? "s" : ""}
      </div>
      ${s.critical > 0 ? `<div style="color:#ef4444;font-size:10px;margin-top:2px">● ${s.critical} critical</div>` : ""}
      ${s.high > 0     ? `<div style="color:#f59e0b;font-size:10px;margin-top:2px">● ${s.high} high</div>` : ""}
    </div>
  `);
}

export default InteractiveNERMap;
