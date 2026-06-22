"""
paoi_brief.py — Priority Area of Interest (PAOI) brief sections.

Shared by monthly + fortnightly briefs. Produces:
  1. Per-PAOI period aggregation (faultline score movement + keyword article pulls)
  2. Commander Priority Dashboard rows (deterministic, no LLM)
  3. Period inference synthesis (LLM): how faultlines moved + forward concerns
     - RICH tier (first generation): 1 LLM call per PAOI + 1 overall
     - LEAN tier (regeneration): 1 batched LLM call for all PAOIs
  4. Other Faultline Movements (rising/declining NOT in any PAOI)

Faultline scores are CONCERN-oriented (higher = worse, CRITICAL >= 75) — the
de-saturated faultline_engine scale. This is the OPPOSITE of the State Severity
Index stability score (higher = more stable). Keep them distinct.

Reuses:
  - db.faultline_scores (per faultline per date, de-saturated)
  - db.priority_areas (PAOI registry + keyword pulls)
  - db.intelligence_items (keyword article pulls)
  - faultline_engine._score_level for concern banding
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger("paoi_brief")

_SEV_SCORE = {"LOW": 25, "MEDIUM": 50, "HIGH": 75, "CRITICAL": 100}


def _concern_level(score: float) -> str:
    """Concern band (higher = worse). Mirrors faultline_engine._score_level."""
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "ELEVATED"
    if score >= 35:
        return "MONITOR"
    return "STABLE"


def _trend_arrow(delta: float) -> str:
    if delta >= 5:
        return "RISING"
    if delta <= -5:
        return "FALLING"
    return "STEADY"


# ── 1. Per-PAOI period aggregation ────────────────────────────────────────────
async def aggregate_paoi_period(db, start_iso: str, end_iso: str) -> dict:
    """
    Aggregate each PAOI over [start_iso, end_iso] (date strings YYYY-MM-DD…).

    Returns {
      "paois": [
        {
          id, rank, name, description, color, actors_of_interest, geography,
          watch_geography, intel_notes,
          faultline_movement: {
            first, last, peak, avg, delta, level, n_faultlines,
            dominant: {id, name, last, delta},
            per_faultline: [{id, name, first, last, peak, delta, level}],
          },
          keyword_hits: {
            n_articles, top_articles: [{id, title, source, published_at,
                                        severity, url}]
          }
        }, ...
      ],
      "as_of": end_date
    }
    """
    start_date = start_iso[:10]
    end_date = end_iso[:10]

    paois = await db.priority_areas.find(
        {"enabled": True}, {"_id": 0}
    ).sort("rank", 1).to_list(length=50)
    if not paois:
        return {"paois": [], "as_of": end_date}

    # Pull all faultline scores in window once
    score_cursor = db.faultline_scores.find(
        {"date": {"$gte": start_date, "$lte": end_date}},
        {"_id": 0, "faultline_id": 1, "faultline_name": 1, "date": 1,
         "score": 1, "level": 1, "dominant_subissues": 1, "loc_risk": 1},
    ).sort("date", 1)
    by_fl: dict[str, list] = defaultdict(list)
    async for s in score_cursor:
        by_fl[s["faultline_id"]].append(s)

    def _fl_summary(fl_id: str) -> dict | None:
        series = by_fl.get(fl_id)
        if not series:
            return None
        series = sorted(series, key=lambda x: x["date"])
        first = series[0]["score"]
        last = series[-1]["score"]
        peak = max(s["score"] for s in series)
        avg = sum(s["score"] for s in series) / len(series)
        latest = series[-1]
        return {
            "id": fl_id,
            "name": latest.get("faultline_name", fl_id),
            "first": round(first, 1),
            "last": round(last, 1),
            "peak": round(peak, 1),
            "avg": round(avg, 1),
            "delta": round(last - first, 1),
            "level": _concern_level(last),
            "dominant_subissues": latest.get("dominant_subissues") or [],
            "loc_risk": bool(latest.get("loc_risk")),
        }

    # State priority: commander's focus states first, then others by rank.
    _STATE_PRIORITY = {
        "Meghalaya": 0, "Bangladesh": 1, "Assam": 2,
        "Mizoram": 3, "Tripura": 4,
    }

    def _paoi_sort_key(p: dict) -> tuple:
        geo = p.get("geography", []) + p.get("watch_geography", [])
        prio = min((_STATE_PRIORITY.get(g, 9) for g in geo), default=9)
        return (prio, p.get("rank", 99))

    out_paois = []
    for pa in paois:
        # Faultline movement
        fl_summaries = []
        for fl_id in pa.get("linked_faultline_ids", []):
            s = _fl_summary(fl_id)
            if s:
                fl_summaries.append(s)
        fl_summaries.sort(key=lambda x: -x["last"])

        if fl_summaries:
            lasts = [f["last"] for f in fl_summaries]
            firsts = [f["first"] for f in fl_summaries]
            peaks = [f["peak"] for f in fl_summaries]
            agg_last = max(lasts)              # PAOI status = worst faultline
            agg_first = max(firsts)
            agg_peak = max(peaks)

            # Collect dominant sub-issues across all faultlines, dedup by name
            all_si: dict[str, dict] = {}
            for fs in fl_summaries:
                for si in fs.get("dominant_subissues") or []:
                    key = si.get("name", "")
                    if key and si.get("contribution", 0) > all_si.get(key, {}).get("contribution", -1):
                        all_si[key] = si
            top_subissues = sorted(all_si.values(), key=lambda x: -x.get("contribution", 0))[:4]

            movement = {
                "first": round(agg_first, 1),
                "last": round(agg_last, 1),
                "peak": round(agg_peak, 1),
                "avg": round(sum(lasts) / len(lasts), 1),
                "delta": round(agg_last - agg_first, 1),
                "level": _concern_level(agg_last),
                "n_faultlines": len(fl_summaries),
                "dominant": {
                    "id": fl_summaries[0]["id"],
                    "name": fl_summaries[0]["name"],
                    "last": fl_summaries[0]["last"],
                    "delta": fl_summaries[0]["delta"],
                },
                "per_faultline": fl_summaries[:8],
                "top_subissues": top_subissues,
                "loc_risk": any(fs.get("loc_risk") for fs in fl_summaries),
            }
        else:
            movement = {
                "first": None, "last": None, "peak": None, "avg": None,
                "delta": 0.0, "level": "STABLE", "n_faultlines": 0,
                "dominant": None, "per_faultline": [],
                "top_subissues": [], "loc_risk": False,
            }

        # Keyword article pull (covers keyword-driven PAOIs like P3 LOC, and
        # adds exemplar articles for all PAOIs)
        keyword_hits = await _keyword_article_pull(
            db, pa.get("keyword_pull") or {}, start_iso, end_iso
        )

        out_paois.append({
            "id": pa["id"],
            "rank": pa.get("rank", 99),
            "name": pa["name"],
            "description": pa.get("description", ""),
            "color": pa.get("color", "red"),
            "actors_of_interest": pa.get("actors_of_interest", []),
            "geography": pa.get("geography", []),
            "watch_geography": pa.get("watch_geography", []),
            "intel_notes": pa.get("intel_notes", ""),
            "faultline_movement": movement,
            "keyword_hits": keyword_hits,
        })

    out_paois.sort(key=_paoi_sort_key)
    for i, p in enumerate(out_paois):
        p["rank"] = i + 1

    return {"paois": out_paois, "as_of": end_date}


async def _keyword_article_pull(db, keyword_pull: dict, start_iso: str, end_iso: str) -> dict:
    """Count + sample articles matching a PAOI's keyword pull in the window."""
    keywords = [k.lower() for k in keyword_pull.get("keywords", [])]
    regions = keyword_pull.get("regions", [])
    if not keywords:
        return {"n_articles": 0, "top_articles": []}

    # Region gate (regions[] or state) + window.
    # published_at is stored as a date-only string ("YYYY-MM-DD"); compare
    # against date-only bounds so first-day articles aren't dropped by a
    # datetime suffix on the lower bound (ASCII ordering).
    q: dict = {
        "published_at": {"$gte": start_iso[:10], "$lt": end_iso[:10]},
        "processed": True,
    }
    if regions:
        q["$or"] = [
            {"regions": {"$in": regions}},
            {"state": {"$in": regions}},
        ]

    cursor = db.intelligence_items.find(
        q,
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "why_it_matters": 1,
         "entities": 1, "state": 1, "district": 1, "threat_trajectory": 1,
         "source": 1, "source_url": 1, "published_at": 1,
         "severity": 1, "priority_score": 1},
    ).sort("priority_score", -1).limit(300)

    matched = []
    async for art in cursor:
        hay = " ".join([
            (art.get("title") or "").lower(),
            (art.get("ai_summary") or "").lower(),
        ])
        if any(kw in hay for kw in keywords):
            matched.append(art)
        if len(matched) >= 40:
            break

    top = [
        {
            "id": a["id"],
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "published_at": (a.get("published_at") or "")[:10],
            "severity": a.get("severity", ""),
            "priority_score": a.get("priority_score") or 0,
            "url": a.get("source_url", ""),
            "ai_summary": a.get("ai_summary", ""),
            "why_it_matters": a.get("why_it_matters", ""),
            "state": a.get("state", ""),
            "district": a.get("district", ""),
            "threat_trajectory": a.get("threat_trajectory", ""),
        }
        for a in matched[:20]
    ]
    return {"n_articles": len(matched), "top_articles": top}


