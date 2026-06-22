"""
Fortnightly Strategic Intelligence Brief — covers a 14-day window.

Periods:
  Period 1: days 1–15 of month
  Period 2: days 16–end of month

Endpoints:
  POST /brief/fortnightly/generate?year=Y&month=M&period=1|2
  GET  /brief/fortnightly/{year}/{month}/{period}
  GET  /brief/fortnightly/list
  GET  /brief/fortnightly/{year}/{month}/{period}/pdf
  GET  /brief/fortnightly/{year}/{month}/{period}/notebooklm

Reuses all LLM prompts, aggregation, and rendering from brief_monthly.
"""
import asyncio
import io
from calendar import monthrange
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse

from shared import db, logger
from utils.auth import get_current_user
from routers.brief_monthly import _require_brief_author

# ── Import shared machinery from brief_monthly ────────────────────────────────
from routers.brief_monthly import (
    _aggregate_month_stats,
    _exec_summary_prompt,
    _state_section_prompt,
    _mitigation_playbook_prompt,
    _scenarios_prompt,
    _cross_border_prompt,
    _call_llm_json,
    _call_llm_text,
    _coerce_state_section,
    _build_notebooklm_script,
    _render_pdf,
    _aggregate_faultline_section,
    NER_STATES_FULL,
    BORDER_COUNTRIES,
)

router = APIRouter()
fortnightly_briefs_col = db.fortnightly_briefs


async def _build_fortnightly_paoi(year, month, period, start_iso, end_iso, period_label, force_rich: bool = False) -> dict:
    """PAOI analysis for a fortnightly brief. Rich first gen or when force_rich=True, lean on regen."""
    import paoi_brief
    prior = await fortnightly_briefs_col.find_one(
        {"year": year, "month": month, "period": period},
        {"_id": 0, "generation_count": 1},
    )
    prior_count = (prior or {}).get("generation_count", 0)
    tier = "rich" if (prior_count == 0 or force_rich) else "lean"
    try:
        agg = await paoi_brief.aggregate_paoi_period(db, start_iso, end_iso)
        dashboard = paoi_brief.build_commander_dashboard(agg)
        synthesis = await paoi_brief.run_paoi_synthesis(
            db, agg, dashboard, period_label, tier, _call_llm_json
        )
        other = await paoi_brief.other_faultline_movements(db, start_iso, end_iso)
        return {
            "available": bool(agg.get("paois")),
            "commander_dashboard": dashboard,
            "paois": agg.get("paois", []),
            "synthesis": synthesis,
            "other_movements": other,
            "synthesis_tier": tier,
            "_next_generation_count": prior_count + 1,
        }
    except Exception as e:
        logger.exception(f"Fortnightly PAOI build failed: {e}")
        return {
            "available": False, "commander_dashboard": [], "paois": [],
            "synthesis": {}, "other_movements": {},
            "synthesis_tier": tier, "_next_generation_count": prior_count + 1,
        }


# ── Period helpers ─────────────────────────────────────────────────────────────

def _fortnightly_range(year: int, month: int, period: int):
    """Return (start_iso, end_iso, label) for the given fortnightly period."""
    if period == 1:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end   = datetime(year, month, 16, tzinfo=timezone.utc)
        label = f"1-15 {start.strftime('%B %Y')}"
    else:
        start = datetime(year, month, 16, tzinfo=timezone.utc)
        last_day = monthrange(year, month)[1]
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        label = f"16-{last_day} {start.strftime('%B %Y')}"
    return start.isoformat(), end.isoformat(), label


def _current_fortnightly_default():
    """Return (year, month, period) for the most recently COMPLETED fortnightly period."""
    now = datetime.now(timezone.utc)
    if now.day <= 15:
        # We're in period 1 of current month — most recently completed = period 2 of last month
        if now.month == 1:
            return now.year - 1, 12, 2
        return now.year, now.month - 1, 2
    else:
        # We're in period 2 — most recently completed = period 1 of current month
        return now.year, now.month, 1


