import { useState, useEffect, useRef } from "react";
import { TrendingUp, BarChart3, Activity, Shield, MapPin, Users, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import Tip from "../components/Tip";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, LineChart, Line, Legend, ComposedChart,
} from "recharts";

const SEVERITY_COLORS = {
  critical: "#ef4444",
  high:     "#f59e0b",
  medium:   "#eab308",
  low:      "#a3e635",
};
const STATE_COLORS = [
  "#a3e635", "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6",
  "#06b6d4", "#ec4899", "#6366f1", "#84cc16", "#f97316",
];
const CONCERN_COLOR = {
  CRITICAL: "#ef4444",
  ELEVATED: "#f59e0b",
  MONITOR:  "#eab308",
  STABLE:   "#a3e635",
};
const RANGE_OPTIONS = [
  { value: "7d",   label: "7 DAYS" },
  { value: "30d",  label: "30 DAYS" },
  { value: "90d",  label: "90 DAYS" },
  { value: "365d", label: "1 YEAR" },
];

const tooltipStyle = {
  background: "hsl(120,10%,8%)",
  border: "1px solid hsl(120,5%,20%)",
  borderRadius: 0,
  fontSize: 12,
};

// Tooltip for State Severity Evolution — sorts states by value descending
const CustomEvolutionTooltip = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;
  const sorted = [...payload]
    .filter(p => p.value > 0)
    .sort((a, b) => b.value - a.value);
  if (sorted.length === 0) return null;
  return (
    <div style={{ ...tooltipStyle, padding: "8px 10px", minWidth: 140 }}>
      <div style={{ fontSize: 10, color: "hsl(120,5%,60%)", marginBottom: 4 }}>{label}</div>
      {sorted.map(p => (
        <div key={p.dataKey} style={{ fontSize: 11, color: p.stroke, display: "flex", justifyContent: "space-between", gap: 16 }}>
          <span>{p.dataKey}</span>
          <span style={{ fontWeight: "bold" }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

// Severity weight for tooltip ordering
const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };

// Tooltip for Severity Trend Aggregate — orders critical → high → medium → low
const CustomSeverityTooltip = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;
  const sorted = [...payload].sort((a, b) =>
    (SEV_ORDER[a.dataKey] ?? 99) - (SEV_ORDER[b.dataKey] ?? 99)
  );
  return (
    <div style={{ ...tooltipStyle, padding: "8px 10px", minWidth: 130 }}>
      <div style={{ fontSize: 10, color: "hsl(120,5%,60%)", marginBottom: 4 }}>{label}</div>
      {sorted.map(p => (
        <div key={p.dataKey} style={{ fontSize: 11, color: p.stroke, display: "flex", justifyContent: "space-between", gap: 16 }}>
          <span style={{ textTransform: "capitalize" }}>{p.dataKey}</span>
          <span style={{ fontWeight: "bold" }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

export default function Trends({ api }) {
  const [range, setRange]               = useState("7d");
  const [data, setData]                 = useState(null);
  const [stability, setStability]       = useState(null);
  const [crossBorder, setCrossBorder]   = useState(null);
  const [loading, setLoading]           = useState(true);
  const [selectedState, setSelectedState] = useState(null);
  const [drilldown, setDrilldown]       = useState(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const drilldownRef = useRef(null);

  // Scroll drill-down into view when state selected
  useEffect(() => {
    if (selectedState && drilldownRef.current) {
      // Delay so layout has time to render the panel
      const t = setTimeout(() => {
        drilldownRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
      return () => clearTimeout(t);
    }
  }, [selectedState]);

  // Fetch top-level data + stability + cross-border whenever range changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      axios.get(`${api}/trends?range=${range}`),
      axios.get(`${api}/trends/stability?range=${range === "24h" ? "7d" : range}`),
      axios.get(`${api}/trends/cross-border?range=${range === "24h" ? "7d" : range}`),
    ])
      .then(([t, s, cb]) => {
        if (cancelled) return;
        setData(t.data);
        setStability(s.data);
        setCrossBorder(cb.data);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        console.error("Trends fetch failed:", e);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [api, range]);

  // Fetch drill-down when state selected
  useEffect(() => {
    if (!selectedState) { setDrilldown(null); return; }
    setDrilldownLoading(true);
    axios.get(`${api}/trends/state/${encodeURIComponent(selectedState)}?range=${range}`)
      .then((r) => setDrilldown(r.data))
      .catch((e) => console.error("Drilldown fetch failed:", e))
      .finally(() => setDrilldownLoading(false));
  }, [api, range, selectedState]);

  if (loading) {
    return (
      <div className="space-y-4" data-testid="trends-loading">
        <div className="h-10 bg-muted animate-pulse w-1/2" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="border border-border bg-card p-4 animate-pulse h-[300px]" />
        ))}
      </div>
    );
  }

  const dailyData      = data?.daily_severity || [];
  const categoryData   = data?.category_stats || [];
  const stateData      = data?.state_stats || [];
  const stateEvolution = data?.state_evolution || [];
  const topActors      = (data?.top_actors || []).slice(0, 12);
  const stabilityStates = stability?.states || [];
  const crossBorderSeries = crossBorder?.series || [];

  // Build merged state evolution data: [{date, Manipur:n, Assam:n, ...}]
  const evolutionMerged = (() => {
    const dateSet = new Set();
    stateEvolution.forEach(s => s.series.forEach(p => dateSet.add(p.date)));
    const dates = Array.from(dateSet).sort();
    return dates.map(d => {
      const row = { date: d };
      stateEvolution.forEach(s => {
        const p = s.series.find(x => x.date === d);
        row[s.state] = p ? p.count : 0;
      });
      return row;
    });
  })();

  const stateNames = stateEvolution.map(s => s.state);

  return (
    <div className="space-y-6" data-testid="trends-page">
      {/* Header + Range Selector */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']"
              data-testid="trends-title" data-tour="trends-title">
            Trends Intelligence Center
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            Multi-timeframe operational analysis · Stability Index · Cross-border correlation
          </p>
        </div>
        <div className="flex gap-1" data-tour="trends-range">
          {RANGE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => { setRange(opt.value); setSelectedState(null); }}
              className={`px-3 py-2 text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                range === opt.value
                  ? "border-primary bg-primary/15 text-primary"
                  : "border-border bg-card text-muted-foreground hover:border-primary/50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Strategic Stability Index — top concern panel */}
      <Card className="border border-border rounded-none bg-card" data-tour="trends-stability">
        <CardHeader className="py-3 px-4 border-b border-border">
          <Tip text="Composite 0-100 score per state. Lower = higher operational concern. Severity load (40%) + velocity acceleration (25%) + unique actor spread (20%) + cross-border share (15%). States are ranked most-concerning first." side="top">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
              <Shield size={16} className="text-primary" />
              Strategic Stability Index
            </CardTitle>
          </Tip>
        </CardHeader>
        <CardContent className="p-4" data-testid="stability-index">
          {stabilityStates.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {stabilityStates.map(s => (
                <button
                  key={s.state}
                  onClick={() => setSelectedState(s.state)}
                  className={`border p-3 text-left transition-colors hover:border-primary ${
                    selectedState === s.state ? "border-primary bg-primary/5" : "border-border bg-background"
                  }`}
                  data-testid={`stability-${s.state}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                      {s.state}
                    </span>
                    <span className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5"
                          style={{ background: `${CONCERN_COLOR[s.concern_level]}22`,
                                   color: CONCERN_COLOR[s.concern_level],
                                   border: `1px solid ${CONCERN_COLOR[s.concern_level]}55` }}>
                      {s.concern_level}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold font-['Barlow_Condensed']"
                          style={{ color: CONCERN_COLOR[s.concern_level] }}>
                      {s.stability_score}
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground">/100</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-1 text-[9px] font-mono text-muted-foreground">
                    <div>Items: <span className="text-foreground">{s.metrics.total_items}</span></div>
                    <div>Actors: <span className="text-foreground">{s.metrics.actor_count}</span></div>
                    <div>Velocity: <span className="text-foreground">{s.metrics.velocity}x</span></div>
                    <div>X-Border: <span className="text-foreground">{Math.round(s.metrics.cross_border_share * 100)}%</span></div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="h-[140px] flex items-center justify-center text-muted-foreground text-sm">
              No stability data available for this range
            </div>
          )}
        </CardContent>
      </Card>

      {/* State Severity Evolution (multi-line) */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <Tip text="Per-state daily incident count over the selected range. Each line is one state — diverging lines show which states are escalating vs. de-escalating relative to peers." side="top">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
              <TrendingUp size={16} className="text-primary" />
              State Severity Evolution
            </CardTitle>
          </Tip>
        </CardHeader>
        <CardContent className="p-4" data-testid="state-evolution-chart">
          {evolutionMerged.length > 0 && stateNames.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={evolutionMerged}>
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }}
                       tickFormatter={(v) => v?.slice(5) || v} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                <Tooltip content={<CustomEvolutionTooltip />} />
                <Legend wrapperStyle={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                {stateNames.map((name, i) => (
                  <Line key={name} type="monotone" dataKey={name}
                        stroke={STATE_COLORS[i % STATE_COLORS.length]}
                        strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[320px] flex items-center justify-center text-muted-foreground text-sm">
              No state evolution data
            </div>
          )}
        </CardContent>
      </Card>

      {/* Severity Stacked Area (kept from old WeeklyTrends) */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <Tip text="Stacked area of all NER intel items by severity over time. Red/orange surge = escalating threat environment." side="top">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
              <Activity size={16} className="text-primary" />
              Severity Trend (Aggregate)
            </CardTitle>
          </Tip>
        </CardHeader>
        <CardContent className="p-4" data-testid="severity-trend-chart">
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={dailyData}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }}
                       tickFormatter={(v) => v?.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                <Tooltip content={<CustomSeverityTooltip />} />
                <Legend wrapperStyle={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Area type="monotone" dataKey="critical" stackId="1"
                      stroke={SEVERITY_COLORS.critical} fill={SEVERITY_COLORS.critical} fillOpacity={0.6} />
                <Area type="monotone" dataKey="high"     stackId="1"
                      stroke={SEVERITY_COLORS.high}     fill={SEVERITY_COLORS.high}     fillOpacity={0.6} />
                <Area type="monotone" dataKey="medium"   stackId="1"
                      stroke={SEVERITY_COLORS.medium}   fill={SEVERITY_COLORS.medium}   fillOpacity={0.4} />
                <Area type="monotone" dataKey="low"      stackId="1"
                      stroke={SEVERITY_COLORS.low}      fill={SEVERITY_COLORS.low}      fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[260px] flex items-center justify-center text-muted-foreground text-sm">
              No trend data available
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cross-Border Correlation */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <Tip text="Dual-axis correlation: events in border countries (red bars) vs. correlated NER state activity (green line). Lagged spikes in green following red = potential spillover signal." side="top">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
              <Users size={16} className="text-primary" />
              Cross-Border Correlation
            </CardTitle>
          </Tip>
        </CardHeader>
        <CardContent className="p-4 space-y-4" data-testid="cross-border-chart">
          {crossBorderSeries.length === 0 ? (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              No cross-border activity in range
            </div>
          ) : crossBorderSeries.map(s => (
            <div key={s.border}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">
                {s.border} ↔ {s.ner_states.join(", ")}
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <ComposedChart data={s.data}>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }}
                         tickFormatter={(v) => v?.slice(5)} />
                  <YAxis yAxisId="left"  tick={{ fontSize: 9, fill: "#ef4444" }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 9, fill: "#a3e635" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar  yAxisId="left"  dataKey="border_events" fill="#ef4444" opacity={0.7}
                        name={`${s.border} events`} />
                  <Line yAxisId="right" type="monotone" dataKey="ner_events" stroke="#a3e635"
                        strokeWidth={2} dot={false} name="NER activity" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Category Analysis */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <Tip text="Threat categories ranked by item volume over the selected range. Red/amber overlay shows critical/high severity share within each category." side="top">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                <BarChart3 size={16} className="text-primary" />
                Threat Category Analysis
              </CardTitle>
            </Tip>
          </CardHeader>
          <CardContent className="p-4" data-testid="category-analysis-chart">
            {categoryData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={categoryData.slice(0, 12)}>
                  <XAxis dataKey="category" tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }}
                         angle={-30} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" radius={0}>
                    {categoryData.slice(0, 12).map((_, i) => (
                      <Cell key={i} fill={STATE_COLORS[i % STATE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">
                No category data
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Actors */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <Tip text="Most-frequently-mentioned actors/organizations across all NER intel items in this range. Includes insurgent groups, government forces and political organizations." side="top">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                <Users size={16} className="text-primary" />
                Top Actors
              </CardTitle>
            </Tip>
          </CardHeader>
          <CardContent className="p-4" data-testid="top-actors-chart">
            {topActors.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={topActors} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <YAxis dataKey="name" type="category" width={120}
                         tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="#f59e0b" radius={0} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">
                No actor data
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* State Drill-down (visible when state selected) */}
      {selectedState && (
        <Card ref={drilldownRef} className="border-2 border-primary rounded-none bg-card scroll-mt-4" data-tour="trends-drilldown">
          <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <MapPin size={16} className="text-primary" />
              Drill-Down: {selectedState}
            </CardTitle>
            <button onClick={() => setSelectedState(null)}
                    className="text-[10px] font-mono text-muted-foreground hover:text-foreground uppercase tracking-wider">
              ✕ Close
            </button>
          </CardHeader>
          <CardContent className="p-4" data-testid="drilldown-panel">
            {drilldownLoading ? (
              <div className="h-[260px] flex items-center justify-center text-muted-foreground text-sm">
                Loading drill-down…
              </div>
            ) : drilldown ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Top Locations */}
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1">
                    <AlertTriangle size={11} /> Top Locations / Districts
                  </div>
                  {drilldown.top_locations.length === 0 ? (
                    <div className="text-xs text-muted-foreground">No location data</div>
                  ) : (
                    <div className="space-y-2">
                      {drilldown.top_locations.map((loc, i) => {
                        const max = drilldown.top_locations[0].count || 1;
                        const pct = (loc.count / max) * 100;
                        return (
                          <div key={loc.name} data-testid={`drilldown-loc-${loc.name}`}>
                            <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                              <span className="uppercase">{loc.name}</span>
                              <div className="flex gap-2">
                                {loc.critical > 0 && <span className="text-red-400">{loc.critical}c</span>}
                                {loc.high > 0 && <span className="text-amber-400">{loc.high}h</span>}
                                <span className="font-bold">{loc.count}</span>
                              </div>
                            </div>
                            <div className="h-1.5 bg-muted overflow-hidden">
                              <div className="h-full transition-all"
                                   style={{ width: `${pct}%`,
                                            background: loc.critical > 0 ? SEVERITY_COLORS.critical
                                                       : loc.high > 0 ? SEVERITY_COLORS.high
                                                       : SEVERITY_COLORS.low }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Top Actors */}
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1">
                    <Users size={11} /> Active Actors in State
                  </div>
                  {drilldown.top_actors.length === 0 ? (
                    <div className="text-xs text-muted-foreground">No actor data</div>
                  ) : (
                    <div className="space-y-1">
                      {drilldown.top_actors.map((a, i) => (
                        <div key={a.name} className="flex items-center justify-between text-[10px] font-mono py-1 border-b border-border/40">
                          <span className="uppercase">{a.name.slice(0, 28)}</span>
                          <span className="font-bold text-foreground">{a.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Categories */}
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1">
                    <BarChart3 size={11} /> Threat Categories
                  </div>
                  {drilldown.categories.length === 0 ? (
                    <div className="text-xs text-muted-foreground">No category data</div>
                  ) : (
                    <div className="space-y-1">
                      {drilldown.categories.slice(0, 10).map((c) => (
                        <div key={c.category} className="flex items-center justify-between text-[10px] font-mono py-1 border-b border-border/40">
                          <span>{c.category}</span>
                          <span className="font-bold">{c.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">No data</div>
            )}

            {/* Daily severity for drilled state */}
            {drilldown && drilldown.daily_severity.length > 0 && (
              <div className="mt-6">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                  {selectedState} Daily Severity Trend
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={drilldown.daily_severity}>
                    <XAxis dataKey="date" tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }}
                           tickFormatter={(v) => v?.slice(5)} />
                    <YAxis tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Area type="monotone" dataKey="critical" stackId="1"
                          stroke={SEVERITY_COLORS.critical} fill={SEVERITY_COLORS.critical} fillOpacity={0.6} />
                    <Area type="monotone" dataKey="high"     stackId="1"
                          stroke={SEVERITY_COLORS.high}     fill={SEVERITY_COLORS.high}     fillOpacity={0.6} />
                    <Area type="monotone" dataKey="medium"   stackId="1"
                          stroke={SEVERITY_COLORS.medium}   fill={SEVERITY_COLORS.medium}   fillOpacity={0.4} />
                    <Area type="monotone" dataKey="low"      stackId="1"
                          stroke={SEVERITY_COLORS.low}      fill={SEVERITY_COLORS.low}      fillOpacity={0.3} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* State Activity Bars (kept) */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
            State-wise Activity (Range)
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          {stateData.length > 0 ? (
            <div className="space-y-3">
              {stateData.map((state) => {
                const maxCount = Math.max(...stateData.map(s => s.count));
                const pct = maxCount > 0 ? (state.count / maxCount) * 100 : 0;
                return (
                  <button
                    key={state.state}
                    onClick={() => setSelectedState(state.state)}
                    className="block w-full text-left hover:bg-muted/40 px-2 py-1 transition-colors"
                    data-testid={`state-bar-${state.state}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono uppercase tracking-wider">{state.state}</span>
                      <div className="flex items-center gap-2">
                        {state.critical > 0 && <span className="text-[10px] font-mono text-red-400">{state.critical} crit</span>}
                        {state.high > 0 && <span className="text-[10px] font-mono text-amber-400">{state.high} high</span>}
                        <span className="text-xs font-mono font-bold">{state.count}</span>
                      </div>
                    </div>
                    <div className="h-2 bg-muted overflow-hidden">
                      <div className="h-full transition-all duration-300"
                           style={{ width: `${pct}%`,
                                    background: state.critical > 0 ? SEVERITY_COLORS.critical
                                               : state.high > 0 ? SEVERITY_COLORS.high
                                               : SEVERITY_COLORS.low }} />
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="text-muted-foreground text-sm py-8 text-center">No state activity in range</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
