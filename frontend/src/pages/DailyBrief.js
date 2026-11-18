import { useState, useEffect, useRef, useCallback, Component, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  FileText, RefreshCw, Calendar, Shield, Globe, AlertTriangle, Download,
  Newspaper, Upload, ExternalLink, GitBranch, Layers,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import Tip from "../components/Tip";
import axios from "axios";
import MonthlyBrief from "./MonthlyBrief";
import FortnightlyBrief from "./FortnightlyBrief";
import { useAuth } from "../contexts/AuthContext";
import ConfirmAction from "../components/ConfirmAction";
import LoadError from "../components/LoadError";
import PastBriefs from "../components/PastBriefs";
import { useAdminIod } from "../contexts/AdminIodContext";

class BriefErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="text-center py-16 border border-border bg-card">
          <AlertTriangle size={40} className="mx-auto text-amber-400 mb-4" />
          <p className="text-muted-foreground text-sm mb-2">Failed to render the daily brief.</p>
          <p className="text-xs text-muted-foreground mb-4 font-mono">{String(this.state.error?.message || '').slice(0, 100)}</p>
          <Button onClick={() => { this.setState({ hasError: false }); window.location.reload(); }} className="rounded-none uppercase text-xs tracking-wider">
            Reload Page
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

const NEW_BADGE_LOGIN_THRESHOLD = 3;

const TABS = ["daily", "fortnightly", "monthly", "past"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const POLL_EVERY_MS = 5000;
const POLL_GIVE_UP_MS = 3 * 60 * 1000;

const todayIST = () => new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);

// Server times may arrive without a zone marker; they are UTC.
function fmtIst(iso) {
  if (!iso) return "";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  if (isNaN(d)) return "";
  return `${d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" })} IST`;
}

export default function DailyBrief({ api }) {
  const { user } = useAuth();
  const { viewIod } = useAdminIod();
  const effectiveIod = (user?.role === "admin" && viewIod) ? viewIod : (user?.iod || "IOD-1");
  const showNewBadge = useMemo(() => {
    try {
      const count = parseInt(localStorage.getItem(`rd_login_count_${user?.username}`) || "0", 10);
      return count < NEW_BADGE_LOGIN_THRESHOLD;
    } catch { return false; }
  }, [user?.username]);

  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab = TABS.includes(tabParam) ? tabParam : "daily";
  const dateParam = DATE_RE.test(searchParams.get("date") || "") ? searchParams.get("date") : null;
  const setTab = (t) => setSearchParams(t === "daily" ? {} : { tab: t });
  const openPast = (kind, params) => {
    const q = Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]));
    setSearchParams(kind === "daily" ? q : { tab: kind, ...q });
  };
  const setDate = (d) => setSearchParams(d && DATE_RE.test(d) ? { date: d } : {});

  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [genError, setGenError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  const reqRef = useRef(0);
  const pollRef = useRef(null);
  const baselineRef = useRef(null);

  const viewDate = dateParam || brief?.date || todayIST();

  const stopPoll = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const fetchBrief = useCallback(async () => {
    const id = ++reqRef.current;
    setLoading(true);
    setBrief(null);
    setLoadError(false);
    try {
      const res = await axios.get(`${api}/daily-brief`, { params: dateParam ? { date: dateParam } : {} });
      if (id !== reqRef.current) return;
      setBrief(res.data);
    } catch (e) {
      if (id !== reqRef.current) return;
      // 404 just means no brief for that date: the "No brief" panel shows.
      if (e?.response?.status !== 404) setLoadError(true);
    }
    setLoading(false);
  }, [api, dateParam]);

  // Changing date (or tab back to daily) clears the old brief and loads the new one.
  useEffect(() => {
    stopPoll();
    setGenerating(false);
    setTimedOut(false);
    setGenError(null);
    if (tab === "daily") fetchBrief();
    return stopPoll;
  }, [tab, fetchBrief, stopPoll]);

  // Polls only that date; replaces the brief in place (no loading state, so no flashing).
  const startPolling = (date) => {
    stopPoll();
    setTimedOut(false);
    setGenerating(true);
    const started = Date.now();
    pollRef.current = setInterval(async () => {
      if (Date.now() - started > POLL_GIVE_UP_MS) {
        stopPoll();
        setGenerating(false);
        setTimedOut(true);
        return;
      }
      try {
        const res = await axios.get(`${api}/daily-brief`, { params: { date } });
        if (res.data && res.data.generated_at !== baselineRef.current) {
          stopPoll();
          setBrief(res.data);
          setGenerating(false);
        }
      } catch { /* not there yet, or a blip: keep waiting */ }
    }, POLL_EVERY_MS);
  };

  const generateBrief = async () => {
    setGenError(null);
    baselineRef.current = brief?.generated_at ?? null;
    try {
      await axios.post(`${api}/generate-brief`, null, { params: { date: viewDate } });
      startPolling(viewDate);
    } catch (e) {
      setGenError(e?.response?.data?.detail || "Could not start the brief. Please try again.");
    }
  };

  const downloadPDF = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const dateParam = brief?.date || viewDate;
      const res = await axios.get(`${api}/daily-brief/pdf`, {
        params: { date: dateParam },
        responseType: "blob",
        timeout: 120000, // 2 min — Render cold-start can be slow
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Rhino_Drishti_Brief_${dateParam}.pdf`);
      document.body.appendChild(link);
      link.click();
      setTimeout(() => { link.remove(); window.URL.revokeObjectURL(url); }, 1000);
    } catch (e) {
      console.error("PDF download failed:", e);
      const msg = e.response?.data instanceof Blob
        ? await e.response.data.text().then(t => { try { return JSON.parse(t).detail; } catch { return t; } }).catch(() => e.message)
        : (e.response?.data?.detail || e.message || "PDF generation failed");
      setDownloadError(msg);
    } finally {
      setDownloading(false);
    }
  };

  // Safe string render helper - prevents React error #31
  const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    if (typeof val === 'number' || typeof val === 'boolean') return String(val);
    return JSON.stringify(val);
  };

  // Helper to render a news item (string or object)
  const renderNewsItem = (item, index) => {
    if (!item) return null;
    if (typeof item === 'string') {
      return (
        <li key={index} className="brief-bullet">
          <span className="text-primary font-mono text-xs mt-0.5 shrink-0">{String(index + 1).padStart(2, '0')}.</span>
          <span className="text-sm">{item}</span>
        </li>
      );
    }
    if (typeof item !== 'object') {
      return (
        <li key={index} className="brief-bullet">
          <span className="text-primary font-mono text-xs mt-0.5 shrink-0">{String(index + 1).padStart(2, '0')}.</span>
          <span className="text-sm">{String(item)}</span>
        </li>
      );
    }
    // Object format with title, summary, source_url, and analysis fields
    // brief items store date as `timestamp` (build_brief_item) or `published_at`
    const briefItemDate = (() => {
      const raw = item.timestamp || item.published_at;
      if (!raw) return null;
      try {
        const d = new Date(raw);
        return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
      } catch { return null; }
    })();

    return (
      <li key={index} className="border-b border-border/50 pb-4 last:border-0 last:pb-0">
        <div className="flex items-start gap-2">
          <span className="text-primary font-mono text-xs mt-1 shrink-0">{String(index + 1).padStart(2, '0')}.</span>
          <div className="flex-1 space-y-1.5">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <p className="text-sm font-medium flex-1">{safeStr(item.title)}</p>
              {item.older_item && (
                <span className="text-[10px] font-mono uppercase text-amber-500 border border-amber-500/40 px-1 shrink-0">Earlier item</span>
              )}
              {briefItemDate && (
                <span className="text-[10px] font-mono text-muted-foreground shrink-0">{briefItemDate}</span>
              )}
            </div>
            {item.summary && (
              <p className="text-xs text-muted-foreground leading-relaxed">{safeStr(item.summary)}</p>
            )}
            {item.why_it_matters && (
              <div className="text-xs border-l-2 border-primary/40 pl-2 mt-1">
                <span className="font-semibold text-primary/80">Why it matters: </span>
                <span className="text-muted-foreground">{safeStr(item.why_it_matters)}</span>
              </div>
            )}
            {item.potential_impact && (
              <div className="text-xs border-l-2 border-amber-500/40 pl-2">
                <span className="font-semibold text-amber-400/80">Potential impact: </span>
                <span className="text-muted-foreground">{safeStr(item.potential_impact)}</span>
              </div>
            )}
            {item.early_warning && (
              <div className="text-xs bg-red-500/10 border border-red-500/20 px-2 py-1 mt-1">
                <span className="font-semibold text-red-400">Early Warning: </span>
                <span className="text-red-300/80">{safeStr(item.early_warning)}</span>
              </div>
            )}
            {item.special_flags && Array.isArray(item.special_flags) && item.special_flags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {item.special_flags.map((flag, fi) => (
                  <Badge key={fi} variant="outline" className="text-[9px] rounded-none px-1.5 py-0 border-amber-500/40 text-amber-400">
                    {safeStr(flag)}
                  </Badge>
                ))}
              </div>
            )}
            {item.faultline_tags && Array.isArray(item.faultline_tags) && item.faultline_tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 mt-1">
                <span className="text-[8px] uppercase tracking-wider font-mono text-muted-foreground">Faultlines:</span>
                {item.faultline_tags.map((ft, ti) => (
                  <Badge
                    key={ti}
                    variant="outline"
                    title={ft.is_priority ? "Priority Area of Interest" : "Monitored faultline"}
                    className={`text-[9px] rounded-none px-1.5 py-0 ${
                      ft.is_priority
                        ? "border-red-500/60 text-red-400 bg-red-950/30 font-semibold"
                        : "border-cyan-500/40 text-cyan-400"
                    }`}
                  >
                    {ft.is_priority && "▲ "}{safeStr(ft.name)}
                  </Badge>
                ))}
              </div>
            )}
            {item.analyst_note && (
              <div className="mt-2 px-3 py-2 bg-violet-950/30 border border-violet-500/30 border-l-2 border-l-violet-400">
                <p className="text-[10px] uppercase tracking-widest text-violet-400 font-mono mb-0.5">Analyst Note</p>
                <p className="text-xs text-violet-200 leading-relaxed">{safeStr(item.analyst_note)}</p>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3 mt-1">
              {item.source_url && (
                <a 
                  href={safeStr(item.source_url)} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  <ExternalLink size={10} />
                  Source
                </a>
              )}
              {item.state && (
                <Badge variant="outline" className="text-[9px] rounded-none px-1 py-0">{safeStr(item.state)}</Badge>
              )}
              {item.severity && item.severity !== 'low' && (
                <Badge className={`text-[9px] rounded-none px-1 py-0 ${
                  item.severity === 'critical' ? 'bg-red-500' : 
                  item.severity === 'high' ? 'bg-orange-500' : 'bg-yellow-500'
                }`}>{safeStr(item.severity)}</Badge>
              )}
              {item.actors && (
                <span className="text-[9px] text-muted-foreground font-mono">Actors: {safeStr(item.actors)}</span>
              )}
              {item.attention_level && (
                <Badge variant="outline" className="text-[9px] rounded-none px-1 py-0 border-red-500/40 text-red-400">
                  {safeStr(item.attention_level)}
                </Badge>
              )}
            </div>
          </div>
        </div>
      </li>
    );
  };

  // Tab bar — shared across loading and full render
  const renderTabBar = () => (
    <div className="flex items-center gap-1 border-b border-border" data-testid="brief-tabs">
      <button onClick={() => setTab("daily")}
              className={`px-4 py-2 text-xs font-mono uppercase tracking-wider border-b-2 -mb-px flex items-center gap-2 transition-colors ${
                tab === "daily" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              data-testid="tab-daily">
        <FileText size={13} /> Daily
      </button>
      <button onClick={() => setTab("fortnightly")}
              className={`px-4 py-2 text-xs font-mono uppercase tracking-wider border-b-2 -mb-px flex items-center gap-2 transition-colors ${
                tab === "fortnightly" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              data-testid="tab-fortnightly">
        <Globe size={13} /> Fortnightly
        {showNewBadge && <span className="text-[8px] font-bold uppercase tracking-wider text-emerald-400 animate-pulse">New</span>}
      </button>
      <button onClick={() => setTab("monthly")}
              className={`px-4 py-2 text-xs font-mono uppercase tracking-wider border-b-2 -mb-px flex items-center gap-2 transition-colors ${
                tab === "monthly" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              data-testid="tab-monthly">
        <Layers size={13} /> Monthly Strategic
        {showNewBadge && <span className="text-[8px] font-bold uppercase tracking-wider text-emerald-400 animate-pulse">New</span>}
      </button>
      <button onClick={() => setTab("past")}
              className={`px-4 py-2 text-xs font-mono uppercase tracking-wider border-b-2 -mb-px flex items-center gap-2 transition-colors ${
                tab === "past" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              data-testid="tab-past">
        <Calendar size={13} /> Past
      </button>
    </div>
  );

  if (tab === "fortnightly" || tab === "monthly" || tab === "past") {
    return (
      <div className="space-y-4">
        {renderTabBar()}
        {tab === "fortnightly" && <FortnightlyBrief api={api} />}
        {tab === "monthly" && <MonthlyBrief api={api} />}
        {tab === "past" && (
          <PastBriefs api={api} iod={effectiveIod} isAdmin={user?.role === "admin"} onOpen={openPast} />
        )}
      </div>
    );
  }

  return (
    <BriefErrorBoundary>
    <div className="space-y-6" data-testid="daily-brief-page">
      {renderTabBar()}
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="brief-title" data-tour="brief-title">
            Daily Intelligence Brief
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <Calendar size={12} className="text-muted-foreground" />
            <input
              type="date"
              value={viewDate}
              max={todayIST()}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent border border-border px-2 py-0.5 text-xs font-mono text-muted-foreground rounded-none"
              aria-label="Brief date"
              data-testid="brief-date"
            />
            {dateParam && (
              <button onClick={() => setDate(null)} className="text-[10px] font-mono uppercase text-primary hover:underline">
                Latest
              </button>
            )}
            {brief?.generated_at && (
              <>
                <span className="text-muted-foreground">|</span>
                <p className="text-xs font-mono text-muted-foreground" data-testid="brief-generated-at">
                  Last generated: {fmtIst(brief.generated_at)}
                </p>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {brief && (
            <div className="flex flex-col items-end gap-1">
              <Tip text="Download this brief as a formatted PDF with RESTRICTED classification headers — suitable for distribution within authorized channels." side="bottom">
                <Button
                  variant="outline"
                  onClick={downloadPDF}
                  disabled={downloading}
                  className="uppercase text-xs font-bold tracking-wider rounded-none"
                  data-testid="download-pdf-btn"
                  data-tour="brief-export"
                >
                  <Download size={14} className={`mr-2 ${downloading ? "animate-pulse" : ""}`} />
                  {downloading ? "Generating..." : "Export PDF"}
                </Button>
              </Tip>
              {downloadError && (
                <p className="text-[10px] text-red-400 font-mono max-w-[260px] text-right">{downloadError}</p>
              )}
            </div>
          )}
          {brief && user?.role !== "viewer" && (
          <Tip text="Generate a fresh brief using all intelligence collected since the last brief. Runs in the background — takes ~30 seconds to complete." side="bottom">
            <span>
            <ConfirmAction title={`Regenerate the brief for ${viewDate}?`} description="Uses one AI call (under 1 US cent)." confirmLabel="Regenerate" onConfirm={generateBrief}>
            <Button
              disabled={generating}
              className="uppercase text-xs font-bold tracking-wider rounded-none"
              data-testid="generate-brief-btn"
              data-tour="brief-generate"
            >
              <RefreshCw size={14} className={`mr-2 ${generating ? "animate-spin" : ""}`} />
              {generating ? "Generating..." : "Regenerate Brief"}
            </Button>
            </ConfirmAction>
            </span>
          </Tip>
          )}
        </div>
      </div>

      {generating && (
        <div className="border border-primary bg-primary/5 p-3 text-xs font-mono text-primary flex items-center gap-2" data-testid="brief-generating">
          <RefreshCw size={14} className="animate-spin" />
          Preparing the brief for {viewDate}. This usually takes about 30 seconds; this page will update by itself.
        </div>
      )}
      {timedOut && (
        <div className="border border-amber-500/40 bg-amber-500/5 p-3 text-xs text-amber-400 flex items-center gap-3" role="alert" data-testid="brief-timed-out">
          <AlertTriangle size={14} className="shrink-0" />
          The brief is taking longer than expected. It may still finish in the background.
          <Button variant="outline" onClick={() => startPolling(viewDate)} className="ml-auto rounded-none uppercase text-[10px] tracking-wider">
            Check again
          </Button>
        </div>
      )}
      {genError && <p className="text-xs text-red-400 font-mono" role="alert">{genError}</p>}

      {loading ? (
        <div className="space-y-4" data-testid="daily-brief-loading">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="border border-border bg-card p-4 animate-pulse">
              <div className="h-4 bg-muted w-1/4 mb-3" />
              <div className="h-3 bg-muted w-full mb-2" />
              <div className="h-3 bg-muted w-5/6 mb-2" />
              <div className="h-3 bg-muted w-3/4" />
            </div>
          ))}
        </div>
      ) : loadError ? (
        <LoadError what="the daily brief" onRetry={fetchBrief} />
      ) : brief ? (
        <div className="space-y-4">
          {/* Analyst Summary */}
          <Card className="border border-border rounded-none bg-card border-l-4 border-l-primary">
            <CardHeader className="py-3 px-4 border-b border-border">
              <Tip text="AI-generated strategic overview summarizing the day's most significant developments, key trends and items requiring immediate attention." side="top">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                  <Shield size={16} className="text-primary" />
                  Analyst Assessment
                </CardTitle>
              </Tip>
            </CardHeader>
            <CardContent className="p-4" data-testid="analyst-summary">
              <p className="text-sm leading-relaxed">{safeStr(brief.analyst_summary)}</p>
            </CardContent>
          </Card>

          {/* NER Key Developments */}
          <Card className="border border-border rounded-none bg-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <Tip text="Top intelligence items strictly from Northeast Indian states (Assam, Manipur, Mizoram, Meghalaya, Nagaland, Tripura, Arunachal Pradesh, Sikkim). No international items appear here." side="top">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                  <AlertTriangle size={16} className="text-amber-400" />
                  NER Key Developments
                </CardTitle>
              </Tip>
            </CardHeader>
            <CardContent className="p-4" data-testid="key-developments">
              {brief.key_developments && brief.key_developments.length > 0 ? (
                <ul className="space-y-3">
                  {(() => {
                    const isPriority = (item) =>
                      item.state === "Meghalaya" ||
                      (item.faultline_tags || []).some(ft => ft.is_priority) ||
                      (item.title || "").toLowerCase().includes("bangladesh") ||
                      (item.summary || "").toLowerCase().includes("bangladesh border") ||
                      (item.special_flags || []).some(f => /bangladesh|border/i.test(f));
                    const priority = brief.key_developments.filter(isPriority);
                    const rest = brief.key_developments.filter(item => !isPriority(item));
                    return [...priority, ...rest].map((dev, i) => renderNewsItem(dev, i));
                  })()}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No key developments recorded.</p>
              )}
            </CardContent>
          </Card>

          {/* National News Section */}
          {brief.national_news && brief.national_news.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <Tip text="Relevant national-level developments affecting NER security — from Indian news sources covering MHA, defence ministry, central government and national security events." side="top">
                  <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                    <Newspaper size={16} className="text-blue-400" />
                    National News ({brief.national_news.length})
                  </CardTitle>
                </Tip>
              </CardHeader>
              <CardContent className="p-4" data-testid="national-news">
                <ul className="space-y-3">
                  {brief.national_news.map((news, i) => renderNewsItem(news, i))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Cross-Border Intelligence */}
          {((brief.cross_border_bangladesh && brief.cross_border_bangladesh.length > 0) ||
            (brief.cross_border_myanmar && brief.cross_border_myanmar.length > 0)) && (
            <Card className="border border-border rounded-none bg-card border-l-4 border-l-red-500" data-testid="cross-border-section">
              <CardHeader className="py-3 px-4 border-b border-border">
                <Tip text="Intelligence from Bangladesh and Myanmar with direct India-facing implications. Grouped by country and categorized as Diplomatic, Defence, Internal Politics or Economics." side="top">
                  <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                    <Shield size={16} className="text-red-400" />
                    Cross-Border Intelligence ({(brief.cross_border_bangladesh?.length || 0) + (brief.cross_border_myanmar?.length || 0)})
                  </CardTitle>
                </Tip>
              </CardHeader>
              <CardContent className="p-4 space-y-4" data-testid="cross-border-content">
                {brief.cross_border_bangladesh && brief.cross_border_bangladesh.length > 0 && (
                  <div>
                    <h3 className="text-xs uppercase tracking-widest font-bold text-amber-400 mb-2 font-mono">Bangladesh ({brief.cross_border_bangladesh.length})</h3>
                    <ul className="space-y-3">
                      {brief.cross_border_bangladesh.map((item, i) => (
                        <li key={i} className="border-b border-border/50 pb-2 last:border-0 last:pb-0">
                          <div className="flex items-start gap-2">
                            <span className="text-muted-foreground font-mono text-xs mt-0.5">{String(i + 1).padStart(2, '0')}.</span>
                            <div className="flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <p className="text-sm font-medium">{safeStr(item.title)}</p>
                                {item.category && (
                                  <Badge className="rounded-none text-[9px] px-1 py-0 border bg-blue-500/20 text-blue-300 border-blue-500/30">{item.category}</Badge>
                                )}
                                {item.severity && item.severity !== 'medium' && (
                                  <Badge className={`rounded-none text-[9px] px-1 py-0 border ${
                                    item.severity === 'critical' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                                    item.severity === 'high' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                                    'bg-muted text-muted-foreground border-border'
                                  }`}>{item.severity?.toUpperCase()}</Badge>
                                )}
                              </div>
                              {item.summary && <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{safeStr(item.summary)}</p>}
                              {item.analyst_note && (
                                <div className="mt-2 px-2 py-1.5 bg-violet-950/30 border border-violet-500/30 border-l-2 border-l-violet-400">
                                  <p className="text-[9px] uppercase tracking-widest text-violet-400 font-mono mb-0.5">Analyst Note</p>
                                  <p className="text-xs text-violet-200 leading-relaxed">{safeStr(item.analyst_note)}</p>
                                </div>
                              )}
                              {item.source && <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono">Source: {item.source}</p>}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {brief.cross_border_myanmar && brief.cross_border_myanmar.length > 0 && (
                  <div>
                    <h3 className="text-xs uppercase tracking-widest font-bold text-amber-400 mb-2 font-mono">Myanmar ({brief.cross_border_myanmar.length})</h3>
                    <ul className="space-y-3">
                      {brief.cross_border_myanmar.map((item, i) => (
                        <li key={i} className="border-b border-border/50 pb-2 last:border-0 last:pb-0">
                          <div className="flex items-start gap-2">
                            <span className="text-muted-foreground font-mono text-xs mt-0.5">{String(i + 1).padStart(2, '0')}.</span>
                            <div className="flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <p className="text-sm font-medium">{safeStr(item.title)}</p>
                                {item.category && (
                                  <Badge className="rounded-none text-[9px] px-1 py-0 border bg-blue-500/20 text-blue-300 border-blue-500/30">{item.category}</Badge>
                                )}
                                {item.severity && item.severity !== 'medium' && (
                                  <Badge className={`rounded-none text-[9px] px-1 py-0 border ${
                                    item.severity === 'critical' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                                    item.severity === 'high' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                                    'bg-muted text-muted-foreground border-border'
                                  }`}>{item.severity?.toUpperCase()}</Badge>
                                )}
                              </div>
                              {item.summary && <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{safeStr(item.summary)}</p>}
                              {item.analyst_note && (
                                <div className="mt-2 px-2 py-1.5 bg-violet-950/30 border border-violet-500/30 border-l-2 border-l-violet-400">
                                  <p className="text-[9px] uppercase tracking-widest text-violet-400 font-mono mb-0.5">Analyst Note</p>
                                  <p className="text-xs text-violet-200 leading-relaxed">{safeStr(item.analyst_note)}</p>
                                </div>
                              )}
                              {item.source && <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono">Source: {item.source}</p>}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* International News Section */}
          {brief.international_news && brief.international_news.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <Tip text="Strategic international items from sources like BBC, Al Jazeera and Reuters with direct or indirect relevance to NER security, India-China-Pakistan dynamics or regional geopolitics." side="top">
                  <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                    <Globe size={16} className="text-green-400" />
                    International News ({brief.international_news.length})
                  </CardTitle>
                </Tip>
              </CardHeader>
              <CardContent className="p-4" data-testid="international-news">
                <ul className="space-y-3">
                  {brief.international_news.map((news, i) => renderNewsItem(news, i))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Pattern Insights / Escalation Warnings */}
          {brief.pattern_insights && brief.pattern_insights.length > 0 && (
            <Card className="border border-border rounded-none bg-card border-l-4 border-l-orange-500">
              <CardHeader className="py-3 px-4 border-b border-border">
                <Tip text="Escalation warnings from the Pattern Detection Engine — recurring threat clusters detected in the past 7 days with CRITICAL or HIGH escalation risk." side="top">
                  <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                    <GitBranch size={16} className="text-orange-400" />
                    Pattern Detection - Escalation Warnings ({brief.pattern_insights.length})
                  </CardTitle>
                </Tip>
              </CardHeader>
              <CardContent className="p-4" data-testid="pattern-insights">
                <ul className="space-y-3">
                  {brief.pattern_insights.map((p, i) => (
                    <li key={i} className="border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <div className="flex items-start gap-2">
                        <span className="text-orange-400 font-mono text-xs mt-1">{String(i + 1).padStart(2, '0')}.</span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium">{safeStr(p.region)} - {safeStr(p.detail)}</p>
                            <Badge className={`rounded-none text-[9px] px-1 py-0 border ${
                              p.escalation_risk === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                              p.escalation_risk === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                              'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                            }`}>
                              {safeStr(p.escalation_risk)}
                            </Badge>
                          </div>
                          <p className="text-[10px] font-mono text-muted-foreground mt-1">
                            {p.event_count} events / {p.window_days}d window | Avg Priority: {p.avg_priority_score}
                          </p>
                          {p.sample_titles && p.sample_titles.length > 0 && (
                            <div className="mt-1">
                              {p.sample_titles.map((t, ti) => (
                                <p key={ti} className="text-xs text-muted-foreground truncate">- {safeStr(t)}</p>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Uploaded Document Insights */}
          {brief.uploaded_insights && brief.uploaded_insights.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <Upload size={16} className="text-purple-400" />
                  Uploaded Document Insights ({brief.uploaded_insights.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4" data-testid="uploaded-insights">
                <ul className="space-y-3">
                  {brief.uploaded_insights.map((doc, i) => (
                    <li key={i} className="border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <p className="text-sm font-medium">{safeStr(doc.filename)}</p>
                      {doc.ai_analysis && (
                        <p className="text-xs text-muted-foreground mt-1">{safeStr(doc.ai_analysis)}</p>
                      )}
                      {doc.region && (
                        <Badge variant="outline" className="text-[9px] rounded-none px-1 py-0 mt-1">{safeStr(doc.region)}</Badge>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* State-wise Highlights */}
          <Card className="border border-border rounded-none bg-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <FileText size={16} className="text-primary" />
                State-wise Highlights
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4" data-testid="state-highlights">
              {brief.state_highlights && Object.keys(brief.state_highlights).length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(brief.state_highlights).map(([state, highlight]) => (
                    <div key={state} className="p-3 border border-border bg-background/50">
                      <Badge variant="outline" className="rounded-none uppercase text-[10px] tracking-wider mb-2">
                        {state}
                      </Badge>
                      <p className="text-sm text-muted-foreground leading-relaxed">{safeStr(highlight)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No state-specific highlights available.</p>
              )}
            </CardContent>
          </Card>

          {/* Cross-Border Insights */}
          <Card className="border border-border rounded-none bg-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Globe size={16} className="text-amber-400" />
                Cross-Border Insights
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4" data-testid="cross-border-insights">
              <p className="text-sm leading-relaxed">
                {safeStr(brief.cross_border_insights) || "No significant cross-border developments to report."}
              </p>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="text-center py-16 border border-border bg-card" data-testid="no-brief-for-date">
          <FileText size={40} className="mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground text-sm mb-4">No brief for this date ({viewDate}).</p>
          {user?.role !== "viewer" && (
          <ConfirmAction title={`Generate the brief for ${viewDate}?`} description="Uses one AI call (under 1 US cent)." confirmLabel="Generate" onConfirm={generateBrief}>
            <Button disabled={generating} className="rounded-none uppercase text-xs tracking-wider" data-testid="generate-first-brief-btn">
              Generate Brief
            </Button>
          </ConfirmAction>
          )}
        </div>
      )}
    </div>
    </BriefErrorBoundary>
  );
}
