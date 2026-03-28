import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Shield, AlertTriangle, Activity, TrendingUp,
  ChevronRight, RefreshCw, Target, ArrowUp,
  Rss, Eye, EyeOff, Clock, CheckCircle2, Loader2
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import NERMap from "../components/NERMap";
import IntelligenceCard from "../components/IntelligenceCard";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie
} from "recharts";

const SEVERITY_COLORS = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#eab308",
  low: "#a3e635",
};

function StatBox({ label, value, icon: Icon, color, sub, testId, onClick }) {
  return (
    <div
      className={`stat-card flex items-center gap-4 ${onClick ? "cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-all duration-200" : ""}`}
      data-testid={testId}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className={`p-2.5 ${color}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold font-['Barlow_Condensed'] tracking-tight">{value}</p>
        <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">{label}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
      {onClick && <ChevronRight size={14} className="ml-auto text-muted-foreground" />}
    </div>
  );
}

function ScanProgressBar({ api }) {
  const [scanStatus, setScanStatus] = useState(null);
  const [visible, setVisible] = useState(true);
  const pollRef = useRef(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${api}/scan-status`);
        setScanStatus(res.data);
      } catch (e) { /* silent */ }
    };
    fetchStatus();
    pollRef.current = setInterval(fetchStatus, 3000);
    return () => clearInterval(pollRef.current);
  }, [api]);

  const formatIST = (isoStr) => {
    if (!isoStr) return "N/A";
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true });
    } catch { return "N/A"; }
  };

  if (!scanStatus) return null;

  const isScanning = scanStatus.is_scanning;
  const progress = scanStatus.progress || 0;
  const lastResult = scanStatus.last_scan_result;

  return (
    <Card className="border border-border rounded-none bg-card overflow-hidden" data-testid="scan-progress-card">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <Rss size={14} className={isScanning ? "text-primary animate-pulse" : "text-muted-foreground"} />
          <span className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
            RSS Scanner
          </span>
          {isScanning && (
            <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-primary/20 text-primary border-primary/30 animate-pulse">
              SCANNING
            </Badge>
          )}
          {!isScanning && lastResult && !lastResult.error && (
            <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-green-500/20 text-green-400 border-green-500/30">
              IDLE
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={() => setVisible(!visible)}
          data-testid="toggle-scan-progress"
        >
          {visible ? <EyeOff size={12} /> : <Eye size={12} />}
        </Button>
      </div>

      {visible && (
        <CardContent className="p-4 space-y-3">
          {/* Progress bar */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
              <span>{isScanning ? `Scanning... ${progress}%` : "Last scan complete"}</span>
              <span>{scanStatus.sources_scanned || 0}/{scanStatus.total_sources || 0} feeds</span>
            </div>
            <div className="w-full h-2 bg-muted/30 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${isScanning ? "bg-primary animate-pulse" : "bg-green-500"}`}
                style={{ width: `${isScanning ? progress : 100}%` }}
              />
            </div>
          </div>

          {/* Live source name during scan */}
          {isScanning && scanStatus.current_source && (
            <div className="flex items-center gap-2 text-xs" data-testid="current-scan-source">
              <Loader2 size={12} className="animate-spin text-primary" />
              <span className="text-muted-foreground">Scanning:</span>
              <span className="font-medium text-foreground truncate">{scanStatus.current_source}</span>
            </div>
          )}

          {/* Scan log - last few sources */}
          {isScanning && scanStatus.scan_log && scanStatus.scan_log.length > 0 && (
            <div className="max-h-20 overflow-y-auto space-y-0.5" data-testid="scan-log">
              {scanStatus.scan_log.slice(-5).map((source, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground">
                  <CheckCircle2 size={9} className="text-green-500 shrink-0" />
                  <span className="truncate">{source}</span>
                </div>
              ))}
            </div>
          )}

          {/* Last scan info + results */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs border-t border-border pt-2">
            <div className="flex items-center gap-1.5" data-testid="last-scan-time">
              <Clock size={11} className="text-muted-foreground" />
              <span className="text-muted-foreground">Last scan:</span>
              <span className="font-mono font-medium">{formatIST(scanStatus.last_scan_at)}</span>
            </div>
            {lastResult && !lastResult.error && (
              <>
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">Feeds:</span>
                  <span className="font-mono font-bold">{lastResult.feeds_scanned}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">Articles:</span>
                  <span className="font-mono font-bold">{lastResult.total_articles}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">New:</span>
                  <span className="font-mono font-bold text-primary">{lastResult.new_relevant}</span>
                </div>
              </>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export default function Dashboard({ stats: propStats, api }) {
  const [recentItems, setRecentItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [localStats, setLocalStats] = useState(null);
  const navigate = useNavigate();

  const stats = propStats || localStats;

  useEffect(() => {
    fetchRecent();
    if (!propStats) {
      fetchStats();
    }
  }, [api, propStats]);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${api}/dashboard/stats`);
      setLocalStats(res.data);
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  };

  const fetchRecent = async () => {
    try {
      const res = await axios.get(`${api}/intelligence?limit=6`);
      setRecentItems(res.data.items || []);
    } catch (e) {
      console.error("Failed to fetch recent items:", e);
    }
  };

  const handleFetchNews = async () => {
    setLoading(true);
    try {
      await axios.post(`${api}/fetch-news`);
    } catch (e) {
      console.error("Fetch failed:", e);
    }
    setTimeout(() => {
      setLoading(false);
      fetchRecent();
    }, 3000);
  };

  const threatData = stats?.threat_distribution
    ? Object.entries(stats.threat_distribution).map(([k, v]) => ({ name: k, value: v }))
    : [];

  const trendData = stats?.trend_7d || [];

  const stateStatsMap = {};
  if (stats?.state_distribution) {
    Object.entries(stats.state_distribution).forEach(([state, count]) => {
      stateStatsMap[state] = {
        count,
        critical: stats.recent_critical?.filter((i) => i.state === state && i.severity === "critical").length || 0,
        high: stats.recent_critical?.filter((i) => i.state === state && i.severity === "high").length || 0,
      };
    });
  }
  // Ensure Bangladesh/Myanmar always appear on map even if not yet in state_distribution
  ["Bangladesh", "Myanmar"].forEach((region) => {
    if (!stateStatsMap[region]) {
      const crossBorderItems = stats?.recent_critical?.filter(
        (i) => i.countries_involved?.includes(region) || i.state === region
      ) || [];
      if (crossBorderItems.length > 0) {
        stateStatsMap[region] = {
          count: crossBorderItems.length,
          critical: crossBorderItems.filter((i) => i.severity === "critical").length,
          high: crossBorderItems.filter((i) => i.severity === "high").length,
        };
      }
    }
  });

  const PIE_COLORS = ["#ef4444", "#f59e0b", "#eab308", "#a3e635", "#3b82f6", "#8b5cf6", "#06b6d4", "#6366f1"];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="dashboard-title">
            Intelligence Overview
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            NER Situation Awareness Dashboard
          </p>
        </div>
        <Button
          onClick={handleFetchNews}
          disabled={loading}
          className="uppercase text-xs font-bold tracking-wider rounded-none"
          data-testid="fetch-news-btn"
        >
          <RefreshCw size={14} className={`mr-2 ${loading ? "animate-spin" : ""}`} />
          Fetch Intel
        </Button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <StatBox
          label="Total Items"
          value={stats?.total_items || 0}
          icon={Activity}
          color="bg-primary/10 text-primary"
          sub={`${stats?.today_count || 0} today`}
          testId="stat-total"
          onClick={() => navigate("/feed")}
        />
        <StatBox
          label="Critical"
          value={stats?.critical_count || 0}
          icon={AlertTriangle}
          color="bg-red-500/10 text-red-400"
          testId="stat-critical"
          onClick={() => navigate("/feed?severity=critical")}
        />
        <StatBox
          label="High"
          value={stats?.high_count || 0}
          icon={Target}
          color="bg-amber-500/10 text-amber-400"
          testId="stat-high"
          onClick={() => navigate("/feed?severity=high")}
        />
        <StatBox
          label="Medium"
          value={stats?.medium_count || 0}
          icon={Shield}
          color="bg-yellow-500/10 text-yellow-400"
          testId="stat-medium"
          onClick={() => navigate("/feed?severity=medium")}
        />
        <StatBox
          label="Low"
          value={stats?.low_count || 0}
          icon={ArrowUp}
          color="bg-green-500/10 text-green-400"
          testId="stat-low"
          onClick={() => navigate("/feed?severity=low")}
        />
      </div>

      {/* RSS Scan Progress Bar */}
      <ScanProgressBar api={api} />

      {/* Map + Recent Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* NER Map */}
        <div className="lg:col-span-7">
          <NERMap
            stateStats={stateStatsMap}
            onStateClick={(state) => navigate(`/feed?state=${encodeURIComponent(state)}`)}
          />
        </div>

        {/* Recent Critical Alerts */}
        <div className="lg:col-span-5">
          <Card className="border border-border rounded-none bg-card h-full">
            <CardHeader className="py-3 px-4 border-b border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
                  Recent Critical Alerts
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-primary uppercase tracking-wider"
                  onClick={() => navigate("/alerts")}
                  data-testid="view-all-alerts-btn"
                >
                  View All <ChevronRight size={14} />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-3 space-y-3 max-h-[400px] overflow-y-auto" data-testid="recent-alerts-list">
              {(stats?.recent_critical || []).map((item, i) => (
                <div
                  key={item.id || i}
                  className={`p-3 border border-border ${item.severity === "critical" ? "border-l-4 border-l-red-500 glow-critical" : "border-l-4 border-l-amber-500"}`}
                  data-testid={`recent-alert-${i}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-medium leading-tight line-clamp-2">{item.title}</h4>
                    <Badge className={`shrink-0 rounded-none uppercase text-[10px] px-1.5 py-0 border ${item.severity === "critical" ? "severity-critical" : "severity-high"}`}>
                      {item.severity}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground font-mono">
                    <span>{item.state}</span>
                    <span>|</span>
                    <span>{item.source}</span>
                  </div>
                </div>
              ))}
              {(!stats?.recent_critical || stats.recent_critical.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-8">No critical alerts</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Threat Distribution */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              Threat Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4" data-testid="threat-distribution-chart">
            {threatData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={threatData} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10, fill: "hsl(120,5%,60%)" }} />
                  <Tooltip
                    contentStyle={{ background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)", borderRadius: 0, fontSize: 12 }}
                  />
                  <Bar dataKey="value" fill="hsl(84,80%,55%)" radius={0}>
                    {threatData.map((entry, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground text-sm">
                No data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* State Distribution Pie */}
        <Card className="border border-border rounded-none bg-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
              State-wise Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4" data-testid="state-distribution-chart">
            {stats?.state_distribution && Object.keys(stats.state_distribution).length > 0 ? (
              <div className="flex items-center">
                <ResponsiveContainer width="60%" height={250}>
                  <PieChart>
                    <Pie
                      data={Object.entries(stats.state_distribution).map(([k, v]) => ({ name: k, value: v }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      stroke="hsl(120,10%,5%)"
                      strokeWidth={2}
                    >
                      {Object.keys(stats.state_distribution).map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: "hsl(120,10%,8%)", border: "1px solid hsl(120,5%,20%)", borderRadius: 0, fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="w-[40%] space-y-1.5">
                  {Object.entries(stats.state_distribution).map(([state, count], i) => (
                    <div key={state} className="flex items-center gap-2 text-xs">
                      <div className="w-2.5 h-2.5 shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="text-muted-foreground truncate">{state}</span>
                      <span className="font-mono font-bold ml-auto">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground text-sm">
                No data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Intelligence */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl uppercase tracking-wide font-['Barlow_Condensed'] font-semibold">
            Latest Intelligence
          </h2>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-primary uppercase tracking-wider"
            onClick={() => navigate("/feed")}
            data-testid="view-all-feed-btn"
          >
            View Full Feed <ChevronRight size={14} />
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="recent-intelligence-grid">
          {recentItems.map((item) => (
            <IntelligenceCard key={item.id} item={item} compact />
          ))}
          {recentItems.length === 0 && (
            <p className="text-sm text-muted-foreground col-span-full text-center py-8">
              No intelligence items yet. Click "Fetch Intel" to gather data.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
