/**
 * Widget rendering registry — one renderer per widget type.
 *
 * Each renderer receives `{ data }` already fetched by the parent and outputs
 * the visualization content (wrapped in WidgetCard by the parent).
 */
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, Cell, PieChart, Pie,
  LineChart, Line, ComposedChart,
} from "recharts";

const SEVERITY_COLORS = {
  critical: "#ef4444", high: "#f59e0b", medium: "#eab308", low: "#a3e635",
};
const PIE_COLORS = ["#ef4444", "#f59e0b", "#eab308", "#a3e635", "#06b6d4", "#8b5cf6", "#ec4899", "#3b82f6"];

const tooltipStyle = {
  background: "hsl(120,10%,8%)",
  border: "1px solid hsl(120,5%,20%)",
  borderRadius: 0,
  fontSize: 11,
};

// ─── Severity Evolution (stacked area) ──────────────────────────────────────
export function SeverityEvolutionRender({ data }) {
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data}>
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }}
               tickFormatter={(v) => v?.slice(5)} />
        <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
        {["critical", "high", "medium", "low"].map(sev => (
          <Area key={sev} type="monotone" dataKey={sev} stackId="1"
                stroke={SEVERITY_COLORS[sev]} fill={SEVERITY_COLORS[sev]} fillOpacity={0.6} />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── Threat Heatmap (state × category SVG grid) ─────────────────────────────
export function ThreatHeatmapRender({ data, categories }) {
  if (!data?.length || !categories?.length) return <Empty />;
  const maxCell = Math.max(...data.flatMap(r => categories.map(c => r[c] || 0)), 1);
  const cellW = 70, cellH = 26, labelW = 110, headerH = 80;
  const W = labelW + cellW * categories.length + 20;
  const H = headerH + cellH * data.length + 10;
  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={W} height={H} style={{ background: "#0a0f0a", fontFamily: "JetBrains Mono" }}>
        {/* Category labels (rotated) */}
        {categories.map((c, i) => (
          <text key={c} x={labelW + i * cellW + cellW / 2} y={headerH - 6}
                fill="#9ca3af" fontSize="9"
                textAnchor="start"
                transform={`rotate(-45, ${labelW + i * cellW + cellW / 2}, ${headerH - 6})`}>
            {c.slice(0, 20)}
          </text>
        ))}
        {/* Rows */}
        {data.map((row, ri) => (
          <g key={row.state}>
            <text x={labelW - 6} y={headerH + ri * cellH + cellH * 0.65}
                  fill="#d4d4d4" fontSize="10" textAnchor="end">
              {row.state}
            </text>
            {categories.map((c, ci) => {
              const v = row[c] || 0;
              const intensity = v / maxCell;
              const fill = v === 0 ? "#1a1f1a" : `hsla(0, 80%, ${20 + intensity * 35}%, ${0.3 + intensity * 0.7})`;
              return (
                <g key={c}>
                  <rect x={labelW + ci * cellW + 1} y={headerH + ri * cellH + 1}
                        width={cellW - 2} height={cellH - 2}
                        fill={fill} stroke="#0a0f0a" />
                  {v > 0 && (
                    <text x={labelW + ci * cellW + cellW / 2}
                          y={headerH + ri * cellH + cellH * 0.65}
                          fill="#fff" fontSize="10" fontWeight="600"
                          textAnchor="middle">{v}</text>
                  )}
                </g>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}

// ─── Actor Activity Tracker ─────────────────────────────────────────────────
export function ActorActivityRender({ data }) {
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 22)}>
      <BarChart data={data} layout="vertical" stackOffset="sign">
        <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
        <YAxis dataKey="name" type="category" width={140}
               tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
        <Bar dataKey="critical" stackId="a" fill={SEVERITY_COLORS.critical} />
        <Bar dataKey="high"     stackId="a" fill={SEVERITY_COLORS.high} />
        <Bar dataKey="medium"   stackId="a" fill={SEVERITY_COLORS.medium} />
        <Bar dataKey="low"      stackId="a" fill={SEVERITY_COLORS.low} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Intelligence Velocity ──────────────────────────────────────────────────
export function IntelVelocityRender({ data }) {
  if (!data?.length) return <Empty />;
  const TREND_COLOR = { RISING: "#ef4444", STEADY: "#a3e635", FALLING: "#06b6d4" };
  return (
    <div className="space-y-2">
      {data.map(d => (
        <div key={d.state} className="flex items-center gap-3 py-1.5 border-b border-border/40"
             data-testid={`velocity-${d.state}`}>
          <span className="text-xs font-mono uppercase tracking-wider w-32">{d.state}</span>
          <div className="flex-1 grid grid-cols-3 gap-3 text-[10px] font-mono">
            <div>
              <span className="text-muted-foreground">/day:</span>
              <span className="ml-1 font-bold">{d.per_day}</span>
            </div>
            <div>
              <span className="text-muted-foreground">accel:</span>
              <span className="ml-1 font-bold">{d.acceleration}x</span>
            </div>
            <div>
              <span className="text-muted-foreground">total:</span>
              <span className="ml-1 font-bold">{d.total}</span>
            </div>
          </div>
          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm"
                style={{ background: `${TREND_COLOR[d.trend]}22`,
                         color: TREND_COLOR[d.trend],
                         border: `1px solid ${TREND_COLOR[d.trend]}55` }}>
            {d.trend}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Geographic Threat Density ──────────────────────────────────────────────
export function GeoDensityRender({ data }) {
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 24)}>
      <BarChart data={data} layout="vertical">
        <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
        <YAxis dataKey="name" type="category" width={130}
               tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} />
        <Tooltip contentStyle={tooltipStyle}
                 formatter={(v, n) => [v, n]}
                 labelFormatter={(name) => {
                   const r = data.find(d => d.name === name);
                   return `${name}${r?.primary_state ? ` (${r.primary_state})` : ""}`;
                 }} />
        <Legend wrapperStyle={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
        <Bar dataKey="critical" stackId="a" fill={SEVERITY_COLORS.critical} />
        <Bar dataKey="high"     stackId="a" fill={SEVERITY_COLORS.high} />
        <Bar dataKey="medium"   stackId="a" fill={SEVERITY_COLORS.medium} />
        <Bar dataKey="low"      stackId="a" fill={SEVERITY_COLORS.low} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Category Breakdown ─────────────────────────────────────────────────────
export function CategoryBreakdownRender({ data }) {
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data}>
        <XAxis dataKey="category" tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }}
               angle={-30} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="count" radius={0}>
          {data.map((_, i) => (
            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Severity Pie ───────────────────────────────────────────────────────────
export function SeverityPieRender({ data }) {
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
             innerRadius={50} outerRadius={90} paddingAngle={2}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || "#888"} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ─── Source Breakdown ───────────────────────────────────────────────────────
export function SourceBreakdownRender({ data }) {
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 22)}>
      <BarChart data={data} layout="vertical">
        <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
        <YAxis dataKey="source" type="category" width={150}
               tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="count" fill="#06b6d4" radius={0} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function Empty() {
  return (
    <div className="h-[200px] flex items-center justify-center text-muted-foreground text-xs font-mono">
      No data for current filters
    </div>
  );
}

// ─── Registry map ───────────────────────────────────────────────────────────
export const WIDGET_RENDERERS = {
  severity_evolution:  SeverityEvolutionRender,
  threat_heatmap:      ThreatHeatmapRender,
  actor_activity:      ActorActivityRender,
  intel_velocity:      IntelVelocityRender,
  geo_density:         GeoDensityRender,
  category_breakdown:  CategoryBreakdownRender,
  severity_pie:        SeverityPieRender,
  source_breakdown:    SourceBreakdownRender,
};
