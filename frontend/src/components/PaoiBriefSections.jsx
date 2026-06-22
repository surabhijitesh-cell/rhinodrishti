import { Target, Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const CONCERN_COLOR = {
  CRITICAL: "#ef4444", ELEVATED: "#f59e0b", MONITOR: "#eab308", STABLE: "#a3e635",
};

// Format [CONFIRMED]/[ASSESSED]/[SPECULATIVE] claim labels with color chips.
function renderLabeledText(text) {
  if (!text) return null;
  const str = typeof text === "string" ? text : String(text);
  const parts = str.split(/(\[(?:CONFIRMED|ASSESSED|SPECULATIVE)\])/g);
  return parts.map((p, i) => {
    if (p === "[CONFIRMED]")   return <span key={i} className="inline-block text-[8px] font-mono px-1 py-px ml-0.5 mr-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/40 align-middle">CONFIRMED</span>;
    if (p === "[ASSESSED]")    return <span key={i} className="inline-block text-[8px] font-mono px-1 py-px ml-0.5 mr-0.5 bg-amber-500/15  text-amber-400  border border-amber-500/40  align-middle">ASSESSED</span>;
    if (p === "[SPECULATIVE]") return <span key={i} className="inline-block text-[8px] font-mono px-1 py-px ml-0.5 mr-0.5 bg-cyan-500/15   text-cyan-400   border border-cyan-500/40   align-middle">SPECULATIVE</span>;
    return <span key={i}>{p}</span>;
  });
}

const trendIcon = (t) => (t === "RISING" ? "▲" : t === "FALLING" ? "▼" : "▬");
const trendColor = (t) => (t === "RISING" ? "#ef4444" : t === "FALLING" ? "#a3e635" : "#888");

/**
 * Commander's Priority Dashboard — top-of-brief PAOI status table + bottom line.
 * @param {{ paoiAnalysis: object }} props
 */
export function CommanderDashboard({ paoiAnalysis }) {
  if (!paoiAnalysis || !paoiAnalysis.available) return null;
  const rows = paoiAnalysis.commander_dashboard || [];
  const overall = paoiAnalysis.synthesis?.overall || {};

  return (
    <Card className="border-2 border-red-500/40 rounded-none bg-red-950/10" data-testid="commander-dashboard">
      <CardHeader className="py-3 px-4 border-b border-red-500/30">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2 text-red-400">
          <Target size={16} /> Commander's Priority Dashboard
          {paoiAnalysis.synthesis_tier && (
            <span className="ml-auto text-[9px] font-mono text-muted-foreground normal-case">
              {paoiAnalysis.synthesis_tier} synthesis
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-3">
        <div className="grid grid-cols-1 gap-2">
          {rows.map((r) => (
            <div key={r.id} className="flex items-center gap-3 border border-border p-2 bg-background" data-testid={`paoi-row-${r.id}`}>
              <span className="text-[10px] font-mono text-muted-foreground w-6">P{r.rank}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-tight">{r.name}</p>
                <p className="text-[10px] text-muted-foreground font-mono truncate">{r.what_changed}</p>
              </div>
              <span className="text-xs font-mono" style={{ color: trendColor(r.trend) }}>
                {trendIcon(r.trend)} {r.delta > 0 ? "+" : ""}{Math.round(r.delta)}
              </span>
              <span className="text-2xl font-bold font-['Barlow_Condensed'] w-12 text-right" style={{ color: CONCERN_COLOR[r.level] }}>
                {r.score != null ? Math.round(r.score) : "—"}
              </span>
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 w-20 text-center"
                    style={{ background: `${CONCERN_COLOR[r.level]}22`, color: CONCERN_COLOR[r.level], border: `1px solid ${CONCERN_COLOR[r.level]}55` }}>
                {r.level}
              </span>
            </div>
          ))}
        </div>
        {overall.bottom_line && (
          <div className="border-t border-red-500/20 pt-3">
            <div className="text-[10px] font-mono uppercase tracking-wider text-red-400 mb-1">Bottom Line</div>
            <p className="text-sm leading-relaxed">{renderLabeledText(overall.bottom_line)}</p>
          </div>
        )}
        {Array.isArray(overall.top_3_focus_next) && overall.top_3_focus_next.length > 0 && (
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-amber-400 mb-1">Focus Next Period</div>
            <ul className="space-y-1">
              {overall.top_3_focus_next.map((f, i) => (
                <li key={i} className="text-xs flex items-start gap-2">
                  <span className="text-amber-400">{i + 1}.</span>
                  <span>{typeof f === "string" ? f : String(f)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Priority Area Deep-Dives — per-PAOI faultline bars + narrative + other movements.
 * @param {{ paoiAnalysis: object }} props
 */
export function PaoiDeepDives({ paoiAnalysis }) {
  if (!paoiAnalysis || !paoiAnalysis.available) return null;
  const paois = paoiAnalysis.paois || [];
  const per = paoiAnalysis.synthesis?.per_paoi || {};
  const other = paoiAnalysis.other_movements || {};

  return (
    <Card className="border border-border rounded-none bg-card" data-testid="paoi-deepdives">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Layers size={16} className="text-primary" /> Priority Area Deep-Dives
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {paois.map((p) => {
          const mv = p.faultline_movement || {};
          const syn = per[p.id] || {};
          return (
            <div key={p.id} className="border border-red-500/30 bg-red-950/10 p-3" data-testid={`deepdive-${p.id}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold flex items-center gap-2">
                  <span className="text-[10px] font-mono text-muted-foreground">P{p.rank}</span>
                  {p.name}
                </span>
                {mv.last != null && (
                  <span className="text-xl font-bold font-['Barlow_Condensed']" style={{ color: CONCERN_COLOR[mv.level] }}>
                    {Math.round(mv.last)}
                  </span>
                )}
              </div>

              {Array.isArray(mv.per_faultline) && mv.per_faultline.length > 0 && (
                <div className="space-y-1 mb-2">
                  {mv.per_faultline.slice(0, 5).map((f) => (
                    <div key={f.id} className="flex items-center gap-2 text-[11px] font-mono">
                      <span className="w-44 truncate text-muted-foreground">{f.name}</span>
                      <div className="flex-1 h-1.5 bg-muted/30">
                        <div className="h-full" style={{ width: `${Math.min(100, f.last)}%`, background: CONCERN_COLOR[f.level] }} />
                      </div>
                      <span className="w-8 text-right">{Math.round(f.last)}</span>
                      <span className="w-10 text-right" style={{ color: f.delta > 0 ? "#ef4444" : f.delta < 0 ? "#a3e635" : "#888" }}>
                        {f.delta > 0 ? "+" : ""}{Math.round(f.delta)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {syn.situation_overview ? (
                <div className="space-y-2 mt-1">
                  <div className="bg-emerald-950/30 border border-emerald-500/20 px-3 py-2">
                    <p className="text-[9px] font-mono uppercase tracking-wider text-emerald-400 mb-1">A. Situation Overview</p>
                    <p className="text-sm leading-relaxed">{renderLabeledText(syn.situation_overview)}</p>
                  </div>
                  {Array.isArray(syn.events) && syn.events.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-[9px] font-mono uppercase tracking-wider text-blue-400">B. Key Events</p>
                      {syn.events.map((ev, i) => (
                        <div key={i} className="border border-border bg-background px-3 py-2">
                          <div className="flex items-start gap-2 mb-1">
                            <span className="text-[9px] font-mono text-muted-foreground mt-0.5 shrink-0">{ev.location || ""}</span>
                            <p className="text-xs font-semibold leading-tight">{ev.heading}</p>
                          </div>
                          {ev.what_happened && (
                            <p className="text-[11px] leading-relaxed mb-0.5">{renderLabeledText(ev.what_happened)}</p>
                          )}
                          {ev.why_it_matters && (
                            <p className="text-[11px] text-amber-300/80 leading-relaxed">
                              <span className="text-[9px] font-mono text-amber-400 uppercase">Why: </span>
                              {renderLabeledText(ev.why_it_matters)}
                            </p>
                          )}
                          {ev.linkages && (
                            <p className="text-[10px] text-cyan-300/70 mt-0.5">
                              <span className="text-[9px] font-mono text-cyan-400 uppercase">Links: </span>
                              {ev.linkages}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {syn.overall_assessment && (
                    <div className="bg-amber-950/20 border border-amber-500/20 px-3 py-2">
                      <p className="text-[9px] font-mono uppercase tracking-wider text-amber-400 mb-1">C. Overall Assessment</p>
                      <p className="text-sm leading-relaxed">{renderLabeledText(syn.overall_assessment)}</p>
                      {syn.risk_trajectory && (
                        <p className="text-[10px] font-mono text-muted-foreground mt-1">
                          Trajectory: <span className="text-amber-300">{syn.risk_trajectory}</span>
                        </p>
                      )}
                    </div>
                  )}
                  {Array.isArray(syn.commander_focus) && syn.commander_focus.length > 0 && (
                    <div className="bg-red-950/20 border border-red-500/20 px-3 py-2">
                      <p className="text-[9px] font-mono uppercase tracking-wider text-red-400 mb-1">D. Commander Focus</p>
                      <ul className="space-y-0.5">
                        {syn.commander_focus.map((item, i) => (
                          <li key={i} className="text-xs flex gap-2">
                            <span className="text-red-400 shrink-0">▸</span>
                            <span>{renderLabeledText(item)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {syn.period_impact && (
                    <p className="text-sm leading-relaxed mb-1">{renderLabeledText(syn.period_impact)}</p>
                  )}
                  {syn.forward_concerns && (
                    <p className="text-xs text-amber-300/90 mb-1">
                      <span className="uppercase tracking-wider font-mono text-[9px] text-amber-400">Watch next: </span>
                      {renderLabeledText(syn.forward_concerns)}
                    </p>
                  )}
                  {syn.manual_review && (
                    <p className="text-[11px] text-muted-foreground italic pt-1 border-t border-border mt-1">
                      <span className="uppercase tracking-wider font-mono text-[9px] text-cyan-400">Manual review: </span>
                      {typeof syn.manual_review === "string" ? syn.manual_review : String(syn.manual_review)}
                    </p>
                  )}
                </>
              )}

              {p.keyword_hits?.n_articles > 0 && (
                <div className="mt-2 text-[10px] text-muted-foreground font-mono">
                  {p.keyword_hits.n_articles} related reports · {(p.actors_of_interest || []).slice(0, 4).join(", ")}
                </div>
              )}
            </div>
          );
        })}

        {(other.rising?.length > 0 || other.declining?.length > 0) && (
          <div className="border border-border p-3">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
              Other Faultline Movements (outside priority areas)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {other.rising?.length > 0 && (
                <div>
                  <div className="text-[10px] text-red-400 font-mono mb-1">Rising</div>
                  {other.rising.slice(0, 6).map((f) => (
                    <div key={f.id} className="flex items-center gap-2 text-[11px]">
                      <span className="text-muted-foreground w-16 truncate">[{f.state}]</span>
                      <span className="flex-1 truncate">{f.name}</span>
                      <span className="text-red-400">+{Math.round(f.delta)}</span>
                    </div>
                  ))}
                </div>
              )}
              {other.declining?.length > 0 && (
                <div>
                  <div className="text-[10px] text-green-400 font-mono mb-1">Declining</div>
                  {other.declining.slice(0, 6).map((f) => (
                    <div key={f.id} className="flex items-center gap-2 text-[11px]">
                      <span className="text-muted-foreground w-16 truncate">[{f.state}]</span>
                      <span className="flex-1 truncate">{f.name}</span>
                      <span className="text-green-400">{Math.round(f.delta)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
