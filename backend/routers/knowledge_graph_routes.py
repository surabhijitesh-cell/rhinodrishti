"""Knowledge Graph endpoints."""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from typing import Optional
from shared import db, logger

router = APIRouter()


@router.post("/knowledge-graph/build")
async def build_kg(background_tasks: BackgroundTasks):
    from knowledge_graph import build_knowledge_graph

    async def _build():
        result = await build_knowledge_graph(db)
        logger.info(f"KG build complete: {result}")

    background_tasks.add_task(_build)
    return {"message": "Knowledge graph build started"}


@router.get("/knowledge-graph/stats")
async def kg_stats():
    actor_count = await db.kg_actors.count_documents({})
    location_count = await db.kg_locations.count_documents({})
    edge_count = await db.kg_edges.count_documents({})

    if actor_count == 0:
        return {"built": False, "actors": 0, "locations": 0, "edges": 0}

    top_actors = await db.kg_actors.find(
        {}, {"_id": 0, "name": 1, "activity_count": 1, "article_count": 1, "is_cross_border": 1}
    ).sort("activity_count", -1).limit(10).to_list(10)

    top_locations = await db.kg_locations.find(
        {}, {"_id": 0, "name": 1, "activity_count": 1, "is_border": 1}
    ).sort("activity_count", -1).limit(10).to_list(10)

    cross_border = await db.kg_actors.count_documents({"is_cross_border": True})
    border_locs = await db.kg_locations.count_documents({"is_border": True})

    sample = await db.kg_actors.find_one({}, {"_id": 0, "built_at": 1})
    built_at = sample.get("built_at", "") if sample else ""

    return {
        "built": True,
        "built_at": built_at,
        "actors": actor_count,
        "locations": location_count,
        "edges": edge_count,
        "cross_border_actors": cross_border,
        "border_locations": border_locs,
        "top_actors": top_actors,
        "top_locations": top_locations,
    }


@router.get("/knowledge-graph/actors")
async def kg_actors(
    sort_by: str = Query("activity_count", description="Sort: activity_count, article_count, name"),
    cross_border: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
):
    query = {}
    if cross_border is not None:
        query["is_cross_border"] = cross_border

    sort_field = sort_by if sort_by in ("activity_count", "article_count", "name") else "activity_count"
    sort_dir = 1 if sort_field == "name" else -1

    items = await db.kg_actors.find(query, {"_id": 0}).sort(sort_field, sort_dir).limit(limit).to_list(limit)
    return {"actors": items, "count": len(items)}


@router.get("/knowledge-graph/actors/{actor_name}")
async def kg_actor_detail(actor_name: str):
    import re as _re
    escaped = _re.escape(actor_name)
    actor = await db.kg_actors.find_one(
        {"name": {"$regex": f"^{escaped}$", "$options": "i"}},
        {"_id": 0}
    )
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    edges = await db.kg_edges.find(
        {"actor": actor["name"]}, {"_id": 0}
    ).sort("count", -1).to_list(100)

    return {"actor": actor, "edges": edges}


@router.get("/knowledge-graph/locations")
async def kg_locations(
    is_border: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
):
    query = {}
    if is_border is not None:
        query["is_border"] = is_border

    items = await db.kg_locations.find(query, {"_id": 0}).sort("activity_count", -1).limit(limit).to_list(limit)
    return {"locations": items, "count": len(items)}


@router.get("/knowledge-graph/edges")
async def kg_edges(
    actor: Optional[str] = None,
    location: Optional[str] = None,
    min_count: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
):
    query = {"count": {"$gte": min_count}}
    if actor:
        query["actor"] = {"$regex": actor, "$options": "i"}
    if location:
        query["location"] = {"$regex": location, "$options": "i"}

    items = await db.kg_edges.find(query, {"_id": 0}).sort("count", -1).limit(limit).to_list(limit)
    return {"edges": items, "count": len(items)}


@router.get("/knowledge-graph/network")
async def kg_network(limit: int = Query(50, ge=10, le=200)):
    top_actors = await db.kg_actors.find(
        {}, {"_id": 0, "name": 1, "activity_count": 1, "is_cross_border": 1,
             "threat_types": 1, "severity_counts": 1, "article_count": 1}
    ).sort("activity_count", -1).limit(limit).to_list(limit)

    actor_names = {a["name"] for a in top_actors}

    loc_query = {}
    if actor_names:
        loc_conditions = [{"actors." + name: {"$exists": True}} for name in actor_names]
        if loc_conditions:
            loc_query = {"$or": loc_conditions}

    top_locations = await db.kg_locations.find(
        loc_query if loc_query else {},
        {"_id": 0, "name": 1, "activity_count": 1, "is_border": 1, "states": 1}
    ).sort("activity_count", -1).limit(limit).to_list(limit)

    location_names = {l["name"] for l in top_locations}

    nodes = []
    for a in top_actors:
        threats = a.get("threat_types", {})
        primary_threat = max(threats, key=threats.get) if threats else "Unknown"
        severity = a.get("severity_counts", {})
        max_severity = "low"
        for s in ["critical", "high", "medium", "low"]:
            if severity.get(s, 0) > 0:
                max_severity = s
                break

        nodes.append({
            "id": f"actor:{a['name']}",
            "label": a["name"],
            "type": "actor",
            "size": min(30, 8 + a.get("activity_count", 0)),
            "activity": a.get("activity_count", 0),
            "articles": a.get("article_count", 0),
            "cross_border": a.get("is_cross_border", False),
            "primary_threat": primary_threat,
            "max_severity": max_severity,
        })

    for l in top_locations:
        nodes.append({
            "id": f"location:{l['name']}",
            "label": l["name"],
            "type": "location",
            "size": min(25, 6 + l.get("activity_count", 0)),
            "activity": l.get("activity_count", 0),
            "is_border": l.get("is_border", False),
            "states": l.get("states", []),
        })

    edges = await db.kg_edges.find(
        {"actor": {"$in": list(actor_names)}, "location": {"$in": list(location_names)}},
        {"_id": 0}
    ).sort("count", -1).limit(300).to_list(300)

    links = []
    for e in edges:
        contexts = e.get("contexts", {})
        primary_context = max(contexts, key=contexts.get) if contexts else "Unknown"
        links.append({
            "source": f"actor:{e['actor']}",
            "target": f"location:{e['location']}",
            "weight": e["count"],
            "context": primary_context,
        })

    return {
        "nodes": nodes,
        "links": links,
        "actor_count": len([n for n in nodes if n["type"] == "actor"]),
        "location_count": len([n for n in nodes if n["type"] == "location"]),
    }
