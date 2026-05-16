"""
Knowledge Graph Builder — Aggregates entity relationships across intelligence items
to surface cross-article patterns: actor movement corridors, hotspot locations, 
and organization networks.

Collections:
  - kg_actors: Actor profiles with locations, activity, threat types
  - kg_locations: Location profiles with actors, activity counts
  - kg_edges: Actor-Location edges with frequency, dates, contexts
"""
import logging
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)



# ── Canonical militant group names ───────────────────────────────────────────
# All variants → one canonical name. Lowercase keys for case-insensitive lookup.
MILITANT_ALIASES: dict[str, str] = {
    # ── ULFA (Assam) ──
    "ulfa":                                     "ULFA-I",
    "ulfa-i":                                   "ULFA-I",
    "ulfa(i)":                                  "ULFA-I",
    "ulfa (i)":                                 "ULFA-I",
    "ulfa independent":                         "ULFA-I",
    "united liberation front of asom":          "ULFA-I",
    "united liberation front of assam":         "ULFA-I",
    "ulfa pro-talk":                            "ULFA (Pro-Talk)",
    "ulfa (pro-talk)":                          "ULFA (Pro-Talk)",
    # ── NSCN (Nagaland) ──
    "nscn":                                     "NSCN-IM",   # default to IM (dominant faction)
    "nscn-im":                                  "NSCN-IM",
    "nscn(im)":                                 "NSCN-IM",
    "nscn (im)":                                "NSCN-IM",
    "nscn isak muivah":                         "NSCN-IM",
    "nscn isak-muivah":                         "NSCN-IM",
    "national socialist council of nagaland im":"NSCN-IM",
    "nscn-k":                                   "NSCN-K",
    "nscn(k)":                                  "NSCN-K",
    "nscn (k)":                                 "NSCN-K",
    "nscn khaplang":                            "NSCN-K",
    "national socialist council of nagaland k": "NSCN-K",
    "nscn-kk":                                  "NSCN-KK",
    "nscn-r":                                   "NSCN-R",
    # ── PLA / Manipur groups ──
    "pla":                                      "PLA Manipur",
    "pla manipur":                              "PLA Manipur",
    "people's liberation army":                 "PLA Manipur",
    "people's liberation army manipur":         "PLA Manipur",
    "arambai tenggol":                          "Arambai Tenggol",
    "arambai":                                  "Arambai Tenggol",
    "meitei leepun":                            "Meitei Leepun",
    "prepak":                                   "PREPAK",
    "people's revolutionary party of kangleipak":"PREPAK",
    "unlf":                                     "UNLF",
    "united national liberation front":         "UNLF",
    "kcp":                                      "KCP",
    "kangleipak communist party":               "KCP",
    "pulf":                                     "PULF",
    "people's united liberation front":         "PULF",
    "mnpf":                                     "MNPF",
    "meitei national people's front":           "MNPF",
    "kuki militants":                           "Kuki militants",
    "kuki-zo militants":                        "Kuki militants",
    "kuki armed groups":                        "Kuki militants",
    "kuki":                                     "Kuki militants",
    # ── NDFB (Bodoland / Assam) ──
    "ndfb":                                     "NDFB",
    "ndfb-s":                                   "NDFB-S",
    "ndfb songbijit":                           "NDFB-S",
    "ndfb-rd":                                  "NDFB-RD",
    "ndfb ranjan daimary":                      "NDFB-RD",
    "ndfb-p":                                   "NDFB-P",
    "national democratic front of bodoland":    "NDFB",
    # ── Assam others ──
    "kplt":                                     "KPLT",
    "karbi people's liberation tigers":         "KPLT",
    "klo":                                      "KLO",
    "kamatapur liberation organisation":        "KLO",
    "upds":                                     "UPDS",
    "united people's democratic solidarity":    "UPDS",
    # ── Meghalaya ──
    "hnlc":                                     "HNLC",
    "hynniewtrep national liberation council":  "HNLC",
    "gnla":                                     "GNLA",
    "garo national liberation army":            "GNLA",
    # ── Tripura ──
    "nlft":                                     "NLFT",
    "national liberation front of tripura":     "NLFT",
    "attf":                                     "ATTF",
    "all tripura tiger force":                  "ATTF",
    # ── Mizoram ──
    "zrf":                                      "ZRF",
    "zoram reunification front":                "ZRF",
    # ── Myanmar armed groups ──
    "arakan army":                              "Arakan Army",
    "tatmadaw":                                 "Myanmar Military",
    "myanmar military":                         "Myanmar Military",
    "myanmar army":                             "Myanmar Military",
    "tnla":                                     "TNLA",
    "ta'ang national liberation army":          "TNLA",
    "kia":                                      "KIA",
    "kachin independence army":                 "KIA",
    "pdf myanmar":                              "PDF Myanmar",
    "people's defence force":                   "PDF Myanmar",
    "chin national army":                       "Chin National Army",
    "cna":                                      "Chin National Army",
    "mndaa":                                    "MNDAA",
    "myanmar national democratic alliance army":"MNDAA",
    # ── Bangladesh armed groups ──
    "arsa":                                     "ARSA",
    "arakan rohingya salvation army":           "ARSA",
    "jmb":                                      "JMB",
    "jamaat-ul-mujahideen bangladesh":          "JMB",
    "ansar al-islam":                           "Ansar al-Islam",
    # ── Indian security forces (canonical display names) ──
    "border security force":                    "BSF",
    "central reserve police force":             "CRPF",
    "assam rifles":                             "Assam Rifles",
    "indian army":                              "Indian Army",
    "national investigation agency":            "NIA",
}


