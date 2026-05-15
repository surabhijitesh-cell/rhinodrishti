"""
API usage tracker for Rhino Drishti — multi-provider.

Tracks Anthropic (Haiku), Gemini (Flash-Lite), and OpenAI (embeddings).

Collection schema (one doc per provider+model per hour):
  date         : "2026-05-07"          (UTC date string)
  hour         : 14                    (0-23 UTC)
  provider     : "anthropic" | "gemini" | "openai"
  model        : model identifier string
  input_tokens         : int
  output_tokens        : int
  cache_read_tokens    : int
  cache_write_tokens   : int
  call_count           : int
  cost_usd             : float        (accumulated)
  last_updated         : ISO string
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from shared import db

logger = logging.getLogger(__name__)

# ── Forex ─────────────────────────────────────────────────────────────────────
_forex_cache: dict = {"rate": 84.0, "fetched_at": 0.0}
_FOREX_TTL = 6 * 3600  # refresh every 6h


async def get_usd_to_inr() -> float:
    """Fetch live USD→INR rate from exchangerate-api (free, no key needed). Cache 6h."""
    import time
    import httpx
    now = time.time()
    if now - _forex_cache["fetched_at"] < _FOREX_TTL:
        return _forex_cache["rate"]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://api.exchangerate-api.com/v4/latest/USD"
            )
            data = resp.json()
            rate = float(data["rates"]["INR"])
            _forex_cache["rate"] = rate
            _forex_cache["fetched_at"] = now
            logger.debug(f"Forex: 1 USD = {rate} INR (refreshed)")
            return rate
    except Exception as e:
        logger.warning(f"Forex fetch failed, using cached {_forex_cache['rate']}: {e}")
        return _forex_cache["rate"]


def get_usd_to_inr_sync() -> float:
    """Synchronous cached rate for non-async contexts."""
    return _forex_cache["rate"]


# Keep the old constant for backward compat with any remaining direct references
@property
def USD_TO_INR():  # noqa – not actually used as descriptor; see below
    return _forex_cache["rate"]

USD_TO_INR = 84.0  # initial value — overwritten at startup by first async fetch


# ── Provider pricing (per million tokens, USD) ────────────────────────────────
MODEL_PRICING: dict[str, dict] = {
    # Anthropic
    "claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "input": 0.80, "output": 4.00,
        "cache_write": 1.00, "cache_read": 0.08,
    },
    "claude-3-haiku-20240307": {
        "provider": "anthropic",
        "input": 0.25, "output": 1.25,
        "cache_write": 0.30, "cache_read": 0.03,
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "input": 0.80, "output": 4.00,
        "cache_write": 1.00, "cache_read": 0.08,
    },
    "claude-3-5-sonnet-20241022": {
        "provider": "anthropic",
        "input": 3.00, "output": 15.00,
        "cache_write": 3.75, "cache_read": 0.30,
    },
    # Gemini — direct API keys
    "gemini-2.5-flash": {
        "provider": "gemini",
        "input": 0.15, "output": 0.60,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "gemini-2.0-flash": {
        "provider": "gemini",
        "input": 0.10, "output": 0.40,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "gemini-2.5-flash-lite": {
        "provider": "gemini",
        "input": 0.10, "output": 0.40,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    # Gemini via OpenRouter (prefixed model names)
    "google/gemini-2.5-flash": {
        "provider": "gemini",
        "input": 0.15, "output": 0.60,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "google/gemini-2.5-flash-lite-preview-06-17": {
        "provider": "gemini",
        "input": 0.10, "output": 0.40,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "google/gemini-2.0-flash-lite-001": {
        "provider": "gemini",
        "input": 0.075, "output": 0.30,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "gemini-2.0-flash-lite": {
        "provider": "gemini",
        "input": 0.075, "output": 0.30,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "gemini-2.0-flash-lite": {
        "provider": "gemini",
        "input": 0.075, "output": 0.30,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "gemini-1.5-flash-8b": {
        "provider": "gemini",
        "input": 0.037, "output": 0.15,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    # OpenAI (embeddings)
    "text-embedding-3-small": {
        "provider": "openai",
        "input": 0.02, "output": 0.0,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    "text-embedding-3-large": {
        "provider": "openai",
        "input": 0.13, "output": 0.0,
        "cache_write": 0.0, "cache_read": 0.0,
    },
    # Default fallback
    "_default": {
        "provider": "anthropic",
        "input": 0.80, "output": 4.00,
        "cache_write": 1.00, "cache_read": 0.08,
    },
}

PROVIDER_SUB_ALERT_DEFAULTS = {
    "anthropic": 1.50,
    "gemini": 0.30,
    "openai": 0.20,
}


def _cost_usd(input_tok: int, output_tok: int, cache_read: int, cache_write: int,
              model: str) -> float:
    p = MODEL_PRICING.get(model, MODEL_PRICING["_default"])
    return (
        input_tok   / 1_000_000 * p["input"]
        + output_tok    / 1_000_000 * p["output"]
        + cache_write   / 1_000_000 * p["cache_write"]
        + cache_read    / 1_000_000 * p["cache_read"]
    )


# ── Anthropic-specific tracker (called with response.usage object) ────────────
async def track_usage(usage, model: str) -> None:
    """Record Anthropic API call via response.usage object."""
    try:
        inp   = getattr(usage, "input_tokens",                0) or 0
        out   = getattr(usage, "output_tokens",               0) or 0
        cr    = getattr(usage, "cache_read_input_tokens",     0) or 0
        cw    = getattr(usage, "cache_creation_input_tokens", 0) or 0
        await track_usage_generic(inp, out, model, cr=cr, cw=cw)
    except Exception as e:
        logger.warning(f"usage_tracker.track_usage: {e}")


# ── Generic tracker ────────────────────────────────────────────────────────────
async def track_usage_generic(
    input_tokens: int,
    output_tokens: int,
    model: str,
    cr: int = 0,
    cw: int = 0,
) -> None:
    """
    Record any provider's API call. Works for Anthropic, Gemini, and OpenAI.
    Derive provider from MODEL_PRICING table.
    """
    try:
        provider = MODEL_PRICING.get(model, MODEL_PRICING["_default"])["provider"]
        cost = _cost_usd(input_tokens, output_tokens, cr, cw, model)

        now    = datetime.now(timezone.utc)
        date_s = now.strftime("%Y-%m-%d")
        hour   = now.hour

        await db.api_usage.update_one(
            {"date": date_s, "hour": hour, "model": model, "provider": provider},
            {
                "$inc": {
                    "input_tokens":       input_tokens,
                    "output_tokens":      output_tokens,
                    "cache_read_tokens":  cr,
                    "cache_write_tokens": cw,
                    "call_count":         1,
                    "cost_usd":           round(cost, 8),
                },
                "$set": {"last_updated": now.isoformat()},
                "$setOnInsert": {
                    "date": date_s, "hour": hour,
                    "model": model, "provider": provider,
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"usage_tracker.track_usage_generic: {e}")


# ── Query helpers ──────────────────────────────────────────────────────────────
async def get_daily_summary(days: int = 7) -> list[dict]:
    """Total cost per day (all providers combined)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$date",
            "call_count":         {"$sum": "$call_count"},
            "input_tokens":       {"$sum": "$input_tokens"},
            "output_tokens":      {"$sum": "$output_tokens"},
            "cache_read_tokens":  {"$sum": "$cache_read_tokens"},
            "cache_write_tokens": {"$sum": "$cache_write_tokens"},
            "cost_usd":           {"$sum": "$cost_usd"},
        }},
        {"$sort": {"_id": 1}},
    ]
    rate = get_usd_to_inr_sync()
    docs = await db.api_usage.aggregate(pipeline).to_list(length=days + 1)
    return [{
        "date":               d["_id"],
        "call_count":         d["call_count"],
        "input_tokens":       d["input_tokens"],
        "output_tokens":      d["output_tokens"],
        "cache_read_tokens":  d["cache_read_tokens"],
        "cache_write_tokens": d["cache_write_tokens"],
        "cost_usd":           round(d["cost_usd"], 4),
        "cost_inr":           round(d["cost_usd"] * rate, 2),
    } for d in docs]


