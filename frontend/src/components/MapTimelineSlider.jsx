/**
 * MapTimelineSlider — Temporal Intelligence scrubber for the NER situation map.
 *
 * Phase 1 (no pattern engine yet):
 *  - 24h / 7d / 30d range selectors with auto-scaled default windows
 *  - Adjustable active-window width via always-visible native select
 *  - Auto-positions window over the newest available item on first load
 *    so something pulses immediately (not centred on "now" if no recent data)
 *  - Draggable scrubber to step through time
 *  - Live mode anchors window-end to "now"
 *  - Pause / play / step buttons
 *  - Severity-density gradient bar showing where events cluster on the timeline
 *  - Event dots for critical/high
 *
 * Output (via onWindowChange callback):
 *   (windowStart, windowEnd, rangeStart, rangeEnd) — all Date objects.
 *
 * Parent (Dashboard) tags items with `_opacity` per timestamp distance and
 * passes them to <NERMap items={...} />. STATE-POLYGON colouring on the map
 * uses a separate stateStats prop that is NOT timeline-filtered, so the
 * state-boundary layer is unaffected by scrubbing — only the markers fade.
 */
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  Play, Pause, SkipBack, SkipForward, Clock, Radio,
} from "lucide-react";

// ── Range presets (entire slider span) ─────────────────────────────────────────
const RANGE_OPTIONS = [
  { id: 24,   label: "24h",  hours: 24      },
  { id: 168,  label: "7d",   hours: 24 * 7  },
  { id: 720,  label: "30d",  hours: 24 * 30 },
];

// ── Sensible default active-window width per slider range ─────────────────────
const DEFAULT_WINDOW_FOR_RANGE = {
  24:  3,    // 24h slider → 3h window
  168: 12,   // 7d slider  → 12h window
  720: 24,   // 30d slider → 24h window
};

// ── Active-window presets (width of the bright slice) ──────────────────────────
const WINDOW_PRESETS = [
  { label: "30 min", hours: 0.5 },
  { label: "1 hour", hours: 1   },
  { label: "3 hours",hours: 3   },
  { label: "6 hours",hours: 6   },
  { label: "12 hours",hours: 12 },
  { label: "24 hours",hours: 24 },
  { label: "3 days", hours: 72  },
  { label: "7 days", hours: 168 },
];

