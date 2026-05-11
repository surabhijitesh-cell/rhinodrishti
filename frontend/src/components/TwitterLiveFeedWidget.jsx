/**
 * TwitterLiveFeedWidget — embeddable tweet feed.
 *
 * Used inline in the Dashboard's SourceScanners drill-down panel AND as a
 * pinned widget at the top of the Dashboard. The same component handles
 * both placements; props control compact-mode + pin state.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import {
  Twitter, RefreshCw, ExternalLink, Heart, Repeat2, Loader2,
  Filter, AlertTriangle, Pin, PinOff, X as XIcon, Zap, Brain, Eye,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";

const REFRESH_MS = 30000;

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)     return `${diff}s`;
  if (diff < 3600)   return `${Math.floor(diff / 60)}m`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d`;
  return new Date(iso).toLocaleDateString();
}

function initials(name) {
  if (!name) return "?";
  return name.split(/\s+/).filter(Boolean).slice(0, 2)
    .map(s => s[0]?.toUpperCase()).join("") || "?";
}

function TweetCard({ tweet }) {
  const handle = (tweet.handle || "").replace(/^@/, "");
  const name   = tweet.account_name || handle || "Unknown";
  const text   = tweet.tweet_text || "";
  const likes  = tweet.likes || 0;
  const rts    = tweet.retweets || 0;

  return (
    <div className="border-b border-border px-3 py-2.5 hover:bg-muted/5 transition-colors group">
      <div className="flex items-start gap-2.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-slate-600 to-slate-800 flex items-center justify-center shrink-0 border border-slate-500/30">
          <span className="text-[9px] font-bold text-slate-200 font-mono">{initials(name)}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-foreground truncate">{name}</span>
            <span className="text-[10px] font-mono text-muted-foreground truncate">@{handle}</span>
            <span className="text-muted-foreground/40 text-[10px]">·</span>
            <span className="text-[10px] font-mono text-muted-foreground" title={tweet.posted_at}>
              {timeAgo(tweet.posted_at)}
            </span>
            {tweet.list_name && (
              <Badge className="rounded-none text-[8px] px-1 py-0 bg-emerald-500/10 text-emerald-400 border-emerald-500/20 ml-auto">
                {tweet.list_name}
              </Badge>
            )}
          </div>
          <p className="text-xs leading-relaxed mt-1 whitespace-pre-wrap break-words text-foreground/90">
            {text}
          </p>
          <div className="flex items-center gap-3 mt-1.5">
            <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
              <Heart size={10} className="text-rose-400/70" />{likes.toLocaleString()}
            </span>
            <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
              <Repeat2 size={10} className="text-emerald-400/70" />{rts.toLocaleString()}
            </span>
            {tweet.tweet_url && (
              <a href={tweet.tweet_url} target="_blank" rel="noreferrer"
                 className="ml-auto flex items-center gap-1 text-[10px] font-mono text-muted-foreground hover:text-primary uppercase tracking-wider opacity-0 group-hover:opacity-100">
                On X <ExternalLink size={9} />
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TwitterLiveFeedWidget({
  api,
  compact = true,
  pinned = false,
  onTogglePin,
  onClose,
}) {
  const [tweets, setTweets]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError]       = useState(null);

  // Filter state
  const [filterText, setFilterText]     = useState("");
  const [filterSource, setFilterSource] = useState("all");      // all | list | account | search
  const [timeWindow, setTimeWindow]     = useState("all");      // 24h | 7d | 30d | all
  const [hideLowEng, setHideLowEng]     = useState(false);      // hide tweets with likes+rts<5

  // DIRECT mode (default) → /api/twitter-feeds (raw tweets, no AI filter)
  // CURATED mode          → /api/intelligence?source_type=twitter (AI-classified, low-severity hidden)
  const [mode, setMode] = useState("direct");

  const load = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      let url;
      if (mode === "direct") {
        url = `${api}/twitter-feeds?limit=100`;
      } else {
        url = `${api}/intelligence?source_type=twitter&limit=100&sort_by=published_at&sort_order=desc`;
      }
      const res = await axios.get(url);

      // Normalize response shape — twitter-feeds returns {feeds:[...]},
      // intelligence returns {items:[...]} with different field names.
      let items = [];
      if (mode === "direct") {
        items = res.data.feeds || [];
      } else {
        items = (res.data.items || []).map(it => ({
          id:           it.id,
          handle:       it.source || "",
          account_name: (it.title || "").replace(/^Tweet by\s*/i, ""),
          tweet_text:   it.raw_content || it.ai_summary || "",
          tweet_url:    it.source_url,
          posted_at:    it.published_at,
          likes:        0,                         // not preserved in intel pipeline
          retweets:     0,
          category:     it.threat_category || "",
          severity:     it.severity,
          priority:     it.priority_score,
          state:        it.state,
        }));
      }
      setTweets(items);
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      console.error("twitter widget fetch failed:", e);
      setError(e.response?.data?.detail || e.message || "Failed to load tweets");
    }
    setLoading(false);
    setRefreshing(false);
  }, [api, mode]);

  useEffect(() => {
    load();
    const id = setInterval(() => load(true), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  // Trigger an immediate Twitter fetch on the backend, then poll for results
  const fetchNow = async () => {
    setTriggering(true);
    try {
      await axios.post(`${api}/social/fetch-all`);
      toast.success("Twitter fetch triggered — new tweets will appear shortly");
      // Poll a few times — list/list_id endpoints typically return in 5-15s
      const delays = [8000, 18000, 35000, 60000];
      delays.forEach((d, i) => setTimeout(() => {
        load(true);
        if (i === delays.length - 1) setTriggering(false);
      }, d));
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fetch trigger failed");
      setTriggering(false);
    }
  };

  const filtered = useMemo(() => {
    const windowMs = {
      "24h": 24 * 3600 * 1000,
      "7d":   7 * 86400 * 1000,
      "30d": 30 * 86400 * 1000,
    }[timeWindow] || null;
    const cutoff = windowMs ? Date.now() - windowMs : null;

    return tweets.filter(t => {
      // Source-type filter (only meaningful in direct mode)
      if (mode === "direct") {
        if (filterSource === "list"    && !t.list_id) return false;
        if (filterSource === "account" && (t.list_id || t.category === "search")) return false;
        if (filterSource === "search"  && t.category !== "search") return false;
      }
      // Time-window filter
      if (cutoff && t.posted_at && new Date(t.posted_at).getTime() < cutoff) return false;
      // Engagement filter (direct mode only — intel items don't preserve like/RT counts)
      if (mode === "direct" && hideLowEng && (t.likes || 0) + (t.retweets || 0) < 5) return false;
      // Text search across body / handle / name
      if (filterText) {
        const n = filterText.toLowerCase();
        const h = `${t.tweet_text||""} ${t.handle||""} ${t.account_name||""}`.toLowerCase();
        if (!h.includes(n)) return false;
      }
      return true;
    });
  }, [tweets, filterText, filterSource, timeWindow, hideLowEng, mode]);

  const stats = useMemo(() => {
    const out = { lists: 0, accounts: 0, searches: 0 };
    for (const t of tweets) {
      if (t.list_id) out.lists++;
      else if (t.category === "search") out.searches++;
      else out.accounts++;
    }
    return out;
  }, [tweets]);

  return (
    <div className="border-t border-slate-500/20 bg-slate-500/5">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-card/60 flex-wrap">
        <Twitter size={12} className="text-slate-300 shrink-0" />
        <span className="text-[10px] uppercase tracking-widest font-bold text-slate-300 font-['Barlow_Condensed']">
          Live Tweet Feed
        </span>
        <span className="text-[9px] font-mono text-muted-foreground">
          {tweets.length} total · {stats.lists} list · {stats.accounts} acct · {stats.searches} srch
        </span>
        {lastUpdated && (
          <span className="text-[9px] font-mono text-muted-foreground/60 hidden sm:inline">
            updated {timeAgo(lastUpdated.toISOString())} ago · auto 30s
          </span>
        )}

        {/* DIRECT / CURATED toggle — pill-style segmented control */}
        <div className="ml-auto flex items-center border border-border rounded-none overflow-hidden mr-1" data-testid="tw-mode-toggle">
          <button
            onClick={() => setMode("direct")}
            className={`text-[9px] uppercase tracking-wider font-mono font-semibold h-6 px-2 transition-colors ${
              mode === "direct"
                ? "bg-emerald-500/20 text-emerald-300"
                : "text-muted-foreground hover:bg-muted/30"
            }`}
            title="Show all fetched tweets directly from twitter_feeds (no AI filter, no severity gate)"
          >
            <Eye size={9} className="inline mr-1" />Direct
          </button>
          <button
            onClick={() => setMode("curated")}
            className={`text-[9px] uppercase tracking-wider font-mono font-semibold h-6 px-2 transition-colors border-l border-border ${
              mode === "curated"
                ? "bg-violet-500/20 text-violet-300"
                : "text-muted-foreground hover:bg-muted/30"
            }`}
            title="Show AI-classified tweets only — filters out low-severity items and unprocessed tweets"
          >
            <Brain size={9} className="inline mr-1" />Curated
          </button>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost" size="sm"
            onClick={fetchNow}
            disabled={triggering}
            className="h-6 px-2 text-[9px] rounded-none font-mono uppercase border border-border hover:text-emerald-400"
            title="Trigger an immediate Twitter fetch on the backend"
          >
            {triggering ? <Loader2 size={9} className="animate-spin mr-1" /> : <Zap size={9} className="mr-1" />}
            Fetch
          </Button>
          <Button
            variant="ghost" size="sm"
            onClick={() => load()}
            disabled={refreshing}
            className="h-6 px-2 text-[9px] rounded-none font-mono uppercase border border-border"
          >
            {refreshing ? <Loader2 size={9} className="animate-spin" /> : <RefreshCw size={9} />}
          </Button>
          {onTogglePin && (
            <Button
              variant="ghost" size="sm"
              onClick={onTogglePin}
              className={`h-6 px-2 text-[9px] rounded-none font-mono uppercase border border-border ${
                pinned ? "text-amber-400 hover:text-amber-300" : "hover:text-amber-400"
              }`}
              title={pinned ? "Unpin from Dashboard" : "Pin to Dashboard"}
            >
              {pinned ? <PinOff size={9} className="mr-1" /> : <Pin size={9} className="mr-1" />}
              {pinned ? "Unpin" : "Pin"}
            </Button>
          )}
          {onClose && (
            <Button
              variant="ghost" size="sm"
              onClick={onClose}
              className="h-6 px-2 rounded-none border border-border"
              title="Close"
            >
              <XIcon size={9} />
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      {tweets.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border/50 bg-card/30 flex-wrap">
          <Filter size={10} className="text-muted-foreground shrink-0" />
          <Input
            placeholder="Filter…"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="rounded-none text-xs h-6 w-44"
          />

          {/* Source-type — only meaningful in direct mode (curated lacks list_id metadata) */}
          {mode === "direct" && (
            <Select value={filterSource} onValueChange={setFilterSource}>
              <SelectTrigger className="rounded-none text-[10px] h-6 w-28" title="Filter by where the tweet came from"><SelectValue /></SelectTrigger>
              <SelectContent className="rounded-none">
                <SelectItem value="all"     className="text-xs">All Sources</SelectItem>
                <SelectItem value="list"    className="text-xs">Lists Only</SelectItem>
                <SelectItem value="account" className="text-xs">Accounts Only</SelectItem>
                <SelectItem value="search"  className="text-xs">Searches Only</SelectItem>
              </SelectContent>
            </Select>
          )}

          {/* Time window */}
          <Select value={timeWindow} onValueChange={setTimeWindow}>
            <SelectTrigger className="rounded-none text-[10px] h-6 w-24" title="Restrict to a recent time window"><SelectValue /></SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="24h" className="text-xs">Last 24h</SelectItem>
              <SelectItem value="7d"  className="text-xs">Last 7d</SelectItem>
              <SelectItem value="30d" className="text-xs">Last 30d</SelectItem>
              <SelectItem value="all" className="text-xs">All Time</SelectItem>
            </SelectContent>
          </Select>

          {/* Hide low-engagement toggle (direct mode only) */}
          {mode === "direct" && (
            <button
              onClick={() => setHideLowEng(v => !v)}
              className={`text-[9px] uppercase tracking-wider font-mono h-6 px-2 border border-border rounded-none transition-colors ${
                hideLowEng ? "bg-amber-500/15 text-amber-300 border-amber-500/30" : "text-muted-foreground hover:bg-muted/20"
              }`}
              title="Hide tweets with fewer than 5 total likes+retweets"
            >
              {hideLowEng ? "Hi-Eng ✓" : "Hi-Eng"}
            </button>
          )}

          <span className="text-[9px] font-mono text-muted-foreground ml-auto">
            {filtered.length} of {tweets.length} {mode === "curated" ? "(AI)" : "(raw)"}
          </span>
        </div>
      )}

      {/* Body */}
      <div
        className={compact ? "max-h-[380px] overflow-y-auto" : "max-h-[640px] overflow-y-auto"}
      >
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex items-start gap-2 p-4 border-l-4 border-amber-500 bg-amber-500/5">
            <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-bold text-amber-400">Could not load tweets</p>
              <p className="text-muted-foreground font-mono mt-0.5">{error}</p>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-8 px-4">
            <Twitter size={24} className="text-muted-foreground/30 mx-auto mb-2" />
            {tweets.length === 0 ? (
              <>
                <p className="text-xs text-muted-foreground mb-3">
                  No tweets in the database yet.
                </p>
                <ul className="text-[10px] font-mono text-muted-foreground/70 text-left max-w-md mx-auto space-y-1 mb-3">
                  <li>1. Confirm <code className="text-slate-300">TWITTER_BEARER_TOKEN</code> is set</li>
                  <li>2. Add a List in <strong>Settings → Social Scan → X/Twitter</strong></li>
                  <li>3. Click the <strong>Fetch</strong> button above (or "Fetch Intel" on the Dashboard)</li>
                  <li>4. Wait ~10–60s for tweets to land</li>
                </ul>
                <Button
                  size="sm"
                  onClick={fetchNow}
                  disabled={triggering}
                  className="rounded-none text-[10px] uppercase tracking-wider"
                >
                  {triggering ? <Loader2 size={10} className="mr-1 animate-spin" /> : <Zap size={10} className="mr-1" />}
                  Trigger Twitter Fetch Now
                </Button>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">No tweets match your filter.</p>
            )}
          </div>
        ) : (
          <div>
            {filtered.map((t) => <TweetCard key={t.id || t.tweet_url} tweet={t} />)}
          </div>
        )}
      </div>
    </div>
  );
}
