/**
 * ApiUsageWidget — Admin-only panel showing Anthropic API token spend.
 *
 * Shows:
 *  - Today's cost in USD + INR  with a progress bar vs threshold
 *  - Hourly sparkline for today
 *  - 7-day daily cost bar chart
 *  - Threshold editor (admin)
 *  - Alert popup (toast) when threshold is breached
 */

import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  DollarSign, AlertTriangle, TrendingUp, Settings2,
  RefreshCw, Zap, CheckCircle2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

const POLL_MS = 5 * 60 * 1000;   // poll every 5 minutes

function Bar({ value, max, color = "bg-emerald-500" }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full h-1.5 bg-muted/30 rounded-none overflow-hidden">
      <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SparkLine({ hourly }) {
  if (!hourly?.length) return <div className="text-[9px] text-muted-foreground font-mono">No data yet</div>;
  const maxCost = Math.max(...hourly.map(h => h.cost_usd), 0.0001);
  const HEIGHT  = 32;
  return (
    <div className="flex items-end gap-0.5 h-8 mt-1">
      {Array.from({ length: 24 }, (_, i) => {
        const h = hourly.find(x => x.hour === i);
        const cost = h?.cost_usd || 0;
        const barH = Math.max(Math.round((cost / maxCost) * HEIGHT), cost > 0 ? 2 : 1);
        return (
          <div
            key={i}
            title={`${i}:00 — $${cost.toFixed(4)} (${h?.call_count || 0} calls)`}
            className={`flex-1 rounded-none transition-all ${cost > 0 ? "bg-violet-500/70" : "bg-muted/20"}`}
            style={{ height: `${barH}px` }}
          />
        );
      })}
    </div>
  );
}

function DayBar({ day, maxCost }) {
  const pct = maxCost > 0 ? Math.min((day.cost_usd / maxCost) * 100, 100) : 0;
  const label = day.date.slice(5);   // "MM-DD"
  return (
    <div className="flex items-center gap-2 text-[9px] font-mono">
      <span className="w-10 text-muted-foreground shrink-0">{label}</span>
      <div className="flex-1 h-3 bg-muted/20 relative overflow-hidden rounded-none">
        <div className="h-full bg-violet-500/60" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right text-muted-foreground shrink-0">
        ₹{day.cost_inr.toFixed(0)}
      </span>
      <span className="w-12 text-right text-muted-foreground/60 shrink-0">
        ${day.cost_usd.toFixed(2)}
      </span>
    </div>
  );
}

export default function ApiUsageWidget({ api }) {
  const [today, setToday]       = useState(null);
  const [daily, setDaily]       = useState([]);
  const [threshold, setThreshold] = useState(15);
  const [editingThr, setEditingThr] = useState(false);
  const [newThr, setNewThr]     = useState("");
  const [loading, setLoading]   = useState(true);
  const alertFiredRef           = useRef(false);

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

      // Alert popup — fires once per session when threshold crossed
      if (t.alert && !alertFiredRef.current) {
        alertFiredRef.current = true;
        toast.error(
          `⚠ Anthropic API spend alert! Today: ₹${t.today_inr} ($${t.today_usd}) — ${t.pct_of_limit}% of your $${t.threshold_usd} daily limit. Review usage in the API Usage panel.`,
          { duration: 12000 }
        );
      }
      // Reset alert flag if cost drops below threshold (e.g. new day)
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
    const val = parseFloat(newThr);
    if (!val || val <= 0) return;
    try {
      await axios.post(`${api}/admin/api-usage/threshold`, { threshold_usd: val });
      toast.success(`Alert threshold set to $${val} (₹${(val * 84).toFixed(0)})`);
      setEditingThr(false);
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
  const pctColor = today?.pct_of_limit >= 90 ? "bg-red-500"
                 : today?.pct_of_limit >= 70 ? "bg-amber-500"
                 : "bg-emerald-500";

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Zap size={14} className="text-violet-400" />
          Anthropic API Usage
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

        {/* ── Today's spend ── */}
        {today && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase text-muted-foreground tracking-wider">Today's Spend</span>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-bold font-mono ${today.alert ? "text-red-400" : "text-emerald-400"}`}>
                  ₹{today.today_inr.toFixed(0)}
                </span>
                <span className="text-[9px] font-mono text-muted-foreground">${today.today_usd.toFixed(3)}</span>
              </div>
            </div>

            {/* Progress bar vs threshold */}
            <div className="space-y-1">
              <Bar value={today.today_usd} max={today.threshold_usd} color={pctColor} />
              <div className="flex justify-between text-[9px] font-mono text-muted-foreground">
                <span>{today.pct_of_limit}% of daily limit</span>
                <span>Limit: ₹{today.threshold_inr} (${today.threshold_usd})</span>
              </div>
            </div>

            {/* Hourly sparkline */}
            <div>
              <p className="text-[9px] font-mono text-muted-foreground mb-1 uppercase tracking-wider">Hourly (UTC)</p>
              <SparkLine hourly={today.hourly} />
            </div>
          </div>
        )}

        {/* ── 7-day history ── */}
        {daily.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">7-Day History</p>
            {daily.map(d => <DayBar key={d.date} day={d} maxCost={maxDailyCost} />)}
          </div>
        )}

        {daily.length === 0 && !today?.hourly?.length && (
          <p className="text-[10px] font-mono text-muted-foreground text-center py-2">
            No usage data yet — data accumulates as the AI pipeline runs.
          </p>
        )}

        {/* ── Threshold editor ── */}
        <div className="border-t border-border pt-3">
          {editingThr ? (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-muted-foreground shrink-0">Alert at $</span>
              <Input
                type="number" value={newThr} onChange={e => setNewThr(e.target.value)}
                className="rounded-none text-xs h-7 w-20 font-mono"
                placeholder={String(threshold)} min={0.5} step={0.5}
              />
              <Button size="sm" onClick={saveThreshold} className="rounded-none h-7 text-[10px] uppercase">Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditingThr(false)} className="rounded-none h-7 text-[10px]">Cancel</Button>
            </div>
          ) : (
            <button
              onClick={() => { setNewThr(String(threshold)); setEditingThr(true); }}
              className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground/50 hover:text-muted-foreground transition-colors"
            >
              <Settings2 size={10} />
              Alert threshold: ${threshold}/day (₹{(threshold * 84).toFixed(0)})
            </button>
          )}
        </div>

        {/* ── Alternative recommendation ── */}
        <div className="border border-amber-500/20 bg-amber-500/5 p-2.5 space-y-1.5">
          <p className="text-[9px] font-mono text-amber-400 uppercase tracking-wider font-semibold flex items-center gap-1">
            <TrendingUp size={9} /> Cheaper Alternatives
          </p>
          <div className="space-y-1 text-[9px] font-mono text-muted-foreground">
            <div className="flex justify-between">
              <span className="text-emerald-400 font-semibold">Google Gemini 2.0 Flash ★ Best</span>
              <span>$0.10 / $0.40 per MTok</span>
            </div>
            <div className="text-muted-foreground/60 pl-2">8× cheaper on input, 10× cheaper on output. Comparable quality for structured classification. Switch via Google AI SDK.</div>
            <div className="flex justify-between mt-1">
              <span>Gemini 1.5 Flash-8B</span>
              <span>$0.037 / $0.15 per MTok</span>
            </div>
            <div className="text-muted-foreground/60 pl-2">21× cheaper. Best for high-volume, simpler classification tasks.</div>
            <div className="flex justify-between mt-1">
              <span>OpenAI GPT-4o-mini</span>
              <span>$0.15 / $0.60 per MTok</span>
            </div>
            <div className="text-muted-foreground/60 pl-2">5× cheaper than Haiku. Solid JSON output reliability.</div>
            <div className="mt-1.5 text-amber-300/70">
              Current: claude-haiku-3 @ $0.25 / $1.25 per MTok (switched from haiku-4-5)
            </div>
          </div>
        </div>

      </CardContent>
    </Card>
  );
}
