"""
Embedding Service — Generates vector embeddings for intelligence items
using OpenAI text-embedding-3-small with a dedicated OpenAI API Key.

Supports: single embedding, batch embedding, semantic similarity search.
"""
import os
import logging
import asyncio
import numpy as np
from typing import List, Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for a single text string using OpenAI API."""
    if not text or len(text.strip()) < 5:
        return None
    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY not set for embeddings")
        return None
    
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        
        clean_text = text.replace("\n", " ").strip()[:8000]
        
        response = await client.embeddings.create(
            input=[clean_text],
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
        )

        # Track embedding cost
        try:
            total_tok = getattr(response.usage, "total_tokens", 0) or 0
            from usage_tracker import track_usage_generic
            await track_usage_generic(
                input_tokens=total_tok,
                output_tokens=0,
                model=EMBEDDING_MODEL,
            )
        except Exception:
            pass

        embedding = response.data[0].embedding
        return embedding
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")
        return None


async def generate_batch_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts (sequential to avoid rate limits)."""
    results = []
    for text in texts:
        emb = await generate_embedding(text)
        results.append(emb)
        await asyncio.sleep(0.2)  # Rate limit safety
    return results


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


async def semantic_search(db, query_text: str, limit: int = 10, min_score: float = 0.3) -> list:
    """
    Perform semantic search across intelligence items.
    1. Generate embedding for query
    2. Find items with embeddings
    3. Compute cosine similarity
    4. Return top-k results
    """
    query_embedding = await generate_embedding(query_text)
    if not query_embedding:
        return []
    
    # Get items that have embeddings
    items = await db.intelligence_items.find(
        {"embedding": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "severity": 1,
         "state": 1, "source": 1, "published_at": 1, "priority_score": 1,
         "embedding": 1, "threat_category": 1}
    ).to_list(2000)
    
    if not items:
        return []
    
    # Compute similarities
    results = []
    for item in items:
        item_emb = item.get("embedding")
        if not item_emb:
            continue
        score = cosine_similarity(query_embedding, item_emb)
        if score >= min_score:
            item_copy = {k: v for k, v in item.items() if k != "embedding"}
            item_copy["similarity_score"] = round(score, 4)
            results.append(item_copy)
    
    # Sort by similarity
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:limit]


async def backfill_embeddings(db, batch_size: int = 20) -> int:
    """Backfill embeddings for items that don't have them yet."""
    items = await db.intelligence_items.find(
        {"processed": True, "$or": [{"embedding": {"$exists": False}}, {"embedding": None}]},
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1}
    ).limit(batch_size).to_list(batch_size)
    
    count = 0
    for item in items:
        text = f"{item.get('title', '')}. {item.get('ai_summary', '')}"
        emb = await generate_embedding(text)
        if emb:
            await db.intelligence_items.update_one(
                {"id": item["id"]},
                {"$set": {"embedding": emb}}
            )
            count += 1
            await asyncio.sleep(0.3)
    
    logger.info(f"Backfilled {count}/{len(items)} embeddings")
    return count
