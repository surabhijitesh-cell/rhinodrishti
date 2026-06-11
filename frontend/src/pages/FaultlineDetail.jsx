import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Target, AlertTriangle, ExternalLink, Save, RefreshCw,
  Network, FileText, Check,
} from "lucide-react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine, Area, AreaChart,
} from "recharts";

const LEVEL_STYLE = {
  CRITICAL: { color: "#ef4444", text: "text-red-400",    border: "border-red-500/40",    bg: "bg-red-950/20" },
  ELEVATED: { color: "#f59e0b", text: "text-orange-400", border: "border-orange-500/40", bg: "bg-orange-950/20" },
  MONITOR:  { color: "#eab308", text: "text-yellow-400", border: "border-yellow-500/30", bg: "bg-yellow-950/15" },
  STABLE:   { color: "#a3e635", text: "text-green-400",  border: "border-green-500/30",  bg: "bg-green-950/10" },
};

const tooltipStyle = {
  background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)",
  borderRadius: 0, fontSize: 11,
};

function ScoreBreakdown({ score }) {
  if (!score) return null;
  const rows = [
    { key: "severity_load", label: "Severity load",  weight: "40%" },
    { key: "velocity",      label: "Velocity",       weight: "25%" },
    { key: "actor_spread",  label: "Actor spread",   weight: "20%" },
    { key: "cross_border",  label: "Cross-border",   weight: "15%" },
  ];
  return (
    <div className="space-y-1.5">
      {rows.map((r) => {
        const v = score[r.key] || 0;
        return (
          <div key={r.key} className="flex items-center gap-2 text-xs font-mono">
            <span className="w-28 text-muted-foreground">{r.label}</span>
            <span className="w-10 text-muted-foreground">{r.weight}</span>
            <div className="flex-1 h-1.5 bg-muted/30">
              <div className="h-full bg-primary" style={{ width: `${Math.min(100, v)}%` }} />
            </div>
            <span className="w-10 text-right">{v.toFixed?.(1) ?? v}</span>
          </div>
        );
      })}
      <div className="pt-2 mt-2 border-t border-border space-y-1 text-[11px] text-muted-foreground font-mono">
        <div>LLM avg impact: <span className="text-foreground">{score.avg_impact?.toFixed?.(1) ?? "—"}</span></div>
        <div>LLM avg confidence: <span className="text-foreground">{score.avg_confidence?.toFixed?.(1) ?? "—"}</span></div>
        <div>Articles considered: <span className="text-foreground">{score.n_articles ?? 0}</span></div>
      </div>
    </div>
  );
}

