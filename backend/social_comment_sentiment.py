"""
Real per-post comment/reply sentiment — Facebook, Instagram, Twitter. One
shared, config-driven module (was Facebook-only; generalized 2026-07-12 when
Twitter/Instagram reached feature parity).

Each platform's comment/reply actor is a SEPARATE Apify actor from its
post-scraper (post scrapers only return counts, not text) — verified live
for all three before building this, never assumed:
  Facebook:  apify/facebook-comments-scraper    startUrls=[{"url":..}]  field "text"
  Instagram: apify/instagram-comment-scraper    directUrls=[url,...]   field "text"
  Twitter:   scraper_one/x-post-replies-scraper postUrls=[url,...]     field "replyText"

Non-fatal by design: any failure here must not block the post itself from
being ingested — comment_sentiment is an enrichment, not a gate.
"""
import json
import logging

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

SENTIMENT_PROMPT = """You are analyzing public sentiment in social media comments on a \
North East India security/current-affairs post. Given the comment texts below, estimate \
what percentage express positive/supportive sentiment vs negative/critical/angry sentiment \
toward the situation described. Ignore off-topic or spam comments when judging tone, but \
still count them in sample_size.

Respond with ONLY a JSON object:
{"positive_pct": <0-100 int>, "negative_pct": <0-100 int>, "sample_size": <int>}

positive_pct + negative_pct need not sum to 100 (neutral comments make up the rest)."""


async def fetch_post_comments(platform: str, post_url: str, max_comments: int = MAX_COMMENTS_PER_POST) -> list[str]:
    cfg = PLATFORM_CONFIG[platform]
    url_value = [{"url": post_url}] if cfg["wrap_url"] else [post_url]
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


async def analyze_comments(platform: str, post_url: str, comment_count: int) -> dict | None:
    """Best-effort: returns None on any failure so callers can skip the tag."""
    if not post_url or comment_count <= 0:
        return None
    try:
        comments = await fetch_post_comments(platform, post_url)
        return await score_comment_sentiment(comments)
    except Exception as e:
        logger.warning(f"{platform} comment sentiment failed for {post_url}: {e}")
        return None


async def backfill_comment_sentiment(db, platform: str) -> dict:
    """One-time (idempotent) sweep for a given platform's source_type — safe
    to re-run, only touches docs missing comment_sentiment."""
    source_type = f"{platform}_apify"
    cursor = db.intelligence_items.find(
        {"source_type": source_type, "comment_sentiment": {"$exists": False}},
        {"_id": 0, "id": 1, "source_url": 1, "comments_count": 1},
    )
    updated, skipped = 0, 0
    async for item in cursor:
        sentiment = await analyze_comments(platform, item.get("source_url", ""), item.get("comments_count", 0))
        if sentiment:
            await db.intelligence_items.update_one({"id": item["id"]}, {"$set": {"comment_sentiment": sentiment}})
            updated += 1
        else:
            skipped += 1
    return {"updated": updated, "skipped": skipped}
