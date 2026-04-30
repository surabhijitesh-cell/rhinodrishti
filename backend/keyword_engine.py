"""
Dynamic Keyword Generation Engine — Generates intelligence-relevant keywords
from historical data, high-priority news, and AI-powered expansion.

Produces multi-layered keywords:
1. PRIMARY: Direct threat terms
2. ENTITY: Actor + action combinations
3. GEO: Region-specific combinations
4. CROSS_BORDER: Cross-border intelligence terms
5. EMERGING: AI-generated signal keywords from recent patterns

Each keyword is scored 0-100 based on frequency, severity association,
cross-border relevance, and recency (time decay).
"""
import os
import logging
import asyncio
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

from llm_client import get_client, MODEL

logger = logging.getLogger(__name__)

# ============================================================
# STATIC SEED KEYWORDS (baseline intelligence vocabulary)
# ============================================================

SEED_KEYWORDS = {
    "primary": [
        "insurgency", "border infiltration", "arms smuggling", "illegal immigration",
        "drone activity", "ethnic clashes", "military movement", "drug trafficking",
        "ceasefire violation", "cross-border shelling", "militant hideout",
        "arms cache", "ied explosion", "ambush", "encounter killing",
        "extortion racket", "kidnapping", "forced recruitment",
        "refugee influx", "demographic shift", "radicalization",
        "cyber attack", "surveillance breach", "espionage",
        "infrastructure sabotage", "dual-use facility",
    ],
    "geo": [
        "Manipur violence", "Assam border tension", "Tripura infiltration",
        "Nagaland ceasefire", "Meghalaya coal mafia", "Mizoram refugee crisis",
        "Arunachal incursion", "Moreh border crossing", "Dawki checkpoint",
        "Tawang standoff", "Siliguri corridor", "Chicken Neck vulnerability",
    ],
    "cross_border": [
        # ── Existing NER-relevant cross-border seeds ───────────────────────
        "India Bangladesh border issue", "Myanmar insurgent camps",
        "Rohingya infiltration India", "BGB BSF coordination",
        "China PLA activity Arunachal", "Pakistan ISI northeast",
        "Myanmar junta resistance", "Chin refugee Mizoram",
        "Arakan Army India border", "Bangladesh India water dispute",

        # ── Bangladesh — events with NER impact ────────────────────────────
        # Each phrase pairs a BD entity/topic with an NER-relevant anchor
        # (border, infiltration, smuggling, India relations, NER state names,
        # insurgent groups operating across the BD border). Pure domestic-BD
        # politics is intentionally excluded — those don't help NER analysts.

        # Indo-Bangladesh diplomacy & political ties
        "India Bangladesh diplomatic relations",
        "Bangladesh Sheikh Hasina India visit",
        "BNP rally India relations",
        "Awami League India bilateral",
        "Indo-Bangla connectivity Northeast",

        # China–Bangladesh nexus (strategic concern for NER)
        "China Bangladesh strategic investment",
        "China loan Bangladesh debt trap",
        "Bangladesh military exercise China",
        "BNS submarine Chinese supply",
        "Belt Road Bangladesh Chittagong",

        # Bangladesh armed forces / paramilitary at NER border
        "BGB border firing infiltrator",
        "BSF BGB joint patrol",
        "Bangladesh Rifles Tripura border",
        "Bangladesh Coast Guard smuggling seizure",

        # Border crime & smuggling impacting NER
        "Tripura Bangladesh cattle smuggling",
        "Meghalaya Dawki coal smuggling",
        "Bangladesh fake currency NER seizure",
        "Yaba pills Bangladesh border",
        "Bangladesh phensedyl smuggling Assam",
        "human trafficking Bangladesh India border",
        "arms smuggling Bangladesh NSCN",

        # Insurgency in BD-NER border belt
        "ULFA Bangladesh hideout",
        "NSCN Bangladesh refuge",
        "JMB Ansar al Islam India border",
        "HuJI Bangladesh terror Northeast",
        "Chittagong Hill Tracts insurgency Tripura",

        # Refugee / minority movement
        "Hindu minority attack Bangladesh",
        "Rohingya Bangladesh repatriation Myanmar",
        "Cox Bazar refugee crisis spillover",
        "Bangladesh Hindu Tripura refugee",

        # Political stability with cross-border spillover
        "Bangladesh election violence border",
        "Hefazat Islamists Bangladesh",
        "Bangladesh political unrest infiltration",
        "Khaleda Zia BNP protest border",

        # Economic stability impacting NER trade
        "Bangladesh forex crisis trade",
        "Bangladesh garment workers protest",
        "Bangladesh economic slowdown Northeast trade",

        # Water / energy / infrastructure shared with NER
        "Teesta water sharing dispute",
        "Ganges Farakka treaty",
        "Bangladesh Maitree power import",
        "Bangladesh Padma Bridge trade impact",
        "Bangladesh Northeast India transit",
    ],
}

