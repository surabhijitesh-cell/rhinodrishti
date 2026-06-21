"""
faultline_engine.py — Faultline scoring, matching, and propagation engine.

Pipeline (daily pass):
  1. Load active faultlines from db.faultlines
  2. For each faultline:
       a. Filter candidate articles via keyword/tag/region pre-filter (cheap)
       b. Score impact per article via LLM (only for matched candidates)
       c. Persist mappings (article ↔ faultline + rationale) in db.faultline_mappings
  3. Compute daily score per faultline using stability-style composite formula
  4. Apply cross-faultline propagation via static weighted graph
  5. Persist daily snapshot to db.faultline_scores
  6. Evaluate alert conditions → persist to db.faultline_alerts

Reuses:
  - Stability scoring formula pattern from routers/trends.py
  - intelligence_items schema (priority_score, severity, regions, tags, signal_bucket)
  - LLM client (llm_client.get_client) — same prompt-caching pattern as ai_pipeline.py

Design constraints:
  - Idempotent: re-running same date overwrites scores (replace_one upsert)
  - Auditable: every mapping stores rationale + confidence + evidence article ids
  - Efficient: pre-filter prevents most LLM calls; backfill batches with sleep
"""
import asyncio
import json
import logging
import math
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("faultline_engine")

# ── Severity weighting (matches trends.py / brief_monthly.py) ─────────────────
_SEV_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


# ── LLM string sanitization ───────────────────────────────────────────────────
# LLM output is stored and later rendered in UI + PDF + monthly briefs. Strip
# markup-like characters to prevent prompt-injected payloads from embedding
# misleading structure into official audit documents.
_LLM_STRIP_PATTERN = re.compile(r"[<>{}\\]|```")


def _sanitize_llm_string(value, max_len: int) -> str:
    """Sanitize a single LLM-output string for safe storage and rendering."""
    if not isinstance(value, str):
        return ""
    cleaned = _LLM_STRIP_PATTERN.sub("", value).strip()
    # Collapse newlines + tabs into spaces — rationale should be a single sentence
    cleaned = re.sub(r"[\r\n\t]+", " ", cleaned)
    # Collapse runs of whitespace
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned[:max_len]


def _sanitize_llm_list(values, max_items: int, max_item_len: int) -> list[str]:
    """Sanitize a list of LLM-output strings."""
    if not isinstance(values, list):
        return []
    out = []
    for v in values[:max_items]:
        s = _sanitize_llm_string(v, max_item_len)
        if s:
            out.append(s)
    return out

# ── Scoring weights (composite formula, mirrors stability index) ──────────────
W_SEVERITY_LOAD = 0.40
W_VELOCITY = 0.25
W_ACTOR_SPREAD = 0.20
W_CROSS_BORDER = 0.15

# ── Alert thresholds ──────────────────────────────────────────────────────────
ALERT_SCORE_THRESHOLD = 75          # absolute score crossing → CRITICAL alert
ALERT_DELTA_THRESHOLD = 15          # 7-day delta crossing → ELEVATED alert
ALERT_DEDUP_HOURS = 24              # no re-alert same faultline+type within 24h
ALERT_EXPIRY_HOURS = 48             # auto-expire un-ack'd alerts after 48h

