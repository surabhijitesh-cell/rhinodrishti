"""
Facebook Graph API fetcher for Rhino Drishti.

Monitors public Facebook pages for OSINT.

Requirements:
  FACEBOOK_APP_ID     — from Meta Developer Portal
  FACEBOOK_APP_SECRET — from Meta Developer Portal

The app access token (App ID + Secret → token) is auto-generated
on every request. It gives access to public page posts.

For pages that require a Page Access Token, set FACEBOOK_PAGE_TOKEN_<PAGE_ID>
in .env (e.g. FACEBOOK_PAGE_TOKEN_123456789=EAA...).
"""

import uuid
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"

# ── Default seeds ─────────────────────────────────────────────────────────────
DEFAULT_PAGES = [
    {"name": "Indian Army",                "page_id": "IndianArmy.adgpi",         "category": "defense"},
    {"name": "Ministry of Defence India",  "page_id": "ministryofdefenceindia",   "category": "government"},
    {"name": "BSF India",                  "page_id": "BSFindia",                 "category": "paramilitary"},
    {"name": "CRPF India",                 "page_id": "CRPFmedia",                "category": "paramilitary"},
    {"name": "Assam Rifles",               "page_id": "AssamRiflesOfficial",      "category": "paramilitary"},
    {"name": "Ministry of External Affairs","page_id": "IndianMEA",               "category": "government"},
    {"name": "East Mojo",                  "page_id": "eastmojo",                 "category": "northeast_media"},
    {"name": "NE Now News",               "page_id": "nenownews",                "category": "northeast_media"},
    {"name": "The Morung Express",         "page_id": "morungexpress",            "category": "northeast_media"},
    {"name": "Imphal Free Press",          "page_id": "ImphalFreePress",          "category": "northeast_media"},
]


def _app_id() -> str:
    return os.environ.get("FACEBOOK_APP_ID", "").strip()


def _app_secret() -> str:
    return os.environ.get("FACEBOOK_APP_SECRET", "").strip()


def _get_app_access_token() -> Optional[str]:
    """Get a fresh app access token using App ID + Secret."""
    app_id     = _app_id()
    app_secret = _app_secret()
    if not app_id or not app_secret:
        logger.warning("FACEBOOK_APP_ID or FACEBOOK_APP_SECRET not set — Facebook disabled")
        return None
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{GRAPH_BASE}/oauth/access_token",
                params={
                    "client_id":     app_id,
                    "client_secret": app_secret,
                    "grant_type":    "client_credentials",
                },
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as e:
        logger.error(f"Facebook token error: {e}")
        return None


def _page_token(page_id: str) -> Optional[str]:
    """Look for a page-specific token override, else use app token."""
    env_key = f"FACEBOOK_PAGE_TOKEN_{page_id.upper().replace('-', '_')}"
    override = os.environ.get(env_key, "").strip()
    if override:
        return override
    return _get_app_access_token()


# ─────────────────────────────────────────────────────────────────────────────
# Core fetch
# ─────────────────────────────────────────────────────────────────────────────

def fetch_page_posts_sync(page_id: str, page_name: str,
                          limit: int = 10) -> list:
    """Fetch recent public posts from a Facebook page."""
    token = _page_token(page_id)
    if not token:
        return []
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{GRAPH_BASE}/{page_id}/posts",
                params={
                    "fields":       "id,message,story,created_time,permalink_url,full_picture",
                    "limit":        limit,
                    "access_token": token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        posts = []
        for post in data.get("data", []):
            text = post.get("message") or post.get("story") or ""
            if not text:
                continue
            posts.append({
                "post_id":     post.get("id", ""),
                "text":        text,
                "url":         post.get("permalink_url") or f"https://facebook.com/{post.get('id','')}",
                "page_name":   page_name,
                "page_id":     page_id,
                "created_time": post.get("created_time", datetime.now(timezone.utc).isoformat()),
            })
        logger.info(f"Facebook: {len(posts)} posts from {page_name}")
        return posts
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.warning(f"Facebook 403 for page {page_id} — may need Page Access Token")
        else:
            logger.error(f"Facebook API error for {page_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Facebook fetch error for {page_id}: {e}")
        return []


def _post_to_intel_item(post: dict) -> dict:
    from firecrawl_fetcher import _base_item
    raw = {
        "title":        f"Facebook: {post['page_name']}",
        "raw_content":  post["text"],
        "source":       post["page_name"],
        "source_url":   post["url"],
        "source_type":  "facebook",
        "published_at": post.get("created_time", datetime.now(timezone.utc).isoformat()),
    }
    item = _base_item(raw)
    item["facebook_post_id"] = post.get("post_id")
    return item


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled job
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_facebook_pages(db) -> int:
    from ai_pipeline import classify_and_analyze_article

    pages = await db.facebook_pages.find({"active": True}).to_list(100)
    if not pages:
        return 0

    saved = 0
    for page in pages:
        page_id   = page.get("page_id")
        page_name = page.get("name", page_id)
        if not page_id:
            continue

        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(
            None, lambda pid=page_id, pn=page_name: fetch_page_posts_sync(pid, pn, 10)
        )

        for post in posts:
            existing = await db.intelligence_items.find_one({"source_url": post["url"]})
            if existing:
                continue

            item = _post_to_intel_item(post)
            if len(item["raw_content"].strip()) < 30:
                continue
            try:
                analysis = await classify_and_analyze_article(
                    item["raw_content"][:4000], item["title"]
                )
                item.update(analysis)
            except Exception as e:
                logger.error(f"AI analysis failed for Facebook post: {e}")
                item["processed"] = False

            await db.intelligence_items.insert_one(item)
            saved += 1

        await db.facebook_pages.update_one(
            {"_id": page["_id"]},
            {"$set": {"last_fetched": datetime.now(timezone.utc)}}
        )

    logger.info(f"fetch_facebook_pages: {saved} new items from {len(pages)} pages")
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Seed defaults
# ─────────────────────────────────────────────────────────────────────────────

async def seed_facebook_defaults(db) -> None:
    if await db.facebook_pages.count_documents({}) == 0:
        docs = [
            {
                "id":          str(uuid.uuid4()),
                "name":        p["name"],
                "page_id":     p["page_id"],
                "category":    p["category"],
                "active":      True,
                "last_fetched": None,
                "created_at":  datetime.now(timezone.utc),
            }
            for p in DEFAULT_PAGES
        ]
        await db.facebook_pages.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default Facebook pages")


