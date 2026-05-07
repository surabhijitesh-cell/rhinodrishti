"""
Anthropic API usage tracker for Rhino Drishti.

Called after every client.messages.create() call to accumulate token
counts and costs into the `api_usage` MongoDB collection.

Collection schema (one doc per model per hour):
  date        : "2026-05-07"          (UTC date string)
  hour        : 14                    (0–23 UTC)
  model       : "claude-haiku-4-5-..."
  input_tokens         : int
  output_tokens        : int
  cache_read_tokens    : int
  cache_write_tokens   : int
  call_count           : int
  cost_usd             : float        (accumulated)
  last_updated         : ISO string
"""

import logging
from datetime import datetime, timezone
from shared import db

logger = logging.getLogger(__name__)

USD_TO_INR = 84.0   # approximate — update periodically

# Pricing per million tokens (USD)
MODEL_PRICING: dict[str, dict] = {
    # ── Active model ──────────────────────────────────────────────────────────
    "claude-3-haiku-20240307": {       # $0.25/$1.25 MTok — 68% cheaper than 4.5
        "input":       0.25,
        "output":      1.25,
        "cache_write": 0.30,
        "cache_read":  0.03,
    },
    # ── Previous model (kept for historical cost tracking) ───────────────────
    "claude-haiku-4-5-20251001": {
        "input":       0.80,
        "output":      4.00,
        "cache_write": 1.00,
        "cache_read":  0.08,
    },
    "claude-3-5-haiku-20241022": {
        "input":       0.80,
        "output":      4.00,
        "cache_write": 1.00,
        "cache_read":  0.08,
    },
    "claude-3-5-sonnet-20241022": {
        "input":       3.00,
        "output":     15.00,
        "cache_write": 3.75,
        "cache_read":  0.30,
    },
    # Default fallback — assume claude-3-haiku pricing
    "_default": {
        "input":       0.25,
        "output":      1.25,
        "cache_write": 0.30,
        "cache_read":  0.03,
    },
}


def _cost_usd(usage, model: str) -> float:
    p = MODEL_PRICING.get(model, MODEL_PRICING["_default"])
    inp   = (getattr(usage, "input_tokens",                   0) or 0) / 1_000_000
    out   = (getattr(usage, "output_tokens",                  0) or 0) / 1_000_000
    cr    = (getattr(usage, "cache_read_input_tokens",        0) or 0) / 1_000_000
    cw    = (getattr(usage, "cache_creation_input_tokens",    0) or 0) / 1_000_000
    return inp * p["input"] + out * p["output"] + cw * p["cache_write"] + cr * p["cache_read"]


async def track_usage(usage, model: str) -> None:
    """
    Call this right after every client.messages.create() with response.usage
    and the model name.  Failures are non-fatal — logged and swallowed.
    """
    try:
        now     = datetime.now(timezone.utc)
        date_s  = now.strftime("%Y-%m-%d")
        hour    = now.hour

        input_tok  = getattr(usage, "input_tokens",                0) or 0
        output_tok = getattr(usage, "output_tokens",               0) or 0
        cr_tok     = getattr(usage, "cache_read_input_tokens",     0) or 0
        cw_tok     = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cost       = _cost_usd(usage, model)

        await db.api_usage.update_one(
            {"date": date_s, "hour": hour, "model": model},
            {
                "$inc": {
                    "input_tokens":       input_tok,
                    "output_tokens":      output_tok,
                    "cache_read_tokens":  cr_tok,
                    "cache_write_tokens": cw_tok,
                    "call_count":         1,
                    "cost_usd":           round(cost, 8),
                },
                "$set": {"last_updated": now.isoformat()},
                "$setOnInsert": {"date": date_s, "hour": hour, "model": model},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"usage_tracker: failed to record usage: {e}")


async def get_daily_summary(days: int = 7) -> list[dict]:
    """
    Return one dict per calendar day (UTC) for the last `days` days.
    Each dict: date, call_count, input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens, cost_usd, cost_inr
    """
    from datetime import timedelta
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
    docs = await db.api_usage.aggregate(pipeline).to_list(length=days + 1)
    return [
        {
            "date":               d["_id"],
            "call_count":         d["call_count"],
            "input_tokens":       d["input_tokens"],
            "output_tokens":      d["output_tokens"],
            "cache_read_tokens":  d["cache_read_tokens"],
            "cache_write_tokens": d["cache_write_tokens"],
            "cost_usd":           round(d["cost_usd"], 4),
            "cost_inr":           round(d["cost_usd"] * USD_TO_INR, 2),
        }
        for d in docs
    ]


async def get_today_cost_usd() -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": today}},
        {"$group": {"_id": None, "total": {"$sum": "$cost_usd"}}},
    ]
    docs = await db.api_usage.aggregate(pipeline).to_list(length=1)
    return round(docs[0]["total"], 4) if docs else 0.0
