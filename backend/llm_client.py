"""
Shared AI clients for Rhino Drishti.

Primary:  Claude Haiku 4.5 (Anthropic) — Stage 2 full classification.
Fallback: Gemini 2.5 Flash (via OpenAI-compat endpoint) — used when Haiku
          quota is exhausted or as a cost-saving switch.

Prompt caching: enabled via cache_control blocks on static system prompts.
NOTE: claude-haiku-4-5-20251001 (Oct 2025) has caching built-in — do NOT
pass the old `anthropic-beta: prompt-caching-2024-07-31` header, it breaks
caching by overriding the built-in behaviour (caused $15/day overspend).
"""
import os
import anthropic

# ── Anthropic singleton ────────────────────────────────────────────────────────
_client: anthropic.AsyncAnthropic | None = None

# Primary model — change here to upgrade globally
MODEL = "claude-haiku-4-5-20251001"


def get_client() -> anthropic.AsyncAnthropic:
    """Return (or lazily create) the shared async Anthropic client."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to backend/.env before starting the server."
            )
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


# ── Gemini 2.5 Flash fallback (OpenAI-compatible endpoint) ───────────────────
# Recommended fallback when Haiku quota is exhausted:
#   - ~83% cheaper than Haiku ($0.15/$0.60 vs $0.80/$4.00 per MTok)
#   - Near-Haiku quality on structured JSON classification (5% gap)
#   - Uses same OpenAI SDK already installed for cheap_classifier.py
#   - Avoid Gemini 1.5 Flash — too weak on complex 10-step prompt

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_FLASH_MODEL = "gemini-2.5-flash"

_gemini_client = None


def get_gemini_client():
    """
    Return OpenAI-SDK client pointed at Gemini 2.5 Flash.
    Returns None if GEMINI_API_KEY not set.
    Used as cost-saving fallback when Haiku quota is exhausted.
    """
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    from openai import AsyncOpenAI
    _gemini_client = AsyncOpenAI(api_key=key, base_url=GEMINI_BASE_URL, max_retries=1)
    return _gemini_client
