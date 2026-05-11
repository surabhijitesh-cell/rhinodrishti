"""
YouTube Data API v3 fetcher for Rhino Drishti.

Monitors specific channels and keyword searches.
YOUTUBE_API_KEY must be set in .env (free, 10k quota/day from Google Cloud Console).
"""

import uuid
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL  = "https://www.googleapis.com/youtube/v3/videos"

# ── Default seeds ─────────────────────────────────────────────────────────────
DEFAULT_CHANNELS = [
    {"name": "DD News",              "channel_id": "UCF57zOiPKmFdIbJRiHyKGog", "category": "government"},
    {"name": "Doordarshan Northeast","channel_id": "UCmphdqZNmqL72bJ7oqZGFvA", "category": "government"},
    {"name": "Indian Army",          "channel_id": "UCXHlgFNJpPDJv3_6xJPUiIw", "category": "defense"},
    {"name": "Ministry of Defence",  "channel_id": "UC7kNS4blU2nk3OKC9U2CJHA", "category": "government"},
    {"name": "NDTV",                 "channel_id": "UCZFMm1mMw0F81Z37aaEzTUA", "category": "media"},
    {"name": "The Wire",             "channel_id": "UCVdmxHNNaFnAVrOXnUVR89Q", "category": "media"},
    {"name": "Republic World",       "channel_id": "UCKBbMhRRcqI3K3VdCRs16uw", "category": "media"},
    {"name": "EastMojo",             "channel_id": "UCTi6i8vfnCH3LZFB0L2d_JA", "category": "northeast"},
    {"name": "Northeast Live",       "channel_id": "UCl3FZF3qFqSCPPFeBcm7O4A", "category": "northeast"},
]

DEFAULT_SEARCHES = [
    {"query": "northeast india security insurgency",   "max_results": 5},
    {"query": "Manipur conflict ethnic violence",      "max_results": 5},
    {"query": "India Bangladesh border Assam",         "max_results": 5},
    {"query": "India Myanmar border security",         "max_results": 5},
    {"query": "China Arunachal Pradesh border",        "max_results": 5},
    {"query": "NSCN ULFA militant northeast",          "max_results": 3},
    {"query": "Brahmaputra floods infrastructure",     "max_results": 3},
]


