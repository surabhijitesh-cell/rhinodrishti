"""
Unified Social Media management router.

Covers: X (Twitter), YouTube, Facebook, Telegram
Each platform has:
  GET    /api/social/{platform}           — list sources
  POST   /api/social/{platform}           — add source
  PATCH  /api/social/{platform}/{id}      — update / toggle active
  DELETE /api/social/{platform}/{id}      — remove
  POST   /api/social/{platform}/{id}/fetch — on-demand fetch

GET /api/social/status   — configured status of all platforms
POST /api/social/fetch-all — trigger all platforms now (admin use)
"""

import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from shared import db, logger

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class TwitterAccountBody(BaseModel):
    handle: str          # without @
    name: str
    category: str = "general"
    active: bool = True

class TwitterSearchBody(BaseModel):
    query: str
    num_results: int = 10
    active: bool = True

class YouTubeChannelBody(BaseModel):
    name: str
    channel_id: str
    category: str = "media"
    active: bool = True

class YouTubeSearchBody(BaseModel):
    query: str
    max_results: int = 5
    active: bool = True

class FacebookPageBody(BaseModel):
    name: str
    page_id: str
    category: str = "media"
    active: bool = True

class TelegramChannelBody(BaseModel):
    username: str        # without @
    name: str
    category: str = "media"
    active: bool = True

class PatchBody(BaseModel):
    active: Optional[bool] = None
    name: Optional[str] = None
    category: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Status endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/status")
