"""
Apify-based social media fetcher — Instagram, Facebook, Twitter/X.

Replaces the old twitter_fetcher.py / facebook_fetcher.py (official-API
based, both failed completely — cost/access issues, never produced usable
data). This module uses managed Apify actors instead: no logins, no proxy
management, no account-ban risk — the actor maintainer absorbs the anti-bot
arms race, not us.

Actors used (chosen for cost + reliability, see memory/plans research):
  Twitter:   apidojo/tweet-scraper       — $0.0004/tweet
  Instagram: breathtaking_anthem/instagram-hashtag-posts-scraper — $0.0014/post
  Facebook:  scraper_one/facebook-posts-search — $0.002/post

All three platforms have full feature parity as of 2026-07-12 (Apify Starter
plan, $29/mo): ingestion, comment/reply sentiment (social_comment_sentiment.py),
Dashboard widget, source emblem, Social Pulse. Twitter was previously disabled
— the free-plan API block on apidojo/tweet-scraper is confirmed lifted under
Starter (live test call, not assumed). Instagram's once-daily cap and
Facebook's rate limit are also confirmed lifted under Starter.

Volume mode (throttled default / firehose) is stored in Mongo
(db.app_settings, doc id "social_fetch") so the admin toggle in API &
Pipeline Monitor takes effect immediately without a redeploy or restart.

Same pattern as every other fetcher: pull items → dedup on source_url →
classify_and_analyze_article → db.intelligence_items. No pipeline changes.

NOTE ON FIELD MAPPING: Apify does not publish a fixed output schema for
these actors (community-maintained, not versioned APIs) — the ai_pipeline_
Author/ mapping below reads several candidate key names defensively and
skips a post rather than crashing if none match. Verified against real run
output for all three platforms (see git history for the live test calls).
"""
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Actor IDs ──────────────────────────────────────────────────────────────
ACTOR_TWITTER = "apidojo/tweet-scraper"
ACTOR_INSTAGRAM = "breathtaking_anthem/instagram-hashtag-posts-scraper"
ACTOR_FACEBOOK = "scraper_one/facebook-posts-search"

# ── Region seeds — reuse the app's existing NER state list, don't invent one ─
from shared import NER_STATES  # ["Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura"]

INSTAGRAM_HASHTAGS = [s.replace(" ", "") for s in NER_STATES] + ["Northeast India", "NER"]
SEARCH_QUERIES = [f"{state} India" for state in NER_STATES] + ["Northeast India security"]

# ── Volume modes ─────────────────────────────────────────────────────────────
FETCH_CONFIG = {
    "throttled": {"max_items_per_platform": 50, "hours_between_runs": 84},   # ~2x/week
    "firehose":  {"max_items_per_platform": 100, "hours_between_runs": 24},  # daily
}
DEFAULT_MODE = "throttled"


# ── Mode persistence (Mongo — takes effect without redeploy) ─────────────────

async def get_fetch_mode(db) -> str:
    doc = await db.app_settings.find_one({"id": "social_fetch"})
    mode = (doc or {}).get("mode", DEFAULT_MODE)
    return mode if mode in FETCH_CONFIG else DEFAULT_MODE


