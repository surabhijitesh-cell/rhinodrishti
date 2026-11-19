"""
Pattern Detection Engine for Rhino Drishti.

Detects recurring intelligence patterns using a sliding window approach:
- Tracks entity/region/threat co-occurrences over time
- Flags patterns when >=3 similar events occur within a configurable window
- Generates escalation warnings for accelerating patterns
"""
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from collections import Counter

logger = logging.getLogger(__name__)

# Pattern detection thresholds
MIN_EVENTS_FOR_PATTERN = 3
WINDOW_DAYS = 7
ESCALATION_THRESHOLD = 5  # >=5 distinct stories = escalation warning
MAX_ITEMS = 20000  # safety cap on items analysed per run; logged when hit
_PROJECTION = {"_id": 0, "id": 1, "title": 1, "state": 1, "threat_category": 1,
               "tags": 1, "actors": 1, "regions": 1, "is_cross_border": 1,
               "countries_involved": 1, "severity": 1, "published_at": 1,
               "priority_score": 1, "source": 1, "cluster_id": 1, "is_cluster_primary": 1}


def story_key(item: dict) -> str:
    """Identity of a story: its fusion cluster, else the normalised title."""
    cid = item.get("cluster_id")
    if cid:
        return f"c:{cid}"
    title = re.sub(r"\W+", " ", (item.get("title") or "").lower()).strip()
    return f"t:{title}" if title else f"i:{item.get('id', id(item))}"


def distinct_stories(items: list) -> list:
    """One item per story (newest first order kept); non-primary cluster copies are dropped."""
    seen = {}
    for it in items:
        if it.get("is_cluster_primary") is False:
            continue
        seen.setdefault(story_key(it), it)
    return list(seen.values())


def extract_pattern_keys(item: dict) -> list:
    """Extract pattern grouping keys from an intelligence item."""
    keys = []
    state = item.get("state", "")
    threat = item.get("threat_category", "")
    tags = item.get("tags", [])
    actors = item.get("actors", [])

    # Region + Threat combo
    if state and threat:
        keys.append(f"region_threat:{state}:{threat}")

    # Region + Actor combo
    if isinstance(actors, list):
        for actor in actors[:3]:
            if state:
                keys.append(f"region_actor:{state}:{actor}")

    # Tag-based patterns
    if isinstance(tags, list):
        for tag in tags[:3]:
            if state:
                keys.append(f"region_tag:{state}:{tag}")

    # Cross-border patterns
    if item.get("is_cross_border"):
        countries = item.get("countries_involved", [])
        if isinstance(countries, list):
            for c in countries:
                keys.append(f"crossborder:{c}")

    return keys


async def _load_window(items_col, days: int) -> tuple:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items = await items_col.find(
        {"processed": True, "published_at": {"$gte": cutoff}, "is_cluster_primary": {"$ne": False}},
        _PROJECTION,
    ).sort("published_at", -1).to_list(MAX_ITEMS + 1)
    capped = len(items) > MAX_ITEMS
    if capped:
        logger.warning(f"Pattern Engine: hit the {MAX_ITEMS}-item cap on a {days}-day window; oldest items skipped")
        items = items[:MAX_ITEMS]
    return items, capped


def _geo_priority(p: dict) -> int:
    # Bangladesh actors/border + NE states float to the top within their risk tier.
    region = (p.get("region") or "").lower()
    detail = (p.get("detail") or "").lower()
    key = (p.get("pattern_key") or "").lower()
    if region in {"assam", "meghalaya", "tripura", "mizoram", "west bengal", "north bengal"}:
        return 0
    if any(t in detail or t in key for t in {"bangladesh", "north bengal", "bgb", "border", "indo-bangladesh"}):
        return 0
    return 1


def build_patterns(recent_items: list, window_days: int) -> list:
    """Pure pattern computation; every count is of distinct stories."""
    pattern_groups = {}
    for item in recent_items:
        for key in extract_pattern_keys(item):
            pattern_groups.setdefault(key, []).append(item)

    now_iso = datetime.now(timezone.utc).isoformat()
    detected = []
    for key, group in pattern_groups.items():
        items = distinct_stories(group)
        if len(items) < MIN_EVENTS_FOR_PATTERN:
            continue

        parts = key.split(":")
        severities = Counter(i.get("severity", "low") for i in items)
        avg_priority = sum(i.get("priority_score", 0) or 0 for i in items) / len(items)

        escalation_risk = "LOW"
        if len(items) >= ESCALATION_THRESHOLD:
            escalation_risk = "HIGH"
        elif len(items) >= MIN_EVENTS_FOR_PATTERN + 1:
            escalation_risk = "MODERATE"
        if severities.get("critical", 0) >= 2:
            escalation_risk = "CRITICAL"

        detected.append({
            "pattern_key": key,
            "pattern_type": parts[0],
            "region": parts[1] if len(parts) > 1 else "",
            "detail": parts[2] if len(parts) > 2 else "",
            "event_count": len(items),
            "window_days": window_days,
            "avg_priority_score": round(avg_priority, 1),
            "severity_breakdown": dict(severities),
            "escalation_risk": escalation_risk,
            "sources": list(set(i.get("source", "") for i in items))[:5],
            "sample_titles": [i.get("title", "") for i in items[:5]],
            "first_event": items[-1].get("published_at", ""),
            "latest_event": items[0].get("published_at", ""),
            "detected_at": now_iso,
        })

    risk_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    detected.sort(key=lambda p: (risk_order.get(p["escalation_risk"], 4), _geo_priority(p), -p["event_count"]))
    return detected


async def _replace_patterns(db, detected: list, window_days: int, capped: bool) -> None:
    """Insert the new set first, then remove older rows; on failure keep the old set."""
    patterns_col = db.intelligence_patterns
    run_id = uuid.uuid4().hex
    try:
        if detected:
            await patterns_col.insert_many([{**p, "run_id": run_id} for p in detected])
    except Exception:
        logger.exception("Pattern Engine: saving failed; keeping previous patterns")
        try:
            await patterns_col.delete_many({"run_id": run_id})
        except Exception:
            logger.exception("Pattern Engine: could not remove partial new patterns")
        raise
    # Zero patterns on a successful run clears stale ones ($ne also matches rows without run_id).
    await patterns_col.delete_many({"run_id": {"$ne": run_id}})
    await db.app_settings.update_one(
        {"key": "patterns_last_run"},
        {"$set": {"ran_at": datetime.now(timezone.utc).isoformat(), "pattern_count": len(detected),
                  "window_days": window_days, "capped": capped, "run_id": run_id}},
        upsert=True,
    )


async def detect_patterns(db, window_days: int = WINDOW_DAYS) -> list:
    """
    Analyze the full configured window for recurring patterns (distinct stories).
    Returns list of detected patterns. A failure raises and leaves old patterns.
    """
    items_col = db.intelligence_items
    recent_items, capped = await _load_window(items_col, window_days)

    # If too few stories in window, expand to last 30 days
    if len(distinct_stories(recent_items)) < MIN_EVENTS_FOR_PATTERN:
        recent_items, capped = await _load_window(items_col, 30)
        window_days = 30
        logger.info(f"Pattern Engine: Expanded window to 30 days ({len(recent_items)} items)")

    detected = build_patterns(recent_items, window_days)
    await _replace_patterns(db, detected, window_days, capped)
    logger.info(f"Pattern Engine: Detected {len(detected)} patterns ({sum(1 for p in detected if p['escalation_risk'] in ('CRITICAL', 'HIGH'))} high/critical) from {len(recent_items)} items")
    return detected
