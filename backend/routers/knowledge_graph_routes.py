"""Knowledge Graph endpoints."""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Depends
from utils.roles import require_analyst_or_admin
from typing import Optional
import re
from shared import db, logger

router = APIRouter()

# ── Govt/security actor filter ────────────────────────────────────────────────
# Build known insurgent whitelist from MILITANT_ALIASES (imported lazily to avoid circular)
_SECURITY_FORCE_CANONICAL = {"BSF", "CRPF", "Assam Rifles", "Indian Army", "NIA"}

def _get_insurgent_canonical() -> set:
    """Canonical insurgent/militant group names derived from MILITANT_ALIASES."""
    try:
        from knowledge_graph import MILITANT_ALIASES
        return {v for v in MILITANT_ALIASES.values()} - _SECURITY_FORCE_CANONICAL
    except Exception:
        return set()

# Keyword blocklist — any of these substrings in lowercase actor name → govt
_GOVT_KEYWORDS = {
    "police", "army", "military", "paramilitary",
    "security force", "security forces", "armed force", "armed forces",
    "joint force", "joint forces",
    "battalion", "regiment", "crpf", "bsf", "cisf", "ssb", "rpf", "irb",
    "nia", "cbi", "raw", "nsg", "commandos", "constabulary",
    "border security", "central reserve", "rapid action", "india reserve",
    "jawans", "troopers", "unified command", "intelligence bureau",
    "indian navy", "indian air force", "coast guard", "marcos", "garud",
    "stf", "sog ", "sit ", "hg ", "vdf", "defence force", "defence forces",
    "home guard", "state force", "state forces", "quick reaction",
}

# Whole-word matching: "nia" must not match "India", "raw" must not match "draw".
_GOVT_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(k.strip()) for k in sorted(_GOVT_KEYWORDS)) + r")\b"
)


def _is_govt_actor(name: str) -> bool:
    if name in _SECURITY_FORCE_CANONICAL:
        return True
    return bool(_GOVT_RE.search(name.lower()))


async def _scope(extra: Optional[dict] = None) -> dict:
    """Limit a query to the active graph build so a rebuild never shows mixed rows."""
    from knowledge_graph import get_active_build_filter
    scope = await get_active_build_filter(db)
    if not extra:
        return dict(scope)
    return {**extra, **scope}


@router.post("/knowledge-graph/build", dependencies=[Depends(require_analyst_or_admin)])
async def build_kg(background_tasks: BackgroundTasks):
    from knowledge_graph import build_knowledge_graph

    async def _build():
        result = await build_knowledge_graph(db)
        logger.info(f"KG build complete: {result}")

    background_tasks.add_task(_build)
    return {"message": "Knowledge graph build started"}


@router.get("/knowledge-graph/stats")
async def kg_stats():
    scope = await _scope()
    actor_count = await db.kg_actors.count_documents(scope)
    location_count = await db.kg_locations.count_documents(scope)
    edge_count = await db.kg_edges.count_documents(scope)

    if actor_count == 0:
        return {"built": False, "actors": 0, "locations": 0, "edges": 0}

    top_actors = await db.kg_actors.find(
        scope, {"_id": 0, "name": 1, "activity_count": 1, "article_count": 1, "is_cross_border": 1}
    ).sort("activity_count", -1).limit(10).to_list(10)

    top_locations = await db.kg_locations.find(
        scope, {"_id": 0, "name": 1, "activity_count": 1, "is_border": 1}
    ).sort("activity_count", -1).limit(10).to_list(10)

    cross_border = await db.kg_actors.count_documents({**scope, "is_cross_border": True})
    border_locs = await db.kg_locations.count_documents({**scope, "is_border": True})

    sample = await db.kg_actors.find_one(scope, {"_id": 0, "built_at": 1})
    built_at = sample.get("built_at", "") if sample else ""
    build_doc = await db.app_settings.find_one({"key": "kg_active_build"}, {"_id": 0})
    built_at = (build_doc or {}).get("built_at") or built_at

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
    query = await _scope()
    if cross_border is not None:
        query["is_cross_border"] = cross_border

    sort_field = sort_by if sort_by in ("activity_count", "article_count", "name") else "activity_count"
    sort_dir = 1 if sort_field == "name" else -1

    items = await db.kg_actors.find(query, {"_id": 0}).sort(sort_field, sort_dir).limit(limit).to_list(limit)
    return {"actors": items, "count": len(items)}


