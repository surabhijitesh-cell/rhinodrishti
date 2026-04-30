"""
Firecrawl integration for Rhino Drishti.

Handles three modes:
  1. scrape_url()         — scrape a single URL to clean markdown
  2. search_and_scrape()  — keyword search + scrape top results
  3. fetch_web_sources()  — scheduled job: scrape all active web_sources docs
  4. run_keyword_searches() — scheduled job: run all active firecrawl_searches docs
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Northeast India news sites to seed (no RSS, JS-heavy, or paywalled) ──────
DEFAULT_WEB_SOURCES = [
    {"name": "Morung Express",          "url": "https://morungexpress.com",        "region": "Nagaland",          "category": "established"},
    {"name": "Nagaland Post",           "url": "https://nagalandpost.com",          "region": "Nagaland",          "category": "established"},
    {"name": "East Mojo",               "url": "https://eastmojo.com",              "region": "Northeast",         "category": "established"},
    {"name": "NE Now News",             "url": "https://nenow.in",                  "region": "Northeast",         "category": "established"},
    {"name": "Imphal Free Press",       "url": "https://ifp.co.in",                 "region": "Manipur",           "category": "established"},
    {"name": "Sangai Express",          "url": "https://sangaiexpress.com",          "region": "Manipur",           "category": "established"},
    {"name": "The Shillong Times",      "url": "https://theshillongtimes.com",       "region": "Meghalaya",         "category": "established"},
    {"name": "Arunachal Times",         "url": "https://arunachaltimes.in",          "region": "Arunachal Pradesh", "category": "established"},
    {"name": "Pratidin Time",           "url": "https://pratidintime.com",           "region": "Assam",             "category": "established"},
    {"name": "The Sentinel Assam",      "url": "https://sentinelassam.com",          "region": "Assam",             "category": "established"},
    {"name": "Mizoram Post",            "url": "https://mizorampost.in",             "region": "Mizoram",           "category": "established"},
    {"name": "Tripura Tribune",         "url": "https://tripuratribune.in",          "region": "Tripura",           "category": "established"},
    {"name": "The Meghalayan",          "url": "https://themeghalayan.com",          "region": "Meghalaya",         "category": "grassroots"},
    {"name": "Nagaland Tribune",        "url": "https://nagalandtribune.in",         "region": "Nagaland",          "category": "grassroots"},
    {"name": "Northeast Live",          "url": "https://northeastlive.in",           "region": "Northeast",         "category": "grassroots"},

    # ── Bangladesh outlets — secondary priority. Captured for events with NER impact:
    # Indo-BD relations, China-BD nexus, BD armed forces, border insurgency / smuggling,
    # refugee movement, minority attacks, political/economic instability with cross-border
    # spillover. Pure-domestic BD politics filtered downstream by AI relevance scoring.
    {"name": "The Daily Star (BD)",       "url": "https://www.thedailystar.net/news/bangladesh", "region": "Bangladesh", "category": "established"},
    {"name": "bdnews24",                  "url": "https://bdnews24.com/bangladesh",              "region": "Bangladesh", "category": "established"},
    {"name": "Prothom Alo English",       "url": "https://en.prothomalo.com/bangladesh",         "region": "Bangladesh", "category": "established"},
    {"name": "TBS News (Business Std)",   "url": "https://www.tbsnews.net/bangladesh",           "region": "Bangladesh", "category": "established"},
    {"name": "Dhaka Tribune",             "url": "https://www.dhakatribune.com/bangladesh",      "region": "Bangladesh", "category": "established"},
    {"name": "New Age (BD)",              "url": "https://www.newagebd.net/section/bangladesh",  "region": "Bangladesh", "category": "established"},
    {"name": "United News Bangladesh",    "url": "https://www.unb.com.bd/category/Bangladesh",   "region": "Bangladesh", "category": "established"},
    {"name": "BSS News (BD official)",    "url": "https://www.bssnews.net/news",                 "region": "Bangladesh", "category": "established"},
]

# ── OSINT keyword searches seeded by default ──────────────────────────────────
DEFAULT_KEYWORD_SEARCHES = [
    {"query": "northeast india insurgency militant",            "num_results": 5},
    {"query": "NSCN ULFA ceasefire negotiation",               "num_results": 5},
    {"query": "Manipur ethnic violence displaced",              "num_results": 5},
    {"query": "Bangladesh border infiltration Assam",           "num_results": 5},
    {"query": "Myanmar military junta northeast india border",  "num_results": 5},
    {"query": "China PLA Arunachal Pradesh border",             "num_results": 5},
    {"query": "drug trafficking northeast india Myanmar",       "num_results": 5},
    {"query": "Brahmaputra floods infrastructure disruption",   "num_results": 3},
    {"query": "arms smuggling BSF Assam Tripura",               "num_results": 3},
    {"query": "Mizoram Chin refugees Myanmar border",           "num_results": 3},
]


def _get_app() -> Optional[object]:
    """Return a FirecrawlApp instance or None if key not set."""
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not set — Firecrawl disabled")
        return None
    try:
        from firecrawl import FirecrawlApp
        return FirecrawlApp(api_key=api_key)
    except ImportError:
        logger.error("firecrawl-py not installed — run: pip install firecrawl-py")
        return None
    except Exception as e:
        logger.error(f"Firecrawl init error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def scrape_url_sync(url: str) -> Optional[dict]:
    """
    Scrape a single URL (synchronous — Firecrawl SDK is sync).
    Returns a dict ready to merge into an intelligence item, or None on failure.
    """
    app = _get_app()
    if not app:
        return None
    try:
        result = app.scrape_url(url, params={"formats": ["markdown"]})
        if not result:
            return None

        # SDK can return a dict or a ScrapeResponse object
        if hasattr(result, "__dict__"):
            result = result.__dict__

        markdown = result.get("markdown") or result.get("content") or ""
        if not markdown or len(markdown.strip()) < 100:
            logger.warning(f"Firecrawl returned thin content for {url}")
            return None

        metadata = result.get("metadata") or {}
        if hasattr(metadata, "__dict__"):
            metadata = metadata.__dict__

        return {
            "title":        metadata.get("title") or url,
            "raw_content":  markdown,
            "source":       metadata.get("siteName") or _domain(url),
            "source_url":   url,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source_type":  "firecrawl_scrape",
        }
    except Exception as e:
        logger.error(f"Firecrawl scrape error for {url}: {e}")
        return None


def search_sync(query: str, num_results: int = 5) -> list:
    """
    Keyword search via Firecrawl — returns a list of raw result dicts.
    Each item has title, raw_content, source_url, source.
    """
    app = _get_app()
    if not app:
        return []
    try:
        response = app.search(query, params={"limit": num_results})
        if hasattr(response, "__dict__"):
            response = response.__dict__

        data = response.get("data") or response.get("results") or []
        items = []
        for r in data:
            if hasattr(r, "__dict__"):
                r = r.__dict__
            content = r.get("markdown") or r.get("description") or r.get("content") or ""
            url = r.get("url") or ""
            if not content or len(content.strip()) < 50:
                continue
            items.append({
                "title":        r.get("title") or url,
                "raw_content":  content,
                "source":       _domain(url),
                "source_url":   url,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source_type":  "firecrawl_search",
                "search_query": query,
            })
        return items
    except Exception as e:
        logger.error(f"Firecrawl search error for '{query}': {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled job helpers (called from server.py)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_web_sources(db) -> int:
    """
    Scheduled job: scrape all active web_sources documents and push results
    through the existing AI classification pipeline.
    """
    import asyncio
    from ai_pipeline import classify_and_analyze_article

    sources = await db.web_sources.find({"active": True}).to_list(length=200)
    if not sources:
        return 0

    saved = 0
    for source in sources:
        url = source.get("url")
        if not url:
            continue

        # Skip if scraped within the last 2 hours
        last_fetched = source.get("last_fetched")
        if last_fetched:
            age = (datetime.now(timezone.utc) - last_fetched).total_seconds()
            if age < 7200:
                continue

        # Firecrawl SDK is synchronous — run in thread pool
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, scrape_url_sync, url)
        if not raw:
            continue

        # Deduplicate by URL
        existing = await db.intelligence_items.find_one({"source_url": url})
        if existing:
            await db.web_sources.update_one(
                {"_id": source["_id"]},
                {"$set": {"last_fetched": datetime.now(timezone.utc)}}
            )
            continue

        item = _base_item(raw)
        try:
            analysis = await classify_and_analyze_article(
                raw["raw_content"][:4000], raw["title"]
            )
            item.update(analysis)
        except Exception as e:
            logger.error(f"AI analysis failed for {url}: {e}")
            item["processed"] = False

        await db.intelligence_items.insert_one(item)
        await db.web_sources.update_one(
            {"_id": source["_id"]},
            {"$set": {"last_fetched": datetime.now(timezone.utc)}}
        )
        saved += 1
        logger.info(f"Firecrawl saved: {raw['title'][:60]}")

    logger.info(f"fetch_web_sources: {saved} new items from {len(sources)} sources")
    return saved


async def run_keyword_searches(db) -> int:
    """
    Scheduled job: run all active firecrawl_searches documents + top keyword
    bank entries through Firecrawl search, then push results through AI.
    """
    import asyncio
    from ai_pipeline import classify_and_analyze_article
    from keyword_engine import get_top_keywords_for_search

    # 1. Manual searches (user added via Settings UI)
    manual = await db.firecrawl_searches.find({"active": True}).to_list(length=100)
    queries = [(s.get("query"), s.get("num_results", 5), s.get("_id"))
               for s in manual if s.get("query")]

    # 2. Top keywords from the dynamic keyword bank
    bank_keywords = await get_top_keywords_for_search(db, limit=10, min_score=40)
    seen = {q[0].lower() for q in queries}
    for kw in bank_keywords:
        if kw.lower() not in seen:
            queries.append((kw, 3, None))  # 3 results per bank query (credit-conscious)
            seen.add(kw.lower())

    if not queries:
        return 0

    logger.info(f"Firecrawl searches: {len(manual)} manual + {len(bank_keywords)} from bank "
                f"= {len(queries)} unique queries")

    saved = 0
    for query, num_results, doc_id in queries:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, lambda q=query, n=num_results: search_sync(q, n)
        )

        for raw in results:
            existing = await db.intelligence_items.find_one({"source_url": raw["source_url"]})
            if existing:
                continue

            item = _base_item(raw)
            try:
                analysis = await classify_and_analyze_article(
                    raw["raw_content"][:4000], raw["title"]
                )
                item.update(analysis)
            except Exception as e:
                logger.error(f"AI analysis failed for search result {raw['source_url']}: {e}")
                item["processed"] = False

            await db.intelligence_items.insert_one(item)
            saved += 1
            logger.info(f"Firecrawl search saved: {raw['title'][:60]}")

        # Only stamp last_run on manually-configured searches
        if doc_id is not None:
            await db.firecrawl_searches.update_one(
                {"_id": doc_id},
                {"$set": {"last_run": datetime.now(timezone.utc)}}
            )

    logger.info(f"run_keyword_searches: {saved} new items from {len(queries)} queries")
    return saved


async def seed_firecrawl_defaults(db) -> None:
    """
    Called once at startup: ensure DEFAULT_WEB_SOURCES and
    DEFAULT_KEYWORD_SEARCHES are present.

    Web sources are seeded *idempotently* — any DEFAULT entry whose URL
    is not already in db.web_sources gets inserted. This lets us add
    new outlets to DEFAULT_WEB_SOURCES (e.g. Bangladesh feeds) and have
    them flow into existing installs on next backend restart, without
    re-seeding or duplicating user-added sources.
    """
    # ── Idempotent web-source seeding ─────────────────────────────────
    existing_urls = set()
    async for doc in db.web_sources.find({}, {"_id": 0, "url": 1}):
        u = doc.get("url")
        if u:
            existing_urls.add(u)

    new_sources = [s for s in DEFAULT_WEB_SOURCES if s["url"] not in existing_urls]
    if new_sources:
        docs = [
            {
                "id": str(uuid.uuid4()),
                "name": s["name"],
                "url": s["url"],
                "region": s["region"],
                "category": s["category"],
                "active": True,
                "last_fetched": None,
                "created_at": datetime.now(timezone.utc),
            }
            for s in new_sources
        ]
        await db.web_sources.insert_many(docs)
        logger.info(f"Seeded {len(docs)} new web sources: "
                    f"{[s['name'] for s in new_sources]}")

    ks_count = await db.firecrawl_searches.count_documents({})
    if ks_count == 0:
        docs = [
            {
                "id": str(uuid.uuid4()),
                "query": s["query"],
                "num_results": s["num_results"],
                "active": True,
                "last_run": None,
                "created_at": datetime.now(timezone.utc),
            }
            for s in DEFAULT_KEYWORD_SEARCHES
        ]
        await db.firecrawl_searches.insert_many(docs)
        logger.info(f"Seeded {len(docs)} default keyword searches")


# ─────────────────────────────────────────────────────────────────────────────
# Internal utils
# ─────────────────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    try:
        return url.split("/")[2]
    except IndexError:
        return url


def _base_item(raw: dict) -> dict:
    return {
        "id":           str(uuid.uuid4()),
        "title":        raw.get("title", "Untitled"),
        "source":       raw.get("source", "firecrawl"),
        "source_url":   raw.get("source_url", ""),
        "published_at": raw.get("published_at", datetime.now(timezone.utc).isoformat()),
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
        "raw_content":  raw.get("raw_content", ""),
        "source_type":  raw.get("source_type", "firecrawl_scrape"),
        "search_query": raw.get("search_query"),
        "processed":    True,
        # AI fields — filled in after classify_and_analyze_article()
        "ai_summary":       "",
        "why_it_matters":   "",
        "potential_impact": "",
        "attention_level":  "Routine Monitoring",
        "state":            "",
        "threat_category":  "",
        "severity":         "medium",
        "is_cross_border":  False,
        "countries_involved": [],
        "tags":             [],
        "priority_score":   30,
        "confidence_score": 70,
        "threat_trajectory": "INDETERMINATE",
        "regions":          [],
        "actors":           [],
        "special_flags":    [],
        "early_warning_signal": "",
        "entities":         {"persons": [], "organizations": [], "locations": []},
        "sifter_level":     1,
        "sifter_triggers":  [],
        "relationships":    [],
    }
