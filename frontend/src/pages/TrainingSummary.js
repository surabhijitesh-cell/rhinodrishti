import { useState, useEffect, useRef } from "react";
import {
  BarChart3, Brain, ShieldAlert, TrendingDown, TrendingUp,
  Gauge, Users, Star, AlertTriangle, Target, RefreshCw, Upload,
  FileText, Trash2, CheckCircle, Link, Play, Loader2, Clock, Globe,
  Activity, Zap, Hash
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import axios from "axios";

const STATUS_COLORS = {
  pending: "text-yellow-400 border-yellow-500/30",
  ready: "text-blue-400 border-blue-500/30",
  processing: "text-amber-400 border-amber-500/30",
  completed: "text-emerald-400 border-emerald-500/30",
};

export default function TrainingSummary({ api }) {
  const [stats, setStats] = useState(null);
  const [profile, setProfile] = useState(null);
  const [queue, setQueue] = useState([]);
  const [insights, setInsights] = useState(null);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [urlInput, setUrlInput] = useState("");
  const [urlRelevance, setUrlRelevance] = useState(null);
  const [activityLog, setActivityLog] = useState(null);
  const [addingUrl, setAddingUrl] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);
  const pollRef = useRef(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statsR, profileR, queueR, insightsR, activityR] = await Promise.all([
        axios.get(`${api}/feedback/stats`).catch(() => ({ data: null })),
        axios.get(`${api}/feedback/training-profile`).catch(() => ({ data: null })),
        axios.get(`${api}/training/queue`).catch(() => ({ data: { items: [] } })),
        axios.get(`${api}/training/insights`).catch(() => ({ data: null })),
        axios.get(`${api}/training/activity-log`).catch(() => ({ data: null })),
      ]);
      setStats(statsR.data);
      setProfile(profileR.data);
      setQueue(queueR.data.items || []);
      setInsights(insightsR.data);
      setActivityLog(activityR.data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, [api]);

  // Poll training progress
  useEffect(() => {
    if (!training) return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await axios.get(`${api}/training/progress`);
        setProgress(res.data);
        if (!res.data.running && res.data.total > 0) {
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ===== LEFT: UPLOAD + QUEUE ===== */}
        <div className="space-y-4">
          {/* URL Input */}
          <Card className="border border-border rounded-none bg-card" data-testid="url-input-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Link size={16} className="text-primary" />
                Add Intelligence URL
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Paste news URL here..."
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addUrl()}
                  className="rounded-none flex-1"
                  data-testid="training-url-input"
                />
                <Button onClick={addUrl} disabled={addingUrl || !urlInput.trim()} className="rounded-none uppercase text-xs tracking-wider shrink-0" data-testid="add-url-btn">
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
          <Card className="border border-border rounded-none bg-card" data-testid="file-upload-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Upload size={16} className="text-emerald-400" />
                Upload Document
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div
                className="border-2 border-dashed border-border p-5 text-center cursor-pointer hover:border-muted-foreground transition-colors"
                onClick={() => document.getElementById("train-file-input").click()}
                data-testid="upload-dropzone"
              >
                <Upload size={20} className="mx-auto text-muted-foreground mb-1.5" />
                <p className="text-sm text-muted-foreground">{uploading ? "Uploading..." : "Click to browse or drop file"}</p>
                <p className="text-[10px] text-muted-foreground/50 font-mono mt-0.5">PDF, DOCX, TXT</p>
              </div>
              <input id="train-file-input" type="file" className="hidden" accept=".pdf,.docx,.doc,.txt"
                onChange={async (e) => { if (e.target.files?.[0]) await uploadFile(e.target.files[0]); e.target.value = ""; }}
              />
            </CardContent>
          </Card>

          {/* Train Button + Progress */}
          <Card className="border border-border rounded-none bg-card" data-testid="train-action-card">
            <CardContent className="p-4 space-y-3">
              <Button
                onClick={startTraining}
                disabled={training || pendingCount === 0}
                className="w-full rounded-none uppercase text-sm font-bold tracking-wider py-5"
                data-testid="train-btn"
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
              Training Queue ({queue.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {queue.length === 0 ? (
              <p className="text-sm text-muted-foreground p-4">No items in training queue. Add URLs or upload files above.</p>
            ) : (
              <div className="max-h-[420px] overflow-y-auto divide-y divide-border">
                {queue.map((item) => (
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

      {/* ===== TRAINING ACTIVITY LOG ===== */}
      <Card className="border border-border rounded-none bg-card" data-testid="activity-log-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Activity size={16} className="text-cyan-400" />
            Training Activity Log & Impact
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-5">
          {/* Impact Summary Row */}
          {activityLog?.summary && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {[
                { label: "Feedback Ratings", val: activityLog.summary.total_feedback_ratings, color: "text-primary" },
                { label: "Recent (7d)", val: activityLog.summary.recent_feedback_7d, color: "text-blue-400" },
                { label: "Items Trained", val: activityLog.summary.total_items_trained, color: "text-emerald-400" },
                { label: "Errors", val: activityLog.summary.training_errors, color: "text-red-400" },
                { label: "Relevance Tagged", val: activityLog.summary.items_with_relevance_tag, color: "text-amber-400" },
              ].map(({ label, val, color }) => (
                <div key={label} className="p-2 border border-border">
                  <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">{label}</p>
                  <p className={`text-lg font-bold font-['Barlow_Condensed'] ${color}`}>{val}</p>
                </div>
              ))}
            </div>
          )}

          {/* AI Impact */}
          {activityLog?.ai_impact?.total_successful > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Zap size={12} className="text-amber-400" />
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                  AI Impact — {activityLog.ai_impact.total_successful} items analyzed
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.keys(activityLog.ai_impact.regions_learned || {}).length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Regions Learned</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(activityLog.ai_impact.regions_learned).map(([r, c]) => (
                        <Badge key={r} variant="outline" className="rounded-none text-[9px] text-cyan-400 border-cyan-500/30 px-1.5 py-0">{r} ({c})</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {Object.keys(activityLog.ai_impact.actors_learned || {}).length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Actors Identified</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(activityLog.ai_impact.actors_learned).map(([a, c]) => (
                        <Badge key={a} variant="outline" className="rounded-none text-[9px] text-emerald-400 border-emerald-500/30 px-1.5 py-0">{a} ({c})</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {Object.keys(activityLog.ai_impact.keywords_learned || {}).length > 0 && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Keywords Extracted</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(activityLog.ai_impact.keywords_learned).map(([k, c]) => (
                        <Badge key={k} variant="outline" className="rounded-none text-[9px] text-amber-400 border-amber-500/30 px-1.5 py-0">{k} ({c})</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Activity Timeline */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Clock size={12} className="text-muted-foreground" />
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Recent Activity</span>
            </div>
            {activityLog?.entries?.length > 0 ? (
              <div className="max-h-[300px] overflow-y-auto divide-y divide-border border border-border">
                {activityLog.entries.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3 p-2.5 hover:bg-muted/5" data-testid={`activity-entry-${entry.id}`}>
                    <div className={`mt-0.5 shrink-0 ${
                      entry.type === "training_run" ? "text-purple-400" :
                      entry.type === "url_added" ? "text-blue-400" :
                      "text-emerald-400"
                    }`}>
                      {entry.type === "training_run" ? <Brain size={13} /> :
                       entry.type === "url_added" ? <Globe size={13} /> :
                       <FileText size={13} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs truncate">{entry.description}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {new Date(entry.timestamp).toLocaleString()}
                        </span>
                        <Badge variant="outline" className={`rounded-none text-[9px] px-1.5 py-0 uppercase ${
                          entry.type === "training_run" ? "text-purple-400 border-purple-500/30" :
                          entry.type === "url_added" ? "text-blue-400 border-blue-500/30" :
                          "text-emerald-400 border-emerald-500/30"
                        }`}>
                          {entry.type === "training_run" ? "Run" : entry.type === "url_added" ? "URL" : "File"}
                        </Badge>
                        {entry.relevance_tag && (
                          <Badge variant="outline" className="rounded-none text-[9px] px-1.5 py-0 text-primary border-primary/30">
                            REL: {entry.relevance_tag}/6
                          </Badge>
                        )}
                        {entry.type === "training_run" && entry.items_processed != null && (
                          <span className="text-[10px] font-mono text-muted-foreground">
                            {entry.items_processed} processed{entry.errors ? `, ${entry.errors} errors` : ""}
                          </span>
                        )}
                      </div>
                      {entry.type === "training_run" && entry.regions_found && Object.keys(entry.regions_found).length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {Object.entries(entry.regions_found).map(([r, c]) => (
                            <Badge key={r} variant="outline" className="rounded-none text-[8px] text-purple-400 border-purple-500/20 px-1 py-0">{r}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground border border-border p-3">
                No activity recorded yet. Add URLs, upload files, or run training to see activity here.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