@router.get("/knowledge-graph/insurgent-actors")
async def kg_insurgent_actors(
    min_articles: int = Query(3, ge=2, le=100,
                              description="Minimum article count to qualify"),
):
    """
    Non-government actors with >= min_articles mentions.
    Excludes Indian security forces, police, military via keyword filter.
    Returns name + article_count + article_ids for NERMap actor-filter dropdown.
    """
    docs = await db.kg_actors.find(
        await _scope({"article_count": {"$gte": min_articles}}),
        {"_id": 0, "name": 1, "article_count": 1, "article_ids": 1}
    ).sort("article_count", -1).to_list(300)

    insurgent_canonical = _get_insurgent_canonical()

    def _include(name: str) -> bool:
        # Govt/security keywords → always exclude, regardless of whitelist
        if _is_govt_actor(name):
            return False
        # Whitelist available: only include known insurgent canonical names
        if insurgent_canonical:
            return name in insurgent_canonical
        # Whitelist failed to load: keyword-only filtering (fallback)
        return True

    actors = [d for d in docs if _include(d.get("name", ""))]
    return {"actors": actors, "count": len(actors)}


@router.get("/knowledge-graph/actors/{actor_name}")
async def kg_actor_detail(actor_name: str):
    import re as _re
    escaped = _re.escape(actor_name)
    actor = await db.kg_actors.find_one(
        await _scope({"name": {"$regex": f"^{escaped}$", "$options": "i"}}),
        {"_id": 0}
    )
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    edges = await db.kg_edges.find(
        await _scope({"actor": actor["name"]}), {"_id": 0}
    ).sort("count", -1).to_list(100)

    return {"actor": actor, "edges": edges}


@router.get("/knowledge-graph/locations")
async def kg_locations(
    is_border: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
):
    query = await _scope()
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
    query = await _scope({"count": {"$gte": min_count}})
    if actor:
        query["actor"] = {"$regex": re.escape(actor), "$options": "i"}
    if location:
        query["location"] = {"$regex": re.escape(location), "$options": "i"}

    items = await db.kg_edges.find(query, {"_id": 0}).sort("count", -1).limit(limit).to_list(limit)
    return {"edges": items, "count": len(items)}


@router.get("/knowledge-graph/network")
async def kg_network(limit: int = Query(50, ge=10, le=200)):
    scope = await _scope()
    top_actors = await db.kg_actors.find(
        scope, {"_id": 0, "name": 1, "activity_count": 1, "is_cross_border": 1,
             "threat_types": 1, "severity_counts": 1, "article_count": 1}
    ).sort("activity_count", -1).limit(limit).to_list(limit)

    actor_names = {a["name"] for a in top_actors}

    loc_query = dict(scope)
    if actor_names:
        loc_conditions = [{"actors." + name: {"$exists": True}} for name in actor_names]
        if loc_conditions:
            loc_query = {**scope, "$or": loc_conditions}

    top_locations = await db.kg_locations.find(
        loc_query,
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
        {**scope, "actor": {"$in": list(actor_names)}, "location": {"$in": list(location_names)}},
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


@router.get("/patterns/status")
async def patterns_status():
    """When pattern detection last finished successfully (even if it found nothing)."""
    doc = await db.app_settings.find_one({"key": "patterns_last_run"}, {"_id": 0})
    return {
        "last_run_at": (doc or {}).get("ran_at"),
        "pattern_count": (doc or {}).get("pattern_count"),
        "capped": (doc or {}).get("capped", False),
    }
