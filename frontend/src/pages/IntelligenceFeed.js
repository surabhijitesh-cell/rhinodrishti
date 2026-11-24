import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Search, Filter, X, ChevronLeft, ChevronRight, SlidersHorizontal, ArrowUpDown, Sparkles, Star,
  FileDown, Loader2
} from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import Tip from "../components/Tip";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "../components/ui/select";
import IntelligenceCard from "../components/IntelligenceCard";
import axios from "axios";
import LoadError from "../components/LoadError";
import ConfirmAction from "../components/ConfirmAction";
import { useAuth } from "../contexts/AuthContext";
import { useAdminIod } from "../contexts/AdminIodContext";
import { formatIST } from "../lib/time";
import { toast } from "sonner";

const SEARCH_DELAY_MS = 400;        // wait this long after typing stops before searching
const FRESHNESS_CHECK_MS = 60000;   // look for newer items this often while the page is visible
const FRESHNESS_BUFFER_MS = 15 * 60000; // items are collected a little before they are classified

/** Only the ids the page is not already showing count as new. */
export function countNewItems(candidateIds, shownIds) {
  const shown = new Set(shownIds);
  return (candidateIds || []).filter((id) => !shown.has(id)).length;
}

/** The time (ISO) to ask the server "what is newer than this?" about. */
export function freshSince(loadedAtMs) {
  return new Date(loadedAtMs - FRESHNESS_BUFFER_MS).toISOString();
}

export function newItemsLabel(n) {
  return n === 1 ? "1 new item" : `${n} new items`;
}

