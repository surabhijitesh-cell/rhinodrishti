"""Cross-Border Watch: Bangladesh & Myanmar intelligence with India-relevance scoring."""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone, timedelta
from shared import db, intelligence_col, logger

router = APIRouter()

# Geographic boost locations
GEO_BOOST_INDIA = {"moreh", "champhai", "agartala", "dawki", "sutarkandi", "karimganj", "silchar", "churachandpur"}
GEO_BOOST_BD = {"cox's bazar", "bandarban", "chittagong", "sylhet", "teknaf", "rangamati", "comilla", "brahmanbaria", "dhaka"}
GEO_BOOST_MM = {"chin state", "sagaing", "tamu", "rakhine", "kachin", "shan", "mandalay", "kalay", "hakha", "falam"}

POSTURE_THRESHOLDS = {"deteriorating": 75, "elevated": 60, "watchful": 40, "stable": 0}


def _compute_posture(items: list) -> str:
    """Compute overall posture from items."""
    if not items:
        return "stable"
    avg_priority = sum(i.get("priority_score", 30) for i in items) / len(items)
    escalating = sum(1 for i in items if i.get("threat_trajectory") == "ESCALATING")
    escalation_ratio = escalating / len(items) if items else 0

    score = avg_priority + (escalation_ratio * 20)
    for posture, threshold in POSTURE_THRESHOLDS.items():
        if score >= threshold:
            return posture
    return "stable"


def _compute_watchpoints(items: list) -> list:
    """Extract top watchpoints from cross-border items."""
    themes = {}
    for item in items:
        bucket = item.get("signal_bucket", "")
        if bucket:
            themes[bucket] = themes.get(bucket, 0) + 1
        ews = item.get("early_warning_signal", "")
        if ews and ews != "None identified":
            themes[ews[:80]] = themes.get(ews[:80], 0) + 1

    sorted_themes = sorted(themes.items(), key=lambda x: -x[1])
    return [t for t, _ in sorted_themes[:5]]


def _apply_geo_boost(item: dict) -> int:
    """Apply geographic relevance boost based on mentioned locations."""
    boost = 0
    locations = [loc.lower() for loc in (item.get("entities", {}).get("locations", []) or [])]
    title_lower = (item.get("title", "") + " " + item.get("ai_summary", "")).lower()

    all_text = " ".join(locations) + " " + title_lower
    if any(loc in all_text for loc in GEO_BOOST_INDIA):
        boost += 3
    if any(loc in all_text for loc in GEO_BOOST_BD):
        boost += 2
    if any(loc in all_text for loc in GEO_BOOST_MM):
        boost += 2
    return boost


