import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Target, MapPin, Users, Package, Shield, AlertTriangle,
  Wifi, Building, Clock, ExternalLink, ChevronDown, ChevronUp,
  Flag, TrendingUp, Radar, Layers, Trash2, RefreshCw, Pencil, X, Check,
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import FeedbackWidget from "./FeedbackWidget";
import Tip from "./Tip";
import { useAuth } from "../contexts/AuthContext";

const THREAT_ICONS = {
  "Insurgency": Target,
  "Insurgency / Militancy": Target,
  "Cross-border Movement": MapPin,
  "Illegal Immigration": Users,
  "Drug Trafficking": Package,
  "Arms Smuggling": Shield,
  "Ethnic Conflicts": AlertTriangle,
  "Ethnic / Tribal Tension": AlertTriangle,
  "Cyber Threats": Wifi,
  "Strategic Infrastructure": Building,
  "Infrastructure / Logistics": Building,
  "Military Movement": Shield,
  "Foreign Influence (China/Pakistan/USA)": Flag,
  "Information Warfare / Narrative": Radar,
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

const SPECIAL_FLAG_LABELS = {
  "PLA_PAKISTAN_PRESENCE": "PLA/Pak Presence",
  "COORDINATED_NARRATIVE": "Info Warfare",
  "DEMOGRAPHIC_TREND": "Demographic Shift",
  "DUAL_USE_INFRA": "Dual-Use Infra",
  "PATTERN_DETECTED": "Pattern Alert",
};

function formatTime(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diff = now - d;
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    const abs = d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: days > 300 ? "numeric" : undefined });
    if (hours < 1) return `Just now · ${abs}`;
    if (hours < 24) return `${hours}h ago · ${abs}`;
    if (days < 7)   return `${days}d ago · ${abs}`;
    return abs;
  } catch {
    return "";
  }
}

// ── Fading helpers ────────────────────────────────────────────────────────────
// Map visibility_band → CSS opacity so the card itself dims as the item ages.
const FADE_OPACITY = {
  full:     "opacity-100",
  fading:   "opacity-80",
  dim:      "opacity-55",
  archived: "opacity-30",
};

function FadingBadge({ item }) {
  const v = item.visibility_score;
  const band = item.visibility_band;
  if (v == null || band == null) return null;

  const label = band === "full"     ? `V${Math.round(v)}`
              : band === "fading"   ? `V${Math.round(v)} ↘`
              : band === "dim"      ? `V${Math.round(v)} ↓↓`
              : `V${Math.round(v)} ⌛`;

  const colour = band === "full"   ? "text-green-400"
               : band === "fading" ? "text-yellow-400"
               : band === "dim"    ? "text-orange-400"
               : "text-red-400/60";

  return (
    <Tip
      text={
        `Visibility Score ${Math.round(v)}/100 — computed by the Drishti fading formula: ` +
        `V = P₀ × e^(−t/τ) × W_cb × W_fb × W_traj × W_flag.  ` +
        `P₀=${item.priority_score} (birth priority), τ=${
          {critical:1440,high:720,medium:336,low:72}[item.severity] ?? 336
        }h (${item.severity} half-life), ` +
        `cross-border boost ${item.is_cross_border ? '+25%' : '—'}, ` +
        `trajectory ${item.threat_trajectory || '—'}.  ` +
        `Threshold: ≥50 full, 30–50 fading, 15–30 dim, <15 archived.`
      }
      side="left"
    >
      <span className={`text-[10px] font-mono cursor-default ${colour}`}>{label}</span>
    </Tip>
  );
}

