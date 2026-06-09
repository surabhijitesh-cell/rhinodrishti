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
         "score": 1, "level": 1},
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
        return {
            "id": fl_id,
            "name": series[-1].get("faultline_name", fl_id),
            "first": round(first, 1),
            "last": round(last, 1),
            "peak": round(peak, 1),
            "avg": round(avg, 1),
            "delta": round(last - first, 1),
            "level": _concern_level(last),
        }

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
            }
        else:
            movement = {
                "first": None, "last": None, "peak": None, "avg": None,
                "delta": 0.0, "level": "STABLE", "n_faultlines": 0,
                "dominant": None, "per_faultline": [],
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
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "source": 1,
         "source_url": 1, "published_at": 1, "severity": 1, "priority_score": 1},
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
            "url": a.get("source_url", ""),
        }
        for a in matched[:8]
    ]
    return {"n_articles": len(matched), "top_articles": top}


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


def rich_paoi_prompt(pa: dict, period_label: str) -> str:
    """One PAOI, deep synthesis."""
    return f"""You are writing the analysis for ONE commander priority area in an NER strategic intelligence brief.

Period: {period_label}

{_paoi_context_block(pa)}

Write a tight analysis. Use claim labels: [CONFIRMED] for direct data points,
[ASSESSED] for inference, [SPECULATIVE] for forecasts.

Return strict JSON:
{{
  "period_impact": "3-5 sentences: how this priority area's faultlines moved this period and WHY, citing the data above",
  "forward_concerns": "2-4 sentences: what to watch in this area next period",
  "manual_review": "1-2 sentences: specific OSINT/social-media checks to validate weak signals here"
}}"""


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

    if tier == "rich":
        tasks = [call_llm_json(rich_paoi_prompt(pa, period_label), 700) for pa in paois]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for pa, res in zip(paois, results):
            if isinstance(res, Exception):
                logger.warning(f"PAOI rich synthesis call failed for {pa['id']}: {res}")
            elif isinstance(res, dict) and res:
                per_paoi[pa["id"]] = {
                    "period_impact": res.get("period_impact", ""),
                    "forward_concerns": res.get("forward_concerns", ""),
                    "manual_review": res.get("manual_review", ""),
                }
            else:
                logger.warning(f"PAOI rich synthesis empty for {pa['id']}")
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
