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
import hashlib
import logging
from datetime import datetime, timezone, timedelta
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
# Runs every 6 hours. Each query fetches num_results pages via Firecrawl search,
# then each new (non-duplicate) result goes through the AI classification pipeline.
# Keep num_results at 3-5 for broad queries; up to 8 for highly specific ones.
DEFAULT_KEYWORD_SEARCHES = [
    # ── NER insurgency & militancy ────────────────────────────────────────────
    {"query": "northeast india insurgency militant 2025",           "num_results": 5},
    {"query": "NSCN ULFA ceasefire negotiation Naga peace",        "num_results": 5},
    {"query": "Manipur ethnic violence Meitei Kuki displaced",      "num_results": 5},
    {"query": "Assam Meghalaya Tripura insurgency arrest",          "num_results": 5},
    {"query": "Nagaland armed group ceasefire 2025",                "num_results": 3},

    # ── Bangladesh security & cross-border ────────────────────────────────────
    {"query": "Bangladesh border infiltration Assam BSF",           "num_results": 5},
    {"query": "BGB BSF border shooting Bangladesh India",           "num_results": 5},
    {"query": "Bangladesh China military cooperation 2025",         "num_results": 5},
    {"query": "Bangladesh minority Hindu attack violence",          "num_results": 5},
    {"query": "Bangladesh political instability military Dhaka",    "num_results": 5},
    {"query": "Bangladesh Rohingya border Myanmar Cox Bazar",       "num_results": 3},
    {"query": "illegal immigration Bangladesh Assam arrest",        "num_results": 5},

    # ── Myanmar & Chin State ──────────────────────────────────────────────────
    {"query": "Myanmar civil war Chin State India border Mizoram",  "num_results": 5},
    {"query": "Myanmar military junta northeast india border",      "num_results": 5},
    {"query": "Tatmadaw Arakan Army offensive Rakhine",             "num_results": 5},
    {"query": "Myanmar refugees Mizoram India 2025",                "num_results": 5},
    {"query": "Myanmar drug trafficking methamphetamine India",     "num_results": 3},

    # ── China & PLA ───────────────────────────────────────────────────────────
    {"query": "China PLA Arunachal Pradesh border incursion",       "num_results": 5},
    {"query": "China Bangladesh infrastructure Belt Road",          "num_results": 5},
    {"query": "PLA exercise India border Himalaya 2025",            "num_results": 3},

    # ── Smuggling, trafficking, drones ───────────────────────────────────────
    {"query": "drug trafficking northeast india Myanmar heroin",    "num_results": 5},
    {"query": "arms smuggling BSF Assam Tripura arrested",          "num_results": 5},
    {"query": "drone incursion northeast india border UAV",         "num_results": 3},

    # ── Infrastructure & early warning ────────────────────────────────────────
    {"query": "Brahmaputra floods infrastructure disruption 2025",  "num_results": 3},
    {"query": "northeast india highway blockade shutdown protest",  "num_results": 3},
]


