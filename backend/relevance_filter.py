"""
Stage 0.5 — Semantic relevance filter via embeddings.

Concept:
  - Build reference centroid from past critical / high / medium items (DB).
  - For each new item: embed title+snippet, compute cosine similarity to centroid.
  - Threshold: items with sim >= MIN_SIM proceed to Stage 1 (Gemini).
  - Items below threshold are dropped (still subject to fail-open on any error).

Reasoning:
  Captures semantic relevance that keyword Stage 0 misses (paraphrases,
  unfamiliar phrasings, non-English-translated text). Costs ~$0.000004/item
  via OpenAI text-embedding-3-small — effectively free at our volume.

Fail-open: if embedding fails, no reference set, or numpy unavailable,
the filter returns relevant=True so the item proceeds downstream.
"""
import logging
import os
import time
from typing import Optional

import numpy as np

from embedding_service import generate_embedding, cosine_similarity

logger = logging.getLogger(__name__)

# Tuning knobs — can be overridden by env var OR at runtime via set_min_sim_threshold()
# 0.35 chosen as conservative safe floor: items scoring below 0.35 vs a
# security-content centroid are almost never genuine NER security news.
MIN_SIM_THRESHOLD = float(os.environ.get("STAGE05_MIN_SIM", "0.35"))
REF_REFRESH_SECONDS = 6 * 3600  # rebuild centroid every 6h
REF_MIN_ITEMS = 20              # need at least this many ref items to enable filter
REF_MAX_ITEMS = 200              # cap reference set size

# In-memory cache
_centroid: Optional[np.ndarray] = None
_centroid_built_at: float = 0.0
_ref_count: int = 0


async def _build_centroid(db) -> Optional[np.ndarray]:
    """Compute centroid vector from past relevant items with embeddings."""
    try:
        items = await db.intelligence_items.find(
            {
                "processed": True,
                "embedding": {"$exists": True, "$ne": None},
                "severity": {"$in": ["critical", "high", "medium"]},
            },
            {"_id": 0, "embedding": 1}
        ).sort("published_at", -1).limit(REF_MAX_ITEMS).to_list(REF_MAX_ITEMS)

        if len(items) < REF_MIN_ITEMS:
            logger.info(f"Stage 0.5: only {len(items)} reference items "
                        f"(need {REF_MIN_ITEMS}) — filter disabled, fail-open")
            return None

        vectors = [item["embedding"] for item in items if item.get("embedding")]
        if not vectors:
            return None

        arr = np.array(vectors, dtype=np.float32)
        centroid = arr.mean(axis=0)
        # Normalize so cosine sim stays well-conditioned
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        global _ref_count
        _ref_count = len(vectors)
        logger.info(f"Stage 0.5: built centroid from {_ref_count} reference items")
        return centroid

    except Exception as e:
        logger.warning(f"Stage 0.5 centroid build failed: {e}")
        return None


async def _ensure_centroid(db) -> Optional[np.ndarray]:
    """Lazy-init + periodic refresh of centroid."""
    global _centroid, _centroid_built_at
    now = time.time()
    if _centroid is None or (now - _centroid_built_at) > REF_REFRESH_SECONDS:
        _centroid = await _build_centroid(db)
        _centroid_built_at = now
    return _centroid


async def is_semantically_relevant(article: dict, db) -> dict:
    """
    Stage 0.5 semantic relevance check.
    Returns:
        {"relevant": bool, "similarity": float, "reason": str}
    Fail-open: returns relevant=True on any failure.
    """
    centroid = await _ensure_centroid(db)
    if centroid is None:
        return {"relevant": True, "similarity": 0.0, "reason": "no_reference_set"}

    title = (article.get("title") or "").strip()
    content = (article.get("raw_content") or article.get("description") or "").strip()
    text = f"{title}. {content[:400]}"
    if len(text.strip()) < 10:
        return {"relevant": True, "similarity": 0.0, "reason": "text_too_short"}

    try:
        emb = await generate_embedding(text)
        if not emb:
            return {"relevant": True, "similarity": 0.0, "reason": "embed_unavailable"}

        sim = cosine_similarity(emb, centroid.tolist())
        relevant = sim >= MIN_SIM_THRESHOLD

        # Cache embedding on the article dict so Stage 2 can persist it later
        article["_stage05_embedding"] = emb

        return {
            "relevant": relevant,
            "similarity": round(sim, 4),
            "reason": f"sim={sim:.3f} thr={MIN_SIM_THRESHOLD}",
        }
    except Exception as e:
        logger.warning(f"Stage 0.5 sim check failed: {e}")
        return {"relevant": True, "similarity": 0.0, "reason": f"error:{type(e).__name__}"}


async def batch_relevance(articles: list[dict], db, concurrency: int = 5) -> list[dict]:
    """Check relevance for many articles concurrently."""
    import asyncio
    # Warm centroid once before fan-out
    await _ensure_centroid(db)

    sem = asyncio.Semaphore(concurrency)

    async def _one(a):
        async with sem:
            return await is_semantically_relevant(a, db)

    return await asyncio.gather(*(_one(a) for a in articles))


def get_filter_stats() -> dict:
    """Diagnostics endpoint helper."""
    return {
        "centroid_built": _centroid is not None,
        "reference_items": _ref_count,
        "min_sim_threshold": MIN_SIM_THRESHOLD,
        "last_built_at": _centroid_built_at,
        "refresh_interval_seconds": REF_REFRESH_SECONDS,
    }


def set_min_sim_threshold(val: float) -> float:
    """
    Runtime override of the similarity threshold.
    Called by the admin filter-settings endpoint when user applies new values.
    Returns the clamped value actually set.
    """
    global MIN_SIM_THRESHOLD
    MIN_SIM_THRESHOLD = max(0.10, min(0.70, float(val)))
    logger.info(f"Stage 0.5 min_sim_threshold set to {MIN_SIM_THRESHOLD}")
    return MIN_SIM_THRESHOLD