def select_top_events_for_paoi(
    articles: list[dict], pa: dict, n: int = 5, period_end: str = ""
) -> list[dict]:
    """Score and select top n articles for a PAOI, with sub-region diversity."""
    if not articles:
        return []
    geo_lower = set(
        g.lower() for g in pa.get("geography", []) + pa.get("watch_geography", [])
    )

    def _score(a: dict) -> float:
        ps = min(float(a.get("priority_score") or 0), 100) / 100
        sv = _SEV_SCORE.get((a.get("severity") or "").upper(), 50) / 100
        art_state = (a.get("state") or "").lower()
        paoi_rel = 1.0 if (art_state and art_state in geo_lower) else 0.4
        rec = 0.5
        if period_end:
            try:
                from datetime import datetime as _dt
                pub = (a.get("published_at") or "")[:10]
                end = period_end[:10]
                if pub and end:
                    days_gap = (_dt.fromisoformat(end) - _dt.fromisoformat(pub)).days
                    rec = max(0.0, 1.0 - days_gap / 30)
            except Exception:
                pass
        return 0.4 * ps + 0.3 * sv + 0.2 * paoi_rel + 0.1 * rec

    scored = sorted(articles, key=_score, reverse=True)

    # Sub-region diversity: prefer articles from different states
    selected: list[dict] = []
    seen_states: set[str] = set()
    remainder: list[dict] = []
    for a in scored:
        st = a.get("state") or "unknown"
        if st not in seen_states:
            selected.append(a)
            seen_states.add(st)
        else:
            remainder.append(a)
        if len(selected) >= n:
            break

    for a in remainder:
        if len(selected) >= n:
            break
        selected.append(a)

    return selected[:n]


