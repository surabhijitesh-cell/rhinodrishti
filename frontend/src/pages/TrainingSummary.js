import { useState, useEffect, useRef } from "react";
import {
  BarChart3, Brain, ShieldAlert, TrendingDown, TrendingUp,
  Gauge, Users, Star, AlertTriangle, Target, RefreshCw, Upload,
  FileText, Trash2, CheckCircle, Link, Play, Loader2, Clock, Globe,
  Activity, Hash, Zap
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";

const STATUS_COLORS = {
  pending: "text-yellow-400 border-yellow-500/30",
  ready: "text-blue-400 border-blue-500/30",
  processing: "text-amber-400 border-amber-500/30",
  completed: "text-emerald-400 border-emerald-500/30",
};

export default function TrainingSummary({ api }) {
  const { user } = useAuth();
  const isViewer = user?.role === "viewer";
  const [stats, setStats] = useState(null);
  const [profile, setProfile] = useState(null);
  const [queue, setQueue] = useState([]);
  const [insights, setInsights] = useState(null);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [urlInput, setUrlInput] = useState("");
  const [urlRelevance, setUrlRelevance] = useState(null);
  const [activityLog, setActivityLog] = useState(null);
  const [logPage, setLogPage] = useState(1);
  const [effectiveness, setEffectiveness] = useState(null);
  const [biasProfile, setBiasProfile] = useState(null);
  const [addingUrl, setAddingUrl] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);
  const pollRef = useRef(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statsR, profileR, queueR, insightsR, activityR, effR, biasR] = await Promise.all([
        axios.get(`${api}/feedback/stats`).catch(() => ({ data: null })),
        axios.get(`${api}/feedback/training-profile`).catch(() => ({ data: null })),
        axios.get(`${api}/training/queue`).catch(() => ({ data: { items: [] } })),
        axios.get(`${api}/training/insights`).catch(() => ({ data: null })),
        axios.get(`${api}/training/activity-log?page=${logPage}`).catch(() => ({ data: null })),
        axios.get(`${api}/training/effectiveness`).catch(() => ({ data: null })),
        axios.get(`${api}/feedback/bias-profile`).catch(() => ({ data: null })),
      ]);
      setStats(statsR.data);
      setProfile(profileR.data);
      setQueue(queueR.data.items || []);
      setInsights(insightsR.data);
      setActivityLog(activityR.data);
      setEffectiveness(effR.data);
      setBiasProfile(biasR.data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, [api]);

  // Refetch activity log when page changes
  useEffect(() => {
    if (!loading) {
      axios.get(`${api}/training/activity-log?page=${logPage}`)
        .then((res) => setActivityLog(res.data))
        .catch(() => {});
    }
  }, [logPage]);

  // Poll training progress + queue refresh
  useEffect(() => {
    if (!training) return;
    pollRef.current = setInterval(async () => {
      try {
        const [progRes, queueRes] = await Promise.all([
          axios.get(`${api}/training/progress`),
          axios.get(`${api}/training/queue`),
        ]);
        setProgress(progRes.data);
        // Update queue live — completed items will disappear from pending view
        setQueue(queueRes.data.items || []);
        if (!progRes.data.running && progRes.data.total > 0) {
          setTraining(false);
          clearInterval(pollRef.current);
          toast.success("Training complete!");
          fetchAll();
        }
      } catch {}
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [training, api]);

  const addUrl = async () => {
    if (!urlInput.trim()) return;
    setAddingUrl(true);
    try {
      const payload = { url: urlInput.trim() };
      if (urlRelevance) payload.relevance = urlRelevance;
      await axios.post(`${api}/training/add-url`, payload);
      toast.success("URL added to training queue");
      setUrlInput("");
      setUrlRelevance(null);
      const res = await axios.get(`${api}/training/queue`);
      setQueue(res.data.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add URL");
    }
    setAddingUrl(false);
  };

  const uploadFile = async (file) => {
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await axios.post(`${api}/training/upload-file`, fd);
      toast.success(`Uploaded: ${file.name}`);
      const res = await axios.get(`${api}/training/queue`);
      setQueue(res.data.items || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    }
    setUploading(false);
  };

  const deleteItem = async (id) => {
    try {
      await axios.delete(`${api}/training/queue/${id}`);
      setQueue((q) => q.filter((i) => i.id !== id));
      toast.success("Item removed");
    } catch {
      toast.error("Failed to delete");
    }
  };

  const startTraining = async () => {
    setTraining(true);
    try {
      await axios.post(`${api}/training/run`);
      toast.success("Training pipeline started");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to start training");
      setTraining(false);
    }
  };

  const pendingCount = queue.filter((i) => ["pending", "ready"].includes(i.status)).length;
  const completedCount = queue.filter((i) => i.status === "completed").length;
  const pct = progress && progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
  // During training, only show non-completed items so they clear sequentially
  const displayQueue = training
    ? queue.filter((i) => i.status !== "completed")
    : queue;

  if (loading) {
    return (
      <div className="space-y-6" data-testid="training-summary-page">
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">
          Training & Feedback
        </h1>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="border border-border bg-card p-6 h-32 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="training-summary-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="training-title">
            Training & Feedback
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            Upload missed intelligence, rate articles, and train the system
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-none uppercase text-xs tracking-wider" onClick={fetchAll} data-testid="refresh-training-btn">
          <RefreshCw size={14} className="mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: "Total Ratings", value: stats?.total_feedback || 0, icon: BarChart3, color: "text-primary" },
          { label: "Items Rated", value: stats?.unique_items_rated || 0, icon: Target, color: "text-blue-400" },
          { label: "Analysts", value: stats?.unique_devices || 0, icon: Users, color: "text-emerald-400" },
          { label: "Avg Rating", value: stats?.global_avg_rating?.toFixed(1) || "N/A", icon: Star, color: "text-amber-400" },
          { label: "Training Queue", value: queue.length, icon: Brain, color: "text-purple-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="border border-border rounded-none bg-card">
            <CardContent className="p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <Icon size={12} className={color} />
                <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">{label}</span>
              </div>
              <p className="text-xl font-bold font-['Barlow_Condensed']">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ===== TRAINING EFFECTIVENESS SCORE ===== */}
      <Card className="border border-border rounded-none bg-card" data-testid="effectiveness-score-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Gauge size={16} className="text-cyan-400" />
            Training Effectiveness Score
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          {effectiveness?.score != null ? (
            <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-6">
              {/* Score dial */}
              <div className="flex flex-col items-center justify-center gap-1.5">
                <div className={`relative w-28 h-28 rounded-full border-4 flex items-center justify-center ${
                  effectiveness.grade === "EXCELLENT" ? "border-emerald-400" :
                  effectiveness.grade === "GOOD" ? "border-blue-400" :
                  effectiveness.grade === "MODERATE" ? "border-amber-400" :
                  "border-red-400"
                }`} data-testid="effectiveness-dial">
                  <div className="text-center">
                    <p className={`text-3xl font-black font-['Barlow_Condensed'] ${
                      effectiveness.grade === "EXCELLENT" ? "text-emerald-400" :
                      effectiveness.grade === "GOOD" ? "text-blue-400" :
                      effectiveness.grade === "MODERATE" ? "text-amber-400" :
                      "text-red-400"
                    }`}>{effectiveness.score}%</p>
                  </div>
                </div>
                <Badge variant="outline" className={`rounded-none text-[10px] px-2.5 py-0.5 uppercase tracking-wider ${
                  effectiveness.grade === "EXCELLENT" ? "text-emerald-400 border-emerald-500/40" :
                  effectiveness.grade === "GOOD" ? "text-blue-400 border-blue-500/40" :
                  effectiveness.grade === "MODERATE" ? "text-amber-400 border-amber-500/40" :
                  "text-red-400 border-red-500/40"
                }`} data-testid="effectiveness-grade">
                  {effectiveness.grade?.replace("_", " ")}
                </Badge>
                <p className="text-[10px] text-muted-foreground font-mono">{effectiveness.sample_size} items analyzed</p>
                {effectiveness.delta_from_last != null && (
                  <div className={`flex items-center gap-1 text-xs font-mono ${
                    effectiveness.delta_from_last > 0 ? "text-emerald-400" :
                    effectiveness.delta_from_last < 0 ? "text-red-400" :
                    "text-muted-foreground"
                  }`} data-testid="effectiveness-delta">
                    {effectiveness.delta_from_last > 0 ? <TrendingUp size={12} /> :
                     effectiveness.delta_from_last < 0 ? <TrendingDown size={12} /> : null}
                    {effectiveness.delta_from_last > 0 ? "+" : ""}{effectiveness.delta_from_last}% since last run
                  </div>
                )}
              </div>

              {/* Details */}
              <div className="space-y-4">
                <p className="text-xs text-muted-foreground">
                  Measures alignment between AI classifications (severity) and analyst feedback ratings.
                  Higher scores mean the AI is classifying articles closer to how analysts rate them.
                </p>

                {/* Worst misalignments */}
                {effectiveness.worst_misalignments?.length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5 flex items-center gap-1">
                      <AlertTriangle size={10} className="text-red-400" /> Biggest Gaps (AI vs Analyst)
                    </p>
                    <div className="space-y-1">
                      {effectiveness.worst_misalignments.map((m) => (
                        <div key={m.id} className="flex items-center gap-2 text-xs border border-border p-1.5" data-testid={`misalign-${m.id}`}>
                          <span className="text-red-400 font-mono text-[10px] shrink-0 w-12">{Math.round(m.alignment * 100)}%</span>
                          <span className="truncate flex-1">{m.title || m.id}</span>
                          <span className="text-[9px] font-mono text-muted-foreground shrink-0">
                            AI:{m.ai_severity} | User:{m.analyst_avg}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Best alignments */}
                {effectiveness.best_alignments?.length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5 flex items-center gap-1">
                      <CheckCircle size={10} className="text-emerald-400" /> Best Alignments
                    </p>
                    <div className="space-y-1">
                      {effectiveness.best_alignments.map((m) => (
                        <div key={m.id} className="flex items-center gap-2 text-xs border border-border p-1.5" data-testid={`align-${m.id}`}>
                          <span className="text-emerald-400 font-mono text-[10px] shrink-0 w-12">{Math.round(m.alignment * 100)}%</span>
                          <span className="truncate flex-1">{m.title || m.id}</span>
                          <span className="text-[9px] font-mono text-muted-foreground shrink-0">
                            AI:{m.ai_severity} | User:{m.analyst_avg}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Trend sparkline */}
                {effectiveness.trend?.length > 1 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5 flex items-center gap-1">
                      <Hash size={10} /> Score History
                    </p>
                    <div className="flex items-end gap-1 h-10" data-testid="effectiveness-trend">
                      {[...effectiveness.trend].reverse().map((s, i) => (
                        <div key={i} className="flex flex-col items-center gap-0.5" title={`${s.score}% — ${new Date(s.timestamp).toLocaleDateString()}`}>
                          <div
                            className={`w-5 ${
                              s.score >= 65 ? "bg-emerald-500/60" : s.score >= 50 ? "bg-amber-500/60" : "bg-red-500/60"
                            }`}
                            style={{ height: `${Math.max(4, (s.score / 100) * 40)}px` }}
                          />
                          <span className="text-[8px] font-mono text-muted-foreground">{s.score}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Not enough data yet. Rate more articles on the Intelligence Feed to build an effectiveness baseline.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ===== LEFT: UPLOAD + QUEUE ===== */}
        <div className="space-y-4">
          {/* URL Input */}
          <Card className={`border border-border rounded-none bg-card ${isViewer ? "opacity-50" : ""}`} data-testid="url-input-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Link size={16} className="text-primary" />
                Add Intelligence URL
                {isViewer && <span className="text-[9px] text-muted-foreground font-normal ml-auto">View Only</span>}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Paste news URL here..."
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !isViewer && addUrl()}
                  className="rounded-none flex-1"
                  disabled={isViewer}
                  data-testid="training-url-input"
                />
                <Button onClick={addUrl} disabled={isViewer || addingUrl || !urlInput.trim()} className="rounded-none uppercase text-xs tracking-wider shrink-0 disabled:opacity-50 disabled:cursor-not-allowed" data-testid="add-url-btn"
                  title={isViewer ? "Viewers cannot upload training data" : "Add URL"}>
                  {addingUrl ? <Loader2 size={14} className="animate-spin" /> : <><Globe size={14} className="mr-1" /> Add</>}
                </Button>
              </div>
              {/* Relevance Tag */}
              <div className="flex items-center gap-3">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono shrink-0">Relevance Tag:</span>
                <div className="flex gap-1.5" data-testid="url-relevance-selector">
                  {[1, 2, 3, 4, 5, 6].map((val) => (
                    <button
                      key={val}
                      onClick={() => setUrlRelevance(urlRelevance === val ? null : val)}
                      className={`w-7 h-7 text-xs font-bold border transition-all duration-150 ${
                        urlRelevance === val
                          ? "bg-primary text-primary-foreground border-primary"
                          : "border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground"
                      }`}
                      data-testid={`url-relevance-${val}`}
                    >
                      {val}
                    </button>
                  ))}
                </div>
                {urlRelevance && (
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {urlRelevance <= 2 ? "Low" : urlRelevance <= 4 ? "Moderate" : "High"}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* File Upload */}
          <Card className={`border border-border rounded-none bg-card ${isViewer ? "opacity-50" : ""}`} data-testid="file-upload-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Upload size={16} className="text-emerald-400" />
                Upload Document
                {isViewer && <span className="text-[9px] text-muted-foreground font-normal ml-auto">View Only</span>}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div
                className={`border-2 border-dashed border-border p-5 text-center transition-colors ${isViewer ? "cursor-not-allowed" : "cursor-pointer hover:border-muted-foreground"}`}
                onClick={() => !isViewer && document.getElementById("train-file-input").click()}
                title={isViewer ? "Viewers cannot upload training data" : ""}
                data-testid="upload-dropzone"
              >
                <Upload size={20} className="mx-auto text-muted-foreground mb-1.5" />
                <p className="text-sm text-muted-foreground">{isViewer ? "Upload disabled for viewers" : uploading ? "Uploading..." : "Click to browse or drop file"}</p>
                <p className="text-[10px] text-muted-foreground/50 font-mono mt-0.5">PDF, DOCX, TXT</p>
              </div>
              <input id="train-file-input" type="file" className="hidden" accept=".pdf,.docx,.doc,.txt"
                onChange={async (e) => { if (e.target.files?.[0]) await uploadFile(e.target.files[0]); e.target.value = ""; }}
                disabled={isViewer}
              />
            </CardContent>
          </Card>

          {/* Train Button + Progress */}
          <Card className="border border-border rounded-none bg-card" data-testid="train-action-card">
            <CardContent className="p-4 space-y-3">
              <Button
                onClick={startTraining}
                disabled={isViewer || training || pendingCount === 0}
                className="w-full rounded-none uppercase text-sm font-bold tracking-wider py-5 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="train-btn"
                title={isViewer ? "Viewers cannot trigger training" : ""}
              >
                {training ? (
                  <><Loader2 size={16} className="mr-2 animate-spin" /> Training in Progress...</>
                ) : (
                  <><Play size={16} className="mr-2" /> Train Rhino Drishti ({pendingCount} items)</>
                )}
              </Button>

              {training && progress && (
                <div className="space-y-2" data-testid="training-progress">
                  <Progress value={pct} className="h-2 rounded-none" />
                  <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                    <span>{progress.current}/{progress.total} items</span>
                    <span>{pct}%</span>
                  </div>
                  {progress.current_title && (
                    <p className="text-[10px] font-mono text-muted-foreground truncate">
                      Processing: {progress.current_title}
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ===== RIGHT: TRAINING QUEUE ===== */}
        <Card className="border border-border rounded-none bg-card" data-testid="training-queue-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <FileText size={16} className="text-blue-400" />
              Training Queue ({displayQueue.length}{training && completedCount > 0 ? ` / ${queue.length} total` : ""})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {displayQueue.length === 0 ? (
              <p className="text-sm text-muted-foreground p-4">
                {training ? "All items processed!" : "No items in training queue. Add URLs or upload files above."}
              </p>
            ) : (
              <div className="max-h-[420px] overflow-y-auto divide-y divide-border">
                {displayQueue.map((item) => (
                  <div key={item.id} className="flex items-start gap-3 p-3 hover:bg-muted/5" data-testid={`queue-item-${item.id}`}>
                    {item.type === "url" ? (
                      <Globe size={14} className="text-blue-400 shrink-0 mt-0.5" />
                    ) : (
                      <FileText size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate font-medium">
                        {item.title || item.url || item.file_path || "Untitled"}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] font-mono text-muted-foreground">{item.source}</span>
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {new Date(item.uploaded_at).toLocaleDateString()}
                        </span>
                        <Badge variant="outline" className={`rounded-none text-[9px] px-1.5 py-0 uppercase ${STATUS_COLORS[item.status] || ""}`}>
                          {item.status}
                        </Badge>
                        {item.relevance && (
                          <Badge variant="outline" className="rounded-none text-[9px] px-1.5 py-0 text-primary border-primary/30">
                            REL: {item.relevance}/6
                          </Badge>
                        )}
                      </div>
                    </div>
                    <button onClick={() => deleteItem(item.id)} className="p-1 hover:text-red-400 transition-colors shrink-0" data-testid={`delete-queue-${item.id}`}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ===== TRAINING INSIGHTS ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Analyst Preferences from Feedback */}
        <Card className="border border-border rounded-none bg-card" data-testid="positive-weights-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <TrendingUp size={16} className="text-emerald-400" />
              Analyst Preferences (Feedback)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {profile?.positive_weights?.regions && Object.keys(profile.positive_weights.regions).length > 0 ? (
              <>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5">Preferred Regions</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.positive_weights.regions).map(([r, c]) => (
                      <Badge key={r} variant="outline" className="rounded-none text-[10px] text-emerald-400 border-emerald-500/30 px-2 py-0.5">{r} ({c})</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5">Preferred Threats</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.positive_weights.threat_categories || {}).map(([t, c]) => (
                      <Badge key={t} variant="outline" className="rounded-none text-[10px] text-blue-400 border-blue-500/30 px-2 py-0.5">{t} ({c})</Badge>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No preferences detected yet. Rate more articles to build a profile.</p>
            )}
          </CardContent>
        </Card>

        {/* Training Pipeline Insights */}
        <Card className="border border-border rounded-none bg-card" data-testid="training-insights-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <Brain size={16} className="text-purple-400" />
              Training Pipeline Insights
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {insights?.has_data ? (
              <>
                <p className="text-xs text-muted-foreground">{insights.items_processed} documents processed</p>
                {insights.positive_signals?.regions && Object.keys(insights.positive_signals.regions).length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5">Priority Regions</p>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(insights.positive_signals.regions).map(([r, c]) => (
                        <Badge key={r} variant="outline" className="rounded-none text-[10px] text-purple-400 border-purple-500/30 px-2 py-0.5">{r} ({c})</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {insights.positive_signals?.keywords && Object.keys(insights.positive_signals.keywords).length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1.5">Key Signals</p>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(insights.positive_signals.keywords).slice(0, 10).map(([k, c]) => (
                        <Badge key={k} variant="outline" className="rounded-none text-[10px] text-amber-400 border-amber-500/30 px-2 py-0.5">{k} ({c})</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No training data processed yet. Add URLs or files and click "Train Rhino Drishti".</p>
            )}
          </CardContent>
        </Card>

        {/* Noise Patterns from Feedback */}
        <Card className="border border-border rounded-none bg-card" data-testid="negative-weights-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <TrendingDown size={16} className="text-red-400" />
              Noise Patterns (Low-Rated)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {profile?.negative_weights?.regions && Object.keys(profile.negative_weights.regions).length > 0 ? (
              <>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(profile.negative_weights.threat_categories || {}).map(([c, n]) => (
                    <Badge key={c} variant="outline" className="rounded-none text-[10px] text-red-400 border-red-500/30 px-2 py-0.5">{c} ({n})</Badge>
                  ))}
                </div>
                {profile.noise_patterns?.slice(0, 5).map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <AlertTriangle size={10} className="text-red-400 shrink-0" />
                    <span className="truncate">{item.title}</span>
                  </div>
                ))}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No noise patterns identified yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Scoring Formula */}
        <Card className="border border-border rounded-none bg-card" data-testid="scoring-formula-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <ShieldAlert size={16} className="text-amber-400" />
              Scoring Integration
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="bg-muted/20 border border-border p-3 font-mono text-xs space-y-1">
              <p className="text-primary">final_score = base_ai_score + training_bias + feedback_bias</p>
              <p className="text-muted-foreground mt-1">training_bias = log(total_ratings + 1) * (avg_rating - 3.5)</p>
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { label: "High Rated", val: profile?.high_rated_count || 0, color: "text-emerald-400" },
                { label: "Low Rated", val: profile?.low_rated_count || 0, color: "text-red-400" },
                { label: "Recent 7d", val: stats?.recent_7d || 0, color: "" },
                { label: "Confidence", val: profile?.confidence_level || "N/A", color: "text-blue-400" },
              ].map(({ label, val, color }) => (
                <div key={label} className="p-2 border border-border">
                  <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">{label}</p>
                  <p className={`text-base font-bold font-['Barlow_Condensed'] ${color}`}>{val}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ===== ACTIVE FEEDBACK BIAS (AI PIPELINE INTEGRATION) ===== */}
      <Card className="border border-border rounded-none bg-card border-l-4 border-l-primary" data-testid="feedback-bias-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Zap size={16} className="text-primary" />
            Active Feedback Bias (Live AI Pipeline)
            {biasProfile?.status === "active" && (
              <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-green-500/20 text-green-400 border-green-500/30 ml-2">
                ACTIVE
              </Badge>
            )}
            {biasProfile?.status === "insufficient_data" && (
              <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-amber-500/20 text-amber-400 border-amber-500/30 ml-2">
                NEEDS DATA
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          {biasProfile?.status === "active" ? (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Based on <span className="text-foreground font-semibold">{biasProfile.total_ratings}</span> ratings across{" "}
                <span className="text-foreground font-semibold">{biasProfile.unique_items}</span> articles in the last{" "}
                <span className="text-foreground font-semibold">{biasProfile.window_label || "30 days"}</span>.
                This bias is dynamically injected into the AI classification pipeline.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Upweighted */}
                <div className="space-y-2">
                  <p className="text-[10px] uppercase tracking-wider text-emerald-400 font-mono font-semibold flex items-center gap-1">
                    <TrendingUp size={10} /> Upweighted by Analysts ({biasProfile.high_rated_items} items)
                  </p>
                  {Object.keys(biasProfile.upweight_regions || {}).length > 0 && (
                    <div>
                      <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Regions (+5 to +10 priority)</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(biasProfile.upweight_regions).map(([r, c]) => (
                          <Badge key={r} variant="outline" className="rounded-none text-[10px] text-emerald-400 border-emerald-500/30 px-2 py-0.5">
                            {r} ({c})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {Object.keys(biasProfile.upweight_threats || {}).length > 0 && (
                    <div>
                      <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Threat Categories</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(biasProfile.upweight_threats).map(([t, c]) => (
                          <Badge key={t} variant="outline" className="rounded-none text-[10px] text-blue-400 border-blue-500/30 px-2 py-0.5">
                            {t} ({c})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {Object.keys(biasProfile.upweight_actors || {}).length > 0 && (
                    <div>
                      <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Key Actors</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(biasProfile.upweight_actors).map(([a, c]) => (
                          <Badge key={a} variant="outline" className="rounded-none text-[10px] text-cyan-400 border-cyan-500/30 px-2 py-0.5">
                            {a} ({c})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {Object.keys(biasProfile.upweight_regions || {}).length === 0 &&
                   Object.keys(biasProfile.upweight_threats || {}).length === 0 && (
                    <p className="text-xs text-muted-foreground">No strong upweight signals yet.</p>
                  )}
                </div>

                {/* Downweighted */}
                <div className="space-y-2">
                  <p className="text-[10px] uppercase tracking-wider text-red-400 font-mono font-semibold flex items-center gap-1">
                    <TrendingDown size={10} /> Downweighted by Analysts ({biasProfile.low_rated_items} items)
                  </p>
                  {Object.keys(biasProfile.downweight_regions || {}).length > 0 && (
                    <div>
                      <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Regions (-5 to -10 priority)</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(biasProfile.downweight_regions).map(([r, c]) => (
                          <Badge key={r} variant="outline" className="rounded-none text-[10px] text-red-400 border-red-500/30 px-2 py-0.5">
                            {r} ({c})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {Object.keys(biasProfile.downweight_threats || {}).length > 0 && (
                    <div>
                      <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Threat Categories</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(biasProfile.downweight_threats).map(([t, c]) => (
                          <Badge key={t} variant="outline" className="rounded-none text-[10px] text-orange-400 border-orange-500/30 px-2 py-0.5">
                            {t} ({c})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {Object.keys(biasProfile.downweight_regions || {}).length === 0 &&
                   Object.keys(biasProfile.downweight_threats || {}).length === 0 && (
                    <p className="text-xs text-muted-foreground">No strong downweight signals yet.</p>
                  )}
                </div>
              </div>

              <div className="bg-muted/20 border border-border p-3 font-mono text-xs space-y-1 mt-2">
                <p className="text-primary">pipeline_prompt = base_classification + feedback_bias_context</p>
                <p className="text-muted-foreground mt-1">
                  influence: {biasProfile.influence_pct || "~20-25%"} weight ({biasProfile.influence || "moderate"}) | window: {biasProfile.window_label || "30 days"} ({biasProfile.window_mode || "rolling_30"}) | cache: 5 min TTL
                </p>
              </div>
            </div>
          ) : (
            <div className="text-center py-4">
              <Zap size={24} className="mx-auto text-muted-foreground/30 mb-2" />
              <p className="text-sm text-muted-foreground">
                {biasProfile?.status === "insufficient_data"
                  ? `Need at least ${biasProfile.min_required} ratings to activate bias. Currently: ${biasProfile.total_ratings}.`
                  : "Rate articles on the Intelligence Feed to build feedback bias for the AI pipeline."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== TRAINING ACTIVITY LOG ===== */}
      <Card className="border border-border rounded-none bg-card" data-testid="activity-log-card">
        <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Activity size={16} className="text-cyan-400" />
            Activity Log
          </CardTitle>
          {activityLog?.total_pages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline" size="sm"
                className="rounded-none text-[10px] h-6 px-2"
                disabled={logPage <= 1}
                onClick={() => setLogPage((p) => Math.max(1, p - 1))}
                data-testid="log-prev-page"
              >
                Prev
              </Button>
              <span className="text-[10px] font-mono text-muted-foreground">
                {activityLog.page}/{activityLog.total_pages}
              </span>
              <Button
                variant="outline" size="sm"
                className="rounded-none text-[10px] h-6 px-2"
                disabled={logPage >= activityLog.total_pages}
                onClick={() => setLogPage((p) => p + 1)}
                data-testid="log-next-page"
              >
                Next
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {activityLog?.entries?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="activity-log-table">
                <thead>
                  <tr className="border-b border-border bg-muted/10">
                    <th className="text-left p-2.5 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-36">Timestamp</th>
                    <th className="text-left p-2.5 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-16">Device</th>
                    <th className="text-left p-2.5 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-40">Activity Type</th>
                    <th className="text-left p-2.5 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-48">Volume</th>
                    <th className="text-left p-2.5 text-[9px] uppercase tracking-wider font-mono text-muted-foreground">Impact</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {activityLog.entries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-muted/5" data-testid={`activity-row-${entry.id}`}>
                      <td className="p-2.5 font-mono text-[10px] text-muted-foreground whitespace-nowrap">
                        {new Date(entry.timestamp).toLocaleString(undefined, {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                        })}
                      </td>
                      <td className="p-2.5">
                        {entry.device_id ? (
                          <span className="font-mono text-[10px] text-blue-400">{entry.device_id}</span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/40">—</span>
                        )}
                      </td>
                      <td className="p-2.5">
                        <Badge variant="outline" className={`rounded-none text-[9px] px-2 py-0.5 uppercase tracking-wider ${
                          entry.activity_type === "training_session"
                            ? "text-purple-400 border-purple-500/30"
                            : "text-cyan-400 border-cyan-500/30"
                        }`}>
                          {entry.activity_type === "training_session" ? "URL/Article Training" : "Rating Feedback"}
                        </Badge>
                      </td>
                      <td className="p-2.5 font-mono text-[10px]">
                        {entry.volume || `${entry.total_items || 0} items`}
                      </td>
                      <td className="p-2.5 text-[11px] text-muted-foreground leading-relaxed max-w-md">
                        {entry.impact_summary || "Processing..."}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-6 text-center">
              <Activity size={24} className="mx-auto text-muted-foreground/30 mb-2" />
              <p className="text-sm text-muted-foreground">
                No sessions recorded yet. Click "Train Rhino Drishti" or rate 5+ articles to generate activity.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