# Keyword cache
_keyword_cache = {
    "keywords": [],
    "generated_at": None,
    "ttl_seconds": 1800,  # 30 min cache
}

MAX_KEYWORDS = 500


def _time_decay_score(published_at: str, base_score: float, half_life_days: int = 7) -> float:
    """Apply exponential time decay to a score. Recent items score higher."""
    try:
        if not published_at:
            return base_score * 0.5
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_days = (now - pub).total_seconds() / 86400
        decay = 0.5 ** (age_days / half_life_days)
        return base_score * max(decay, 0.1)
    except Exception:
        return base_score * 0.5


async def _extract_from_historical(db, days: int = 14) -> dict:
    """
    Extract keyword material from recent intelligence items.
    Returns: {entities, actors, locations, threat_types, high_priority_titles}
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    entities_counter = Counter()
    actors_counter = Counter()
    locations_counter = Counter()
    threat_counter = Counter()
    high_priority_texts = []
    region_threat_pairs = Counter()
    actor_location_pairs = Counter()
    
    cursor = db.intelligence_items.find(
        {"processed": True, "published_at": {"$gte": cutoff}},
        {"_id": 0, "title": 1, "actors": 1, "entities": 1, "tags": 1,
         "severity": 1, "state": 1, "regions": 1, "is_cross_border": 1,
         "priority_score": 1, "published_at": 1, "ai_summary": 1,
         "countries_involved": 1, "threat_category": 1}
    )
    
    item_count = 0
    async for item in cursor:
        item_count += 1
        severity = item.get("severity", "low")
        priority = item.get("priority_score", 0)
        published_at = item.get("published_at", "")
        
        # Weight by severity
        sev_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity, 1)
        
        # Actors
        for actor in (item.get("actors") or []):
            if actor and len(actor) > 2:
                actors_counter[actor.strip()] += sev_weight
        
        # Entities
        ents = item.get("entities") or {}
        for org in (ents.get("organizations") or []):
            if org and len(org) > 2:
                entities_counter[org.strip()] += sev_weight
        for person in (ents.get("persons") or []):
            if person and len(person) > 3:
                entities_counter[person.strip()] += sev_weight
        for loc in (ents.get("locations") or []):
            if loc and len(loc) > 2:
                locations_counter[loc.strip()] += sev_weight
        
        # Tags / threat types
        for tag in (item.get("tags") or []):
            if tag:
                threat_counter[tag.strip()] += sev_weight
        if item.get("threat_category"):
            threat_counter[item["threat_category"].strip()] += sev_weight
        
        # Region-threat pairs
        for region in (item.get("regions") or [item.get("state", "")]):
            if region:
                for tag in (item.get("tags") or []):
                    if tag:
                        region_threat_pairs[f"{region}:{tag}"] += sev_weight
        
        # Actor-location pairs
        for actor in (item.get("actors") or []):
            for loc in (ents.get("locations") or [item.get("state", "")]):
                if actor and loc and len(actor) > 2 and len(loc) > 2:
                    actor_location_pairs[f"{actor}:{loc}"] += sev_weight
        
        # High-priority items for AI expansion
        if severity in ("critical", "high") or priority >= 60:
            text = f"{item.get('title', '')} {item.get('ai_summary', '')}"
            high_priority_texts.append({
                "text": text[:300],
                "severity": severity,
                "published_at": published_at,
            })
    
    logger.info(f"Keyword extraction: {item_count} items, {len(actors_counter)} actors, "
                f"{len(locations_counter)} locations, {len(threat_counter)} threats")
    
    return {
        "entities": entities_counter,
        "actors": actors_counter,
        "locations": locations_counter,
        "threats": threat_counter,
        "region_threat_pairs": region_threat_pairs,
        "actor_location_pairs": actor_location_pairs,
        "high_priority_texts": high_priority_texts[:20],
        "item_count": item_count,
    }


def _generate_primary_keywords(historical: dict) -> list:
    """Generate primary threat keywords from seed + historical data."""
    keywords = []
    
    # Seed keywords
    for kw in SEED_KEYWORDS["primary"]:
        keywords.append({
            "keyword": kw,
            "type": "primary",
            "score": 50,
            "source": "seed",
        })
    
    # Top threats from historical data
    for threat, count in historical["threats"].most_common(30):
        if len(threat) > 3 and threat.lower() not in [k["keyword"].lower() for k in keywords]:
            score = min(95, 40 + count * 3)
            keywords.append({
                "keyword": threat,
                "type": "primary",
                "score": score,
                "source": "historical",
            })
    
    return keywords


def _generate_entity_keywords(historical: dict) -> list:
    """Generate entity-based keywords (actor + action combinations)."""
    keywords = []
    
    # Top actors
    for actor, count in historical["actors"].most_common(25):
        if len(actor) < 3:
            continue
        score = min(90, 35 + count * 4)
        keywords.append({
            "keyword": actor,
            "type": "entity",
            "score": score,
            "source": "historical",
        })
    
    # Top organizations
    for org, count in historical["entities"].most_common(20):
        if len(org) < 3:
            continue
        score = min(85, 30 + count * 3)
        keywords.append({
            "keyword": org,
            "type": "entity",
            "score": score,
            "source": "historical",
        })
    
    # Actor + location combinations (most valuable)
    for pair, count in historical["actor_location_pairs"].most_common(20):
        parts = pair.split(":")
        if len(parts) == 2 and count >= 2:
            actor, loc = parts
            combo = f"{actor} {loc}"
            score = min(95, 45 + count * 5)
            keywords.append({
                "keyword": combo,
                "type": "entity",
                "score": score,
                "source": "historical",
            })
    
    return keywords


def _generate_geo_keywords(historical: dict) -> list:
    """Generate region-specific combination keywords."""
    keywords = []
    
    # Seed geo keywords
    for kw in SEED_KEYWORDS["geo"]:
        keywords.append({
            "keyword": kw,
            "type": "geo",
            "score": 45,
            "source": "seed",
        })
    
    # Top locations
    for loc, count in historical["locations"].most_common(30):
        if len(loc) < 3:
            continue
        score = min(80, 30 + count * 3)
        keywords.append({
            "keyword": loc,
            "type": "geo",
            "score": score,
            "source": "historical",
        })
    
    # Region-threat pairs
    for pair, count in historical["region_threat_pairs"].most_common(25):
        parts = pair.split(":")
        if len(parts) == 2 and count >= 2:
            region, threat = parts
            combo = f"{region} {threat}"
            score = min(90, 40 + count * 4)
            keywords.append({
                "keyword": combo,
                "type": "geo",
                "score": score,
                "source": "historical",
            })
    
    return keywords


def _generate_cross_border_keywords(historical: dict) -> list:
    """Generate cross-border intelligence keywords."""
    keywords = []
    
    # Seed cross-border
    for kw in SEED_KEYWORDS["cross_border"]:
        keywords.append({
            "keyword": kw,
            "type": "cross_border",
            "score": 55,
            "source": "seed",
        })
    
    return keywords


async def _generate_emerging_keywords(historical: dict, emergent_key: str = "") -> list:
    """Use Claude to generate emerging signal keywords from recent high-priority patterns."""
    if not historical.get("high_priority_texts"):
        return []
    
    # Build context from high-priority items
    context_items = historical["high_priority_texts"][:15]
    context_text = "\n".join([f"- [{h['severity']}] {h['text']}" for h in context_items])
    
    top_actors = [a for a, _ in historical["actors"].most_common(10)]
    top_threats = [t for t, _ in historical["threats"].most_common(10)]
    top_locations = [l for l, _ in historical["locations"].most_common(10)]
    
    prompt = f"""You are a military intelligence keyword analyst. Based on the following recent HIGH-PRIORITY intelligence items, generate 15-20 EMERGING SIGNAL KEYWORDS that would help detect similar or escalating threats.

