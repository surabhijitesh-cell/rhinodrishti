"""
Feedback Bias Engine — Closes the loop between analyst ratings and AI classification.

Aggregates analyst feedback patterns (high-rated and low-rated content) and builds
a dynamic bias context that gets injected into the AI classification prompt.
This allows the system to learn from analyst corrections over time.

Uses a rolling 30-day window with moderate influence (~20-25% weight).
"""
import logging
from datetime import datetime, timezone, timedelta
from shared import feedback_col, intelligence_col

logger = logging.getLogger(__name__)

# Cache to avoid recomputing on every article
_bias_cache = {
    "data": None,
    "computed_at": None,
}
BIAS_CACHE_TTL_SECONDS = 300  # Recompute every 5 minutes


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
    window_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Get all feedback from the last 30 days
    recent_feedback = await feedback_col.find(
        {"timestamp": {"$gte": window_start}},
        {"_id": 0, "intelligence_id": 1, "rating": 1, "derived_features": 1}
    ).to_list(5000)

    if len(recent_feedback) < 5:
        return {
            "status": "insufficient_data",
            "total_ratings": len(recent_feedback),
            "min_required": 5,
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

    # Compute per-item averages
    high_rated_features = []  # avg >= 4.5
    low_rated_features = []   # avg <= 2.5

    for iid, data in item_ratings.items():
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

    return {
        "status": "active",
        "total_ratings": len(recent_feedback),
        "unique_items": len(item_ratings),
        "high_rated_items": len(high_rated_features),
        "low_rated_items": len(low_rated_features),
        "window_days": 30,
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

    # Only inject if we have meaningful signal
    has_upweight = profile["upweight_regions"] or profile["upweight_threats"]
    has_downweight = profile["downweight_regions"] or profile["downweight_threats"]

    if not has_upweight and not has_downweight:
        return ""

    lines = [
        "",
        "--------------------------------------------------",
        "ANALYST FEEDBACK CALIBRATION (DYNAMIC — LAST 30 DAYS)",
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
            lines.append("  → Boost priority_score by +5 to +10 for articles in these regions")
        if profile["upweight_threats"]:
            threats_str = ", ".join(f"{t} ({c} high ratings)" for t, c in profile["upweight_threats"].items())
            lines.append(f"  - Threat Categories: {threats_str}")
            lines.append("  → Boost priority_score by +5 to +10 for articles matching these categories")
        if profile["upweight_actors"]:
            actors_str = ", ".join(f"{a} ({c})" for a, c in list(profile["upweight_actors"].items())[:5])
            lines.append(f"  - Key Actors: {actors_str}")
        lines.append("")

    if profile["downweight_regions"] or profile["downweight_threats"]:
        lines.append("DOWNWEIGHT (analysts consistently rate these as less relevant):")
        if profile["downweight_regions"]:
            regions_str = ", ".join(f"{r} ({c} low ratings)" for r, c in profile["downweight_regions"].items())
            lines.append(f"  - Regions: {regions_str}")
            lines.append("  → Reduce priority_score by -5 to -10 for articles in these regions")
        if profile["downweight_threats"]:
            threats_str = ", ".join(f"{t} ({c} low ratings)" for t, c in profile["downweight_threats"].items())
            lines.append(f"  - Threat Categories: {threats_str}")
            lines.append("  → Reduce priority_score by -5 to -10 for articles matching these categories")
        lines.append("")

    lines.append("NOTE: These calibrations reflect analyst consensus. Apply them as adjustments")
    lines.append("to your independent analysis — they should influence but not override your judgment.")
    lines.append("The adjustments should represent approximately 20-25% influence on the final score.")

    return "\n".join(lines)
