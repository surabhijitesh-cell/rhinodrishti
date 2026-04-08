"""Sources, Twitter feeds, and Handbook endpoints."""
from fastapi import APIRouter, Query, HTTPException
import os
from shared import sources_col, tweets_col, TWITTER_ACCOUNTS_TO_MONITOR, logger

router = APIRouter()


@router.get("/sources")
async def get_sources():
    sources = await sources_col.find({}, {"_id": 0}).to_list(100)
    return {"sources": sources}


@router.get("/twitter-accounts")
async def get_twitter_accounts():
    return {"accounts": TWITTER_ACCOUNTS_TO_MONITOR}


@router.get("/twitter-feeds")
async def get_twitter_feeds(limit: int = Query(50, ge=1, le=200)):
    feeds = await tweets_col.find({}, {"_id": 0}).sort("posted_at", -1).limit(limit).to_list(limit)
    return {"feeds": feeds, "count": len(feeds)}


@router.get("/handbook")
async def get_handbook():
    handbook_path = os.path.join(os.path.dirname(__file__), '..', '..', 'USER_HANDBOOK.md')
    try:
        with open(handbook_path, 'r') as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Handbook not found")
