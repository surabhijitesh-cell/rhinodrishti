"""
faultline_pdf.py — Faultline Analysis Report PDF (6 pages).

Same visual identity as the Monthly Strategic Brief (via brief_pdf_style.BriefPDF)
plus faultline-specific content:

  Page 1 — Cover + Key Metrics + MoM Level Distribution + Bottom Line (LLM B1)
  Page 2 — Priority Areas of Interest (P1->P5) with cached PAOI synthesis
  Page 3 — State-wise faultline tables + state narratives (10 states)
  Page 4 — Top 10 Movers + News Drivers (3 per mover) + outlooks (LLM B2)
  Page 5 — Actors of Interest | NER + BD + MM | Top 10 by mention count (LLM B4)
  Page 6 — Cross-cutting Manual Review Advisory (LLM B3) + per-state roll-up

Data sources (all DB-resident — no re-scoring):
  - faultline_scores      (current month + previous month for MoM)
  - faultline_mappings    (top news drivers per mover, joined with intelligence_items)
  - intelligence_items    (actors[], entities.organizations[], state filter for scope)
  - priority_areas        (PAOI registry for ordering)
  - monthly_briefs        (cached state_narratives + paoi_analysis synthesis)

LLM calls (Path B, 4 total, run in parallel):
  B1 — Bottom Line MoM executive (~700 tokens)
  B2 — Batched outlooks for top 10 movers (~1200 tokens, single call)
  B3 — Cross-cutting Manual Review Advisory (~500 tokens)
  B4 — Actor posture profiles, top 10 (~600 tokens)
"""
import asyncio
import hashlib
import io
import re
import logging
from collections import defaultdict, Counter
from datetime import date, datetime, timezone, timedelta

import brief_periods
from brief_pdf_style import (
    BriefPDF, NL, ascii_safe, concern_level,
    C_TBL_HDR, C_TBL_ALT, C_SEC_TEXT, CONCERN_COLORS,
)

logger = logging.getLogger("faultline_pdf")

# NER states + Bangladesh + Myanmar — scope for actor aggregation.
ACTOR_SCOPE_STATES = {
    "Manipur", "Assam", "Meghalaya", "Tripura", "Mizoram",
    "Nagaland", "North Bengal", "Bangladesh", "Myanmar", "Arunachal Pradesh",
}


# ── Data aggregation ─────────────────────────────────────────────────────────
def report_windows(year: int, month: int, period: int | None = None) -> dict:
    """Current and previous windows for the report, as inclusive IST dates.
    period None = whole calendar month vs previous month; 1|2 = that fortnight
    vs the previous fortnight (P1 -> P2 of the previous month)."""
    if period is None:
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        prev_period = None
        cur = brief_periods.month_range(year, month)
        prv = brief_periods.month_range(prev_year, prev_month)
        label = date(year, month, 1).strftime("%B %Y")
        prev_label = date(prev_year, prev_month, 1).strftime("%B %Y")
    else:
        from routers.brief_fortnightly import _prev_fortnight
        pk = _prev_fortnight(year, month, period)
        prev_year, prev_month, prev_period = pk["year"], pk["month"], pk["period"]
        cur_start, cur_end, label = brief_periods.fortnight_range(year, month, period)
        prv_start, prv_end, prev_label = brief_periods.fortnight_range(prev_year, prev_month, prev_period)
        cur, prv = (cur_start, cur_end), (prv_start, prv_end)
    return {
        "current": brief_periods.period_dates(*cur),
        "previous": brief_periods.period_dates(*prv),
        "label": label, "prev_label": prev_label,
        "prev_year": prev_year, "prev_month": prev_month, "prev_period": prev_period,
    }