RECENT HIGH-PRIORITY INTELLIGENCE:
{context_text}

TOP ACTIVE ACTORS: {', '.join(top_actors[:10])}
TOP THREAT TYPES: {', '.join(top_threats[:10])}
TOP LOCATIONS: {', '.join(top_locations[:10])}

Generate keywords that capture:
1. Emerging patterns (coordinated operations, new alliances, shifting tactics)
2. Precursor signals (mobilization indicators, supply chain shifts, communication changes)
3. Cross-domain connections (infrastructure + military, migration + radicalization)
4. Intelligence-style phrasings that journalists and analysts might use

RULES:
- Each keyword 2-5 words
- Must be intelligence/security-focused, NOT generic
- No sports, entertainment, lifestyle terms
- Focus on NER/Bangladesh/Myanmar/China/Pakistan context

Return ONLY a JSON array of strings. No explanation.
Example: ["coordinated ethnic mobilization", "infrastructure dual-use concern", "cross-border supply chain disruption"]"""

    try:
        import json
        client = get_client()
        response = await client.messages.create(
            model=MODEL,
            max_tokens=512,
            system="You are a military intelligence keyword generator. Output ONLY valid JSON arrays.",
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text
        arr_start = response_text.find('[')
        arr_end = response_text.rfind(']') + 1
        if arr_start >= 0 and arr_end > arr_start:
            emerging_list = json.loads(response_text[arr_start:arr_end])
        else:
            logger.warning("No JSON array in AI keyword response")
            return []
        
        keywords = []
        for kw in emerging_list:
            if isinstance(kw, str) and 3 < len(kw) < 80:
                keywords.append({
                    "keyword": kw.strip(),
                    "type": "emerging",
                    "score": 70,
                    "source": "ai",
                })
        
        logger.info(f"AI generated {len(keywords)} emerging signal keywords")
        return keywords
    
    except Exception as e:
        logger.error(f"AI keyword generation failed: {e}")
        return []


async def _expand_keywords_with_ai(base_keywords: list, emergent_key: str = "") -> list:
    """Use AI to expand high-score keywords into synonyms and related phrases."""
    
    # Pick top-scoring keywords for expansion
    top_kws = sorted(base_keywords, key=lambda k: k["score"], reverse=True)[:15]
    kw_list = [k["keyword"] for k in top_kws]
    
    prompt = f"""Expand these intelligence keywords into synonyms and related intelligence phrases. For each keyword, provide 2-3 alternatives that mean the same thing in intelligence context.

