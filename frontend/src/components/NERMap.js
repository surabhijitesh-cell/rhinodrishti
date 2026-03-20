import { useState, useEffect, memo } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
  Marker,
} from "react-simple-maps";
import { Badge } from "../components/ui/badge";

const NER_GEO_URL = "/ner-states.geojson";
const BORDER_GEO_URL = "/border-countries.geojson";

const NER_STATES = [
  "Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura"
];
const MONITORED_REGIONS = [...NER_STATES, "Bangladesh", "Myanmar"];

const NEIGHBOR_STATES = ["Nagaland", "Sikkim", "West Bengal"];

// Approximate label positions for each region (lon, lat)
const REGION_LABELS = {
  "Arunachal Pradesh": [94.5, 28.0],
  "Assam": [92.5, 26.2],
  "Nagaland": [94.5, 26.0],
  "Manipur": [93.9, 24.8],
  "Meghalaya": [91.3, 25.5],
  "Tripura": [91.7, 23.8],
  "Mizoram": [92.8, 23.2],
  "Sikkim": [88.5, 27.5],
  "West Bengal": [88.0, 24.5],
  "Bangladesh": [90.3, 23.7],
  "Myanmar": [96.5, 21.5],
};

function getSeverityFill(stats, isNER) {
  if (!stats || stats.count === 0) {
    return isNER ? "hsl(120, 8%, 22%)" : "hsl(120, 5%, 16%)";
  }
  if (stats.critical > 0) return "hsl(0, 65%, 38%)";
  if (stats.high > 0) return "hsl(38, 75%, 38%)";
  if (stats.count > 3) return "hsl(84, 50%, 30%)";
  return "hsl(84, 40%, 25%)";
}

function getSeverityStroke(stats) {
  if (!stats || stats.count === 0) return "hsl(120, 5%, 30%)";
  if (stats.critical > 0) return "hsl(0, 70%, 50%)";
  if (stats.high > 0) return "hsl(38, 80%, 55%)";
  return "hsl(84, 60%, 45%)";
}

