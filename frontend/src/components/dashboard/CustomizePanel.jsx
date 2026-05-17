import { useEffect, useState } from "react";
import { X, Sliders, RotateCcw, Bookmark, Eye, EyeOff } from "lucide-react";
import axios from "axios";
import { PRESETS, WIDGET_TYPES } from "../../lib/dashboardPrefs";

const SEVERITIES = ["All", "critical", "high", "medium", "low"];
const RANGES = [
  { v: "24h",  label: "24 HRS" },
  { v: "7d",   label: "7 DAYS" },
  { v: "30d",  label: "30 DAYS" },
  { v: "90d",  label: "90 DAYS" },
  { v: "365d", label: "1 YEAR" },
];

/**
 * Slide-out customize panel for the Custom Analytics section.
 *
 * Props:
 *   open           — show/hide
 *   onClose        — close handler
 *   prefs          — current prefs object
 *   onPrefsChange  — receive updated prefs
 *   onApplyPreset  — apply a named preset by key
 *   onReset        — reset to default
 *   api            — base URL for filter-options fetch
 */
export default function CustomizePanel({
  open, onClose, prefs, onPrefsChange, onApplyPreset, onReset, api,
}) {
  const [opts, setOpts] = useState({ states: [], categories: [], actors: [] });
  const [optsLoaded, setOptsLoaded] = useState(false);

  useEffect(() => {
    if (!open || optsLoaded) return;
    axios.get(`${api}/analytics/filter-options`)
      .then(r => { setOpts(r.data); setOptsLoaded(true); })
      .catch(e => console.warn("filter options fetch failed:", e));
  }, [open, api, optsLoaded]);

  if (!open) return null;

  const f = prefs.filters;
  const updateFilter = (key, value) => {
    onPrefsChange({ ...prefs, filters: { ...prefs.filters, [key]: value }, active_preset: "custom" });
  };
  const toggleWidget = (id) => {
    onPrefsChange({
      ...prefs,
      widgets: prefs.widgets.map(w => w.id === id ? { ...w, visible: !w.visible } : w),
      active_preset: "custom",
    });
  };
  const renameWidget = (id, title) => {
    onPrefsChange({
      ...prefs,
      widgets: prefs.widgets.map(w => w.id === id ? { ...w, title } : w),
    });
  };
  const addWidget = (type) => {
    const idx = prefs.widgets.length + 1;
    const meta = WIDGET_TYPES.find(t => t.type === type);
    const newWidget = { id: `w${idx}_${Date.now()}`, type, title: meta?.title || type, visible: true };
    onPrefsChange({ ...prefs, widgets: [...prefs.widgets, newWidget], active_preset: "custom" });
  };
  const removeWidget = (id) => {
    onPrefsChange({
      ...prefs,
      widgets: prefs.widgets.filter(w => w.id !== id),
      active_preset: "custom",
    });
  };

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose}
           className="fixed inset-0 bg-black/60 z-40"
           data-testid="customize-backdrop" />
      {/* Panel */}
      <div
        className="fixed top-0 right-0 h-full w-[420px] max-w-[95vw] bg-card border-l border-border z-50 overflow-y-auto"
        data-testid="customize-panel"
      >
        <div className="sticky top-0 bg-card border-b border-border px-4 py-3 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <Sliders size={16} className="text-primary" />
            <h2 className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              Customize Analytics
            </h2>
          </div>
          <button onClick={onClose} className="p-1 hover:text-red-400" data-testid="customize-close">
            <X size={16} />
          </button>
        </div>

        <div className="p-4 space-y-5">
          {/* ── Presets ── */}
          <section>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1">
              <Bookmark size={11} /> Command Views
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {Object.entries(PRESETS).map(([key, p]) => (
                <button
                  key={key}
                  onClick={() => onApplyPreset(key)}
                  className={`px-2 py-2 text-[10px] font-mono uppercase tracking-wider border text-left transition-colors ${
                    prefs.active_preset === key
                      ? "border-primary bg-primary/15 text-primary"
                      : "border-border bg-background text-muted-foreground hover:border-primary/50"
                  }`}
                  data-testid={`preset-${key}`}
                >
                  {p.name}
                </button>
              ))}
            </div>
            <button
              onClick={onReset}
              className="mt-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground flex items-center gap-1"
              data-testid="customize-reset"
            >
              <RotateCcw size={11} /> Reset to default
            </button>
          </section>

          {/* ── Filters ── */}
          <section>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
              Filters
            </div>
            <div className="space-y-3">
              {/* Range */}
              <div>
                <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-1">Range</label>
                <div className="grid grid-cols-5 gap-1">
                  {RANGES.map(r => (
                    <button
                      key={r.v}
                      onClick={() => updateFilter("range", r.v)}
                      className={`px-1 py-1.5 text-[9px] font-mono uppercase border ${
                        f.range === r.v ? "border-primary bg-primary/15 text-primary" : "border-border"
                      }`}
                    >{r.label}</button>
                  ))}
                </div>
              </div>
              {/* State */}
              <div>
                <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-1">State</label>
                <select
                  value={f.state}
                  onChange={e => updateFilter("state", e.target.value)}
                  className="w-full bg-background border border-border px-2 py-1.5 text-xs font-mono"
                  data-testid="filter-state"
                >
                  <option value="All">All states</option>
                  {opts.states.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              {/* Category */}
              <div>
                <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-1">Threat Category</label>
                <select
                  value={f.category}
                  onChange={e => updateFilter("category", e.target.value)}
                  className="w-full bg-background border border-border px-2 py-1.5 text-xs font-mono"
                  data-testid="filter-category"
                >
                  <option value="All">All categories</option>
                  {opts.categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              {/* Severity */}
              <div>
                <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-1">Severity</label>
                <div className="grid grid-cols-5 gap-1">
                  {SEVERITIES.map(s => (
                    <button
                      key={s}
                      onClick={() => updateFilter("severity", s)}
                      className={`px-1 py-1.5 text-[9px] font-mono uppercase border ${
                        f.severity === s ? "border-primary bg-primary/15 text-primary" : "border-border"
                      }`}
                    >{s === "All" ? "ALL" : s.slice(0,4)}</button>
                  ))}
                </div>
              </div>
              {/* Actor */}
              <div>
                <label className="text-[9px] font-mono uppercase text-muted-foreground block mb-1">Actor (substring)</label>
                <input
                  type="text"
                  value={f.actor}
                  onChange={e => updateFilter("actor", e.target.value)}
                  placeholder="e.g. ULFA, NSCN, PLA"
                  className="w-full bg-background border border-border px-2 py-1.5 text-xs font-mono"
                  data-testid="filter-actor"
                />
              </div>
              {/* Border-only */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!f.border_only}
                  onChange={e => updateFilter("border_only", e.target.checked)}
                  className="accent-primary"
                  data-testid="filter-border-only"
                />
                <span className="text-xs font-mono uppercase tracking-wider">
                  Cross-border items only
                </span>
              </label>
            </div>
          </section>

          {/* ── Widgets ── */}
          <section>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1">
              <Eye size={11} /> Active Widgets ({prefs.widgets.filter(w => w.visible).length})
            </div>
            <div className="space-y-1">
              {prefs.widgets.map(w => (
                <div key={w.id} className="flex items-center gap-2 py-1 border-b border-border/40">
                  <button
                    onClick={() => toggleWidget(w.id)}
                    className={`p-1 ${w.visible ? "text-primary" : "text-muted-foreground"}`}
                    data-testid={`widget-toggle-${w.id}`}
                  >
                    {w.visible ? <Eye size={12} /> : <EyeOff size={12} />}
                  </button>
                  <input
                    type="text"
                    value={w.title}
                    onChange={e => renameWidget(w.id, e.target.value)}
                    className="flex-1 bg-transparent text-[11px] font-mono px-1 py-0.5 hover:bg-muted/30 focus:bg-muted/50 outline-none border border-transparent focus:border-border"
                  />
                  <span className="text-[9px] font-mono text-muted-foreground">{w.type}</span>
                  <button
                    onClick={() => removeWidget(w.id)}
                    className="p-1 text-muted-foreground hover:text-red-400"
                  ><X size={11} /></button>
                </div>
              ))}
            </div>

            {/* Add widget */}
            <div className="mt-3">
              <div className="text-[9px] font-mono uppercase text-muted-foreground block mb-1">
                Add Widget
              </div>
              <select
                onChange={(e) => { if (e.target.value) { addWidget(e.target.value); e.target.value = ""; }}}
                value=""
                className="w-full bg-background border border-border px-2 py-1.5 text-xs font-mono"
                data-testid="widget-add-select"
              >
                <option value="">+ Add widget…</option>
                {WIDGET_TYPES.map(w => (
                  <option key={w.type} value={w.type}>
                    {w.title} — {w.desc}
                  </option>
                ))}
              </select>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