# ── Score levels (matches stability level vocabulary) ─────────────────────────
def _score_level(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "ELEVATED"
    if score >= 35:
        return "MONITOR"
    return "STABLE"


# ── Article ↔ faultline matching ──────────────────────────────────────────────
def pre_filter_articles(faultline: dict, articles: list[dict]) -> list[dict]:
    """
    Cheap pre-filter: keyword + tag + signal_bucket overlap with faultline definition.
    No LLM. Reduces ~1000 articles to ~5-30 candidates per faultline per day.
    Article passes if ANY of:
      - matches state (regions[] overlap)
      - title/summary contains any faultline keyword
      - tags[] overlap with faultline.tags
      - signal_bucket in faultline.signal_buckets
    Must match state OR (one keyword AND tag/signal_bucket overlap).
    """
    from faultline_seed import STATE_TO_REGIONS

    fl_state_regions = set(STATE_TO_REGIONS.get(faultline["state"], [faultline["state"]]))
    fl_keywords = [k.lower() for k in faultline.get("keywords", [])]
    fl_tags = set(faultline.get("tags", []))
    fl_buckets = set(faultline.get("signal_buckets", []))

    candidates: list[dict] = []
    for art in articles:
        # State match
        art_regions = set(art.get("regions") or [])
        if art.get("state"):
            art_regions.add(art["state"])
        state_match = bool(art_regions & fl_state_regions)

        # Tag match
        art_tags = set(art.get("tags") or [])
        tag_match = bool(art_tags & fl_tags)

        # Signal bucket match
        bucket_match = (art.get("signal_bucket") or "") in fl_buckets

        # Keyword match (title + summary, case-insensitive substring)
        haystack = " ".join([
            (art.get("title") or "").lower(),
            (art.get("ai_summary") or "").lower(),
        ])
        kw_match = any(kw in haystack for kw in fl_keywords)

        # LOC focus match (extra keywords from faultline.loc_focus, if present)
        loc_kw = [l.lower() for l in faultline.get("loc_focus", [])]
        loc_match = any(lk in haystack for lk in loc_kw) if loc_kw else False

        # Require state match + at least one of {tag, bucket, keyword, loc_focus}
        if state_match and (tag_match or bucket_match or kw_match or loc_match):
            candidates.append(art)

    return candidates


# ── Stage 2: sub-issue structured matching ───────────────────────────────────
# Threshold below which an (article, subissue) pair is dropped before LLM.
# Set low enough to catch weak-but-real signals; Stage 3 LLM filters further.
SUBISSUE_STRUCTURED_THRESHOLD = 25

# Tags → actor_type mapping (extend as new tags are introduced)
_TAG_TO_ACTOR_TYPE: dict[str, str] = {
    "Ethnic / Tribal Tension":                  "ethnic_org",
    "Insurgency / Militancy":                   "insurgent_group",
    "Foreign Influence (China/Pakistan/USA)":   "chinese_entity",
    "Border Security":                          "border_force",
    "Arms Smuggling":                           "smuggler_network",
    "Drug Trafficking":                         "smuggler_network",
    "Radicalization Indicator":                 "isl_outfit",
    "Infrastructure / Logistics Disruption":    "road_authority",
    "Floods / Climate Impact":                  "flood_authority",
    "Military Movement":                        "paramilitary",
    "Political Developments":                   "political_party",
    "Information Warfare / Narrative":          "political_party",
}

# Tags → event_type mapping
_TAG_TO_EVENT_TYPE: dict[str, str] = {
    "Civil Unrest":                             "protest",
    "Insurgency / Militancy":                   "militant_attack",
    "Infrastructure / Logistics Disruption":    "road_closure",
    "Floods / Climate Impact":                  "flood",
    "Arms Smuggling":                           "smuggling_case",
    "Drug Trafficking":                         "smuggling_case",
    "Illegal Immigration":                      "illegal_migration_case",
}

# threat_trajectory → coarse event_type
_TRAJ_TO_EVENT_TYPE: dict[str, str] = {
    "ESCALATING": "militant_attack",
    "DE_ESCALATING": "protest",
}


def match_subissues_to_article(
    faultline: dict,
    article: dict,
    subissues: list[dict],
) -> list[dict]:
    """
    Stage 2: deterministic sub-issue matching — no LLM.

    Scores each (article, subissue) pair using keyword, LOC, actor-type,
    event-type, and narrative-marker overlap. Returns only sub-issues
    that scored >= SUBISSUE_STRUCTURED_THRESHOLD, sorted desc.

    Each returned item: {subissue, structured_score, matched_features}
    """
    haystack = " ".join([
        (article.get("title") or "").lower(),
        (article.get("ai_summary") or "").lower(),
        (article.get("why_it_matters") or "").lower(),
    ])

    # Infer article actor_types from tags
    art_tags = set(article.get("tags") or [])
    art_actor_types = {_TAG_TO_ACTOR_TYPE[t] for t in art_tags if t in _TAG_TO_ACTOR_TYPE}

    # Infer article event_types from tags + threat_trajectory
    art_event_types = {_TAG_TO_EVENT_TYPE[t] for t in art_tags if t in _TAG_TO_EVENT_TYPE}
    traj = article.get("threat_trajectory") or ""
    if traj in _TRAJ_TO_EVENT_TYPE:
        art_event_types.add(_TRAJ_TO_EVENT_TYPE[traj])

    # Build article location corpus for loc_focus matching
    loc_corpus: set[str] = set()
    for loc in (article.get("locations_mentioned") or []):
        loc_corpus.add(loc.lower())
    entities = article.get("entities") or {}
    for loc in (entities.get("locations") or []):
        loc_corpus.add(loc.lower())
    if article.get("district"):
        loc_corpus.add(article["district"].lower())

    results = []
    for si in subissues:
        if not si.get("enabled", True):
            continue

        # Keyword hits
        si_kw = [k.lower() for k in si.get("keywords", [])]
        kw_hit = [k for k in si_kw if k in haystack]

        # LOC hits (haystack + entity locations)
        loc_hit = [
            loc for loc in si.get("loc_focus", [])
            if loc.lower() in haystack or loc.lower() in loc_corpus
        ]

        # Actor type hits
        actor_hit = [a for a in si.get("actor_types", []) if a in art_actor_types]

        # Event type hits
        event_hit = [e for e in si.get("event_types", []) if e in art_event_types]

        # Narrative marker hits
        marker_hit = [
            m for m in si.get("narrative_markers", [])
            if m.lower() in haystack
        ]

        # Weighted score (weights sum to 100)
        keyword_score = min(40, len(kw_hit) * 10)
        loc_score     = min(25, len(loc_hit) * 12)
        actor_score   = min(15, len(actor_hit) * 8)
        event_score   = min(12, len(event_hit) * 6)
        marker_score  = min(8,  len(marker_hit) * 4)
        structured_score = keyword_score + loc_score + actor_score + event_score + marker_score

        if structured_score >= SUBISSUE_STRUCTURED_THRESHOLD:
            results.append({
                "subissue": si,
                "structured_score": structured_score,
                "matched_features": {
                    "keywords_hit": kw_hit[:6],
                    "actor_types_hit": actor_hit,
                    "event_types_hit": event_hit,
                    "narrative_markers_hit": marker_hit[:4],
                    "loc_hits": loc_hit[:5],
                },
            })

    return sorted(results, key=lambda x: x["structured_score"], reverse=True)


async def _fetch_subissues(db, faultline_id: str) -> list[dict]:
    """Load enabled sub-issues for a faultline from db.faultline_subissues."""
    return await db.faultline_subissues.find(
        {"faultline_id": faultline_id, "enabled": True},
        {"_id": 1, "faultline_id": 1, "name": 1, "description": 1, "keywords": 1,
         "actor_types": 1, "event_types": 1, "narrative_markers": 1, "loc_focus": 1,
         "default_weight": 1, "cross_border_relevance": 1, "enabled": 1},
    ).to_list(length=50)


def _build_subissues_block(matched: list[dict]) -> str:
    """Format matched sub-issues list for LLM prompt injection."""
    lines = []
    for m in matched[:5]:
        si = m["subissue"]
        feat = m["matched_features"]
        sid = str(si.get("_id", si.get("name", "unknown")))
        parts = []
        if feat["keywords_hit"]:
            parts.append(f"keywords={feat['keywords_hit'][:3]}")
        if feat["loc_hits"]:
            parts.append(f"loc={feat['loc_hits'][:3]}")
        if feat["actor_types_hit"]:
            parts.append(f"actors={feat['actor_types_hit']}")
        if feat["event_types_hit"]:
            parts.append(f"events={feat['event_types_hit']}")
        line = (
            f"- [{sid}] {si['name']}: {si.get('description', '')}\n"
            f"  Matched: {' | '.join(parts) or 'keyword overlap'}"
        )
        lines.append(line)
    return "\n".join(lines) if lines else "None"


# ── LLM impact scoring ────────────────────────────────────────────────────────
FAULTLINE_IMPACT_PROMPT = """You are scoring how a single news article affects a specific faultline.

FAULTLINE: {fl_name} ({fl_state})
DESCRIPTION: {fl_description}

ARTICLE:
Title: {title}
Summary: {summary}
Source: {source}
Severity: {severity} | Priority: {priority}/100 | Trajectory: {trajectory}

Score the article's impact on THIS faultline (not in general).

Return strict JSON only:
{{
  "impact_score": 0-100 integer (0=no impact, 50=moderate, 100=major escalation),
  "direction": "ESCALATING" | "STABLE" | "DE_ESCALATING",
  "confidence": 0-100 integer (how confident this article actually relates to this faultline),
  "rationale": "1-2 sentence explanation citing specific article content",
  "evidence_phrases": ["phrase 1 from article", "phrase 2 from article"]
}}

Be conservative on confidence. If the article is only tangentially related, set confidence below 40.
"""

# Sub-issue-aware prompt (Stage 3). Used when matched_subissues is provided.
FAULTLINE_IMPACT_PROMPT_V2 = """You are assessing how a news article affects a specific security faultline and its sub-issues.

FAULTLINE: {fl_name} | State/Region: {fl_state}
{fl_description}

MATCHED SUB-ISSUES (deterministic pre-screening found these relevant):
{subissues_block}

ARTICLE:
Title: {title}
Summary: {summary}
Severity: {severity} | Priority: {priority}/100 | Trajectory: {trajectory}
Signal Strength: {signal_strength}/100 | India Relevance: {india_relevance}/100

Score how much this article impacts each matched sub-issue and the overall faultline.
0 = no impact, 50 = moderate signal, 100 = direct major escalation of that sub-issue.
loc_risk_flag = true ONLY if the article directly confirms NH/railway/bridge/river disruption.

Return strict JSON only, no prose:
{{
  "subissue_impacts": [
    {{
      "subissue_id": "<the id/name string from the sub-issue block above>",
      "impact_score": 0-100,
      "rationale": "1-2 sentences citing specific article content",
      "confidence": 0-100
    }}
  ],
  "overall_faultline_impact_score": 0-100,
  "overall_rationale": "1-2 sentences",
  "overall_confidence": 0-100,
  "loc_risk_flag": true
}}

Be conservative on confidence. Tangential articles → confidence below 40.
If article does not support a sub-issue despite pre-screen, set impact_score 0 for it.
"""


async def score_article_faultline_impact(
    faultline: dict,
    article: dict,
    llm_client=None,
    model: str = None,
    matched_subissues: list[dict] | None = None,
) -> Optional[dict]:
    """
    LLM call: score one article against one faultline.
    Returns dict with impact_score, direction, confidence, rationale, evidence_phrases.
    Returns None on LLM failure.
    """
    if llm_client is None or model is None:
        from llm_client import get_client, MODEL as DEFAULT_MODEL
        if llm_client is None:
            llm_client = get_client()
        if model is None:
            model = DEFAULT_MODEL

    if matched_subissues:
        # Stage 3: sub-issue-aware prompt
        prompt = FAULTLINE_IMPACT_PROMPT_V2.format(
            fl_name=faultline["name"],
            fl_state=faultline["state"],
            fl_description=faultline.get("description", ""),
            subissues_block=_build_subissues_block(matched_subissues),
            title=(article.get("title") or "")[:200],
            summary=(article.get("ai_summary") or article.get("raw_content") or "")[:600],
            severity=article.get("severity") or "low",
            priority=article.get("priority_score") or 0,
            trajectory=article.get("threat_trajectory") or "INDETERMINATE",
            signal_strength=article.get("signal_strength") or 0,
            india_relevance=article.get("india_relevance_score") or 0,
        )
        max_tokens = 600  # more tokens needed for subissue_impacts array
    else:
        # Legacy path: original single-faultline prompt
        prompt = FAULTLINE_IMPACT_PROMPT.format(
            fl_name=faultline["name"],
            fl_state=faultline["state"],
            fl_description=faultline.get("description", ""),
            title=(article.get("title") or "")[:200],
            summary=(article.get("ai_summary") or article.get("raw_content") or "")[:600],
            source=article.get("source") or "",
            severity=article.get("severity") or "low",
            priority=article.get("priority_score") or 0,
            trajectory=article.get("threat_trajectory") or "INDETERMINATE",
        )
        max_tokens = 400

    raw_text = ""
    try:
        # OpenAI/OpenRouter chat completions API (used by llm_client.get_client).
        # NOTE: not Anthropic SDK — get_client() returns AsyncOpenAI.
        # `response_format` asks OpenRouter to coerce the model into valid JSON,
        # which removes 95% of parse failures on Gemini 2.5 Flash.
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            ),
            timeout=45,
        )
        raw_text = resp.choices[0].message.content if resp.choices else ""
        text = raw_text or ""

        # Strip <think>…</think> blocks (Gemini 2.5 Flash reasoning tokens)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        # Strip code fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

        # Robust JSON extraction: find first '{' and last '}' if the model
        # surrounded the JSON with explanatory prose.
        if text and not text.startswith("{"):
            lo = text.find("{")
            hi = text.rfind("}")
            if lo != -1 and hi != -1 and hi > lo:
                text = text[lo:hi + 1]

        if not text:
            logger.warning(
                f"score_article_faultline_impact empty response for "
                f"{faultline['id']}/{article.get('id')}. raw={raw_text[:200]!r}"
            )
            return None

        data = json.loads(text)

        # Constrain `direction` to known vocabulary — prevent arbitrary LLM strings
        direction = data.get("direction") or "STABLE"
        if direction not in ("ESCALATING", "STABLE", "DE_ESCALATING"):
            direction = "STABLE"

        # Coerce numeric fields tolerantly: LLM sometimes returns "75" instead of 75
        def _to_int(value, default: int = 0) -> int:
            if value is None:
                return default
            if isinstance(value, bool):
                return default
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(float(value.strip()))
                except (ValueError, AttributeError):
                    return default
            return default

        # Clamp + sanitize. LLM string fields go through _sanitize_llm_string to
        # strip markup-like characters (prevents prompt-injected payloads from
        # embedding HTML / template tokens into the stored audit trail).
        if matched_subissues and "overall_faultline_impact_score" in data:
            # V2 response: subissue_impacts + overall fields
            raw_si = data.get("subissue_impacts") or []
            sanitized_si = []
            for si in raw_si[:10]:
                if not isinstance(si, dict):
                    continue
                sanitized_si.append({
                    "subissue_id": _sanitize_llm_string(str(si.get("subissue_id", "")), 200),
                    "impact_score": max(0, min(100, _to_int(si.get("impact_score")))),
                    "rationale": _sanitize_llm_string(si.get("rationale", ""), 400),
                    "confidence": max(0, min(100, _to_int(si.get("confidence")))),
                })
            return {
                # Legacy-compatible fields (overall values)
                "impact_score": max(0, min(100, _to_int(data.get("overall_faultline_impact_score")))),
                "direction": direction,
                "confidence": max(0, min(100, _to_int(data.get("overall_confidence")))),
                "rationale": _sanitize_llm_string(data.get("overall_rationale", ""), 500),
                "evidence_phrases": [],
                # V2 extension fields
                "subissue_impacts": sanitized_si,
                "loc_risk_flag": bool(data.get("loc_risk_flag", False)),
            }
        return {
            "impact_score": max(0, min(100, _to_int(data.get("impact_score")))),
            "direction": direction,
            "confidence": max(0, min(100, _to_int(data.get("confidence")))),
            "rationale": _sanitize_llm_string(data.get("rationale"), 500),
            "evidence_phrases": _sanitize_llm_list(data.get("evidence_phrases"), 3, 120),
        }
    except asyncio.TimeoutError:
        logger.warning(
            f"score_article_faultline_impact TIMEOUT for "
            f"{faultline['id']}/{article.get('id')}"
        )
        return None
    except json.JSONDecodeError as e:
        logger.warning(
            f"score_article_faultline_impact JSON parse failed for "
            f"{faultline['id']}/{article.get('id')}: {e}. raw={raw_text[:300]!r}"
        )
        return None
    except Exception as e:
        logger.warning(
            f"score_article_faultline_impact failed for "
            f"{faultline['id']}/{article.get('id')}: {type(e).__name__}: {e}. "
            f"raw={raw_text[:200]!r}"
        )
        return None


