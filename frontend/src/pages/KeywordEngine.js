import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Key, RefreshCw, Filter, ArrowUpDown, Search, Plus, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";

const TYPE_STYLES = {
  primary: { bg: "bg-red-900/30 text-red-300 border-red-800/40", label: "Primary Threat" },
  entity: { bg: "bg-blue-900/30 text-blue-300 border-blue-800/40", label: "Entity/Actor" },
  geo: { bg: "bg-yellow-900/30 text-yellow-300 border-yellow-800/40", label: "Geographic" },
  cross_border: { bg: "bg-purple-900/30 text-purple-300 border-purple-800/40", label: "Cross-Border" },
  emerging: { bg: "bg-green-900/30 text-green-300 border-green-800/40", label: "AI Emerging Signal" },
  expanded: { bg: "bg-slate-800/30 text-slate-300 border-slate-700/40", label: "AI Expanded" },
};

const SOURCE_LABELS = {
  seed: "Baseline",
  historical: "Historical Data",
  ai: "AI Generated",
  ai_expansion: "AI Expansion",
  adaptive: "Adaptive Learning",
  stored: "Stored",
  manual: "Manually Added",
};

export default function KeywordEngine({ api }) {
  const [keywords, setKeywords] = useState([]);
  const [typeBreakdown, setTypeBreakdown] = useState({});
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("score");
  const [addType, setAddType] = useState("primary");
  const [addScore, setAddScore] = useState("60");
  const [adding, setAdding] = useState(false);

  const fetchKeywords = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/keywords?limit=300`);
      setKeywords(res.data.keywords || []);
      setTypeBreakdown(res.data.type_breakdown || {});
    } catch (e) { console.error(e); }
  }, [api]);

  useEffect(() => { fetchKeywords(); }, [fetchKeywords]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await axios.post(`${api}/keywords/refresh`);
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await fetchKeywords();
        if (attempts >= 10) { clearInterval(poll); setRefreshing(false); }
      }, 3000);
    } catch { setRefreshing(false); }
  };

  const handleAddKeyword = async () => {
    const trimmed = search.trim();
    if (!trimmed || trimmed.length < 2) return;
    setAdding(true);
    try {
      const res = await axios.post(`${api}/keywords/add`, {
        keyword: trimmed,
        type: addType,
        score: parseInt(addScore, 10),
      });
      toast.success(res.data.message || `Keyword "${trimmed}" added`);
      setSearch("");
      await fetchKeywords();
    } catch (e) {
      const msg = e.response?.data?.detail || "Failed to add keyword";
      toast.error(msg);
    }
    setAdding(false);
  };

  const filtered = keywords
    .filter(k => typeFilter === "all" || k.type === typeFilter)
    .filter(k => !search || k.keyword.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === "score") return b.score - a.score;
      if (sortBy === "alpha") return a.keyword.localeCompare(b.keyword);
      if (sortBy === "type") return a.type.localeCompare(b.type);
      return 0;
    });

  const scoreDistribution = {
    high: keywords.filter(k => k.score >= 70).length,
    medium: keywords.filter(k => k.score >= 40 && k.score < 70).length,
    low: keywords.filter(k => k.score < 40).length,
  };

  return (
    <div className="space-y-5 p-4 md:p-6" data-testid="keyword-engine-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="font-mono text-2xl font-bold tracking-tight flex items-center gap-2">
            <Key size={24} className="text-primary" /> Dynamic Keyword Engine
          </h1>
          <p className="text-xs text-muted-foreground font-mono mt-1">
            AI-powered intelligence keyword generation driving RSS detection
          </p>
        </div>
        <Button
          data-testid="ai-refresh-btn"
          onClick={handleRefresh}
          disabled={refreshing}
          variant="outline"
          className="font-mono text-xs rounded-none"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin mr-1" : "mr-1"} />
          {refreshing ? "AI Generating..." : "AI Refresh Keywords"}
        </Button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="keyword-stats">
        <div className="bg-card/60 border border-border/50 p-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-mono">Total Keywords</div>
          <div className="text-2xl font-mono font-bold mt-1">{keywords.length}</div>
        </div>
        <div className="bg-card/60 border border-border/50 p-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-mono">High Score (70+)</div>
          <div className="text-2xl font-mono font-bold mt-1 text-red-400">{scoreDistribution.high}</div>
        </div>
        <div className="bg-card/60 border border-border/50 p-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-mono">Medium (40-69)</div>
          <div className="text-2xl font-mono font-bold mt-1 text-yellow-400">{scoreDistribution.medium}</div>
        </div>
        <div className="bg-card/60 border border-border/50 p-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-mono">Low (&lt;40)</div>
          <div className="text-2xl font-mono font-bold mt-1 text-green-400">{scoreDistribution.low}</div>
        </div>
      </div>

      {/* Type breakdown */}
      <div className="flex flex-wrap gap-2" data-testid="type-breakdown">
        {Object.entries(typeBreakdown).map(([type, count]) => (
          <button
            key={type}
            onClick={() => setTypeFilter(typeFilter === type ? "all" : type)}
            className={`text-[10px] px-2.5 py-1 border font-mono transition-all ${
              typeFilter === type ? "ring-1 ring-primary" : ""
            } ${(TYPE_STYLES[type] || {}).bg || "bg-muted"}`}
            data-testid={`type-filter-${type}`}
          >
            {(TYPE_STYLES[type] || {}).label || type}: {count}
          </button>
        ))}
        {typeFilter !== "all" && (
          <button onClick={() => setTypeFilter("all")} className="text-[10px] text-primary font-mono hover:underline">
            Clear filter
          </button>
        )}
      </div>

      {/* Search + Sort */}
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="keyword-search"
            placeholder="Search keywords..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-8 h-8 text-xs font-mono rounded-none"
          />
        </div>
        <div className="flex gap-1">
          {[
            { key: "score", label: "Score" },
            { key: "alpha", label: "A-Z" },
            { key: "type", label: "Type" },
          ].map(s => (
            <button
              key={s.key}
              onClick={() => setSortBy(s.key)}
              className={`text-[10px] px-2 py-1 font-mono border ${
                sortBy === s.key ? "bg-primary text-primary-foreground" : "bg-muted/30 text-muted-foreground"
              }`}
            >
              <ArrowUpDown size={9} className="inline mr-0.5" /> {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Keyword grid */}
      <div className="bg-card/60 border border-border/50 p-4" data-testid="keyword-grid">
        <div className="text-[10px] text-muted-foreground font-mono mb-3 uppercase tracking-wider">
          Showing {filtered.length} of {keywords.length} keywords
          {typeFilter !== "all" && ` (filtered: ${typeFilter})`}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {filtered.map((kw, i) => {
            const scoreColor = kw.score >= 70 ? "text-red-400" : kw.score >= 40 ? "text-yellow-400" : "text-green-400";
            return (
              <span
                key={i}
                className={`text-[11px] px-2 py-0.5 border font-mono inline-flex items-center gap-1.5 cursor-default hover:brightness-125 transition-all ${
                  (TYPE_STYLES[kw.type] || {}).bg || "bg-muted"
                }`}
                title={`Type: ${(TYPE_STYLES[kw.type] || {}).label || kw.type}\nScore: ${kw.score}/100\nSource: ${SOURCE_LABELS[kw.source] || kw.source || "generated"}`}
                data-testid={`keyword-${i}`}
              >
                {kw.keyword}
                <span className={`text-[9px] font-bold ${scoreColor}`}>{kw.score}</span>
              </span>
            );
          })}
        </div>
        {filtered.length === 0 && search.trim().length >= 2 && (
          <div className="border border-dashed border-primary/30 bg-primary/5 p-4 mt-2" data-testid="add-keyword-prompt">
            <p className="text-xs text-muted-foreground font-mono mb-3">
              No keyword found for "<span className="text-primary font-semibold">{search.trim()}</span>". Add it manually?
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Type</p>
                <Select value={addType} onValueChange={setAddType}>
                  <SelectTrigger className="w-[160px] h-8 rounded-none text-xs font-mono" data-testid="add-keyword-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="rounded-none">
                    <SelectItem value="primary" className="text-xs">Primary Threat</SelectItem>
                    <SelectItem value="entity" className="text-xs">Entity/Actor</SelectItem>
                    <SelectItem value="geo" className="text-xs">Geographic</SelectItem>
                    <SelectItem value="cross_border" className="text-xs">Cross-Border</SelectItem>
                    <SelectItem value="emerging" className="text-xs">Emerging Signal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Score</p>
                <Select value={addScore} onValueChange={setAddScore}>
                  <SelectTrigger className="w-[110px] h-8 rounded-none text-xs font-mono" data-testid="add-keyword-score">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="rounded-none">
                    <SelectItem value="90" className="text-xs">90 (Critical)</SelectItem>
                    <SelectItem value="75" className="text-xs">75 (High)</SelectItem>
                    <SelectItem value="60" className="text-xs">60 (Medium)</SelectItem>
                    <SelectItem value="40" className="text-xs">40 (Low)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={handleAddKeyword}
                disabled={adding}
                className="h-8 rounded-none text-xs font-mono uppercase tracking-wider"
                data-testid="add-keyword-btn"
              >
                {adding ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Plus size={12} className="mr-1" />}
                Add Keyword
              </Button>
            </div>
          </div>
        )}
        {filtered.length === 0 && search.trim().length < 2 && (
          <p className="text-xs text-muted-foreground font-mono text-center py-6">No keywords match your filters.</p>
        )}
      </div>

      {/* Legend */}
      <div className="bg-card/40 border border-border/30 p-3">
        <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider mb-2">Legend</div>
        <div className="flex flex-wrap gap-3">
          {Object.entries(TYPE_STYLES).map(([type, style]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span className={`w-3 h-3 border ${style.bg}`} />
              <span className="text-[10px] text-muted-foreground font-mono">{style.label}</span>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 mt-2">
          <span className="text-[10px] font-mono"><span className="text-red-400 font-bold">70+</span> = High priority</span>
          <span className="text-[10px] font-mono"><span className="text-yellow-400 font-bold">40-69</span> = Medium</span>
          <span className="text-[10px] font-mono"><span className="text-green-400 font-bold">&lt;40</span> = Low</span>
        </div>
      </div>
    </div>
  );
}
