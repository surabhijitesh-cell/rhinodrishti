"""Feedback endpoints: submit/update ratings, aggregation, training profile."""
from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone, timedelta
import math
import uuid
import os
from shared import db, feedback_col, intelligence_col, activity_log_col, logger

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
@router.post("/feedback")
async def submit_feedback(body: dict, request: Request, background_tasks: BackgroundTasks):
    intelligence_id = body.get("intelligence_id")
    device_id = body.get("device_id")
    rating = body.get("rating")

    if not intelligence_id or not device_id:
        raise HTTPException(status_code=400, detail="intelligence_id and device_id are required")
    if not isinstance(rating, int) or rating < 1 or rating > 6:
        raise HTTPException(status_code=400, detail="rating must be integer 1-6")

    item = await intelligence_col.find_one({"id": intelligence_id}, {"_id": 0, "id": 1, "state": 1, "threat_category": 1, "actors": 1, "tags": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Intelligence item not found")

    # Check max feedback limit
    settings = await db.app_settings.find_one({"key": "max_feedback_per_item"}, {"_id": 0})
    max_limit = settings.get("value", 20) if settings else 20

    existing = await feedback_col.find_one(
        {"intelligence_id": intelligence_id, "device_id": device_id},
        {"_id": 0}
    )

    if existing:
        # Update existing rating
        await feedback_col.update_one(
            {"intelligence_id": intelligence_id, "device_id": device_id},
            {"$set": {
                "rating": rating,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await _update_aggregation(intelligence_id)
        background_tasks.add_task(_check_feedback_session, device_id)
        return {"message": "Rating updated", "action": "updated", "rating": rating}

    # Check cap before inserting new
    current_count = await feedback_col.count_documents({"intelligence_id": intelligence_id})
    if current_count >= max_limit:
        raise HTTPException(status_code=429, detail=f"Maximum feedback limit ({max_limit}) reached for this item")

    # Derive features from the intelligence item
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
        "rating": rating,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ip_address": request.client.host if request.client else "",
        "derived_features": derived,
    }

    await feedback_col.insert_one(doc)
    await _update_aggregation(intelligence_id)

    # Check if device has enough ratings for a feedback session log
    background_tasks.add_task(_check_feedback_session, device_id)

    return {"message": "Rating submitted", "action": "created", "rating": rating}


# ============================================================
# Batch Feedback Status (for feed pages)
# NOTE: Static routes MUST come before {intelligence_id} path
# ============================================================
@router.post("/feedback/batch")
async def get_batch_feedback(body: dict):
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
    if device_id:
        async for doc in feedback_col.find(
            {"intelligence_id": {"$in": item_ids}, "device_id": device_id},
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
async def get_feedback_for_item(intelligence_id: str, device_id: Optional[str] = None):
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

    user_rating = None
    if device_id:
        existing = await feedback_col.find_one(
            {"intelligence_id": intelligence_id, "device_id": device_id},
            {"_id": 0, "rating": 1}
        )
        if existing:
            user_rating = existing["rating"]

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


FEEDBACK_SESSION_THRESHOLD = 5  # Minimum ratings to trigger a session log


async def _check_feedback_session(device_id: str):
    """Check if device has accumulated enough unlogged ratings to create a feedback session."""
    try:
        # Find the timestamp of the last feedback session for this device
        last_session = await activity_log_col.find_one(
            {"activity_type": "feedback_session", "device_id": device_id},
            {"_id": 0, "timestamp": 1},
            sort=[("timestamp", -1)]
        )
        since = last_session["timestamp"] if last_session else "2000-01-01T00:00:00"

        # Count ratings from this device since last session
        unlogged = await feedback_col.find(
            {"device_id": device_id, "timestamp": {"$gt": since}},
            {"_id": 0, "rating": 1, "intelligence_id": 1, "derived_features": 1}
        ).to_list(200)

        if len(unlogged) < FEEDBACK_SESSION_THRESHOLD:
            return

        # Build distribution
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        for fb in unlogged:
            r = fb.get("rating", 0)
            if r in distribution:
                distribution[r] += 1

        # Aggregate features from high-rated and low-rated items
        high_regions, high_threats, high_actors = {}, {}, {}
        low_regions, low_threats = {}, {}
        for fb in unlogged:
            feats = fb.get("derived_features") or {}
            rating = fb.get("rating", 3)
            region = feats.get("region", "")
            threat = feats.get("threat_category", "")
            if rating >= 4:
                if region:
                    high_regions[region] = high_regions.get(region, 0) + 1
                if threat:
                    high_threats[threat] = high_threats.get(threat, 0) + 1
                for a in (feats.get("actors") or []):
                    high_actors[a] = high_actors.get(a, 0) + 1
            elif rating <= 2:
                if region:
                    low_regions[region] = low_regions.get(region, 0) + 1
                if threat:
                    low_threats[threat] = low_threats.get(threat, 0) + 1

        high_features = {"regions": high_regions, "threat_categories": high_threats, "actors": high_actors}
        low_features = {"regions": low_regions, "threat_categories": low_threats}

        # Generate AI impact summary
        from routers.training import _generate_feedback_impact_summary
        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        impact_summary = await _generate_feedback_impact_summary(
            emergent_key, len(unlogged), distribution, high_features, low_features
        )

        # Build volume string
        dist_parts = [f"{v}x{k}" for k, v in sorted(distribution.items()) if v > 0]
        volume = f"{len(unlogged)} ratings ({', '.join(dist_parts)})"

        await activity_log_col.insert_one({
            "id": str(uuid.uuid4()),
            "activity_type": "feedback_session",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id[-6:],
            "total_items": len(unlogged),
            "volume": volume,
            "rating_distribution": {str(k): v for k, v in distribution.items()},
            "impact_summary": impact_summary,
        })
        logger.info(f"Feedback session logged for device {device_id[-6:]}: {len(unlogged)} ratings")

    except Exception as e:
        logger.error(f"Feedback session check failed: {e}")
