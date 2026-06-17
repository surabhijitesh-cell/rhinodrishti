import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { X, Plus, Edit2, Trash2, Save, ChevronDown, ChevronUp, Target } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EMPTY_FORM = {
  name: "",
  description: "",
  rank: "",
  geography: "",
  actors_of_interest: "",
  linked_faultline_ids: [],
  keywords: "",
  keyword_regions: "",
  watch_geography: "",
  color: "red",
};

function authHeader() {
  const token = localStorage.getItem("rd_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function ChipInput({ label, value, onChange, placeholder }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">
        {label}
      </label>
      <input
        className="w-full bg-muted/30 border border-border px-2 py-1.5 text-xs text-foreground rounded-none focus:outline-none focus:border-primary"
        value={draft}
        onChange={(e) => { setDraft(e.target.value); onChange(e.target.value); }}
        placeholder={placeholder || "comma-separated"}
      />
      <p className="text-[9px] text-muted-foreground mt-0.5">Separate with commas</p>
    </div>
  );
}

function FaultlineSelect({ allFaultlines, selected, onChange }) {
  const [search, setSearch] = useState("");
  const filtered = allFaultlines.filter(
    (fl) =>
      fl.name.toLowerCase().includes(search.toLowerCase()) ||
      fl.state?.toLowerCase().includes(search.toLowerCase())
  );
  const toggle = (id) => {
    if (selected.includes(id)) onChange(selected.filter((x) => x !== id));
    else onChange([...selected, id]);
  };
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">
        Linked Faultlines
      </label>
      <input
        className="w-full bg-muted/30 border border-border px-2 py-1.5 text-xs mb-1 focus:outline-none focus:border-primary"
        placeholder="Search faultlines…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="max-h-36 overflow-y-auto border border-border divide-y divide-border/50">
        {filtered.slice(0, 50).map((fl) => (
          <label
            key={fl.id}
            className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-muted/20 transition-colors"
          >
            <input
              type="checkbox"
              checked={selected.includes(fl.id)}
              onChange={() => toggle(fl.id)}
              className="accent-primary"
            />
            <span className="text-[10px] text-muted-foreground font-mono w-16 shrink-0">{fl.state}</span>
            <span className="text-xs text-foreground leading-tight">{fl.name}</span>
          </label>
        ))}
        {filtered.length === 0 && (
          <p className="text-xs text-muted-foreground px-2 py-2">No faultlines match</p>
        )}
      </div>
      {selected.length > 0 && (
        <p className="text-[10px] text-primary mt-1">{selected.length} faultline{selected.length !== 1 ? "s" : ""} selected</p>
      )}
    </div>
  );
}

