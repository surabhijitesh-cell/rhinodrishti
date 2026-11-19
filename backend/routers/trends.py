"""
Trends Intelligence Center endpoints.

Multi-timeframe trend analysis, state drill-down, stability index,
and cross-border correlation — all driven from intelligence_items.

GET /trends?range=7d|30d|90d|365d           — top-level dashboard data
GET /trends/state/{state}?range=...         — drill-down for a single state
GET /trends/stability?range=30d             — per-state composite stability index
GET /trends/cross-border?range=30d          — Bangladesh/Myanmar ↔ NER correlation

Only processed, relevant items with a real severity (critical/high/medium/low)
are counted, and only the primary copy of a duplicate cluster.
"""
from fastapi import APIRouter, Query
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from shared import db, intelligence_col, NER_STATES, logger
from intel_rules import is_cross_border_item, cross_border_query, CROSS_BORDER_COUNTRIES

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


# ── What counts as an item ────────────────────────────────────────────────────
REAL_SEVERITIES = ["critical", "high", "medium", "low"]
HIDDEN_TAGS = ["not_relevant", "unprocessed", "stage0_filtered", "stage05_filtered", "stage1_filtered"]

def countable_query(cutoff: str, extra: Optional[dict] = None) -> dict:
    """Database filter for items Trends may count."""
    query = {
        "published_at": {"$gte": cutoff},
        "processed": True,
        "severity": {"$in": REAL_SEVERITIES},
        "is_cluster_primary": {"$ne": False},
        "tags": {"$nin": HIDDEN_TAGS},
    }
    if extra:
        query.update(extra)
    return query

def is_countable_item(item: dict) -> bool:
    """Same rule as countable_query, applied to one item (belt and braces)."""
    if not isinstance(item, dict) or item.get("processed") is not True:
        return False
    if item.get("severity") not in REAL_SEVERITIES or item.get("is_cluster_primary") is False:
        return False
    tags = item.get("tags")
    return not (isinstance(tags, list) and set(tags) & set(HIDDEN_TAGS))

def _text_list(item: dict, key: str) -> List[str]:
    """Null-safe list of strings from item['entities'][key]."""
    entities = item.get("entities")
    values = entities.get(key) if isinstance(entities, dict) else None
    return [v for v in (values if isinstance(values, list) else []) if isinstance(v, str) and v]

def _known_state(item: dict) -> Optional[str]:
    """The NER state of an item, or None (Unclassified, Bangladesh, Myanmar, junk)."""
    state = item.get("state")
    return state if isinstance(state, str) and state in NER_STATES_FULL else None


