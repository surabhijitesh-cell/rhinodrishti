"""
Feedback Bias Engine — Closes the loop between analyst ratings and AI classification.

Aggregates analyst feedback patterns (high-rated and low-rated content) and builds
a dynamic bias context that gets injected into the AI classification prompt.
This allows the system to learn from analyst corrections over time.

Settings (configurable via /api/settings/bias):
  - bias_window: "rolling_30" (default) or "all_time"
  - bias_influence: "light" (~10-15%), "moderate" (~20-25% default), "high" (~35-40%)
"""
import logging
from datetime import datetime, timezone, timedelta
from shared import feedback_col, intelligence_col, db

logger = logging.getLogger(__name__)

# Cache to avoid recomputing on every article
_bias_cache = {
    "data": None,
    "computed_at": None,
}
BIAS_CACHE_TTL_SECONDS = 300  # Recompute every 5 minutes

# Influence level configs
INFLUENCE_CONFIG = {
    "light": {
        "boost_range": "+3 to +5",
        "reduce_range": "-3 to -5",
        "pct_label": "~10-15%",
        "description": "Light influence — AI judgment dominates, feedback provides gentle nudges",
    },
    "moderate": {
        "boost_range": "+5 to +10",
        "reduce_range": "-5 to -10",
        "pct_label": "~20-25%",
        "description": "Moderate influence — noticeable impact from analyst corrections",
    },
    "high": {
        "boost_range": "+10 to +20",
        "reduce_range": "-10 to -20",
        "pct_label": "~35-40%",
        "description": "High influence — analyst consensus strongly shapes classification",
    },
}


async def _get_bias_settings() -> dict:
    """Read bias settings from DB. Returns defaults if not configured."""
    window_doc = await db.app_settings.find_one({"key": "bias_window"}, {"_id": 0})
    influence_doc = await db.app_settings.find_one({"key": "bias_influence"}, {"_id": 0})
    return {
        "window": window_doc.get("value", "rolling_30") if window_doc else "rolling_30",
        "influence": influence_doc.get("value", "moderate") if influence_doc else "moderate",
    }


async def get_feedback_bias_context() -> str:
    """Build a dynamic bias context string from analyst feedback patterns.

    Returns a string that can be appended to the classification prompt,
    or empty string if insufficient data.
    """
    now = datetime.now(timezone.utc)

    # Check cache
    if (_bias_cache["data"] is not None and
            _bias_cache["computed_at"] and
            (now - _bias_cache["computed_at"]).total_seconds() < BIAS_CACHE_TTL_SECONDS):
        return _bias_cache["data"]

    try:
        context = await _compute_bias_context()
        _bias_cache["data"] = context
        _bias_cache["computed_at"] = now
        return context
    except Exception as e:
        logger.error(f"Failed to compute feedback bias: {e}")
        return ""


async def get_feedback_bias_profile() -> dict:
    """Return the raw bias profile data for the API/UI."""
    return await _compute_bias_profile()


def invalidate_bias_cache():
    """Force recomputation on next call."""
    _bias_cache["data"] = None
    _bias_cache["computed_at"] = None


