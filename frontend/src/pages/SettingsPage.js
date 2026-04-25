import { useState, useEffect, useCallback } from "react";
import { Navigate } from "react-router-dom";
import {
  Settings as SettingsIcon, Clock, Save, RefreshCw, ShieldCheck, Zap,
  TrendingUp, TrendingDown, Minus, BarChart3, Loader2, Rss, Plus, Trash2, Globe
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
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

const INFLUENCE_LABELS = {
  light: { label: "Light Influence", pct: "~10-15%", desc: "AI judgment dominates, feedback provides gentle nudges", color: "text-green-400" },
  moderate: { label: "Moderate Influence", pct: "~20-25%", desc: "Noticeable impact from analyst corrections", color: "text-amber-400" },
  high: { label: "High Influence", pct: "~35-40%", desc: "Analyst consensus strongly shapes classification", color: "text-red-400" },
};

const WINDOW_LABELS = {
  rolling_30: { label: "Rolling 30 Days", desc: "Recent analyst preferences dominate" },
  all_time: { label: "All Time", desc: "Full historical feedback included" },
};

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

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get(`${api}/settings/retention`);
        setRetentionDays(String(res.data.retention_days || 30));
      } catch (e) {
        console.error("Failed to fetch retention setting:", e);
      }
      setLoading(false);
    };
    fetch();
  }, [api]);

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
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="settings-title">
          Platform Settings
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Configure intelligence platform parameters
        </p>
      </div>

      {/* RSS Feed Management — Full width */}
      <RssFeedManager api={api} />

      {/* Row 1: Retention + Pipeline side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* News Retention Window */}
        <Card className="border border-border rounded-none bg-card" data-testid="retention-card">
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
              <Button onClick={handleSaveRetention} disabled={savingRetention} className="uppercase text-xs font-bold tracking-wider rounded-none" data-testid="save-retention-btn">
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

        {/* Pipeline Info */}
        <PipelineInfo api={api} />
      </div>

      {/* Row 2: Bias Config + Training Controls side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BiasSettings api={api} />
        <FeedbackSettings api={api} />
      </div>

      {/* Row 3: Full-width Bias Impact Report */}
      <BiasImpactReport api={api} />
    </div>
  );
}


function PipelineInfo({ api }) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get(`${api}/pipeline/status`);
        setStatus(res.data);
      } catch (e) { /* silent */ }
    };
    fetch();
  }, [api]);

  if (!status) {
    return (
      <Card className="border border-border rounded-none bg-card" data-testid="pipeline-info-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <SettingsIcon size={16} className="text-primary" />
            Pipeline Status
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="h-24 flex items-center justify-center">
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border border-border rounded-none bg-card" data-testid="pipeline-info-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <SettingsIcon size={16} className="text-primary" />
          Pipeline Status
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Total Items</p>
            <p className="font-bold font-['Barlow_Condensed'] text-lg">{status.total_items}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">AI Processed</p>
            <p className="font-bold font-['Barlow_Condensed'] text-lg">{status.ai_processed}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Processing Rate</p>
            <p className="font-bold font-['Barlow_Condensed'] text-lg">{status.processing_rate}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">RSS Sources</p>
            <p className="font-bold font-['Barlow_Condensed'] text-lg">{status.rss_sources}</p>
          </div>
        </div>
        <div className="mt-3 pt-2 border-t border-border">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Scheduler</p>
          <p className="text-[10px] font-mono mt-0.5 text-muted-foreground">{status.scheduler}</p>
        </div>
      </CardContent>
    </Card>
  );
}


function FeedbackSettings({ api }) {
  const [maxFeedback, setMaxFeedback] = useState("20");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await axios.get(`${api}/settings/feedback`);
        setMaxFeedback(String(res.data.max_feedback_per_item || 20));
      } catch (e) {
        console.error("Failed to fetch feedback settings:", e);
      }
      setLoading(false);
    };
    fetchSettings();
  }, [api]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await axios.put(`${api}/settings/feedback`, {
        max_feedback_per_item: parseInt(maxFeedback, 10),
      });
      toast.success(res.data.message || "Feedback limit updated");
    } catch (e) {
      toast.error("Failed to update feedback setting");
    }
    setSaving(false);
  };

  return (
    <Card className="border border-border rounded-none bg-card" data-testid="feedback-settings-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <ShieldCheck size={16} className="text-primary" />
          Training Controls
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-3">
        <p className="text-xs text-muted-foreground">
          Maximum number of feedback ratings allowed per intelligence item.
        </p>
        <div className="flex items-center gap-3">
          <Select value={maxFeedback} onValueChange={setMaxFeedback} disabled={loading}>
            <SelectTrigger className="w-[200px] rounded-none" data-testid="feedback-limit-select">
              <SelectValue placeholder="Select limit" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="5">5 ratings</SelectItem>
              <SelectItem value="10">10 ratings</SelectItem>
              <SelectItem value="15">15 ratings</SelectItem>
              <SelectItem value="20">20 ratings (default)</SelectItem>
              <SelectItem value="30">30 ratings</SelectItem>
              <SelectItem value="50">50 ratings</SelectItem>
              <SelectItem value="100">100 ratings</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSave} disabled={saving} className="uppercase text-xs font-bold tracking-wider rounded-none" data-testid="save-feedback-limit-btn">
            {saving ? <RefreshCw size={14} className="mr-1.5 animate-spin" /> : <Save size={14} className="mr-1.5" />}
            Save
          </Button>
        </div>
        <div className="p-2.5 border border-border bg-muted/10">
          <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Current: </span>
          <span className="text-base font-bold font-['Barlow_Condensed']" data-testid="feedback-limit-current">{maxFeedback} ratings/item</span>
        </div>
      </CardContent>
    </Card>
  );
}


