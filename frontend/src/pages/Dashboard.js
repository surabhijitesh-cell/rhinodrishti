import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Shield, AlertTriangle, Activity, TrendingUp,
  ChevronRight, RefreshCw, Target, ArrowUp,
  Rss, Eye, EyeOff, Clock, CheckCircle2, Loader2,
  Filter, Languages, BellRing, GitBranch, Check, Wifi, WifiOff,
  ArrowUpDown, Youtube, Facebook, Send, Twitter, ChevronDown, ChevronUp,
  Play, Zap, Radio, Globe
} from "lucide-react";
import Tip from "../components/Tip";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "../components/ui/select";
import NERMap from "../components/NERMap";
import IntelligenceCard from "../components/IntelligenceCard";
import { useIntelligenceWS } from "../hooks/useIntelligenceWS";
import SocialMediaFeedWidget from "../components/SocialMediaFeedWidget";
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

// ─── compact scanner card (grid item) ───────────────────────────────────────
function ScannerCard({
  label, icon: Icon, accentColor, bgAccent, borderAccent, barColor,
  isConfigured, isActive, activeLabel, progress, stat1, stat2,
  lastFetched, onTrigger, triggering, configNote, testId,
  isSelected, onClick, tooltip,
}) {
  const badge = isActive
    ? <Badge className={`rounded-none text-[8px] px-1 py-0 border ${bgAccent} ${accentColor} ${borderAccent} animate-pulse leading-3`}>{activeLabel || "ACTIVE"}</Badge>
    : isConfigured
      ? <Badge className="rounded-none text-[8px] px-1 py-0 bg-muted/20 text-muted-foreground border-border leading-3">IDLE</Badge>
      : <Badge className="rounded-none text-[8px] px-1 py-0 bg-orange-500/10 text-orange-400 border-orange-500/20 leading-3">SETUP</Badge>;

  return (
    <div
      className={`border rounded-none bg-card flex flex-col gap-2 p-3 transition-all duration-200 cursor-pointer
        ${isSelected ? `${borderAccent} ${bgAccent}` : isActive ? borderAccent : "border-border hover:border-muted-foreground/30"}
        ${!isConfigured ? "opacity-70" : ""}`}
      data-testid={testId}
      onClick={onClick}
    >
      {/* row 1: icon + label + badge */}
      <div className="flex items-center gap-1.5 min-w-0">
        <div className={`p-1 shrink-0 ${bgAccent}`}>
          <Icon size={11} className={isConfigured ? accentColor : "text-muted-foreground"} />
        </div>
        {tooltip ? (
          <Tip text={tooltip} side="top">
            <span className={`text-[10px] uppercase tracking-wider font-['Barlow_Condensed'] font-bold truncate flex-1 cursor-help ${isConfigured ? "text-foreground" : "text-muted-foreground"}`}>
              {label}
            </span>
          </Tip>
        ) : (
          <span className={`text-[10px] uppercase tracking-wider font-['Barlow_Condensed'] font-bold truncate flex-1 ${isConfigured ? "text-foreground" : "text-muted-foreground"}`}>
            {label}
          </span>
        )}
        {badge}
      </div>

      {/* row 2: progress bar */}
      <div className="w-full h-1 bg-muted/20 overflow-hidden">
        <div
          className={`h-full transition-all duration-700 ${barColor} ${isActive ? "animate-pulse" : ""}`}
          style={{ width: `${isConfigured ? Math.max(progress, 8) : 8}%`, opacity: isConfigured ? 1 : 0.3 }}
        />
      </div>

      {/* row 3: stats + last fetch */}
      <div className="flex items-center justify-between gap-1 min-w-0">
        <span className="text-[10px] font-mono text-muted-foreground truncate">
          {isConfigured ? stat1 : (configNote || "Not configured")}
        </span>
        <span className={`text-[10px] font-mono shrink-0 ${lastFetched ? accentColor : "text-muted-foreground"}`}>
          {lastFetched ? timeAgo(lastFetched) : stat2 || "—"}
        </span>
      </div>

      {/* row 4: trigger button — stops propagation so card click still works */}
      <Button
        variant="ghost" size="sm"
        className={`h-5 w-full text-[9px] rounded-none font-mono border tracking-wider ${
          isConfigured
            ? `${borderAccent} ${accentColor} opacity-60 hover:opacity-100`
            : "border-border text-muted-foreground opacity-40 cursor-not-allowed"
        }`}
        onClick={e => { e.stopPropagation(); onTrigger && onTrigger(); }}
        disabled={!isConfigured || triggering || !onTrigger}
      >
        {triggering ? <Loader2 size={9} className="animate-spin mr-1" /> : <Zap size={9} className="mr-1" />}
        {triggering ? "FETCHING…" : "FETCH"}
      </Button>

      {/* selected indicator */}
      {isSelected && (
        <div className={`text-[9px] font-mono text-center ${accentColor} opacity-70`}>
          ▲ viewing sources below
        </div>
      )}
    </div>
  );
}

