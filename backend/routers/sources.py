"""Sources, Social feeds, and Handbook endpoints."""
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
import uuid
import os
from shared import sources_col, tweets_col, intelligence_col, TWITTER_ACCOUNTS_TO_MONITOR, logger, db, invalidate_stats_cache

router = APIRouter()


@router.get("/sources")
async def get_sources():
    sources = await sources_col.find({}, {"_id": 0}).to_list(100)
    return {"sources": sources}


@router.get("/twitter-accounts")
async def get_twitter_accounts():
    return {"accounts": TWITTER_ACCOUNTS_TO_MONITOR}


@router.get("/twitter-feeds")
async def get_twitter_feeds(limit: int = Query(100, ge=1, le=500)):
    """
    Returns raw tweets from db.twitter_feeds (direct, no AI filter).
    Falls back to intelligence_items with source_type=twitter* when raw collection is empty.
    """
    feeds = await tweets_col.find({}, {"_id": 0}).sort("posted_at", -1).limit(limit).to_list(limit)
    if feeds:
        return {"feeds": feeds, "count": len(feeds), "source": "raw_feeds"}

    # Fallback: pull from AI pipeline (all twitter items including unprocessed)
    items = await intelligence_col.find(
        {"source_type": {"$regex": "^twitter", "$options": "i"}},
        {"_id": 0},
    ).sort("published_at", -1).limit(limit).to_list(limit)

    # Normalize to twitter-feed shape so the widget doesn't need to branch
    feeds = [_intel_to_tweet_shape(it) for it in items]
    return {"feeds": feeds, "count": len(feeds), "source": "intelligence_pipeline"}


@router.get("/social-feeds/{source_type}")
async def get_social_feeds(
    source_type: str,
    limit: int = Query(100, ge=1, le=500),
    include_unprocessed: bool = Query(True),
):
    """
    Generic raw feed endpoint for any social/web source type.
    Returns ALL items regardless of AI processing status (no severity gate, no
    relevance filter) so analysts can see exactly what was fetched.

    source_type: twitter | youtube | facebook | telegram | firecrawl
    """
    source_type = source_type.lower().strip()

    if source_type == "twitter":
        # Twitter has its own raw collection
        feeds = await tweets_col.find({}, {"_id": 0}).sort("posted_at", -1).limit(limit).to_list(limit)
        if feeds:
            return {"items": feeds, "count": len(feeds), "source": "raw_feeds"}
        # Fallback to intelligence_items
        items = await intelligence_col.find(
            {"source_type": {"$regex": "^twitter", "$options": "i"}},
            {"_id": 0},
        ).sort("published_at", -1).limit(limit).to_list(limit)
        return {"items": [_intel_to_tweet_shape(it) for it in items], "count": len(items), "source": "intelligence_pipeline"}

    # All other sources: query intelligence_items directly (no AI/severity gate)
    mongo_query: dict = {"source_type": {"$regex": f"^{source_type}", "$options": "i"}}
    if not include_unprocessed:
        mongo_query["processed"] = True

    items = await intelligence_col.find(mongo_query, {"_id": 0}).sort("published_at", -1).limit(limit).to_list(limit)
    return {"items": items, "count": len(items), "source": "intelligence_pipeline"}


def _intel_to_tweet_shape(item: dict) -> dict:
    """Normalize an intelligence_items doc to the twitter-feeds field shape."""
    return {
        "id":           item.get("id", ""),
        "handle":       item.get("source", ""),
        "account_name": (item.get("title", "") or "").replace("Tweet by ", ""),
        "tweet_text":   item.get("raw_content", "") or item.get("ai_summary", ""),
        "tweet_url":    item.get("source_url", ""),
        "posted_at":    item.get("published_at", ""),
        "fetched_at":   item.get("fetched_at", ""),
        "category":     item.get("source_type", "twitter"),
        "severity":     item.get("severity", ""),
        "priority":     item.get("priority_score", 0),
        "processed":    item.get("processed", False),
        # Keep all original fields too so the widget can show severity/state
        **{k: v for k, v in item.items() if k not in (
            "id", "handle", "account_name", "tweet_text", "tweet_url",
            "posted_at", "fetched_at", "category",
        )},
    }


@router.post("/social/import")
async def import_social_item(body: dict):
    """Import a raw social-media item into the intelligence_items collection.

    Used when the item has NOT yet been processed by the AI pipeline (e.g. a raw
    tweet from db.twitter_feeds that wasn't stored in intelligence_items).

    Pass the full item dict from the social-feed widget.  A new intelligence_items
    entry is upserted by source_url / tweet_url so duplicates are avoided.
    """
    source_url = (
        body.get("tweet_url") or body.get("source_url") or body.get("url") or ""
    )
    if not source_url:
        raise HTTPException(status_code=422, detail="item must have tweet_url or source_url")

    now = datetime.now(timezone.utc).isoformat()

    # Check if already in intelligence_items
    existing = await intelligence_col.find_one(
        {"source_url": source_url}, {"_id": 0, "id": 1, "processed": 1}
    )
    if existing:
        # Already imported — if accepted flag wanted, caller should use /intelligence/{id}/accept
        return {
            "message": "Item already in intelligence database",
            "id": existing["id"],
            "action": "existing",
        }

    # Build a minimal intelligence_items document from the raw feed item
    new_id = str(uuid.uuid4())
    raw_content = (
        body.get("tweet_text") or body.get("raw_content") or
        body.get("ai_summary") or body.get("title") or ""
    )
    source_type = body.get("source_type") or body.get("category") or "social"
    doc = {
        "id":                new_id,
        "title":             body.get("account_name") or body.get("title") or body.get("source") or "",
        "raw_content":       raw_content,
        "source":            body.get("handle") or body.get("source") or source_type,
        "source_url":        source_url,
        "source_type":       source_type,
        "published_at":      body.get("posted_at") or body.get("published_at") or now,
        "fetched_at":        now,
        "processed":         True,          # manually added — mark as accepted
        "is_relevant":       True,
        "manually_accepted": True,
        "manually_accepted_at": now,
        "severity":          body.get("severity") or "medium",
        "state":             body.get("state") or "",
        "tags":              ["manually_imported"],
        "entities":          body.get("entities") or {},
        "priority_score":    body.get("priority") or body.get("priority_score") or 5,
    }

    await intelligence_col.insert_one(doc)
    invalidate_stats_cache()
    return {"message": "Item imported into intelligence feed", "id": new_id, "action": "created"}


@router.get("/handbook")
async def get_handbook():
    handbook_path = os.path.join(os.path.dirname(__file__), '..', '..', 'USER_HANDBOOK.md')
    try:
        with open(handbook_path, 'r') as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Handbook not found")