function BiasSettings({ api }) {
  const [biasWindow, setBiasWindow] = useState("rolling_30");
  const [biasInfluence, setBiasInfluence] = useState("moderate");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await axios.get(`${api}/settings/bias`);
        setBiasWindow(res.data.bias_window || "rolling_30");
        setBiasInfluence(res.data.bias_influence || "moderate");
      } catch (e) {
        console.error("Failed to fetch bias settings:", e);
      }
      setLoading(false);
    };
    fetchSettings();
  }, [api]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await axios.put(`${api}/settings/bias`, {
        bias_window: biasWindow,
        bias_influence: biasInfluence,
      });
      toast.success(res.data.message || "Bias settings updated");
    } catch (e) {
      toast.error("Failed to update bias settings");
    }
    setSaving(false);
  };

  const currentInfluence = INFLUENCE_LABELS[biasInfluence] || INFLUENCE_LABELS.moderate;
  const currentWindow = WINDOW_LABELS[biasWindow] || WINDOW_LABELS.rolling_30;

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-primary" data-testid="bias-settings-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Zap size={16} className="text-primary" />
          Feedback Bias Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <p className="text-xs text-muted-foreground">
          Control how analyst feedback influences the AI classification pipeline.
        </p>

        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-semibold">Feedback Window</p>
          <Select value={biasWindow} onValueChange={setBiasWindow} disabled={loading}>
            <SelectTrigger className="w-full rounded-none" data-testid="bias-window-select">
              <SelectValue placeholder="Select window" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="rolling_30" className="text-sm">Rolling 30 Days (default)</SelectItem>
              <SelectItem value="all_time" className="text-sm">All Time (cumulative)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-semibold">Influence Level</p>
          <Select value={biasInfluence} onValueChange={setBiasInfluence} disabled={loading}>
            <SelectTrigger className="w-full rounded-none" data-testid="bias-influence-select">
              <SelectValue placeholder="Select influence" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="light" className="text-sm">Light (~10-15% weight)</SelectItem>
              <SelectItem value="moderate" className="text-sm">Moderate (~20-25% weight)</SelectItem>
              <SelectItem value="high" className="text-sm">High (~35-40% weight)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button onClick={handleSave} disabled={saving} className="w-full uppercase text-xs font-bold tracking-wider rounded-none" data-testid="save-bias-settings-btn">
          {saving ? <RefreshCw size={14} className="mr-1.5 animate-spin" /> : <Save size={14} className="mr-1.5" />}
          Save Bias Settings
        </Button>

        <div className="p-2.5 border border-border bg-muted/10 grid grid-cols-2 gap-2">
          <div>
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Window</p>
            <p className="text-sm font-bold font-['Barlow_Condensed']" data-testid="bias-window-current">{currentWindow.label}</p>
            <p className="text-[9px] text-muted-foreground">{currentWindow.desc}</p>
          </div>
          <div>
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Influence</p>
            <p className={`text-sm font-bold font-['Barlow_Condensed'] ${currentInfluence.color}`} data-testid="bias-influence-current">{currentInfluence.label}</p>
            <Badge variant="outline" className={`rounded-none text-[9px] px-1.5 py-0 ${currentInfluence.color}`}>{currentInfluence.pct}</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}