const InteractiveNERMap = memo(function InteractiveNERMap({ stateStats = {}, onStateClick }) {
  const [tooltip, setTooltip] = useState(null);
  const [position, setPosition] = useState({ coordinates: [92.5, 25], zoom: 1 });

  const handleZoomIn = () => setPosition((p) => ({ ...p, zoom: Math.min(p.zoom * 1.5, 6) }));
  const handleZoomOut = () => setPosition((p) => ({ ...p, zoom: Math.max(p.zoom / 1.5, 0.5) }));
  const handleReset = () => setPosition({ coordinates: [92.5, 25], zoom: 1 });

  // Collect markers for critical alerts
  const criticalMarkers = [];
  Object.entries(stateStats).forEach(([region, stats]) => {
    if (stats.critical > 0 && REGION_LABELS[region]) {
      criticalMarkers.push({
        name: region,
        coordinates: REGION_LABELS[region],
        count: stats.critical,
      });
    }
  });

  return (
    <div className="map-container relative" data-testid="ner-map">
      {/* Title */}
      <div className="absolute top-2 left-3 z-10">
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-mono">
          NER + Border Threat Map
        </p>
      </div>

      {/* Zoom controls */}
      <div className="absolute top-2 right-3 z-10 flex flex-col gap-1" data-testid="map-zoom-controls">
        <button
          onClick={handleZoomIn}
          className="w-6 h-6 bg-card border border-border text-xs font-bold hover:bg-secondary flex items-center justify-center"
          data-testid="map-zoom-in"
        >+</button>
        <button
          onClick={handleZoomOut}
          className="w-6 h-6 bg-card border border-border text-xs font-bold hover:bg-secondary flex items-center justify-center"
          data-testid="map-zoom-out"
        >-</button>
        <button
          onClick={handleReset}
          className="w-6 h-6 bg-card border border-border text-[8px] font-bold hover:bg-secondary flex items-center justify-center"
          data-testid="map-zoom-reset"
        >R</button>
      </div>

      <ComposableMap
        projection="geoMercator"
        projectionConfig={{
          center: [92.5, 25],
          scale: 2800,
        }}
        style={{ width: "100%", height: "auto" }}
        data-testid="composable-map"
      >
        <ZoomableGroup
          center={position.coordinates}
          zoom={position.zoom}
          onMoveEnd={setPosition}
        >
          {/* Grid background */}
          <defs>
            <pattern id="mapGrid" width="2" height="2" patternUnits="userSpaceOnUse">
              <path d="M 2 0 L 0 0 0 2" fill="none" stroke="hsl(120,5%,18%)" strokeWidth="0.05" />
            </pattern>
          </defs>
          <rect x="-500" y="-500" width="2000" height="2000" fill="url(#mapGrid)" />

          {/* Bangladesh & Myanmar (border countries - monitored) */}
          <Geographies geography={BORDER_GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const name = geo.properties.name;
                const stats = stateStats[name] || { count: 0, critical: 0, high: 0 };
                const isHovered = tooltip?.name === name;
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={getSeverityFill(stats, false)}
                    stroke={isHovered ? "hsl(84, 80%, 55%)" : getSeverityStroke(stats)}
                    strokeWidth={isHovered ? 1.5 : 0.8}
                    strokeDasharray="4,2"
                    style={{
                      default: { outline: "none", cursor: "pointer" },
                      hover: { outline: "none", cursor: "pointer", filter: "brightness(1.3)" },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={() => setTooltip({ name, stats })}
                    onMouseLeave={() => setTooltip(null)}
                    onClick={() => onStateClick && onStateClick(name)}
                    data-testid={`map-region-${name.toLowerCase()}`}
                  />
                );
              })
            }
          </Geographies>

          {/* NER States (India) */}
          <Geographies geography={NER_GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const name = geo.properties.ST_NM;
                const isNER = NER_STATES.includes(name);
                const isNeighbor = NEIGHBOR_STATES.includes(name);
                const stats = stateStats[name] || { count: 0, critical: 0, high: 0 };
                const isHovered = tooltip?.name === name;

                if (!isNER && !isNeighbor) return null;

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={isNeighbor ? "hsl(120, 5%, 14%)" : getSeverityFill(stats, true)}
                    stroke={isHovered && isNER ? "hsl(84, 80%, 55%)" : isNER ? getSeverityStroke(stats) : "hsl(120, 5%, 25%)"}
                    strokeWidth={isHovered && isNER ? 1.5 : isNER ? 0.8 : 0.4}
                    style={{
                      default: { outline: "none", cursor: isNER ? "pointer" : "default" },
                      hover: { outline: "none", cursor: isNER ? "pointer" : "default", filter: isNER ? "brightness(1.3)" : "none" },
                      pressed: { outline: "none" },
                    }}
                    onMouseEnter={() => isNER && setTooltip({ name, stats })}
                    onMouseLeave={() => setTooltip(null)}
                    onClick={() => isNER && onStateClick && onStateClick(name)}
                    data-testid={`map-region-${name.toLowerCase().replace(/\s+/g, '-')}`}
                  />
                );
              })
            }
          </Geographies>

          {/* Region labels */}
          {Object.entries(REGION_LABELS).map(([name, coords]) => {
            if (NEIGHBOR_STATES.includes(name)) return null;
            const stats = stateStats[name] || { count: 0 };
            const isCountry = ["Bangladesh", "Myanmar"].includes(name);
            return (
              <Marker key={`label-${name}`} coordinates={coords}>
                <text
                  textAnchor="middle"
                  style={{
                    fontFamily: "Barlow Condensed, sans-serif",
                    fontSize: isCountry ? "5px" : "4px",
                    fontWeight: 600,
                    fill: "hsl(120, 5%, 80%)",
                    textTransform: "uppercase",
                    pointerEvents: "none",
                    letterSpacing: "0.05em",
                  }}
                >
                  {name.length > 10 ? name.split(" ").map((w, i) => (
                    <tspan key={i} x="0" dy={i === 0 ? 0 : "5px"}>{w}</tspan>
                  )) : name}
                </text>
                {stats.count > 0 && (
                  <text
                    textAnchor="middle"
                    y={name.split(" ").length > 1 ? 11 : 6}
                    style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "3px",
                      fill: "hsl(120, 5%, 55%)",
                      pointerEvents: "none",
                    }}
                  >
                    {stats.count} items
                  </text>
                )}
              </Marker>
            );
          })}

          {/* Critical markers (pulsing red dots) */}
          {criticalMarkers.map((m) => (
            <Marker key={`crit-${m.name}`} coordinates={[m.coordinates[0] + 1.5, m.coordinates[1] + 0.5]}>
              <circle r={3} fill="hsl(0, 85%, 50%)" opacity={0.9}>
                <animate attributeName="r" values="3;4.5;3" dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" repeatCount="indefinite" />
              </circle>
              <text
                textAnchor="middle"
                y={1.2}
                style={{
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: "3px",
                  fontWeight: "bold",
                  fill: "white",
                  pointerEvents: "none",
                }}
              >
                {m.count}
              </text>
            </Marker>
          ))}
        </ZoomableGroup>
      </ComposableMap>

      {/* Tooltip */}
      {tooltip && (
        <div className="absolute bottom-14 left-1/2 -translate-x-1/2 z-20 bg-card border border-primary px-3 py-2 min-w-[160px]" data-testid="map-tooltip">
          <p className="text-xs font-bold uppercase tracking-wider font-['Barlow_Condensed']">{tooltip.name}</p>
          <div className="flex items-center gap-3 mt-1 text-[10px] font-mono text-muted-foreground">
            <span>{tooltip.stats.count || 0} items</span>
            {tooltip.stats.critical > 0 && (
              <span className="text-red-400">{tooltip.stats.critical} critical</span>
            )}
            {tooltip.stats.high > 0 && (
              <span className="text-amber-400">{tooltip.stats.high} high</span>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2 right-3 flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5" style={{ background: "hsl(0, 65%, 38%)" }} />
          <span className="text-[9px] font-mono text-muted-foreground">Critical</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5" style={{ background: "hsl(38, 75%, 38%)" }} />
          <span className="text-[9px] font-mono text-muted-foreground">High</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5" style={{ background: "hsl(84, 50%, 30%)" }} />
          <span className="text-[9px] font-mono text-muted-foreground">Active</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 border border-dashed border-muted-foreground" />
          <span className="text-[9px] font-mono text-muted-foreground">Border Region</span>
        </div>
      </div>
    </div>
  );
});

export default InteractiveNERMap;
