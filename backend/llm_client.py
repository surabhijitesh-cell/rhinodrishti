"""
Shared AI clients for Rhino Drishti.

Primary:  Gemini 2.5 Flash via OpenRouter — Stage 2 full classification.
Fallback: Claude Haiku 4.5 (Anthropic) — kept as legacy, not actively used.

Gemini 2.5 Flash is ~83% cheaper than Haiku ($0.15/$0.60 vs $0.80/$4.00 per MTok)
and achieves near-identical accuracy on the 10-step structured JSON NER prompt.

Using OpenRouter (openrouter.ai/api/v1) instead of generativelanguage.googleapis.com
because Render's US servers are geo-blocked by Gemini's free-tier API restrictions.
OpenRouter routes through globally available infrastructure.
"""
import os

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
    _gemini_client = AsyncOpenAI(api_key=key, base_url=OPENROUTER_BASE_URL, max_retries=1)
    return _gemini_client


# Alias — cheap_classifier.py imports get_gemini_client() directly
get_gemini_client = get_client

# ── Gemini model constant (also exported so importers can reference it) ───────
GEMINI_FLASH_MODEL = MODEL
# Short alias without vendor prefix — useful for usage_tracker model key lookups
GEMINI_FLASH_MODEL_SHORT = "gemini-2.5-flash"


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
