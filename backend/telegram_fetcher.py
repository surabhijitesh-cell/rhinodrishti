"""
Telegram channel fetcher for Rhino Drishti (Telethon / user-account approach).

Setup (one time):
  1. Go to https://my.telegram.org → Log in → API Development Tools
  2. Create an app → note API ID and API Hash
  3. Run: python backend/telegram_setup.py
     Follow the prompts (phone number + OTP) → copies SESSION_STRING to clipboard
  4. Add to .env and Render:
       TELEGRAM_API_ID=<number>
       TELEGRAM_API_HASH=<string>
       TELEGRAM_SESSION_STRING=<long string from setup>

Why user-account (not bot):
  - Bots can only read messages from chats they were added to
  - User accounts can read ALL public channels — critical for OSINT
  - Telethon StringSession stores auth as a string → safe in env var

Singleton pattern:
  A single TelegramClient is created per process lifetime and reused for
  all channel fetches. This avoids AuthKeyDuplicatedError (IP conflict) which
  occurs when a new client is created per channel — each connect/disconnect
  cycle can leave lingering auth keys on Telegram servers, and Render
  restarts compound the problem by connecting the same session from a new IP.
"""

import uuid
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Default seeds ─────────────────────────────────────────────────────────────
DEFAULT_CHANNELS = [
    # Official defense / government
    {"username": "MODIndia",           "name": "Ministry of Defence India",    "category": "government"},
    {"username": "MEAIndia",           "name": "Ministry of External Affairs", "category": "government"},
    {"username": "BSFIndia",           "name": "BSF India",                    "category": "paramilitary"},
    # Northeast India media
    {"username": "eastmojo",           "name": "East Mojo",                    "category": "northeast_media"},
    {"username": "nenownews",          "name": "NE Now News",                  "category": "northeast_media"},
    {"username": "morungexpress",      "name": "Morung Express",               "category": "northeast_media"},
    {"username": "theshillongtimes",   "name": "The Shillong Times",           "category": "northeast_media"},
    {"username": "ImphalFreePress",    "name": "Imphal Free Press",            "category": "northeast_media"},
    {"username": "NagalandPost",       "name": "Nagaland Post",                "category": "northeast_media"},
    # National security news
    {"username": "ThePrintIndia",      "name": "The Print",                    "category": "national_media"},
    {"username": "TheWireNews",        "name": "The Wire",                     "category": "national_media"},
    {"username": "ANI",                "name": "ANI News",                     "category": "national_media"},
    # Border / security watch channels (public OSINT)
    {"username": "NortheastIntelligence", "name": "NE Intelligence Watch",    "category": "osint"},
    {"username": "IndiaChinaBorder",   "name": "India-China Border Watch",    "category": "osint"},
]


def _credentials():
    api_id   = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    session  = os.environ.get("TELEGRAM_SESSION_STRING", "").strip()
    return api_id, api_hash, session


def _is_configured() -> bool:
    api_id, api_hash, session = _credentials()
    return bool(api_id and api_hash and session)


# ── Singleton client ──────────────────────────────────────────────────────────
# One TelegramClient per server process. Never create a new client per channel
# fetch — that causes AuthKeyDuplicatedError when sessions overlap.
_tg_client = None
_tg_client_lock = None   # asyncio.Lock — created lazily (needs running event loop)


def _get_lock():
    global _tg_client_lock
    if _tg_client_lock is None:
        _tg_client_lock = asyncio.Lock()
    return _tg_client_lock


async def _get_or_create_client():
    """
    Return the singleton TelegramClient, creating and connecting it if needed.
    Thread-safe via asyncio.Lock. Raises on auth failure.
    """
    global _tg_client

    async with _get_lock():
        # Reuse existing connected client
        if _tg_client is not None and _tg_client.is_connected():
            return _tg_client

        if not _is_configured():
            raise RuntimeError(
                "Telegram not configured — set TELEGRAM_API_ID, "
                "TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING"
            )

        api_id, api_hash, session_str = _credentials()

        from telethon import TelegramClient
        from telethon.sessions import StringSession

        client = TelegramClient(
            StringSession(session_str),
            int(api_id),
            api_hash,
        )
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError(
                "Telegram session not authorized — re-run telegram_setup.py "
                "and update TELEGRAM_SESSION_STRING in Render env vars."
            )

        _tg_client = client
        logger.info("Telegram: singleton client connected")
        return _tg_client


async def _reset_client():
    """Disconnect and clear singleton so next call re-creates it."""
    global _tg_client
    async with _get_lock():
        if _tg_client is not None:
            try:
                await _tg_client.disconnect()
            except Exception:
                pass
            _tg_client = None
    logger.info("Telegram: singleton client reset")


