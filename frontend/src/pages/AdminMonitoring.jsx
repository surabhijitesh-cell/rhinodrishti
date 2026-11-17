/**
 * AdminMonitoring — /admin route, admin-only.
 *
 * Two-column layout:
 *  Left:  API Spend (multi-provider, live cost + alerts)
 *  Right: Filter Cascade (funnel stats, health, savings)
 */

import { useAuth } from "../contexts/AuthContext";
import { Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import axios from "axios";
import ApiUsageWidget from "../components/ApiUsageWidget";
import FilterCascadeWidget from "../components/FilterCascadeWidget";
import FilterThresholdSimulator from "../components/FilterThresholdSimulator";
import { Shield, Database, Trash2, AlertTriangle, Radio, Zap, Activity } from "lucide-react";
import LoadError from "../components/LoadError";
import ConfirmAction from "../components/ConfirmAction";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "../components/ui/alert-dialog";

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
            API spend + filter cascade — visible to admin only
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
