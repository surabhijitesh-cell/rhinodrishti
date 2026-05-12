"""
Stage 1 cheap classifier — binary relevance filter via Gemini 2.5 Flash-Lite.

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

logger = logging.getLogger(__name__)

# Gemini's OpenAI-compatible endpoint
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.5-flash-lite"

_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    _client = AsyncOpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
    return _client


SYSTEM_PROMPT = """You are a fast binary news classifier for an Indian security
intelligence platform focused on Northeast India (NER), Siliguri Corridor,
Bangladesh, Myanmar, and adjacent regions.

For each item you decide ONE thing: is this news item likely to affect the
security, stability, or general calmness of the NER region?

RELEVANT topics (mark relevant=true):
- Insurgency, militancy, armed groups (ULFA, NSCN, PLA, HNLC, KCP, etc.)
- Military / paramilitary / border force activity (BSF, Assam Rifles, BGB, Tatmadaw)
- Border incidents, infiltration, smuggling, narcotics, arms haul
- Communal / ethnic tension, riots, curfew, ILP, NRC, CAA disputes
- Political unrest: protests, bandhs, blockades, election violence
- Natural disasters: earthquake, flood, landslide, cyclone, cloudburst
- Extreme weather affecting NER: heatwave, drought, IMD alerts
- Infrastructure: bridge/road/rail collapse, power grid, internet shutdown,
  dam release, Siliguri Corridor disruption
- Major economic: tea industry, oil refinery, illegal mining, GST scam crore+
- Health: disease outbreaks, epidemics, ASF, bird flu
- Cyber attacks, espionage, disinformation
- China / Tibet / LAC / Arunachal claim issues, Bangladesh/Myanmar political turmoil
- Wildlife crime: poaching, illegal logging in NER reserves

NOT RELEVANT (mark relevant=false):
- Cricket / IPL / sports (any)
- Bollywood / entertainment / celebrity gossip
- Stock market routine ticks, mutual fund tips, crypto price moves
- Lifestyle, fashion, recipes, horoscope, lottery
- Routine education / coaching admissions
- General national India news with no NER hook
- Pure international news with no India / China / Bangladesh / Myanmar angle

Tier guess (best-effort severity if relevant):
- critical: imminent violence, mass casualty disaster, major border crisis
- high:     serious incident, security force engagement, large protest, named disaster
- medium:   noteworthy but contained — minor clash, weather warning, policy move
- low:      relevant but routine — political statement, briefing, background
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
    fail_open = {
        "relevant": True,
        "tier_guess": "low",
        "reason": "stage1_unavailable",
    }

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
                    model=GEMINI_MODEL,
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
        logger.warning(f"Stage 1 Gemini call failed: {type(e).__name__}: {str(e)[:100]}")
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
