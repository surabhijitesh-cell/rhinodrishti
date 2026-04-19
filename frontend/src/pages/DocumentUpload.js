import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Upload, Link2, FileText, Trash2, RefreshCw, CheckCircle, AlertTriangle,
  Clock, Shield, Target, MapPin, Users, TrendingUp, ChevronDown, ChevronUp,
  Search, Plus, Rss, Loader2
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";

const SEV_STYLES = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-green-500/20 text-green-400 border-green-500/30",
};

const THREAT_CATEGORIES = [
  "Military Movement", "Insurgency/Militancy", "Drug Trafficking", "Arms Smuggling",
  "Border Incursion", "Ethnic/Tribal Tension", "Political Instability", "Cyber Threat",
  "Infrastructure/Strategic", "Cross-border Crime", "Ceasefire Violation",
  "Counter-terrorism Ops", "Diplomatic Tension", "Immigration/Refugees",
  "Environmental Security", "Economic Security", "Intelligence Activity", "Unclassified",
];

const NER_STATES = [
  "Assam", "Manipur", "Meghalaya", "Mizoram", "Tripura", "Nagaland",
  "Arunachal Pradesh", "Sikkim", "Bangladesh", "Myanmar", "India", "Multiple", "Unknown",
];

function AnalysisCard({ doc, onDelete, onAddToFeed, api }) {
  const [expanded, setExpanded] = useState(false);
  const [selectedKw, setSelectedKw] = useState(new Set());
  const [addingKw, setAddingKw] = useState(false);
  const a = doc.analysis || {};
  const tc = a.threat_classification || {};
  const pa = a.pattern_analysis || {};
  const ra = a.relevance_assessment || {};
  const ke = a.key_entities || {};
  const actions = a.recommended_actions || [];

  return (
    <Card className="border border-border rounded-none bg-card" data-testid={`analysis-card-${doc.id}`}>
      <CardHeader className="py-3 px-4 border-b border-border cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className={`w-2 h-8 shrink-0 ${
              tc.severity === "CRITICAL" ? "bg-red-500" :
              tc.severity === "HIGH" ? "bg-orange-500" :
              tc.severity === "MEDIUM" ? "bg-yellow-500" : "bg-green-500"
            }`} />
            <div className="min-w-0 flex-1">
              <CardTitle className="text-sm font-semibold truncate">{doc.filename}</CardTitle>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {doc.processed && tc.severity && (
                  <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${SEV_STYLES[tc.severity] || SEV_STYLES.MEDIUM}`}>
                    {tc.severity}
                  </Badge>
                )}
                {tc.threat_category && (
                  <Badge className="rounded-none text-[9px] px-1.5 py-0 border bg-primary/10 text-primary border-primary/30">
                    {tc.threat_category}
                  </Badge>
                )}
                {ra.primary_region && (
                  <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-1">
                    <MapPin size={10} />{ra.primary_region}
                  </span>
                )}
                {pa.escalation_indicator && (
                  <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${
                    pa.escalation_indicator === "ESCALATING" ? "bg-red-500/15 text-red-400 border-red-500/25" :
                    pa.escalation_indicator === "NEW_THREAT" ? "bg-purple-500/15 text-purple-400 border-purple-500/25" :
                    pa.escalation_indicator === "DE-ESCALATING" ? "bg-green-500/15 text-green-400 border-green-500/25" :
                    "bg-muted text-muted-foreground border-border"
                  }`}>
                    {pa.escalation_indicator}
                  </Badge>
                )}
                <span className="text-[10px] text-muted-foreground font-mono">
                  {doc.source_type === "url" ? "URL" : doc.file_type?.toUpperCase()} | {new Date(doc.uploaded_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {!doc.processed && (
              <div className="flex items-center gap-1 text-amber-400 mr-2">
                <RefreshCw size={14} className="animate-spin" />
                <span className="text-[10px] font-mono">Analyzing...</span>
              </div>
            )}
            {doc.processed && doc.source_type === "url" && !a?.error && (
              <Button
                variant="outline" size="sm"
                className="h-7 text-[10px] rounded-none border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 mr-1"
                onClick={(e) => { e.stopPropagation(); onAddToFeed(doc); }}
                data-testid={`add-to-feed-${doc.id}`}
                title="Add to Intelligence Feed"
              >
                <Rss size={11} className="mr-1" /> Add to Feed
              </Button>
            )}
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-400" onClick={(e) => { e.stopPropagation(); onDelete(doc.id); }}
              title="Delete" data-testid={`delete-doc-${doc.id}`}>
              <Trash2 size={13} />
            </Button>
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </div>
      </CardHeader>

      {expanded && doc.processed && a && !a.error && (
        <CardContent className="p-4 space-y-4" data-testid={`analysis-detail-${doc.id}`}>
          {a.executive_summary && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Executive Summary</h4>
              <p className="text-sm leading-relaxed">{a.executive_summary}</p>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 bg-muted/20 border border-border">
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-2 flex items-center gap-1">
                <Shield size={12} /> Threat Classification
              </h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Severity</span>
                  <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${SEV_STYLES[tc.severity] || ""}`}>{tc.severity}</Badge>
                </div>
                <div className="flex justify-between"><span className="text-muted-foreground">Category</span><span className="font-mono text-xs">{tc.threat_category}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Confidence</span><span className="font-mono text-xs">{tc.confidence}</span></div>
              </div>
            </div>
            <div className="p-3 bg-muted/20 border border-border">
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-2 flex items-center gap-1">
                <Target size={12} /> Relevance
              </h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Score</span><span className="font-bold">{ra.relevance_score}/10</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Primary</span><span className="font-mono text-xs">{ra.primary_region}</span></div>
                {ra.secondary_regions?.length > 0 && (
                  <div className="flex justify-between"><span className="text-muted-foreground">Secondary</span><span className="font-mono text-xs">{ra.secondary_regions.join(", ")}</span></div>
                )}
              </div>
              {ra.relevance_explanation && <p className="text-xs text-muted-foreground mt-2">{ra.relevance_explanation}</p>}
            </div>
          </div>
          {pa.pattern_description && (
            <div className="p-3 bg-muted/20 border border-border">
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1 flex items-center gap-1">
                <TrendingUp size={12} /> Pattern Analysis
              </h4>
              <div className="flex items-center gap-2 mb-1">
                <Badge className={`rounded-none text-[9px] px-1.5 py-0 border ${pa.matches_existing_pattern ? "bg-amber-500/20 text-amber-400 border-amber-500/30" : "bg-blue-500/20 text-blue-400 border-blue-500/30"}`}>
                  {pa.matches_existing_pattern ? "MATCHES EXISTING PATTERN" : "NEW PATTERN"}
                </Badge>
              </div>
              <p className="text-sm">{pa.pattern_description}</p>
            </div>
          )}
          {(ke.actors?.length > 0 || ke.locations?.length > 0 || ke.events?.length > 0) && (
            <div className="p-3 bg-muted/20 border border-border">
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-2 flex items-center gap-1">
                <Users size={12} /> Key Entities
                <span className="text-muted-foreground/50 ml-1">(click to select for keyword bank)</span>
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {ke.actors?.map((a, i) => {
                  const sel = selectedKw.has(`entity|${a}`);
                  return (
                    <Badge key={`a-${i}`}
                      className={`rounded-none text-[9px] px-1.5 py-0 border cursor-pointer transition-all ${
                        sel ? "bg-red-500/25 text-red-300 border-red-400 ring-1 ring-red-400/50" : "bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/15 hover:border-red-500/40"
                      }`}
                      onClick={() => { const s = new Set(selectedKw); s.has(`entity|${a}`) ? s.delete(`entity|${a}`) : s.add(`entity|${a}`); setSelectedKw(s); }}
                      data-testid={`kw-actor-${i}`}
                    >{sel && <CheckCircle size={9} className="mr-0.5" />}{typeof a === "string" ? a : JSON.stringify(a)}</Badge>
                  );
                })}
                {ke.locations?.map((l, i) => {
                  const sel = selectedKw.has(`geo|${l}`);
                  return (
                    <Badge key={`l-${i}`}
                      className={`rounded-none text-[9px] px-1.5 py-0 border cursor-pointer transition-all ${
                        sel ? "bg-blue-500/25 text-blue-300 border-blue-400 ring-1 ring-blue-400/50" : "bg-blue-500/10 text-blue-400 border-blue-500/20 hover:bg-blue-500/15 hover:border-blue-500/40"
                      }`}
                      onClick={() => { const s = new Set(selectedKw); s.has(`geo|${l}`) ? s.delete(`geo|${l}`) : s.add(`geo|${l}`); setSelectedKw(s); }}
                      data-testid={`kw-loc-${i}`}
                    >{sel && <CheckCircle size={9} className="mr-0.5" />}{typeof l === "string" ? l : JSON.stringify(l)}</Badge>
                  );
                })}
                {ke.events?.map((e, i) => {
                  const sel = selectedKw.has(`primary|${e}`);
                  return (
                    <Badge key={`e-${i}`}
                      className={`rounded-none text-[9px] px-1.5 py-0 border cursor-pointer transition-all ${
                        sel ? "bg-amber-500/25 text-amber-300 border-amber-400 ring-1 ring-amber-400/50" : "bg-amber-500/10 text-amber-400 border-amber-500/20 hover:bg-amber-500/15 hover:border-amber-500/40"
                      }`}
                      onClick={() => { const s = new Set(selectedKw); s.has(`primary|${e}`) ? s.delete(`primary|${e}`) : s.add(`primary|${e}`); setSelectedKw(s); }}
                      data-testid={`kw-event-${i}`}
                    >{sel && <CheckCircle size={9} className="mr-0.5" />}{typeof e === "string" ? e : JSON.stringify(e)}</Badge>
                  );
                })}
              </div>
              {selectedKw.size > 0 && (
                <div className="mt-3 pt-2 border-t border-border flex items-center gap-2" data-testid="kw-add-bar">
                  <span className="text-[10px] font-mono text-muted-foreground">{selectedKw.size} selected</span>
                  <Button
                    size="sm"
                    className="h-7 rounded-none text-[10px] uppercase tracking-wider"
                    disabled={addingKw}
                    onClick={async () => {
                      setAddingKw(true);
                      let added = 0, skipped = 0;
                      for (const entry of selectedKw) {
                        const [type, keyword] = entry.split("|");
                        const clean = keyword.replace(/\s*\(.*?\)\s*/g, "").trim();
                        if (clean.length < 2) { skipped++; continue; }
                        try {
                          await axios.post(`${api}/keywords/add`, { keyword: clean, type, score: 70 });
                          added++;
                        } catch { skipped++; }
                      }
                      if (added > 0) toast.success(`${added} keyword${added > 1 ? "s" : ""} added to keyword bank`);
                      if (skipped > 0) toast.info(`${skipped} skipped (duplicates or too short)`);
                      setSelectedKw(new Set());
                      setAddingKw(false);
                    }}
                    data-testid="add-selected-kw-btn"
                  >
                    {addingKw ? <Loader2 size={11} className="mr-1 animate-spin" /> : <Plus size={11} className="mr-1" />}
                    Add to Keyword Bank
                  </Button>
                  <button
                    className="text-[10px] text-muted-foreground font-mono hover:text-foreground"
                    onClick={() => setSelectedKw(new Set())}
                    data-testid="clear-kw-selection"
                  >Clear</button>
                </div>
              )}
            </div>
          )}
          {actions.length > 0 && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-2">Recommended Actions</h4>
              <div className="space-y-1.5">
                {actions.map((act, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <Badge className={`rounded-none text-[8px] px-1 py-0 shrink-0 mt-0.5 border ${
                      act.priority === "IMMEDIATE" ? "bg-red-500/20 text-red-400 border-red-500/30" :
                      act.priority === "HIGH" ? "bg-orange-500/20 text-orange-400 border-orange-500/30" :
                      "bg-muted text-muted-foreground border-border"
                    }`}>{act.priority}</Badge>
                    <span>{act.action}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {a.cross_references && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Cross-References to Current Intelligence</h4>
              {typeof a.cross_references === "string" ? (
                <p className="text-sm text-muted-foreground">{a.cross_references}</p>
              ) : (
                <div className="space-y-1 text-sm text-muted-foreground">
                  {Object.entries(a.cross_references).map(([key, val]) => (
                    <div key={key}><span className="text-foreground font-mono text-xs">{key.replace(/_/g, " ")}:</span> {typeof val === "string" ? val : JSON.stringify(val)}</div>
                  ))}
                </div>
              )}
            </div>
          )}
          {a.intelligence_gaps?.length > 0 && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Intelligence Gaps</h4>
              <ul className="list-disc list-inside text-sm text-muted-foreground space-y-0.5">
                {a.intelligence_gaps.map((g, i) => <li key={i}>{typeof g === "string" ? g : JSON.stringify(g)}</li>)}
              </ul>
            </div>
          )}
        </CardContent>
      )}

      {expanded && doc.processed && a?.error && (
        <CardContent className="p-4">
          <div className="text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle size={14} /> Analysis error: {a.error}
          </div>
        </CardContent>
      )}

      {expanded && !doc.processed && (
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-amber-400 text-sm">
            <RefreshCw size={14} className="animate-spin" />
            Analysis in progress — this may take 15-30 seconds...
          </div>
        </CardContent>
      )}
    </Card>
  );
}


