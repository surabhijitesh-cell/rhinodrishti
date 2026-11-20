import { useState, useEffect, useCallback } from "react";
import { Navigate } from "react-router-dom";
import {
  Clock, Save, RefreshCw,
  Loader2, Rss, Plus, Trash2, Globe,
  Youtube, Activity, Radio, Play,
  AlertTriangle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import LoadError from "../components/LoadError";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";

const RETENTION_OPTIONS = [
  { value: "7", label: "7 days" },
  { value: "14", label: "14 days" },
  { value: "30", label: "30 days (default)" },
  { value: "60", label: "60 days" },
  { value: "90", label: "90 days" },
  { value: "180", label: "180 days" },
  { value: "365", label: "365 days" },
];

export default function SettingsPage({ api }) {
  const { user } = useAuth();

  // Block viewer access — redirect to dashboard
  if (user?.role === "viewer") {
    return <Navigate to="/" replace />;
  }

  return <SettingsContent api={api} />;
}

function SettingsContent({ api }) {
  const [retentionDays, setRetentionDays] = useState("30");
  const [savingRetention, setSavingRetention] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  const fetch = async () => {
    try {
      const res = await axios.get(`${api}/settings/retention`);
      setRetentionDays(String(res.data.retention_days || 30));
      setLoadFailed(false);
    } catch (e) {
      console.error("Failed to fetch retention setting:", e);
      setLoadFailed(true);
    }
    setLoading(false);
  };

  useEffect(() => { fetch(); }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSaveRetention = async () => {
    setSavingRetention(true);
    try {
      const res = await axios.put(`${api}/settings/retention`, {
        retention_days: parseInt(retentionDays, 10),
      });
      toast.success(res.data.message || "Retention window updated");
    } catch (e) {
      toast.error("Failed to update retention setting");
    }
    setSavingRetention(false);
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="settings-title" data-tour="settings-title">
          Platform Settings
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Configure intelligence platform parameters
        </p>
      </div>

      {/* RSS Feed Management — Full width */}
      <RssFeedManager api={api} />

      {/* Social Media Scan Configuration — Full width */}
      <SocialScanManager api={api} />

      {/* News Retention Window */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="border border-border rounded-none bg-card" data-testid="retention-card" data-tour="retention-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <Clock size={16} className="text-primary" />
              News Retention Window
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            <p className="text-xs text-muted-foreground">
              How many days of intelligence data to display. Older items remain in the database but won't appear in stats.
            </p>
            {loadFailed && <LoadError what="the current retention setting" onRetry={fetch} />}
            <div className="flex items-center gap-3">
              <Select value={retentionDays} onValueChange={setRetentionDays} disabled={loading}>
                <SelectTrigger className="w-[200px] rounded-none" data-testid="retention-select">
                  <SelectValue placeholder="Select retention" />
                </SelectTrigger>
                <SelectContent className="rounded-none">
                  {RETENTION_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value} className="text-sm">{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button onClick={handleSaveRetention} disabled={savingRetention || loadFailed} className="uppercase text-xs font-bold tracking-wider rounded-none" data-testid="save-retention-btn">
                {savingRetention ? <RefreshCw size={14} className="mr-1.5 animate-spin" /> : <Save size={14} className="mr-1.5" />}
                Save
              </Button>
            </div>
            <div className="p-2.5 border border-border bg-muted/10">
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Current: </span>
              <span className="text-base font-bold font-['Barlow_Condensed']" data-testid="retention-current">{retentionDays} days</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}


// ─── Social Media Scan Manager ────────────────────────────────────────────────

const SM_CATS = ["media", "government", "defense", "paramilitary", "general", "intelligence"];
const SM_TABS = [
  { id: "youtube",   label: "YouTube",   Icon: Youtube,  accent: "text-red-400"    },
  { id: "telegram",  label: "Telegram",  Icon: Radio,    accent: "text-sky-400"    },
];

function useSocialStatus(api) {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    let cancelled = false;
    axios.get(`${api}/social/status`)
      .then(r => { if (!cancelled) setStatus(r.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [api]);
  return status;
}

function PlatformBanner({ status, platformId }) {
  if (!status || !status[platformId]) return null;
  const p = status[platformId];
  if (p.available) return null;
  return (
    <div className="border border-amber-500/30 bg-amber-500/5 p-3 flex items-start gap-3 mb-3">
      <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-wider text-amber-400 font-['Barlow_Condensed']">
          Source Currently Disabled
        </p>
        <p className="text-[10px] text-muted-foreground font-mono leading-relaxed mt-1">
          {p.note}
        </p>
        <p className="text-[10px] text-muted-foreground/70 font-mono mt-1">
          You can still configure sources below — fetching will resume once the API key is set.
        </p>
      </div>
    </div>
  );
}

function useSourceList(api, path, listKey) {
  const [items, setItems]     = useState([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}${path}`);
      setItems(res.data[listKey] || []);
    } catch (e) { console.error(`fetch ${path} failed`, e); }
    setLoading(false);
  }, [api, path, listKey]);
  useEffect(() => { load(); }, [load]);
  return { items, loading, refresh: load };
}

function SmRow({ item, primary, secondary, badge, onDelete, deleting, onAction, actionLabel, actioning }) {
  const busy = deleting === item.id;
  const running = actioning === item.id;
  return (
    <div className="px-3 py-2.5 flex items-center gap-3 hover:bg-muted/5 group">
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{primary}</p>
        {secondary && <p className="text-[9px] font-mono text-muted-foreground/60 truncate mt-0.5">{secondary}</p>}
      </div>
      {badge && (
        <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-muted text-muted-foreground border-border shrink-0">{badge}</Badge>
      )}
      {item.active === false && (
        <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-amber-500/10 text-amber-400 border-amber-500/20 shrink-0">paused</Badge>
      )}
      {onAction && (
        <button
          onClick={() => onAction(item.id)}
          disabled={running || busy}
          className="p-1 shrink-0 text-muted-foreground/30 hover:text-orange-400 transition-colors opacity-0 group-hover:opacity-100"
          title={actionLabel || "Run now"}
        >
          {running ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
        </button>
      )}
      <button
        onClick={() => onDelete(item.id)}
        disabled={busy}
        className="p-1 shrink-0 text-muted-foreground/30 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
        title="Remove"
      >
        {busy ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
      </button>
    </div>
  );
}

function SmSection({ accent, title, items, loading, renderRow, showForm, setShowForm, addLabel, form }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className={`text-[10px] uppercase tracking-widest font-mono font-semibold ${accent}`}>
          {title}
          <span className="text-muted-foreground font-normal ml-2">({loading ? "…" : items.length})</span>
        </p>
        {!showForm && (
          <Button
            variant="outline" size="sm"
            className="rounded-none text-[10px] h-6 px-2 uppercase tracking-wider"
            onClick={() => setShowForm(true)}
          >
            <Plus size={10} className="mr-1" />{addLabel}
          </Button>
        )}
      </div>
      {showForm && form}
      {loading ? (
        <div className="flex items-center gap-2 py-3"><Loader2 size={12} className="animate-spin text-muted-foreground" /><span className="text-[10px] text-muted-foreground font-mono">Loading…</span></div>
      ) : items.length === 0 ? (
        <p className="text-[10px] text-muted-foreground font-mono py-2.5 px-3 border border-dashed border-border">None configured</p>
      ) : (
        <div className="divide-y divide-border border border-border">{items.map(renderRow)}</div>
      )}
    </div>
  );
}

// ── YouTube Tab ───────────────────────────────────────────────────────────────

function YouTubeTab({ api }) {
  const ch = useSourceList(api, "/social/youtube/channels", "channels");
  const sr = useSourceList(api, "/social/youtube/searches", "searches");
  const [del, setDel] = useState(null);
  const [showCh, setShowCh] = useState(false);
  const [showSr, setShowSr] = useState(false);
  const [chName, setChName] = useState(""); const [chId, setChId] = useState(""); const [chCat, setChCat] = useState("media");
  const [srQ, setSrQ] = useState(""); const [srMax, setSrMax] = useState(5);
  const [adding, setAdding] = useState(false);

  const handleDel = async (path, refresh, id) => {
    setDel(id);
    try { await axios.delete(`${api}${path}/${id}`); refresh(); toast.success("Removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const addCh = async (e) => {
    e.preventDefault(); if (!chName.trim() || !chId.trim()) return;
    setAdding("ch");
    try { await axios.post(`${api}/social/youtube/channels`, { name: chName.trim(), channel_id: chId.trim(), category: chCat });
      toast.success("Channel added"); setChName(""); setChId(""); setShowCh(false); ch.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };
  const addSr = async (e) => {
    e.preventDefault(); if (!srQ.trim()) return;
    setAdding("sr");
    try { await axios.post(`${api}/social/youtube/searches`, { query: srQ.trim(), max_results: srMax });
      toast.success("Search added"); setSrQ(""); setShowSr(false); sr.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <div className="space-y-5">
      <SmSection
        accent="text-red-400" title="Channels" items={ch.items} loading={ch.loading}
        showForm={showCh} setShowForm={setShowCh} addLabel="Add Channel"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`Channel ID: ${item.channel_id}`} badge={item.category} onDelete={id=>handleDel("/social/youtube/channels", ch.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addCh} className="border border-red-500/20 bg-red-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Channel Name *</label>
                <Input value={chName} onChange={e=>setChName(e.target.value)} placeholder="e.g. DD News" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Channel ID *</label>
                <Input value={chId} onChange={e=>setChId(e.target.value)} placeholder="UCxxxxxxxxxxxxxxxxxxx" className="rounded-none text-xs h-8 font-mono" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
                <Select value={chCat} onValueChange={setChCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none">{SM_CATS.map(c=><SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="ch"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="ch"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Channel</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowCh(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
      <SmSection
        accent="text-red-400" title="Keyword Searches" items={sr.items} loading={sr.loading}
        showForm={showSr} setShowForm={setShowSr} addLabel="Add Search"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.query} secondary={`${item.max_results} results per run`} onDelete={id=>handleDel("/social/youtube/searches", sr.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addSr} className="border border-red-500/20 bg-red-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Search Query *</label>
                <Input value={srQ} onChange={e=>setSrQ(e.target.value)} placeholder="e.g. Assam border incident" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Max Results</label>
                <Input type="number" value={srMax} onChange={e=>setSrMax(parseInt(e.target.value)||5)} min={1} max={50} className="rounded-none text-xs h-8" /></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="sr"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="sr"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Search</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowSr(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
    </div>
  );
}


// ── Telegram Tab ──────────────────────────────────────────────────────────────

function TelegramTab({ api }) {
  const ch = useSourceList(api, "/social/telegram/channels", "channels");
  const [del, setDel] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [tgUser, setTgUser] = useState(""); const [tgName, setTgName] = useState(""); const [tgCat, setTgCat] = useState("media");
  const [adding, setAdding] = useState(false);

  const handleDel = async (id) => {
    setDel(id);
    try { await axios.delete(`${api}/social/telegram/channels/${id}`); ch.refresh(); toast.success("Channel removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const handleAdd = async (e) => {
    e.preventDefault(); if (!tgUser.trim() || !tgName.trim()) return;
    setAdding(true);
    try { await axios.post(`${api}/social/telegram/channels`, { username: tgUser.trim().replace(/^@/, ""), name: tgName.trim(), category: tgCat });
      toast.success("Channel added"); setTgUser(""); setTgName(""); setShowForm(false); ch.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <SmSection
      accent="text-sky-400" title="Channels" items={ch.items} loading={ch.loading}
      showForm={showForm} setShowForm={setShowForm} addLabel="Add Channel"
      renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`@${item.username}`} badge={item.category} onDelete={handleDel} deleting={del} />}
      form={
        <form onSubmit={handleAdd} className="border border-sky-500/20 bg-sky-500/5 p-3 space-y-2 mb-1">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Username (no @) *</label>
              <Input value={tgUser} onChange={e=>setTgUser(e.target.value)} placeholder="e.g. BSFIndia" className="rounded-none text-xs h-8 font-mono" /></div>
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Display Name *</label>
              <Input value={tgName} onChange={e=>setTgName(e.target.value)} placeholder="e.g. BSF India Official" className="rounded-none text-xs h-8" /></div>
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
              <Select value={tgCat} onValueChange={setTgCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                <SelectContent className="rounded-none">{SM_CATS.map(c=><SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}</SelectContent></Select></div>
          </div>
          <div className="flex gap-2">
            <Button type="submit" disabled={adding} size="sm" className="rounded-none text-[10px] uppercase h-7">
              {adding?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Channel</Button>
            <Button type="button" variant="outline" size="sm" onClick={()=>setShowForm(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
          </div>
        </form>
      }
    />
  );
}

// ── Main Social Scan Manager ─────────────────────────────────────────────────

function SocialScanManager({ api }) {
  const [activeTab, setActiveTab] = useState("youtube");
  const active = SM_TABS.find(t => t.id === activeTab);
  const status = useSocialStatus(api);

  const renderTab = () => {
    switch (activeTab) {
      case "youtube":   return <YouTubeTab api={api} />;
      case "telegram":  return <TelegramTab api={api} />;
      default: return null;
    }
  };

  const tabDesc = {
    youtube:   "channels and keyword searches",
    telegram:  "channels",
  };

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500" data-testid="social-scan-manager" data-tour="social-scan-manager">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Activity size={16} className="text-violet-400" />
          Social Media Scan Configuration
          <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-violet-500/20 text-violet-400 border-violet-500/30 ml-1">
            {SM_TABS.length} platforms
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {/* Tab bar */}
        <div className="flex border-b border-border overflow-x-auto">
          {SM_TABS.map(tab => {
            const { Icon } = tab;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                data-testid={`sm-tab-${tab.id}`}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider whitespace-nowrap transition-colors border-b-2 ${
                  isActive
                    ? `${tab.accent} border-current bg-muted/5`
                    : "text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/5"
                }`}
              >
                <Icon size={12} />
                {tab.label}
              </button>
            );
          })}
        </div>
        {/* Tab content */}
        <div className="p-4">
          <p className="text-[10px] text-muted-foreground font-mono mb-4">
            Configure which {active?.label} {tabDesc[activeTab]} are scanned during each intelligence fetch cycle. Changes apply on the next fetch.
          </p>
          <PlatformBanner status={status} platformId={activeTab} />
          {renderTab()}
        </div>
      </CardContent>
    </Card>
  );
}


const CATEGORIES = [
  { value: "regional", label: "Regional (NER)" },
  { value: "national", label: "National (India)" },
  { value: "bangladesh", label: "Bangladesh" },
  { value: "myanmar", label: "Myanmar" },
  { value: "international", label: "International" },
  { value: "government", label: "Government" },
];
const PRIORITIES = [
  { value: "grassroots", label: "Grassroots (every 60 min)" },
  { value: "standard", label: "Standard (every 30 min)" },
  { value: "elite", label: "Elite (every 12 hours)" },
];
const REGIONS = [
  "NER", "Assam", "Manipur", "Meghalaya", "Mizoram", "Tripura",
  "Nagaland", "Arunachal Pradesh", "Sikkim", "India",
  "Bangladesh", "Myanmar", "International",
];

function RssFeedManager({ api }) {
  const [feeds, setFeeds] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState("national");
  const [language, setLanguage] = useState("en");
  const [region, setRegion] = useState("India");
  const [priority, setPriority] = useState("standard");
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState(null);

  const fetchFeeds = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/settings/rss-feeds`);
      setFeeds(res.data);
    } catch (e) {
      console.error("Failed to fetch feeds:", e);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchFeeds(); }, [fetchFeeds]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!name.trim() || !url.trim()) return;
    setAdding(true);
    try {
      const res = await axios.post(`${api}/settings/rss-feeds`, {
        name: name.trim(), url: url.trim(), category, language: language.trim(), region, priority,
      });
      toast.success(res.data.message || "Feed added");
      setName(""); setUrl(""); setShowForm(false);
      fetchFeeds();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add feed");
    }
    setAdding(false);
  };

  const handleDelete = async (feedUrl) => {
    setDeleting(feedUrl);
    try {
      await axios.delete(`${api}/settings/rss-feeds?url=${encodeURIComponent(feedUrl)}`);
      toast.success("Feed removed");
      fetchFeeds();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to remove feed");
    }
    setDeleting(null);
  };

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-emerald-500" data-testid="rss-feed-manager" data-tour="rss-manager">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Rss size={16} className="text-emerald-400" />
          RSS Feed Management
          {feeds && (
            <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-emerald-500/15 text-emerald-400 border-emerald-500/30 ml-2">
              {feeds.total} Sources ({feeds.builtin_count} built-in + {feeds.custom_count} custom)
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <p className="text-xs text-muted-foreground">
          Add custom RSS feeds to expand intelligence coverage. Custom feeds are included in the regular scanning schedule alongside the {feeds?.builtin_count || 89} built-in sources.
        </p>

        {/* Add Feed Form */}
        {!showForm ? (
          <Button
            variant="outline" size="sm"
            className="rounded-none text-xs uppercase tracking-wider border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
            onClick={() => setShowForm(true)}
            data-testid="show-add-feed-form"
          >
            <Plus size={12} className="mr-1.5" /> Add New RSS Feed
          </Button>
        ) : (
          <form onSubmit={handleAdd} className="border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-3" data-testid="add-feed-form">
            <p className="text-[10px] uppercase tracking-widest text-emerald-400 font-mono font-semibold">New RSS Feed</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Feed Name *</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Defense News India" className="rounded-none text-sm" data-testid="feed-name-input" />
              </div>
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">RSS URL *</label>
                <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/rss/feed" className="rounded-none text-sm font-mono" data-testid="feed-url-input" />
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Category</label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger className="rounded-none text-xs" data-testid="feed-category-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none">
                    {CATEGORIES.map((c) => <SelectItem key={c.value} value={c.value} className="text-xs">{c.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Region</label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger className="rounded-none text-xs" data-testid="feed-region-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none max-h-48">
                    {REGIONS.map((r) => <SelectItem key={r} value={r} className="text-xs">{r}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Scan Priority</label>
                <Select value={priority} onValueChange={setPriority}>
                  <SelectTrigger className="rounded-none text-xs" data-testid="feed-priority-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none">
                    {PRIORITIES.map((p) => <SelectItem key={p.value} value={p.value} className="text-xs">{p.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Language</label>
                <Input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en" className="rounded-none text-xs" data-testid="feed-language-input" />
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding || !name.trim() || !url.trim()} className="rounded-none text-xs uppercase tracking-wider" data-testid="submit-feed-btn">
                {adding ? <Loader2 size={12} className="mr-1.5 animate-spin" /> : <Plus size={12} className="mr-1.5" />}
                Add Feed
              </Button>
              <Button type="button" variant="outline" onClick={() => setShowForm(false)} className="rounded-none text-xs">Cancel</Button>
            </div>
          </form>
        )}

        {/* Custom Feeds List */}
        {feeds?.custom_feeds?.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono font-semibold mb-2">
              Custom Feeds ({feeds.custom_feeds.length})
            </p>
            <div className="divide-y divide-border border border-border">
              {feeds.custom_feeds.map((f) => (
                <div key={f.url} className="p-3 flex items-center gap-3 hover:bg-muted/5" data-testid={`custom-feed-${f.name}`}>
                  <Globe size={14} className="text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{f.name}</p>
                    <div className="flex items-center gap-2 flex-wrap mt-0.5">
                      <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-emerald-500/10 text-emerald-400 border-emerald-500/20">{f.category}</Badge>
                      <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-muted text-muted-foreground border-border">{f.region}</Badge>
                      <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-muted text-muted-foreground border-border">{f.priority}</Badge>
                      <span className="text-[9px] font-mono text-muted-foreground/50 truncate">{f.url}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(f.url)}
                    disabled={deleting === f.url}
                    className="p-1.5 text-muted-foreground/40 hover:text-red-400 transition-colors shrink-0"
                    title="Remove feed"
                    data-testid={`delete-feed-${f.name}`}
                  >
                    {deleting === f.url ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-4">
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
