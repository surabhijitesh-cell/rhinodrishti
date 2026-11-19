"""Cross-Border Watch: Bangladesh & Myanmar intelligence with India-relevance scoring."""
import math
from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone, timedelta
from shared import db, intelligence_col, feedback_col, logger, has_non_latin_chars
from intel_rules import cross_border_query

router = APIRouter()

# Fetch this many candidates (best priority first) before classifying per country.
FETCH_CAP = 2000
HIDDEN_TAGS = ["not_relevant", "unprocessed", "stage0_filtered", "stage05_filtered", "stage1_filtered"]

# Geographic boost locations
GEO_BOOST_INDIA = {"moreh", "champhai", "agartala", "dawki", "sutarkandi", "karimganj", "silchar", "churachandpur"}
GEO_BOOST_BD = {"cox's bazar", "bandarban", "chittagong", "sylhet", "teknaf", "rangamati", "comilla", "brahmanbaria", "dhaka", "moulvibazar", "beanibazar", "bogura", "sherpur"}
GEO_BOOST_MM = {"chin state", "sagaing", "tamu", "rakhine", "kachin", "shan", "mandalay", "kalay", "hakha", "falam", "nay pyi taw", "yangon", "minbya"}

CATEGORY_ORDER = ["defence", "diplomatic", "internal_politics", "economics"]
CATEGORY_LABELS = {
    "diplomatic": "Diplomatic",
    "defence": "Defence",
    "internal_politics": "Internal Politics",
    "economics": "Economics",
}

# Keyword-based auto-categorization for items processed before prompt update
_CAT_KEYWORDS = {
    "diplomatic": {"bilateral", "delegation", "diplomat", "ambassador", "foreign affair", "foreign minister", "cooperation", "treaty", "mou signed", "visit", "invited", "summit", "relations"},
    "defence": {"military", "army", "bgb", "bsf", "coast guard", "seized", "arrested", "raid", "deployed", "platoon", "airstrike", "gunfight", "arms", "weapons", "heroin", "drug", "smuggl", "militant", "killed", "operation", "security force"},
    "internal_politics": {"parliament", "election", "minister", "government", "reform", "bill passed", "speaker", "opposition", "political", "protest", "arrest", "junta", "party", "ispr"},
    "economics": {"trade", "export", "import", "economy", "bank", "revenue", "inflation", "pmi", "gdp", "investment", "business", "infra", "logistics", "reserve", "remittance", "jetty", "port"},
}

# Indian states that border Bangladesh/Myanmar
INDIA_BORDER_STATES = {"manipur", "mizoram", "nagaland", "assam", "tripura", "meghalaya", "arunachal pradesh", "arunachal", "sikkim"}
BD_KEYWORDS = {"bangladesh", "dhaka", "bgb", "rohingya", "cox's bazar", "chittagong", "sylhet", "teknaf", "bandarban", "awami league", "bnp", "hasina", "yunus", "indo-bangladesh"}
MM_KEYWORDS = {"myanmar", "burma", "tatmadaw", "chin state", "sagaing", "rakhine", "kachin", "shan state", "tamu", "nscn", "kalay", "hakha", "min aung hlaing", "junta", "indo-myanmar", "chin hills"}


def _s(value) -> str:
    """Null-safe text."""
    return value if isinstance(value, str) else ""


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        return default
    return value


def _locations(item: dict) -> list:
    entities = item.get("entities")
    locs = entities.get("locations") if isinstance(entities, dict) else None
    return [l for l in _list(locs) if isinstance(l, str)]


def _auto_categorize(item):
    """Keyword-based fallback categorization for items without AI category."""
    cat = item.get("cross_border_category")
    if isinstance(cat, str) and cat in CATEGORY_LABELS:
        return cat
    text = (_s(item.get("title")) + " " + _s(item.get("ai_summary"))).lower()
    scores = {}
    for category, keywords in _CAT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return "other"

POSTURE_THRESHOLDS = {"deteriorating": 75, "elevated": 60, "watchful": 40, "stable": 0}