def normalize_actor(name: str) -> str:
    """Normalize actor names to merge duplicates. Checks comprehensive alias table first."""
    if not name:
        return ""
    name = name.strip()
    # Strip parenthetical suffix for lookup
    base = name.split("(")[0].strip()
    # Check full name and base against alias table (case-insensitive)
    for candidate in (name.lower(), base.lower()):
        if candidate in MILITANT_ALIASES:
            return MILITANT_ALIASES[candidate]
    # Fallback: return base if meaningful, else full name
    return base if len(base) > 2 else name


def normalize_location(name: str) -> str:
    """Normalize location names."""
    if not name:
        return ""
    name = name.strip()
    # Remove trailing descriptions
    for suffix in [" district", " area", " region", " complex", " border area"]:
        if name.lower().endswith(suffix):
            name = name[:len(name) - len(suffix)].strip()
    return name


async def build_knowledge_graph(db):
    """
    Build the knowledge graph from all processed intelligence items.
    Extracts relationships and cross-references them.
    """
    logger.info("Building knowledge graph...")
    
    actors = defaultdict(lambda: {
        "name": "",
        "aliases": set(),
        "locations": defaultdict(int),
        "threat_types": defaultdict(int),
        "activity_count": 0,
        "first_seen": None,
        "last_seen": None,
        "is_cross_border": False,
        "countries": set(),
        "severity_counts": defaultdict(int),
        "related_actors": defaultdict(int),
        "sample_titles": [],
        "article_ids": [],
    })
    
    locations = defaultdict(lambda: {
        "name": "",
        "actors": defaultdict(int),
        "threat_types": defaultdict(int),
        "activity_count": 0,
        "states": set(),
        "is_border": False,
        "severity_counts": defaultdict(int),
    })
    
    edges = defaultdict(lambda: {
        "actor": "",
        "location": "",
        "count": 0,
        "contexts": defaultdict(int),
        "dates": [],
        "article_ids": [],
    })
    
    # Process all items with entities or actors
    cursor = db.intelligence_items.find(
        {"processed": True, "$or": [
            {"entities": {"$exists": True, "$ne": None}},
            {"actors": {"$exists": True, "$ne": []}},
            {"relationships": {"$exists": True, "$ne": []}}
        ]},
        {"_id": 0}
    )
    
    item_count = 0
    async for item in cursor:
        item_count += 1
        item_id = item.get("id", "")
        title = item.get("title", "")
        pub_date = item.get("published_at", "")
        severity = item.get("severity", "low")
        threat = item.get("threat_category", "")
        state = item.get("state", "")
        is_cross_border = item.get("is_cross_border", False)
        countries = item.get("countries_involved", [])
        
        # Extract from pre-built relationships
        rels = item.get("relationships", [])
        if rels:
            for rel in rels:
                actor_raw = rel.get("actor", "")
                location_raw = rel.get("location", "")
                context = rel.get("context", threat)
                date = rel.get("date", pub_date)
                
                if not actor_raw or not location_raw:
                    continue
                
                actor_key = normalize_actor(actor_raw)
                loc_key = normalize_location(location_raw)
                
                if not actor_key or not loc_key:
                    continue
                
                # Update actor
                a = actors[actor_key]
                a["name"] = actor_key
                a["aliases"].add(actor_raw)
                a["locations"][loc_key] += 1
                a["threat_types"][context] += 1
                a["activity_count"] += 1
                a["severity_counts"][severity] += 1
                a["is_cross_border"] = a["is_cross_border"] or is_cross_border
                for c in countries:
                    a["countries"].add(c)
                if pub_date:
                    if not a["first_seen"] or pub_date < a["first_seen"]:
                        a["first_seen"] = pub_date
                    if not a["last_seen"] or pub_date > a["last_seen"]:
                        a["last_seen"] = pub_date
                if item_id not in a["article_ids"]:
                    a["article_ids"].append(item_id)
                if title and len(a["sample_titles"]) < 5 and title not in a["sample_titles"]:
                    a["sample_titles"].append(title)
                
                # Update location
                loc = locations[loc_key]
                loc["name"] = loc_key
                loc["actors"][actor_key] += 1
                loc["threat_types"][context] += 1
                loc["activity_count"] += 1
                loc["severity_counts"][severity] += 1
                if state:
                    loc["states"].add(state)
                border_keywords = ["border", "indo-", "india-", "myanmar", "bangladesh"]
                if any(bk in loc_key.lower() for bk in border_keywords):
                    loc["is_border"] = True
                
                # Update edge
                edge_key = f"{actor_key}||{loc_key}"
                e = edges[edge_key]
                e["actor"] = actor_key
                e["location"] = loc_key
                e["count"] += 1
                e["contexts"][context] += 1
                if date:
                    e["dates"].append(date)
                if item_id not in e["article_ids"]:
                    e["article_ids"].append(item_id)
        
        else:
            # Fallback: build relationships from entities + actors fields
            item_actors = list(item.get("actors", []))
            entities = item.get("entities", {})
            item_locations = (entities.get("locations", []) if entities else [])

            # Merge militant_groups (Stage 2 explicit extraction) into actors list.
            # These are already exact-named (ULFA-I, NSCN-IM etc.) so take priority.
            militant_groups = (entities.get("militant_groups", []) if entities else [])
            for mg in militant_groups:
                if mg and mg not in item_actors:
                    item_actors.insert(0, mg)  # prepend: higher priority than generic actors
            
            # Add region/state as fallback location
            if not item_locations and state:
                item_locations = [state]
            
            for actor_raw in item_actors:
                actor_key = normalize_actor(actor_raw)
                if not actor_key:
                    continue
                
                a = actors[actor_key]
                a["name"] = actor_key
                a["aliases"].add(actor_raw)
                a["threat_types"][threat] += 1
                a["severity_counts"][severity] += 1
                a["is_cross_border"] = a["is_cross_border"] or is_cross_border
                for c in countries:
                    a["countries"].add(c)
                if pub_date:
                    if not a["first_seen"] or pub_date < a["first_seen"]:
                        a["first_seen"] = pub_date
                    if not a["last_seen"] or pub_date > a["last_seen"]:
                        a["last_seen"] = pub_date
                if item_id not in a["article_ids"]:
                    a["article_ids"].append(item_id)
                if title and len(a["sample_titles"]) < 5 and title not in a["sample_titles"]:
                    a["sample_titles"].append(title)
                
                for loc_raw in item_locations:
                    loc_key = normalize_location(loc_raw)
                    if not loc_key:
                        continue
                    
                    a["locations"][loc_key] += 1
                    a["activity_count"] += 1
                    
                    loc = locations[loc_key]
                    loc["name"] = loc_key
                    loc["actors"][actor_key] += 1
                    loc["threat_types"][threat] += 1
                    loc["activity_count"] += 1
                    loc["severity_counts"][severity] += 1
                    if state:
                        loc["states"].add(state)
                    border_keywords = ["border", "indo-", "india-", "myanmar", "bangladesh"]
                    if any(bk in loc_key.lower() for bk in border_keywords):
                        loc["is_border"] = True
                    
                    edge_key = f"{actor_key}||{loc_key}"
                    e = edges[edge_key]
                    e["actor"] = actor_key
                    e["location"] = loc_key
                    e["count"] += 1
                    e["contexts"][threat] += 1
                    if pub_date:
                        e["dates"].append(pub_date)
                    if item_id not in e["article_ids"]:
                        e["article_ids"].append(item_id)
            
            # Track co-occurring actors
            if len(item_actors) > 1:
                normalized_list = [normalize_actor(a) for a in item_actors if normalize_actor(a)]
                for i, a1 in enumerate(normalized_list):
                    for a2 in normalized_list[i+1:]:
                        if a1 != a2:
                            actors[a1]["related_actors"][a2] += 1
                            actors[a2]["related_actors"][a1] += 1
    
    # Store to MongoDB
    kg_actors_col = db.kg_actors
    kg_locations_col = db.kg_locations
    kg_edges_col = db.kg_edges
    
    await kg_actors_col.drop()
    await kg_locations_col.drop()
    await kg_edges_col.drop()
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Store actors
    actor_docs = []
    for key, a in actors.items():
        if a["activity_count"] == 0 and not a["article_ids"]:
            continue
        actor_docs.append({
            "name": a["name"],
            "aliases": list(a["aliases"]),
            "locations": dict(a["locations"]),
            "threat_types": dict(a["threat_types"]),
            "activity_count": a["activity_count"],
            "article_count": len(a["article_ids"]),
            "first_seen": a["first_seen"],
            "last_seen": a["last_seen"],
            "is_cross_border": a["is_cross_border"],
            "countries": list(a["countries"]),
            "severity_counts": dict(a["severity_counts"]),
            "related_actors": dict(a["related_actors"]),
            "sample_titles": a["sample_titles"],
            "article_ids": a["article_ids"][:20],
            "built_at": now,
        })
    
    if actor_docs:
        await kg_actors_col.insert_many(actor_docs)
    
    # Store locations
    location_docs = []
    for key, loc in locations.items():
        if loc["activity_count"] == 0:
            continue
        location_docs.append({
            "name": loc["name"],
            "actors": dict(loc["actors"]),
            "threat_types": dict(loc["threat_types"]),
            "activity_count": loc["activity_count"],
            "states": list(loc["states"]),
            "is_border": loc["is_border"],
            "severity_counts": dict(loc["severity_counts"]),
            "built_at": now,
        })
    
    if location_docs:
        await kg_locations_col.insert_many(location_docs)
    
    # Store edges
    edge_docs = []
    for key, e in edges.items():
        if e["count"] == 0:
            continue
        edge_docs.append({
            "actor": e["actor"],
            "location": e["location"],
            "count": e["count"],
            "contexts": dict(e["contexts"]),
            "dates": sorted(e["dates"])[-10:],
            "article_ids": e["article_ids"][:20],
            "built_at": now,
        })
    
    if edge_docs:
        await kg_edges_col.insert_many(edge_docs)
    
    logger.info(f"Knowledge graph built: {len(actor_docs)} actors, {len(location_docs)} locations, {len(edge_docs)} edges from {item_count} items")
    
    return {
        "actors": len(actor_docs),
        "locations": len(location_docs),
        "edges": len(edge_docs),
        "items_processed": item_count,
        "built_at": now,
    }
