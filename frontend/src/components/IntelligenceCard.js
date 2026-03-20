import { useState } from "react";
import {
  Target, MapPin, Users, Package, Shield, AlertTriangle,
  Wifi, Building, Clock, ExternalLink, ChevronDown, ChevronUp
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";

const THREAT_ICONS = {
  "Insurgency": Target,
  "Cross-border Movement": MapPin,
  "Illegal Immigration": Users,
  "Drug Trafficking": Package,
  "Arms Smuggling": Shield,
  "Ethnic Conflicts": AlertTriangle,
  "Cyber Threats": Wifi,
  "Strategic Infrastructure": Building,
};

const SEVERITY_CLASSES = {
  critical: "severity-critical",
  high: "severity-high",
  medium: "severity-medium",
  low: "severity-low",
};

const CARD_BORDER_CLASSES = {
  critical: "intel-card-critical",
  high: "intel-card-high",
  medium: "intel-card-medium",
  low: "intel-card-low",
};

function formatTime(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diff = now - d;
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (hours < 1) return "Just now";
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  } catch {
    return "";
  }
}

export default function IntelligenceCard({ item, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  const ThreatIcon = THREAT_ICONS[item.threat_category] || AlertTriangle;
  const severityClass = SEVERITY_CLASSES[item.severity] || "severity-low";
  const borderClass = CARD_BORDER_CLASSES[item.severity] || "intel-card-low";

  return (
    <div
      className={`intel-card ${borderClass} p-4 animate-slide-in ${item.severity === "critical" ? "glow-critical" : ""}`}
      data-testid={`intel-card-${item.id}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <ThreatIcon size={16} className="text-muted-foreground shrink-0 mt-0.5" />
          <div className="min-w-0">
            <h3 className="text-sm font-semibold leading-tight line-clamp-2" data-testid="card-title">
              {item.title}
            </h3>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground font-mono">
              <span data-testid="card-source">{item.source}</span>
              <span>|</span>
              <Clock size={10} />
              <span>{formatTime(item.published_at)}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <Badge
            className={`${severityClass} rounded-none uppercase tracking-widest text-[10px] px-2 py-0.5 border`}
            data-testid="card-severity"
          >
            {item.severity}
          </Badge>
        </div>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        {item.state && (
          <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0" data-testid="card-state">
            {item.state}
          </Badge>
        )}
        {item.threat_category && (
          <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0" data-testid="card-threat">
            {item.threat_category}
          </Badge>
        )}
        {item.is_cross_border && (
          <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0 text-amber-400 border-amber-500/30">
            Cross-Border
          </Badge>
        )}
      </div>

      {/* Summary */}
      {item.ai_summary && (
        <p className="text-sm text-muted-foreground leading-relaxed mb-2" data-testid="card-summary">
          {compact ? item.ai_summary.slice(0, 150) + (item.ai_summary.length > 150 ? "..." : "") : item.ai_summary}
        </p>
      )}

      {/* Expandable section */}
      {!compact && (
        <>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs uppercase tracking-wider text-muted-foreground p-0 h-auto hover:text-primary"
            onClick={() => setExpanded(!expanded)}
            data-testid="card-expand-btn"
          >
            {expanded ? <ChevronUp size={14} className="mr-1" /> : <ChevronDown size={14} className="mr-1" />}
            {expanded ? "Less" : "Analysis"}
          </Button>

          {expanded && (
            <div className="mt-3 space-y-3 border-t border-border pt-3 animate-slide-in">
              {item.why_it_matters && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Why It Matters</p>
                  <p className="text-sm" data-testid="card-why-matters">{item.why_it_matters}</p>
                </div>
              )}
              {item.potential_impact && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Potential Impact</p>
                  <p className="text-sm" data-testid="card-impact">{item.potential_impact}</p>
                </div>
              )}
              {item.attention_level && (
                <div className="flex items-center gap-2">
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Attention Level:</p>
                  <span className="text-sm font-semibold text-primary" data-testid="card-attention">{item.attention_level}</span>
                </div>
              )}
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  data-testid="card-source-link"
                >
                  <ExternalLink size={12} /> View Source
                </a>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
