import { useState, useEffect } from "react";
import {
  GitBranch, AlertTriangle, TrendingUp, RefreshCw, MapPin
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import axios from "axios";

const RISK_STYLES = {
  CRITICAL: { badge: "bg-red-500/20 text-red-400 border-red-500/30", border: "border-l-4 border-l-red-500" },
  HIGH: { badge: "bg-orange-500/20 text-orange-400 border-orange-500/30", border: "border-l-4 border-l-orange-500" },
  MODERATE: { badge: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30", border: "border-l-4 border-l-yellow-500" },
  LOW: { badge: "bg-green-500/20 text-green-400 border-green-500/30", border: "border-l-4 border-l-green-500" },
};

function formatTime(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  } catch { return ""; }
}

export default function Patterns({ api }) {
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);

  const fetchPatterns = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/patterns`);
      setPatterns(res.data.patterns || []);
    } catch (e) {
      console.error("Failed to fetch patterns:", e);
    }
    setLoading(false);
  };

  const triggerDetection = async () => {
    setDetecting(true);
    try {
      await axios.post(`${api}/patterns/detect`);
      setTimeout(fetchPatterns, 3000);
    } catch (e) {
      console.error("Detection trigger failed:", e);
    }
    setTimeout(() => setDetecting(false), 3000);
  };

  useEffect(() => { fetchPatterns(); }, [api]);

  const criticalPatterns = patterns.filter(p => p.escalation_risk === "CRITICAL" || p.escalation_risk === "HIGH");
  const otherPatterns = patterns.filter(p => p.escalation_risk !== "CRITICAL" && p.escalation_risk !== "HIGH");

  return (
    <div className="space-y-6" data-testid="patterns-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="patterns-title">
            Pattern Detection Engine
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            Recurring threat patterns across intelligence items
          </p>
        </div>
        <Button
          onClick={triggerDetection}
          disabled={detecting}
          className="uppercase text-xs font-bold tracking-wider rounded-none"
          data-testid="detect-patterns-btn"
        >
          <RefreshCw size={14} className={`mr-2 ${detecting ? "animate-spin" : ""}`} />
          Run Detection
        </Button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card flex items-center gap-3">
          <GitBranch size={18} className="text-primary" />
          <div>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">{patterns.length}</p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">Total Patterns</p>
          </div>
        </div>
        <div className="stat-card flex items-center gap-3">
          <AlertTriangle size={18} className="text-red-400" />
          <div>
            <p className="text-2xl font-bold font-['Barlow_Condensed'] text-red-400">
              {patterns.filter(p => p.escalation_risk === "CRITICAL").length}
            </p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">Critical</p>
          </div>
        </div>
        <div className="stat-card flex items-center gap-3">
          <TrendingUp size={18} className="text-orange-400" />
          <div>
            <p className="text-2xl font-bold font-['Barlow_Condensed'] text-orange-400">
              {patterns.filter(p => p.escalation_risk === "HIGH").length}
            </p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">High Risk</p>
          </div>
        </div>
        <div className="stat-card flex items-center gap-3">
          <MapPin size={18} className="text-blue-400" />
          <div>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">
              {new Set(patterns.map(p => p.region)).size}
            </p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">Regions</p>
          </div>
        </div>
      </div>

      {/* Critical / High Risk Patterns */}
      {criticalPatterns.length > 0 && (
        <div>
          <h2 className="text-lg uppercase tracking-wide font-['Barlow_Condensed'] font-semibold mb-3 text-red-400">
            Escalation Warnings
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {criticalPatterns.map((p, i) => (
              <PatternCard key={i} pattern={p} />
            ))}
          </div>
        </div>
      )}

      {/* Other Patterns */}
      {otherPatterns.length > 0 && (
        <div>
          <h2 className="text-lg uppercase tracking-wide font-['Barlow_Condensed'] font-semibold mb-3">
            All Detected Patterns
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {otherPatterns.map((p, i) => (
              <PatternCard key={i} pattern={p} />
            ))}
          </div>
        </div>
      )}

      {patterns.length === 0 && !loading && (
        <Card className="border border-border rounded-none bg-card">
          <CardContent className="p-8 text-center text-muted-foreground">
            <GitBranch size={32} className="mx-auto mb-3 opacity-50" />
            <p className="text-sm">No patterns detected yet. Click "Run Detection" to analyze recent intelligence.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PatternCard({ pattern }) {
  const style = RISK_STYLES[pattern.escalation_risk] || RISK_STYLES.LOW;

  return (
    <Card className={`border border-border rounded-none bg-card ${style.border}`} data-testid={`pattern-card-${pattern.pattern_key}`}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">{pattern.region}</h3>
            <p className="text-xs text-muted-foreground">{pattern.detail || pattern.pattern_type}</p>
          </div>
          <Badge className={`rounded-none text-[10px] px-1.5 py-0 border ${style.badge}`}>
            {pattern.escalation_risk}
          </Badge>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 bg-muted/20 border border-border">
            <p className="text-lg font-bold font-['Barlow_Condensed']">{pattern.event_count}</p>
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Events</p>
          </div>
          <div className="p-2 bg-muted/20 border border-border">
            <p className="text-lg font-bold font-['Barlow_Condensed']">{pattern.avg_priority_score}</p>
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Avg Priority</p>
          </div>
          <div className="p-2 bg-muted/20 border border-border">
            <p className="text-lg font-bold font-['Barlow_Condensed']">{pattern.window_days}d</p>
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Window</p>
          </div>
        </div>

        {/* Severity breakdown */}
        {pattern.severity_breakdown && (
          <div className="flex items-center gap-2 text-[10px] font-mono">
            {pattern.severity_breakdown.critical > 0 && (
              <span className="text-red-400">C:{pattern.severity_breakdown.critical}</span>
            )}
            {pattern.severity_breakdown.high > 0 && (
              <span className="text-orange-400">H:{pattern.severity_breakdown.high}</span>
            )}
            {pattern.severity_breakdown.medium > 0 && (
              <span className="text-yellow-400">M:{pattern.severity_breakdown.medium}</span>
            )}
            {pattern.severity_breakdown.low > 0 && (
              <span className="text-green-400">L:{pattern.severity_breakdown.low}</span>
            )}
          </div>
        )}

        {/* Sample titles */}
        {pattern.sample_titles && pattern.sample_titles.length > 0 && (
          <div className="space-y-1 border-t border-border pt-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Recent Events</p>
            {pattern.sample_titles.slice(0, 3).map((t, i) => (
              <p key={i} className="text-xs text-muted-foreground truncate">{t}</p>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono border-t border-border pt-2">
          <span>First: {formatTime(pattern.first_event)}</span>
          <span>Latest: {formatTime(pattern.latest_event)}</span>
        </div>
      </CardContent>
    </Card>
  );
}
