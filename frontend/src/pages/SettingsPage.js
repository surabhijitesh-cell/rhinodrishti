import { useState, useEffect } from "react";
import { Settings as SettingsIcon, Clock, Save, RefreshCw, ShieldCheck, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import axios from "axios";

const RETENTION_OPTIONS = [
  { value: "7", label: "7 days" },
  { value: "14", label: "14 days" },
  { value: "30", label: "30 days (default)" },
  { value: "60", label: "60 days" },
  { value: "90", label: "90 days" },
  { value: "180", label: "180 days" },
  { value: "365", label: "365 days" },
];

export default function SettingsPage({ api }) {
  const [retentionDays, setRetentionDays] = useState("30");
  const [saving, setSaving] = useState(false);
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

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await axios.put(`${api}/settings/retention`, {
        retention_days: parseInt(retentionDays, 10),
      });
      toast.success(res.data.message || "Retention window updated");
    } catch (e) {
      toast.error("Failed to update retention setting");
    }
    setSaving(false);
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

      {/* News Retention Window */}
      <Card className="border border-border rounded-none bg-card max-w-xl" data-testid="retention-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Clock size={16} className="text-primary" />
            News Retention Window
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            Set how many days of intelligence data to display on the Dashboard and Intelligence Feed.
            Older items remain in the database but won't appear in stats or listings.
          </p>

          <div className="flex items-center gap-4">
            <Select
              value={retentionDays}
              onValueChange={setRetentionDays}
              disabled={loading}
            >
              <SelectTrigger className="w-[200px] rounded-none" data-testid="retention-select">
                <SelectValue placeholder="Select retention" />
              </SelectTrigger>
              <SelectContent className="rounded-none">
                {RETENTION_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value} className="text-sm">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              onClick={handleSave}
              disabled={saving}
              className="uppercase text-xs font-bold tracking-wider rounded-none"
              data-testid="save-retention-btn"
            >
              {saving ? (
                <RefreshCw size={14} className="mr-2 animate-spin" />
              ) : (
                <Save size={14} className="mr-2" />
              )}
              Save
            </Button>
          </div>

          <div className="p-3 border border-border bg-muted/10">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Current Setting</p>
            <p className="text-lg font-bold font-['Barlow_Condensed']" data-testid="retention-current">
              {retentionDays} days
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Info */}
      <PipelineInfo api={api} />

      {/* Feedback Bias Configuration */}
      <BiasSettings api={api} />

      {/* Training Controls */}
      <FeedbackSettings api={api} />
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

  if (!status) return null;

  return (
    <Card className="border border-border rounded-none bg-card max-w-xl" data-testid="pipeline-info-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <SettingsIcon size={16} className="text-primary" />
          Pipeline Status
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
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
          <div className="col-span-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Scheduler</p>
            <p className="text-xs font-mono mt-1">{status.scheduler}</p>
          </div>
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
    <Card className="border border-border rounded-none bg-card max-w-xl" data-testid="feedback-settings-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <ShieldCheck size={16} className="text-primary" />
          Training Controls
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <p className="text-sm text-muted-foreground">
          Set the maximum number of feedback ratings allowed per intelligence item.
        </p>

        <div className="flex items-center gap-3">
          <Select value={maxFeedback} onValueChange={setMaxFeedback} disabled={loading}>
            <SelectTrigger className="w-[220px] rounded-none" data-testid="feedback-limit-select">
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

          <Button
            onClick={handleSave}
            disabled={saving}
            className="uppercase text-xs font-bold tracking-wider rounded-none"
            data-testid="save-feedback-limit-btn"
          >
            {saving ? <RefreshCw size={14} className="mr-2 animate-spin" /> : <Save size={14} className="mr-2" />}
            Save
          </Button>
        </div>

        <div className="p-3 border border-border bg-muted/10">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Current Limit</p>
          <p className="text-lg font-bold font-['Barlow_Condensed']" data-testid="feedback-limit-current">
            {maxFeedback} ratings per item
          </p>
        </div>
      </CardContent>
    </Card>
  );
}


const INFLUENCE_LABELS = {
  light: { label: "Light Influence", pct: "~10-15%", desc: "AI judgment dominates, feedback provides gentle nudges", color: "text-green-400" },
  moderate: { label: "Moderate Influence", pct: "~20-25%", desc: "Noticeable impact from analyst corrections", color: "text-amber-400" },
  high: { label: "High Influence", pct: "~35-40%", desc: "Analyst consensus strongly shapes classification", color: "text-red-400" },
};

const WINDOW_LABELS = {
  rolling_30: { label: "Rolling 30 Days", desc: "Most adaptive — recent analyst preferences dominate" },
  all_time: { label: "All Time", desc: "Cumulative learning — all historical feedback included" },
};


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
    <Card className="border border-border rounded-none bg-card max-w-xl border-l-4 border-l-primary" data-testid="bias-settings-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Zap size={16} className="text-primary" />
          Feedback Bias Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-5">
        <p className="text-sm text-muted-foreground">
          Control how analyst feedback influences the AI classification pipeline.
          These settings affect how incoming articles are scored and prioritized.
        </p>

        {/* Feedback Window */}
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-semibold">
            Feedback Window
          </p>
          <p className="text-xs text-muted-foreground">
            Choose whether the AI uses only recent feedback or the full history of analyst ratings.
          </p>
          <Select value={biasWindow} onValueChange={setBiasWindow} disabled={loading}>
            <SelectTrigger className="w-[280px] rounded-none" data-testid="bias-window-select">
              <SelectValue placeholder="Select window" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="rolling_30" className="text-sm">Rolling 30 Days (default)</SelectItem>
              <SelectItem value="all_time" className="text-sm">All Time (cumulative)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Influence Level */}
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-semibold">
            Influence Level
          </p>
          <p className="text-xs text-muted-foreground">
            How strongly should analyst feedback override the AI's independent judgment?
          </p>
          <Select value={biasInfluence} onValueChange={setBiasInfluence} disabled={loading}>
            <SelectTrigger className="w-[280px] rounded-none" data-testid="bias-influence-select">
              <SelectValue placeholder="Select influence" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="light" className="text-sm">Light (~10-15% weight)</SelectItem>
              <SelectItem value="moderate" className="text-sm">Moderate (~20-25% weight)</SelectItem>
              <SelectItem value="high" className="text-sm">High (~35-40% weight)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button
          onClick={handleSave}
          disabled={saving}
          className="uppercase text-xs font-bold tracking-wider rounded-none"
          data-testid="save-bias-settings-btn"
        >
          {saving ? <RefreshCw size={14} className="mr-2 animate-spin" /> : <Save size={14} className="mr-2" />}
          Save Bias Settings
        </Button>

        {/* Current Config Summary */}
        <div className="p-3 border border-border bg-muted/10 space-y-2">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Active Configuration</p>
          <div className="flex items-center gap-3">
            <div>
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Window</p>
              <p className="text-sm font-bold font-['Barlow_Condensed']" data-testid="bias-window-current">
                {currentWindow.label}
              </p>
              <p className="text-[10px] text-muted-foreground">{currentWindow.desc}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div>
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono">Influence</p>
              <p className={`text-sm font-bold font-['Barlow_Condensed'] ${currentInfluence.color}`} data-testid="bias-influence-current">
                {currentInfluence.label}
                <Badge variant="outline" className={`ml-2 rounded-none text-[9px] px-1.5 py-0 ${currentInfluence.color}`}>
                  {currentInfluence.pct}
                </Badge>
              </p>
              <p className="text-[10px] text-muted-foreground">{currentInfluence.desc}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
