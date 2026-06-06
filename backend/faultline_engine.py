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
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("faultline_engine")

# ── Severity weighting (matches trends.py / brief_monthly.py) ─────────────────
_SEV_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}

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

        # Require state match + at least one of {tag, bucket, keyword}
        if state_match and (tag_match or bucket_match or kw_match):
            candidates.append(art)

    return candidates


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


async def score_article_faultline_impact(
    faultline: dict, article: dict, llm_client=None, model: str = None
) -> Optional[dict]:
    """
    LLM call: score one article against one faultline.
    Returns dict with impact_score, direction, confidence, rationale, evidence_phrases.
    Returns None on LLM failure.
    """
    if llm_client is None:
        from llm_client import get_client, MODEL
        llm_client = get_client()
        model = model or MODEL

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

    try:
        resp = await asyncio.wait_for(
            llm_client.messages.create(
                model=model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=45,
        )
        text = resp.content[0].text if resp.content else ""
        # Strip code fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        data = json.loads(text)
        # Clamp + sanitize
        return {
            "impact_score": max(0, min(100, int(data.get("impact_score", 0)))),
            "direction": data.get("direction") or "STABLE",
            "confidence": max(0, min(100, int(data.get("confidence", 0)))),
            "rationale": (data.get("rationale") or "")[:500],
            "evidence_phrases": (data.get("evidence_phrases") or [])[:3],
        }
    except (asyncio.TimeoutError, json.JSONDecodeError, ValueError, KeyError, Exception) as e:
        logger.warning(f"score_article_faultline_impact failed for {faultline['id']}/{article.get('id')}: {e}")
        return None


# ── Daily score computation (mirrors stability formula in trends.py) ──────────
def compute_faultline_score(matched_articles: list[dict], mappings: list[dict]) -> dict:
    """
    Compute composite faultline score from matched articles + their LLM impact mappings.

    Formula (mirrors trends.py stability):
      score = severity_load × 0.40 + velocity × 0.25 + actor_spread × 0.20 + cross_border × 0.15

    severity_load: weighted average severity of matched articles (scaled to 0-100)
    velocity:      article count in last 7d normalized (more recent stories = higher)
    actor_spread:  number of distinct actors / locations mentioned (proxy for breadth)
    cross_border:  share of cross-border or foreign-influence articles

    Returns {raw_score, severity_load, velocity, actor_spread, cross_border, n_articles}
    """
    n = len(matched_articles)
    if n == 0:
        return {
            "raw_score": 0.0,
            "severity_load": 0.0,
            "velocity": 0.0,
            "actor_spread": 0.0,
            "cross_border": 0.0,
            "n_articles": 0,
            "avg_impact": 0.0,
            "avg_confidence": 0.0,
        }

    # Severity load (0-100): weighted average severity × 25 (since weights are 1-4)
    sev_sum = sum(_SEV_WEIGHT.get(a.get("severity", "low"), 1) for a in matched_articles)
    severity_load = (sev_sum / n) * 25

    # Velocity (0-100): article count, capped at 20 articles = 100
    velocity = min(100, n * 5)

    # Actor spread (0-100): unique actors + locations, capped at 10 = 100
    actors = set()
    for a in matched_articles:
        for actor in (a.get("actors") or []):
            actors.add(actor)
        entities = a.get("entities") or {}
        for loc in (entities.get("locations") or []):
            actors.add(loc)
    actor_spread = min(100, len(actors) * 10)

    # Cross-border share (0-100)
    cb_count = sum(1 for a in matched_articles if a.get("is_cross_border"))
    cross_border = (cb_count / n) * 100

    # LLM-weighted impact: avg impact × avg confidence/100
    impacts = [m.get("impact_score", 0) for m in mappings]
    confidences = [m.get("confidence", 0) for m in mappings]
    avg_impact = sum(impacts) / len(impacts) if impacts else 0
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Composite — same weight structure as stability
    raw_score = (
        severity_load * W_SEVERITY_LOAD
        + velocity * W_VELOCITY
        + actor_spread * W_ACTOR_SPREAD
        + cross_border * W_CROSS_BORDER
    )

    # Blend with LLM impact (LLM weighted to ~30%, formula to ~70%)
    llm_weight = (avg_confidence / 100) * 0.3
    final_raw = raw_score * (1 - llm_weight) + avg_impact * llm_weight

    return {
        "raw_score": round(final_raw, 2),
        "severity_load": round(severity_load, 2),
        "velocity": round(velocity, 2),
        "actor_spread": round(actor_spread, 2),
        "cross_border": round(cross_border, 2),
        "n_articles": n,
        "avg_impact": round(avg_impact, 2),
        "avg_confidence": round(avg_confidence, 2),
    }


# ── Cross-faultline propagation ───────────────────────────────────────────────
def apply_propagation(
    raw_scores: dict[str, float],
    faultlines: list[dict],
    propagation_factor: float = 0.5,
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
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=ALERT_EXPIRY_HOURS)).isoformat(),
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
    }
    await db.faultline_alerts.insert_one(alert)
    return alert


