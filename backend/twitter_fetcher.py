"""
X (Twitter) fetcher — official API v2 with Nitter/ntscraper fallback.

If TWITTER_BEARER_TOKEN is set → uses official X API v2 (tweepy).
If not → falls back to ntscraper (existing free Nitter-based approach).
All results land in db.twitter_feeds AND run through the AI pipeline
into db.intelligence_items.
"""

import asyncio
import uuid
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Default seeds ─────────────────────────────────────────────────────────────
DEFAULT_ACCOUNTS = [
    {"handle": "adgpi",           "name": "ADG PI - Indian Army",          "category": "defense"},
    {"handle": "IAF_MCC",         "name": "Indian Air Force",               "category": "defense"},
    {"handle": "indiannavy",      "name": "Indian Navy",                    "category": "defense"},
    {"handle": "easterncomd",     "name": "Eastern Command",                "category": "defense"},
    {"handle": "DefenceMinIndia", "name": "Ministry of Defence",            "category": "government"},
    {"handle": "MEAIndia",        "name": "Ministry of External Affairs",   "category": "government"},
    {"handle": "HMOIndia",        "name": "Home Ministry",                  "category": "government"},
    {"handle": "PMOIndia",        "name": "Prime Minister's Office",        "category": "government"},
    {"handle": "BSF_India",       "name": "Border Security Force",          "category": "paramilitary"},
    {"handle": "official_dgar",   "name": "Assam Rifles",                   "category": "paramilitary"},
    {"handle": "ITBP_official",   "name": "ITBP",                           "category": "paramilitary"},
    {"handle": "crpf_india",      "name": "CRPF",                           "category": "paramilitary"},
]

DEFAULT_SEARCHES = [
    {"query": "northeast india security -is:retweet lang:en",         "num_results": 10},
    {"query": "Manipur violence conflict -is:retweet lang:en",        "num_results": 10},
    {"query": "Assam Bangladesh border infiltration -is:retweet",     "num_results": 10},
    {"query": "NSCN ULFA ceasefire -is:retweet lang:en",              "num_results": 5},
    {"query": "India Myanmar border security -is:retweet lang:en",    "num_results": 5},
    {"query": "China PLA Arunachal Pradesh -is:retweet lang:en",      "num_results": 5},
]


def _bearer_token() -> str:
    return os.environ.get("TWITTER_BEARER_TOKEN", "").strip()


def _make_tweepy_client():
    token = _bearer_token()
    if not token:
        return None
    try:
        import tweepy
        return tweepy.Client(bearer_token=token, wait_on_rate_limit=True)
    except ImportError:
        logger.error("tweepy not installed — run: pip install tweepy")
        return None
    except Exception as e:
        logger.error(f"Tweepy init error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Official API helpers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_user_tweets_official(handle: str, account_name: str,
                               category: str, max_results: int = 10) -> list:
    """Fetch recent tweets from a user via X API v2."""
    client = _make_tweepy_client()
    if not client:
        return []
    try:
        user_resp = client.get_user(username=handle)
        if not user_resp.data:
            logger.warning(f"X API: user @{handle} not found")
            return []
        user_id = user_resp.data.id

        tweets_resp = client.get_users_tweets(
            id=user_id,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "text", "public_metrics"],
            exclude=["retweets", "replies"],
        )
        if not tweets_resp.data:
            return []

        results = []
        for t in tweets_resp.data:
            results.append({
                "id":           str(uuid.uuid4()),
                "handle":       f"@{handle}",
                "account_name": account_name,
                "tweet_text":   t.text,
                "tweet_url":    f"https://x.com/{handle}/status/{t.id}",
                "posted_at":    t.created_at.isoformat() if t.created_at else datetime.now(timezone.utc).isoformat(),
                "fetched_at":   datetime.now(timezone.utc).isoformat(),
                "category":     category,
                "source":       "x_official",
                "is_relevant":  True,
            })
        logger.info(f"X API: {len(results)} tweets from @{handle}")
        return results
    except Exception as e:
        logger.error(f"X API fetch error for @{handle}: {e}")
        return []


