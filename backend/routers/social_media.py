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
from datetime import datetime, timezone, timedelta
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

class TwitterListBody(BaseModel):
    list_id: str          # numeric id from x.com URL, e.g. /i/lists/1234567890
    name: str             # human-readable name
    max_results: int = 50
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

    # Fetch item counts per source from DB
    now_utc = datetime.now(timezone.utc)
    cutoff  = (now_utc - timedelta(days=30)).isoformat()

    async def _count(src_prefix: str) -> int:
        return await db.intelligence_items.count_documents({
            "source_type": {"$regex": f"^{src_prefix}", "$options": "i"},
            "published_at": {"$gte": cutoff},
        })

    twitter_count   = await db.twitter_feeds.count_documents({})
    youtube_count   = await _count("youtube")
    facebook_count  = await _count("facebook")
    telegram_count  = await _count("telegram")
    firecrawl_count = await _count("firecrawl")
    intel_twitter_count = await _count("twitter")

    return {
        "twitter": {
            "configured": twitter_configured,
            "available":  twitter_configured,
            "item_count": twitter_count,
            "intel_count": intel_twitter_count,
            "free_tier": twitter_configured and twitter_count == 0,
            "note": (
                "⚠ TWITTER_BEARER_TOKEN not set. Add it to Render environment variables."
            ) if not twitter_configured else (
                "⚠ Free API tier — your Bearer Token is set but no tweets have been collected. "
                "X/Twitter API v2 requires the Basic plan ($100/month) to read public tweets. "
                "Free tier tokens can only post, not read. "
                "Upgrade at developer.x.com/en/portal/dashboard to enable data collection."
            ) if twitter_count == 0 else (
                f"✓ X API active — {twitter_count} raw tweets cached, {intel_twitter_count} in intel feed (30d)."
            ),
        },
        "youtube": {
            "configured": youtube_configured,
            "available":  youtube_configured,
            "item_count": youtube_count,
            "note": "YouTube Data API v3 (free, 10k quota/day). Set YOUTUBE_API_KEY."
            if not youtube_configured else f"YouTube Data API v3 active. {youtube_count} items (30d).",
        },
        "facebook": {
            "configured": facebook_configured,
            "available":  facebook_configured,
            "item_count": facebook_count,
            "note": (
                "⚠ Facebook Graph API client-credentials access token NO LONGER "
                "allows reading page posts as of 2018 API changes. Each page must "
                "grant your app a Page Access Token via Meta Business Suite. "
                "Set FACEBOOK_PAGE_TOKEN_<PAGE_ID> per page, or use the Firecrawl "
                "source instead to scrape public FB pages."
            ) if not facebook_configured else (
                f"Graph API credentials set. {facebook_count} items saved (30d). "
                "⚠ If count is 0, pages likely need per-page access tokens — see FACEBOOK_PAGE_TOKEN_<PAGE_ID>."
            ),
        },
        "telegram": {
            "configured": tg_ok(),
            "available":  tg_ok(),
            "item_count": telegram_count,
            "note": "Telethon user session — run telegram_setup.py once to generate session."
            if not tg_ok() else f"Telethon session active. {telegram_count} items (30d).",
        },
        "firecrawl": {
            "configured": firecrawl_configured,
            "available":  firecrawl_configured,
            "item_count": firecrawl_count,
            "note": "Firecrawl SaaS — set FIRECRAWL_API_KEY."
            if not firecrawl_configured else (
                f"Firecrawl active. {firecrawl_count} items (30d). "
                "Web sources: each homepage scraped once (dedup by URL); keyword searches add fresh items every 6h."
            ),
        },
    }