# ── Significance gate (de-saturation) ─────────────────────────────────────────
# Only articles the LLM judged as genuinely impacting the faultline count toward
# the score. A pre-filter keyword hit is NOT enough — the LLM must assign real
# impact + confidence. This is what stops "every state article → score 100".
SIG_IMPACT_MIN = 45      # LLM impact_score floor to count
DECAY_LAMBDA   = 0.35   # exponential time-decay rate (λ): e^(-λ*age_days)
SIG_CONF_MIN = 45        # LLM confidence floor to count
VELOCITY_PER_ARTICLE = 8 # 12.5 significant articles → velocity caps (was 5 = 20)


# ── Daily score computation (mirrors stability formula in trends.py) ──────────
def compute_faultline_score(
    matched_articles: list[dict],
    mappings: list[dict],
    target_date: Optional[str] = None,
) -> dict:
    """
    Compute composite faultline score from matched articles + their LLM impact mappings.

    De-saturated design (demo build):
      1. Only LLM-significant articles count (impact >= SIG_IMPACT_MIN AND
         confidence >= SIG_CONF_MIN). A bare keyword match no longer inflates
         the score — the LLM has to judge real impact.
      2. LLM impact is HALF the final score (was ~24% via confidence blend),
         so day-to-day variance from the LLM actually shows in the trendline.
      3. Velocity de-capped: 12.5 significant articles to max (was 20 raw → cap
         at n=20 meant every busy day pegged 100).
      4. Exponential time-decay (λ=0.35) prevents stale articles in the 7-day
         window from holding a faultline at CRITICAL when no new news arrived.
         Day-0 article = weight 1.0; Day-6 article = weight 0.12.

    Formula backbone (weights scoped to SIGNIFICANT articles, decay-weighted):
      raw = severity_load×0.40 + velocity×0.25 + actor_spread×0.20 + cross_border×0.15
      final = 0.5×raw + 0.5×avg_llm_impact

    Returns {raw_score, severity_load, velocity, actor_spread, cross_border,
             n_articles, n_significant, avg_impact, avg_confidence}
    """
    n_total = len(matched_articles)
    if n_total == 0:
        return {
            "raw_score": 0.0, "severity_load": 0.0, "velocity": 0.0,
            "actor_spread": 0.0, "cross_border": 0.0,
            "n_articles": 0, "n_significant": 0,
            "avg_impact": 0.0, "avg_confidence": 0.0,
        }

    # Gate: keep only (article, mapping) pairs the LLM judged significant.
    sig_articles: list[dict] = []
    sig_mappings: list[dict] = []
    for art, m in zip(matched_articles, mappings):
        if m.get("impact_score", 0) >= SIG_IMPACT_MIN and m.get("confidence", 0) >= SIG_CONF_MIN:
            sig_articles.append(art)
            sig_mappings.append(m)

    n = len(sig_articles)
    if n == 0:
        # Nothing significant today — faultline quiet.
        return {
            "raw_score": 0.0, "severity_load": 0.0, "velocity": 0.0,
            "actor_spread": 0.0, "cross_border": 0.0,
            "n_articles": n_total, "n_significant": 0,
            "avg_impact": 0.0, "avg_confidence": 0.0,
        }

    # ── Time-decay weights ────────────────────────────────────────────────────
    # e^(-λ * age_days): Day 0=1.0, Day 1=0.70, Day 2=0.49 … Day 6=0.12
    ref_date = None
    if target_date:
        try:
            ref_date = datetime.fromisoformat(target_date).date()
        except Exception:
            pass

    def _decay(art: dict) -> float:
        if ref_date is None:
            return 1.0
        pub = art.get("published_at", "")
        if not pub:
            return 1.0
        try:
            age = (ref_date - datetime.fromisoformat(pub[:10]).date()).days
            return math.exp(-DECAY_LAMBDA * max(0, age))
        except Exception:
            return 1.0

    weights = [_decay(a) for a in sig_articles]
    total_w = sum(weights) or 1.0

    # Severity load (0-100): decay-weighted average severity × 25
    sev_sum = sum(_SEV_WEIGHT.get(a.get("severity", "low"), 1) * w
                  for a, w in zip(sig_articles, weights))
    severity_load = (sev_sum / total_w) * 25

    # Velocity (0-100): decay-weighted effective article count
    velocity = min(100, total_w * VELOCITY_PER_ARTICLE)

    # Actor spread (0-100): unique actors + locations — presence-based, not decayed
    actors = set()
    for a in sig_articles:
        for actor in (a.get("actors") or []):
            actors.add(actor)
        entities = a.get("entities") or {}
        for loc in (entities.get("locations") or []):
            actors.add(loc)
    actor_spread = min(100, len(actors) * 10)

    # Cross-border share (0-100) — ratio, not decayed
    cb_count = sum(1 for a in sig_articles if a.get("is_cross_border"))
    cross_border = (cb_count / n) * 100

    # LLM impact — decay-weighted mean over significant mappings
    impacts = [m.get("impact_score", 0) for m in sig_mappings]
    confidences = [m.get("confidence", 0) for m in sig_mappings]
    avg_impact = sum(imp * w for imp, w in zip(impacts, weights)) / total_w
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Composite
    raw_score = (
        severity_load * W_SEVERITY_LOAD
        + velocity * W_VELOCITY
        + actor_spread * W_ACTOR_SPREAD
        + cross_border * W_CROSS_BORDER
    )

    # LLM impact is HALF the score → real day-to-day variance shows
    final_raw = 0.5 * raw_score + 0.5 * avg_impact

    return {
        "raw_score": round(final_raw, 2),
        "severity_load": round(severity_load, 2),
        "velocity": round(velocity, 2),
        "actor_spread": round(actor_spread, 2),
        "cross_border": round(cross_border, 2),
        "n_articles": n_total,
        "n_significant": n,
        "avg_impact": round(avg_impact, 2),
        "avg_confidence": round(avg_confidence, 2),
    }


