"""
Multi-Article Fusion Engine
Detects duplicate/similar articles across sources, clusters them,
picks the best summary, and cites all covering sources.
"""
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# Title Normalization & Similarity
# ============================================================

def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


KNOWN_ORGS = {'ulfa', 'nscn', 'rpf', 'pla', 'hnlc', 'gnla', 'kla', 'mnf', 'unlf', 'prepak',
              'knf', 'arsa', 'tnla', 'mndaa', 'assam rifles', 'bsf', 'crpf', 'army', 'bgb',
              'tatmadaw', 'ispr', 'nia', 'bro', 'nhidcl'}
KNOWN_PLACES = {'manipur', 'assam', 'meghalaya', 'mizoram', 'tripura', 'arunachal', 'nagaland',
                'sikkim', 'tinsukia', 'changlang', 'tamenglong', 'imphal', 'dimapur', 'guwahati',
                'silchar', 'agartala', 'shillong', 'aizawl', 'itanagar', 'kohima', 'myanmar',
                'bangladesh', 'dhaka', 'chittagong', 'cox', 'moreh', 'champhai', 'sivasagar'}
KNOWN_EVENTS = {'gunfire', 'gunfight', 'bomb', 'blast', 'attack', 'ambush', 'shootout', 'firing',
                'seized', 'arrested', 'killed', 'injured', 'protest', 'blockade', 'collapse',
                'election', 'turnout', 'heroin', 'drugs', 'arms', 'grenade', 'rocket', 'militant'}


def extract_key_entities(title: str) -> set:
    t = (title or "").lower()
    entities = set()
    for org in KNOWN_ORGS:
        if org in t:
            entities.add(org)
    for place in KNOWN_PLACES:
        if place in t:
            entities.add(place)
    for event in KNOWN_EVENTS:
        if event in t:
            entities.add(event)
    numbers = re.findall(r'\b(\d+)\s*(?:killed|injured|arrested|seized|dead)\b', t)
    for n in numbers:
        entities.add(f"count_{n}")
    return entities


def title_similarity(title_a: str, title_b: str) -> float:
    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)
    if not norm_a or not norm_b:
        return 0.0
    words_a = set(norm_a.split())
    words_b = set(norm_b.split())
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    total = max(len(words_a), len(words_b))
    return overlap / total if total > 0 else 0.0


def entity_similarity(title_a: str, title_b: str) -> int:
    ents_a = extract_key_entities(title_a)
    ents_b = extract_key_entities(title_b)
    return len(ents_a & ents_b)


def are_similar(item_a: dict, item_b: dict, title_threshold: float = 0.50) -> bool:
    title_a = item_a.get("title", "")
    title_b = item_b.get("title", "")

    # Title word overlap
    t_sim = title_similarity(title_a, title_b)
    if t_sim >= title_threshold:
        return True

    # Entity overlap — strong entity match even with different wording
    ent_overlap = entity_similarity(title_a, title_b)
    if ent_overlap >= 3 and t_sim >= 0.30:
        return True

    return False


def embedding_similarity(emb_a, emb_b) -> float:
    if not emb_a or not emb_b:
        return 0.0
    try:
        import numpy as np
        a = np.array(emb_a)
        b = np.array(emb_b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
    except Exception:
        return 0.0


# ============================================================
# Cluster Selection — Best Primary
# ============================================================

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def pick_primary(items: list) -> dict:
    """Pick the best article as cluster primary: longest summary, then highest priority."""
    if not items:
        return {}
    return max(items, key=lambda x: (
        len(x.get("ai_summary", "") or ""),
        x.get("priority_score", 0),
        SEVERITY_RANK.get(x.get("severity", "low"), 0),
    ))


def build_cluster_sources(items: list) -> list:
    """Build the citations list from cluster items."""
    sources = []
    seen_urls = set()
    for item in items:
        url = item.get("source_url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        sources.append({
            "source": item.get("source", "Unknown"),
            "source_url": url,
            "title": item.get("title", ""),
            "published_at": item.get("published_at", ""),
        })
    return sources


# ============================================================
# Real-time Fusion — Called after AI classification
# ============================================================