function BiasImpactReport({ api }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await axios.get(`${api}/feedback/bias-impact`);
        setReport(res.data);
      } catch (e) {
        console.error("Failed to fetch bias impact:", e);
      }
      setLoading(false);
    };
    fetchReport();
  }, [api]);

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/feedback/bias-impact`);
      setReport(res.data);
    } catch (e) {
      console.error("Refresh failed:", e);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <Card className="border border-border rounded-none bg-card" data-testid="bias-impact-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <BarChart3 size={16} className="text-cyan-400" />
            Bias Impact Report
          </CardTitle>
        </CardHeader>
        <CardContent className="p-8 flex items-center justify-center">
          <Loader2 size={20} className="animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!report || report.status === "no_data") {
    return (
      <Card className="border border-border rounded-none bg-card" data-testid="bias-impact-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <BarChart3 size={16} className="text-cyan-400" />
            Bias Impact Report
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6 text-center">
          <p className="text-sm text-muted-foreground">
            {report?.message || "Rate articles on the Intelligence Feed to generate impact data."}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { summary, items, influence, influence_label } = report;

  return (
    <Card className="border border-border rounded-none bg-card" data-testid="bias-impact-card">
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <BarChart3 size={16} className="text-cyan-400" />
          Bias Impact Report
          <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-cyan-500/20 text-cyan-400 border-cyan-500/30 ml-1">
            {report.total_items_analyzed} items
          </Badge>
        </CardTitle>
        <Button variant="outline" size="sm" className="rounded-none text-[10px] h-6 px-2 uppercase" onClick={refresh} data-testid="refresh-impact-btn">
          <RefreshCw size={11} className="mr-1" /> Refresh
        </Button>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Summary stats row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="p-2.5 border border-border">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Influence</p>
            <p className={`text-base font-bold font-['Barlow_Condensed'] capitalize ${
              influence === "light" ? "text-green-400" : influence === "high" ? "text-red-400" : "text-amber-400"
            }`} data-testid="impact-influence">{influence}</p>
            <p className="text-[9px] text-muted-foreground font-mono">{influence_label}</p>
          </div>
          <div className="p-2.5 border border-border">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Boosted</p>
            <p className="text-base font-bold font-['Barlow_Condensed'] text-emerald-400" data-testid="impact-boosted">{summary.boosted}</p>
          </div>
          <div className="p-2.5 border border-border">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Reduced</p>
            <p className="text-base font-bold font-['Barlow_Condensed'] text-red-400" data-testid="impact-reduced">{summary.reduced}</p>
          </div>
          <div className="p-2.5 border border-border">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Unchanged</p>
            <p className="text-base font-bold font-['Barlow_Condensed']" data-testid="impact-unchanged">{summary.unchanged}</p>
          </div>
          <div className="p-2.5 border border-border">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Avg Delta</p>
            <p className="text-base font-bold font-['Barlow_Condensed'] text-cyan-400" data-testid="impact-avg-delta">{summary.avg_absolute_delta} pts</p>
          </div>
        </div>

        {/* Impact items table */}
        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="impact-items-table">
              <thead>
                <tr className="border-b border-border bg-muted/10">
                  <th className="text-left p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground">Article</th>
                  <th className="text-left p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-20">Region</th>
                  <th className="text-center p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-16">Original</th>
                  <th className="text-center p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-16">Biased</th>
                  <th className="text-center p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-16">Delta</th>
                  <th className="text-center p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground w-16">Rating</th>
                  <th className="text-left p-2 text-[9px] uppercase tracking-wider font-mono text-muted-foreground">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/5" data-testid={`impact-row-${item.id}`}>
                    <td className="p-2 max-w-[280px]">
                      <p className="truncate text-xs font-medium">{item.title}</p>
                      <p className="text-[9px] text-muted-foreground font-mono">{item.threat_category}</p>
                    </td>
                    <td className="p-2 text-[10px] font-mono text-muted-foreground">{item.region}</td>
                    <td className="p-2 text-center font-mono font-semibold">{item.original_score}</td>
                    <td className={`p-2 text-center font-mono font-semibold ${
                      item.delta > 0 ? "text-emerald-400" : item.delta < 0 ? "text-red-400" : ""
                    }`}>{item.biased_score}</td>
                    <td className="p-2 text-center">
                      {item.delta !== 0 ? (
                        <span className={`inline-flex items-center gap-0.5 font-mono font-bold text-[10px] ${
                          item.delta > 0 ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {item.delta > 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                          {item.delta > 0 ? "+" : ""}{item.delta}
                        </span>
                      ) : (
                        <Minus size={10} className="mx-auto text-muted-foreground" />
                      )}
                    </td>
                    <td className="p-2 text-center">
                      <span className="font-mono text-[10px] text-amber-400">{item.analyst_avg_rating}</span>
                      <span className="text-[8px] text-muted-foreground ml-0.5">({item.rating_count})</span>
                    </td>
                    <td className="p-2 text-[10px] text-muted-foreground max-w-[200px]">
                      {item.reasons.length > 0 ? item.reasons.join("; ") : "No bias match"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-emerald-500" data-testid="rss-feed-manager">
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
