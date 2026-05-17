"""
Trends Intelligence Center endpoints.

Multi-timeframe trend analysis, state drill-down, stability index,
and cross-border correlation — all driven from intelligence_items.

GET /trends?range=7d|30d|90d|365d           — top-level dashboard data
GET /trends/state/{state}?range=...         — drill-down for a single state
GET /trends/stability?range=30d             — per-state composite stability index
GET /trends/cross-border?range=30d          — Bangladesh/Myanmar ↔ NER correlation
"""
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from collections import defaultdict
from shared import db, intelligence_col, NER_STATES, logger

router = APIRouter()

# Full NER state set including Nagaland + Sikkim (shared.NER_STATES omits these
# because some queries use it as an exclusion list — keep that untouched, but
# Trends + Stability Index must cover all 8 NER states).
NER_STATES_FULL = list(dict.fromkeys(NER_STATES + ["Nagaland", "Sikkim"]))

# ── Range parsing ─────────────────────────────────────────────────────────────
_RANGE_HOURS = {"24h": 24, "7d": 24*7, "30d": 24*30, "90d": 24*90, "365d": 24*365}

def _range_to_hours(range_str: str) -> int:
    return _RANGE_HOURS.get(range_str, 24*7)

def _cutoff_iso(range_str: str) -> str:
    hours = _range_to_hours(range_str)
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

def _bucket_size_days(range_str: str) -> int:
    """Group items into buckets sized by range — keep chart x-axis readable."""
    h = _range_to_hours(range_str)
    if h <= 24:        return 1   # hourly-ish but treated as 1-day buckets here
    if h <= 24*7:      return 1   # daily
    if h <= 24*30:     return 1   # daily
    if h <= 24*90:     return 3   # 3-day
    return 7                       # weekly buckets for 365d


# ── Cross-border country detection ────────────────────────────────────────────
_BORDER_COUNTRIES = {"Bangladesh", "Myanmar", "Bhutan", "China", "Nepal"}

def _has_cross_border(item: dict) -> bool:
    """Item touches a border country (mentioned in entities.locations or state)."""
    locs = (item.get("entities") or {}).get("locations") or []
    if any(c in (locs or []) for c in _BORDER_COUNTRIES):
        return True
    state = item.get("state") or ""
    return state in _BORDER_COUNTRIES


# ── Severity weight ───────────────────────────────────────────────────────────
_SEV_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


