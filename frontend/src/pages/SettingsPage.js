import { useState, useEffect } from "react";
import { Navigate } from "react-router-dom";
import {
  Settings as SettingsIcon, Clock, Save, RefreshCw, ShieldCheck, Zap,
  TrendingUp, TrendingDown, Minus, BarChart3, Loader2
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
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
