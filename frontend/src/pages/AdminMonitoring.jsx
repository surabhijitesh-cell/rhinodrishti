/**
 * AdminMonitoring — /admin route, admin-only.
 *
 * Two-column layout:
 *  Left:  API Spend (multi-provider, live cost + alerts)
 *  Right: Filter Cascade (funnel stats, health, savings)
 */

import { useAuth } from "../contexts/AuthContext";
import { Navigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import ApiUsageWidget from "../components/ApiUsageWidget";
import FilterCascadeWidget from "../components/FilterCascadeWidget";
import FilterThresholdSimulator from "../components/FilterThresholdSimulator";
import {
  Shield, Database, Trash2, AlertTriangle, Radio, Zap, Activity, Settings,
  BarChart3, Loader2, RefreshCw, ExternalLink, Globe, Youtube,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { timeAgo } from "../lib/time";
import LoadError from "../components/LoadError";
import ConfirmAction from "../components/ConfirmAction";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "../components/ui/alert-dialog";

function PipelineStatusCard({ api }) {
  const [status, setStatus] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const res = await axios.get(`${api}/pipeline/status`);
      setStatus(res.data);
    } catch (e) {
      setFailed(true);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  return (
    <Card className="border border-border rounded-none bg-card" data-testid="pipeline-info-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Settings size={16} className="text-primary" />
          Pipeline Status
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {failed && <LoadError what="the pipeline status" onRetry={load} />}
        {!failed && !status && (
          <div className="h-24 flex items-center justify-center">
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          </div>
        )}
        {!failed && status && (
          <>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                ["Total Items", status.total_items],
                ["AI Processed", status.ai_processed],
                ["Processing Rate", status.processing_rate],
                ["RSS Sources", status.rss_sources],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">{label}</p>
                  <p className="font-bold font-['Barlow_Condensed'] text-lg">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-2 border-t border-border">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Scheduler</p>
              <p className="text-[10px] font-mono mt-0.5 text-muted-foreground">{status.scheduler}</p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Source Effectiveness ─────────────────────────────────────────────────────

const SOURCE_META = {
  youtube:   { label: "YouTube",   Icon: Youtube,       accent: "text-red-400",     border: "border-l-red-500",     bg: "bg-red-500/10",   dot: "bg-red-400"   },
  telegram:  { label: "Telegram",  Icon: Radio,         accent: "text-sky-400",     border: "border-l-sky-500",     bg: "bg-sky-500/10",   dot: "bg-sky-400"   },
};

const SEV_COLOR = {
  critical: "bg-red-500",
  high:     "bg-orange-500",
  medium:   "bg-yellow-500",
  low:      "bg-emerald-500",
};

const timeAgoShort = (iso) => timeAgo(iso) || "—";

function SevBar({ severity }) {
  const total = (severity.critical + severity.high + severity.medium + severity.low) || 1;
  const segs = ["critical", "high", "medium", "low"];
  return (
    <div className="flex h-1.5 w-full rounded-full overflow-hidden gap-px">
      {segs.map(s => severity[s] > 0 && (
        <div
          key={s}
          title={`${s}: ${severity[s]}`}
          className={`${SEV_COLOR[s]} transition-all`}
          style={{ width: `${(severity[s] / total) * 100}%` }}
        />
      ))}
      {total === 1 && <div className="bg-muted/30 flex-1 rounded-full" />}
    </div>
  );
}

function SourceEffectivenessCard({ api }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(null); // source_type of expanded row

  const fetchData = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const res = await axios.get(`${api}/intelligence/source-stats`);
      setData(res.data);
    } catch (e) {
      setFailed(true);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <BarChart3 size={16} className="text-violet-400" /> Source Effectiveness
        </CardTitle>
      </CardHeader>
      <CardContent className="p-8 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-muted-foreground" />
      </CardContent>
    </Card>
  );

  if (failed) return (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <BarChart3 size={16} className="text-violet-400" /> Source Effectiveness
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4"><LoadError what="source effectiveness" onRetry={fetchData} /></CardContent>
    </Card>
  );

  const { sources = [], recent_catches = [], retention_days = 30 } = data || {};
  const totalNonRss = sources.reduce((s, x) => s + x.total, 0);

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500" data-tour="source-effectiveness">
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <BarChart3 size={16} className="text-violet-400" />
          Source Effectiveness
          <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-violet-500/20 text-violet-400 border-violet-500/30 ml-1">
            {totalNonRss} items · last {retention_days}d
          </Badge>
        </CardTitle>
        <Button variant="outline" size="sm" className="rounded-none text-[10px] h-6 px-2 uppercase" onClick={fetchData}>
          <RefreshCw size={11} className="mr-1" /> Refresh
        </Button>
      </CardHeader>

      <CardContent className="p-4 space-y-4">
        <p className="text-xs text-muted-foreground">
          Intelligence items collected from non-RSS sources in the last {retention_days} days.
          Click a row to preview the latest catch from that source.
        </p>

        {/* Per-source rows */}
        <div className="divide-y divide-border border border-border">
          {sources.map(src => {
            const meta = SOURCE_META[src.source_type] || { label: src.source_type, Icon: Globe, accent: "text-muted-foreground", border: "", bg: "bg-muted/10", dot: "bg-muted-foreground" };
            const { Icon } = meta;
            const total          = src.raw_fetched ?? src.total;
            const pipelineIn     = src.total;          // entered intelligence_items
            const accepted       = src.accepted ?? 0;
            const rejected       = src.rejected ?? 0;
            const pctAccepted    = pipelineIn > 0 ? Math.round((accepted / pipelineIn) * 100) : 0;
            const pctRejected    = pipelineIn > 0 ? Math.round((rejected / pipelineIn) * 100) : 0;
            const isOpen         = expanded === src.source_type;
            const highValue      = src.severity.critical + src.severity.high;

            return (
              <div key={src.source_type}>
                <button
                  onClick={() => setExpanded(isOpen ? null : src.source_type)}
                  className={`w-full text-left p-3 hover:bg-muted/5 transition-colors flex items-center gap-3 ${isOpen ? "bg-muted/5" : ""}`}
                >
                  {/* Icon + label */}
                  <div className={`w-7 h-7 rounded flex items-center justify-center shrink-0 ${meta.bg}`}>
                    <Icon size={14} className={meta.accent} />
                  </div>
                  <div className="w-24 shrink-0">
                    <p className={`text-xs font-bold font-['Barlow_Condensed'] uppercase tracking-wide ${meta.accent}`}>{meta.label}</p>
                    <p className="text-[9px] font-mono text-muted-foreground">{timeAgoShort(src.latest_at)}</p>
                  </div>

                  {/* Pipeline flow: Fetched → Pipeline → ✓ Accepted / ✗ Rejected */}
                  <div className="flex-1 min-w-0">
                    {total === 0 ? (
                      <p className="text-[9px] font-mono text-muted-foreground">no data yet</p>
                    ) : (
                      <>
                        {/* Arrow pipeline diagram */}
                        <div className="flex items-center gap-1 text-[9px] font-mono flex-wrap">
                          <span className="text-muted-foreground font-semibold">{total} fetched</span>
                          <span className="text-muted-foreground/40">→</span>
                          <span className="text-blue-400">{pipelineIn} AI pipeline</span>
                          <span className="text-muted-foreground/40">→</span>
                          <span className="text-emerald-400">{accepted} ✓</span>
                          <span className="text-muted-foreground/30 mx-0.5">|</span>
                          <span className="text-red-400/70">{rejected} ✗</span>
                        </div>
                        {/* Severity bar */}
                        <div className="mt-1">
                          <SevBar severity={src.severity} />
                        </div>
                        <div className="flex gap-2 text-[8px] font-mono mt-0.5">
                          {src.severity.critical > 0 && <span className="text-red-400">{src.severity.critical} crit</span>}
                          {src.severity.high > 0     && <span className="text-orange-400">{src.severity.high} high</span>}
                          {src.severity.medium > 0   && <span className="text-yellow-400">{src.severity.medium} med</span>}
                          {src.severity.low > 0      && <span className="text-emerald-400">{src.severity.low} low</span>}
                        </div>
                      </>
                    )}
                  </div>

                  {/* Accept % */}
                  <div className="w-20 shrink-0 text-right">
                    <p className={`text-sm font-bold font-['Barlow_Condensed'] ${pctAccepted >= 30 ? "text-emerald-400" : pipelineIn === 0 ? "text-muted-foreground" : "text-amber-400"}`}>
                      {pipelineIn === 0 ? "—" : `${pctAccepted}%`}
                    </p>
                    <p className="text-[8px] font-mono text-muted-foreground">accepted</p>
                    {rejected > 0 && (
                      <p className="text-[8px] font-mono text-red-400/70">{pctRejected}% rej.</p>
                    )}
                  </div>

                  {/* High-value badge */}
                  <div className="w-16 shrink-0 text-center">
                    {highValue > 0 ? (
                      <Badge className="rounded-none text-[8px] px-1 py-0 bg-red-500/15 text-red-400 border-red-500/30">
                        {highValue} ⚠
                      </Badge>
                    ) : (
                      <span className="text-[9px] font-mono text-muted-foreground/40">—</span>
                    )}
                  </div>

                  {/* Expand caret */}
                  <span className="text-muted-foreground/50 text-xs">{isOpen ? "▲" : "▼"}</span>
                </button>

                {/* Expanded: pipeline detail + latest catch */}
                {isOpen && (
                  <div className={`px-4 pb-3 pt-2 ${meta.bg} border-t border-border space-y-2`}>
                    {/* Pipeline breakdown */}
                    {pipelineIn > 0 && (
                      <div>
                        <p className="text-[9px] uppercase tracking-widest font-mono text-muted-foreground font-semibold mb-1">AI Pipeline Breakdown</p>
                        <div className="grid grid-cols-4 gap-2 text-center">
                          {[
                            { label: "Fetched",  val: total,      color: "text-foreground" },
                            { label: "→ AI In",  val: pipelineIn, color: "text-blue-400" },
                            { label: "✓ Accept", val: accepted,   color: "text-emerald-400" },
                            { label: "✗ Reject", val: rejected,   color: "text-red-400/70" },
                          ].map(({ label, val, color }) => (
                            <div key={label} className="bg-black/20 p-1.5 rounded-none border border-border/50">
                              <p className={`text-base font-bold font-['Barlow_Condensed'] ${color}`}>{val}</p>
                              <p className="text-[8px] font-mono text-muted-foreground uppercase">{label}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Latest catch */}
                    {src.latest_title ? (
                      <div className="space-y-0.5">
                        <p className="text-[9px] uppercase tracking-widest font-mono text-muted-foreground font-semibold">Latest Catch</p>
                        <div className="flex items-start gap-2">
                          <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${SEV_COLOR[src.latest_severity] || "bg-muted"}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium leading-tight line-clamp-2">{src.latest_title}</p>
                            <p className="text-[9px] font-mono text-muted-foreground">
                              {src.latest_severity?.toUpperCase()} · {timeAgoShort(src.latest_at)}
                            </p>
                          </div>
                          {src.latest_url && (
                            <a href={src.latest_url} target="_blank" rel="noreferrer"
                               className="text-muted-foreground/50 hover:text-primary transition-colors shrink-0 mt-0.5"
                               onClick={e => e.stopPropagation()}>
                              <ExternalLink size={11} />
                            </a>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="text-[10px] text-muted-foreground font-mono py-1">No items collected yet — fetch will populate this source.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Recent catches across all non-RSS sources */}
        {recent_catches.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-widest font-mono font-semibold text-muted-foreground mb-2">
              Recent Catches — All Sources
            </p>
            <div className="divide-y divide-border border border-border">
              {recent_catches.map((item, i) => {
                const m = SOURCE_META[item.source_type] || { label: item.source_type, dot: "bg-muted-foreground", accent: "text-muted-foreground" };
                return (
                  <div key={i} className="p-2.5 flex items-start gap-2.5 hover:bg-muted/5">
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${SEV_COLOR[item.severity] || "bg-muted"}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{item.title}</p>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        <span className={`text-[8px] uppercase font-mono font-bold ${m.accent}`}>{m.label}</span>
                        {item.source && <span className="text-[8px] font-mono text-muted-foreground truncate max-w-[120px]">{item.source}</span>}
                        {item.threat_category && <span className="text-[8px] font-mono text-muted-foreground/60">{item.threat_category}</span>}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <Badge className={`rounded-none text-[7px] px-1 py-0 ${
                        item.severity === "critical" ? "bg-red-500/15 text-red-400 border-red-500/30" :
                        item.severity === "high"     ? "bg-orange-500/15 text-orange-400 border-orange-500/30" :
                        item.severity === "medium"   ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" :
                        "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                      }`}>{item.severity}</Badge>
                      <p className="text-[8px] font-mono text-muted-foreground mt-0.5">{timeAgoShort(item.published_at)}</p>
                    </div>
                    {item.source_url && (
                      <a href={item.source_url} target="_blank" rel="noreferrer"
                         className="text-muted-foreground/40 hover:text-primary transition-colors shrink-0 mt-1">
                        <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {totalNonRss === 0 && !loading && (
          <div className="text-center py-6 text-muted-foreground text-sm">
            No intelligence yet from non-RSS sources. Trigger a fetch from the Dashboard scanners to populate.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CreditWarningBanner({ api }) {
  const [warning, setWarning] = useState(null);

  useEffect(() => {
    const check = () =>
      axios.get(`${api}/admin/openrouter-credit-warning`)
        .then(r => setWarning(r.data))
        .catch(() => {});
    check();
    const id = setInterval(check, 60_000);
    return () => clearInterval(id);
  }, [api]);

  if (!warning || warning.level === "ok") return null;

  const isCritical = warning.level === "critical";
  const remaining = warning.remaining_usd != null
    ? `$${warning.remaining_usd.toFixed(2)} remaining`
    : "credits exhausted";

  return (
    <div className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-semibold ${
      isCritical
        ? "bg-red-950/60 border-red-500/50 text-red-300"
        : "bg-amber-950/60 border-amber-500/50 text-amber-300"
    }`}>
      <AlertTriangle size={14} className="shrink-0" />
      <span>
        OpenRouter credits {isCritical ? "critical" : "low"} — {remaining}.{" "}
        <a
          href={warning.top_up_url}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2 hover:opacity-80"
        >
          Top up →
        </a>
      </span>
    </div>
  );
}

function StorageCleanupPanel({ api }) {
  const [stats, setStats] = useState(null);
  const [days, setDays] = useState(60);
  const [loading, setLoading] = useState(null); // "strip" | "delete" | null
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  // Confirmation step: { kind: "strip"|"delete", preview?: {...}, failed?: true }
  const [pending, setPending] = useState(null);
  const [typed, setTyped] = useState("");

  async function askConfirm(kind) {
    setTyped("");
    setPending({ kind });
    try {
      const r = await axios.get(`${api}/admin/storage/preview?older_than_days=${days}`);
      setPending({ kind, preview: r.data });
    } catch {
      setPending({ kind, failed: true });
    }
  }

  function confirmPending() {
    const kind = pending.kind;
    setPending(null);
    if (kind === "strip") runStrip(); else runDelete();
  }

  const refreshStats = () =>
    axios.get(`${api}/admin/storage/stats`).then(r => setStats(r.data)).catch(() => {});

  useEffect(() => { refreshStats(); }, [api]);

  async function runStrip() {
    setLoading("strip");
    setResult(null);
    setError(null);
    try {
      const r = await axios.post(`${api}/admin/storage/strip-raw-content`, { older_than_days: days });
      setResult({ type: "strip", ...r.data });
      await refreshStats();
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Strip failed");
    } finally {
      setLoading(null);
    }
  }

  async function runDelete() {
    setLoading("delete");
    setResult(null);
    setError(null);
    try {
      const r = await axios.post(`${api}/admin/storage/cleanup-articles`, { older_than_days: days });
      setResult({ type: "delete", ...r.data });
      await refreshStats();
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Cleanup failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Database size={14} className="text-amber-400" />
        <h2 className="text-sm font-semibold uppercase tracking-widest font-['Barlow_Condensed']">
          Storage Cleanup
        </h2>
        <span className="text-[10px] font-mono text-muted-foreground ml-auto">Flex — 5 GB included</span>
      </div>

      {/* Collection counts */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {Object.entries(stats.counts).map(([name, count]) => (
            <div key={name} className="bg-background rounded p-2 text-center">
              <div className="text-xs font-mono text-muted-foreground truncate">{name}</div>
              <div className="text-sm font-semibold font-mono mt-0.5">
                {typeof count === "number" ? count.toLocaleString() : count}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <label className="text-xs text-muted-foreground">Articles older than</label>
        <select
          value={days}
          onChange={e => setDays(Number(e.target.value))}
          className="text-xs bg-background border border-border rounded px-2 py-1 font-mono"
        >
          {[30, 45, 60, 90, 120].map(d => (
            <option key={d} value={d}>{d} days</option>
          ))}
        </select>

        <button
          onClick={() => askConfirm("strip")}
          disabled={!!loading}
          title="Remove raw body text — keeps source link + all AI analysis"
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold transition-colors"
        >
          <Database size={12} />
          {loading === "strip" ? "Stripping…" : "Strip Raw Content"}
        </button>

        <button
          onClick={() => askConfirm("delete")}
          disabled={!!loading}
          title="Permanently delete articles — cannot be undone"
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-semibold transition-colors"
        >
          <Trash2 size={12} />
          {loading === "delete" ? "Deleting…" : "Delete Articles"}
        </button>
      </div>

      <p className="text-[10px] font-mono text-muted-foreground">
        Strip Raw Content — removes body text, keeps source URL + AI analysis. Pipeline auto-strips articles &gt;45 days daily.
      </p>

      {result && (
        <div className="text-xs font-mono bg-green-950/40 border border-green-800/40 rounded p-2 text-green-300">
          {result.type === "strip"
            ? `✓ ${result.message}`
            : `✓ ${result.message} · cutoff: ${result.cutoff_date}`
          }
        </div>
      )}
      {error && (
        <div className="text-xs font-mono bg-red-950/40 border border-red-800/40 rounded p-2 text-red-300">
          ✗ {error}
        </div>
      )}

      <AlertDialog open={!!pending} onOpenChange={(o) => { if (!o) setPending(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pending?.kind === "delete" ? "Delete old articles?" : "Remove stored full text?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pending?.failed
                ? "Couldn't count the items — nothing was deleted"
                : !pending?.preview
                  ? "Counting items…"
                  : pending.kind === "delete"
                    ? `This will permanently delete ${pending.preview.articles_to_delete} items older than ${days} days (published before ${pending.preview.cutoff_date}). This cannot be undone.`
                    : `This will remove the stored full text from ${pending.preview.articles_to_strip} items older than ${days} days. Titles, summaries and analysis stay. This cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {pending?.preview && pending.kind === "delete" && (
            <input
              value={typed}
              onChange={e => setTyped(e.target.value)}
              placeholder="Type DELETE to confirm"
              className="text-sm bg-background border border-border rounded px-2 py-1.5 font-mono"
              data-testid="delete-confirm-input"
            />
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            {pending?.preview && (
              <AlertDialogAction
                onClick={confirmPending}
                disabled={pending.kind === "delete" && typed !== "DELETE"}
                className="bg-red-600 hover:bg-red-700 text-white disabled:opacity-30"
              >
                {pending.kind === "delete" ? "Delete" : "Remove text"}
              </AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SocialFetchPanel({ api }) {
  const [status, setStatus] = useState(null);
  const [switching, setSwitching] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [message, setMessage] = useState(null);

  const refresh = () =>
    axios.get(`${api}/social/apify/status`).then(r => setStatus(r.data)).catch(() => {});

  useEffect(() => { refresh(); }, [api]);

  async function setMode(mode) {
    if (!status || mode === status.mode) return;
    setSwitching(true);
    setMessage(null);
    try {
      await axios.put(`${api}/social/apify/mode`, { mode });
      await refresh();
      setMessage({ type: "ok", text: `Switched to ${mode === "firehose" ? "Firehose" : "Throttled"} mode.` });
    } catch (e) {
      setMessage({ type: "error", text: e?.response?.data?.detail || e.message || "Failed to switch mode" });
    } finally {
      setSwitching(false);
    }
  }

  async function fetchNow() {
    setFetching(true);
    setMessage(null);
    try {
      const r = await axios.post(`${api}/social/apify/fetch-now`);
      setMessage({ type: "ok", text: r.data.message });
      setTimeout(refresh, 4000);
    } catch (e) {
      setMessage({ type: "error", text: e?.response?.data?.detail || e.message || "Fetch failed to start" });
    } finally {
      setFetching(false);
    }
  }

  const isFirehose = status?.mode === "firehose";

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Radio size={14} className="text-violet-400" />
        <h2 className="text-sm font-semibold uppercase tracking-widest font-['Barlow_Condensed']">
          Social Media Scraping (Instagram / Facebook)
        </h2>
        {status && !status.configured && (
          <span className="text-[10px] font-mono text-amber-400 ml-auto">APIFY_TOKEN not set</span>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground -mt-2">
        Twitter/X paused — the scraping actor blocks free-plan API access. Revisit if a paid plan is worth it later.
      </p>

      {status?.total_counts && (
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(status.total_counts).map(([platform, count]) => (
            <div key={platform} className="bg-background rounded p-2 text-center">
              <div className="text-xs font-mono text-muted-foreground capitalize">{platform}</div>
              <div className="text-sm font-semibold font-mono mt-0.5">{count.toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}

      {/* Throttled / Firehose toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <label className="text-xs text-muted-foreground">Volume mode</label>
        <div className="inline-flex rounded border border-border overflow-hidden">
          <button
            onClick={() => setMode("throttled")}
            disabled={switching || !status}
            className={`text-xs px-3 py-1.5 font-semibold transition-colors ${
              !isFirehose ? "bg-violet-600 text-white" : "bg-background text-muted-foreground hover:text-foreground"
            }`}
          >
            Throttled
          </button>
          <ConfirmAction when={!isFirehose} title="Switch to Firehose mode?" description="This starts paid scraping on Apify (a few cents per run). Continue?" onConfirm={() => setMode("firehose")}>
          <button
            disabled={switching || !status}
            className={`text-xs px-3 py-1.5 font-semibold transition-colors ${
              isFirehose ? "bg-red-600 text-white" : "bg-background text-muted-foreground hover:text-foreground"
            }`}
          >
            Firehose
          </button>
          </ConfirmAction>
        </div>

        <ConfirmAction title="Fetch now?" description="This starts paid scraping on Apify (a few cents per run). Continue?" confirmLabel="Fetch now" onConfirm={fetchNow}>
        <button
          disabled={fetching || !status?.configured}
          title={!status?.configured ? "Set APIFY_TOKEN first" : "Fetch immediately, bypassing the schedule"}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-semibold transition-colors ml-auto"
        >
          <Zap size={12} />
          {fetching ? "Starting…" : "Fetch Now"}
        </button>
        </ConfirmAction>
      </div>

      <p className="text-[10px] font-mono text-muted-foreground">
        Throttled — ~50 posts/platform, every ~3.5 days (fits Apify's $5 free monthly credit, ~$0 cost).{" "}
        Firehose — ~100 posts/platform daily (~$11/month). Last run:{" "}
        {status?.last_run ? new Date(status.last_run).toLocaleString("en-IN") : "never"}
        {status?.last_run_counts && (
          <> · {Object.entries(status.last_run_counts).map(([p, c]) => `${p}: ${c}`).join(", ")}</>
        )}
      </p>

      {message && (
        <div className={`text-xs font-mono rounded p-2 ${
          message.type === "ok"
            ? "bg-green-950/40 border border-green-800/40 text-green-300"
            : "bg-red-950/40 border border-red-800/40 text-red-300"
        }`}>
          {message.type === "ok" ? "✓" : "✗"} {message.text}
        </div>
      )}
    </div>
  );
}

const HEALTH_BADGES = {
  ok:      { label: "OK",      cls: "bg-green-950/40 border-green-800/40 text-green-300" },
  silent:  { label: "Silent",  cls: "bg-amber-950/40 border-amber-800/40 text-amber-300" },
  failing: { label: "Failing", cls: "bg-red-950/40 border-red-800/40 text-red-300" },
  never:   { label: "No data", cls: "bg-muted border-border text-muted-foreground" },
};

function hoursAgo(iso) {
  if (!iso) return "never";
  const h = (Date.now() - new Date(iso).getTime()) / 3600000;
  if (Number.isNaN(h)) return "never";
  if (h < 1) return "under 1 h ago";
  if (h < 48) return `${Math.round(h)} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

function SourceHealthPanel({ api }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setFailed(false);
    axios.get(`${api}/admin/source-health`)
      .then(r => setData(r.data))
      .catch(() => setFailed(true));
  };

  useEffect(() => { load(); }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  const sources = data?.sources || [];
  const attention = data?.needs_attention ?? 0;

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3" data-testid="source-health-panel">
      <div className="flex items-center gap-2">
        <Activity size={14} className="text-violet-400" />
        <h2 className="text-sm font-semibold uppercase tracking-widest font-['Barlow_Condensed']">
          Source health
        </h2>
        {data && (
          <span className={`text-[10px] font-mono ml-auto ${attention ? "text-amber-400" : "text-green-400"}`}>
            {attention === 0
              ? "All sources reporting"
              : `${attention} source${attention === 1 ? "" : "s"} need${attention === 1 ? "s" : ""} attention`}
          </span>
        )}
      </div>

      {failed && <LoadError what="source health" onRetry={load} />}

      {!failed && data && sources.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No source has reported yet. Entries appear after the next fetch cycle.
        </p>
      )}

      {!failed && sources.length > 0 && (
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase text-muted-foreground">
                <th className="py-1 pr-2">Status</th>
                <th className="py-1 pr-2">Source</th>
                <th className="py-1 pr-2">Type</th>
                <th className="py-1 pr-2">Last success</th>
                <th className="py-1 pr-2">Last error</th>
                <th className="py-1 text-right">Items last run</th>
              </tr>
            </thead>
            <tbody>
              {sources.map(s => {
                const badge = HEALTH_BADGES[s.status] || HEALTH_BADGES.never;
                return (
                  <tr key={`${s.kind}:${s.name}`} className="border-t border-border/50">
                    <td className="py-1 pr-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-mono ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="py-1 pr-2 font-medium">{s.name}</td>
                    <td className="py-1 pr-2 text-muted-foreground capitalize">{s.kind}</td>
                    <td className="py-1 pr-2 font-mono text-muted-foreground">{hoursAgo(s.last_success)}</td>
                    <td className="py-1 pr-2 text-muted-foreground max-w-[16rem] truncate" title={s.last_error || ""}>
                      {s.last_error ? s.last_error.slice(0, 60) : "—"}
                    </td>
                    <td className="py-1 text-right font-mono">{s.last_items ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TitleList({ titles }) {
  if (!titles?.length) return null;
  return (
    <ul className="list-disc pl-5 text-[11px] text-muted-foreground space-y-0.5">
      {titles.map((t, i) => <li key={i}>{t}</li>)}
    </ul>
  );
}

function ModelTrialPanel({ api }) {
  const [trial, setTrial] = useState(null);
  const [routing, setRouting] = useState(null);
  const [failed, setFailed] = useState(false);
  const [starting, setStarting] = useState(false);

  const load = () => {
    setFailed(false);
    Promise.all([
      axios.get(`${api}/admin/model-trial/latest`),
      axios.get(`${api}/admin/model-routing`),
    ]).then(([t, r]) => { setTrial(t.data); setRouting(r.data); })
      .catch(() => setFailed(true));
  };

  useEffect(() => { load(); }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  const running = trial?.status === "running";
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [running, api]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setStarting(true);
    try {
      await axios.post(`${api}/admin/model-trial`, { n: 300 });
      load();
    } catch (e) {
      setFailed(true);
    }
    setStarting(false);
  };

  const sum = trial?.status === "done" ? trial.summary : null;
  const s1 = sum?.stage1;
  const fp = sum?.first_pass;
  const onOff = v => (v ? "On" : "Off");

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3" data-testid="model-trial-panel">
      <div className="flex items-center gap-2">
        <Zap size={14} className="text-violet-400" />
        <h2 className="text-sm font-semibold uppercase tracking-widest font-['Barlow_Condensed']">Model trial</h2>
        <div className="ml-auto">
          <ConfirmAction
            title="Run model trial?"
            description="Re-scores about 300 stored items with the cheaper models to compare. Costs about $0.20–$0.50 once. Nothing in the feed changes."
            confirmLabel="Run trial"
            onConfirm={start}
          >
            <button
              disabled={running || starting}
              className="text-[10px] font-mono uppercase border border-border px-2 py-1 hover:bg-accent disabled:opacity-50"
              data-testid="run-model-trial"
            >
              {running ? "Running…" : "Run model trial"}
            </button>
          </ConfirmAction>
        </div>
      </div>

      {failed && <LoadError what="the model trial" onRetry={load} />}

      {!failed && routing && (
        <p className="text-[11px] text-muted-foreground font-mono">
          Cheap pre-filter on news: {onOff(routing.stage1_on_news)} · Two-step scoring: {onOff(routing.two_step_scoring)}
        </p>
      )}

      {!failed && trial?.status === "none" && (
        <p className="text-xs text-muted-foreground">No trial has been run yet.</p>
      )}
      {!failed && running && (
        <p className="text-xs text-amber-400">
          Running: {trial.done_count ?? 0} of {trial.n} items checked. Updates every 10 seconds.
        </p>
      )}
      {!failed && trial?.status === "failed" && (
        <p className="text-xs text-red-400">The last trial failed{trial.error ? `: ${trial.error}` : ""}. You can run it again.</p>
      )}

      {!failed && sum && (
        <div className="space-y-3 text-xs">
          <p>
            Checked {sum.scored} items. Estimated cost of the trial: ${sum.estimated_cost_usd}.
          </p>
          <div className="space-y-1">
            <p>
              Pre-filter would drop {s1.would_reject} items, of which {s1.of_which_critical_high} were Critical/High
              {s1.examples.length ? ":" : "."}
            </p>
            <TitleList titles={s1.examples} />
            {s1.filter_failed > 0 && (
              <p className="text-amber-400">
                Warning: the pre-filter failed on {s1.filter_failed} items (it keeps items when it fails), so its result above is not reliable.
              </p>
            )}
          </div>
          <div className="space-y-1">
            <p>
              Cheaper first pass would keep {fp.critical_high_kept_pct ?? "—"}% of Critical/High above the cut-off
              {fp.missed_examples.length ? "; these would be missed:" : "."}
            </p>
            <TitleList titles={fp.missed_examples} />
            <p className="text-muted-foreground">
              About {fp.share_to_full_model_pct ?? "—"}% of items would still go to the full model.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminMonitoring({ api }) {
  const { user } = useAuth();

  if (user?.role !== "admin") {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="p-4 md:p-6 space-y-4 max-w-7xl mx-auto">

      {/* ── Header ── */}
      <div className="flex items-center gap-3 border-b border-border pb-4">
        <Shield size={18} className="text-violet-400" />
        <div>
          <h1 className="text-base font-semibold uppercase tracking-widest font-['Barlow_Condensed']">
            Admin Monitoring
          </h1>
          <p className="text-[10px] font-mono text-muted-foreground">
            API spend, filters, pipeline and source health — visible to admin only
          </p>
        </div>
      </div>

      {/* ── Credit Warning ── */}
      <CreditWarningBanner api={api} />

      {/* ── Storage Cleanup ── */}
      <StorageCleanupPanel api={api} />

      {/* ── Social Media Scraping (Instagram / Facebook / Twitter) ── */}
      <SocialFetchPanel api={api} />

      {/* ── Source health ── */}
      <SourceHealthPanel api={api} />

      <ModelTrialPanel api={api} />

      {/* ── Pipeline status + source effectiveness ── */}
      <PipelineStatusCard api={api} />
      <SourceEffectivenessCard api={api} />

      {/* ── Two-column panels ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ApiUsageWidget api={api} />
        <FilterCascadeWidget api={api} />
      </div>

      {/* ── Filter Threshold Simulator ── */}
      <FilterThresholdSimulator api={api} />

    </div>
  );
}