Keywords: {', '.join(kw_list)}

Return ONLY a JSON object mapping each keyword to its expansions array.
Example: {{"border infiltration": ["unauthorized border crossing", "cross-border intrusion", "illegal entry attempt"]}}"""

    try:
        import json
        client = get_client()
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system="You are a military intelligence thesaurus. Output ONLY valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text
        
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            expansions = json.loads(response_text[json_start:json_end])
        else:
            return []
        
        expanded = []
        for original_kw, synonyms in expansions.items():
            if not isinstance(synonyms, list):
                continue
            # Find the original's score
            orig_score = next((k["score"] for k in top_kws if k["keyword"].lower() == original_kw.lower()), 50)
            for syn in synonyms:
                if isinstance(syn, str) and 3 < len(syn) < 80:
                    expanded.append({
                        "keyword": syn.strip(),
                        "type": "expanded",
                        "score": max(30, orig_score - 15),
                        "source": "ai_expansion",
                        "parent_keyword": original_kw,
                    })
        
        logger.info(f"AI expanded into {len(expanded)} synonym keywords")
        return expanded
    
    except Exception as e:
        logger.error(f"AI keyword expansion failed: {e}")
        return []


def _deduplicate_and_rank(all_keywords: list) -> list:
    """Deduplicate keywords and keep highest-scoring version. Cap at MAX_KEYWORDS."""
    seen = {}
    for kw in all_keywords:
        key = kw["keyword"].lower().strip()
        if key in seen:
            if kw["score"] > seen[key]["score"]:
                seen[key] = kw
        else:
            seen[key] = kw
    
    ranked = sorted(seen.values(), key=lambda k: k["score"], reverse=True)
    return ranked[:MAX_KEYWORDS]


async def generate_keywords(db, emergent_key: str = "", use_ai: bool = True) -> list:  # emergent_key kept for compat, unused
    """
    Main entry point: generate the full multi-layered keyword set.
    
    Returns list of keyword dicts: [{keyword, type, score, source}, ...]
    """
    # Check cache
    if (_keyword_cache["generated_at"] and
        _keyword_cache["keywords"] and
        (datetime.now(timezone.utc) - _keyword_cache["generated_at"]).total_seconds() < _keyword_cache["ttl_seconds"]):
        logger.info(f"Returning {len(_keyword_cache['keywords'])} cached keywords")
        return _keyword_cache["keywords"]
    
    logger.info("Generating dynamic keywords...")
    
    # Step 1: Extract from historical intelligence data
    historical = await _extract_from_historical(db, days=14)
    
    # Step 2: Generate each keyword layer
    all_keywords = []
    all_keywords.extend(_generate_primary_keywords(historical))
    all_keywords.extend(_generate_entity_keywords(historical))
    all_keywords.extend(_generate_geo_keywords(historical))
    all_keywords.extend(_generate_cross_border_keywords(historical))
    
    # Step 3: AI-powered generation (emerging signals + expansion)
    if use_ai:
        emerging = await _generate_emerging_keywords(historical)
        all_keywords.extend(emerging)

        expanded = await _expand_keywords_with_ai(all_keywords)
        all_keywords.extend(expanded)
    
    # Step 4: Deduplicate and rank
    final_keywords = _deduplicate_and_rank(all_keywords)
    
    # Step 5: Cache
    _keyword_cache["keywords"] = final_keywords
    _keyword_cache["generated_at"] = datetime.now(timezone.utc)
    
    logger.info(f"Generated {len(final_keywords)} dynamic keywords "
                f"(primary: {sum(1 for k in final_keywords if k['type']=='primary')}, "
                f"entity: {sum(1 for k in final_keywords if k['type']=='entity')}, "
                f"geo: {sum(1 for k in final_keywords if k['type']=='geo')}, "
                f"cross_border: {sum(1 for k in final_keywords if k['type']=='cross_border')}, "
                f"emerging: {sum(1 for k in final_keywords if k['type']=='emerging')}, "
                f"expanded: {sum(1 for k in final_keywords if k['type']=='expanded')})")
    
    return final_keywords


async def store_keywords_to_db(db, keywords: list):
    """Persist generated keywords to MongoDB keyword_store collection."""
    now = datetime.now(timezone.utc).isoformat()
    
    for kw in keywords:
        await db.keyword_store.update_one(
            {"keyword": kw["keyword"]},
            {"$set": {
                "keyword": kw["keyword"],
                "category": kw["type"],
                "score": kw["score"],
                "source": kw.get("source", "generated"),
                "parent_keyword": kw.get("parent_keyword"),
                "last_updated": now,
            }, "$setOnInsert": {"created_at": now}},
            upsert=True
        )


async def adaptive_feedback(db, article: dict, classification_result: dict):
    """
    Adaptive learning loop: adjust keyword scores based on AI classification results.
    
    HIGH/CRITICAL → extract new keywords, boost triggering keywords
    LOW relevance → decay triggering keywords
    """
    severity = classification_result.get("severity", "low")
    is_relevant = classification_result.get("is_relevant", True)
    title = (article.get("title", "") or "").lower()
    content = (article.get("raw_content", "") or "").lower()[:500]
    text = f"{title} {content}"
    
    now = datetime.now(timezone.utc).isoformat()
    
    if not is_relevant or severity == "low":
        # Decay keywords that matched this low-relevance article
        cursor = db.keyword_store.find({"score": {"$gt": 10}}, {"_id": 0, "keyword": 1})
        async for kw_doc in cursor:
            kw = kw_doc["keyword"].lower()
            if kw in text:
                await db.keyword_store.update_one(
                    {"keyword": kw_doc["keyword"]},
                    {"$inc": {"score": -2}, "$set": {"last_updated": now}}
                )
    
    elif severity in ("critical", "high"):
        # Boost keywords that matched this high-priority article
        cursor = db.keyword_store.find({}, {"_id": 0, "keyword": 1, "score": 1})
        async for kw_doc in cursor:
            kw = kw_doc["keyword"].lower()
            if kw in text:
                new_score = min(100, kw_doc.get("score", 50) + 5)
                await db.keyword_store.update_one(
                    {"keyword": kw_doc["keyword"]},
                    {"$set": {"score": new_score, "last_updated": now}}
                )
        
        # Extract new keywords from high-priority article
        actors = classification_result.get("actors", [])
        entities = classification_result.get("entities", {})
        
        new_keywords = []
        for actor in actors:
            if actor and len(actor) > 2:
                new_keywords.append({"keyword": actor, "type": "entity", "score": 70, "source": "adaptive"})
        for loc in (entities.get("locations") or []):
            if loc and len(loc) > 2:
                new_keywords.append({"keyword": loc, "type": "geo", "score": 60, "source": "adaptive"})
        for org in (entities.get("organizations") or []):
            if org and len(org) > 2:
                new_keywords.append({"keyword": org, "type": "entity", "score": 65, "source": "adaptive"})
        
        for kw in new_keywords:
            await db.keyword_store.update_one(
                {"keyword": kw["keyword"]},
                {"$set": {
                    "keyword": kw["keyword"],
                    "category": kw["type"],
                    "score": kw["score"],
                    "source": kw["source"],
                    "last_updated": now,
                }, "$setOnInsert": {"created_at": now}},
                upsert=True
            )


def get_dynamic_keywords_for_matching(keywords: list) -> list:
    """
    Convert keyword list to weighted matching terms for RSS filtering.
    Returns list of (keyword, weight) tuples sorted by weight descending.
    """
    return [(kw["keyword"].lower(), kw["score"] / 100.0) for kw in keywords if kw["score"] > 20]


async def get_top_keywords_for_search(db, limit: int = 10, min_score: int = 40) -> list:
    """
    Return top-scored keyword strings from db.keyword_store, suitable for use
    as search queries on YouTube, Twitter, Firecrawl.

    Falls back to SEED_KEYWORDS if the bank is empty or all below threshold —
    so social media searches always have *something* to search for, even on
    a fresh install before the keyword engine has run.

    Args:
      limit:     max number of queries to return
      min_score: skip keywords scored below this (range 0-100)
    """
    keywords = []
    try:
        cursor = db.keyword_store.find(
            {"score": {"$gte": min_score}},
            {"_id": 0, "keyword": 1, "score": 1, "category": 1},
        ).sort("score", -1).limit(limit * 2)  # over-fetch, then dedupe
        async for doc in cursor:
            kw = (doc.get("keyword") or "").strip()
            if kw and 3 <= len(kw) <= 80 and kw.lower() not in {k.lower() for k in keywords}:
                keywords.append(kw)
            if len(keywords) >= limit:
                break
    except Exception as e:
        logger.error(f"get_top_keywords_for_search: keyword_store query failed: {e}")

    if not keywords:
        logger.warning("Keyword bank empty — falling back to SEED_KEYWORDS for searches")
        # Build a balanced fallback: 5 primary + 3 geo + 2 cross-border
        keywords = (
            SEED_KEYWORDS["primary"][:5]
            + SEED_KEYWORDS["geo"][:3]
            + SEED_KEYWORDS["cross_border"][:2]
        )

    return keywords[:limit]


def score_article_against_keywords(article: dict, keyword_weights: list) -> float:
    """
    Score an article against dynamic keywords.
    Returns a weighted relevance score 0-100.
    """
    title = (article.get("title", "") or "").lower()
    content = (article.get("raw_content", "") or article.get("description", "") or "").lower()
    text = f"{title} {content[:500]}"
    
    total_weight = 0
    max_possible = 0
    title_bonus = 0
    
    for kw, weight in keyword_weights:
        max_possible += weight
        if kw in text:
            total_weight += weight
            # Extra weight for title matches
            if kw in title:
                title_bonus += weight * 0.5
    
    if max_possible == 0:
        return 0
    
    raw_score = ((total_weight + title_bonus) / max_possible) * 100
    return min(100, raw_score)