async def get_daily_summary_by_provider(days: int = 7) -> list[dict]:
    """Cost per day per provider — for stacked bar chart."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"date": "$date", "provider": "$provider"},
            "call_count": {"$sum": "$call_count"},
            "cost_usd":   {"$sum": "$cost_usd"},
        }},
        {"$sort": {"_id.date": 1}},
    ]
    rate = get_usd_to_inr_sync()
    docs = await db.api_usage.aggregate(pipeline).to_list(length=(days + 1) * 5)
    return [{
        "date":       d["_id"]["date"],
        "provider":   d["_id"]["provider"],
        "call_count": d["call_count"],
        "cost_usd":   round(d["cost_usd"], 4),
        "cost_inr":   round(d["cost_usd"] * rate, 2),
    } for d in docs]


async def get_today_cost_usd() -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": today}},
        {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}},
    ]
    docs = await db.api_usage.aggregate(pipeline).to_list(length=1)
    return round(docs[0]["total"], 4) if docs else 0.0


async def get_today_cost_by_provider() -> dict[str, float]:
    """Return {provider: cost_usd} for today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": today}},
        {"$group": {"_id": "$provider", "cost": {"$sum": "$cost_usd"},
                    "calls": {"$sum": "$call_count"},
                    "input_tokens": {"$sum": "$input_tokens"},
                    "output_tokens": {"$sum": "$output_tokens"}}},
    ]
    docs = await db.api_usage.aggregate(pipeline).to_list(length=10)
    return {
        d["_id"]: {
            "cost_usd": round(d["cost"], 4),
            "call_count": d["calls"],
            "input_tokens": d["input_tokens"],
            "output_tokens": d["output_tokens"],
        }
        for d in docs if d["_id"]
    }


async def get_today_hourly_by_provider() -> list[dict]:
    """Hourly breakdown by provider for sparkline."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": today}},
        {"$group": {
            "_id": {"hour": "$hour", "provider": "$provider"},
            "cost_usd":   {"$sum": "$cost_usd"},
            "call_count": {"$sum": "$call_count"},
        }},
        {"$sort": {"_id.hour": 1}},
    ]
    docs = await db.api_usage.aggregate(pipeline).to_list(length=24 * 5)
    rate = get_usd_to_inr_sync()
    return [{
        "hour":       d["_id"]["hour"],
        "provider":   d["_id"]["provider"],
        "cost_usd":   round(d["cost_usd"], 5),
        "cost_inr":   round(d["cost_usd"] * rate, 3),
        "call_count": d["call_count"],
    } for d in docs]
