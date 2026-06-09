import { useEffect, useState, useCallback } from "react";
import {
  Calendar, FileText, RefreshCw, Download, Copy, ChevronDown, ChevronUp,
  Shield, AlertTriangle, Users, MapPin, Phone, Activity, TrendingUp,
  Target, Layers, CheckCircle2, Clock, Globe,
} from "lucide-react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import Tip from "../components/Tip";
import { CommanderDashboard, PaoiDeepDives } from "../components/PaoiBriefSections";
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

const SEVERITY_COLORS = {
  critical: "#ef4444", high: "#f59e0b", medium: "#eab308", low: "#a3e635",
};
const CONCERN_COLOR = {
  CRITICAL: "#ef4444", ELEVATED: "#f59e0b", MONITOR: "#eab308", STABLE: "#a3e635",
};
const tooltipStyle = {
  background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)",
  borderRadius: 0, fontSize: 11,
};

function renderLabeledText(text) {
  if (!text) return null;
  const str = typeof text === "string" ? text : String(text);
  const parts = str.split(/(\[(?:CONFIRMED|ASSESSED|SPECULATIVE)\])/g);
  return parts.map((p, i) => {
    if (p === "[CONFIRMED]")   return <span key={i} className="inline-block text-[8px] font-mono px-1 py-px ml-0.5 mr-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/40 align-middle">CONFIRMED</span>;
    if (p === "[ASSESSED]")    return <span key={i} className="inline-block text-[8px] font-mono px-1 py-px ml-0.5 mr-0.5 bg-amber-500/15  text-amber-400  border border-amber-500/40  align-middle">ASSESSED</span>;
    if (p === "[SPECULATIVE]") return <span key={i} className="inline-block text-[8px] font-mono px-1 py-px ml-0.5 mr-0.5 bg-cyan-500/15   text-cyan-400   border border-cyan-500/40   align-middle">SPECULATIVE</span>;
    return <span key={i}>{p}</span>;
  });
}

function defaultPeriod() {
  const now = new Date();
  const day  = now.getDate();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  if (day <= 15) {
    // Currently in period 1 — most recently completed = period 2 of last month
    if (month === 1) return { year: year - 1, month: 12, period: 2 };
    return { year, month: month - 1, period: 2 };
  }
  // Currently in period 2 — most recently completed = period 1 of current month
  return { year, month, period: 1 };
}

