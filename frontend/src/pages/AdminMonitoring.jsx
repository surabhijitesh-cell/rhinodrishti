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
import { Shield, Database, Trash2, AlertTriangle, Radio, Zap } from "lucide-react";

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
          onClick={runStrip}
          disabled={!!loading}
          title="Remove raw body text — keeps source link + all AI analysis"
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold transition-colors"
        >
          <Database size={12} />
          {loading === "strip" ? "Stripping…" : "Strip Raw Content"}
        </button>

        <button
          onClick={runDelete}
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
            : `✓ ${result.message} · API usage logs deleted: ${result.api_usage_deleted} · cutoff: ${result.cutoff_date}`
          }
        </div>
      )}
      {error && (
        <div className="text-xs font-mono bg-red-950/40 border border-red-800/40 rounded p-2 text-red-300">
          ✗ {error}
        </div>
      )}
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
          Social Media Scraping (Instagram / Facebook / Twitter)
        </h2>
        {status && !status.configured && (
          <span className="text-[10px] font-mono text-amber-400 ml-auto">APIFY_TOKEN not set</span>
        )}
      </div>

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
          <button
            onClick={() => setMode("firehose")}
            disabled={switching || !status}
            className={`text-xs px-3 py-1.5 font-semibold transition-colors ${
              isFirehose ? "bg-red-600 text-white" : "bg-background text-muted-foreground hover:text-foreground"
            }`}
          >
            Firehose
          </button>
        </div>

        <button
          onClick={fetchNow}
          disabled={fetching || !status?.configured}
          title={!status?.configured ? "Set APIFY_TOKEN first" : "Fetch immediately, bypassing the schedule"}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-semibold transition-colors ml-auto"
        >
          <Zap size={12} />
          {fetching ? "Starting…" : "Fetch Now"}
        </button>
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
