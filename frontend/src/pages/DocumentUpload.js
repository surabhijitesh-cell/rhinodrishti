import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Upload, Link2, FileText, Trash2, RefreshCw, CheckCircle, AlertTriangle,
  Clock, Shield, Target, MapPin, Users, TrendingUp, ChevronDown, ChevronUp, Search
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

const SEV_STYLES = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-green-500/20 text-green-400 border-green-500/30",
};

function AnalysisCard({ doc, onDelete, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
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
          {/* Executive Summary */}
          {a.executive_summary && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Executive Summary</h4>
              <p className="text-sm leading-relaxed">{a.executive_summary}</p>
            </div>
          )}

          {/* Threat Classification + Relevance side by side */}
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

          {/* Pattern Analysis */}
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

          {/* Key Entities */}
          {(ke.actors?.length > 0 || ke.locations?.length > 0) && (
            <div className="p-3 bg-muted/20 border border-border">
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-2 flex items-center gap-1">
                <Users size={12} /> Key Entities
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {ke.actors?.map((a, i) => <Badge key={`a-${i}`} className="rounded-none text-[9px] px-1.5 py-0 bg-red-500/10 text-red-400 border border-red-500/20">{a}</Badge>)}
                {ke.locations?.map((l, i) => <Badge key={`l-${i}`} className="rounded-none text-[9px] px-1.5 py-0 bg-blue-500/10 text-blue-400 border border-blue-500/20">{l}</Badge>)}
                {ke.events?.map((e, i) => <Badge key={`e-${i}`} className="rounded-none text-[9px] px-1.5 py-0 bg-amber-500/10 text-amber-400 border border-amber-500/20">{e}</Badge>)}
              </div>
            </div>
          )}

          {/* Recommended Actions */}
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

          {/* Cross References */}
          {a.cross_references && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Cross-References to Current Intelligence</h4>
              <p className="text-sm text-muted-foreground">{a.cross_references}</p>
            </div>
          )}

          {/* Intelligence Gaps */}
          {a.intelligence_gaps?.length > 0 && (
            <div>
              <h4 className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Intelligence Gaps</h4>
              <ul className="list-disc list-inside text-sm text-muted-foreground space-y-0.5">
                {a.intelligence_gaps.map((g, i) => <li key={i}>{g}</li>)}
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


export default function DocumentUpload({ api }) {
  const [documents, setDocuments] = useState([]);
  const [tab, setTab] = useState("file"); // file | url
  const [uploading, setUploading] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [queryInput, setQueryInput] = useState("");
  const [dragActive, setDragActive] = useState(false);

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/uploaded-documents`);
      setDocuments(res.data.documents || []);
    } catch (e) {
      console.error("Failed to fetch documents:", e);
    }
  }, [api]);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  // Auto-refresh for pending analyses
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
          Intelligence Analysis
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Upload a document or paste a URL for contextual threat assessment against current NER security environment
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
                  disabled={uploading} data-testid="file-input" />
                <Button as="span" disabled={uploading} className="rounded-none uppercase text-xs tracking-wider" data-testid="select-file-btn">
                  {uploading ? <><RefreshCw size={12} className="mr-2 animate-spin" />Uploading...</> : "Select File"}
                </Button>
              </label>
            </div>
          ) : (
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
                  Specific Analysis Query <span className="text-muted-foreground/50">(optional)</span>
                </label>
                <textarea
                  value={queryInput} onChange={(e) => setQueryInput(e.target.value)}
                  placeholder="e.g., Assess the implications of this development for Manipur border security..."
                  className="w-full bg-background border border-border px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-primary transition-colors resize-none h-20"
                  data-testid="query-input"
                />
              </div>
              <Button type="submit" disabled={uploading} className="rounded-none uppercase text-xs tracking-wider" data-testid="analyze-url-btn">
                {uploading ? <><RefreshCw size={12} className="mr-2 animate-spin" />Analyzing...</> : <><Search size={12} className="mr-2" />Analyze</>}
              </Button>
            </form>
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
            <AnalysisCard key={doc.id} doc={doc} onDelete={handleDelete} onRefresh={fetchDocuments} />
          ))
        )}
      </div>
    </div>
  );
}