def search_tweets_official(query: str, max_results: int = 10) -> list:
    """Search recent tweets via X API v2."""
    client = _make_tweepy_client()
    if not client:
        return []
    try:
        import tweepy
        resp = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "text", "author_id", "public_metrics"],
        )
        if not resp.data:
            return []
        results = []
        for t in resp.data:
            results.append({
                "id":           str(uuid.uuid4()),
                "handle":       f"@{t.author_id}",
                "account_name": "Search Result",
                "tweet_text":   t.text,
                "tweet_url":    f"https://x.com/i/web/status/{t.id}",
                "posted_at":    t.created_at.isoformat() if t.created_at else datetime.now(timezone.utc).isoformat(),
                "fetched_at":   datetime.now(timezone.utc).isoformat(),
                "category":     "search",
                "search_query": query,
                "source":       "x_official",
                "is_relevant":  True,
            })
        return results
    except Exception as e:
        logger.error(f"X API search error for '{query}': {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Nitter fallback helpers (reuses existing twitter_scraper logic)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_user_tweets_nitter(handle: str, account_name: str,
                             category: str, max_tweets: int = 5) -> list:
    try:
        from twitter_scraper import scrape_tweets_sync
        return scrape_tweets_sync(handle, max_tweets)
    except Exception as e:
        logger.warning(f"Nitter fallback failed for @{handle}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Unified fetch (tries official, falls back to Nitter)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_user_tweets(handle: str, account_name: str,
                      category: str, max_results: int = 10) -> list:
    if _bearer_token():
        return fetch_user_tweets_official(handle, account_name, category, max_results)
    return fetch_user_tweets_nitter(handle, account_name, category, max_results)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled jobs
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_twitter_accounts(db) -> int:
    """Scheduled: scrape/fetch all active twitter_accounts documents."""
    from ai_pipeline import classify_and_analyze_article

    accounts = await db.twitter_accounts.find({"active": True}).to_list(200)
    if not accounts:
        return 0

    saved = 0
    for acc in accounts:
        handle   = acc.get("handle", "").lstrip("@")
        name     = acc.get("name", handle)
        category = acc.get("category", "general")

        loop = asyncio.get_event_loop()
        tweets = await loop.run_in_executor(
            None, lambda h=handle, n=name, c=category: fetch_user_tweets(h, n, c, 10)
        )

        for tw in tweets:
            existing = await db.twitter_feeds.find_one({
                "$or": [
                    {"tweet_url": tw["tweet_url"]},
                    {"tweet_text": tw["tweet_text"], "handle": tw["handle"]},
                ]
            })
            if existing:
                continue
            await db.twitter_feeds.insert_one(tw)

            # Push into intelligence pipeline
            text = tw["tweet_text"]
            if len(text) > 50:
                item = _tweet_to_intel_item(tw)
                try:
                    analysis = await classify_and_analyze_article(text, f"Tweet: {name}")
                    item.update(analysis)
                except Exception as e:
                    logger.error(f"AI analysis failed for tweet: {e}")
                    item["processed"] = False
                await db.intelligence_items.insert_one(item)
            saved += 1

        await asyncio.sleep(1)  # be polite between accounts

    logger.info(f"fetch_twitter_accounts: {saved} new tweets from {len(accounts)} accounts")
    return saved


async def fetch_twitter_searches(db) -> int:
    """Scheduled: run all active twitter_searches documents."""
    from ai_pipeline import classify_and_analyze_article

    searches = await db.twitter_searches.find({"active": True}).to_list(100)
    if not searches:
        return 0

    if not _bearer_token():
        logger.info("TWITTER_BEARER_TOKEN not set — skipping keyword search (Nitter has no search)")
        return 0

    saved = 0
    for s in searches:
        query = s.get("query")
        if not query:
            continue
        loop = asyncio.get_event_loop()
        tweets = await loop.run_in_executor(
            None, lambda q=query, n=s.get("num_results", 10): search_tweets_official(q, n)
        )

        for tw in tweets:
            existing = await db.twitter_feeds.find_one({"tweet_url": tw["tweet_url"]})
            if existing:
                continue
            await db.twitter_feeds.insert_one(tw)

            text = tw["tweet_text"]
            if len(text) > 50:
                item = _tweet_to_intel_item(tw)
                try:
                    analysis = await classify_and_analyze_article(text, f"X search: {query}")
                    item.update(analysis)
                except Exception as e:
                    item["processed"] = False
                await db.intelligence_items.insert_one(item)
            saved += 1

        await db.twitter_searches.update_one(
            {"_id": s["_id"]},
            {"$set": {"last_run": datetime.now(timezone.utc)}}
        )

    logger.info(f"fetch_twitter_searches: {saved} new tweets")
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Seed defaults on startup
# ─────────────────────────────────────────────────────────────────────────────

async def seed_twitter_defaults(db) -> None:
    if await db.twitter_accounts.count_documents({}) == 0:
        docs = [
            {
                "id": str(uuid.uuid4()),
                "handle": a["handle"],
                "name":   a["name"],
                "category": a["category"],
                "active": True,
                "created_at": datetime.now(timezone.utc),
            }
            for a in DEFAULT_ACCOUNTS
        ]
        await db.twitter_accounts.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default Twitter accounts")

    if await db.twitter_searches.count_documents({}) == 0:
        docs = [
            {
                "id": str(uuid.uuid4()),
                "query": s["query"],
                "num_results": s["num_results"],
                "active": True,
                "last_run": None,
                "created_at": datetime.now(timezone.utc),
            }
            for s in DEFAULT_SEARCHES
        ]
        await db.twitter_searches.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default Twitter searches")


# ─────────────────────────────────────────────────────────────────────────────
# Internal util
# ─────────────────────────────────────────────────────────────────────────────

def _tweet_to_intel_item(tw: dict) -> dict:
    from firecrawl_fetcher import _base_item
    raw = {
        "title":       f"Tweet by {tw.get('account_name', tw.get('handle'))}",
        "raw_content": tw.get("tweet_text", ""),
        "source":      tw.get("handle", "twitter"),
        "source_url":  tw.get("tweet_url", ""),
        "source_type": "twitter",
        "published_at": tw.get("posted_at", datetime.now(timezone.utc).isoformat()),
    }
    return _base_item(raw)
