import { useState, useEffect } from "react";
import { TrendingUp, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, LineChart, Line, Legend
} from "recharts";

const SEVERITY_COLORS = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#eab308",
  low: "#a3e635",
};
const STATE_COLORS = ["#a3e635", "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#06b6d4", "#ec4899", "#6366f1"];

export default function WeeklyTrends({ api }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrends();
  }, [api]);

  const fetchTrends = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/weekly-trends`);
      setData(res.data);
    } catch (e) {
      console.error("Failed to fetch trends:", e);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="space-y-4" data-testid="weekly-trends-loading">
        <div className="h-10 bg-muted animate-pulse w-1/2" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="border border-border bg-card p-4 animate-pulse h-[300px]" />
        ))}
      </div>
    );
  }

  const dailyData = data?.daily_severity || [];
  const categoryData = data?.category_stats || [];
  const stateData = data?.state_stats || [];

  const tooltipStyle = {
    background: "hsl(120,10%,8%)",
    border: "1px solid hsl(120,5%,20%)",
    borderRadius: 0,
    fontSize: 12,
  };

  return (
    <div className="space-y-6" data-testid="weekly-trends-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="trends-title">
          Weekly Trend Analysis
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Pattern detection and escalation signals
        </p>
      </div>

      {/* Severity Trend Over Time */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <TrendingUp size={16} className="text-primary" />
            Severity Trend Over Time
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4" data-testid="severity-trend-chart">
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={dailyData}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend
                  wrapperStyle={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
                />
                <Area
                  type="monotone"
                  dataKey="critical"
                  stackId="1"
                  stroke={SEVERITY_COLORS.critical}
                  fill={SEVERITY_COLORS.critical}
                  fillOpacity={0.6}
                />
                <Area
                  type="monotone"
                  dataKey="high"
                  stackId="1"
                  stroke={SEVERITY_COLORS.high}
                  fill={SEVERITY_COLORS.high}
                  fillOpacity={0.6}
                />
                <Area
                  type="monotone"
                  dataKey="medium"
                  stackId="1"
                  stroke={SEVERITY_COLORS.medium}
                  fill={SEVERITY_COLORS.medium}
                  fillOpacity={0.4}
                />
                <Area
                  type="monotone"
                  dataKey="low"
                  stackId="1"
                  stroke={SEVERITY_COLORS.low}
                  fill={SEVERITY_COLORS.low}
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-muted-foreground text-sm">
              No trend data available
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Category Analysis */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <BarChart3 size={16} className="text-primary" />
              Threat Category Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4" data-testid="category-analysis-chart">
            {categoryData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={categoryData}>
                  <XAxis
                    dataKey="category"
                    tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }}
                    angle={-30}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="hsl(84,80%,55%)" radius={0}>
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={STATE_COLORS[i % STATE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground text-sm">
                No category data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* State Analysis */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              State-wise Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4" data-testid="state-analysis-chart">
            {stateData.length > 0 ? (
              <div className="space-y-3">
                {stateData.map((state, i) => {
                  const maxCount = Math.max(...stateData.map((s) => s.count));
                  const pct = maxCount > 0 ? (state.count / maxCount) * 100 : 0;
                  return (
                    <div key={state.state} data-testid={`state-bar-${state.state}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-mono uppercase tracking-wider">{state.state}</span>
                        <div className="flex items-center gap-2">
                          {state.critical > 0 && (
                            <span className="text-[10px] font-mono text-red-400">{state.critical} crit</span>
                          )}
                          {state.high > 0 && (
                            <span className="text-[10px] font-mono text-amber-400">{state.high} high</span>
                          )}
                          <span className="text-xs font-mono font-bold">{state.count}</span>
                        </div>
                      </div>
                      <div className="h-2 bg-muted overflow-hidden">
                        <div
                          className="h-full transition-all duration-300"
                          style={{
                            width: `${pct}%`,
                            background: state.critical > 0
                              ? SEVERITY_COLORS.critical
                              : state.high > 0
                              ? SEVERITY_COLORS.high
                              : SEVERITY_COLORS.low,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground text-sm">
                No state data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Total Trend */}
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
            Total Intelligence Volume
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4" data-testid="volume-trend-chart">
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={dailyData}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="hsl(84,80%,55%)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "hsl(84,80%,55%)" }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              No volume data available
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
