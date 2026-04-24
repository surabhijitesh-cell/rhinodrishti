import { useState } from "react";
import {
  FileText, MapPin, Globe, SlidersHorizontal, Loader2, FileDown,
  Calendar, Shield, Target, Search
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import axios from "axios";

const NER_STATES = [
  "Assam", "Manipur", "Meghalaya", "Mizoram", "Tripura",
  "Nagaland", "Arunachal Pradesh", "Sikkim",
];

const THREAT_TYPES = [
  "Military Movement", "Insurgency/Militancy", "Drug Trafficking", "Arms Smuggling",
  "Border Incursion", "Ethnic/Tribal Tension", "Political Instability", "Cyber Threat",
  "Infrastructure/Strategic", "Cross-border Crime", "Ceasefire Violation",
  "Counter-terrorism Ops", "Diplomatic Tension", "Immigration/Refugees",
];

const SEVERITIES = ["critical", "high", "medium"];

function downloadBlob(data, filename) {
  const url = window.URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}


function ReportCard({ icon: Icon, title, description, color, children, testId }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card className={`border border-border rounded-none bg-card ${expanded ? `border-l-4 border-l-${color}` : ""}`} data-testid={testId}>
      <CardHeader className="py-3 px-4 border-b border-border cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Icon size={16} className={`text-${color}`} />
          {title}
          <Badge className={`rounded-none text-[8px] px-1.5 py-0 ml-auto ${expanded ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
            {expanded ? "OPEN" : "CLICK TO CONFIGURE"}
          </Badge>
        </CardTitle>
        {!expanded && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
      </CardHeader>
      {expanded && <CardContent className="p-4">{children}</CardContent>}
    </Card>
  );
}


function RegionalThreatReport({ api }) {
  const [region, setRegion] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    if (!region) { toast.error("Select a region"); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams({ region });
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
      const res = await axios.get(`${api}/reports/regional-threat?${params}`, { responseType: "blob" });
      downloadBlob(res.data, `${region}_Threat_Report.pdf`);
      toast.success("Regional Threat Report downloaded");
    } catch (e) {
      toast.error(e.response?.status === 404 ? "No data for selected region/period" : "Report generation failed");
    }
    setLoading(false);
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Region *</label>
          <Select value={region} onValueChange={setRegion}>
            <SelectTrigger className="rounded-none" data-testid="regional-region"><SelectValue placeholder="Select State" /></SelectTrigger>
            <SelectContent className="rounded-none">
              {NER_STATES.map((s) => <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">From Date</label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50" data-testid="regional-from" />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">To Date</label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50" data-testid="regional-to" />
        </div>
      </div>
      <Button onClick={generate} disabled={loading || !region} className="rounded-none uppercase text-xs font-bold tracking-wider" data-testid="regional-generate">
        {loading ? <Loader2 size={12} className="mr-2 animate-spin" /> : <FileDown size={12} className="mr-2" />}
        Generate Regional Threat Report
      </Button>
    </div>
  );
}


function CrossBorderSitrep({ api }) {
  const [country, setCountry] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    if (!country) { toast.error("Select a country"); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams({ country });
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
      const res = await axios.get(`${api}/reports/cross-border-sitrep?${params}`, { responseType: "blob" });
      downloadBlob(res.data, `${country}_SITREP.pdf`);
      toast.success("Cross-Border SITREP downloaded");
    } catch (e) {
      toast.error(e.response?.status === 404 ? "No cross-border data for selected period" : "Report generation failed");
    }
    setLoading(false);
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Country *</label>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger className="rounded-none" data-testid="sitrep-country"><SelectValue placeholder="Select Country" /></SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="Bangladesh" className="text-xs">Bangladesh</SelectItem>
              <SelectItem value="Myanmar" className="text-xs">Myanmar</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">From Date</label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50" data-testid="sitrep-from" />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">To Date</label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50" data-testid="sitrep-to" />
        </div>
      </div>
      <Button onClick={generate} disabled={loading || !country} className="rounded-none uppercase text-xs font-bold tracking-wider" data-testid="sitrep-generate">
        {loading ? <Loader2 size={12} className="mr-2 animate-spin" /> : <FileDown size={12} className="mr-2" />}
        Generate Cross-Border SITREP
      </Button>
    </div>
  );
}


function CustomReport({ api }) {
  const [title, setTitle] = useState("Custom Intelligence Report");
  const [region, setRegion] = useState("");
  const [threat, setThreat] = useState("");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [minPriority, setMinPriority] = useState("");
  const [crossBorder, setCrossBorder] = useState("");
  const [source, setSource] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (title) params.set("title", title);
      if (region) params.set("state", region);
      if (threat) params.set("threat_type", threat);
      if (severity) params.set("severity", severity);
      if (search) params.set("search", search);
      if (minPriority) params.set("min_priority", minPriority);
      if (crossBorder === "yes") params.set("is_cross_border", "true");
      if (source) params.set("source", source);
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
      const res = await axios.get(`${api}/reports/custom?${params}`, { responseType: "blob" });
      downloadBlob(res.data, `${title.replace(/\s+/g, '_')}.pdf`);
      toast.success("Custom report downloaded");
    } catch (e) {
      toast.error(e.response?.status === 404 ? "No items match the selected filters" : "Report generation failed");
    }
    setLoading(false);
  };

  return (
    <div className="space-y-3">
      <div>
        <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Report Title</label>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} className="rounded-none text-sm" data-testid="custom-title" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Region</label>
          <Select value={region || "all"} onValueChange={(v) => setRegion(v === "all" ? "" : v)}>
            <SelectTrigger className="rounded-none text-xs" data-testid="custom-region"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All Regions</SelectItem>
              {[...NER_STATES, "Bangladesh", "Myanmar", "India"].map((s) => <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Threat Category</label>
          <Select value={threat || "all"} onValueChange={(v) => setThreat(v === "all" ? "" : v)}>
            <SelectTrigger className="rounded-none text-xs" data-testid="custom-threat"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent className="rounded-none max-h-48">
              <SelectItem value="all" className="text-xs">All Threats</SelectItem>
              {THREAT_TYPES.map((t) => <SelectItem key={t} value={t} className="text-xs">{t}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Severity</label>
          <Select value={severity || "all"} onValueChange={(v) => setSeverity(v === "all" ? "" : v)}>
            <SelectTrigger className="rounded-none text-xs" data-testid="custom-severity"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All</SelectItem>
              {SEVERITIES.map((s) => <SelectItem key={s} value={s} className="text-xs uppercase">{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Min Priority</label>
          <Select value={minPriority || "all"} onValueChange={(v) => setMinPriority(v === "all" ? "" : v)}>
            <SelectTrigger className="rounded-none text-xs" data-testid="custom-priority"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all" className="text-xs">All</SelectItem>
              <SelectItem value="80" className="text-xs">80+ Critical</SelectItem>
              <SelectItem value="60" className="text-xs">60+ High</SelectItem>
              <SelectItem value="40" className="text-xs">40+ Medium</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Search Keywords</label>
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. ULFA, arms" className="rounded-none text-xs" data-testid="custom-search" />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Source Name</label>
          <Input value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. NDTV, NE Now" className="rounded-none text-xs" data-testid="custom-source" />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">From Date</label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50" data-testid="custom-from" />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">To Date</label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-none text-xs [&::-webkit-calendar-picker-indicator]:invert [&::-webkit-calendar-picker-indicator]:opacity-50" data-testid="custom-to" />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={crossBorder === "yes"} onChange={(e) => setCrossBorder(e.target.checked ? "yes" : "")} className="w-3.5 h-3.5 accent-primary" />
          <span className="text-[10px] font-mono uppercase text-muted-foreground">Cross-Border Only</span>
        </label>
      </div>
      <Button onClick={generate} disabled={loading} className="rounded-none uppercase text-xs font-bold tracking-wider" data-testid="custom-generate">
        {loading ? <Loader2 size={12} className="mr-2 animate-spin" /> : <FileDown size={12} className="mr-2" />}
        Generate Custom Report
      </Button>
    </div>
  );
}


export default function ReportsPage({ api }) {
  return (
    <div className="space-y-4" data-testid="reports-page">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">
          Intelligence Reports
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Generate PDF reports from archived intelligence data
        </p>
      </div>

      <ReportCard
        icon={MapPin} title="Regional Threat Summary" color="primary"
        description="Generate a threat assessment for a specific NER state with severity breakdown and categorized items"
        testId="regional-report-card"
      >
        <RegionalThreatReport api={api} />
      </ReportCard>

      <ReportCard
        icon={Globe} title="Cross-Border SITREP" color="amber-400"
        description="Situation report for Bangladesh or Myanmar border — grouped by Diplomatic, Defence, Politics, Economics"
        testId="sitrep-report-card"
      >
        <CrossBorderSitrep api={api} />
      </ReportCard>

      <ReportCard
        icon={SlidersHorizontal} title="Custom Filtered Report" color="cyan-400"
        description="Build a custom report with any combination of region, threat, severity, source, date range, and keywords"
        testId="custom-report-card"
      >
        <CustomReport api={api} />
      </ReportCard>
    </div>
  );
}