# ── Severity weight ───────────────────────────────────────────────────────────
_SEV_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# Stability reference levels, per day of the selected range. A state at or above
# the reference scores full concern on that part; scaling is absolute, so the
# busiest state is NOT automatically the maximum. PROVISIONAL: to be calibrated
# from live data.
STABILITY_SEVERITY_LOAD_REF_PER_DAY = 70.0  # just above the busiest state seen in Nov 2026 (56-66 a day)
STABILITY_ACTOR_SPREAD_REF_PER_DAY = 20.0  # just above the busiest state seen in Nov 2026 (about 14 a day)
STABILITY_FULL_CONFIDENCE_ITEMS = 10       # below this, surge and cross-border shares are scaled down


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_stability(m: dict, days: float) -> dict:
    """Stability result for one state's metrics (pure).

    No items -> status "No data", score None (never a fake STABLE 100).
    """
    total = m["total"]
    actor_count = len(m["actors"])
    if total == 0:
        return {"stability_score": None, "concern_level": "No data",
                "velocity": 0.0, "cross_border_share": 0.0}

    days = max(days, 1.0)
    severity_load = _clamp01(m["sev_weight"] / (STABILITY_SEVERITY_LOAD_REF_PER_DAY * days))
    velocity = 0.0
    if m["early_count"] > 0:
        velocity = _clamp01((m["late_count"] / m["early_count"]) / 3)  # 3x = full
    elif m["late_count"] > 0:
        velocity = 0.8  # late activity with no early baseline
    actor_spread = _clamp01(actor_count / (STABILITY_ACTOR_SPREAD_REF_PER_DAY * days))
    cross_border = _clamp01(m["cross_border_count"] / total)

    # One or two items must not read as a surge or as a mostly cross-border state.
    confidence = _clamp01(total / STABILITY_FULL_CONFIDENCE_ITEMS)
    concern = (severity_load * 0.40 + velocity * confidence * 0.25 +
               actor_spread * 0.20 + cross_border * confidence * 0.15)
    stability = int(max(0, min(100, round(100 - concern * 100))))

    if   stability >= 75: level = "STABLE"
    elif stability >= 50: level = "MONITOR"
    elif stability >= 25: level = "ELEVATED"
    else:                 level = "CRITICAL"
    return {"stability_score": stability, "concern_level": level,
            "velocity": round(velocity, 2), "cross_border_share": round(cross_border, 2)}


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
    total_items = 0
    unclassified_count = 0   # counted above, but not in a known NER state

    async for item in intelligence_col.find(
        countable_query(cutoff),
        {"published_at": 1, "severity": 1, "threat_category": 1, "state": 1,
         "entities": 1, "processed": 1, "tags": 1, "is_cluster_primary": 1, "_id": 0},
    ):
        try:
            if not is_countable_item(item):
                continue
            pub = item.get("published_at")
            if not isinstance(pub, str) or len(pub) < 10:
                continue
            date_key = pub[:10]
            sev = item["severity"]
            state = _known_state(item)
            category = item.get("threat_category")
            category = category if isinstance(category, str) and category else "Other"

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
            daily_severity[bucket_key][sev] += 1
            daily_severity[bucket_key]["total"] += 1

            # Category stats
            if category not in category_stats:
                category_stats[category] = {"category": category, "count": 0,
                                            "critical": 0, "high": 0}
            category_stats[category]["count"] += 1
            if sev in ("critical", "high"):
                category_stats[category][sev] += 1

            # State stats / per-state daily: known NER states only
            if state:
                if state not in state_stats:
                    state_stats[state] = {"state": state, "count": 0, "critical": 0, "high": 0,
                                          "medium": 0, "low": 0}
                state_stats[state]["count"] += 1
                state_stats[state][sev] += 1
                state_daily[state][bucket_key] += 1
            else:
                unclassified_count += 1

            for actor in _text_list(item, "organizations")[:5]:
                actor_freq[actor] += 1
            total_items += 1
        except Exception as e:  # one bad record must not fail the page
            logger.warning("trends: skipped bad item: %s", e)

    # Always include all NER states (zero-fill when no items) so the chart legend
    # and stability ranking show every state.
    state_evolution = []
    all_buckets = sorted(daily_severity.keys())
    for state in NER_STATES_FULL:
        daily = state_daily.get(state, {})
        series = [{"date": b, "count": daily.get(b, 0)} for b in all_buckets]
        state_evolution.append({"state": state, "series": series})

    top_actors = sorted(
        [{"name": k, "count": v} for k, v in actor_freq.items()],
        key=lambda x: -x["count"]
    )[:20]

    return {
        "range": range,
        "total_items": total_items,
        "unclassified_count": unclassified_count,
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
        countable_query(cutoff, {"state": state}),
        {"published_at": 1, "severity": 1, "threat_category": 1,
         "entities": 1, "title": 1, "id": 1, "processed": 1, "tags": 1,
         "is_cluster_primary": 1, "_id": 0},
    ):
        try:
            if not is_countable_item(item):
                continue
            sev = item["severity"]
            pub = (item.get("published_at") or "")[:10] if isinstance(item.get("published_at"), str) else ""
            cat = item.get("threat_category")
            cat = cat if isinstance(cat, str) and cat else "Other"
            category_stats[cat] += 1

            if pub:
                if pub not in daily:
                    daily[pub] = {"date": pub, "critical": 0, "high": 0, "medium": 0,
                                  "low": 0, "total": 0}
                daily[pub][sev] += 1
                daily[pub]["total"] += 1

            for loc in _text_list(item, "locations"):
                if loc == state:
                    continue
                if loc not in location_stats:
                    location_stats[loc] = {"name": loc, "count": 0, "critical": 0, "high": 0}
                location_stats[loc]["count"] += 1
                if sev in ("critical", "high"):
                    location_stats[loc][sev] += 1

            for actor in _text_list(item, "organizations"):
                if actor not in actor_stats:
                    actor_stats[actor] = {"name": actor, "count": 0, "critical": 0, "high": 0}
                actor_stats[actor]["count"] += 1
                if sev in ("critical", "high"):
                    actor_stats[actor][sev] += 1
        except Exception as e:
            logger.warning("trends drilldown: skipped bad item: %s", e)

    def loc_score(l):
        return l["critical"] * 10 + l["high"] * 5 + l["count"]

    top_locations = sorted(location_stats.values(), key=lambda x: -loc_score(x))[:10]
    top_actors    = sorted(actor_stats.values(),    key=lambda x: -x["count"])[:10]
    categories    = sorted([{"category": k, "count": v} for k, v in category_stats.items()],
                           key=lambda x: -x["count"])

    return {
        "state": state,
        "range": range,
        "total_items": sum(category_stats.values()),
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
    A state with no items reports "No data" (score null), never a fake 100.

    Composition:
      Severity load   40%  — weighted severity intensity vs. a per-day reference level
      Velocity        25%  — acceleration (recent third vs. earliest third)
      Actor spread    20%  — unique militant orgs vs. a per-day reference level
      Cross-border    15%  — share of items mentioning border countries
    """
    cutoff = _cutoff_iso(range)
    hours  = _range_to_hours(range)
    third  = hours / 3
    cutoff_dt = datetime.fromisoformat(cutoff)
    early_end = (cutoff_dt + timedelta(hours=third)).isoformat()
    late_start = (datetime.now(timezone.utc) - timedelta(hours=third)).isoformat()

    # Pre-seed all NER states so every state shows a card even with zero items
    state_metrics: Dict[str, Dict] = {
        st: {"state": st, "total": 0, "sev_weight": 0, "early_count": 0,
             "late_count": 0, "actors": set(), "cross_border_count": 0}
        for st in NER_STATES_FULL
    }

    async for item in intelligence_col.find(
        countable_query(cutoff, {"state": {"$in": NER_STATES_FULL}}),
        {"published_at": 1, "severity": 1, "state": 1, "entities": 1,
         "is_cross_border": 1, "countries_involved": 1, "processed": 1,
         "tags": 1, "is_cluster_primary": 1, "_id": 0},
    ):
        try:
            state = _known_state(item)
            if not state or not is_countable_item(item):
                continue
            m = state_metrics[state]
            m["total"] += 1
            m["sev_weight"] += _SEV_WEIGHT[item["severity"]]

            pub = item.get("published_at") if isinstance(item.get("published_at"), str) else ""
            if pub and pub < early_end:
                m["early_count"] += 1
            if pub and pub >= late_start:
                m["late_count"] += 1

            m["actors"].update(_text_list(item, "organizations"))
            if is_cross_border_item(item):
                m["cross_border_count"] += 1
        except Exception as e:
            logger.warning("stability: skipped bad item: %s", e)

    days = hours / 24
    results = []
    for m in state_metrics.values():
        r = compute_stability(m, days)
        results.append({
            "state": m["state"],
            "stability_score": r["stability_score"],
            "concern_level": r["concern_level"],
            "metrics": {
                "total_items":   m["total"],
                "sev_weight":    m["sev_weight"],
                "early_count":   m["early_count"],
                "late_count":    m["late_count"],
                "velocity":      r["velocity"],
                "actor_count":   len(m["actors"]),
                "cross_border_share": r["cross_border_share"],
            },
        })

    # most concerning first; "No data" states last
    results.sort(key=lambda x: (x["stability_score"] is None, x["stability_score"] or 0))
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
    Border events count only items that pass the shared cross-border rule.
    """
    cutoff = _cutoff_iso(range)
    pairs = {
        "Myanmar":    ["Manipur", "Nagaland"],
        "Bangladesh": ["Assam", "Tripura", "Meghalaya"],
        "China":      ["Arunachal Pradesh", "Sikkim"],
    }
    border_daily: Dict[str, Dict[str, int]] = {b: defaultdict(int) for b in pairs}
    ner_daily:    Dict[str, Dict[str, int]] = {b: defaultdict(int) for b in pairs}

    # NER activity needs every relevant item in the pair's states; border events
    # need the cross-border rule. Fetch the union.
    ner_states_all = [s for v in pairs.values() for s in v]
    async for item in intelligence_col.find(
        countable_query(cutoff, {"$or": cross_border_query()["$or"] + [{"state": {"$in": ner_states_all}}]}),
        {"published_at": 1, "state": 1, "entities": 1, "is_cross_border": 1,
         "countries_involved": 1, "severity": 1, "processed": 1, "tags": 1,
         "is_cluster_primary": 1, "_id": 0},
    ):
        try:
            if not is_countable_item(item):
                continue
            pub = item.get("published_at")
            pub = pub[:10] if isinstance(pub, str) else ""
            if not pub:
                continue
            state = item.get("state") if isinstance(item.get("state"), str) else ""
            mentioned = set(_text_list(item, "locations")) | {state} | {
                c for c in (item.get("countries_involved") or []) if isinstance(c, str)}
            mentioned &= set(CROSS_BORDER_COUNTRIES)
            crosses = is_cross_border_item(item)

            for border, ner_states in pairs.items():
                if crosses and border in mentioned:
                    border_daily[border][pub] += 1
                if state in ner_states:
                    ner_daily[border][pub] += 1
        except Exception as e:
            logger.warning("trends cross-border: skipped bad item: %s", e)

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
            "total_border_events": sum(border_daily[border].values()),
            "data": merged,
        })

    return {"range": range, "series": series}
