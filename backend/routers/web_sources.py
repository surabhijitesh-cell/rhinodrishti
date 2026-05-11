"""
Web Sources & Firecrawl router.

Endpoints:
  GET  /api/web-sources              — list all web sources
  POST /api/web-sources              — add a new web source
  PATCH /api/web-sources/{id}        — toggle active / update fields
  DELETE /api/web-sources/{id}       — remove a web source
  POST /api/web-sources/{id}/scrape  — on-demand scrape of one source

  GET  /api/firecrawl-searches              — list keyword searches
  POST /api/firecrawl-searches              — add a keyword search
  PATCH /api/firecrawl-searches/{id}        — update / toggle active
  DELETE /api/firecrawl-searches/{id}       — remove
  POST /api/firecrawl-searches/{id}/run     — run one search now

  POST /api/firecrawl/scrape-url    — on-demand: scrape any URL
  GET  /api/firecrawl/status        — is Firecrawl configured?
"""

import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
from shared import db, logger

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class WebSourceCreate(BaseModel):
    name: str
    url: str
    region: str = "Northeast"
    category: str = "grassroots"       # grassroots | established
    active: bool = True


class WebSourcePatch(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    region: Optional[str] = None
    category: Optional[str] = None


class KeywordSearchCreate(BaseModel):
    query: str
    num_results: int = 5
    active: bool = True


class KeywordSearchPatch(BaseModel):
    query: Optional[str] = None
    num_results: Optional[int] = None
    active: Optional[bool] = None


class ScrapeUrlRequest(BaseModel):
    url: str


# ─────────────────────────────────────────────────────────────────────────────
# Firecrawl status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/firecrawl/status")
async def firecrawl_status():
    import os
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    return {
        "configured": bool(key),
        "key_preview": f"{key[:8]}..." if key else None,
    }


@router.get("/firecrawl/diagnose")
async def firecrawl_diagnose():
    """
    Full diagnostic — call this to see exactly why Firecrawl is failing.
    Returns: API key status, SDK version, and a live test scrape result.
    """
    import os
    result = {}

    # 1. API key
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    result["api_key_set"] = bool(key)
    result["api_key_preview"] = f"{key[:8]}..." if key else "NOT SET"

    # 2. SDK version
    try:
        import firecrawl as _fc
        result["sdk_version"] = getattr(_fc, "__version__", "installed but version unknown")
    except ImportError:
        result["sdk_version"] = "NOT INSTALLED"
        return result

    # 3. Test scrape a small, reliable page
    TEST_URL = "https://eastmojo.com"
    from firecrawl_fetcher import scrape_url_raising
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, scrape_url_raising, TEST_URL)
        result["test_scrape"] = "OK"
        result["test_title"] = raw.get("title", "")[:100]
        result["test_content_chars"] = len(raw.get("raw_content", ""))
    except RuntimeError as exc:
        result["test_scrape"] = "FAILED"
        result["test_error"] = str(exc)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Web Sources CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/web-sources")
async def list_web_sources():
    sources = await db.web_sources.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return {"sources": sources, "count": len(sources)}


@router.post("/web-sources", status_code=201)
async def add_web_source(body: WebSourceCreate):
    existing = await db.web_sources.find_one({"url": body.url})
    if existing:
        raise HTTPException(status_code=409, detail="URL already exists")
    doc = {
        "id":           str(uuid.uuid4()),
        "name":         body.name,
        "url":          body.url,
        "region":       body.region,
        "category":     body.category,
        "active":       body.active,
        "last_fetched": None,
        "created_at":   datetime.now(timezone.utc),
    }
    await db.web_sources.insert_one(doc)
    doc.pop("_id", None)
    return {"source": doc}