async def _load_scores(db, window: tuple, fl_ids: list | None = None) -> dict:
    """Returns {faultline_id: {first, last, peak, avg, days, state, name, level}}
    over the inclusive (first_date, last_date) window; fl_ids None = all."""
    query: dict = {"date": {"$gte": window[0], "$lte": window[1]}}
    if fl_ids is not None:
        query["faultline_id"] = {"$in": list(fl_ids)}
    cursor = db.faultline_scores.find(
        query,
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
            "name": series[-1].get("faultline_name") or str(fl_id).replace("_", " ").replace("-", " ").title(),
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


async def _top_actors(db, window: tuple, fl_ids: list | None = None) -> list:
    """
    Top 10 actors/orgs by mention count across ACTOR_SCOPE_STATES faultline-mapped
    articles in the window (inclusive IST dates).  Returns list of dicts:
      {name, count, faultlines[3], headline{title,date,source,severity}}
    """
    m_query: dict = {"date": {"$gte": window[0], "$lte": window[1]}, "confidence": {"$gte": 45}}
    if fl_ids is not None:
        m_query["faultline_id"] = {"$in": list(fl_ids)}

    # Collect article_id → set of faultline names from mappings in the window.
    article_faultlines: dict = defaultdict(set)
    m_cursor = db.faultline_mappings.find(
        m_query,
        {"_id": 0, "article_id": 1, "faultline_name": 1, "faultline_id": 1},
    )
    async for m in m_cursor:
        aid = m.get("article_id")
        if aid:
            fl_name = m.get("faultline_name") or m.get("faultline_id", "")
            article_faultlines[aid].add(fl_name)

    if not article_faultlines:
        return []

    # Fetch intelligence_items for mapped articles, filter by scope state.
    actor_counts: Counter = Counter()
    actor_faultlines: dict = defaultdict(set)
    actor_headlines: dict = {}

    items_cursor = db.intelligence_items.find(
        {"id": {"$in": list(article_faultlines.keys())}},
        {"_id": 0, "id": 1, "actors": 1, "entities": 1, "state": 1,
         "title": 1, "published_at": 1, "source": 1, "severity": 1},
    )
    async for item in items_cursor:
        state = item.get("state") or ""
        if state and state not in ACTOR_SCOPE_STATES:
            continue
        aid = item["id"]
        fl_names = article_faultlines.get(aid, set())

        actors = list(item.get("actors") or [])
        orgs = list((item.get("entities") or {}).get("organizations") or [])
        for actor in actors + orgs:
            actor = (actor or "").strip()
            if len(actor) < 3:
                continue
            actor_counts[actor] += 1
            actor_faultlines[actor].update(fl_names)
            if actor not in actor_headlines:
                actor_headlines[actor] = {
                    "title": item.get("title", ""),
                    "date": (item.get("published_at") or "")[:10],
                    "source": item.get("source", ""),
                    "severity": item.get("severity", ""),
                }

    result = []
    for actor, count in actor_counts.most_common(10):
        result.append({
            "name": actor,
            "count": count,
            "faultlines": sorted(actor_faultlines[actor])[:3],
            "headline": actor_headlines.get(actor, {}),
        })
    return result


def level_distribution(scores: dict) -> dict:
    """Count faultlines per concern level using the period-average score, so the
    current and previous periods are always measured the same way."""
    d = {"CRITICAL": 0, "ELEVATED": 0, "MONITOR": 0, "STABLE": 0}
    for s in scores.values():
        lvl = concern_level(s["avg"])
        d[lvl] = d.get(lvl, 0) + 1
    return d


_ID_LIKE = re.compile(r"^[A-Za-z0-9]+(?:[_\-][A-Za-z0-9]+)+$")


def reader_faultline_name(label, names: dict | None = None) -> str:
    """A faultline label fit for readers: known id -> its display name; anything that
    still looks like an internal id (snake_case/kebab, no spaces) -> '' (dropped)."""
    s = (label or "").strip() if isinstance(label, str) else ""
    if names and s in names:
        s = names[s]
    return "" if (not s or _ID_LIKE.match(s)) else s


async def aggregate_faultline_report(
    db, year: int, month: int, iod: str = "IOD-1",
    period: int | None = None, fl_ids: list | None = None,
) -> dict:
    """Aggregate everything the PDF needs. No LLM here — that's a separate pass.

    iod defaults to IOD-1 (today's only PAOI owner) — memory/plans/
    iod-scoping-plan.md cross-cutting fix #4: without this, another IOD's
    first PAOI would leak into this report's red-flagging pass.

    period None = the calendar month (vs previous month); 1|2 = that fortnight
    (vs the previous fortnight). fl_ids limits the faultlines to an IOD's
    watch-list (None = all). Dates are IST calendar days."""
    win = report_windows(year, month, period)
    prev_year, prev_month = win["prev_year"], win["prev_month"]

    # Actors of interest (parallel with score load — independent query)
    actors_task = asyncio.ensure_future(_top_actors(db, win["current"], fl_ids))

    # Current + previous period scores for the comparison
    curr = await _load_scores(db, win["current"], fl_ids)
    prev = await _load_scores(db, win["previous"], fl_ids)

    # MoM delta per faultline (using avg as the representative monthly value).
    # If no prior month data, delta_mom = None.
    for fl_id, c in curr.items():
        p = prev.get(fl_id)
        c["mom_delta"] = round(c["avg"] - p["avg"], 1) if (p and p["avg"] > 0) else None
        c["prev_avg"] = p["avg"] if (p and p["avg"] > 0) else None

    # Level distribution this period vs previous: BOTH use the period-average score
    mom_levels = {
        "current": level_distribution(curr),
        "previous": level_distribution(prev),
        "measure": "avg",
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
    from routers.brief_monthly import _iod_query_filter
    brief_col = db.monthly_briefs if period is None else db.fortnightly_briefs
    brief_key = {"year": year, "month": month, **_iod_query_filter(iod)}
    if period is not None:
        brief_key["period"] = period
    brief = await brief_col.find_one(
        brief_key,
        {"_id": 0, "faultline_analysis": 1, "paoi_analysis": 1, "generated_at": 1},
    ) or {}
    state_narratives = (brief.get("faultline_analysis") or {}).get("state_narratives", {}) or {}
    paoi_analysis = brief.get("paoi_analysis") or {}

    # PAOI registry — used to order and group
    paois_cursor = db.priority_areas.find({"enabled": True, "iod": iod}, {"_id": 0}).sort("rank", 1)
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
        m_cursor = db.faultline_mappings.find(
            {
                "faultline_id": {"$in": mover_ids},
                "date": {"$gte": win["current"][0], "$lte": win["current"][1]},
                "confidence": {"$gte": 45},
            },
            {"_id": 0, "faultline_id": 1, "article_id": 1, "impact_score": 1,
             "confidence": 1, "rationale": 1, "article_title": 1,
             "article_published_at": 1, "article_severity": 1},
        ).sort("impact_score", -1).limit(1000)
        # Dedup by article_id within each faultline's driver list — re-scoring
        # can produce multiple mapping rows per (article_id, faultline_id) and
        # the un-deduped version made all 3 driver slots identical (issue #3).
        seen_articles_by_fl: dict = defaultdict(set)
        async for m in m_cursor:
            fid = m["faultline_id"]
            aid = m.get("article_id")
            if not aid or aid in seen_articles_by_fl[fid]:
                continue
            slot = drivers_by_fl[fid]
            if len(slot) < 3:
                slot.append(m)
                seen_articles_by_fl[fid].add(aid)

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

    # Await actors task (started at top of function alongside score loads)
    try:
        top_actors = await actors_task
    except Exception as e:
        logger.warning(f"Actor aggregation failed: {e}")
        top_actors = []
    # Faultline labels on the actors page must be readable names, never internal ids.
    id_names = {i: f["name"] for i, f in {**prev, **curr}.items()}
    for a in top_actors:
        a["faultlines"] = [n for n in (reader_faultline_name(x, id_names)
                                       for x in a.get("faultlines") or []) if n]

    return {
        "year": year, "month": month, "period": period, "iod": iod,
        "is_fortnight": period is not None,
        "prev_year": prev_year, "prev_month": prev_month,
        "prev_period": win["prev_period"],
        # period wording: the month name, or e.g. "1-15 November 2026"
        "month_name": win["label"],
        "prev_month_name": win["prev_label"],
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
        "top_actors": top_actors,
    }


def _pw(agg: dict) -> str:
    """Period word for wording: Fortnight or Month."""
    return "Fortnight" if agg.get("is_fortnight") else "Month"


def _cmp_tag(agg: dict) -> str:
    """Short tag for the comparison with the previous period."""
    return "FoF" if agg.get("is_fortnight") else "MoM"


# ── LLM synthesis (Path B — 3 calls) ──────────────────────────────────────────
def _b1_bottom_line_prompt(agg: dict) -> str:
    km = agg["key_metrics"]
    lv = agg["mom_levels"]
    lines = [
        f"Period: {agg['month_name']} vs {agg['prev_month_name']} "
        f"({'fortnight' if agg.get('is_fortnight') else 'month'}).",
        f"Total faultlines monitored: {km['total']}.",
        f"Currently CRITICAL: {km['critical_now']}.",
        f"Rising this period (Δ>=+10): {km['rising_period']}.",
        f"Declining (Δ<=-10): {km['declining_period']}.",
        "",
        f"Level distribution {_cmp_tag(agg)} (by period-average score, both periods):",
    ]
    for lvl in ("CRITICAL", "ELEVATED", "MONITOR", "STABLE"):
        c = lv["current"].get(lvl, 0)
        p = lv["previous"].get(lvl, 0)
        d = lv["delta"].get(lvl, 0)
        lines.append(f"  {lvl}: {c} (prev {p}, Δ {d:+d})")

    # Top movers context
    if agg["top_movers"]:
        lines.append("")
        lines.append(f"Top 5 movers (state, faultline, current score, period Δ, {_cmp_tag(agg)} Δ):")
        for f in agg["top_movers"][:5]:
            mom = f["mom_delta"] if f["mom_delta"] is not None else "n/a"
            lines.append(
                f"  [{f['state']}] {f['name']}: now {f['last']:.0f}, "
                f"period Δ {f['delta_period']:+.1f}, {_cmp_tag(agg)} Δ {mom}"
            )

    return (
        "You are writing the BOTTOM LINE for a Faultline Analysis Report.\n\n"
        + "\n".join(lines) + "\n\n"
        + "Write 5-7 sentences. Open with the single most important read of the\n"
        + f"{_pw(agg).lower()}. Cover movement-vs-previous-{_pw(agg).lower()} direction (escalation or de-escalation),\n"
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
            f"{_cmp_tag(agg)} Δ {mom}).{drivers_str}"
        )
    return (
        "You are writing FORWARD OUTLOOK statements for top mover faultlines.\n\n"
        "Top 10 movers this period:\n" + "\n".join(items) + "\n\n"
        + "For EACH faultline (by its `id`), give a 1-sentence forward outlook\n"
        + "describing the most likely movement in the COMING PERIOD and the key\n"
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
        + "     manually this period (cross-state if possible)\n"
        + "  2. Specific channels/sources worth checking (regional language press,\n"
        + "     local Telegram channels, influencer amplification patterns)\n"
        + "  3. The borderline / weak-signal faultline most worth a second look\n\n"
        + "Use [ASSESSED] / [SPECULATIVE] labels where useful.\n"
        + "Return strict JSON: {\"advisory\": \"paragraph...\"}"
    )


def _b4_actors_prompt(actors: list) -> str:
    lines = []
    for i, a in enumerate(actors, 1):
        fls = ", ".join(a["faultlines"][:3]) or "unspecified"
        lines.append(f"{i}. {a['name']} — {a['count']} mentions — faultlines: {fls}")
    return (
        "You are writing ACTOR PROFILES for a Faultline Analysis Report.\n\n"
        "Top actors/organizations by mention count this period (NER + BD + MM scope):\n"
        + "\n".join(lines) + "\n\n"
        + "For EACH actor (by exact name as listed), write ONE sentence describing:\n"
        + "  - their likely role (state security force, insurgent group, political party,\n"
        + "    Islamist organisation, media/disinfo outlet, foreign state actor, etc.)\n"
        + "  - their current posture (escalatory, conciliatory, destabilising, monitoring, etc.)\n"
        + "  - the primary faultline or concern they are most associated with\n\n"
        + "Use [ASSESSED] for inferences. Be specific — name known affiliation or agenda.\n\n"
        + "Return strict JSON keyed by exact actor name: "
        + "{\"<name>\": \"one-sentence profile...\"}"
    )


def _synthesis_prompts(agg: dict) -> list:
    prompts = [_b1_bottom_line_prompt(agg), _b3_advisory_prompt(agg)]
    if agg.get("top_movers"):
        prompts.append(_b2_movers_prompt(agg))
    if agg.get("top_actors"):
        prompts.append(_b4_actors_prompt(agg["top_actors"]))
    return prompts


def synthesis_input_hash(agg: dict) -> str:
    """Stable hash of everything that reaches the AI prompts (the prompts themselves)."""
    return hashlib.sha256("\n\x00\n".join(_synthesis_prompts(agg)).encode("utf-8")).hexdigest()


def _valid_synthesis(syn, agg: dict) -> bool:
    """A usable synthesis has every part the prompts asked for; odd stored values are misses."""
    if not isinstance(syn, dict):
        return False
    if not (isinstance(syn.get("bottom_line"), str) and syn["bottom_line"].strip()):
        return False
    if not (isinstance(syn.get("advisory"), str) and syn["advisory"].strip()):
        return False
    if agg.get("top_movers") and not (isinstance(syn.get("mover_outlooks"), dict) and syn["mover_outlooks"]):
        return False
    if agg.get("top_actors") and not (isinstance(syn.get("actor_profiles"), dict) and syn["actor_profiles"]):
        return False
    return True


async def get_or_run_pdf_synthesis(db, agg: dict, call_llm_json) -> dict:
    """Reuse stored AI report text when the inputs are unchanged; otherwise generate and
    store it. Failed/partial AI text is returned but never stored. The result carries
    generated_at (when the text was written)."""
    key = {
        "year": agg.get("year"), "month": agg.get("month"), "period": agg.get("period"),
        "iod": agg.get("iod") or "IOD-1", "input_hash": synthesis_input_hash(agg),
    }
    col = db.faultline_report_synthesis
    try:
        stored = await col.find_one(key, {"_id": 0})
    except Exception as e:
        logger.warning(f"Faultline synthesis cache read failed: {e}")
        stored = None
    syn = stored.get("synthesis") if isinstance(stored, dict) else None
    if _valid_synthesis(syn, agg):
        gen = stored.get("generated_at")
        return {**syn, "generated_at": gen if isinstance(gen, str) else ""}

    fresh = await run_pdf_synthesis(agg, call_llm_json)
    generated_at = datetime.now(timezone.utc).isoformat()
    if _valid_synthesis(fresh, agg):
        try:
            await col.update_one(key, {"$set": {**key, "synthesis": fresh, "generated_at": generated_at}},
                                 upsert=True)
        except Exception as e:
            logger.warning(f"Faultline synthesis cache write failed: {e}")
    return {**fresh, "generated_at": generated_at}


async def run_pdf_synthesis(agg: dict, call_llm_json) -> dict:
    """Run B1+B2+B3+B4 in parallel. Returns {bottom_line, mover_outlooks{}, advisory, actor_profiles{}}."""
    b1_task = call_llm_json(_b1_bottom_line_prompt(agg), max_tokens=700)
    b2_task = (call_llm_json(_b2_movers_prompt(agg), max_tokens=1500)
               if agg["top_movers"] else asyncio.sleep(0, result={}))
    b3_task = call_llm_json(_b3_advisory_prompt(agg), max_tokens=600)
    b4_task = (call_llm_json(_b4_actors_prompt(agg["top_actors"]), max_tokens=700)
               if agg.get("top_actors") else asyncio.sleep(0, result={}))

    b1, b2, b3, b4 = await asyncio.gather(b1_task, b2_task, b3_task, b4_task, return_exceptions=True)

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
    actor_profiles = _safe(b4) or {}

    return {
        "bottom_line": bottom_line,
        "mover_outlooks": mover_outlooks,
        "advisory": advisory,
        "actor_profiles": actor_profiles,
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


def render_faultline_pdf(agg: dict, synthesis: dict, priority_map: dict = None) -> bytes:
    """Render PDF.  priority_map is optional {faultline_id: rank(1-10)} from user watchlist."""
    pdf = BriefPDF()
    pdf.brief_type = f"FAULTLINE ANALYSIS REPORT  |  {agg.get('iod') or 'IOD-1'}"
    pdf.display_period = agg["month_name"]
    pw, tag = _pw(agg), _cmp_tag(agg)
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
                      f"Period-average score | {agg['month_name']} vs {agg['prev_month_name']}")
    pdf.set_fill_color(*C_TBL_HDR); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(45, 6, "  Level",       fill=True)
    pdf.cell(45, 6, f"This {pw} (avg)", fill=True, align="C")
    pdf.cell(45, 6, f"Last {pw} (avg)", fill=True, align="C")
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
                      f"{tag} Executive Read | {agg['month_name']}")
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
        mom_str = "" if mom is None else f"  {tag} Δ {mom:+.1f}"
        sub_text = f"P{pa.get('rank')} {pa.get('name')}   {max_score:.0f} {level}{mom_str}"
        col = CONCERN_COLORS.get(level, (60, 80, 50))
        pdf.sub_band(sub_text, fill_rgb=col)

        # Top-3 mini table
        pdf.set_fill_color(*C_TBL_HDR); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(90, 5, "  Faultline", fill=True)
        pdf.cell(30, 5, "Now",        fill=True, align="C")
        pdf.cell(30, 5, ascii_safe(f"{tag} D"), fill=True, align="C")
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
        syn = per_paoi.get(pa["id"]) if isinstance(per_paoi.get(pa["id"]), dict) else {}
        pi = syn.get("period_impact") or ""
        wn = syn.get("forward_concerns") or ""
        if pi:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)
            # Trim to ~2 sentences
            pdf.multi_cell(0, 4, ascii_safe(pi)[:300], **NL)
        if wn:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 80, 20)
            pdf.multi_cell(0, 4, ascii_safe(f"Watch next: {ascii_safe(wn)[:200]}"), **NL)
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
        pdf.cell(20, 5, ascii_safe(f"{tag} D"),    fill=True, align="C")
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
            pdf.multi_cell(0, 4, ascii_safe(narr)[:240], **NL)
        pdf.ln(1)

    # ──────────────── PAGE 4 — Top 10 Movers + News Drivers ──────────────────
    pdf.add_page()
    pdf.section_title("Top 10 Movers + News Drivers",
                      "Priority-First | 3 Top Drivers Each")
    mover_outlooks = synthesis.get("mover_outlooks") or {}
    _pmap = priority_map or {}

    for i, m in enumerate(agg["top_movers"], 1):
        if pdf.get_y() > 245:
            pdf.add_page()
        level = m["level"]
        col = CONCERN_COLORS.get(level, (60, 80, 50))
        mom = m["mom_delta"]
        mom_str = "" if mom is None else f"  {tag} Δ {mom:+.1f}"
        rank_badge = f"[WL#{_pmap[m['id']]}] " if m["id"] in _pmap else ""
        hdr = (f"#{i}  {rank_badge}[{m['state']}]  {m['name']}   {m['last']:.0f} {level}   "
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
            rationale = ascii_safe(d.get("rationale"))[:160]
            if rationale:
                pdf.set_font("Helvetica", "I", 7)
                pdf.set_text_color(80, 80, 80)
                pdf.multi_cell(0, 3.5, ascii_safe(f"       Rationale: {rationale}"), **NL)

        # Forward outlook (B2, batched)
        outlook = mover_outlooks.get(m["id"]) if isinstance(mover_outlooks, dict) else None
        if outlook:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 80, 20)
            pdf.multi_cell(0, 4, ascii_safe(f"  Watch next: {ascii_safe(outlook)[:280]}"), **NL)
        pdf.ln(1)

    # ──────────────── PAGE 5 — Actors of Interest ────────────────────────────
    pdf.add_page()
    pdf.section_title("Actors of Interest",
                      "NER + BD + MM | Top 10 by Mention Count")
    top_actors = agg.get("top_actors") or []
    actor_profiles = synthesis.get("actor_profiles") or {}

    if not top_actors:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 8, "No actor data available for this period.", **NL)
    else:
        for rank, actor in enumerate(top_actors, 1):
            if pdf.get_y() > 252:
                pdf.add_page()
            name = actor["name"]
            count = actor["count"]
            fls = actor.get("faultlines") or []
            hl = actor.get("headline") or {}

            # Actor name band
            pdf.set_fill_color(45, 60, 40)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5.5, ascii_safe(f"  #{rank}  {name}"), fill=True, **NL)

            # Mention count + faultlines row
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)
            fl_names = [n for n in (reader_faultline_name(x) for x in fls) if n]
            fl_str = "  |  ".join(fl_names) if fl_names else "-"
            pdf.cell(0, 4, ascii_safe(
                f"  Mentions: {count}   Faultlines: {fl_str[:100]}"
            ), **NL)

            # Representative headline
            if hl.get("title"):
                date_str = hl.get("date", "")
                sev_str = hl.get("severity", "")
                src_str = (hl.get("source") or "")[:25]
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*C_SEC_TEXT)
                pdf.multi_cell(0, 3.5, ascii_safe(
                    f"  Rep. headline [{date_str}|{sev_str}]: "
                    f"{hl['title'][:110]}  ({src_str})"
                ), **NL)

            # B4 LLM posture line
            profile = actor_profiles.get(name) or ""
            if profile:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(120, 80, 20)
                pdf.multi_cell(0, 4, ascii_safe(f"  Assessment: {ascii_safe(profile)[:260]}"), **NL)
            pdf.ln(1)

    # ──────────────── PAGE 6 — Manual Review Advisory ────────────────────────
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
        pdf.multi_cell(0, 4, ascii_safe(f"    {ascii_safe(advisory)[:280]}"), **NL)
        pdf.ln(1)

    return bytes(pdf.output())
