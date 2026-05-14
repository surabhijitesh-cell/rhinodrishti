/**
 * FilterThresholdSimulator — admin-only widget on /admin page.
 *
 * Shows sliders for every tunable pipeline stage threshold.
 * As sliders move, instantly recomputes a simulated funnel chart
 * using today's ACTUAL cycle data as baseline.
 *
 * On "Apply Settings" → shows honest impact modal → user confirms
 * → POST /admin/filter-settings → pipeline picks up in ≤5 min.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell, LabelList,
} from "recharts";
import { Slider } from "./ui/slider";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { SlidersHorizontal, AlertTriangle, CheckCircle2, RefreshCw, Info } from "lucide-react";

// ── Cost constants (Gemini 2.5 Flash pricing — Stage 2 primary model) ────────
// Stage 1: Gemini Flash-Lite  $0.10/$0.40 per MTok (cheap_classifier.py)
// Stage 2: Gemini 2.5 Flash   $0.15/$0.60 per MTok (ai_pipeline.py) ← simulator models this
const GEMINI_INPUT_PER_M  = 0.15;  // USD per million input tokens
const GEMINI_OUTPUT_PER_M = 0.60;  // USD per million output tokens
const AVG_INPUT_TOK_PER_CALL  = 1500;
const AVG_OUTPUT_TOK_PER_CALL = 400;
const CYCLES_PER_DAY = 96;         // every 15 min × 24h
const INR_RATE = 84;

const COST_PER_CALL_USD =
  (AVG_INPUT_TOK_PER_CALL  / 1_000_000 * GEMINI_INPUT_PER_M) +
  (AVG_OUTPUT_TOK_PER_CALL / 1_000_000 * GEMINI_OUTPUT_PER_M);

// ── Simulation engine ─────────────────────────────────────────────────────────
function simulateFunnel(settings, todayData, savedSettings) {
  const scanned   = todayData?.items_scanned  || 200;
  const s0pass    = todayData?.stage0_pass     || scanned;
  const s05pass   = todayData?.stage05_pass    || s0pass;
  const s1pass    = todayData?.stage1_pass     || s05pass;
  const haikuTotal = (todayData?.haiku_relevant || 0) + (todayData?.haiku_not_relevant || 0);
  const cycles    = todayData?.cycles          || 1;

  // Stage 0: keyword filter — not tunable, use actual
  const afterS0 = s0pass;

  // Stage 0.5: estimate impact of min_sim change
  const baselinePassRate = s0pass > 0 ? s05pass / s0pass : 1.0;
  const simDelta = (settings.stage05_min_sim - (savedSettings?.stage05_min_sim || 0.35)) * 1.8;
  const simPassRate05 = settings.stage05_enabled
    ? Math.max(0.20, Math.min(1.0, baselinePassRate - simDelta))
    : 1.0;
  const afterS05 = Math.round(afterS0 * simPassRate05);

  // Stage 1: Gemini filter — use actual pass rate if enabled
  const s1baseRate = s05pass > 0 ? s1pass / s05pass : 1.0;
  const afterS1 = settings.stage1_enabled
    ? Math.round(afterS05 * s1baseRate)
    : afterS05;

  // Stage 2: Haiku cap per cycle
  const haikuCap     = settings.stage2_max_haiku * cycles;
  const toHaiku      = Math.min(afterS1, haikuCap);
  const haikuPerDay  = toHaiku / cycles * CYCLES_PER_DAY;
  const costPerDayUsd = haikuPerDay * COST_PER_CALL_USD;
  const costPerDayInr = Math.round(costPerDayUsd * INR_RATE);

  // Baseline cost (current actual settings applied)
  const baseHaikuPerDay = (haikuTotal / cycles) * CYCLES_PER_DAY;
  const baseCostUsd = baseHaikuPerDay * COST_PER_CALL_USD;

  const savingsPct = baseCostUsd > 0
    ? Math.round((1 - costPerDayUsd / baseCostUsd) * 100)
    : 0;

  // Coverage risk
  const filterRate = afterS0 > 0 ? 1 - toHaiku / afterS0 : 0;
  let coverageRisk = "LOW";
  let riskColor    = "text-emerald-400";
  if (settings.stage05_min_sim > 0.55 || !settings.stage1_enabled) {
    coverageRisk = "HIGH — may miss critical news";
    riskColor    = "text-red-400";
  } else if (settings.stage05_min_sim > 0.45) {
    coverageRisk = "MEDIUM — some relevant news may be filtered";
    riskColor    = "text-amber-400";
  }

  return {
    afterS0, afterS05, afterS1, toHaiku,
    costPerDayUsd, costPerDayInr, haikuPerDay,
    baseCostUsd, savingsPct, filterRate,
    coverageRisk, riskColor,
  };
}

// ── Funnel chart data builder ─────────────────────────────────────────────────
function buildChartData(scanned, sim) {
  const stages = [
    { name: "Scanned",    pass: scanned,       drop: 0 },
    { name: "After S0",   pass: sim.afterS0,   drop: scanned - sim.afterS0 },
    { name: "After S0.5", pass: sim.afterS05,  drop: sim.afterS0 - sim.afterS05 },
    { name: "After S1",   pass: sim.afterS1,   drop: sim.afterS05 - sim.afterS1 },
    { name: "→ Gemini",   pass: sim.toHaiku,   drop: sim.afterS1 - sim.toHaiku },
  ];
  return stages;
}

// ── Slider row helper ─────────────────────────────────────────────────────────
function SliderRow({ label, value, min, max, step, onChange, format, hint, warn }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[9px] font-mono">
        <span className={`text-muted-foreground ${warn ? "text-amber-400" : ""}`}>{label}</span>
        <span className={`font-bold ${warn ? "text-amber-400" : "text-foreground"}`}>
          {format ? format(value) : value}
        </span>
      </div>
      <Slider
        min={min} max={max} step={step}
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        className={warn ? "[&_.bg-primary]:bg-amber-500" : ""}
      />
      {hint && <p className="text-[8px] font-mono text-muted-foreground/60">{hint}</p>}
    </div>
  );
}

// ── Toggle switch ─────────────────────────────────────────────────────────────
function ToggleRow({ label, value, onChange, warn }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className={`text-[9px] font-mono ${warn && !value ? "text-red-400" : "text-muted-foreground"}`}>
        {label}
      </span>
      <button
        onClick={() => onChange(!value)}
        className={`text-[8px] font-mono px-2 py-0.5 border rounded-none transition-colors ${
          value
            ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
            : "bg-red-500/20 text-red-400 border-red-500/30"
        }`}
      >
        {value ? "ON" : "OFF"}
      </button>
    </div>
  );
}

// ── Impact confirmation modal ─────────────────────────────────────────────────
function ConfirmModal({ sim, settings, onConfirm, onCancel, saving }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="border border-border bg-card rounded-none shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-widest font-['Barlow_Condensed']">
          Confirm Filter Settings
        </h2>

        <div className="text-[10px] font-mono space-y-1 text-muted-foreground">
          <div className="flex justify-between">
            <span>Stage 0.5 min similarity</span>
            <span className="text-foreground">{settings.stage05_min_sim.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span>Stage 0.5 enabled</span>
            <span className={settings.stage05_enabled ? "text-emerald-400" : "text-red-400"}>
              {settings.stage05_enabled ? "YES" : "NO"}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Stage 1 (Gemini) enabled</span>
            <span className={settings.stage1_enabled ? "text-emerald-400" : "text-red-400"}>
              {settings.stage1_enabled ? "YES" : "NO"}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Max scan/cycle</span>
            <span className="text-foreground">{settings.stage2_max_scan}</span>
          </div>
          <div className="flex justify-between">
            <span>Max Gemini calls/cycle</span>
            <span className="text-foreground">{settings.stage2_max_haiku}</span>
          </div>
        </div>

        <div className={`border p-3 space-y-1 ${
          sim.coverageRisk.startsWith("HIGH")
            ? "border-red-500/30 bg-red-500/10"
            : sim.coverageRisk.startsWith("MEDIUM")
            ? "border-amber-500/30 bg-amber-500/10"
            : "border-emerald-500/30 bg-emerald-500/10"
        }`}>
          <p className="text-[9px] font-mono font-semibold uppercase tracking-wider text-muted-foreground">
            Impact Assessment
          </p>
          <p className="text-[10px] font-mono">
            Est. Gemini Flash calls/day: <span className="font-bold">{Math.round(sim.haikuPerDay).toLocaleString()}</span>
          </p>
          <p className="text-[10px] font-mono">
            Est. cost/day: <span className="font-bold text-emerald-400">₹{sim.costPerDayInr}</span>
            {sim.savingsPct > 0 && (
              <span className="text-emerald-400/70 ml-1">({sim.savingsPct}% less)</span>
            )}
          </p>
          <p className="text-[10px] font-mono">
            Coverage risk: <span className={`font-bold ${sim.riskColor}`}>{sim.coverageRisk}</span>
          </p>
          <p className="text-[10px] font-mono text-muted-foreground">
            ~{Math.round(sim.filterRate * 100)}% of items filtered before Gemini Flash
          </p>
        </div>

        {sim.coverageRisk.startsWith("HIGH") && (
          <div className="flex items-start gap-2 text-[9px] font-mono text-red-400 border border-red-500/30 bg-red-500/10 p-2">
            <AlertTriangle size={10} className="shrink-0 mt-0.5" />
            <span>Warning: aggressive settings may prevent critical NER news from reaching classification. Proceed with caution.</span>
          </div>
        )}

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 rounded-none text-[9px] font-mono"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            className="flex-1 rounded-none text-[9px] font-mono bg-violet-600 hover:bg-violet-700"
            onClick={onConfirm}
            disabled={saving}
          >
            {saving ? <RefreshCw size={9} className="animate-spin mr-1" /> : <CheckCircle2 size={9} className="mr-1" />}
            {saving ? "Applying…" : "Confirm & Apply"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Main widget ───────────────────────────────────────────────────────────────
export default function FilterThresholdSimulator({ api }) {
  const [savedSettings, setSavedSettings] = useState(null);
  const [settings, setSettings]           = useState(null);
  const [todayData, setTodayData]         = useState(null);
  const [loading, setLoading]             = useState(true);
  const [showModal, setShowModal]         = useState(false);
  const [saving, setSaving]               = useState(false);
  const [saved, setSaved]                 = useState(false);
  const [error, setError]                 = useState(null);

  const load = useCallback(async () => {
    try {
      const [settingsRes, todayRes] = await Promise.all([
        axios.get(`${api}/admin/filter-settings`),
        axios.get(`${api}/admin/filter-cascade/today`),
      ]);
      const s = settingsRes.data;
      setSavedSettings(s);
      setSettings({ ...s });
      setTodayData(todayRes.data);
    } catch (e) {
      setError("Failed to load settings");
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const sim = useMemo(() => {
    if (!settings || !todayData) return null;
    return simulateFunnel(settings, todayData, savedSettings);
  }, [settings, todayData, savedSettings]);

  const chartData = useMemo(() => {
    if (!sim || !todayData) return [];
    return buildChartData(todayData.items_scanned || 200, sim);
  }, [sim, todayData]);

  const hasChanges = useMemo(() => {
    if (!settings || !savedSettings) return false;
    return JSON.stringify(settings) !== JSON.stringify(savedSettings);
  }, [settings, savedSettings]);

  const handleApply = async () => {
    setSaving(true);
    try {
      await axios.post(`${api}/admin/filter-settings`, settings);
      setSavedSettings({ ...settings });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError("Failed to save settings");
    }
    setSaving(false);
    setShowModal(false);
  };

  const update = (key) => (val) => setSettings(s => ({ ...s, [key]: val }));

  if (loading) {
    return (
      <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500">
        <CardContent className="p-4 flex items-center gap-2 text-muted-foreground text-xs">
          <RefreshCw size={12} className="animate-spin" /> Loading simulator…
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {showModal && sim && (
        <ConfirmModal
          sim={sim}
          settings={settings}
          onConfirm={handleApply}
          onCancel={() => setShowModal(false)}
          saving={saving}
        />
      )}

      <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <SlidersHorizontal size={14} className="text-violet-400" />
            Filter Threshold Simulator
            <Badge className="rounded-none text-[8px] px-1.5 py-0 border bg-violet-500/10 text-violet-400 border-violet-500/30">
              LIVE SIM
            </Badge>
            {saved && (
              <Badge className="rounded-none text-[8px] px-1.5 py-0 border bg-emerald-500/10 text-emerald-400 border-emerald-500/30 ml-1">
                ✓ SAVED
              </Badge>
            )}
            <button onClick={load} className="ml-auto text-muted-foreground/40 hover:text-muted-foreground">
              <RefreshCw size={10} />
            </button>
          </CardTitle>
        </CardHeader>

        <CardContent className="p-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* ── Left: sliders ── */}
            <div className="space-y-5">
              <div>
                <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold mb-3">
                  Stage 0.5 — Embedding Similarity
                </p>
                <ToggleRow
                  label="Enabled"
                  value={settings.stage05_enabled}
                  onChange={update("stage05_enabled")}
                />
                <SliderRow
                  label="Min similarity threshold"
                  value={settings.stage05_min_sim}
                  min={0.10} max={0.70} step={0.01}
                  onChange={update("stage05_min_sim")}
                  format={v => v.toFixed(2)}
                  hint="0.25 = permissive · 0.35 = balanced · 0.50+ = aggressive"
                  warn={settings.stage05_min_sim > 0.45}
                />
              </div>

              <div>
                <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold mb-3">
                  Stage 1 — Gemini Flash-Lite binary filter
                </p>
                <ToggleRow
                  label="Enabled"
                  value={settings.stage1_enabled}
                  onChange={update("stage1_enabled")}
                  warn={true}
                />
                <p className="text-[8px] font-mono text-muted-foreground/60 mt-1">
                  Disabling Stage 1 sends all S0.5 survivors directly to Gemini Flash — significantly increases cost.
                </p>
              </div>

              <div>
                <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold mb-3">
                  Stage 2 — Gemini 2.5 Flash capacity
                </p>
                <SliderRow
                  label="Max items scanned/cycle"
                  value={settings.stage2_max_scan}
                  min={50} max={500} step={25}
                  onChange={update("stage2_max_scan")}
                  hint="Higher = clears backlog faster but uses more memory"
                />
                <div className="mt-3">
                  <SliderRow
                    label="Max Gemini calls/cycle"
                    value={settings.stage2_max_haiku}
                    min={5} max={50} step={1}
                    onChange={update("stage2_max_haiku")}
                    hint="Primary cost lever — lower = cheaper but slower processing"
                    warn={settings.stage2_max_haiku > 35}
                  />
                </div>
              </div>

              {/* Apply button */}
              <div className="pt-2">
                <Button
                  className={`w-full rounded-none text-[10px] font-mono uppercase tracking-wider h-8 ${
                    hasChanges
                      ? "bg-violet-600 hover:bg-violet-700 text-white"
                      : "bg-muted/20 text-muted-foreground cursor-not-allowed"
                  }`}
                  disabled={!hasChanges || saving}
                  onClick={() => setShowModal(true)}
                >
                  {saving ? (
                    <><RefreshCw size={9} className="animate-spin mr-1" /> Applying…</>
                  ) : hasChanges ? (
                    "Apply Settings →"
                  ) : (
                    "No changes"
                  )}
                </Button>
                {hasChanges && (
                  <button
                    onClick={() => setSettings({ ...savedSettings })}
                    className="w-full text-[8px] font-mono text-muted-foreground/50 hover:text-muted-foreground mt-1 text-center"
                  >
                    reset to saved
                  </button>
                )}
                {error && <p className="text-[9px] text-red-400 font-mono mt-1">{error}</p>}
              </div>
            </div>

            {/* ── Right: simulated funnel ── */}
            <div className="space-y-4">
              <div>
                <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold mb-2">
                  Simulated Funnel
                  <span className="ml-2 text-muted-foreground/50 normal-case">
                    based on today's {todayData?.cycles || 0} cycles
                  </span>
                </p>

                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
                    >
                      <XAxis type="number" hide />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={58}
                        tick={{ fontSize: 8, fontFamily: "monospace", fill: "hsl(var(--muted-foreground))" }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: 0,
                          fontSize: 9,
                          fontFamily: "monospace",
                        }}
                        formatter={(v, name) => [v.toLocaleString(), name]}
                      />
                      <Bar dataKey="pass" stackId="a" name="Pass" fill="#10b981" opacity={0.8} radius={0}>
                        <LabelList
                          dataKey="pass"
                          position="right"
                          style={{ fontSize: 8, fontFamily: "monospace", fill: "hsl(var(--foreground))" }}
                          formatter={v => v.toLocaleString()}
                        />
                      </Bar>
                      <Bar dataKey="drop" stackId="a" name="Drop" fill="#ef4444" opacity={0.5} radius={0} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Cost & impact summary */}
              {sim && (
                <div className="border border-border/30 p-3 bg-muted/5 space-y-2">
                  <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold">
                    Estimated Impact (per day)
                  </p>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[9px] font-mono">
                    <span className="text-muted-foreground">Gemini Flash calls</span>
                    <span className="text-foreground font-bold">{Math.round(sim.haikuPerDay).toLocaleString()}</span>

                    <span className="text-muted-foreground">Est. cost</span>
                    <span className="text-emerald-400 font-bold">
                      ₹{sim.costPerDayInr} (${sim.costPerDayUsd.toFixed(2)})
                    </span>

                    <span className="text-muted-foreground">vs current</span>
                    <span className={sim.savingsPct >= 0 ? "text-emerald-400" : "text-red-400"}>
                      {sim.savingsPct >= 0 ? `-${sim.savingsPct}%` : `+${Math.abs(sim.savingsPct)}%`}
                    </span>

                    <span className="text-muted-foreground">Filter rate</span>
                    <span className="text-foreground">{Math.round(sim.filterRate * 100)}% before Gemini Flash</span>

                    <span className="text-muted-foreground">Coverage risk</span>
                    <span className={sim.riskColor}>{sim.coverageRisk.split(" —")[0]}</span>
                  </div>

                  {sim.coverageRisk !== "LOW" && (
                    <div className="flex items-start gap-1.5 text-[8px] font-mono text-amber-400 mt-1">
                      <AlertTriangle size={9} className="shrink-0 mt-0.5" />
                      <span>{sim.coverageRisk}</span>
                    </div>
                  )}

                  <div className="flex items-start gap-1.5 text-[8px] font-mono text-muted-foreground/60 mt-1 border-t border-border/20 pt-1.5">
                    <Info size={8} className="shrink-0 mt-0.5" />
                    <span>
                      Simulation uses today's actual cycle data as baseline.
                      Stage 0.5 estimate uses linear approximation — actual may vary
                      ±10% depending on article distribution.
                    </span>
                  </div>
                </div>
              )}
            </div>

          </div>
        </CardContent>
      </Card>
    </>
  );
}
