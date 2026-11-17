"""
Stage 1 cheap classifier — removes obviously off-topic items via Gemini 2.5 Flash-Lite.
Default is PASS: the full classifier makes every real relevance decision.

Sits between Stage 0 (keyword) and Stage 2 (Haiku full classify).
Goal: kill another ~70% of items that survived Stage 0 but are still not
NER security-relevant, at ~10x lower cost than Haiku.

Calls Gemini through its OpenAI-compatible endpoint so we reuse the existing
`openai` Python SDK and avoid a new dependency.

Returns a dict:
    {
        "relevant": bool,
        "tier_guess": "critical" | "high" | "medium" | "low" | "none",
        "reason": str,
    }

On any error (no key, timeout, malformed JSON) returns relevant=True so the
item falls through to Haiku — fail-open, never silently drop news.
"""
import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI

from model_routing import STAGE1_MODEL

logger = logging.getLogger(__name__)

# OpenRouter — globally available proxy for Gemini models.
# Render's Oregon servers are geo-blocked by generativelanguage.googleapis.com
# free-tier restrictions. OpenRouter bypasses this.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GEMINI_MODEL = STAGE1_MODEL  # gemini-2.0-flash-lite-001 was retired; failed open since June

# Short name for usage_tracker model key lookups
GEMINI_MODEL_SHORT = "gemini-2.5-flash-lite"

_client: Optional[AsyncOpenAI] = None

# Circuit breaker: epoch-second timestamp after which calls resume.
# Set to now+300 when a quota/rate 429 is detected; all calls within
# the cooldown window return fail_open immediately without hitting the API.
_quota_paused_until: float = 0.0


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return None
    # max_retries=1: the SDK's built-in retry loop floods logs with dozens of
    # "Retrying request" lines when quota is exhausted. One retry is enough;
    # our own circuit breaker handles persistent quota failures at batch level.
    _client = AsyncOpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL, max_retries=1)
    return _client


SYSTEM_PROMPT = """You are a cheap first screen for an Indian Army intelligence platform covering
Northeast India (Assam, Meghalaya, Manipur, Nagaland, Mizoram, Tripura, Arunachal
Pradesh, Sikkim), the Siliguri Corridor / North Bengal, Bangladesh and Myanmar.
A stronger model judges everything you pass. Your only job is to remove items that
are OBVIOUSLY off-topic, cheaply.

DEFAULT DECISION: PASS (relevant=true). When in doubt → PASS.
Dropping a real security item is far worse than passing junk.

ALWAYS PASS anything touching, in or near the regions above:
• Army, Assam Rifles, BSF, police or armed-group activity; insurgency, militancy,
  encounters, IEDs, arms/drug seizures, extortion, infiltration, border incidents
• Bangladesh: politics, elections, protests, army, BGB, Awami League/BNP/Jamaat,
  violence against Hindus or minorities, India-Bangladesh relations
• Myanmar: junta, Arakan Army, Chin/Kuki groups, refugees, cross-border fighting
• China/LAC/Arunachal, Pakistan or China links in South Asia, diplomatic moves that
  affect India's security
• Communal or religious tension, Hindu-Muslim conflict, tribal vs non-tribal or
  indigenous vs migrant tension, ethnic violence, bandhs, blockades, strikes,
  protests and civil unrest — including ones only announced or threatened
• Roads, highways, bridges, railways: closures, blockades, landslides, collapse,
  traffic disruption; floods and disasters
• Drones, cyber attacks on Indian targets, propaganda / information campaigns
• Ex-servicemen or veterans' issues; illegal immigration; demographic change

REJECT ONLY when the item is clearly one of these AND has no angle above:
• Sports, entertainment, celebrities, films, music, fashion, lifestyle, recipes,
  horoscopes, lottery
• Stock markets, company results, personal finance, crypto, product launches
• Exams, admissions, school/university routine news, scholarships
• Health tips, routine hospital or vaccination news
• Tourism promotion, cultural festivals, awards and honours
• Routine transfers/appointments, routine court hearings, welfare payments
• Purely foreign news with no link to India, Bangladesh, Myanmar, China or Pakistan

Tier (only if relevant=true, a rough guess):
- critical: active violence, mass casualty, immediate border breach
- high:     serious incident, named armed group, disaster with deaths
- medium:   contained incident, seizure, credible threat, significant unrest
- low:      worth monitoring
- none:     not relevant

Return ONLY valid JSON. No prose, no markdown fences. Schema:
{"relevant": true|false, "tier_guess": "critical|high|medium|low|none", "reason": "<8 words>"}
"""


async def cheap_filter(article: dict, timeout: float = 8.0) -> dict:
    """
    Binary-classify an article with Gemini Flash-Lite.

    Fail-open: on any error (no API key, timeout, malformed response) returns
    relevant=True so the item proceeds to Haiku. Never silently drop news.
    """
    import time

    fail_open = {
        "relevant": True,
        "tier_guess": "low",
        "reason": "stage1_unavailable",
    }

    # Circuit breaker: skip calls during quota cooldown window
    global _quota_paused_until
    if time.time() < _quota_paused_until:
        return {**fail_open, "reason": "stage1_quota_cooldown"}

    client = _get_client()
    if client is None:
        return fail_open

    title = (article.get("title") or "").strip()
    content = (article.get("raw_content") or article.get("description") or "").strip()
    snippet = content[:600]
    source = article.get("source", "")
    region = article.get("region", "")

    user_msg = (
        f"SOURCE: {source} ({region})\n"
        f"TITLE: {title}\n"
        f"CONTENT: {snippet}"
    )

    try:
        resp = await client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=80,
            response_format={"type": "json_object"},
            timeout=timeout,
        )

        # Track usage
        try:
            usage = resp.usage
            if usage:
                from usage_tracker import track_usage_generic
                await track_usage_generic(
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    model=GEMINI_MODEL_SHORT,  # short name maps to usage_tracker pricing
                    feature="cheap_classifier__stage1",
                    cost_usd=getattr(usage, "cost", None),
                )
        except Exception:
            pass

        raw = resp.choices[0].message.content or ""
        data = json.loads(raw)
        return {
            "relevant": bool(data.get("relevant", True)),
            "tier_guess": str(data.get("tier_guess", "low")).lower(),
            "reason": str(data.get("reason", ""))[:80],
        }
    except json.JSONDecodeError as e:
        logger.warning(f"Stage 1 Gemini returned non-JSON: {e}")
        return fail_open
    except Exception as e:
        err_str = str(e)
        # Detect quota exhaustion (429) — activate circuit breaker for 5 min
        if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
            _quota_paused_until = time.time() + 300
            logger.warning("Stage 1 Gemini quota exhausted — skipping for 5 min")
        else:
            logger.warning(f"Stage 1 Gemini call failed: {type(e).__name__}: {str(e)[:80]}")
        return fail_open


async def cheap_filter_batch(articles: list[dict], concurrency: int = 5) -> list[dict]:
    """
    Classify a batch of articles concurrently.
    Returns a list of result dicts in the same order as input.
    """
    import asyncio

    sem = asyncio.Semaphore(concurrency)

    async def _one(a):
        async with sem:
            return await cheap_filter(a)

    return await asyncio.gather(*(_one(a) for a in articles))
