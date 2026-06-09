import { useEffect, useState, useCallback } from "react";
import {
  Calendar, FileText, RefreshCw, Download, Copy, ChevronDown, ChevronUp,
  Shield, AlertTriangle, Users, MapPin, Phone, Mail, Activity, TrendingUp,
  Target, Layers, CheckCircle2, Clock, Globe,
} from "lucide-react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import Tip from "../components/Tip";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell,
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

// Format claim labels with color hints
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

function previousMonth() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

export default function MonthlyBrief({ api }) {
  const init = previousMonth();
  const [year, setYear]       = useState(init.year);
  const [month, setMonth]     = useState(init.month);
  const [brief, setBrief]         = useState(null);
  const [prevBrief, setPrevBrief] = useState(null);
  const [history,    setHistory]    = useState([]);
  const [selPeriods, setSelPeriods] = useState(null);
  const [viewMode,   setViewMode]   = useState("minigraphs");
  const [loading,    setLoading]    = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError]     = useState(null);
  const [openStates, setOpenStates] = useState({});
  const [openMitig,  setOpenMitig]  = useState({});
  const [copied, setCopied]   = useState(false);

  const monthLabel = new Date(year, month - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" });
  const prevYear  = month === 1 ? year - 1 : year;
  const prevMonth = month === 1 ? 12 : month - 1;
  const prevMonthLabel = new Date(prevYear, prevMonth - 1, 1).toLocaleString("en-IN", { month: "long", year: "numeric" });

  const fetchBrief = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const r = await axios.get(`${api}/brief/monthly/${year}/${month}`);
      setBrief(r.data);
      if (r.data.status === "generating") {
        setGenerating(true);
      } else {
        setGenerating(false);
      }
    } catch (e) {
      if (e?.response?.status === 404) {
        setBrief(null);
      } else {
        setError(e?.response?.data?.detail || "Fetch failed");
      }
      setGenerating(false);
    }
    setLoading(false);
    // Fetch previous month brief silently (for comparison)
    try {
      const pr = await axios.get(`${api}/brief/monthly/${prevYear}/${prevMonth}`);
      if (pr.data?.status === "ready" || pr.data?.status === "partial") {
        setPrevBrief(pr.data);
      } else {
        setPrevBrief(null);
      }
    } catch {
      setPrevBrief(null);
    }
    // Fetch full stability history for trend chart
    try {
      const hr = await axios.get(`${api}/brief/monthly/stability-history`);
      setHistory(hr.data?.history || []);
    } catch {
      setHistory([]);
    }
  }, [api, year, month, prevYear, prevMonth]);

  useEffect(() => { fetchBrief(); }, [fetchBrief]);

  // Poll while generating
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(fetchBrief, 8000);
    return () => clearInterval(t);
  }, [generating, fetchBrief]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await axios.post(`${api}/brief/monthly/generate?year=${year}&month=${month}`);
      // Poll for completion
      setTimeout(fetchBrief, 4000);
    } catch (e) {
      setError(e?.response?.data?.detail || "Generation request failed");
      setGenerating(false);
    }
  };

  const handleCopyNotebookLM = async () => {
    try {
      const r = await axios.get(`${api}/brief/monthly/${year}/${month}/notebooklm`);
      await navigator.clipboard.writeText(r.data);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (e) {
      setError("Copy failed: " + (e?.message || ""));
    }
  };

  const handleDownloadPDF = () => {
    window.open(`${api}/brief/monthly/${year}/${month}/pdf`, "_blank");
  };

  const adjustMonth = (delta) => {
    let m = month + delta;
    let y = year;
    while (m < 1) { m += 12; y -= 1; }
    while (m > 12) { m -= 12; y += 1; }
    setMonth(m); setYear(y);
  };

  // ── Renderers ────────────────────────────────────────────────────────────

  const renderHeader = () => (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="monthly-brief-title">
          Monthly Strategic Brief
        </h1>
        <div className="flex items-center gap-2 mt-1">
          <Calendar size={12} className="text-muted-foreground" />
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">
            {monthLabel}
          </p>
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
        <button onClick={() => adjustMonth(-1)} className="px-2 py-1.5 border border-border text-xs font-mono hover:border-primary">&lt; Prev</button>
        <div className="text-xs font-mono uppercase tracking-wider min-w-[120px] text-center">{monthLabel}</div>
        <button onClick={() => adjustMonth(1)}  className="px-2 py-1.5 border border-border text-xs font-mono hover:border-primary">Next &gt;</button>
        <Button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded-none uppercase text-xs tracking-wider"
          data-testid="generate-monthly-btn"
        >
          {generating ? <><RefreshCw size={12} className="mr-1 animate-spin" /> Generating…</> :
            brief?.status === "ready" ? <><RefreshCw size={12} className="mr-1" /> Regenerate</> :
                                          <><FileText  size={12} className="mr-1" /> Generate</>}
        </Button>
        {brief?.status === "ready" && (
          <>
            <Button onClick={handleDownloadPDF} variant="outline" className="rounded-none uppercase text-xs tracking-wider" data-testid="download-pdf-btn">
              <Download size={12} className="mr-1" /> PDF
            </Button>
            <Button onClick={handleCopyNotebookLM} variant="outline" className="rounded-none uppercase text-xs tracking-wider" data-testid="copy-notebooklm-btn">
              {copied ? <><CheckCircle2 size={12} className="mr-1 text-emerald-400" /> Copied!</> :
                        <><Copy size={12} className="mr-1" /> NotebookLM</>}
            </Button>
          </>
        )}
      </div>
    </div>
  );

  const renderOverview = () => {
    const s = brief?.stats || {};
    const sc = s.sev_counts || {};
    return (
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Activity size={16} className="text-primary" /> Regional Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Stat label="Items" value={s.total || 0} />
            <Stat label="Critical" value={sc.critical || 0} color={SEVERITY_COLORS.critical} />
            <Stat label="High"     value={sc.high || 0}     color={SEVERITY_COLORS.high} />
            <Stat label="X-Border" value={s.cross_border_count || 0} color="#06b6d4" />
          </div>
          {s.daily_severity?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Daily Severity Timeline
              </div>
              <ResponsiveContainer width="100%" height={200}>
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
          <Shield size={16} className="text-primary" /> Strategic Stability Index
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(brief?.stats?.stability || []).map(s => (
            <div
              key={s.state}
              className={`border p-3 bg-background ${s.is_cross_border_region ? "border-cyan-500/50" : "border-border"}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  {s.is_cross_border_region && <Globe size={10} className="text-cyan-400" />}
                  {s.state}
                </span>
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
    const ACCENT = "#a3e635";

    // Sort states by current brief stability score ascending (most critical first)
    const currStabMap = Object.fromEntries((brief?.stats?.stability || []).map(s => [s.state, s.score]));
    const orderedStates = [...NER_8].sort((a, b) => (currStabMap[a] ?? 100) - (currStabMap[b] ?? 100));

    const allLabels = history.map(h => h.label);
    const defaultSel = new Set(allLabels.slice(-6));
    const active = selPeriods ?? defaultSel;

    const chartData = history
      .filter(h => active.has(h.label))
      .map(h => {
        const row = { label: h.label };
        const stab = Object.fromEntries(h.stability.map(s => [s.state, s.score]));
        orderedStates.forEach(st => { row[st] = stab[st] ?? null; });
        return row;
      });

    const togglePeriod = (lbl) => {
      const next = new Set(active);
      if (next.has(lbl)) { if (next.size > 1) next.delete(lbl); }
      else next.add(lbl);
      setSelPeriods(next);
    };
    const selectLast = (n) => setSelPeriods(new Set(allLabels.slice(-n)));
    const selectAll  = () => setSelPeriods(new Set(allLabels));

    const stabilityBg = (score) => {
      if (score === null || score === undefined) return "rgba(255,255,255,0.04)";
      if (score >= 75) return `rgba(163,230,53,${0.15 + (score-75)/25*0.55})`;
      if (score >= 50) return `rgba(234,179,8,${0.15 + (score-50)/25*0.55})`;
      if (score >= 25) return `rgba(249,115,22,${0.15 + (score-25)/25*0.55})`;
      return `rgba(239,68,68,${0.25 + (25-score)/25*0.5})`;
    };

    return (
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <TrendingUp size={16} className="text-primary" /> Stability Trend — Historical
            </CardTitle>
            <div className="flex gap-1">
              {[["minigraphs","Minigraphs"],["heatmap","Heatmap"]].map(([v, lbl]) => (
                <button key={v} onClick={() => setViewMode(v)}
                  className={`text-[9px] font-mono uppercase px-2 py-0.5 border transition-colors ${
                    viewMode === v ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground"
                  }`}>
                  {lbl}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          {/* Period controls */}
          <div className="flex flex-wrap gap-1 items-center">
            <span className="text-[9px] font-mono uppercase text-muted-foreground mr-1">Periods:</span>
            {[3,6,12].map(n => (
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

          {viewMode === "minigraphs" ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {orderedStates.map(st => {
                const currScore = currStabMap[st];
                const currLevel = (brief?.stats?.stability || []).find(s => s.state === st)?.level;
                return (
                  <div key={st} className="border border-border bg-background p-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] font-mono uppercase font-semibold tracking-wide truncate" style={{maxWidth:"70%"}}>{st}</span>
                      {currScore !== undefined && (
                        <span className="text-[9px] font-bold font-mono" style={{ color: CONCERN_COLOR[currLevel] || "#888" }}>
                          {currScore}
                        </span>
                      )}
                    </div>
                    <div style={{ height: 68 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 2, right: 2, bottom: 0, left: 0 }}>
                          <YAxis domain={[0, 100]} hide />
                          <XAxis dataKey="label" hide />
                          <Tooltip
                            contentStyle={{ background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)", borderRadius: 0, fontSize: 9, padding: "2px 6px" }}
                            labelStyle={{ color: "#b4db50", fontFamily: "monospace", fontSize: 9 }}
                            itemStyle={{ fontFamily: "monospace", fontSize: 9 }}
                            formatter={(val) => [val !== null ? `${val}/100` : "—", st]}
                          />
                          <Line type="monotone" dataKey={st} stroke={ACCENT}
                            strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} connectNulls={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    {chartData.length > 1 && (
                      <div className="flex justify-between mt-0.5">
                        <span className="text-[7px] font-mono text-muted-foreground truncate" style={{maxWidth:"48%"}}>{chartData[0]?.label}</span>
                        <span className="text-[7px] font-mono text-muted-foreground truncate text-right" style={{maxWidth:"48%"}}>{chartData[chartData.length-1]?.label}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            /* Heatmap */
            <div className="overflow-x-auto">
              <div style={{ minWidth: Math.max(260, 56 + chartData.length * 50) }}>
                <div className="flex mb-1" style={{ paddingLeft: 56 }}>
                  {chartData.map(d => (
                    <div key={d.label} className="text-[8px] font-mono text-muted-foreground shrink-0"
                      style={{ width: 50, textAlign: "center", transform: "rotate(-30deg)", transformOrigin: "left bottom", height: 28, lineHeight: "28px" }}>
                      {d.label}
                    </div>
                  ))}
                </div>
                {orderedStates.map(st => {
                  const currLevel = (brief?.stats?.stability || []).find(s => s.state === st)?.level;
                  return (
                    <div key={st} className="flex items-center mb-px">
                      <div className="shrink-0 text-[9px] font-mono text-right pr-2"
                        style={{ width: 56, color: CONCERN_COLOR[currLevel] || "#888" }}>
                        {STATE_SHORT[st] || st.slice(0,2).toUpperCase()}
                      </div>
                      {chartData.map(d => {
                        const score = d[st];
                        return (
                          <div key={d.label} className="shrink-0 flex items-center justify-center"
                            style={{ width: 50, height: 26, background: stabilityBg(score), cursor: "default" }}
                            title={`${st} | ${d.label}: ${score ?? "—"}/100`}>
                            <span className="text-[8px] font-bold font-mono select-none"
                              style={{ color: score !== null && score >= 50 ? "#111" : "#eee" }}>
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
          <Target size={16} className="text-primary" /> Executive Strategic Assessment
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

                  {/* Critical incident list */}
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

                  {/* Analyst notes (human-enhanced items for this state) */}
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

  const renderActionMatrix = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <Tip text="Threat-to-action mapping derived from observed activity volumes. Rows ordered by incident count. Use as command-level prioritization framework." side="top">
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
                  <Td><Badge color={r.severity === "CRITICAL" ? "red" : r.severity === "HIGH" ? "amber" : "yellow"}>{r.severity}</Badge></Td>
                  <Td><Badge color={r.probability === "HIGH" ? "red" : r.probability === "MODERATE" ? "amber" : "green"}>{r.probability}</Badge></Td>
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

  const renderScenarios = () => (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <TrendingUp size={16} className="text-primary" /> Predictive Scenarios (30-90 Days)
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
                    ["long_term", "Long Term (3-12 months)", "#a3e635"]].map(([k, label, color]) => {
                    const actions = plan[k] || [];
                    if (!actions.length) return null;
                    return (
                      <div key={k}>
                        <div className="text-[10px] uppercase tracking-wider font-bold mb-1" style={{color}}>{label}</div>
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
          {fields.map(([k, label]) => {
            const v = data[k];
            if (!v) return null;
            return (
              <div key={k}>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-bold">{label}</div>
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
          <BorderBlock
            data={cba.bangladesh_border}
            title="Indo-Bangladesh Border"
            accentClass="border-orange-500"
          />
          <BorderBlock
            data={cba.myanmar_border}
            title="Indo-Myanmar Border"
            accentClass="border-red-500"
          />
        </CardContent>
      </Card>
    );
  };

  // ── Faultline section (Phase 5c) ──────────────────────────────────────────
  // ── Commander Priority Dashboard (top of brief) ───────────────────────────
  const renderCommanderDashboard = () => {
    const pa = brief?.paoi_analysis;
    if (!pa || !pa.available) return null;
    const rows = pa.commander_dashboard || [];
    const overall = pa.synthesis?.overall || {};
    const trendIcon = (t) => t === "RISING" ? "▲" : t === "FALLING" ? "▼" : "▬";
    const trendColor = (t) => t === "RISING" ? "#ef4444" : t === "FALLING" ? "#a3e635" : "#888";

    return (
      <Card className="border-2 border-red-500/40 rounded-none bg-red-950/10" data-testid="commander-dashboard">
        <CardHeader className="py-3 px-4 border-b border-red-500/30">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 text-red-400">
            <Target size={16} /> Commander's Priority Dashboard
            {pa.synthesis_tier && (
              <span className="ml-auto text-[9px] font-mono text-muted-foreground normal-case">
                {pa.synthesis_tier} synthesis
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-1 gap-2">
            {rows.map((r) => (
              <div
                key={r.id}
                className="flex items-center gap-3 border border-border p-2 bg-background"
                data-testid={`paoi-row-${r.id}`}
              >
                <span className="text-[10px] font-mono text-muted-foreground w-6">P{r.rank}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium leading-tight">{r.name}</p>
                  <p className="text-[10px] text-muted-foreground font-mono truncate">{r.what_changed}</p>
                </div>
                <span className="text-xs font-mono" style={{ color: trendColor(r.trend) }}>
                  {trendIcon(r.trend)} {r.delta > 0 ? "+" : ""}{Math.round(r.delta)}
                </span>
                <span className="text-2xl font-bold font-['Barlow_Condensed'] w-12 text-right"
                      style={{ color: CONCERN_COLOR[r.level] }}>
                  {r.score != null ? Math.round(r.score) : "—"}
                </span>
                <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 w-20 text-center"
                      style={{ background: `${CONCERN_COLOR[r.level]}22`, color: CONCERN_COLOR[r.level], border: `1px solid ${CONCERN_COLOR[r.level]}55` }}>
                  {r.level}
                </span>
              </div>
            ))}
          </div>
          {overall.bottom_line && (
            <div className="border-t border-red-500/20 pt-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-red-400 mb-1">Bottom Line</div>
              <p className="text-sm leading-relaxed">{renderLabeledText(overall.bottom_line)}</p>
            </div>
          )}
          {Array.isArray(overall.top_3_focus_next) && overall.top_3_focus_next.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-amber-400 mb-1">Focus Next Period</div>
              <ul className="space-y-1">
                {overall.top_3_focus_next.map((f, i) => (
                  <li key={i} className="text-xs flex items-start gap-2">
                    <span className="text-amber-400">{i + 1}.</span>
                    <span>{typeof f === "string" ? f : String(f)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  // ── PAOI Deep-Dives ───────────────────────────────────────────────────────
  const renderPaoiDeepDives = () => {
    const pa = brief?.paoi_analysis;
    if (!pa || !pa.available) return null;
    const paois = pa.paois || [];
    const per = pa.synthesis?.per_paoi || {};
    const other = pa.other_movements || {};

    return (
      <Card className="border border-border rounded-none bg-card" data-testid="paoi-deepdives">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Layers size={16} className="text-primary" /> Priority Area Deep-Dives
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {paois.map((p) => {
            const mv = p.faultline_movement || {};
            const syn = per[p.id] || {};
            return (
              <div key={p.id} className="border border-red-500/30 bg-red-950/10 p-3" data-testid={`deepdive-${p.id}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold flex items-center gap-2">
                    <span className="text-[10px] font-mono text-muted-foreground">P{p.rank}</span>
                    {p.name}
                  </span>
                  {mv.last != null && (
                    <span className="text-xl font-bold font-['Barlow_Condensed']" style={{ color: CONCERN_COLOR[mv.level] }}>
                      {Math.round(mv.last)}
                    </span>
                  )}
                </div>

                {/* Per-faultline mini bars */}
                {Array.isArray(mv.per_faultline) && mv.per_faultline.length > 0 && (
                  <div className="space-y-1 mb-2">
                    {mv.per_faultline.slice(0, 5).map((f) => (
                      <div key={f.id} className="flex items-center gap-2 text-[11px] font-mono">
                        <span className="w-44 truncate text-muted-foreground">{f.name}</span>
                        <div className="flex-1 h-1.5 bg-muted/30">
                          <div className="h-full" style={{ width: `${Math.min(100, f.last)}%`, background: CONCERN_COLOR[f.level] }} />
                        </div>
                        <span className="w-8 text-right">{Math.round(f.last)}</span>
                        <span className="w-10 text-right" style={{ color: f.delta > 0 ? "#ef4444" : f.delta < 0 ? "#a3e635" : "#888" }}>
                          {f.delta > 0 ? "+" : ""}{Math.round(f.delta)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {syn.period_impact && (
                  <p className="text-sm leading-relaxed mb-1">{renderLabeledText(syn.period_impact)}</p>
                )}
                {syn.forward_concerns && (
                  <p className="text-xs text-amber-300/90 mb-1">
                    <span className="uppercase tracking-wider font-mono text-[9px] text-amber-400">Watch next: </span>
                    {renderLabeledText(syn.forward_concerns)}
                  </p>
                )}
                {syn.manual_review && (
                  <p className="text-[11px] text-muted-foreground italic pt-1 border-t border-border mt-1">
                    <span className="uppercase tracking-wider font-mono text-[9px] text-cyan-400">Manual review: </span>
                    {typeof syn.manual_review === "string" ? syn.manual_review : String(syn.manual_review)}
                  </p>
                )}

                {p.keyword_hits?.n_articles > 0 && (
                  <div className="mt-2 text-[10px] text-muted-foreground font-mono">
                    {p.keyword_hits.n_articles} related reports · {(p.actors_of_interest || []).slice(0, 4).join(", ")}
                  </div>
                )}
              </div>
            );
          })}

          {/* Other faultline movements (not in PAOIs) */}
          {(other.rising?.length > 0 || other.declining?.length > 0) && (
            <div className="border border-border p-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Other Faultline Movements (outside priority areas)
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {other.rising?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-red-400 font-mono mb-1">Rising</div>
                    {other.rising.slice(0, 6).map((f) => (
                      <div key={f.id} className="flex items-center gap-2 text-[11px]">
                        <span className="text-muted-foreground w-16 truncate">[{f.state}]</span>
                        <span className="flex-1 truncate">{f.name}</span>
                        <span className="text-red-400">+{Math.round(f.delta)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {other.declining?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-green-400 font-mono mb-1">Declining</div>
                    {other.declining.slice(0, 6).map((f) => (
                      <div key={f.id} className="flex items-center gap-2 text-[11px]">
                        <span className="text-muted-foreground w-16 truncate">[{f.state}]</span>
                        <span className="flex-1 truncate">{f.name}</span>
                        <span className="text-green-400">{Math.round(f.delta)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderFaultlines = () => {
    const fa = brief?.faultline_analysis;
    if (!fa || !fa.available) return null;

    const states = Object.keys(fa.by_state || {}).sort();
    const rising = fa.rising || [];
    const critical = fa.critical || [];
    const narratives = fa.state_narratives || {};

    const handleDownload = () => {
      window.open(`${api}/faultlines/report?year=${year}&month=${month}`, "_blank");
    };

    return (
      <Card className="border border-border rounded-none bg-card" data-testid="faultline-section">
        <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center gap-2">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Target size={16} className="text-primary" /> Faultline Analysis
          </CardTitle>
          <Button
            variant="outline" size="sm"
            className="ml-auto rounded-none text-xs"
            onClick={handleDownload}
            data-testid="download-faultline-pdf-btn"
          >
            <Download size={12} className="mr-1" /> Faultline Report PDF
          </Button>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {/* Summary strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Monitored"  value={fa.total_faultlines || 0} />
            <Stat label="Critical"   value={critical.length} color={CONCERN_COLOR.CRITICAL} />
            <Stat label="Rising"     value={rising.length}   color={CONCERN_COLOR.ELEVATED} />
            <Stat label="States"     value={states.length} />
          </div>

          {/* Critical roll-up */}
          {critical.length > 0 && (
            <div className="border border-red-500/30 bg-red-500/5 p-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-red-400 mb-2">
                Currently CRITICAL (score ≥ 75)
              </div>
              <div className="space-y-1">
                {critical.slice(0, 10).map((c) => (
                  <div key={c.faultline_id} className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-[10px] text-muted-foreground w-20 shrink-0">
                      [{c.state}]
                    </span>
                    <span className="flex-1 truncate">{c.faultline_name}</span>
                    <span className="font-bold text-red-400 w-12 text-right">
                      {Math.round(c.last)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rising roll-up */}
          {rising.length > 0 && (
            <div className="border border-orange-500/30 bg-orange-500/5 p-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-orange-400 mb-2">
                Rising this month (Δ ≥ +10 pts)
              </div>
              <div className="space-y-1">
                {rising.slice(0, 10).map((r) => (
                  <div key={r.faultline_id} className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-[10px] text-muted-foreground w-20 shrink-0">
                      [{r.state}]
                    </span>
                    <span className="flex-1 truncate">{r.faultline_name}</span>
                    <span className="text-orange-400 w-12 text-right font-mono text-[10px]">
                      +{r.delta.toFixed(0)}
                    </span>
                    <span className="font-bold w-12 text-right">{Math.round(r.last)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Per-state heatmap */}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
              State × Faultline heatmap (top 5 per state)
            </div>
            <div className="space-y-1">
              {states.map((st) => {
                const fls = (fa.by_state[st] || []).slice(0, 5);
                return (
                  <div key={st} className="flex items-center gap-2">
                    <span className="text-xs font-mono uppercase tracking-wider w-24 shrink-0 text-muted-foreground">
                      {st}
                    </span>
                    <div className="flex-1 flex gap-1">
                      {fls.map((f) => (
                        <div
                          key={f.faultline_id}
                          className="flex-1 px-2 py-2 text-[10px] font-mono border cursor-pointer hover:opacity-90"
                          style={{
                            background: `${CONCERN_COLOR[f.level]}22`,
                            borderColor: `${CONCERN_COLOR[f.level]}55`,
                            color: CONCERN_COLOR[f.level],
                          }}
                          title={`${f.faultline_name}: ${f.last.toFixed(0)} (${f.level}), Δ ${f.delta.toFixed(0)}`}
                          onClick={() => window.open(`/faultlines/${f.faultline_id}`, "_blank")}
                          data-testid={`fl-heatmap-${f.faultline_id}`}
                        >
                          <div className="truncate">{f.faultline_name}</div>
                          <div className="flex items-center justify-between mt-1">
                            <span className="font-bold text-base">{Math.round(f.last)}</span>
                            <span>
                              {f.delta > 0 ? "+" : ""}{f.delta.toFixed(0)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Per-state narratives */}
          {Object.keys(narratives).length > 0 && (
            <div className="space-y-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                State narratives
              </div>
              {states.map((st) => {
                const n = narratives[st];
                if (!n || !n.summary) return null;
                return (
                  <div key={st} className="border border-border p-3 bg-background">
                    <div className="text-xs font-mono uppercase tracking-wider text-primary mb-1">
                      {st}
                    </div>
                    <p className="text-sm leading-relaxed">
                      {renderLabeledText(n.summary)}
                    </p>
                    {n.manual_review_advisory && (
                      <p className="text-[11px] text-muted-foreground italic mt-2 pt-2 border-t border-border">
                        <span className="uppercase tracking-wider font-mono text-[9px] text-amber-400">
                          Manual review:
                        </span>{" "}
                        {n.manual_review_advisory}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderContacts = () => {
    const directory = brief?.contact_directory || {};
    const firstState = Object.keys(directory)[0];
    const regional = firstState ? directory[firstState].regional_contacts : [];
    return (
      <Card className="border border-border rounded-none bg-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Phone size={16} className="text-primary" /> Contact Directory
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="text-[10px] font-mono italic text-muted-foreground border border-amber-500/30 bg-amber-500/5 p-2 mb-3">
            Public offices only — incumbent names rotate; verify via respective .gov.in portal before engagement.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(directory).map(([state, block]) => (
              <div key={state}>
                <div className="text-[11px] uppercase tracking-wider font-bold text-primary mb-1">{state}</div>
                <ul className="text-[11px] font-mono space-y-1">
                  {block.state_contacts?.map((c, i) => (
                    <li key={i} className="border-l border-border pl-2">
                      <div className="text-foreground">{c.office}</div>
                      <div className="text-muted-foreground text-[10px]">
                        {c.hq} · {c.phone} · {c.email}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-border">
            <div className="text-[11px] uppercase tracking-wider font-bold text-cyan-400 mb-1">Regional / National</div>
            <ul className="text-[11px] font-mono space-y-1">
              {regional.map((c, i) => (
                <li key={i} className="border-l border-cyan-500/40 pl-2">
                  <div className="text-foreground">{c.office}</div>
                  <div className="text-muted-foreground text-[10px]">{c.hq} · {c.phone} · {c.email}</div>
                </li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>
    );
  };

  // ── Top-level render ─────────────────────────────────────────────────────

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
    <div className="space-y-5" data-testid="monthly-brief-page">
      {renderHeader()}

      {error && (
        <div className="border border-red-500/40 bg-red-500/5 p-3 text-xs font-mono text-red-400 flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Generating state */}
      {generating && (
        <div className="border border-primary bg-primary/5 p-4 text-xs font-mono text-primary flex items-center gap-2">
          <Clock size={14} className="animate-pulse" />
          Generating {monthLabel} brief — synthesizing per-state assessments, action matrix, scenarios, and contact directory. This typically takes 60-180 seconds.
        </div>
      )}

      {/* No brief yet */}
      {!brief && !generating && (
        <div className="border border-border bg-card p-8 text-center">
          <FileText size={32} className="mx-auto text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground mb-1">No monthly brief generated for {monthLabel} yet.</p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-4">
            Click GENERATE to synthesize the strategic brief from this month's intelligence.
          </p>
        </div>
      )}

      {/* Status: generating in DB, but we have stub */}
      {brief?.status === "generating" && (
        <div className="border border-primary bg-primary/5 p-4 text-xs font-mono text-primary">
          <Clock size={14} className="inline mr-2 animate-pulse" />
          Generation in progress — auto-refreshing every 8s.
        </div>
      )}

      {/* Empty month */}
      {brief?.status === "empty" && (
        <div className="border border-amber-500/40 bg-amber-500/5 p-4 text-xs font-mono text-amber-400">
          No intelligence items recorded for {monthLabel}. Cannot generate brief.
        </div>
      )}

      {/* Error state */}
      {brief?.status === "error" && (
        <div className="border border-red-500/40 bg-red-500/5 p-4 text-xs font-mono text-red-400">
          Generation failed: {brief.error || "unknown error"}. Try regenerating.
        </div>
      )}

      {/* Partial — LLM calls failed silently */}
      {brief?.status === "partial" && (
        <div className="border border-amber-500/40 bg-amber-500/5 p-3 text-xs font-mono text-amber-400 mb-2">
          LLM synthesis failed — sections below may be empty. {brief._llm_error || "Re-generate to retry."}
        </div>
      )}

      {/* Full brief (ready or partial — stats + tables always present) */}
      {(brief?.status === "ready" || brief?.status === "partial") && (
        <>
          {renderCommanderDashboard()}
          {renderOverview()}
          {renderStability()}
          {renderStabilityHistory()}
          {renderExecSummary()}
          {renderPaoiDeepDives()}
          {renderStateSections()}
          {renderCrossBorder()}
          {renderScenarios()}
          {renderActionMatrix()}
          {renderMitigation()}
          {renderFaultlines()}
          {renderContacts()}
        </>
      )}
    </div>
  );
}

// ── Small UI helpers ────────────────────────────────────────────────────────
function Stat({ label, value, color }) {
  return (
    <div className="border border-border p-3 bg-background">
      <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-2xl font-bold font-['Barlow_Condensed']" style={{ color: color || undefined }}>
        {value}
      </div>
    </div>
  );
}
function Th({ children }) { return <th className="text-left px-2 py-2 text-[10px] uppercase tracking-wider font-bold text-muted-foreground">{children}</th>; }
function Td({ children, className = "" }) { return <td className={`px-2 py-2 align-top ${className}`}>{children}</td>; }
function Badge({ children, color }) {
  const styles = {
    red:    "bg-red-500/15    text-red-400    border-red-500/40",
    amber:  "bg-amber-500/15  text-amber-400  border-amber-500/40",
    yellow: "bg-yellow-500/15 text-yellow-400 border-yellow-500/40",
    green:  "bg-emerald-500/15 text-emerald-400 border-emerald-500/40",
  }[color] || "bg-muted/15 text-muted-foreground border-border";
  return <span className={`inline-block text-[9px] font-mono uppercase px-1.5 py-0.5 border ${styles}`}>{children}</span>;
}
