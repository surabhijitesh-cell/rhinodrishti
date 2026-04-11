"""Intelligence feed, alerts, acknowledgement, semantic search, embeddings, patterns."""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone, timedelta
from shared import (
    db, intelligence_col, patterns_col, _stats_cache, STATS_CACHE_TTL,
    invalidate_stats_cache, SEVERITY_LEVELS, logger,
    has_non_latin_chars, translate_to_english,
)

router = APIRouter()


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    now = datetime.now(timezone.utc)
    if _stats_cache["data"] and _stats_cache["expires_at"] and now < _stats_cache["expires_at"]:
        return _stats_cache["data"]

    settings = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    retention_days = settings.get("value", 30) if settings else 30
    retention_cutoff = (now - timedelta(days=retention_days)).isoformat()
    base_filter = {"published_at": {"$gte": retention_cutoff}, "processed": True}

    total = await intelligence_col.count_documents(base_filter)
    critical = await intelligence_col.count_documents({**base_filter, "severity": "critical"})
    high = await intelligence_col.count_documents({**base_filter, "severity": "high"})
    medium = await intelligence_col.count_documents({**base_filter, "severity": "medium"})
    low = await intelligence_col.count_documents({**base_filter, "severity": "low"})

    state_dist = {}
    async for doc in intelligence_col.aggregate([
        {"$match": base_filter},
        {"$group": {"_id": "$state", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]):
        if doc["_id"]:
            state_dist[doc["_id"]] = doc["count"]

    threat_dist = {}
    async for doc in intelligence_col.aggregate([
        {"$match": base_filter},
        {"$group": {"_id": "$threat_category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]):
        if doc["_id"]:
            threat_dist[doc["_id"]] = doc["count"]

    recent_critical = await intelligence_col.find(
        {**base_filter, "severity": {"$in": ["critical", "high"]}},
        {"_id": 0}
    ).sort("published_at", -1).limit(5).to_list(5)

    today = now.strftime("%Y-%m-%d")
    today_count = await intelligence_col.count_documents(
        {"published_at": {"$regex": f"^{today}"}}
    )

    trend_data = []
    async for doc in intelligence_col.aggregate([
        {"$match": base_filter},
        {"$group": {
            "_id": {"$substr": ["$published_at", 0, 10]},
            "count": {"$sum": 1},
            "critical": {"$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}},
            "high": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]):
        trend_data.append({"date": doc["_id"], "count": doc["count"], "critical": doc["critical"], "high": doc["high"]})

    result = {
        "total_items": total, "today_count": today_count,
        "critical_count": critical, "high_count": high,
        "medium_count": medium, "low_count": low,
        "state_distribution": state_dist, "threat_distribution": threat_dist,
        "recent_critical": recent_critical, "trend_7d": trend_data[-7:],
        "retention_days": retention_days,
    }

    _stats_cache["data"] = result
    _stats_cache["expires_at"] = now + timedelta(seconds=STATS_CACHE_TTL)
    return result


@router.get("/intelligence")
async def get_intelligence(
    state: Optional[str] = None,
    threat_type: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_cross_border: Optional[bool] = None,
    min_priority: Optional[int] = None,
    sort_by: Optional[str] = Query(None, description="Sort field: published_at, priority_score, severity"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    translate: bool = Query(True)
):
    query = {
        "processed": True,
        "is_cluster_primary": {"$ne": False},
        "severity": {"$nin": ["low", "LOW"]},
        "tags": {"$nin": ["not_relevant", "unprocessed"]},
    }

    if not date_from:
        settings = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
        retention_days = settings.get("value", 30) if settings else 30
        retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        query["published_at"] = {"$gte": retention_cutoff}

    if state:
        query["state"] = state
    if threat_type:
        query["threat_category"] = threat_type
    if severity:
        query["severity"] = severity
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"ai_summary": {"$regex": search, "$options": "i"}},
            {"raw_content": {"$regex": search, "$options": "i"}}
        ]
    if date_from:
        query.setdefault("published_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("published_at", {})["$lte"] = date_to
    if is_cross_border is not None:
        query["is_cross_border"] = is_cross_border
    if min_priority is not None:
        query["priority_score"] = {"$gte": min_priority}

    sort_dir = -1 if sort_order == "desc" else 1
    sort_field = "published_at"
    if sort_by == "priority_score":
        sort_field = "priority_score"
    elif sort_by == "severity":
        sort_field = "severity"

    skip = (page - 1) * limit
    total = await intelligence_col.count_documents(query)
    items = await intelligence_col.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit).to_list(limit)

    if translate:
        for item in items:
            if has_non_latin_chars(item.get("title", "")):
                item["title"] = await translate_to_english(item["title"])

    return {
        "items": items, "total": total, "page": page,
        "limit": limit, "pages": max((total + limit - 1) // limit, 0)
    }


@router.get("/intelligence/{item_id}")
async def get_intelligence_item(item_id: str):
    item = await intelligence_col.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/alerts")
async def get_alerts():
    items = await intelligence_col.find(
        {"severity": {"$in": ["critical", "high"]}, "processed": True}, {"_id": 0}
    ).sort("published_at", -1).limit(30).to_list(30)
    return {"alerts": items, "count": len(items)}


@router.get("/alerts/unacknowledged")
async def get_unacknowledged_alerts():
    items = await intelligence_col.find(
        {
            "severity": {"$in": ["critical", "high"]},
            "processed": True,
            "$or": [
                {"acknowledged": {"$exists": False}},
                {"acknowledged": False}
            ]
        },
        {"_id": 0}
    ).sort("published_at", -1).limit(50).to_list(50)
    return {"alerts": items, "count": len(items)}


@router.post("/intelligence/{item_id}/acknowledge")
async def acknowledge_alert(item_id: str):
    result = await intelligence_col.update_one(
        {"id": item_id},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Alert acknowledged", "id": item_id}


@router.get("/patterns")
async def get_patterns():
    patterns = await patterns_col.find({}, {"_id": 0}).to_list(100)
    return {"patterns": patterns, "count": len(patterns)}


@router.post("/patterns/detect")
async def trigger_pattern_detection(background_tasks: BackgroundTasks):
    from pattern_engine import detect_patterns
    background_tasks.add_task(detect_patterns, db)
    return {"message": "Pattern detection started"}


@router.post("/intelligence/semantic-search")
async def intelligence_semantic_search(body: dict):
    query = body.get("query", "")
    limit = body.get("limit", 10)
    min_score = body.get("min_score", 0.3)

    if not query or len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    from embedding_service import semantic_search
    results = await semantic_search(db, query, limit=limit, min_score=min_score)

    return {"results": results, "count": len(results), "query": query}


@router.post("/embeddings/backfill")
async def trigger_embedding_backfill(background_tasks: BackgroundTasks):
    from embedding_service import backfill_embeddings
    background_tasks.add_task(backfill_embeddings, db, 50)
    return {"message": "Embedding backfill started (batch of 50)"}


@router.post("/fusion/run")
async def trigger_batch_fusion(background_tasks: BackgroundTasks):
    from fusion_engine import run_batch_fusion
    background_tasks.add_task(run_batch_fusion, db)
    return {"message": "Batch fusion started"}


@router.get("/fusion/stats")
async def get_fusion_stats():
    from datetime import timedelta
    settings = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    retention_days = settings.get("value", 30) if settings else 30
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    total_items = await intelligence_col.count_documents({"processed": True, "published_at": {"$gte": cutoff}})
    clustered = await intelligence_col.count_documents({
        "processed": True,
        "published_at": {"$gte": cutoff},
        "cluster_id": {"$exists": True, "$ne": None},
    })
    primaries = await intelligence_col.count_documents({
        "processed": True,
        "published_at": {"$gte": cutoff},
        "cluster_id": {"$exists": True, "$ne": None},
        "is_cluster_primary": True,
    })
    unclustered = total_items - clustered

    # Get cluster size distribution
    cluster_sizes = []
    async for doc in intelligence_col.aggregate([
        {"$match": {"cluster_id": {"$exists": True, "$ne": None}, "is_cluster_primary": True, "published_at": {"$gte": cutoff}}},
        {"$project": {"_id": 0, "cluster_size": 1, "title": 1}},
        {"$sort": {"cluster_size": -1}},
        {"$limit": 20}
    ]):
        cluster_sizes.append({"title": (doc.get("title", "")[:80]), "size": doc.get("cluster_size", 0)})

    return {
        "total_items": total_items,
        "clustered_items": clustered,
        "unique_clusters": primaries,
        "unclustered_items": unclustered,
        "dedup_ratio": round((1 - (primaries + unclustered) / total_items) * 100, 1) if total_items > 0 else 0,
        "visible_items": primaries + unclustered,
        "top_clusters": cluster_sizes,
    }
