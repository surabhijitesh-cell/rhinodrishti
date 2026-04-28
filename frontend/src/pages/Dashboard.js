import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Shield, AlertTriangle, Activity, TrendingUp,
  ChevronRight, RefreshCw, Target, ArrowUp,
  Rss, Eye, EyeOff, Clock, CheckCircle2, Loader2,
  Filter, Languages, BellRing, GitBranch, Check, Wifi, WifiOff,
  ArrowUpDown, Youtube, Facebook, Send, Twitter, ChevronDown, ChevronUp,
  Play, Zap, Radio
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "../components/ui/select";
import NERMap from "../components/NERMap";
import IntelligenceCard from "../components/IntelligenceCard";
import { useIntelligenceWS } from "../hooks/useIntelligenceWS";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie
} from "recharts";

const SEVERITY_COLORS = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#eab308",
  low: "#a3e635",
};

function StatBox({ label, value, icon: Icon, color, sub, testId, onClick }) {
  return (
    <div
      className={`stat-card flex items-center gap-4 ${onClick ? "cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-all duration-200" : ""}`}
      data-testid={testId}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className={`p-2.5 ${color}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold font-['Barlow_Condensed'] tracking-tight">{value}</p>
        <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">{label}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
      {onClick && <ChevronRight size={14} className="ml-auto text-muted-foreground" />}
    </div>
  );
}

// ─── helpers ────────────────────────────────────────────────────────────────
function formatIST(isoStr) {
  if (!isoStr) return null;
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata", day: "2-digit", month: "short",
      hour: "2-digit", minute: "2-digit", hour12: true,
    });
  } catch { return null; }
}

function timeAgo(isoStr) {
  if (!isoStr) return "never";
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ─── individual scanner panel ────────────────────────────────────────────────
function ScannerPanel({
  label, icon: Icon, accentColor, barColor, bgAccent, borderAccent,
  isConfigured, configNote, isActive, activeLabel,
  progress, progressLabel, statsChips,
  lastFetched, onTrigger, triggering, children, testId,
}) {
  const [expanded, setExpanded] = useState(false);

  const statusBadge = isActive
    ? <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${bgAccent} ${accentColor} ${borderAccent} animate-pulse`}>{activeLabel || "ACTIVE"}</Badge>
    : isConfigured
      ? <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-muted/30 text-muted-foreground border-border">IDLE</Badge>
      : <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-orange-500/10 text-orange-400 border-orange-500/30">NOT CONFIGURED</Badge>;

  return (
    <Card className={`rounded-none border bg-card overflow-hidden transition-all duration-200 ${isActive ? borderAccent : "border-border"}`} data-testid={testId}>
      {/* Header row */}
      <div
        className="flex items-center gap-2.5 px-4 py-2.5 border-b border-border cursor-pointer select-none hover:bg-muted/10 transition-colors"
        onClick={() => setExpanded(v => !v)}
      >
        <div className={`p-1.5 rounded-sm ${bgAccent}`}>
          <Icon size={13} className={accentColor} />
        </div>
        <span className={`text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-bold ${isConfigured ? "text-foreground" : "text-muted-foreground"}`}>
          {label}
        </span>
        {statusBadge}
        <div className="ml-auto flex items-center gap-2">
          {lastFetched && (
            <span className="text-[10px] font-mono text-muted-foreground hidden sm:block">
              {timeAgo(lastFetched)}
            </span>
          )}
          {isConfigured && onTrigger && (
            <Button
              variant="ghost" size="sm"
              className={`h-6 px-2 text-[10px] rounded-none font-mono ${accentColor} hover:${bgAccent} border ${borderAccent} opacity-70 hover:opacity-100`}
              onClick={e => { e.stopPropagation(); onTrigger(); }}
              disabled={triggering}
            >
              {triggering ? <Loader2 size={10} className="animate-spin" /> : <Zap size={10} />}
            </Button>
          )}
          {expanded ? <ChevronUp size={12} className="text-muted-foreground" /> : <ChevronDown size={12} className="text-muted-foreground" />}
        </div>
      </div>

      {/* Progress bar — always visible */}
      <div className="px-4 pt-2 pb-0">
        <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground mb-1">
          <span>{progressLabel}</span>
          {statsChips && (
            <div className="flex items-center gap-2">
              {statsChips.map((chip, i) => (
                <span key={i} className={chip.color || "text-muted-foreground"}>
                  {chip.label}: <span className="font-bold">{chip.value}</span>
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="w-full h-1.5 bg-muted/20 overflow-hidden mb-2.5">
          <div
            className={`h-full transition-all duration-700 ${barColor} ${isActive ? "animate-pulse" : ""}`}
            style={{ width: `${isConfigured ? progress : 0}%` }}
          />
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <CardContent className="px-4 pb-3 pt-0 space-y-2 border-t border-border/50 bg-muted/5">
          {!isConfigured && configNote && (
            <p className="text-[10px] text-orange-400/80 font-mono pt-2">{configNote}</p>
          )}
          {children}
          {lastFetched && (
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground pt-1 border-t border-border/30">
              <Clock size={9} />
              <span>Last: {formatIST(lastFetched) || timeAgo(lastFetched)}</span>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

// ─── main component ──────────────────────────────────────────────────────────
function SourceScanners({ api }) {
  const [rss, setRss] = useState(null);
  const [socialStatus, setSocialStatus] = useState(null);
  const [ytData, setYtData] = useState({ channels: [], searches: [] });
  const [fbData, setFbData] = useState({ pages: [] });
  const [tgData, setTgData] = useState({ channels: [] });
  const [twData, setTwData] = useState({ accounts: [], searches: [] });
  const [triggering, setTriggering] = useState({});

  // Poll RSS status fast when scanning, slow otherwise
  useEffect(() => {
    const fetchRss = async () => {
      try { const r = await axios.get(`${api}/scan-status`); setRss(r.data); } catch { /* silent */ }
    };
    fetchRss();
    const id = setInterval(fetchRss, 4000);
    return () => clearInterval(id);
  }, [api]);

  // Poll social data every 60s
  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [status, yt, ytS, fb, tg, twA, twS] = await Promise.allSettled([
          axios.get(`${api}/social/status`),
          axios.get(`${api}/social/youtube/channels`),
          axios.get(`${api}/social/youtube/searches`),
          axios.get(`${api}/social/facebook/pages`),
          axios.get(`${api}/social/telegram/channels`),
          axios.get(`${api}/social/twitter/accounts`),
          axios.get(`${api}/social/twitter/searches`),
        ]);
        if (status.status === "fulfilled") setSocialStatus(status.value.data);
        setYtData({
          channels: yt.status === "fulfilled" ? yt.value.data.channels || [] : [],
          searches: ytS.status === "fulfilled" ? ytS.value.data.searches || [] : [],
        });
        setFbData({ pages: fb.status === "fulfilled" ? fb.value.data.pages || [] : [] });
        setTgData({ channels: tg.status === "fulfilled" ? tg.value.data.channels || [] : [] });
        setTwData({
          accounts: twA.status === "fulfilled" ? twA.value.data.accounts || [] : [],
          searches: twS.status === "fulfilled" ? twS.value.data.searches || [] : [],
        });
      } catch { /* silent */ }
    };
    fetchAll();
    const id = setInterval(fetchAll, 60000);
    return () => clearInterval(id);
  }, [api]);

  const trigger = async (platform, endpoint) => {
    setTriggering(t => ({ ...t, [platform]: true }));
    try { await axios.post(`${api}${endpoint}`); } catch { /* silent */ }
    setTimeout(() => setTriggering(t => ({ ...t, [platform]: false })), 5000);
  };

  // ── derived ──
  const rssScanning  = rss?.is_scanning || false;
  const rssProgress  = rssScanning ? (rss?.progress || 0) : 100;
  const lastResult   = rss?.last_scan_result;

  const ytActive = socialStatus?.youtube?.configured;
  const ytChannels = ytData.channels.filter(c => c.active);
  const ytLastFetched = ytChannels.reduce((latest, c) => {
    if (!c.last_fetched) return latest;
    return !latest || new Date(c.last_fetched) > new Date(latest) ? c.last_fetched : latest;
  }, null);

  const fbActive = socialStatus?.facebook?.configured;
  const fbPages  = fbData.pages.filter(p => p.active);
  const fbLastFetched = fbPages.reduce((latest, p) => {
    if (!p.last_fetched) return latest;
    return !latest || new Date(p.last_fetched) > new Date(latest) ? p.last_fetched : latest;
  }, null);

  const tgActive = socialStatus?.telegram?.configured;
  const tgChannels = tgData.channels.filter(c => c.active);
  const tgLastFetched = tgChannels.reduce((latest, c) => {
    if (!c.last_fetched) return latest;
    return !latest || new Date(c.last_fetched) > new Date(latest) ? c.last_fetched : latest;
  }, null);

  const twConfigured = socialStatus?.twitter?.configured;
  const twAccounts = twData.accounts.filter(a => a.active);
  const twSearches = twData.searches.filter(s => s.active);
  const twLastRun = twData.searches.reduce((latest, s) => {
    if (!s.last_run) return latest;
    return !latest || new Date(s.last_run) > new Date(latest) ? s.last_run : latest;
  }, null);

  return (
    <div className="space-y-2">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio size={13} className="text-primary" />
          <span className="text-xs uppercase tracking-widest font-['Barlow_Condensed'] font-bold text-muted-foreground">
            Intelligence Source Monitors
          </span>
        </div>
        <Button
          variant="ghost" size="sm"
          className="h-6 px-2 text-[10px] rounded-none font-mono text-muted-foreground border border-border hover:text-foreground"
          onClick={() => trigger("all", "/social/fetch-all")}
          disabled={triggering["all"]}
        >
          {triggering["all"] ? <Loader2 size={9} className="animate-spin mr-1" /> : <RefreshCw size={9} className="mr-1" />}
          FETCH ALL
        </Button>
      </div>

      {/* ── RSS ── */}
      <ScannerPanel
        label="RSS Feeds"
        icon={Rss}
        accentColor="text-green-400"
        bgAccent="bg-green-500/10"
        borderAccent="border-green-500/30"
        barColor="bg-green-500"
        isConfigured={true}
        isActive={rssScanning}
        activeLabel="SCANNING"
        progress={rssProgress}
        progressLabel={rssScanning ? `Scanning… ${rss?.progress || 0}%` : "Last scan complete"}
        statsChips={[
          { label: "Feeds", value: rss?.total_sources || "—" },
          ...(lastResult ? [
            { label: "Articles", value: lastResult.total_articles },
            { label: "New", value: lastResult.new_relevant, color: "text-green-400" },
          ] : []),
        ]}
        lastFetched={rss?.last_scan_at}
        onTrigger={() => trigger("rss", "/fetch-news")}
        triggering={triggering["rss"]}
        testId="scanner-rss"
      >
        {rssScanning && rss?.current_source && (
          <div className="flex items-center gap-1.5 text-[10px] font-mono pt-2">
            <Loader2 size={9} className="animate-spin text-green-400" />
            <span className="text-muted-foreground">Scanning:</span>
            <span className="text-foreground truncate">{rss.current_source}</span>
          </div>
        )}
        {rssScanning && rss?.scan_log?.length > 0 && (
          <div className="max-h-16 overflow-y-auto space-y-0.5">
            {rss.scan_log.slice(-4).map((s, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground">
                <CheckCircle2 size={8} className="text-green-500 shrink-0" />
                <span className="truncate">{s}</span>
              </div>
            ))}
          </div>
        )}
        {lastResult && !lastResult.error && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono pt-2">
            {lastResult.filtered_out > 0 && (
              <span className="text-orange-400"><Filter size={8} className="inline mr-0.5" />Filtered: <b>{lastResult.filtered_out}</b></span>
            )}
            {lastResult.translated > 0 && (
              <span className="text-blue-400"><Languages size={8} className="inline mr-0.5" />Translated: <b>{lastResult.translated}</b></span>
            )}
          </div>
        )}
      </ScannerPanel>

      {/* ── YouTube ── */}
      <ScannerPanel
        label="YouTube"
        icon={Youtube}
        accentColor="text-red-400"
        bgAccent="bg-red-500/10"
        borderAccent="border-red-500/30"
        barColor="bg-red-500"
        isConfigured={!!ytActive}
        configNote="Set YOUTUBE_API_KEY in Render env → Google Cloud Console → YouTube Data API v3"
        isActive={triggering["youtube"]}
        activeLabel="FETCHING"
        progress={ytActive ? 100 : 0}
        progressLabel={ytActive ? `${ytChannels.length} channels · ${ytData.searches.length} searches active` : "API key not configured"}
        statsChips={ytActive ? [
          { label: "Channels", value: ytChannels.length },
          { label: "Searches", value: ytData.searches.filter(s => s.active).length },
        ] : []}
        lastFetched={ytLastFetched}
        onTrigger={ytActive ? () => trigger("youtube", "/social/fetch-all") : null}
        triggering={triggering["youtube"] || triggering["all"]}
        testId="scanner-youtube"
      >
        {ytChannels.slice(0, 5).map((ch, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
            <Play size={8} className="text-red-400 shrink-0" />
            <span className="truncate flex-1">{ch.name}</span>
            {ch.last_fetched && <span className="shrink-0">{timeAgo(ch.last_fetched)}</span>}
          </div>
        ))}
        {ytChannels.length > 5 && (
          <p className="text-[10px] font-mono text-muted-foreground">+{ytChannels.length - 5} more channels</p>
        )}
      </ScannerPanel>

      {/* ── Facebook ── */}
      <ScannerPanel
        label="Facebook"
        icon={Facebook}
        accentColor="text-blue-400"
        bgAccent="bg-blue-500/10"
        borderAccent="border-blue-500/30"
        barColor="bg-blue-500"
        isConfigured={!!fbActive}
        configNote="Set FACEBOOK_APP_ID + FACEBOOK_APP_SECRET in Render env → developers.facebook.com"
        isActive={triggering["facebook"]}
        activeLabel="FETCHING"
        progress={fbActive ? 100 : 0}
        progressLabel={fbActive ? `${fbPages.length} pages monitored` : "App credentials not configured"}
        statsChips={fbActive ? [{ label: "Pages", value: fbPages.length }] : []}
        lastFetched={fbLastFetched}
        onTrigger={fbActive ? () => trigger("facebook", "/social/fetch-all") : null}
        triggering={triggering["facebook"] || triggering["all"]}
        testId="scanner-facebook"
      >
        {fbPages.slice(0, 5).map((p, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
            <Facebook size={8} className="text-blue-400 shrink-0" />
            <span className="truncate flex-1">{p.name}</span>
            {p.last_fetched && <span className="shrink-0">{timeAgo(p.last_fetched)}</span>}
          </div>
        ))}
        {fbPages.length > 5 && (
          <p className="text-[10px] font-mono text-muted-foreground">+{fbPages.length - 5} more pages</p>
        )}
      </ScannerPanel>

      {/* ── Telegram ── */}
      <ScannerPanel
        label="Telegram"
        icon={Send}
        accentColor="text-sky-400"
        bgAccent="bg-sky-500/10"
        borderAccent="border-sky-500/30"
        barColor="bg-sky-500"
        isConfigured={!!tgActive}
        configNote="Run python backend/telegram_setup.py to generate TELEGRAM_SESSION_STRING, then add to Render env"
        isActive={triggering["telegram"]}
        activeLabel="FETCHING"
        progress={tgActive ? 100 : 0}
        progressLabel={tgActive ? `${tgChannels.length} channels monitored` : "Session not configured"}
        statsChips={tgActive ? [{ label: "Channels", value: tgChannels.length }] : []}
        lastFetched={tgLastFetched}
        onTrigger={tgActive ? () => trigger("telegram", "/social/fetch-all") : null}
        triggering={triggering["telegram"] || triggering["all"]}
        testId="scanner-telegram"
      >
        {tgChannels.slice(0, 5).map((ch, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
            <Send size={8} className="text-sky-400 shrink-0" />
            <span className="truncate flex-1">@{ch.username}</span>
            {ch.last_fetched && <span className="shrink-0">{timeAgo(ch.last_fetched)}</span>}
          </div>
        ))}
        {tgChannels.length > 5 && (
          <p className="text-[10px] font-mono text-muted-foreground">+{tgChannels.length - 5} more channels</p>
        )}
      </ScannerPanel>

      {/* ── Twitter / X ── */}
      <ScannerPanel
        label="X / Twitter"
        icon={Twitter}
        accentColor="text-slate-300"
        bgAccent="bg-slate-500/10"
        borderAccent="border-slate-500/30"
        barColor="bg-slate-400"
        isConfigured={true}
        configNote=""
        isActive={triggering["twitter"]}
        activeLabel="FETCHING"
        progress={100}
        progressLabel={
          twConfigured
            ? `Official API · ${twAccounts.length} accounts · ${twSearches.length} searches`
            : `Nitter fallback · ${twAccounts.length} accounts monitored`
        }
        statsChips={[
          { label: "Accounts", value: twAccounts.length },
          ...(twConfigured ? [{ label: "Searches", value: twSearches.length }] : []),
        ]}
        lastFetched={twLastRun}
        onTrigger={() => trigger("twitter", "/social/fetch-all")}
        triggering={triggering["twitter"] || triggering["all"]}
        testId="scanner-twitter"
      >
        <div className="flex items-center gap-1.5 pt-1">
          <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${twConfigured ? "bg-slate-500/20 text-slate-300 border-slate-500/30" : "bg-orange-500/10 text-orange-400 border-orange-500/30"}`}>
            {twConfigured ? "OFFICIAL API" : "NITTER MODE"}
          </Badge>
          {!twConfigured && (
            <span className="text-[10px] font-mono text-muted-foreground">
              Set TWITTER_BEARER_TOKEN for keyword search
            </span>
          )}
        </div>
        {twAccounts.slice(0, 5).map((a, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
            <Twitter size={8} className="text-slate-400 shrink-0" />
            <span className="truncate flex-1">@{a.handle}</span>
            <span className="text-muted-foreground/60">{a.category}</span>
          </div>
        ))}
        {twAccounts.length > 5 && (
          <p className="text-[10px] font-mono text-muted-foreground">+{twAccounts.length - 5} more accounts</p>
        )}
      </ScannerPanel>
    </div>
  );
}

function UnacknowledgedAlerts({ api }) {
  const [alerts, setAlerts] = useState([]);
  const [dismissing, setDismissing] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get(`${api}/alerts/unacknowledged`);
        setAlerts(res.data.alerts || []);
      } catch (e) { /* silent */ }
    };
    fetch();
    const interval = setInterval(fetch, 30000);
    return () => clearInterval(interval);
  }, [api]);

  const acknowledge = async (id) => {
    setDismissing(id);
    try {
      await axios.post(`${api}/intelligence/${id}/acknowledge`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch (e) { console.error(e); }
    setDismissing(null);
  };

  if (alerts.length === 0) return null;

  return (
    <Card className="border-2 border-red-500/40 rounded-none bg-red-950/20 animate-slide-in" data-testid="unacknowledged-alerts-panel">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-red-500/30">
        <BellRing size={14} className="text-red-400 animate-pulse" />
        <span className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold text-red-400">
          Unacknowledged Critical Alerts ({alerts.length})
        </span>
        <Button
          variant="ghost" size="sm"
          className="ml-auto text-xs text-red-400"
          onClick={() => navigate("/alerts")}
        >
          View All <ChevronRight size={12} />
        </Button>
      </div>
      <CardContent className="p-3 space-y-2 max-h-48 overflow-y-auto">
        {alerts.slice(0, 5).map((item) => (
          <div key={item.id} className="flex items-center gap-3 p-2 border border-red-500/20 bg-red-950/30" data-testid={`unack-alert-${item.id}`}>
            <AlertTriangle size={14} className="text-red-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium leading-tight truncate">{item.title}</p>
              <p className="text-[10px] text-muted-foreground font-mono">{item.state} | {item.source}</p>
            </div>
            <Badge className={`shrink-0 rounded-none uppercase text-[10px] px-1.5 py-0 border ${item.severity === "critical" ? "severity-critical" : "severity-high"}`}>
              {item.severity}
            </Badge>
            <Button
              variant="outline" size="sm"
              className="h-7 text-[10px] rounded-none border-green-500/30 text-green-400 hover:bg-green-500/10"
              onClick={() => acknowledge(item.id)}
              disabled={dismissing === item.id}
              data-testid={`ack-btn-${item.id}`}
            >
              <Check size={12} className="mr-1" />
              ACK
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function PatternInsights({ api }) {
  const [patterns, setPatterns] = useState([]);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get(`${api}/patterns`);
        setPatterns(res.data.patterns || []);
      } catch (e) { /* silent */ }
    };
    fetch();
  }, [api]);

  if (patterns.length === 0) return null;

  const riskColors = {
    CRITICAL: "text-red-400 bg-red-500/20 border-red-500/30",
    HIGH: "text-orange-400 bg-orange-500/20 border-orange-500/30",
    MODERATE: "text-yellow-400 bg-yellow-500/20 border-yellow-500/30",
    LOW: "text-green-400 bg-green-500/20 border-green-500/30",
  };

  return (
    <Card className="border border-border rounded-none bg-card" data-testid="pattern-insights-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <div className="flex items-center gap-2">
          <GitBranch size={14} className="text-primary" />
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
            Detected Patterns ({patterns.length})
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-3 space-y-2 max-h-64 overflow-y-auto">
        {patterns.slice(0, 8).map((p, i) => (
          <div key={i} className="p-2 border border-border space-y-1" data-testid={`pattern-${i}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">
                {p.region} - {p.detail || p.pattern_type}
              </span>
              <Badge className={`rounded-none text-[10px] px-1.5 py-0 border ${riskColors[p.escalation_risk] || riskColors.LOW}`}>
                {p.escalation_risk}
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono">
              <span>{p.event_count} events / {p.window_days}d</span>
              <span>Avg Priority: {p.avg_priority_score}</span>
            </div>
            {p.sample_titles && p.sample_titles[0] && (
              <p className="text-xs text-muted-foreground truncate">Latest: {p.sample_titles[0]}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function Dashboard({ stats: propStats, api }) {
  const [recentItems, setRecentItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [localStats, setLocalStats] = useState(null);
  const [sortBy, setSortBy] = useState("published_at");
  const [minPriority, setMinPriority] = useState("");
  const navigate = useNavigate();

  // WebSocket real-time connection
  const { connected: wsConnected, newItems: wsNewItems, criticalAlerts, clearNewItems } = useIntelligenceWS(api);

  const stats = propStats || localStats;

  useEffect(() => {
    fetchRecent();
    if (!propStats) {
      fetchStats();
    }
  }, [api, propStats]);

  // Refetch items when sort/filter changes
  useEffect(() => {
    fetchRecent();
  }, [sortBy, minPriority]);

  // Auto-refresh stats when new WS items arrive
  useEffect(() => {
    if (wsNewItems.length > 0) {
      fetchStats();
    }
  }, [wsNewItems.length]);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${api}/dashboard/stats`);
      setLocalStats(res.data);
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  };

  const fetchRecent = async () => {
    try {
      const params = new URLSearchParams();
      params.set("limit", "6");
      if (sortBy) params.set("sort_by", sortBy);
      params.set("sort_order", "desc");
      if (minPriority) params.set("min_priority", minPriority);
      const res = await axios.get(`${api}/intelligence?${params.toString()}`);
      setRecentItems(res.data.items || []);
    } catch (e) {
      console.error("Failed to fetch recent items:", e);
    }
  };

  const handleFetchNews = async () => {
    setLoading(true);
    try {
      await axios.post(`${api}/fetch-news`);
    } catch (e) {
      console.error("Fetch failed:", e);
    }
    setTimeout(() => {
      setLoading(false);
      fetchRecent();
    }, 3000);
  };

  const threatData = stats?.threat_distribution
    ? Object.entries(stats.threat_distribution).map(([k, v]) => ({ name: k, value: v }))
    : [];

  const trendData = stats?.trend_7d || [];

  const stateStatsMap = {};
  if (stats?.state_distribution) {
    Object.entries(stats.state_distribution).forEach(([state, count]) => {
      stateStatsMap[state] = {
        count,
        critical: stats.recent_critical?.filter((i) => i.state === state && i.severity === "critical").length || 0,
        high: stats.recent_critical?.filter((i) => i.state === state && i.severity === "high").length || 0,
      };
    });
  }
  // Ensure Bangladesh/Myanmar always appear on map even if not yet in state_distribution
  ["Bangladesh", "Myanmar"].forEach((region) => {
    if (!stateStatsMap[region]) {
      const crossBorderItems = stats?.recent_critical?.filter(
        (i) => i.countries_involved?.includes(region) || i.state === region
      ) || [];
      if (crossBorderItems.length > 0) {
        stateStatsMap[region] = {
          count: crossBorderItems.length,
          critical: crossBorderItems.filter((i) => i.severity === "critical").length,
          high: crossBorderItems.filter((i) => i.severity === "high").length,
        };
      }
    }
  });

  const PIE_COLORS = ["#ef4444", "#f59e0b", "#eab308", "#a3e635", "#3b82f6", "#8b5cf6", "#06b6d4", "#6366f1"];

  const handleDeleteItem = async (itemId) => {
    try {
      await axios.delete(`${api}/intelligence/${itemId}`);
      setRecentItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="dashboard-title">
            Intelligence Overview
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            NER Situation Awareness Dashboard
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[10px] font-mono" data-testid="ws-status">
            {wsConnected ? (
              <>
                <Wifi size={12} className="text-green-400" />
                <span className="text-green-400 uppercase">Live</span>
              </>
            ) : (
              <>
                <WifiOff size={12} className="text-muted-foreground" />
                <span className="text-muted-foreground uppercase">Offline</span>
              </>
            )}
          </div>
          <Button
            onClick={handleFetchNews}
            disabled={loading}
            className="uppercase text-xs font-bold tracking-wider rounded-none"
            data-testid="fetch-news-btn"
          >
            <RefreshCw size={14} className={`mr-2 ${loading ? "animate-spin" : ""}`} />
            Fetch Intel
          </Button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <StatBox
          label="Total Items"
          value={stats?.total_items || 0}
          icon={Activity}
          color="bg-primary/10 text-primary"
          sub={`${stats?.today_count || 0} today`}
          testId="stat-total"
          onClick={() => navigate("/feed")}
        />
        <StatBox
          label="Critical"
          value={stats?.critical_count || 0}
          icon={AlertTriangle}
          color="bg-red-500/10 text-red-400"
          testId="stat-critical"
          onClick={() => navigate("/feed?severity=critical")}
        />
        <StatBox
          label="High"
          value={stats?.high_count || 0}
          icon={Target}
          color="bg-amber-500/10 text-amber-400"
          testId="stat-high"
          onClick={() => navigate("/feed?severity=high")}
        />
        <StatBox
          label="Medium"
          value={stats?.medium_count || 0}
          icon={Shield}
          color="bg-yellow-500/10 text-yellow-400"
          testId="stat-medium"
          onClick={() => navigate("/feed?severity=medium")}
        />
        <StatBox
          label="Low"
          value={stats?.low_count || 0}
          icon={ArrowUp}
          color="bg-green-500/10 text-green-400"
          testId="stat-low"
          onClick={() => navigate("/feed?severity=low")}
        />
      </div>

      {/* Source Scanners */}
      <SourceScanners api={api} />

      {/* Unacknowledged Critical Alerts - Sticky Panel */}
      <UnacknowledgedAlerts api={api} />

      {/* WebSocket Live Feed - Shows items as they arrive */}
      {wsNewItems.length > 0 && (
        <Card className="border border-green-500/30 rounded-none bg-green-950/10 animate-slide-in" data-testid="ws-live-feed">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-green-500/20">
            <Wifi size={12} className="text-green-400 animate-pulse" />
            <span className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold text-green-400">
              Live Feed ({wsNewItems.length} new)
            </span>
            <Button
              variant="ghost" size="sm"
              className="ml-auto text-xs text-green-400 hover:text-green-300"
              onClick={() => { clearNewItems(); fetchRecent(); fetchStats(); }}
              data-testid="ws-refresh-btn"
            >
              <RefreshCw size={12} className="mr-1" /> Refresh Dashboard
            </Button>
          </div>
          <CardContent className="p-3 space-y-1.5 max-h-40 overflow-y-auto">
            {wsNewItems.slice(0, 8).map((item, i) => (
              <div key={item.id || i} className="flex items-center gap-3 p-1.5 text-xs" data-testid={`ws-item-${i}`}>
                <Badge className={`shrink-0 rounded-none uppercase text-[9px] px-1 py-0 border ${
                  item.severity === "critical" ? "severity-critical" :
                  item.severity === "high" ? "severity-high" :
                  item.severity === "medium" ? "severity-medium" : "severity-low"
                }`}>
                  {item.severity}
                </Badge>
                <span className="truncate flex-1">{item.title}</span>
                <span className="text-muted-foreground font-mono shrink-0">P:{item.priority_score}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Map + Recent Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* NER Map */}
        <div className="lg:col-span-7">
          <NERMap
            stateStats={stateStatsMap}
            onStateClick={(state) => navigate(`/feed?state=${encodeURIComponent(state)}`)}
          />
        </div>

        {/* Recent Critical Alerts */}
        <div className="lg:col-span-5">
          <Card className="border border-border rounded-none bg-card h-full">
            <CardHeader className="py-3 px-4 border-b border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
                  Recent Critical Alerts
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-primary uppercase tracking-wider"
                  onClick={() => navigate("/alerts")}
                  data-testid="view-all-alerts-btn"
                >
                  View All <ChevronRight size={14} />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-3 space-y-3 max-h-[400px] overflow-y-auto" data-testid="recent-alerts-list">
              {(stats?.recent_critical || []).map((item, i) => (
                <div
                  key={item.id || i}
                  className={`p-3 border border-border ${item.severity === "critical" ? "border-l-4 border-l-red-500 glow-critical" : "border-l-4 border-l-amber-500"}`}
                  data-testid={`recent-alert-${i}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-medium leading-tight line-clamp-2">{item.title}</h4>
                    <Badge className={`shrink-0 rounded-none uppercase text-[10px] px-1.5 py-0 border ${item.severity === "critical" ? "severity-critical" : "severity-high"}`}>
                      {item.severity}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground font-mono">
                    <span>{item.state}</span>
                    <span>|</span>
                    <span>{item.source}</span>
                  </div>
                </div>
              ))}
              {(!stats?.recent_critical || stats.recent_critical.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-8">No critical alerts</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Threat Distribution */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              Threat Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4" data-testid="threat-distribution-chart">
            {threatData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={threatData} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <Tooltip
                    contentStyle={{ background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)", borderRadius: 0, fontSize: 12 }}
                  />
                  <Bar dataKey="value" fill="hsl(84,80%,55%)" radius={0}>
                    {threatData.map((entry, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground text-sm">
                No data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* State Distribution Pie */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              State-wise Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4" data-testid="state-distribution-chart">
            {stats?.state_distribution && Object.keys(stats.state_distribution).length > 0 ? (
              <div className="flex items-center">
                <ResponsiveContainer width="60%" height={250}>
                  <PieChart>
                    <Pie
                      data={Object.entries(stats.state_distribution).map(([k, v]) => ({ name: k, value: v }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      stroke="hsl(120,10%,5%)"
                      strokeWidth={2}
                    >
                      {Object.keys(stats.state_distribution).map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)", borderRadius: 0, fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="w-[40%] space-y-1.5">
                  {Object.entries(stats.state_distribution).map(([state, count], i) => (
                    <div key={state} className="flex items-center gap-2 text-xs">
                      <div className="w-2.5 h-2.5 shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="text-muted-foreground truncate">{state}</span>
                      <span className="font-mono font-bold ml-auto">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground text-sm">
                No data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Pattern Insights */}
      <PatternInsights api={api} />

      {/* Recent Intelligence */}
      <div>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 className="text-xl uppercase tracking-wide font-['Barlow_Condensed'] font-semibold">
            Latest Intelligence
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            <Select value={minPriority || "all"} onValueChange={(v) => setMinPriority(v === "all" ? "" : v)}>
              <SelectTrigger className="w-[150px] rounded-none text-[10px] uppercase h-7" data-testid="dashboard-priority-filter">
                <Filter size={11} className="mr-1" />
                <SelectValue placeholder="All Priority" />
              </SelectTrigger>
              <SelectContent className="rounded-none">
                <SelectItem value="all" className="text-xs">All Priority</SelectItem>
                <SelectItem value="80" className="text-xs">80+ (Critical)</SelectItem>
                <SelectItem value="60" className="text-xs">60+ (High)</SelectItem>
                <SelectItem value="40" className="text-xs">40+ (Medium)</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={(v) => setSortBy(v)}>
              <SelectTrigger className="w-[155px] rounded-none text-[10px] uppercase h-7" data-testid="dashboard-sort-by">
                <ArrowUpDown size={11} className="mr-1" />
                <SelectValue placeholder="Sort By" />
              </SelectTrigger>
              <SelectContent className="rounded-none">
                <SelectItem value="published_at" className="text-xs">Most Recent</SelectItem>
                <SelectItem value="priority_score" className="text-xs">Highest Priority</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-primary uppercase tracking-wider h-7"
              onClick={() => navigate("/feed")}
              data-testid="view-all-feed-btn"
            >
              View Full Feed <ChevronRight size={14} />
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="recent-intelligence-grid">
          {recentItems.map((item) => (
            <IntelligenceCard key={item.id} item={item} compact api={api} onDelete={handleDeleteItem} />
          ))}
          {recentItems.length === 0 && (
            <p className="text-sm text-muted-foreground col-span-full text-center py-8">
              No intelligence items yet. Click "Fetch Intel" to gather data.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