# ── Daily orchestrator ────────────────────────────────────────────────────────
async def run_daily_faultline_pass(
    db,
    target_date: Optional[str] = None,
    max_articles_per_faultline: int = 30,
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

    # Load articles in window (project only fields needed for scoring)
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

    async def _score_one(fl_id: str, art: dict, fl: dict) -> tuple[str, dict] | None:
        async with sem:
            result = await score_article_faultline_impact(fl, art, llm_client, MODEL)
            return (art["id"], result) if result else None

    for fl in faultlines:
        fl_id = fl["id"]
        candidates = pre_filter_articles(fl, articles)
        candidates = candidates[:max_articles_per_faultline]

        if not candidates:
            raw_scores[fl_id] = 0.0
            breakdowns[fl_id] = compute_faultline_score([], [])
            continue

        # Score each candidate via LLM (parallel within concurrency limit)
        mappings: list[dict] = []
        if llm_client:
            tasks = [_score_one(fl_id, art, fl) for art in candidates]
            results = await asyncio.gather(*tasks, return_exceptions=False)
        else:
            results = [None] * len(candidates)

        # Build mappings + persist
        mapping_docs: list[dict] = []
        kept_articles: list[dict] = []
        for art, scored in zip(candidates, results):
            if scored is None:
                # Fallback: keep article with neutral impact when LLM unavailable
                mapping = {
                    "impact_score": 50,
                    "direction": "STABLE",
                    "confidence": 30,
                    "rationale": "Pre-filter match only (LLM unavailable)",
                    "evidence_phrases": [],
                }
            else:
                mapping = scored[1]

            # Drop low-confidence mappings (<25) — keeps noise out
            if mapping["confidence"] < 25:
                continue

            mapping_doc = {
                "id": str(uuid.uuid4()),
                "faultline_id": fl_id,
                "article_id": art["id"],
                "date": target_date,
                "impact_score": mapping["impact_score"],
                "direction": mapping["direction"],
                "confidence": mapping["confidence"],
                "rationale": mapping["rationale"],
                "evidence_phrases": mapping["evidence_phrases"],
                "article_title": art.get("title", ""),
                "article_published_at": art.get("published_at", ""),
                "article_severity": art.get("severity", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            mapping_docs.append(mapping_doc)
            mappings.append(mapping)
            kept_articles.append(art)

        if mapping_docs:
            # Replace today's mappings for this faultline (idempotent)
            await db.faultline_mappings.delete_many({"faultline_id": fl_id, "date": target_date})
            await db.faultline_mappings.insert_many(mapping_docs)
            all_mappings_count += len(mapping_docs)

        breakdown = compute_faultline_score(kept_articles, mappings)
        raw_scores[fl_id] = breakdown["raw_score"]
        breakdowns[fl_id] = breakdown

    # Apply cross-faultline propagation
    final_scores = apply_propagation(raw_scores, faultlines)

    # Persist daily snapshots + evaluate alerts
    alerts_emitted = 0
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
            "avg_impact": breakdown["avg_impact"],
            "avg_confidence": breakdown["avg_confidence"],
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

    return {
        "date": target_date,
        "faultlines_scored": len(faultlines),
        "articles_in_window": len(articles),
        "mappings_created": all_mappings_count,
        "alerts_emitted": alerts_emitted,
    }


# ── Backfill ──────────────────────────────────────────────────────────────────
async def run_backfill(
    db,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    inter_day_sleep_seconds: float = 5.0,
) -> dict:
    """
    Backfill: re-run daily pass for each day in [start_date, end_date].

    Defaults: start_date = earliest published_at in intelligence_items, end_date = today.
    Sleeps between days to avoid rate-limiting and Render starvation.

    Run as background task. Long-running.
    """
    if start_date is None:
        earliest = await db.intelligence_items.find(
            {}, {"published_at": 1}
        ).sort("published_at", 1).limit(1).to_list(length=1)
        if not earliest:
            return {"status": "no articles in DB"}
        start_date = earliest[0]["published_at"][:10]

    if end_date is None:
        end_date = datetime.now(timezone.utc).date().isoformat()

    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()

    logger.info(f"Backfill: {start} → {end}")

    days_processed = 0
    total_alerts = 0
    cur = start
    while cur <= end:
        try:
            result = await run_daily_faultline_pass(db, target_date=cur.isoformat())
            days_processed += 1
            total_alerts += result.get("alerts_emitted", 0)
            logger.info(f"Backfill {cur}: {result}")
        except Exception as e:
            logger.exception(f"Backfill failed for {cur}: {e}")
        cur = cur + timedelta(days=1)
        await asyncio.sleep(inter_day_sleep_seconds)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "days_processed": days_processed,
        "total_alerts_emitted": total_alerts,
    }
