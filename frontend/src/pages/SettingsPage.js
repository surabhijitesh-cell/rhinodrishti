import { useState, useEffect } from "react";
import { Settings as SettingsIcon, Clock, Save, RefreshCw, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
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
    const fetch = async () => {
      try {
        const res = await axios.get(`${api}/settings/feedback`);
        setMaxFeedback(String(res.data.max_feedback_per_item || 20));
      } catch (e) {
        console.error("Failed to fetch feedback settings:", e);
      }
      setLoading(false);
    };
    fetch();
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

  const options = [
    { value: "5", label: "5 ratings" },
    { value: "10", label: "10 ratings" },
    { value: "15", label: "15 ratings" },
    { value: "20", label: "20 ratings (default)" },
    { value: "30", label: "30 ratings" },
    { value: "50", label: "50 ratings" },
    { value: "100", label: "100 ratings" },
  ];

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
          This prevents over-sampling and ensures controlled data collection.
        </p>

        <div className="flex items-center gap-4">
          <label className="text-xs text-muted-foreground font-mono uppercase shrink-0">Max Ratings</label>
          <select
            value={maxFeedback}
            onChange={(e) => setMaxFeedback(e.target.value)}
            disabled={loading}
            className="h-9 w-[200px] border border-border bg-background text-foreground px-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            data-testid="feedback-limit-select"
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <Button
            onClick={handleSave}
            disabled={saving}
            className="uppercase text-xs font-bold tracking-wider rounded-none"
            data-testid="save-feedback-limit-btn"
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
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-1">Current Limit</p>
          <p className="text-lg font-bold font-['Barlow_Condensed']" data-testid="feedback-limit-current">
            {maxFeedback} ratings per item
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