# ── 2. Commander Priority Dashboard (deterministic) ───────────────────────────
def build_commander_dashboard(paoi_agg: dict) -> list[dict]:
    """One row per PAOI: status, trend, 1-line what-changed. No LLM."""
    rows = []
    for pa in paoi_agg.get("paois", []):
        mv = pa["faultline_movement"]
        kw = pa["keyword_hits"]
        score = mv["last"]
        level = mv["level"]
        delta = mv["delta"]
        trend = _trend_arrow(delta)

        if mv["dominant"]:
            what = f"{mv['dominant']['name']} {mv['dominant']['last']:.0f} ({trend})"
        elif kw["n_articles"]:
            what = f"{kw['n_articles']} related reports this period"
        else:
            what = "No significant activity"

        rows.append({
            "id": pa["id"],
            "rank": pa["rank"],
            "name": pa["name"],
            "score": score,
            "level": level,
            "delta": delta,
            "trend": trend,
            "n_articles": kw["n_articles"],
            "what_changed": what,
            "color": pa["color"],
        })
    rows.sort(key=lambda r: r["rank"])
    return rows


# ── 3. Period inference synthesis (LLM, rich or lean) ─────────────────────────
def _strip_json(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    if text and not text.startswith("{"):
        lo, hi = text.find("{"), text.rfind("}")
        if lo != -1 and hi > lo:
            text = text[lo:hi + 1]
    return text


def _paoi_context_block(pa: dict) -> str:
    mv = pa["faultline_movement"]
    lines = [f"PAOI: {pa['name']} (rank {pa['rank']})"]
    if pa.get("intel_notes"):
        lines.append(f"Standing intel: {pa['intel_notes']}")
    lines.append(f"Actors of interest: {', '.join(pa.get('actors_of_interest', [])) or 'n/a'}")
    if mv["n_faultlines"]:
        lines.append(f"Faultline status (concern 0-100, higher=worse): "
                     f"now {mv['last']:.0f} ({mv['level']}), {_trend_arrow(mv['delta'])} {mv['delta']:+.0f}, peak {mv['peak']:.0f}")
        for f in mv["per_faultline"][:6]:
            lines.append(f"  - {f['name']}: {f['last']:.0f} ({f['level']}) {f['delta']:+.0f}")
    kw = pa["keyword_hits"]
    if kw["n_articles"]:
        lines.append(f"Related reports this period: {kw['n_articles']}. Notable:")
        for a in kw["top_articles"][:5]:
            lines.append(f"  - [{a['published_at']}] {a['title'][:110]} ({a['severity']})")
    return "\n".join(lines)


def _extract_location_hotspots(all_articles: list[dict], top_n: int = 20) -> list[str]:
    """
    Rank locations by mention frequency across ALL matched articles (not just top 5).
    Returns deduplicated list of specific place names, most-mentioned first.
    Filters out state-level and country-level names that are too broad.
    """
    from collections import Counter
    _BROAD = {
        "assam", "meghalaya", "tripura", "mizoram", "manipur", "nagaland",
        "arunachal", "arunachal pradesh", "west bengal", "bangladesh", "india",
        "ner", "northeast", "north east", "northeast india", "new delhi", "delhi",
        "north bengal", "siliguri",
    }
    counter: Counter = Counter()
    for art in all_articles:
        locs = (art.get("entities") or {}).get("locations", [])
        # Also pull from title — titles often contain the most precise location
        title = art.get("title", "")
        district = art.get("district", "")
        if district and district.lower() not in _BROAD:
            counter[district] += 2  # district from classifier gets double weight
        for loc in locs:
            loc = loc.strip()
            if loc and loc.lower() not in _BROAD and len(loc) > 3:
                counter[loc] += 1
    return [loc for loc, _ in counter.most_common(top_n)]


def narrative_paoi_prompt(pa: dict, events: list[dict], period_label: str,
                          all_articles: list[dict] = None) -> str:
    """One PAOI, narrative synthesis grounded in concrete events."""
    mv = pa["faultline_movement"]
    level = mv.get("level", "MONITOR")
    trend = _trend_arrow(mv.get("delta", 0))
    dominant_name = (mv.get("dominant") or {}).get("name", "")
    fl_verbal = f"{level} and {trend.lower()}"
    if dominant_name:
        fl_verbal += f", led by {dominant_name}"

    subissues_block = ""
    top_si = mv.get("top_subissues") or []
    if top_si:
        si_lines = "\n".join(
            f"  - {si.get('name','')}: {si.get('description', si.get('rationale', ''))[:80]}"
            for si in top_si
        )
        subissues_block = f"\nActive sub-issues:\n{si_lines}"

    # Pre-compute hotspot locations from the full article set
    hotspots = _extract_location_hotspots(all_articles or events)
    hotspot_block = ""
    if hotspots:
        hotspot_block = (
            "\nSPECIFIC LOCATIONS CONFIRMED IN REPORTING THIS PERIOD "
            "(use these — do not substitute vague area names):\n"
            + ", ".join(hotspots)
        )

    event_lines = []
    for i, ev in enumerate(events, 1):
        body = (ev.get("why_it_matters") or ev.get("ai_summary") or "")[:300]
        ner_locs = (ev.get("entities") or {}).get("locations", [])
        loc_str = ", ".join(ner_locs[:10]) if ner_locs else ""
        loc_line = f"  NER locations: {loc_str}\n" if loc_str else ""
        district = ev.get("district", "")
        event_lines.append(
            f"EVENT {i}: {ev.get('title', '')}\n"
            f"  Date: {ev.get('published_at','')[:10]}  "
            f"State: {ev.get('state','n/a')}  District: {district or 'n/a'}\n"
            f"{loc_line}"
            f"  Summary: {body}\n"
            f"  Severity: {ev.get('severity','n/a')}  Trajectory: {ev.get('threat_trajectory','n/a')}"
        )
    events_block = "\n\n".join(event_lines) if event_lines else "No specific events retrieved."

    n_events = len(events)
    return f"""You are writing the PAOI narrative section for a commander intelligence brief.

Period: {period_label}
Priority Area: P{pa.get('rank')} {pa['name']}
Geography: {', '.join(pa.get('geography', []))}
Actors of interest: {', '.join(pa.get('actors_of_interest', [])[:6])}
Faultline status: {fl_verbal}{subissues_block}
{hotspot_block}

Most impactful events this period:
{events_block}

STRICT RULES — violation means the output is unusable:
1. Use [CONFIRMED] for direct data points, [ASSESSED] for inference, [SPECULATIVE] for forecasts.
2. No raw faultline scores or numbers.
3. LOCATION SPECIFICITY IS MANDATORY. "Tripura border" = REJECTED. "Assam" alone = REJECTED.
   You MUST name the exact place from the events: crossing point, ICP, border haat, village, NH number + segment, bridge name, district + sub-division, or town. If the event title says "Agartala-Akhaura ICP" — use "Agartala-Akhaura ICP". If it says "NH-44 near Lumding" — use "NH-44, Lumding". Pull directly from the event titles, NER locations, and district fields above.
4. commander_focus format is FIXED: "<Exact named place>: <specific action with timeframe or unit>".
   BAD: "Enhance surveillance along border" — REJECTED (no place, no action detail).
   GOOD: "Sutarkandi ICP, Assam: Deploy additional Customs and BSF team for 24-hr vehicle scanning — 4 cattle + arms seizures confirmed this period".
5. watch_locations must be specific named places from the events above — town, ICP, border haat, NH segment, village. NOT state names.

Return strict JSON:
{{
  "situation_overview": "3-5 sentences naming the most active specific flashpoints from events",
  "events": [
    {{
      "heading": "action-headline under 10 words",
      "location": "EXACT place from event: town / ICP / border haat / NH segment / village",
      "what_happened": "2-3 sentences with specific actor names and exact places",
      "why_it_matters": "1-2 sentences on operational or strategic significance",
      "linkages": "1 sentence connecting to a faultline, sub-issue, or cross-border dynamic"
    }}
  ],
  "overall_assessment": "2-3 sentences naming the highest-risk specific flashpoints",
  "risk_trajectory": "IMPROVING or STABLE or DETERIORATING",
  "watch_locations": ["exact place 1", "exact place 2", "exact place 3", "exact place 4", "exact place 5"],
  "commander_focus": ["<Exact named place>: <specific action + timeframe/unit>", "<place>: <action>", "<place>: <action>"]
}}

Generate one events entry for each of the {n_events} EVENT(s) above.
"""


def lean_all_paoi_prompt(paois: list[dict], period_label: str) -> str:
    """All PAOIs, one batched call (regeneration tier)."""
    blocks = "\n\n".join(_paoi_context_block(pa) for pa in paois)
    ids = [pa["id"] for pa in paois]
    return f"""You are updating the priority-area analysis in an NER strategic intelligence brief (regeneration — keep it concise).

Period: {period_label}

{blocks}

For EACH priority area, give a 2-3 sentence period impact + 1-2 sentence forward concern.
Use claim labels [CONFIRMED]/[ASSESSED]/[SPECULATIVE].

Return strict JSON keyed by PAOI id ({', '.join(ids)}):
{{
  "<paoi_id>": {{"period_impact": "...", "forward_concerns": "...", "manual_review": "..."}},
  ...
}}"""


def overall_inference_prompt(dashboard: list[dict], period_label: str) -> str:
    """Cross-PAOI commander summary."""
    rows = "\n".join(
        f"  P{r['rank']} {r['name']}: {r['score'] if r['score'] is not None else 'n/a'} "
        f"({r['level']}) {r['trend']} {r['delta']:+.0f} — {r['what_changed']}"
        for r in dashboard
    )
    return f"""You are the senior analyst writing the COMMANDER'S BOTTOM LINE for an NER strategic intelligence brief.

Period: {period_label}

Priority area status this period:
{rows}

Return strict JSON:
{{
  "bottom_line": "4-6 sentences: the single most important read across all priority areas this period — what moved, what is most dangerous, what the commander must act on",
  "top_3_focus_next": ["concrete focus item 1 for next period", "item 2", "item 3"]
}}"""


async def run_paoi_synthesis(
    db, paoi_agg: dict, dashboard: list[dict], period_label: str,
    tier: str, call_llm_json
) -> dict:
    """
    Run LLM synthesis. tier='rich' (per-PAOI + overall) or 'lean' (1 batched + overall).
    call_llm_json: async fn(prompt, max_tokens) -> dict  (reuse brief's _call_llm_json).

    Returns {tier, per_paoi: {id: {period_impact, forward_concerns, manual_review}},
             overall: {bottom_line, top_3_focus_next}}
    """
    import asyncio

    paois = paoi_agg.get("paois", [])
    per_paoi: dict = {}

    period_end = paoi_agg.get("as_of", "")

    if tier == "rich":
        def _rich_prompt(pa):
            all_arts = pa["keyword_hits"]["top_articles"]
            events = select_top_events_for_paoi(all_arts, pa, n=5, period_end=period_end)
            return narrative_paoi_prompt(pa, events, period_label, all_articles=all_arts)

        # Sequential calls with a short pause to avoid bursting OpenRouter rate limits.
        # asyncio.gather on 8+ PAOIs causes simultaneous requests that all get throttled.
        for pa in paois:
            try:
                res = await call_llm_json(_rich_prompt(pa), 2000)
                if isinstance(res, dict) and res:
                    per_paoi[pa["id"]] = {
                        "situation_overview": res.get("situation_overview", ""),
                        "events": res.get("events") or [],
                        "overall_assessment": res.get("overall_assessment", ""),
                        "risk_trajectory": res.get("risk_trajectory", "STABLE"),
                        "watch_locations": res.get("watch_locations") or [],
                        "commander_focus": res.get("commander_focus") or [],
                    }
                else:
                    logger.warning(f"PAOI rich synthesis empty for {pa['id']}")
            except Exception as e:
                logger.warning(f"PAOI rich synthesis call failed for {pa['id']}: {e}")
            await asyncio.sleep(1.0)
    else:  # lean
        res = await call_llm_json(lean_all_paoi_prompt(paois, period_label), 1600)
        if isinstance(res, dict):
            # Detect key mismatch — LLM may key by short id / name instead of PAOI id
            known = {pa["id"] for pa in paois}
            returned = set(res.keys())
            if known and not (known & returned):
                logger.error(
                    f"Lean PAOI synthesis key mismatch: got {sorted(returned)}, "
                    f"expected {sorted(known)} — per_paoi will be empty"
                )
            for pa in paois:
                entry = res.get(pa["id"]) or {}
                if entry:
                    per_paoi[pa["id"]] = {
                        "period_impact": entry.get("period_impact", ""),
                        "forward_concerns": entry.get("forward_concerns", ""),
                        "manual_review": entry.get("manual_review", ""),
                    }
        else:
            logger.warning("Lean PAOI synthesis returned non-dict — per_paoi empty")

    overall = await call_llm_json(overall_inference_prompt(dashboard, period_label), 700)
    if not isinstance(overall, dict):
        overall = {}

    return {
        "tier": tier,
        "per_paoi": per_paoi,
        "overall": {
            "bottom_line": overall.get("bottom_line", ""),
            "top_3_focus_next": overall.get("top_3_focus_next", []),
        },
    }


# ── 4. Other Faultline Movements (not in any PAOI) ────────────────────────────
async def other_faultline_movements(db, start_iso: str, end_iso: str, limit: int = 10) -> dict:
    """Rising/declining faultlines NOT linked to any PAOI."""
    from priority_areas_seed import get_priority_faultline_ids
    priority_ids = get_priority_faultline_ids()

    start_date, end_date = start_iso[:10], end_iso[:10]
    cursor = db.faultline_scores.find(
        {"date": {"$gte": start_date, "$lte": end_date},
         "faultline_id": {"$nin": list(priority_ids)}},
        {"_id": 0, "faultline_id": 1, "faultline_name": 1, "state": 1,
         "date": 1, "score": 1, "level": 1},
    ).sort("date", 1)

    by_fl: dict[str, list] = defaultdict(list)
    async for s in cursor:
        by_fl[s["faultline_id"]].append(s)

    summaries = []
    for fl_id, series in by_fl.items():
        series = sorted(series, key=lambda x: x["date"])
        first, last = series[0]["score"], series[-1]["score"]
        summaries.append({
            "id": fl_id,
            "name": series[-1].get("faultline_name", fl_id),
            "state": series[-1].get("state", ""),
            "last": round(last, 1),
            "delta": round(last - first, 1),
            "level": _concern_level(last),
        })

    rising = sorted([s for s in summaries if s["delta"] >= 8], key=lambda x: -x["delta"])[:limit]
    declining = sorted([s for s in summaries if s["delta"] <= -8], key=lambda x: x["delta"])[:limit]
    return {"rising": rising, "declining": declining}
