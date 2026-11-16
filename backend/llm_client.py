"""
Shared AI clients for Rhino Drishti.

Primary:  Gemini 2.5 Flash via OpenRouter — Stage 2 full classification.
Fallback: Claude Haiku 4.5 (Anthropic) — kept as legacy, not actively used.

Gemini 2.5 Flash is cheaper than Haiku ($0.30/$2.50 vs $0.80/$4.00 per MTok, Nov 2026)
and achieves near-identical accuracy on the 10-step structured JSON NER prompt.

Using OpenRouter (openrouter.ai/api/v1) instead of generativelanguage.googleapis.com
because Render's US servers are geo-blocked by Gemini's free-tier API restrictions.
OpenRouter routes through globally available infrastructure.
"""
import os
import sys
import time as _time

# ── Primary model ─────────────────────────────────────────────────────────────
MODEL = "google/gemini-2.5-flash"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Keep GEMINI_BASE_URL as alias so any stale imports don't break
GEMINI_BASE_URL = OPENROUTER_BASE_URL

_gemini_client = None


def get_client():
    """Return (or lazily create) the shared async Gemini 2.5 Flash client via OpenRouter.

    Used by ai_pipeline.py for Stage 2 full classification and brief generation.
    Raises RuntimeError if OPENROUTER_API_KEY is not set.
    """
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to backend/.env (or Render environment variables) before starting. "
            "Sign up free at openrouter.ai — no geo-restrictions unlike Gemini direct API."
        )
    from openai import AsyncOpenAI
    _gemini_client = _with_usage_tracking(
        AsyncOpenAI(api_key=key, base_url=OPENROUTER_BASE_URL, max_retries=1)
    )
    return _gemini_client


def _with_usage_tracking(client):
    """Record every chat call made through the shared client, so the API usage
    widget covers all features (classification, briefs, faultline scoring,
    Custom Brief Generator, sentiment, documents) without per-call-site code.
    Uses the cost OpenRouter itself reports when present."""
    create = client.chat.completions.create

    async def tracked_create(*args, **kwargs):
        caller = sys._getframe(1)
        feature = f"{caller.f_globals.get('__name__', '?').rsplit('.', 1)[-1]}__{caller.f_code.co_name}"
        # Ask OpenRouter to include the real charge in the response.
        kwargs["extra_body"] = {**(kwargs.get("extra_body") or {}), "usage": {"include": True}}
        response = await create(*args, **kwargs)
        try:
            usage = getattr(response, "usage", None)
            if usage:
                from usage_tracker import track_usage_generic
                await track_usage_generic(
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    model=kwargs.get("model", MODEL),
                    feature=feature,
                    cost_usd=getattr(usage, "cost", None),
                )
        except Exception:
            pass  # usage recording must never break a model call
        return response

    client.chat.completions.create = tracked_create
    return client


# Alias — cheap_classifier.py imports get_gemini_client() directly
get_gemini_client = get_client

# ── Gemini model constant (also exported so importers can reference it) ───────
GEMINI_FLASH_MODEL = MODEL
# Short alias without vendor prefix — useful for usage_tracker model key lookups
GEMINI_FLASH_MODEL_SHORT = "gemini-2.5-flash"


# ── Anthropic model constant (used by documents/training analysis endpoints) ──
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# ── OpenRouter quota-exhaustion fallback state ────────────────────────────────
# When OpenRouter returns persistent 429s, Stage 2 switches to Anthropic Haiku
# for OPENROUTER_FALLBACK_DURATION seconds before retrying OpenRouter again.
OPENROUTER_FALLBACK_DURATION = 1800  # 30 minutes
_openrouter_exhausted_until: float = 0.0


def mark_openrouter_exhausted() -> None:
    global _openrouter_exhausted_until
    _openrouter_exhausted_until = _time.time() + OPENROUTER_FALLBACK_DURATION


def is_openrouter_exhausted() -> bool:
    return _time.time() < _openrouter_exhausted_until


def clear_openrouter_exhausted() -> None:
    global _openrouter_exhausted_until
    _openrouter_exhausted_until = 0.0


# ── OpenRouter credit-level warning state ─────────────────────────────────────
# Populated every 30 min by _check_openrouter_credits() in server.py.
# "ok" → no banner; "low" → amber (≤ $2); "critical" → red (≤ $0.50)
_credit_warning_level: str = "ok"
_credit_remaining_usd: float | None = None


def set_credit_warning(level: str, remaining: float | None) -> None:
    global _credit_warning_level, _credit_remaining_usd
    _credit_warning_level = level
    _credit_remaining_usd = remaining


def get_credit_warning() -> dict:
    return {"level": _credit_warning_level, "remaining_usd": _credit_remaining_usd}


# ── Legacy Anthropic client (no longer primary — kept for emergency rollback) ─
_anthropic_client = None


def get_anthropic_client():
    """Return Anthropic async client. Only use if explicitly rolling back to Haiku."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    _anthropic_client = anthropic.AsyncAnthropic(api_key=key)
    return _anthropic_client
