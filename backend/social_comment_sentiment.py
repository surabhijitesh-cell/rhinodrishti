"""
Real per-post comment/reply sentiment — Facebook, Instagram, Twitter, YouTube.
One shared module (was Facebook-only; generalized 2026-07-12 when Twitter/
Instagram reached feature parity; YouTube added same day).

Facebook/Instagram/Twitter each need a SEPARATE Apify actor from their
post-scraper (post scrapers only return counts, not text) — verified live
for all three before building this, never assumed:
  Facebook:  apify/facebook-comments-scraper    startUrls=[{"url":..}]  field "text"
  Instagram: apify/instagram-comment-scraper    directUrls=[url,...]   field "text"
  Twitter:   scraper_one/x-post-replies-scraper postUrls=[url,...]     field "replyText"
YouTube uses the native (free) commentThreads.list endpoint on the same
YOUTUBE_API_KEY youtube_fetcher.py already has — no Apify actor, no extra
cost. Verified live with a real video id before building this.

Non-fatal by design: any failure here must not block the post itself from
being ingested — comment_sentiment is an enrichment, not a gate.
"""
import json
import logging
import os

import httpx

from apify_social_fetcher import _run_actor
from llm_client import get_client, MODEL

logger = logging.getLogger(__name__)

MAX_COMMENTS_PER_POST = 20

PLATFORM_CONFIG = {
    "facebook": {
        "actor": "apify/facebook-comments-scraper",
        "url_param": "startUrls",
        "wrap_url": True,
        "text_field": "text",
    },
    "instagram": {
        "actor": "apify/instagram-comment-scraper",
        "url_param": "directUrls",
        "wrap_url": False,
        "text_field": "text",
    },
    "twitter": {
        "actor": "scraper_one/x-post-replies-scraper",
        "url_param": "postUrls",
        "wrap_url": False,
        "text_field": "replyText",
    },
}

YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


async def fetch_youtube_comments(video_id: str, max_comments: int = MAX_COMMENTS_PER_POST) -> list[str]:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        return []
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(YOUTUBE_COMMENT_THREADS_URL, params={
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(max_comments, 100),
            "key": api_key,
        })
        resp.raise_for_status()
        data = resp.json()
    return [
        item["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
        for item in data.get("items", [])
    ]

SENTIMENT_PROMPT = """You are analyzing public sentiment in social media comments on a \
North East India security/current-affairs post. Given the comment texts below, estimate \
what percentage express positive/supportive sentiment vs negative/critical/angry sentiment \
toward the situation described. Ignore off-topic or spam comments when judging tone, but \
still count them in sample_size.

Respond with ONLY a JSON object:
{"positive_pct": <0-100 int>, "negative_pct": <0-100 int>, "sample_size": <int>}

positive_pct + negative_pct need not sum to 100 (neutral comments make up the rest)."""


async def fetch_post_comments(platform: str, identifier: str, max_comments: int = MAX_COMMENTS_PER_POST) -> list[str]:
    """identifier is a post URL for facebook/instagram/twitter, a video_id for youtube."""
    if platform == "youtube":
        return await fetch_youtube_comments(identifier, max_comments)
    cfg = PLATFORM_CONFIG[platform]
    url_value = [{"url": identifier}] if cfg["wrap_url"] else [identifier]
    raw = await _run_actor(cfg["actor"], {cfg["url_param"]: url_value, "resultsLimit": max_comments})
    return [c[cfg["text_field"]] for c in raw if c.get(cfg["text_field"])]


async def score_comment_sentiment(comments: list[str]) -> dict | None:
    if not comments:
        return None
    client = get_client()
    joined = "\n".join(f"- {c[:300]}" for c in comments[:MAX_COMMENTS_PER_POST])
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=200,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SENTIMENT_PROMPT},
            {"role": "user", "content": joined},
        ],
    )
    text = response.choices[0].message.content or ""
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    result = json.loads(text[start:end])
    if not isinstance(result, dict):
        return None
    return result


async def analyze_comments(platform: str, identifier: str, comment_count: int = 1) -> dict | None:
    """Best-effort: returns None on any failure so callers can skip the tag.
    comment_count gates the paid Apify platforms (skip when 0, save the
    call) — YouTube's commentThreads is free, so it always attempts."""
    if not identifier:
        return None
    if platform != "youtube" and comment_count <= 0:
        return None
    try:
        comments = await fetch_post_comments(platform, identifier)
        return await score_comment_sentiment(comments)
    except Exception as e:
        logger.warning(f"{platform} comment sentiment failed for {identifier}: {e}")
        return None


MAX_BACKFILL_PER_CALL = 20  # bounds runtime — call again to keep sweeping the backlog


async def backfill_comment_sentiment(db, platform: str) -> dict:
    """Idempotent sweep for a given platform's source_type — safe to re-run,
    only touches docs missing comment_sentiment. Capped per call (each
    lookup is a slow Apify + LLM call) so it can't run indefinitely; call it
    again to keep working through a large backlog."""
    if platform == "youtube":
        source_type_filter, id_field = {"$regex": "^youtube"}, "video_id"
    else:
        source_type_filter, id_field = f"{platform}_apify", "source_url"
    cursor = db.intelligence_items.find(
        {"source_type": source_type_filter, "comment_sentiment": {"$exists": False}},
        {"_id": 0, "id": 1, id_field: 1, "comments_count": 1},
    ).limit(MAX_BACKFILL_PER_CALL)
    updated, skipped = 0, 0
    async for item in cursor:
        identifier = item.get(id_field, "")
        sentiment = await analyze_comments(platform, identifier, item.get("comments_count", 1))
        if sentiment:
            await db.intelligence_items.update_one({"id": item["id"]}, {"$set": {"comment_sentiment": sentiment}})
            updated += 1
        else:
            skipped += 1
    return {"updated": updated, "skipped": skipped}