# ─────────────────────────────────────────────────────────────────────────────
# Core fetch (uses shared singleton client)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_channel_messages(username: str, channel_name: str,
                                 limit: int = 20,
                                 since_hours: int = 6) -> list:
    """
    Fetch recent messages from a public Telegram channel using the
    singleton client. Returns list of message dicts.

    Does NOT connect/disconnect — caller manages client lifetime.
    On auth errors (AuthKeyDuplicatedError, session revoked) resets
    the singleton so the next call reconnects cleanly.
    """
    try:
        client = await _get_or_create_client()
    except RuntimeError as e:
        logger.error(f"Telegram client unavailable: {e}")
        return []

    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    messages = []

    try:
        async for msg in client.iter_messages(username, limit=limit):
            if not msg.date:
                continue
            msg_date = (
                msg.date.replace(tzinfo=timezone.utc)
                if msg.date.tzinfo is None
                else msg.date
            )
            if msg_date < since:
                break

            text = msg.message or msg.text or ""
            if not text or len(text.strip()) < 20:
                continue

            messages.append({
                "message_id":   msg.id,
                "channel":      username,
                "channel_name": channel_name,
                "text":         text,
                "url":          f"https://t.me/{username}/{msg.id}",
                "posted_at":    msg_date.isoformat(),
                "views":        getattr(msg, "views", 0) or 0,
                "has_media":    msg.media is not None,
            })

        logger.info(f"Telegram: {len(messages)} messages from @{username}")
        return messages

    except Exception as e:
        err_str = str(e)
        # Auth/IP conflict errors — reset client so next run reconnects fresh
        if any(kw in err_str.lower() for kw in
               ("auth", "duplicate", "conflict", "key", "deactivated", "banned")):
            logger.error(
                f"Telegram auth error for @{username} — resetting client: {e}"
            )
            await _reset_client()
        else:
            logger.error(f"Telegram fetch error for @{username}: {e}")
        return []


def _msg_to_intel_item(msg: dict) -> dict:
    from firecrawl_fetcher import _base_item
    raw = {
        "title":        f"Telegram: {msg['channel_name']}",
        "raw_content":  msg["text"],
        "source":       f"t.me/{msg['channel']}",
        "source_url":   msg["url"],
        "source_type":  "telegram",
        "published_at": msg.get("posted_at", datetime.now(timezone.utc).isoformat()),
    }
    item = _base_item(raw)
    item["telegram_message_id"] = msg.get("message_id")
    item["telegram_views"]      = msg.get("views", 0)
    return item


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled job
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_telegram_channels(db) -> int:
    """
    Scheduled: fetch messages from all active telegram_channels documents.

    Uses singleton client — no per-channel connect/disconnect.
    Items saved with processed=False so the filter cascade handles AI
    classification (avoids competing with main pipeline for Haiku quota).
    """
    if not _is_configured():
        return 0

    channels = await db.telegram_channels.find({"active": True}).to_list(100)
    if not channels:
        return 0

    # Warm up client once before the channel loop
    try:
        await _get_or_create_client()
    except RuntimeError as e:
        logger.error(f"Telegram: cannot start fetch — {e}")
        return 0

    saved = 0
    for ch in channels:
        username = ch.get("username", "").lstrip("@")
        name     = ch.get("name", username)
        if not username:
            continue

        try:
            messages = await fetch_channel_messages(username, name, limit=20, since_hours=6)
        except Exception as e:
            logger.error(f"Telegram channel fetch failed for @{username}: {e}")
            continue

        for msg in messages:
            existing = await db.intelligence_items.find_one({"source_url": msg["url"]})
            if existing:
                continue

            # Queue for filter pipeline — do NOT call Haiku inline here.
            # analyze_unprocessed_items() picks this up within 15 min.
            item = _msg_to_intel_item(msg)
            item["processed"] = False   # enters queue, override _base_item default

            await db.intelligence_items.insert_one(item)
            saved += 1

        await db.telegram_channels.update_one(
            {"_id": ch["_id"]},
            {"$set": {"last_fetched": datetime.now(timezone.utc)}}
        )

        # Polite delay between channels — avoids Telegram flood limits
        await asyncio.sleep(2)

    logger.info(f"fetch_telegram_channels: {saved} queued from {len(channels)} channels")
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Seed defaults
# ─────────────────────────────────────────────────────────────────────────────

async def seed_telegram_defaults(db) -> None:
    if await db.telegram_channels.count_documents({}) == 0:
        docs = [
            {
                "id":           str(uuid.uuid4()),
                "username":     c["username"],
                "name":         c["name"],
                "category":     c["category"],
                "active":       True,
                "last_fetched": None,
                "created_at":   datetime.now(timezone.utc),
            }
            for c in DEFAULT_CHANNELS
        ]
        await db.telegram_channels.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default Telegram channels")
