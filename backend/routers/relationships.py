"""
Relationship endpoints for Rhino Drishti.

GET  /api/relationships                — edges for a set of item_ids (NERMap use)
GET  /api/relationships/stats          — edge counts by type (admin panel)
POST /api/relationships                — create user-drawn edge
PATCH /api/relationships/{edge_id}     — confirm or soft-delete an edge
GET  /api/relationships/{edge_id}/explain — lazy AI explanation for an edge
POST /api/admin/relationships/compute  — manual trigger of batch job (admin)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from shared import db
from relationship_engine import (
    get_edges_for_items, get_edge_stats,
    upsert_edge, relationships_col,
)

router = APIRouter()


# ── Request / response models ─────────────────────────────────────────────────

class CreateEdgeBody(BaseModel):
    from_id: str
    to_id: str
    type: str = "user_drawn"   # always "user_drawn" for user-created edges
    note: Optional[str] = None  # optional user note


class PatchEdgeBody(BaseModel):
    user_confirmed: Optional[bool] = None
    user_deleted: Optional[bool] = None


# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get("/relationships")
async def list_relationships(
    item_ids: str = Query(..., description="Comma-separated item_ids"),
    types: Optional[str] = Query(None, description="Comma-separated types to filter"),
    include_deleted: bool = Query(False),
):
    """
    Return edges where from_id or to_id is in item_ids.
    Called by NERMap to draw lines for visible markers.
    Max 100 item_ids per request.
    """
    ids = [x.strip() for x in item_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(400, "item_ids required")
    if len(ids) > 100:
        raise HTTPException(400, "max 100 item_ids per request")

    type_list = None
    if types:
        type_list = [t.strip() for t in types.split(",") if t.strip()]

    edges = await get_edges_for_items(ids, types=type_list, include_deleted=include_deleted)
    return {"edges": edges, "count": len(edges)}


@router.get("/relationships/stats")
async def relationship_stats():
    """Edge counts by type — for admin dashboard."""
    return await get_edge_stats()


@router.get("/relationships/{edge_id}/explain")
async def explain_edge(edge_id: str):
    """
    Lazy AI explanation for a relationship edge.
    If explanation already cached, returns it immediately.
    Otherwise calls Gemini Flash-Lite to explain, caches in DB.
    """
    try:
        oid = ObjectId(edge_id)
    except Exception:
        raise HTTPException(400, "Invalid edge_id")

    edge = await relationships_col.find_one({"_id": oid})
    if not edge:
        raise HTTPException(404, "Edge not found")

    if edge.get("ai_explanation"):
        return {"explanation": edge["ai_explanation"], "cached": True}

    # Fetch both items for context
    from_doc = await db.intelligence_items.find_one(
        {"id": edge["from_id"]},
        {"title": 1, "entities": 1, "threat_category": 1, "severity": 1, "_id": 0}
    )
    to_doc = await db.intelligence_items.find_one(
        {"id": edge["to_id"]},
        {"title": 1, "entities": 1, "threat_category": 1, "severity": 1, "_id": 0}
    )
    if not from_doc or not to_doc:
        raise HTTPException(404, "One or both linked items not found")

    # Build prompt
    rel_type_desc = {
        "same_incident": "they are progressive reports of the same incident (same cluster)",
        "same_actor":    "they share one or more organizations/armed groups",
        "semantic":      "they are semantically similar based on embedding vectors",
        "user_drawn":    "an analyst manually linked them",
    }.get(edge["type"], edge["type"])

    prompt = (
        f"Two intelligence items from Northeast India are linked because {rel_type_desc}.\n\n"
        f"Item A: [{from_doc.get('severity','').upper()}] {from_doc.get('title','')}\n"
        f"  Category: {from_doc.get('threat_category','')}\n"
        f"  Orgs: {', '.join(from_doc.get('entities', {}).get('organizations', []))}\n\n"
        f"Item B: [{to_doc.get('severity','').upper()}] {to_doc.get('title','')}\n"
        f"  Category: {to_doc.get('threat_category','')}\n"
        f"  Orgs: {', '.join(to_doc.get('entities', {}).get('organizations', []))}\n\n"
        f"In 1-2 sentences, explain the strategic significance of this link for NER security analysts. "
        f"Be specific about actors, locations, and threat escalation patterns."
    )

    try:
        from llm_client import get_client, MODEL
        client = get_client()
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
            extra_body={"include_reasoning": False},
        )
        explanation = resp.choices[0].message.content.strip()

        # Track usage
        try:
            from usage_tracker import track_usage_generic
            u = resp.usage
            await track_usage_generic(
                input_tokens=getattr(u, "prompt_tokens", 0) or 0,
                output_tokens=getattr(u, "completion_tokens", 0) or 0,
                model="google/gemini-2.5-flash",
            )
        except Exception:
            pass

        await relationships_col.update_one(
            {"_id": oid},
            {"$set": {"ai_explanation": explanation,
                      "explanation_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"explanation": explanation, "cached": False}

    except Exception as e:
        raise HTTPException(503, f"AI explanation failed: {e}")


# ── Write endpoints ───────────────────────────────────────────────────────────

@router.post("/relationships")
async def create_user_edge(body: CreateEdgeBody):
    """User-drawn relationship between two items."""
    if body.from_id == body.to_id:
        raise HTTPException(400, "from_id and to_id must be different")

    # Verify both items exist
    for iid in [body.from_id, body.to_id]:
        doc = await db.intelligence_items.find_one({"id": iid}, {"_id": 1})
        if not doc:
            raise HTTPException(404, f"Item not found: {iid}")

    await upsert_edge(
        body.from_id, body.to_id,
        edge_type="user_drawn",
        strength=1.0,
        meta={"user_confirmed": True, "user_note": body.note or ""},
    )
    return {"ok": True}


@router.patch("/relationships/{edge_id}")
async def patch_edge(edge_id: str, body: PatchEdgeBody):
    """Confirm or soft-delete an edge."""
    try:
        oid = ObjectId(edge_id)
    except Exception:
        raise HTTPException(400, "Invalid edge_id")

    update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.user_confirmed is not None:
        update["user_confirmed"] = body.user_confirmed
    if body.user_deleted is not None:
        update["user_deleted"] = body.user_deleted

    result = await relationships_col.update_one({"_id": oid}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Edge not found")
    return {"ok": True}


# ── Admin: manual batch trigger ───────────────────────────────────────────────

@router.post("/admin/relationships/compute")
async def trigger_relationship_compute(rebuild_kg: bool = False):
    """
    Admin: manually trigger relationship batch job.
    Runs synchronously — expect 10-60s depending on item count.
    Set rebuild_kg=true to rebuild Knowledge Graph + Pattern Engine first
    (ensures same_actor / same_hotspot / same_pattern passes use fresh data).
    """
    try:
        if rebuild_kg:
            # Rebuild KG and patterns before computing relationships
            from knowledge_graph import build_knowledge_graph
            from pattern_engine import detect_patterns
            from shared import db as _db
            await build_knowledge_graph(_db)
            await detect_patterns(_db)

        from relationship_engine import run_relationship_batch
        summary = await run_relationship_batch()
        return {"ok": True, "summary": summary, "kg_rebuilt": rebuild_kg}
    except Exception as e:
        raise HTTPException(500, f"Batch job failed: {e}")