async def find_and_merge_cluster(db, new_item: dict) -> dict:
    """
    After a new item is classified, check if it matches existing items.
    If so, merge into the existing cluster. Returns the (possibly updated) item.
    """
    intelligence_col = db.intelligence_items
    new_title = new_item.get("title", "")
    if not new_title or len(new_title) < 10:
        return new_item

    # Search recent items with similar characteristics
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    state = new_item.get("state", "")

    candidates_query = {
        "processed": True,
        "published_at": {"$gte": cutoff},
        "id": {"$ne": new_item.get("id", "")},
    }
    # Narrow search by state if available
    if state:
        candidates_query["state"] = state

    candidates = await intelligence_col.find(
        candidates_query,
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "source": 1,
         "source_url": 1, "published_at": 1, "priority_score": 1, "severity": 1,
         "cluster_id": 1, "is_cluster_primary": 1, "cluster_sources": 1, "cluster_size": 1,
         "embedding": 1}
    ).sort("published_at", -1).limit(200).to_list(200)

    best_match = None
    best_sim = 0.0

    for cand in candidates:
        if are_similar(new_item, cand):
            sim = title_similarity(new_item.get("title", ""), cand.get("title", ""))
            if sim > best_sim:
                best_sim = sim
                best_match = cand

    # Also check embedding similarity for items without strong title match
    if not best_match and new_item.get("embedding"):
        for cand in candidates:
            if cand.get("embedding"):
                emb_sim = embedding_similarity(new_item.get("embedding"), cand.get("embedding"))
                if emb_sim >= 0.88 and emb_sim > best_sim:
                    best_sim = emb_sim
                    best_match = cand

    if not best_match:
        return new_item

    # Found a match — merge into cluster
    existing_cluster_id = best_match.get("cluster_id")

    if existing_cluster_id:
        # Add to existing cluster
        cluster_id = existing_cluster_id
        # Get current primary
        primary = await intelligence_col.find_one(
            {"cluster_id": cluster_id, "is_cluster_primary": True},
            {"_id": 0, "id": 1, "ai_summary": 1, "priority_score": 1, "severity": 1,
             "cluster_sources": 1, "cluster_size": 1}
        )
        if not primary:
            primary = best_match

        current_sources = primary.get("cluster_sources", [])
        new_source_entry = {
            "source": new_item.get("source", "Unknown"),
            "source_url": new_item.get("source_url", ""),
            "title": new_item.get("title", ""),
            "published_at": new_item.get("published_at", ""),
        }

        # Check if this source URL is already in the cluster
        existing_urls = {s.get("source_url") for s in current_sources if s.get("source_url")}
        if new_item.get("source_url") not in existing_urls:
            current_sources.append(new_source_entry)

        new_size = len(current_sources)

        # Decide if new item should be primary (longer summary)
        new_summary_len = len(new_item.get("ai_summary", "") or "")
        primary_summary_len = len(primary.get("ai_summary", "") or "")

        if new_summary_len > primary_summary_len:
            # New item becomes primary
            await intelligence_col.update_one(
                {"id": primary.get("id")},
                {"$set": {"is_cluster_primary": False}}
            )
            new_item["cluster_id"] = cluster_id
            new_item["is_cluster_primary"] = True
            new_item["cluster_sources"] = current_sources
            new_item["cluster_size"] = new_size
        else:
            # Existing primary stays, mark new item as non-primary
            new_item["cluster_id"] = cluster_id
            new_item["is_cluster_primary"] = False
            # Update primary with new source
            await intelligence_col.update_one(
                {"id": primary.get("id")},
                {"$set": {
                    "cluster_sources": current_sources,
                    "cluster_size": new_size,
                }}
            )

    else:
        # Create new cluster from these two items
        cluster_id = str(uuid.uuid4())

        all_items_for_cluster = [best_match, new_item]
        primary_item = pick_primary(all_items_for_cluster)
        sources = build_cluster_sources(all_items_for_cluster)

        is_new_primary = primary_item.get("title") == new_item.get("title")

        # Update existing match
        await intelligence_col.update_one(
            {"id": best_match["id"]},
            {"$set": {
                "cluster_id": cluster_id,
                "is_cluster_primary": not is_new_primary,
                "cluster_sources": sources if not is_new_primary else [],
                "cluster_size": len(sources) if not is_new_primary else 0,
            }}
        )

        # Set fields on new item
        new_item["cluster_id"] = cluster_id
        new_item["is_cluster_primary"] = is_new_primary
        if is_new_primary:
            new_item["cluster_sources"] = sources
            new_item["cluster_size"] = len(sources)

    logger.info(f"Fusion: merged '{new_item.get('title', '')[:50]}' into cluster {cluster_id[:8]}... (sim={best_sim:.2f})")
    return new_item