# ── Sub-issue-aware daily scoring ────────────────────────────────────────────
def compute_faultline_score_v2(
    matched_articles: list[dict],
    subissue_match_docs: list[dict],
    subissues_by_id: dict[str, dict],
    target_date: Optional[str] = None,
) -> dict:
    """
    Sub-issue-aware scoring. Same stability backbone as compute_faultline_score.

    Each (article, subissue) combined_impact_score replaces the raw LLM impact.
    Formula per pair:
      combined = 0.4*llm_impact + 0.3*structured_score + 0.2*(sev/4*100) + 0.1*priority_norm
      eff      = combined * subissue.default_weight

    Final: final_raw = 0.5 * raw_score + 0.5 * avg_combined_impact  (same backbone)

    Returns same keys as compute_faultline_score plus:
      dominant_subissues: top-3 sub-issues by contribution
      loc_risk: bool — True if any dominant sub-issue has loc_focus
    """
    if not matched_articles or not subissue_match_docs:
        base = compute_faultline_score([], [], target_date=target_date)
        return {**base, "dominant_subissues": [], "loc_risk": False}

    art_map = {a["id"]: a for a in matched_articles}

    subissue_contrib: dict[str, float] = {}
    subissue_articles: dict[str, list[str]] = {}
    cross_border_count = 0
    combined_impacts: list[float] = []
    sig_article_ids: set[str] = set()

    for m in subissue_match_docs:
        if m.get("llm_confidence", 0) < SIG_CONF_MIN:
            continue
        if m.get("llm_impact_score", 0) < SIG_IMPACT_MIN:
            continue

        art = art_map.get(m["article_id"])
        sev_w = _SEV_WEIGHT.get((art or {}).get("severity", "low"), 1) if art else 1
        pri = min((art or {}).get("priority_score") or 0, 100) if art else 0
        si = subissues_by_id.get(str(m.get("subissue_id", "")), {})
        default_w = si.get("default_weight", 0.5)

        combined = (
            0.4 * m.get("llm_impact_score", 0)
            + 0.3 * m.get("structured_score", 0)
            + 0.2 * (sev_w / 4 * 100)
            + 0.1 * pri
        )
        eff = combined * default_w

        si_id = str(m.get("subissue_id", ""))
        subissue_contrib[si_id] = subissue_contrib.get(si_id, 0.0) + eff
        subissue_articles.setdefault(si_id, []).append(m["article_id"])
        combined_impacts.append(eff)

        if si.get("cross_border_relevance") or (art or {}).get("is_cross_border"):
            cross_border_count += 1
        if art:
            sig_article_ids.add(art["id"])

    if not combined_impacts:
        base = compute_faultline_score([], [], target_date=target_date)
        return {**base, "dominant_subissues": [], "loc_risk": False}

    sig_articles = [art_map[aid] for aid in sig_article_ids if aid in art_map]

    # Re-use existing backbone for severity_load, velocity, actor_spread
    # Build fake mappings list (combined_impact as impact_score, 70 confidence)
    fake_mappings = [
        {"impact_score": min(100, v), "confidence": 70}
        for v in combined_impacts
    ]
    base = compute_faultline_score(sig_articles, fake_mappings, target_date=target_date)

    # Override cross_border with sub-issue-aware value
    cb = (cross_border_count / len(combined_impacts)) * 100 if combined_impacts else 0.0
    raw_score = (
        base["severity_load"] * W_SEVERITY_LOAD
        + base["velocity"] * W_VELOCITY
        + base["actor_spread"] * W_ACTOR_SPREAD
        + cb * W_CROSS_BORDER
    )
    avg_combined = sum(combined_impacts) / len(combined_impacts)
    final_raw = round(0.5 * raw_score + 0.5 * avg_combined, 2)

    # Top-3 dominant sub-issues
    top3 = sorted(subissue_contrib.items(), key=lambda x: x[1], reverse=True)[:3]
    dominant = []
    for sid, contrib in top3:
        si = subissues_by_id.get(sid, {})
        dominant.append({
            "subissue_id": sid,
            "name": si.get("name", sid),
            "loc_focus": si.get("loc_focus", []),
            "contribution": round(contrib, 2),
            "sample_article_ids": subissue_articles.get(sid, [])[:3],
        })

    loc_risk = any(bool(d.get("loc_focus")) for d in dominant)

    return {
        **base,
        "raw_score": final_raw,
        "cross_border": round(cb, 2),
        "n_significant": len(sig_article_ids),
        "avg_impact": round(avg_combined, 2),
        "dominant_subissues": dominant,
        "loc_risk": loc_risk,
    }


