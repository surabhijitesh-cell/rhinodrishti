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
import LoadError from "./LoadError";
import { SlidersHorizontal, AlertTriangle, CheckCircle2, RefreshCw, Info } from "lucide-react";

// ── Cost assumptions (shown to the reader at the bottom of the panel) ─────────
// Full classification: measured real charge per call, 17 Nov 2026.
const COST_PER_CLASSIFY_CALL_USD = 0.0012;
// Cheap pre-filter (google/gemini-2.5-flash-lite) at its listed OpenRouter price.
const PREFILTER_INPUT_PER_M  = 0.10;   // USD per million input tokens
const PREFILTER_OUTPUT_PER_M = 0.40;   // USD per million output tokens
// The page does not receive real text sizes, so these are stated assumptions.
const PREFILTER_INPUT_TOKENS  = 400;   // title + short excerpt per item
const PREFILTER_OUTPUT_TOKENS = 20;    // a yes/no answer
const COST_PER_PREFILTER_CALL_USD =
  (PREFILTER_INPUT_TOKENS  / 1_000_000 * PREFILTER_INPUT_PER_M) +
  (PREFILTER_OUTPUT_TOKENS / 1_000_000 * PREFILTER_OUTPUT_PER_M);
const CYCLES_PER_DAY = 96;         // every 15 min x 24h

// Rupees only when the live rate is known; otherwise dollars alone.
const rupees = (usd, rate) => (rate ? `₹${Math.round(usd * rate).toLocaleString("en-IN")}` : null);

function money(usd, rate) {
  const inr = rupees(usd, rate);
  return inr ? `${inr} ($${usd.toFixed(2)})` : `$${usd.toFixed(2)}`;
}

// ── Simulation engine ─────────────────────────────────────────────────────────
function simulateFunnel(settings, todayData, savedSettings) {
  const cycles      = Math.max(1, todayData?.cycles || 1);
  const scannedAct  = todayData?.items_scanned  || 200;
  const s0Act       = todayData?.stage0_pass     || scannedAct;
  const s05Act      = todayData?.stage05_pass    || s0Act;
  const s1Act       = todayData?.stage1_pass     || s05Act;
  const haikuTotal  = (todayData?.haiku_relevant || 0) + (todayData?.haiku_not_relevant || 0);

  // "Max items scanned per cycle": if today's cycles were hitting the saved cap,
  // scale volume with the new cap; otherwise the cap only bites when lowered below
  // what a cycle actually scanned.
  const savedScan  = savedSettings?.stage2_max_scan || settings.stage2_max_scan;
  const perCycle   = scannedAct / cycles;
  const wasCapped  = perCycle >= 0.95 * savedScan;
  const simPerCycle = wasCapped
    ? perCycle * (settings.stage2_max_scan / savedScan)
    : Math.min(perCycle, settings.stage2_max_scan);
  const k = perCycle > 0 ? simPerCycle / perCycle : 1;

  const scanned = Math.round(scannedAct * k);
  const afterS0 = Math.round(s0Act * k);   // keyword filter: not tunable

  // Stage 0.5: estimate impact of the similarity change
  const baselinePassRate = s0Act > 0 ? s05Act / s0Act : 1.0;
  const simDelta = (settings.stage05_min_sim - (savedSettings?.stage05_min_sim || 0.35)) * 1.8;
  const simPassRate05 = settings.stage05_enabled
    ? Math.max(0.20, Math.min(1.0, baselinePassRate - simDelta))
    : 1.0;
  const afterS05 = Math.round(afterS0 * simPassRate05);

  // Stage 1: cheap pre-filter; use today's real pass rate when on
  const s1baseRate = s05Act > 0 ? s1Act / s05Act : 1.0;
  const afterS1 = settings.stage1_enabled ? Math.round(afterS05 * s1baseRate) : afterS05;

  // Stage 2: full classification, capped per cycle
  const toHaiku     = Math.min(afterS1, settings.stage2_max_haiku * cycles);
  const haikuPerDay = toHaiku / cycles * CYCLES_PER_DAY;
  const prefilterPerDay = settings.stage1_enabled ? afterS05 / cycles * CYCLES_PER_DAY : 0;
  const costPerDayUsd = haikuPerDay * COST_PER_CLASSIFY_CALL_USD + prefilterPerDay * COST_PER_PREFILTER_CALL_USD;

  // Baseline = today's actual behaviour at the saved settings
  const basePrefilterPerDay = savedSettings?.stage1_enabled !== false ? s05Act / cycles * CYCLES_PER_DAY : 0;
  const baseCostUsd = (haikuTotal / cycles) * CYCLES_PER_DAY * COST_PER_CLASSIFY_CALL_USD
    + basePrefilterPerDay * COST_PER_PREFILTER_CALL_USD;
  const savingsPct = baseCostUsd > 0 ? Math.round((1 - costPerDayUsd / baseCostUsd) * 100) : 0;

  const filterRate = afterS0 > 0 ? 1 - toHaiku / afterS0 : 0;

  // Coverage risk is about missed news only. Turning the pre-filter off is
  // the opposite trade: it costs more but misses fewer items.
  let coverageRisk = "LOW";
  let riskColor    = "text-emerald-400";
  if (settings.stage05_min_sim > 0.55) {
    coverageRisk = "HIGH — may miss critical news";
    riskColor    = "text-red-400";
  } else if (settings.stage05_min_sim > 0.45) {
    coverageRisk = "MEDIUM — some relevant news may be filtered";
    riskColor    = "text-amber-400";
  }
  const prefilterOff = !settings.stage1_enabled;

  return {
    scanned, afterS0, afterS05, afterS1, toHaiku,
    costPerDayUsd, haikuPerDay,
    baseCostUsd, savingsPct, filterRate,
    coverageRisk, riskColor, prefilterOff,
  };
}

