"""
Custom analytics widget endpoints — powers the Dashboard customization section.

Single dispatch endpoint:
  GET /analytics/widget?widget=<type>&state=&category=&actor=&severity=&range=&border_only=

Widget types:
  - severity_evolution   per-state daily severity bands (stacked area input)
  - threat_heatmap       state × threat_category activity matrix
  - actor_activity       top actors with severity breakdown
  - intel_velocity       incidents/day + acceleration per state
  - geo_density          top locations by item count (severity weighted)
  - category_breakdown   threat-category counts (filtered)
  - severity_pie         severity distribution pie for filter set
  - source_breakdown     items by source/source_type
"""
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from collections import defaultdict
from shared import db, intelligence_col, NER_STATES, logger

router = APIRouter()

NER_STATES_FULL = list(dict.fromkeys(NER_STATES + ["Nagaland", "Sikkim"]))
BORDER_COUNTRIES = {"Bangladesh", "Myanmar", "Bhutan", "China", "Nepal"}

_RANGE_HOURS = {"24h": 24, "7d": 24*7, "30d": 24*30, "90d": 24*90, "365d": 24*365}
_SEV_WEIGHT  = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _build_mongo_filter(
    state: Optional[str], category: Optional[str], actor: Optional[str],
    severity: Optional[str], range_str: str, border_only: bool,
) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=_RANGE_HOURS.get(range_str, 168))).isoformat()
    f: dict = {"published_at": {"$gte": cutoff}}
    if state and state != "All":
        f["state"] = state
    if category and category != "All":
        f["threat_category"] = category
    if severity and severity != "All":
        f["severity"] = severity
    if actor:
        f["entities.organizations"] = {"$regex": actor, "$options": "i"}
    if border_only:
        f["$or"] = [
            {"state": {"$in": list(BORDER_COUNTRIES)}},
            {"entities.locations": {"$elemMatch": {"$in": list(BORDER_COUNTRIES)}}},
        ]
    return f