const STATES = [
  "Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura",
  "Nagaland", "Sikkim", "West Bengal",
  "Bangladesh", "Myanmar"
];
const THREAT_TYPES = [
  "Army Image",
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
  const [loadFailed, setLoadFailed] = useState(false);
  const [openAlertCount, setOpenAlertCount] = useState(0);
  const [acking, setAcking] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState([]);
  // idle -> searching -> results | empty | failed. Anything but "results" shows no old items.
  const [semanticStatus, setSemanticStatus] = useState("idle");
  const semanticLoading = semanticStatus === "searching";
  const [newCount, setNewCount] = useState(0);
  const [lastLoadedAt, setLastLoadedAt] = useState(null);
  const fetchSeq = useRef(0);       // a slower, older answer must not replace a newer one
  const semanticSeq = useRef(0);
  const loadedAtMs = useRef(Date.now());
  const itemsRef = useRef([]);
  const { user } = useAuth();
  const { viewIod } = useAdminIod();
  const isAdmin = user?.role === "admin";
  const adminViewIod = isAdmin && viewIod ? viewIod : "";
  const viewedIod = adminViewIod || user?.iod || "IOD-1";
  const [feedbackMap, setFeedbackMap] = useState({});
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const [pdfClickCount, setPdfClickCount] = useState(() => {
    try { return parseInt(localStorage.getItem("new_badge_export_pdf") || "0", 10); } catch { return 0; }
  });
  const showPdfBadge = pdfClickCount < 3;

  const [filters, setFilters] = useState({
    state: searchParams.get("state") || "",
    threat_type: searchParams.get("threat_type") || "",
    severity: alertsOnly ? "" : (searchParams.get("severity") || ""),
    search: searchParams.get("search") || "",
    min_priority: searchParams.get("min_priority") || "",
    sort_by: searchParams.get("sort_by") || "published_at",
    sort_order: "desc",
  });
  // What is typed in the box; it becomes filters.search once typing pauses.
  const [searchText, setSearchText] = useState(filters.search);

  // The filters the server understands, shared by the list, the new-items check and the PDF.
  const filterParams = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.state) params.set("state", filters.state);
    if (filters.threat_type) params.set("threat_type", filters.threat_type);
    if (filters.severity && !alertsOnly) params.set("severity", filters.severity);
    if (filters.search) params.set("search", filters.search);
    if (filters.min_priority) params.set("min_priority", filters.min_priority);
    return params;
  }, [filters, alertsOnly]);

  const fetchItems = useCallback(async () => {
    const seq = ++fetchSeq.current;
    setLoading(true);
    try {
      const params = filterParams();
      if (filters.sort_by) params.set("sort_by", filters.sort_by);
      if (filters.sort_order) params.set("sort_order", filters.sort_order);
      if (adminViewIod) params.set("iod", adminViewIod);
      let data;
      if (alertsOnly) {
        data = (await axios.get(`${api}/alerts?${params.toString()}`)).data;
      } else {
        if (crossBorderOnly) params.set("is_cross_border", "true");
        params.set("page", String(page));
        params.set("limit", "15");
        data = (await axios.get(`${api}/intelligence?${params.toString()}`)).data;
      }
      if (seq !== fetchSeq.current) return;
      if (alertsOnly) {
        const alertItems = data.alerts || [];
        setItems(alertItems);
        setTotal(data.matched ?? alertItems.length);
        setOpenAlertCount(data.count ?? alertItems.length);
        setPages(1);
      } else {
        setItems(data.items || []);
        setTotal(data.total || 0);
        setPages(data.pages || 0);
      }
      loadedAtMs.current = Date.now();
      setLastLoadedAt(new Date().toISOString());
      setNewCount(0);
      setLoadFailed(false);
    } catch (e) {
      if (seq !== fetchSeq.current) return;
      setLoadFailed(true);
    }
    setLoading(false);
  }, [api, filters.sort_by, filters.sort_order, filterParams, page, crossBorderOnly, alertsOnly, adminViewIod]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  useEffect(() => { itemsRef.current = items; }, [items]);

  // Typing waits for a short pause, then searches once.
  useEffect(() => {
    if (searchText === filters.search) return undefined;
    const timer = setTimeout(() => {
      setFilters((prev) => ({ ...prev, search: searchText }));
      setPage(1);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [searchText, filters.search]);

  // Every minute (while this tab is visible) ask whether anything newer has arrived.
  const checkForNewItems = useCallback(async () => {
    if (document.visibilityState !== "visible" || semanticMode) return;
    try {
      const params = filterParams();
      params.set("since", freshSince(loadedAtMs.current));
      if (alertsOnly) params.set("alerts_only", "true");
      else if (crossBorderOnly) params.set("is_cross_border", "true");
      const res = await axios.get(`${api}/intelligence/new-since?${params.toString()}`);
      setNewCount(countNewItems(res.data.ids, itemsRef.current.map((i) => i.id)));
    } catch {
      // quiet: the next check tries again
    }
  }, [api, filterParams, alertsOnly, crossBorderOnly, semanticMode]);

  useEffect(() => {
    const timer = setInterval(checkForNewItems, FRESHNESS_CHECK_MS);
    document.addEventListener("visibilitychange", checkForNewItems);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", checkForNewItems);
    };
  }, [checkForNewItems]);

  // Loads the new items with the same filters; the list never jumps by itself.
  const showNewItems = () => {
    if (page !== 1) setPage(1);
    else fetchItems();
  };

  // Alerts page: acknowledge one alert, or every alert currently shown.
  const acknowledgeAlerts = async (ids) => {
    if (!ids.length) return;
    setAcking(true);
    try {
      if (ids.length === 1) await axios.post(`${api}/intelligence/${ids[0]}/acknowledge`);
      else await axios.post(`${api}/alerts/acknowledge-all`, { ids });
      setItems((prev) => prev.filter((i) => !ids.includes(i.id)));
      setOpenAlertCount((c) => Math.max(0, c - ids.length));
      toast.success(ids.length === 1 ? "Alert acknowledged" : `${ids.length} alerts acknowledged`);
      if (ids.length > 1) fetchItems();
    } catch (e) {
      toast.error("Could not acknowledge — please try again");
    }
    setAcking(false);
  };

  // Scroll to top when page changes
  useEffect(() => {
    const main = document.querySelector('[data-testid="main-content"]');
    if (main) main.scrollTo({ top: 0, behavior: "smooth" });
  }, [page]);

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

  const handleEnhanced = (itemId, enhancement) => {
    setItems((prev) => prev.map((item) =>
      item.id === itemId
        ? { ...item, analyst_enhancement: enhancement || undefined }
        : item
    ));
  };

  const handleDeleteItem = async (itemId) => {
    // A failure is thrown back to the card, which tells the person and restores its button.
    await axios.delete(`${api}/intelligence/${itemId}`);
    setItems((prev) => prev.filter((i) => i.id !== itemId));
    setSemanticResults((prev) => prev.filter((i) => i.id !== itemId));
    setTotal((prev) => Math.max(0, prev - 1));
  };

  const handleGeneratePdf = async () => {
    setGeneratingPdf(true);
    try {
      // Same filters as the list on screen; on the Alerts page the server exports the alert list itself.
      const params = filterParams();
      if (filters.sort_by) params.set("sort_by", filters.sort_by);
      if (filters.sort_order) params.set("sort_order", filters.sort_order);
      if (alertsOnly) {
        params.set("alerts_only", "true");
        if (adminViewIod) params.set("iod", adminViewIod);
      } else if (crossBorderOnly) {
        params.set("is_cross_border", "true");
      }
      const res = await axios.get(`${api}/reports/filtered-feed?${params.toString()}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `Rhino_Drishti_Filtered_Brief.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("PDF generated and downloaded");
    } catch (e) {
      const msg = e.response?.status === 404 ? "No items match the current filters" : "PDF generation failed";
      toast.error(msg);
    }
    setGeneratingPdf(false);
  };

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const resetSemantic = () => {
    semanticSeq.current += 1;   // forget any search still on its way
    setSemanticResults([]);
    setSemanticStatus("idle");
  };

  const clearFilters = () => {
    setFilters({ state: "", threat_type: "", severity: "", search: "", min_priority: "", sort_by: "published_at", sort_order: "desc" });
    setSearchText("");
    setPage(1);
    setSemanticMode(false);
    setSemanticQuery("");
    resetSemantic();
  };

  const runSemanticSearch = async () => {
    if (!semanticQuery.trim()) return;
    const seq = ++semanticSeq.current;
    setSemanticResults([]);
    setSemanticStatus("searching");
    try {
      const res = await axios.post(`${api}/intelligence/semantic-search`, {
        query: semanticQuery,
        limit: 15,
        min_score: 0.25,
      });
      if (seq !== semanticSeq.current) return;
      const found = res.data.results || [];
      setSemanticResults(found);
      setSemanticStatus(found.length ? "results" : "empty");
    } catch (e) {
      if (seq !== semanticSeq.current) return;
      setSemanticStatus("failed");
    }
  };

  const activeFilterCount = Object.entries(filters).filter(([k, v]) => v && k !== "sort_by" && k !== "sort_order").length;
  const pageTitle = alertsOnly === true ? "Critical & High Alerts" : crossBorderOnly === true ? "Cross-Border Developments" : "Intelligence Feed";
  const pageDesc = alertsOnly === true
    ? "High-priority intelligence items requiring attention"
    : crossBorderOnly === true
    ? "Bangladesh, Myanmar & regional border activity"
    : "All monitored intelligence across NER";
  // Ranking favours the viewed IOD's faultlines; the list itself still covers every IOD.
  const iodNote = !crossBorderOnly && viewedIod !== "IOD-1"
    ? `Items for ${viewedIod}${adminViewIod ? " (admin view)" : ""} are ranked first; the list still includes all IODs.`
    : "";
  const semanticFailedMsg = "Search failed. The AI search could not run, so no results are shown. Please try again.";

  return (
    <div className="space-y-4" data-testid="intelligence-feed-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="feed-title" data-tour="feed-title">
          {pageTitle}
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">{pageDesc}</p>
        {iodNote && <p className="text-[11px] text-muted-foreground mt-1" data-testid="iod-note">{iodNote}</p>}
      </div>

      {alertsOnly && (
        <div className="flex items-center justify-between gap-3 border border-red-500/30 bg-red-950/20 px-3 py-2" data-testid="alerts-ack-bar">
          <span className="text-xs font-mono uppercase tracking-wider text-red-400">
            {openAlertCount} alert{openAlertCount === 1 ? "" : "s"} need attention
            {items.length < openAlertCount ? ` — showing ${items.length}` : ""}
          </span>
          <ConfirmAction
            title={`Acknowledge all ${items.length} alerts shown?`}
            description="They will leave the Alerts list and the sidebar count."
            confirmLabel="Acknowledge all"
            onConfirm={() => acknowledgeAlerts(items.map((i) => i.id))}
          >
            <Button
              variant="outline" size="sm"
              className="rounded-none text-xs uppercase border-green-500/30 text-green-400 hover:bg-green-500/10"
              disabled={acking || items.length === 0}
              data-testid="ack-all-btn"
            >
              ACK all shown ({items.length})
            </Button>
          </ConfirmAction>
        </div>
      )}

      {/* Row 1 — Search + mode toggle */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <Input
            placeholder={semanticMode ? "Describe what you're looking for… (press Enter to search)" : "Search articles by keyword…"}
            value={semanticMode ? semanticQuery : searchText}
            onChange={(e) => {
              if (!semanticMode) { setSearchText(e.target.value); return; }
              setSemanticQuery(e.target.value);
              resetSemantic();   // an edited query never shows the old answer
            }}
            onKeyDown={(e) => { if (e.key === "Enter" && semanticMode) runSemanticSearch(); }}
            className="pl-9 rounded-none h-9 text-sm"
            data-testid="feed-search-input"
          />
        </div>
        <Tip text="Toggle AI semantic search — finds contextually related items even without exact keyword matches. E.g. 'border infiltration' also finds 'unauthorized entry' and 'cross-border movement'." side="bottom">
          <Button
            variant={semanticMode ? "default" : "outline"}
            size="sm"
            className={`rounded-none uppercase text-xs tracking-wider shrink-0 ${semanticMode ? "bg-primary" : ""}`}
            onClick={() => {
              setSemanticMode(!semanticMode);
              setSemanticQuery("");
              resetSemantic();
            }}
            data-testid="semantic-search-toggle"
          >
            <Sparkles size={13} className="mr-1" />
            {semanticMode ? "AI: ON" : "AI Search"}
          </Button>
        </Tip>
        {semanticMode && (
          <Button
            size="sm"
            className="rounded-none uppercase text-xs shrink-0"
            onClick={runSemanticSearch}
            disabled={semanticLoading || !semanticQuery.trim()}
            data-testid="semantic-search-btn"
          >
            {semanticLoading ? <><Loader2 size={13} className="mr-1 animate-spin" />Searching…</> : "Find Similar"}
          </Button>
        )}
      </div>

      {/* Row 2 — Filters + actions + result count */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Rating guide — compact chip */}
        <div className="flex items-center gap-1 px-2 py-1 border border-primary/20 bg-primary/5 shrink-0" data-testid="rating-guide-banner">
          <Star size={11} className="text-amber-400 shrink-0" fill="currentColor" />
          <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">
            Rate 1–6 to train the system
          </span>
        </div>

        <Tip text="Toggle filter panel — narrow results by State, Threat Type, Severity and Minimum Priority. Active filters are shown as a count badge." side="bottom">
          <Button
            variant={showFilters ? "default" : "outline"}
            size="sm"
            className="rounded-none uppercase text-xs tracking-wider shrink-0"
            onClick={() => setShowFilters(!showFilters)}
            data-testid="toggle-filters-btn"
          >
            <SlidersHorizontal size={13} className="mr-1" />
            Filters
            {activeFilterCount > 0 && (
              <Badge className="ml-1 severity-high rounded-none text-[10px] px-1">{activeFilterCount}</Badge>
            )}
          </Button>
        </Tip>

        <Tip text="Export the current filtered view as a formatted PDF brief — includes severity breakdown and all matching items in priority order." side="bottom">
          <Button
            variant="outline"
            size="sm"
            className="rounded-none uppercase text-xs tracking-wider border-primary/30 text-primary hover:bg-primary/10 relative shrink-0"
            onClick={() => {
              const next = pdfClickCount + 1;
              setPdfClickCount(next);
              localStorage.setItem("new_badge_export_pdf", String(next));
              handleGeneratePdf();
            }}
            disabled={generatingPdf}
            data-testid="generate-pdf-btn"
          >
            {generatingPdf ? <Loader2 size={13} className="mr-1 animate-spin" /> : <FileDown size={13} className="mr-1" />}
            {generatingPdf ? "Generating…" : "Export PDF"}
            {showPdfBadge && (
              <span className="absolute -top-2 -right-2 text-[8px] font-bold uppercase tracking-wider text-emerald-400 animate-pulse bg-card px-1 border border-emerald-500/30" data-testid="new-badge-export-pdf">
                New
              </span>
            )}
          </Button>
        </Tip>

        <span className="text-xs font-mono text-muted-foreground ml-auto text-right" data-testid="result-count">
          {semanticMode
            ? (semanticStatus === "results" ? `${semanticResults.length} similar`
              : semanticStatus === "empty" ? "0 similar" : "—")
            : loadFailed ? "—" : `${total} results`}
          {!semanticMode && lastLoadedAt && !loadFailed && (
            <span className="block text-[10px] opacity-70">Updated {formatIST(lastLoadedAt)}</span>
          )}
        </span>
      </div>

      {semanticMode && (
        <p className="text-[11px] text-muted-foreground" data-testid="semantic-scope-note">
          AI search looks across all IODs; it is not limited to the IOD being viewed.
        </p>
      )}

      {!semanticMode && newCount > 0 && (
        <button
          onClick={showNewItems}
          className="w-full border border-primary/40 bg-primary/10 text-primary text-xs font-mono uppercase tracking-wider py-2 hover:bg-primary/20"
          data-testid="new-items-btn"
        >
          {newItemsLabel(newCount)} - click to load
        </button>
      )}

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
              <SelectItem value="severity" className="text-xs">Severity (Critical first)</SelectItem>
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
      {(semanticMode ? semanticStatus === "searching" : loading) ? (
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
      ) : semanticMode && semanticStatus === "failed" ? (
        <div className="text-center py-12 border border-amber-500/40 bg-amber-500/5" role="alert" data-testid="semantic-failed">
          <p className="text-amber-400 text-sm font-semibold">Search failed</p>
          <p className="text-muted-foreground text-xs mt-1">{semanticFailedMsg}</p>
          <Button size="sm" variant="outline" className="rounded-none mt-3 text-xs uppercase" onClick={runSemanticSearch}>
            Try again
          </Button>
        </div>
      ) : semanticMode && semanticStatus === "empty" ? (
        <div className="text-center py-12 border border-border bg-card" data-testid="semantic-empty">
          <p className="text-muted-foreground text-sm">No matching items</p>
        </div>
      ) : semanticMode && semanticStatus === "idle" ? (
        <div className="text-center py-12 border border-border bg-card" data-testid="semantic-idle">
          <p className="text-muted-foreground text-sm">Describe what you are looking for, then press Enter.</p>
        </div>
      ) : semanticMode ? (
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
                <IntelligenceCard item={item} api={api} onDelete={handleDeleteItem} />
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="intelligence-items-grid">
            {items.map((item) => alertsOnly ? (
              <div key={item.id} className="flex flex-col" data-testid={`alert-row-${item.id}`}>
                <IntelligenceCard item={item} api={api} feedbackData={feedbackMap[item.id]} onDelete={handleDeleteItem} onEnhanced={handleEnhanced} />
                <Button
                  variant="outline" size="sm"
                  className="rounded-none border-t-0 text-xs uppercase border-green-500/30 text-green-400 hover:bg-green-500/10"
                  disabled={acking}
                  onClick={() => acknowledgeAlerts([item.id])}
                  data-testid={`alert-ack-btn-${item.id}`}
                >
                  ACK — handled
                </Button>
              </div>
            ) : (
              <IntelligenceCard key={item.id} item={item} api={api} feedbackData={feedbackMap[item.id]} onDelete={handleDeleteItem} onEnhanced={handleEnhanced} />
            ))}
          </div>

          {loadFailed && (
            <LoadError what={alertsOnly ? "the alerts" : "the intelligence items"} onRetry={fetchItems} />
          )}
          {!loadFailed && items.length === 0 && (
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
