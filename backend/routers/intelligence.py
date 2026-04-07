"""Intelligence feed, alerts, acknowledgement, semantic search, embeddings."""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone, timedelta
from shared import db, intelligence_col, _stats_cache, STATS_CACHE_TTL, invalidate_stats_cache, SEVERITY_LEVELS, logger

router = APIRouter()


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    if _stats_cache["data"] and _stats_cache["expires_at"] and datetime.now(timezone.utc) < _stats_cache["expires_at"]:
        return _stats_cache["data"]

    retention = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    retention_days = retention.get("value", 30) if retention else 30
    retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    base_filter = {"published_at": {"$gte": retention_cutoff}, "processed": True}

    total = await intelligence_col.count_documents(base_filter)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = await intelligence_col.count_documents({**base_filter, "published_at": {"$regex": f"^{today}"}})
    severity_counts = {}
    for sev in SEVERITY_LEVELS:
        severity_counts[sev] = await intelligence_col.count_documents({**base_filter, "severity": sev})
    cross_border = await intelligence_col.count_documents({**base_filter, "is_cross_border": True})
    state_distribution = {}
    for state in ["Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura", "Nagaland", "Bangladesh", "Myanmar"]:
        state_distribution[state] = await intelligence_col.count_documents({**base_filter, "state": state})
    recent = await intelligence_col.find(
        {**base_filter, "severity": {"$in": ["critical", "high"]}}, {"_id": 0}
    ).sort("published_at", -1).limit(10).to_list(10)
    trend_data = []
    for i in range(7):
        date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        day_data = {"date": date}
        for sev in SEVERITY_LEVELS:
            day_data[sev] = await intelligence_col.count_documents({
                **base_filter, "severity": sev, "published_at": {"$regex": f"^{date}"}
            })
        trend_data.append(day_data)

    result = {
        "total_items": total, "today_count": today_count,
        "critical_count": severity_counts.get("critical", 0),
        "high_count": severity_counts.get("high", 0),
        "medium_count": severity_counts.get("medium", 0),
        "low_count": severity_counts.get("low", 0),
        "cross_border_count": cross_border,
        "state_distribution": state_distribution,
        "recent_critical": recent, "trend_data": trend_data,
        "retention_days": retention_days,
    }
    _stats_cache["data"] = result
    _stats_cache["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=STATS_CACHE_TTL)
    return result


@router.get("/intelligence")
async def get_intelligence(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = None, state: Optional[str] = None,
    threat: Optional[str] = None, date_from: Optional[str] = None,
    date_to: Optional[str] = None, search: Optional[str] = None,
    sort: Optional[str] = "published_at", cross_border: Optional[bool] = None,
    priority_min: Optional[int] = None,
):
    query = {"processed": True}
    if not date_from:
        retention = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
        retention_days = retention.get("value", 30) if retention else 30
        retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        query["published_at"] = {"$gte": retention_cutoff}
    if severity:
        query["severity"] = severity
    if state:
        query["state"] = state
    if threat:
        query["threat_category"] = threat
    if date_from:
        query.setdefault("published_at", {})
        query["published_at"]["$gte"] = date_from
    if date_to:
        query.setdefault("published_at", {})
        query["published_at"]["$lte"] = date_to
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"ai_summary": {"$regex": search, "$options": "i"}},
            {"raw_content": {"$regex": search, "$options": "i"}},
        ]
    if cross_border is not None:
        query["is_cross_border"] = cross_border
    if priority_min is not None:
        query["priority_score"] = {"$gte": priority_min}

    total = await intelligence_col.count_documents(query)
    sort_field = sort if sort in ("published_at", "severity", "priority_score") else "published_at"
    sort_dir = -1
    skip = (page - 1) * limit
    items = await intelligence_col.find(query, {"_id": 0, "embedding": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit).to_list(limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/intelligence/{item_id}")
async def get_intelligence_item(item_id: str):
    item = await intelligence_col.find_one({"id": item_id}, {"_id": 0, "embedding": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/alerts")
async def get_alerts():
    items = await intelligence_col.find(
        {"severity": {"$in": ["critical", "high"]}, "processed": True}, {"_id": 0}
    ).sort("published_at", -1).limit(30).to_list(30)
    return {"alerts": items}


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
        }, {"_id": 0}
    ).sort("published_at", -1).limit(50).to_list(50)
    return {"alerts": items, "count": len(items)}


@router.post("/intelligence/{item_id}/acknowledge")
async def acknowledge_alert(item_id: str):
    result = await intelligence_col.update_one(
        {"id": item_id},
        {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Alert acknowledged"}


@router.post("/intelligence/semantic-search")
async def intelligence_semantic_search(body: dict):
    query_text = body.get("query", "")
    limit = body.get("limit", 10)
    min_score = body.get("min_score", 0.3)
    if not query_text:
        raise HTTPException(status_code=400, detail="Query text required")
    try:
        from embedding_service import generate_embedding, cosine_similarity
        query_emb = await generate_embedding(query_text)
        if not query_emb:
            return {"results": [], "message": "Could not generate query embedding"}
        cursor = intelligence_col.find(
            {"embedding": {"$exists": True, "$ne": None}, "processed": True},
            {"_id": 0, "embedding": 1, "id": 1, "title": 1, "ai_summary": 1,
             "severity": 1, "state": 1, "source": 1, "published_at": 1,
             "priority_score": 1, "threat_category": 1}
        )
        results = []
        async for item in cursor:
            emb = item.get("embedding")
            if emb:
                score = cosine_similarity(query_emb, emb)
                if score >= min_score:
                    item.pop("embedding", None)
                    item["similarity_score"] = round(score, 4)
                    results.append(item)
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return {"results": results[:limit], "total_searched": len(results)}
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return {"results": [], "error": str(e)}


@router.post("/embeddings/backfill")
async def trigger_embedding_backfill(background_tasks: BackgroundTasks):
    from embedding_service import backfill_embeddings
    background_tasks.add_task(backfill_embeddings, db)
    return {"message": "Embedding backfill started (batch of 50)"}
