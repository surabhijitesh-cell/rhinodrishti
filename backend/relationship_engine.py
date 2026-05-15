"""
relationship_engine.py — Nightly batch job computing item-to-item relationships.

Five relationship types, using ALL existing data sources:

  1. same_incident  — items sharing cluster_id (fusion engine, strength=1.0)
  2. same_actor     — items sharing normalized actor/org in kg_actors.article_ids
                      (KG already computed + normalized: ULFA(I), NSCN(IM) etc.)
  3. same_hotspot   — items sharing an actor+location pair in kg_edges.article_ids
  4. same_pattern   — items matching same intelligence_patterns escalation pattern
                      (strength proportional to escalation_risk: CRITICAL=0.95,
                       HIGH=0.85, MODERATE=0.65, LOW=0.40)
  5. semantic       — cosine similarity on embedding vectors >= 0.72 threshold

Data sources consumed:
  - intelligence_items  (cluster_id, published_at, state, threat_category,
                         actors, tags, is_cross_border, countries_involved, embedding)
  - kg_actors           (article_ids per normalized actor, severity_counts)
  - kg_edges            (article_ids per actor+location pair, count)
  - intelligence_patterns (pattern_key, escalation_risk for re-querying items)

Edge key: canonical pair (min_id, max_id) — no duplicate reversed edges.
Upsert strategy: $set strength/updated_at; $setOnInsert user_ fields so user
edits (user_confirmed, user_deleted) survive nightly re-runs.

AI explanations: lazy — NOT computed here. Computed on first /explain request
and cached in the edge document.

Item ID note: items stored with "id" field (UUID), not "item_id".
              KG article_ids arrays also contain "id" values.

Performance:
  N ≤ 2000 items → full O(N²) cosine scan via numpy chunk-by-chunk (<10s on Render)
  N > 2000       → cap at 2000 most-recent items with embeddings for semantic pass
  KG passes: O(K × M²) where K=actors, M=articles_per_actor — typically <1s
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np

from shared import db

intelligence_col = db.intelligence_items
relationships_col = db.item_relationships
kg_actors_col    = db.kg_actors
kg_edges_col     = db.kg_edges
patterns_col     = db.intelligence_patterns

logger = logging.getLogger(__name__)

SEMANTIC_THRESHOLD = 0.72   # cosine similarity floor for semantic edges
MAX_ITEMS_SEMANTIC = 2000   # cap to avoid O(N²) blow-up
BATCH_SIZE        = 500     # edges per bulk_write call

# Escalation risk → edge strength mapping
ESCALATION_STRENGTH = {
    "CRITICAL": 0.95,
    "HIGH":     0.85,
    "MODERATE": 0.65,
    "LOW":      0.40,
}


# ── Canonical edge key ────────────────────────────────────────────────────────

def _pair_key(a: str, b: str) -> tuple[str, str]:
    """Return (smaller_id, larger_id) to prevent duplicate reversed edges."""
    return (a, b) if a < b else (b, a)


# ── Bulk upsert ───────────────────────────────────────────────────────────────

async def _bulk_upsert(edges: list[dict]) -> int:
    """Upsert a batch of edge dicts. Returns count of newly inserted edges."""
    if not edges:
        return 0
    from pymongo import UpdateOne
    now = datetime.now(timezone.utc).isoformat()
    ops = []
    seen: set[tuple] = set()
    for e in edges:
        key = _pair_key(e["from_id"], e["to_id"])
        dedup_key = key + (e["type"],)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        f, t = key
        ops.append(UpdateOne(
            {"from_id": f, "to_id": t, "type": e["type"]},
            {
                "$set": {
                    "strength":   round(float(e["strength"]), 4),
                    "updated_at": now,
                    **e.get("meta", {}),
                },
                "$setOnInsert": {
                    "from_id": f, "to_id": t, "type": e["type"],
                    "user_confirmed": False, "user_deleted": False,
                    "ai_explanation": None, "created_at": now,
                },
            },
            upsert=True,
        ))
    if not ops:
        return 0
    result = await relationships_col.bulk_write(ops, ordered=False)
    return result.upserted_count


async def _flush(edges: list[dict], new_total: list[int]) -> list[dict]:
    """Flush edge buffer when full. Returns empty list."""
    if len(edges) >= BATCH_SIZE:
        new_total[0] += await _bulk_upsert(edges)
        return []
    return edges


# ── Pass 1: same_incident (cluster_id) ───────────────────────────────────────

async def _compute_same_incident() -> int:
    """
    Fusion engine already groups progressive reports via cluster_id.
    Create strength=1.0 edges for every pair in each cluster.
    """
    pipeline = [
        {"$match": {
            "processed": True,
            "tags": {"$nin": ["not_relevant"]},
            "cluster_id": {"$exists": True, "$ne": None},
        }},
        {"$group": {
            "_id": "$cluster_id",
            "ids": {"$push": "$id"},
        }},
        {"$match": {"ids.1": {"$exists": True}}},  # ≥2 items
    ]
    clusters = await intelligence_col.aggregate(pipeline).to_list(length=10_000)
    edges: list[dict] = []
    new = [0]
    for cluster in clusters:
        ids = [i for i in cluster["ids"] if i]  # drop None/empty
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                edges.append({"from_id": ids[i], "to_id": ids[j],
                               "type": "same_incident", "strength": 1.0})
                edges = await _flush(edges, new)
    new[0] += await _bulk_upsert(edges)
    logger.info(f"  Pass 1 same_incident: {new[0]} new edges")
    return new[0]


# ── Pass 2: same_actor (from Knowledge Graph) ─────────────────────────────────

async def _compute_same_actor() -> int:
    """
    Use kg_actors collection (already built by knowledge_graph.py).
    For each actor, take its article_ids and create edges for every pair.
    Strength weighted by actor's severity profile (more critical/high = stronger).
    Cap per-actor at 50 articles to avoid explosion on high-activity actors.
    """
    actors = await kg_actors_col.find(
        {"article_ids.1": {"$exists": True}},  # ≥2 articles
        {"article_ids": 1, "severity_counts": 1, "name": 1, "_id": 0}
    ).to_list(length=5000)

    edges: list[dict] = []
    new = [0]

    for actor in actors:
        ids = [i for i in (actor.get("article_ids") or []) if i][:50]
        if len(ids) < 2:
            continue

        # Strength: higher if actor has critical/high incidents
        sev = actor.get("severity_counts", {})
        critical_w = sev.get("critical", 0) * 3
        high_w     = sev.get("high", 0)     * 2
        medium_w   = sev.get("medium", 0)
        total_w    = critical_w + high_w + medium_w + sev.get("low", 0) + 1
        strength   = min(0.95, 0.40 + (critical_w + high_w) / total_w * 0.55)

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                edges.append({"from_id": ids[i], "to_id": ids[j],
                               "type": "same_actor", "strength": strength})
                edges = await _flush(edges, new)

    new[0] += await _bulk_upsert(edges)
    logger.info(f"  Pass 2 same_actor (KG): {new[0]} new edges")
    return new[0]


# ── Pass 3: same_hotspot (from Knowledge Graph edges) ─────────────────────────

async def _compute_same_hotspot() -> int:
    """
    Use kg_edges (actor + location pairs) from knowledge_graph.py.
    Items sharing the same actor+location pair = same operational hotspot.
    Strength proportional to recurrence: min(1.0, count / 8).
    """
    kg_edges = await kg_edges_col.find(
        {"article_ids.1": {"$exists": True}},   # ≥2 articles
        {"article_ids": 1, "count": 1, "actor": 1, "location": 1, "_id": 0}
    ).to_list(length=10_000)

    edges: list[dict] = []
    new = [0]

    for ke in kg_edges:
        ids = [i for i in (ke.get("article_ids") or []) if i][:30]
        if len(ids) < 2:
            continue
        strength = min(0.90, (ke.get("count", 1)) / 8)
        strength = max(0.30, strength)

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                edges.append({"from_id": ids[i], "to_id": ids[j],
                               "type": "same_hotspot", "strength": strength})
                edges = await _flush(edges, new)

    new[0] += await _bulk_upsert(edges)
    logger.info(f"  Pass 3 same_hotspot (KG edges): {new[0]} new edges")
    return new[0]


# ── Pass 4: same_pattern (from Pattern Engine) ────────────────────────────────

async def _compute_same_pattern() -> int:
    """
    Use intelligence_patterns collection (computed by pattern_engine.py).
    For each HIGH/CRITICAL/MODERATE pattern, re-query items matching the
    pattern_key criteria and create edges.

    pattern_key formats:
      region_threat:STATE:THREAT_CATEGORY
      region_actor:STATE:ACTOR_NAME
      region_tag:STATE:TAG
      crossborder:COUNTRY
    """
    patterns = await patterns_col.find(
        {"escalation_risk": {"$in": ["CRITICAL", "HIGH", "MODERATE"]}},
        {"pattern_key": 1, "escalation_risk": 1, "_id": 0}
    ).to_list(length=1000)

    edges: list[dict] = []
    new = [0]

    for pattern in patterns:
        key: str = pattern.get("pattern_key", "")
        risk: str = pattern.get("escalation_risk", "MODERATE")
        strength = ESCALATION_STRENGTH.get(risk, 0.65)

        if not key:
            continue

        parts = key.split(":")
        ptype = parts[0]
        query: dict = {
            "processed": True,
            "tags": {"$nin": ["not_relevant"]},
        }

        if ptype == "region_threat" and len(parts) >= 3:
            query["state"] = parts[1]
            query["threat_category"] = parts[2]
        elif ptype == "region_actor" and len(parts) >= 3:
            query["state"] = parts[1]
            query["actors"] = parts[2]
        elif ptype == "region_tag" and len(parts) >= 3:
            query["state"] = parts[1]
            query["tags"] = parts[2]
        elif ptype == "crossborder" and len(parts) >= 2:
            query["is_cross_border"] = True
            query["countries_involved"] = parts[1]
        else:
            continue

        # Fetch items matching this pattern (cap at 40 per pattern)
        docs = await intelligence_col.find(
            query, {"id": 1, "_id": 0}
        ).sort("published_at", -1).limit(40).to_list(40)

        ids = [d["id"] for d in docs if d.get("id")]
        if len(ids) < 2:
            continue

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                edges.append({"from_id": ids[i], "to_id": ids[j],
                               "type": "same_pattern", "strength": strength,
                               "meta": {"pattern_key": key, "escalation_risk": risk}})
                edges = await _flush(edges, new)

    new[0] += await _bulk_upsert(edges)
    logger.info(f"  Pass 4 same_pattern (Pattern Engine): {new[0]} new edges")
    return new[0]


# ── Pass 5: semantic (cosine similarity on embeddings) ───────────────────────

async def _compute_semantic() -> int:
    """
    Load embedding vectors; compute cosine similarity in row-by-row chunks;
    emit edges for pairs above SEMANTIC_THRESHOLD not already covered by
    other passes (semantic fills gaps where entity/cluster data is sparse).
    """
    cursor = intelligence_col.find(
        {
            "processed": True,
            "tags": {"$nin": ["not_relevant"]},
            "embedding.0": {"$exists": True},  # non-empty array
        },
        {"id": 1, "embedding": 1, "_id": 0},
    ).sort("published_at", -1).limit(MAX_ITEMS_SEMANTIC)

    docs = await cursor.to_list(length=MAX_ITEMS_SEMANTIC)
    if len(docs) < 2:
        logger.info("  Pass 5 semantic: not enough items with embeddings, skip.")
        return 0

    ids  = [d["id"]        for d in docs]
    vecs = np.array([d["embedding"] for d in docs], dtype=np.float32)

    # L2-normalize for cosine similarity via dot product
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs_n = vecs / norms

    n = len(ids)
    edges: list[dict] = []
    new = [0]

    for i in range(n):
        sims = vecs_n[i] @ vecs_n[i + 1:].T   # shape: (n-i-1,)
        above = np.where(sims >= SEMANTIC_THRESHOLD)[0]
        for rel_j in above:
            j = i + 1 + int(rel_j)
            edges.append({
                "from_id": ids[i], "to_id": ids[j],
                "type": "semantic", "strength": float(sims[rel_j]),
            })
            edges = await _flush(edges, new)

    new[0] += await _bulk_upsert(edges)
    logger.info(f"  Pass 5 semantic: {new[0]} new edges")
    return new[0]


# ── Index setup ───────────────────────────────────────────────────────────────

async def ensure_indexes() -> None:
    """Create indexes on item_relationships (idempotent)."""
    await relationships_col.create_index(
        [("from_id", 1), ("to_id", 1), ("type", 1)], unique=True
    )
    await relationships_col.create_index([("from_id", 1)])
    await relationships_col.create_index([("to_id", 1)])
    await relationships_col.create_index([("type", 1)])
    await relationships_col.create_index([("user_deleted", 1)])
    await relationships_col.create_index([("created_at", -1)])


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_relationship_batch() -> dict:
    """
    Full nightly batch. Safe to call manually (idempotent).
    Prerequisite: knowledge_graph.py + pattern_engine.py should have been
    run first (they are on separate schedules — KG: on demand / brief,
    patterns: on demand). If their collections are empty, those passes
    silently produce 0 edges without error.
    """
    t0 = time.time()
    logger.info("=== Relationship batch starting ===")
    await ensure_indexes()

    results: dict[str, int] = {}
    for name, fn in [
        ("same_incident", _compute_same_incident),
        ("same_actor",    _compute_same_actor),
        ("same_hotspot",  _compute_same_hotspot),
        ("same_pattern",  _compute_same_pattern),
        ("semantic",      _compute_semantic),
    ]:
        try:
            results[name] = await fn()
        except Exception as e:
            logger.warning(f"  {name} pass failed: {e}")
            results[name] = -1

    elapsed = round(time.time() - t0, 1)
    total_edges = await relationships_col.count_documents({})
    summary = {**results, "total_edges": total_edges, "elapsed_s": elapsed}
    logger.info(f"=== Relationship batch done: {summary} ===")
    return summary


# ── Query helpers (called by API router) ─────────────────────────────────────

async def get_edges_for_items(
    item_ids: list[str],
    types: Optional[list[str]] = None,
    include_deleted: bool = False,
) -> list[dict]:
    """
    Return all non-deleted edges where from_id or to_id is in item_ids.
    Used by NERMap to draw relationship lines for visible markers.
    """
    id_set = list(set(item_ids))
    match: dict = {
        "$or": [{"from_id": {"$in": id_set}}, {"to_id": {"$in": id_set}}],
    }
    if not include_deleted:
        match["user_deleted"] = {"$ne": True}
    if types:
        match["type"] = {"$in": types}

    docs = await relationships_col.find(
        match,
        {"_id": 0, "from_id": 1, "to_id": 1, "type": 1, "strength": 1,
         "ai_explanation": 1, "user_confirmed": 1, "user_deleted": 1,
         "pattern_key": 1, "escalation_risk": 1}
    ).limit(1000).to_list(1000)
    return docs


async def get_edge_stats() -> dict:
    """Summary stats for admin panel."""
    pipeline = [
        {"$group": {
            "_id": "$type",
            "count":        {"$sum": 1},
            "deleted":      {"$sum": {"$cond": ["$user_deleted",   1, 0]}},
            "confirmed":    {"$sum": {"$cond": ["$user_confirmed", 1, 0]}},
            "avg_strength": {"$avg": "$strength"},
        }},
        {"$sort": {"count": -1}},
    ]
    docs = await relationships_col.aggregate(pipeline).to_list(10)
    total = await relationships_col.count_documents({})
    return {
        "total_edges": total,
        "by_type": [
            {
                "type":         d["_id"],
                "count":        d["count"],
                "deleted":      d["deleted"],
                "confirmed":    d["confirmed"],
                "avg_strength": round(d["avg_strength"] or 0, 3),
            }
            for d in docs
        ],
    }


# ── Single-edge upsert (used by relationships router for user-drawn edges) ────

async def upsert_edge(
    from_id: str,
    to_id: str,
    edge_type: str,
    strength: float,
    meta: Optional[dict] = None,
) -> None:
    f, t = _pair_key(from_id, to_id)
    now = datetime.now(timezone.utc).isoformat()
    await relationships_col.update_one(
        {"from_id": f, "to_id": t, "type": edge_type},
        {
            "$set": {"strength": round(float(strength), 4), "updated_at": now, **(meta or {})},
            "$setOnInsert": {
                "from_id": f, "to_id": t, "type": edge_type,
                "user_confirmed": False, "user_deleted": False,
                "ai_explanation": None, "created_at": now,
            },
        },
        upsert=True,
    )
