/**
 * Dashboard customization preferences — localStorage-backed.
 *
 * Stored shape:
 * {
 *   filters: { state, category, actor, severity, range, border_only },
 *   widgets: [{ id, type, title, visible }],
 *   active_preset: "default" | "coin" | ...
 * }
 */

const LS_KEY = "rd_dashboard_prefs_v1";

// All widget types the customize panel can show
export const WIDGET_TYPES = [
  { type: "severity_evolution",  title: "Severity Evolution",       desc: "Stacked area of daily severity bands" },
  { type: "threat_heatmap",      title: "Threat Heatmap",            desc: "State × threat category matrix" },
  { type: "actor_activity",      title: "Actor Activity Tracker",    desc: "Top actors with severity breakdown" },
  { type: "intel_velocity",      title: "Intelligence Velocity",     desc: "Per-state incidents/day + acceleration" },
  { type: "geo_density",         title: "Geographic Threat Density", desc: "Top locations by severity-weighted volume" },
  { type: "category_breakdown",  title: "Threat Category Breakdown", desc: "Bar chart of threat categories" },
  { type: "severity_pie",        title: "Severity Distribution",     desc: "Pie of severity proportions" },
  { type: "source_breakdown",    title: "Source Activity",           desc: "Items per intelligence source" },
];

// ── Built-in presets ────────────────────────────────────────────────────────
export const PRESETS = {
  default: {
    name: "Default Custom View",
    filters: { state: "All", category: "All", actor: "", severity: "All", range: "7d", border_only: false },
    widgets: [
      { id: "w1", type: "severity_evolution", title: "Severity Evolution",       visible: true },
      { id: "w2", type: "intel_velocity",     title: "Intelligence Velocity",     visible: true },
      { id: "w3", type: "actor_activity",     title: "Actor Activity Tracker",    visible: true },
      { id: "w4", type: "geo_density",        title: "Geographic Threat Density", visible: true },
      { id: "w5", type: "threat_heatmap",     title: "Threat Heatmap",            visible: true },
      { id: "w6", type: "category_breakdown", title: "Threat Category Breakdown", visible: false },
      { id: "w7", type: "severity_pie",       title: "Severity Distribution",     visible: false },
      { id: "w8", type: "source_breakdown",   title: "Source Activity",           visible: false },
    ],
  },
  coin: {
    name: "Counter-Insurgency",
    filters: { state: "All", category: "All", actor: "", severity: "All", range: "30d", border_only: false },
    widgets: [
      { id: "w1", type: "actor_activity",     title: "Insurgent Actor Tracker",   visible: true },
      { id: "w2", type: "geo_density",        title: "COIN Hotspot Density",      visible: true },
      { id: "w3", type: "intel_velocity",     title: "Incident Acceleration",     visible: true },
      { id: "w4", type: "severity_evolution", title: "Severity Evolution",        visible: true },
      { id: "w5", type: "threat_heatmap",     title: "Threat Heatmap",            visible: true },
    ],
  },
  cross_border: {
    name: "Cross-Border Threat",
    filters: { state: "All", category: "All", actor: "", severity: "All", range: "30d", border_only: true },
    widgets: [
      { id: "w1", type: "geo_density",        title: "Border Location Density",   visible: true },
      { id: "w2", type: "severity_evolution", title: "Border Severity Evolution", visible: true },
      { id: "w3", type: "actor_activity",     title: "Cross-Border Actors",       visible: true },
      { id: "w4", type: "intel_velocity",     title: "Border Activity Velocity",  visible: true },
    ],
  },
  manipur_monitor: {
    name: "Manipur Escalation Monitor",
    filters: { state: "Manipur", category: "All", actor: "", severity: "All", range: "30d", border_only: false },
    widgets: [
      { id: "w1", type: "severity_evolution", title: "Manipur Severity Trend",    visible: true },
      { id: "w2", type: "geo_density",        title: "Manipur Hotspots",          visible: true },
      { id: "w3", type: "actor_activity",     title: "Manipur Active Actors",     visible: true },
      { id: "w4", type: "category_breakdown", title: "Manipur Threat Categories", visible: true },
      { id: "w5", type: "intel_velocity",     title: "Velocity by State",         visible: true },
    ],
  },
  drug_watch: {
    name: "Drug Trafficking Watch",
    filters: { state: "All", category: "Drug Smuggling", actor: "", severity: "All", range: "90d", border_only: false },
    widgets: [
      { id: "w1", type: "geo_density",        title: "Drug Hotspot Locations",    visible: true },
      { id: "w2", type: "actor_activity",     title: "Drug Cartel Actors",        visible: true },
      { id: "w3", type: "severity_evolution", title: "Drug Severity Trend",       visible: true },
      { id: "w4", type: "source_breakdown",   title: "Reporting Sources",         visible: true },
    ],
  },
  narrative: {
    name: "Narrative Warfare",
    filters: { state: "All", category: "All", actor: "", severity: "All", range: "7d", border_only: false },
    widgets: [
      { id: "w1", type: "source_breakdown",   title: "Social Source Activity",    visible: true },
      { id: "w2", type: "actor_activity",     title: "Mentioned Actors",          visible: true },
      { id: "w3", type: "severity_evolution", title: "Volume Trend",              visible: true },
      { id: "w4", type: "category_breakdown", title: "Topic Categories",          visible: true },
    ],
  },
};

export function loadPrefs() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...PRESETS.default, active_preset: "default" };
    const p = JSON.parse(raw);
    if (!p.filters || !p.widgets) return { ...PRESETS.default, active_preset: "default" };
    return p;
  } catch {
    return { ...PRESETS.default, active_preset: "default" };
  }
}

export function savePrefs(prefs) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(prefs));
  } catch (e) {
    console.warn("savePrefs failed:", e);
  }
}

export function applyPreset(presetKey) {
  const p = PRESETS[presetKey];
  if (!p) return loadPrefs();
  const out = { ...p, active_preset: presetKey, name: p.name, filters: { ...p.filters }, widgets: p.widgets.map(w => ({ ...w })) };
  savePrefs(out);
  return out;
}

export function resetToDefault() {
  return applyPreset("default");
}