// ── Funnel chart data builder ─────────────────────────────────────────────────
function buildChartData(sim) {
  const scanned = sim.scanned;
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
function ConfirmModal({ sim, settings, rate, onConfirm, onCancel, saving }) {
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
            <span>Cheap pre-filter enabled</span>
            <span className={settings.stage1_enabled ? "text-emerald-400" : "text-red-400"}>
              {settings.stage1_enabled ? "YES" : "NO"}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Max items scanned per cycle</span>
            <span className="text-foreground">{settings.stage2_max_scan}</span>
          </div>
          <div className="flex justify-between">
            <span>Max full classifications per cycle</span>
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
            Est. full classifications/day: <span className="font-bold">{Math.round(sim.haikuPerDay).toLocaleString()}</span>
          </p>
          <p className="text-[10px] font-mono">
            Est. cost/day: <span className="font-bold text-emerald-400">{money(sim.costPerDayUsd, rate)}</span>
            {sim.savingsPct > 0 && (
              <span className="text-emerald-400/70 ml-1">({sim.savingsPct}% less)</span>
            )}
          </p>
          <p className="text-[10px] font-mono">
            Coverage risk: <span className={`font-bold ${sim.riskColor}`}>{sim.coverageRisk}</span>
          </p>
          {sim.prefilterOff && (
            <p className="text-[10px] font-mono text-amber-400">
              Pre-filter off: higher cost, fewer missed items.
            </p>
          )}
          <p className="text-[10px] font-mono text-muted-foreground">
            ~{Math.round(sim.filterRate * 100)}% of items filtered before full classification
          </p>
        </div>

        {sim.coverageRisk.startsWith("HIGH") && (
          <div className="flex items-start gap-2 text-[9px] font-mono text-red-400 border border-red-500/30 bg-red-500/10 p-2">
            <AlertTriangle size={10} className="shrink-0 mt-0.5" />
            <span>Warning: this similarity setting may stop critical NER news from reaching classification. Proceed with caution.</span>
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
  const [error, setError]                 = useState(null);       // save failure
  const [todayFailed, setTodayFailed]       = useState(false);

  const load = useCallback(async () => {
    setError(null);
    const [settingsRes, todayRes] = await Promise.allSettled([
      axios.get(`${api}/admin/filter-settings`),
      axios.get(`${api}/admin/filter-cascade/today`),
    ]);
    if (settingsRes.status === "fulfilled" && settingsRes.value.data) {
      const s = settingsRes.value.data;
      setSavedSettings(s);
      setSettings({ ...s });
    }
    // The cascade endpoint reports its own errors inside a normal reply.
    if (todayRes.status === "fulfilled" && !todayRes.value.data?.error) {
      setTodayData(todayRes.value.data);
      setTodayFailed(false);
    } else {
      setTodayFailed(true);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const sim = useMemo(() => {
    if (!settings || !todayData || todayFailed) return null;
    return simulateFunnel(settings, todayData, savedSettings);
  }, [settings, todayData, todayFailed, savedSettings]);

  const chartData = useMemo(() => {
    if (!sim || !todayData) return [];
    return buildChartData(sim);
  }, [sim, todayData]);
  const rate = todayData?.usd_to_inr || null;

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
      setError("Couldn't save the settings. Nothing was changed, try again.");
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

  if (!settings) {
    return (
      <Card className="border border-border rounded-none bg-card border-l-4 border-l-violet-500">
        <CardContent className="p-4">
          <LoadError what="the filter settings" onRetry={load} />
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
          rate={rate}
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
                  Cheap pre-filter (keeps or drops each item before full classification)
                </p>
                <ToggleRow
                  label="Enabled"
                  value={settings.stage1_enabled}
                  onChange={update("stage1_enabled")}
                  warn={true}
                />
                <p className="text-[8px] font-mono text-muted-foreground/60 mt-1">
                  Turning this off costs more (every surviving item gets a full classification) but misses fewer items.
                </p>
              </div>

              <div>
                <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold mb-3">
                  Full classification capacity
                </p>
                <SliderRow
                  label="Max items scanned per cycle"
                  value={settings.stage2_max_scan}
                  min={50} max={500} step={25}
                  onChange={update("stage2_max_scan")}
                  hint="Higher = clears backlog faster. The simulation scales today's volume with this number."
                />
                <div className="mt-3">
                  <SliderRow
                    label="Max full classifications per cycle"
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
                {error && <p className="text-[9px] text-red-400 font-mono mt-1" role="alert">{error}</p>}
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
              {todayFailed && <LoadError what="today's filter figures" onRetry={load} />}
              {sim && (
                <div className="border border-border/30 p-3 bg-muted/5 space-y-2">
                  <p className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider font-semibold">
                    Estimated Impact (per day)
                  </p>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[9px] font-mono">
                    <span className="text-muted-foreground">Full classifications</span>
                    <span className="text-foreground font-bold">{Math.round(sim.haikuPerDay).toLocaleString()}</span>

                    <span className="text-muted-foreground">Est. cost</span>
                    <span className="text-emerald-400 font-bold">
                      {money(sim.costPerDayUsd, rate)}
                    </span>

                    <span className="text-muted-foreground">vs current</span>
                    <span className={sim.savingsPct >= 0 ? "text-emerald-400" : "text-red-400"}>
                      {sim.savingsPct >= 0 ? `-${sim.savingsPct}%` : `+${Math.abs(sim.savingsPct)}%`}
                    </span>

                    <span className="text-muted-foreground">Filter rate</span>
                    <span className="text-foreground">{Math.round(sim.filterRate * 100)}% before full classification</span>

                    <span className="text-muted-foreground">Coverage risk</span>
                    <span className={sim.riskColor}>{sim.coverageRisk.split(" —")[0]}</span>
                  </div>

                  {sim.prefilterOff && (
                    <div className="flex items-start gap-1.5 text-[8px] font-mono text-amber-400 mt-1">
                      <AlertTriangle size={9} className="shrink-0 mt-0.5" />
                      <span>Pre-filter off: higher cost, fewer missed items.</span>
                    </div>
                  )}
                  {sim.coverageRisk !== "LOW" && (
                    <div className="flex items-start gap-1.5 text-[8px] font-mono text-amber-400 mt-1">
                      <AlertTriangle size={9} className="shrink-0 mt-0.5" />
                      <span>{sim.coverageRisk}</span>
                    </div>
                  )}

                  <div className="flex items-start gap-1.5 text-[8px] font-mono text-muted-foreground/60 mt-1 border-t border-border/20 pt-1.5">
                    <Info size={8} className="shrink-0 mt-0.5" />
                    <span>
                      Uses today's real cycles as the baseline; the similarity estimate is a rough
                      straight-line guess (actual may differ by about 10%). Costs assume
                      ${COST_PER_CLASSIFY_CALL_USD} per full classification (measured 17 Nov 2026) and
                      ${COST_PER_PREFILTER_CALL_USD.toFixed(6)} per pre-filter check (listed price
                      ${PREFILTER_INPUT_PER_M} in / ${PREFILTER_OUTPUT_PER_M} out per million tokens, assuming{" "}
                      {PREFILTER_INPUT_TOKENS} tokens in and {PREFILTER_OUTPUT_TOKENS} out per item;
                      real text sizes are not available on this page).
                      {rate ? "" : " Live exchange rate unavailable, so dollars only."}
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
