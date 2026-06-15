"""Daily Brief generation, PDF export, custom briefs, weekly trends."""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone, timedelta
import io
import os
import uuid
from shared import (
    db, intelligence_col, briefs_col, uploads_col, patterns_col,
    DailyBrief, logger, NER_STATES,
    has_non_latin_chars, translate_to_english,
)

router = APIRouter()


# ============================================================
# Faultline tag enrichment (PAOI overlay for Daily Brief)
# ============================================================
async def attach_faultline_tags(items: list[dict]) -> None:
    """
    Enrich brief news items in-place with `faultline_tags`:
      [{id, name, score, is_priority}]
    Each tag = a faultline this article was mapped to (via faultline_mappings),
    with is_priority=True if that faultline belongs to any PAOI.

    is_priority drives the RED chip in the Daily Brief UI. Best (highest-impact)
    faultline per article is listed first. Only confident mappings count
    (confidence >= 45, matching the scoring significance gate).

    Cheap: one mappings query + one faultlines lookup for the whole batch.
    No-op if the faultline collections aren't seeded yet (graceful).
    """
    article_ids = [it.get("id") for it in items if it.get("id")]
    if not article_ids:
        return

    try:
        # All confident mappings for these articles (any date)
        cursor = db.faultline_mappings.find(
            {"article_id": {"$in": article_ids}, "confidence": {"$gte": 45}},
            {"_id": 0, "article_id": 1, "faultline_id": 1, "impact_score": 1},
        )
        mappings = [m async for m in cursor]
        if not mappings:
            return

        # Faultline id -> {name, is_priority}
        fl_ids = list({m["faultline_id"] for m in mappings})
        fl_docs = await db.faultlines.find(
            {"id": {"$in": fl_ids}},
            {"_id": 0, "id": 1, "name": 1, "priority_area_ids": 1},
        ).to_list(length=500)
        fl_meta = {
            d["id"]: {
                "name": d.get("name", d["id"]),
                "is_priority": bool(d.get("priority_area_ids")),
            }
            for d in fl_docs
        }

        # Build per-article tag lists (dedup faultline, keep best impact)
        by_article: dict[str, dict[str, dict]] = {}
        for m in mappings:
            aid = m["article_id"]
            fid = m["faultline_id"]
            meta = fl_meta.get(fid)
            if not meta:
                continue
            slot = by_article.setdefault(aid, {})
            existing = slot.get(fid)
            impact = m.get("impact_score", 0)
            if existing is None or impact > existing["score"]:
                slot[fid] = {
                    "id": fid,
                    "name": meta["name"],
                    "score": impact,
                    "is_priority": meta["is_priority"],
                }

        for it in items:
            aid = it.get("id")
            tags = list(by_article.get(aid, {}).values())
            # Priority tags first, then by impact desc
            tags.sort(key=lambda t: (not t["is_priority"], -t["score"]))
            if tags:
                it["faultline_tags"] = tags
    except Exception as e:
        logger.warning(f"attach_faultline_tags failed (non-fatal): {e}")


# ============================================================
# Brief Endpoints
# ============================================================

@router.get("/daily-brief")
async def get_daily_brief(date: Optional[str] = None):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief = await briefs_col.find_one({"date": date}, {"_id": 0})
    if not brief:
        brief = await generate_brief_for_date(date)
    return brief


@router.post("/generate-brief")
async def generate_brief(background_tasks: BackgroundTasks):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    background_tasks.add_task(generate_brief_for_date, date)
    return {"message": "Brief generation started", "date": date}


@router.get("/daily-brief/pdf")
async def get_daily_brief_pdf(date: Optional[str] = None):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief = await briefs_col.find_one({"date": date}, {"_id": 0})
    if not brief:
        brief = await generate_brief_for_date(date)

    # NOTE: translation removed — translate_brief_for_pdf made N sequential
    # external API calls (one per non-Latin field) causing 40-60s response times
    # that exceeded Render's load-balancer timeout → connection drop → "Network Error".
    # clean_for_pdf() already handles non-Latin chars with a safe fallback string.

    total = await intelligence_col.count_documents({})
    critical = await intelligence_col.count_documents({"severity": "critical"})
    high = await intelligence_col.count_documents({"severity": "high"})

    today_start = f"{date}T00:00:00"
    today_end = f"{date}T23:59:59"
    fresh_uploads = await uploads_col.find(
        {"processed": True, "uploaded_at": {"$gte": today_start, "$lte": today_end}},
        {"_id": 0}
    ).sort("uploaded_at", -1).to_list(20)

    try:
        pdf_bytes = generate_brief_pdf(brief, date, total, critical, high, fresh_uploads)
    except Exception as e:
        logger.error(f"PDF generation failed for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Rhino_Drishti_Brief_{date}.pdf"}
    )


@router.post("/intelligence/custom-brief")
async def generate_custom_brief(body: dict):
    region = body.get("region")
    threat_type = body.get("threat_type")
    severity = body.get("severity")
    hours = body.get("hours", 48)
    search = body.get("search")
    title_override = body.get("title", "Custom Intelligence Brief")

    query = {"processed": True}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query["published_at"] = {"$gte": cutoff}

    if region:
        query["state"] = region
    if threat_type:
        query["threat_category"] = threat_type
    if severity:
        query["severity"] = severity
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"ai_summary": {"$regex": search, "$options": "i"}}
        ]

    items = await intelligence_col.find(query, {"_id": 0}).sort(
        [("priority_score", -1), ("published_at", -1)]
    ).limit(50).to_list(50)

    if not items:
        raise HTTPException(status_code=404, detail="No items match the given filters")

    pdf_bytes = _generate_custom_pdf(items, title_override, region, threat_type, hours)

    filename = f"custom_brief_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/weekly-trends")
