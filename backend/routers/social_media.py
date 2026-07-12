"""
Unified Social Media management router.

Covers: YouTube, Telegram (working), Apify-based Instagram/Facebook/Twitter
(see apify_social_fetcher.py). Each platform has:
  GET    /api/social/{platform}           — list sources
  POST   /api/social/{platform}           — add source
  PATCH  /api/social/{platform}/{id}      — update / toggle active
  DELETE /api/social/{platform}/{id}      — remove
  POST   /api/social/{platform}/{id}/fetch — on-demand fetch

GET /api/social/status   — configured status of all platforms
POST /api/social/fetch-all — trigger all platforms now (admin use)

NOTE: the official-API Twitter and Facebook fetchers (twitter_fetcher.py,
facebook_fetcher.py) were removed — both failed completely on cost/access
grounds and never produced usable data. Instagram/Facebook/Twitter are now
served by apify_social_fetcher.py — see /social/apify/* below.
"""

import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from shared import db, logger
from utils.auth import require_admin_role
import apify_social_fetcher

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class YouTubeChannelBody(BaseModel):
    name: str
    channel_id: str
    category: str = "media"
    active: bool = True

class YouTubeSearchBody(BaseModel):
    query: str
    max_results: int = 5
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

class SocialFetchModeBody(BaseModel):
    mode: str  # "throttled" | "firehose"