function periodLabel(year, month, period) {
  const monthName = new Date(year, month - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
  const lastDay = new Date(year, month, 0).getDate();
  return period === 1 ? `1-15 ${monthName}` : `16-${lastDay} ${monthName}`;
}

export default function FortnightlyBrief({ api }) {
  const init = defaultPeriod();
  const [year,   setYear]   = useState(init.year);
  const [month,  setMonth]  = useState(init.month);
  const [period, setPeriod] = useState(init.period);
  const [brief,      setBrief]      = useState(null);
  const [prevBrief,  setPrevBrief]  = useState(null);
  const [history,    setHistory]    = useState([]);
  const [selPeriods, setSelPeriods] = useState(null);
  const [viewMode,   setViewMode]   = useState("minigraphs");
  const [loading,    setLoading]    = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error,      setError]      = useState(null);
  const [openStates, setOpenStates] = useState({});
  const [openMitig,  setOpenMitig]  = useState({});
  const [copied,     setCopied]     = useState(false);

  const label = periodLabel(year, month, period);
  // Previous period: P2 → P1 same month; P1 → P2 of previous month
  const prevPeriodYear  = period === 1 ? (month === 1 ? year - 1 : year) : year;
  const prevPeriodMonth = period === 1 ? (month === 1 ? 12 : month - 1) : month;
  const prevPeriodNum   = period === 1 ? 2 : 1;
  const prevLabel       = periodLabel(prevPeriodYear, prevPeriodMonth, prevPeriodNum);

  const fetchBrief = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const r = await axios.get(`${api}/brief/fortnightly/${year}/${month}/${period}`);
      setBrief(r.data);
      setGenerating(r.data.status === "generating");
    } catch (e) {
      if (e?.response?.status === 404) {
        setBrief(null);
      } else {
        setError(e?.response?.data?.detail || "Fetch failed");
      }
      setGenerating(false);
    }
    setLoading(false);
    // Fetch previous period brief silently
    try {
      const pr = await axios.get(`${api}/brief/fortnightly/${prevPeriodYear}/${prevPeriodMonth}/${prevPeriodNum}`);
      if (pr.data?.status === "ready" || pr.data?.status === "partial") {
        setPrevBrief(pr.data);
      } else {
        setPrevBrief(null);
      }
    } catch {
      setPrevBrief(null);
    }
    // Fetch full stability history
    try {
      const hr = await axios.get(`${api}/brief/fortnightly/stability-history`);
      setHistory(hr.data?.history || []);
    } catch {
      setHistory([]);
    }
  }, [api, year, month, period, prevPeriodYear, prevPeriodMonth, prevPeriodNum]);

  useEffect(() => { fetchBrief(); }, [fetchBrief]);

  useEffect(() => {
    if (!generating) return;
    const t = setInterval(fetchBrief, 8000);
    return () => clearInterval(t);
  }, [generating, fetchBrief]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await axios.post(`${api}/brief/fortnightly/generate?year=${year}&month=${month}&period=${period}`);
      setTimeout(fetchBrief, 4000);
    } catch (e) {
      setError(e?.response?.data?.detail || "Generation request failed");
      setGenerating(false);
    }
  };

  const handleCopyNotebookLM = async () => {
    try {
      const r = await axios.get(`${api}/brief/fortnightly/${year}/${month}/${period}/notebooklm`);
      await navigator.clipboard.writeText(r.data);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (e) {
      setError("Copy failed: " + (e?.message || ""));
    }
  };

  const handleDownloadPDF = () => {
    window.open(`${api}/brief/fortnightly/${year}/${month}/${period}/pdf`, "_blank");
  };

  const adjustPeriod = (delta) => {
    let p = period + delta;
    let m = month;
    let y = year;
    if (p < 1) { p = 2; m -= 1; }
    if (p > 2) { p = 1; m += 1; }
    if (m < 1)  { m = 12; y -= 1; }
    if (m > 12) { m = 1;  y += 1; }
    setPeriod(p); setMonth(m); setYear(y);
  };

  // ── Renderers ────────────────────────────────────────────────────────────────

  const renderHeader = () => (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="fortnightly-brief-title">
          Fortnightly Strategic Brief
        </h1>
        <div className="flex items-center gap-2 mt-1">
          <Calendar size={12} className="text-muted-foreground" />
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">{label}</p>
          {brief?.generated_at && (
            <>
              <span className="text-muted-foreground">|</span>
              <p className="text-xs font-mono text-muted-foreground">
                Generated: {new Date(brief.generated_at).toLocaleString("en-IN")}
              </p>
            </>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => adjustPeriod(-1)} className="px-2 py-1.5 border border-border text-xs font-mono hover:border-primary">&lt; Prev</button>
        <div className="text-xs font-mono uppercase tracking-wider min-w-[160px] text-center">{label}</div>
        <button onClick={() => adjustPeriod(1)}  className="px-2 py-1.5 border border-border text-xs font-mono hover:border-primary">Next &gt;</button>
        <Button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded-none uppercase text-xs tracking-wider"
          data-testid="generate-fortnightly-btn"
        >
          {generating ? <><RefreshCw size={12} className="mr-1 animate-spin" /> Generating…</> :
            brief?.status === "ready" ? <><RefreshCw size={12} className="mr-1" /> Regenerate</> :
                                          <><FileText  size={12} className="mr-1" /> Generate</>}
        </Button>
        {brief?.status === "ready" && (
          <>
            <Button onClick={handleDownloadPDF} variant="outline" className="rounded-none uppercase text-xs tracking-wider" data-testid="download-fortnightly-pdf-btn">
              <Download size={12} className="mr-1" /> PDF
            </Button>
            <Button onClick={handleCopyNotebookLM} variant="outline" className="rounded-none uppercase text-xs tracking-wider" data-testid="copy-fortnightly-notebooklm-btn">
              {copied ? <><CheckCircle2 size={12} className="mr-1 text-emerald-400" /> Copied!</> :
                        <><Copy size={12} className="mr-1" /> NotebookLM</>}
            </Button>
          </>
        )}
      </div>
    </div>
  );

  const renderOverview = () => {
    const s  = brief?.stats || {};
    const sc = s.sev_counts || {};
    return (
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Activity size={16} className="text-primary" /> Period Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Stat label="Items"    value={s.total || 0} />
            <Stat label="Critical" value={sc.critical || 0} color={SEVERITY_COLORS.critical} />
            <Stat label="High"     value={sc.high || 0}     color={SEVERITY_COLORS.high} />
            <Stat label="X-Border" value={s.cross_border_count || 0} color="#06b6d4" />
          </div>
          {s.daily_severity?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Daily Severity Timeline
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={s.daily_severity}>
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} tickFormatter={(v) => v?.slice(5)} />
                  <YAxis tick={{ fontSize: 9, fill: "hsl(120,5%,60%)" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                  {["critical", "high", "medium", "low"].map(sev => (
                    <Area key={sev} type="monotone" dataKey={sev} stackId="1"
                          stroke={SEVERITY_COLORS[sev]} fill={SEVERITY_COLORS[sev]} fillOpacity={0.6} />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderStability = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Shield size={16} className="text-primary" /> Fortnightly Stability Index
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(brief?.stats?.stability || []).map(s => (
            <div key={s.state} className="border border-border p-3 bg-background">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{s.state}</span>
                <span className="text-[9px] font-mono uppercase px-1.5 py-0.5"
                      style={{ background: `${CONCERN_COLOR[s.level]}22`, color: CONCERN_COLOR[s.level], border: `1px solid ${CONCERN_COLOR[s.level]}55` }}>
                  {s.level}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold font-['Barlow_Condensed']" style={{ color: CONCERN_COLOR[s.level] }}>
                  {s.score}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground">/100</span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );

  const renderStabilityHistory = () => {
    if (!history.length) return null;

    const STATE_SHORT = {
      "Arunachal Pradesh": "AR", "Assam": "AS", "Manipur": "MN", "Meghalaya": "ML",
      "Mizoram": "MZ", "Nagaland": "NL", "Sikkim": "SK", "Tripura": "TR",
    };
    const NER_8 = ["Arunachal Pradesh","Assam","Manipur","Meghalaya","Mizoram","Nagaland","Sikkim","Tripura"];

    const allLabels = history.map(h => h.label);
    const defaultSel = new Set(allLabels.slice(-6));
    const active = selPeriods ?? defaultSel;

    const filteredHistory = history.filter(h => active.has(h.label));

    // Latest brief's stability scores for sort order
    const currStabMap = {};
    (brief?.stats?.stability || []).forEach(s => { currStabMap[s.state] = s.score; });
    const orderedStates = [...NER_8].sort((a, b) => (currStabMap[a] ?? 100) - (currStabMap[b] ?? 100));

    const stabilityBg = (score) => {
      if (score === null || score === undefined) return "rgba(255,255,255,0.04)";
      if (score >= 75) return `rgba(163,230,53,${0.15 + (score - 75) / 25 * 0.55})`;
      if (score >= 50) return `rgba(234,179,8,${0.15 + (score - 50) / 25 * 0.55})`;
      if (score >= 25) return `rgba(249,115,22,${0.15 + (score - 25) / 25 * 0.55})`;
      return `rgba(239,68,68,${0.25 + (25 - score) / 25 * 0.5})`;
    };

    const selectLast = (n) => setSelPeriods(new Set(allLabels.slice(-n)));
    const selectAll  = () => setSelPeriods(new Set(allLabels));
    const togglePeriod = (lbl) => {
      const next = new Set(active);
      if (next.has(lbl)) { if (next.size > 1) next.delete(lbl); }
      else next.add(lbl);
      setSelPeriods(next);
    };

    return (
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <TrendingUp size={16} className="text-primary" /> Stability Trend — Historical
            </CardTitle>
            <div className="flex gap-1">
              {["minigraphs","heatmap"].map(m => (
                <button key={m} onClick={() => setViewMode(m)}
                  className={`text-[9px] font-mono uppercase px-2 py-1 border transition-colors ${
                    viewMode === m ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:border-primary"
                  }`}>
                  {m === "minigraphs" ? "Minigraphs" : "Heatmap"}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          {/* Period controls */}
          <div className="flex flex-wrap gap-1 items-center">
            <span className="text-[9px] font-mono uppercase text-muted-foreground mr-1">Periods:</span>
            {[3, 6, 12].map(n => (
              <button key={n} onClick={() => selectLast(n)}
                className="text-[9px] font-mono uppercase px-2 py-0.5 border border-border hover:border-primary hover:text-primary transition-colors">
                Last {n}
              </button>
            ))}
            <button onClick={selectAll}
              className="text-[9px] font-mono uppercase px-2 py-0.5 border border-border hover:border-primary hover:text-primary transition-colors">
              All
            </button>
            <span className="text-[9px] font-mono text-muted-foreground mx-1">|</span>
            {allLabels.map(lbl => (
              <button key={lbl} onClick={() => togglePeriod(lbl)}
                className={`text-[9px] font-mono px-2 py-0.5 border transition-colors ${
                  active.has(lbl) ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground"
                }`}>
                {lbl}
              </button>
            ))}
          </div>

          {/* Minigraphs view */}
          {viewMode === "minigraphs" && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {orderedStates.map(stateName => {
                const miniData = filteredHistory.map(h => {
                  const s = h.stability.find(x => x.state === stateName);
                  return { label: h.label, score: s?.score ?? null };
                });
                const currScore = currStabMap[stateName];
                const scoreColor = currScore === undefined ? "#888"
                  : currScore >= 75 ? "#a3e635"
                  : currScore >= 50 ? "#eab308"
                  : currScore >= 25 ? "#f59e0b"
                  : "#ef4444";
                const firstLabel = miniData[0]?.label || "";
                const lastLabel  = miniData[miniData.length - 1]?.label || "";
                return (
                  <div key={stateName} className="border border-border bg-background p-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">{stateName}</span>
                      {currScore !== undefined && (
                        <span className="text-[10px] font-bold font-mono" style={{ color: scoreColor }}>{currScore}</span>
                      )}
                    </div>
                    <div style={{ height: 68 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={miniData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
                          <YAxis domain={[0, 100]} hide />
                          <Tooltip
                            contentStyle={{ background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)", borderRadius: 0, fontSize: 9 }}
                            formatter={(val) => [val !== null ? `${val}/100` : "—", "Stability"]}
                            labelStyle={{ color: "#b4db50", fontFamily: "monospace", fontSize: 9 }}
                          />
                          <Line type="monotone" dataKey="score" stroke={scoreColor}
                            strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} connectNulls={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-[7px] font-mono text-muted-foreground truncate max-w-[45%]">{firstLabel}</span>
                      <span className="text-[7px] font-mono text-muted-foreground truncate max-w-[45%] text-right">{lastLabel}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Heatmap view */}
          {viewMode === "heatmap" && (
            <div className="overflow-x-auto">
              <div style={{ minWidth: Math.max(400, filteredHistory.length * 56 + 48) }}>
                {/* Column headers */}
                <div className="flex mb-1" style={{ paddingLeft: 48 }}>
                  {filteredHistory.map(h => (
                    <div key={h.label} style={{ width: 52, flexShrink: 0 }}
                      className="text-[7px] font-mono text-muted-foreground text-center"
                      title={h.label}>
                      <span style={{ display:"inline-block", writingMode:"vertical-rl", transform:"rotate(180deg)", maxHeight:48, overflow:"hidden" }}>
                        {h.label}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Rows */}
                {orderedStates.map(stateName => {
                  const currScore = currStabMap[stateName];
                  const scoreColor = currScore === undefined ? "#888"
                    : currScore >= 75 ? "#a3e635"
                    : currScore >= 50 ? "#eab308"
                    : currScore >= 25 ? "#f59e0b"
                    : "#ef4444";
                  return (
                    <div key={stateName} className="flex items-center mb-0.5">
                      <div className="text-[9px] font-mono font-bold text-right pr-2"
                        style={{ color: scoreColor, width: 48, flexShrink: 0 }}>
                        {STATE_SHORT[stateName] || stateName.slice(0,2).toUpperCase()}
                      </div>
                      {filteredHistory.map(h => {
                        const s = h.stability.find(x => x.state === stateName);
                        const score = s?.score ?? null;
                        return (
                          <div key={h.label} title={`${stateName} · ${h.label} · ${score ?? "—"}/100`}
                            style={{ width: 52, height: 28, flexShrink: 0, background: stabilityBg(score), border: "1px solid rgba(255,255,255,0.06)" }}
                            className="flex items-center justify-center">
                            <span className="text-[9px] font-mono font-bold" style={{ color: score !== null ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.2)" }}>
                              {score ?? "—"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex gap-4 text-[9px] font-mono text-muted-foreground border-t border-border pt-2">
            <span><span className="inline-block w-2 h-2 mr-1 align-middle" style={{background:"#a3e635"}}/>75–100 Stable</span>
            <span><span className="inline-block w-2 h-2 mr-1 align-middle" style={{background:"#eab308"}}/>50–74 Monitor</span>
            <span><span className="inline-block w-2 h-2 mr-1 align-middle" style={{background:"#f59e0b"}}/>25–49 Elevated</span>
            <span><span className="inline-block w-2 h-2 mr-1 align-middle" style={{background:"#ef4444"}}/>0–24 Critical</span>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderExecSummary = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Target size={16} className="text-primary" /> Executive Assessment
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <div className="text-sm leading-relaxed whitespace-pre-wrap font-mono text-foreground/95">
          {renderLabeledText(brief?.executive_summary || "")}
        </div>
        <div className="mt-3 flex gap-3 text-[9px] font-mono uppercase tracking-wider text-muted-foreground border-t border-border pt-2">
          <span><span className="inline-block w-2 h-2 bg-emerald-500/40 mr-1 align-middle"/>Confirmed = data-grounded fact</span>
          <span><span className="inline-block w-2 h-2 bg-amber-500/40   mr-1 align-middle"/>Assessed  = pattern inference</span>
          <span><span className="inline-block w-2 h-2 bg-cyan-500/40    mr-1 align-middle"/>Speculative = forecast</span>
        </div>
      </CardContent>
    </Card>
  );

  const renderStateSections = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <MapPin size={16} className="text-primary" /> State-wise Security Assessment
        </CardTitle>
      </CardHeader>
      <CardContent className="p-2">
        {Object.entries(brief?.state_sections || {})
          .sort(([a], [b]) => {
            const stab = brief?.stats?.stability || [];
            const aScore = stab.find(s => s.state === a)?.score ?? 100;
            const bScore = stab.find(s => s.state === b)?.score ?? 100;
            return aScore - bScore;
          })
          .map(([state, sec]) => {
          const open = openStates[state];
          const st_stats = brief.stats?.states?.[state] || {};
          return (
            <div key={state} className="border-b border-border last:border-b-0">
              <button onClick={() => setOpenStates(p => ({...p, [state]: !open}))}
                      className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/40 transition-colors">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono uppercase tracking-wider font-bold">{state}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {st_stats.total} items · C:{st_stats.sev_counts?.critical || 0} H:{st_stats.sev_counts?.high || 0}
                  </span>
                </div>
                {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {open && (
                <div className="px-4 pb-3 space-y-2 text-sm font-mono leading-relaxed">
                  {["severity_summary", "escalation_pattern", "key_actors", "district_hotspots", "operational_concerns"].map(k => {
                    const v = sec[k];
                    if (!v) return null;
                    const label = {
                      severity_summary: "Severity Profile",
                      escalation_pattern: "Escalation Pattern",
                      key_actors: "Key Actors",
                      district_hotspots: "District Hotspots",
                      operational_concerns: "Operational Concerns",
                    }[k];
                    return (
                      <div key={k}>
                        <div className="text-[10px] uppercase tracking-wider text-primary font-bold">{label}</div>
                        <div className="text-foreground/90 mt-0.5">{renderLabeledText(v)}</div>
                      </div>
                    );
                  })}
                  {st_stats.critical_items?.length > 0 && (
                    <div className="mt-3 border-t border-border pt-2">
                      <div className="text-[10px] uppercase tracking-wider text-red-400 font-bold mb-1">Critical Incidents</div>
                      <ul className="text-xs space-y-1">
                        {st_stats.critical_items.slice(0, 5).map(ci => (
                          <li key={ci.id} className="text-foreground/85">
                            <span className="text-muted-foreground mr-1">[{ci.date}]</span>{ci.title}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {st_stats.analyst_notes?.length > 0 && (
                    <div className="mt-3 border-t border-violet-500/30 pt-2 space-y-2">
                      <div className="text-[10px] uppercase tracking-wider text-violet-400 font-bold flex items-center gap-1">
                        ✎ Analyst Enhancements ({st_stats.analyst_notes.length})
                      </div>
                      {st_stats.analyst_notes.map((n, idx) => (
                        <div key={idx} className="p-2 bg-violet-500/10 border border-violet-500/25 rounded-sm">
                          <div className="text-[9px] text-violet-400/70 font-mono mb-1">
                            [{n.date}] {n.severity?.toUpperCase()} · {n.item_title} · {n.by}
                          </div>
                          <div className="text-xs text-violet-100 leading-relaxed whitespace-pre-wrap">{n.note}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );

  const renderCrossBorder = () => {
    const cba = brief?.cross_border_analysis || {};
    if (!cba.bangladesh_border && !cba.myanmar_border) return null;
    const LEVEL_COLOR = { CRITICAL: "text-red-400", HIGH: "text-orange-400", MEDIUM: "text-yellow-400", LOW: "text-green-400" };
    const BorderBlock = ({ data, title, accentClass }) => {
      if (!data) return null;
      const lvl = data.threat_level || "MEDIUM";
      const fields = [
        ["overview",             "Overview"],
        ["primary_threats",      "Primary Threats"],
        ["hotspot_corridors",    "Hotspot Corridors"],
        ["key_actors",           "Key Actors"],
        ["indo_bd_dimension",    "Indo-Bangladesh Dimension"],
        ["displacement_pressure","Displacement Pressure"],
        ["operational_concerns", "Operational Concerns"],
      ];
      return (
        <div className={`border-l-2 ${accentClass} pl-3 space-y-2`}>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold font-mono uppercase tracking-wider">{title}</span>
            <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 border rounded-sm ${LEVEL_COLOR[lvl] || "text-muted-foreground"} border-current bg-current/10`}>{lvl}</span>
          </div>
          {fields.map(([k, lbl]) => {
            const v = data[k];
            if (!v) return null;
            return (
              <div key={k}>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-bold">{lbl}</div>
                <div className="text-sm text-foreground/90 font-mono leading-relaxed mt-0.5">{renderLabeledText(v)}</div>
              </div>
            );
          })}
        </div>
      );
    };
    return (
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-amber-500/30 bg-amber-500/5">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Globe size={16} className="text-amber-400" /> Cross-Border Threat Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-6">
          <BorderBlock data={cba.bangladesh_border} title="Indo-Bangladesh Border" accentClass="border-orange-500" />
          <BorderBlock data={cba.myanmar_border}    title="Indo-Myanmar Border"    accentClass="border-red-500" />
        </CardContent>
      </Card>
    );
  };

  const renderScenarios = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <TrendingUp size={16} className="text-primary" /> Predictive Scenarios (H+15 / H+30)
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-3">
        {(brief?.scenarios || []).map((sc, i) => (
          <div key={i} className="border border-border bg-background p-3">
            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
              <span className="text-sm font-bold font-['Barlow_Condensed'] uppercase">{sc.title}</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 border border-border bg-muted/20">{sc.horizon}</span>
                <span className="text-xs font-mono font-bold" style={{ color: sc.confidence_pct > 60 ? "#ef4444" : sc.confidence_pct > 30 ? "#f59e0b" : "#a3e635" }}>
                  Conf {sc.confidence_pct}%
                </span>
              </div>
            </div>
            <div className="text-xs leading-relaxed text-foreground/85 mb-2">{sc.narrative}</div>
            {sc.warning_indicators?.length > 0 && (
              <div className="text-[11px] font-mono">
                <span className="text-[9px] uppercase tracking-wider text-amber-400">Warning Indicators</span>
                <ul className="mt-1 ml-3 list-disc text-muted-foreground space-y-0.5">
                  {sc.warning_indicators.map((w, j) => <li key={j}>{w}</li>)}
                </ul>
              </div>
            )}
            {sc.trigger_factors && (
              <div className="text-[11px] mt-2 text-cyan-400/80">
                <span className="text-[9px] uppercase tracking-wider mr-1">Trigger:</span>
                {sc.trigger_factors}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );

  const renderActionMatrix = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <Tip text="Threat-to-action mapping derived from observed activity volumes for this fortnightly period." side="top">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
            <Layers size={16} className="text-primary" /> Commander Action Matrix
          </CardTitle>
        </Tip>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead className="bg-muted/30 border-b border-border">
              <tr>
                <Th>Threat</Th><Th>Severity</Th><Th>Probability</Th><Th>Action</Th><Th>Lead Agency</Th><Th>Horizon</Th>
              </tr>
            </thead>
            <tbody>
              {(brief?.action_matrix || []).map((r, i) => (
                <tr key={i} className="border-b border-border/40">
                  <Td>{r.threat} <span className="text-muted-foreground">({r.incident_count})</span></Td>
                  <Td><BadgeChip color={r.severity === "CRITICAL" ? "red" : r.severity === "HIGH" ? "amber" : "yellow"}>{r.severity}</BadgeChip></Td>
                  <Td><BadgeChip color={r.probability === "HIGH" ? "red" : r.probability === "MODERATE" ? "amber" : "green"}>{r.probability}</BadgeChip></Td>
                  <Td className="max-w-[300px]">{r.action}</Td>
                  <Td className="text-amber-400">{r.lead_agency}</Td>
                  <Td>{r.time_horizon}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );

  const renderMitigation = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Shield size={16} className="text-primary" /> Mitigation Playbook
        </CardTitle>
      </CardHeader>
      <CardContent className="p-2">
        {Object.entries(brief?.mitigation_playbook || {}).map(([state, plan]) => {
          const open = openMitig[state];
          return (
            <div key={state} className="border-b border-border last:border-b-0">
              <button onClick={() => setOpenMitig(p => ({...p, [state]: !open}))}
                      className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/40">
                <span className="text-sm font-mono uppercase tracking-wider font-bold">{state}</span>
                {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {open && (
                <div className="px-4 pb-3 space-y-3">
                  {[["immediate", "Immediate (0-72 hrs)", "#ef4444"],
                    ["short_term", "Short Term (1-4 weeks)", "#f59e0b"],
                    ["medium_term", "Medium Term (1-3 months)", "#eab308"],
                    ["long_term", "Long Term (3-12 months)", "#a3e635"]].map(([k, lbl, color]) => {
                    const actions = plan[k] || [];
                    if (!actions.length) return null;
                    return (
                      <div key={k}>
                        <div className="text-[10px] uppercase tracking-wider font-bold mb-1" style={{color}}>{lbl}</div>
                        <ul className="text-xs space-y-1.5 font-mono">
                          {actions.map((a, i) => (
                            <li key={i} className="text-foreground/85">
                              <div>{a.action}</div>
                              <div className="text-[10px] text-muted-foreground mt-0.5">
                                Lead: <span className="text-amber-400">{a.lead_agency}</span> · {a.rationale}
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );

  // ── Top-level render ─────────────────────────────────────────────────────────

  if (loading && !brief) {
    return (
      <div className="space-y-4">
        {renderHeader()}
        <div className="border border-border bg-card p-8 text-center text-muted-foreground text-xs font-mono">
          Loading…
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="fortnightly-brief-page">
      {renderHeader()}

      {error && (
        <div className="border border-red-500/40 bg-red-500/5 p-3 text-xs font-mono text-red-400 flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {generating && (
        <div className="border border-primary bg-primary/5 p-4 text-xs font-mono text-primary flex items-center gap-2">
          <Clock size={14} className="animate-pulse" />
          Generating {label} brief — synthesizing state assessments, cross-border analysis, scenarios and action matrix. Typically 45-120 seconds.
        </div>
      )}

      {!brief && !generating && (
        <div className="border border-border bg-card p-8 text-center">
          <FileText size={32} className="mx-auto text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground mb-1">No fortnightly brief generated for {label} yet.</p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-4">
            Click GENERATE to synthesize the strategic brief from this period's intelligence.
          </p>
        </div>
      )}

      {brief?.status === "generating" && (
        <div className="border border-primary bg-primary/5 p-4 text-xs font-mono text-primary">
          <Clock size={14} className="inline mr-2 animate-pulse" />
          Generation in progress — auto-refreshing every 8s.
        </div>
      )}

      {brief?.status === "empty" && (
        <div className="border border-amber-500/40 bg-amber-500/5 p-4 text-xs font-mono text-amber-400">
          No intelligence items recorded for {label}. Cannot generate brief.
        </div>
      )}

      {brief?.status === "error" && (
        <div className="border border-red-500/40 bg-red-500/5 p-4 text-xs font-mono text-red-400">
          Generation failed: {brief.error || "unknown error"}. Try regenerating.
        </div>
      )}

      {brief?.status === "ready" && (
        <>
          <CommanderDashboard paoiAnalysis={brief?.paoi_analysis} />
          {renderOverview()}
          {renderStability()}
          {renderStabilityHistory()}
          {renderExecSummary()}
          <PaoiDeepDives paoiAnalysis={brief?.paoi_analysis} />
          {renderStateSections()}
          {renderCrossBorder()}
          {renderScenarios()}
          {renderActionMatrix()}
          {renderMitigation()}
        </>
      )}
    </div>
  );
}

// ── Small UI helpers ─────────────────────────────────────────────────────────
function Stat({ label, value, color }) {
  return (
    <div className="border border-border p-3 bg-background">
      <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-2xl font-bold font-['Barlow_Condensed']" style={{ color: color || undefined }}>{value}</div>
    </div>
  );
}
function Th({ children }) { return <th className="text-left px-2 py-2 text-[10px] uppercase tracking-wider font-bold text-muted-foreground">{children}</th>; }
function Td({ children, className = "" }) { return <td className={`px-2 py-2 align-top ${className}`}>{children}</td>; }
function BadgeChip({ children, color }) {
  const styles = {
    red:    "bg-red-500/15    text-red-400    border-red-500/40",
    amber:  "bg-amber-500/15  text-amber-400  border-amber-500/40",
    yellow: "bg-yellow-500/15 text-yellow-400 border-yellow-500/40",
    green:  "bg-emerald-500/15 text-emerald-400 border-emerald-500/40",
  }[color] || "bg-muted/15 text-muted-foreground border-border";
  return <span className={`inline-block text-[9px] font-mono uppercase px-1.5 py-0.5 border ${styles}`}>{children}</span>;
}