async def _compute_bias_profile() -> dict:
    """Compute the raw bias profile from feedback data."""
    settings = await _get_bias_settings()
    window_mode = settings["window"]
    influence = settings["influence"]

    # Build query based on window mode
    query = {}
    if window_mode == "rolling_30":
        window_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        query = {"timestamp": {"$gte": window_start}}
        window_label = "30 days"
    else:
        window_label = "all time"

    recent_feedback = await feedback_col.find(
        query,
        {"_id": 0, "intelligence_id": 1, "rating": 1, "derived_features": 1}
    ).to_list(10000)

    if len(recent_feedback) < 5:
        return {
            "status": "insufficient_data",
            "total_ratings": len(recent_feedback),
            "min_required": 5,
            "window_mode": window_mode,
            "window_label": window_label,
            "influence": influence,
            "upweight_regions": {},
            "upweight_threats": {},
            "downweight_regions": {},
            "downweight_threats": {},
            "upweight_actors": {},
        }

    # Group by intelligence_id to get per-item averages
    item_ratings = {}
    for fb in recent_feedback:
        iid = fb["intelligence_id"]
        if iid not in item_ratings:
            item_ratings[iid] = {"ratings": [], "features": fb.get("derived_features", {})}
        item_ratings[iid]["ratings"].append(fb["rating"])

    high_rated_features = []  # avg >= 4.5
    low_rated_features = []   # avg <= 2.5

    for data in item_ratings.values():
        avg = sum(data["ratings"]) / len(data["ratings"])
        features = data["features"]
        if avg >= 4.5:
            high_rated_features.append(features)
        elif avg <= 2.5:
            low_rated_features.append(features)

    # Aggregate features
    upweight_regions = {}
    upweight_threats = {}
    upweight_actors = {}
    for f in high_rated_features:
        r = f.get("region", "")
        if r:
            upweight_regions[r] = upweight_regions.get(r, 0) + 1
        tc = f.get("threat_category", "")
        if tc:
            upweight_threats[tc] = upweight_threats.get(tc, 0) + 1
        for a in (f.get("actors") or []):
            upweight_actors[a] = upweight_actors.get(a, 0) + 1

    downweight_regions = {}
    downweight_threats = {}
    for f in low_rated_features:
        r = f.get("region", "")
        if r:
            downweight_regions[r] = downweight_regions.get(r, 0) + 1
        tc = f.get("threat_category", "")
        if tc:
            downweight_threats[tc] = downweight_threats.get(tc, 0) + 1

    inf_conf = INFLUENCE_CONFIG.get(influence, INFLUENCE_CONFIG["moderate"])

    return {
        "status": "active",
        "total_ratings": len(recent_feedback),
        "unique_items": len(item_ratings),
        "high_rated_items": len(high_rated_features),
        "low_rated_items": len(low_rated_features),
        "window_mode": window_mode,
        "window_label": window_label,
        "influence": influence,
        "influence_pct": inf_conf["pct_label"],
        "influence_description": inf_conf["description"],
        "upweight_regions": dict(sorted(upweight_regions.items(), key=lambda x: -x[1])[:8]),
        "upweight_threats": dict(sorted(upweight_threats.items(), key=lambda x: -x[1])[:8]),
        "upweight_actors": dict(sorted(upweight_actors.items(), key=lambda x: -x[1])[:8]),
        "downweight_regions": dict(sorted(downweight_regions.items(), key=lambda x: -x[1])[:8]),
        "downweight_threats": dict(sorted(downweight_threats.items(), key=lambda x: -x[1])[:8]),
    }


async def _compute_bias_context() -> str:
    """Build the actual prompt injection string from the bias profile."""
    profile = await _compute_bias_profile()

    if profile["status"] != "active":
        return ""

    has_upweight = profile["upweight_regions"] or profile["upweight_threats"]
    has_downweight = profile["downweight_regions"] or profile["downweight_threats"]

    if not has_upweight and not has_downweight:
        return ""

    influence = profile.get("influence", "moderate")
    inf_conf = INFLUENCE_CONFIG.get(influence, INFLUENCE_CONFIG["moderate"])
    window_label = profile.get("window_label", "30 days")

    lines = [
        "",
        "--------------------------------------------------",
        f"ANALYST FEEDBACK CALIBRATION (DYNAMIC — {window_label.upper()})",
        "--------------------------------------------------",
        "",
        f"Based on {profile['total_ratings']} analyst ratings across {profile['unique_items']} articles:",
        "",
    ]

    if profile["upweight_regions"] or profile["upweight_threats"]:
        lines.append("UPWEIGHT (analysts consistently rate these as highly relevant):")
        if profile["upweight_regions"]:
            regions_str = ", ".join(f"{r} ({c} high ratings)" for r, c in profile["upweight_regions"].items())
            lines.append(f"  - Regions: {regions_str}")
            lines.append(f"  -> Boost priority_score by {inf_conf['boost_range']} for articles in these regions")
        if profile["upweight_threats"]:
            threats_str = ", ".join(f"{t} ({c} high ratings)" for t, c in profile["upweight_threats"].items())
            lines.append(f"  - Threat Categories: {threats_str}")
            lines.append(f"  -> Boost priority_score by {inf_conf['boost_range']} for articles matching these categories")
        if profile["upweight_actors"]:
            actors_str = ", ".join(f"{a} ({c})" for a, c in list(profile["upweight_actors"].items())[:5])
            lines.append(f"  - Key Actors: {actors_str}")
        lines.append("")

    if profile["downweight_regions"] or profile["downweight_threats"]:
        lines.append("DOWNWEIGHT (analysts consistently rate these as less relevant):")
        if profile["downweight_regions"]:
            regions_str = ", ".join(f"{r} ({c} low ratings)" for r, c in profile["downweight_regions"].items())
            lines.append(f"  - Regions: {regions_str}")
            lines.append(f"  -> Reduce priority_score by {inf_conf['reduce_range']} for articles in these regions")
        if profile["downweight_threats"]:
            threats_str = ", ".join(f"{t} ({c} low ratings)" for t, c in profile["downweight_threats"].items())
            lines.append(f"  - Threat Categories: {threats_str}")
            lines.append(f"  -> Reduce priority_score by {inf_conf['reduce_range']} for articles matching these categories")
        lines.append("")

    lines.append("NOTE: These calibrations reflect analyst consensus. Apply them as adjustments")
    lines.append("to your independent analysis — they should influence but not override your judgment.")
    lines.append(f"The adjustments should represent approximately {inf_conf['pct_label']} influence on the final score.")

    return "\n".join(lines)