@router.patch("/web-sources/{source_id}")
async def update_web_source(source_id: str, body: WebSourcePatch):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.web_sources.update_one({"id": source_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Web source not found")
    return {"updated": True}


@router.delete("/web-sources/{source_id}")
async def delete_web_source(source_id: str):
    result = await db.web_sources.delete_one({"id": source_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Web source not found")
    return {"deleted": True}


@router.post("/web-sources/{source_id}/scrape")
async def scrape_web_source_now(source_id: str):
    """On-demand scrape of a single web source."""
    source = await db.web_sources.find_one({"id": source_id})
    if not source:
        raise HTTPException(status_code=404, detail="Web source not found")

    from firecrawl_fetcher import scrape_url_raising, _base_item
    from ai_pipeline import classify_and_analyze_article
    import hashlib

    url = source["url"]
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, scrape_url_raising, url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Deduplicate by content hash (URL dedup was wrong — homepage URL never changes)
    content_hash = hashlib.md5(raw["raw_content"].encode(errors="ignore")).hexdigest()
    existing = await db.intelligence_items.find_one({"content_hash": content_hash})
    if existing:
        return {"message": "Already in database (same content)", "id": existing.get("id")}

    item = _base_item(raw)
    try:
        analysis = await classify_and_analyze_article(raw["raw_content"][:4000], raw["title"])
        item.update(analysis)
    except Exception as e:
        logger.error(f"AI analysis failed for on-demand scrape {url}: {e}")
        item["processed"] = False

    await db.intelligence_items.insert_one(item)
    await db.web_sources.update_one(
        {"id": source_id},
        {"$set": {"last_fetched": datetime.now(timezone.utc)}}
    )
    item.pop("_id", None)
    return {"saved": True, "item_id": item["id"], "title": item["title"]}


# ─────────────────────────────────────────────────────────────────────────────
# Keyword Searches CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/firecrawl-searches")
async def list_keyword_searches():
    searches = await db.firecrawl_searches.find({}, {"_id": 0}).sort("query", 1).to_list(200)
    return {"searches": searches, "count": len(searches)}


@router.post("/firecrawl-searches", status_code=201)
async def add_keyword_search(body: KeywordSearchCreate):
    existing = await db.firecrawl_searches.find_one({"query": body.query})
    if existing:
        raise HTTPException(status_code=409, detail="Query already exists")
    doc = {
        "id":           str(uuid.uuid4()),
        "query":        body.query,
        "num_results":  body.num_results,
        "active":       body.active,
        "last_run":     None,
        "created_at":   datetime.now(timezone.utc),
    }
    await db.firecrawl_searches.insert_one(doc)
    doc.pop("_id", None)
    return {"search": doc}


@router.patch("/firecrawl-searches/{search_id}")
async def update_keyword_search(search_id: str, body: KeywordSearchPatch):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.firecrawl_searches.update_one({"id": search_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Search not found")
    return {"updated": True}


@router.delete("/firecrawl-searches/{search_id}")
async def delete_keyword_search(search_id: str):
    result = await db.firecrawl_searches.delete_one({"id": search_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Search not found")
    return {"deleted": True}


@router.post("/firecrawl-searches/{search_id}/run")
async def run_keyword_search_now(search_id: str):
    """On-demand: run one keyword search immediately."""
    search = await db.firecrawl_searches.find_one({"id": search_id})
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    from firecrawl_fetcher import search_sync, _base_item
    from ai_pipeline import classify_and_analyze_article

    query = search["query"]
    num_results = search.get("num_results", 5)

    import hashlib
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        None, lambda: search_sync(query, num_results)
    )

    saved = 0
    for raw in results:
        content_hash = hashlib.md5(raw["raw_content"].encode(errors="ignore")).hexdigest()
        existing = await db.intelligence_items.find_one({"content_hash": content_hash})
        if existing:
            continue
        item = _base_item(raw)
        try:
            analysis = await classify_and_analyze_article(raw["raw_content"][:4000], raw["title"])
            item.update(analysis)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            item["processed"] = False
        await db.intelligence_items.insert_one(item)
        saved += 1

    await db.firecrawl_searches.update_one(
        {"id": search_id},
        {"$set": {"last_run": datetime.now(timezone.utc)}}
    )
    return {"saved": saved, "query": query, "results_fetched": len(results)}


# ─────────────────────────────────────────────────────────────────────────────
# On-demand scrape any URL
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/firecrawl/scrape-url")
async def scrape_any_url(body: ScrapeUrlRequest):
    """Scrape any URL on demand and run it through the AI pipeline."""
    from firecrawl_fetcher import scrape_url_raising, _base_item
    from ai_pipeline import classify_and_analyze_article
    import hashlib

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, scrape_url_raising, body.url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    content_hash = hashlib.md5(raw["raw_content"].encode(errors="ignore")).hexdigest()
    existing = await db.intelligence_items.find_one({"content_hash": content_hash})
    if existing:
        return {"message": "Already in database", "id": existing.get("id")}

    item = _base_item(raw)
    try:
        analysis = await classify_and_analyze_article(raw["raw_content"][:4000], raw["title"])
        item.update(analysis)
    except Exception as e:
        logger.error(f"AI analysis failed for on-demand URL {body.url}: {e}")
        item["processed"] = False

    await db.intelligence_items.insert_one(item)
    item.pop("_id", None)
    return {"saved": True, "item_id": item["id"], "title": item["title"]}