def _get_app() -> Optional[object]:
    """
    Return a Firecrawl client or None if key not set.

    firecrawl-py broke its API across major versions:
      v0.x  → FirecrawlApp  + scrape_url(url, params={...})
      v1.x  → FirecrawlApp  + scrape_url(url, formats=[...])
      v1 SDK (PyPI ≥4.x rewrite) → Firecrawl + scrape(url, formats=[...])
    Try newest naming first.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not set — Firecrawl disabled")
        return None
    try:
        # New SDK (≥4.x): class is Firecrawl, method is scrape()
        try:
            from firecrawl import Firecrawl
            return Firecrawl(api_key=api_key)
        except (ImportError, Exception):
            pass
        # Legacy SDK: class is FirecrawlApp
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

def _extract_from_result(result) -> tuple[str, dict]:
    """
    Extract (markdown, metadata_dict) from a Firecrawl SDK response.
    Handles all known SDK shapes across versions.
    """
    def _safe_meta(raw_meta) -> dict:
        if isinstance(raw_meta, dict):
            return raw_meta
        if hasattr(raw_meta, "__dict__"):
            return {k: v for k, v in raw_meta.__dict__.items() if not k.startswith("_")}
        return {}

    # Object with direct attributes (v1 ScrapeResponse / v4 scrape result)
    if hasattr(result, "markdown"):
        return result.markdown or "", _safe_meta(getattr(result, "metadata", {}))

    # Some v4 responses may use `content` instead of `markdown`
    if hasattr(result, "content"):
        meta = _safe_meta(getattr(result, "metadata", {}))
        return result.content or "", meta

    # Dict shape (v0.x)
    if isinstance(result, dict):
        md = result.get("markdown") or result.get("content") or ""
        return md, _safe_meta(result.get("metadata") or {})

    # Last resort: __dict__ of unknown object
    if hasattr(result, "__dict__"):
        d = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
        md = d.get("markdown") or d.get("content") or ""
        return md, _safe_meta(d.get("metadata") or {})

    return "", {}


def _call_scrape(app, url: str):
    """
    Try all known firecrawl-py call signatures, newest first.
    Returns the raw SDK response object on success, raises on failure.

    Signature history:
      v4+ SDK  → app.scrape(url, formats=[...])          ← try first
      v1.x     → app.scrape_url(url, formats=[...])
      v0.x     → app.scrape_url(url, params={...})
      fallback → app.scrape_url(url)  or  app.scrape(url)
    """
    # New SDK (≥4.x): method renamed to scrape()
    if hasattr(app, "scrape"):
        try:
            return app.scrape(url, formats=["markdown"])
        except TypeError:
            try:
                return app.scrape(url)
            except Exception:
                pass

    # Legacy SDK: scrape_url()
    if hasattr(app, "scrape_url"):
        try:
            return app.scrape_url(url, formats=["markdown"])
        except TypeError:
            pass
        try:
            return app.scrape_url(url, params={"formats": ["markdown"]})
        except TypeError:
            pass
        return app.scrape_url(url)

    raise AttributeError(
        f"Neither scrape() nor scrape_url() found on {type(app).__name__} "
        f"(firecrawl-py SDK). Check SDK version."
    )


def scrape_url_raising(url: str) -> dict:
    """
    Same as scrape_url_sync but RAISES with a descriptive message on failure.
    Used by on-demand HTTP endpoints so the real error surfaces to the client.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY is not set on the server. Add it to Render environment variables.")

    try:
        import firecrawl as _fc_mod
        version = getattr(_fc_mod, "__version__", "unknown")
    except ImportError:
        raise RuntimeError("firecrawl-py package not installed on server.")

    app = _get_app()
    if not app:
        raise RuntimeError(f"Firecrawl client init failed (SDK v{version}). Check server logs.")

    try:
        result = _call_scrape(app, url)
    except Exception as e:
        raise RuntimeError(f"Firecrawl API error (SDK v{version}): {e}")

    if not result:
        raise RuntimeError(f"Firecrawl returned empty response for {url} (SDK v{version})")

    markdown, metadata = _extract_from_result(result)

    if not markdown or len(markdown.strip()) < 50:
        chars = len(markdown.strip()) if markdown else 0
        raise RuntimeError(
            f"Firecrawl returned thin content ({chars} chars) for {url}. "
            "The site may block scrapers or the page has no readable text."
        )

    return {
        "title":        metadata.get("title") or metadata.get("ogTitle") or url,
        "raw_content":  markdown,
        "source":       metadata.get("siteName") or metadata.get("ogSiteName") or _domain(url),
        "source_url":   url,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "source_type":  "firecrawl_scrape",
    }