def _fortnightly_exec_summary_prompt(stats: dict, period_label: str) -> str:
    top_actors = ", ".join([f"{a[0]} ({a[1]})" for a in stats["top_actors"][:8]])
    top_cats   = ", ".join([f"{c[0]} ({c[1]})" for c in stats["top_categories"][:6]])
    top_concern = ", ".join([f"{s['state']} ({s['score']}/100 {s['level']})" for s in stats["stability"][:3]])
    return f"""You are the Chief Intelligence Analyst, NER Theatre Command. Write the EXECUTIVE STRATEGIC ASSESSMENT section of the fortnightly intelligence brief for {period_label}.

DATA FOR THE FORTNIGHT:
- Total intelligence items processed: {stats['total']}
- Severity breakdown: {stats['sev_counts']}
- Cross-border items: {stats['cross_border_count']}
- Top actors: {top_actors}
- Top threat categories: {top_cats}
- Most-concerning states: {top_concern}

REQUIREMENTS:
- 3-4 paragraphs maximum (fortnightly is shorter than monthly).
- Open with regional overview. Then key developments of the fortnight. Then near-term outlook.
- Tone: senior military intelligence briefing. Crisp, declarative.
- Label EVERY substantive claim: [CONFIRMED], [ASSESSED], or [SPECULATIVE].

Output: prose only. No headers, no markdown bullets."""


def _fortnightly_scenarios_prompt(stats: dict, period_label: str) -> str:
    top_concern = ", ".join([f"{s['state']} ({s['score']}/100 {s['level']})" for s in stats["stability"][:4]])
    return f"""You are the Predictive Intelligence Cell. Generate 2 STRATEGIC SCENARIOS for NER for the 15-30 days following {period_label}.

Context: Most-concerning states: {top_concern}. Top actors: {", ".join([a[0] for a in stats["top_actors"][:8]])}. Cross-border incidents: {stats["cross_border_count"]}.

Return STRICT JSON only:
{{
  "scenarios": [
    {{
      "title": "Concise scenario name",
      "narrative": "2-3 sentences. What unfolds, where, who drives it.",
      "confidence_pct": 35,
      "warning_indicators": ["observable 1", "observable 2"],
      "horizon": "H+15|H+30",
      "trigger_factors": "1-2 sentences on what would push probability higher"
    }},
    ...2 scenarios total
  ]
}}"""


# ── Generation orchestrator ───────────────────────────────────────────────────

