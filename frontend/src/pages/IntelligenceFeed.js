import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Search, Filter, X, ChevronLeft, ChevronRight, SlidersHorizontal, ArrowUpDown, Sparkles, Star
} from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "../components/ui/select";
import IntelligenceCard from "../components/IntelligenceCard";
import axios from "axios";

const STATES = [
  "Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura",
  "Bangladesh", "Myanmar"
];
const THREAT_TYPES = [
  "Insurgency", "Cross-border Movement", "Illegal Immigration",
  "Drug Trafficking", "Arms Smuggling", "Ethnic Conflicts",
  "Cyber Threats", "Strategic Infrastructure",
  "Political Developments", "Foreign Power Influence",
  "Military Operations", "Economic/Trade"
];
const SEVERITIES = ["critical", "high", "medium", "low"];

export default function IntelligenceFeed({ api, crossBorderOnly = false, alertsOnly = false }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState([]);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [feedbackMap, setFeedbackMap] = useState({});

  const [filters, setFilters] = useState({
    state: searchParams.get("state") || "",
    threat_type: searchParams.get("threat_type") || "",
    severity: alertsOnly ? "" : (searchParams.get("severity") || ""),
    search: searchParams.get("search") || "",
    min_priority: searchParams.get("min_priority") || "",
    sort_by: searchParams.get("sort_by") || "published_at",
    sort_order: "desc",
  });

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.state) params.set("state", filters.state);
      if (filters.threat_type) params.set("threat_type", filters.threat_type);
      if (filters.severity) params.set("severity", filters.severity);
      if (filters.search) params.set("search", filters.search);
      if (crossBorderOnly) params.set("is_cross_border", "true");
      if (filters.min_priority) params.set("min_priority", filters.min_priority);
      if (filters.sort_by) params.set("sort_by", filters.sort_by);
      if (filters.sort_order) params.set("sort_order", filters.sort_order);
      params.set("page", String(page));
      params.set("limit", "15");

      let url = `${api}/intelligence?${params.toString()}`;
      if (alertsOnly) {
        const res = await axios.get(`${api}/alerts`);
        let alertItems = res.data.alerts || [];
        if (filters.state) alertItems = alertItems.filter((i) => i.state === filters.state);
        if (filters.threat_type) alertItems = alertItems.filter((i) => i.threat_category === filters.threat_type);
        if (filters.search) {
          const q = filters.search.toLowerCase();
          alertItems = alertItems.filter((i) =>
            i.title?.toLowerCase().includes(q) || i.ai_summary?.toLowerCase().includes(q)
          );
        }
        setItems(alertItems);
        setTotal(alertItems.length);
        setPages(1);
      } else {
        const res = await axios.get(url);
        setItems(res.data.items || []);
        setTotal(res.data.total || 0);
        setPages(res.data.pages || 0);
      }
    } catch (e) {
      console.error("Failed to fetch:", e);
    }
    setLoading(false);
  }, [api, filters, page, crossBorderOnly, alertsOnly]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Batch-fetch feedback data for displayed items
  useEffect(() => {
    const fetchFeedback = async () => {
      const ids = items.map((i) => i.id).filter(Boolean);
      if (ids.length === 0) return;
      try {
        const deviceId = localStorage.getItem("rhino_drishti_device_id") || "";
        const res = await axios.post(`${api}/feedback/batch`, { item_ids: ids, device_id: deviceId });
        setFeedbackMap(res.data.feedback || {});
      } catch {
        // silent - feedback is non-critical
      }
    };
    fetchFeedback();
  }, [items, api]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({ state: "", threat_type: "", severity: "", search: "", min_priority: "", sort_by: "published_at", sort_order: "desc" });
    setPage(1);
    setSemanticMode(false);
    setSemanticResults([]);
    setSemanticQuery("");
  };

  const runSemanticSearch = async () => {
    if (!semanticQuery.trim()) return;
    setSemanticLoading(true);
    try {
      const res = await axios.post(`${api}/intelligence/semantic-search`, {
        query: semanticQuery,
        limit: 15,
        min_score: 0.25,
      });
      setSemanticResults(res.data.results || []);
    } catch (e) {
      console.error("Semantic search failed:", e);
    }
    setSemanticLoading(false);
  };

  const activeFilterCount = Object.entries(filters).filter(([k, v]) => v && k !== "sort_by" && k !== "sort_order").length;
  const pageTitle = alertsOnly === true ? "Critical & High Alerts" : crossBorderOnly === true ? "Cross-Border Developments" : "Intelligence Feed";
  const pageDesc = alertsOnly === true
    ? "High-priority intelligence items requiring attention"
    : crossBorderOnly === true
    ? "Bangladesh, Myanmar & regional border activity"
    : "All monitored intelligence across NER";

  return (
    <div className="space-y-4" data-testid="intelligence-feed-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="feed-title">
          {pageTitle}
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">{pageDesc}</p>
      </div>

      {/* Search + Filter toggle + Semantic Search */}
      <div className="flex items-center gap-3">
        {/* Rating guide */}
        <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 border border-primary/20 bg-primary/5 shrink-0" data-testid="rating-guide-banner">
          <Star size={12} className="text-amber-400" fill="currentColor" />
          <span className="text-[10px] font-mono text-muted-foreground">
            Rate each article 1 (Entirely Irrelevant) to 6 (Extremely Relevant) to train the system
          </span>
        </div>
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={semanticMode ? "Describe what you're looking for..." : "Search articles..."}
            value={semanticMode ? semanticQuery : filters.search}
            onChange={(e) => semanticMode ? setSemanticQuery(e.target.value) : updateFilter("search", e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && semanticMode) runSemanticSearch(); }}
            className="pl-9 rounded-none"
            data-testid="feed-search-input"
          />
        </div>
        <Button
          variant={semanticMode ? "default" : "outline"}
          size="sm"
          className={`rounded-none uppercase text-xs tracking-wider ${semanticMode ? "bg-primary" : ""}`}
          onClick={() => {
            setSemanticMode(!semanticMode);
            setSemanticResults([]);
            setSemanticQuery("");
          }}
          data-testid="semantic-search-toggle"
        >
          <Sparkles size={14} className="mr-1.5" />
          {semanticMode ? "Semantic ON" : "Semantic"}
        </Button>
        {semanticMode && (
          <Button
            size="sm"
            className="rounded-none uppercase text-xs"
            onClick={runSemanticSearch}
            disabled={semanticLoading || !semanticQuery.trim()}
            data-testid="semantic-search-btn"
          >
            {semanticLoading ? "Searching..." : "Find Similar"}
          </Button>
        )}
        <Button
          variant={showFilters ? "default" : "outline"}
          size="sm"
          className="rounded-none uppercase text-xs tracking-wider"
          onClick={() => setShowFilters(!showFilters)}
          data-testid="toggle-filters-btn"
        >
          <SlidersHorizontal size={14} className="mr-1.5" />
          Filters
          {activeFilterCount > 0 && (
            <Badge className="ml-1.5 severity-high rounded-none text-[10px] px-1">{activeFilterCount}</Badge>
          )}
        </Button>
        <span className="text-xs font-mono text-muted-foreground" data-testid="result-count">
          {semanticMode && semanticResults.length > 0 ? `${semanticResults.length} similar` : `${total} results`}
        </span>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="flex flex-wrap gap-3 p-3 border border-border bg-card animate-slide-in" data-testid="filter-panel">
          <Select value={filters.state || "all"} onValueChange={(v) => updateFilter("state", v === "all" ? "" : v)}>
            <SelectTrigger className="w-[180px] rounded-none text-xs uppercase" data-testid="filter-state">
              <SelectValue placeholder="All States" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All States</SelectItem>
              {STATES.map((s) => (
                <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.threat_type || "all"} onValueChange={(v) => updateFilter("threat_type", v === "all" ? "" : v)}>
            <SelectTrigger className="w-[200px] rounded-none text-xs uppercase" data-testid="filter-threat">
              <SelectValue placeholder="All Threats" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All Threats</SelectItem>
              {THREAT_TYPES.map((t) => (
                <SelectItem key={t} value={t} className="text-xs">{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {!alertsOnly && (
            <Select value={filters.severity || "all"} onValueChange={(v) => updateFilter("severity", v === "all" ? "" : v)}>
              <SelectTrigger className="w-[150px] rounded-none text-xs uppercase" data-testid="filter-severity">
                <SelectValue placeholder="All Severity" />
              </SelectTrigger>
              <SelectContent className="rounded-none">
                <SelectItem value="all" className="text-xs">All Severity</SelectItem>
                {SEVERITIES.map((s) => (
                  <SelectItem key={s} value={s} className="text-xs uppercase">{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Select value={filters.min_priority || "all"} onValueChange={(v) => updateFilter("min_priority", v === "all" ? "" : v)}>
            <SelectTrigger className="w-[170px] rounded-none text-xs uppercase" data-testid="filter-priority">
              <SelectValue placeholder="Min Priority" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All Priority</SelectItem>
              <SelectItem value="80" className="text-xs">80+ (Critical)</SelectItem>
              <SelectItem value="60" className="text-xs">60+ (High)</SelectItem>
              <SelectItem value="40" className="text-xs">40+ (Medium)</SelectItem>
              <SelectItem value="20" className="text-xs">20+ (Low+)</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filters.sort_by} onValueChange={(v) => updateFilter("sort_by", v)}>
            <SelectTrigger className="w-[170px] rounded-none text-xs uppercase" data-testid="sort-by">
              <ArrowUpDown size={12} className="mr-1" />
              <SelectValue placeholder="Sort By" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="published_at" className="text-xs">Date (Newest)</SelectItem>
              <SelectItem value="priority_score" className="text-xs">Priority Score</SelectItem>
            </SelectContent>
          </Select>

          {activeFilterCount > 0 && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="text-xs text-muted-foreground" data-testid="clear-filters-btn">
              <X size={14} className="mr-1" /> Clear
            </Button>
          )}
        </div>
      )}

      {/* Items grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="loading-skeleton">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="border border-border bg-card p-4 h-40 animate-pulse">
              <div className="h-4 bg-muted rounded w-3/4 mb-3" />
              <div className="h-3 bg-muted rounded w-1/2 mb-2" />
              <div className="h-3 bg-muted rounded w-full mb-2" />
              <div className="h-3 bg-muted rounded w-5/6" />
            </div>
          ))}
        </div>
      ) : semanticMode && semanticResults.length > 0 ? (
        <>
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={14} className="text-primary" />
            <span className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              Contextually Related Results
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="semantic-results-grid">
            {semanticResults.map((item, i) => (
              <div key={item.id || i} className="relative">
                <Badge className="absolute top-2 right-2 z-10 rounded-none bg-primary/20 text-primary border-primary/30 text-[9px] px-1">
                  {(item.similarity_score * 100).toFixed(0)}% match
                </Badge>
                <IntelligenceCard item={item} api={api} />
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="intelligence-items-grid">
            {items.map((item) => (
              <IntelligenceCard key={item.id} item={item} api={api} feedbackData={feedbackMap[item.id]} />
            ))}
          </div>

          {items.length === 0 && (
            <div className="text-center py-16 border border-border bg-card">
              <p className="text-muted-foreground text-sm">No intelligence items found matching your criteria.</p>
            </div>
          )}

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-6" data-testid="pagination">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-none"
                data-testid="prev-page-btn"
              >
                <ChevronLeft size={14} /> Prev
              </Button>
              <span className="text-xs font-mono text-muted-foreground">
                Page {page} of {pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-none"
                data-testid="next-page-btn"
              >
                Next <ChevronRight size={14} />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