def _compute_posture(items: list) -> str:
    """Compute overall posture from items."""
    if not items:
        return "stable"
    avg_priority = sum(_num(i.get("priority_score"), 30) for i in items) / len(items)
    escalating = sum(1 for i in items if i.get("threat_trajectory") == "ESCALATING")
    escalation_ratio = escalating / len(items)

    score = avg_priority + (escalation_ratio * 20)
    for posture, threshold in POSTURE_THRESHOLDS.items():
        if score >= threshold:
            return posture
    return "stable"


def _compute_watchpoints(items: list) -> list:
    """Extract top watchpoints from cross-border items."""
    themes = {}
    for item in items:
        bucket = _s(item.get("signal_bucket"))
        if bucket:
            themes[bucket] = themes.get(bucket, 0) + 1
        ews = _s(item.get("early_warning_signal"))
        if ews and ews != "None identified":
            themes[ews[:80]] = themes.get(ews[:80], 0) + 1

    sorted_themes = sorted(themes.items(), key=lambda x: -x[1])
    return [t for t, _ in sorted_themes[:5]]


def _apply_geo_boost(item: dict) -> int:
    """Apply geographic relevance boost based on mentioned locations."""
    boost = 0
    locations = [loc.lower() for loc in _locations(item)]
    title_lower = (_s(item.get("title")) + " " + _s(item.get("ai_summary"))).lower()

    all_text = " ".join(locations) + " " + title_lower
    if any(loc in all_text for loc in GEO_BOOST_INDIA):
        boost += 3
    if any(loc in all_text for loc in GEO_BOOST_BD):
        boost += 2
    if any(loc in all_text for loc in GEO_BOOST_MM):
        boost += 2
    return boost


def _classify(item: dict) -> list:
    """Which country sections ('bangladesh' / 'myanmar') this item belongs to."""
    countries = [c.lower() for c in _list(item.get("countries_involved")) if isinstance(c, str)]
    state_val = _s(item.get("state")).lower()
    title_lower = _s(item.get("title")).lower()
    text_all = (title_lower + " " + _s(item.get("ai_summary")) + " " + _s(item.get("why_it_matters"))).lower()

    # RULE 1: state IS Bangladesh/Myanmar -> that section (primary origin)
    if state_val in ("bangladesh", "myanmar"):
        return [state_val]

    out = []
    # RULE 2: Indian border state items need the TITLE to name the target country
    if state_val in INDIA_BORDER_STATES:
        if "bangladesh" in countries and any(kw in title_lower for kw in BD_KEYWORDS):
            out.append("bangladesh")
        if "myanmar" in countries and any(kw in title_lower for kw in MM_KEYWORDS):
            out.append("myanmar")
        return out

    # RULE 3: other states (e.g. national-level news)
    if "bangladesh" in countries and any(kw in text_all for kw in BD_KEYWORDS):
        out.append("bangladesh")
    if "myanmar" in countries and any(kw in text_all for kw in MM_KEYWORDS):
        out.append("myanmar")
    return out


def _group_by_category(items):
    grouped = {}
    for item in items:
        cat = _auto_categorize(item)
        item["cross_border_category"] = cat  # Set for frontend display
        grouped.setdefault(cat if cat in CATEGORY_LABELS else "other", []).append(item)
    result = []
    for cat in CATEGORY_ORDER:
        if cat in grouped:
            result.append({"category": cat, "label": CATEGORY_LABELS[cat], "items": grouped[cat]})
    if "other" in grouped:
        result.append({"category": "other", "label": "Other", "items": grouped["other"]})
    return result


