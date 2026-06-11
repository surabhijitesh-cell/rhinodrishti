"""
Pattern Detection Engine for Rhino Drishti.

Detects recurring intelligence patterns using a sliding window approach:
- Tracks entity/region/threat co-occurrences over time
- Flags patterns when >=3 similar events occur within a configurable window
- Generates escalation warnings for accelerating patterns
"""
import logging
from datetime import datetime, timezone, timedelta
from collections import Counter

logger = logging.getLogger(__name__)

# Pattern detection thresholds
MIN_EVENTS_FOR_PATTERN = 3
WINDOW_DAYS = 7
ESCALATION_THRESHOLD = 5  # >=5 events = escalation warning


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


async def detect_patterns(db, window_days: int = WINDOW_DAYS) -> list:
    """
    Analyze recent intelligence items for recurring patterns.
    Returns list of detected patterns.
    """
    patterns_col = db.intelligence_patterns
    items_col = db.intelligence_items

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    # Get recent processed items
    recent_items = await items_col.find(
        {"processed": True, "published_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "title": 1, "state": 1, "threat_category": 1,
         "tags": 1, "actors": 1, "regions": 1, "is_cross_border": 1,
         "countries_involved": 1, "severity": 1, "published_at": 1,
         "priority_score": 1, "source": 1}
    ).sort("published_at", -1).to_list(500)

    # If too few items in window, expand to last 30 days
    if len(recent_items) < MIN_EVENTS_FOR_PATTERN:
        expanded_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent_items = await items_col.find(
            {"processed": True, "published_at": {"$gte": expanded_cutoff}},
            {"_id": 0, "id": 1, "title": 1, "state": 1, "threat_category": 1,
             "tags": 1, "actors": 1, "regions": 1, "is_cross_border": 1,
             "countries_involved": 1, "severity": 1, "published_at": 1,
             "priority_score": 1, "source": 1}
        ).sort("published_at", -1).to_list(500)
        window_days = 30
        logger.info(f"Pattern Engine: Expanded window to 30 days ({len(recent_items)} items)")

    if len(recent_items) < MIN_EVENTS_FOR_PATTERN:
        return []

    # Group items by pattern keys
    pattern_groups = {}
    for item in recent_items:
        keys = extract_pattern_keys(item)
        for key in keys:
            if key not in pattern_groups:
                pattern_groups[key] = []
            pattern_groups[key].append(item)

    # Detect patterns (>=3 events with same key)
    detected = []
    for key, items in pattern_groups.items():
        if len(items) < MIN_EVENTS_FOR_PATTERN:
            continue

        parts = key.split(":")
        pattern_type = parts[0]
        region = parts[1] if len(parts) > 1 else ""
        detail = parts[2] if len(parts) > 2 else ""

        # Calculate severity distribution
        severities = Counter(i.get("severity", "low") for i in items)
        avg_priority = sum(i.get("priority_score", 0) for i in items) / len(items)

        # Determine escalation risk
        escalation_risk = "LOW"
        if len(items) >= ESCALATION_THRESHOLD:
            escalation_risk = "HIGH"
        elif len(items) >= MIN_EVENTS_FOR_PATTERN + 1:
            escalation_risk = "MODERATE"
        if severities.get("critical", 0) >= 2:
            escalation_risk = "CRITICAL"

        # Build trend summary
        sources = list(set(i.get("source", "") for i in items))
        titles = [i.get("title", "") for i in items[:5]]

        pattern = {
            "pattern_key": key,
            "pattern_type": pattern_type,
            "region": region,
            "detail": detail,
            "event_count": len(items),
            "window_days": window_days,
            "avg_priority_score": round(avg_priority, 1),
            "severity_breakdown": dict(severities),
            "escalation_risk": escalation_risk,
            "sources": sources[:5],
            "sample_titles": titles,
            "first_event": items[-1].get("published_at", ""),
            "latest_event": items[0].get("published_at", ""),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        detected.append(pattern)

    # Priority geo: Bangladesh actors/border + NE states float to the top
    # within their escalation tier (same risk level, priority geo comes first).
    PRIORITY_REGIONS = {"assam", "meghalaya", "tripura", "mizoram", "west bengal", "north bengal"}
    PRIORITY_TERMS = {"bangladesh", "north bengal", "bgb", "border", "indo-bangladesh"}

    def _geo_priority(p: dict) -> int:
        region = (p.get("region") or "").lower()
        detail = (p.get("detail") or "").lower()
        key = (p.get("pattern_key") or "").lower()
        if region in PRIORITY_REGIONS:
            return 0
        if any(t in detail or t in key for t in PRIORITY_TERMS):
            return 0
        return 1

    risk_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    detected.sort(key=lambda p: (risk_order.get(p["escalation_risk"], 4), _geo_priority(p), -p["event_count"]))

    # Store patterns in DB
    if detected:
        await patterns_col.delete_many({})  # Replace old patterns
        for p in detected:
            await patterns_col.insert_one(p)
        logger.info(f"Pattern Engine: Detected {len(detected)} patterns ({sum(1 for p in detected if p['escalation_risk'] in ('CRITICAL', 'HIGH'))} high/critical)")

    return detected