async def set_fetch_mode(db, mode: str) -> dict:
    if mode not in FETCH_CONFIG:
        raise ValueError(f"mode must be one of {list(FETCH_CONFIG)}")
    await db.app_settings.update_one(
        {"id": "social_fetch"},
        {"$set": {"mode": mode, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"mode": mode}


async def _should_run_now(db, mode: str) -> bool:
    """Gate on last_run so a single always-on scheduler job can serve both
    modes just by checking a different interval — no APScheduler reschedule
    needed when the admin flips the toggle."""
    doc = await db.app_settings.find_one({"id": "social_fetch"})
    last_run = (doc or {}).get("last_run")
    if not last_run:
        return True
    hours_since = (datetime.now(timezone.utc) - datetime.fromisoformat(last_run)).total_seconds() / 3600
    return hours_since >= FETCH_CONFIG[mode]["hours_between_runs"]


async def _mark_run(db, counts: dict) -> None:
    await db.app_settings.update_one(
        {"id": "social_fetch"},
        {"$set": {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_run_counts": counts,
        }},
        upsert=True,
    )


# ── Apify client ──────────────────────────────────────────────────────────────

def _get_client():
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        raise RuntimeError("APIFY_TOKEN not set — add it to backend/.env and Render env vars")
    from apify_client import ApifyClient
    return ApifyClient(token)


def is_configured() -> bool:
    return bool(os.environ.get("APIFY_TOKEN", "").strip())


async def _run_actor(actor_id: str, run_input: dict) -> list[dict]:
    """Run an Apify actor to completion and return its dataset items.
    Synchronous apify-client call — run in an executor so it doesn't block
    the event loop (same pattern as every other fetcher's requests calls)."""
    import asyncio
    client = _get_client()
    loop = asyncio.get_running_loop()

    def _sync_run():
        # apify-client 3.x: .call() returns a pydantic Run model, not a dict —
        # confirmed by inspecting apify_client._models.Run locally (the field
        # is default_dataset_id, snake_case attribute access).
        run = client.actor(actor_id).call(run_input=run_input)
        if run is None:
            return []
        dataset_id = run.default_dataset_id
        return list(client.dataset(dataset_id).iterate_items())

    return await loop.run_in_executor(None, _sync_run)


# ── Field mapping (defensive — see module docstring) ─────────────────────────

def _first(item: dict, *keys, default=""):
    for k in keys:
        v = item.get(k)
        if v:
            return v
    return default


def _twitter_to_intel_item(tweet: dict) -> Optional[dict]:
    text = _first(tweet, "text", "fullText")
    if not text:
        return None
    url = _first(tweet, "url", "twitterUrl")
    author = tweet.get("author") or {}
    handle = author.get("userName") or author.get("username") or "unknown"
    created = _first(tweet, "createdAt", "created_at")
    return {
        "title": f"Tweet by @{handle}: {text[:80]}",
        "source": f"X/Twitter - @{handle}",
        "source_url": url or f"https://x.com/{handle}",
        "published_at": _parse_date(created),
        "raw_content": text,
        "source_type": "twitter_apify",
        "comments_count": tweet.get("replyCount", 0),
    }


def _instagram_to_intel_item(post: dict) -> Optional[dict]:
    caption = _first(post, "caption", "text", "description")
    if not caption:
        return None
    url = _first(post, "url", "postUrl", "permalink")
    author = post.get("author") or {}
    owner = _first(post, "ownerUsername", "username", default="") or author.get("username", "unknown")
    created = _first(post, "taken_at", "taken_at_timestamp", "timestamp", "takenAt", "createdAt")
    return {
        "title": f"Instagram post by @{owner}: {caption[:80]}",
        "source": f"Instagram - @{owner}",
        "source_url": url or f"https://instagram.com/{owner}",
        "published_at": _parse_date(created),
        "raw_content": caption,
        "source_type": "instagram_apify",
        "comments_count": post.get("comment_count", 0),
    }


def _facebook_to_intel_item(post: dict) -> Optional[dict]:
    text = _first(post, "postText", "text", "message", "content")
    if not text:
        return None
    url = _first(post, "url", "postUrl", "link")
    author_obj = post.get("author") or {}
    author = author_obj.get("name") if isinstance(author_obj, dict) else None
    author = author or _first(post, "pageName", "authorName", default="unknown")
    created = _first(post, "timestamp", "time", "date")
    return {
        "title": f"Facebook post by {author}: {text[:80]}",
        "source": f"Facebook - {author}",
        "source_url": url,
        "published_at": _parse_date(created),
        "raw_content": text,
        "source_type": "facebook_apify",
        "comments_count": post.get("commentsCount", 0),
    }


def _parse_date(value) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, (int, float)):
        # Epoch millis (13 digits, e.g. Facebook's `timestamp`) vs epoch
        # seconds (10 digits, e.g. Instagram's `taken_at_timestamp`) —
        # anything past year ~2286 in seconds is unambiguously millis.
        if value > 1e11:
            value = value / 1000
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


# ── Per-platform fetchers ─────────────────────────────────────────────────────

# Comment-sentiment lookups are slow (~15-25s Apify actor call + an LLM call,
# EACH). Doing this for every item in a firehose-sized batch (up to 100)
# blew cycle runtime past Render's limits and the process got killed before
# _mark_run ever ran — last_run looked permanently stuck even though items
# were still being ingested. Capped per platform per cycle so a fetch always
# finishes and records itself; uncapped items just don't get a sentiment tag.
MAX_SENTIMENT_LOOKUPS_PER_CYCLE = 5


async def _ingest(db, items: list[dict], platform: str) -> int:
    from ai_pipeline import classify_and_analyze_article
    saved = 0
    sentiment_lookups = 0
    for item in items:
        if not item.get("source_url") or not item.get("raw_content"):
            continue
        if await db.intelligence_items.find_one({"source_url": item["source_url"]}):
            continue
        item.setdefault("id", str(uuid.uuid4()))
        await db.social_posts.insert_one({**item, "platform": platform, "fetched_at": datetime.now(timezone.utc).isoformat()})
        try:
            analysis = await classify_and_analyze_article(item["raw_content"][:4000], item["title"])
            item.update(analysis)
        except Exception as e:
            logger.warning(f"{platform} classify failed, queued unprocessed: {e}")
            item["processed"] = False

        if item.get("comments_count", 0) > 0 and sentiment_lookups < MAX_SENTIMENT_LOOKUPS_PER_CYCLE:
            sentiment_lookups += 1
            from social_comment_sentiment import analyze_comments
            sentiment = await analyze_comments(platform, item["source_url"], item["comments_count"])
            if sentiment:
                item["comment_sentiment"] = sentiment

        await db.intelligence_items.insert_one(item)
        saved += 1
    return saved


# Re-enabled 2026-07-12 — apidojo/tweet-scraper blocked API calls on Apify's
# free plan ("The developer of this actor doesn't allow the use of API in
# the Free Plan", confirmed live 2026-07-10). Upgrading to Apify Starter
# ($29/mo) lifted this — confirmed live with a real test call before
# re-enabling, not assumed.
async def fetch_twitter_posts(db, max_items: int) -> int:
    query = _rotated(SEARCH_QUERIES, 1)[0]
    raw = await _run_actor(ACTOR_TWITTER, {
        "searchTerms": [query],
        "maxItems": max_items,
        "sort": "Latest",
        "tweetLanguage": "en",
    })
    items = [it for it in (_twitter_to_intel_item(t) for t in raw) if it]
    return await _ingest(db, items, "twitter")


INSTAGRAM_MIN_ITEMS = 24  # actor-enforced floor — validation fails below this


def _rotated(items: list, n: int) -> list:
    """Pick n items starting from a day-of-year-based offset, so repeated
    runs cycle through the full list over time instead of always hitting
    the same first few entries."""
    if not items:
        return []
    offset = datetime.now(timezone.utc).timetuple().tm_yday % len(items)
    rotated = items[offset:] + items[:offset]
    return rotated[:n]


async def fetch_instagram_posts(db, max_items: int) -> int:
    # The once-per-day free-tier cap ("Access denied! Free User allowed to
    # run once daily") is confirmed LIFTED under Apify Starter — tested live
    # 2026-07-12 with two consecutive calls, both succeeded. Kept the
    # one-hashtag-per-fetch rotation anyway: it's a sane default footprint,
    # not a forced workaround anymore — loosen if you want broader coverage.
    hashtag = _rotated(INSTAGRAM_HASHTAGS, 1)[0]
    raw = await _run_actor(ACTOR_INSTAGRAM, {
        "hashtag": hashtag,
        "scrape_type": "recent",
        "max_items": max(max_items, INSTAGRAM_MIN_ITEMS),  # 24 is a floor, not a cap
    })
    items = [it for it in (_instagram_to_intel_item(p) for p in raw) if it]
    return await _ingest(db, items, "instagram")


async def fetch_facebook_posts(db, max_items: int) -> int:
    # The free-tier rate limit ("Rate limit reached" on every call after the
    # first when looped across all 8 NER queries) is confirmed LIFTED under
    # Apify Starter — tested live 2026-07-12. Kept the one-query-per-fetch
    # rotation anyway as a sane default footprint, not a forced workaround.
    query = _rotated(SEARCH_QUERIES, 1)[0]
    raw = await _run_actor(ACTOR_FACEBOOK, {
        "query": query,
        "resultsCount": max_items,
        "searchType": "latest",
    })
    items = [it for it in (_facebook_to_intel_item(p) for p in raw) if it]
    return await _ingest(db, items, "facebook")


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def run_social_fetch(db, force: bool = False) -> dict:
    """Fetch all three platforms at the current volume mode.
    force=True skips the interval gate (used by the manual 'Fetch Now' button)."""
    if not is_configured():
        return {"status": "not_configured", "message": "APIFY_TOKEN not set"}

    mode = await get_fetch_mode(db)
    if not force and not await _should_run_now(db, mode):
        return {"status": "skipped", "mode": mode, "message": "Not due yet per current interval"}

    max_items = FETCH_CONFIG[mode]["max_items_per_platform"]
    counts = {}
    for platform, fn in [
        ("instagram", fetch_instagram_posts),
        ("facebook", fetch_facebook_posts),
        ("twitter", fetch_twitter_posts),
    ]:
        try:
            counts[platform] = await fn(db, max_items)
        except Exception as e:
            logger.error(f"Apify {platform} fetch failed: {e}")
            counts[platform] = 0

    await _mark_run(db, counts)
    return {"status": "ok", "mode": mode, "max_items_per_platform": max_items, "counts": counts}