# ─────────────────────────────────────────────────────────────────────────────
@router.get("/trends")
async def get_trends(range: str = Query("7d", regex="^(24h|7d|30d|90d|365d)$")):
    """Top-level trends data for the Trends Intelligence Center page."""
    cutoff = _cutoff_iso(range)
    bucket_days = _bucket_size_days(range)

    # Daily severity buckets
    daily_severity: Dict[str, Dict] = {}
    category_stats: Dict[str, Dict] = {}
    state_stats: Dict[str, Dict] = {}
    state_daily: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    actor_freq: Dict[str, int] = defaultdict(int)

    async for item in intelligence_col.find(
        {"published_at": {"$gte": cutoff}},
        {"published_at": 1, "severity": 1, "threat_category": 1, "state": 1,
         "entities": 1, "_id": 0},
    ):
        pub = item.get("published_at", "")
        if not pub or len(pub) < 10:
            continue
        date_key = pub[:10]
        sev = item.get("severity") or "low"
        state = item.get("state") or "Unknown"
        category = item.get("threat_category") or "Other"

        # Bucket date for chart
        try:
            d = datetime.fromisoformat(date_key)
            bucket_idx = (d.toordinal() // bucket_days) * bucket_days
            bucket_key = datetime.fromordinal(bucket_idx).strftime("%Y-%m-%d")
        except Exception:
            bucket_key = date_key

        # Daily severity totals
        if bucket_key not in daily_severity:
            daily_severity[bucket_key] = {"date": bucket_key, "critical": 0, "high": 0,
                                          "medium": 0, "low": 0, "total": 0}
        if sev in daily_severity[bucket_key]:
            daily_severity[bucket_key][sev] += 1
        daily_severity[bucket_key]["total"] += 1

        # Category stats
        if category not in category_stats:
            category_stats[category] = {"category": category, "count": 0,
                                        "critical": 0, "high": 0}
        category_stats[category]["count"] += 1
        if sev in ("critical", "high"):
            category_stats[category][sev] += 1

        # State stats
        if state not in state_stats:
            state_stats[state] = {"state": state, "count": 0, "critical": 0, "high": 0,
                                  "medium": 0, "low": 0}
        state_stats[state]["count"] += 1
        if sev in state_stats[state]:
            state_stats[state][sev] += 1

        # Per-state daily for evolution chart
        state_daily[state][bucket_key] += 1

        # Actor frequency
        actors = (item.get("entities") or {}).get("organizations") or []
        for actor in actors[:5]:
            if actor:
                actor_freq[actor] += 1

    # Build per-state daily series for multi-line chart.
    # Always include all NER states (zero-fill when no items) so the chart legend
    # and stability ranking show every state.
    state_evolution = []
    all_buckets = sorted(daily_severity.keys())
    for state in NER_STATES_FULL:
        daily = state_daily.get(state, {})
        series = [{"date": b, "count": daily.get(b, 0)} for b in all_buckets]
        state_evolution.append({"state": state, "series": series})

    # Top actors (sorted)
    top_actors = sorted(
        [{"name": k, "count": v} for k, v in actor_freq.items()],
        key=lambda x: -x["count"]
    )[:20]

    return {
        "range": range,
        "daily_severity": sorted(daily_severity.values(), key=lambda x: x["date"]),
        "category_stats": sorted(category_stats.values(), key=lambda x: -x["count"]),
        "state_stats": sorted(state_stats.values(), key=lambda x: -x["count"]),
        "state_evolution": state_evolution,
        "top_actors": top_actors,
    }


# ─────────────────────────────────────────────────────────────────────────────
@router.get("/trends/state/{state}")
async def get_state_drilldown(
    state: str,
    range: str = Query("30d", regex="^(24h|7d|30d|90d|365d)$"),
):
    """Per-state drill-down: top locations, top actors, daily evolution, category breakdown."""
    cutoff = _cutoff_iso(range)
    location_stats: Dict[str, Dict] = {}
    actor_stats: Dict[str, Dict] = {}
    category_stats: Dict[str, int] = defaultdict(int)
    daily: Dict[str, Dict] = {}

    async for item in intelligence_col.find(
        {"state": state, "published_at": {"$gte": cutoff}},
        {"published_at": 1, "severity": 1, "threat_category": 1,
         "entities": 1, "title": 1, "id": 1, "_id": 0},
    ):
        sev = item.get("severity") or "low"
        pub = (item.get("published_at") or "")[:10]
        cat = item.get("threat_category") or "Other"
        category_stats[cat] += 1

        # Daily
        if pub:
            if pub not in daily:
                daily[pub] = {"date": pub, "critical": 0, "high": 0, "medium": 0,
                              "low": 0, "total": 0}
            if sev in daily[pub]:
                daily[pub][sev] += 1
            daily[pub]["total"] += 1

        # Locations (skip state names themselves)
        locs = (item.get("entities") or {}).get("locations") or []
        for loc in locs:
            if not loc or loc == state:
                continue
            if loc not in location_stats:
                location_stats[loc] = {"name": loc, "count": 0, "critical": 0, "high": 0}
            location_stats[loc]["count"] += 1
            if sev in ("critical", "high"):
                location_stats[loc][sev] += 1

        # Actors
        actors = (item.get("entities") or {}).get("organizations") or []
        for actor in actors:
            if not actor:
                continue
            if actor not in actor_stats:
                actor_stats[actor] = {"name": actor, "count": 0, "critical": 0, "high": 0}
            actor_stats[actor]["count"] += 1
            if sev in ("critical", "high"):
                actor_stats[actor][sev] += 1

    # Score locations by severity weight + raw count
    def loc_score(l):
        return l["critical"] * 10 + l["high"] * 5 + l["count"]

    top_locations = sorted(location_stats.values(), key=lambda x: -loc_score(x))[:10]
    top_actors    = sorted(actor_stats.values(),    key=lambda x: -x["count"])[:10]
    categories    = sorted([{"category": k, "count": v} for k, v in category_stats.items()],
                           key=lambda x: -x["count"])

    return {
        "state": state,
        "range": range,
        "daily_severity": sorted(daily.values(), key=lambda x: x["date"]),
        "top_locations": top_locations,
        "top_actors":    top_actors,
        "categories":    categories,
    }


# ─────────────────────────────────────────────────────────────────────────────
@router.get("/trends/stability")
async def get_stability_index(
    range: str = Query("30d", regex="^(7d|30d|90d|365d)$"),
):
    """
    Strategic Stability Index per state — composite 0-100 score.
    Lower score = more unstable / higher operational concern.

    Composition:
      Severity load   40%  — weighted severity intensity vs. peer states
      Velocity        25%  — acceleration (recent third vs. earliest third)
      Actor spread    20%  — unique militant orgs operating in state
      Cross-border    15%  — share of items mentioning border countries
    """
    cutoff = _cutoff_iso(range)
    hours  = _range_to_hours(range)
    third  = hours / 3
    cutoff_dt = datetime.fromisoformat(cutoff)
    early_end = (cutoff_dt + timedelta(hours=third)).isoformat()
    late_start = (datetime.now(timezone.utc) - timedelta(hours=third)).isoformat()

    state_metrics: Dict[str, Dict] = {}

    # Pre-seed all NER states so every state shows a card even with zero items
    for st in NER_STATES_FULL:
        state_metrics[st] = {
            "state": st, "total": 0, "sev_weight": 0,
            "early_count": 0, "late_count": 0,
            "actors": set(), "cross_border_count": 0,
        }

    async for item in intelligence_col.find(
        {"published_at": {"$gte": cutoff}},
        {"published_at": 1, "severity": 1, "state": 1, "entities": 1, "_id": 0},
    ):
        state = item.get("state") or "Unknown"
        if state not in NER_STATES_FULL:
            continue
        m = state_metrics[state]
        m["total"] += 1
        m["sev_weight"] += _SEV_WEIGHT.get(item.get("severity") or "low", 1)

        pub = item.get("published_at") or ""
        if pub < early_end:
            m["early_count"] += 1
        if pub >= late_start:
            m["late_count"] += 1

        for actor in ((item.get("entities") or {}).get("organizations") or []):
            if actor:
                m["actors"].add(actor)

        if _has_cross_border(item):
            m["cross_border_count"] += 1

    # Normalize & score
    if not state_metrics:
        return {"range": range, "states": []}

    max_sev    = max((m["sev_weight"] for m in state_metrics.values()), default=1) or 1
    max_actors = max((len(m["actors"]) for m in state_metrics.values()), default=1) or 1

    results = []
    for m in state_metrics.values():
        # severity load (0-1)
        severity_load = m["sev_weight"] / max_sev
        # velocity (0-1) — accelerating = late/early ratio > 1, capped
        velocity = 0.0
        if m["early_count"] > 0:
            ratio = m["late_count"] / max(m["early_count"], 1)
            velocity = min(ratio / 3, 1.0)  # 3x = full
        elif m["late_count"] > 0:
            velocity = 0.8  # late activity with no early baseline
        # actor spread (0-1)
        actor_spread = len(m["actors"]) / max_actors
        # cross-border share (0-1)
        cross_border = (m["cross_border_count"] / m["total"]) if m["total"] else 0

        concern = (severity_load * 0.40 + velocity * 0.25 +
                   actor_spread * 0.20 + cross_border * 0.15)
        stability = max(0, round(100 - concern * 100))

        # Concern level label
        if   stability >= 75: level = "STABLE"
        elif stability >= 50: level = "MONITOR"
        elif stability >= 25: level = "ELEVATED"
        else:                 level = "CRITICAL"

        results.append({
            "state": m["state"],
            "stability_score": stability,
            "concern_level": level,
            "metrics": {
                "total_items":   m["total"],
                "sev_weight":    m["sev_weight"],
                "early_count":   m["early_count"],
                "late_count":    m["late_count"],
                "velocity":      round(velocity, 2),
                "actor_count":   len(m["actors"]),
                "cross_border_share": round(cross_border, 2),
            },
        })

    results.sort(key=lambda x: x["stability_score"])  # most concerning first
    return {"range": range, "states": results}


# ─────────────────────────────────────────────────────────────────────────────
@router.get("/trends/cross-border")
async def get_cross_border_trends(
    range: str = Query("30d", regex="^(7d|30d|90d|365d)$"),
):
    """
    Dual-axis correlation series: border-country events ↔ correlated NER state activity.
    Pairs:
      Myanmar    ↔ Manipur + Nagaland
      Bangladesh ↔ Assam + Tripura + Meghalaya
      China      ↔ Arunachal Pradesh + Sikkim
    """
    cutoff = _cutoff_iso(range)
    pairs = {
        "Myanmar":    ["Manipur", "Nagaland"],
        "Bangladesh": ["Assam", "Tripura", "Meghalaya"],
        "China":      ["Arunachal Pradesh", "Sikkim"],
    }
    border_daily: Dict[str, Dict[str, int]] = {b: defaultdict(int) for b in pairs}
    ner_daily:    Dict[str, Dict[str, int]] = {b: defaultdict(int) for b in pairs}

    async for item in intelligence_col.find(
        {"published_at": {"$gte": cutoff}},
        {"published_at": 1, "state": 1, "entities": 1, "_id": 0},
    ):
        pub = (item.get("published_at") or "")[:10]
        if not pub:
            continue
        state = item.get("state") or ""
        locs  = set((item.get("entities") or {}).get("locations") or [])

        for border, ner_states in pairs.items():
            if state == border or border in locs:
                border_daily[border][pub] += 1
            if state in ner_states:
                ner_daily[border][pub] += 1

    # Merge into series per border
    series = []
    for border in pairs:
        all_dates = sorted(set(border_daily[border].keys()) | set(ner_daily[border].keys()))
        merged = [{
            "date": d,
            "border_events": border_daily[border].get(d, 0),
            "ner_events":    ner_daily[border].get(d, 0),
        } for d in all_dates]
        series.append({
            "border": border,
            "ner_states": pairs[border],
            "data": merged,
        })

    return {"range": range, "series": series}
