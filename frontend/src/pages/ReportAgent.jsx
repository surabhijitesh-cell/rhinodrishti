/**
 * ReportAgent — /report-agent route, admin-only.
 *
 * Chat-driven configurable intelligence report generation.
 * Left panel: conversation with the report configuration assistant.
 * Right panel: current spec preview + generate controls + past reports.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Navigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import {
  MessageSquare, Send, Sparkles, FileText, Download,
  Trash2, RefreshCw, ChevronDown, ChevronUp, Bot,
} from "lucide-react";

// ── PAOI label map ────────────────────────────────────────────────────────────
const PAOI_LABELS = {
  P1_india_bangladesh_border: "P1 · India-Bangladesh Border",
  P2_jem_radicalisation:      "P2 · JeI Spread & Radicalisation",
  P3_ner_loc:                 "P3 · NER Lines of Communication",
  P4_meghalaya_internal:      "P4 · Meghalaya Internal Security",
  P5_tribal_meg:              "P5 · Tribal Dynamics — Meghalaya",
};

const ALL_PAOI_IDS = Object.keys(PAOI_LABELS);

// ── Month helpers ─────────────────────────────────────────────────────────────
function currentYearMonth() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function monthLabel(year, month) {
  return new Date(year, month - 1, 1).toLocaleString("default", { month: "long", year: "numeric" });
}

// ── SpecCard ──────────────────────────────────────────────────────────────────
function SpecCard({ spec }) {
  if (!spec) return null;

  const {
    report_type, focus_paoi_ids, custom_focus_notes, recommendation_granularity,
    include_faultlines, commander_notes,
  } = spec;

  const focusPaois = focus_paoi_ids?.length
    ? focus_paoi_ids.map(id => PAOI_LABELS[id] || id)
    : ["All PAOIs"];

  return (
    <div className="rounded border border-border bg-background p-3 space-y-2 text-xs font-mono">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
        <Sparkles size={10} />
        Extracted Specification
      </div>

      <Row label="Report type"  value={(report_type || "fortnightly").toUpperCase()} />
      <Row label="PAOI focus"   value={focusPaois.join(", ")} />
      <Row label="Granularity"  value={recommendation_granularity || "operational"} />
      <Row label="Faultlines"   value={include_faultlines !== false ? "Yes" : "No"} />

      {custom_focus_notes && Object.keys(custom_focus_notes).length > 0 && (
        <div>
          <div className="text-muted-foreground mb-0.5">Custom focus:</div>
          {Object.entries(custom_focus_notes).map(([id, note]) => (
            <div key={id} className="ml-2 text-[10px] text-foreground">
              <span className="text-amber-400">{PAOI_LABELS[id] || id}: </span>
              {note}
            </div>
          ))}
        </div>
      )}

      {commander_notes && (
        <Row label="Commander emphasis" value={commander_notes} />
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex gap-2">
      <span className="text-muted-foreground w-32 shrink-0">{label}:</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

// ── PeriodSelector ────────────────────────────────────────────────────────────
function PeriodSelector({ reportType, value, onChange }) {
  const { year, month } = value;
  const months = Array.from({ length: 12 }, (_, i) => i + 1);
  const years = [currentYearMonth().year - 1, currentYearMonth().year];

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <select
        value={year}
        onChange={e => onChange({ ...value, year: Number(e.target.value) })}
        className="text-xs bg-background border border-border rounded px-2 py-1 font-mono"
      >
        {years.map(y => <option key={y} value={y}>{y}</option>)}
      </select>

      <select
        value={month}
        onChange={e => onChange({ ...value, month: Number(e.target.value) })}
        className="text-xs bg-background border border-border rounded px-2 py-1 font-mono"
      >
        {months.map(m => (
          <option key={m} value={m}>
            {new Date(year, m - 1, 1).toLocaleString("default", { month: "long" })}
          </option>
        ))}
      </select>

      {reportType === "fortnightly" && (
        <select
          value={value.period ?? 1}
          onChange={e => onChange({ ...value, period: Number(e.target.value) })}
          className="text-xs bg-background border border-border rounded px-2 py-1 font-mono"
        >
          <option value={1}>Period 1 (1-15)</option>
          <option value={2}>Period 2 (16-end)</option>
        </select>
      )}
    </div>
  );
}

// ── ReportRow ─────────────────────────────────────────────────────────────────
function ReportRow({ report, api }) {
  const [downloading, setDownloading] = useState(false);

  async function download() {
    setDownloading(true);
    try {
      const res = await axios.get(`${api}/report-agent/reports/${report.id}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `RDRISHTI_${report.period_label?.replace(/\s/g, "_")}_${report.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silent
    } finally {
      setDownloading(false);
    }
  }

  const rt = report.report_type === "monthly" ? "MONTHLY" : "FORTNIGHTLY";
  const dt = (report.generated_at || "")?.slice(0, 10);

  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
      <div>
        <div className="text-xs font-semibold">{report.period_label}</div>
        <div className="text-[10px] font-mono text-muted-foreground">{rt} · {dt}</div>
      </div>
      <button
        onClick={download}
        disabled={downloading}
        className="flex items-center gap-1.5 text-[10px] px-2 py-1 rounded bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white font-semibold transition-colors"
      >
        {downloading ? <RefreshCw size={10} className="animate-spin" /> : <Download size={10} />}
        PDF
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ReportAgent({ api }) {
  const { user } = useAuth();

  // All hooks must be called before any conditional return
  const [messages, setMessages]               = useState([]);
  const [input, setInput]                     = useState("");
  const [thinking, setThinking]               = useState(false);
  const [spec, setSpec]                       = useState(null);
  const [specId, setSpecId]                   = useState(null);
  const [period, setPeriod]                   = useState({ ...currentYearMonth(), period: 1 });
  const [generating, setGenerating]           = useState(false);
  const [generatedReport, setGeneratedReport] = useState(null);
  const [pastReports, setPastReports]         = useState([]);
  const [showPast, setShowPast]               = useState(false);
  const [savedSpecs, setSavedSpecs]           = useState([]);
  const [showSpecs, setShowSpecs]             = useState(false);
  const chatEndRef = useRef(null);

  const reportType = spec?.report_type || "fortnightly";

  // Scroll to bottom on new message
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const loadPastReports = useCallback(async () => {
    try {
      const r = await axios.get(`${api}/report-agent/reports`);
      setPastReports(r.data || []);
    } catch { /* silent */ }
  }, [api]);

  const loadSavedSpecs = useCallback(async () => {
    try {
      const r = await axios.get(`${api}/report-agent/specs`);
      setSavedSpecs(r.data || []);
    } catch { /* silent */ }
  }, [api]);

  useEffect(() => {
    loadPastReports();
    loadSavedSpecs();
  }, [loadPastReports, loadSavedSpecs]);

  if (user?.role !== "admin") return <Navigate to="/" replace />;

  async function sendMessage() {
    const text = input.trim();
    if (!text || thinking) return;

    const newMessages = [...messages, { role: "user", content: text }];
    setMessages(newMessages);
    setInput("");
    setThinking(true);

    try {
      const res = await axios.post(`${api}/report-agent/chat`, {
        messages: newMessages,
        spec_id: specId || undefined,
      });
      setMessages([...newMessages, { role: "assistant", content: res.data.reply }]);
      setSpec(res.data.spec);
      setSpecId(res.data.spec_id);
    } catch (e) {
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Sorry — could not reach the report assistant. Please try again." },
      ]);
    } finally {
      setThinking(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  async function generate() {
    if (!specId) return;
    setGenerating(true);
    setGeneratedReport(null);
    try {
      const res = await axios.post(`${api}/report-agent/generate`, {
        spec_id: specId,
        year: period.year,
        month: period.month,
        period: reportType === "fortnightly" ? (period.period ?? 1) : null,
      });
      setGeneratedReport(res.data);
      await loadPastReports();
    } catch (e) {
      alert(e?.response?.data?.detail || "Generation failed. Check the server logs.");
    } finally {
      setGenerating(false);
    }
  }

  async function downloadGenerated() {
    if (!generatedReport) return;
    try {
      const res = await axios.get(
        `${api}/report-agent/reports/${generatedReport.id}/pdf`,
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `RDRISHTI_${(generatedReport.period_label || "report").replace(/\s/g, "_")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
  }

  async function resetChat() {
    setMessages([]);
    setSpec(null);
    setSpecId(null);
    setGeneratedReport(null);
  }

  async function loadSpec(s) {
    try {
      const res = await axios.get(`${api}/report-agent/specs/${s.id}`);
      const full = res.data;
      setSpec(full);
      setSpecId(full.id);
      setMessages(full.conversation || []);
      setShowSpecs(false);
    } catch { /* silent */ }
  }

  async function deleteSpec(id) {
    await axios.delete(`${api}/report-agent/specs/${id}`);
    await loadSavedSpecs();
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-4">

      {/* ── Header ── */}
      <div className="flex items-center gap-3 border-b border-border pb-4">
        <Bot size={18} className="text-emerald-400" />
        <div>
          <h1 className="text-base font-semibold uppercase tracking-widest font-['Barlow_Condensed']">
            Report Generation Agent
          </h1>
          <p className="text-[10px] font-mono text-muted-foreground">
            Chat to configure · generate customized intelligence reports · admin only
          </p>
        </div>
        <button
          onClick={resetChat}
          title="Start a new session"
          className="ml-auto text-muted-foreground/50 hover:text-muted-foreground"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* ── LEFT: Chat panel ── */}
        <div className="lg:col-span-3 flex flex-col gap-3">

          {/* Chat window */}
          <div className="rounded border border-border bg-card flex flex-col" style={{ minHeight: 420 }}>
            <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ maxHeight: 480 }}>

              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-40 text-center">
                  <MessageSquare size={28} className="text-muted-foreground/30 mb-2" />
                  <p className="text-xs text-muted-foreground">
                    Tell me what you want in your next intelligence report.
                  </p>
                  <p className="text-[10px] text-muted-foreground/60 mt-1">
                    Example: "I want a fortnightly report focused on Bangladesh border infiltration, with very specific unit-level recommendations."
                  </p>
                </div>
              )}

              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded px-3 py-2 text-xs leading-relaxed ${
                      m.role === "user"
                        ? "bg-emerald-700/20 border border-emerald-700/30 text-foreground"
                        : "bg-muted/30 border border-border text-foreground"
                    }`}
                  >
                    {m.role === "assistant" && (
                      <div className="flex items-center gap-1 mb-1 text-[9px] text-emerald-400 font-semibold uppercase tracking-wider">
                        <Bot size={9} /> Assistant
                      </div>
                    )}
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  </div>
                </div>
              ))}

              {thinking && (
                <div className="flex justify-start">
                  <div className="bg-muted/30 border border-border rounded px-3 py-2 text-xs text-muted-foreground">
                    <span className="animate-pulse">Thinking…</span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Input bar */}
            <div className="border-t border-border p-2 flex gap-2">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Describe your report requirements… (Enter to send, Shift+Enter for newline)"
                rows={2}
                className="flex-1 text-xs bg-background border border-border rounded px-2 py-1.5 resize-none font-mono focus:outline-none focus:ring-1 focus:ring-emerald-600 text-foreground placeholder:text-muted-foreground"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || thinking}
                className="px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 text-white transition-colors self-end"
              >
                <Send size={13} />
              </button>
            </div>
          </div>

          {/* Saved specs accordion */}
          {savedSpecs.length > 0 && (
            <div className="rounded border border-border bg-card">
              <button
                onClick={() => setShowSpecs(v => !v)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-widest font-['Barlow_Condensed'] text-muted-foreground hover:text-foreground"
              >
                Saved Configurations ({savedSpecs.length})
                {showSpecs ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showSpecs && (
                <div className="px-3 pb-2 space-y-1">
                  {savedSpecs.map(s => (
                    <div key={s.id} className="flex items-center justify-between py-1 border-b border-border/40 last:border-0">
                      <div className="text-[10px] font-mono text-muted-foreground">
                        <span className="text-foreground font-semibold">
                          {(s.report_type || "?").toUpperCase()}
                        </span>
                        {" — "}
                        {(s.focus_paoi_ids?.length ? s.focus_paoi_ids.join(", ") : "All PAOIs")}
                        {" · "}
                        {(s.updated_at || "")?.slice(0, 10)}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => loadSpec(s)}
                          className="text-[10px] text-emerald-400 hover:text-emerald-300"
                        >
                          Load
                        </button>
                        <button
                          onClick={() => deleteSpec(s.id)}
                          className="text-[10px] text-red-400 hover:text-red-300"
                        >
                          <Trash2 size={9} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── RIGHT: Controls + spec + reports ── */}
        <div className="lg:col-span-2 space-y-3">

          {/* Spec preview */}
          <div className="rounded border border-border bg-card p-3 space-y-3">
            <div className="text-[10px] uppercase tracking-widest font-semibold font-['Barlow_Condensed'] text-muted-foreground">
              Current Specification
            </div>

            {spec ? (
              <SpecCard spec={spec} />
            ) : (
              <p className="text-[10px] font-mono text-muted-foreground italic">
                Chat with the assistant to build your report specification.
              </p>
            )}
          </div>

          {/* Generate controls */}
          {spec && (
            <div className="rounded border border-border bg-card p-3 space-y-3">
              <div className="text-[10px] uppercase tracking-widest font-semibold font-['Barlow_Condensed'] text-muted-foreground">
                Generate Report
              </div>

              <div>
                <div className="text-[10px] font-mono text-muted-foreground mb-1">Select period:</div>
                <PeriodSelector
                  reportType={reportType}
                  value={period}
                  onChange={setPeriod}
                />
              </div>

              <div className="text-[10px] font-mono text-muted-foreground">
                Will generate: <span className="text-foreground font-semibold">
                  {reportType === "fortnightly"
                    ? `Fortnightly · ${period.period === 2 ? `16-end` : `1-15`} ${monthLabel(period.year, period.month)}`
                    : `Monthly · ${monthLabel(period.year, period.month)}`
                  }
                </span>
              </div>

              <button
                onClick={generate}
                disabled={generating}
                className="w-full flex items-center justify-center gap-2 py-2 rounded bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white text-xs font-semibold transition-colors"
              >
                {generating ? (
                  <><RefreshCw size={12} className="animate-spin" /> Generating…</>
                ) : (
                  <><FileText size={12} /> Generate Report</>
                )}
              </button>

              {generating && (
                <p className="text-[10px] font-mono text-muted-foreground text-center">
                  Running PAOI synthesis — this takes 30-90 seconds…
                </p>
              )}
            </div>
          )}

          {/* Generated report download */}
          {generatedReport && (
            <div className="rounded border border-emerald-700/40 bg-emerald-950/30 p-3 space-y-2">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                <FileText size={12} />
                Report Ready
              </div>
              <div className="text-[10px] font-mono text-muted-foreground">
                {generatedReport.period_label} · {(generatedReport.generated_at || "")?.slice(0, 10)}
              </div>
              <div className="text-[10px] font-mono text-muted-foreground">
                {generatedReport.paoi_reports?.length || 0} PAOIs analysed
              </div>
              <button
                onClick={downloadGenerated}
                className="w-full flex items-center justify-center gap-2 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold transition-colors"
              >
                <Download size={11} /> Download PDF
              </button>
            </div>
          )}

          {/* Past reports */}
          {pastReports.length > 0 && (
            <div className="rounded border border-border bg-card p-3 space-y-2">
              <button
                onClick={() => setShowPast(v => !v)}
                className="w-full flex items-center justify-between text-[10px] uppercase tracking-widest font-semibold font-['Barlow_Condensed'] text-muted-foreground hover:text-foreground"
              >
                Past Reports ({pastReports.length})
                {showPast ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
              </button>
              {showPast && (
                <div>
                  {pastReports.slice(0, 10).map(r => (
                    <ReportRow key={r.id} report={r} api={api} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
