import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Target, AlertTriangle, TrendingUp, TrendingDown, Minus,
  Activity, RefreshCw, ChevronRight, Filter, MapPin, Network,
} from "lucide-react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  LineChart, Line, ResponsiveContainer, Tooltip,
} from "recharts";

const LEVEL_STYLE = {
  CRITICAL: { color: "#ef4444", bg: "bg-red-950/25",     border: "border-red-500/40",    text: "text-red-400" },
  ELEVATED: { color: "#f59e0b", bg: "bg-orange-950/25",  border: "border-orange-500/40", text: "text-orange-400" },
  MONITOR:  { color: "#eab308", bg: "bg-yellow-950/15",  border: "border-yellow-500/30", text: "text-yellow-400" },
  STABLE:   { color: "#a3e635", bg: "bg-green-950/10",   border: "border-green-500/30",  text: "text-green-400" },
};

const tooltipStyle = {
  background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)",
  borderRadius: 0, fontSize: 11,
};

function TrendArrow({ delta }) {
  if (delta == null) return <Minus size={12} className="text-muted-foreground" />;
  if (delta > 2)  return <TrendingUp size={12} className="text-red-400" />;
  if (delta < -2) return <TrendingDown size={12} className="text-green-400" />;
  return <Minus size={12} className="text-muted-foreground" />;
}