# ─────────────────────────────────────────────────────────────────────────────
# Status endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/status")
async def social_status():
    import os
    from telegram_fetcher import _is_configured as tg_ok

    youtube_configured  = bool(os.environ.get("YOUTUBE_API_KEY", "").strip())
    firecrawl_configured = bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())

    # Fetch item counts per source from DB
    now_utc = datetime.now(timezone.utc)
    cutoff  = (now_utc - timedelta(days=30)).isoformat()

    async def _count(src_prefix: str) -> int:
        return await db.intelligence_items.count_documents({
            "source_type": {"$regex": f"^{src_prefix}", "$options": "i"},
            "published_at": {"$gte": cutoff},
        })

    youtube_count   = await _count("youtube")
    telegram_count  = await _count("telegram")
    firecrawl_count = await _count("firecrawl")

    return {
        "twitter": {
            "configured": False,
            "available": False,
            "item_count": 0,
            "note": "Removed — official X API fetcher failed completely (cost/access). "
                    "Replaced by Apify-based scraping, see /social/apify/status.",
        },
        "youtube": {
            "configured": youtube_configured,
            "available":  youtube_configured,
            "item_count": youtube_count,
            "note": "YouTube Data API v3 (free, 10k quota/day). Set YOUTUBE_API_KEY."
            if not youtube_configured else f"YouTube Data API v3 active. {youtube_count} items (30d).",
        },
        "facebook": {
            "configured": False,
            "available": False,
            "item_count": 0,
            "note": "Removed — official Graph API fetcher failed completely (page-token access "
                    "restrictions). Replaced by Apify-based scraping, see /social/apify/status.",
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

    # ── Twitter ────────────────────────────────────────────────────────────
    # Official X API fetcher removed (failed completely). Twitter is now
    # served via Apify — see /social/apify/status for its connection test.
    results["twitter"] = {
        "status": "removed",
        "message": "Official API fetcher removed. See /social/apify/status for the Apify-based source.",
    }

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
    # Official Graph API fetcher removed (failed completely). Facebook is now
    # served via Apify — see /social/apify/status for its connection test.
    results["facebook"] = {
        "status": "removed",
        "message": "Official API fetcher removed. See /social/apify/status for the Apify-based source.",
    }

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
    username = ch["username"].lstrip("@")
    messages = await fetch_channel_messages(username, ch["name"], limit=20, since_hours=24)
    saved = 0
    for msg in messages:
        if await db.intelligence_items.find_one({"source_url": msg["url"]}):
            continue
        # Queue for filter pipeline — do NOT call Haiku inline here
        item = _msg_to_intel_item(msg)
        item["processed"] = False
        await db.intelligence_items.insert_one(item)
        saved += 1
    await db.telegram_channels.update_one({"id": item_id}, {"$set": {"last_fetched": datetime.now(timezone.utc)}})
    return {"saved": saved, "queued": saved, "channel": ch["name"]}


@router.post("/social/telegram/reconnect")
async def telegram_reconnect():
    """
    Admin endpoint: reset the Telegram singleton client and force reconnect.
    Use this after AuthKeyDuplicatedError (IP conflict) or after updating
    TELEGRAM_SESSION_STRING in Render env vars.
    Does NOT require a server restart.
    """
    from telegram_fetcher import _reset_client, _get_or_create_client, _is_configured
    if not _is_configured():
        raise HTTPException(400, "Telegram not configured — set env vars first")
    await _reset_client()
    try:
        await _get_or_create_client()
        return {"status": "reconnected", "message": "Telegram client reset and reconnected successfully"}
    except RuntimeError as e:
        raise HTTPException(502, f"Reconnect failed: {e}")


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
            db.telegram_channels.update_many({"active": {"$ne": False}}, {"$set": {"last_fetched": now}}),
            db.web_sources.update_many({"active": {"$ne": False}},       {"$set": {"last_fetched": now}}),
            db.firecrawl_searches.update_many({"active": {"$ne": False}}, {"$set": {"last_run": now}}),
        )
        counts = [r.modified_count for r in results]
        labels = ["yt_ch", "tg_ch", "web_src", "fc_srch"]
        logger.info(f"fetch-all: timestamps written — {dict(zip(labels, counts))}")
    except Exception as e:
        logger.error(f"fetch-all: instant timestamp update failed: {e}")

    # ── 2. Background network fetches ─────────────────────────────────────────
    async def _run_all():
        try:
            from youtube_fetcher   import fetch_youtube_channels, fetch_youtube_searches
            from telegram_fetcher  import fetch_telegram_channels
            from firecrawl_fetcher import fetch_web_sources, run_keyword_searches

            coros  = [
                fetch_youtube_channels(db),
                fetch_youtube_searches(db),
                fetch_telegram_channels(db),
                fetch_web_sources(db),
                run_keyword_searches(db),
                apify_social_fetcher.run_social_fetch(db),
            ]
            labels = [
                "youtube_channels", "youtube_searches",
                "telegram_channels",
                "firecrawl_sites",  "firecrawl_searches",
                "apify_social",
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


# ─────────────────────────────────────────────────────────────────────────────
# Apify — Instagram / Facebook / Twitter (replaces the removed official-API
# fetchers). Volume mode (throttled default / firehose) is admin-toggled from
# API & Pipeline Monitor and takes effect on the next scheduler tick — no
# redeploy needed.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/social/apify/status")
async def apify_social_status():
    configured = apify_social_fetcher.is_configured()
    mode = await apify_social_fetcher.get_fetch_mode(db)
    doc = await db.app_settings.find_one({"id": "social_fetch"}, {"_id": 0})
    counts = {
        "instagram": await db.social_posts.count_documents({"platform": "instagram"}),
        "facebook":  await db.social_posts.count_documents({"platform": "facebook"}),
        "twitter":   await db.social_posts.count_documents({"platform": "twitter"}),
    }
    return {
        "configured": configured,
        "mode": mode,
        "last_run": (doc or {}).get("last_run"),
        "last_run_counts": (doc or {}).get("last_run_counts"),
        "total_counts": counts,
        "note": "APIFY_TOKEN not set — add it to Render environment variables."
        if not configured else f"Apify configured. Mode: {mode}.",
    }


@router.get("/social/apify/mode")
async def get_apify_fetch_mode():
    return {"mode": await apify_social_fetcher.get_fetch_mode(db)}


@router.put("/social/apify/mode")
async def set_apify_fetch_mode(body: SocialFetchModeBody, admin: dict = Depends(require_admin_role)):
    if body.mode not in apify_social_fetcher.FETCH_CONFIG:
        raise HTTPException(400, f"mode must be one of {list(apify_social_fetcher.FETCH_CONFIG)}")
    result = await apify_social_fetcher.set_fetch_mode(db, body.mode)
    logger.info(f"Social fetch mode set to {body.mode} by {admin.get('username')}")
    return result


@router.post("/social/apify/fetch-now")
async def apify_fetch_now(background_tasks: BackgroundTasks, admin: dict = Depends(require_admin_role)):
    """Manual trigger — bypasses the interval gate (force=True) so an admin
    can test immediately after setting APIFY_TOKEN, regardless of mode."""
    if not apify_social_fetcher.is_configured():
        raise HTTPException(400, "APIFY_TOKEN not set — add it to Render environment variables first")

    async def _run():
        result = await apify_social_fetcher.run_social_fetch(db, force=True)
        logger.info(f"Apify manual fetch: {result}")

    background_tasks.add_task(_run)
    return {"status": "fetch started", "message": "Running in background — check /social/apify/status shortly"}


@router.post("/social/apify/backfill-comments/{platform}")
async def apify_backfill_comments(platform: str, background_tasks: BackgroundTasks, admin: dict = Depends(require_admin_role)):
    """One-time (idempotent) sweep: attach comment_sentiment to existing
    items of the given platform (facebook | instagram | twitter) that don't
    have it yet. Safe to re-run — only touches docs missing the field."""
    if platform not in ("facebook", "instagram", "twitter", "youtube"):
        raise HTTPException(400, "platform must be one of facebook, instagram, twitter, youtube")
    if platform != "youtube" and not apify_social_fetcher.is_configured():
        raise HTTPException(400, "APIFY_TOKEN not set — add it to Render environment variables first")

    async def _run():
        from social_comment_sentiment import backfill_comment_sentiment
        result = await backfill_comment_sentiment(db, platform)
        logger.info(f"{platform} comment sentiment backfill: {result}")

    background_tasks.add_task(_run)
    return {"status": "backfill started", "platform": platform, "message": "Running in background"}


@router.get("/social/sentiment-pulse")
async def social_sentiment_pulse():
    """Live aggregate of comment_sentiment per platform, plus a combined
    figure across all of them — backs the Dashboard's per-card pulse badges
    and the combined Social Pulse indicator. Cheap: averages an existing
    field, no new scraping."""
    source_type_by_platform = {
        "facebook":  "facebook_apify",
        "instagram": "instagram_apify",
        "twitter":   "twitter_apify",
        "youtube":   {"$regex": "^youtube"},
    }
    pulse = {}
    all_scores = []
    for platform, source_type in source_type_by_platform.items():
        items = await db.intelligence_items.find(
            {"source_type": source_type, "comment_sentiment": {"$exists": True}},
            {"_id": 0, "comment_sentiment": 1},
        ).to_list(500)
        if not items:
            pulse[platform] = None
            continue
        pos = round(sum(it["comment_sentiment"].get("positive_pct", 0) for it in items) / len(items))
        neg = round(sum(it["comment_sentiment"].get("negative_pct", 0) for it in items) / len(items))
        pulse[platform] = {"positive_pct": pos, "negative_pct": neg, "post_count": len(items)}
        all_scores.extend(items)

    if all_scores:
        pulse["combined"] = {
            "positive_pct": round(sum(it["comment_sentiment"].get("positive_pct", 0) for it in all_scores) / len(all_scores)),
            "negative_pct": round(sum(it["comment_sentiment"].get("negative_pct", 0) for it in all_scores) / len(all_scores)),
            "post_count": len(all_scores),
        }
    else:
        pulse["combined"] = None

    return pulse