export default function FaultlineDetail({ api }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [faultline, setFaultline] = useState(null);
  const [history, setHistory] = useState([]);
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [tab, setTab] = useState("articles");
  const [notesDraft, setNotesDraft] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  // Only initialize notesDraft from the server response on the first load.
  // Subsequent fetchAll calls (e.g. days-selector change, refresh, polling)
  // would otherwise silently overwrite the user's in-progress draft.
  const notesInitialized = useRef(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [fl, hist, arts] = await Promise.all([
        axios.get(`${api}/faultlines/${id}`),
        axios.get(`${api}/faultlines/${id}/history?days=${days}`),
        axios.get(`${api}/faultlines/${id}/articles?limit=50`),
      ]);
      setFaultline(fl.data);
      setHistory(hist.data.series || []);
      setArticles(arts.data.articles || []);
      if (!notesInitialized.current) {
        setNotesDraft(fl.data?.notes || "");
        notesInitialized.current = true;
      }
    } catch (e) {
      console.error("Failed to load faultline detail", e);
    }
    setLoading(false);
  }, [api, id, days]);

  // Reset the "initialized" flag when the user navigates to a different faultline
  // — otherwise a fresh page would still show stale notes from the prior faultline.
  useEffect(() => {
    notesInitialized.current = false;
  }, [id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const saveNotes = async () => {
    setSavingNotes(true);
    setNotesSaved(false);
    try {
      await axios.patch(`${api}/faultlines/${id}`, { notes: notesDraft });
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 3000);
    } catch (e) { console.error(e); }
    setSavingNotes(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await axios.post(`${api}/faultlines/${id}/refresh?lookback_hours=24`);
      // Give the background task ~2 s to insert new mappings, then re-fetch
      await new Promise((r) => setTimeout(r, 2000));
      await fetchAll();
    } catch (e) {
      console.error("Faultline refresh failed", e);
      await fetchAll();
    }
    setRefreshing(false);
  };

  const ackAlert = async (alertId) => {
    try {
      await axios.post(`${api}/faultlines/warnings/${alertId}/ack`);
      fetchAll();
    } catch (e) { console.error(e); }
  };

  if (loading && !faultline) {
    return <div className="p-6 text-sm text-muted-foreground font-mono">Loading…</div>;
  }
  if (!faultline) {
    return (
      <div className="p-6">
        <Button variant="ghost" onClick={() => navigate("/faultlines")}>
          <ArrowLeft size={14} className="mr-1" /> Back
        </Button>
        <p className="text-sm text-red-400 mt-2">Faultline not found.</p>
      </div>
    );
  }

  const level = faultline.latest_score?.level || "STABLE";
  const style = LEVEL_STYLE[level] || LEVEL_STYLE.STABLE;
  const score = faultline.latest_score?.score ?? 0;
  const alert = faultline.active_alert;

  return (
    <div className="space-y-4 p-4 max-w-7xl mx-auto">
      {/* Back + header */}
      <Button
        variant="ghost" size="sm"
        className="text-xs"
        onClick={() => navigate("/faultlines")}
      >
        <ArrowLeft size={12} className="mr-1" /> All faultlines
      </Button>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
            {faultline.state}
          </p>
          <h1 className="text-2xl font-bold leading-tight flex items-center gap-2">
            <Target size={20} className="text-primary" />
            {faultline.name}
          </h1>
          {faultline.description && (
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
              {faultline.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className={`border ${style.border} ${style.bg} px-4 py-2 text-center`}>
            <p className={`text-[10px] uppercase tracking-wider font-mono ${style.text}`}>
              {level}
            </p>
            <p className="text-3xl font-bold font-['Barlow_Condensed']" style={{ color: style.color }}>
              {Math.round(score)}
            </p>
            <p className="text-[10px] text-muted-foreground font-mono">/ 100</p>
          </div>
        </div>
      </div>

      {/* Active alert banner */}
      {alert && (
        <Card className={`border-2 ${style.border} ${style.bg} rounded-none`}>
          <CardContent className="p-3 flex items-center gap-3">
            <AlertTriangle size={14} className={`${style.text} animate-pulse shrink-0`} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider font-['Barlow_Condensed']">
                Active warning · {alert.alert_type}
              </p>
              <p className="text-sm">{alert.reason}</p>
              <p className="text-[10px] text-muted-foreground font-mono">
                created {alert.created_at} · expires {alert.expires_at}
              </p>
            </div>
            <Button
              variant="outline" size="sm"
              className="rounded-none text-[10px]"
              onClick={() => ackAlert(alert.id)}
            >
              <Check size={12} className="mr-1" /> ACK
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Trendline + score breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card className="lg:col-span-2 border border-border rounded-none">
          <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center gap-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText size={14} /> Trendline
            </CardTitle>
            <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
              <SelectTrigger className="w-28 h-7 rounded-none text-xs ml-auto" data-testid="days-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="30">30 days</SelectItem>
                <SelectItem value="90">90 days</SelectItem>
                <SelectItem value="180">180 days</SelectItem>
                <SelectItem value="365">365 days</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
              className="h-7"
              title="Scan for new articles matching this faultline"
            >
              <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            </Button>
          </CardHeader>
          <CardContent className="p-3 h-64">
            {history.length === 0 ? (
              <p className="text-sm text-muted-foreground font-mono">No history yet for this faultline.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={style.color} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={style.color} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#555" />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} stroke="#555" />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "CRITICAL", fontSize: 9, fill: "#ef4444" }} />
                  <ReferenceLine y={55} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: "ELEVATED", fontSize: 9, fill: "#f59e0b" }} />
                  <Area type="monotone" dataKey="score" stroke={style.color} strokeWidth={2} fill="url(#trendGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="border border-border rounded-none">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm">Score breakdown</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <ScoreBreakdown score={faultline.latest_score} />
          </CardContent>
        </Card>
      </div>

      {/* Tabs: Articles / Cross-links / Notes */}
      <div className="flex gap-1 border-b border-border">
        {["articles", "cross-links", "notes"].map((t) => (
          <button
            key={t}
            className={`px-3 py-1.5 text-xs uppercase tracking-wider font-mono border-b-2 ${
              tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground"
            }`}
            onClick={() => setTab(t)}
            data-testid={`tab-${t}`}
          >
            {t === "articles" ? `Matched articles (${articles.length})` : t === "cross-links" ? "Cross-links" : "Manual notes"}
          </button>
        ))}
      </div>

      {/* Articles tab */}
      {tab === "articles" && (
        <Card className="border border-border rounded-none">
          <CardContent className="p-0">
            {articles.length === 0 ? (
              <p className="text-sm text-muted-foreground font-mono p-4">
                No matched articles for the latest date.
              </p>
            ) : (
              <div className="divide-y divide-border">
                {articles.map((a) => (
                  <div key={a.id} className="p-3 hover:bg-muted/10" data-testid={`article-${a.id}`}>
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium leading-snug">
                          {a.article_title}
                        </p>
                        <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                          {a.source || a.article_source} · {a.article_published_at?.slice(0, 10)} · {a.article_severity}
                        </p>
                        <p className="text-xs italic text-muted-foreground mt-2">
                          "{a.rationale}"
                        </p>
                        {(a.evidence_phrases || []).length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {a.evidence_phrases.map((ph, i) => (
                              <Badge key={i} variant="outline" className="rounded-none text-[10px] px-1.5 py-0">
                                {ph}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        <Badge className="rounded-none text-[10px]">
                          impact {a.impact_score}
                        </Badge>
                        <Badge variant="outline" className="rounded-none text-[10px]">
                          conf {a.confidence}
                        </Badge>
                        {a.source_url && (
                          <a
                            href={a.source_url} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-primary hover:underline flex items-center gap-1"
                          >
                            source <ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Cross-links tab */}
      {tab === "cross-links" && (
        <Card className="border border-border rounded-none">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm flex items-center gap-2">
              <Network size={14} /> Linked faultlines
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground font-mono mb-3">
              These faultlines influence this one (or are influenced by it) via the propagation graph.
            </p>
            {(faultline.linked_faultlines || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No linked faultlines configured.</p>
            ) : (
              <div className="space-y-2">
                {faultline.linked_faultlines.map((lf) => (
                  <div
                    key={lf.id}
                    className="flex items-center gap-3 p-2 border border-border cursor-pointer hover:bg-muted/10"
                    onClick={() => navigate(`/faultlines/${lf.id}`)}
                  >
                    <Target size={12} className="text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">{lf.name || lf.id}</p>
                      {lf.state && (
                        <p className="text-[10px] text-muted-foreground font-mono">{lf.state}</p>
                      )}
                    </div>
                    <Badge variant="outline" className="rounded-none text-[10px]">
                      weight {lf.weight?.toFixed?.(2) ?? lf.weight}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Notes tab */}
      {tab === "notes" && (
        <Card className="border border-border rounded-none">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm">Manual review notes</CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-2">
            <p className="text-[11px] text-muted-foreground font-mono">
              Use this for manual review findings: local news cycles, narrative spikes, influencer amplification, cross-posting patterns, repeated claims observed beyond automated coverage.
            </p>
            <textarea
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
              className="w-full h-48 p-3 bg-background border border-border rounded-none text-sm font-mono resize-none focus:outline-none focus:border-primary"
              placeholder="Add manual review notes here…"
              data-testid="notes-textarea"
            />
            <div className="flex items-center gap-2">
              <Button
                onClick={saveNotes}
                disabled={savingNotes}
                size="sm" className="rounded-none text-xs"
                data-testid="save-notes-btn"
              >
                <Save size={12} className="mr-1" />
                {savingNotes ? "Saving…" : "Save notes"}
              </Button>
              {notesSaved && (
                <span className="text-[10px] text-green-400 font-mono">Saved.</span>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