def build_watch_payload(all_items: list, limit: int) -> dict:
    """Classify candidates per country, sort, then apply `limit` PER COUNTRY.

    `count` is the true number of matching items for that country; `shown` is
    how many are returned. One bad record is logged and skipped.
    """
    seen_ids = set()
    buckets = {"bangladesh": [], "myanmar": []}

    for item in all_items or []:
        try:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            title_text, summary_text = _s(item.get("title")), _s(item.get("ai_summary"))
            if not summary_text:
                continue
            # Skip untranslated items (still in non-Latin script)
            if has_non_latin_chars(title_text) or has_non_latin_chars(summary_text):
                continue
            if _s(item.get("severity")).lower() == "low":
                continue

            targets = _classify(item)
            if not targets:
                continue

            geo_boost = _apply_geo_boost(item)
            item["geo_boost"] = geo_boost
            priority = _num(item.get("priority_score"))
            effective = priority + geo_boost
            fb_avg = item.get("feedback_avg_rating")
            fb_count = _num(item.get("feedback_total_ratings"))
            if _num(fb_avg) and fb_count > 0:
                effective += math.log(fb_count + 1) * (fb_avg - 3.5)
                item["feedback_boosted"] = True
            item["effective_priority"] = effective

            for target in targets:
                buckets[target].append(item)
        except Exception as e:  # one bad record must never fail the page
            logger.warning("cross-border: skipped bad item %r: %s", (item or {}).get("id") if isinstance(item, dict) else None, e)

    sections = {}
    shown_all = []
    for name, items in buckets.items():
        items.sort(key=lambda x: -_num(x.get("effective_priority")))
        true_count = len(items)
        shown = items[:limit]
        shown_all.extend(shown)
        sections[name] = {
            "items": shown,
            "grouped": _group_by_category(shown),
            "count": true_count,
            "shown": len(shown),
            "posture": _compute_posture(items),
        }

    bucket_dist = {}
    for item in shown_all:
        b = _s(item.get("signal_bucket"))
        if b:
            bucket_dist[b] = bucket_dist.get(b, 0) + 1

    return {
        "bangladesh": sections["bangladesh"],
        "myanmar": sections["myanmar"],
        "watchpoints": _compute_watchpoints(shown_all),
        "signal_distribution": dict(sorted(bucket_dist.items(), key=lambda x: -x[1])),
        "total": sections["bangladesh"]["count"] + sections["myanmar"]["count"],
    }


def build_watch_query(retention_cutoff: str, min_signal: Optional[str] = None) -> dict:
    query = {
        "processed": True,
        "ai_summary": {"$exists": True, "$ne": ""},
        "published_at": {"$gte": retention_cutoff},
        "severity": {"$nin": ["low", "LOW"]},
        "is_cluster_primary": {"$ne": False},
        "tags": {"$nin": HIDDEN_TAGS},
        **cross_border_query(),
    }
    if min_signal == "HIGH":
        query["signal_strength"] = "HIGH"
    elif min_signal == "MEDIUM":
        query["signal_strength"] = {"$in": ["HIGH", "MEDIUM"]}
    return query


@router.get("/cross-border/watch")
async def get_cross_border_watch(
    min_signal: Optional[str] = Query(None, description="Minimum signal strength: HIGH, MEDIUM"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get cross-border intelligence split by Bangladesh and Myanmar."""
    settings = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    retention_days = settings.get("value", 30) if settings else 30
    retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    PROJECTION = {
        "_id": 0, "id": 1, "title": 1, "ai_summary": 1, "why_it_matters": 1,
        "early_warning_signal": 1, "severity": 1, "priority_score": 1,
        "threat_trajectory": 1, "is_cross_border": 1, "countries_involved": 1,
        "state": 1, "regions": 1, "actors": 1, "entities": 1, "source": 1,
        "source_url": 1, "published_at": 1, "tags": 1, "special_flags": 1,
        "india_relevance_score": 1, "signal_bucket": 1, "signal_strength": 1,
        "threat_category": 1, "cross_border_category": 1,
        "feedback_avg_rating": 1, "feedback_total_ratings": 1,
    }

    all_items = await intelligence_col.find(
        build_watch_query(retention_cutoff, min_signal), PROJECTION
    ).sort("priority_score", -1).limit(FETCH_CAP).to_list(FETCH_CAP)
    if len(all_items) >= FETCH_CAP:
        logger.warning("cross-border watch hit the %d-item fetch cap; lowest-priority items not considered", FETCH_CAP)

    return build_watch_payload(all_items, limit)
