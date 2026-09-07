import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Download, Circle } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Badge } from "./ui/badge";

function downloadBlob(data, filename) {
  const url = window.URL.createObjectURL(new Blob([data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function lastCompletedWeek() {
  const today = new Date();
  const day = today.getDay(); // 0=Sun..6=Sat
  const daysSinceMonday = (day + 6) % 7;
  const thisMonday = new Date(today);
  thisMonday.setDate(today.getDate() - daysSinceMonday);
  const lastMonday = new Date(thisMonday);
  lastMonday.setDate(thisMonday.getDate() - 7);
  const lastSunday = new Date(thisMonday);
  lastSunday.setDate(thisMonday.getDate() - 1);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { from: fmt(lastMonday), to: fmt(lastSunday) };
}

function OnlineUsers({ api }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchOnline = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/admin/user-activity/online`);
      setSessions(res.data.sessions || []);
    } catch {
      /* silent — non-critical polling */
    }
    setLoading(false);
  }, [api]);

  useEffect(() => {
    fetchOnline();
    const t = setInterval(fetchOnline, 20000);
    return () => clearInterval(t);
  }, [fetchOnline]);

  return (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          Currently Online
          <Badge className="text-[9px] font-mono bg-muted/40 text-muted-foreground border-border px-1.5 py-0">
            {sessions.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {loading ? (
          <p className="text-xs text-muted-foreground">Loading…</p>
        ) : sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground">No one currently active.</p>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <div key={s.id} className="flex items-center justify-between text-xs border-b border-border/50 pb-2 last:border-0">
                <div className="flex items-center gap-2">
                  <Circle
                    size={8}
                    className={s.status === "online" ? "fill-emerald-400 text-emerald-400" : "fill-amber-400 text-amber-400"}
                  />
                  <span className="font-mono font-semibold">{s.username}</span>
                  <Badge className="text-[9px] font-mono bg-muted/30 text-muted-foreground border-border px-1 py-0">
                    {s.role}
                  </Badge>
                </div>
                <span className="text-muted-foreground font-mono">
                  {s.status === "online" ? "active now" : "away"} · last seen {new Date(s.last_activity_at).toLocaleTimeString("en-IN")}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ActivityReport({ api }) {
  const defaults = lastCompletedWeek();
  const [dateFrom, setDateFrom] = useState(defaults.from);
  const [dateTo, setDateTo] = useState(defaults.to);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  const generate = async () => {
    if (!dateFrom || !dateTo) { toast.error("Pick both dates"); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${api}/admin/user-activity/report`, {
        params: { date_from: dateFrom, date_to: dateTo },
      });
      setReport(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Report generation failed");
    }
    setLoading(false);
  };

  const downloadPdf = async () => {
    setPdfLoading(true);
    try {
      const res = await axios.get(`${api}/admin/user-activity/report/pdf`, {
        params: { date_from: dateFrom, date_to: dateTo },
        responseType: "blob",
      });
      downloadBlob(res.data, `user_activity_${dateFrom}_to_${dateTo}.pdf`);
    } catch {
      toast.error("PDF download failed");
    }
    setPdfLoading(false);
  };

  return (
    <Card className="border border-border rounded-none bg-card">
      <CardHeader className="py-3 px-4 border-b border-border">
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold">
          Activity Report
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">From</label>
            <Input
              type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
              className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50"
              data-testid="activity-report-from"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">To</label>
            <Input
              type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
              className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50"
              data-testid="activity-report-to"
            />
          </div>
          <Button onClick={generate} disabled={loading} size="sm" className="rounded-none text-xs uppercase tracking-wider" data-testid="generate-activity-report-btn">
            <RefreshCw size={12} className={`mr-1 ${loading ? "animate-spin" : ""}`} />
            Generate
          </Button>
          {report && (
            <Button onClick={downloadPdf} disabled={pdfLoading} variant="outline" size="sm" className="rounded-none text-xs uppercase tracking-wider" data-testid="download-activity-report-btn">
              <Download size={12} className="mr-1" />
              {pdfLoading ? "Preparing…" : "PDF"}
            </Button>
          )}
        </div>

        {report && (
          report.users.length === 0 ? (
            <p className="text-xs text-muted-foreground">No user activity recorded in this period.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground font-mono text-left">
                    <th className="py-1.5 pr-3">Username</th>
                    <th className="py-1.5 pr-3">Logins</th>
                    <th className="py-1.5 pr-3">Total Active (min)</th>
                    <th className="py-1.5 pr-3">Ratings</th>
                    <th className="py-1.5 pr-3">Uploads</th>
                    <th className="py-1.5 pr-3">Training</th>
                  </tr>
                </thead>
                <tbody>
                  {report.users.map((u) => (
                    <tr key={u.username} className="border-b border-border/50 font-mono">
                      <td className="py-1.5 pr-3 font-semibold">{u.username}</td>
                      <td className="py-1.5 pr-3">{u.login_count}</td>
                      <td className="py-1.5 pr-3">
                        {u.sessions.reduce((sum, s) => sum + s.duration_minutes, 0).toFixed(1)}
                      </td>
                      <td className="py-1.5 pr-3">{u.relevance_ratings_given}</td>
                      <td className="py-1.5 pr-3">{u.manual_uploads}</td>
                      <td className="py-1.5 pr-3">{u.training_actions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </CardContent>
    </Card>
  );
}

export default function UserActivityTab({ api }) {
  return (
    <div className="space-y-4">
      <OnlineUsers api={api} />
      <ActivityReport api={api} />
    </div>
  );
}