function AddToFeedModal({ doc, api, onClose, onSuccess }) {
  const a = doc?.analysis || {};
  const tc = a.threat_classification || {};
  const ra = a.relevance_assessment || {};

  const [title, setTitle] = useState(doc?.filename || "");
  const [severity, setSeverity] = useState((tc.severity || "MEDIUM").toLowerCase());
  const [priorityScore, setPriorityScore] = useState(
    ra.relevance_score ? Math.min(100, ra.relevance_score * 10) : 50
  );
  const [threatCategory, setThreatCategory] = useState(tc.threat_category || "Unclassified");
  const [region, setRegion] = useState(ra.primary_region || "Unknown");
  const [summary, setSummary] = useState(a.executive_summary || "");
  const [crossBorder, setCrossBorder] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const res = await axios.post(`${api}/add-to-feed`, {
        url: doc.source_url,
        title: title.trim(),
        severity,
        priority_score: priorityScore,
        threat_category: threatCategory,
        state: region,
        ai_summary: summary.trim(),
        is_cross_border: crossBorder,
        tags: [],
      });
      toast.success(res.data.message || "Added to intelligence feed");
      onSuccess();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add to feed");
    }
    setSubmitting(false);
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="add-feed-modal">
      <Card className="border border-primary/30 rounded-none bg-card w-full max-w-lg max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <CardHeader className="py-3 px-4 border-b border-border bg-primary/5">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Rss size={16} className="text-primary" />
            Add to Intelligence Feed
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} className="rounded-none text-sm" data-testid="feed-title" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Severity</label>
              <Select value={severity} onValueChange={setSeverity}>
                <SelectTrigger className="rounded-none" data-testid="feed-severity">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="rounded-none">
                  <SelectItem value="critical" className="text-xs">Critical</SelectItem>
                  <SelectItem value="high" className="text-xs">High</SelectItem>
                  <SelectItem value="medium" className="text-xs">Medium</SelectItem>
                  <SelectItem value="low" className="text-xs">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Priority Score (0-100)</label>
              <Input type="number" min="0" max="100" value={priorityScore}
                onChange={(e) => setPriorityScore(Math.min(100, Math.max(0, parseInt(e.target.value) || 0)))}
                className="rounded-none text-sm font-mono" data-testid="feed-priority" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Threat Category</label>
              <Select value={threatCategory} onValueChange={setThreatCategory}>
                <SelectTrigger className="rounded-none" data-testid="feed-threat">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="rounded-none max-h-48">
                  {THREAT_CATEGORIES.map((cat) => (
                    <SelectItem key={cat} value={cat} className="text-xs">{cat}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Region / State</label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger className="rounded-none" data-testid="feed-region">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="rounded-none max-h-48">
                  {NER_STATES.map((st) => (
                    <SelectItem key={st} value={st} className="text-xs">{st}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Intelligence Summary</label>
            <textarea
              value={summary} onChange={(e) => setSummary(e.target.value)}
              className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary resize-none h-20"
              placeholder="Brief intelligence summary..."
              data-testid="feed-summary"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={crossBorder} onChange={(e) => setCrossBorder(e.target.checked)}
              className="w-4 h-4 accent-primary" data-testid="feed-cross-border" />
            <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Cross-Border Item</span>
          </label>

          <div className="flex gap-2 pt-2">
            <Button onClick={handleSubmit} disabled={submitting || !title.trim()} className="flex-1 rounded-none uppercase text-xs font-bold tracking-wider" data-testid="confirm-add-feed-btn">
              {submitting ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Plus size={14} className="mr-2" />}
              Add to Feed
            </Button>
            <Button variant="outline" onClick={onClose} className="rounded-none uppercase text-xs tracking-wider" data-testid="cancel-add-feed-btn">
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


function QuickAddToFeed({ api, urlInput, setUrlInput }) {
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [priorityScore, setPriorityScore] = useState(50);
  const [threatCategory, setThreatCategory] = useState("Unclassified");
  const [region, setRegion] = useState("Unknown");
  const [summary, setSummary] = useState("");
  const [crossBorder, setCrossBorder] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setSubmitting(true);
    try {
      const res = await axios.post(`${api}/add-to-feed`, {
        url: urlInput.trim(),
        title: title.trim(),
        severity,
        priority_score: priorityScore,
        threat_category: threatCategory,
        state: region,
        ai_summary: summary.trim(),
        is_cross_border: crossBorder,
        tags: [],
      });
      toast.success(res.data.message || "Added to intelligence feed");
      setUrlInput("");
      setShowForm(false);
      setTitle(""); setSummary("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add to feed");
    }
    setSubmitting(false);
  };

  if (!showForm) {
    return (
      <Button
        type="button"
        variant="outline"
        onClick={() => setShowForm(true)}
        disabled={!urlInput.trim()}
        className="rounded-none uppercase text-xs tracking-wider border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
        data-testid="quick-add-feed-btn"
      >
        <Rss size={12} className="mr-2" />Add to Feed
      </Button>
    );
  }

  return (
    <div className="border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-3 mt-3" data-testid="quick-add-form">
      <p className="text-[10px] uppercase tracking-widest text-emerald-400 font-mono font-semibold">
        Add Directly to Intelligence Feed
      </p>
      <div>
        <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Title (optional — auto-scraped if blank)</label>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} className="rounded-none text-sm" placeholder="Article title..." data-testid="quick-title" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-0.5">Severity</label>
          <Select value={severity} onValueChange={setSeverity}>
            <SelectTrigger className="rounded-none h-8 text-xs" data-testid="quick-severity"><SelectValue /></SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="critical" className="text-xs">Critical</SelectItem>
              <SelectItem value="high" className="text-xs">High</SelectItem>
              <SelectItem value="medium" className="text-xs">Medium</SelectItem>
              <SelectItem value="low" className="text-xs">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-0.5">Priority (0-100)</label>
          <Input type="number" min="0" max="100" value={priorityScore}
            onChange={(e) => setPriorityScore(Math.min(100, Math.max(0, parseInt(e.target.value) || 0)))}
            className="rounded-none h-8 text-xs font-mono" data-testid="quick-priority" />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-0.5">Threat</label>
          <Select value={threatCategory} onValueChange={setThreatCategory}>
            <SelectTrigger className="rounded-none h-8 text-xs" data-testid="quick-threat"><SelectValue /></SelectTrigger>
            <SelectContent className="rounded-none max-h-48">
              {THREAT_CATEGORIES.map((cat) => (
                <SelectItem key={cat} value={cat} className="text-xs">{cat}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-0.5">Region</label>
          <Select value={region} onValueChange={setRegion}>
            <SelectTrigger className="rounded-none h-8 text-xs" data-testid="quick-region"><SelectValue /></SelectTrigger>
            <SelectContent className="rounded-none max-h-48">
              {NER_STATES.map((st) => (
                <SelectItem key={st} value={st} className="text-xs">{st}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div>
        <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-0.5">Summary (optional)</label>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)}
          className="w-full bg-background border border-border px-3 py-2 text-xs font-mono focus:outline-none focus:border-primary resize-none h-16"
          placeholder="Brief intelligence summary..." data-testid="quick-summary" />
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={crossBorder} onChange={(e) => setCrossBorder(e.target.checked)} className="w-3.5 h-3.5 accent-primary" />
          <span className="text-[10px] font-mono uppercase text-muted-foreground">Cross-Border</span>
        </label>
        <div className="flex-1" />
        <Button type="button" variant="outline" onClick={() => setShowForm(false)} className="rounded-none text-xs h-8" data-testid="cancel-quick-add">Cancel</Button>
        <Button type="button" onClick={handleSubmit} disabled={submitting || !urlInput.trim()} className="rounded-none text-xs h-8 uppercase tracking-wider" data-testid="submit-quick-add">
          {submitting ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Plus size={12} className="mr-1" />}
          Add to Feed
        </Button>
      </div>
    </div>
  );
}


export default function DocumentUpload({ api }) {
  const [documents, setDocuments] = useState([]);
  const [tab, setTab] = useState("file");
  const [uploading, setUploading] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [feedModal, setFeedModal] = useState(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/uploaded-documents`);
      setDocuments(res.data.documents || []);
    } catch (e) {
      console.error("Failed to fetch documents:", e);
    }
  }, [api]);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  useEffect(() => {
    const hasPending = documents.some(d => !d.processed);
    if (!hasPending) return;
    const interval = setInterval(fetchDocuments, 5000);
    return () => clearInterval(interval);
  }, [documents, fetchDocuments]);

  const handleFile = async (file) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post(`${api}/upload-document`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(`"${file.name}" uploaded — analysis starting`);
      fetchDocuments();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    }
    setUploading(false);
  };

  const handleURL = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setUploading(true);
    try {
      await axios.post(`${api}/analyze-url`, { url: urlInput.trim(), analysis_query: queryInput.trim() });
      toast.success("URL fetched — analysis starting");
      setUrlInput("");
      setQueryInput("");
      fetchDocuments();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to analyze URL");
    }
    setUploading(false);
  };

  const handleDelete = async (docId) => {
    if (!window.confirm("Delete this analysis?")) return;
    try {
      await axios.delete(`${api}/uploaded-documents/${docId}`);
      toast.success("Deleted");
      fetchDocuments();
    } catch (e) {
      toast.error("Delete failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="document-analysis-page">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">
          Manual Intelligence Uploads
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Analyze articles or add them directly to the intelligence feed with custom parameters
        </p>
      </div>

      {/* Input Tabs */}
      <Card className="border border-border rounded-none bg-card" data-testid="upload-card">
        <CardHeader className="py-0 px-0 border-b border-border">
          <div className="flex">
            <button
              onClick={() => setTab("file")}
              className={`flex-1 py-3 text-xs uppercase tracking-widest font-mono text-center border-b-2 transition-colors ${
                tab === "file" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              data-testid="tab-file"
            >
              <Upload size={14} className="inline mr-2" />Upload File
            </button>
            <button
              onClick={() => setTab("url")}
              className={`flex-1 py-3 text-xs uppercase tracking-widest font-mono text-center border-b-2 transition-colors ${
                tab === "url" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              data-testid="tab-url"
            >
              <Link2 size={14} className="inline mr-2" />Analyze URL
            </button>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          {tab === "file" ? (
            <div
              className={`border-2 border-dashed p-8 text-center transition-all cursor-pointer ${
                dragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
              }`}
              onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
              onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); setDragActive(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
              data-testid="upload-dropzone"
            >
              <Upload className={`w-10 h-10 mx-auto mb-3 ${dragActive ? "text-primary" : "text-muted-foreground"}`} />
              <p className="text-sm mb-1">{dragActive ? "Drop file here" : "Drag & drop a document"}</p>
              <p className="text-[10px] text-muted-foreground font-mono mb-3">PDF, Word, Excel, TXT</p>
              <label className="cursor-pointer">
                <input type="file" className="hidden" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
                  onChange={(e) => { if (e.target.files[0]) handleFile(e.target.files[0]); }}
                  disabled={uploading} data-testid="file-input" id="file-upload-input" />
                <span
                  role="button"
                  tabIndex={0}
                  onClick={() => document.getElementById('file-upload-input')?.click()}
                  className="inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-all bg-primary text-primary-foreground shadow-xs hover:bg-primary/90 h-9 px-4 py-2 rounded-none uppercase text-xs tracking-wider cursor-pointer"
                  data-testid="select-file-btn"
                >
                  {uploading ? <><RefreshCw size={12} className="mr-2 animate-spin" />Uploading...</> : "Select File"}
                </span>
              </label>
            </div>
          ) : (
            <div className="space-y-3">
              <form onSubmit={handleURL} className="space-y-3">
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">Article / Report URL</label>
                  <input
                    type="url" value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
                    placeholder="https://example.com/article..."
                    className="w-full bg-background border border-border px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-primary transition-colors"
                    required data-testid="url-input"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono block mb-1">
                    Specific Analysis Query <span className="text-muted-foreground/50">(optional — for AI analysis only)</span>
                  </label>
                  <textarea
                    value={queryInput} onChange={(e) => setQueryInput(e.target.value)}
                    placeholder="e.g., Assess the implications of this development for Manipur border security..."
                    className="w-full bg-background border border-border px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-primary transition-colors resize-none h-20"
                    data-testid="query-input"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={uploading} className="rounded-none uppercase text-xs tracking-wider" data-testid="analyze-url-btn">
                    {uploading ? <><RefreshCw size={12} className="mr-2 animate-spin" />Analyzing...</> : <><Search size={12} className="mr-2" />Analyze</>}
                  </Button>
                  <QuickAddToFeed api={api} urlInput={urlInput} setUrlInput={setUrlInput} />
                </div>
              </form>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Analysis Results */}
      <div className="space-y-3">
        <h2 className="text-xs uppercase tracking-widest font-mono text-muted-foreground">
          Analysis History ({documents.length})
        </h2>
        {documents.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No documents analyzed yet</p>
            <p className="text-xs mt-1">Upload a PDF or paste a URL to get started</p>
          </div>
        ) : (
          documents.map((doc) => (
            <AnalysisCard
              key={doc.id}
              doc={doc}
              onDelete={handleDelete}
              onAddToFeed={(d) => setFeedModal(d)}
              api={api}
            />
          ))
        )}
      </div>

      {/* Add to Feed Modal (after analysis) */}
      {feedModal && (
        <AddToFeedModal
          doc={feedModal}
          api={api}
          onClose={() => setFeedModal(null)}
          onSuccess={() => { setFeedModal(null); fetchDocuments(); }}
        />
      )}
    </div>
  );
}
