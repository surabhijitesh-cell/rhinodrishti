import { useState, useEffect, useCallback } from "react";
import { Navigate } from "react-router-dom";
import {
  Settings as SettingsIcon, Clock, Save, RefreshCw, ShieldCheck, Zap,
  TrendingUp, TrendingDown, Minus, BarChart3, Loader2, Rss, Plus, Trash2, Globe,
  Youtube, Facebook, MessageCircle, Twitter, Activity, ExternalLink, Radio,
  Database, HardDrive, Wifi, WifiOff, Download, CheckCircle2, AlertTriangle,
  Server, ArrowRight, Copy,
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
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="settings-title" data-tour="settings-title">
          Platform Settings
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Configure intelligence platform parameters
        </p>
      </div>

      {/* Local Database Setup — Full width, top priority */}
      <LocalDatabaseCard api={api} />

      {/* RSS Feed Management — Full width */}
      <RssFeedManager api={api} />

      {/* Social Media Scan Configuration — Full width */}
      <SocialScanManager api={api} />

      {/* Row 1: Retention + Pipeline side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* News Retention Window */}
        <Card className="border border-border rounded-none bg-card" data-testid="retention-card" data-tour="retention-card">
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

      {/* Row 3: Source Effectiveness */}
      <SourceEffectivenessCard api={api} />

      {/* Row 4: Full-width Bias Impact Report */}
      <BiasImpactReport api={api} />
    </div>
  );
}


// ─── Local Database Card ──────────────────────────────────────────────────────

const STEPS = [
  { n: 1, title: "Download Installer",      desc: "Click the button below to get the PowerShell wizard" },
  { n: 2, title: "Run as Administrator",    desc: 'Right-click setup-wizard.ps1 → "Run with PowerShell" (Admin)' },
  { n: 3, title: "Follow the wizard",       desc: "Installs MongoDB 7.0 + Tailscale VPN automatically (~20 min)" },
  { n: 4, title: "Create Tailscale key",    desc: "Free at tailscale.com/admin/settings/keys (reusable + ephemeral)" },
  { n: 5, title: "Update Render settings",  desc: "Paste MONGO_URL + TAILSCALE_AUTH_KEY + new Start Command" },
  { n: 6, title: "Redeploy on Render",      desc: "Click Manual Deploy — your backend now connects to local DB" },
];

const RENDER_START_CMD =
  `curl -fsSL https://tailscale.com/install.sh | sh && tailscale up --authkey=$TAILSCALE_AUTH_KEY --hostname=render-rhinodrishti-api --ephemeral && sleep 6 && uvicorn server:app --host 0.0.0.0 --port $PORT`;

function CopyButton({ text, label = "Copy" }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 border border-border hover:border-primary hover:text-primary transition-colors"
    >
      {copied ? <CheckCircle2 size={10} className="text-emerald-400" /> : <Copy size={10} />}
      {copied ? "Copied!" : label}
    </button>
  );
}

