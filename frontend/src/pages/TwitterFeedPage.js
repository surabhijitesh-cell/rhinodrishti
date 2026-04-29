import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import {
  Twitter, RefreshCw, ExternalLink, Heart, Repeat2, Loader2,
  Filter, AlertTriangle, ListIcon,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";

const REFRESH_MS = 30000;

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)    return `${diff}s`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d`;
  return new Date(iso).toLocaleDateString();
}

function initials(name) {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(s => s[0]?.toUpperCase())
    .join("") || "?";
}

// ─── Tweet card ──────────────────────────────────────────────────────────────

function TweetCard({ tweet }) {
  const handle = (tweet.handle || "").replace(/^@/, "");
  const name   = tweet.account_name || handle || "Unknown";
  const text   = tweet.tweet_text || "";
  const likes  = tweet.likes || 0;
  const rts    = tweet.retweets || 0;

  return (
    <div className="border-b border-border p-4 hover:bg-muted/5 transition-colors group">
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-600 to-slate-800 flex items-center justify-center shrink-0 border border-slate-500/30">
          <span className="text-[11px] font-bold text-slate-200 font-mono">{initials(name)}</span>
        </div>

        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold text-foreground truncate">{name}</span>
            <span className="text-[11px] font-mono text-muted-foreground truncate">@{handle}</span>
            <span className="text-muted-foreground/40">·</span>
            <span className="text-[11px] font-mono text-muted-foreground" title={tweet.posted_at}>
              {timeAgo(tweet.posted_at)}
            </span>
            {tweet.list_name && (
              <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-emerald-500/10 text-emerald-400 border-emerald-500/20 ml-auto">
                <ListIcon size={8} className="mr-1" />
                {tweet.list_name}
              </Badge>
            )}
            {tweet.category && !tweet.list_name && (
              <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-slate-500/10 text-slate-300 border-slate-500/20 ml-auto">
                {tweet.category}
              </Badge>
            )}
          </div>

          {/* Tweet body */}
          <p className="text-sm leading-relaxed mt-1.5 whitespace-pre-wrap break-words">
            {text}
          </p>

          {/* Footer row */}
          <div className="flex items-center gap-4 mt-2.5">
            <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
              <Heart size={11} className="text-rose-400/70" />
              {likes.toLocaleString()}
            </span>
            <span className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
              <Repeat2 size={11} className="text-emerald-400/70" />
              {rts.toLocaleString()}
            </span>
            {tweet.tweet_url && (
              <a
                href={tweet.tweet_url}
                target="_blank"
                rel="noreferrer"
                className="ml-auto flex items-center gap-1 text-[10px] font-mono text-muted-foreground hover:text-primary transition-colors uppercase tracking-wider opacity-0 group-hover:opacity-100"
              >
                View on X <ExternalLink size={10} />
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function TwitterFeedPage({ api }) {
  const [tweets, setTweets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);

  // Filter state
  const [filterText, setFilterText] = useState("");
  const [filterSource, setFilterSource] = useState("all"); // all | list | account | search

  const fetchTweets = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      const res = await axios.get(`${api}/twitter-feeds?limit=100`);
      setTweets(res.data.feeds || []);
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      console.error("Twitter feed fetch failed:", e);
      setError(e.response?.data?.detail || "Failed to load tweets");
    }
    setLoading(false);
    setRefreshing(false);
  }, [api]);

  useEffect(() => {
    fetchTweets();
    const id = setInterval(() => fetchTweets(true), REFRESH_MS);
    return () => clearInterval(id);
  }, [fetchTweets]);

  // Apply client-side filters
  const filtered = useMemo(() => {
    return tweets.filter(t => {
      if (filterSource === "list" && !t.list_id) return false;
      if (filterSource === "account" && t.list_id) return false;
      if (filterSource === "account" && t.category === "search") return false;
      if (filterSource === "search" && t.category !== "search") return false;
      if (filterText) {
        const needle = filterText.toLowerCase();
        const haystack = `${t.tweet_text || ""} ${t.handle || ""} ${t.account_name || ""}`.toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
  }, [tweets, filterText, filterSource]);

  // Quick stats
  const stats = useMemo(() => {
    const out = { lists: 0, accounts: 0, searches: 0, total: tweets.length };
    for (const t of tweets) {
      if (t.list_id) out.lists++;
      else if (t.category === "search") out.searches++;
      else out.accounts++;
    }
    return out;
  }, [tweets]);

  return (
    <div className="space-y-4" data-testid="twitter-feed-page">
      {/* Header */}
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed'] flex items-center gap-3" data-testid="twitter-feed-title">
            <Twitter size={28} className="text-slate-300" />
            X / Twitter Live Feed
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            Latest tweets from monitored Lists, Accounts and Searches
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-[10px] font-mono text-muted-foreground">
              Updated {timeAgo(lastUpdated.toISOString())} ago
            </span>
          )}
          <Button
            variant="outline" size="sm"
            onClick={() => fetchTweets()}
            disabled={refreshing}
            className="rounded-none text-xs uppercase tracking-wider"
          >
            {refreshing ? (
              <><Loader2 size={12} className="mr-1.5 animate-spin" />Refreshing</>
            ) : (
              <><RefreshCw size={12} className="mr-1.5" />Refresh</>
            )}
          </Button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="rounded-none border-l-4 border-l-slate-400">
          <CardContent className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Total</p>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">{stats.total}</p>
          </CardContent>
        </Card>
        <Card className="rounded-none border-l-4 border-l-emerald-500">
          <CardContent className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">From Lists</p>
            <p className="text-2xl font-bold font-['Barlow_Condensed'] text-emerald-400">{stats.lists}</p>
          </CardContent>
        </Card>
        <Card className="rounded-none border-l-4 border-l-blue-500">
          <CardContent className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">From Accounts</p>
            <p className="text-2xl font-bold font-['Barlow_Condensed'] text-blue-400">{stats.accounts}</p>
          </CardContent>
        </Card>
        <Card className="rounded-none border-l-4 border-l-violet-500">
          <CardContent className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">From Searches</p>
            <p className="text-2xl font-bold font-['Barlow_Condensed'] text-violet-400">{stats.searches}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="rounded-none">
        <CardContent className="p-3 flex items-center gap-3 flex-wrap">
          <Filter size={14} className="text-muted-foreground shrink-0" />
          <Input
            placeholder="Filter by text or handle…"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="rounded-none text-sm flex-1 min-w-[200px] max-w-md"
            data-testid="twitter-filter-input"
          />
          <Select value={filterSource} onValueChange={setFilterSource}>
            <SelectTrigger className="rounded-none w-[180px]" data-testid="twitter-filter-source">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All Sources</SelectItem>
              <SelectItem value="list" className="text-xs">Lists Only</SelectItem>
              <SelectItem value="account" className="text-xs">Accounts Only</SelectItem>
              <SelectItem value="search" className="text-xs">Searches Only</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-[10px] font-mono text-muted-foreground ml-auto">
            Showing {filtered.length} of {tweets.length} · auto-refresh 30s
          </span>
        </CardContent>
      </Card>

      {/* Tweet list */}
      <Card className="rounded-none">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Twitter size={14} className="text-slate-300" />
            Tweet Feed
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 size={20} className="animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex items-start gap-3 p-6 border-l-4 border-amber-500 bg-amber-500/5">
              <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-bold text-amber-400">Failed to load tweets</p>
                <p className="text-xs text-muted-foreground font-mono mt-1">{error}</p>
              </div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Twitter size={32} className="text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {tweets.length === 0
                  ? "No tweets fetched yet. Configure a List or Accounts in Settings → Social Scan, then click Fetch Intel on the Dashboard."
                  : "No tweets match your filter."}
              </p>
            </div>
          ) : (
            <div data-testid="twitter-feed-list">
              {filtered.map((t) => (
                <TweetCard key={t.id || t.tweet_url} tweet={t} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
