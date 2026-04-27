"""Keyword Engine endpoints."""
from fastapi import APIRouter, Query, BackgroundTasks
from typing import Optional
import os
from shared import db, logger

router = APIRouter()


@router.get("/keywords")
async def get_keywords(
    type: Optional[str] = None,
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(100, ge=1, le=300),
):
    from keyword_engine import generate_keywords

    keywords = await generate_keywords(db, use_ai=False)

    stored = await db.keyword_store.find(
        {"score": {"$gte": min_score}},
        {"_id": 0}
    ).sort("score", -1).limit(300).to_list(300)

    kw_map = {k["keyword"].lower(): k for k in keywords}

    for sk in stored:
        key = sk.get("keyword", "").lower()
        if key in kw_map:
            if sk.get("score", 0) > kw_map[key]["score"]:
                kw_map[key]["score"] = sk["score"]
                kw_map[key]["source"] = sk.get("source", kw_map[key].get("source", ""))
        else:
            kw_map[key] = {
                "keyword": sk.get("keyword", ""),
                "type": sk.get("category", "primary"),
                "score": sk.get("score", 50),
                "source": sk.get("source", "stored"),
            }

    result = sorted(kw_map.values(), key=lambda k: k["score"], reverse=True)

    if type:
        result = [k for k in result if k["type"] == type]

    result = [k for k in result if k["score"] >= min_score][:limit]

    type_counts = {}
    for k in result:
        t = k["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "keywords": result,
        "count": len(result),
        "type_breakdown": type_counts,
    }


@router.post("/keywords/refresh")
async def refresh_keywords(background_tasks: BackgroundTasks):
    from keyword_engine import generate_keywords, store_keywords_to_db, _keyword_cache

    _keyword_cache["generated_at"] = None
    _keyword_cache["keywords"] = []

    async def _refresh():
        keywords = await generate_keywords(db, use_ai=True)
        await store_keywords_to_db(db, keywords)
        logger.info(f"Keyword refresh complete: {len(keywords)} keywords stored")

    background_tasks.add_task(_refresh)
    return {"message": "Keyword refresh started with AI expansion"}


@router.post("/keywords/add")
async def add_keyword_manually(body: dict):
    keyword = (body.get("keyword") or "").strip()
    if not keyword or len(keyword) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Keyword must be at least 2 characters")

    kw_type = body.get("type", "primary")
    score = body.get("score", 60)
    if not isinstance(score, int) or score < 1 or score > 100:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Score must be integer 1-100")

    valid_types = ["primary", "entity", "geo", "cross_border", "emerging", "expanded"]
    if kw_type not in valid_types:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Type must be one of {valid_types}")

    # Check if keyword already exists
    existing = await db.keyword_store.find_one(
        {"keyword": {"$regex": f"^{keyword}$", "$options": "i"}},
        {"_id": 0}
    )
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"Keyword '{keyword}' already exists")

    from datetime import datetime, timezone
    doc = {
        "keyword": keyword,
        "category": kw_type,
        "score": score,
        "source": "manual",
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.keyword_store.insert_one(doc)

    logger.info(f"Manual keyword added: '{keyword}' type={kw_type} score={score}")
    return {"message": f"Keyword '{keyword}' added", "keyword": keyword, "type": kw_type, "score": score}
