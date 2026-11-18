import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { FileText, Download, ChevronRight, AlertTriangle, RefreshCw } from "lucide-react";
import { downloadPdf } from "../lib/downloadPdf";

const KIND_LABEL = { daily: "Daily", fortnightly: "Fortnightly", monthly: "Monthly", custom: "Custom" };
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const pad = (n) => String(n).padStart(2, "0");
const asList = (d) => (Array.isArray(d) ? d : d?.briefs || []);

// Sort key is the END of the period so a month sorts after its own fortnights.
function toRow(kind, b) {
  if (kind === "daily") {
    return { kind, key: `${b.date}-0`, title: `Daily brief, ${b.date}`, generated_at: b.generated_at, open: { date: b.date } };
  }
  if (kind === "fortnightly") {
    const last = b.period === 1 ? "15" : "31";
    return {
      kind, key: `${b.year}-${pad(b.month)}-${last}-1`,
      title: b.period_label || `${b.period === 1 ? "1-15" : "16-end"} ${MONTHS[b.month - 1]} ${b.year}`,
      generated_at: b.generated_at, status: b.status,
      open: { year: b.year, month: b.month, period: b.period },
    };
  }
  if (kind === "monthly") {
    return {
      kind, key: `${b.year}-${pad(b.month)}-31-2`, title: `${MONTHS[b.month - 1]} ${b.year}`,
      generated_at: b.generated_at, status: b.status, open: { year: b.year, month: b.month },
    };
  }
  return {
    kind, key: `${String(b.generated_at || "").slice(0, 10)}-9`, title: b.title || b.period_label || "Custom brief",
    generated_at: b.generated_at, id: b.id,
  };
}

const SOURCES = (api, iod, isAdmin) => [
  { kind: "daily", label: "Daily briefs", url: `${api}/daily-brief/list`, params: { limit: 60, iod } },
  { kind: "fortnightly", label: "Fortnightly briefs", url: `${api}/brief/fortnightly/list`, params: { iod } },
  { kind: "monthly", label: "Monthly briefs", url: `${api}/brief/monthly/list`, params: { iod } },
  ...(isAdmin ? [{ kind: "custom", label: "Custom briefs", url: `${api}/report-agent/reports`, params: { limit: 30, skip: 0 } }] : []),
];

function fmtIst(iso) {
  if (!iso) return "";
  const s = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(s);
  if (isNaN(d)) return "";
  return `${d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" })} IST`;
}

/**
 * One newest-first list of every stored brief for the viewed IOD.
 * onOpen(kind, params) takes the user to that brief on its own tab.
 */
export default function PastBriefs({ api, iod, isAdmin, onOpen }) {
  const [rows, setRows] = useState([]);
  const [failed, setFailed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [pdfError, setPdfError] = useState(null);

  const load = useCallback(async (isCurrent) => {
    setLoading(true);
    const sources = SOURCES(api, iod, isAdmin);
    const results = await Promise.allSettled(sources.map((s) => axios.get(s.url, { params: s.params })));
    if (!isCurrent()) return;
    const bad = [];
    const all = [];
    results.forEach((r, i) => {
      if (r.status === "fulfilled") asList(r.value.data).forEach((b) => all.push(toRow(sources[i].kind, b)));
      else bad.push(sources[i].label);
    });
    all.sort((a, b) => (a.key < b.key ? 1 : a.key > b.key ? -1 : 0));
    setRows(all);
    setFailed(bad);
    setLoading(false);
  }, [api, iod, isAdmin]);

  useEffect(() => {
    let current = true;
    load(() => current);
    return () => { current = false; };
  }, [load]);

  const downloadCustom = async (row) => {
    setBusyId(row.id);
    setPdfError(null);
    const res = await downloadPdf(axios, `${api}/report-agent/reports/${row.id}/pdf`, `custom_brief_${row.id}.pdf`);
    setBusyId(null);
    if (!res.ok) setPdfError(`Could not download that brief: ${res.error}`);
  };

  return (
    <div className="space-y-4" data-testid="past-briefs">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">Past Briefs</h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Every stored brief for {iod}, newest first
        </p>
      </div>

      {failed.length > 0 && (
        <div className="flex items-center gap-3 p-3 border border-amber-500/40 bg-amber-500/5 text-amber-400" role="alert" data-testid="past-briefs-partial">
          <AlertTriangle size={14} className="shrink-0" />
          <span className="text-xs">
            Could not load: {failed.join(", ")}. The list below is incomplete, not empty.
          </span>
          <button
            onClick={() => load(() => true)}
            className="ml-auto inline-flex items-center gap-1 text-[10px] font-mono uppercase border border-amber-500/40 px-2 py-1 hover:bg-amber-500/10"
          >
            <RefreshCw size={10} /> Retry
          </button>
        </div>
      )}
      {pdfError && <p className="text-xs text-red-400 font-mono">{pdfError}</p>}

      {loading ? (
        <div className="border border-border bg-card p-8 text-center text-muted-foreground text-xs font-mono">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          {failed.length ? "Nothing could be loaded." : "No briefs have been generated yet."}
        </div>
      ) : (
        <ul className="border border-border bg-card divide-y divide-border">
          {rows.map((r) => (
            <li key={`${r.kind}-${r.key}-${r.id || ""}`}>
              <button
                type="button"
                onClick={() => (r.kind === "custom" ? downloadCustom(r) : onOpen(r.kind, r.open))}
                disabled={busyId === r.id && r.kind === "custom"}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/40"
              >
                <FileText size={14} className="text-primary shrink-0" />
                <span className="text-[10px] font-mono uppercase tracking-wider w-24 shrink-0 text-muted-foreground">{KIND_LABEL[r.kind]}</span>
                <span className="text-sm flex-1">{r.title}</span>
                {r.status && r.status !== "ready" && (
                  <span className="text-[10px] font-mono uppercase text-amber-400">{r.status === "partial" ? "Incomplete" : r.status}</span>
                )}
                <span className="text-[10px] font-mono text-muted-foreground hidden md:inline">{fmtIst(r.generated_at)}</span>
                {r.kind === "custom" ? <Download size={14} className="shrink-0" /> : <ChevronRight size={14} className="shrink-0" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
