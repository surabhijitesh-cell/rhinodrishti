"""
Facebook comment sentiment — real comment text via a second Apify actor,
scored in one batched LLM call per post.

Uses apify/facebook-comments-scraper (official, PAY_PER_EVENT: $0.0025/comment
+ $0.001/run start). Separate from scraper_one/facebook-posts-search (the post
scraper in apify_social_fetcher.py), which only returns reaction/comment
*counts*, not comment text — confirmed via a live test call before building
this (see plan discussion). Skipped for posts with commentsCount == 0 to avoid
paying for an empty result.

Non-fatal by design: any failure here (actor error, LLM parse failure) must
not block the post itself from being ingested — comment_sentiment is an
enrichment, not a gate.
"""
import json
import logging

from apify_social_fetcher import _run_actor
from llm_client import get_client, MODEL

logger = logging.getLogger(__name__)

COMMENT_ACTOR = "apify/facebook-comments-scraper"
MAX_COMMENTS_PER_POST = 20

SENTIMENT_PROMPT = """You are analyzing public sentiment in Facebook comments on a \
North East India security/current-affairs post. Given the comment texts below, \
estimate what percentage express positive/supportive sentiment vs negative/critical/\
angry sentiment toward the situation described. Ignore off-topic or spam comments \
when judging tone, but still count them in sample_size.

Respond with ONLY a JSON object:
{"positive_pct": <0-100 int>, "negative_pct": <0-100 int>, "sample_size": <int>}

positive_pct + negative_pct need not sum to 100 (neutral comments make up the rest)."""


async def fetch_post_comments(post_url: str, max_comments: int = MAX_COMMENTS_PER_POST) -> list[str]:
    raw = await _run_actor(COMMENT_ACTOR, {
        "startUrls": [{"url": post_url}],
        "resultsLimit": max_comments,
    })
    return [c["text"] for c in raw if c.get("text")]


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


async def analyze_facebook_comments(post_url: str, comments_count: int) -> dict | None:
    """Best-effort: returns None on any failure so callers can skip the tag."""
    if not post_url or comments_count <= 0:
        return None
    try:
        comments = await fetch_post_comments(post_url)
        return await score_comment_sentiment(comments)
    except Exception as e:
        logger.warning(f"Facebook comment sentiment failed for {post_url}: {e}")
        return None


async def backfill_facebook_comment_sentiment(db) -> dict:
    """One-time (idempotent) sweep: attach comment_sentiment to existing
    Facebook items that don't have it yet. Safe to call repeatedly — only
    touches docs missing the field."""
    cursor = db.intelligence_items.find(
        {"source_type": "facebook_apify", "comment_sentiment": {"$exists": False}},
        {"_id": 0, "id": 1, "source_url": 1, "comments_count": 1},
    )
    updated, skipped = 0, 0
    async for item in cursor:
        sentiment = await analyze_facebook_comments(
            item.get("source_url", ""), item.get("comments_count", 0)
        )
        if sentiment:
            await db.intelligence_items.update_one(
                {"id": item["id"]}, {"$set": {"comment_sentiment": sentiment}}
            )
            updated += 1
        else:
            skipped += 1
    return {"updated": updated, "skipped": skipped}