function LocalDatabaseCard({ api }) {
  const [status, setStatus]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [showSteps, setShowSteps] = useState(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/settings/local-db-status`);
      setStatus(res.data);
    } catch (e) {
      console.error("local-db-status failed", e);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const isLocal = status?.mode !== "atlas";

  const downloadScript = () => {
    window.open(
      "https://raw.githubusercontent.com/surabhijitesh-cell/rhinodrishti/feature/social-media-integration/local-setup/setup-wizard.ps1",
      "_blank"
    );
  };

  return (
    <Card className={`border border-border rounded-none bg-card border-l-4 ${isLocal ? "border-l-emerald-500" : "border-l-amber-500"}`} data-tour="local-db-card">
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <HardDrive size={16} className={isLocal ? "text-emerald-400" : "text-amber-400"} />
          Database Storage
          <Badge className={`rounded-none text-[9px] px-1.5 py-0 ml-1 ${
            isLocal
              ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
              : "bg-amber-500/20 text-amber-400 border-amber-500/30"
          }`}>
            {loading ? "checking..." : isLocal ? "LOCAL DISK" : "ATLAS CLOUD"}
          </Badge>
        </CardTitle>
        <Button variant="outline" size="sm" className="rounded-none text-[10px] h-6 px-2 uppercase" onClick={fetchStatus}>
          <RefreshCw size={11} className="mr-1" /> Refresh
        </Button>
      </CardHeader>

      <CardContent className="p-4 space-y-4">

        {/* Architecture diagram */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Current status */}
          <div className="space-y-3">
            <p className="text-[10px] uppercase tracking-widest font-mono font-semibold text-muted-foreground">Current Mode</p>

            {loading ? (
              <div className="flex items-center gap-2"><Loader2 size={14} className="animate-spin text-muted-foreground" /><span className="text-xs text-muted-foreground">Checking...</span></div>
            ) : (
              <div className={`p-3 border ${isLocal ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"}`}>
                <div className="flex items-center gap-2 mb-2">
                  {isLocal
                    ? <Wifi size={14} className="text-emerald-400" />
                    : <WifiOff size={14} className="text-amber-400" />}
                  <span className={`text-xs font-bold font-['Barlow_Condensed'] uppercase ${isLocal ? "text-emerald-400" : "text-amber-400"}`}>
                    {isLocal ? "Local MongoDB via Tailscale VPN" : "MongoDB Atlas (Cloud)"}
                  </span>
                </div>
                <p className="text-[10px] font-mono text-muted-foreground truncate">{status?.mongo_url_hint}</p>
                {status?.data_size_mb != null && (
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <div>
                      <p className="text-[8px] uppercase font-mono text-muted-foreground">Data Size</p>
                      <p className="text-sm font-bold font-['Barlow_Condensed']">{status.data_size_mb} MB</p>
                    </div>
                    <div>
                      <p className="text-[8px] uppercase font-mono text-muted-foreground">On Disk</p>
                      <p className="text-sm font-bold font-['Barlow_Condensed']">{status.storage_mb} MB</p>
                    </div>
                    <div>
                      <p className="text-[8px] uppercase font-mono text-muted-foreground">Collections</p>
                      <p className="text-sm font-bold font-['Barlow_Condensed']">{status.collections}</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Migration log */}
            {status?.migration_log?.length > 0 && (
              <div>
                <p className="text-[9px] uppercase tracking-widest font-mono font-semibold text-muted-foreground mb-1">Migration History</p>
                {status.migration_log.map((entry, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground py-0.5 border-b border-border/50">
                    <CheckCircle2 size={10} className="text-emerald-400 shrink-0" />
                    <span>{new Date(entry.migrated_at).toLocaleDateString()}</span>
                    <span>·</span>
                    <span>{entry.docs_copied?.toLocaleString()} docs</span>
                    <span>·</span>
                    <span>{entry.duration_s}s</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Architecture diagram */}
          <div className="space-y-3">
            <p className="text-[10px] uppercase tracking-widest font-mono font-semibold text-muted-foreground">Architecture</p>
            <div className="p-3 border border-border bg-muted/5 font-mono text-[10px] text-muted-foreground space-y-1 leading-5">
              <div className="flex items-center gap-2">
                <Globe size={10} className="text-blue-400 shrink-0" />
                <span className="text-blue-400">Remote Users</span>
              </div>
              <div className="pl-4 text-muted-foreground/50">│ HTTPS</div>
              <div className="flex items-center gap-2">
                <Server size={10} className="text-violet-400 shrink-0" />
                <span className="text-violet-400">Vercel</span>
                <span className="text-muted-foreground/40">(React frontend)</span>
              </div>
              <div className="pl-4 text-muted-foreground/50">│ API calls</div>
              <div className="flex items-center gap-2">
                <Server size={10} className="text-cyan-400 shrink-0" />
                <span className="text-cyan-400">Render</span>
                <span className="text-muted-foreground/40">(FastAPI backend)</span>
              </div>
              <div className="pl-4 text-muted-foreground/50">│ Tailscale WireGuard VPN</div>
              <div className="flex items-center gap-2">
                <HardDrive size={10} className="text-emerald-400 shrink-0" />
                <span className="text-emerald-400">Windows 11 PC</span>
                <span className="text-muted-foreground/40">(your collection centre)</span>
              </div>
              <div className="pl-6 text-muted-foreground/50">├── Tailscale daemon</div>
              <div className="pl-6 text-emerald-400">└── MongoDB 7.0 (1TB local disk)</div>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Tailscale creates an encrypted WireGuard tunnel — no port forwarding, no static IP needed.
              Data never leaves your PC. Remote users see the same app via Vercel + Render.
            </p>
          </div>
        </div>

        {/* Setup button + steps */}
        {!isLocal && (
          <div className="border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-amber-400">Currently using MongoDB Atlas (cloud)</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Run the installer wizard on your Windows 11 collection centre PC to shift storage to local disk.
                </p>
              </div>
            </div>

            <div className="flex gap-2 flex-wrap">
              <Button
                onClick={downloadScript}
                className="rounded-none text-xs uppercase tracking-wider bg-amber-500 hover:bg-amber-600 text-black font-bold"
              >
                <Download size={13} className="mr-1.5" />
                Download Setup Wizard (.ps1)
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowSteps(s => !s)}
                className="rounded-none text-xs uppercase tracking-wider"
              >
                {showSteps ? "Hide Steps" : "View Setup Steps"}
              </Button>
            </div>

            {showSteps && (
              <div className="space-y-2 pt-1">
                {STEPS.map(step => (
                  <div key={step.n} className="flex items-start gap-3">
                    <div className="w-5 h-5 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-[9px] font-bold text-amber-400">{step.n}</span>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold">{step.title}</p>
                      <p className="text-[10px] text-muted-foreground">{step.desc}</p>
                    </div>
                  </div>
                ))}

                {/* Render start command */}
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-[9px] uppercase tracking-widest font-mono font-semibold text-muted-foreground mb-1">
                    Render Start Command (from Step 5)
                  </p>
                  <div className="flex items-start gap-2">
                    <code className="text-[9px] font-mono bg-muted/20 border border-border p-2 flex-1 break-all leading-4">
                      {RENDER_START_CMD}
                    </code>
                    <CopyButton text={RENDER_START_CMD} label="Copy" />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {isLocal && (
          <div className="border border-emerald-500/20 bg-emerald-500/5 p-3 flex items-center gap-3">
            <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-emerald-400">Local database active</p>
              <p className="text-[10px] text-muted-foreground">
                Your intelligence data is stored on local disk and routed via Tailscale VPN. Keep this PC powered on.
              </p>
            </div>
          </div>
        )}

      </CardContent>
    </Card>
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
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-primary" data-testid="bias-settings-card" data-tour="bias-card">
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


// ─── Source Effectiveness Card ────────────────────────────────────────────────

const SOURCE_META = {
  youtube:   { label: "YouTube",   Icon: Youtube,       accent: "text-red-400",     border: "border-l-red-500",     bg: "bg-red-500/10",   dot: "bg-red-400"   },
  facebook:  { label: "Facebook",  Icon: Facebook,      accent: "text-blue-400",    border: "border-l-blue-500",    bg: "bg-blue-500/10",  dot: "bg-blue-400"  },
  telegram:  { label: "Telegram",  Icon: Radio,         accent: "text-sky-400",     border: "border-l-sky-500",     bg: "bg-sky-500/10",   dot: "bg-sky-400"   },
  twitter:   { label: "X/Twitter", Icon: Twitter,       accent: "text-slate-300",   border: "border-l-slate-400",   bg: "bg-slate-500/10", dot: "bg-slate-300" },
  firecrawl: { label: "Firecrawl", Icon: Activity,      accent: "text-orange-400",  border: "border-l-orange-500",  bg: "bg-orange-500/10",dot: "bg-orange-400"},
};

const SEV_COLOR = {
  critical: "bg-red-500",
  high:     "bg-orange-500",
  medium:   "bg-yellow-500",
  low:      "bg-emerald-500",
};

function timeAgoShort(iso) {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function SevBar({ severity }) {
  const total = (severity.critical + severity.high + severity.medium + severity.low) || 1;
  const segs = ["critical", "high", "medium", "low"];
  return (
    <div className="flex h-1.5 w-full rounded-full overflow-hidden gap-px">
      {segs.map(s => severity[s] > 0 && (
        <div
          key={s}
          title={`${s}: ${severity[s]}`}
          className={`${SEV_COLOR[s]} transition-all`}
          style={{ width: `${(severity[s] / total) * 100}%` }}
        />
      ))}
      {total === 1 && <div className="bg-muted/30 flex-1 rounded-full" />}
    </div>
  );
}

function SourceEffectivenessCard({ api }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null); // source_type of expanded row

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/intelligence/source-stats`);
      setData(res.data);
    } catch (e) {
      console.error("source-stats fetch failed", e);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <BarChart3 size={16} className="text-violet-400" /> Source Effectiveness
        </CardTitle>
      </CardHeader>
      <CardContent className="p-8 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-muted-foreground" />
      </CardContent>
    </Card>
  );

  const { sources = [], recent_catches = [], retention_days = 30 } = data || {};
  const totalNonRss = sources.reduce((s, x) => s + x.total, 0);

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500" data-tour="source-effectiveness">
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <BarChart3 size={16} className="text-violet-400" />
          Source Effectiveness
          <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-violet-500/20 text-violet-400 border-violet-500/30 ml-1">
            {totalNonRss} items · last {retention_days}d
          </Badge>
        </CardTitle>
        <Button variant="outline" size="sm" className="rounded-none text-[10px] h-6 px-2 uppercase" onClick={fetchData}>
          <RefreshCw size={11} className="mr-1" /> Refresh
        </Button>
      </CardHeader>

      <CardContent className="p-4 space-y-4">
        <p className="text-xs text-muted-foreground">
          Intelligence items collected from non-RSS sources in the last {retention_days} days.
          Click a row to preview the latest catch from that source.
        </p>

        {/* Per-source rows */}
        <div className="divide-y divide-border border border-border">
          {sources.map(src => {
            const meta = SOURCE_META[src.source_type] || { label: src.source_type, Icon: Globe, accent: "text-muted-foreground", border: "", bg: "bg-muted/10", dot: "bg-muted-foreground" };
            const { Icon } = meta;
            const total          = src.raw_fetched ?? src.total;
            const pipelineIn     = src.total;          // entered intelligence_items
            const accepted       = src.accepted ?? 0;
            const rejected       = src.rejected ?? 0;
            const pctAccepted    = pipelineIn > 0 ? Math.round((accepted / pipelineIn) * 100) : 0;
            const pctRejected    = pipelineIn > 0 ? Math.round((rejected / pipelineIn) * 100) : 0;
            const isOpen         = expanded === src.source_type;
            const highValue      = src.severity.critical + src.severity.high;

            return (
              <div key={src.source_type}>
                <button
                  onClick={() => setExpanded(isOpen ? null : src.source_type)}
                  className={`w-full text-left p-3 hover:bg-muted/5 transition-colors flex items-center gap-3 ${isOpen ? "bg-muted/5" : ""}`}
                >
                  {/* Icon + label */}
                  <div className={`w-7 h-7 rounded flex items-center justify-center shrink-0 ${meta.bg}`}>
                    <Icon size={14} className={meta.accent} />
                  </div>
                  <div className="w-24 shrink-0">
                    <p className={`text-xs font-bold font-['Barlow_Condensed'] uppercase tracking-wide ${meta.accent}`}>{meta.label}</p>
                    <p className="text-[9px] font-mono text-muted-foreground">{timeAgoShort(src.latest_at)}</p>
                  </div>

                  {/* Pipeline flow: Fetched → Pipeline → ✓ Accepted / ✗ Rejected */}
                  <div className="flex-1 min-w-0">
                    {total === 0 ? (
                      <p className="text-[9px] font-mono text-muted-foreground">no data yet</p>
                    ) : (
                      <>
                        {/* Arrow pipeline diagram */}
                        <div className="flex items-center gap-1 text-[9px] font-mono flex-wrap">
                          <span className="text-muted-foreground font-semibold">{total} fetched</span>
                          <span className="text-muted-foreground/40">→</span>
                          <span className="text-blue-400">{pipelineIn} AI pipeline</span>
                          <span className="text-muted-foreground/40">→</span>
                          <span className="text-emerald-400">{accepted} ✓</span>
                          <span className="text-muted-foreground/30 mx-0.5">|</span>
                          <span className="text-red-400/70">{rejected} ✗</span>
                        </div>
                        {/* Severity bar */}
                        <div className="mt-1">
                          <SevBar severity={src.severity} />
                        </div>
                        <div className="flex gap-2 text-[8px] font-mono mt-0.5">
                          {src.severity.critical > 0 && <span className="text-red-400">{src.severity.critical} crit</span>}
                          {src.severity.high > 0     && <span className="text-orange-400">{src.severity.high} high</span>}
                          {src.severity.medium > 0   && <span className="text-yellow-400">{src.severity.medium} med</span>}
                          {src.severity.low > 0      && <span className="text-emerald-400">{src.severity.low} low</span>}
                        </div>
                      </>
                    )}
                  </div>

                  {/* Accept % */}
                  <div className="w-20 shrink-0 text-right">
                    <p className={`text-sm font-bold font-['Barlow_Condensed'] ${pctAccepted >= 30 ? "text-emerald-400" : pipelineIn === 0 ? "text-muted-foreground" : "text-amber-400"}`}>
                      {pipelineIn === 0 ? "—" : `${pctAccepted}%`}
                    </p>
                    <p className="text-[8px] font-mono text-muted-foreground">accepted</p>
                    {rejected > 0 && (
                      <p className="text-[8px] font-mono text-red-400/70">{pctRejected}% rej.</p>
                    )}
                  </div>

                  {/* High-value badge */}
                  <div className="w-16 shrink-0 text-center">
                    {highValue > 0 ? (
                      <Badge className="rounded-none text-[8px] px-1 py-0 bg-red-500/15 text-red-400 border-red-500/30">
                        {highValue} ⚠
                      </Badge>
                    ) : (
                      <span className="text-[9px] font-mono text-muted-foreground/40">—</span>
                    )}
                  </div>

                  {/* Expand caret */}
                  <span className="text-muted-foreground/50 text-xs">{isOpen ? "▲" : "▼"}</span>
                </button>

                {/* Expanded: pipeline detail + latest catch */}
                {isOpen && (
                  <div className={`px-4 pb-3 pt-2 ${meta.bg} border-t border-border space-y-2`}>
                    {/* Pipeline breakdown */}
                    {pipelineIn > 0 && (
                      <div>
                        <p className="text-[9px] uppercase tracking-widest font-mono text-muted-foreground font-semibold mb-1">AI Pipeline Breakdown</p>
                        <div className="grid grid-cols-4 gap-2 text-center">
                          {[
                            { label: "Fetched",  val: total,      color: "text-foreground" },
                            { label: "→ AI In",  val: pipelineIn, color: "text-blue-400" },
                            { label: "✓ Accept", val: accepted,   color: "text-emerald-400" },
                            { label: "✗ Reject", val: rejected,   color: "text-red-400/70" },
                          ].map(({ label, val, color }) => (
                            <div key={label} className="bg-black/20 p-1.5 rounded-none border border-border/50">
                              <p className={`text-base font-bold font-['Barlow_Condensed'] ${color}`}>{val}</p>
                              <p className="text-[8px] font-mono text-muted-foreground uppercase">{label}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Latest catch */}
                    {src.latest_title ? (
                      <div className="space-y-0.5">
                        <p className="text-[9px] uppercase tracking-widest font-mono text-muted-foreground font-semibold">Latest Catch</p>
                        <div className="flex items-start gap-2">
                          <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${SEV_COLOR[src.latest_severity] || "bg-muted"}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium leading-tight line-clamp-2">{src.latest_title}</p>
                            <p className="text-[9px] font-mono text-muted-foreground">
                              {src.latest_severity?.toUpperCase()} · {timeAgoShort(src.latest_at)}
                            </p>
                          </div>
                          {src.latest_url && (
                            <a href={src.latest_url} target="_blank" rel="noreferrer"
                               className="text-muted-foreground/50 hover:text-primary transition-colors shrink-0 mt-0.5"
                               onClick={e => e.stopPropagation()}>
                              <ExternalLink size={11} />
                            </a>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="text-[10px] text-muted-foreground font-mono py-1">No items collected yet — fetch will populate this source.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Recent catches across all non-RSS sources */}
        {recent_catches.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-widest font-mono font-semibold text-muted-foreground mb-2">
              Recent Catches — All Sources
            </p>
            <div className="divide-y divide-border border border-border">
              {recent_catches.map((item, i) => {
                const m = SOURCE_META[item.source_type] || { label: item.source_type, dot: "bg-muted-foreground", accent: "text-muted-foreground" };
                return (
                  <div key={i} className="p-2.5 flex items-start gap-2.5 hover:bg-muted/5">
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${SEV_COLOR[item.severity] || "bg-muted"}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{item.title}</p>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        <span className={`text-[8px] uppercase font-mono font-bold ${m.accent}`}>{m.label}</span>
                        {item.source && <span className="text-[8px] font-mono text-muted-foreground truncate max-w-[120px]">{item.source}</span>}
                        {item.threat_category && <span className="text-[8px] font-mono text-muted-foreground/60">{item.threat_category}</span>}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <Badge className={`rounded-none text-[7px] px-1 py-0 ${
                        item.severity === "critical" ? "bg-red-500/15 text-red-400 border-red-500/30" :
                        item.severity === "high"     ? "bg-orange-500/15 text-orange-400 border-orange-500/30" :
                        item.severity === "medium"   ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" :
                        "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                      }`}>{item.severity}</Badge>
                      <p className="text-[8px] font-mono text-muted-foreground mt-0.5">{timeAgoShort(item.published_at)}</p>
                    </div>
                    {item.source_url && (
                      <a href={item.source_url} target="_blank" rel="noreferrer"
                         className="text-muted-foreground/40 hover:text-primary transition-colors shrink-0 mt-1">
                        <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {totalNonRss === 0 && !loading && (
          <div className="text-center py-6 text-muted-foreground text-sm">
            No intelligence yet from non-RSS sources. Trigger a fetch from the Dashboard scanners to populate.
          </div>
        )}
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


// ─── Social Media Scan Manager ────────────────────────────────────────────────

const SM_CATS = ["media", "government", "defense", "paramilitary", "general", "intelligence"];
const SM_REGIONS_LIST = [
  "Northeast", "NER", "Assam", "Manipur", "Meghalaya", "Mizoram", "Tripura",
  "Nagaland", "Arunachal Pradesh", "Sikkim", "India", "Bangladesh", "Myanmar", "International",
];

const SM_TABS = [
  { id: "youtube",   label: "YouTube",   Icon: Youtube,  accent: "text-red-400"    },
  { id: "facebook",  label: "Facebook",  Icon: Facebook, accent: "text-blue-400"   },
  { id: "telegram",  label: "Telegram",  Icon: Radio,    accent: "text-sky-400"    },
  { id: "twitter",   label: "X/Twitter", Icon: Twitter,  accent: "text-slate-300"  },
  { id: "firecrawl", label: "Firecrawl", Icon: Activity, accent: "text-orange-400" },
];

function useSocialStatus(api) {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    let cancelled = false;
    axios.get(`${api}/social/status`)
      .then(r => { if (!cancelled) setStatus(r.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [api]);
  return status;
}

function PlatformBanner({ status, platformId }) {
  if (!status || !status[platformId]) return null;
  const p = status[platformId];
  if (p.available) return null;
  return (
    <div className="border border-amber-500/30 bg-amber-500/5 p-3 flex items-start gap-3 mb-3">
      <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-wider text-amber-400 font-['Barlow_Condensed']">
          Source Currently Disabled
        </p>
        <p className="text-[10px] text-muted-foreground font-mono leading-relaxed mt-1">
          {p.note}
        </p>
        <p className="text-[10px] text-muted-foreground/70 font-mono mt-1">
          You can still configure sources below — fetching will resume once the API key is set.
        </p>
      </div>
    </div>
  );
}

function useSourceList(api, path, listKey) {
  const [items, setItems]     = useState([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}${path}`);
      setItems(res.data[listKey] || []);
    } catch (e) { console.error(`fetch ${path} failed`, e); }
    setLoading(false);
  }, [api, path, listKey]);
  useEffect(() => { load(); }, [load]);
  return { items, loading, refresh: load };
}

function SmRow({ item, primary, secondary, badge, onDelete, deleting }) {
  const busy = deleting === item.id;
  return (
    <div className="px-3 py-2.5 flex items-center gap-3 hover:bg-muted/5 group">
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{primary}</p>
        {secondary && <p className="text-[9px] font-mono text-muted-foreground/60 truncate mt-0.5">{secondary}</p>}
      </div>
      {badge && (
        <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-muted text-muted-foreground border-border shrink-0">{badge}</Badge>
      )}
      {item.active === false && (
        <Badge className="rounded-none text-[8px] px-1.5 py-0 bg-amber-500/10 text-amber-400 border-amber-500/20 shrink-0">paused</Badge>
      )}
      <button
        onClick={() => onDelete(item.id)}
        disabled={busy}
        className="p-1 shrink-0 text-muted-foreground/30 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
        title="Remove"
      >
        {busy ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
      </button>
    </div>
  );
}

function SmSection({ accent, title, items, loading, renderRow, showForm, setShowForm, addLabel, form }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className={`text-[10px] uppercase tracking-widest font-mono font-semibold ${accent}`}>
          {title}
          <span className="text-muted-foreground font-normal ml-2">({loading ? "…" : items.length})</span>
        </p>
        {!showForm && (
          <Button
            variant="outline" size="sm"
            className="rounded-none text-[10px] h-6 px-2 uppercase tracking-wider"
            onClick={() => setShowForm(true)}
          >
            <Plus size={10} className="mr-1" />{addLabel}
          </Button>
        )}
      </div>
      {showForm && form}
      {loading ? (
        <div className="flex items-center gap-2 py-3"><Loader2 size={12} className="animate-spin text-muted-foreground" /><span className="text-[10px] text-muted-foreground font-mono">Loading…</span></div>
      ) : items.length === 0 ? (
        <p className="text-[10px] text-muted-foreground font-mono py-2.5 px-3 border border-dashed border-border">None configured</p>
      ) : (
        <div className="divide-y divide-border border border-border">{items.map(renderRow)}</div>
      )}
    </div>
  );
}

// ── YouTube Tab ───────────────────────────────────────────────────────────────

function YouTubeTab({ api }) {
  const ch = useSourceList(api, "/social/youtube/channels", "channels");
  const sr = useSourceList(api, "/social/youtube/searches", "searches");
  const [del, setDel] = useState(null);
  const [showCh, setShowCh] = useState(false);
  const [showSr, setShowSr] = useState(false);
  const [chName, setChName] = useState(""); const [chId, setChId] = useState(""); const [chCat, setChCat] = useState("media");
  const [srQ, setSrQ] = useState(""); const [srMax, setSrMax] = useState(5);
  const [adding, setAdding] = useState(false);

  const handleDel = async (path, refresh, id) => {
    setDel(id);
    try { await axios.delete(`${api}${path}/${id}`); refresh(); toast.success("Removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const addCh = async (e) => {
    e.preventDefault(); if (!chName.trim() || !chId.trim()) return;
    setAdding("ch");
    try { await axios.post(`${api}/social/youtube/channels`, { name: chName.trim(), channel_id: chId.trim(), category: chCat });
      toast.success("Channel added"); setChName(""); setChId(""); setShowCh(false); ch.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };
  const addSr = async (e) => {
    e.preventDefault(); if (!srQ.trim()) return;
    setAdding("sr");
    try { await axios.post(`${api}/social/youtube/searches`, { query: srQ.trim(), max_results: srMax });
      toast.success("Search added"); setSrQ(""); setShowSr(false); sr.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <div className="space-y-5">
      <SmSection
        accent="text-red-400" title="Channels" items={ch.items} loading={ch.loading}
        showForm={showCh} setShowForm={setShowCh} addLabel="Add Channel"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`Channel ID: ${item.channel_id}`} badge={item.category} onDelete={id=>handleDel("/social/youtube/channels", ch.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addCh} className="border border-red-500/20 bg-red-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Channel Name *</label>
                <Input value={chName} onChange={e=>setChName(e.target.value)} placeholder="e.g. DD News" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Channel ID *</label>
                <Input value={chId} onChange={e=>setChId(e.target.value)} placeholder="UCxxxxxxxxxxxxxxxxxxx" className="rounded-none text-xs h-8 font-mono" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
                <Select value={chCat} onValueChange={setChCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none">{SM_CATS.map(c=><SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="ch"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="ch"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Channel</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowCh(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
      <SmSection
        accent="text-red-400" title="Keyword Searches" items={sr.items} loading={sr.loading}
        showForm={showSr} setShowForm={setShowSr} addLabel="Add Search"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.query} secondary={`${item.max_results} results per run`} onDelete={id=>handleDel("/social/youtube/searches", sr.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addSr} className="border border-red-500/20 bg-red-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Search Query *</label>
                <Input value={srQ} onChange={e=>setSrQ(e.target.value)} placeholder="e.g. Assam border incident" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Max Results</label>
                <Input type="number" value={srMax} onChange={e=>setSrMax(parseInt(e.target.value)||5)} min={1} max={50} className="rounded-none text-xs h-8" /></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="sr"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="sr"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Search</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowSr(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
    </div>
  );
}

// ── Facebook Tab ──────────────────────────────────────────────────────────────

function FacebookTab({ api }) {
  const pg = useSourceList(api, "/social/facebook/pages", "pages");
  const [del, setDel] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [pgName, setPgName] = useState(""); const [pgId, setPgId] = useState(""); const [pgCat, setPgCat] = useState("media");
  const [adding, setAdding] = useState(false);

  const handleDel = async (id) => {
    setDel(id);
    try { await axios.delete(`${api}/social/facebook/pages/${id}`); pg.refresh(); toast.success("Page removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const handleAdd = async (e) => {
    e.preventDefault(); if (!pgName.trim() || !pgId.trim()) return;
    setAdding(true);
    try { await axios.post(`${api}/social/facebook/pages`, { name: pgName.trim(), page_id: pgId.trim(), category: pgCat });
      toast.success("Page added"); setPgName(""); setPgId(""); setShowForm(false); pg.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <SmSection
      accent="text-blue-400" title="Pages" items={pg.items} loading={pg.loading}
      showForm={showForm} setShowForm={setShowForm} addLabel="Add Page"
      renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`Page ID: ${item.page_id}`} badge={item.category} onDelete={handleDel} deleting={del} />}
      form={
        <form onSubmit={handleAdd} className="border border-blue-500/20 bg-blue-500/5 p-3 space-y-2 mb-1">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Page Name *</label>
              <Input value={pgName} onChange={e=>setPgName(e.target.value)} placeholder="e.g. BSF Official" className="rounded-none text-xs h-8" /></div>
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Page ID / Slug *</label>
              <Input value={pgId} onChange={e=>setPgId(e.target.value)} placeholder="e.g. BSFIndia" className="rounded-none text-xs h-8 font-mono" /></div>
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
              <Select value={pgCat} onValueChange={setPgCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                <SelectContent className="rounded-none">{SM_CATS.map(c=><SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}</SelectContent></Select></div>
          </div>
          <div className="flex gap-2">
            <Button type="submit" disabled={adding} size="sm" className="rounded-none text-[10px] uppercase h-7">
              {adding?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Page</Button>
            <Button type="button" variant="outline" size="sm" onClick={()=>setShowForm(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
          </div>
        </form>
      }
    />
  );
}

// ── Telegram Tab ──────────────────────────────────────────────────────────────

function TelegramTab({ api }) {
  const ch = useSourceList(api, "/social/telegram/channels", "channels");
  const [del, setDel] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [tgUser, setTgUser] = useState(""); const [tgName, setTgName] = useState(""); const [tgCat, setTgCat] = useState("media");
  const [adding, setAdding] = useState(false);

  const handleDel = async (id) => {
    setDel(id);
    try { await axios.delete(`${api}/social/telegram/channels/${id}`); ch.refresh(); toast.success("Channel removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const handleAdd = async (e) => {
    e.preventDefault(); if (!tgUser.trim() || !tgName.trim()) return;
    setAdding(true);
    try { await axios.post(`${api}/social/telegram/channels`, { username: tgUser.trim().replace(/^@/, ""), name: tgName.trim(), category: tgCat });
      toast.success("Channel added"); setTgUser(""); setTgName(""); setShowForm(false); ch.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <SmSection
      accent="text-sky-400" title="Channels" items={ch.items} loading={ch.loading}
      showForm={showForm} setShowForm={setShowForm} addLabel="Add Channel"
      renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`@${item.username}`} badge={item.category} onDelete={handleDel} deleting={del} />}
      form={
        <form onSubmit={handleAdd} className="border border-sky-500/20 bg-sky-500/5 p-3 space-y-2 mb-1">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Username (no @) *</label>
              <Input value={tgUser} onChange={e=>setTgUser(e.target.value)} placeholder="e.g. BSFIndia" className="rounded-none text-xs h-8 font-mono" /></div>
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Display Name *</label>
              <Input value={tgName} onChange={e=>setTgName(e.target.value)} placeholder="e.g. BSF India Official" className="rounded-none text-xs h-8" /></div>
            <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
              <Select value={tgCat} onValueChange={setTgCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                <SelectContent className="rounded-none">{SM_CATS.map(c=><SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}</SelectContent></Select></div>
          </div>
          <div className="flex gap-2">
            <Button type="submit" disabled={adding} size="sm" className="rounded-none text-[10px] uppercase h-7">
              {adding?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Channel</Button>
            <Button type="button" variant="outline" size="sm" onClick={()=>setShowForm(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
          </div>
        </form>
      }
    />
  );
}

// ── Twitter Tab ───────────────────────────────────────────────────────────────

function TwitterTab({ api }) {
  const ac = useSourceList(api, "/social/twitter/accounts", "accounts");
  const sr = useSourceList(api, "/social/twitter/searches", "searches");
  const ls = useSourceList(api, "/social/twitter/lists", "lists");
  const [del, setDel] = useState(null);
  const [showAc, setShowAc] = useState(false);
  const [showSr, setShowSr] = useState(false);
  const [showLs, setShowLs] = useState(false);
  const [acHandle, setAcHandle] = useState(""); const [acName, setAcName] = useState(""); const [acCat, setAcCat] = useState("general");
  const [srQ, setSrQ] = useState(""); const [srNum, setSrNum] = useState(10);
  const [lsId, setLsId] = useState(""); const [lsName, setLsName] = useState(""); const [lsMax, setLsMax] = useState(50);
  const [adding, setAdding] = useState(false);

  const handleDel = async (path, refresh, id) => {
    setDel(id);
    try { await axios.delete(`${api}${path}/${id}`); refresh(); toast.success("Removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const addAc = async (e) => {
    e.preventDefault(); if (!acHandle.trim() || !acName.trim()) return;
    setAdding("ac");
    try { await axios.post(`${api}/social/twitter/accounts`, { handle: acHandle.trim().replace(/^@/, ""), name: acName.trim(), category: acCat });
      toast.success("Account added"); setAcHandle(""); setAcName(""); setShowAc(false); ac.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };
  const addSr = async (e) => {
    e.preventDefault(); if (!srQ.trim()) return;
    setAdding("sr");
    try { await axios.post(`${api}/social/twitter/searches`, { query: srQ.trim(), num_results: srNum });
      toast.success("Search added"); setSrQ(""); setShowSr(false); sr.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };
  const addLs = async (e) => {
    e.preventDefault(); if (!lsId.trim() || !lsName.trim()) return;
    setAdding("ls");
    try { await axios.post(`${api}/social/twitter/lists`, { list_id: lsId.trim(), name: lsName.trim(), max_results: lsMax });
      toast.success("List added"); setLsId(""); setLsName(""); setShowLs(false); ls.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <div className="space-y-5">
      {/* Lists section — first because it works on free tier */}
      <SmSection
        accent="text-emerald-400" title="Lists (free-tier friendly)" items={ls.items} loading={ls.loading}
        showForm={showLs} setShowForm={setShowLs} addLabel="Add List"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`List ID: ${item.list_id} · ${item.max_results} tweets/run`} onDelete={id=>handleDel("/social/twitter/lists", ls.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addLs} className="border border-emerald-500/20 bg-emerald-500/5 p-3 space-y-2 mb-1">
            <p className="text-[9px] text-emerald-400 font-mono uppercase tracking-wider">
              Tip: Create a public List on x.com → /i/lists/&lt;ID&gt; → paste the numeric ID below.
              One fetch returns tweets from every account in the list — works on free X API tier.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">List ID *</label>
                <Input value={lsId} onChange={e=>setLsId(e.target.value)} placeholder="e.g. 1234567890123456789" className="rounded-none text-xs h-8 font-mono" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Display Name *</label>
                <Input value={lsName} onChange={e=>setLsName(e.target.value)} placeholder="e.g. Indian Defence" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Tweets Per Fetch</label>
                <Input type="number" value={lsMax} onChange={e=>setLsMax(parseInt(e.target.value)||50)} min={1} max={100} className="rounded-none text-xs h-8" /></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="ls"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="ls"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add List</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowLs(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
      <SmSection
        accent="text-slate-300" title="Accounts to Monitor" items={ac.items} loading={ac.loading}
        showForm={showAc} setShowForm={setShowAc} addLabel="Add Account"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={`@${item.handle}`} badge={item.category} onDelete={id=>handleDel("/social/twitter/accounts", ac.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addAc} className="border border-slate-500/20 bg-slate-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Handle (no @) *</label>
                <Input value={acHandle} onChange={e=>setAcHandle(e.target.value)} placeholder="e.g. BSF_India" className="rounded-none text-xs h-8 font-mono" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Display Name *</label>
                <Input value={acName} onChange={e=>setAcName(e.target.value)} placeholder="e.g. Border Security Force" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
                <Select value={acCat} onValueChange={setAcCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none">{SM_CATS.map(c=><SelectItem key={c} value={c} className="text-xs">{c}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="ac"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="ac"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Account</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowAc(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
      <SmSection
        accent="text-slate-300" title="Keyword Searches" items={sr.items} loading={sr.loading}
        showForm={showSr} setShowForm={setShowSr} addLabel="Add Search"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.query} secondary={`${item.num_results} results per run`} onDelete={id=>handleDel("/social/twitter/searches", sr.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addSr} className="border border-slate-500/20 bg-slate-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Search Query *</label>
                <Input value={srQ} onChange={e=>setSrQ(e.target.value)} placeholder="e.g. Manipur violence OR Assam border" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Results Per Run</label>
                <Input type="number" value={srNum} onChange={e=>setSrNum(parseInt(e.target.value)||10)} min={1} max={100} className="rounded-none text-xs h-8" /></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="sr"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="sr"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Search</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowSr(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
    </div>
  );
}

// ── Firecrawl Tab ─────────────────────────────────────────────────────────────

function FirecrawlTab({ api }) {
  const ws = useSourceList(api, "/web-sources", "sources");
  const fc = useSourceList(api, "/firecrawl-searches", "searches");
  const [del, setDel] = useState(null);
  const [showWs, setShowWs] = useState(false);
  const [showFc, setShowFc] = useState(false);
  const [wsName, setWsName] = useState(""); const [wsUrl, setWsUrl] = useState("");
  const [wsRegion, setWsRegion] = useState("Northeast"); const [wsCat, setWsCat] = useState("grassroots");
  const [fcQ, setFcQ] = useState(""); const [fcNum, setFcNum] = useState(5);
  const [adding, setAdding] = useState(false);

  const handleDel = async (path, refresh, id) => {
    setDel(id);
    try { await axios.delete(`${api}${path}/${id}`); refresh(); toast.success("Removed"); }
    catch { toast.error("Delete failed"); }
    setDel(null);
  };
  const addWs = async (e) => {
    e.preventDefault(); if (!wsName.trim() || !wsUrl.trim()) return;
    setAdding("ws");
    try { await axios.post(`${api}/web-sources`, { name: wsName.trim(), url: wsUrl.trim(), region: wsRegion, category: wsCat });
      toast.success("Web source added"); setWsName(""); setWsUrl(""); setShowWs(false); ws.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };
  const addFc = async (e) => {
    e.preventDefault(); if (!fcQ.trim()) return;
    setAdding("fc");
    try { await axios.post(`${api}/firecrawl-searches`, { query: fcQ.trim(), num_results: fcNum });
      toast.success("Search added"); setFcQ(""); setShowFc(false); fc.refresh(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    setAdding(false);
  };

  return (
    <div className="space-y-5">
      <SmSection
        accent="text-orange-400" title="Web Sources" items={ws.items} loading={ws.loading}
        showForm={showWs} setShowForm={setShowWs} addLabel="Add Website"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.name} secondary={item.url} badge={item.region} onDelete={id=>handleDel("/web-sources", ws.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addWs} className="border border-orange-500/20 bg-orange-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Source Name *</label>
                <Input value={wsName} onChange={e=>setWsName(e.target.value)} placeholder="e.g. NorthEast Now" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">URL *</label>
                <Input value={wsUrl} onChange={e=>setWsUrl(e.target.value)} placeholder="https://example.com" className="rounded-none text-xs h-8 font-mono" /></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Region</label>
                <Select value={wsRegion} onValueChange={setWsRegion}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none max-h-48">{SM_REGIONS_LIST.map(r=><SelectItem key={r} value={r} className="text-xs">{r}</SelectItem>)}</SelectContent></Select></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Category</label>
                <Select value={wsCat} onValueChange={setWsCat}><SelectTrigger className="rounded-none text-xs h-8"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-none"><SelectItem value="grassroots" className="text-xs">Grassroots</SelectItem><SelectItem value="established" className="text-xs">Established</SelectItem></SelectContent></Select></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="ws"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="ws"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Website</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowWs(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
      <SmSection
        accent="text-orange-400" title="Keyword Searches" items={fc.items} loading={fc.loading}
        showForm={showFc} setShowForm={setShowFc} addLabel="Add Search"
        renderRow={item => <SmRow key={item.id} item={item} primary={item.query} secondary={`${item.num_results} results per run`} onDelete={id=>handleDel("/firecrawl-searches", fc.refresh, id)} deleting={del} />}
        form={
          <form onSubmit={addFc} className="border border-orange-500/20 bg-orange-500/5 p-3 space-y-2 mb-1">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Search Query *</label>
                <Input value={fcQ} onChange={e=>setFcQ(e.target.value)} placeholder="e.g. northeast India border conflict" className="rounded-none text-xs h-8" /></div>
              <div><label className="text-[9px] uppercase font-mono text-muted-foreground block mb-1">Results Per Run</label>
                <Input type="number" value={fcNum} onChange={e=>setFcNum(parseInt(e.target.value)||5)} min={1} max={20} className="rounded-none text-xs h-8" /></div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={adding==="fc"} size="sm" className="rounded-none text-[10px] uppercase h-7">
                {adding==="fc"?<Loader2 size={10} className="mr-1 animate-spin"/>:<Plus size={10} className="mr-1"/>}Add Search</Button>
              <Button type="button" variant="outline" size="sm" onClick={()=>setShowFc(false)} className="rounded-none text-[10px] h-7">Cancel</Button>
            </div>
          </form>
        }
      />
    </div>
  );
}

// ── Main Social Scan Manager ─────────────────────────────────────────────────

function SocialScanManager({ api }) {
  const [activeTab, setActiveTab] = useState("youtube");
  const active = SM_TABS.find(t => t.id === activeTab);
  const status = useSocialStatus(api);

  const renderTab = () => {
    switch (activeTab) {
      case "youtube":   return <YouTubeTab api={api} />;
      case "facebook":  return <FacebookTab api={api} />;
      case "telegram":  return <TelegramTab api={api} />;
      case "twitter":   return <TwitterTab api={api} />;
      case "firecrawl": return <FirecrawlTab api={api} />;
      default: return null;
    }
  };

  const tabDesc = {
    youtube:   "channels and keyword searches",
    facebook:  "pages",
    telegram:  "channels",
    twitter:   "accounts and keyword searches",
    firecrawl: "websites and keyword searches",
  };

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500" data-testid="social-scan-manager" data-tour="social-scan-manager">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Activity size={16} className="text-violet-400" />
          Social Media Scan Configuration
          <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-violet-500/20 text-violet-400 border-violet-500/30 ml-1">
            5 platforms
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {/* Tab bar */}
        <div className="flex border-b border-border overflow-x-auto">
          {SM_TABS.map(tab => {
            const { Icon } = tab;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                data-testid={`sm-tab-${tab.id}`}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider whitespace-nowrap transition-colors border-b-2 ${
                  isActive
                    ? `${tab.accent} border-current bg-muted/5`
                    : "text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/5"
                }`}
              >
                <Icon size={12} />
                {tab.label}
              </button>
            );
          })}
        </div>
        {/* Tab content */}
        <div className="p-4">
          <p className="text-[10px] text-muted-foreground font-mono mb-4">
            Configure which {active?.label} {tabDesc[activeTab]} are scanned during each intelligence fetch cycle. Changes apply on the next fetch.
          </p>
          <PlatformBanner status={status} platformId={activeTab} />
          {renderTab()}
        </div>
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
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-emerald-500" data-testid="rss-feed-manager" data-tour="rss-manager">
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
