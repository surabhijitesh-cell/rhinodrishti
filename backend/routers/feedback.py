"""Feedback endpoints: submit/update ratings, aggregation, training profile."""
from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks, Depends
from typing import Optional
from datetime import datetime, timezone, timedelta
import math
import uuid
import os
from shared import db, feedback_col, intelligence_col, activity_log_col, logger
from feedback_bias import get_feedback_bias_profile, invalidate_bias_cache
from utils.auth import get_current_user_optional
from utils.roles import require_analyst_or_admin
from user_activity import log_action

router = APIRouter()

RATING_LABELS = {
    1: "Entirely Irrelevant",
    2: "Mostly Irrelevant",
    3: "Slightly Relevant",
    4: "Moderately Relevant",
    5: "Highly Relevant",
    6: "Extremely Relevant",
}


def _derive_relevance(avg: float) -> str:
    if avg >= 5.0:
        return "CRITICAL"
    if avg >= 4.0:
        return "HIGH"
    if avg >= 3.0:
        return "MODERATE"
    return "LOW"


# ============================================================
# Submit / Update a Rating
# ============================================================
def _user_filter(user: dict, intelligence_id: str) -> dict:
    return {"intelligence_id": intelligence_id, "user_id": user["id"]}


def _legacy_device_filter(intelligence_id: str, device_id) -> dict | None:
    """Old ratings were keyed by browser device id and carry no user_id."""
    if not device_id:
        return None
    return {"intelligence_id": intelligence_id, "device_id": device_id, "user_id": {"$exists": False}}