async def _run_fortnightly_generation(year: int, month: int, period: int, force_rich: bool = False):
    start_iso, end_iso, period_label = _fortnightly_range(year, month, period)
    logger.info(f"Fortnightly brief generation start: {period_label}")

    # Stats aggregation — reuse monthly logic but with fortnightly range
    stats = await _aggregate_month_stats.__wrapped__(year, month) if hasattr(_aggregate_month_stats, "__wrapped__") else None
    # _aggregate_month_stats uses year/month → compute month range then filter by our range
    # Simpler: call the underlying aggregation directly by re-using the module's function
    # with the correct range via a monkey-patched call. Instead, we use the shared helper
    # by passing start_iso/end_iso via the collection query directly.
    from shared import intelligence_col
    from collections import Counter, defaultdict
    from datetime import timedelta

    _SEV_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    q = {
        "published_at": {"$gte": start_iso, "$lt": end_iso},
        "processed": True,
        "severity": {"$nin": ["filtered_out"]},
        "tags": {"$nin": ["not_relevant", "stage0_filtered", "stage05_filtered", "stage1_filtered"]},
    }

    total = 0
    sev_counts = Counter()
    state_stats = defaultdict(lambda: {
        "total": 0, "sev_counts": Counter(),
        "actors": Counter(), "locations": Counter(),
        "categories": Counter(), "daily": Counter(),
        "critical_items": [], "high_items": [], "analyst_notes": [],
    })
    overall_actors    = Counter()
    overall_locations = Counter()
    overall_cats      = Counter()
    daily_severity    = defaultdict(lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0})
    cross_border_count = 0
    _BD_STATES = {"Assam", "Tripura", "Meghalaya"}
    _MM_STATES = {"Manipur", "Nagaland", "Mizoram", "Arunachal Pradesh"}
    cb_bangladesh: list = []
    cb_myanmar: list = []

    async for item in intelligence_col.find(q, {
        "id": 1, "title": 1, "severity": 1, "state": 1, "threat_category": 1,
        "published_at": 1, "entities": 1, "summary": 1, "ai_summary": 1,
        "analyst_enhancement": 1, "is_cross_border": 1, "countries_involved": 1, "_id": 0,
    }):
        total += 1
        sev = item.get("severity") or "low"
        sev_counts[sev] += 1
        state = item.get("state") or "Unknown"
        cat = item.get("threat_category") or "Other"
        overall_cats[cat] += 1
        pub_date = (item.get("published_at") or "")[:10]
        if pub_date:
            if sev in daily_severity[pub_date]:
                daily_severity[pub_date][sev] += 1
            daily_severity[pub_date]["total"] += 1

        locs = (item.get("entities") or {}).get("locations") or []
        orgs = (item.get("entities") or {}).get("organizations") or []
        for a in orgs[:5]:
            if a:
                overall_actors[a] += 1
        for l in locs[:5]:
            if l and l not in NER_STATES_FULL and l not in BORDER_COUNTRIES:
                overall_locations[l] += 1
        if any(c in BORDER_COUNTRIES for c in locs) or state in BORDER_COUNTRIES:
            cross_border_count += 1

        if item.get("is_cross_border"):
            countries = item.get("countries_involved") or []
            _cb_rec = {
                "title": (item.get("title") or "")[:180],
                "severity": sev, "state": state, "category": cat, "date": pub_date,
                "summary": (item.get("ai_summary") or item.get("summary") or "")[:200],
            }
            if "Bangladesh" in countries or state in _BD_STATES:
                if len(cb_bangladesh) < 10:
                    cb_bangladesh.append(_cb_rec)
            elif "Myanmar" in countries or state in _MM_STATES:
                if len(cb_myanmar) < 10:
                    cb_myanmar.append(_cb_rec)

        if state in NER_STATES_FULL:
            s = state_stats[state]
            s["total"] += 1
            s["sev_counts"][sev] += 1
            s["categories"][cat] += 1
            for a in orgs[:5]:
                if a:
                    s["actors"][a] += 1
            for l in locs[:5]:
                if l and l not in NER_STATES_FULL and l not in BORDER_COUNTRIES:
                    s["locations"][l] += 1
            if pub_date:
                s["daily"][pub_date] += 1
            if sev == "critical" and len(s["critical_items"]) < 8:
                s["critical_items"].append({
                    "id": item.get("id"), "title": (item.get("title") or "")[:200],
                    "date": pub_date, "summary": (item.get("summary") or "")[:300],
                })
            elif sev == "high" and len(s["high_items"]) < 8:
                s["high_items"].append({
                    "id": item.get("id"), "title": (item.get("title") or "")[:200],
                    "date": pub_date,
                })
            enh = item.get("analyst_enhancement") or {}
            if enh.get("is_enhanced") and enh.get("analyst_note") and len(s["analyst_notes"]) < 6:
                s["analyst_notes"].append({
                    "note": enh["analyst_note"][:500],
                    "by": enh.get("enhanced_by_name", "Analyst"),
                    "date": pub_date,
                    "item_title": (item.get("title") or "")[:150],
                    "severity": sev,
                })

    if total == 0:
        doc = {
            "year": year, "month": month, "period": period,
            "period_label": period_label,
            "status": "empty",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": f"No intelligence items found for {period_label}",
        }
        await fortnightly_briefs_col.replace_one(
            {"year": year, "month": month, "period": period}, doc, upsert=True
        )
        return doc

    states_out = {}
    for st, s in state_stats.items():
        states_out[st] = {
            "total":          s["total"],
            "sev_counts":     dict(s["sev_counts"]),
            "top_actors":     s["actors"].most_common(8),
            "top_locations":  s["locations"].most_common(8),
            "top_categories": s["categories"].most_common(8),
            "daily_volume":   sorted(s["daily"].items()),
            "critical_items": s["critical_items"],
            "high_items":     s["high_items"],
            "analyst_notes":  s["analyst_notes"],
        }

    # Stability scores (same formula as monthly)
    days = max((datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)).days, 1)
    third_days = max(days // 3, 1)
    early_cutoff = (datetime.fromisoformat(start_iso) + timedelta(days=third_days)).isoformat()
    late_cutoff  = (datetime.fromisoformat(end_iso)   - timedelta(days=third_days)).isoformat()
    max_sev_w = 1
    for st in NER_STATES_FULL:
        sw = sum(_SEV_WEIGHT.get(k, 0) * v for k, v in states_out.get(st, {}).get("sev_counts", {}).items())
        max_sev_w = max(max_sev_w, sw)

    early_late = defaultdict(lambda: [0, 0])
    async for item in intelligence_col.find(q, {"published_at": 1, "state": 1, "_id": 0}):
        st = item.get("state") or ""
        if st not in NER_STATES_FULL:
            continue
        pub = item.get("published_at") or ""
        if pub < early_cutoff:
            early_late[st][0] += 1
        if pub >= late_cutoff:
            early_late[st][1] += 1

    stability = []
    for st in NER_STATES_FULL:
        s_sev = states_out.get(st, {}).get("sev_counts", {})
        sw = sum(_SEV_WEIGHT.get(k, 0) * v for k, v in s_sev.items())
        severity_load = sw / max_sev_w if max_sev_w else 0
        early, late  = early_late[st]
        velocity = min(late / early / 3, 1.0) if early > 0 else (0.8 if late > 0 else 0.0)
        actors_count = len(states_out.get(st, {}).get("top_actors", []))
        actor_spread = min(actors_count / 8, 1.0)
        concern = severity_load * 0.40 + velocity * 0.25 + actor_spread * 0.20
        score = max(0, round(100 - concern * 100))
        level = "STABLE" if score >= 75 else "MONITOR" if score >= 50 else "ELEVATED" if score >= 25 else "CRITICAL"
        stability.append({"state": st, "score": score, "level": level,
                          "severity_load": round(severity_load, 2), "velocity": round(velocity, 2)})

    # Bangladesh + Myanmar cards (commander ask) — same inverted formula,
    # scoped to cross-border regions (regions[]/countries_involved).
    for region_name, region_match in [
        ("Bangladesh", {"$or": [{"regions": "Bangladesh"}, {"countries_involved": "Bangladesh"}, {"state": "Bangladesh"}]}),
        ("Myanmar", {"$or": [{"regions": "Myanmar"}, {"countries_involved": "Myanmar"}, {"state": "Myanmar"}]}),
    ]:
        rq = {**q, **region_match}
        r_sev: Counter = Counter()
        r_actors_counter: Counter = Counter()
        r_cats_counter: Counter = Counter()
        r_total = 0
        r_early = r_late = 0
        async for item in intelligence_col.find(
            rq,
            {"published_at": 1, "severity": 1, "actors": 1,
             "threat_category": 1, "tags": 1, "_id": 0},
        ):
            r_total += 1
            r_sev[item.get("severity", "low")] += 1
            for a in (item.get("actors") or []):
                if a:
                    r_actors_counter[a] += 1
            cat = item.get("threat_category")
            if not cat:
                tags = item.get("tags") or []
                cat = tags[0] if tags else None
            if cat:
                r_cats_counter[cat] += 1
            pub = item.get("published_at") or ""
            if pub < early_cutoff:
                r_early += 1
            if pub >= late_cutoff:
                r_late += 1
        sw = sum(_SEV_WEIGHT.get(k, 0) * v for k, v in r_sev.items())
        severity_load = sw / max_sev_w if max_sev_w else 0
        velocity = min(r_late / r_early / 3, 1.0) if r_early > 0 else (0.8 if r_late > 0 else 0.0)
        actor_spread = min(len(r_actors_counter) / 8, 1.0)
        concern = severity_load * 0.40 + velocity * 0.25 + actor_spread * 0.20 + 1.0 * 0.15
        score = max(0, round(100 - concern * 100))
        level = "STABLE" if score >= 75 else "MONITOR" if score >= 50 else "ELEVATED" if score >= 25 else "CRITICAL"
        stability.append({"state": region_name, "score": score, "level": level,
                          "severity_load": round(severity_load, 2), "velocity": round(velocity, 2),
                          "is_cross_border_region": True})

        # Populate states_out so the mitigation_playbook loop picks up BD/Myanmar.
        states_out[region_name] = {
            "total":          r_total,
            "sev_counts":     dict(r_sev),
            "top_actors":     r_actors_counter.most_common(8),
            "top_locations":  [],
            "top_categories": r_cats_counter.most_common(8),
            "daily_volume":   [],
            "critical_items": [],
            "high_items":     [],
            "is_cross_border_region": True,
        }

    stability.sort(key=lambda x: x["score"])

    stats = {
        "period_start": start_iso, "period_end": end_iso,
        "total": total, "sev_counts": dict(sev_counts),
        "cross_border_count": cross_border_count,
        "states": states_out, "stability": stability,
        "top_actors": overall_actors.most_common(15),
        "top_locations": overall_locations.most_common(15),
        "top_categories": overall_cats.most_common(10),
        "daily_severity": [{"date": d, **v} for d, v in sorted(daily_severity.items())],
        "cb_bangladesh": cb_bangladesh, "cb_myanmar": cb_myanmar,
    }

    # LLM calls
    exec_summary = await _call_llm_text(_fortnightly_exec_summary_prompt(stats, period_label), max_tokens=700)

    target_states = [st for st, sd in stats["states"].items() if sd["total"] > 0]
    stability_map = {s["state"]: s for s in stats["stability"]}
    state_section_tasks = []
    for st in target_states:
        sd = stats["states"][st]
        stab = stability_map.get(st, {"score": 50, "level": "MONITOR"})
        state_section_tasks.append(_call_llm_json(_state_section_prompt(st, sd, stab, period_label), max_tokens=500))
    state_results = await asyncio.gather(*state_section_tasks)
    _STR_FIELDS = {"severity_summary", "escalation_pattern", "key_actors", "district_hotspots", "operational_concerns"}
    def _coerce(sec):
        for f in _STR_FIELDS:
            v = sec.get(f)
            if isinstance(v, list):
                sec[f] = "; ".join(str(x) for x in v)
            elif v is not None and not isinstance(v, str):
                sec[f] = str(v)
        return sec
    state_sections = {st: _coerce(res) for st, res in zip(target_states, state_results) if res}

    mitigation_tasks = []
    mitigation_states = []
    for s in stats["stability"]:
        if s["level"] in ("ELEVATED", "CRITICAL", "MONITOR") and stats["states"].get(s["state"], {}).get("total", 0) > 2:
            mitigation_states.append(s["state"])
            sd = stats["states"][s["state"]]
            actors_str = ", ".join([a[0] for a in sd["top_actors"][:5]]) or "various"
            cats_str   = ", ".join([c[0] for c in sd["top_categories"][:4]]) or "mixed"
            mitigation_tasks.append(_call_llm_json(_mitigation_playbook_prompt(s["state"], s, actors_str, cats_str), max_tokens=1400))
    mitigation_results = await asyncio.gather(*mitigation_tasks)
    for st, res in zip(mitigation_states, mitigation_results):
        if not res:
            logger.warning(f"Mitigation playbook empty for {st} — LLM returned no parseable JSON")
        else:
            logger.info(f"Mitigation playbook OK for {st}: keys={list(res.keys())}")
    mitigation_playbook = {st: res for st, res in zip(mitigation_states, mitigation_results) if res}

    cross_border_analysis = await _call_llm_json(
        _cross_border_prompt(cb_bangladesh, cb_myanmar, period_label), max_tokens=900
    )

    scenarios_payload = await _call_llm_json(_fortnightly_scenarios_prompt(stats, period_label), max_tokens=600)
    scenarios = scenarios_payload.get("scenarios", []) if isinstance(scenarios_payload, dict) else []

    # PAOI sections — rich on first generation of this period, lean on regen.
    paoi_analysis = await _build_fortnightly_paoi(year, month, period, start_iso, end_iso, period_label, force_rich=force_rich)

    faultline_analysis = await _aggregate_faultline_section(year, month)

    llm_ok = bool(exec_summary and state_sections)
    if not llm_ok:
        logger.error(
            f"Fortnightly brief LLM content missing: exec_summary={bool(exec_summary)}, "
            f"state_sections={len(state_sections)}/{len(target_states)} states"
        )

    brief = {
        "year": year, "month": month, "period": period,
        "period_label": period_label,
        "status": "ready" if llm_ok else "partial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "executive_summary": exec_summary,
        "state_sections": state_sections,
        "mitigation_playbook": mitigation_playbook,
        "scenarios": scenarios,
        "cross_border_analysis": cross_border_analysis,
        "paoi_analysis": paoi_analysis,
        "faultline_analysis": faultline_analysis,
        "generation_count": paoi_analysis.pop("_next_generation_count", 1),
    }
    if not llm_ok:
        brief["_llm_error"] = "LLM calls returned empty — check OpenRouter API key and rate limits. Re-generate to retry."
    brief["notebooklm_script"] = _build_notebooklm_script(brief, year, month)

    await fortnightly_briefs_col.replace_one(
        {"year": year, "month": month, "period": period}, brief, upsert=True
    )
    logger.info(f"Fortnightly brief generation {'complete' if llm_ok else 'partial (LLM empty)'}: {period_label}")
    return brief


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/brief/fortnightly/generate")
async def generate_fortnightly_brief(
    background_tasks: BackgroundTasks,
    year:   int = Query(...),
    month:  int = Query(..., ge=1, le=12),
    period: int = Query(..., ge=1, le=2),
    force_rich: bool = Query(False, description="Force rich LLM synthesis even on regen"),
    current_user: dict = Depends(get_current_user),
):
    _require_brief_author(current_user)

    # Preserve generation_count so rich/lean tier selection survives regen.
    prior = await fortnightly_briefs_col.find_one(
        {"year": year, "month": month, "period": period},
        {"_id": 0, "generation_count": 1},
    )
    prior_count = (prior or {}).get("generation_count", 0)

    await fortnightly_briefs_col.replace_one(
        {"year": year, "month": month, "period": period},
        {"year": year, "month": month, "period": period,
         "status": "generating",
         "generation_count": prior_count,
         "started_at": datetime.now(timezone.utc).isoformat()},
        upsert=True,
    )

    async def _bg():
        try:
            await _run_fortnightly_generation(year, month, period, force_rich=force_rich)
        except Exception as e:
            logger.exception("fortnightly brief generation crashed")
            await fortnightly_briefs_col.update_one(
                {"year": year, "month": month, "period": period},
                {"$set": {"status": "error", "error": str(e)[:300]}},
            )

    background_tasks.add_task(_bg)
    _, _, label = _fortnightly_range(year, month, period)
    return {"status": "generating", "year": year, "month": month, "period": period, "period_label": label}


@router.get("/brief/fortnightly/list")
async def list_fortnightly_briefs():
    cursor = fortnightly_briefs_col.find(
        {}, {"_id": 0, "year": 1, "month": 1, "period": 1, "period_label": 1, "status": 1, "generated_at": 1}
    ).sort([("year", -1), ("month", -1), ("period", -1)]).limit(48)
    return {"briefs": [b async for b in cursor]}


@router.get("/brief/fortnightly/stability-history")
async def fortnightly_stability_history():
    """Return stability scores + sev_counts for all ready fortnightly briefs (for trend chart)."""
    cursor = fortnightly_briefs_col.find(
        {"status": {"$in": ["ready", "partial"]}},
        {"_id": 0, "year": 1, "month": 1, "period": 1, "period_label": 1,
         "stats.stability": 1, "stats.sev_counts": 1, "stats.total": 1},
    ).sort([("year", 1), ("month", 1), ("period", 1)])
    results = []
    async for b in cursor:
        stats = b.get("stats") or {}
        results.append({
            "year": b["year"],
            "month": b["month"],
            "period": b["period"],
            "label": b.get("period_label", f"{b['year']}-{b['month']:02d}-P{b['period']}"),
            "stability": stats.get("stability", []),
            "sev_counts": stats.get("sev_counts", {}),
            "total": stats.get("total", 0),
        })
    return {"history": results}


@router.get("/brief/fortnightly/default")
async def get_fortnightly_default():
    year, month, period = _current_fortnightly_default()
    return {"year": year, "month": month, "period": period}


@router.get("/brief/fortnightly/{year}/{month}/{period}")
async def get_fortnightly_brief(year: int, month: int, period: int):
    brief = await fortnightly_briefs_col.find_one(
        {"year": year, "month": month, "period": period}, {"_id": 0}
    )
    if not brief:
        raise HTTPException(404, f"Fortnightly brief not generated — POST to /brief/fortnightly/generate first")
    return brief


@router.get("/brief/fortnightly/{year}/{month}/{period}/notebooklm", response_class=PlainTextResponse)
async def get_fortnightly_notebooklm(year: int, month: int, period: int):
    brief = await fortnightly_briefs_col.find_one(
        {"year": year, "month": month, "period": period}, {"notebooklm_script": 1}
    )
    if not brief or not brief.get("notebooklm_script"):
        raise HTTPException(404, "Brief not generated or markdown not ready")
    return brief["notebooklm_script"]


@router.get("/brief/fortnightly/{year}/{month}/{period}/pdf")
async def get_fortnightly_pdf(year: int, month: int, period: int):
    brief = await fortnightly_briefs_col.find_one(
        {"year": year, "month": month, "period": period}, {"_id": 0}
    )
    if not brief:
        raise HTTPException(404, "Brief not generated")
    if brief.get("status") not in ("ready", "partial"):
        raise HTTPException(425, f"Brief status: {brief.get('status')} — wait for generation")

    # Fetch previous period for recap section
    if period == 2:
        # P2 → recap P1 of same month
        prev_brief = await fortnightly_briefs_col.find_one(
            {"year": year, "month": month, "period": 1, "status": "ready"}, {"_id": 0}
        )
    else:
        # P1 → recap P2 of previous month
        prev_year  = year if month > 1 else year - 1
        prev_month = month - 1 if month > 1 else 12
        prev_brief = await fortnightly_briefs_col.find_one(
            {"year": prev_year, "month": prev_month, "period": 2, "status": "ready"}, {"_id": 0}
        )

    try:
        pdf_bytes = _render_pdf(brief, prev_brief=prev_brief)
    except Exception as e:
        import traceback
        logger.error(f"Fortnightly PDF render failed: {traceback.format_exc()}")
        raise HTTPException(500, f"PDF render error: {type(e).__name__}: {e}")
    label = brief.get("period_label", f"{year}-{month:02d}-P{period}").replace(" ", "_").replace("-", "_")
    filename = f"NER_Fortnightly_Brief_{label}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
