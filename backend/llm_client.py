"""
Shared Anthropic client — single instance used across all backend modules.

Replaces emergentintegrations.llm.chat.LlmChat.
All AI calls in this codebase use Claude Haiku via the direct Anthropic SDK.
Prompt caching is enabled on large static system prompts (CLASSIFICATION_PROMPT,
BRIEF_PROMPT, CONTEXTUAL_ANALYSIS_PROMPT) to cut input-token costs by ~80%.
"""
import os
import anthropic

# ── singleton client ──────────────────────────────────────────────────────────
_client: anthropic.AsyncAnthropic | None = None

# Model used everywhere in the app — change here to upgrade globally
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