@router.post("/feedback")
async def submit_feedback(
    body: dict, request: Request, background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_analyst_or_admin),
):
    """One rating per logged-in analyst per item; re-rating updates it.
    Rating costs no AI calls and creates no activity sessions."""
    intelligence_id = body.get("intelligence_id")
    device_id = body.get("device_id")  # optional, only used to find an old pre-login rating
    rating = body.get("rating")

    if not intelligence_id:
        raise HTTPException(status_code=400, detail="intelligence_id is required")
    if not isinstance(rating, int) or isinstance(rating, bool) or rating < 1 or rating > 6:
        raise HTTPException(status_code=400, detail="rating must be integer 1-6")

    item = await intelligence_col.find_one({"id": intelligence_id}, {"_id": 0, "id": 1, "state": 1, "threat_category": 1, "actors": 1, "tags": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    settings = await db.app_settings.find_one({"key": "max_feedback_per_item"}, {"_id": 0})
    max_limit = settings.get("value", 20) if settings else 20

    now = datetime.now(timezone.utc).isoformat()
    who = {"user_id": current_user["id"], "username": current_user.get("username", "")}

    existing = await feedback_col.find_one(_user_filter(current_user, intelligence_id), {"_id": 0})
    if not existing:
        # Old device-based rating from this browser: adopt it instead of counting twice.
        # shortcut: a shared browser could adopt a colleague's old rating; acceptable for legacy rows.
        legacy_filter = _legacy_device_filter(intelligence_id, device_id)
        if legacy_filter and await feedback_col.find_one(legacy_filter, {"_id": 0, "id": 1}):
            await feedback_col.update_one(legacy_filter, {"$set": {**who, "rating": rating, "updated_at": now}})
            existing = True

    if existing:
        if existing is not True:
            await feedback_col.update_one(
                _user_filter(current_user, intelligence_id),
                {"$set": {"rating": rating, "updated_at": now}},
            )
        await _update_aggregation(intelligence_id)
        invalidate_bias_cache()
        background_tasks.add_task(
            log_action, current_user, "relevance_rating",
            f"rating={rating} on item {intelligence_id} (updated)",
        )
        return {"message": "Rating updated", "action": "updated", "rating": rating}

    current_count = await feedback_col.count_documents({"intelligence_id": intelligence_id})
    if current_count >= max_limit:
        raise HTTPException(status_code=429, detail=f"Maximum feedback limit ({max_limit}) reached for this item")

    derived = {
        "region": item.get("state", ""),
        "threat_category": item.get("threat_category", ""),
        "actors": item.get("actors", []),
        "keywords": item.get("tags", []),
    }
    doc = {
        "id": str(uuid.uuid4()),
        "intelligence_id": intelligence_id,
        "device_id": device_id,
        **who,
        "rating": rating,
        "timestamp": now,
        "updated_at": now,
        "ip_address": request.client.host if request.client else "",
        "derived_features": derived,
    }
    await feedback_col.insert_one(doc)
    await _update_aggregation(intelligence_id)
    invalidate_bias_cache()
    background_tasks.add_task(
        log_action, current_user, "relevance_rating",
        f"rating={rating} on item {intelligence_id}",
    )
    return {"message": "Rating submitted", "action": "created", "rating": rating}


async def _find_user_rating(user, intelligence_id: str, device_id=None):
    """The caller's own rating: by user id first, then an old device-based row."""
    if user:
        row = await feedback_col.find_one(_user_filter(user, intelligence_id), {"_id": 0, "rating": 1})
        if row:
            return row["rating"]
    legacy = _legacy_device_filter(intelligence_id, device_id)
    if legacy:
        row = await feedback_col.find_one(legacy, {"_id": 0, "rating": 1})
        if row:
            return row["rating"]
    return None


# ============================================================
# Batch Feedback Status (for feed pages)
# NOTE: Static routes MUST come before {intelligence_id} path
# ============================================================
@router.post("/feedback/batch")
async def get_batch_feedback(body: dict, current_user: Optional[dict] = Depends(get_current_user_optional)):
    item_ids = body.get("item_ids", [])
    device_id = body.get("device_id", "")

    if not item_ids or len(item_ids) > 50:
        raise HTTPException(status_code=400, detail="item_ids required (max 50)")

    settings = await db.app_settings.find_one({"key": "max_feedback_per_item"}, {"_id": 0})
    max_limit = settings.get("value", 20) if settings else 20

    # Aggregate counts and averages
    pipeline = [
        {"$match": {"intelligence_id": {"$in": item_ids}}},
        {"$group": {
            "_id": "$intelligence_id",
            "total": {"$sum": 1},
            "avg_rating": {"$avg": "$rating"},
        }}
    ]
    agg_map = {}
    async for doc in feedback_col.aggregate(pipeline):
        agg_map[doc["_id"]] = {
            "total_ratings": doc["total"],
            "avg_rating": round(doc["avg_rating"], 2),
            "limit_reached": doc["total"] >= max_limit,
            "max_limit": max_limit,
        }

    # Fetch user's own ratings for these items
    user_ratings = {}
    if device_id:  # old device-based ratings (lowest priority)
        async for doc in feedback_col.find(
            {"intelligence_id": {"$in": item_ids}, "device_id": device_id, "user_id": {"$exists": False}},
            {"_id": 0, "intelligence_id": 1, "rating": 1}
        ):
            user_ratings[doc["intelligence_id"]] = doc["rating"]
    if current_user:
        async for doc in feedback_col.find(
            {"intelligence_id": {"$in": item_ids}, "user_id": current_user["id"]},
            {"_id": 0, "intelligence_id": 1, "rating": 1}
        ):
            user_ratings[doc["intelligence_id"]] = doc["rating"]

    result = {}
    for iid in item_ids:
        info = agg_map.get(iid, {"total_ratings": 0, "avg_rating": 0, "limit_reached": False, "max_limit": max_limit})
        info["user_rating"] = user_ratings.get(iid)
        result[iid] = info

    return {"feedback": result}


# ============================================================
# Training Profile (Aggregated Intelligence)
# ============================================================
@router.get("/feedback/training-profile")
async def get_training_profile():
    total_feedback = await feedback_col.count_documents({})
    unique_items = len(await feedback_col.distinct("intelligence_id"))

    if total_feedback == 0:
        return {
            "total_feedback": 0,
            "unique_items_rated": 0,
            "positive_weights": {},
            "negative_weights": {},
            "high_rated_regions": [],
            "low_rated_categories": [],
            "confidence_level": "INSUFFICIENT_DATA",
            "noise_patterns": [],
            "preferred_categories": [],
        }

    # HIGH-RATED analysis (avg >= 4.0)
    high_pipeline = [
        {"$group": {
            "_id": "$intelligence_id",
            "avg": {"$avg": "$rating"},
            "count": {"$sum": 1},
        }},
        {"$match": {"avg": {"$gte": 4.0}, "count": {"$gte": 2}}},
    ]
    high_ids = []
    async for doc in feedback_col.aggregate(high_pipeline):
        high_ids.append(doc["_id"])

    positive_regions = {}
    positive_threats = {}
    positive_actors = {}
    if high_ids:
        async for item in intelligence_col.find(
            {"id": {"$in": high_ids}},
            {"_id": 0, "state": 1, "threat_category": 1, "actors": 1, "tags": 1}
        ):
            r = item.get("state", "")
            if r:
                positive_regions[r] = positive_regions.get(r, 0) + 1
            tc = item.get("threat_category", "")
            if tc:
                positive_threats[tc] = positive_threats.get(tc, 0) + 1
            for a in (item.get("actors") or []):
                positive_actors[a] = positive_actors.get(a, 0) + 1

    # LOW-RATED analysis (avg < 3.0)
    low_pipeline = [
        {"$group": {
            "_id": "$intelligence_id",
            "avg": {"$avg": "$rating"},
            "count": {"$sum": 1},
        }},
        {"$match": {"avg": {"$lt": 3.0}, "count": {"$gte": 2}}},
    ]
    low_ids = []
    async for doc in feedback_col.aggregate(low_pipeline):
        low_ids.append(doc["_id"])

    negative_regions = {}
    negative_threats = {}
    noise_patterns = []
    if low_ids:
        async for item in intelligence_col.find(
            {"id": {"$in": low_ids}},
            {"_id": 0, "state": 1, "threat_category": 1, "tags": 1, "title": 1}
        ):
            r = item.get("state", "")
            if r:
                negative_regions[r] = negative_regions.get(r, 0) + 1
            tc = item.get("threat_category", "")
            if tc:
                negative_threats[tc] = negative_threats.get(tc, 0) + 1
            noise_patterns.append({
                "title": (item.get("title", ""))[:80],
                "category": tc,
                "region": r,
            })

    # Confidence level
    if total_feedback >= 100:
        confidence = "HIGH"
    elif total_feedback >= 30:
        confidence = "MODERATE"
    elif total_feedback >= 10:
        confidence = "LOW"
    else:
        confidence = "INSUFFICIENT_DATA"

    # Time decay factor
    recent_count = await feedback_col.count_documents({
        "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}
    })
    recency_ratio = round(recent_count / max(total_feedback, 1), 2)

    return {
        "total_feedback": total_feedback,
        "unique_items_rated": unique_items,
        "confidence_level": confidence,
        "recency_ratio": recency_ratio,
        "positive_weights": {
            "regions": dict(sorted(positive_regions.items(), key=lambda x: -x[1])[:10]),
            "threat_categories": dict(sorted(positive_threats.items(), key=lambda x: -x[1])[:10]),
            "actors": dict(sorted(positive_actors.items(), key=lambda x: -x[1])[:10]),
        },
        "negative_weights": {
            "regions": dict(sorted(negative_regions.items(), key=lambda x: -x[1])[:10]),
            "threat_categories": dict(sorted(negative_threats.items(), key=lambda x: -x[1])[:10]),
        },
        "high_rated_regions": sorted(positive_regions.items(), key=lambda x: -x[1])[:5],
        "low_rated_categories": sorted(negative_threats.items(), key=lambda x: -x[1])[:5],
        "noise_patterns": noise_patterns[:15],
        "preferred_categories": sorted(positive_threats.items(), key=lambda x: -x[1])[:5],
        "high_rated_count": len(high_ids),
        "low_rated_count": len(low_ids),
    }


# ============================================================
# Active Feedback Bias Profile (used by AI classification)
# ============================================================
@router.get("/feedback/bias-profile")
async def get_active_bias_profile():
    """Returns the current feedback bias profile that is dynamically
    injected into the AI classification pipeline."""
    profile = await get_feedback_bias_profile()
    return profile


# ============================================================
# Bias Impact Report
# ============================================================
@router.get("/feedback/bias-impact")
async def get_bias_impact_report():
    """Compare how items with feedback would score with vs without bias.
    Shows concrete examples of how analyst ratings shift AI priorities."""
    from feedback_bias import _get_bias_settings, INFLUENCE_CONFIG

    settings = await _get_bias_settings()
    influence = settings["influence"]
    inf_conf = INFLUENCE_CONFIG.get(influence, INFLUENCE_CONFIG["moderate"])

    # Get items that have feedback aggregation
    rated_items = await intelligence_col.find(
        {"feedback_avg_rating": {"$exists": True, "$gt": 0}, "feedback_total_ratings": {"$gte": 1}},
        {"_id": 0, "id": 1, "title": 1, "severity": 1, "priority_score": 1, "state": 1,
         "threat_category": 1, "feedback_avg_rating": 1, "feedback_total_ratings": 1}
    ).sort("feedback_total_ratings", -1).to_list(200)

    if not rated_items:
        return {
            "status": "no_data",
            "message": "No rated items found. Rate articles on the Intelligence Feed to generate impact data.",
            "items": [],
            "summary": {},
        }

    # Get the current bias profile to know what's upweighted/downweighted
    profile = await get_feedback_bias_profile()
    upweight_regions = set(profile.get("upweight_regions", {}).keys())
    upweight_threats = set(profile.get("upweight_threats", {}).keys())
    downweight_regions = set(profile.get("downweight_regions", {}).keys())
    downweight_threats = set(profile.get("downweight_threats", {}).keys())

    # Boost/reduce ranges based on influence
    boost_map = {"light": (3, 5), "moderate": (5, 10), "high": (10, 20)}
    reduce_map = {"light": (3, 5), "moderate": (5, 10), "high": (10, 20)}
    boost_lo, boost_hi = boost_map.get(influence, (5, 10))
    reduce_lo, reduce_hi = reduce_map.get(influence, (5, 10))

    impact_items = []
    total_boosted = 0
    total_reduced = 0
    total_unchanged = 0
    total_delta = 0

    for item in rated_items:
        original_score = item.get("priority_score", 30)
        region = item.get("state", "")
        threat = item.get("threat_category", "")
        avg_rating = item.get("feedback_avg_rating", 3.0)
        rating_count = item.get("feedback_total_ratings", 0)

        # Estimate bias delta
        delta = 0
        reasons = []

        if region in upweight_regions:
            avg_boost = (boost_lo + boost_hi) / 2
            delta += avg_boost
            reasons.append(f"Region '{region}' upweighted")
        elif region in downweight_regions:
            avg_reduce = (reduce_lo + reduce_hi) / 2
            delta -= avg_reduce
            reasons.append(f"Region '{region}' downweighted")

        if threat in upweight_threats:
            avg_boost = (boost_lo + boost_hi) / 2
            delta += avg_boost
            reasons.append(f"Threat '{threat}' upweighted")
        elif threat in downweight_threats:
            avg_reduce = (reduce_lo + reduce_hi) / 2
            delta -= avg_reduce
            reasons.append(f"Threat '{threat}' downweighted")

        # Clamp to -30..+30 and round
        delta = max(-30, min(30, round(delta)))
        biased_score = max(0, min(100, original_score + delta))

        if delta > 0:
            total_boosted += 1
            direction = "boosted"
        elif delta < 0:
            total_reduced += 1
            direction = "reduced"
        else:
            total_unchanged += 1
            direction = "unchanged"

        total_delta += abs(delta)

        impact_items.append({
            "id": item["id"],
            "title": (item.get("title") or "")[:80],
            "region": region,
            "threat_category": threat,
            "severity": item.get("severity", ""),
            "original_score": original_score,
            "biased_score": biased_score,
            "delta": delta,
            "direction": direction,
            "analyst_avg_rating": round(avg_rating, 1),
            "rating_count": rating_count,
            "reasons": reasons,
        })

    # Sort: biggest absolute deltas first
    impact_items.sort(key=lambda x: -abs(x["delta"]))

    avg_delta = round(total_delta / max(len(impact_items), 1), 1)

    return {
        "status": "active",
        "influence": influence,
        "influence_label": inf_conf["pct_label"],
        "window": settings["window"],
        "total_items_analyzed": len(impact_items),
        "summary": {
            "boosted": total_boosted,
            "reduced": total_reduced,
            "unchanged": total_unchanged,
            "avg_absolute_delta": avg_delta,
        },
        "items": impact_items[:30],
    }


# ============================================================
# Feedback Summary Stats
# ============================================================
@router.get("/feedback/stats")
async def get_feedback_stats():
    total = await feedback_col.count_documents({})
    unique_items = len(await feedback_col.distinct("intelligence_id"))
    unique_devices = len(await feedback_col.distinct("device_id"))

    # Global rating distribution
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    async for doc in feedback_col.aggregate([
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ]):
        if doc["_id"] in distribution:
            distribution[doc["_id"]] = doc["count"]

    global_avg = 0.0
    if total > 0:
        total_sum = sum(r * c for r, c in distribution.items())
        global_avg = round(total_sum / total, 2)

    # Recent activity (last 7 days)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recent = await feedback_col.count_documents({"timestamp": {"$gte": week_ago}})

    # Top rated items
    top_pipeline = [
        {"$group": {
            "_id": "$intelligence_id",
            "avg": {"$avg": "$rating"},
            "count": {"$sum": 1},
        }},
        {"$match": {"count": {"$gte": 2}}},
        {"$sort": {"avg": -1}},
        {"$limit": 5},
    ]
    top_items = []
    async for doc in feedback_col.aggregate(top_pipeline):
        item = await intelligence_col.find_one({"id": doc["_id"]}, {"_id": 0, "title": 1, "severity": 1, "state": 1})
        if item:
            top_items.append({
                "intelligence_id": doc["_id"],
                "avg_rating": round(doc["avg"], 2),
                "total_ratings": doc["count"],
                "title": item.get("title", "")[:80],
                "severity": item.get("severity", ""),
                "state": item.get("state", ""),
            })

    # Lowest rated items
    low_pipeline = [
        {"$group": {
            "_id": "$intelligence_id",
            "avg": {"$avg": "$rating"},
            "count": {"$sum": 1},
        }},
        {"$match": {"count": {"$gte": 2}}},
        {"$sort": {"avg": 1}},
        {"$limit": 5},
    ]
    low_items = []
    async for doc in feedback_col.aggregate(low_pipeline):
        item = await intelligence_col.find_one({"id": doc["_id"]}, {"_id": 0, "title": 1, "severity": 1, "state": 1})
        if item:
            low_items.append({
                "intelligence_id": doc["_id"],
                "avg_rating": round(doc["avg"], 2),
                "total_ratings": doc["count"],
                "title": item.get("title", "")[:80],
                "severity": item.get("severity", ""),
                "state": item.get("state", ""),
            })

    settings = await db.app_settings.find_one({"key": "max_feedback_per_item"}, {"_id": 0})
    max_limit = settings.get("value", 20) if settings else 20

    return {
        "total_feedback": total,
        "unique_items_rated": unique_items,
        "unique_devices": unique_devices,
        "global_avg_rating": global_avg,
        "distribution": distribution,
        "recent_7d": recent,
        "max_feedback_per_item": max_limit,
        "top_rated_items": top_items,
        "lowest_rated_items": low_items,
    }



# ============================================================
# Get Feedback Status for a Single Item (MUST come after static routes)
# ============================================================
@router.get("/feedback/{intelligence_id}")
async def get_feedback_for_item(intelligence_id: str, device_id: Optional[str] = None,
                                current_user: Optional[dict] = Depends(get_current_user_optional)):
    settings = await db.app_settings.find_one({"key": "max_feedback_per_item"}, {"_id": 0})
    max_limit = settings.get("value", 20) if settings else 20

    total = await feedback_col.count_documents({"intelligence_id": intelligence_id})

    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    async for doc in feedback_col.aggregate([
        {"$match": {"intelligence_id": intelligence_id}},
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ]):
        if doc["_id"] in distribution:
            distribution[doc["_id"]] = doc["count"]

    avg_rating = 0.0
    if total > 0:
        total_sum = sum(r * c for r, c in distribution.items())
        avg_rating = round(total_sum / total, 2)

    user_rating = await _find_user_rating(current_user, intelligence_id, device_id)

    limit_reached = total >= max_limit

    return {
        "intelligence_id": intelligence_id,
        "total_ratings": total,
        "max_limit": max_limit,
        "limit_reached": limit_reached,
        "avg_rating": avg_rating,
        "derived_relevance": _derive_relevance(avg_rating) if total > 0 else None,
        "confidence_factor": round(math.log(total + 1), 2),
        "distribution": distribution,
        "user_rating": user_rating,
    }


# ============================================================
# Internal: Update aggregation on the intelligence item
# ============================================================
async def _update_aggregation(intelligence_id: str):
    pipeline = [
        {"$match": {"intelligence_id": intelligence_id}},
        {"$group": {
            "_id": None,
            "avg_rating": {"$avg": "$rating"},
            "total_ratings": {"$sum": 1},
        }}
    ]
    result = None
    async for doc in feedback_col.aggregate(pipeline):
        result = doc

    if result:
        avg = round(result["avg_rating"], 2)
        total = result["total_ratings"]
        confidence = round(math.log(total + 1), 2)
        derived = _derive_relevance(avg)

        await intelligence_col.update_one(
            {"id": intelligence_id},
            {"$set": {
                "feedback_avg_rating": avg,
                "feedback_total_ratings": total,
                "feedback_confidence": confidence,
                "feedback_derived_relevance": derived,
            }}
        )
