/**
 * ApiUsageWidget — Admin-only panel: multi-provider API spend.
 *
 * Shows:
 *  - Total today's cost (INR + USD) vs total alert threshold
 *  - Per-provider breakdown (Anthropic / Gemini / OpenAI) with sub-alerts
 *  - Hourly stacked sparkline (color per provider)
 *  - 7-day daily cost history
 *  - Threshold editor (total + per-provider)
 */

import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  DollarSign, AlertTriangle, TrendingUp, Settings2,
  RefreshCw, Zap, ChevronDown, ChevronUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

const POLL_MS = 5 * 60 * 1000;

const PROVIDER_META = {
  anthropic: { label: "Anthropic (legacy)", color: "bg-violet-500",  dot: "bg-violet-400"  },
  gemini:    { label: "Gemini Flash (S1+S2)", color: "bg-amber-500", dot: "bg-amber-400"   },
  openai:    { label: "OpenAI Embeddings",  color: "bg-cyan-500",    dot: "bg-cyan-400"    },
};

function MiniBar({ value, max, color = "bg-emerald-500" }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full h-1.5 bg-muted/30 rounded-none overflow-hidden">
      <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function StackedSparkline({ hourly }) {
  if (!hourly?.length) return <div className="text-[9px] text-muted-foreground font-mono">No data yet</div>;

  const hourMap = {};
  for (const h of hourly) {
    const hr = h.hour;
    if (!hourMap[hr]) hourMap[hr] = {};
    hourMap[hr][h.provider] = (hourMap[hr][h.provider] || 0) + h.cost_usd;
  }

  const totals = Object.values(hourMap).map(ps => Object.values(ps).reduce((a, b) => a + b, 0));
  const maxVal = Math.max(...totals, 0.0001);

  return (
    <div className="flex items-end gap-0.5 h-8 mt-1">
      {Array.from({ length: 24 }, (_, i) => {
        const ps = hourMap[i] || {};
        const total = Object.values(ps).reduce((a, b) => a + b, 0);
        const barH = total > 0 ? Math.max(Math.round((total / maxVal) * 32), 2) : 1;
        const tooltip = `${i}:00 — $${total.toFixed(4)} total`;
        return (
          <div
            key={i}
            title={tooltip}
            className="flex-1 flex flex-col-reverse overflow-hidden rounded-none"
            style={{ height: `${barH}px` }}
          >
            {["anthropic", "gemini", "openai"].map(p => {
              const cost = ps[p] || 0;
              if (!cost) return null;
              const pct = (cost / (total || 1)) * 100;
              return (
                <div
                  key={p}
                  className={`${PROVIDER_META[p]?.color || "bg-muted"} w-full`}
                  style={{ height: `${pct}%` }}
                />
              );
            })}
            {total === 0 && <div className="bg-muted/20 w-full h-full" />}
          </div>
        );
      })}
    </div>
  );
}

function DayBar({ day, maxCost }) {
  const pct = maxCost > 0 ? Math.min((day.cost_usd / maxCost) * 100, 100) : 0;
  const label = day.date.slice(5);
  return (
    <div className="flex items-center gap-2 text-[9px] font-mono">
      <span className="w-10 text-muted-foreground shrink-0">{label}</span>
      <div className="flex-1 h-3 bg-muted/20 relative overflow-hidden rounded-none">
        <div className="h-full bg-violet-500/60" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right text-muted-foreground shrink-0">₹{day.cost_inr.toFixed(0)}</span>
      <span className="w-12 text-right text-muted-foreground/60 shrink-0">${day.cost_usd.toFixed(3)}</span>
    </div>
  );
}

function ProviderRow({ name, data, onEditThreshold }) {
  const meta = PROVIDER_META[name] || { label: name, color: "bg-muted", dot: "bg-muted" };
  const cost = data?.cost_usd || 0;
  const calls = data?.call_count || 0;
  const thr = data?.threshold_usd || 0;
  const pct = thr > 0 ? Math.min(cost / thr * 100, 100) : 0;
  const alert = data?.alert;
  const inr = data?.cost_inr || 0;

  return (
    <div className={`space-y-1 p-2 border rounded-none ${alert ? "border-red-500/30 bg-red-500/5" : "border-border/30"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
          <span className="text-[10px] font-mono text-muted-foreground">{meta.label}</span>
          {alert && <span className="text-[8px] text-red-400 font-bold">⚠</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[11px] font-bold font-mono ${alert ? "text-red-400" : "text-foreground"}`}>
            ₹{inr.toFixed(0)}
          </span>
          <span className="text-[9px] font-mono text-muted-foreground/60">${cost.toFixed(3)}</span>
          <span className="text-[9px] font-mono text-muted-foreground/40">{calls} calls</span>
          <button
            onClick={() => onEditThreshold(name, thr)}
            className="text-muted-foreground/30 hover:text-muted-foreground"
            title={`Alert at $${thr}`}
          >
            <Settings2 size={9} />
          </button>
        </div>
      </div>
      <div className="flex gap-1 items-center">
        <div className="flex-1 h-1 bg-muted/20 overflow-hidden rounded-none">
          <div className={`h-full ${meta.color} opacity-70`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[8px] font-mono text-muted-foreground/40 w-8 text-right">
          {pct.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

export default function ApiUsageWidget({ api }) {
  const [today, setToday]           = useState(null);
  const [daily, setDaily]           = useState([]);
  const [threshold, setThreshold]   = useState(15);
  const [editMode, setEditMode]     = useState(null); // null | "total" | provider name
  const [editVal, setEditVal]       = useState("");
  const [loading, setLoading]       = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const alertFiredRef               = useRef(false);

  const load = useCallback(async (silent = false) => {
    try {
      const [todayRes, histRes] = await Promise.all([
        axios.get(`${api}/admin/api-usage/today`),
        axios.get(`${api}/admin/api-usage?days=7`),
      ]);
      const t = todayRes.data;
      setToday(t);
      setDaily(histRes.data.daily || []);
      setThreshold(histRes.data.threshold_usd || 15);

      if (t.alert && !alertFiredRef.current) {
        alertFiredRef.current = true;
        toast.error(
          `⚠ API spend alert! Total today: ₹${t.today_inr} ($${t.today_usd}) — ${t.pct_of_limit}% of $${t.threshold_usd} daily limit.`,
          { duration: 12000 }
        );
      }
      if (!t.alert) alertFiredRef.current = false;
    } catch (e) {
      if (!silent) console.error("ApiUsageWidget load error:", e);
    }
    if (!silent) setLoading(false);
  }, [api]);

  useEffect(() => {
    load();
    const id = setInterval(() => load(true), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const saveThreshold = async () => {
    const val = parseFloat(editVal);
    if (!val || val <= 0) return;
    try {
      if (editMode === "total") {
        await axios.post(`${api}/admin/api-usage/threshold`, { threshold_usd: val });
        toast.success(`Total daily limit set to $${val}`);
      } else {
        await axios.post(`${api}/admin/api-usage/threshold/provider`,
          { provider: editMode, threshold_usd: val });
        toast.success(`${PROVIDER_META[editMode]?.label || editMode} limit set to $${val}`);
      }
      setEditMode(null);
      load(true);
    } catch {
      toast.error("Failed to save threshold");
    }
  };

  if (loading) {
    return (
      <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500">
        <CardContent className="p-4 flex items-center gap-2 text-muted-foreground text-xs">
          <RefreshCw size={12} className="animate-spin" /> Loading usage data…
        </CardContent>
      </Card>
    );
  }

  const maxDailyCost = Math.max(...daily.map(d => d.cost_usd), 0.01);
  const totalPctColor = today?.pct_of_limit >= 90 ? "bg-red-500"
                      : today?.pct_of_limit >= 70 ? "bg-amber-500"
                      : "bg-emerald-500";
  const providers = today?.by_provider || {};

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Zap size={14} className="text-violet-400" />
          API Spend
          {today?.alert && (
            <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-red-500/20 text-red-400 border-red-500/30 ml-1 animate-pulse">
              ⚠ ALERT
            </Badge>
          )}
          <button onClick={() => load(true)} className="ml-auto text-muted-foreground/40 hover:text-muted-foreground">
            <RefreshCw size={10} />
          </button>
        </CardTitle>
      </CardHeader>

      <CardContent className="p-4 space-y-4">

        {/* ── Total today ── */}
        {today && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono uppercase text-muted-foreground tracking-wider">Today Total</span>
                <button
                  onClick={() => { setEditVal(String(threshold)); setEditMode("total"); }}
                  className="text-muted-foreground/30 hover:text-muted-foreground"
                  title="Edit total limit"
                ><Settings2 size={9} /></button>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-bold font-mono ${today.alert ? "text-red-400" : "text-emerald-400"}`}>
                  ₹{today.today_inr.toFixed(0)}
                </span>
                <span className="text-[9px] font-mono text-muted-foreground">${today.today_usd.toFixed(3)}</span>
              </div>
            </div>
            <MiniBar value={today.today_usd} max={today.threshold_usd} color={totalPctColor} />
            <div className="flex justify-between text-[9px] font-mono text-muted-foreground">
              <span>{today.pct_of_limit}% of daily limit</span>
              <span>Limit ₹{today.threshold_inr} (${today.threshold_usd})</span>
            </div>
          </div>
        )}

        {/* ── Threshold inline editor ── */}
        {editMode && (
          <div className="flex items-center gap-2 border border-border p-2">
            <span className="text-[10px] font-mono text-muted-foreground shrink-0">
              {editMode === "total" ? "Total limit $" : `${PROVIDER_META[editMode]?.label || editMode} limit $`}
            </span>
            <Input
              type="number" value={editVal} onChange={e => setEditVal(e.target.value)}
              className="rounded-none text-xs h-7 w-20 font-mono"
              min={0.01} step={0.1}
              onKeyDown={e => e.key === "Enter" && saveThreshold()}
            />
            <Button size="sm" onClick={saveThreshold} className="rounded-none h-7 text-[10px] uppercase">Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditMode(null)} className="rounded-none h-7 text-[10px]">✕</Button>
          </div>
        )}

        {/* ── Per-provider rows ── */}
        <div className="space-y-1.5">
          <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">By Provider</p>
          {["anthropic", "gemini", "openai"].map(p => (
            <ProviderRow
              key={p}
              name={p}
              data={providers[p]}
              onEditThreshold={(name, cur) => { setEditVal(String(cur)); setEditMode(name); }}
            />
          ))}
        </div>

        {/* ── Hourly sparkline ── */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">Hourly (UTC)</p>
            <div className="flex items-center gap-2 ml-auto">
              {Object.entries(PROVIDER_META).map(([k, m]) => (
                <span key={k} className="flex items-center gap-0.5 text-[8px] font-mono text-muted-foreground">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${m.dot}`} />{k.slice(0, 3)}
                </span>
              ))}
            </div>
          </div>
          <StackedSparkline hourly={today?.hourly || []} />
        </div>

        {/* ── 7-day history (collapsible) ── */}
        {daily.length > 0 && (
          <div className="space-y-1.5">
            <button
              onClick={() => setShowHistory(h => !h)}
              className="flex items-center gap-1 text-[9px] font-mono text-muted-foreground uppercase tracking-wider hover:text-foreground"
            >
              7-Day History {showHistory ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
            </button>
            {showHistory && daily.map(d => <DayBar key={d.date} day={d} maxCost={maxDailyCost} />)}
          </div>
        )}

        {/* ── Exchange rate footer ── */}
        {today?.usd_to_inr && (
          <p className="text-[8px] font-mono text-muted-foreground/40 text-right border-t border-border/30 pt-2">
            1 USD = ₹{today.usd_to_inr.toFixed(2)} · live rate
          </p>
        )}

      </CardContent>
    </Card>
  );
}
