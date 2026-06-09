"""
faultline_pdf.py — Faultline Analysis Report PDF (5 pages).

Same visual identity as the Monthly Strategic Brief (via brief_pdf_style.BriefPDF)
plus faultline-specific content:

  Page 1 — Cover + Key Metrics + MoM Level Distribution + Bottom Line (LLM B1)
  Page 2 — Priority Areas of Interest (P1->P5) with cached PAOI synthesis
  Page 3 — State-wise faultline tables + state narratives (10 states)
  Page 4 — Top 10 Movers + News Drivers (3 per mover) + outlooks (LLM B2)
  Page 5 — Cross-cutting Manual Review Advisory (LLM B3) + per-state roll-up

Data sources (all DB-resident — no re-scoring):
  - faultline_scores   (current month + previous month for MoM)
  - faultline_mappings (top news drivers per mover, joined with intelligence_items)
  - priority_areas     (PAOI registry for ordering)
  - monthly_briefs     (cached state_narratives + paoi_analysis synthesis)

LLM calls (Path B, 3 total):
  B1 — Bottom Line MoM executive (~700 tokens)
  B2 — Batched outlooks for top 10 movers (~1200 tokens, single call)
  B3 — Cross-cutting Manual Review Advisory (~500 tokens)
"""
import asyncio
import io
import logging
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

from brief_pdf_style import (
    BriefPDF, NL, ascii_safe, concern_level,
    C_TBL_HDR, C_TBL_ALT, C_SEC_TEXT, CONCERN_COLORS,
)

logger = logging.getLogger("faultline_pdf")