// ─── source detail panel (shown below grid when a card is selected) ──────────
function SourceDetailPanel({ platform, accentColor, borderAccent, bgAccent, icon: Icon, items, emptyMsg }) {
  if (!items || items.length === 0) {
    return (
      <div className={`border-t ${borderAccent} px-4 py-3 ${bgAccent}`}>
        <p className="text-[10px] font-mono text-muted-foreground">{emptyMsg || "No sources configured."}</p>
      </div>
    );
  }
  return (
    <div className={`border-t ${borderAccent} ${bgAccent} px-4 py-3`}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1 max-h-48 overflow-y-auto">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2 min-w-0 py-0.5">
            <Icon size={9} className={`${accentColor} shrink-0`} />
            <span className="text-[10px] font-mono text-foreground truncate flex-1">{item.label}</span>
            {item.sub && <span className="text-[10px] font-mono text-muted-foreground shrink-0">{item.sub}</span>}
            {item.time && (
              <span className={`text-[10px] font-mono shrink-0 ${item.time === "never" ? "text-muted-foreground/50" : accentColor}`}>
                {item.time}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── collapsible source scanners ─────────────────────────────────────────────
function SourceScanners({ api, socialTrigger, twitterPinned, onToggleTwitterPin }) {
  const [open, setOpen]               = useState(true);   // expanded by default
  const [selected, setSelected]       = useState(null);   // which card is drilled into
  const [rss, setRss]                 = useState(null);
  const [rssSources, setRssSources]   = useState([]);
  const [socialStatus, setSocialStatus] = useState(null);
  const [ytData, setYtData]           = useState({ channels: [], searches: [] });
  const [fbData, setFbData]           = useState({ pages: [] });
  const [tgData, setTgData]           = useState({ channels: [] });
  const [twData, setTwData]           = useState({ accounts: [], searches: [] });
  const [fcData, setFcData]           = useState({ sources: [], searches: [] });
  const [triggering, setTriggering]   = useState({});
  // Local timestamp set immediately when any fetch fires so cards show the
  // correct elapsed time even when MongoDB Atlas doesn't persist last_fetched.
  // Persisted to localStorage so it survives page refreshes.
  const [localScanTime, setLocalScanTime] = useState(
    () => localStorage.getItem("rhino_last_social_scan") || null
  );
  const recordScan = () => {
    const t = new Date().toISOString();
    setLocalScanTime(t);
    localStorage.setItem("rhino_last_social_scan", t);
  };

  // ── RSS status (fast poll) ──
  useEffect(() => {
    const f = async () => {
      try { const r = await axios.get(`${api}/scan-status`); setRss(r.data); } catch {}
    };
    f(); const id = setInterval(f, 4000); return () => clearInterval(id);
  }, [api]);

  // ── extract social data fetcher so we can call it after triggers ──
  const refreshSocial = useCallback(async () => {
    try {
      const results = await Promise.allSettled([
        axios.get(`${api}/social/status`),
        axios.get(`${api}/social/youtube/channels`),
        axios.get(`${api}/social/youtube/searches`),
        axios.get(`${api}/social/facebook/pages`),
        axios.get(`${api}/social/telegram/channels`),
        axios.get(`${api}/social/twitter/accounts`),
        axios.get(`${api}/social/twitter/searches`),
        axios.get(`${api}/web-sources`),
        axios.get(`${api}/firecrawl-searches`),
        axios.get(`${api}/sources`),
      ]);
      const [status, yt, ytS, fb, tg, twA, twS, ws, fs, rssS] = results;
      if (status.status === "fulfilled") setSocialStatus(status.value.data);
      setYtData({ channels: yt.value?.data?.channels || [], searches: ytS.value?.data?.searches || [] });
      setFbData({ pages: fb.value?.data?.pages || [] });
      setTgData({ channels: tg.value?.data?.channels || [] });
      setTwData({ accounts: twA.value?.data?.accounts || [], searches: twS.value?.data?.searches || [] });
      setFcData({ sources: ws.value?.data?.sources || [], searches: fs.value?.data?.searches || [] });
      setRssSources(rssS.value?.data?.sources || []);
    } catch {}
  }, [api]);

  useEffect(() => {
    refreshSocial();
    const id = setInterval(refreshSocial, 60000);
    return () => clearInterval(id);
  }, [refreshSocial]);

  // ── respond to "Fetch Intel" button from parent Dashboard ────────────────
  // socialTrigger increments each time the parent fires /social/fetch-all.
  // We immediately set a local timestamp so cards show "0s ago" without
  // waiting for MongoDB Atlas read-after-write propagation.
  useEffect(() => {
    if (!socialTrigger) return; // skip initial render (value=0)
    recordScan(); // instant local timestamp — persisted to localStorage
    setTriggering(t => ({ ...t, all: true }));
    refreshSocial();
    const delays = [8000, 18000, 35000, 55000, 90000];
    const timers = delays.map((delay, i) =>
      setTimeout(() => {
        refreshSocial();
        if (i === delays.length - 1) setTriggering(t => ({ ...t, all: false }));
      }, delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [socialTrigger, refreshSocial]);

  // ── trigger fetch + persistent polling until last_fetched updates ──
  // Backend now returns immediately (BackgroundTasks) so we poll at
  // 10s, 20s, 35s, 55s, 80s, 110s, 150s after the click to catch
  // slow sources (Telegram can take 60-90s, Firecrawl up to 3 min).
  const trigger = async (key, endpoint) => {
    setTriggering(t => ({ ...t, [key]: true }));
    recordScan(); // instant local timestamp — persisted to localStorage
    try { await axios.post(`${api}${endpoint}`); } catch {}

    const pollDelays = [10000, 20000, 35000, 55000, 80000, 110000, 150000];
    pollDelays.forEach((delay, i) => {
      setTimeout(() => {
        refreshSocial();
        if (i === pollDelays.length - 1) setTriggering(t => ({ ...t, [key]: false }));
      }, delay);
    });
  };

  // ── timestamp helper: use local override if it's newer than MongoDB data ──
  // This ensures "0s ago" is shown immediately after a global fetch trigger
  // instead of waiting for MongoDB Atlas read-after-write propagation.
  const freshTime = (mongoIso) => {
    if (!localScanTime) return mongoIso;
    if (!mongoIso) return localScanTime;
    return new Date(localScanTime) >= new Date(mongoIso) ? localScanTime : mongoIso;
  };

  // ── derived ──
  const rssScanning  = rss?.is_scanning || false;
  const lastResult   = rss?.last_scan_result;
  const ytActive     = !!socialStatus?.youtube?.configured;
  const fbActive     = !!socialStatus?.facebook?.configured;
  const tgActive     = !!socialStatus?.telegram?.configured;
  const twConfigured = !!socialStatus?.twitter?.configured;
  const fcConfigured = !!socialStatus?.firecrawl?.configured || fcData.sources.length > 0;

  const latest = (arr, key) => arr.reduce((best, item) => {
    if (!item[key]) return best;
    return !best || new Date(item[key]) > new Date(best) ? item[key] : best;
  }, null);

  const ytChannels = ytData.channels.filter(c => c.active);
  const fbPages    = fbData.pages.filter(p => p.active);
  const tgChannels = tgData.channels.filter(c => c.active);
  const twAccounts = twData.accounts.filter(a => a.active);
  const fcSources  = fcData.sources.filter(s => s.active);
  const fcSearches = fcData.searches.filter(s => s.active);

  const platforms = [
    { key: "rss", ok: true,         active: rssScanning },
    { key: "yt",  ok: ytActive,     active: triggering["youtube"] },
    { key: "fb",  ok: fbActive,     active: triggering["facebook"] },
    { key: "tg",  ok: tgActive,     active: triggering["telegram"] },
    { key: "tw",  ok: true,         active: triggering["twitter"] },
    { key: "fc",  ok: fcConfigured, active: triggering["firecrawl"] },
  ];
  const configuredCount = platforms.filter(p => p.ok).length;
  const anyActive = platforms.some(p => p.active);

  // ── source detail data per platform ──
  const detailData = {
    rss: {
      icon: Rss, accentColor: "text-green-400", borderAccent: "border-green-500/20", bgAccent: "bg-green-500/5",
      items: rssSources.map(s => ({ label: s.name || s.url, sub: s.category, time: timeAgo(s.last_fetched) })),
      emptyMsg: "No RSS sources configured.",
    },
    youtube: {
      icon: Youtube, accentColor: "text-red-400", borderAccent: "border-red-500/20", bgAccent: "bg-red-500/5",
      items: [
        ...ytChannels.map(c => ({ label: c.name, sub: "channel", time: timeAgo(c.last_fetched) })),
        ...ytData.searches.filter(s=>s.active).map(s => ({ label: s.query, sub: "search", time: timeAgo(s.last_run) })),
      ],
      emptyMsg: "No YouTube channels configured. Add YOUTUBE_API_KEY to Render.",
    },
    facebook: {
      icon: Facebook, accentColor: "text-blue-400", borderAccent: "border-blue-500/20", bgAccent: "bg-blue-500/5",
      items: fbPages.map(p => ({ label: p.name, sub: p.category, time: timeAgo(p.last_fetched) })),
      emptyMsg: "No Facebook pages configured. Add FACEBOOK_APP_ID + FACEBOOK_APP_SECRET.",
    },
    telegram: {
      icon: Send, accentColor: "text-sky-400", borderAccent: "border-sky-500/20", bgAccent: "bg-sky-500/5",
      items: tgChannels.map(c => ({ label: c.name, sub: `@${c.username}`, time: timeAgo(c.last_fetched) })),
      emptyMsg: "No Telegram channels configured. Run telegram_setup.py to generate session.",
    },
    // X/Twitter is intentionally omitted from the drill-down panel.
    // Clicking the X/Twitter card navigates to /twitter-feed instead, which
    // shows actual tweet content rather than a list of monitored handles.
    firecrawl: {
      icon: Globe, accentColor: "text-orange-400", borderAccent: "border-orange-500/20", bgAccent: "bg-orange-500/5",
      items: [
        ...fcSources.map(s => ({ label: s.name || s.url, sub: s.region, time: timeAgo(s.last_fetched) })),
        ...fcSearches.map(s => ({ label: s.query, sub: "keyword", time: timeAgo(s.last_run) })),
      ],
      emptyMsg: "No Firecrawl sources configured. Add FIRECRAWL_API_KEY.",
    },
  };

  const handleCardClick = (key) => setSelected(prev => prev === key ? null : key);

  return (
    <Card className="rounded-none border border-border bg-card overflow-hidden">
      {/* ── header (always visible) ── */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 cursor-pointer select-none hover:bg-muted/10 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <Radio size={13} className={anyActive ? "text-primary animate-pulse" : "text-muted-foreground"} />
        <span className="text-[11px] uppercase tracking-widest font-['Barlow_Condensed'] font-bold text-muted-foreground">
          Intelligence Source Monitors
        </span>
        <div className="flex items-center gap-1.5 ml-1">
          {platforms.map(p => (
            <span key={p.key} className={`w-1.5 h-1.5 rounded-full transition-colors ${
              p.active ? "bg-primary animate-pulse" : p.ok ? "bg-green-500/70" : "bg-orange-500/40"
            }`} />
          ))}
        </div>
        <span className="text-[10px] font-mono text-muted-foreground ml-1 hidden sm:block">{configuredCount}/6 configured</span>
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost" size="sm"
            className="h-6 px-2 text-[9px] rounded-none font-mono text-muted-foreground border border-border hover:text-foreground"
            title="Fetch all social & web sources (excludes RSS)"
            onClick={e => { e.stopPropagation(); trigger("all", "/social/fetch-all"); }}
            disabled={triggering["all"]}
          >
            {triggering["all"] ? <Loader2 size={9} className="animate-spin mr-1" /> : <RefreshCw size={9} className="mr-1" />}
            {triggering["all"] ? "FETCHING…" : "SCAN SOCIAL MEDIA"}
          </Button>
          {open ? <ChevronUp size={13} className="text-muted-foreground" /> : <ChevronDown size={13} className="text-muted-foreground" />}
        </div>
      </div>

      {/* ── expanded grid ── */}
      {open && (
        <>
          <div className="border-t border-border p-3">
            <p className="text-[9px] font-mono text-muted-foreground/50 mb-2 uppercase tracking-wider">Click a card to view its sources · Click header to collapse panel</p>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">

              <ScannerCard
                label="RSS Feeds" icon={Rss}
                accentColor="text-green-400" bgAccent="bg-green-500/10"
                borderAccent="border-green-500/30" barColor="bg-green-500"
                isConfigured={true} isActive={rssScanning} activeLabel="SCANNING"
                progress={rssScanning ? (rss?.progress || 0) : 100}
                stat1={rssScanning ? `${rss?.sources_scanned || 0}/${rss?.total_sources || 0}` : `${rss?.total_sources || "—"} feeds`}
                stat2={lastResult ? `+${lastResult.new_relevant} new` : ""}
                lastFetched={rss?.last_scan_at}
                onTrigger={() => trigger("rss", "/fetch-news")}
                triggering={triggering["rss"]}
                isSelected={selected === "rss"}
                onClick={() => handleCardClick("rss")}
                testId="scanner-rss"
                tooltip="RSS Feeds — 89 curated news sources: NER regional papers, national outlets, Bangladesh/Myanmar publications, and government PIB offices. Auto-fetched every 30-60 min."
              />

              <ScannerCard
                label="YouTube" icon={Youtube}
                accentColor="text-red-400" bgAccent="bg-red-500/10"
                borderAccent="border-red-500/30" barColor="bg-red-500"
                isConfigured={ytActive} isActive={triggering["youtube"] || triggering["all"]} activeLabel="FETCHING"
                progress={ytActive ? 100 : 0}
                stat1={ytActive ? `${ytChannels.length} ch · ${ytData.searches.filter(s=>s.active).length} srch` : ""}
                lastFetched={freshTime(latest(ytChannels, "last_fetched"))}
                onTrigger={() => trigger("youtube", "/social/fetch-all")}
                triggering={triggering["youtube"] || triggering["all"]}
                configNote="Add YOUTUBE_API_KEY"
                isSelected={selected === "youtube"}
                onClick={() => handleCardClick("youtube")}
                testId="scanner-youtube"
                tooltip={`YouTube — ${ytChannels.length} subscribed channels + ${ytData.searches.filter(s=>s.active).length} keyword searches. Requires YOUTUBE_API_KEY on Render. Fetches video metadata and transcripts.`}
              />

              <ScannerCard
                label="Facebook" icon={Facebook}
                accentColor="text-blue-400" bgAccent="bg-blue-500/10"
                borderAccent="border-blue-500/30" barColor="bg-blue-500"
                isConfigured={fbActive} isActive={triggering["facebook"] || triggering["all"]} activeLabel="FETCHING"
                progress={fbActive ? 100 : 0}
                stat1={fbActive ? `${fbPages.length} pages` : ""}
                lastFetched={freshTime(latest(fbPages, "last_fetched"))}
                onTrigger={() => trigger("facebook", "/social/fetch-all")}
                triggering={triggering["facebook"] || triggering["all"]}
                configNote="Add FB credentials"
                isSelected={selected === "facebook"}
                onClick={() => handleCardClick("facebook")}
                testId="scanner-facebook"
                tooltip={`Facebook — ${fbPages.length} monitored pages. Requires FACEBOOK_APP_ID + FACEBOOK_APP_SECRET on Render. Good for NER political party and activist pages.`}
              />

              <ScannerCard
                label="Telegram" icon={Send}
                accentColor="text-sky-400" bgAccent="bg-sky-500/10"
                borderAccent="border-sky-500/30" barColor="bg-sky-500"
                isConfigured={tgActive} isActive={triggering["telegram"] || triggering["all"]} activeLabel="FETCHING"
                progress={tgActive ? 100 : 0}
                stat1={tgActive ? `${tgChannels.length} channels` : ""}
                lastFetched={freshTime(latest(tgChannels, "last_fetched"))}
                onTrigger={() => trigger("telegram", "/social/fetch-all")}
                triggering={triggering["telegram"] || triggering["all"]}
                configNote="Run telegram_setup.py"
                isSelected={selected === "telegram"}
                onClick={() => handleCardClick("telegram")}
                testId="scanner-telegram"
                tooltip={`Telegram — ${tgChannels.length} monitored channels via Telethon client. Session ID required (run telegram_setup.py). High-value for militant and political org communications.`}
              />

              <ScannerCard
                label="X / Twitter" icon={Twitter}
                accentColor="text-slate-300" bgAccent="bg-slate-500/10"
                borderAccent="border-slate-500/30" barColor="bg-slate-400"
                isConfigured={twConfigured} isActive={triggering["twitter"] || triggering["all"]} activeLabel="FETCHING"
                progress={twConfigured ? 100 : 0}
                stat1={twConfigured ? `${twAccounts.length} acct · ${twData.searches.filter(s=>s.active).length} srch` : "API key needed"}
                stat2={twConfigured ? "Live" : "—"}
                lastFetched={freshTime(latest(twData.searches, "last_run"))}
                onTrigger={() => trigger("twitter", "/social/fetch-all")}
                triggering={triggering["twitter"] || triggering["all"]}
                isSelected={selected === "twitter"}
                onClick={() => handleCardClick("twitter")}
                configNote="Add TWITTER_BEARER_TOKEN"
                testId="scanner-twitter"
                tooltip={`X/Twitter — click to open the live tweet feed inline. ${twConfigured ? "Official API active." : "Set TWITTER_BEARER_TOKEN to enable."} ${twAccounts.length} accounts + ${twData.searches.filter(s=>s.active).length} searches monitored. Configure Lists in Settings → Social Scan for free-tier compatibility.`}
              />

              <ScannerCard
                label="Firecrawl" icon={Globe}
                accentColor="text-orange-400" bgAccent="bg-orange-500/10"
                borderAccent="border-orange-500/30" barColor="bg-orange-500"
                isConfigured={fcConfigured} isActive={triggering["firecrawl"] || triggering["all"]} activeLabel="CRAWLING"
                progress={fcConfigured ? 100 : 0}
                stat1={fcConfigured ? `${fcSources.length} sites · ${fcSearches.length} queries` : ""}
                lastFetched={freshTime(latest(fcSources, "last_fetched"))}
                onTrigger={fcConfigured ? () => trigger("firecrawl", "/social/fetch-all") : null}
                triggering={triggering["firecrawl"] || triggering["all"]}
                configNote="Add FIRECRAWL_API_KEY"
                isSelected={selected === "firecrawl"}
                onClick={() => handleCardClick("firecrawl")}
                testId="scanner-firecrawl"
                tooltip={`Firecrawl — deep-crawls ${fcSources.length} configured websites + ${fcSearches.length} keyword web searches. Reaches sites with no RSS feed. Requires FIRECRAWL_API_KEY on Render.`}
              />
            </div>
          </div>

          {/* ── source detail / live-feed panel ── */}
          {/* All 5 social platforms now show a live-feed widget with direct
              (raw) and curated (AI-classified) toggle instead of a static
              handle list. The RSS card still shows the old static panel. */}
          {selected && ["youtube","facebook","telegram","twitter","firecrawl"].includes(selected) ? (
            <SocialMediaFeedWidget
              api={api}
              sourceType={selected}
              compact={true}
              pinned={twitterPinned && selected === "twitter"}
              onTogglePin={selected === "twitter" ? onToggleTwitterPin : undefined}
              onClose={() => setSelected(null)}
            />
          ) : selected === "rss" && detailData.rss ? (
            <SourceDetailPanel {...detailData.rss} platform="rss" />
          ) : null}
        </>
      )}
    </Card>
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
          <Tip text="Automatically detected recurring threat clusters. Each pattern groups 3+ intelligence items sharing the same region, threat type or actor within a 7-day window." side="top">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold cursor-help">
              Detected Patterns ({patterns.length})
            </CardTitle>
          </Tip>
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
  // Increments every time "Fetch Intel" fires social/fetch-all so SourceScanners
  // can show FETCHING badges and start its polling schedule.
  const [socialTrigger, setSocialTrigger] = useState(0);
  const navigate = useNavigate();

  // Twitter Live Feed widget pin state — persisted to localStorage so the
  // user's choice survives page reloads.
  const [twitterPinned, setTwitterPinned] = useState(
    () => localStorage.getItem("dashboard_twitter_pinned") === "1"
  );
  const toggleTwitterPin = () => {
    setTwitterPinned(p => {
      const next = !p;
      localStorage.setItem("dashboard_twitter_pinned", next ? "1" : "0");
      return next;
    });
  };

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
      // Trigger all 6 sources: RSS + social/web in parallel
      await Promise.allSettled([
        axios.post(`${api}/fetch-news`),
        axios.post(`${api}/social/fetch-all`),
      ]);
      // Tell SourceScanners a global social fetch just fired so it can
      // show FETCHING badges and kick off its own polling schedule.
      setSocialTrigger(t => t + 1);
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
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="dashboard-title" data-tour="dashboard-title">
            Intelligence Overview
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            NER Situation Awareness Dashboard
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Tip text={wsConnected ? "WebSocket live — new intel items arrive instantly without a page refresh" : "WebSocket offline — data updates on manual refresh only"} side="bottom">
            <div className="flex items-center gap-1.5 text-[10px] font-mono cursor-default" data-testid="ws-status">
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
          </Tip>
          <Tip text="Trigger a full sweep of all 6 sources — RSS feeds + YouTube, Facebook, Telegram, X/Twitter and Firecrawl — simultaneously" side="bottom">
            <Button
              onClick={handleFetchNews}
              disabled={loading}
              className="uppercase text-xs font-bold tracking-wider rounded-none"
              data-testid="fetch-news-btn"
              data-tour="fetch-intel-btn"
            >
              <RefreshCw size={14} className={`mr-2 ${loading ? "animate-spin" : ""}`} />
              Fetch Intel
            </Button>
          </Tip>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <Tip text="Total AI-processed intelligence items in your retention window. Click to open the full Intelligence Feed." side="bottom">
          <div data-tour="stat-total">
            <StatBox label="Total Items" value={stats?.total_items || 0} icon={Activity} color="bg-primary/10 text-primary" sub={`${stats?.today_count || 0} today`} testId="stat-total" onClick={() => navigate("/feed")} />
          </div>
        </Tip>
        <Tip text="CRITICAL items — immediate threats. Click to filter feed to critical only." side="bottom">
          <div data-tour="stat-critical">
            <StatBox label="Critical" value={stats?.critical_count || 0} icon={AlertTriangle} color="bg-red-500/10 text-red-400" testId="stat-critical" onClick={() => navigate("/feed?severity=critical")} />
          </div>
        </Tip>
        <Tip text="HIGH severity items — significant events requiring priority review. Click to filter." side="bottom">
          <div data-tour="stat-high">
            <StatBox label="High" value={stats?.high_count || 0} icon={Target} color="bg-amber-500/10 text-amber-400" testId="stat-high" onClick={() => navigate("/feed?severity=high")} />
          </div>
        </Tip>
        <Tip text="MEDIUM severity — notable but non-urgent items. Click to filter." side="bottom">
          <div data-tour="stat-medium">
            <StatBox label="Medium" value={stats?.medium_count || 0} icon={Shield} color="bg-yellow-500/10 text-yellow-400" testId="stat-medium" onClick={() => navigate("/feed?severity=medium")} />
          </div>
        </Tip>
        <Tip text="LOW severity — informational items. Click to filter." side="bottom">
          <div>
            <StatBox label="Low" value={stats?.low_count || 0} icon={ArrowUp} color="bg-green-500/10 text-green-400" testId="stat-low" onClick={() => navigate("/feed?severity=low")} />
          </div>
        </Tip>
      </div>

      {/* Pinned Twitter Live Feed (only renders when user has pinned) */}
      {twitterPinned && (
        <div className="border border-slate-500/30 rounded-none bg-card overflow-hidden" data-testid="pinned-twitter-feed">
          <SocialMediaFeedWidget
            api={api}
            sourceType="twitter"
            compact={false}
            pinned={true}
            onTogglePin={toggleTwitterPin}
          />
        </div>
      )}

      {/* Source Scanners */}
      <div data-tour="source-scanners">
        <SourceScanners
          api={api}
          socialTrigger={socialTrigger}
          twitterPinned={twitterPinned}
          onToggleTwitterPin={toggleTwitterPin}
        />
      </div>

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
        <div className="lg:col-span-7" data-tour="ner-map">
          <NERMap
            stateStats={stateStatsMap}
            items={stats?.recent_critical || []}
            navigate={navigate}
            onStateClick={(state) => navigate(`/feed?state=${encodeURIComponent(state)}`)}
          />
        </div>

        {/* Recent Critical Alerts */}
        <div className="lg:col-span-5">
          <Card className="border border-border rounded-none bg-card h-full">
            <CardHeader className="py-3 px-4 border-b border-border">
              <div className="flex items-center justify-between">
                <Tip text="Most recent CRITICAL and HIGH severity items. These require immediate analyst attention. Click View All to open the full Alerts page." side="top">
                  <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold cursor-help">
                    Recent Critical Alerts
                  </CardTitle>
                </Tip>
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
            <Tip text="Horizontal bar chart showing how intelligence items are distributed across threat categories (insurgency, drug trafficking, border incursion, etc.) within your retention window." side="top">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold cursor-help w-fit">
                Threat Distribution
              </CardTitle>
            </Tip>
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
            <Tip text="Pie chart showing how intelligence items are distributed across NER states and border countries. Each slice represents one state or country. Larger slice = more intelligence activity." side="top">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold cursor-help w-fit">
                State-wise Distribution
              </CardTitle>
            </Tip>
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
      <div data-tour="recent-intel">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <Tip text="Most recent AI-classified intelligence items. Use the Priority Filter to show only high-scoring items, or Sort By Priority to surface the most urgent items first." side="top">
            <h2 className="text-xl uppercase tracking-wide font-['Barlow_Condensed'] font-semibold cursor-help">
              Latest Intelligence
            </h2>
          </Tip>
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