# ── Cross-faultline propagation ───────────────────────────────────────────────
def apply_propagation(
    raw_scores: dict[str, float],
    faultlines: list[dict],
    propagation_factor: float = 0.2,
) -> dict[str, float]:
    """
    Apply weighted cross-faultline influence.
    For each faultline f:
      final[f] = raw[f] + propagation_factor × Σ(raw[g] × weight[g→f])

    Capped at 100. Propagation_factor < 1 prevents runaway feedback loops.
    Single-pass (no iterative convergence — keeps it cheap and predictable).
    """
    # Build reverse graph: target faultline → list of (source, weight)
    reverse_graph: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for fl in faultlines:
        for link in fl.get("linked_faultlines", []):
            target = link.get("id")
            weight = link.get("weight", 0)
            if target and weight > 0:
                reverse_graph[target].append((fl["id"], float(weight)))

    final_scores: dict[str, float] = {}
    for fl in faultlines:
        fl_id = fl["id"]
        own = raw_scores.get(fl_id, 0.0)
        boost = 0.0
        for src_id, w in reverse_graph.get(fl_id, []):
            boost += raw_scores.get(src_id, 0.0) * w
        final = own + propagation_factor * boost
        final_scores[fl_id] = min(100.0, round(final, 2))

    return final_scores


# ── Alert detection ───────────────────────────────────────────────────────────
async def evaluate_alerts(
    db, faultline: dict, today_score: float, today_breakdown: dict
) -> Optional[dict]:
    """
    Decide whether to emit a warning alert for this faultline.
    Triggers:
      - score >= ALERT_SCORE_THRESHOLD (CRITICAL)
      - delta 7d >= ALERT_DELTA_THRESHOLD (SHARP_RISE)
    Dedup: skip if active un-ack'd alert exists for same faultline+type within ALERT_DEDUP_HOURS.

    Returns alert dict if emitted, else None.
    """
    now = datetime.now(timezone.utc)
    fl_id = faultline["id"]

    # Determine alert type
    alert_type = None
    reason = ""
    if today_score >= ALERT_SCORE_THRESHOLD:
        alert_type = "CRITICAL"
        reason = f"Score {today_score:.0f}/100 crossed critical threshold ({ALERT_SCORE_THRESHOLD})"

    # Compute 7-day delta from history
    week_ago = (now - timedelta(days=7)).date().isoformat()
    cursor = db.faultline_scores.find(
        {"faultline_id": fl_id, "date": {"$lte": week_ago}},
        {"score": 1, "date": 1},
    ).sort("date", -1).limit(1)
    prev = await cursor.to_list(length=1)
    if prev:
        delta = today_score - prev[0].get("score", 0)
        if delta >= ALERT_DELTA_THRESHOLD and alert_type != "CRITICAL":
            alert_type = "SHARP_RISE"
            reason = f"Score rose {delta:+.0f} pts in 7 days (now {today_score:.0f}/100)"

    if not alert_type:
        return None

    # Dedup: skip if recent alert exists
    dedup_cutoff = (now - timedelta(hours=ALERT_DEDUP_HOURS)).isoformat()
    existing = await db.faultline_alerts.find_one({
        "faultline_id": fl_id,
        "alert_type": alert_type,
        "created_at": {"$gte": dedup_cutoff},
        "acknowledged": {"$ne": True},
    })
    if existing:
        return None

    dominant = today_breakdown.get("dominant_subissues", [])
    loc_risk = today_breakdown.get("loc_risk", False)
    loc_segment = ", ".join(
        loc for d in dominant for loc in (d.get("loc_focus") or [])
    )[:200]

    if dominant:
        sub_names = ", ".join(d["name"] for d in dominant[:2])
        reason = f"{reason}. Leading sub-issues: {sub_names}."
        if loc_risk and loc_segment:
            reason = f"{reason} LOC at risk: {loc_segment}."

    alert = {
        "id": str(uuid.uuid4()),
        "faultline_id": fl_id,
        "faultline_name": faultline["name"],
        "state": faultline["state"],
        "alert_type": alert_type,
        "level": _score_level(today_score),
        "score": today_score,
        "score_breakdown": today_breakdown,
        "reason": reason,
        "trend_direction": "ESCALATING" if today_score >= 55 else "STABLE",
        "dominant_subissues": dominant,
        "loc_risk": loc_risk,
        "loc_segment": loc_segment,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=ALERT_EXPIRY_HOURS)).isoformat(),
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
    }
    await db.faultline_alerts.insert_one(alert)

    # Dispatch in-app + push notification for this alert
    try:
        from utils.notifications import create_and_dispatch_notification, resolve_system_notification_recipients
        recipients = await resolve_system_notification_recipients(
            db, "FAULTLINE_ESCALATION", {"faultline_id": fl_id}
        )
        if recipients:
            await create_and_dispatch_notification(
                notif_type="FAULTLINE_ESCALATION",
                title=f"Faultline Alert: {faultline['name']}",
                body=reason,
                payload={
                    "faultline_id": fl_id,
                    "faultline_name": faultline["name"],
                    "alert_type": alert_type,
                    "score": today_score,
                    "state": faultline.get("state", ""),
                },
                deep_link=f"/faultlines/{fl_id}",
                source_type="system",
                source_id=fl_id,
                created_by=None,
                recipient_user_ids=recipients,
            )
    except Exception as _notif_err:
        import logging as _log
        _log.getLogger("faultline_engine").warning(
            f"Notification dispatch failed for faultline alert {fl_id}: {_notif_err}"
        )

    return alert


