/**
 * SocialMediaFeedWidget — generic live-feed panel for any social/web source.
 *
 * Works for: twitter, youtube, facebook, telegram, firecrawl
 *
 * Direct mode  → /api/social-feeds/{source_type}  (ALL raw items, no AI gate)
 * Curated mode → /api/intelligence?source_type=X  (AI-classified only)
 *
 * Reusable in two placements:
 *   1. Inline in Dashboard SourceScanners (compact=true, onClose provided)
 *   2. Pinned at top of Dashboard (compact=false, pinned=true)
 */
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import axios from "axios";
import {
  RefreshCw, ExternalLink, Heart, Repeat2, Loader2,
  Filter, AlertTriangle, Pin, PinOff, X as XIcon, Zap, Brain, Eye,
  Youtube, Send, Globe, Twitter, CheckCircle2,
  XCircle, Clock, PlusCircle, Lock, Facebook, ArrowUp, ArrowDown,
} from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "./ui/select";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";

// Roles that may view the raw social-media feed
const ALLOWED_ROLES = ["admin", "analyst"];

const REFRESH_MS = 30_000;

// ─── Source configuration ─────────────────────────────────────────────────────
const SOURCE_CFG = {
  twitter: {
    label: "X / Twitter",
    Icon: Twitter,
    color: "text-slate-300",
    borderColor: "border-slate-500/20",
    bgColor: "bg-slate-500/5",
    headerBg: "bg-slate-500/10",
    rawEndpoint: (api) => `${api}/social-feeds/twitter`,
    curatedEndpoint: (api) => `${api}/intelligence?source_type=twitter&limit=100&sort_by=published_at`,
    getTitle: (it) => it.account_name || (it.handle || "").replace(/^@/, "") || "Unknown",
    getSubtitle: (it) => (it.handle || "").replace(/^@/, ""),
    getText: (it) => it.tweet_text || it.raw_content || "",
    getUrl: (it) => it.tweet_url || it.source_url || "",
    getTime: (it) => it.posted_at || it.published_at || "",
    getLikes: (it) => it.likes || 0,
    getShares: (it) => it.retweets || 0,
    shareIcon: Repeat2,
    shareLabel: "RT",
    likeLabel: "Likes",
    emptyHint: [
      "Set TWITTER_BEARER_TOKEN in the backend .env",
      "Add a List in Settings → Social Scan → X/Twitter",
      "Click Fetch Now below",
      "Wait 10–60s for tweets to appear",
    ],
  },
  telegram: {
    label: "Telegram",
    Icon: Send,
    color: "text-sky-400",
    borderColor: "border-sky-500/20",
    bgColor: "bg-sky-500/5",
    headerBg: "bg-sky-500/10",
    rawEndpoint: (api) => `${api}/social-feeds/telegram`,
    curatedEndpoint: (api) => `${api}/intelligence?source_type=telegram&limit=100&sort_by=published_at`,
    getTitle: (it) => it.source || it.title?.replace(/^Telegram:\s*/i, "") || "Telegram",
    getSubtitle: (it) => it.source || "",
    getText: (it) => it.raw_content || it.tweet_text || "",
    getUrl: (it) => it.source_url || it.tweet_url || "",
    getTime: (it) => it.published_at || it.posted_at || "",
    getLikes: (it) => it.telegram_views || 0,
    getShares: () => 0,
    shareIcon: RefreshCw,
    shareLabel: "",
    likeLabel: "Views",
    emptyHint: [
      "Run telegram_setup.py to generate a session",
      "Add channels in Settings → Social Scan → Telegram",
      "Click Fetch Now below",
    ],
  },
  youtube: {
    label: "YouTube",
    Icon: Youtube,
    color: "text-red-400",
    borderColor: "border-red-500/20",
    bgColor: "bg-red-500/5",
    headerBg: "bg-red-500/10",
    rawEndpoint: (api) => `${api}/social-feeds/youtube`,
    curatedEndpoint: (api) => `${api}/intelligence?source_type=youtube&limit=100&sort_by=published_at`,
    getTitle: (it) => it.title || it.source || "YouTube Video",
    getSubtitle: (it) => it.source || "",
    getText: (it) => it.raw_content || it.ai_summary || "",
    getUrl: (it) => it.source_url || "",
    getTime: (it) => it.published_at || "",
    getLikes: () => 0,
    getShares: () => 0,
    shareIcon: RefreshCw,
    shareLabel: "",
    likeLabel: "",
    emptyHint: [
      "Add YOUTUBE_API_KEY to backend .env",
      "Add channels in Settings → Social Scan → YouTube",
      "Click Fetch Now below",
    ],
  },
  facebook: {
    label: "Facebook",
    Icon: Facebook,
    color: "text-blue-400",
    borderColor: "border-blue-500/20",
    bgColor: "bg-blue-500/5",
    headerBg: "bg-blue-500/10",
    rawEndpoint: (api) => `${api}/social-feeds/facebook`,
    curatedEndpoint: (api) => `${api}/intelligence?source_type=facebook&limit=100&sort_by=published_at`,
    getTitle: (it) => it.source || "Facebook",
    getSubtitle: (it) => it.source || "",
    getText: (it) => it.raw_content || it.ai_summary || "",
    getUrl: (it) => it.source_url || "",
    getTime: (it) => it.published_at || "",
    getLikes: () => 0,
    getShares: () => 0,
    shareIcon: RefreshCw,
    shareLabel: "",
    likeLabel: "",
    emptyHint: [
      "Add APIFY_TOKEN to backend .env",
      "Runs automatically via the scheduler (throttled/firehose toggle above)",
      "Click Fetch Now below",
    ],
  },
  firecrawl: {
    label: "Firecrawl",
    Icon: Globe,
    color: "text-orange-400",
    borderColor: "border-orange-500/20",
    bgColor: "bg-orange-500/5",
    headerBg: "bg-orange-500/10",
    rawEndpoint: (api) => `${api}/social-feeds/firecrawl`,
    curatedEndpoint: (api) => `${api}/intelligence?source_type=firecrawl&limit=100&sort_by=published_at`,
    getTitle: (it) => it.title || it.source || "Web Article",
    getSubtitle: (it) => it.source || "",
    getText: (it) => it.raw_content?.slice(0, 300) || it.ai_summary || "",
    getUrl: (it) => it.source_url || "",
    getTime: (it) => it.published_at || "",
    getLikes: () => 0,
    getShares: () => 0,
    shareIcon: RefreshCw,
    shareLabel: "",
    likeLabel: "",
    emptyHint: [
      "Add FIRECRAWL_API_KEY to backend .env",
      "Add sites in Settings → Social Scan → Firecrawl",
      "Click Fetch Now below",
    ],
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function timeAgo(iso) {
  if (!iso) return "—";
  try {
    const d   = new Date(iso);
    const diff = Math.floor((Date.now() - d) / 1000);
    const abs  = d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    if (diff < 60)     return `${diff}s · ${abs}`;
    if (diff < 3600)   return `${Math.floor(diff / 60)}m · ${abs}`;
    if (diff < 86400)  return `${Math.floor(diff / 3600)}h · ${abs}`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d · ${abs}`;
    return abs;
  } catch {
    return "—";
  }
}

function initials(name) {
  if (!name) return "?";
  return name.split(/\s+/).filter(Boolean).slice(0, 2)
    .map(s => s[0]?.toUpperCase()).join("") || "?";
}

const SEV_COLOR = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-muted-foreground",
};

// ─── Item card (source-aware) ─────────────────────────────────────────────────
function FeedCard({ item, cfg, api }) {
  const title    = cfg.getTitle(item);
  const subtitle = cfg.getSubtitle(item);
  const text     = cfg.getText(item);
  const url      = cfg.getUrl(item);
  const t        = cfg.getTime(item);
  const likes    = cfg.getLikes(item);
  const shares   = cfg.getShares(item);
  const { Icon, color, shareIcon: ShareIcon } = cfg;
  const sev      = item.severity;

  // ── Add-to-Feed ────────────────────────────────────────────────────────────
  const [adding, setAdding]   = useState(false);
  const [added,  setAdded]    = useState(
    // Pre-mark as already in feed if item is processed+relevant
    !!(item.processed && item.is_relevant !== false &&
       !( item.tags || [] ).includes("not_relevant") &&
       item.severity && item.severity !== "low")
  );

  const handleAddToFeed = async () => {
    setAdding(true);
    try {
      const itemId   = item.id;
      const sourceUrl = item.source_url || item.tweet_url;

      if (itemId) {
        // Item is already in intelligence_items — force-accept it
        try {
          await axios.post(`${api}/intelligence/${itemId}/accept`);
          toast.success("Added to intelligence feed");
          setAdded(true);
        } catch (e) {
          if (e.response?.status === 404) {
            // ID belongs to twitter_feeds, not intelligence_items — import it
            await axios.post(`${api}/social/import`, item);
            toast.success("Item imported into intelligence feed");
            setAdded(true);
          } else {
            throw e;
          }
        }
      } else if (sourceUrl) {
        await axios.post(`${api}/social/import`, item);
        toast.success("Item imported into intelligence feed");
        setAdded(true);
      } else {
        toast.error("Cannot add item — no ID or URL");
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add item");
    }
    setAdding(false);
  };

  return (
    <div className="border-b border-border px-3 py-2.5 hover:bg-muted/5 transition-colors group">
      <div className="flex items-start gap-2.5">
        {/* Avatar */}
        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border border-border ${cfg.headerBg}`}>
          <span className={`text-[9px] font-bold font-mono ${color}`}>{initials(title)}</span>
        </div>
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-foreground truncate max-w-[120px]">{title}</span>
            {subtitle && subtitle !== title && (
              <span className={`text-[10px] font-mono ${color} truncate`}>{subtitle}</span>
            )}
            <span className="text-muted-foreground/40 text-[10px]">·</span>
            <span className="text-[10px] font-mono text-muted-foreground">{timeAgo(t)}</span>
            {/* AI pipeline status badges */}
            <div className="ml-auto flex items-center gap-1">
              {sev && (
                <span className={`text-[9px] font-mono uppercase ${SEV_COLOR[sev] || "text-muted-foreground"}`}>
                  {sev}
                </span>
              )}
              {item.processed === true && (
                <CheckCircle2 size={9} className="text-emerald-400" title="AI processed" />
              )}
              {item.processed === false && (
                <XCircle size={9} className="text-red-400/50" title="Not processed" />
              )}
              {item.list_name && (
                <Badge className="rounded-none text-[8px] px-1 py-0 bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                  {item.list_name}
                </Badge>
              )}
            </div>
          </div>

          {/* Content title (for YouTube/Firecrawl, the title IS the main content) */}
          {(cfg === SOURCE_CFG.youtube || cfg === SOURCE_CFG.firecrawl) && item.title && (
            <p className="text-xs font-semibold mt-0.5 leading-tight line-clamp-2">{item.title}</p>
          )}

          {/* Text body */}
          {text && (
            <p className="text-xs leading-relaxed mt-1 text-foreground/85 line-clamp-3 whitespace-pre-wrap break-words">
              {text}
            </p>
          )}

          {/* Footer: engagement + link + Add to Feed */}
          <div className="flex items-center gap-3 mt-1.5">
            {likes > 0 && (
              <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
                <Heart size={10} className="text-rose-400/70" />{likes.toLocaleString()}
              </span>
            )}
            {shares > 0 && (
              <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
                <ShareIcon size={10} className="text-emerald-400/70" />{shares.toLocaleString()}
              </span>
            )}
            {item.state && (
              <span className="text-[9px] font-mono text-muted-foreground/70 border border-border px-1 py-0">
                {item.state}
              </span>
            )}

            {/* ── Add to Feed button ── */}
            <button
              onClick={handleAddToFeed}
              disabled={adding || added}
              title={added ? "Already in intelligence feed" : "Promote this item to the intelligence feed"}
              className={`flex items-center gap-0.5 text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 border transition-colors ${
                added
                  ? "border-emerald-500/30 text-emerald-400/60 cursor-default"
                  : "border-violet-500/30 text-violet-400 hover:bg-violet-500/10 hover:border-violet-500/60"
              }`}
            >
              {adding
                ? <Loader2 size={8} className="animate-spin" />
                : added
                  ? <CheckCircle2 size={8} />
                  : <PlusCircle size={8} />
              }
              <span>{added ? "In Feed" : "Add"}</span>
            </button>

            {url && (
              <a href={url} target="_blank" rel="noreferrer"
                 className="ml-auto flex items-center gap-1 text-[10px] font-mono text-muted-foreground hover:text-primary uppercase tracking-wider opacity-0 group-hover:opacity-100">
                View <ExternalLink size={9} />
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Widget ──────────────────────────────────────────────────────────────
export default function SocialMediaFeedWidget({
  api,
  sourceType = "twitter",
  compact = true,
  pinned = false,
  onTogglePin,
  onClose,
}) {
  const cfg = SOURCE_CFG[sourceType] || SOURCE_CFG.twitter;
  const { Icon, color, label, borderColor, bgColor } = cfg;

  // ── Auth — MUST be first hook, never after an early return ─────────────────
  const { user } = useAuth();
  const isAllowed = !!(user && ALLOWED_ROLES.includes(user.role));

  // All hooks must be declared unconditionally (Rules of Hooks)
  const [items, setItems]         = useState([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError]         = useState(null);
  const [statusNote, setStatusNote] = useState(null);   // from /social/status endpoint
  const [twitterFreeTier, setTwitterFreeTier] = useState(false);
  const autoTriggeredRef = useRef(false);  // fire once per mount, not on every refresh

  // DIRECT mode  → raw /social-feeds/{type} endpoint (no AI filter)
  // CURATED mode → /intelligence?source_type=X (AI-classified only)
  const [mode, setMode]           = useState("direct");
  const [filterText, setFilterText] = useState("");
  const [timeWindow, setTimeWindow] = useState("all");

  const load = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      let rawItems = [];
      if (mode === "direct") {
        // Raw mode — no AI gate, returns all fetched items
        const res = await axios.get(`${cfg.rawEndpoint(api)}?limit=150`);
        rawItems = res.data.items || res.data.feeds || [];
      } else {
        // Curated mode — AI-classified only via intelligence endpoint
        // The curatedEndpoint already contains ?param=val so just use it as-is
        // (do NOT append &limit=150 — the intelligence endpoint caps at le=100 → 422)
        const res = await axios.get(cfg.curatedEndpoint(api));
        rawItems = res.data.items || [];
      }
      setItems(rawItems);
      setLastUpdated(new Date());
      setError(null);

      // Always fetch status for Twitter (to detect free vs paid tier).
      // For other sources only fetch when empty.
      if (sourceType === "twitter" || rawItems.length === 0) {
        try {
          const statusRes = await axios.get(`${api}/social/status`);
          const srcStatus = statusRes.data?.[sourceType];
          if (srcStatus?.note) setStatusNote(srcStatus.note);
          if (sourceType === "twitter") {
            setTwitterFreeTier(!!srcStatus?.free_tier);
          }
        } catch (_) {/* non-fatal */}
      }
    } catch (e) {
      console.error(`[SocialFeed/${sourceType}] fetch failed:`, e);
      // FastAPI 422 detail is an array of objects — serialise to string to avoid React crash
      const detail = e.response?.data?.detail;
      const errMsg = Array.isArray(detail)
        ? (detail[0]?.msg || `Validation error (${e.response.status})`)
        : (typeof detail === "string" ? detail : e.message || "Failed to load");
      setError(errMsg);
    }
    setLoading(false);
    setRefreshing(false);
  }, [api, mode, sourceType, cfg, statusNote]);

  useEffect(() => {
    load();
    const id = setInterval(() => load(true), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  // Auto-trigger fetch when data is stale (firecrawl only) ───────────────────
  // Fires once per widget mount. Triggers if:
  //   a) no items at all, OR
  //   b) newest item's fetched_at is > 3 hours old
  // This catches cold starts where the scheduler hasn't run yet.
  useEffect(() => {
    if (sourceType !== "firecrawl") return;
    if (autoTriggeredRef.current) return;
    if (loading) return;   // wait for first load to complete

    const THREE_HOURS_MS = 3 * 60 * 60 * 1000;
    const newestFetch = items.reduce((best, it) => {
      const t = new Date(it.fetched_at || it.published_at || 0).getTime();
      return t > best ? t : best;
    }, 0);

    const isStale = newestFetch === 0 || (Date.now() - newestFetch) > THREE_HOURS_MS;

    if (isStale) {
      autoTriggeredRef.current = true;
      setTriggering(true);
      axios.post(`${api}/social/fetch-all`).catch(() => {});
      // Poll after delays typical for firecrawl (can take 60–180s)
      [15000, 40000, 80000, 140000].forEach((d, i) => setTimeout(() => {
        load(true);
        if (i === 3) setTriggering(false);
      }, d));
    } else {
      autoTriggeredRef.current = true; // data is fresh, no need to trigger
    }
  }, [loading, items, sourceType, api, load]);

  const fetchNow = async () => {
    setTriggering(true);
    try {
      await axios.post(`${api}/social/fetch-all`);
      toast.success(`${label} fetch triggered — new items will appear shortly`);
      [8000, 20000, 45000].forEach((d, i) => setTimeout(() => {
        load(true);
        if (i === 2) setTriggering(false);
      }, d));
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fetch trigger failed");
      setTriggering(false);
    }
  };

  const filtered = useMemo(() => {
    const windowMs = { "24h": 86400000, "7d": 604800000, "30d": 2592000000 }[timeWindow] || null;
    const cutoff   = windowMs ? Date.now() - windowMs : null;
    const result = items.filter(it => {
      const t = cfg.getTime(it);
      if (cutoff && t && new Date(t).getTime() < cutoff) return false;
      if (filterText) {
        const q = filterText.toLowerCase();
        const hay = `${cfg.getText(it)} ${cfg.getTitle(it)} ${cfg.getSubtitle(it)}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    // Sort: newest fetched_at first (falls back to published_at).
    // For firecrawl this shows the latest crawl's items at the top
    // regardless of the article's original publication date.
    result.sort((a, b) => {
      const ta = new Date(a.fetched_at || a.published_at || 0).getTime();
      const tb = new Date(b.fetched_at || b.published_at || 0).getTime();
      return tb - ta;
    });
    return result;
  }, [items, filterText, timeWindow, cfg]);

  // Pipeline stats (direct mode only — meaningful since raw items have processed flag)
  const pipelineStats = useMemo(() => {
    if (mode !== "direct") return null;
    const total     = items.length;
    const processed = items.filter(it => it.processed === true).length;
    const rejected  = items.filter(it => it.is_relevant === false || (it.tags || []).includes("not_relevant")).length;
    const accepted  = items.filter(it => it.processed && it.is_relevant !== false && !(it.tags || []).includes("not_relevant")).length;
    return { total, processed, accepted, rejected, pending: total - processed };
  }, [items, mode]);

  // Social Pulse — live aggregate of comment_sentiment across currently
  // loaded Facebook items. Not persisted — recomputed from `items` on every
  // poll, so it always reflects what's on screen right now.
  const socialPulse = useMemo(() => {
    if (sourceType !== "facebook") return null;
    const scored = items.filter(it => it.comment_sentiment);
    if (scored.length === 0) return null;
    const avg = (key) => Math.round(
      scored.reduce((sum, it) => sum + (it.comment_sentiment[key] || 0), 0) / scored.length
    );
    return { positive_pct: avg("positive_pct"), negative_pct: avg("negative_pct"), postCount: scored.length };
  }, [items, sourceType]);

  // ── Role gate — rendered AFTER all hooks (Rules of Hooks) ──────────────────
  if (!isAllowed) {
    return (
      <div className={`border-t ${borderColor} ${bgColor} p-6 flex flex-col items-center gap-2 text-center`}>
        <Lock size={20} className="text-muted-foreground/40" />
        <p className="text-xs text-muted-foreground font-mono">
          Social media feeds are restricted to <strong>Analyst</strong> and{" "}
          <strong>Admin</strong> users.
        </p>
      </div>
    );
  }

  return (
    <div className={`border-t ${borderColor} ${bgColor}`}>
      {/* ── Header ── */}
      <div className={`flex items-center gap-2 px-3 py-2 border-b border-border ${cfg.headerBg} flex-wrap`}>
        <Icon size={12} className={`${color} shrink-0`} />
        <span className={`text-[10px] uppercase tracking-widest font-bold ${color} font-['Barlow_Condensed']`}>
          {label} Live Feed
        </span>
        <span className="text-[9px] font-mono text-muted-foreground">
          {items.length} items
        </span>
        {lastUpdated && (
          <span className="text-[9px] font-mono text-muted-foreground/60 hidden sm:inline">
            · updated {timeAgo(lastUpdated.toISOString())} ago · auto 30s
          </span>
        )}

        {/* Pipeline mini-stats (direct mode) */}
        {pipelineStats && pipelineStats.total > 0 && (
          <div className="flex items-center gap-1.5 text-[9px] font-mono">
            <span className="text-emerald-400 flex items-center gap-0.5">
              <CheckCircle2 size={9} />{pipelineStats.accepted}
            </span>
            <span className="text-red-400/70 flex items-center gap-0.5">
              <XCircle size={9} />{pipelineStats.rejected}
            </span>
            {pipelineStats.pending > 0 && (
              <span className="text-amber-400 flex items-center gap-0.5">
                <Clock size={9} />{pipelineStats.pending}
              </span>
            )}
          </div>
        )}

        {/* Social Pulse — Facebook only, live aggregate of comment sentiment */}
        {socialPulse && (
          <div className="flex items-center gap-1.5 text-[9px] font-mono" title={`Aggregated from ${socialPulse.postCount} scored posts currently loaded`}>
            <span className="text-emerald-400 flex items-center gap-0.5">
              <ArrowUp size={9} />{socialPulse.positive_pct}%
            </span>
            <span className="text-red-400 flex items-center gap-0.5">
              <ArrowDown size={9} />{socialPulse.negative_pct}%
            </span>
          </div>
        )}

        {/* Direct / Curated toggle */}
        <div className="ml-auto flex items-center border border-border rounded-none overflow-hidden mr-1">
          <button
            onClick={() => setMode("direct")}
            className={`text-[9px] uppercase tracking-wider font-mono font-semibold h-6 px-2 transition-colors ${
              mode === "direct" ? `bg-emerald-500/20 text-emerald-300` : "text-muted-foreground hover:bg-muted/30"
            }`}
            title="All fetched items — no AI severity filter"
          >
            <Eye size={9} className="inline mr-1" />Raw
          </button>
          <button
            onClick={() => setMode("curated")}
            className={`text-[9px] uppercase tracking-wider font-mono font-semibold h-6 px-2 transition-colors border-l border-border ${
              mode === "curated" ? "bg-violet-500/20 text-violet-300" : "text-muted-foreground hover:bg-muted/30"
            }`}
            title="AI-classified items only (severity medium+ visible on Intelligence Feed)"
          >
            <Brain size={9} className="inline mr-1" />Curated
          </button>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={fetchNow} disabled={triggering}
            className="h-6 px-2 text-[9px] rounded-none font-mono uppercase border border-border hover:text-emerald-400"
            title="Trigger an immediate fetch on the backend">
            {triggering ? <Loader2 size={9} className="animate-spin mr-1" /> : <Zap size={9} className="mr-1" />}
            Fetch
          </Button>
          <Button variant="ghost" size="sm" onClick={() => load()} disabled={refreshing}
            className="h-6 px-2 text-[9px] rounded-none font-mono uppercase border border-border">
            {refreshing ? <Loader2 size={9} className="animate-spin" /> : <RefreshCw size={9} />}
          </Button>
          {onTogglePin && (
            <Button variant="ghost" size="sm" onClick={onTogglePin}
              className={`h-6 px-2 text-[9px] rounded-none font-mono uppercase border border-border ${
                pinned ? "text-amber-400 hover:text-amber-300" : "hover:text-amber-400"
              }`}
              title={pinned ? "Unpin from Dashboard" : "Pin to Dashboard top"}>
              {pinned ? <PinOff size={9} className="mr-1" /> : <Pin size={9} className="mr-1" />}
              {pinned ? "Unpin" : "Pin"}
            </Button>
          )}
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}
              className="h-6 px-2 rounded-none border border-border">
              <XIcon size={9} />
            </Button>
          )}
        </div>
      </div>

      {/* ── Twitter free-tier persistent banner ── */}
      {sourceType === "twitter" && twitterFreeTier && (
        <div className="flex items-start gap-2 px-3 py-2.5 border-b border-amber-500/30 bg-amber-500/8 text-amber-300">
          <AlertTriangle size={13} className="shrink-0 mt-0.5 text-amber-400" />
          <div className="text-[10px] font-mono leading-relaxed">
            <span className="font-semibold text-amber-300">Free API tier — Twitter data unavailable.</span>
            <span className="text-amber-300/70 ml-1">
              X/Twitter API v2 requires the <span className="text-amber-300">Basic plan ($100/mo)</span> to
              read public tweets. Your current Bearer Token is Free tier (post-only).
              Upgrade at{" "}
              <a href="https://developer.x.com/en/portal/dashboard"
                target="_blank" rel="noopener noreferrer"
                className="underline hover:text-amber-200">developer.x.com</a>
              , then update TWITTER_BEARER_TOKEN on Render — this banner will disappear automatically
              once tweets start flowing.
            </span>
          </div>
        </div>
      )}

      {/* ── Filters ── */}
      {items.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border/50 bg-card/30 flex-wrap">
          <Filter size={10} className="text-muted-foreground shrink-0" />
          <Input placeholder="Filter…" value={filterText} onChange={e => setFilterText(e.target.value)}
            className="rounded-none text-xs h-6 w-40" />
          <Select value={timeWindow} onValueChange={setTimeWindow}>
            <SelectTrigger className="rounded-none text-[10px] h-6 w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="24h" className="text-xs">Last 24h</SelectItem>
              <SelectItem value="7d"  className="text-xs">Last 7d</SelectItem>
              <SelectItem value="30d" className="text-xs">Last 30d</SelectItem>
              <SelectItem value="all" className="text-xs">All time</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-[9px] font-mono text-muted-foreground ml-auto">
            {filtered.length}/{items.length} {mode === "curated" ? "(AI)" : "(raw)"}
          </span>
        </div>
      )}

      {/* ── Body ── */}
      <div className={compact ? "max-h-[380px] overflow-y-auto" : "max-h-[640px] overflow-y-auto"}>
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex items-start gap-2 p-4 border-l-4 border-amber-500 bg-amber-500/5">
            <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-bold text-amber-400">Could not load {label} feed</p>
              <p className="text-muted-foreground font-mono mt-0.5">{error}</p>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-8 px-4">
            <Icon size={24} className="text-muted-foreground/30 mx-auto mb-2" />
            {items.length === 0 ? (
              <>
                <p className="text-xs text-muted-foreground mb-3">
                  No {label} data in the database yet.
                </p>

                {/* Status note from backend — shows API tier warnings / restrictions */}
                {statusNote && (
                  <div className={`text-left max-w-md mx-auto mb-3 p-2 border text-[10px] font-mono leading-relaxed ${
                    statusNote.includes("⚠")
                      ? "border-amber-500/40 bg-amber-500/5 text-amber-300"
                      : "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
                  }`}>
                    <AlertTriangle size={10} className="inline mr-1 shrink-0" />
                    {statusNote}
                  </div>
                )}

                <ul className="text-[10px] font-mono text-muted-foreground/70 text-left max-w-md mx-auto space-y-1 mb-3">
                  {cfg.emptyHint.map((h, i) => (
                    <li key={i}>{i + 1}. {h}</li>
                  ))}
                </ul>
                <Button size="sm" onClick={fetchNow} disabled={triggering}
                  className="rounded-none text-[10px] uppercase tracking-wider">
                  {triggering ? <Loader2 size={10} className="mr-1 animate-spin" /> : <Zap size={10} className="mr-1" />}
                  Trigger {label} Fetch Now
                </Button>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">No items match the current filter.</p>
            )}
          </div>
        ) : (
          <div>
            {filtered.map((it, idx) => (
              <FeedCard key={it.id || it.tweet_url || it.source_url || idx} item={it} cfg={cfg} api={api} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
