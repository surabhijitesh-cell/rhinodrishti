/**
 * FilterCascadeWidget — Admin-only: 4-stage pipeline funnel monitor.
 *
 * Shows:
 *  - Per-stage drop counts + pass rates (funnel viz)
 *  - Estimated Haiku calls saved + cost saved (INR + USD)
 *  - Health status: centroid age, Stage 1 fail-open rate
 *  - 7-day daily savings trend
 *  - Recent cycle table
 */

import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { RefreshCw, Filter, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";

const POLL_MS = 15 * 60 * 1000;  // cascade updates every 15min cycle

const STAGE_META = [
  {
    key: "stage0",
    label: "Stage 0 — Keyword",
    color: "bg-blue-500",
    bgLight: "bg-blue-500/10",
    cost: "FREE",
    rejKey: "stage0_rejected",
    passKey: "stage0_pass",
  },
  {
    key: "stage05",
    label: "Stage 0.5 — Embedding",
    color: "bg-cyan-500",
    bgLight: "bg-cyan-500/10",
    cost: "~$0.05/day",
    rejKey: "stage05_rejected",
    passKey: "stage05_pass",
  },
  {
    key: "stage1",
    label: "Stage 1 — Gemini",
    color: "bg-amber-500",
    bgLight: "bg-amber-500/10",
    cost: "~$0.20/day",
    rejKey: "stage1_rejected",
    passKey: "stage1_pass",
  },
  {
    key: "stage2",
    label: "Stage 2 — Haiku",
    color: "bg-violet-500",
    bgLight: "bg-violet-500/10",
    cost: "~$0.70/day",
    rejKey: null,
    passKey: "haiku_relevant",
  },
];

function pct(part, total) {
  if (!total) return 0;
  return Math.min(100, Math.round(part / total * 100));
}

function StatusPill({ status }) {
  const map = {
    healthy:  { color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30", label: "● HEALTHY" },
    degraded: { color: "bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse", label: "⚠ DEGRADED" },
    failing:  { color: "bg-red-500/20 text-red-400 border-red-500/30 animate-pulse", label: "✗ FAILING" },
    unknown:  { color: "bg-muted/20 text-muted-foreground border-border", label: "? UNKNOWN" },
  };
  const s = map[status] || map.unknown;
  return (
    <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${s.color}`}>
      {s.label}
    </Badge>
  );
}

function FunnelBar({ stage, scanned, data }) {
  const rej   = data?.[stage.rejKey] || 0;
  const pass  = data?.[stage.passKey] || 0;
  const total = stage.key === "stage2" ? (data?.haiku_relevant || 0) + (data?.haiku_not_relevant || 0) : (rej + pass);
  const passW = pct(pass || data?.haiku_relevant || 0, scanned);
  const rejW  = pct(rej, scanned);

  return (
    <div className={`p-2 rounded-none ${stage.bgLight} border border-transparent`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-mono font-semibold text-foreground">{stage.label}</span>
        <span className="text-[9px] font-mono text-muted-foreground/60">{stage.cost}</span>
      </div>

      {/* Funnel bar */}
      <div className="h-4 bg-muted/30 rounded-none overflow-hidden flex">
        {stage.key !== "stage2" ? (
          <>
            <div className={`${stage.color} opacity-80`} style={{ width: `${passW}%` }} title={`${pass} pass`} />
            <div className="bg-red-500/40" style={{ width: `${rejW}%` }} title={`${rej} rejected`} />
          </>
        ) : (
          <>
            <div className="bg-violet-500/80" style={{ width: `${pct(data?.haiku_relevant || 0, scanned)}%` }}
              title={`${data?.haiku_relevant || 0} relevant`} />
            <div className="bg-violet-500/30" style={{ width: `${pct(data?.haiku_not_relevant || 0, scanned)}%` }}
              title={`${data?.haiku_not_relevant || 0} not relevant`} />
          </>
        )}
      </div>

      <div className="flex justify-between mt-1 text-[9px] font-mono">
        {stage.key !== "stage2" ? (
          <>
            <span className="text-emerald-400">{pass.toLocaleString()} pass ({pct(pass, total)}%)</span>
            <span className="text-red-400">{rej.toLocaleString()} drop</span>
          </>
        ) : (
          <>
            <span className="text-violet-400">{(data?.haiku_relevant || 0).toLocaleString()} kept</span>
            <span className="text-muted-foreground">{(data?.haiku_not_relevant || 0)} not relevant</span>
          </>
        )}
      </div>
    </div>
  );
}

function DailySavingsBar({ rows }) {
  if (!rows?.length) return null;
  const maxSaved = Math.max(...rows.map(r => r.est_cost_saved_usd || 0), 0.01);
  return (
    <div className="space-y-1">
      {rows.map(r => {
        const pctW = Math.min((r.est_cost_saved_usd || 0) / maxSaved * 100, 100);
        return (
          <div key={r.date} className="flex items-center gap-2 text-[9px] font-mono">
            <span className="w-10 text-muted-foreground shrink-0">{r.date.slice(5)}</span>
            <div className="flex-1 h-2.5 bg-muted/20 overflow-hidden rounded-none">
              <div className="h-full bg-emerald-500/60" style={{ width: `${pctW}%` }} />
            </div>
            <span className="w-16 text-right text-emerald-400 shrink-0">
              ₹{((r.est_cost_saved_usd || 0) * 84).toFixed(0)} saved
            </span>
          </div>
        );
      })}
    </div>
  );
}

function RecentCyclesTable({ cycles }) {
  if (!cycles?.length) return <p className="text-[9px] font-mono text-muted-foreground">No cycle data yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[9px] font-mono">
        <thead>
          <tr className="text-muted-foreground border-b border-border">
            <th className="text-left pb-1 pr-2">Time</th>
            <th className="text-right pb-1 pr-2">Scanned</th>
            <th className="text-right pb-1 pr-2">S0↓</th>
            <th className="text-right pb-1 pr-2">S0.5↓</th>
            <th className="text-right pb-1 pr-2">S1↓</th>
            <th className="text-right pb-1 pr-2">Haiku✓</th>
            <th className="text-right pb-1">Saved</th>
          </tr>
        </thead>
        <tbody>
          {cycles.slice(0, 10).map((c, i) => (
            <tr key={i} className="border-b border-border/20 hover:bg-muted/10">
              <td className="py-0.5 pr-2 text-muted-foreground">
                {c.started_at ? c.started_at.slice(11, 16) : "—"}
              </td>
              <td className="py-0.5 pr-2 text-right">{c.items_scanned}</td>
              <td className="py-0.5 pr-2 text-right text-blue-400">{c.stage0_rejected}</td>
              <td className="py-0.5 pr-2 text-right text-cyan-400">{c.stage05_rejected}</td>
              <td className="py-0.5 pr-2 text-right text-amber-400">{c.stage1_rejected}</td>
              <td className="py-0.5 pr-2 text-right text-violet-400">{c.haiku_relevant}</td>
              <td className="py-0.5 text-right text-emerald-400">
                ₹{((c.est_cost_saved_usd || 0) * 84).toFixed(0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FilterCascadeWidget({ api }) {
  const [today, setToday]           = useState(null);
  const [daily, setDaily]           = useState([]);
  const [recent, setRecent]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [showTrend, setShowTrend]   = useState(false);
  const [showCycles, setShowCycles] = useState(false);

  const load = useCallback(async (silent = false) => {
    try {
      const [todayRes, dailyRes, recentRes] = await Promise.all([
        axios.get(`${api}/admin/filter-cascade/today`),
        axios.get(`${api}/admin/filter-cascade/daily?days=7`),
        axios.get(`${api}/admin/filter-cascade/recent?limit=20`),
      ]);
      setToday(todayRes.data);
      setDaily(dailyRes.data.daily || []);
      setRecent(recentRes.data.cycles || []);
    } catch (e) {
      if (!silent) console.error("FilterCascadeWidget load error:", e);
    }
    if (!silent) setLoading(false);
  }, [api]);

  useEffect(() => {
    load();
    const id = setInterval(() => load(true), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  if (loading) {
    return (
      <Card className="border border-border rounded-none bg-card border-l-4 border-l-emerald-500">
        <CardContent className="p-4 flex items-center gap-2 text-muted-foreground text-xs">
          <RefreshCw size={12} className="animate-spin" /> Loading cascade data…
        </CardContent>
      </Card>
    );
  }

  const d = today || {};
  const health = d.health || {};
  const scanned = d.items_scanned || 0;
  const savedUsd = d.est_cost_saved_usd || 0;
  const savedInr = d.est_cost_saved_inr || Math.round(savedUsd * 84);
  const savedPct = scanned > 0
    ? Math.round(((scanned - (d.haiku_relevant || 0) - (d.haiku_not_relevant || 0)) / scanned) * 100)
    : 0;

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-emerald-500">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Filter size={14} className="text-emerald-400" />
          Filter Cascade
          <StatusPill status={health.status || "unknown"} />
          <button onClick={() => load(true)} className="ml-auto text-muted-foreground/40 hover:text-muted-foreground">
            <RefreshCw size={10} />
          </button>
        </CardTitle>
      </CardHeader>

      <CardContent className="p-4 space-y-4">

        {/* ── Overview ── */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">Today Scanned</p>
            <p className="text-lg font-bold font-mono">{scanned.toLocaleString()}</p>
            <p className="text-[9px] font-mono text-muted-foreground">{d.cycles || 0} cycles</p>
          </div>
          <div className="text-right">
            <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">Haiku Calls Saved</p>
            <p className="text-lg font-bold font-mono text-emerald-400">
              {(d.est_haiku_calls_saved || 0).toLocaleString()}
            </p>
            <p className="text-[9px] font-mono text-emerald-400/70">{savedPct}% reduction</p>
          </div>
          <div className="text-right">
            <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">Cost Saved</p>
            <p className="text-lg font-bold font-mono text-emerald-400">₹{savedInr}</p>
            <p className="text-[9px] font-mono text-muted-foreground/60">${savedUsd.toFixed(3)}</p>
          </div>
        </div>

        {/* ── Funnel stages ── */}
        <div className="space-y-1.5">
          {STAGE_META.map(stage => (
            <FunnelBar key={stage.key} stage={stage} scanned={scanned} data={d} />
          ))}
        </div>

        {/* ── Health block ── */}
        <div className="border border-border/30 p-2.5 space-y-1.5 bg-muted/5">
          <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold">
            System Health
          </p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[9px] font-mono">
            <span className="text-muted-foreground">Gemini key</span>
            <span className={health.stage1_key_present ? "text-emerald-400" : "text-red-400"}>
              {health.stage1_key_present ? "✓ present" : "✗ missing — Stage 1 disabled"}
            </span>
            <span className="text-muted-foreground">S1 fail-open (24h)</span>
            <span className={health.stage1_failopen_rate_pct > 5 ? "text-amber-400" : "text-emerald-400"}>
              {health.stage1_failopen_rate_pct?.toFixed(1) || 0}%
            </span>
            <span className="text-muted-foreground">Centroid</span>
            <span className={health.centroid_ready ? "text-emerald-400" : "text-amber-400"}>
              {health.centroid_ready
                ? `✓ ${health.centroid_ref_items} refs · ${health.centroid_age_hours?.toFixed(1)}h old`
                : "⚠ not ready"}
            </span>
            <span className="text-muted-foreground">Min similarity</span>
            <span className="text-foreground">{health.centroid_min_sim}</span>
            <span className="text-muted-foreground">Avg cycle duration</span>
            <span className="text-foreground">{d.avg_duration ? `${d.avg_duration}s` : "—"}</span>
            <span className="text-muted-foreground">Cycles (24h)</span>
            <span className="text-foreground">{health.cycles_last_24h || 0}</span>
          </div>
        </div>

        {/* ── 7-day savings trend (collapsible) ── */}
        <div>
          <button
            onClick={() => setShowTrend(v => !v)}
            className="flex items-center gap-1 text-[9px] font-mono text-muted-foreground uppercase tracking-wider hover:text-foreground"
          >
            7-Day Savings {showTrend ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
          </button>
          {showTrend && (
            <div className="mt-2">
              <DailySavingsBar rows={daily} />
            </div>
          )}
        </div>

        {/* ── Recent cycles table (collapsible) ── */}
        <div>
          <button
            onClick={() => setShowCycles(v => !v)}
            className="flex items-center gap-1 text-[9px] font-mono text-muted-foreground uppercase tracking-wider hover:text-foreground"
          >
            Recent Cycles {showCycles ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
          </button>
          {showCycles && (
            <div className="mt-2">
              <RecentCyclesTable cycles={recent} />
            </div>
          )}
        </div>

      </CardContent>
    </Card>
  );
}
