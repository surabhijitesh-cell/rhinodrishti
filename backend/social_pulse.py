"""
Social Media Pulse for periodic briefs (daily/fortnightly/monthly).

Same averaging logic as GET /social/sentiment-pulse (routers/social_media.py),
but scoped to a date window instead of all-time — each brief should reflect
sentiment from its own period, not the whole corpus.
"""
from datetime import datetime, timezone

PLATFORM_SOURCE_TYPES = {
    "facebook":  "facebook_apify",
    "instagram": "instagram_apify",
    "twitter":   "twitter_apify",
    "youtube":   {"$regex": "^youtube"},
}


async def get_social_pulse_for_period(db, start_iso: str, end_iso: str) -> dict | None:
    """Returns {platforms: {name: {positive_pct, negative_pct, post_count}}, combined: {...}}
    or None if no platform has any scored posts in the window."""
    platforms = {}
    all_scores = []
    for platform, source_type in PLATFORM_SOURCE_TYPES.items():
        items = await db.intelligence_items.find(
            {
                "source_type": source_type,
                "comment_sentiment": {"$exists": True},
                "published_at": {"$gte": start_iso, "$lte": end_iso},
            },
            {"_id": 0, "comment_sentiment": 1},
        ).to_list(500)
        if not items:
            continue
        pos = round(sum(it["comment_sentiment"].get("positive_pct", 0) for it in items) / len(items))
        neg = round(sum(it["comment_sentiment"].get("negative_pct", 0) for it in items) / len(items))
        platforms[platform] = {"positive_pct": pos, "negative_pct": neg, "post_count": len(items)}
        all_scores.extend(items)

    if not all_scores:
        return None

    combined = {
        "positive_pct": round(sum(it["comment_sentiment"].get("positive_pct", 0) for it in all_scores) / len(all_scores)),
        "negative_pct": round(sum(it["comment_sentiment"].get("negative_pct", 0) for it in all_scores) / len(all_scores)),
        "post_count": len(all_scores),
    }
    return {"platforms": platforms, "combined": combined}
