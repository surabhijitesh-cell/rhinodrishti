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

# OpenRouter — globally available proxy for Gemini models.
# Render's Oregon servers are geo-blocked by generativelanguage.googleapis.com
# free-tier restrictions. OpenRouter bypasses this.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GEMINI_MODEL = "google/gemini-2.0-flash-lite-001"

# Short name for usage_tracker model key lookups
GEMINI_MODEL_SHORT = "gemini-2.0-flash-lite"

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


SYSTEM_PROMPT = """You are a STRICT binary pre-filter for an Indian security intelligence
platform tracking Northeast India (NER: Assam, Meghalaya, Manipur, Nagaland, Mizoram,
Tripura, Arunachal Pradesh, Sikkim) and the Siliguri Corridor (Chicken's Neck).

DEFAULT DECISION: REJECT (relevant=false).
Mark relevant=true ONLY when you are CONFIDENT the item directly threatens or
destabilises NER security RIGHT NOW. Uncertainty → REJECT.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASS (relevant=true) — strict allowlist. Item must clearly fit one of:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. ARMED MILITANCY / INSURGENCY: Active operations, encounters, IED blasts,
   ambushes, extortion demands with violence, arms/explosives seizure (≥500g or
   with named group) by ULFA, NSCN variants, PLA/MPA, HNLC, KCP, Bodo factions,
   or any named insurgent group operating in NER.

2. BORDER SECURITY INCIDENT: Confirmed infiltration; large drug/arms haul AT
   India-Bangladesh or India-Myanmar border (not generic seizure press releases);
   BSF/Assam Rifles operational contact; fencing breach; Siliguri Corridor
   physical blockage or disruption.

3. ACTIVE COMMUNAL / ETHNIC VIOLENCE: Riots in progress, curfew IMPOSED,
   targeted killings along ethnic lines, forced displacement — inside NER states.
   (Protests/bandhs CALLED but no violence → REJECT)

4. CRITICAL INFRASTRUCTURE FAILURE IN NER: Bridge/rail collapse cutting off a
   district; dam failure or emergency release causing flooding; state-ordered
   internet/power shutdown; landslide blocking NH in NER.

5. MAJOR NATURAL DISASTER WITH CASUALTIES IN NER: Flood/earthquake/landslide/
   cyclone with confirmed deaths or mass displacement inside NER states.
   (Weather forecast or advisory alone, no casualties → REJECT)

6. BANGLADESH / MYANMAR DIRECT BORDER THREAT: Armed group movements at the
   India border; Rohingya/refugee wave entering Tripura or Mizoram; Tatmadaw or
   Arakan Army shelling/crossfire near Indian territory.

7. CHINA / LAC LIVE INCIDENT: New military standoff or troop ingress at LAC in
   Arunachal; construction inside Indian claimed territory confirmed by defence
   sources. (Diplomatic talks, historical claims, routine patrols → REJECT)

8. DISEASE OUTBREAK DECLARED IN NER: Official public-health emergency or
   epidemic declared by state/central authority in NER states.
   (National health campaigns, AIIMS news, routine advisories → REJECT)

9. MEGHALAYA / NER COMMUNITY INCIDENT: Any of the following IN Meghalaya or
   other NER states, reported by a local/regional outlet:
   • Murder, killing, or suspicious death involving ethnic communities
     (Khasi, Garo, Jaintia, Hajong, Koch, Biate, Pnar, Karbi, Dimasa, Rabha)
   • Local (indigenous) vs non-local / immigrant tension or violence
   • Veterans, ex-servicemen, or defence personnel grievances or incidents
   • Social unrest, community mobilisation, or strikes with unrest potential
   • Bangladesh border area crimes, illegal settler confrontations
   • Major crimes (armed robbery, gang conflict, organised crime) with
     potential to trigger community protests or ethnic polarisation
   • Economic disruption, road blockades, or supply chain disruption
     affecting Meghalaya districts
   (Purely personal disputes, traffic accidents, routine theft → REJECT)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALWAYS REJECT — regardless of NER mention:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Cricket, IPL, Olympics, sports of any kind
• Bollywood, OTT, celebrity gossip, entertainment
• Sensex, mutual funds, RBI rate decisions, crypto, corporate earnings
• Lifestyle, recipes, fashion, horoscope, lottery
• Board exams, coaching, NEP, scholarship schemes, university news
• PM/CM inaugurations, ribbon-cutting, development project launches
  (only infrastructure FAILURE is relevant, not construction/opening)
• Awards, Padma honours, national rankings, achiever profiles
• Routine judicial: bail orders, court hearings not involving armed groups
• Routine transfers, appointments, government scheme launches
• India-Pakistan tension without NER/China/border angle
• India-China diplomatic talks, trade disputes (no troop movement)
• Bangladesh/Myanmar political or economic news without armed-group/border angle
• National vaccination drives, health awareness, hospital openings
• Routine police crime: theft, fraud, domestic violence, cybercrime (generic)
  EXCEPTION: Murder/killing involving ethnic communities in Meghalaya/NER → PASS (category 9)
• NE India cultural festivals, tourism, film festivals, brand campaigns
• MGNREGA, PM-KISAN, welfare disbursement news
• Political protests/bandhs ANNOUNCED (no violence confirmed)
• Routine BSF/Assam Rifles flag meetings, patrol briefings (no incident)
• Weather alerts, IMD forecasts for NER (no casualty/disaster declared)
• Wildlife poaching or forest crime without security-group connection
• Opinion pieces, analysis, retrospectives without current active incident
• Any article where NER is mentioned only as passing geography, not as the
  location of an active incident

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BORDERLINE → DEFAULT REJECT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"NER mentioned but article is about national policy" → REJECT
"Drug bust <500g, location unspecified" → REJECT
"Armed group issued statement / press release" (no action) → REJECT
"Military exercise announced" (routine, no incident) → REJECT
"Political tension / war of words" (no violence) → REJECT
"Economic crime / scam" (no armed group involvement) → REJECT

Tier (only if relevant=true):
- critical: active violence, mass casualty, immediate border breach
- high:     serious incident, named-group engagement, disaster with deaths
- medium:   contained incident, significant seizure, credible threat
- low:      monitoring-worthy but low urgency
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