@router.post("/social/test-connections")
async def test_social_connections():
    """
    Actually test each API connection live — not just check if keys are set.
    Returns ok/error/warning per platform with actionable messages.
    """
    import os, asyncio

    results = {}

    # ── Twitter ──────────────────────────────────────────────────────────────
    token = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
    if not token:
        results["twitter"] = {"status": "not_configured", "message": "TWITTER_BEARER_TOKEN not set"}
    else:
        try:
            import tweepy
            loop = asyncio.get_running_loop()
            def _test_twitter():
                c = tweepy.Client(bearer_token=token, wait_on_rate_limit=False)
                # search_recent_tweets with a simple query — fails on Free tier
                resp = c.search_recent_tweets(
                    query="india",
                    max_results=10,
                    tweet_fields=["created_at"],
                )
                return resp
            resp = await loop.run_in_executor(None, _test_twitter)
            count = len(resp.data or [])
            results["twitter"] = {"status": "ok", "message": f"Connected — returned {count} tweets"}
        except Exception as e:
            err = str(e)
            if "403" in err or "Read" in err or "Forbidden" in err or "unauthorized" in err.lower():
                results["twitter"] = {
                    "status": "auth_error",
                    "message": (
                        "401/403 from X API — your Bearer Token is likely a FREE tier key. "
                        "Free tier only allows posting (no tweet reads). "
                        "Upgrade to X API Basic ($100/mo) to fetch tweets."
                    )
                }
            elif "429" in err or "rate" in err.lower():
                results["twitter"] = {"status": "rate_limited", "message": f"Rate limited: {err}"}
            else:
                results["twitter"] = {"status": "error", "message": err[:200]}

    # ── YouTube ──────────────────────────────────────────────────────────────
    yt_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not yt_key:
        results["youtube"] = {"status": "not_configured", "message": "YOUTUBE_API_KEY not set"}
    else:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as hc:
                r = await hc.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={"key": yt_key, "id": "dQw4w9WgXcQ", "part": "id"},
                )
            if r.status_code == 200:
                results["youtube"] = {"status": "ok", "message": "Connected — YouTube Data API v3 active"}
            elif r.status_code == 403:
                results["youtube"] = {"status": "auth_error", "message": f"403 Forbidden — key may be restricted or quota exceeded. Response: {r.text[:200]}"}
            else:
                results["youtube"] = {"status": "error", "message": f"HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            results["youtube"] = {"status": "error", "message": str(e)[:200]}

    # ── Facebook ─────────────────────────────────────────────────────────────
    fb_id     = os.environ.get("FACEBOOK_APP_ID", "").strip()
    fb_secret = os.environ.get("FACEBOOK_APP_SECRET", "").strip()
    if not fb_id or not fb_secret:
        results["facebook"] = {"status": "not_configured", "message": "FACEBOOK_APP_ID or FACEBOOK_APP_SECRET not set"}
    else:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as hc:
                r = await hc.get(
                    "https://graph.facebook.com/v19.0/oauth/access_token",
                    params={"client_id": fb_id, "client_secret": fb_secret, "grant_type": "client_credentials"},
                )
            data = r.json()
            if "access_token" in data:
                # Try reading a known public page to test if posts are accessible
                token_val = data["access_token"]
                async with httpx.AsyncClient(timeout=8) as hc:
                    r2 = await hc.get(
                        "https://graph.facebook.com/v19.0/IndianArmy.adgpi/posts",
                        params={"fields": "id,message", "limit": 1, "access_token": token_val},
                    )
                d2 = r2.json()
                if r2.status_code == 200 and "data" in d2:
                    count = len(d2.get("data", []))
                    if count > 0:
                        results["facebook"] = {"status": "ok", "message": f"Connected — app token works, got {count} posts from test page"}
                    else:
                        results["facebook"] = {
                            "status": "warning",
                            "message": (
                                "App token obtained but test page returned 0 posts. "
                                "Meta now requires Page Access Tokens (not app tokens) to read posts. "
                                "Set FACEBOOK_PAGE_TOKEN_<PAGE_ID> per page in your environment."
                            )
                        }
                else:
                    err_msg = d2.get("error", {}).get("message", r2.text[:200])
                    results["facebook"] = {
                        "status": "warning",
                        "message": (
                            f"App token OK but page read failed: {err_msg}. "
                            "Meta restricts post access — set FACEBOOK_PAGE_TOKEN_<PAGE_ID> per page."
                        )
                    }
            else:
                results["facebook"] = {"status": "auth_error", "message": f"Token exchange failed: {data.get('error', {}).get('message', str(data)[:200])}"}
        except Exception as e:
            results["facebook"] = {"status": "error", "message": str(e)[:200]}

    # ── Firecrawl ────────────────────────────────────────────────────────────
    fc_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not fc_key:
        results["firecrawl"] = {"status": "not_configured", "message": "FIRECRAWL_API_KEY not set"}
    else:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as hc:
                r = await hc.get(
                    "https://api.firecrawl.dev/v1/team/usage",
                    headers={"Authorization": f"Bearer {fc_key}"},
                )
            if r.status_code == 200:
                usage = r.json()
                credits_used = usage.get("creditsUsed", usage.get("credits_used", "?"))
                credits_total = usage.get("totalCredits", usage.get("total_credits", "?"))
                results["firecrawl"] = {"status": "ok", "message": f"Connected — credits used: {credits_used}/{credits_total}"}
            elif r.status_code == 401:
                results["firecrawl"] = {"status": "auth_error", "message": "401 Unauthorized — FIRECRAWL_API_KEY is invalid"}
            else:
                results["firecrawl"] = {"status": "warning", "message": f"Status endpoint returned {r.status_code} — key may be valid but usage check failed"}
        except Exception as e:
            results["firecrawl"] = {"status": "error", "message": str(e)[:200]}

    # ── Telegram ─────────────────────────────────────────────────────────────
    from telegram_fetcher import _is_configured as tg_ok
    results["telegram"] = {
        "status": "ok" if tg_ok() else "not_configured",
        "message": "Telethon session file present" if tg_ok() else "No Telethon session — run telegram_setup.py on the server",
    }

    return {"results": results}


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
    loop = asyncio.get_running_loop()
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
    loop = asyncio.get_running_loop()
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
# Twitter — lists (free-tier friendly: 1 call → many accounts)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/twitter/lists")
async def list_twitter_lists():
    items = await db.twitter_lists.find({}, {"_id": 0}).sort("name", 1).to_list(100)
    return {"lists": items, "count": len(items)}


@router.post("/social/twitter/lists", status_code=201)
async def add_twitter_list(body: TwitterListBody):
    if await db.twitter_lists.find_one({"list_id": body.list_id}):
        raise HTTPException(409, "List already tracked")
    doc = {"id": str(uuid.uuid4()), "list_id": body.list_id, "name": body.name,
           "max_results": body.max_results, "active": body.active,
           "last_fetched": None, "created_at": datetime.now(timezone.utc)}
    await db.twitter_lists.insert_one(doc)
    doc.pop("_id", None)
    return {"list": doc}


@router.delete("/social/twitter/lists/{item_id}")
async def delete_twitter_list(item_id: str):
    r = await db.twitter_lists.delete_one({"id": item_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.post("/social/twitter/lists/{item_id}/fetch")
async def fetch_twitter_list_now(item_id: str):
    lst = await db.twitter_lists.find_one({"id": item_id})
    if not lst:
        raise HTTPException(404, "Not found")
    from twitter_fetcher import fetch_list_tweets_official, _tweet_to_intel_item
    from ai_pipeline import classify_and_analyze_article

    list_id   = lst["list_id"]
    list_name = lst["name"]
    loop = asyncio.get_running_loop()
    tweets = await loop.run_in_executor(
        None, lambda: fetch_list_tweets_official(list_id, list_name, lst.get("max_results", 50))
    )
    saved = 0
    for tw in tweets:
        if await db.twitter_feeds.find_one({"tweet_url": tw["tweet_url"]}):
            continue
        await db.twitter_feeds.insert_one(tw)
        if len(tw.get("tweet_text", "")) > 50:
            item = _tweet_to_intel_item(tw)
            try:
                analysis = await classify_and_analyze_article(tw["tweet_text"], f"X List: {list_name}")
                item.update(analysis)
            except Exception:
                item["processed"] = False
            await db.intelligence_items.insert_one(item)
        saved += 1
    await db.twitter_lists.update_one({"id": item_id}, {"$set": {"last_fetched": datetime.now(timezone.utc)}})
    return {"saved": saved, "list": list_name}


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
    loop = asyncio.get_running_loop()
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
    loop = asyncio.get_running_loop()
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
            db.twitter_lists.update_many({"active": {"$ne": False}},     {"$set": {"last_fetched": now}}),
            db.web_sources.update_many({"active": {"$ne": False}},       {"$set": {"last_fetched": now}}),
            db.firecrawl_searches.update_many({"active": {"$ne": False}}, {"$set": {"last_run": now}}),
        )
        counts = [r.modified_count for r in results]
        labels = ["yt_ch", "fb_pg", "tg_ch", "tw_srch", "tw_lists", "web_src", "fc_srch"]
        logger.info(f"fetch-all: timestamps written — {dict(zip(labels, counts))}")
    except Exception as e:
        logger.error(f"fetch-all: instant timestamp update failed: {e}")

    # ── 2. Background network fetches ─────────────────────────────────────────
    async def _run_all():
        try:
            from twitter_fetcher   import fetch_twitter_accounts, fetch_twitter_searches, fetch_twitter_lists
            from youtube_fetcher   import fetch_youtube_channels, fetch_youtube_searches
            from facebook_fetcher  import fetch_facebook_pages
            from telegram_fetcher  import fetch_telegram_channels
            from firecrawl_fetcher import fetch_web_sources, run_keyword_searches

            coros  = [
                fetch_twitter_accounts(db),
                fetch_twitter_searches(db),
                fetch_twitter_lists(db),
                fetch_youtube_channels(db),
                fetch_youtube_searches(db),
                fetch_facebook_pages(db),
                fetch_telegram_channels(db),
                fetch_web_sources(db),
                run_keyword_searches(db),
            ]
            labels = [
                "twitter_accounts", "twitter_searches", "twitter_lists",
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
