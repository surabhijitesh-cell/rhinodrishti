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
import ApiUsageWidget from "../components/ApiUsageWidget";
import FilterCascadeWidget from "../components/FilterCascadeWidget";
import FilterThresholdSimulator from "../components/FilterThresholdSimulator";
import { Shield, Database, Trash2 } from "lucide-react";

function StorageCleanupPanel({ api }) {
  const [stats, setStats] = useState(null);
  const [days, setDays] = useState(60);
  const [loading, setLoading] = useState(null); // "strip" | "delete" | null
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const refreshStats = () =>
    api.get("/admin/storage/stats").then(r => setStats(r.data)).catch(() => {});

  useEffect(() => { refreshStats(); }, [api]);

  async function runStrip() {
    setLoading("strip");
    setResult(null);
    setError(null);
    try {
      const r = await api.post("/admin/storage/strip-raw-content", { older_than_days: days });
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
      const r = await api.post("/admin/storage/cleanup-articles", { older_than_days: days });
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

      {/* ── Storage Cleanup ── */}
      <StorageCleanupPanel api={api} />

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