# ── Daily orchestrator ────────────────────────────────────────────────────────
async def run_daily_faultline_pass(
    db,
    target_date: Optional[str] = None,
    max_articles_per_faultline: int = 12,
    llm_concurrency: int = 4,
) -> dict:
    """
    Main daily orchestration. Idempotent — re-run for same date overwrites.

    target_date: ISO YYYY-MM-DD. Defaults to today UTC.
    max_articles_per_faultline: cap LLM calls per faultline per day (cost control).
    llm_concurrency: parallel LLM calls per faultline.

    Returns summary dict.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date().isoformat()

    # Window: articles published in last 7 days (so velocity reflects recent activity)
    window_end = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc) + timedelta(days=1)
    window_start = window_end - timedelta(days=7)

    logger.info(f"Faultline pass for {target_date} (window {window_start.date()} → {window_end.date()})")

    # Load active faultlines
    faultlines = await db.faultlines.find({"active": True}).to_list(length=500)
    if not faultlines:
        logger.warning("No active faultlines configured. Run /api/faultlines/seed first.")
        return {"date": target_date, "faultlines_scored": 0, "alerts_emitted": 0}

    # Load articles in window (project fields needed for scoring + sub-issue matching)
    articles = await db.intelligence_items.find(
        {
            "published_at": {"$gte": window_start.isoformat(), "$lt": window_end.isoformat()},
            "processed": True,
            "is_relevant": {"$ne": False},
            "is_archived": {"$ne": True},
        },
        {
            "id": 1, "title": 1, "ai_summary": 1, "source": 1, "source_url": 1,
            "published_at": 1, "severity": 1, "priority_score": 1, "tags": 1,
            "signal_bucket": 1, "regions": 1, "state": 1, "actors": 1,
            "entities": 1, "is_cross_border": 1, "threat_trajectory": 1,
            # Stage 2 sub-issue matching needs these extra fields
            "why_it_matters": 1, "signal_strength": 1, "india_relevance_score": 1,
            "district": 1, "locations_mentioned": 1, "threat_category": 1,
        },
    ).to_list(length=5000)

    logger.info(f"Loaded {len(faultlines)} faultlines, {len(articles)} articles in window")

    # LLM client setup
    try:
        from llm_client import get_client, MODEL
        llm_client = get_client()
    except Exception as e:
        logger.error(f"LLM client unavailable, skipping LLM impact scoring: {e}")
        llm_client = None
        MODEL = None

    sem = asyncio.Semaphore(llm_concurrency)
    raw_scores: dict[str, float] = {}
    breakdowns: dict[str, dict] = {}
    all_mappings_count = 0
    # Track LLM health across the whole pass. If zero successes but we attempted
    # calls, the day is LLM-dead (e.g. 402 insufficient credits) — the resume
    # logic must NOT treat such a day as "done".
    llm_attempts = 0
    llm_successes = 0

    for fl in faultlines:
        fl_id = fl["id"]
        candidates = pre_filter_articles(fl, articles)
        candidates = candidates[:max_articles_per_faultline]

        if not candidates:
            raw_scores[fl_id] = 0.0
            breakdowns[fl_id] = compute_faultline_score([], [], target_date=target_date)
            continue

        # ── Stage 2: sub-issue structured matching ────────────────────────────
        subissues = await _fetch_subissues(db, fl_id)
        subissue_mode = bool(subissues)

        # Map each article to its matched sub-issues (or None for legacy path)
        pairs: list[tuple[dict, list[dict] | None]] = []
        for art in candidates:
            if subissue_mode:
                matched = match_subissues_to_article(fl, art, subissues)
                if matched:
                    pairs.append((art, matched))
                # else: no sub-issue passed threshold — skip LLM for this article
            else:
                pairs.append((art, None))  # legacy: no sub-issues defined

        if not pairs:
            raw_scores[fl_id] = 0.0
            breakdowns[fl_id] = compute_faultline_score([], [], target_date=target_date)
            continue

        # ── Stage 3: LLM for articles that passed Stage 2 ────────────────────
        async def _score_one_v2(
            art: dict, matched_si: list[dict] | None
        ) -> tuple[dict, list[dict] | None, dict | None]:
            async with sem:
                result = await score_article_faultline_impact(
                    fl, art, llm_client, MODEL,
                    matched_subissues=matched_si,
                )
                return (art, matched_si, result)

        if llm_client:
            tasks = [_score_one_v2(art, msi) for art, msi in pairs]
            scored_triples = await asyncio.gather(*tasks, return_exceptions=False)
            llm_attempts += len(pairs)
            llm_successes += sum(1 for _, _, r in scored_triples if r is not None)
        else:
            scored_triples = [(art, msi, None) for art, msi in pairs]

        # ── Persist mappings + sub-issue matches ──────────────────────────────
        mapping_docs: list[dict] = []
        kept_articles: list[dict] = []
        mappings: list[dict] = []
        subissue_match_docs: list[dict] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for art, matched_si, llm_result in scored_triples:
            if llm_result is None:
                if llm_client:
                    continue  # LLM attempted but failed — don't use neutral fallback
                # LLM unavailable: fallback for no-LLM mode
                llm_result = {
                    "impact_score": 50, "direction": "STABLE", "confidence": 30,
                    "rationale": "Pre-filter match only (LLM unavailable)",
                    "evidence_phrases": [],
                }

            if llm_result.get("confidence", 0) < 25:
                continue

            # Legacy faultline_mappings write (backward compat)
            mapping = llm_result
            mapping_doc = {
                "id": str(uuid.uuid4()),
                "faultline_id": fl_id,
                "article_id": art["id"],
                "date": target_date,
                "impact_score": mapping["impact_score"],
                "direction": mapping["direction"],
                "confidence": mapping["confidence"],
                "rationale": mapping["rationale"],
                "evidence_phrases": mapping.get("evidence_phrases", []),
                "article_title": art.get("title", ""),
                "article_published_at": art.get("published_at", ""),
                "article_severity": art.get("severity", ""),
                "created_at": now_iso,
            }
            mapping_docs.append(mapping_doc)
            mappings.append(mapping)
            kept_articles.append(art)

            # Sub-issue match docs (V2 path)
            if matched_si and "subissue_impacts" in llm_result:
                si_impacts = llm_result["subissue_impacts"] or []
                for si_impact in si_impacts:
                    raw_sid = si_impact.get("subissue_id", "")
                    # Find the sub-issue whose name or _id matches
                    si_match = next(
                        (m for m in matched_si
                         if str(m["subissue"].get("_id", "")) == raw_sid
                         or m["subissue"].get("name", "") == raw_sid
                         or str(m["subissue"].get("_id", "")) in raw_sid),
                        None,
                    )
                    if si_match is None:
                        continue
                    si_doc = si_match["subissue"]
                    si_id = str(si_doc.get("_id", si_doc.get("name", "")))
                    llm_imp = si_impact.get("impact_score", 0)
                    struct_score = si_match["structured_score"]
                    combined = round(0.6 * llm_imp + 0.4 * struct_score, 2)
                    subissue_match_docs.append({
                        "article_id": art["id"],
                        "faultline_id": fl_id,
                        "subissue_id": si_id,
                        "date": target_date,
                        "structured_score": struct_score,
                        "llm_impact_score": llm_imp,
                        "combined_impact_score": combined,
                        "llm_confidence": si_impact.get("confidence", 0),
                        "rationale": _sanitize_llm_string(si_impact.get("rationale", ""), 400),
                        "matched_features": si_match["matched_features"],
                        "created_at": now_iso,
                    })

        # Upsert faultline_mappings (atomic, idempotent)
        if mapping_docs:
            kept_article_ids: list[str] = []
            for doc in mapping_docs:
                set_doc = {k: v for k, v in doc.items() if k != "id"}
                await db.faultline_mappings.update_one(
                    {"faultline_id": fl_id, "article_id": doc["article_id"], "date": target_date},
                    {"$set": set_doc, "$setOnInsert": {"id": doc["id"]}},
                    upsert=True,
                )
                kept_article_ids.append(doc["article_id"])

            await db.faultline_mappings.delete_many({
                "faultline_id": fl_id,
                "date": target_date,
                "article_id": {"$nin": kept_article_ids},
            })
            all_mappings_count += len(mapping_docs)

        # Upsert sub-issue matches
        for doc in subissue_match_docs:
            await db.article_faultline_subissue_matches.update_one(
                {"article_id": doc["article_id"], "faultline_id": fl_id,
                 "subissue_id": doc["subissue_id"]},
                {"$set": doc},
                upsert=True,
            )

        # ── Scoring ───────────────────────────────────────────────────────────
        if subissue_mode and subissue_match_docs:
            subissues_by_id = {
                str(si.get("_id", si.get("name", ""))): si for si in subissues
            }
            breakdown = compute_faultline_score_v2(
                kept_articles, subissue_match_docs, subissues_by_id,
                target_date=target_date,
            )
        else:
            breakdown = compute_faultline_score(kept_articles, mappings, target_date=target_date)

        raw_scores[fl_id] = breakdown["raw_score"]
        breakdowns[fl_id] = breakdown

    # Apply cross-faultline propagation
    final_scores = apply_propagation(raw_scores, faultlines)

    # Persist daily snapshots + evaluate alerts
    alerts_emitted = 0
    # Pass-level LLM health. llm_ok=True means at least one LLM call succeeded
    # this pass. If we made attempts but ALL failed (e.g. 402 insufficient
    # credits), llm_ok=False → resume will re-process this date later.
    # No attempts (no candidate articles anywhere) counts as ok=True — there
    # was genuinely nothing to score, re-running won't help.
    llm_ok = (llm_attempts == 0) or (llm_successes > 0)

    for fl in faultlines:
        fl_id = fl["id"]
        final = final_scores.get(fl_id, 0.0)
        breakdown = breakdowns[fl_id]
        snapshot = {
            "faultline_id": fl_id,
            "faultline_name": fl["name"],
            "state": fl["state"],
            "date": target_date,
            "score": final,
            "raw_score_pre_propagation": breakdown["raw_score"],
            "level": _score_level(final),
            "severity_load": breakdown["severity_load"],
            "velocity": breakdown["velocity"],
            "actor_spread": breakdown["actor_spread"],
            "cross_border": breakdown["cross_border"],
            "n_articles": breakdown["n_articles"],
            "n_significant": breakdown.get("n_significant", 0),
            "avg_impact": breakdown["avg_impact"],
            "avg_confidence": breakdown.get("avg_confidence", 0.0),
            "dominant_subissues": breakdown.get("dominant_subissues", []),
            "loc_risk": breakdown.get("loc_risk", False),
            "llm_ok": llm_ok,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.faultline_scores.replace_one(
            {"faultline_id": fl_id, "date": target_date},
            snapshot,
            upsert=True,
        )

        alert = await evaluate_alerts(db, fl, final, breakdown)
        if alert:
            alerts_emitted += 1

    if not llm_ok:
        logger.warning(
            f"Faultline pass {target_date}: LLM DEAD — {llm_attempts} attempts, "
            f"0 successes (likely 402/credits). Scores stored as 0; resume will redo this date."
        )

    return {
        "date": target_date,
        "faultlines_scored": len(faultlines),
        "articles_in_window": len(articles),
        "mappings_created": all_mappings_count,
        "alerts_emitted": alerts_emitted,
        "llm_attempts": llm_attempts,
        "llm_successes": llm_successes,
        "llm_ok": llm_ok,
    }


# ── Incremental pass (no LLM) ─────────────────────────────────────────────────
async def run_incremental_faultline_pass(
    db,
    lookback_hours: int = 6,
    faultline_id: Optional[str] = None,
) -> dict:
    """Keyword-only pass that appends newly processed articles to today's mappings.

    Runs every few hours to keep faultlines current without expensive LLM calls.
    Only inserts mappings for articles not yet seen today; leaves existing
    LLM-scored mappings untouched.

    faultline_id: when set, only updates that one faultline (used by per-faultline
                  refresh button). When None, scans all active faultlines.

    Returns a summary dict.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

    fl_query: dict = {"active": True}
    if faultline_id:
        fl_query["id"] = faultline_id

    faultlines = await db.faultlines.find(fl_query).to_list(length=500)
    if not faultlines:
        return {"date": today, "new_mappings": 0, "faultline_id": faultline_id}

    # New articles processed since cutoff
    articles = await db.intelligence_items.find(
        {
            "published_at": {"$gte": cutoff},
            "processed": True,
            "is_relevant": {"$ne": False},
            "is_archived": {"$ne": True},
        },
        {
            "id": 1, "title": 1, "ai_summary": 1, "source": 1, "source_url": 1,
            "published_at": 1, "severity": 1, "priority_score": 1, "tags": 1,
            "signal_bucket": 1, "regions": 1, "state": 1, "actors": 1,
            "entities": 1, "is_cross_border": 1, "threat_trajectory": 1,
        },
    ).to_list(length=2000)

    if not articles:
        logger.info(f"[incr-faultline] No new articles since {cutoff}")
        return {"date": today, "new_mappings": 0}

    logger.info(f"[incr-faultline] {len(articles)} new articles to map across {len(faultlines)} faultlines")

    # Pre-fetch article IDs already mapped today to skip them
    existing_today = set()
    async for m in db.faultline_mappings.find({"date": today}, {"article_id": 1, "_id": 0}):
        existing_today.add(m["article_id"])

    new_mappings = 0
    for fl in faultlines:
        fl_id = fl["id"]
        candidates = pre_filter_articles(fl, articles)
        fresh = [a for a in candidates if a["id"] not in existing_today]
        if not fresh:
            continue

        for art in fresh:
            doc = {
                "id": str(uuid.uuid4()),
                "faultline_id": fl_id,
                "article_id": art["id"],
                "date": today,
                "impact_score": 50,
                "direction": "STABLE",
                "confidence": 30,
                "rationale": "Keyword match (incremental pass — awaiting LLM score)",
                "evidence_phrases": [],
                "article_title": art.get("title", ""),
                "article_published_at": art.get("published_at", ""),
                "article_severity": art.get("severity", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.faultline_mappings.update_one(
                {"faultline_id": fl_id, "article_id": art["id"], "date": today},
                {"$setOnInsert": doc},
                upsert=True,
            )
            new_mappings += 1

    scope = faultline_id or "all"
    logger.info(f"[incr-faultline] Added {new_mappings} new keyword-matched mappings for {today} (scope: {scope})")
    return {"date": today, "new_mappings": new_mappings, "faultline_id": faultline_id}


# ── Backfill ──────────────────────────────────────────────────────────────────
BACKFILL_DEFAULT_LOOKBACK_DAYS = 90
BACKFILL_MAX_LOOKBACK_DAYS = 365


async def run_backfill(
    db,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    inter_day_sleep_seconds: float = 5.0,
    resume: bool = True,
) -> dict:
    """
    Backfill: re-run daily pass for each day in [start_date, end_date].

    Defaults:
      end_date   = today (UTC)
      start_date = max(end_date - BACKFILL_DEFAULT_LOOKBACK_DAYS, earliest article)

    If start_date is supplied explicitly, it is still capped at
    (end_date - BACKFILL_MAX_LOOKBACK_DAYS) to prevent multi-year runaway runs
    caused by a single stale article in the DB.

    resume=True (default): skip any date that already has score docs. If Render
    hibernates/OOMs mid-run, just re-fire the same backfill — it picks up where
    it left off instead of restarting from day 1. Set resume=False to force a
    full re-score (overwrites everything).

    Run as background task. Long-running.
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc).date().isoformat()
    end = datetime.fromisoformat(end_date).date()

    default_start = end - timedelta(days=BACKFILL_DEFAULT_LOOKBACK_DAYS)
    hard_floor = end - timedelta(days=BACKFILL_MAX_LOOKBACK_DAYS)

    if start_date is None:
        # Find earliest article, but clamp to default lookback so a stale
        # 2018 article cannot drag the backfill across 8 years.
        earliest = await db.intelligence_items.find(
            {}, {"published_at": 1}
        ).sort("published_at", 1).limit(1).to_list(length=1)
        if not earliest:
            return {"status": "no articles in DB"}
        article_earliest = datetime.fromisoformat(earliest[0]["published_at"][:10]).date()
        # Use the LATER of (today - 90d) and (earliest article date).
        # If articles are newer than 90 days, start from articles.
        # If articles are older than 90 days, start from 90 days ago.
        start = max(default_start, article_earliest)
        start_date = start.isoformat()
    else:
        # Explicit start_date — still cap at hard floor (today - 365d) to
        # block accidental multi-year runs from the caller.
        start = datetime.fromisoformat(start_date).date()
        if start < hard_floor:
            logger.warning(
                f"Backfill start_date {start} below hard floor {hard_floor}; "
                f"clamping to {hard_floor}"
            )
            start = hard_floor
            start_date = start.isoformat()

    logger.info(f"Backfill: {start} → {end} ({(end - start).days + 1} days)")

    days_processed = 0
    days_skipped = 0
    total_alerts = 0
    cur = start
    while cur <= end:
        cur_iso = cur.isoformat()
        try:
            if resume:
                # Skip a date only if it was scored with a HEALTHY LLM pass.
                # Dates scored during an LLM outage (llm_ok=False, e.g. 402
                # insufficient credits) are NOT considered done — they get
                # re-processed so a resume run after topping up credits fixes
                # the zero-score days. Legacy docs without the llm_ok field are
                # treated as healthy (don't redo old good data).
                healthy = await db.faultline_scores.count_documents({
                    "date": cur_iso,
                    "$or": [{"llm_ok": True}, {"llm_ok": {"$exists": False}}],
                })
                if healthy > 0:
                    days_skipped += 1
                    logger.info(f"Backfill {cur_iso}: SKIP (already scored, llm healthy)")
                    cur = cur + timedelta(days=1)
                    continue
            result = await run_daily_faultline_pass(db, target_date=cur_iso)
            days_processed += 1
            total_alerts += result.get("alerts_emitted", 0)
            logger.info(f"Backfill {cur_iso}: {result}")
        except Exception as e:
            logger.exception(f"Backfill failed for {cur_iso}: {e}")
        cur = cur + timedelta(days=1)
        await asyncio.sleep(inter_day_sleep_seconds)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "days_processed": days_processed,
        "days_skipped": days_skipped,
        "total_alerts_emitted": total_alerts,
    }