export default function IntelligenceCard({ item, compact = false, api, feedbackData, onDelete, onEnhanced }) {
  const [expanded, setExpanded] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [editingNote, setEditingNote] = useState(false);
  const [noteText, setNoteText] = useState(item.analyst_enhancement?.analyst_note || "");
  const [savingNote, setSavingNote] = useState(false);
  const { user } = useAuth();

  const canEnhance = user && (user.role === "analyst" || user.role === "admin");
  const enhancement = item.analyst_enhancement;

  const handleSaveNote = async () => {
    if (!noteText.trim()) return;
    setSavingNote(true);
    try {
      const token = localStorage.getItem("rd_token");
      const res = await axios.patch(
        `${api}/intelligence/${item.id}/enhance`,
        { analyst_note: noteText.trim() },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success("Enhancement saved");
      setEditingNote(false);
      if (onEnhanced) onEnhanced(item.id, res.data.analyst_enhancement);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Save failed");
    }
    setSavingNote(false);
  };

  const handleRemoveNote = async () => {
    if (!window.confirm("Remove analyst enhancement from this item?")) return;
    try {
      const token = localStorage.getItem("rd_token");
      await axios.delete(`${api}/intelligence/${item.id}/enhance`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success("Enhancement removed");
      setNoteText("");
      if (onEnhanced) onEnhanced(item.id, null);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Remove failed");
    }
  };

  const handleReprocess = async (e) => {
    e.stopPropagation();
    setReprocessing(true);
    try {
      await axios.post(`${api}/intelligence/${item.id}/reprocess`);
      toast.success("Queued for re-classification — severity will update within 30s");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Re-queue failed");
    }
    setTimeout(() => setReprocessing(false), 5000);
  };
  const ThreatIcon = THREAT_ICONS[item.threat_category] || THREAT_ICONS[item.tags?.[0]] || AlertTriangle;
  const severityClass = SEVERITY_CLASSES[item.severity] || "severity-low";
  const borderClass = CARD_BORDER_CLASSES[item.severity] || "intel-card-low";
  const priorityScore = item.priority_score || 0;
  const fadeOpacity = FADE_OPACITY[item.visibility_band] || "opacity-100";

  return (
    <div
      className={`intel-card ${borderClass} p-4 animate-slide-in ${item.severity === "critical" ? "glow-critical" : ""} ${fadeOpacity} transition-opacity duration-500`}
      data-testid={`intel-card-${item.id}`}
    >
      {/* Manually Enhanced badge */}
      {enhancement?.is_enhanced && (
        <div className="flex items-center justify-between mb-2 px-2 py-1 bg-violet-500/15 border border-violet-500/40 rounded-sm">
          <div className="flex items-center gap-1.5">
            <Pencil size={10} className="text-violet-400" />
            <span className="text-[10px] uppercase tracking-widest font-bold text-violet-300">Manually Enhanced</span>
            {enhancement.enhanced_by_name && (
              <span className="text-[10px] text-violet-400/70 font-mono">
                — {enhancement.enhanced_by_name}
              </span>
            )}
          </div>
          {canEnhance && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => { setNoteText(enhancement.analyst_note || ""); setEditingNote(true); setExpanded(true); }}
                className="p-0.5 text-violet-400/60 hover:text-violet-300 transition-colors"
                title="Edit enhancement"
              >
                <Pencil size={10} />
              </button>
              <button
                onClick={handleRemoveNote}
                className="p-0.5 text-violet-400/60 hover:text-red-400 transition-colors"
                title="Remove enhancement"
              >
                <X size={10} />
              </button>
            </div>
          )}
        </div>
      )}

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
              {item.cluster_size > 1 && (
                <Tip text={`${item.cluster_size} independent sources reported this same event. The AI fused them into one card to reduce noise. Click to see all source titles and links.`} side="bottom">
                  <button
                    onClick={(e) => { e.stopPropagation(); setSourcesExpanded(!sourcesExpanded); }}
                    className="inline-flex items-center gap-1 ml-1 px-1.5 py-0.5 bg-blue-500/15 border border-blue-500/30 text-blue-400 hover:bg-blue-500/25 transition-colors cursor-pointer rounded-sm"
                    data-testid="cluster-sources-badge"
                  >
                    <Layers size={10} />
                    <span className="text-[10px] font-semibold">{item.cluster_size} sources</span>
                  </button>
                </Tip>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {/* Severity badge */}
          <Tip
            text={
              item.severity === "critical" ? "CRITICAL — Immediate threat requiring urgent analyst action" :
              item.severity === "high"     ? "HIGH — Significant event warranting priority review" :
              item.severity === "medium"   ? "MEDIUM — Notable but non-urgent; monitor closely" :
                                            "LOW — Informational; relevant background context"
            }
            side="left"
          >
            <Badge
              className={`${severityClass} rounded-none uppercase tracking-widest text-[10px] px-2 py-0.5 border cursor-default`}
              data-testid="card-severity"
            >
              {item.severity}
            </Badge>
          </Tip>

          {/* Priority score */}
          {priorityScore > 0 && (
            <Tip
              text={`Priority Score ${priorityScore}/100 — AI-computed urgency combining severity, source credibility and strategic relevance. ≥80 critical (red), ≥60 elevated (orange), <60 routine.`}
              side="left"
            >
              <span className={`text-[10px] font-mono cursor-default ${priorityScore >= 80 ? 'text-red-400' : priorityScore >= 60 ? 'text-orange-400' : 'text-muted-foreground'}`}>
                P{priorityScore}
              </span>
            </Tip>
          )}

          {/* Confidence score */}
          {item.confidence_score && (
            <Tip
              text={`Confidence Score ${item.confidence_score}% — AI's certainty in its classification. ≥90 high confidence (green), ≥70 moderate (blue), <70 uncertain — verify manually.`}
              side="left"
            >
              <span className={`text-[10px] font-mono cursor-default ${item.confidence_score >= 90 ? 'text-green-400' : item.confidence_score >= 70 ? 'text-blue-400' : 'text-muted-foreground'}`}>
                C{item.confidence_score}%
              </span>
            </Tip>
          )}

          {/* Fading / Visibility score */}
          <FadingBadge item={item} />

          {/* Threat trajectory */}
          {item.threat_trajectory && item.threat_trajectory !== "INDETERMINATE" && (
            <Tip
              text={
                item.threat_trajectory === "ESCALATING"    ? "ESC — Threat is ESCALATING: recent reporting shows increasing severity or frequency" :
                item.threat_trajectory === "DE-ESCALATING" ? "DE-ESC — Threat is DE-ESCALATING: situation appears to be cooling or resolving" :
                item.threat_trajectory === "NEW_THREAT"    ? "NEW — First-time or newly identified threat pattern with no prior baseline" :
                                                             "STABLE — Threat level holding steady with no significant change detected"
              }
              side="left"
            >
              <Badge variant="outline" className={`rounded-none text-[9px] px-1 py-0 cursor-default ${
                item.threat_trajectory === "ESCALATING"    ? "text-red-400 border-red-500/30" :
                item.threat_trajectory === "DE-ESCALATING" ? "text-green-400 border-green-500/30" :
                item.threat_trajectory === "NEW_THREAT"    ? "text-amber-400 border-amber-500/30" :
                "text-muted-foreground border-border"
              }`} data-testid="card-trajectory">
                {item.threat_trajectory === "ESCALATING"    ? "ESC" :
                 item.threat_trajectory === "DE-ESCALATING" ? "DE-ESC" :
                 item.threat_trajectory === "NEW_THREAT"    ? "NEW" :
                 item.threat_trajectory === "STABLE"        ? "STABLE" : ""}
              </Badge>
            </Tip>
          )}

          {/* Reprocess */}
          {api && (
            <Tip text="Re-run AI classification on this item (e.g. after severity rule changes)" side="left">
              <button
                onClick={handleReprocess}
                disabled={reprocessing}
                className="p-1 text-muted-foreground/40 hover:text-violet-400 transition-colors mt-0.5"
                data-testid={`reprocess-intel-${item.id}`}
              >
                <RefreshCw size={12} className={reprocessing ? "animate-spin text-violet-400" : ""} />
              </button>
            </Tip>
          )}

          {/* Delete */}
          {onDelete && (
            <Tip text="Permanently delete this intelligence item" side="left">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm("Delete this intelligence item? This cannot be undone.")) {
                    setDeleting(true);
                    onDelete(item.id);
                  }
                }}
                disabled={deleting}
                className="p-1 text-muted-foreground/40 hover:text-red-400 transition-colors mt-0.5"
                data-testid={`delete-intel-${item.id}`}
              >
                <Trash2 size={12} />
              </button>
            </Tip>
          )}
        </div>
      </div>

      {/* Feedback Widget - TOP of card */}
      {api && (
        <FeedbackWidget
          itemId={item.id}
          api={api}
          compact
          initialData={feedbackData}
        />
      )}

      {/* Fused Sources Panel */}
      {sourcesExpanded && item.cluster_sources && item.cluster_sources.length > 0 && (
        <div className="mb-2 p-2 bg-blue-500/5 border border-blue-500/20 rounded space-y-1 animate-slide-in" data-testid="cluster-sources-panel">
          <p className="text-[10px] uppercase tracking-widest text-blue-400 font-mono mb-1">
            Covered by {item.cluster_sources.length} sources
          </p>
          {item.cluster_sources.map((src, idx) => (
            <div key={idx} className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground font-mono shrink-0 w-4">{idx + 1}.</span>
              <span className="text-muted-foreground font-semibold shrink-0">{src.source}</span>
              {src.source_url ? (
                <a
                  href={src.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:underline truncate"
                  data-testid={`cluster-source-link-${idx}`}
                >
                  {src.title?.slice(0, 60) || "View"}
                  {src.title?.length > 60 ? "..." : ""}
                </a>
              ) : (
                <span className="text-muted-foreground truncate">{src.title?.slice(0, 60)}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tags - Enhanced with multi-label support */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        {item.state && (
          <Tip text={`Geographic region: ${item.state}. Click the NER map on the Dashboard to filter all intelligence by this state.`} side="bottom">
            <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0 cursor-default" data-testid="card-state">
              {item.state}
            </Badge>
          </Tip>
        )}
        {/* Show multiple tags if available */}
        {item.tags && item.tags.length > 0 ? (
          item.tags.slice(0, 3).map((tag, idx) => (
            <Tip key={idx} text={`AI-assigned tag: "${tag}". Tags classify the nature of the intelligence item for filtering and pattern detection.`} side="bottom">
              <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0 cursor-default">
                {tag}
              </Badge>
            </Tip>
          ))
        ) : item.threat_category && (
          <Tip text={`Threat category: ${item.threat_category}. AI-classified primary threat type used for filtering, pattern analysis and daily brief generation.`} side="bottom">
            <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0 cursor-default" data-testid="card-threat">
              {item.threat_category}
            </Badge>
          </Tip>
        )}
        {item.is_cross_border && (
          <Tip text="Cross-border indicator — the AI detected explicit references to movement, activity or actors crossing an international border. See the Cross-Border Watch page for full context." side="bottom">
            <Badge variant="outline" className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0 text-amber-400 border-amber-500/30 cursor-default">
              Cross-Border
            </Badge>
          </Tip>
        )}
        {/* Special Flags */}
        {item.special_flags && item.special_flags.map((flag, idx) => {
          const flagTooltips = {
            "PLA_PAKISTAN_PRESENCE":  "PLA/Pakistan Presence — AI detected indicators of Chinese PLA or Pakistani actors in the reporting area. High strategic significance.",
            "COORDINATED_NARRATIVE":  "Information Warfare — AI detected signs of coordinated or inorganic narrative amplification. Treat source credibility with extra scrutiny.",
            "DEMOGRAPHIC_TREND":      "Demographic Shift — item relates to population movement, migration or demographic change with long-term strategic implications.",
            "DUAL_USE_INFRA":         "Dual-Use Infrastructure — civilian infrastructure with potential military or strategic utility detected in this item.",
            "PATTERN_DETECTED":       "Pattern Alert — this item matches a recurring threat pattern previously identified by the Pattern Detection Engine.",
          };
          return (
            <Tip key={idx} text={flagTooltips[flag] || `Special flag: ${flag}`} side="bottom">
              <Badge className="rounded-none text-[10px] uppercase tracking-wider px-1.5 py-0 bg-red-500/20 text-red-400 border-red-500/30 cursor-default">
                {SPECIAL_FLAG_LABELS[flag] || flag}
              </Badge>
            </Tip>
          );
        })}
      </div>

      {/* Actors involved */}
      {item.actors && item.actors.length > 0 && (
        <Tip text={`Named actors identified by the AI: individuals, groups or organisations explicitly mentioned or implied as key participants in this event.`} side="top">
          <div className="flex items-center gap-1 mb-2 text-xs text-muted-foreground cursor-default">
            <Users size={10} />
            <span>Actors: {item.actors.slice(0, 3).join(", ")}</span>
          </div>
        </Tip>
      )}

      {/* Summary */}
      {item.ai_summary && (
        <p className="text-sm text-muted-foreground leading-relaxed mb-2" data-testid="card-summary">
          {compact ? item.ai_summary.slice(0, 150) + (item.ai_summary.length > 150 ? "..." : "") : item.ai_summary}
        </p>
      )}

      {/* Early Warning Signal */}
      {item.early_warning_signal && item.early_warning_signal !== "None identified" && (
        <Tip text="Early Warning Signal — AI-detected precursor indicator suggesting this event may be the leading edge of a larger or escalating threat pattern. Treat as an actionable flag." side="top">
          <div className="flex items-start gap-1.5 mb-2 p-2 bg-amber-500/10 border border-amber-500/20 rounded cursor-default">
            <TrendingUp size={12} className="text-amber-400 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-300">{item.early_warning_signal}</p>
          </div>
        </Tip>
      )}

      {/* Expandable section */}
      {!compact && (
        <>
          <Tip text="Expand to see AI analysis: why this matters, potential impact, named entities (persons, organisations, locations), countries involved, and a link to the original source." side="top">
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
          </Tip>

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
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Early Warning</p>
                  <p className="text-sm" data-testid="card-impact">{item.potential_impact}</p>
                </div>
              )}
              {item.countries_involved && item.countries_involved.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Countries Involved</p>
                  <p className="text-sm">{item.countries_involved.join(", ")}</p>
                </div>
              )}
              {item.entities && (item.entities.persons?.length > 0 || item.entities.organizations?.length > 0 || item.entities.locations?.length > 0) && (
                <div data-testid="card-entities">
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono mb-1">Named Entities</p>
                  <div className="flex flex-wrap gap-1">
                    {item.entities.persons?.map((p, i) => (
                      <Badge key={`p-${i}`} variant="outline" className="rounded-none text-[9px] px-1 py-0 text-blue-400 border-blue-500/30">
                        {p}
                      </Badge>
                    ))}
                    {item.entities.organizations?.map((o, i) => (
                      <Badge key={`o-${i}`} variant="outline" className="rounded-none text-[9px] px-1 py-0 text-purple-400 border-purple-500/30">
                        {o}
                      </Badge>
                    ))}
                    {item.entities.locations?.map((l, i) => (
                      <Badge key={`l-${i}`} variant="outline" className="rounded-none text-[9px] px-1 py-0 text-green-400 border-green-500/30">
                        {l}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {item.attention_level && (
                <Tip text="Attention Level — AI-recommended analyst response urgency: Immediate Action (act now), Priority Review (within hours), Routine Monitoring (next scheduled review), or Background Context (file for reference)." side="top">
                  <div className="flex items-center gap-2 cursor-default">
                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Attention:</p>
                    <span className={`text-sm font-semibold ${
                      item.attention_level.includes("Immediate") ? "text-red-400" :
                      item.attention_level.includes("Priority") ? "text-orange-400" : "text-primary"
                    }`} data-testid="card-attention">{item.attention_level}</span>
                  </div>
                </Tip>
              )}
              {/* Analyst Note display */}
              {enhancement?.analyst_note && !editingNote && (
                <div className="p-2.5 bg-violet-500/10 border border-violet-500/30 rounded space-y-1">
                  <p className="text-[10px] uppercase tracking-widest text-violet-400 font-mono">Analyst Note</p>
                  <p className="text-sm text-violet-100 leading-relaxed whitespace-pre-wrap">{enhancement.analyst_note}</p>
                  <p className="text-[10px] text-violet-400/60 font-mono">
                    {enhancement.enhanced_by_name} · {enhancement.enhanced_at ? new Date(enhancement.enhanced_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : ""}
                  </p>
                </div>
              )}

              {/* Inline editor */}
              {editingNote && (
                <div className="space-y-2">
                  <p className="text-[10px] uppercase tracking-widest text-violet-400 font-mono">Analyst Note</p>
                  <textarea
                    className="w-full min-h-[100px] p-2 text-sm bg-background border border-violet-500/40 rounded resize-y focus:outline-none focus:border-violet-400 text-foreground font-mono"
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Add your analysis, ground-truth corrections, or operational context here…"
                    maxLength={4000}
                  />
                  <div className="flex items-center gap-2 justify-between">
                    <span className="text-[10px] text-muted-foreground font-mono">{noteText.length}/4000</span>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingNote(false)}>
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 text-xs bg-violet-600 hover:bg-violet-500 text-white"
                        onClick={handleSaveNote}
                        disabled={savingNote || !noteText.trim()}
                      >
                        {savingNote ? "Saving…" : <><Check size={12} className="mr-1" /> Save</>}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Add enhancement button (only if not yet enhanced or currently no note) */}
              {canEnhance && api && !editingNote && !enhancement?.is_enhanced && (
                <button
                  onClick={() => { setEditingNote(true); setNoteText(""); }}
                  className="inline-flex items-center gap-1 text-xs text-violet-400/70 hover:text-violet-300 transition-colors"
                  data-testid="add-enhancement-btn"
                >
                  <Pencil size={11} /> Add analyst note
                </button>
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