def scrape_url_sync(url: str) -> Optional[dict]:
    """
    Scrape a single URL (synchronous — Firecrawl SDK is sync).
    Returns a dict ready to merge into an intelligence item, or None on failure.
    Supports firecrawl-py v1 (formats= kwarg) and legacy (params= kwarg).
    """
    app = _get_app()
    if not app:
        return None
    try:
        result = _call_scrape(app, url)

        if not result:
            logger.warning(f"Firecrawl returned empty result for {url}")
            return None

        markdown, metadata = _extract_from_result(result)

        if not markdown or len(markdown.strip()) < 50:
            logger.warning(f"Firecrawl thin content ({len(markdown)} chars) for {url}")
            return None

        return {
            "title":        metadata.get("title") or metadata.get("ogTitle") or url,
            "raw_content":  markdown,
            "source":       metadata.get("siteName") or metadata.get("ogSiteName") or _domain(url),
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
    Supports firecrawl-py v1 (limit= kwarg) and legacy (params= dict).
    """
    app = _get_app()
    if not app:
        return []
    try:
        # firecrawl-py v1 uses keyword args
        try:
            response = app.search(query, limit=num_results)
        except TypeError:
            response = app.search(query, params={"limit": num_results})

        # v1 returns SearchResponse with .data list of SearchResult objects
        if hasattr(response, "data"):
            raw_list = response.data or []
        elif isinstance(response, dict):
            raw_list = response.get("data") or response.get("results") or []
        elif hasattr(response, "__dict__"):
            d = response.__dict__
            raw_list = d.get("data") or d.get("results") or []
        else:
            raw_list = []

        items = []
        for r in raw_list:
            # Each result may be a SearchResult object or a dict
            if hasattr(r, "url"):
                url     = r.url or ""
                content = (getattr(r, "markdown", None) or
                           getattr(r, "description", None) or
                           getattr(r, "content", None) or "")
                title   = getattr(r, "title", None) or url
            elif isinstance(r, dict):
                url     = r.get("url") or ""
                content = r.get("markdown") or r.get("description") or r.get("content") or ""
                title   = r.get("title") or url
            elif hasattr(r, "__dict__"):
                rd      = r.__dict__
                url     = rd.get("url") or ""
                content = rd.get("markdown") or rd.get("description") or rd.get("content") or ""
                title   = rd.get("title") or url
            else:
                continue

            if not content or len(content.strip()) < 50:
                continue

            items.append({
                "title":        title,
                "raw_content":  content,
                "source":       _domain(url),
                "source_url":   url,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source_type":  "firecrawl_search",
                "search_query": query,
            })
        logger.info(f"Firecrawl search '{query}': {len(items)} results")
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
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, scrape_url_sync, url)
        if not raw:
            continue

        # Dedup by MD5 hash of content — identical homepage snapshots are skipped,
        # but a changed homepage (new articles at top) always saves.
        # Title-based dedup was wrong: homepage title never changes → blocked every
        # subsequent fetch.  URL-based dedup also wrong: same reason.
        content_hash = hashlib.md5(raw["raw_content"].encode(errors="ignore")).hexdigest()
        existing = await db.intelligence_items.find_one({"content_hash": content_hash})

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
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, lambda q=query, n=num_results: search_sync(q, n)
        )

        for raw in results:
            # Dedup by content hash — same article content already stored → skip
            content_hash = hashlib.md5(raw["raw_content"].encode(errors="ignore")).hexdigest()
            existing = await db.intelligence_items.find_one({"content_hash": content_hash})
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
    content = raw.get("raw_content", "")
    return {
        "id":           str(uuid.uuid4()),
        "title":        raw.get("title", "Untitled"),
        "source":       raw.get("source", "firecrawl"),
        "source_url":   raw.get("source_url", ""),
        "published_at": raw.get("published_at", datetime.now(timezone.utc).isoformat()),
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
        "raw_content":  content,
        "content_hash": hashlib.md5(content.encode(errors="ignore")).hexdigest(),
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