@router.get("/cross-border/watch")
async def get_cross_border_watch(
    min_signal: Optional[str] = Query(None, description="Minimum signal strength: HIGH, MEDIUM"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get cross-border intelligence split by Bangladesh and Myanmar."""
    settings = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    retention_days = settings.get("value", 30) if settings else 30
    retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    base_query = {
        "processed": True,
        "ai_summary": {"$exists": True, "$ne": ""},
        "published_at": {"$gte": retention_cutoff},
        "$or": [
            {"is_cross_border": True},
            {"countries_involved": {"$elemMatch": {"$in": ["Bangladesh", "Myanmar"]}}},
            {"state": {"$in": ["Bangladesh", "Myanmar"]}},
        ]
    }

    if min_signal:
        if min_signal == "HIGH":
            base_query["signal_strength"] = "HIGH"
        elif min_signal == "MEDIUM":
            base_query["signal_strength"] = {"$in": ["HIGH", "MEDIUM"]}

    PROJECTION = {
        "_id": 0, "id": 1, "title": 1, "ai_summary": 1, "why_it_matters": 1,
        "early_warning_signal": 1, "severity": 1, "priority_score": 1,
        "threat_trajectory": 1, "is_cross_border": 1, "countries_involved": 1,
        "state": 1, "regions": 1, "actors": 1, "entities": 1, "source": 1,
        "source_url": 1, "published_at": 1, "tags": 1, "special_flags": 1,
        "india_relevance_score": 1, "signal_bucket": 1, "signal_strength": 1,
        "threat_category": 1,
    }

    all_items = await intelligence_col.find(base_query, PROJECTION).sort("priority_score", -1).limit(limit * 3).to_list(limit * 3)

    # Indian states that border Bangladesh/Myanmar
    INDIA_BORDER_STATES = {"manipur", "mizoram", "nagaland", "assam", "tripura", "meghalaya", "arunachal pradesh", "arunachal", "sikkim"}
    BD_KEYWORDS = {"bangladesh", "dhaka", "bgb", "rohingya", "cox's bazar", "chittagong", "sylhet", "teknaf", "bandarban", "awami league", "bnp", "hasina", "yunus", "indo-bangladesh"}
    MM_KEYWORDS = {"myanmar", "burma", "tatmadaw", "chin state", "sagaing", "rakhine", "kachin", "shan state", "tamu", "nscn", "kalay", "hakha", "min aung hlaing", "junta", "indo-myanmar", "chin hills"}

    # Strict classification
    seen_ids = set()
    bangladesh_items = []
    myanmar_items = []

    for item in all_items:
        item_id = item.get("id", "")
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        if not item.get("ai_summary"):
            continue

        geo_boost = _apply_geo_boost(item)
        item["geo_boost"] = geo_boost
        item["effective_priority"] = item.get("priority_score", 0) + geo_boost

        countries = [c.lower() for c in (item.get("countries_involved", []) or [])]
        state_val = (item.get("state", "") or "").lower()
        title_lower = (item.get("title", "") or "").lower()
        text_all = (title_lower + " " + (item.get("ai_summary", "") or "") + " " + (item.get("why_it_matters", "") or "")).lower()

        # RULE 1: If state IS Bangladesh/Myanmar → goes to that section (primary origin)
        if state_val == "bangladesh":
            bangladesh_items.append(item)
            continue
        if state_val == "myanmar":
            myanmar_items.append(item)
            continue

        # RULE 2: Indian border state items — require STRONG evidence of target country focus
        if state_val in INDIA_BORDER_STATES:
            # Only include if the TITLE explicitly mentions the target country or its keywords
            title_has_bd = any(kw in title_lower for kw in BD_KEYWORDS)
            title_has_mm = any(kw in title_lower for kw in MM_KEYWORDS)

            if title_has_bd and "bangladesh" in countries:
                bangladesh_items.append(item)
            if title_has_mm and "myanmar" in countries:
                myanmar_items.append(item)
            # If title doesn't mention target country by name, skip — it's Indian domestic news
            continue

        # RULE 3: Other states (e.g., national-level news)
        if "bangladesh" in countries and any(kw in text_all for kw in BD_KEYWORDS):
            bangladesh_items.append(item)
        if "myanmar" in countries and any(kw in text_all for kw in MM_KEYWORDS):
            myanmar_items.append(item)

    # Sort by effective priority
    bangladesh_items.sort(key=lambda x: -x.get("effective_priority", 0))
    myanmar_items.sort(key=lambda x: -x.get("effective_priority", 0))

    # Trim to limit
    bangladesh_items = bangladesh_items[:limit]
    myanmar_items = myanmar_items[:limit]

    # Compute posture
    bd_posture = _compute_posture(bangladesh_items)
    mm_posture = _compute_posture(myanmar_items)

    # Watchpoints
    all_watch = bangladesh_items + myanmar_items
    watchpoints = _compute_watchpoints(all_watch)

    # Signal bucket distribution
    bucket_dist = {}
    for item in all_watch:
        b = item.get("signal_bucket", "")
        if b:
            bucket_dist[b] = bucket_dist.get(b, 0) + 1

    return {
        "bangladesh": {
            "items": bangladesh_items,
            "count": len(bangladesh_items),
            "posture": bd_posture,
        },
        "myanmar": {
            "items": myanmar_items,
            "count": len(myanmar_items),
            "posture": mm_posture,
        },
        "watchpoints": watchpoints,
        "signal_distribution": dict(sorted(bucket_dist.items(), key=lambda x: -x[1])),
        "total": len(bangladesh_items) + len(myanmar_items),
    }