@router.get("/analytics/widget")
async def get_widget_data(
    widget:      str  = Query(..., description="Widget type"),
    state:       Optional[str] = None,
    category:    Optional[str] = None,
    actor:       Optional[str] = None,
    severity:    Optional[str] = None,
    range:       str = Query("7d", regex="^(24h|7d|30d|90d|365d)$"),
    border_only: bool = False,
    limit:       int  = Query(15, ge=3, le=50),
):
    q = _build_mongo_filter(state, category, actor, severity, range, border_only)
    range_str = range

    # ── 1. severity_evolution: per-state daily bands ──────────────────────────
    if widget == "severity_evolution":
        buckets: dict = {}
        async for item in intelligence_col.find(q, {"published_at": 1, "severity": 1, "state": 1, "_id": 0}):
            d = (item.get("published_at") or "")[:10]
            if not d:
                continue
            sev = item.get("severity") or "low"
            if d not in buckets:
                buckets[d] = {"date": d, "critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
            if sev in buckets[d]:
                buckets[d][sev] += 1
            buckets[d]["total"] += 1
        return {"widget": widget, "data": sorted(buckets.values(), key=lambda x: x["date"])}

    # ── 2. threat_heatmap: state × category matrix ────────────────────────────
    if widget == "threat_heatmap":
        matrix: dict = defaultdict(lambda: defaultdict(int))
        categories_set, states_set = set(), set()
        async for item in intelligence_col.find(q, {"state": 1, "threat_category": 1, "_id": 0}):
            st = item.get("state") or "Unknown"
            cat = item.get("threat_category") or "Other"
            if st not in NER_STATES_FULL and st not in BORDER_COUNTRIES:
                continue
            matrix[st][cat] += 1
            categories_set.add(cat)
            states_set.add(st)
        cats = sorted(categories_set)
        rows = [{"state": st, **{c: matrix[st][c] for c in cats}, "total": sum(matrix[st].values())}
                for st in sorted(states_set)]
        return {"widget": widget, "categories": cats, "data": rows}

    # ── 3. actor_activity: top actors ─────────────────────────────────────────
    if widget == "actor_activity":
        actor_stats: dict = defaultdict(lambda: {"name": "", "count": 0, "critical": 0, "high": 0,
                                                  "medium": 0, "low": 0, "states": set()})
        async for item in intelligence_col.find(q, {"entities": 1, "severity": 1, "state": 1, "_id": 0}):
            sev = item.get("severity") or "low"
            st  = item.get("state") or ""
            for a in ((item.get("entities") or {}).get("organizations") or [])[:5]:
                if not a:
                    continue
                rec = actor_stats[a]
                rec["name"] = a
                rec["count"] += 1
                if sev in rec:
                    rec[sev] += 1
                if st:
                    rec["states"].add(st)
        top = sorted(actor_stats.values(), key=lambda x: -x["count"])[:limit]
        for t in top:
            t["state_count"] = len(t["states"])
            t["states"] = sorted(t["states"])
        return {"widget": widget, "data": top}

    # ── 4. intel_velocity: per-state incidents/day + acceleration ─────────────
    if widget == "intel_velocity":
        hours  = _RANGE_HOURS[range_str]
        third  = hours / 3
        cutoff_dt   = datetime.now(timezone.utc) - timedelta(hours=hours)
        early_end   = (cutoff_dt + timedelta(hours=third)).isoformat()
        late_start  = (datetime.now(timezone.utc) - timedelta(hours=third)).isoformat()

        st_counts: dict = defaultdict(lambda: {"state": "", "total": 0, "early": 0, "late": 0, "sev_weight": 0})
        for st in NER_STATES_FULL:
            st_counts[st]["state"] = st
        async for item in intelligence_col.find(q, {"published_at": 1, "state": 1, "severity": 1, "_id": 0}):
            st = item.get("state") or ""
            if st not in NER_STATES_FULL:
                continue
            rec = st_counts[st]
            rec["total"] += 1
            rec["sev_weight"] += _SEV_WEIGHT.get(item.get("severity") or "low", 1)
            pub = item.get("published_at") or ""
            if pub < early_end:
                rec["early"] += 1
            if pub >= late_start:
                rec["late"] += 1

        results = []
        days = max(hours / 24, 1)
        for rec in st_counts.values():
            per_day = round(rec["total"] / days, 2)
            if rec["early"] > 0:
                accel = round(rec["late"] / rec["early"], 2)
            elif rec["late"] > 0:
                accel = 3.0  # late activity, no early baseline
            else:
                accel = 0.0
            trend = "RISING" if accel > 1.2 else "FALLING" if accel < 0.8 and rec["total"] > 0 else "STEADY"
            results.append({"state": rec["state"], "total": rec["total"],
                            "per_day": per_day, "acceleration": accel,
                            "sev_weight": rec["sev_weight"], "trend": trend})
        results.sort(key=lambda x: (-x["sev_weight"], -x["total"]))
        return {"widget": widget, "data": results}

    # ── 5. geo_density: top locations ─────────────────────────────────────────
    if widget == "geo_density":
        loc_stats: dict = defaultdict(lambda: {"name": "", "count": 0, "critical": 0, "high": 0,
                                                "medium": 0, "low": 0, "states": set()})
        async for item in intelligence_col.find(q, {"entities": 1, "severity": 1, "state": 1, "_id": 0}):
            sev = item.get("severity") or "low"
            st  = item.get("state") or ""
            for loc in ((item.get("entities") or {}).get("locations") or []):
                if not loc or loc in NER_STATES_FULL or loc in BORDER_COUNTRIES:
                    continue
                rec = loc_stats[loc]
                rec["name"] = loc
                rec["count"] += 1
                if sev in rec:
                    rec[sev] += 1
                if st:
                    rec["states"].add(st)
        results = sorted(loc_stats.values(), key=lambda x: (-x["critical"]*10 - x["high"]*5, -x["count"]))[:limit]
        for r in results:
            r["primary_state"] = next(iter(r["states"])) if r["states"] else ""
            r["states"] = sorted(r["states"])
        return {"widget": widget, "data": results}

    # ── 6. category_breakdown ─────────────────────────────────────────────────
    if widget == "category_breakdown":
        cat_stats: dict = defaultdict(lambda: {"category": "", "count": 0, "critical": 0, "high": 0})
        async for item in intelligence_col.find(q, {"threat_category": 1, "severity": 1, "_id": 0}):
            cat = item.get("threat_category") or "Other"
            sev = item.get("severity") or "low"
            rec = cat_stats[cat]
            rec["category"] = cat
            rec["count"] += 1
            if sev in ("critical", "high"):
                rec[sev] += 1
        results = sorted(cat_stats.values(), key=lambda x: -x["count"])[:limit]
        return {"widget": widget, "data": results}

    # ── 7. severity_pie ───────────────────────────────────────────────────────
    if widget == "severity_pie":
        sev_stats = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        async for item in intelligence_col.find(q, {"severity": 1, "_id": 0}):
            sev = item.get("severity") or "low"
            if sev in sev_stats:
                sev_stats[sev] += 1
        return {"widget": widget,
                "data": [{"name": k, "value": v} for k, v in sev_stats.items() if v > 0]}

    # ── 8. source_breakdown ───────────────────────────────────────────────────
    if widget == "source_breakdown":
        src_stats: dict = defaultdict(lambda: {"source": "", "count": 0, "critical": 0, "high": 0})
        async for item in intelligence_col.find(q, {"source_name": 1, "source_type": 1, "severity": 1, "_id": 0}):
            src = item.get("source_name") or item.get("source_type") or "Unknown"
            sev = item.get("severity") or "low"
            rec = src_stats[src]
            rec["source"] = src
            rec["count"] += 1
            if sev in ("critical", "high"):
                rec[sev] += 1
        return {"widget": widget,
                "data": sorted(src_stats.values(), key=lambda x: -x["count"])[:limit]}

    raise HTTPException(400, f"Unknown widget type: {widget}")


# ── Filter options for the customize panel ───────────────────────────────────
@router.get("/analytics/filter-options")
async def get_filter_options():
    """Returns lists of available states / categories / actors for filter dropdowns."""
    states = NER_STATES_FULL + list(BORDER_COUNTRIES)
    categories = await intelligence_col.distinct("threat_category")
    categories = [c for c in categories if c]
    # Top actors only (full list is huge — limit to most active)
    top_actors_cursor = intelligence_col.aggregate([
        {"$unwind": "$entities.organizations"},
        {"$group": {"_id": "$entities.organizations", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
        {"$project": {"_id": 0, "name": "$_id", "count": 1}},
    ])
    actors = [a async for a in top_actors_cursor]
    return {
        "states":     sorted(states),
        "categories": sorted(categories),
        "actors":     actors,
    }
