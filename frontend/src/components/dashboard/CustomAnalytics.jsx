import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import {
  Sliders, Bookmark, Activity, TrendingUp, MapPin, Users,
  Grid3x3, PieChart, Layers, Radio,
} from "lucide-react";
import WidgetCard from "./WidgetCard";
import CustomizePanel from "./CustomizePanel";
import { WIDGET_RENDERERS } from "./WidgetRegistry";
import { loadPrefs, savePrefs, applyPreset, resetToDefault, PRESETS } from "../../lib/dashboardPrefs";

const WIDGET_ICONS = {
  severity_evolution: Activity,
  threat_heatmap:     Grid3x3,
  actor_activity:     Users,
  intel_velocity:     TrendingUp,
  geo_density:        MapPin,
  category_breakdown: Layers,
  severity_pie:       PieChart,
  source_breakdown:   Radio,
};

const WIDGET_TIPS = {
  severity_evolution:  "Daily severity bands across the selected filter set. Surges in red/amber = escalation.",
  threat_heatmap:      "State × threat category activity matrix. Cell intensity reflects volume; darker red = hotter intersection.",
  actor_activity:      "Top organizations / militant groups by item count over the range, with severity breakdown stack.",
  intel_velocity:      "Per-state incidents-per-day and acceleration ratio (late third / early third of range). RISING = accelerating, FALLING = de-escalating.",
  geo_density:         "Highest-activity locations (city / district), severity-weighted. Excludes state names.",
  category_breakdown:  "Threat category counts under current filters.",
  severity_pie:        "Severity distribution proportion within current filter set.",
  source_breakdown:    "Items by intelligence source — surfaces which sources are driving the current narrative.",
};

/**
 * Custom Analytics section — slots below the default dashboard.
 * User toggles via the "Customize" button to choose widgets / filters / presets.
 */
export default function CustomAnalytics({ api }) {
  const [prefs, setPrefs]               = useState(loadPrefs);
  const [panelOpen, setPanelOpen]       = useState(false);
  const [widgetData, setWidgetData]     = useState({});   // { widget_id: { loading, error, data } }

  // Persist prefs on any change
  useEffect(() => { savePrefs(prefs); }, [prefs]);

  // Fetch data for a single widget
  const fetchWidget = useCallback(async (widget) => {
    const f = prefs.filters;
    const params = new URLSearchParams({
      widget: widget.type,
      state:    f.state || "All",
      category: f.category || "All",
      actor:    f.actor || "",
      severity: f.severity || "All",
      range:    f.range || "7d",
      border_only: f.border_only ? "true" : "false",
    });
    setWidgetData(prev => ({ ...prev, [widget.id]: { ...(prev[widget.id] || {}), loading: true, error: null }}));
    try {
      const res = await axios.get(`${api}/analytics/widget?${params}`);
      setWidgetData(prev => ({ ...prev, [widget.id]: { loading: false, error: null, payload: res.data }}));
    } catch (e) {
      setWidgetData(prev => ({ ...prev, [widget.id]: { loading: false,
        error: e?.response?.data?.detail || "Fetch failed", payload: null }}));
    }
  }, [api, prefs.filters]);

  // Refetch all visible widgets when filters change OR widget set changes
  const filtersKey = JSON.stringify(prefs.filters);
  const widgetsKey = prefs.widgets.filter(w => w.visible).map(w => `${w.id}:${w.type}`).join(",");
  useEffect(() => {
    prefs.widgets.filter(w => w.visible).forEach(w => fetchWidget(w));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey, widgetsKey, fetchWidget]);

  const handlePrefsChange = (p) => setPrefs(p);
  const handleApplyPreset = (key) => setPrefs(applyPreset(key));
  const handleReset       = () => setPrefs(resetToDefault());
  const handleHideWidget  = (id) => setPrefs({
    ...prefs,
    widgets: prefs.widgets.map(w => w.id === id ? { ...w, visible: false } : w),
    active_preset: "custom",
  });

  const visibleWidgets = prefs.widgets.filter(w => w.visible);
  const activePresetName = PRESETS[prefs.active_preset]?.name || "Custom";

  return (
    <section className="space-y-4" data-testid="custom-analytics-section" data-tour="custom-analytics">
      {/* Section header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 border-t border-border pt-6">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold uppercase tracking-tight font-['Barlow_Condensed']"
              data-testid="custom-analytics-title">
            Custom Analytics Workspace
          </h2>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            <span className="inline-flex items-center gap-1">
              <Bookmark size={11} /> {activePresetName}
            </span>
            <span className="mx-2 opacity-50">·</span>
            {prefs.filters.range.toUpperCase()}
            {prefs.filters.state !== "All" && <> · {prefs.filters.state}</>}
            {prefs.filters.category !== "All" && <> · {prefs.filters.category}</>}
            {prefs.filters.severity !== "All" && <> · {prefs.filters.severity.toUpperCase()}</>}
            {prefs.filters.actor && <> · "{prefs.filters.actor}"</>}
            {prefs.filters.border_only && <> · BORDER-ONLY</>}
          </p>
        </div>
        <button
          onClick={() => setPanelOpen(true)}
          className="px-4 py-2 border border-primary bg-primary/10 text-primary hover:bg-primary/20 text-xs font-mono uppercase tracking-wider flex items-center gap-2"
          data-testid="customize-open"
        >
          <Sliders size={14} /> Customize
        </button>
      </div>

      {/* Empty state */}
      {visibleWidgets.length === 0 && (
        <div className="border border-border bg-card p-8 text-center text-muted-foreground text-xs font-mono">
          No widgets visible. Click <button onClick={() => setPanelOpen(true)} className="text-primary underline">Customize</button> to add some.
        </div>
      )}

      {/* Widget grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {visibleWidgets.map(w => {
          const Renderer = WIDGET_RENDERERS[w.type];
          if (!Renderer) {
            return (
              <WidgetCard key={w.id} title={w.title} testId={`widget-${w.id}`}>
                <div className="text-red-400 text-xs font-mono">Unknown widget type: {w.type}</div>
              </WidgetCard>
            );
          }
          const state = widgetData[w.id] || {};
          const Icon = WIDGET_ICONS[w.type];
          const payload = state.payload || {};
          return (
            <WidgetCard
              key={w.id}
              title={w.title}
              tip={WIDGET_TIPS[w.type]}
              icon={Icon}
              onHide={() => handleHideWidget(w.id)}
              loading={state.loading}
              error={state.error}
              testId={`widget-${w.id}`}
            >
              <Renderer data={payload.data} categories={payload.categories} />
            </WidgetCard>
          );
        })}
      </div>

      <CustomizePanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        prefs={prefs}
        onPrefsChange={handlePrefsChange}
        onApplyPreset={handleApplyPreset}
        onReset={handleReset}
        api={api}
      />
    </section>
  );
}
