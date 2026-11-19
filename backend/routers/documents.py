"""Document upload, URL analysis, and contextual intelligence assessment."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Depends
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import io
import os
import re
import uuid
import json
import socket
import ipaddress
from urllib.parse import urlparse, urljoin
from shared import db, uploads_col, intelligence_col, patterns_col, logger
from llm_client import get_client, MODEL as ANALYSIS_MODEL
from utils.auth import get_current_user
from user_activity import log_action

router = APIRouter()


# ============================================================
# Robust JSON extraction helper
# ============================================================

def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from Claude's response text.

    Handles:
    - Markdown code fences (```json ... ```)
    - Trailing commas before } or ] (common Claude quirk)
    - Extra prose before/after the JSON block
    - Truncated responses (graceful fallback)
    """
    # 1. Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # 2. Try parsing the whole cleaned string directly
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Find the outermost {...} block
    start = cleaned.find("{")
    if start != -1:
        # Walk backwards from end to find matching closing brace
        depth = 0
        end = -1
        for i, ch in enumerate(cleaned[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            json_str = cleaned[start : end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # 4. Fix trailing commas before } or ] (common Claude formatting issue)
                fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

    # 5. Final fallback — return whatever we got as a plain summary
    logger.warning("_extract_json: could not parse JSON from LLM response")
    return {
        "executive_summary": text[:600],
        "error": "Could not parse structured response — raw text stored",
    }


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 3


def file_content_matches(file_type: str, data: bytes) -> bool:
    """Check the real bytes match the claimed type (the browser header is untrusted)."""
    if file_type == "pdf":
        return data.startswith(b"%PDF")
    if file_type in ("docx", "xlsx"):
        return data.startswith(b"PK\x03\x04")
    if file_type in ("doc", "xls"):
        return data.startswith(b"\xd0\xcf\x11\xe0") or data.startswith(b"PK\x03\x04")
    if file_type == "txt":
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return False


def _ip_is_public(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text.split("%")[0])
    except ValueError:
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified)


def is_public_http_url(url: str, resolver=socket.getaddrinfo) -> bool:
    """True only for http/https URLs whose host resolves exclusively to public IPs (SSRF guard).
    shortcut: DNS can change between this check and the fetch (rebinding); pin the IP if that matters."""
    try:
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return False
        infos = resolver(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
        addrs = [i[4][0] for i in infos]
    except Exception:
        return False
    return bool(addrs) and all(_ip_is_public(a) for a in addrs)


async def _get_public(client, url: str, headers: dict):
    """GET following up to MAX_REDIRECTS redirects, re-checking each hop is public."""
    for _ in range(MAX_REDIRECTS + 1):
        if not is_public_http_url(url):
            raise HTTPException(status_code=400, detail="That address is not allowed")
        resp = await client.get(url, headers=headers)
        if not resp.is_redirect:
            return resp
        url = urljoin(url, resp.headers.get("location", ""))
    raise ValueError("Too many redirects")


def _require_writer(user: dict) -> None:
    if user.get("role") not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Your role cannot do this")


def _can_see_doc(doc: dict, user: dict) -> bool:
    """Admins see all; others see their own IOD's docs plus old docs with no IOD."""
    if user.get("role") == "admin" or "iod" not in doc:
        return True
    return doc.get("iod") == (user.get("iod") or "IOD-1")


async def _get_visible_doc(doc_id: str, user: dict) -> dict:
    doc = await uploads_col.find_one({"id": doc_id}, {"_id": 0})
    if not doc or not _can_see_doc(doc, user):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


class URLAnalysisRequest(BaseModel):
    url: str
    analysis_query: str = ""


class TextAnalysisRequest(BaseModel):
    text: str
    analysis_query: str = ""


# ============================================================
# Fetch current security context for AI prompts
# ============================================================

async def _get_security_context() -> str:
    """Build a snapshot of the current security environment from recent intelligence."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Recent high-priority items
    recent_items = await intelligence_col.find(
        {"processed": True, "severity": {"$in": ["critical", "high"]}, "published_at": {"$gte": cutoff}},
        {"_id": 0, "title": 1, "state": 1, "severity": 1, "tags": 1, "ai_summary": 1}
    ).sort("priority_score", -1).limit(15).to_list(15)

    # Active patterns
    recent_patterns = await patterns_col.find(
        {"detected_at": {"$gte": cutoff}},
        {"_id": 0, "pattern_type": 1, "description": 1, "severity": 1, "states": 1}
    ).sort("detected_at", -1).limit(10).to_list(10)

    # Build context string
    ctx = "=== CURRENT NER SECURITY ENVIRONMENT (Last 7 Days) ===\n\n"
    ctx += "--- HIGH PRIORITY DEVELOPMENTS ---\n"
    for i, item in enumerate(recent_items, 1):
        ctx += f"{i}. [{item.get('state','')}|{item.get('severity','').upper()}] {item.get('title','')}\n"
        if item.get('ai_summary'):
            ctx += f"   Summary: {item['ai_summary'][:150]}\n"
        tags = item.get('tags', [])
        if tags:
            ctx += f"   Tags: {', '.join(tags[:5])}\n"

    ctx += "\n--- DETECTED PATTERNS ---\n"
    for p in recent_patterns:
        ctx += f"- [{p.get('severity','').upper()}] {p.get('pattern_type','')}: {p.get('description','')[:120]}\n"
        states = p.get('states', [])
        if states:
            ctx += f"  Affected: {', '.join(states)}\n"

    return ctx


CONTEXTUAL_ANALYSIS_PROMPT = """You are a SENIOR MILITARY INTELLIGENCE ANALYST at India's Northeast Regional Command.

You have been provided:
1. A document/article/report submitted for analysis
2. The CURRENT SECURITY ENVIRONMENT — a snapshot of the latest 7 days of intelligence from the region

Your task: Provide a COMPREHENSIVE CONTEXTUAL INTELLIGENCE ASSESSMENT of the submitted document.

Structure your response STRICTLY as JSON:
{
  "executive_summary": "3-4 sentence overview of what this document reports and why it matters",
  "threat_classification": {
    "severity": "CRITICAL / HIGH / MEDIUM / LOW",
    "threat_category": "One of: INSURGENCY, BORDER SECURITY, DRUG TRAFFICKING, ARMS SMUGGLING, ETHNIC CONFLICT, POLITICAL INSTABILITY, CROSS-BORDER INFILTRATION, TERRORISM, CIVIL UNREST, NATURAL DISASTER, OTHER",
    "confidence": "HIGH / MEDIUM / LOW"
  },
  "pattern_analysis": {
    "matches_existing_pattern": true/false,
    "pattern_description": "How this fits or diverges from detected patterns in the region. Be specific.",
    "escalation_indicator": "ESCALATING / STABLE / DE-ESCALATING / NEW_THREAT"
  },
  "relevance_assessment": {
    "relevance_score": 1-10,
    "primary_region": "State or country most affected",
    "secondary_regions": ["other affected areas"],
    "relevance_explanation": "How this connects to the current NER security scenario"
  },
  "key_entities": {
    "actors": ["Named groups, forces, individuals"],
    "locations": ["Specific places mentioned"],
    "events": ["Key events described"]
  },
  "recommended_actions": [
    {"priority": "IMMEDIATE/HIGH/MEDIUM/LOW", "action": "Specific actionable recommendation"},
    ...
  ],
  "intelligence_gaps": ["What information is missing that would improve assessment"],
  "cross_references": "Which of the current security developments (from the context provided) are most related to this document and how"
}

RULES:
- Be specific, not generic. Reference actual locations, actors, events.
- recommended_actions must be ACTIONABLE — not vague suggestions.
- If the document is NOT relevant to NER security, say so clearly but still provide the classification.
- Use the current security context to make connections the raw document alone would not reveal."""


# ============================================================
# Endpoints
# ============================================================

@router.get("/uploaded-documents")
async def get_uploaded_documents(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") == "admin":
        query = {}
    else:
        query = {"$or": [{"iod": current_user.get("iod") or "IOD-1"}, {"iod": {"$exists": False}}]}
    docs = await uploads_col.find(query, {"_id": 0}).sort("uploaded_at", -1).to_list(100)
    return {"documents": docs, "count": len(docs)}


@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...), background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
):
    allowed_types = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "text/plain": "txt"
    }
    _require_writer(current_user)
    content_type = file.content_type
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not supported. Allowed: PDF, Word, Excel, TXT")

    file_type = allowed_types[content_type]
    file_content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    if not file_content_matches(file_type, file_content):
        raise HTTPException(status_code=400, detail="File contents do not match its type")

    extracted_text = ""
    try:
        if file_type == "pdf":
            from PyPDF2 import PdfReader
            pdf_reader = PdfReader(io.BytesIO(file_content))
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() or ""
        elif file_type in ["docx", "doc"]:
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            extracted_text = "\n".join([p.text for p in doc.paragraphs])
        elif file_type in ["xlsx", "xls"]:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(file_content))
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    extracted_text += " | ".join([str(c) for c in row if c]) + "\n"
        elif file_type == "txt":
            extracted_text = file_content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error extracting text from {file.filename}: {e}")
        extracted_text = f"Error extracting text: {str(e)}"

    doc_record = {
        "id": str(uuid.uuid4()),
        "filename": file.filename,
        "file_type": file_type,
        "source_type": "file",
        "uploaded_by": current_user.get("username"),
        "iod": current_user.get("iod") or "IOD-1",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "extracted_text": extracted_text[:15000],
        "analysis": None,
        "processed": False,
    }
    await uploads_col.insert_one(doc_record)

    if background_tasks:
        background_tasks.add_task(_run_contextual_analysis, doc_record["id"])
        background_tasks.add_task(log_action, current_user, "manual_upload", f"file: {file.filename}")

    return {"message": "Document uploaded — analysis starting", "document_id": doc_record["id"], "filename": file.filename}


@router.post("/analyze-url")
async def analyze_url(
    data: URLAnalysisRequest, background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
):
    """Fetch a URL and run contextual intelligence analysis."""
    _require_writer(current_user)
    url = data.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    if not is_public_http_url(url):
        raise HTTPException(status_code=400, detail="That address is not allowed")

    # Scrape the URL (redirects followed by hand so every hop is re-checked)
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            resp = await _get_public(client, url, {"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else url
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")

    doc_record = {
        "id": str(uuid.uuid4()),
        "filename": title[:200] if title else url[:200],
        "file_type": "url",
        "source_type": "url",
        "source_url": url,
        "uploaded_by": current_user.get("username"),
        "iod": current_user.get("iod") or "IOD-1",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "extracted_text": text[:15000],
        "analysis_query": data.analysis_query,
        "analysis": None,
        "processed": False,
    }
    await uploads_col.insert_one(doc_record)

    if background_tasks:
        background_tasks.add_task(_run_contextual_analysis, doc_record["id"])
        background_tasks.add_task(log_action, current_user, "manual_upload", f"url: {url}")

    return {"message": "URL fetched — analysis starting", "document_id": doc_record["id"], "filename": doc_record["filename"]}


@router.get("/uploaded-documents/{doc_id}")
async def get_document_detail(doc_id: str, current_user: dict = Depends(get_current_user)):
    return await _get_visible_doc(doc_id, current_user)


@router.delete("/uploaded-documents/{doc_id}")
async def delete_uploaded_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    _require_writer(current_user)
    doc = await _get_visible_doc(doc_id, current_user)
    is_admin = current_user.get("role") == "admin"
    if not is_admin and doc.get("uploaded_by") != current_user.get("username"):
        raise HTTPException(status_code=403, detail="Only the uploader or an admin can delete this")
    result = await uploads_col.delete_one({"id": doc_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}


@router.post("/uploaded-documents/{doc_id}/reanalyze")
async def reanalyze_document(
    doc_id: str, background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Re-trigger contextual analysis for a single document (e.g. after a previous error)."""
    _require_writer(current_user)
    await _get_visible_doc(doc_id, current_user)
    # Clear previous error so the UI shows "in progress"
    await uploads_col.update_one(
        {"id": doc_id},
        {"$set": {"processed": False, "analysis": None}}
    )
    background_tasks.add_task(_run_contextual_analysis, doc_id)
    return {"message": "Re-analysis queued", "doc_id": doc_id}


@router.post("/reanalyze-errors")
async def reanalyze_all_errors(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Re-trigger analysis for all documents that previously errored (max 20)."""
    _require_writer(current_user)
    failed = await uploads_col.find(
        {"analysis.error": {"$exists": True}},
        {"_id": 0, "id": 1}
    ).sort("uploaded_at", -1).limit(20).to_list(20)

    if not failed:
        return {"message": "No failed documents found", "queued": 0}

    for doc in failed:
        doc_id = doc["id"]
        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {"processed": False, "analysis": None}}
        )
        background_tasks.add_task(_run_contextual_analysis, doc_id)

    return {"message": f"Re-analysis queued for {len(failed)} documents", "queued": len(failed)}


# ============================================================
# Add URL to Intelligence Feed
# ============================================================

class AddToFeedRequest(BaseModel):
    url: str = ""
    document_id: str = ""   # set to add an uploaded file instead of a link
    title: str = ""
    severity: str = "medium"
    priority_score: int = 50
    threat_category: str = ""
    state: str = ""
    ai_summary: str = ""
    is_cross_border: bool = False
    tags: list = []


@router.post("/add-to-feed")
async def add_url_to_feed(data: AddToFeedRequest, current_user: dict = Depends(get_current_user)):
    """Scrape a URL and add it directly to the intelligence feed with user-defined parameters."""
    _require_writer(current_user)
    if data.document_id.strip():
        return await _add_document_to_feed(data, current_user)
    url = data.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    if not is_public_http_url(url):
        raise HTTPException(status_code=400, detail="That address is not allowed")

    # Check for duplicate URL
    existing = await intelligence_col.find_one({"source_url": url}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="This URL already exists in the intelligence feed")

    # Scrape the URL for content (best-effort — still add even if scraping fails)
    raw_content = ""
    scraped_title = ""
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            resp = await _get_public(client, url, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        raw_content = soup.get_text(separator="\n", strip=True)[:5000]
        scraped_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    except Exception as e:
        logger.warning(f"URL scrape failed for {url}: {e} — adding with user-provided data")
        if not data.title.strip():
            raise HTTPException(status_code=400, detail=f"Could not fetch URL and no title provided. Error: {str(e)}")

    title = data.title.strip() or scraped_title or url[:200]
    severity = data.severity.lower() if data.severity else "medium"
    if severity not in ("critical", "high", "medium", "low"):
        severity = "medium"

    priority_score = max(0, min(100, data.priority_score))

    # Translate non-English title and content
    from shared import has_non_latin_chars, translate_to_english
    summary = data.ai_summary or title
    if has_non_latin_chars(title):
        translated_title = await translate_to_english(title)
        if translated_title and translated_title != title:
            title = translated_title
    if has_non_latin_chars(summary):
        translated_summary = await translate_to_english(summary)
        if translated_summary and translated_summary != summary:
            summary = translated_summary
    if raw_content and has_non_latin_chars(raw_content[:500]):
        translated_content = await translate_to_english(raw_content[:3000])
        if translated_content:
            raw_content = translated_content

    item = {
        "id": str(uuid.uuid4()),
        "title": title,
        "source": "Manual Upload",
        "source_url": url,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_content": raw_content,
        "severity": severity,
        "priority_score": priority_score,
        "threat_category": data.threat_category or "Unclassified",
        "state": data.state or "Unknown",
        "ai_summary": summary,
        "is_cross_border": data.is_cross_border,
        "tags": data.tags or [],
        "countries_involved": [],
        "processed": True,
        "is_relevant": True,
        "why_it_matters": summary,
        "attention_level": "Priority Monitoring" if priority_score >= 60 else "Standard Monitoring",
        "potential_impact": "",
    }

    await intelligence_col.insert_one(item)
    logger.info(f"Manual feed item added: '{title[:60]}' severity={severity} priority={priority_score}")

    return {
        "message": "Article added to intelligence feed",
        "item_id": item["id"],
        "title": title,
        "severity": severity,
        "priority_score": priority_score,
    }


def _clean_severity(value: str) -> str:
    severity = (value or "medium").lower()
    return severity if severity in ("critical", "high", "medium", "low") else "medium"


async def _add_document_to_feed(data: "AddToFeedRequest", current_user: dict) -> dict:
    """Add an uploaded file's analysis to the feed. Same role and IOD rules as the document itself."""
    doc = await _get_visible_doc(data.document_id.strip(), current_user)
    if doc.get("source_type") == "url":
        raise HTTPException(status_code=400, detail="This is a link; add it using its address")
    if not doc.get("processed") or (doc.get("analysis") or {}).get("error"):
        raise HTTPException(status_code=400, detail="Wait for a finished analysis before adding to the feed")
    if await intelligence_col.find_one({"source_document_id": doc["id"]}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=409, detail="This file already exists in the intelligence feed")

    title = data.title.strip() or doc.get("filename") or "Uploaded document"
    summary = data.ai_summary or (doc.get("analysis") or {}).get("executive_summary") or title
    severity = _clean_severity(data.severity)
    priority_score = max(0, min(100, data.priority_score))
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "title": title[:300],
        "source": "Manual Upload",
        "source_url": "",
        "source_document_id": doc["id"],
        "iod": doc.get("iod") or current_user.get("iod") or "IOD-1",
        "published_at": now,
        "fetched_at": now,
        "raw_content": (doc.get("extracted_text") or "")[:5000],
        "severity": severity,
        "priority_score": priority_score,
        "threat_category": data.threat_category or "Unclassified",
        "state": data.state or "Unknown",
        "ai_summary": summary,
        "is_cross_border": data.is_cross_border,
        "tags": data.tags or [],
        "countries_involved": [],
        "processed": True,
        "is_relevant": True,
        "why_it_matters": summary,
        "attention_level": "Priority Monitoring" if priority_score >= 60 else "Standard Monitoring",
        "potential_impact": "",
    }
    await intelligence_col.insert_one(item)
    logger.info(f"Manual feed item added from file: '{title[:60]}' severity={severity}")
    return {
        "message": "File added to intelligence feed",
        "item_id": item["id"],
        "title": item["title"],
        "severity": severity,
        "priority_score": priority_score,
    }


# ============================================================
# Contextual AI Analysis
# ============================================================

async def _run_contextual_analysis(doc_id: str):
    """Run comprehensive contextual intelligence analysis on a document."""
    doc = await uploads_col.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        return

    text = doc.get("extracted_text", "")
    if not text or len(text) < 20:
        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {"processed": True, "analysis": {"error": "No extractable text found"}}}
        )
        return

    try:
        security_context = await _get_security_context()
        extra_query = doc.get("analysis_query", "")

        # Cap document text at 4 000 chars to keep prompt size manageable and
        # reduce the chance of the LLM response being truncated at max_tokens.
        user_prompt = f"=== DOCUMENT/ARTICLE SUBMITTED FOR ANALYSIS ===\n\n{text[:4000]}\n\n"
        user_prompt += f"=== SECURITY CONTEXT ===\n{security_context}\n\n"
        if extra_query:
            user_prompt += f"=== SPECIFIC ANALYSIS REQUEST ===\n{extra_query}\n\n"
        user_prompt += "Provide your COMPREHENSIVE CONTEXTUAL INTELLIGENCE ASSESSMENT as JSON."

        client = get_client()
        response = await client.chat.completions.create(
            model=ANALYSIS_MODEL,
            max_tokens=3000,
            timeout=90.0,
            messages=[
                {"role": "system", "content": CONTEXTUAL_ANALYSIS_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        response_text = response.choices[0].message.content or ""

        # Robust JSON extraction — handles markdown fences, trailing commas,
        # and partial responses much better than a plain regex+json.loads.
        analysis = _extract_json(response_text)

        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {
                "analysis": analysis,
                "processed": True,
                "region": analysis.get("relevance_assessment", {}).get("primary_region", ""),
            }}
        )
        logger.info(
            f"Contextual analysis complete for {doc_id}: "
            f"{analysis.get('threat_classification', {}).get('severity', '?')}"
        )

    except Exception as e:
        logger.error(f"Analysis failed for {doc_id}: {e}")
        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {"processed": True, "analysis": {"error": str(e)}}}
        )