# ── Data aggregation ─────────────────────────────────────────────────────────
async def _load_month_scores(db, year: int, month: int) -> dict:
    """Returns {faultline_id: {first, last, peak, avg, days, state, name, level}}."""
    start = datetime(year, month, 1, tzinfo=timezone.utc).date()
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).date()
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc).date()

    cursor = db.faultline_scores.find(
        {"date": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
        {"_id": 0},
    ).sort([("faultline_id", 1), ("date", 1)])

    by_fl: dict = defaultdict(list)
    async for s in cursor:
        by_fl[s["faultline_id"]].append(s)

    out: dict = {}
    for fl_id, series in by_fl.items():
        series = sorted(series, key=lambda x: x["date"])
        scores = [s["score"] for s in series]
        out[fl_id] = {
            "id": fl_id,
            "name": series[-1].get("faultline_name", fl_id),
            "state": series[-1].get("state", ""),
            "first": round(scores[0], 1),
            "last": round(scores[-1], 1),
            "peak": round(max(scores), 1),
            "avg": round(sum(scores) / len(scores), 1),
            "delta_period": round(scores[-1] - scores[0], 1),
            "days": len(series),
            "level": concern_level(scores[-1]),
        }
    return out


async def aggregate_faultline_report(
    db, year: int, month: int
) -> dict:
    """Aggregate everything the PDF needs. No LLM here — that's a separate pass."""
    # Current + previous month scores for MoM
    curr = await _load_month_scores(db, year, month)
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    prev = await _load_month_scores(db, prev_year, prev_month)

    # MoM delta per faultline (using avg as the representative monthly value).
    # If no prior month data, delta_mom = None.
    for fl_id, c in curr.items():
        p = prev.get(fl_id)
        c["mom_delta"] = round(c["avg"] - p["avg"], 1) if p else None
        c["prev_avg"] = p["avg"] if p else None

    # Level distribution this month vs last
    def _dist(scores_dict: dict) -> dict:
        d = {"CRITICAL": 0, "ELEVATED": 0, "MONITOR": 0, "STABLE": 0}
        for s in scores_dict.values():
            lvl = concern_level(s["last"]) if scores_dict is curr else concern_level(s["avg"])
            d[lvl] = d.get(lvl, 0) + 1
        return d

    mom_levels = {
        "current": _dist(curr),
        "previous": _dist(prev),
    }
    mom_levels["delta"] = {
        k: mom_levels["current"].get(k, 0) - mom_levels["previous"].get(k, 0)
        for k in ("CRITICAL", "ELEVATED", "MONITOR", "STABLE")
    }

    # Key metrics
    fl_list = list(curr.values())
    rising = [f for f in fl_list if f["delta_period"] >= 10]
    declining = [f for f in fl_list if f["delta_period"] <= -10]
    critical_now = [f for f in fl_list if f["last"] >= 75]

    # Load cached brief (state_narratives + paoi_analysis synthesis)
    brief = await db.monthly_briefs.find_one(
        {"year": year, "month": month},
        {"_id": 0, "faultline_analysis": 1, "paoi_analysis": 1, "generated_at": 1},
    ) or {}
    state_narratives = (brief.get("faultline_analysis") or {}).get("state_narratives", {}) or {}
    paoi_analysis = brief.get("paoi_analysis") or {}

    # PAOI registry — used to order and group
    paois_cursor = db.priority_areas.find({"enabled": True}, {"_id": 0}).sort("rank", 1)
    paois = [p async for p in paois_cursor]

    # Attach per-PAOI faultline summaries (using curr scores)
    for pa in paois:
        fl_ids = pa.get("linked_faultline_ids", [])
        members = [curr[fid] for fid in fl_ids if fid in curr]
        members.sort(key=lambda x: -x["last"])
        pa["members"] = members
        if members:
            pa["max_score"] = max(m["last"] for m in members)
            pa["max_level"] = concern_level(pa["max_score"])
            # PAOI MoM delta = max member's MoM
            mom_vals = [m["mom_delta"] for m in members if m["mom_delta"] is not None]
            pa["mom_delta"] = round(max(mom_vals, key=abs), 1) if mom_vals else None
        else:
            pa["max_score"] = None
            pa["max_level"] = "STABLE"
            pa["mom_delta"] = None

    # Group faultlines by state (excluding pure-priority-only ones not needed)
    by_state: dict = defaultdict(list)
    for f in fl_list:
        by_state[f["state"] or "Unknown"].append(f)
    for st, lst in by_state.items():
        lst.sort(key=lambda x: -x["last"])
    state_summaries = []
    for st in sorted(by_state.keys(), key=lambda x: -max(f["last"] for f in by_state[x])):
        members = by_state[st]
        crit = sum(1 for m in members if m["last"] >= 75)
        elev = sum(1 for m in members if 55 <= m["last"] < 75)
        state_summaries.append({
            "state": st,
            "members": members,
            "max_score": members[0]["last"],
            "max_level": concern_level(members[0]["last"]),
            "n_critical": crit,
            "n_elevated": elev,
            "narrative": (state_narratives.get(st) or {}).get("summary", ""),
            "manual_review_advisory": (state_narratives.get(st) or {}).get(
                "manual_review_advisory", ""
            ),
        })

    # Top movers by |delta_period|, PAOI-linked first
    priority_fl_ids = set()
    for pa in paois:
        priority_fl_ids.update(pa.get("linked_faultline_ids", []))

    def _mover_key(f):
        is_priority = 0 if f["id"] in priority_fl_ids else 1
        return (is_priority, -abs(f["delta_period"]))

    top_movers = sorted(fl_list, key=_mover_key)[:10]

    # Top news drivers per mover (3 per mover, by impact_score desc)
    mover_ids = [m["id"] for m in top_movers]
    drivers_by_fl: dict = defaultdict(list)
    if mover_ids:
        start_iso = datetime(year, month, 1, tzinfo=timezone.utc).date().isoformat()
        end_iso = (datetime(year + (month // 12), (month % 12) + 1, 1, tzinfo=timezone.utc)
                   .date().isoformat())
        m_cursor = db.faultline_mappings.find(
            {
                "faultline_id": {"$in": mover_ids},
                "date": {"$gte": start_iso, "$lt": end_iso},
                "confidence": {"$gte": 45},
            },
            {"_id": 0, "faultline_id": 1, "article_id": 1, "impact_score": 1,
             "confidence": 1, "rationale": 1, "article_title": 1,
             "article_published_at": 1, "article_severity": 1},
        ).sort("impact_score", -1).limit(500)
        async for m in m_cursor:
            slot = drivers_by_fl[m["faultline_id"]]
            if len(slot) < 3:
                slot.append(m)

        # Fetch source URLs in one go
        all_aids = [d["article_id"] for ds in drivers_by_fl.values() for d in ds]
        if all_aids:
            meta_cursor = db.intelligence_items.find(
                {"id": {"$in": all_aids}},
                {"_id": 0, "id": 1, "source": 1, "source_url": 1},
            )
            meta_map = {x["id"]: x async for x in meta_cursor}
            for ds in drivers_by_fl.values():
                for d in ds:
                    meta = meta_map.get(d["article_id"], {})
                    d["source"] = meta.get("source", "")
                    d["source_url"] = meta.get("source_url", "")

    for m in top_movers:
        m["drivers"] = drivers_by_fl.get(m["id"], [])

    return {
        "year": year, "month": month,
        "prev_year": prev_year, "prev_month": prev_month,
        "month_name": datetime(year, month, 1).strftime("%B %Y"),
        "prev_month_name": datetime(prev_year, prev_month, 1).strftime("%B %Y"),
        "generated_at": brief.get("generated_at", ""),
        "all_faultlines": fl_list,
        "key_metrics": {
            "total": len(fl_list),
            "critical_now": len(critical_now),
            "rising_period": len(rising),
            "declining_period": len(declining),
        },
        "mom_levels": mom_levels,
        "paois": paois,
        "state_summaries": state_summaries,
        "top_movers": top_movers,
        "paoi_analysis": paoi_analysis,
        "state_narratives": state_narratives,
    }


# ── LLM synthesis (Path B — 3 calls) ──────────────────────────────────────────
def _b1_bottom_line_prompt(agg: dict) -> str:
    km = agg["key_metrics"]
    lv = agg["mom_levels"]
    lines = [
        f"Period: {agg['month_name']} vs {agg['prev_month_name']}.",
        f"Total faultlines monitored: {km['total']}.",
        f"Currently CRITICAL: {km['critical_now']}.",
        f"Rising this period (Δ>=+10): {km['rising_period']}.",
        f"Declining (Δ<=-10): {km['declining_period']}.",
        "",
        "Level distribution MoM:",
    ]
    for lvl in ("CRITICAL", "ELEVATED", "MONITOR", "STABLE"):
        c = lv["current"].get(lvl, 0)
        p = lv["previous"].get(lvl, 0)
        d = lv["delta"].get(lvl, 0)
        lines.append(f"  {lvl}: {c} (prev {p}, Δ {d:+d})")

    # Top movers context
    if agg["top_movers"]:
        lines.append("")
        lines.append("Top 5 movers (state, faultline, current score, period Δ, MoM Δ):")
        for f in agg["top_movers"][:5]:
            mom = f["mom_delta"] if f["mom_delta"] is not None else "n/a"
            lines.append(
                f"  [{f['state']}] {f['name']}: now {f['last']:.0f}, "
                f"period Δ {f['delta_period']:+.1f}, MoM Δ {mom}"
            )

    return (
        "You are writing the BOTTOM LINE for a Faultline Analysis Report.\n\n"
        + "\n".join(lines) + "\n\n"
        + "Write 5-7 sentences. Open with the single most important read of the\n"
        + "month. Cover MoM movement direction (escalation or de-escalation),\n"
        + "which faultline area drove it, and the 1-2 sharpest moves. Use claim\n"
        + "labels [CONFIRMED] for direct data, [ASSESSED] for inference.\n\n"
        + "Return strict JSON: {\"bottom_line\": \"...\"}"
    )


def _b2_movers_prompt(agg: dict) -> str:
    items = []
    for i, m in enumerate(agg["top_movers"], 1):
        mom = m["mom_delta"] if m["mom_delta"] is not None else "n/a"
        drivers_str = ""
        if m.get("drivers"):
            drivers_str = " Top drivers: " + "; ".join(
                d.get("article_title", "")[:80] for d in m["drivers"][:2]
            )
        items.append(
            f"{i}. id={m['id']} [{m['state']}] {m['name']}: now {m['last']:.0f} "
            f"(start {m['first']:.0f}, peak {m['peak']:.0f}, period Δ {m['delta_period']:+.1f}, "
            f"MoM Δ {mom}).{drivers_str}"
        )
    return (
        "You are writing FORWARD OUTLOOK statements for top mover faultlines.\n\n"
        "Top 10 movers this period:\n" + "\n".join(items) + "\n\n"
        + "For EACH faultline (by its `id`), give a 1-sentence forward outlook\n"
        + "describing the most likely movement in the COMING MONTH and the key\n"
        + "indicator to watch. Use [ASSESSED] for inferences, [SPECULATIVE] for\n"
        + "forecasts. Be specific and grounded — name actors, locations, or events.\n\n"
        + "Return strict JSON keyed by id: {\"<id1>\": \"outlook...\", \"<id2>\": \"...\"}"
    )


def _b3_advisory_prompt(agg: dict) -> str:
    # Synthesise across rising faultlines + critical PAOI areas
    rising = [f for f in agg["all_faultlines"] if f["delta_period"] >= 10][:8]
    critical = [f for f in agg["all_faultlines"] if f["last"] >= 75][:8]
    lines = ["Rising faultlines (need manual review):"]
    for r in rising:
        lines.append(f"  [{r['state']}] {r['name']} - now {r['last']:.0f}, Δ {r['delta_period']:+.1f}")
    lines.append("\nCritical faultlines (sustained high concern):")
    for c in critical:
        lines.append(f"  [{c['state']}] {c['name']} - {c['last']:.0f}")

    return (
        "You are writing the cross-cutting MANUAL REVIEW ADVISORY for a Faultline\n"
        "Analysis Report. The reader is a commander who must decide where to\n"
        "spend manual OSINT effort beyond automated coverage.\n\n"
        + "\n".join(lines) + "\n\n"
        + "Write ONE paragraph (4-6 sentences) advising:\n"
        + "  1. The single most important narrative spike or actor network to inspect\n"
        + "     manually this month (cross-state if possible)\n"
        + "  2. Specific channels/sources worth checking (regional language press,\n"
        + "     local Telegram channels, influencer amplification patterns)\n"
        + "  3. The borderline / weak-signal faultline most worth a second look\n\n"
        + "Use [ASSESSED] / [SPECULATIVE] labels where useful.\n"
        + "Return strict JSON: {\"advisory\": \"paragraph...\"}"
    )


async def run_pdf_synthesis(agg: dict, call_llm_json) -> dict:
    """Run B1+B2+B3 in parallel. Returns {bottom_line, mover_outlooks{}, advisory}."""
    b1_task = call_llm_json(_b1_bottom_line_prompt(agg), max_tokens=700)
    b2_task = (call_llm_json(_b2_movers_prompt(agg), max_tokens=1500)
               if agg["top_movers"] else asyncio.sleep(0, result={}))
    b3_task = call_llm_json(_b3_advisory_prompt(agg), max_tokens=600)

    b1, b2, b3 = await asyncio.gather(b1_task, b2_task, b3_task, return_exceptions=True)

    def _safe(r, key=None):
        if isinstance(r, Exception):
            logger.warning(f"Faultline PDF LLM call failed: {r}")
            return {}
        if not isinstance(r, dict):
            return {}
        return r.get(key, "") if key else r

    bottom_line = _safe(b1, "bottom_line") or ""
    mover_outlooks = _safe(b2) or {}
    advisory = _safe(b3, "advisory") or ""

    return {
        "bottom_line": bottom_line,
        "mover_outlooks": mover_outlooks,
        "advisory": advisory,
    }


# ── PDF rendering (5 pages) ───────────────────────────────────────────────────
def _color_for_delta(delta: float) -> tuple:
    if delta >= 5:
        return (200, 50, 50)    # rising = red
    if delta <= -5:
        return (60, 140, 70)    # falling = green
    return (120, 120, 120)      # steady = grey


def _short_state(name: str) -> str:
    s = (name or "").strip()
    aliases = {
        "Bangladesh": "BD", "Myanmar": "MM",
        "North Bengal": "NBN", "Meghalaya": "Megh", "Manipur": "Man",
        "Tripura": "Trp", "Mizoram": "Miz", "Nagaland": "Nag", "Assam": "Asm",
    }
    return aliases.get(s, s[:6])


def render_faultline_pdf(agg: dict, synthesis: dict) -> bytes:
    pdf = BriefPDF()
    pdf.brief_type = "FAULTLINE ANALYSIS REPORT"
    pdf.display_period = agg["month_name"]
    pdf.gen_ts = (agg.get("generated_at") or
                  datetime.now(timezone.utc).isoformat())[:19].replace("T", " ")
    pdf.alias_nb_pages()
    pdf.set_margins(10, 32, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    # ──────────────── PAGE 1 — Cover + Snapshot ──────────────────────────────
    pdf.add_page()
    km = agg["key_metrics"]
    lv = agg["mom_levels"]

    pdf.section_title("Key Metrics")
    # 4-stat row
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*C_SEC_TEXT)
    stats = [
        ("Faultlines",       km["total"]),
        ("CRITICAL Now",     km["critical_now"]),
        ("Rising (>=+10)",   km["rising_period"]),
        ("Declining (<=-10)", km["declining_period"]),
    ]
    for label, val in stats:
        pdf.cell(45, 8, ascii_safe(f"  {label}: {val}"), border=1, **NL)
    pdf.ln(2)

    # MoM Level Distribution
    pdf.section_title("Concern Level Distribution",
                      f"{agg['month_name']} vs {agg['prev_month_name']}")
    pdf.set_fill_color(*C_TBL_HDR); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(45, 6, "  Level",       fill=True)
    pdf.cell(45, 6, "This Month",    fill=True, align="C")
    pdf.cell(45, 6, "Last Month",    fill=True, align="C")
    pdf.cell(45, 6, "Delta",         fill=True, align="C", **NL)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    for i, lvl in enumerate(("CRITICAL", "ELEVATED", "MONITOR", "STABLE")):
        col = CONCERN_COLORS[lvl]
        c = lv["current"].get(lvl, 0)
        p = lv["previous"].get(lvl, 0)
        d = lv["delta"].get(lvl, 0)
        if i % 2 == 0:
            pdf.set_fill_color(*C_TBL_ALT); fill = True
        else:
            fill = False
        pdf.set_text_color(*col); pdf.set_font("Helvetica", "B", 9)
        pdf.cell(45, 6, ascii_safe(f"  {lvl}"), fill=fill)
        pdf.set_text_color(40, 40, 40); pdf.set_font("Helvetica", "", 9)
        pdf.cell(45, 6, str(c), fill=fill, align="C")
        pdf.cell(45, 6, str(p), fill=fill, align="C")
        delta_str = f"{d:+d}"
        pdf.set_text_color(*_color_for_delta(d))
        pdf.cell(45, 6, delta_str, fill=fill, align="C", **NL)
        pdf.set_text_color(40, 40, 40)
    pdf.ln(2)

    # Bottom Line (B1)
    pdf.section_title("Bottom Line",
                      f"MoM Executive Read | {agg['month_name']}")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    bl = synthesis.get("bottom_line") or "Bottom line synthesis unavailable for this period."
    pdf.multi_cell(0, 5, ascii_safe(bl), **NL)

    # ──────────────── PAGE 2 — Priority Areas of Interest ────────────────────
    pdf.add_page()
    pdf.section_title("Priority Areas of Interest",
                      "Commander Ranked | Top Faultlines + Period Read")
    paois = agg.get("paois", [])
    per_paoi = (agg.get("paoi_analysis") or {}).get("synthesis", {}).get("per_paoi", {})

    for pa in paois:
        members = pa.get("members") or []
        max_score = pa.get("max_score")
        if max_score is None:
            max_score = 0
        level = pa.get("max_level", "STABLE")
        mom = pa.get("mom_delta")
        mom_str = "" if mom is None else f"  MoM Δ {mom:+.1f}"
        sub_text = f"P{pa.get('rank')} {pa.get('name')}   {max_score:.0f} {level}{mom_str}"
        col = CONCERN_COLORS.get(level, (60, 80, 50))
        pdf.sub_band(sub_text, fill_rgb=col)

        # Top-3 mini table
        pdf.set_fill_color(*C_TBL_HDR); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(90, 5, "  Faultline", fill=True)
        pdf.cell(30, 5, "Now",        fill=True, align="C")
        pdf.cell(30, 5, ascii_safe("MoM D"), fill=True, align="C")
        pdf.cell(40, 5, "Level",      fill=True, align="C", **NL)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 40, 40)
        for i, m in enumerate(members[:3]):
            if i % 2 == 0:
                pdf.set_fill_color(*C_TBL_ALT); fill = True
            else:
                fill = False
            mom = m["mom_delta"]
            mom_str = "n/a" if mom is None else f"{mom:+.1f}"
            pdf.cell(90, 5, ascii_safe(f"  {m['name'][:55]}"), fill=fill)
            pdf.cell(30, 5, f"{m['last']:.0f}", fill=fill, align="C")
            pdf.cell(30, 5, mom_str, fill=fill, align="C")
            pdf.set_text_color(*CONCERN_COLORS[m["level"]])
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(40, 5, m["level"], fill=fill, align="C", **NL)
            pdf.set_text_color(40, 40, 40)
            pdf.set_font("Helvetica", "", 8)

        # Period impact + watch next (reused from cached PAOI synthesis)
        syn = per_paoi.get(pa["id"]) or {}
        pi = syn.get("period_impact") or ""
        wn = syn.get("forward_concerns") or ""
        if pi:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)
            # Trim to ~2 sentences
            pdf.multi_cell(0, 4, ascii_safe(pi[:300]), **NL)
        if wn:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 80, 20)
            pdf.multi_cell(0, 4, ascii_safe(f"Watch next: {wn[:200]}"), **NL)
        pdf.ln(1)

    # ──────────────── PAGE 3 — State Faultline Tables ────────────────────────
    pdf.add_page()
    pdf.section_title("State-wise Faultline Status",
                      "Sorted by Maximum Score Descending")
    for st in agg["state_summaries"]:
        if pdf.get_y() > 250:
            pdf.add_page()
        level = st["max_level"]
        col = CONCERN_COLORS.get(level, (60, 80, 50))
        sub_text = (f"{st['state']}   Max {st['max_score']:.0f} {level}   "
                    f"{st['n_critical']}C / {st['n_elevated']}E")
        pdf.sub_band(sub_text, fill_rgb=col, height=5.5)

        # Top-4 faultlines mini table
        pdf.set_fill_color(*C_TBL_HDR); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(85, 5, "  Faultline", fill=True)
        pdf.cell(20, 5, "Now",         fill=True, align="C")
        pdf.cell(20, 5, ascii_safe("MoM D"),    fill=True, align="C")
        pdf.cell(20, 5, ascii_safe("Period D"), fill=True, align="C")
        pdf.cell(20, 5, "Peak",        fill=True, align="C")
        pdf.cell(25, 5, "Level",       fill=True, align="C", **NL)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(40, 40, 40)
        for i, m in enumerate(st["members"][:4]):
            if i % 2 == 0:
                pdf.set_fill_color(*C_TBL_ALT); fill = True
            else:
                fill = False
            mom = m["mom_delta"]
            mom_str = "n/a" if mom is None else f"{mom:+.1f}"
            pdf.cell(85, 5, ascii_safe(f"  {m['name'][:52]}"), fill=fill)
            pdf.cell(20, 5, f"{m['last']:.0f}",       fill=fill, align="C")
            pdf.cell(20, 5, mom_str,                  fill=fill, align="C")
            pdf.cell(20, 5, f"{m['delta_period']:+.1f}", fill=fill, align="C")
            pdf.cell(20, 5, f"{m['peak']:.0f}",       fill=fill, align="C")
            pdf.set_text_color(*CONCERN_COLORS[m["level"]])
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(25, 5, m["level"],                fill=fill, align="C", **NL)
            pdf.set_text_color(40, 40, 40)
            pdf.set_font("Helvetica", "", 7)

        # 2-line state narrative
        narr = (st.get("narrative") or "")
        if narr:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 4, ascii_safe(narr[:240]), **NL)
        pdf.ln(1)

    # ──────────────── PAGE 4 — Top 10 Movers + News Drivers ──────────────────
    pdf.add_page()
    pdf.section_title("Top 10 Movers + News Drivers",
                      "Priority-First | 3 Top Drivers Each")
    mover_outlooks = synthesis.get("mover_outlooks") or {}

    for i, m in enumerate(agg["top_movers"], 1):
        if pdf.get_y() > 245:
            pdf.add_page()
        level = m["level"]
        col = CONCERN_COLORS.get(level, (60, 80, 50))
        mom = m["mom_delta"]
        mom_str = "" if mom is None else f"  MoM Δ {mom:+.1f}"
        hdr = (f"#{i}  [{m['state']}]  {m['name']}   {m['last']:.0f} {level}   "
               f"Period Δ {m['delta_period']:+.1f}{mom_str}")
        pdf.sub_band(hdr, fill_rgb=col, height=5.5)

        # Movement line
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 4, ascii_safe(
            f"  Movement: Start {m['first']:.0f} -> Peak {m['peak']:.0f} "
            f"-> End {m['last']:.0f}   ({m['days']} days)"
        ), **NL)

        # Top 3 drivers
        for j, d in enumerate(m.get("drivers") or [], 1):
            title = (d.get("article_title") or "")[:95]
            src = (d.get("source") or "")[:25]
            date = (d.get("article_published_at") or "")[:10]
            sev = d.get("article_severity") or ""
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(*C_SEC_TEXT)
            pdf.multi_cell(0, 3.5, ascii_safe(
                f"    {j}. [{date}|{sev}] {title}  ({src})"
            ), **NL)
            rationale = (d.get("rationale") or "")[:160]
            if rationale:
                pdf.set_font("Helvetica", "I", 7)
                pdf.set_text_color(80, 80, 80)
                pdf.multi_cell(0, 3.5, ascii_safe(f"       Rationale: {rationale}"), **NL)

        # Forward outlook (B2, batched)
        outlook = mover_outlooks.get(m["id"]) if isinstance(mover_outlooks, dict) else None
        if outlook:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 80, 20)
            pdf.multi_cell(0, 4, ascii_safe(f"  Watch next: {outlook[:280]}"), **NL)
        pdf.ln(1)

    # ──────────────── PAGE 5 — Manual Review Advisory ────────────────────────
    pdf.add_page()
    pdf.section_title("Manual Review Advisory",
                      "Cross-Cutting + Per-State Roll-up")

    # B3 cross-cutting paragraph
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*C_SEC_TEXT)
    pdf.cell(0, 6, "  Commander Advisory (cross-state synthesis)", **NL)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    adv = synthesis.get("advisory") or (
        "Cross-cutting advisory synthesis unavailable for this period. "
        "Review rising faultlines individually using the state-by-state advisory "
        "below as a starting point."
    )
    pdf.multi_cell(0, 5, ascii_safe(adv), **NL)
    pdf.ln(2)

    # Per-state advisory roll-up
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*C_SEC_TEXT)
    pdf.cell(0, 6, "  Per-State Manual Review Notes", **NL)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(60, 60, 60)
    for st in agg["state_summaries"]:
        advisory = st.get("manual_review_advisory") or ""
        if not advisory:
            continue
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_SEC_TEXT)
        pdf.cell(0, 5, ascii_safe(f"  {st['state']}"), **NL)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 4, ascii_safe(f"    {advisory[:280]}"), **NL)
        pdf.ln(1)

    return bytes(pdf.output())
