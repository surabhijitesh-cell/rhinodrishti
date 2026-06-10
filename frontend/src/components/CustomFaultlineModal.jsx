import { useState } from "react";
import axios from "axios";
import { X, Sparkles, Plus, Loader2 } from "lucide-react";
import { Button } from "./ui/button";

const STATES = [
  "Assam", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
  "Tripura", "Arunachal Pradesh", "North Bengal", "Bangladesh", "Myanmar",
];

export default function CustomFaultlineModal({ api, onClose, onCreated }) {
  const [step, setStep] = useState(1); // 1 = describe, 2 = keywords
  const [form, setForm] = useState({ name: "", state: STATES[0], description: "" });
  const [keywords, setKeywords] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [custom, setCustom] = useState("");
  const [loadingKw, setLoadingKw] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleRecommend = async () => {
    if (!form.name.trim() || !form.description.trim()) {
      setError("Name and description are required.");
      return;
    }
    setError(null);
    setLoadingKw(true);
    try {
      const res = await axios.post(`${api}/faultlines/recommend-keywords`, form);
      const kws = res.data.keywords || [];
      setKeywords(kws);
      setSelected(new Set(kws));
      setStep(2);
    } catch (e) {
      setError(e?.response?.data?.detail || "Keyword recommendation failed.");
    }
    setLoadingKw(false);
  };

  const toggleKeyword = (kw) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(kw) ? next.delete(kw) : next.add(kw);
      return next;
    });
  };

  const addCustom = () => {
    const kw = custom.trim();
    if (!kw) return;
    setKeywords((prev) => (prev.includes(kw) ? prev : [...prev, kw]));
    setSelected((prev) => new Set([...prev, kw]));
    setCustom("");
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await axios.post(`${api}/faultlines`, {
        ...form,
        keywords: Array.from(selected),
      });
      onCreated(res.data.faultline);
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to create faultline.");
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-background border border-border w-full max-w-lg p-5 relative">
        <button
          className="absolute top-3 right-3 text-muted-foreground hover:text-foreground"
          onClick={onClose}
        >
          <X size={16} />
        </button>

        <h2 className="text-sm font-bold uppercase tracking-wider font-mono mb-4">
          {step === 1 ? "New Custom Faultline" : "Select Monitoring Keywords"}
        </h2>

        {step === 1 && (
          <div className="space-y-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">Name</label>
              <input
                className="mt-1 w-full bg-muted border border-border text-xs px-2 py-1.5 outline-none focus:ring-1 focus:ring-primary"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Bodo Land Ethnic Tension"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">State / Region</label>
              <select
                className="mt-1 w-full bg-muted border border-border text-xs px-2 py-1.5 outline-none"
                value={form.state}
                onChange={(e) => setForm((p) => ({ ...p, state: e.target.value }))}
              >
                {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">Description</label>
              <textarea
                className="mt-1 w-full bg-muted border border-border text-xs px-2 py-1.5 outline-none focus:ring-1 focus:ring-primary resize-none"
                rows={4}
                value={form.description}
                onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                placeholder="Describe what this faultline tracks — key issues, actors, geography…"
              />
            </div>
            {error && <p className="text-[10px] text-red-400 font-mono">{error}</p>}
            <div className="flex justify-end pt-1">
              <Button
                size="sm"
                className="rounded-none text-xs"
                onClick={handleRecommend}
                disabled={loadingKw}
              >
                {loadingKw
                  ? <><Loader2 size={12} className="mr-1 animate-spin" /> Thinking…</>
                  : <><Sparkles size={12} className="mr-1" /> Recommend keywords</>
                }
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <p className="text-[10px] text-muted-foreground font-mono">
              Click to toggle. Selected keywords will be used for article matching.
            </p>
            <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
              {keywords.map((kw) => (
                <button
                  key={kw}
                  onClick={() => toggleKeyword(kw)}
                  className={`px-2 py-0.5 text-[10px] font-mono border transition-colors ${
                    selected.has(kw)
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-muted text-muted-foreground border-border"
                  }`}
                >
                  {kw}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                className="flex-1 bg-muted border border-border text-xs px-2 py-1 outline-none focus:ring-1 focus:ring-primary"
                placeholder="Add keyword…"
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustom(); } }}
              />
              <Button variant="outline" size="sm" className="rounded-none text-xs" onClick={addCustom}>
                <Plus size={12} />
              </Button>
            </div>
            {error && <p className="text-[10px] text-red-400 font-mono">{error}</p>}
            <div className="flex justify-between pt-1">
              <Button variant="ghost" size="sm" className="rounded-none text-xs" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                size="sm"
                className="rounded-none text-xs"
                onClick={handleSave}
                disabled={saving || selected.size === 0}
              >
                {saving
                  ? <><Loader2 size={12} className="mr-1 animate-spin" /> Saving…</>
                  : "Create faultline"
                }
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
