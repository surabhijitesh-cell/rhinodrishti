"""Training pipeline: URL/file upload, AI processing, pattern aggregation."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from typing import Optional
from datetime import datetime, timezone, timedelta
import asyncio
import uuid
import os
import io
from shared import db, training_col, intelligence_col, activity_log_col, feedback_col, logger

router = APIRouter()


# ============================================================
# Add URL to training queue
# ============================================================
@router.post("/training/add-url")
async def add_training_url(body: dict):
    url = (body.get("url") or "").strip()
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="A valid URL is required")

    relevance = body.get("relevance")
    if relevance is not None:
        if not isinstance(relevance, int) or relevance < 1 or relevance > 6:
            raise HTTPException(status_code=400, detail="relevance must be integer 1-6")

    existing = await training_col.find_one({"url": url}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="This URL is already in the training queue")

    doc = {
        "id": str(uuid.uuid4()),
        "title": "",
        "source": url.split("/")[2] if len(url.split("/")) > 2 else "Unknown",
        "url": url,
        "file_path": None,
        "extracted_text": "",
        "type": "url",
        "processed": False,
        "status": "pending",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "ai_analysis": None,
        "relevance": relevance,
    }
    await training_col.insert_one(doc)

    # Log activity
    await activity_log_col.insert_one({
        "id": str(uuid.uuid4()),
        "type": "url_added",
        "item_id": doc["id"],
        "description": f"URL added: {url[:80]}",
        "relevance_tag": relevance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"message": "URL added to training queue", "id": doc["id"], "source": doc["source"], "relevance": relevance}


# ============================================================
# Upload file to training queue
# ============================================================
@router.post("/training/upload-file")
async def upload_training_file(file: UploadFile = File(...)):
    allowed = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "text/plain": "txt",
    }
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Supported: PDF, DOCX, TXT")

    file_type = allowed[file.content_type]
    content = await file.read()

    extracted = ""
    try:
        if file_type == "pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            for page in reader.pages:
                extracted += page.extract_text() or ""
        elif file_type in ("docx", "doc"):
            from docx import Document
            doc = Document(io.BytesIO(content))
            extracted = "\n".join(p.text for p in doc.paragraphs)
        elif file_type == "txt":
            extracted = content.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Text extraction failed for {file.filename}: {e}")
        extracted = f"[Extraction error: {e}]"

    doc = {
        "id": str(uuid.uuid4()),
        "title": file.filename or "Uploaded File",
        "source": f"File Upload ({file_type.upper()})",
        "url": None,
        "file_path": file.filename,
        "extracted_text": extracted[:15000],
        "type": "file",
        "processed": False,
        "status": "ready" if extracted else "pending",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "ai_analysis": None,
    }
    await training_col.insert_one(doc)

    # Log activity
    await activity_log_col.insert_one({
        "id": str(uuid.uuid4()),
        "type": "file_uploaded",
        "item_id": doc["id"],
        "description": f"File uploaded: {file.filename}",
        "relevance_tag": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "message": "File uploaded to training queue",
        "id": doc["id"],
        "filename": file.filename,
        "chars_extracted": len(extracted),
    }


# ============================================================
# Get training queue
# ============================================================
@router.get("/training/queue")
async def get_training_queue():
    items = await training_col.find({}, {"_id": 0}).sort("uploaded_at", -1).to_list(200)
    pending = sum(1 for i in items if i.get("status") == "pending")
    ready = sum(1 for i in items if i.get("status") == "ready")
    processed = sum(1 for i in items if i.get("status") == "completed")
    return {
        "items": items,
        "total": len(items),
        "pending": pending,
        "ready": ready,
        "processed": processed,
    }


# ============================================================
# Delete training item
# ============================================================
@router.delete("/training/queue/{item_id}")
async def delete_training_item(item_id: str):
    result = await training_col.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item removed from training queue"}


# ============================================================
# Train — process all pending/ready items
# ============================================================
@router.post("/training/run")
async def run_training(background_tasks: BackgroundTasks):
    pending = await training_col.count_documents({"status": {"$in": ["pending", "ready"]}})
    if pending == 0:
        raise HTTPException(status_code=400, detail="No pending items in training queue")
    background_tasks.add_task(_run_training_pipeline)
    return {"message": f"Training started for {pending} items", "pending": pending}


# ============================================================
# Training progress (polled by frontend)
# ============================================================
_training_status = {
    "running": False,
    "total": 0,
    "current": 0,
    "current_title": "",
    "completed": 0,
    "errors": 0,
}

@router.get("/training/progress")
async def get_training_progress():
    return _training_status


# ============================================================
# Training insights (aggregated profile)
# ============================================================
@router.get("/training/insights")
async def get_training_insights():
    completed = await training_col.find(
        {"status": "completed", "ai_analysis": {"$ne": None}},
        {"_id": 0}
    ).to_list(500)

    if not completed:
        return {"has_data": False, "positive_signals": {}, "priority_regions": [], "key_actors": []}

    regions = {}
    threats = {}
    actors = {}
    keywords = {}

    for item in completed:
        analysis = item.get("ai_analysis") or {}
        r = analysis.get("region", "")
        if r:
            regions[r] = regions.get(r, 0) + 1
        tc = analysis.get("threat_category", "")
        if tc:
            threats[tc] = threats.get(tc, 0) + 1
        for a in (analysis.get("actors") or []):
            actors[a] = actors.get(a, 0) + 1
        for kw in (analysis.get("keywords") or []):
            keywords[kw] = keywords.get(kw, 0) + 1

    return {
        "has_data": True,
        "items_processed": len(completed),
        "positive_signals": {
            "regions": dict(sorted(regions.items(), key=lambda x: -x[1])[:10]),
            "threat_categories": dict(sorted(threats.items(), key=lambda x: -x[1])[:10]),
            "actors": dict(sorted(actors.items(), key=lambda x: -x[1])[:10]),
            "keywords": dict(sorted(keywords.items(), key=lambda x: -x[1])[:15]),
        },
        "priority_regions": sorted(regions.items(), key=lambda x: -x[1])[:5],
        "key_actors": sorted(actors.items(), key=lambda x: -x[1])[:10],
    }


# ============================================================
# Training Activity Log
# ============================================================
@router.get("/training/activity-log")
async def get_activity_log():

    # Fetch stored activity entries (url adds, file uploads, training runs)
    entries = await activity_log_col.find({}, {"_id": 0}).sort("timestamp", -1).to_list(100)

    # Aggregate feedback summary
    total_feedback = await feedback_col.count_documents({})
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recent_feedback = await feedback_col.count_documents({"timestamp": {"$gte": week_ago}})

    # Training data stats
    total_trained = await training_col.count_documents({"status": "completed"})
    total_errors = await training_col.count_documents({"status": "completed", "ai_analysis.error": {"$exists": True}})
    total_with_relevance = await training_col.count_documents({"relevance": {"$ne": None}})

    # Compute AI impact from completed training items
    completed = await training_col.find(
        {"status": "completed", "ai_analysis": {"$ne": None}, "ai_analysis.error": {"$exists": False}},
        {"_id": 0, "ai_analysis": 1, "relevance": 1}
    ).to_list(500)

    regions_learned = {}
    actors_learned = {}
    keywords_learned = {}
    for item in completed:
        analysis = item.get("ai_analysis") or {}
        r = analysis.get("region", "")
        if r:
            regions_learned[r] = regions_learned.get(r, 0) + 1
        for a in (analysis.get("actors") or []):
            actors_learned[a] = actors_learned.get(a, 0) + 1
        for kw in (analysis.get("keywords") or []):
            keywords_learned[kw] = keywords_learned.get(kw, 0) + 1

    return {
        "entries": entries,
        "summary": {
            "total_feedback_ratings": total_feedback,
            "recent_feedback_7d": recent_feedback,
            "total_items_trained": total_trained,
            "training_errors": total_errors,
            "items_with_relevance_tag": total_with_relevance,
        },
        "ai_impact": {
            "regions_learned": dict(sorted(regions_learned.items(), key=lambda x: -x[1])[:8]),
            "actors_learned": dict(sorted(actors_learned.items(), key=lambda x: -x[1])[:8]),
            "keywords_learned": dict(sorted(keywords_learned.items(), key=lambda x: -x[1])[:10]),
            "total_successful": len(completed),
        },
    }


# ============================================================
# Training Effectiveness Score
# ============================================================
SEVERITY_MAP = {"critical": 6.0, "high": 5.0, "medium": 3.5, "low": 2.0}


async def _compute_effectiveness():
    """Compute alignment between AI classifications and analyst feedback ratings.
    Returns score 0-100 and per-item breakdown."""
    rated_items = await intelligence_col.find(
        {"feedback_avg_rating": {"$exists": True, "$gt": 0}, "feedback_total_ratings": {"$gte": 1}},
        {"_id": 0, "id": 1, "severity": 1, "priority_score": 1,
         "feedback_avg_rating": 1, "feedback_total_ratings": 1, "title": 1}
    ).to_list(1000)

    if not rated_items:
        return {"score": None, "sample_size": 0, "alignments": [], "grade": "INSUFFICIENT_DATA"}

    alignments = []
    for item in rated_items:
        sev = (item.get("severity") or "").lower()
        ai_score = SEVERITY_MAP.get(sev, 3.0)
        analyst_avg = item["feedback_avg_rating"]
        # Alignment: 1 means perfect match, 0 means max disagreement
        alignment = max(0, 1.0 - abs(ai_score - analyst_avg) / 5.0)
        alignments.append({
            "id": item["id"],
            "title": (item.get("title") or "")[:60],
            "ai_severity": sev or "unknown",
            "ai_mapped": ai_score,
            "analyst_avg": round(analyst_avg, 2),
            "ratings_count": item.get("feedback_total_ratings", 0),
            "alignment": round(alignment, 3),
        })

    avg_alignment = sum(a["alignment"] for a in alignments) / len(alignments)
    score = round(avg_alignment * 100, 1)

    if score >= 80:
        grade = "EXCELLENT"
    elif score >= 65:
        grade = "GOOD"
    elif score >= 50:
        grade = "MODERATE"
    elif score >= 35:
        grade = "NEEDS_IMPROVEMENT"
    else:
        grade = "POOR"

    # Sort: worst alignments first so analysts see what needs attention
    alignments.sort(key=lambda a: a["alignment"])

    return {
        "score": score,
        "sample_size": len(alignments),
        "grade": grade,
        "worst_misalignments": alignments[:5],
        "best_alignments": alignments[-5:][::-1],
    }


@router.get("/training/effectiveness")
async def get_effectiveness_score():
    current = await _compute_effectiveness()

    # Fetch historical snapshots for trend
    snapshots = await activity_log_col.find(
        {"type": "effectiveness_snapshot"},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(20)

    trend = [{"score": s["score"], "sample_size": s["sample_size"], "timestamp": s["timestamp"]} for s in snapshots]

    # Compute delta from last snapshot
    delta = None
    if trend and current["score"] is not None and trend[0].get("score") is not None:
        delta = round(current["score"] - trend[0]["score"], 1)

    return {
        **current,
        "trend": trend[:10],
        "delta_from_last": delta,
    }


# ============================================================
# Background pipeline
# ============================================================
async def _run_training_pipeline():
    global _training_status

    items = await training_col.find(
        {"status": {"$in": ["pending", "ready"]}}, {"_id": 0}
    ).to_list(200)

    _training_status["running"] = True
    _training_status["total"] = len(items)
    _training_status["current"] = 0
    _training_status["completed"] = 0
    _training_status["errors"] = 0
    _training_status["current_title"] = ""

    EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

    for idx, item in enumerate(items):
        _training_status["current"] = idx + 1
        _training_status["current_title"] = (item.get("title") or item.get("url") or "Unknown")[:60]

        try:
            await training_col.update_one({"id": item["id"]}, {"$set": {"status": "processing"}})

            # Step 1: Content extraction
            text = item.get("extracted_text", "")
            if not text and item.get("url"):
                text = await _scrape_url(item["url"])
                title = text[:80].split("\n")[0] if text else item.get("url", "")
                await training_col.update_one(
                    {"id": item["id"]},
                    {"$set": {"extracted_text": text[:15000], "title": title}}
                )

            if not text:
                await training_col.update_one(
                    {"id": item["id"]},
                    {"$set": {"status": "completed", "ai_analysis": {"error": "No text extracted"}}}
                )
                _training_status["errors"] += 1
                continue

            # Step 2: AI analysis
            analysis = await _analyze_training_item(text, EMERGENT_KEY)

            # Update title if we got one from AI
            updates = {
                "status": "completed",
                "processed": True,
                "ai_analysis": analysis,
            }
            if analysis.get("title") and not item.get("title"):
                updates["title"] = analysis["title"]

            await training_col.update_one({"id": item["id"]}, {"$set": updates})
            _training_status["completed"] += 1

        except Exception as e:
            logger.error(f"Training pipeline error for {item.get('id')}: {e}")
            await training_col.update_one(
                {"id": item["id"]},
                {"$set": {"status": "completed", "ai_analysis": {"error": str(e)}}}
            )
            _training_status["errors"] += 1

        await asyncio.sleep(2)

    _training_status["running"] = False
    _training_status["current_title"] = ""
    logger.info(f"Training complete: {_training_status['completed']} processed, {_training_status['errors']} errors")

    # Log activity for this training run
    try:
        # Gather impact summary from items just processed
        run_regions = {}
        run_actors = {}
        for item in items:
            refreshed = await training_col.find_one({"id": item["id"]}, {"_id": 0, "ai_analysis": 1})
            if refreshed and refreshed.get("ai_analysis"):
                analysis = refreshed["ai_analysis"]
                r = analysis.get("region", "")
                if r:
                    run_regions[r] = run_regions.get(r, 0) + 1
                for a in (analysis.get("actors") or []):
                    run_actors[a] = run_actors.get(a, 0) + 1

        await activity_log_col.insert_one({
            "id": str(uuid.uuid4()),
            "type": "training_run",
            "description": f"Training run completed: {_training_status['completed']} processed, {_training_status['errors']} errors",
            "items_processed": _training_status["completed"],
            "errors": _training_status["errors"],
            "total": len(items),
            "regions_found": dict(sorted(run_regions.items(), key=lambda x: -x[1])[:5]),
            "actors_found": dict(sorted(run_actors.items(), key=lambda x: -x[1])[:5]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Store effectiveness snapshot for trend tracking
        eff = await _compute_effectiveness()
        if eff["score"] is not None:
            await activity_log_col.insert_one({
                "id": str(uuid.uuid4()),
                "type": "effectiveness_snapshot",
                "score": eff["score"],
                "grade": eff["grade"],
                "sample_size": eff["sample_size"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.error(f"Failed to log training activity: {e}")


async def _scrape_url(url: str) -> str:
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text[:15000]
    except Exception as e:
        logger.error(f"URL scrape failed for {url}: {e}")
        return ""


async def _analyze_training_item(text: str, emergent_key: str) -> dict:
    import json
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        prompt = """You are a military intelligence analyst. Analyze this content and extract:
1. A short headline/title (max 80 chars)
2. Primary region affected (Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar, National, International)
3. Threat category (Insurgency, Cross-border, Military Movement, Arms/Drug Trafficking, Ethnic Tension, Political, Infrastructure, Border Security, Foreign Influence, Other)
4. Key actors/organizations mentioned
5. Important keywords for intelligence monitoring
6. Why this is relevant to NER security

Respond ONLY in JSON:
{"title":"...","region":"...","threat_category":"...","actors":["..."],"keywords":["..."],"relevance":"..."}"""

        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"train-{uuid.uuid4()}",
            system_message=prompt
        ).with_model("anthropic", "claude-haiku-4-5-20251001")

        response = await chat.send_message(UserMessage(text=f"Analyze:\n\n{text[:4000]}"))
        resp_text = str(response)

        start = resp_text.find("{")
        end = resp_text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(resp_text[start:end])
        return {"title": text[:60], "relevance": resp_text[:300]}

    except Exception as e:
        logger.error(f"AI training analysis failed: {e}")
        return {"error": str(e), "title": text[:60]}