async def get_weekly_trends():
    daily_severity = {}
    async for doc in intelligence_col.aggregate([
        {"$group": {
            "_id": {"date": {"$substr": ["$published_at", 0, 10]}, "severity": "$severity"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.date": 1}}
    ]):
        date = doc["_id"]["date"]
        sev = doc["_id"]["severity"]
        if date not in daily_severity:
            daily_severity[date] = {"date": date, "critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
        daily_severity[date][sev] = doc["count"]
        daily_severity[date]["total"] += doc["count"]

    category_stats = []
    async for doc in intelligence_col.aggregate([
        {"$group": {
            "_id": "$threat_category", "count": {"$sum": 1},
            "critical": {"$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}},
            "high": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}}
        }},
        {"$sort": {"count": -1}}
    ]):
        if doc["_id"]:
            category_stats.append({"category": doc["_id"], "count": doc["count"], "critical": doc["critical"], "high": doc["high"]})

    state_stats = []
    async for doc in intelligence_col.aggregate([
        {"$group": {
            "_id": "$state", "count": {"$sum": 1},
            "critical": {"$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}},
            "high": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}}
        }},
        {"$sort": {"count": -1}}
    ]):
        if doc["_id"]:
            state_stats.append({"state": doc["_id"], "count": doc["count"], "critical": doc["critical"], "high": doc["high"]})

    return {
        "daily_severity": sorted(daily_severity.values(), key=lambda x: x["date"])[-14:],
        "category_stats": category_stats,
        "state_stats": state_stats
    }


# ============================================================
# Translation Helpers
# ============================================================

async def translate_brief_for_pdf(brief: dict) -> dict:
    translated = dict(brief)

    if translated.get("key_developments"):
        new_devs = []
        for dev in translated["key_developments"]:
            if isinstance(dev, dict):
                if has_non_latin_chars(dev.get("title", "")):
                    dev["title"] = await translate_to_english(dev["title"])
                if has_non_latin_chars(dev.get("summary", "")):
                    dev["summary"] = await translate_to_english(dev["summary"])
                new_devs.append(dev)
            elif isinstance(dev, str) and has_non_latin_chars(dev):
                new_devs.append(await translate_to_english(dev))
            else:
                new_devs.append(dev)
        translated["key_developments"] = new_devs

    if translated.get("national_news"):
        for news in translated["national_news"]:
            if isinstance(news, dict):
                if has_non_latin_chars(news.get("title", "")):
                    news["title"] = await translate_to_english(news["title"])
                if has_non_latin_chars(news.get("summary", "")):
                    news["summary"] = await translate_to_english(news["summary"])

    if translated.get("international_news"):
        for news in translated["international_news"]:
            if isinstance(news, dict):
                if has_non_latin_chars(news.get("title", "")):
                    news["title"] = await translate_to_english(news["title"])
                if has_non_latin_chars(news.get("summary", "")):
                    news["summary"] = await translate_to_english(news["summary"])

    if translated.get("state_highlights"):
        for state_name, highlight in translated["state_highlights"].items():
            if has_non_latin_chars(highlight):
                translated["state_highlights"][state_name] = await translate_to_english(highlight)

    if has_non_latin_chars(translated.get("analyst_summary", "")):
        translated["analyst_summary"] = await translate_to_english(translated["analyst_summary"])
    if has_non_latin_chars(translated.get("cross_border_insights", "")):
        translated["cross_border_insights"] = await translate_to_english(translated["cross_border_insights"])

    return translated


def clean_for_pdf(text: str) -> str:
    if not text:
        return ""
    replacements = {
        '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
        '\u2013': '-', '\u2014': '-', '\u2026': '...', '\u2022': '*',
        '\u200b': '', '\u200c': '', '\u200d': '',
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)

    if has_non_latin_chars(text):
        return "[Content requires translation - see original source]"

    return text.encode('latin-1', 'replace').decode('latin-1')


# ============================================================
# Custom PDF Generator
# ============================================================

def _generate_custom_pdf(items: list, title: str, region: str, threat: str, hours: int) -> bytes:
    from fpdf import FPDF
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(timezone.utc).astimezone(ist)

    class CustomPDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(200, 30, 30)
            self.cell(0, 4, 'RESTRICTED', align='C', new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 7)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Page {self.page_no()} | RESTRICTED | Rhino Drishti Elite', align='C')

    pdf = CustomPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(34, 50, 30)
    clean_title = title.encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 10, clean_title, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(80, 80, 80)
    filter_desc = f"Generated: {now_ist.strftime('%d %b %Y %H:%M IST')} | Window: Last {hours}h"
    if region:
        filter_desc += f" | Region: {region}"
    if threat:
        filter_desc += f" | Threat: {threat}"
    pdf.cell(0, 5, filter_desc, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Total Items: {len(items)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    effective_w = pdf.w - pdf.l_margin - pdf.r_margin
    for i, item in enumerate(items, 1):
        sev = item.get('severity', 'low').upper()
        priority = item.get('priority_score', 0)
        trajectory = item.get('threat_trajectory', '')

        if sev == 'CRITICAL':
            pdf.set_text_color(200, 30, 30)
        elif sev == 'HIGH':
            pdf.set_text_color(200, 100, 30)
        elif sev == 'MEDIUM':
            pdf.set_text_color(180, 160, 30)
        else:
            pdf.set_text_color(40, 120, 40)

        pdf.set_font('Helvetica', 'B', 10)
        item_title = item.get('title', 'Untitled')[:90]
        clean_item_title = item_title.encode('latin-1', 'replace').decode('latin-1')
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_w, 6, f'{i}. [{sev}|P{priority}] {clean_item_title}')

        pdf.set_text_color(60, 60, 60)
        pdf.set_font('Helvetica', '', 8)
        meta = f"Source: {item.get('source', '')[:40]} | {item.get('state', '')} | {item.get('published_at', '')[:16]}"
        if trajectory and trajectory != 'INDETERMINATE':
            meta += f" | {trajectory}"
        clean_meta = meta.encode('latin-1', 'replace').decode('latin-1')
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_w, 4, clean_meta, new_x="LMARGIN", new_y="NEXT")

        summary = item.get('ai_summary', '')[:400]
        if summary:
            clean_summary = summary.encode('latin-1', 'replace').decode('latin-1')
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(effective_w, 4, clean_summary)

        why = item.get('why_it_matters', '')[:200]
        if why:
            pdf.set_font('Helvetica', 'I', 8)
            pdf.set_text_color(100, 80, 40)
            clean_why = why.encode('latin-1', 'replace').decode('latin-1')
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(effective_w, 4, f"Why: {clean_why}")

        pdf.ln(3)

    return pdf.output()


# ============================================================
# Daily Brief PDF Generator
# ============================================================

def generate_brief_pdf(brief: dict, date: str, total: int, critical: int, high: int, fresh_uploads: list = None) -> bytes:
    from fpdf import FPDF

    class BriefPDF(FPDF):
        def header(self):
            self.set_fill_color(30, 35, 25)
            self.rect(0, 0, 210, 30, 'F')
            self.set_font('Helvetica', 'B', 18)
            self.set_text_color(180, 220, 80)
            self.set_y(5)
            self.cell(0, 8, 'RHINO DRISHTI', align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_font('Helvetica', '', 8)
            self.set_text_color(160, 170, 150)
            self.cell(0, 4, 'NER INTELLIGENCE PLATFORM  |  DAILY INTELLIGENCE BRIEF', align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_font('Helvetica', '', 7)
            self.cell(0, 4, f'Classification: RESTRICTED  |  Date: {date}', align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_y(34)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 7)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, f'Rhino Drishti - Auto-generated Intelligence Brief | Page {self.page_no()}/{{nb}} | RESTRICTED', align='C')

        def section_title(self, title):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(50, 60, 40)
            self.set_fill_color(230, 240, 220)
            self.cell(0, 8, f'  {title}', fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

        def body_text(self, text):
            self.set_font('Helvetica', '', 9)
            self.set_text_color(40, 40, 40)
            clean_text = text.encode('latin-1', 'replace').decode('latin-1')
            self.multi_cell(0, 5, clean_text)
            self.ln(2)

        def news_item_with_link(self, index, title, summary, source_url, timestamp=""):
            if self.get_y() > 260:
                self.add_page()

            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(40, 60, 80)
            clean_title = title.encode('latin-1', 'replace').decode('latin-1')[:150]
            self.multi_cell(0, 5, f'{index}. {clean_title}', new_x="LMARGIN", new_y="NEXT")

            if summary:
                self.set_font('Helvetica', '', 8)
                self.set_text_color(60, 60, 60)
                clean_summary = summary.encode('latin-1', 'replace').decode('latin-1')[:400]
                if clean_summary:
                    self.multi_cell(0, 4, clean_summary, new_x="LMARGIN", new_y="NEXT")

            if source_url and len(source_url) > 5:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(70, 100, 150)
                url_display = source_url[:70] + '...' if len(source_url) > 70 else source_url
                self.cell(0, 4, f'[Source: {url_display}]', new_x="LMARGIN", new_y="NEXT", link=source_url)

            if timestamp:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(120, 120, 120)
                self.cell(0, 4, f'Time: {timestamp[:19]}', new_x="LMARGIN", new_y="NEXT")

            self.ln(2)

        def news_item_comprehensive(self, index, item):
            if self.get_y() > 240:
                self.add_page()

            title = item.get('title', '')
            summary = item.get('summary', '')
            source_url = item.get('source_url', '')
            severity = item.get('severity', '')
            state = item.get('state', '')
            priority = item.get('priority_score', 0)

            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(40, 60, 80)
            sev_label = f' [{severity.upper()}]' if severity in ('critical', 'high') else ''
            clean_title = f'{index}. {title}{sev_label}'.encode('latin-1', 'replace').decode('latin-1')[:180]
            self.multi_cell(0, 5, clean_title, new_x="LMARGIN", new_y="NEXT")

            # Faultline tags from previous 24h cycle assessment
            fl_tags = item.get('faultline_tags', [])
            if fl_tags:
                paoi_tags  = [t for t in fl_tags if t.get('is_priority')]
                other_tags = [t for t in fl_tags if not t.get('is_priority')]
                if paoi_tags:
                    self.set_font('Helvetica', 'B', 7)
                    self.set_text_color(160, 40, 40)
                    tag_str = '[PAOI] ' + ' | '.join(t['name'][:28] for t in paoi_tags[:3])
                    self.cell(0, 4, tag_str.encode('latin-1', 'replace').decode('latin-1'), new_x="LMARGIN", new_y="NEXT")
                if other_tags:
                    self.set_font('Helvetica', '', 7)
                    self.set_text_color(90, 90, 130)
                    tag_str = 'Faultlines: ' + ' | '.join(t['name'][:28] for t in other_tags[:3])
                    self.cell(0, 4, tag_str.encode('latin-1', 'replace').decode('latin-1'), new_x="LMARGIN", new_y="NEXT")

            cluster_size = item.get('cluster_size', 0)
            if cluster_size and cluster_size > 1:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(110, 110, 110)
                self.cell(0, 3.5, f'  Reported by {cluster_size} sources', new_x="LMARGIN", new_y="NEXT")

            if summary:
                self.set_font('Helvetica', '', 8)
                self.set_text_color(60, 60, 60)
                self.multi_cell(0, 4, summary.encode('latin-1', 'replace').decode('latin-1')[:500], new_x="LMARGIN", new_y="NEXT")

            why = item.get('why_it_matters', '')
            if why:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(50, 120, 50)
                self.cell(30, 4, 'Why it matters: ', new_x="END")
                self.set_font('Helvetica', '', 7)
                self.set_text_color(80, 80, 80)
                self.multi_cell(0, 4, why.encode('latin-1', 'replace').decode('latin-1')[:300], new_x="LMARGIN", new_y="NEXT")

            impact = item.get('potential_impact', '')
            if impact:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(180, 120, 30)
                self.cell(30, 4, 'Potential impact: ', new_x="END")
                self.set_font('Helvetica', '', 7)
                self.set_text_color(80, 80, 80)
                self.multi_cell(0, 4, impact.encode('latin-1', 'replace').decode('latin-1')[:300], new_x="LMARGIN", new_y="NEXT")

            warning = item.get('early_warning', '')
            if warning:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(200, 50, 50)
                self.cell(30, 4, 'EARLY WARNING: ', new_x="END")
                self.set_font('Helvetica', '', 7)
                self.set_text_color(150, 50, 50)
                self.multi_cell(0, 4, warning.encode('latin-1', 'replace').decode('latin-1')[:300], new_x="LMARGIN", new_y="NEXT")

            flags = item.get('special_flags', [])
            if flags and isinstance(flags, list) and len(flags) > 0:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(140, 100, 40)
                flags_text = 'Flags: ' + ' | '.join(str(f) for f in flags[:5])
                self.cell(0, 4, flags_text.encode('latin-1', 'replace').decode('latin-1')[:150], new_x="LMARGIN", new_y="NEXT")

            actors = item.get('actors', '')
            if actors:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(100, 100, 120)
                self.cell(0, 4, f'Actors: {str(actors)[:120]}'.encode('latin-1', 'replace').decode('latin-1'), new_x="LMARGIN", new_y="NEXT")

            analyst_note = item.get('analyst_note', '')
            if analyst_note:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(100, 50, 160)
                self.cell(0, 4, 'ANALYST NOTE:', new_x="LMARGIN", new_y="NEXT")
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(70, 40, 120)
                note_clean = analyst_note[:400].encode('latin-1', 'replace').decode('latin-1')
                self.multi_cell(0, 4, note_clean, new_x="LMARGIN", new_y="NEXT")

            meta_parts = []
            if state: meta_parts.append(f'Region: {state}')
            if priority: meta_parts.append(f'Priority: {priority}')
            if source_url:
                url_display = source_url[:60] + '...' if len(source_url) > 60 else source_url
                meta_parts.append(f'Source: {url_display}')

            if meta_parts:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(100, 100, 100)
                meta_text = ' | '.join(meta_parts)
                if source_url:
                    self.cell(0, 4, meta_text.encode('latin-1', 'replace').decode('latin-1')[:180], new_x="LMARGIN", new_y="NEXT", link=source_url)
                else:
                    self.cell(0, 4, meta_text.encode('latin-1', 'replace').decode('latin-1')[:180], new_x="LMARGIN", new_y="NEXT")

            self.ln(3)

    pdf = BriefPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.set_fill_color(245, 245, 240)
    pdf.set_draw_color(180, 190, 170)
    pdf.rect(10, pdf.get_y(), 190, 18, 'FD')
    y_start = pdf.get_y() + 3
    pdf.set_xy(15, y_start)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(60, 5, f'Total Intelligence Items: {total}')
    pdf.cell(60, 5, f'Critical Alerts: {critical}')
    pdf.cell(60, 5, f'High Priority: {high}')
    pdf.set_xy(15, y_start + 7)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, 'Covering: Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura')
    pdf.ln(15)

    # NER REGIONAL SECTION
    pdf.section_title('NORTHEAST REGION - KEY DEVELOPMENTS')

    NER_STATES_PDF = ["Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura", "Nagaland", "Sikkim", "Multiple"]
    developments = brief.get('key_developments', [])
    ner_developments = []
    for dev in developments:
        if isinstance(dev, dict):
            state = dev.get('state', '')
            if state in NER_STATES_PDF:
                ner_developments.append(dev)
        else:
            ner_developments.append(dev)

    if ner_developments:
        for i, dev in enumerate(ner_developments, 1):
            if isinstance(dev, dict):
                pdf.news_item_comprehensive(i, dev)
            else:
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(40, 40, 40)
                clean_dev = str(dev).encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 5, f'{i:02d}. {clean_dev}')
                pdf.ln(1)
    else:
        pdf.body_text('No key developments recorded for this period.')
    pdf.ln(2)

    # CROSS-BORDER INTELLIGENCE
    bd_items = brief.get('cross_border_bangladesh', [])
    mm_items = brief.get('cross_border_myanmar', [])
    if bd_items or mm_items:
        pdf.section_title("CROSS-BORDER INTELLIGENCE")
        pdf.ln(1)

        def _render_cb_section(country_name, items_list):
            if not items_list:
                return
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(30, 60, 40)
            pdf.cell(0, 6, country_name, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            by_cat = {}
            for item in items_list:
                cat = item.get('category', 'Other')
                by_cat.setdefault(cat, []).append(item)
            for cat_name, cat_items in by_cat.items():
                pdf.set_font('Helvetica', 'I', 9)
                pdf.set_text_color(80, 80, 80)
                cat_clean = cat_name.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(0, 5, f"  {cat_clean}", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(0.5)
                for idx, item in enumerate(cat_items, 1):
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    severity = (item.get('severity', '') or '').upper()
                    sev_marker = f"[{severity}] " if severity and severity != "MEDIUM" else ""
                    raw_title = item.get('title', '')
                    title_text = f"  {idx}. {sev_marker}{raw_title}"
                    title_clean = title_text.encode('latin-1', 'replace').decode('latin-1')[:150]
                    pdf.set_font('Helvetica', 'B', 9)
                    pdf.set_text_color(40, 60, 80)
                    pdf.multi_cell(0, 4.5, title_clean, new_x="LMARGIN", new_y="NEXT")
                    # Faultline tags from previous 24h cycle
                    fl_tags = item.get('faultline_tags', [])
                    if fl_tags:
                        paoi_fl  = [t for t in fl_tags if t.get('is_priority')]
                        other_fl = [t for t in fl_tags if not t.get('is_priority')]
                        if paoi_fl:
                            pdf.set_font('Helvetica', 'B', 7)
                            pdf.set_text_color(160, 40, 40)
                            tag_str = '     [PAOI] ' + ' | '.join(t['name'][:28] for t in paoi_fl[:3])
                            pdf.cell(0, 3.5, tag_str.encode('latin-1', 'replace').decode('latin-1'), new_x="LMARGIN", new_y="NEXT")
                        if other_fl:
                            pdf.set_font('Helvetica', '', 7)
                            pdf.set_text_color(90, 90, 130)
                            tag_str = '     Faultlines: ' + ' | '.join(t['name'][:28] for t in other_fl[:3])
                            pdf.cell(0, 3.5, tag_str.encode('latin-1', 'replace').decode('latin-1'), new_x="LMARGIN", new_y="NEXT")
                    summary = item.get('summary', '')
                    if summary:
                        pdf.set_font('Helvetica', '', 8)
                        pdf.set_text_color(40, 40, 40)
                        s_clean = summary[:300].encode('latin-1', 'replace').decode('latin-1')
                        pdf.multi_cell(0, 4, f"     {s_clean}", new_x="LMARGIN", new_y="NEXT")
                    source = item.get('source', '')
                    if source:
                        pdf.set_font('Helvetica', 'I', 7)
                        pdf.set_text_color(100, 100, 100)
                        source_clean = str(source)[:80].encode('latin-1', 'replace').decode('latin-1')
                        pdf.cell(0, 3.5, f"     Source: {source_clean}", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(1)
            pdf.ln(1)

        _render_cb_section("BANGLADESH", bd_items)
        _render_cb_section("MYANMAR", mm_items)
        pdf.ln(2)

    # UPLOADED DOCUMENT INSIGHTS
    ner_keywords = ['assam', 'meghalaya', 'mizoram', 'manipur', 'arunachal', 'tripura', 'nagaland',
                    'northeast', 'ner', 'nscn', 'ulfa', 'pla', 'rpf', 'myanmar', 'border',
                    'insurgency', 'militant', 'security force', 'army', 'bsf', 'crpf', 'assam rifles']
    same_date_docs = []
    for doc in (fresh_uploads or []):
        analysis_text = (str(doc.get('ai_analysis', '')) + str(doc.get('extracted_text', '')) + str(doc.get('filename', ''))).lower()
        if any(kw in analysis_text for kw in ner_keywords):
            same_date_docs.append(doc)

    if same_date_docs:
        pdf.section_title('UPLOADED DOCUMENT INSIGHTS')
        for i, doc in enumerate(same_date_docs[:10], 1):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(80, 60, 40)
            filename = str(doc.get('filename', 'Unknown Document')).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 5, f'{i}. {filename}', new_x="LMARGIN", new_y="NEXT")

            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(60, 60, 60)
            analysis = doc.get('ai_analysis', doc.get('content_summary', ''))[:500]
            clean_analysis = analysis.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 4, clean_analysis)
            pdf.ln(2)

    # PATTERN INSIGHTS
    pattern_insights = brief.get('pattern_insights', [])
    if pattern_insights:
        pdf.section_title('PATTERN DETECTION - ESCALATION WARNINGS')
        for i, p in enumerate(pattern_insights[:10], 1):
            risk = p.get('escalation_risk', 'LOW')
            region = p.get('region', 'Unknown')
            detail = p.get('detail', p.get('pattern_type', ''))
            events = p.get('event_count', 0)
            avg_pri = p.get('avg_priority_score', 0)
            window = p.get('window_days', 7)

            if risk == 'CRITICAL':
                pdf.set_text_color(200, 30, 30)
            elif risk == 'HIGH':
                pdf.set_text_color(200, 100, 30)
            elif risk == 'MODERATE':
                pdf.set_text_color(180, 160, 30)
            else:
                pdf.set_text_color(40, 120, 40)

            pdf.set_font('Helvetica', 'B', 9)
            header = f'{i}. [{risk}] {region} - {detail}'
            clean_header = header.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 5, clean_header, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(80, 80, 80)
            stats_line = f'   {events} events in {window} days | Avg Priority: {avg_pri}'
            pdf.cell(0, 4, stats_line, new_x="LMARGIN", new_y="NEXT")

            samples = p.get('sample_titles', [])
            if samples:
                pdf.set_font('Helvetica', 'I', 7)
                pdf.set_text_color(100, 100, 100)
                for title in samples[:2]:
                    clean_t = str(title).encode('latin-1', 'replace').decode('latin-1')[:120]
                    pdf.cell(0, 4, f'     - {clean_t}', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    # ANALYST SUMMARY
    pdf.add_page()
    pdf.section_title('ANALYST ASSESSMENT')
    summary = brief.get('analyst_summary', 'No analyst summary available.')
    pdf.body_text(summary)
    pdf.ln(2)

    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(150, 50, 50)
    pdf.cell(0, 5, 'DISTRIBUTION: RESTRICTED | FOR AUTHORIZED PERSONNEL ONLY', align='C')

    return pdf.output()


# ============================================================
# Brief Generation Logic
# ============================================================

async def generate_brief_for_date(date: str):
    import pytz
    import re

    ist = pytz.timezone("Asia/Kolkata")
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(ist)

    previous_date = (now_ist - timedelta(days=1)).strftime("%Y-%m-%d")

    prev_day_brief = await briefs_col.find_one(
        {"date": previous_date},
        {"_id": 0, "generated_at": 1, "included_item_ids": 1, "date": 1},
        sort=[("generated_at", -1)]
    )

    any_previous_brief = await briefs_col.find_one(
        {"date": {"$lt": date}},
        {"_id": 0, "generated_at": 1, "included_item_ids": 1, "date": 1},
        sort=[("date", -1)]
    )

    previous_item_ids = set()
    today_0600_ist = now_ist.replace(hour=6, minute=0, second=0, microsecond=0)

    if prev_day_brief and prev_day_brief.get("generated_at"):
        cutoff_utc = prev_day_brief["generated_at"]
        if prev_day_brief.get("included_item_ids"):
            previous_item_ids.update(prev_day_brief["included_item_ids"])
        logger.info(f"Brief window: prev day brief ({previous_date}) generated at {cutoff_utc} -> now")
    elif any_previous_brief and any_previous_brief.get("generated_at"):
        cutoff_utc = any_previous_brief["generated_at"]
        if any_previous_brief.get("included_item_ids"):
            previous_item_ids.update(any_previous_brief["included_item_ids"])
        logger.info(f"Brief window: last brief ({any_previous_brief.get('date')}) generated at {cutoff_utc} -> now")
    else:
        cutoff_ist = today_0600_ist - timedelta(days=1)
        cutoff_utc = cutoff_ist.astimezone(timezone.utc).isoformat()
        logger.info(f"Brief window (first brief): {cutoff_utc} -> now")

    # ── Hard cap: brief window must never exceed 48 hours ────────────────────
    # Without this cap, if a previous brief ran days ago (e.g. after a gap day),
    # the window stretches back days and the brief surfaces stale items.
    max_cutoff_utc = (now_utc - timedelta(hours=48)).isoformat()
    if cutoff_utc < max_cutoff_utc:
        logger.info(f"Brief: capping window from {cutoff_utc} to {max_cutoff_utc} (48 h max)")
        cutoff_utc = max_cutoff_utc

    logger.info(f"Excluding {len(previous_item_ids)} items from previous briefs")

    # Title dedup helpers
    def normalize_title(title):
        t = (title or "").lower().strip()
        t = re.sub(r'[^a-z0-9\s]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def extract_key_entities(title):
        t = (title or "").lower()
        entities = set()
        known_orgs = ['ulfa', 'nscn', 'rpf', 'pla', 'hnlc', 'gnla', 'kla', 'mnf', 'unlf', 'prepak', 'knf', 'arsa', 'tnla', 'mndaa', 'assam rifles', 'bsf', 'crpf', 'army']
        known_places = ['manipur', 'assam', 'meghalaya', 'mizoram', 'tripura', 'arunachal', 'nagaland', 'tinsukia', 'changlang', 'tamenglong', 'imphal', 'dimapur', 'guwahati', 'silchar', 'agartala', 'shillong', 'aizawl', 'itanagar', 'kohima', 'myanmar', 'bangladesh', 'dhaka', 'chittagong', 'cox']
        known_events = ['rpg', 'grenade', 'gunfire', 'gunfight', 'bomb', 'blast', 'attack', 'ambush', 'shootout', 'firing', 'seized', 'arrested', 'killed', 'injured', 'rally', 'protest', 'blockade', 'bandh']

        for org in known_orgs:
            if org in t:
                entities.add(org)
        for place in known_places:
            if place in t:
                entities.add(place)
        for event in known_events:
            if event in t:
                entities.add(event)
        numbers = re.findall(r'\b(\d+)\s*(?:killed|injured|arrested|seized|dead)\b', t)
        for n in numbers:
            entities.add(f"count_{n}")
        return entities

    def is_duplicate_title(new_title, seen_titles, seen_entities_list, threshold=0.55):
        norm_new = normalize_title(new_title)
        if not norm_new or len(norm_new) < 10:
            return False
        new_words = set(norm_new.split())
        new_entities = extract_key_entities(new_title)

        for i, seen in enumerate(seen_titles):
            seen_words = set(seen.split())
            if not seen_words:
                continue
            overlap = len(new_words & seen_words)
            total = max(len(new_words), len(seen_words))
            word_sim = overlap / total if total > 0 else 0

            seen_ents = seen_entities_list[i] if i < len(seen_entities_list) else set()
            if new_entities and seen_ents:
                ent_overlap = len(new_entities & seen_ents)
                ent_total = max(len(new_entities), len(seen_ents))

                if ent_overlap >= 3:
                    return True
                if ent_overlap >= 2 and word_sim >= 0.35:
                    return True

            if word_sim >= threshold:
                return True
        return False

    # 1. GET CRITICAL/HIGH ITEMS
    base_filter = {"processed": True, "published_at": {"$gte": cutoff_utc}}
    if previous_item_ids:
        base_filter["id"] = {"$nin": list(previous_item_ids)}

    # Exclude non-primary cluster members — each story appears once (the primary)
    _cluster_primary_filter = {"$nor": [
        {"cluster_id": {"$exists": True, "$ne": None}, "is_cluster_primary": {"$ne": True}}
    ]}

    critical_high_items = await intelligence_col.find(
        {
            **base_filter,
            **_cluster_primary_filter,
            "$or": [
                {"severity": {"$in": ["critical", "high"]}},
                {"priority_score": {"$gte": 60}}
            ]
        },
        {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).to_list(100)

    if len(critical_high_items) < 5:
        logger.info(f"Brief: Only {len(critical_high_items)} items in time window, expanding to 7d")
        # Fallback still respects a maximum 7-day window so the brief never
        # surfaces items older than one week.
        fallback_cutoff = (now_utc - timedelta(days=7)).isoformat()
        fallback_filter = {
            "processed": True,
            "published_at": {"$gte": fallback_cutoff},
        }
        if previous_item_ids:
            fallback_filter["id"] = {"$nin": list(previous_item_ids)}
        fallback_items = await intelligence_col.find(
            {
                **fallback_filter,
                "$or": [
                    {"severity": {"$in": ["critical", "high"]}},
                    {"priority_score": {"$gte": 60}}
                ]
            },
            {"_id": 0}
        ).sort([("priority_score", -1), ("published_at", -1)]).limit(30).to_list(30)
        existing_urls = set(i.get("source_url") for i in critical_high_items)
        for item in fallback_items:
            if item.get("source_url") not in existing_urls:
                critical_high_items.append(item)
                existing_urls.add(item.get("source_url"))

    seen_titles = []
    seen_entities = []
    deduped_critical = []
    for item in critical_high_items:
        title = item.get("title", "")
        if not is_duplicate_title(title, seen_titles, seen_entities):
            deduped_critical.append(item)
            seen_titles.append(normalize_title(title))
            seen_entities.append(extract_key_entities(title))

    logger.info(f"Brief: {len(critical_high_items)} critical/high items found, {len(deduped_critical)} after title dedup")

    # 2. GET NER REGIONAL ITEMS
    ner_states_full = NER_STATES + ["Nagaland", "Sikkim", "Multiple"]
    ner_query = {
        "processed": True,
        "published_at": {"$gte": cutoff_utc},
        "state": {"$in": ner_states_full},
        "$or": [
            {"priority_score": {"$gte": 30}},
            {"tags": {"$exists": True, "$ne": []}},
            {"severity": {"$in": ["critical", "high", "medium"]}}
        ],
        **_cluster_primary_filter,
    }
    if previous_item_ids:
        ner_query["id"] = {"$nin": list(previous_item_ids)}

    ner_items = await intelligence_col.find(
        ner_query, {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).limit(80).to_list(80)

    if len(ner_items) < 5:
        logger.info(f"Brief: Only {len(ner_items)} NER items in window, expanding")
        fallback_ner_query = {
            "processed": True,
            "state": {"$in": ner_states_full},
            "severity": {"$in": ["critical", "high", "medium"]}
        }
        if previous_item_ids:
            fallback_ner_query["id"] = {"$nin": list(previous_item_ids)}
        fallback_ner = await intelligence_col.find(
            fallback_ner_query, {"_id": 0}
        ).sort([("priority_score", -1), ("published_at", -1)]).limit(40).to_list(40)
        existing_urls = set(i.get("source_url") for i in ner_items)
        for item in fallback_ner:
            if item.get("source_url") not in existing_urls:
                ner_items.append(item)
                existing_urls.add(item.get("source_url"))

    seen_sources = {}
    diverse_ner_items = []
    for item in ner_items:
        title = item.get("title", "")
        source = item.get("source", "Unknown")
        if is_duplicate_title(title, seen_titles, seen_entities):
            continue
        if source not in seen_sources:
            seen_sources[source] = 0
        if seen_sources[source] < 4:
            diverse_ner_items.append(item)
            seen_sources[source] += 1
            seen_titles.append(normalize_title(title))
            seen_entities.append(extract_key_entities(title))

    logger.info(f"Brief: {len(ner_items)} NER items, {len(diverse_ner_items)} after dedup from {len(seen_sources)} sources")

    # 3. GET NATIONAL NEWS
    # Dynamically get all national source names from rss_fetcher
    from rss_fetcher import RSS_SOURCES
    national_source_names = [s["name"] for s in RSS_SOURCES if s.get("category") == "national"]
    # Also include government sources
    govt_source_names = [s["name"] for s in RSS_SOURCES if s.get("category") == "government"]
    all_national_sources = national_source_names + govt_source_names

    national_query = {
        "processed": True,
        "is_relevant": True,
        "published_at": {"$gte": cutoff_utc},
        "source": {"$in": all_national_sources},
        "state": {"$nin": NER_STATES + ["Bangladesh", "Myanmar", "Multiple"]},
        "severity": {"$in": ["critical", "high", "medium"]},
        **_cluster_primary_filter,
    }
    if previous_item_ids:
        national_query["id"] = {"$nin": list(previous_item_ids)}
    national_items = await intelligence_col.find(
        national_query, {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).limit(30).to_list(30)

    # Strict filter: only security/defense/strategic relevant national news
    NATIONAL_EXCLUDE_KEYWORDS = [
        'cricket', 'football', 'sports', 'match', 'tournament', 'celebrity', 'entertainment',
        'movie', 'film', 'music', 'concert', 'festival', 'recipe', 'fashion', 'lifestyle',
        'wedding', 'divorce', 'animal', 'zoo', 'weather forecast', 'horoscope', 'lottery',
        'quiz', 'game show', 'reality show', 'bollywood', 'tollywood', 'ipl', 'champions league',
        'chelsea', 'goalkeeper', 'striker', 'midfielder', 'coach', 'player', 'oscar', 'grammy',
        'tequila', 'cruise ship', 'volcano', 'mars', 'neolithic', 'dinosaur', 'pulp fiction',
        'murder-suicide', 'colorado river', 'phd scholar', 'assassinated', 'candace owens',
    ]

    def is_relevant_national(item):
        title = (item.get("title", "") or "").lower()
        summary = (item.get("ai_summary", "") or "").lower()
        content = title + " " + summary
        # Reject noise
        for kw in NATIONAL_EXCLUDE_KEYWORDS:
            if kw in content:
                return False
        # Must have meaningful priority or security tags
        if item.get("priority_score", 0) >= 40:
            return True
        tags = item.get("tags", [])
        security_tags = ["Military", "Border", "Insurgency", "Cross-border", "Arms", "Drug",
                         "Security", "Foreign", "Defence", "Infrastructure", "Political",
                         "Cyber", "Strategic", "Immigration"]
        for tag in tags:
            for st in security_tags:
                if st.lower() in tag.lower():
                    return True
        return False

    military_national = [item for item in national_items if is_relevant_national(item)]

    logger.info(f"Brief: {len(national_items)} national items, {len(military_national)} military-relevant")

    # 4. GET INTERNATIONAL NEWS
    intl_query = {
        "processed": True,
        "published_at": {"$gte": cutoff_utc},
        "$or": [
            {"state": {"$in": ["Bangladesh", "Myanmar"]}},
            {"countries_involved": {"$in": ["China", "Pakistan"]}},
            {"priority_score": {"$gte": 35}},
            {"severity": {"$in": ["critical", "high"]}},
            {"tags": {"$in": [
                "Military Movement", "Cross-border Movement", "Insurgency / Militancy",
                "Foreign Influence (China/Pakistan/USA)", "Border Security", "Arms Smuggling",
                "Drug Trafficking", "Illegal Immigration", "Bangladesh Internal Dynamics",
                "Myanmar Instability", "Infrastructure / Logistics"
            ]}}
        ],
        "state": {"$nin": NER_STATES + ["Multiple", "India", ""]},
        **_cluster_primary_filter,
    }
    if previous_item_ids:
        intl_query["id"] = {"$nin": list(previous_item_ids)}
    international_items = await intelligence_col.find(
        intl_query, {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).limit(40).to_list(40)

    EXCLUDE_KEYWORDS = [
        'cricket', 'football', 'sports', 'match', 'tournament', 'celebrity', 'entertainment',
        'movie', 'film', 'music', 'concert', 'festival', 'recipe', 'fashion', 'lifestyle',
        'wedding', 'divorce', 'sparrow', 'bird', 'animal', 'zoo', 'weather forecast',
        'horoscope', 'lottery', 'quiz', 'game show', 'reality show', 'bollywood', 'tollywood',
        'chelsea', 'goalkeeper', 'striker', 'midfielder', 'coach', 'player'
    ]

    def is_strategic_news(item):
        title = (item.get("title", "") or "").lower()
        summary = (item.get("ai_summary", "") or "").lower()
        content = title + " " + summary
        for kw in EXCLUDE_KEYWORDS:
            if kw in content:
                return False
        if item.get("priority_score", 0) >= 35:
            return True
        tags = item.get("tags", [])
        security_tags = ["Military", "Border", "Insurgency", "Cross-border", "Arms", "Drug", "Security", "Foreign"]
        for tag in tags:
            for st in security_tags:
                if st.lower() in tag.lower():
                    return True
        return False

    strategic_intl_items = [item for item in international_items if is_strategic_news(item)]

    seen_intl_sources = {}
    diverse_intl_items = []
    for item in strategic_intl_items:
        title = item.get("title", "")
        source = item.get("source", "Unknown")
        if is_duplicate_title(title, seen_titles, seen_entities):
            continue
        if source not in seen_intl_sources:
            seen_intl_sources[source] = 0
        if seen_intl_sources[source] < 3:
            diverse_intl_items.append(item)
            seen_intl_sources[source] += 1
            seen_titles.append(normalize_title(title))
            seen_entities.append(extract_key_entities(title))

    logger.info(f"Brief: {len(international_items)} intl items, {len(strategic_intl_items)} strategic, {len(diverse_intl_items)} deduplicated")

    # 5. PATTERN INSIGHTS
    from pattern_engine import detect_patterns
    try:
        detected_patterns = await detect_patterns(db)
    except Exception as e:
        logger.warning(f"Pattern detection failed during brief gen: {e}")
        detected_patterns = await patterns_col.find({}, {"_id": 0}).to_list(50)

    # 6. UPLOADED DOCUMENT INSIGHTS (only for current brief period)
    uploaded_docs = await uploads_col.find(
        {"processed": True, "uploaded_at": {"$gte": cutoff_utc}},
        {"_id": 0}
    ).sort("uploaded_at", -1).limit(10).to_list(10)

    # 7. GENERATE AI BRIEF
    items_for_ai = deduped_critical + diverse_ner_items[:20]

    try:
        from ai_pipeline import generate_daily_brief_ai
        brief_data = await generate_daily_brief_ai(items_for_ai, date)
    except Exception as e:
        logger.error(f"AI brief generation failed: {e}")
        brief_data = generate_manual_brief(items_for_ai, date)

    # 8. BUILD KEY DEVELOPMENTS
    def build_brief_item(item):
        result = {
            "id": item.get("id", ""),  # used for faultline-tag enrichment
            "title": item.get("title", ""),
            "summary": item.get("ai_summary", ""),
            "source_url": item.get("source_url", ""),
            "timestamp": item.get("published_at", ""),
            "severity": item.get("severity", "medium"),
            "priority_score": item.get("priority_score", 0),
            "state": item.get("state", ""),
            "source": item.get("source", ""),
        }
        # Carry cluster metadata so PDF can show "Reported by N sources"
        cluster_size = item.get("cluster_size", 0)
        if cluster_size and cluster_size > 1:
            result["cluster_size"] = cluster_size
            result["cluster_sources"] = item.get("cluster_sources", [])
        if item.get("why_it_matters"):
            result["why_it_matters"] = item["why_it_matters"]
        if item.get("potential_impact"):
            result["potential_impact"] = item["potential_impact"]
        if item.get("early_warning_signal"):
            result["early_warning"] = item["early_warning_signal"]
        if item.get("special_flags"):
            flags = item["special_flags"]
            result["special_flags"] = flags if isinstance(flags, list) else [str(flags)]
        if item.get("actors"):
            actors = item["actors"]
            result["actors"] = ", ".join(actors) if isinstance(actors, list) else str(actors)
        if item.get("attention_level") and item["attention_level"] != "Routine Monitoring":
            result["attention_level"] = item["attention_level"]
        analyst_enhancement = item.get("analyst_enhancement") or {}
        if isinstance(analyst_enhancement, dict):
            note = analyst_enhancement.get("analyst_note", "")
            if note and isinstance(note, str) and note.strip():
                result["analyst_note"] = note.strip()
        return result

    key_developments = []
    added_ids = set()
    cluster_ids_in_brief = set()  # track cluster_ids so we can exclude siblings from next brief

    NER_STATES_FULL = NER_STATES + ["Nagaland", "Sikkim", "Multiple"]
    for item in deduped_critical:
        item_id = item.get("id")
        if item_id and item_id not in added_ids:
            if item.get("state") in NER_STATES_FULL:
                key_developments.append(build_brief_item(item))
                added_ids.add(item_id)
                if item.get("cluster_id"):
                    cluster_ids_in_brief.add(item["cluster_id"])

    for item in diverse_ner_items:
        item_id = item.get("id")
        if item_id and item_id not in added_ids:
            key_developments.append(build_brief_item(item))
            added_ids.add(item_id)
            if item.get("cluster_id"):
                cluster_ids_in_brief.add(item["cluster_id"])

    brief_data["key_developments"] = key_developments

    # 9. NATIONAL NEWS
    national_deduped = []
    for item in military_national:
        title = item.get("title", "")
        item_id = item.get("id")
        if item_id not in added_ids and not is_duplicate_title(title, seen_titles, seen_entities):
            national_deduped.append(build_brief_item(item))
            seen_titles.append(normalize_title(title))
            seen_entities.append(extract_key_entities(title))
            if item_id:
                added_ids.add(item_id)
            if item.get("cluster_id"):
                cluster_ids_in_brief.add(item["cluster_id"])
    brief_data["national_news"] = national_deduped[:15]

    # 10. INTERNATIONAL NEWS
    intl_built = []
    for item in diverse_intl_items:
        item_id = item.get("id")
        if item_id not in added_ids:
            intl_built.append({
                **build_brief_item(item),
                "countries": ", ".join(item.get("countries_involved", [])) if isinstance(item.get("countries_involved"), list) else str(item.get("countries_involved", "")),
            })
            if item_id:
                added_ids.add(item_id)
            if item.get("cluster_id"):
                cluster_ids_in_brief.add(item["cluster_id"])
    brief_data["international_news"] = intl_built

    # 10.5 CROSS-BORDER INTELLIGENCE (Bangladesh & Myanmar)
    # Use the same cutoff_utc as the rest of the brief (previous brief's generation
    # time) so the same BD/MM articles never appear in consecutive briefs.
    # 7-day hard cap kept as safety net for gap days.
    from routers.cross_border import _auto_categorize, CATEGORY_LABELS
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cb_cutoff = max(cutoff_utc, seven_days_ago)
    cb_query = {
        "processed": True,
        "ai_summary": {"$exists": True, "$ne": ""},
        "severity": {"$nin": ["low", "LOW"]},
        "published_at": {"$gte": cb_cutoff},
        "$or": [
            {"is_cross_border": True},
            {"countries_involved": {"$elemMatch": {"$in": ["Bangladesh", "Myanmar"]}}},
            {"state": {"$in": ["Bangladesh", "Myanmar"]}},
        ],
        **_cluster_primary_filter,
    }
    if previous_item_ids:
        cb_query["id"] = {"$nin": list(previous_item_ids)}
    cb_items = await intelligence_col.find(
        cb_query, {"_id": 0}
    ).sort("priority_score", -1).limit(80).to_list(80)

    BD_KW = {"bangladesh", "dhaka", "bgb", "rohingya", "cox's bazar", "chittagong", "sylhet", "awami league", "bnp", "hasina", "yunus"}
    MM_KW = {"myanmar", "burma", "tatmadaw", "chin state", "sagaing", "rakhine", "kachin", "shan state", "tamu", "nscn", "junta", "min aung hlaing"}

    bd_brief_items = []
    mm_brief_items = []
    for item in cb_items:
        if not item.get("ai_summary"):
            continue
        if has_non_latin_chars(item.get("title", "") or ""):
            continue
        state_val = (item.get("state", "") or "").lower()
        text_all = ((item.get("title", "") or "") + " " + (item.get("ai_summary", "") or "")).lower()
        cat = _auto_categorize(item)
        cat_label = CATEGORY_LABELS.get(cat, cat.replace("_", " ").title() if cat else "Other")
        brief_item = {**build_brief_item(item), "category": cat_label}

        if state_val == "bangladesh" or any(kw in text_all for kw in BD_KW):
            bd_brief_items.append(brief_item)
        elif state_val == "myanmar" or any(kw in text_all for kw in MM_KW):
            mm_brief_items.append(brief_item)

    # Deduplicate by title within each section
    def _dedup_cb(items):
        seen = []
        result = []
        for item in items:
            norm = normalize_title(item.get("title", ""))
            if not any(title_similarity(norm, s) > 0.5 for s in seen):
                result.append(item)
                seen.append(norm)
        return result

    def title_similarity(a, b):
        wa, wb = set(a.split()), set(b.split())
        if not wa or not wb:
            return 0
        return len(wa & wb) / max(len(wa), len(wb))

    bd_brief_items = _dedup_cb(bd_brief_items)[:15]
    mm_brief_items = _dedup_cb(mm_brief_items)[:15]

    # Track CB items in added_ids (built dicts, cluster_id not present — use cb_items raw list)
    cb_ids_included = {item.get("id") for item in bd_brief_items + mm_brief_items if item.get("id")}
    for raw_cb in cb_items:
        if raw_cb.get("id") in cb_ids_included:
            added_ids.add(raw_cb["id"])
            if raw_cb.get("cluster_id"):
                cluster_ids_in_brief.add(raw_cb["cluster_id"])

    brief_data["cross_border_bangladesh"] = bd_brief_items
    brief_data["cross_border_myanmar"] = mm_brief_items

    logger.info(f"Brief cross-border: {len(bd_brief_items)} Bangladesh, {len(mm_brief_items)} Myanmar")

    # 11. PATTERN INSIGHTS AND UPLOADS
    brief_data["pattern_insights"] = [
        {
            "region": p.get("region", ""),
            "detail": p.get("detail", p.get("pattern_type", "")),
            "event_count": p.get("event_count", 0),
            "escalation_risk": p.get("escalation_risk", "LOW"),
            "avg_priority_score": p.get("avg_priority_score", 0),
            "window_days": p.get("window_days", 7),
            "sample_titles": p.get("sample_titles", [])[:2],
        }
        for p in detected_patterns
        if p.get("escalation_risk") in ("CRITICAL", "HIGH", "MODERATE")
    ][:15]

    brief_data["uploaded_insights"] = [
        {
            "filename": doc.get("filename", ""),
            "ai_analysis": doc.get("ai_analysis", doc.get("content_summary", "")),
            "region": doc.get("region", ""),
            "uploaded_at": doc.get("uploaded_at", "")
        }
        for doc in uploaded_docs[:10]
    ]

    # 12. TRACK INCLUDED ITEM IDS
    # Expand with cluster siblings so next brief's previous_item_ids also excludes them.
    # This prevents non-primary cluster members from leaking into tomorrow's brief.
    if cluster_ids_in_brief:
        sibling_docs = await intelligence_col.find(
            {"cluster_id": {"$in": list(cluster_ids_in_brief)}, "id": {"$nin": list(added_ids)}},
            {"_id": 0, "id": 1}
        ).to_list(2000)
        sibling_count = 0
        for doc in sibling_docs:
            if doc.get("id"):
                added_ids.add(doc["id"])
                sibling_count += 1
        if sibling_count:
            logger.info(f"Brief: expanded included_item_ids by {sibling_count} cluster siblings from {len(cluster_ids_in_brief)} clusters")

    brief_data["included_item_ids"] = list(added_ids)

    # 12b. FAULTLINE TAGS (PAOI overlay) — enrich news items with faultline
    #      chips; RED in UI when the faultline belongs to a Priority Area.
    await attach_faultline_tags(brief_data.get("key_developments", []))
    await attach_faultline_tags(brief_data.get("national_news", []))
    await attach_faultline_tags(brief_data.get("international_news", []))
    await attach_faultline_tags(brief_data.get("cross_border_bangladesh", []))
    await attach_faultline_tags(brief_data.get("cross_border_myanmar", []))

    # 13. SAVE AND RETURN
    brief = DailyBrief(**brief_data)
    doc = brief.model_dump()
    doc.pop("twitter_highlights", None)
    await briefs_col.replace_one({"date": date}, doc, upsert=True)

    logger.info(f"Brief generated: {len(key_developments)} NER developments, {len(brief_data.get('national_news', []))} national, {len(brief_data.get('international_news', []))} international, {len(brief_data.get('pattern_insights', []))} patterns, {len(added_ids)} items tracked")

    return doc


def generate_manual_brief(items, date):
    developments = []
    state_highlights = {}
    cross_border_items = []

    for item in items[:15]:
        sev = item.get('severity', 'medium').upper()
        developments.append(f"[{sev}] {item['title']}")
        state = item.get('state', '')
        if state and state not in state_highlights:
            state_highlights[state] = item.get('ai_summary', item['title'])
        if item.get('is_cross_border'):
            cross_border_items.append(item['title'])

    critical_count = sum(1 for i in items if i.get('severity') == 'critical')
    high_count = sum(1 for i in items if i.get('severity') == 'high')

    return {
        "id": str(uuid.uuid4()),
        "date": date,
        "key_developments": developments[:8],
        "state_highlights": state_highlights,
        "cross_border_insights": "; ".join(cross_border_items[:3]) if cross_border_items else "No significant cross-border developments reported in this period.",
        "analyst_summary": f"Intelligence summary for {date}: {len(items)} items monitored across NER. {critical_count} critical and {high_count} high-severity items require immediate attention. Continuous monitoring of cross-border activities and insurgent movements recommended.",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# Scheduler wrapper
async def generate_scheduled_daily_brief():
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(timezone.utc).astimezone(ist)
    date = now_ist.strftime("%Y-%m-%d")
    logger.info(f"=== SCHEDULED DAILY BRIEF GENERATION: {date} at {now_ist.strftime('%H:%M IST')} ===")
    try:
        brief = await generate_brief_for_date(date)
        dev_count = len(brief.get("key_developments", []))
        pattern_count = len(brief.get("pattern_insights", []))
        logger.info(f"Scheduled brief generated: {dev_count} developments, {pattern_count} pattern insights")
    except Exception as e:
        logger.error(f"Scheduled brief generation failed: {e}")