function FaultlineCard({ fl, sparkData, delta7d, onClick }) {
  const level = fl.latest_score?.level || "STABLE";
  const style = LEVEL_STYLE[level] || LEVEL_STYLE.STABLE;
  const score = fl.latest_score?.score ?? 0;
  const n = fl.latest_score?.n_articles ?? 0;

  return (
    <div
      className={`border ${style.border} ${style.bg} p-4 cursor-pointer hover:opacity-95 transition-opacity`}
      onClick={onClick}
      data-testid={`faultline-card-${fl.id}`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
            {fl.state}
          </p>
          <h3 className="text-sm font-semibold leading-tight mt-0.5 line-clamp-2">
            {fl.name}
          </h3>
        </div>
        <Badge className={`shrink-0 rounded-none text-[10px] px-1.5 py-0 ${style.text} border ${style.border}`}>
          {level}
        </Badge>
      </div>

      <div className="flex items-end justify-between gap-2 mb-2">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold font-['Barlow_Condensed']" style={{ color: style.color }}>
            {Math.round(score)}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">/100</span>
        </div>
        <div className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
          <TrendArrow delta={delta7d} />
          {delta7d != null && (
            <span className={delta7d > 0 ? "text-red-400" : delta7d < 0 ? "text-green-400" : ""}>
              {delta7d > 0 ? "+" : ""}{delta7d.toFixed(0)}
            </span>
          )}
          <span>7d</span>
        </div>
      </div>

      {/* Sparkline */}
      <div className="h-10 -mx-1">
        {sparkData && sparkData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparkData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(v) => [v?.toFixed?.(1) ?? v, "score"]}
                labelFormatter={(d) => d}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke={style.color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-[10px] text-muted-foreground font-mono">
            no history yet
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground font-mono">
        <span>{n} articles</span>
        {fl.active_alert && (
          <span className="flex items-center gap-1 text-orange-400">
            <AlertTriangle size={10} /> alert
          </span>
        )}
      </div>
    </div>
  );
}

export default function FaultlineIntelligence({ api }) {
  const navigate = useNavigate();
  const [faultlines, setFaultlines] = useState([]);
  const [historyByFl, setHistoryByFl] = useState({});
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [running, setRunning] = useState(false);
  const [stateFilter, setStateFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [sortBy, setSortBy] = useState("score_desc");
  const [tab, setTab] = useState("list");

  const fetchFaultlines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/faultlines?include_score=true`);
      setFaultlines(res.data.faultlines || []);
    } catch (e) {
      console.error("Failed to load faultlines", e);
      setFaultlines([]);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchFaultlines(); }, [fetchFaultlines]);

  // Stable signature: comma-joined sorted faultline IDs. Re-runs only when the
  // SET of faultlines changes, not on every refresh that returns the same set
  // (which would otherwise refetch 66 × 7-day history on every poll).
  const faultlineIdsSig = useMemo(
    () => faultlines.map((f) => f.id).sort().join(","),
    [faultlines]
  );

  // Lazily fetch 7-day history per faultline for sparkline (one call per fl, batched)
  useEffect(() => {
    if (!faultlineIdsSig) return;
    const ids = faultlineIdsSig.split(",").filter(Boolean);
    if (!ids.length) return;
    let cancelled = false;
    const load = async () => {
      const out = {};
      // Throttle: 6 at a time
      const chunks = [];
      for (let i = 0; i < ids.length; i += 6) {
        chunks.push(ids.slice(i, i + 6));
      }
      for (const chunk of chunks) {
        if (cancelled) return;
        const results = await Promise.all(
          chunk.map((flId) =>
            axios.get(`${api}/faultlines/${flId}/history?days=7`)
              .then((r) => [flId, r.data.series || []])
              .catch(() => [flId, []])
          )
        );
        results.forEach(([flId, series]) => { out[flId] = series; });
        if (!cancelled) setHistoryByFl((prev) => ({ ...prev, ...out }));
      }
    };
    load();
    return () => { cancelled = true; };
  }, [api, faultlineIdsSig]);

  const states = useMemo(() => {
    const set = new Set(faultlines.map((f) => f.state).filter(Boolean));
    return Array.from(set).sort();
  }, [faultlines]);

  const decorated = useMemo(() => {
    return faultlines.map((fl) => {
      const history = historyByFl[fl.id] || [];
      const sparkData = history.map((p) => ({ date: p.date, score: p.score }));
      const delta7d = history.length >= 2
        ? history[history.length - 1].score - history[0].score
        : null;
      return { ...fl, sparkData, delta7d };
    });
  }, [faultlines, historyByFl]);

  const filtered = useMemo(() => {
    let out = decorated;
    if (stateFilter !== "all") out = out.filter((f) => f.state === stateFilter);
    if (levelFilter !== "all") out = out.filter((f) => (f.latest_score?.level || "STABLE") === levelFilter);
    out = [...out].sort((a, b) => {
      const sa = a.latest_score?.score ?? 0;
      const sb = b.latest_score?.score ?? 0;
      if (sortBy === "score_desc") return sb - sa;
      if (sortBy === "score_asc")  return sa - sb;
      if (sortBy === "state")      return (a.state || "").localeCompare(b.state || "");
      if (sortBy === "delta")      return (b.delta7d ?? -Infinity) - (a.delta7d ?? -Infinity);
      return 0;
    });
    return out;
  }, [decorated, stateFilter, levelFilter, sortBy]);

  const summary = useMemo(() => {
    const counts = { CRITICAL: 0, ELEVATED: 0, MONITOR: 0, STABLE: 0 };
    decorated.forEach((f) => {
      const lvl = f.latest_score?.level || "STABLE";
      counts[lvl] = (counts[lvl] || 0) + 1;
    });
    return counts;
  }, [decorated]);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await axios.post(`${api}/faultlines/seed`);
      await fetchFaultlines();
    } catch (e) { console.error(e); }
    setSeeding(false);
  };

  const handleRunDaily = async () => {
    setRunning(true);
    try {
      await axios.post(`${api}/faultlines/run-daily`);
      // Poll-refresh after 5s grace
      setTimeout(() => { fetchFaultlines(); setRunning(false); }, 5000);
    } catch (e) { console.error(e); setRunning(false); }
  };

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Target size={20} className="text-primary" />
            Faultline Intelligence
          </h1>
          <p className="text-xs text-muted-foreground font-mono">
            Continuous stress monitoring across regional fault lines
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline" size="sm"
            className="rounded-none text-xs"
            onClick={fetchFaultlines}
            disabled={loading}
            data-testid="refresh-btn"
          >
            <RefreshCw size={12} className={`mr-1 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            variant="outline" size="sm"
            className="rounded-none text-xs"
            onClick={handleRunDaily}
            disabled={running}
            data-testid="run-daily-btn"
          >
            <Activity size={12} className="mr-1" />
            {running ? "Running…" : "Run scoring now"}
          </Button>
          {faultlines.length === 0 && (
            <Button
              variant="default" size="sm"
              className="rounded-none text-xs"
              onClick={handleSeed}
              disabled={seeding}
              data-testid="seed-btn"
            >
              {seeding ? "Seeding…" : "Seed faultlines"}
            </Button>
          )}
        </div>
      </div>

      {/* Level summary strip */}
      <div className="grid grid-cols-4 gap-2">
        {Object.entries(LEVEL_STYLE).map(([lvl, style]) => (
          <div
            key={lvl}
            className={`border ${style.border} ${style.bg} p-3 cursor-pointer`}
            onClick={() => setLevelFilter(levelFilter === lvl ? "all" : lvl)}
            data-testid={`level-summary-${lvl}`}
          >
            <p className={`text-[10px] uppercase tracking-wider font-mono ${style.text}`}>
              {lvl}
            </p>
            <p className="text-2xl font-bold font-['Barlow_Condensed']" style={{ color: style.color }}>
              {summary[lvl] || 0}
            </p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {["list", "cross-impact"].map((t) => (
          <button
            key={t}
            className={`px-3 py-1.5 text-xs uppercase tracking-wider font-mono border-b-2 ${
              tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground"
            }`}
            onClick={() => setTab(t)}
            data-testid={`tab-${t}`}
          >
            {t === "list" ? "All Faultlines" : "Cross-Impact"}
          </button>
        ))}
      </div>

      {/* Filters */}
      {tab === "list" && (
        <div className="flex gap-2 flex-wrap items-center">
          <Filter size={12} className="text-muted-foreground" />
          <Select value={stateFilter} onValueChange={setStateFilter}>
            <SelectTrigger className="w-40 h-8 rounded-none text-xs" data-testid="state-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All states</SelectItem>
              {states.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-44 h-8 rounded-none text-xs" data-testid="sort-by">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="score_desc">Score (high → low)</SelectItem>
              <SelectItem value="score_asc">Score (low → high)</SelectItem>
              <SelectItem value="delta">Δ 7d (rising first)</SelectItem>
              <SelectItem value="state">State (A → Z)</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-[10px] text-muted-foreground font-mono ml-auto">
            {filtered.length} of {faultlines.length} shown
          </span>
        </div>
      )}

      {/* List tab */}
      {tab === "list" && (
        <>
          {loading ? (
            <p className="text-sm text-muted-foreground font-mono">Loading faultlines…</p>
          ) : filtered.length === 0 ? (
            <Card className="border border-border rounded-none p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No faultlines found. {faultlines.length === 0 && "Click 'Seed faultlines' to initialize the registry."}
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filtered.map((fl) => (
                <FaultlineCard
                  key={fl.id}
                  fl={fl}
                  sparkData={fl.sparkData}
                  delta7d={fl.delta7d}
                  onClick={() => navigate(`/faultlines/${fl.id}`)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Cross-impact tab */}
      {tab === "cross-impact" && (
        <Card className="border border-border rounded-none">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm flex items-center gap-2">
              <Network size={14} /> Cross-Faultline Influence Graph
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-mono mb-3">
              Faultlines that influence each other through the propagation graph. Higher weight = stronger cross-impact.
            </p>
            <div className="space-y-2">
              {decorated
                .filter((f) => (f.linked_faultlines || []).length > 0)
                .sort((a, b) => (b.latest_score?.score ?? 0) - (a.latest_score?.score ?? 0))
                .map((fl) => (
                  <div key={fl.id} className="border border-border p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                          {fl.state}
                        </span>
                        <p className="text-sm font-medium">{fl.name}</p>
                      </div>
                      <Badge className="rounded-none text-[10px]">
                        {Math.round(fl.latest_score?.score ?? 0)}
                      </Badge>
                    </div>
                    <div className="ml-3 space-y-1">
                      {fl.linked_faultlines.map((lf) => (
                        <div
                          key={lf.id}
                          className="flex items-center gap-2 text-xs font-mono cursor-pointer hover:text-primary"
                          onClick={() => navigate(`/faultlines/${lf.id}`)}
                        >
                          <ChevronRight size={10} />
                          <span className="text-muted-foreground">→</span>
                          <span className="flex-1">{lf.name || lf.id}</span>
                          {lf.state && (
                            <span className="text-muted-foreground">[{lf.state}]</span>
                          )}
                          <Badge variant="outline" className="rounded-none text-[10px] px-1 py-0">
                            w {lf.weight?.toFixed?.(1) ?? lf.weight}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