def _api_key() -> str:
    return os.environ.get("YOUTUBE_API_KEY", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Core API helpers (synchronous — run via executor)
# ─────────────────────────────────────────────────────────────────────────────

def _search_youtube(query: str = None, channel_id: str = None,
                    max_results: int = 5) -> list:
    key = _api_key()
    if not key:
        logger.warning("YOUTUBE_API_KEY not set — YouTube disabled")
        return []

    params = {
        "part":       "snippet",
        "type":       "video",
        "order":      "date",
        "maxResults": max_results,
        "key":        key,
    }
    if query:
        params["q"] = query
    if channel_id:
        params["channelId"] = channel_id

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(YOUTUBE_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = []
        for item in data.get("items", []):
            snippet    = item.get("snippet", {})
            video_id   = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            items.append({
                "video_id":     video_id,
                "title":        snippet.get("title", ""),
                "description":  snippet.get("description", ""),
                "channel_name": snippet.get("channelTitle", ""),
                "channel_id":   snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                "url":          f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail":    snippet.get("thumbnails", {}).get("default", {}).get("url"),
            })
        return items
    except Exception as e:
        logger.error(f"YouTube API error (query='{query}', channel={channel_id}): {e}")
        return []


def _to_intel_item(video: dict, source_type: str = "youtube",
                   search_query: str = None) -> dict:
    from firecrawl_fetcher import _base_item
    content = f"{video['title']}\n\n{video['description']}"
    raw = {
        "title":        video["title"],
        "raw_content":  content,
        "source":       video.get("channel_name", "YouTube"),
        "source_url":   video["url"],
        "source_type":  source_type,
        "published_at": video.get("published_at", datetime.now(timezone.utc).isoformat()),
    }
    item = _base_item(raw)
    if search_query:
        item["search_query"] = search_query
    item["video_id"] = video.get("video_id")
    return item


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled jobs
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_youtube_channels(db) -> int:
    from ai_pipeline import classify_and_analyze_article

    channels = await db.youtube_channels.find({"active": True}).to_list(100)
    if not channels:
        return 0

    saved = 0
    for ch in channels:
        channel_id = ch.get("channel_id")
        if not channel_id:
            continue

        loop = asyncio.get_event_loop()
        videos = await loop.run_in_executor(
            None, lambda cid=channel_id: _search_youtube(channel_id=cid, max_results=5)
        )

        for v in videos:
            existing = await db.intelligence_items.find_one({"source_url": v["url"]})
            if existing:
                continue

            item = _to_intel_item(v, source_type="youtube_channel")
            if len(item["raw_content"].strip()) < 30:
                continue
            try:
                analysis = await classify_and_analyze_article(
                    item["raw_content"][:4000], item["title"]
                )
                item.update(analysis)
            except Exception as e:
                logger.error(f"AI analysis failed for YouTube video {v['url']}: {e}")
                item["processed"] = False

            await db.intelligence_items.insert_one(item)
            saved += 1

        await db.youtube_channels.update_one(
            {"_id": ch["_id"]},
            {"$set": {"last_fetched": datetime.now(timezone.utc)}}
        )

    logger.info(f"fetch_youtube_channels: {saved} new items from {len(channels)} channels")
    return saved


async def fetch_youtube_searches(db) -> int:
    from ai_pipeline import classify_and_analyze_article
    from keyword_engine import get_top_keywords_for_search

    # 1. Manually-configured searches (user added via Settings UI)
    manual = await db.youtube_searches.find({"active": True}).to_list(100)
    queries = [(s.get("query"), s.get("max_results", 5), s.get("_id"), False)
               for s in manual if s.get("query")]

    # 2. Top keywords from the dynamic keyword bank
    bank_keywords = await get_top_keywords_for_search(db, limit=10, min_score=40)
    seen = {q[0].lower() for q in queries}
    for kw in bank_keywords:
        if kw.lower() not in seen:
            queries.append((kw, 3, None, True))  # 3 results per bank query, no _id
            seen.add(kw.lower())

    if not queries:
        return 0

    logger.info(f"YouTube searches: {len(manual)} manual + {len(bank_keywords)} from bank "
                f"= {len(queries)} unique queries")

    saved = 0
    for query, max_results, doc_id, is_bank in queries:
        loop = asyncio.get_event_loop()
        videos = await loop.run_in_executor(
            None, lambda q=query, n=max_results: _search_youtube(query=q, max_results=n)
        )

        for v in videos:
            existing = await db.intelligence_items.find_one({"source_url": v["url"]})
            if existing:
                continue

            item = _to_intel_item(v, source_type="youtube_search", search_query=query)
            if len(item["raw_content"].strip()) < 30:
                continue
            try:
                analysis = await classify_and_analyze_article(
                    item["raw_content"][:4000], item["title"]
                )
                item.update(analysis)
            except Exception as e:
                item["processed"] = False

            await db.intelligence_items.insert_one(item)
            saved += 1

        # Only stamp last_run on manually-configured searches that have a doc id
        if doc_id is not None:
            await db.youtube_searches.update_one(
                {"_id": doc_id},
                {"$set": {"last_run": datetime.now(timezone.utc)}}
            )

    logger.info(f"fetch_youtube_searches: {saved} new items from {len(queries)} queries")
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Seed defaults
# ─────────────────────────────────────────────────────────────────────────────

async def seed_youtube_defaults(db) -> None:
    if await db.youtube_channels.count_documents({}) == 0:
        docs = [
            {
                "id":         str(uuid.uuid4()),
                "name":       c["name"],
                "channel_id": c["channel_id"],
                "category":   c["category"],
                "active":     True,
                "last_fetched": None,
                "created_at": datetime.now(timezone.utc),
            }
            for c in DEFAULT_CHANNELS
        ]
        await db.youtube_channels.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default YouTube channels")

    if await db.youtube_searches.count_documents({}) == 0:
        docs = [
            {
                "id":          str(uuid.uuid4()),
                "query":       s["query"],
                "max_results": s["max_results"],
                "active":      True,
                "last_run":    None,
                "created_at":  datetime.now(timezone.utc),
            }
            for s in DEFAULT_SEARCHES
        ]
        await db.youtube_searches.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default YouTube searches")
