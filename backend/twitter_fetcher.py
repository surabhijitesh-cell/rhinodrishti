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
# List-based fetch — works on free tier (1 call → many accounts)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_list_tweets_official(list_id: str, list_name: str,
                               max_results: int = 50) -> list:
    """
    Fetch the latest tweets from a Twitter (X) List via X API v2.

    Free-tier friendly — one request returns tweets from every account
    in the list, eliminating per-account rate limit pain. Maintain the
    list publicly on twitter.com and edit membership without touching
    Rhino Drishti.
    """
    client = _make_tweepy_client()
    if not client:
        return []
    try:
        resp = client.get_list_tweets(
            id=list_id,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "text", "author_id", "public_metrics"],
            expansions=["author_id"],
            user_fields=["username", "name"],
        )
        if not resp.data:
            return []

        # Build author_id → (username, name) map from expansions
        users = {}
        if resp.includes and "users" in resp.includes:
            for u in resp.includes["users"]:
                users[u.id] = {"username": u.username, "name": u.name}

        results = []
        for t in resp.data:
            author = users.get(t.author_id, {})
            handle = author.get("username", str(t.author_id))
            name   = author.get("name", handle)
            results.append({
                "id":           str(uuid.uuid4()),
                "handle":       f"@{handle}",
                "account_name": name,
                "tweet_text":   t.text,
                "tweet_url":    f"https://x.com/{handle}/status/{t.id}",
                "posted_at":    t.created_at.isoformat() if t.created_at else datetime.now(timezone.utc).isoformat(),
                "fetched_at":   datetime.now(timezone.utc).isoformat(),
                "category":     "list",
                "list_id":      list_id,
                "list_name":    list_name,
                "source":       "x_official",
                "is_relevant":  True,
            })
        logger.info(f"X List '{list_name}' ({list_id}): {len(results)} tweets fetched")
        return results
    except Exception as e:
        logger.error(f"X List fetch error for {list_name} ({list_id}): {e}")
        return []


async def fetch_twitter_lists(db) -> int:
    """Scheduled: fetch tweets from all active twitter_lists documents."""
    from ai_pipeline import classify_and_analyze_article

    if not _bearer_token():
        return 0

    lists = await db.twitter_lists.find({"active": True}).to_list(50)
    if not lists:
        return 0

    saved = 0
    for lst in lists:
        list_id   = lst.get("list_id")
        list_name = lst.get("name", list_id)
        if not list_id:
            continue

        loop = asyncio.get_event_loop()
        tweets = await loop.run_in_executor(
            None, lambda lid=list_id, ln=list_name, n=lst.get("max_results", 50):
                  fetch_list_tweets_official(lid, ln, n)
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
                    analysis = await classify_and_analyze_article(text, f"X List: {list_name}")
                    item.update(analysis)
                except Exception as e:
                    logger.error(f"AI analysis failed for list tweet: {e}")
                    item["processed"] = False
                await db.intelligence_items.insert_one(item)
            saved += 1

        await db.twitter_lists.update_one(
            {"_id": lst["_id"]},
            {"$set": {"last_fetched": datetime.now(timezone.utc)}}
        )

    logger.info(f"fetch_twitter_lists: {saved} new tweets from {len(lists)} lists")
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Unified fetch — official API ONLY (Nitter fallback removed; instances dead 2023+)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_user_tweets(handle: str, account_name: str,
                      category: str, max_results: int = 10) -> list:
    """
    Fetch tweets via X API v2. Returns [] if TWITTER_BEARER_TOKEN is unset.

    Nitter fallback was removed because all public Nitter instances broke
    when Twitter killed guest-account access in mid-2023. Set
    TWITTER_BEARER_TOKEN (X API Basic tier or higher) to re-enable Twitter.
    """
    if not _bearer_token():
        return []
    return fetch_user_tweets_official(handle, account_name, category, max_results)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled jobs
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_twitter_accounts(db) -> int:
    """Scheduled: fetch all active twitter_accounts documents via official X API.

    Returns 0 immediately if TWITTER_BEARER_TOKEN is not set — Nitter
    fallback was removed (all public Nitter instances are dead post-2023).
    """
    from ai_pipeline import classify_and_analyze_article

    if not _bearer_token():
        logger.info("Twitter disabled — TWITTER_BEARER_TOKEN not set (Nitter fallback removed)")
        return 0

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
    """Scheduled: run all active twitter_searches documents + top keyword bank entries."""
    from ai_pipeline import classify_and_analyze_article
    from keyword_engine import get_top_keywords_for_search

    if not _bearer_token():
        logger.info("TWITTER_BEARER_TOKEN not set — skipping keyword search (Nitter has no search)")
        return 0

    # 1. Manual searches
    manual = await db.twitter_searches.find({"active": True}).to_list(100)
    queries = [(s.get("query"), s.get("num_results", 10), s.get("_id"))
               for s in manual if s.get("query")]

    # 2. Keyword bank queries — append twitter operators for cleaner results
    bank_keywords = await get_top_keywords_for_search(db, limit=8, min_score=45)
    seen = {q[0].lower() for q in queries}
    for kw in bank_keywords:
        # Add Twitter operators to filter retweets and force English
        q_str = f"{kw} -is:retweet lang:en"
        if q_str.lower() not in seen:
            queries.append((q_str, 5, None))  # 5 results per bank query
            seen.add(q_str.lower())

    if not queries:
        return 0

    logger.info(f"Twitter searches: {len(manual)} manual + {len(bank_keywords)} from bank "
                f"= {len(queries)} unique queries")

    saved = 0
    for query, num_results, doc_id in queries:
        loop = asyncio.get_event_loop()
        tweets = await loop.run_in_executor(
            None, lambda q=query, n=num_results: search_tweets_official(q, n)
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

        # Only stamp last_run on manually-configured searches that have a doc id
        if doc_id is not None:
            await db.twitter_searches.update_one(
                {"_id": doc_id},
                {"$set": {"last_run": datetime.now(timezone.utc)}}
            )

    logger.info(f"fetch_twitter_searches: {saved} new tweets from {len(queries)} queries")
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