function PAOIForm({ initial, allFaultlines, onSave, onCancel, saving }) {
  const [form, setForm] = useState(() => {
    if (!initial) return EMPTY_FORM;
    return {
      name: initial.name || "",
      description: initial.description || "",
      rank: initial.rank?.toString() || "",
      geography: (initial.geography || []).join(", "),
      actors_of_interest: (initial.actors_of_interest || []).join(", "),
      linked_faultline_ids: initial.linked_faultline_ids || [],
      keywords: (initial.keyword_pull?.keywords || []).join(", "),
      keyword_regions: (initial.keyword_pull?.regions || []).join(", "),
      watch_geography: (initial.watch_geography || []).join(", "),
      color: initial.color || "red",
    };
  });
  const [showAdvanced, setShowAdvanced] = useState(false);

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  const toList = (str) => str.split(",").map((s) => s.trim()).filter(Boolean);

  const handleSave = () => {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      rank: form.rank ? parseInt(form.rank) : undefined,
      geography: toList(form.geography),
      actors_of_interest: toList(form.actors_of_interest),
      linked_faultline_ids: form.linked_faultline_ids,
      watch_geography: toList(form.watch_geography),
      color: form.color,
    };
    const kws = toList(form.keywords);
    const krs = toList(form.keyword_regions);
    if (kws.length > 0 || krs.length > 0) {
      payload.keyword_pull = { keywords: kws, regions: krs };
    }
    onSave(payload);
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <div className="col-span-2">
          <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">
            Name *
          </label>
          <input
            className="w-full bg-muted/30 border border-border px-2 py-1.5 text-xs focus:outline-none focus:border-primary"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="e.g. Meghalaya Internal Security"
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">
            Rank (P#)
          </label>
          <input
            type="number"
            className="w-full bg-muted/30 border border-border px-2 py-1.5 text-xs focus:outline-none focus:border-primary"
            value={form.rank}
            onChange={(e) => set("rank", e.target.value)}
            placeholder="auto"
          />
        </div>
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono block mb-1">
          Description
        </label>
        <textarea
          rows={3}
          className="w-full bg-muted/30 border border-border px-2 py-1.5 text-xs resize-none focus:outline-none focus:border-primary"
          value={form.description}
          onChange={(e) => set("description", e.target.value)}
          placeholder="What is this PAOI about? What should be monitored?"
        />
      </div>

      <ChipInput
        label="Geography (regions in scope)"
        value={form.geography}
        onChange={(v) => set("geography", v)}
        placeholder="Meghalaya, Assam, North Bengal"
      />

      <ChipInput
        label="Actors of Interest"
        value={form.actors_of_interest}
        onChange={(v) => set("actors_of_interest", v)}
        placeholder="HNLC, KSU, smuggling networks"
      />

      <FaultlineSelect
        allFaultlines={allFaultlines}
        selected={form.linked_faultline_ids}
        onChange={(v) => set("linked_faultline_ids", v)}
      />

      <button
        type="button"
        onClick={() => setShowAdvanced((s) => !s)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground font-mono uppercase tracking-wider"
      >
        {showAdvanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        Keyword Pull (advanced)
      </button>

      {showAdvanced && (
        <div className="pl-3 border-l border-border space-y-2">
          <ChipInput
            label="Keywords"
            value={form.keywords}
            onChange={(v) => set("keywords", v)}
            placeholder="bandh, blockade, highway, NH-44"
          />
          <ChipInput
            label="Keyword Regions"
            value={form.keyword_regions}
            onChange={(v) => set("keyword_regions", v)}
            placeholder="Meghalaya, Assam"
          />
          <ChipInput
            label="Watch Geography (secondary)"
            value={form.watch_geography}
            onChange={(v) => set("watch_geography", v)}
            placeholder="North Bengal border districts"
          />
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <Button
          size="sm"
          className="h-8 text-xs bg-primary hover:bg-primary/90"
          onClick={handleSave}
          disabled={saving || !form.name.trim()}
        >
          <Save size={12} className="mr-1" />
          {saving ? "Saving…" : "Save PAOI"}
        </Button>
        <Button size="sm" variant="ghost" className="h-8 text-xs" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function PAOIManager({ onClose }) {
  const [paois, setPaois] = useState([]);
  const [allFaultlines, setAllFaultlines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [paRes, flRes] = await Promise.all([
        axios.get(`${API}/faultlines/priority-areas`, { headers: authHeader() }),
        axios.get(`${API}/faultlines?active_only=false&include_score=false`, { headers: authHeader() }),
      ]);
      setPaois(paRes.data.priority_areas || []);
      setAllFaultlines(flRes.data.faultlines || []);
    } catch (e) {
      setError("Failed to load PAOIs");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (payload) => {
    setSaving(true);
    setError(null);
    try {
      await axios.post(`${API}/faultlines/priority-areas`, payload, { headers: authHeader() });
      setCreating(false);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Create failed");
    }
    setSaving(false);
  };

  const handleUpdate = async (id, payload) => {
    setSaving(true);
    setError(null);
    try {
      await axios.put(`${API}/faultlines/priority-areas/${id}`, payload, { headers: authHeader() });
      setEditingId(null);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Update failed");
    }
    setSaving(false);
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Disable PAOI "${name}"? It will be hidden from all views.`)) return;
    try {
      await axios.delete(`${API}/faultlines/priority-areas/${id}`, { headers: authHeader() });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-card border border-border shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Target size={15} className="text-primary" />
            <span className="text-sm font-semibold uppercase tracking-wider">
              Priority Areas of Interest
            </span>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X size={15} />
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error && (
            <p className="text-xs text-red-400 bg-red-950/20 border border-red-500/30 px-3 py-2">
              {error}
            </p>
          )}

          {loading ? (
            <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
          ) : (
            <>
              {/* Existing PAOIs */}
              {paois.map((pa) => (
                <div key={pa.id} className="border border-border bg-muted/10 p-4">
                  {editingId === pa.id ? (
                    <>
                      <p className="text-[10px] uppercase tracking-wider font-mono text-primary mb-3">
                        Editing P{pa.rank} — {pa.name}
                      </p>
                      <PAOIForm
                        initial={pa}
                        allFaultlines={allFaultlines}
                        onSave={(payload) => handleUpdate(pa.id, payload)}
                        onCancel={() => setEditingId(null)}
                        saving={saving}
                      />
                    </>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge className="text-[9px] font-mono bg-red-950/40 text-red-400 border-red-500/30 px-1.5 py-0">
                            P{pa.rank}
                          </Badge>
                          <span className="text-sm font-semibold">{pa.name}</span>
                        </div>
                        <p className="text-xs text-muted-foreground leading-snug line-clamp-2">
                          {pa.description}
                        </p>
                        {pa.geography?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {pa.geography.slice(0, 5).map((g) => (
                              <span key={g} className="text-[9px] bg-muted/40 border border-border px-1.5 py-0.5 font-mono">
                                {g}
                              </span>
                            ))}
                            {pa.geography.length > 5 && (
                              <span className="text-[9px] text-muted-foreground">
                                +{pa.geography.length - 5} more
                              </span>
                            )}
                          </div>
                        )}
                        <p className="text-[10px] text-muted-foreground mt-1.5 font-mono">
                          {pa.linked_faultline_ids?.length || 0} faultlines linked
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                          onClick={() => { setCreating(false); setEditingId(pa.id); }}
                        >
                          <Edit2 size={13} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
                          onClick={() => handleDelete(pa.id, pa.name)}
                        >
                          <Trash2 size={13} />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* New PAOI form */}
              {creating ? (
                <div className="border border-primary/40 bg-primary/5 p-4">
                  <p className="text-[10px] uppercase tracking-wider font-mono text-primary mb-3">
                    New Priority Area
                  </p>
                  <PAOIForm
                    initial={null}
                    allFaultlines={allFaultlines}
                    onSave={handleCreate}
                    onCancel={() => setCreating(false)}
                    saving={saving}
                  />
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full h-9 text-xs border-dashed border-border text-muted-foreground hover:text-foreground hover:border-primary/50"
                  onClick={() => { setEditingId(null); setCreating(true); }}
                >
                  <Plus size={13} className="mr-1.5" /> Add Priority Area
                </Button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
