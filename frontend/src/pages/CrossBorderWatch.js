import { useState, useEffect } from "react";
import {
  Globe, ShieldAlert, AlertTriangle, TrendingUp, TrendingDown,
  Eye, Loader2, ChevronDown, ChevronUp, ExternalLink, Filter,
  Handshake, Swords, Landmark, BarChart3, Trash2, RefreshCw
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import Tip from "../components/Tip";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import axios from "axios";

const POSTURE_CONFIG = {
  deteriorating: { color: "text-red-400 border-red-500/40 bg-red-500/10", label: "DETERIORATING", icon: TrendingDown },
  elevated: { color: "text-orange-400 border-orange-500/40 bg-orange-500/10", label: "ELEVATED", icon: AlertTriangle },
  watchful: { color: "text-amber-400 border-amber-500/40 bg-amber-500/10", label: "WATCHFUL", icon: Eye },
  stable: { color: "text-emerald-400 border-emerald-500/40 bg-emerald-500/10", label: "STABLE", icon: ShieldAlert },
};

const CATEGORY_ICONS = {
  diplomatic: Handshake,
  defence: Swords,
  internal_politics: Landmark,
  economics: BarChart3,
  other: Globe,
};

const CATEGORY_COLORS = {
  diplomatic: "text-blue-400 border-blue-500/30",
  defence: "text-red-400 border-red-500/30",
  internal_politics: "text-purple-400 border-purple-500/30",
  economics: "text-emerald-400 border-emerald-500/30",
  other: "text-muted-foreground border-border",
};

function SignalItem({ item, index, onDelete }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-border/50 last:border-b-0" data-testid={`signal-item-${item.id}`}>
      <div
        className="p-3 cursor-pointer flex items-start gap-3 hover:bg-muted/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs font-mono text-muted-foreground/50 w-5 shrink-0 mt-0.5">{index}.</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-snug">{item.title}</p>
          {!expanded && item.ai_summary && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{item.ai_summary}</p>
          )}
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            {item.severity && (
              <Badge variant="outline" className={`rounded-none text-[8px] px-1.5 py-0 ${
                item.severity === "critical" ? "text-red-400 border-red-500/30" :
                item.severity === "high" ? "text-orange-400 border-orange-500/30" :
                item.severity === "medium" ? "text-amber-400 border-amber-500/30" :
                "text-muted-foreground border-border"
              }`}>
                {item.severity.toUpperCase()}
              </Badge>
            )}
            {item.threat_trajectory && item.threat_trajectory !== "INDETERMINATE" && item.threat_trajectory !== "STABLE" && (
              <Badge variant="outline" className={`rounded-none text-[8px] px-1.5 py-0 ${
                item.threat_trajectory === "ESCALATING" ? "text-red-400 border-red-500/30" :
                item.threat_trajectory === "DE-ESCALATING" ? "text-emerald-400 border-emerald-500/30" :
                item.threat_trajectory === "NEW_THREAT" ? "text-amber-400 border-amber-500/30" :
                "text-muted-foreground border-border"
              }`}>
                {item.threat_trajectory}
              </Badge>
            )}
            {item.feedback_boosted && (
              <Badge variant="outline" className="rounded-none text-[8px] px-1 py-0 text-primary border-primary/30">
                ANALYST BOOSTED
              </Badge>
            )}
            <span className="text-[9px] font-mono text-muted-foreground/60 ml-auto">{item.source}</span>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0 mt-1">
          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm("Delete this intelligence item?")) onDelete(item.id);
              }}
              className="p-1 text-muted-foreground/30 hover:text-red-400 transition-colors"
              title="Delete"
              data-testid={`delete-signal-${item.id}`}
            >
              <Trash2 size={11} />
            </button>
          )}
          {expanded ? <ChevronUp size={12} className="text-muted-foreground" /> :
                      <ChevronDown size={12} className="text-muted-foreground" />}
        </div>
      </div>

      {expanded && (
        <div className="px-3 pb-3 pl-11 space-y-2 border-t border-border/30">
          {item.ai_summary && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">What happened</p>
              <p className="text-xs mt-0.5">{item.ai_summary}</p>
            </div>
          )}
          {item.why_it_matters && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">India-relevant implication</p>
              <p className="text-xs mt-0.5 text-primary/80">{item.why_it_matters}</p>
            </div>
          )}
          {item.early_warning_signal && item.early_warning_signal !== "None identified" && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Early warning</p>
              <p className="text-xs mt-0.5 text-amber-400/80">{item.early_warning_signal}</p>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            {(item.actors || []).slice(0, 5).map((a) => (
              <Badge key={a} variant="outline" className="rounded-none text-[8px] px-1 py-0">{a}</Badge>
            ))}
          </div>
          {item.source_url && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 font-mono"
            >
              <ExternalLink size={10} /> View source
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function CategoryGroup({ group, startIndex, onDelete }) {
  const CatIcon = CATEGORY_ICONS[group.category] || Globe;
  const color = CATEGORY_COLORS[group.category] || CATEGORY_COLORS.other;
  let idx = startIndex;

  return (
    <div className="mb-3" data-testid={`category-${group.category}`}>
      <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/5 border-b border-border">
        <CatIcon size={13} className={color.split(" ")[0]} />
        <span className="text-[10px] uppercase tracking-wider font-mono font-semibold">{group.label}</span>
        <Badge variant="outline" className={`rounded-none text-[8px] px-1 py-0 ${color}`}>
          {group.items.length}
        </Badge>
      </div>
      {group.items.map((item) => {
        idx++;
        return <SignalItem key={item.id} item={item} index={idx} onDelete={onDelete} />;
      })}
    </div>
  );
}

function CountrySection({ title, flag, data, isLoading, onDelete }) {
  const items = data?.items || [];
  const grouped = data?.grouped || [];
  const posture = data?.posture || "stable";
  const postureConf = POSTURE_CONFIG[posture] || POSTURE_CONFIG.stable;
  const PostureIcon = postureConf.icon;

  // Compute running index for numbered items
  let runningIndex = 0;

  return (
    <Card className="border border-border rounded-none bg-card" data-testid={`section-${title.toLowerCase()}`}>
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <span className="text-lg">{flag}</span>
          {title}
          <Badge variant="outline" className="rounded-none text-[10px] px-1.5 py-0 ml-1">
            {items.length}
          </Badge>
        </CardTitle>
        <Tip text={`Overall threat posture for this border — DETERIORATING: active escalation, ELEVATED: heightened alert, WATCHFUL: monitoring required, STABLE: no immediate concern.`} side="left">
          <Badge variant="outline" className={`rounded-none text-[10px] px-2.5 py-0.5 uppercase tracking-wider flex items-center gap-1.5 ${postureConf.color} cursor-help`}>
            <PostureIcon size={12} />
            {postureConf.label}
          </Badge>
        </Tip>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="animate-spin text-muted-foreground" size={20} />
          </div>
        ) : grouped.length > 0 ? (
          <div className="max-h-[700px] overflow-y-auto">
            {grouped.map((group) => {
              const startIdx = runningIndex;
              runningIndex += group.items.length;
              return <CategoryGroup key={group.category} group={group} startIndex={startIdx} onDelete={onDelete} />;
            })}
          </div>
        ) : items.length > 0 ? (
          <div className="max-h-[700px] overflow-y-auto">
            {items.map((item, i) => (
              <SignalItem key={item.id} item={item} index={i + 1} onDelete={onDelete} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground p-4">
            No intelligence signals detected for this country in the current retention window.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function CrossBorderWatch({ api }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [signalFilter, setSignalFilter] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (signalFilter) params.set("min_signal", signalFilter);
      params.set("limit", "50");
      const res = await axios.get(`${api}/cross-border/watch?${params.toString()}`);
      setData(res.data);
    } catch (e) {
      console.error("Cross-border fetch failed:", e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, [api, signalFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      // Trigger fetch + analysis of latest RSS feeds, then reload display
      await axios.post(`${api}/reclassify-48h`);
      // Give background task ~3s head start before re-fetching display data
      await new Promise((r) => setTimeout(r, 3000));
      await fetchData();
    } catch (e) {
      console.error("Cross-border refresh failed:", e);
      await fetchData();
    }
    setRefreshing(false);
  };

  const today = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }).toUpperCase();

  const handleDeleteItem = async (itemId) => {
    try {
      await axios.delete(`${api}/intelligence/${itemId}`);
      // Remove from local state
      setData((prev) => {
        if (!prev) return prev;
        const removeItem = (section) => {
          if (!section) return section;
          const filteredItems = (section.items || []).filter((i) => i.id !== itemId);
          const filteredGrouped = (section.grouped || []).map((g) => ({
            ...g,
            items: g.items.filter((i) => i.id !== itemId),
          })).filter((g) => g.items.length > 0);
          return { ...section, items: filteredItems, grouped: filteredGrouped };
        };
        return {
          ...prev,
          bangladesh: removeItem(prev.bangladesh),
          myanmar: removeItem(prev.myanmar),
        };
      });
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="space-y-5" data-testid="cross-border-watch">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold uppercase tracking-wider font-['Barlow_Condensed']" data-testid="cb-title" data-tour="cross-border-title">
            Cross-Border Watch
          </h1>
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider mt-0.5">
            Bangladesh & Myanmar — India-Facing Intelligence — {today}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-muted-foreground" />
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Signal:</span>
          {["", "MEDIUM", "HIGH"].map((val) => (
            <Button
              key={val}
              variant="outline"
              size="sm"
              className={`rounded-none text-[10px] h-6 px-2 uppercase ${
                signalFilter === val ? "bg-primary/10 text-primary border-primary/40" : ""
              }`}
              onClick={() => setSignalFilter(val)}
              data-testid={`signal-filter-${val || "all"}`}
            >
              {val || "All"}
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            className="rounded-none text-[10px] h-6 px-2 uppercase"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Fetch latest news and reload"
            data-testid="cb-refresh"
          >
            <RefreshCw size={11} className={refreshing ? "animate-spin mr-1" : "mr-1"} />
            {refreshing ? "Scanning…" : "Refresh"}
          </Button>
        </div>
      </div>

      {/* Watchpoints + Signal Distribution */}
      {data && (data.watchpoints?.length > 0 || Object.keys(data.signal_distribution || {}).length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.watchpoints?.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-2 px-4 border-b border-border">
                <Tip text="Active intelligence watchpoints — specific situations or actors requiring heightened monitoring. Updated by the AI based on cross-border signal patterns." side="top">
                <CardTitle className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                  <Eye size={14} className="text-amber-400" /> Watchpoints
                </CardTitle>
              </Tip>
              </CardHeader>
              <CardContent className="p-3">
                <ul className="space-y-1.5" data-testid="watchpoints-list">
                  {data.watchpoints.map((wp, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-amber-400 shrink-0 mt-0.5">-</span>
                      <span>{wp}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {Object.keys(data.signal_distribution || {}).length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-2 px-4 border-b border-border">
                <Tip text="Breakdown of cross-border intelligence signals by category — shows which types of events (diplomatic, defence, political, economic) are generating the most items." side="top">
                  <CardTitle className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 cursor-help w-fit">
                    <TrendingUp size={14} className="text-cyan-400" /> Signal Distribution
                  </CardTitle>
                </Tip>
              </CardHeader>
              <CardContent className="p-3">
                <div className="flex flex-wrap gap-1.5" data-testid="signal-distribution">
                  {Object.entries(data.signal_distribution).map(([bucket, count]) => (
                    <Badge key={bucket} variant="outline" className="rounded-none text-[9px] px-1.5 py-0 text-cyan-400 border-cyan-500/30">
                      {bucket.replace(/_/g, " ")} ({count})
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Two-column layout: Bangladesh | Myanmar */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <CountrySection
          title="Bangladesh"
          flag="&#x1F1E7;&#x1F1E9;"
          data={data?.bangladesh}
          isLoading={loading}
          onDelete={handleDeleteItem}
        />
        <CountrySection
          title="Myanmar"
          flag="&#x1F1F2;&#x1F1F2;"
          data={data?.myanmar}
          isLoading={loading}
          onDelete={handleDeleteItem}
        />
      </div>
    </div>
  );
}