// ── Utility helpers ────────────────────────────────────────────────────────────
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
const ms = (h) => h * 3600 * 1000;
function fmtTime(d) {
  return d.toLocaleString("en-GB", {
    day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}
function fmtRel(d, now) {
  const diff = (now - d) / 1000;
  if (diff < 60)        return `${Math.round(diff)}s ago`;
  if (diff < 3600)      return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400)     return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

// ── Severity color palette (matches NERMap markers) ────────────────────────────
const SEV_COLOR = {
  critical: [239, 68, 68],    // #ef4444 red
  high:     [245, 158, 11],   // #f59e0b amber
  medium:   [6, 182, 212],    // #06b6d4 cyan
};

// ── Compute marker opacity for an item given the active window ─────────────────
//   In window      → 1.0  (full pulse)
//   Within 1× window-width either side → linear fade 0.95 → 0.25
//   Beyond that but still in slider range → 0.15
export function computeItemOpacity(itemDate, windowStart, windowEnd, rangeStart, rangeEnd) {
  const t = itemDate.getTime();
  const ws = windowStart.getTime();
  const we = windowEnd.getTime();
  const rs = rangeStart.getTime();
  const re = rangeEnd.getTime();

  if (t >= ws && t <= we) return 1.0;
  if (t < rs || t > re)   return 0.0;   // outside slider entirely

  const windowMs = we - ws;
  const distance = t < ws ? (ws - t) : (t - we);
  const fadeBand = windowMs;            // 1× window-width fade band

  if (distance <= fadeBand) {
    const f = distance / fadeBand;
    return 0.95 - f * 0.70;
  }
  return 0.15;
}

// ── Density bucket helper — splits range into N buckets, counts severity ─────
function buildDensityBuckets(items, rangeStart, rangeEnd, numBuckets = 48) {
  const buckets = Array.from({ length: numBuckets }, () => ({
    critical: 0, high: 0, medium: 0, total: 0,
  }));
  if (!items || !items.length) return buckets;
  const rs = rangeStart.getTime();
  const re = rangeEnd.getTime();
  const span = re - rs;
  if (span <= 0) return buckets;
  for (const it of items) {
    if (!it.published_at) continue;
    const t = new Date(it.published_at).getTime();
    if (t < rs || t > re) continue;
    const idx = clamp(Math.floor(((t - rs) / span) * numBuckets), 0, numBuckets - 1);
    const sev = it.severity;
    if (sev === "critical") buckets[idx].critical++;
    else if (sev === "high") buckets[idx].high++;
    else if (sev === "medium") buckets[idx].medium++;
    buckets[idx].total++;
  }
  return buckets;
}

// Mix severity colors weighted by count, return rgba string with given alpha
function bucketRgba(b, alpha) {
  const total = b.critical + b.high + b.medium;
  if (total === 0) return "rgba(0,0,0,0)";
  const r = (SEV_COLOR.critical[0] * b.critical + SEV_COLOR.high[0] * b.high + SEV_COLOR.medium[0] * b.medium) / total;
  const g = (SEV_COLOR.critical[1] * b.critical + SEV_COLOR.high[1] * b.high + SEV_COLOR.medium[1] * b.medium) / total;
  const bl= (SEV_COLOR.critical[2] * b.critical + SEV_COLOR.high[2] * b.high + SEV_COLOR.medium[2] * b.medium) / total;
  return `rgba(${Math.round(r)},${Math.round(g)},${Math.round(bl)},${alpha})`;
}

// ── Main component ────────────────────────────────────────────────────────────
export default function MapTimelineSlider({
  items = [],          // raw items from /intelligence/map-timeline
  onWindowChange,      // (windowStart, windowEnd, rangeStart, rangeEnd) => void
  onRangeChange,       // (hours) => triggers parent to refetch with new range
  defaultRangeHours = 24,
  defaultWindowHours = 3,
}) {
  // ── State ───────────────────────────────────────────────────────────────────
  const [rangeHours,  setRangeHours]  = useState(defaultRangeHours);
  const [windowHours, setWindowHours] = useState(defaultWindowHours);
  const [scrub,       setScrub]       = useState(1.0);   // 0 = oldest end, 1 = newest end (= now in live mode)
  const [mode,        setMode]        = useState("live");// "live" | "paused"
  const [hoverInfo,   setHoverInfo]   = useState(null);
  const initialAutoPositionedRef = useRef(false);

  // Tick — drives "live" mode so window-end stays anchored to wall-clock now
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (mode !== "live") return;
    const id = setInterval(() => setTick((t) => t + 1), 30 * 1000);
    return () => clearInterval(id);
  }, [mode]);

  // Notify parent when range changes so it refetches
  useEffect(() => {
    if (onRangeChange) onRangeChange(rangeHours);
  }, [rangeHours, onRangeChange]);

  // When range changes, auto-scale the default window width (user can still
  // override via the dropdown; this only fires on the range pill change).
  const handleRangeClick = useCallback((newHours) => {
    setRangeHours(newHours);
    const newWindow = DEFAULT_WINDOW_FOR_RANGE[newHours] || Math.max(1, newHours / 8);
    setWindowHours(newWindow);
    initialAutoPositionedRef.current = false; // re-position on new range
  }, []);

  // ── Derived: timeline range + active window ─────────────────────────────────
  const now = useMemo(() => new Date(), [tick, mode, scrub]);   // eslint-disable-line

  const rangeEnd   = now;
  const rangeStart = useMemo(() => new Date(now.getTime() - ms(rangeHours)), [now, rangeHours]);

  const effectiveWindowHours = Math.min(windowHours, rangeHours);

  // On first item-load (per range), auto-snap scrubber so the active window
  // covers the most recent item. This guarantees pulsing markers on load.
  useEffect(() => {
    if (!items || !items.length) return;
    if (initialAutoPositionedRef.current) return;
    let newestMs = 0;
    for (const it of items) {
      const t = it.published_at ? new Date(it.published_at).getTime() : 0;
      if (t > newestMs) newestMs = t;
    }
    if (!newestMs) return;
    const rs = rangeStart.getTime();
    const re = rangeEnd.getTime();
    // If newest item is more than windowHours OLD, snap scrubber there
    // (so the window contains it). Otherwise stay in "live" mode.
    const liveWindowStart = re - ms(effectiveWindowHours);
    if (newestMs < liveWindowStart) {
      const newScrub = clamp((newestMs - rs) / (re - rs), 0.01, 1.0);
      setScrub(newScrub);
      setMode("paused");
    }
    initialAutoPositionedRef.current = true;
  }, [items, rangeStart, rangeEnd, effectiveWindowHours]);

  // In live mode the active window is glued to (now - windowH .. now).
  // In paused mode the window-end follows the scrubber position along the range.
  const windowEnd = useMemo(() => {
    if (mode === "live") return rangeEnd;
    return new Date(rangeStart.getTime() + scrub * (rangeEnd - rangeStart));
  }, [mode, scrub, rangeStart, rangeEnd]);

  const windowStart = useMemo(
    () => new Date(windowEnd.getTime() - ms(effectiveWindowHours)),
    [windowEnd, effectiveWindowHours]
  );

  // Push window up to parent every time it changes
  useEffect(() => {
    if (onWindowChange) onWindowChange(windowStart, windowEnd, rangeStart, rangeEnd);
  }, [windowStart, windowEnd, rangeStart, rangeEnd, onWindowChange]);

  // ── Density buckets (severity-colored shading along the track) ─────────────
  const buckets = useMemo(
    () => buildDensityBuckets(items, rangeStart, rangeEnd, rangeHours <= 24 ? 48 : 60),
    [items, rangeStart, rangeEnd, rangeHours]
  );
  const maxBucketTotal = useMemo(
    () => Math.max(1, ...buckets.map((b) => b.total)),
    [buckets]
  );

  // ── Event dots on the timeline (critical + high only) ───────────────────────
  const dotItems = useMemo(() => {
    if (!items || !items.length) return [];
    return items
      .filter((it) => ["critical", "high"].includes(it.severity))
      .map((it) => {
        const d = new Date(it.published_at);
        const t = d.getTime();
        const pos = (t - rangeStart.getTime()) / (rangeEnd.getTime() - rangeStart.getTime());
        return { ...it, _date: d, _pos: pos };
      })
      .filter((it) => it._pos >= 0 && it._pos <= 1);
  }, [items, rangeStart, rangeEnd]);

  // ── Track interaction ──────────────────────────────────────────────────────
  const trackRef = useRef(null);
  const dragRef  = useRef(false);

  const updateScrubFromEvent = (e) => {
    const track = trackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    const pos = clamp(x / rect.width, 0, 1);
    setScrub(pos);
    if (mode === "live") setMode("paused");
  };
  const onTrackMouseDown = (e) => {
    dragRef.current = true;
    updateScrubFromEvent(e);
  };
  useEffect(() => {
    const onMove = (e) => { if (dragRef.current) updateScrubFromEvent(e); };
    const onUp   = ()  => { dragRef.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup",   onUp);
    window.addEventListener("touchmove", onMove);
    window.addEventListener("touchend",  onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup",   onUp);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("touchend",  onUp);
    };
  }, []);   // eslint-disable-line

  // ── Step buttons (move window by 1 window-width) ───────────────────────────
  const step = (dir) => {
    setMode("paused");
    const stepMs = ms(effectiveWindowHours);
    const totalMs = rangeEnd - rangeStart;
    const currentMs = scrub * totalMs;
    const nextMs = clamp(currentMs + dir * stepMs, 0, totalMs);
    setScrub(nextMs / totalMs);
  };

  // ── Active window highlighted overlay positions (% of track) ────────────────
  const totalMs = rangeEnd.getTime() - rangeStart.getTime();
  const winLeftPct  = clamp((windowStart.getTime() - rangeStart.getTime()) / totalMs, 0, 1) * 100;
  const winWidthPct = clamp((windowEnd.getTime()   - windowStart.getTime()) / totalMs, 0, 1) * 100;

  return (
    <div
      className="bg-black/80 border-t border-border backdrop-blur-md"
      style={{ fontFamily: "ui-monospace, monospace" }}
      data-testid="map-timeline"
    >
      {/* ── Top control row ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 px-3 pt-2 pb-1.5 text-[10px] uppercase tracking-wider">
        {/* Range pills */}
        <div className="flex gap-1">
          {RANGE_OPTIONS.map((r) => (
            <button
              key={r.id}
              onClick={() => handleRangeClick(r.hours)}
              className={`px-2 py-1 border ${
                rangeHours === r.hours
                  ? "border-lime-400/60 bg-lime-400/10 text-lime-300"
                  : "border-white/15 text-white/55 hover:text-white/85"
              }`}
            >{r.label}</button>
          ))}
        </div>

        <div className="text-white/30">|</div>

        {/* Window-width selector — native select for reliability */}
        <label className="flex items-center gap-1.5 text-white/55">
          <span className="text-white/45">WINDOW:</span>
          <select
            value={effectiveWindowHours}
            onChange={(e) => setWindowHours(parseFloat(e.target.value))}
            className="bg-black/70 border border-white/20 text-white/85 px-1.5 py-0.5 text-[10px] uppercase tracking-wider cursor-pointer focus:outline-none focus:border-lime-400/60"
          >
            {WINDOW_PRESETS.filter((p) => p.hours <= rangeHours).map((p) => (
              <option key={p.label} value={p.hours} className="bg-black text-white">
                {p.label}
              </option>
            ))}
          </select>
        </label>

        <div className="text-white/30">|</div>

        {/* Transport controls */}
        <button
          onClick={() => step(-1)}
          className="p-1 border border-white/15 text-white/70 hover:text-white"
          title="Step back one window"
        ><SkipBack size={11} /></button>
        <button
          onClick={() => setMode(mode === "live" ? "paused" : "live")}
          className={`p-1 border ${
            mode === "live"
              ? "border-lime-400/60 bg-lime-400/10 text-lime-300"
              : "border-white/15 text-white/70 hover:text-white"
          }`}
          title={mode === "live" ? "Pause (currently live)" : "Resume live mode"}
        >
          {mode === "live" ? <Pause size={11} /> : <Play size={11} />}
        </button>
        <button
          onClick={() => step(+1)}
          className="p-1 border border-white/15 text-white/70 hover:text-white"
          title="Step forward one window"
        ><SkipForward size={11} /></button>

        {mode === "live" && (
          <div className="flex items-center gap-1 text-lime-400 ml-1">
            <Radio size={10} className="animate-pulse" />
            <span className="text-[9px] tracking-widest">LIVE</span>
          </div>
        )}

        <div className="ml-auto flex items-center gap-3 text-white/60 text-[10px]">
          <span className="flex items-center gap-1">
            <Clock size={10} />
            <span className="text-white/80">{fmtTime(windowStart)}</span>
            <span className="text-white/30">→</span>
            <span className="text-white/80">{fmtTime(windowEnd)}</span>
          </span>
          <span className="text-white/40 normal-case">
            {dotItems.filter((it) => {
              const t = it._date.getTime();
              return t >= windowStart.getTime() && t <= windowEnd.getTime();
            }).length} active
          </span>
        </div>
      </div>

      {/* ── Timeline track ─────────────────────────────────────────────── */}
      <div className="px-3 pb-3 pt-1 relative">
        <div
          ref={trackRef}
          onMouseDown={onTrackMouseDown}
          onTouchStart={onTrackMouseDown}
          className="relative h-10 bg-white/[0.04] border border-white/10 cursor-pointer select-none overflow-hidden"
          style={{ touchAction: "none" }}
        >
          {/* ── Density shading — severity-blended color, alpha = density ── */}
          {buckets.map((b, i) => {
            if (b.total === 0) return null;
            const densityFrac = b.total / maxBucketTotal;
            const alpha = 0.15 + densityFrac * 0.55;   // 0.15 - 0.70 alpha
            const bg = bucketRgba(b, alpha);
            return (
              <div
                key={i}
                className="absolute top-0 bottom-0 pointer-events-none"
                style={{
                  left: `${(i / buckets.length) * 100}%`,
                  width: `${100 / buckets.length}%`,
                  background: bg,
                  filter: "blur(2px)",      // soft gradient feel
                }}
              />
            );
          })}

          {/* Tick marks (5 evenly spaced) */}
          {[0, 0.25, 0.5, 0.75, 1].map((p) => (
            <div
              key={p}
              className="absolute top-0 bottom-0 w-px bg-white/8 pointer-events-none"
              style={{ left: `${p * 100}%` }}
            />
          ))}

          {/* Active window overlay */}
          <div
            className="absolute top-0 bottom-0 border-l border-r border-lime-400/70 pointer-events-none"
            style={{
              left: `${winLeftPct}%`,
              width: `${winWidthPct}%`,
              background: "rgba(163,230,53,0.08)",
              boxShadow: "inset 0 0 0 1px rgba(163,230,53,0.15)",
            }}
          />

          {/* Window-end scrubber handle */}
          <div
            className="absolute top-[-3px] bottom-[-3px] w-[2px] bg-lime-300 pointer-events-none"
            style={{ left: `${(winLeftPct + winWidthPct)}%`, boxShadow: "0 0 6px rgba(163,230,53,0.6)" }}
          />

          {/* Event dots */}
          {dotItems.map((it) => {
            const t = it._date.getTime();
            const inWindow = t >= windowStart.getTime() && t <= windowEnd.getTime();
            const color = it.severity === "critical" ? "#ef4444" : "#f59e0b";
            return (
              <div
                key={it.id}
                className="absolute"
                style={{
                  left: `${it._pos * 100}%`,
                  top: it.severity === "critical" ? 4 : 18,
                  transform: "translateX(-50%)",
                  width: it.severity === "critical" ? 7 : 5,
                  height: it.severity === "critical" ? 7 : 5,
                  borderRadius: "50%",
                  background: color,
                  border: "1px solid rgba(0,0,0,0.6)",
                  opacity: inWindow ? 1 : 0.45,
                  boxShadow: inWindow ? `0 0 4px ${color}` : "none",
                  cursor: "pointer",
                  zIndex: 5,
                }}
                onMouseEnter={(e) => {
                  const rect = trackRef.current.getBoundingClientRect();
                  setHoverInfo({
                    x: e.clientX - rect.left,
                    item: it,
                  });
                }}
                onMouseLeave={() => setHoverInfo(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  const totalMs = rangeEnd - rangeStart;
                  const newScrubMs = clamp(t - rangeStart.getTime(), 0, totalMs);
                  setScrub(newScrubMs / totalMs);
                  setMode("paused");
                }}
                title={`${it.severity.toUpperCase()} · ${fmtRel(it._date, now)} · ${it.title?.slice(0, 70) || ""}`}
              />
            );
          })}

          {/* Hover preview */}
          {hoverInfo && (
            <div
              className="absolute bg-black/95 border border-white/20 px-2 py-1.5 text-[10px] text-white/90 pointer-events-none z-20"
              style={{
                left: clamp(hoverInfo.x, 60, (trackRef.current?.offsetWidth || 600) - 220),
                top: -56,
                width: 240,
              }}
            >
              <div className={`text-[9px] uppercase tracking-wider mb-0.5 ${
                hoverInfo.item.severity === "critical" ? "text-red-400" : "text-amber-400"
              }`}>
                {hoverInfo.item.severity} · {fmtRel(hoverInfo.item._date, now)}
              </div>
              <div className="text-white/85 leading-snug line-clamp-2">
                {hoverInfo.item.title}
              </div>
            </div>
          )}
        </div>

        {/* Track labels */}
        <div className="flex justify-between text-[9px] text-white/40 mt-1 uppercase tracking-wider">
          <span>{fmtTime(rangeStart)}</span>
          <span className="text-white/55">{fmtRel(windowEnd, now)}</span>
          <span>{fmtTime(rangeEnd)}{mode === "live" ? " (live)" : ""}</span>
        </div>
      </div>
    </div>
  );
}