async def social_status():
    import os
    from telegram_fetcher import _is_configured as tg_ok

    twitter_configured  = bool(os.environ.get("TWITTER_BEARER_TOKEN", "").strip())
    youtube_configured  = bool(os.environ.get("YOUTUBE_API_KEY", "").strip())
    facebook_configured = bool(os.environ.get("FACEBOOK_APP_ID", "").strip() and
                               os.environ.get("FACEBOOK_APP_SECRET", "").strip())
    firecrawl_configured = bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())

    return {
        "twitter": {
            "configured": twitter_configured,
            "available":  twitter_configured,  # No Nitter fallback — needs API key
            "note": ("Official X API v2 (Basic tier+). Nitter fallback was removed because "
                     "all public Nitter instances broke when Twitter killed guest-account "
                     "access in mid-2023. Set TWITTER_BEARER_TOKEN to enable.")
            if not twitter_configured else "Official X API v2 active.",
        },
        "youtube": {
            "configured": youtube_configured,
            "available":  youtube_configured,
            "note": "YouTube Data API v3 (free, 10k quota/day). Set YOUTUBE_API_KEY."
            if not youtube_configured else "YouTube Data API v3 active.",
        },
        "facebook": {
            "configured": facebook_configured,
            "available":  facebook_configured,
            "note": "Graph API app access token — public pages only. Set FACEBOOK_APP_ID + FACEBOOK_APP_SECRET."
            if not facebook_configured else "Graph API v19 active.",
        },
        "telegram": {
            "configured": tg_ok(),
            "available":  tg_ok(),
            "note": "Telethon user session — run telegram_setup.py once to generate session."
            if not tg_ok() else "Telethon user session active.",
        },
        "firecrawl": {
            "configured": firecrawl_configured,
            "available":  firecrawl_configured,
            "note": "Firecrawl SaaS — set FIRECRAWL_API_KEY."
            if not firecrawl_configured else "Firecrawl active.",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Twitter — accounts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/twitter/accounts")
async def list_twitter_accounts():
    items = await db.twitter_accounts.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return {"accounts": items, "count": len(items)}


@router.post("/social/twitter/accounts", status_code=201)
async def add_twitter_account(body: TwitterAccountBody):
    handle = body.handle.lstrip("@")
    if await db.twitter_accounts.find_one({"handle": handle}):
        raise HTTPException(409, "Account already tracked")
    doc = {"id": str(uuid.uuid4()), "handle": handle, "name": body.name,
           "category": body.category, "active": body.active,
           "created_at": datetime.now(timezone.utc)}
    await db.twitter_accounts.insert_one(doc)
    doc.pop("_id", None)
    return {"account": doc}


@router.patch("/social/twitter/accounts/{item_id}")
async def update_twitter_account(item_id: str, body: PatchBody):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    r = await db.twitter_accounts.update_one({"id": item_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"updated": True}


@router.delete("/social/twitter/accounts/{item_id}")
async def delete_twitter_account(item_id: str):
    r = await db.twitter_accounts.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.post("/social/twitter/accounts/{item_id}/fetch")
async def fetch_twitter_account_now(item_id: str):
    acc = await db.twitter_accounts.find_one({"id": item_id})
    if not acc:
        raise HTTPException(404, "Not found")
    from twitter_fetcher import fetch_user_tweets, _tweet_to_intel_item
    from ai_pipeline import classify_and_analyze_article
    handle = acc["handle"].lstrip("@")
    loop = asyncio.get_event_loop()
    tweets = await loop.run_in_executor(
        None, lambda: fetch_user_tweets(handle, acc["name"], acc.get("category", "general"), 10)
    )
    saved = 0
    for tw in tweets:
        if await db.twitter_feeds.find_one({"tweet_url": tw["tweet_url"]}):
            continue
        await db.twitter_feeds.insert_one(tw)
        if len(tw.get("tweet_text", "")) > 50:
            item = _tweet_to_intel_item(tw)
            try:
                analysis = await classify_and_analyze_article(tw["tweet_text"], f"Tweet: {acc['name']}")
                item.update(analysis)
            except Exception:
                item["processed"] = False
            await db.intelligence_items.insert_one(item)
        saved += 1
    return {"saved": saved, "handle": handle}


# ─────────────────────────────────────────────────────────────────────────────
# Twitter — searches
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/twitter/searches")
async def list_twitter_searches():
    items = await db.twitter_searches.find({}, {"_id": 0}).to_list(200)
    return {"searches": items, "count": len(items)}


@router.post("/social/twitter/searches", status_code=201)
async def add_twitter_search(body: TwitterSearchBody):
    if await db.twitter_searches.find_one({"query": body.query}):
        raise HTTPException(409, "Query already exists")
    doc = {"id": str(uuid.uuid4()), "query": body.query, "num_results": body.num_results,
           "active": body.active, "last_run": None, "created_at": datetime.now(timezone.utc)}
    await db.twitter_searches.insert_one(doc)
    doc.pop("_id", None)
    return {"search": doc}


@router.delete("/social/twitter/searches/{item_id}")
async def delete_twitter_search(item_id: str):
    r = await db.twitter_searches.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.post("/social/twitter/searches/{item_id}/fetch")
async def run_twitter_search_now(item_id: str):
    s = await db.twitter_searches.find_one({"id": item_id})
    if not s:
        raise HTTPException(404, "Not found")
    from twitter_fetcher import search_tweets_official, _tweet_to_intel_item
    from ai_pipeline import classify_and_analyze_article
    loop = asyncio.get_event_loop()
    tweets = await loop.run_in_executor(
        None, lambda: search_tweets_official(s["query"], s.get("num_results", 10))
    )
    saved = 0
    for tw in tweets:
        if await db.twitter_feeds.find_one({"tweet_url": tw["tweet_url"]}):
            continue
        await db.twitter_feeds.insert_one(tw)
        if len(tw.get("tweet_text", "")) > 50:
            item = _tweet_to_intel_item(tw)
            try:
                analysis = await classify_and_analyze_article(tw["tweet_text"], f"X search")
                item.update(analysis)
            except Exception:
                item["processed"] = False
            await db.intelligence_items.insert_one(item)
        saved += 1
    await db.twitter_searches.update_one({"id": item_id}, {"$set": {"last_run": datetime.now(timezone.utc)}})
    return {"saved": saved, "query": s["query"]}


# ─────────────────────────────────────────────────────────────────────────────
# YouTube — channels
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/youtube/channels")
async def list_youtube_channels():
    items = await db.youtube_channels.find({}, {"_id": 0}).sort("name", 1).to_list(200)
    return {"channels": items, "count": len(items)}


@router.post("/social/youtube/channels", status_code=201)
async def add_youtube_channel(body: YouTubeChannelBody):
    if await db.youtube_channels.find_one({"channel_id": body.channel_id}):
        raise HTTPException(409, "Channel already tracked")
    doc = {"id": str(uuid.uuid4()), "name": body.name, "channel_id": body.channel_id,
           "category": body.category, "active": body.active, "last_fetched": None,
           "created_at": datetime.now(timezone.utc)}
    await db.youtube_channels.insert_one(doc)
    doc.pop("_id", None)
    return {"channel": doc}


@router.patch("/social/youtube/channels/{item_id}")
async def update_youtube_channel(item_id: str, body: PatchBody):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    r = await db.youtube_channels.update_one({"id": item_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"updated": True}


@router.delete("/social/youtube/channels/{item_id}")
async def delete_youtube_channel(item_id: str):
    r = await db.youtube_channels.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.post("/social/youtube/channels/{item_id}/fetch")
async def fetch_youtube_channel_now(item_id: str):
    ch = await db.youtube_channels.find_one({"id": item_id})
    if not ch:
        raise HTTPException(404, "Not found")
    from youtube_fetcher import _search_youtube, _to_intel_item
    from ai_pipeline import classify_and_analyze_article
    loop = asyncio.get_event_loop()
    videos = await loop.run_in_executor(None, lambda: _search_youtube(channel_id=ch["channel_id"], max_results=5))
    saved = 0
    for v in videos:
        if await db.intelligence_items.find_one({"source_url": v["url"]}):
            continue
        item = _to_intel_item(v, "youtube_channel")
        try:
            analysis = await classify_and_analyze_article(item["raw_content"][:4000], item["title"])
            item.update(analysis)
        except Exception:
            item["processed"] = False
        await db.intelligence_items.insert_one(item)
        saved += 1
    await db.youtube_channels.update_one({"id": item_id}, {"$set": {"last_fetched": datetime.now(timezone.utc)}})
    return {"saved": saved, "channel": ch["name"]}


# ─────────────────────────────────────────────────────────────────────────────
# YouTube — searches
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/youtube/searches")
async def list_youtube_searches():
    items = await db.youtube_searches.find({}, {"_id": 0}).to_list(200)
    return {"searches": items, "count": len(items)}


@router.post("/social/youtube/searches", status_code=201)
async def add_youtube_search(body: YouTubeSearchBody):
    if await db.youtube_searches.find_one({"query": body.query}):
        raise HTTPException(409, "Query already exists")
    doc = {"id": str(uuid.uuid4()), "query": body.query, "max_results": body.max_results,
           "active": body.active, "last_run": None, "created_at": datetime.now(timezone.utc)}
    await db.youtube_searches.insert_one(doc)
    doc.pop("_id", None)
    return {"search": doc}


@router.delete("/social/youtube/searches/{item_id}")
async def delete_youtube_search(item_id: str):
    r = await db.youtube_searches.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# Facebook — pages
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/facebook/pages")
async def list_facebook_pages():
    items = await db.facebook_pages.find({}, {"_id": 0}).sort("name", 1).to_list(200)
    return {"pages": items, "count": len(items)}


@router.post("/social/facebook/pages", status_code=201)
async def add_facebook_page(body: FacebookPageBody):
    if await db.facebook_pages.find_one({"page_id": body.page_id}):
        raise HTTPException(409, "Page already tracked")
    doc = {"id": str(uuid.uuid4()), "name": body.name, "page_id": body.page_id,
           "category": body.category, "active": body.active, "last_fetched": None,
           "created_at": datetime.now(timezone.utc)}
    await db.facebook_pages.insert_one(doc)
    doc.pop("_id", None)
    return {"page": doc}


@router.patch("/social/facebook/pages/{item_id}")
async def update_facebook_page(item_id: str, body: PatchBody):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    r = await db.facebook_pages.update_one({"id": item_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"updated": True}


@router.delete("/social/facebook/pages/{item_id}")
async def delete_facebook_page(item_id: str):
    r = await db.facebook_pages.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.post("/social/facebook/pages/{item_id}/fetch")
async def fetch_facebook_page_now(item_id: str):
    page = await db.facebook_pages.find_one({"id": item_id})
    if not page:
        raise HTTPException(404, "Not found")
    from facebook_fetcher import fetch_page_posts_sync, _post_to_intel_item
    from ai_pipeline import classify_and_analyze_article
    loop = asyncio.get_event_loop()
    posts = await loop.run_in_executor(
        None, lambda: fetch_page_posts_sync(page["page_id"], page["name"], 10)
    )
    saved = 0
    for post in posts:
        if await db.intelligence_items.find_one({"source_url": post["url"]}):
            continue
        item = _post_to_intel_item(post)
        try:
            analysis = await classify_and_analyze_article(item["raw_content"][:4000], item["title"])
            item.update(analysis)
        except Exception:
            item["processed"] = False
        await db.intelligence_items.insert_one(item)
        saved += 1
    await db.facebook_pages.update_one({"id": item_id}, {"$set": {"last_fetched": datetime.now(timezone.utc)}})
    return {"saved": saved, "page": page["name"]}


# ─────────────────────────────────────────────────────────────────────────────
# Telegram — channels
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/telegram/channels")
async def list_telegram_channels():
    items = await db.telegram_channels.find({}, {"_id": 0}).sort("name", 1).to_list(200)
    return {"channels": items, "count": len(items)}


@router.post("/social/telegram/channels", status_code=201)
async def add_telegram_channel(body: TelegramChannelBody):
    username = body.username.lstrip("@")
    if await db.telegram_channels.find_one({"username": username}):
        raise HTTPException(409, "Channel already tracked")
    doc = {"id": str(uuid.uuid4()), "username": username, "name": body.name,
           "category": body.category, "active": body.active, "last_fetched": None,
           "created_at": datetime.now(timezone.utc)}
    await db.telegram_channels.insert_one(doc)
    doc.pop("_id", None)
    return {"channel": doc}


@router.patch("/social/telegram/channels/{item_id}")
async def update_telegram_channel(item_id: str, body: PatchBody):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    r = await db.telegram_channels.update_one({"id": item_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"updated": True}


@router.delete("/social/telegram/channels/{item_id}")
async def delete_telegram_channel(item_id: str):
    r = await db.telegram_channels.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.post("/social/telegram/channels/{item_id}/fetch")
async def fetch_telegram_channel_now(item_id: str):
    ch = await db.telegram_channels.find_one({"id": item_id})
    if not ch:
        raise HTTPException(404, "Not found")
    from telegram_fetcher import fetch_channel_messages, _msg_to_intel_item
    from ai_pipeline import classify_and_analyze_article
    username = ch["username"].lstrip("@")
    messages = await fetch_channel_messages(username, ch["name"], limit=20, since_hours=24)
    saved = 0
    for msg in messages:
        if await db.intelligence_items.find_one({"source_url": msg["url"]}):
            continue
        item = _msg_to_intel_item(msg)
        try:
            analysis = await classify_and_analyze_article(msg["text"][:4000], f"Telegram: {ch['name']}")
            item.update(analysis)
        except Exception:
            item["processed"] = False
        await db.intelligence_items.insert_one(item)
        saved += 1
    await db.telegram_channels.update_one({"id": item_id}, {"$set": {"last_fetched": datetime.now(timezone.utc)}})
    return {"saved": saved, "channel": ch["name"]}


# ─────────────────────────────────────────────────────────────────────────────
# Fetch all platforms at once (admin trigger)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/social/fetch-all")
async def fetch_all_social_now(background_tasks: BackgroundTasks):
    """
    Trigger all social/web fetchers.

    Strategy:
      1. Immediately stamp last_fetched = now on every active source document
         so the frontend scanner cards update on the very first poll (~10 s).
      2. Queue a background task that runs the actual network fetches in
         parallel and processes any new items through the AI pipeline.

    This decouples "user clicked Fetch" feedback from "fetch completed" and
    avoids Render's 30 s HTTP timeout killing slow sources like Telegram.
    """
    now = datetime.now(timezone.utc)

    # ── 1. Instant timestamp update (awaited before response) ─────────────────
    # Filter uses $ne False rather than == True so documents where the active
    # field is missing or stored as a non-bool truthy value are also matched.
    try:
        results = await asyncio.gather(
            db.youtube_channels.update_many({"active": {"$ne": False}}, {"$set": {"last_fetched": now}}),
            db.facebook_pages.update_many({"active": {"$ne": False}},   {"$set": {"last_fetched": now}}),
            db.telegram_channels.update_many({"active": {"$ne": False}}, {"$set": {"last_fetched": now}}),
            db.twitter_searches.update_many({"active": {"$ne": False}},  {"$set": {"last_run": now}}),
            db.web_sources.update_many({"active": {"$ne": False}},       {"$set": {"last_fetched": now}}),
            db.firecrawl_searches.update_many({"active": {"$ne": False}}, {"$set": {"last_run": now}}),
        )
        counts = [r.modified_count for r in results]
        labels = ["yt_ch", "fb_pg", "tg_ch", "tw_srch", "web_src", "fc_srch"]
        logger.info(f"fetch-all: timestamps written — {dict(zip(labels, counts))}")
    except Exception as e:
        logger.error(f"fetch-all: instant timestamp update failed: {e}")

    # ── 2. Background network fetches ─────────────────────────────────────────
    async def _run_all():
        try:
            from twitter_fetcher   import fetch_twitter_accounts, fetch_twitter_searches
            from youtube_fetcher   import fetch_youtube_channels, fetch_youtube_searches
            from facebook_fetcher  import fetch_facebook_pages
            from telegram_fetcher  import fetch_telegram_channels
            from firecrawl_fetcher import fetch_web_sources, run_keyword_searches

            coros  = [
                fetch_twitter_accounts(db),
                fetch_twitter_searches(db),
                fetch_youtube_channels(db),
                fetch_youtube_searches(db),
                fetch_facebook_pages(db),
                fetch_telegram_channels(db),
                fetch_web_sources(db),
                run_keyword_searches(db),
            ]
            labels = [
                "twitter_accounts", "twitter_searches",
                "youtube_channels", "youtube_searches",
                "facebook_pages",   "telegram_channels",
                "firecrawl_sites",  "firecrawl_searches",
            ]

            results = await asyncio.gather(*coros, return_exceptions=True)
            for label, result in zip(labels, results):
                if isinstance(result, Exception):
                    logger.error(f"fetch-all [{label}] error: {result}")
                else:
                    logger.info(f"fetch-all [{label}] ok → {result} new items")

        except Exception as e:
            logger.error(f"fetch-all _run_all crashed: {e}")

    background_tasks.add_task(_run_all)
    return {"status": "fetch started", "message": "Timestamps updated; content fetching in background"}