# ============================================================
# Batch Fusion — Scheduled job
# ============================================================

async def run_batch_fusion(db, days: int = 7, max_items: int = 500) -> dict:
    """
    Batch process: find unclustered items and group similar ones.
    Returns stats about clusters formed.
    """
    intelligence_col = db.intelligence_items
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Get unclustered items
    unclustered = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff},
            "$or": [
                {"cluster_id": {"$exists": False}},
                {"cluster_id": None},
            ]
        },
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "source": 1,
         "source_url": 1, "published_at": 1, "priority_score": 1, "severity": 1,
         "state": 1, "embedding": 1}
    ).sort("published_at", -1).limit(max_items).to_list(max_items)

    if not unclustered:
        logger.info("Batch fusion: no unclustered items found")
        return {"clusters_formed": 0, "items_clustered": 0}

    logger.info(f"Batch fusion: processing {len(unclustered)} unclustered items")

    # Group by state for efficiency
    by_state = {}
    for item in unclustered:
        state = item.get("state", "_none")
        by_state.setdefault(state, []).append(item)

    clusters_formed = 0
    items_clustered = 0

    for state, items in by_state.items():
        used = set()
        for i in range(len(items)):
            if i in used:
                continue
            group = [items[i]]
            for j in range(i + 1, len(items)):
                if j in used:
                    continue
                if are_similar(items[i], items[j]):
                    group.append(items[j])
                    used.add(j)
                elif items[i].get("embedding") and items[j].get("embedding"):
                    emb_sim = embedding_similarity(items[i]["embedding"], items[j]["embedding"])
                    if emb_sim >= 0.88:
                        group.append(items[j])
                        used.add(j)

            if len(group) > 1:
                used.add(i)
                cluster_id = str(uuid.uuid4())
                primary = pick_primary(group)
                sources = build_cluster_sources(group)

                for item in group:
                    is_primary = item["id"] == primary["id"]
                    update_fields = {
                        "cluster_id": cluster_id,
                        "is_cluster_primary": is_primary,
                    }
                    if is_primary:
                        update_fields["cluster_sources"] = sources
                        update_fields["cluster_size"] = len(sources)

                    await intelligence_col.update_one(
                        {"id": item["id"]},
                        {"$set": update_fields}
                    )

                clusters_formed += 1
                items_clustered += len(group)
                logger.info(f"Batch fusion: cluster {cluster_id[:8]}... ({len(group)} items) primary='{primary.get('title','')[:50]}'")

    # Also check existing clustered items — find new unclustered items that match them
    already_clustered = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff},
            "cluster_id": {"$exists": True, "$ne": None},
            "is_cluster_primary": True,
        },
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "source": 1,
         "source_url": 1, "cluster_id": 1, "cluster_sources": 1, "cluster_size": 1,
         "embedding": 1}
    ).limit(200).to_list(200)

    still_unclustered = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff},
            "$or": [
                {"cluster_id": {"$exists": False}},
                {"cluster_id": None},
            ]
        },
        {"_id": 0, "id": 1, "title": 1, "source": 1, "source_url": 1,
         "published_at": 1, "embedding": 1}
    ).limit(300).to_list(300)

    for orphan in still_unclustered:
        for primary in already_clustered:
            if are_similar(orphan, primary):
                current_sources = primary.get("cluster_sources", [])
                new_entry = {
                    "source": orphan.get("source", ""),
                    "source_url": orphan.get("source_url", ""),
                    "title": orphan.get("title", ""),
                    "published_at": orphan.get("published_at", ""),
                }
                existing_urls = {s.get("source_url") for s in current_sources if s.get("source_url")}
                if orphan.get("source_url") not in existing_urls:
                    current_sources.append(new_entry)

                await intelligence_col.update_one(
                    {"id": orphan["id"]},
                    {"$set": {"cluster_id": primary["cluster_id"], "is_cluster_primary": False}}
                )
                await intelligence_col.update_one(
                    {"id": primary["id"]},
                    {"$set": {"cluster_sources": current_sources, "cluster_size": len(current_sources)}}
                )
                items_clustered += 1
                break

    stats = {"clusters_formed": clusters_formed, "items_clustered": items_clustered}
    logger.info(f"Batch fusion complete: {stats}")
    return stats
