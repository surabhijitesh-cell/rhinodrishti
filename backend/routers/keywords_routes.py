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
    EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

    keywords = await generate_keywords(db, emergent_key=EMERGENT_KEY, use_ai=False)

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
    EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

    _keyword_cache["generated_at"] = None
    _keyword_cache["keywords"] = []

    async def _refresh():
        keywords = await generate_keywords(db, emergent_key=EMERGENT_KEY, use_ai=True)
        await store_keywords_to_db(db, keywords)
        logger.info(f"Keyword refresh complete: {len(keywords)} keywords stored")

    background_tasks.add_task(_refresh)
    return {"message": "Keyword refresh started with AI expansion"}
