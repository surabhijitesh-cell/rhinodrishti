/**
 * MapTimelineSlider — Temporal Intelligence scrubber for the NER situation map.
 *
 * Phase 1 (no pattern engine yet):
 *  - 24h / 7d / 30d range selectors
 *  - Adjustable active-window width (default 3h)
 *  - Draggable scrubber to step through time
 *  - Live mode anchors window-end to "now" and refreshes via the same WS
 *    pipeline that already updates the map
 *  - Pause / play / step buttons
 *  - Critical+High events plotted as dots on the timeline track
 *
 * Output (via onWindowChange callback):
 *   { windowStart: Date, windowEnd: Date, rangeStart: Date, rangeEnd: Date }
 *
 * Parent (Dashboard) is responsible for:
 *   - fetching items in the timeline range via /api/intelligence/map-timeline
 *   - tagging each item with `_opacity` based on its timestamp vs active window
 *   - passing the tagged items array to <NERMap items={...} />
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Play, Pause, SkipBack, SkipForward, Clock, Radio, Settings2,
} from "lucide-react";

// ── Range presets (entire slider span) ─────────────────────────────────────────
const RANGE_OPTIONS = [
  { id: 24,   label: "24h",  hours: 24      },
  { id: 168,  label: "7d",   hours: 24 * 7  },
  { id: 720,  label: "30d",  hours: 24 * 30 },
];

// ── Active-window presets (width of the bright slice) ──────────────────────────
const WINDOW_PRESETS = [
  { label: "30m", hours: 0.5 },
  { label: "1h",  hours: 1   },
  { label: "3h",  hours: 3   },
  { label: "6h",  hours: 6   },
  { label: "12h", hours: 12  },
  { label: "24h", hours: 24  },
  { label: "3d",  hours: 72  },
  { label: "7d",  hours: 168 },
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

// ── Compute marker opacity for an item given the active window ─────────────────
//   In window      → 1.0  (full pulse)
//   Within 1× window-width either side → linear fade 1.0 → 0.25
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
    // Linear fade 0.95 → 0.25 across fadeBand
    const f = distance / fadeBand;
    return 0.95 - f * 0.70;
  }
  return 0.15;
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
  const [showWindowMenu, setShowWindowMenu] = useState(false);
  const [hoverInfo,      setHoverInfo]      = useState(null); // {x, item}

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

  // ── Derived: timeline range + active window ─────────────────────────────────
  const now = useMemo(() => new Date(), [tick, mode, scrub]);   // eslint-disable-line

  const rangeEnd   = now;
  const rangeStart = useMemo(() => new Date(now.getTime() - ms(rangeHours)), [now, rangeHours]);

  // Clamp window width so it never exceeds the slider range
  const effectiveWindowHours = Math.min(windowHours, rangeHours);

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
              onClick={() => setRangeHours(r.hours)}
              className={`px-2 py-1 border ${
                rangeHours === r.hours
                  ? "border-lime-400/60 bg-lime-400/10 text-lime-300"
                  : "border-white/15 text-white/55 hover:text-white/85"
              }`}
            >{r.label}</button>
          ))}
        </div>

        <div className="text-white/30">|</div>

        {/* Window-width selector */}
        <div className="relative">
          <button
            onClick={() => setShowWindowMenu((s) => !s)}
            className="px-2 py-1 border border-white/15 text-white/70 hover:text-white flex items-center gap-1.5"
            title="Active-window width — bright markers fall inside this window"
          >
            <Settings2 size={11} />
            <span>WINDOW: {effectiveWindowHours < 1
              ? `${Math.round(effectiveWindowHours * 60)}m`
              : effectiveWindowHours < 24
                ? `${effectiveWindowHours}h`
                : `${effectiveWindowHours / 24}d`}
            </span>
          </button>
          {showWindowMenu && (
            <div className="absolute left-0 bottom-full mb-1 bg-black/95 border border-white/15 p-1 z-50 min-w-[120px]">
              {WINDOW_PRESETS.filter((p) => p.hours <= rangeHours).map((p) => (
                <button
                  key={p.label}
                  onClick={() => { setWindowHours(p.hours); setShowWindowMenu(false); }}
                  className={`block w-full px-2 py-1 text-left text-[10px] ${
                    effectiveWindowHours === p.hours
                      ? "bg-lime-400/15 text-lime-300"
                      : "text-white/70 hover:bg-white/10"
                  }`}
                >{p.label}</button>
              ))}
            </div>
          )}
        </div>

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
          className="relative h-9 bg-white/[0.04] border border-white/10 cursor-pointer select-none"
          style={{ touchAction: "none" }}
        >
          {/* Tick marks (5 evenly spaced) */}
          {[0, 0.25, 0.5, 0.75, 1].map((p) => (
            <div
              key={p}
              className="absolute top-0 bottom-0 w-px bg-white/8"
              style={{ left: `${p * 100}%` }}
            />
          ))}

          {/* Active window overlay */}
          <div
            className="absolute top-0 bottom-0 bg-lime-400/15 border-l border-r border-lime-400/50 pointer-events-none"
            style={{ left: `${winLeftPct}%`, width: `${winWidthPct}%` }}
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
                  top: it.severity === "critical" ? 4 : 16,
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
                  // Jump scrubber to event time, with the event roughly at the end of the active window
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
