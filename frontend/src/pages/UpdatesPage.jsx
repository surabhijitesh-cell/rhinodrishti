import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Bell, Plus, Eye, Shield, Clock, ChevronDown,
  Loader2, AlertTriangle, Megaphone
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";

export default function UpdatesPage({ api }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [updates, setUpdates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(null);

  const fetchUpdates = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/app/updates/all`);
      setUpdates(res.data.updates || []);
    } catch (e) {
      console.error("Failed to fetch updates:", e);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { fetchUpdates(); }, [fetchUpdates]);

  const handlePreview = async (version) => {
    setPreviewing(version);
    try {
      const res = await axios.post(`${api}/admin/trigger-update-preview`, { version });
      const p = res.data;
      if (p.priority === "major") {
        toast(p.message, {
          description: `v${p.version} (Preview)`,
          icon: <Bell size={16} className="text-primary" />,
          className: "border-l-4 border-l-primary",
          duration: 12000,
        });
      } else {
        toast(p.message, {
          description: `v${p.version} (Preview)`,
          duration: 12000,
        });
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Preview failed");
    }
    setPreviewing(null);
  };

  useEffect(() => { fetchUpdates(); }, [fetchUpdates]);

  return (
    <div className="space-y-6" data-testid="updates-page">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">
          Platform Updates
        </h1>
        <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
          Version history and release notes
        </p>
      </div>

      {isAdmin && <AdminPanel api={api} onCreated={fetchUpdates} />}

      {/* Update Timeline */}
      <Card className="border border-border rounded-none bg-card" data-testid="updates-timeline">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <Clock size={16} className="text-primary" />
            Update History
            <Badge className="rounded-none text-[9px] px-1.5 py-0 bg-muted text-muted-foreground ml-1">
              {updates.length}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 flex items-center justify-center">
              <Loader2 size={18} className="animate-spin text-muted-foreground" />
            </div>
          ) : updates.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">
              No updates published yet.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {updates.map((u) => (
                <div key={u.version} className="p-4 hover:bg-muted/5 transition-colors" data-testid={`update-entry-${u.version}`}>
                  <div className="flex items-start gap-3">
                    <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                      u.priority === "major" ? "bg-primary" : "bg-muted-foreground/30"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold font-['Barlow_Condensed'] uppercase">
                          v{u.version}
                        </span>
                        <Badge className={`rounded-none text-[8px] px-1.5 py-0 border ${
                          u.priority === "major"
                            ? "bg-primary/10 text-primary border-primary/30"
                            : "bg-muted text-muted-foreground border-border"
                        }`}>
                          {u.priority.toUpperCase()}
                        </Badge>
                        <span className="text-[10px] font-mono text-muted-foreground">
                          {new Date(u.created_at).toLocaleDateString("en-IN", {
                            day: "numeric", month: "short", year: "numeric",
                            hour: "2-digit", minute: "2-digit",
                          })}
                        </span>
                        {u.created_by && (
                          <span className="text-[9px] font-mono text-muted-foreground/50">
                            by {u.created_by}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {u.priority === "major" ? u.message : "Performance improvements and bug fixes"}
                      </p>
                    </div>
                    <Button
                      variant="ghost" size="sm"
                      className="shrink-0 h-7 text-[10px] text-muted-foreground hover:text-primary uppercase tracking-wider font-mono"
                      onClick={() => handlePreview(u.version)}
                      disabled={previewing === u.version}
                      data-testid={`preview-btn-${u.version}`}
                    >
                      {previewing === u.version ? <Loader2 size={11} className="mr-1 animate-spin" /> : <Eye size={11} className="mr-1" />}
                      Preview
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}


function AdminPanel({ api, onCreated }) {
  const [version, setVersion] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("major");
  const [creating, setCreating] = useState(false);
  const [previewVersion, setPreviewVersion] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!version.trim() || !message.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post(`${api}/admin/create-update`, {
        version: version.trim(),
        message: message.trim(),
        priority,
      });
      toast.success(res.data.message || "Update created");
      setVersion("");
      setMessage("");
      onCreated();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create update");
    }
    setCreating(false);
  };

  const handlePreview = async () => {
    if (!previewVersion.trim()) return;
    setPreviewing(true);
    try {
      const res = await axios.post(`${api}/admin/trigger-update-preview`, {
        version: previewVersion.trim(),
      });
      const p = res.data;
      if (p.priority === "major") {
        toast(p.message, {
          description: `v${p.version} (Preview)`,
          icon: <Bell size={16} className="text-primary" />,
          className: "border-l-4 border-l-primary",
          duration: 12000,
        });
      } else {
        toast(p.message, {
          description: `v${p.version} (Preview)`,
          duration: 12000,
        });
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Preview failed");
    }
    setPreviewing(false);
  };

  return (
    <Card className="border border-border rounded-none bg-card border-l-4 border-l-amber-500" data-testid="admin-updates-panel">
      <CardHeader
        className="py-3 px-4 border-b border-border cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
          <Shield size={16} className="text-amber-400" />
          Admin — Manage Updates
          <ChevronDown size={14} className={`ml-auto transition-transform ${expanded ? "rotate-180" : ""}`} />
        </CardTitle>
      </CardHeader>
      {expanded && (
        <CardContent className="p-4 space-y-5">
          {/* Create Update */}
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono font-semibold mb-3 flex items-center gap-1">
              <Plus size={10} /> Create New Update
            </p>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Version</label>
                  <Input
                    value={version} onChange={(e) => setVersion(e.target.value)}
                    placeholder="e.g. 9.3"
                    className="rounded-none text-sm font-mono"
                    data-testid="update-version-input"
                  />
                </div>
                <div>
                  <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Priority</label>
                  <Select value={priority} onValueChange={setPriority}>
                    <SelectTrigger className="rounded-none" data-testid="update-priority-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-none">
                      <SelectItem value="major" className="text-sm">Major</SelectItem>
                      <SelectItem value="minor" className="text-sm">Minor</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-[9px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">Message</label>
                <textarea
                  value={message} onChange={(e) => setMessage(e.target.value)}
                  placeholder="What's new in this version..."
                  className="w-full bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:border-primary resize-none h-20"
                  data-testid="update-message-input"
                />
              </div>
              <Button type="submit" disabled={creating || !version.trim() || !message.trim()}
                className="rounded-none uppercase text-xs font-bold tracking-wider" data-testid="create-update-btn">
                {creating ? <Loader2 size={12} className="mr-2 animate-spin" /> : <Megaphone size={12} className="mr-2" />}
                Publish Update
              </Button>
            </form>
          </div>

          {/* Preview */}
          <div className="border-t border-border pt-4">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono font-semibold mb-3 flex items-center gap-1">
              <Eye size={10} /> Preview Update Toast
            </p>
            <div className="flex gap-2">
              <Input
                value={previewVersion} onChange={(e) => setPreviewVersion(e.target.value)}
                placeholder="Version to preview..."
                className="rounded-none text-sm font-mono flex-1"
                data-testid="preview-version-input"
              />
              <Button variant="outline" onClick={handlePreview} disabled={previewing || !previewVersion.trim()}
                className="rounded-none text-xs uppercase tracking-wider" data-testid="preview-update-btn">
                {previewing ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Eye size={12} className="mr-1" />}
                Preview
              </Button>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
