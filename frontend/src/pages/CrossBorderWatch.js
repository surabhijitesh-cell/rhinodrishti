import { useState, useEffect } from "react";
import {
  Globe, ShieldAlert, AlertTriangle, TrendingUp, TrendingDown,
  Eye, Loader2, ChevronDown, ChevronUp, ExternalLink, Filter
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import axios from "axios";

const POSTURE_CONFIG = {
  deteriorating: { color: "text-red-400 border-red-500/40 bg-red-500/10", label: "DETERIORATING", icon: TrendingDown },
  elevated: { color: "text-orange-400 border-orange-500/40 bg-orange-500/10", label: "ELEVATED", icon: AlertTriangle },
  watchful: { color: "text-amber-400 border-amber-500/40 bg-amber-500/10", label: "WATCHFUL", icon: Eye },
  stable: { color: "text-emerald-400 border-emerald-500/40 bg-emerald-500/10", label: "STABLE", icon: ShieldAlert },
};

const SIGNAL_COLORS = {
  HIGH: "text-red-400 border-red-500/30",
  MEDIUM: "text-amber-400 border-amber-500/30",
  LOW: "text-muted-foreground border-border",
};

const BUCKET_LABELS = {
  border_security: "Border Security",
  infiltration: "Infiltration",
  smuggling: "Smuggling",
  migration_refugees: "Migration / Refugees",
  insurgency: "Insurgency",
  extremism: "Extremism",
  military_movement: "Military Movement",
  conflict_escalation: "Conflict Escalation",
  trade_logistics_disruption: "Trade / Logistics",
  political_instability: "Political Instability",
  external_influence: "External Influence",
  humanitarian_stress: "Humanitarian Stress",
};

function SignalItem({ item }) {
  const [expanded, setExpanded] = useState(false);
  const signal = SIGNAL_COLORS[item.signal_strength] || SIGNAL_COLORS.LOW;

  return (
    <div
      className="border border-border hover:border-primary/20 transition-colors"
      data-testid={`signal-item-${item.id}`}
    >
      <div
        className="p-3 cursor-pointer flex items-start gap-3"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="shrink-0 mt-0.5 flex flex-col items-center gap-1">
          {item.signal_strength && (
            <Badge variant="outline" className={`rounded-none text-[8px] px-1 py-0 ${signal}`}>
              {item.signal_strength}
            </Badge>
          )}
          <span className="text-[9px] font-mono text-muted-foreground">{item.priority_score || 0}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-snug">{item.title}</p>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
            {item.ai_summary || item.why_it_matters || ""}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {item.signal_bucket && (
              <Badge variant="outline" className="rounded-none text-[8px] px-1.5 py-0 text-cyan-400 border-cyan-500/30">
                {BUCKET_LABELS[item.signal_bucket] || item.signal_bucket}
              </Badge>
            )}
            {item.severity && (
              <Badge variant="outline" className={`rounded-none text-[8px] px-1.5 py-0 ${
                item.severity === "critical" ? "text-red-400 border-red-500/30" :
                item.severity === "high" ? "text-orange-400 border-orange-500/30" :
                item.severity === "medium" ? "text-amber-400 border-amber-500/30" :
                "text-muted-foreground border-border"
              }`}>
                {item.severity.toUpperCase()}
              </Badge>
            )}
            {item.threat_trajectory && item.threat_trajectory !== "INDETERMINATE" && (
              <Badge variant="outline" className={`rounded-none text-[8px] px-1.5 py-0 ${
                item.threat_trajectory === "ESCALATING" ? "text-red-400 border-red-500/30" :
                item.threat_trajectory === "DE-ESCALATING" ? "text-emerald-400 border-emerald-500/30" :
                "text-muted-foreground border-border"
              }`}>
                {item.threat_trajectory}
              </Badge>
            )}
            <span className="text-[9px] font-mono text-muted-foreground ml-auto">
              {item.source}
            </span>
          </div>
        </div>
        {expanded ? <ChevronUp size={14} className="text-muted-foreground shrink-0" /> :
                    <ChevronDown size={14} className="text-muted-foreground shrink-0" />}
      </div>

      {expanded && (
        <div className="px-3 pb-3 pt-0 border-t border-border space-y-2">
          {item.ai_summary && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">What happened</p>
              <p className="text-xs mt-0.5">{item.ai_summary}</p>
            </div>
          )}
          {item.why_it_matters && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">India-relevant implication</p>
              <p className="text-xs mt-0.5 text-primary/80">{item.why_it_matters}</p>
            </div>
          )}
          {item.early_warning_signal && item.early_warning_signal !== "None identified" && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Early warning</p>
              <p className="text-xs mt-0.5 text-amber-400/80">{item.early_warning_signal}</p>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            {(item.actors || []).map((a) => (
              <Badge key={a} variant="outline" className="rounded-none text-[8px] px-1 py-0">{a}</Badge>
            ))}
            {item.india_relevance_score > 0 && (
              <Badge variant="outline" className="rounded-none text-[8px] px-1.5 py-0 text-primary border-primary/30">
                IRS: {item.india_relevance_score}/20
              </Badge>
            )}
          </div>
          {item.source_url && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 font-mono"
            >
              <ExternalLink size={10} /> View source
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function CountrySection({ title, flag, items, posture, isLoading }) {
  const postureConf = POSTURE_CONFIG[posture] || POSTURE_CONFIG.stable;
  const PostureIcon = postureConf.icon;

  return (
    <Card className="border border-border rounded-none bg-card" data-testid={`section-${title.toLowerCase()}`}>
      <CardHeader className="py-3 px-4 border-b border-border flex flex-row items-center justify-between">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <span className="text-lg">{flag}</span>
          {title} Intelligence
          <Badge variant="outline" className="rounded-none text-[10px] px-1.5 py-0 ml-1">
            {items.length}
          </Badge>
        </CardTitle>
        <Badge variant="outline" className={`rounded-none text-[10px] px-2.5 py-0.5 uppercase tracking-wider flex items-center gap-1.5 ${postureConf.color}`}>
          <PostureIcon size={12} />
          {postureConf.label}
        </Badge>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="animate-spin text-muted-foreground" size={20} />
          </div>
        ) : items.length > 0 ? (
          <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
            {items.map((item) => (
              <SignalItem key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground p-4">
            No cross-border signals detected for this country in the current retention window.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function CrossBorderWatch({ api }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [signalFilter, setSignalFilter] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (signalFilter) params.set("min_signal", signalFilter);
        const res = await axios.get(`${api}/cross-border/watch?${params.toString()}`);
        setData(res.data);
      } catch (e) {
        console.error("Cross-border fetch failed:", e);
      }
      setLoading(false);
    };
    fetchData();
  }, [api, signalFilter]);

  return (
    <div className="space-y-6" data-testid="cross-border-watch">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold uppercase tracking-wider font-['Barlow_Condensed']" data-testid="cb-title">
            Cross-Border Watch
          </h1>
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider mt-0.5">
            Bangladesh & Myanmar — India-Facing Intelligence
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-muted-foreground" />
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Signal:</span>
          {["", "MEDIUM", "HIGH"].map((val) => (
            <Button
              key={val}
              variant="outline"
              size="sm"
              className={`rounded-none text-[10px] h-6 px-2 uppercase ${
                signalFilter === val ? "bg-primary/10 text-primary border-primary/40" : ""
              }`}
              onClick={() => setSignalFilter(val)}
              data-testid={`signal-filter-${val || "all"}`}
            >
              {val || "All"}
            </Button>
          ))}
        </div>
      </div>

      {/* Watchpoints + Signal Distribution */}
      {data && (data.watchpoints?.length > 0 || Object.keys(data.signal_distribution || {}).length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.watchpoints?.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-2 px-4 border-b border-border">
                <CardTitle className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <Eye size={14} className="text-amber-400" /> Watchpoints
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3">
                <ul className="space-y-1.5" data-testid="watchpoints-list">
                  {data.watchpoints.map((wp, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-amber-400 shrink-0 mt-0.5">-</span>
                      <span>{BUCKET_LABELS[wp] || wp}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {Object.keys(data.signal_distribution || {}).length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-2 px-4 border-b border-border">
                <CardTitle className="text-xs uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <TrendingUp size={14} className="text-cyan-400" /> Signal Distribution
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3">
                <div className="flex flex-wrap gap-1.5" data-testid="signal-distribution">
                  {Object.entries(data.signal_distribution).map(([bucket, count]) => (
                    <Badge key={bucket} variant="outline" className="rounded-none text-[9px] px-1.5 py-0 text-cyan-400 border-cyan-500/30">
                      {BUCKET_LABELS[bucket] || bucket} ({count})
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Two-column layout: Bangladesh | Myanmar */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <CountrySection
          title="Bangladesh"
          flag="🇧🇩"
          items={data?.bangladesh?.items || []}
          posture={data?.bangladesh?.posture || "stable"}
          isLoading={loading}
        />
        <CountrySection
          title="Myanmar"
          flag="🇲🇲"
          items={data?.myanmar?.items || []}
          posture={data?.myanmar?.posture || "stable"}
          isLoading={loading}
        />
      </div>
    </div>
  );
}
