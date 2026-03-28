from fastapi import FastAPI, APIRouter, Query, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
import io

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Rhino Drishti API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

intelligence_col = db.intelligence_items
briefs_col = db.daily_briefs
sources_col = db.rss_sources
uploads_col = db.uploaded_documents
tweets_col = db.twitter_feeds
national_news_col = db.national_news
international_news_col = db.international_news

# In-memory scan status tracker
scan_status = {
    "is_scanning": False,
    "progress": 0,
    "total_sources": 0,
    "current_source": "",
    "sources_scanned": 0,
    "articles_found": 0,
    "relevant_found": 0,
    "last_scan_at": None,
    "last_scan_result": None,
    "scan_log": [],
}

# Twitter/X accounts to monitor for defense updates
TWITTER_ACCOUNTS_TO_MONITOR = [
    {"handle": "@adgpi", "name": "ADG PI - Indian Army", "category": "defense", "url": "https://twitter.com/adgpi"},
    {"handle": "@IAF_MCC", "name": "Indian Air Force", "category": "defense", "url": "https://twitter.com/IAF_MCC"},
    {"handle": "@indiannavy", "name": "Indian Navy", "category": "defense", "url": "https://twitter.com/indiannavy"},
    {"handle": "@easaborterncomd", "name": "Eastern Command - Indian Army", "category": "defense", "url": "https://twitter.com/easterncomd"},
    {"handle": "@DefenceMinIndia", "name": "Ministry of Defence", "category": "government", "url": "https://twitter.com/DefenceMinIndia"},
    {"handle": "@MEAIndia", "name": "Ministry of External Affairs", "category": "government", "url": "https://twitter.com/MEAIndia"},
    {"handle": "@HMOIndia", "name": "Home Ministry", "category": "government", "url": "https://twitter.com/HMOIndia"},
    {"handle": "@PMOIndia", "name": "Prime Minister's Office", "category": "government", "url": "https://twitter.com/PMOIndia"},
    {"handle": "@BSF_India", "name": "Border Security Force", "category": "paramilitary", "url": "https://twitter.com/BSF_India"},
    {"handle": "@craborCRPF", "name": "CRPF", "category": "paramilitary", "url": "https://twitter.com/crpaborCRPF"},
    {"handle": "@official_dgar", "name": "Assam Rifles", "category": "paramilitary", "url": "https://twitter.com/official_dgar"},
    {"handle": "@ABORAITBP", "name": "ITBP", "category": "paramilitary", "url": "https://twitter.com/ITBP_official"},
    {"handle": "@SpsHanada", "name": "SPS Hanada - Defense Analyst", "category": "analyst", "url": "https://twitter.com/SpsHanada"},
]

THREAT_CATEGORIES = [
    "Insurgency", "Cross-border Movement", "Illegal Immigration",
    "Drug Trafficking", "Arms Smuggling", "Ethnic Conflicts",
    "Cyber Threats", "Strategic Infrastructure",
    "Political Developments", "Foreign Power Influence",
    "Military Operations", "Economic/Trade"
]
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]
NER_STATES = ["Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura"]
MONITORED_REGIONS = NER_STATES + ["Bangladesh", "Myanmar"]
BORDER_COUNTRIES = ["Bangladesh", "Myanmar"]


class IntelligenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    source: str
    source_url: str = ""
    published_at: str
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_content: str = ""
    ai_summary: str = ""
    why_it_matters: str = ""
    potential_impact: str = ""
    attention_level: str = "Routine Monitoring"
    state: str = ""
    threat_category: str = ""
    severity: str = "medium"
    is_cross_border: bool = False
    countries_involved: List[str] = []
    processed: bool = True
    tags: List[str] = []
    # New enhanced intelligence fields
    priority_score: int = 30
    regions: List[str] = []
    actors: List[str] = []
    special_flags: List[str] = []
    early_warning_signal: str = ""
    original_title: Optional[str] = None


class DailyBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    # NER Regional News
    key_developments: List[Dict] = []  # Changed from List[str] to support source links
    state_highlights: Dict[str, str] = {}
    cross_border_insights: str = ""
    analyst_summary: str = ""
    # National News Section
    national_news: List[Dict] = []
    # International News Section
    international_news: List[Dict] = []
    # Twitter/X Section
    twitter_highlights: List[Dict] = []
    # Uploaded Document Insights
    uploaded_insights: List[Dict] = []
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UploadedDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_type: str
    uploaded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_summary: str = ""
    extracted_text: str = ""
    ai_analysis: str = ""
    region: str = ""
    processed: bool = False


class TwitterFeed(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    handle: str
    account_name: str
    tweet_text: str
    tweet_url: str = ""
    posted_at: str
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    category: str = "defense"
    is_relevant: bool = True


@api_router.get("/")
async def root():
    return {"message": "Rhino Drishti API - Intelligence Aggregation Platform"}


@api_router.get("/dashboard/stats")
async def get_dashboard_stats():
    total = await intelligence_col.count_documents({})
    critical = await intelligence_col.count_documents({"severity": "critical"})
    high = await intelligence_col.count_documents({"severity": "high"})
    medium = await intelligence_col.count_documents({"severity": "medium"})
    low = await intelligence_col.count_documents({"severity": "low"})

    state_dist = {}
    async for doc in intelligence_col.aggregate([
        {"$group": {"_id": "$state", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]):
        if doc["_id"]:
            state_dist[doc["_id"]] = doc["count"]

    threat_dist = {}
    async for doc in intelligence_col.aggregate([
        {"$group": {"_id": "$threat_category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]):
        if doc["_id"]:
            threat_dist[doc["_id"]] = doc["count"]

    recent_critical = await intelligence_col.find(
        {"severity": {"$in": ["critical", "high"]}},
        {"_id": 0}
    ).sort("published_at", -1).limit(5).to_list(5)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = await intelligence_col.count_documents(
        {"published_at": {"$regex": f"^{today}"}}
    )

    trend_data = []
    async for doc in intelligence_col.aggregate([
        {"$group": {
            "_id": {"$substr": ["$published_at", 0, 10]},
            "count": {"$sum": 1},
            "critical": {"$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}},
            "high": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]):
        trend_data.append({"date": doc["_id"], "count": doc["count"], "critical": doc["critical"], "high": doc["high"]})

    return {
        "total_items": total, "today_count": today_count,
        "critical_count": critical, "high_count": high,
        "medium_count": medium, "low_count": low,
        "state_distribution": state_dist, "threat_distribution": threat_dist,
        "recent_critical": recent_critical, "trend_7d": trend_data[-7:]
    }


@api_router.get("/intelligence")
async def get_intelligence(
    state: Optional[str] = None,
    threat_type: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_cross_border: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    translate: bool = Query(True)  # Auto-translate non-English content
):
    query = {}
    if state:
        query["state"] = state
    if threat_type:
        query["threat_category"] = threat_type
    if severity:
        query["severity"] = severity
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"ai_summary": {"$regex": search, "$options": "i"}},
            {"raw_content": {"$regex": search, "$options": "i"}}
        ]
    if date_from:
        query.setdefault("published_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("published_at", {})["$lte"] = date_to
    if is_cross_border is not None:
        query["is_cross_border"] = is_cross_border

    skip = (page - 1) * limit
    total = await intelligence_col.count_documents(query)
    items = await intelligence_col.find(query, {"_id": 0}).sort("published_at", -1).skip(skip).limit(limit).to_list(limit)

    # Translate non-English titles for display
    if translate:
        for item in items:
            if has_non_latin_chars(item.get("title", "")):
                item["title"] = await translate_to_english(item["title"])

    return {
        "items": items, "total": total, "page": page,
        "limit": limit, "pages": max((total + limit - 1) // limit, 0)
    }


@api_router.get("/intelligence/{item_id}")
async def get_intelligence_item(item_id: str):
    item = await intelligence_col.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@api_router.get("/alerts")
async def get_alerts():
    items = await intelligence_col.find(
        {"severity": {"$in": ["critical", "high"]}}, {"_id": 0}
    ).sort("published_at", -1).limit(30).to_list(30)
    return {"alerts": items, "count": len(items)}


@api_router.get("/daily-brief")
async def get_daily_brief(date: Optional[str] = None):
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief = await briefs_col.find_one({"date": date}, {"_id": 0})
    if not brief:
        brief = await generate_brief_for_date(date)
    return brief


@api_router.post("/generate-brief")
async def generate_brief(background_tasks: BackgroundTasks):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    background_tasks.add_task(generate_brief_for_date, date)
    return {"message": "Brief generation started", "date": date}



@api_router.get("/daily-brief/pdf")
async def get_daily_brief_pdf(date: Optional[str] = None):
    """Generate and return a PDF of the daily intelligence brief with translated content"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief = await briefs_col.find_one({"date": date}, {"_id": 0})
    if not brief:
        brief = await generate_brief_for_date(date)

    # Translate any non-English content in the brief for PDF
    brief = await translate_brief_for_pdf(brief)

    # Get stats for the PDF header
    total = await intelligence_col.count_documents({})
    critical = await intelligence_col.count_documents({"severity": "critical"})
    high = await intelligence_col.count_documents({"severity": "high"})

    pdf_bytes = generate_brief_pdf(brief, date, total, critical, high)

    import io
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Rhino_Drishti_Brief_{date}.pdf"}
    )


async def translate_brief_for_pdf(brief: dict) -> dict:
    """Translate non-English content in brief to English for PDF rendering"""
    translated = dict(brief)
    
    # Translate key_developments
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
    
    # Translate national_news
    if translated.get("national_news"):
        for news in translated["national_news"]:
            if isinstance(news, dict):
                if has_non_latin_chars(news.get("title", "")):
                    news["title"] = await translate_to_english(news["title"])
                if has_non_latin_chars(news.get("summary", "")):
                    news["summary"] = await translate_to_english(news["summary"])
    
    # Translate international_news
    if translated.get("international_news"):
        for news in translated["international_news"]:
            if isinstance(news, dict):
                if has_non_latin_chars(news.get("title", "")):
                    news["title"] = await translate_to_english(news["title"])
                if has_non_latin_chars(news.get("summary", "")):
                    news["summary"] = await translate_to_english(news["summary"])
    
    # Translate state_highlights
    if translated.get("state_highlights"):
        for state, highlight in translated["state_highlights"].items():
            if has_non_latin_chars(highlight):
                translated["state_highlights"][state] = await translate_to_english(highlight)
    
    # Translate analyst_summary and cross_border_insights
    if has_non_latin_chars(translated.get("analyst_summary", "")):
        translated["analyst_summary"] = await translate_to_english(translated["analyst_summary"])
    if has_non_latin_chars(translated.get("cross_border_insights", "")):
        translated["cross_border_insights"] = await translate_to_english(translated["cross_border_insights"])
    
    return translated


def has_non_latin_chars(text: str) -> bool:
    """Check if text contains non-Latin characters (Bengali, Hindi, Assamese, etc.)"""
    if not text:
        return False
    for char in text:
        code = ord(char)
        # Check for Bengali (U+0980-U+09FF), Devanagari (U+0900-U+097F), 
        # and other South Asian scripts
        if (0x0900 <= code <= 0x097F) or \
           (0x0980 <= code <= 0x09FF) or \
           (0x0A00 <= code <= 0x0A7F) or \
           (0x0A80 <= code <= 0x0AFF) or \
           (0x0B00 <= code <= 0x0B7F) or \
           (0x0B80 <= code <= 0x0BFF) or \
           (0x0C00 <= code <= 0x0C7F) or \
           (0x0C80 <= code <= 0x0CFF) or \
           (0x0D00 <= code <= 0x0D7F):
            return True
    return False


async def translate_to_english(text: str) -> str:
    """Translate non-English text to English using AI"""
    if not text or not has_non_latin_chars(text):
        return text
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"translate-{hash(text[:50])}",
            system_message="You are a translator. Translate the following text to English. Return ONLY the English translation, nothing else."
        ).with_model("anthropic", "claude-haiku-4-5-20251001")
        
        response = await chat.send_message(UserMessage(text=text[:1000]))
        return str(response).strip()
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        # Return transliterated version as fallback
        return text.encode('ascii', 'ignore').decode('ascii') or "[Non-English content]"


def clean_for_pdf(text: str) -> str:
    """Clean text for PDF rendering - remove non-Latin characters"""
    if not text:
        return ""
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '"': '"', '"': '"', ''': "'", ''': "'", 
        '–': '-', '—': '-', '…': '...', '•': '*',
        '\u200b': '', '\u200c': '', '\u200d': '',  # Zero-width chars
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    
    # If text has non-Latin chars, mark it for translation
    if has_non_latin_chars(text):
        # For PDF, we can't await, so we'll use a placeholder
        return "[Content requires translation - see original source]"
    
    return text.encode('latin-1', 'replace').decode('latin-1')


def generate_brief_pdf(brief: dict, date: str, total: int, critical: int, high: int) -> bytes:
    """Generate a professional PDF for the daily intelligence brief"""
    from fpdf import FPDF

    class BriefPDF(FPDF):
        def header(self):
            self.set_fill_color(30, 35, 25)
            self.rect(0, 0, 210, 40, 'F')
            self.set_font('Helvetica', 'B', 20)
            self.set_text_color(180, 220, 80)
            self.set_y(8)
            self.cell(0, 10, 'RHINO DRISHTI', align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_font('Helvetica', '', 9)
            self.set_text_color(160, 170, 150)
            self.cell(0, 5, 'NER INTELLIGENCE PLATFORM  |  DAILY INTELLIGENCE BRIEF', align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_font('Helvetica', '', 8)
            self.cell(0, 5, f'Classification: RESTRICTED  |  Date: {date}', align='C', new_x="LMARGIN", new_y="NEXT")
            self.ln(8)

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
            """Render a news item with embedded source link"""
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
            """Render a comprehensive news item with full analysis fields"""
            if self.get_y() > 240:
                self.add_page()
            
            title = item.get('title', '')
            summary = item.get('summary', '')
            source_url = item.get('source_url', '')
            severity = item.get('severity', '')
            state = item.get('state', '')
            priority = item.get('priority_score', 0)
            
            # Title with severity badge
            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(40, 60, 80)
            sev_label = f' [{severity.upper()}]' if severity in ('critical', 'high') else ''
            clean_title = f'{index}. {title}{sev_label}'.encode('latin-1', 'replace').decode('latin-1')[:180]
            self.multi_cell(0, 5, clean_title, new_x="LMARGIN", new_y="NEXT")
            
            # Summary
            if summary:
                self.set_font('Helvetica', '', 8)
                self.set_text_color(60, 60, 60)
                self.multi_cell(0, 4, summary.encode('latin-1', 'replace').decode('latin-1')[:500], new_x="LMARGIN", new_y="NEXT")
            
            # Why it matters
            why = item.get('why_it_matters', '')
            if why:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(50, 120, 50)
                self.cell(30, 4, 'Why it matters: ', new_x="END")
                self.set_font('Helvetica', '', 7)
                self.set_text_color(80, 80, 80)
                self.multi_cell(0, 4, why.encode('latin-1', 'replace').decode('latin-1')[:300], new_x="LMARGIN", new_y="NEXT")
            
            # Potential impact
            impact = item.get('potential_impact', '')
            if impact:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(180, 120, 30)
                self.cell(30, 4, 'Potential impact: ', new_x="END")
                self.set_font('Helvetica', '', 7)
                self.set_text_color(80, 80, 80)
                self.multi_cell(0, 4, impact.encode('latin-1', 'replace').decode('latin-1')[:300], new_x="LMARGIN", new_y="NEXT")
            
            # Early warning
            warning = item.get('early_warning', '')
            if warning:
                if self.get_y() > 270: self.add_page()
                self.set_font('Helvetica', 'B', 7)
                self.set_text_color(200, 50, 50)
                self.cell(30, 4, 'EARLY WARNING: ', new_x="END")
                self.set_font('Helvetica', '', 7)
                self.set_text_color(150, 50, 50)
                self.multi_cell(0, 4, warning.encode('latin-1', 'replace').decode('latin-1')[:300], new_x="LMARGIN", new_y="NEXT")
            
            # Special flags
            flags = item.get('special_flags', [])
            if flags and isinstance(flags, list) and len(flags) > 0:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(140, 100, 40)
                flags_text = 'Flags: ' + ' | '.join(str(f) for f in flags[:5])
                self.cell(0, 4, flags_text.encode('latin-1', 'replace').decode('latin-1')[:150], new_x="LMARGIN", new_y="NEXT")
            
            # Actors
            actors = item.get('actors', '')
            if actors:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(100, 100, 120)
                self.cell(0, 4, f'Actors: {str(actors)[:120]}'.encode('latin-1', 'replace').decode('latin-1'), new_x="LMARGIN", new_y="NEXT")
            
            # Source link and metadata
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

    # Situation Overview box
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
    pdf.cell(0, 5, 'Covering: Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar')
    pdf.ln(15)

    # ========== NER REGIONAL SECTION ==========
    pdf.section_title('NORTHEAST REGION - KEY DEVELOPMENTS')
    developments = brief.get('key_developments', [])
    if developments:
        for i, dev in enumerate(developments, 1):
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

    # Region-wise Highlights
    pdf.section_title('REGION-WISE HIGHLIGHTS')
    highlights = brief.get('state_highlights', {})
    if highlights:
        for region, text in highlights.items():
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(50, 60, 40)
            pdf.cell(0, 5, region.upper(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(60, 60, 60)
            clean_text = str(text).encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, clean_text)
            pdf.ln(2)
    else:
        pdf.body_text('No region-specific highlights available.')
    pdf.ln(2)

    # Cross-Border & Foreign Power Insights
    pdf.section_title('CROSS-BORDER & FOREIGN POWER INSIGHTS')
    cross = brief.get('cross_border_insights', 'No significant cross-border developments.')
    pdf.body_text(cross)
    
    # ========== NATIONAL NEWS SECTION ==========
    pdf.add_page()
    pdf.section_title('NATIONAL NEWS')
    national_news = brief.get('national_news', [])
    if national_news:
        for i, news in enumerate(national_news[:15], 1):
            if isinstance(news, dict):
                pdf.news_item_comprehensive(i, news)
            else:
                pdf.body_text(f'{i}. {news}')
    else:
        pdf.body_text('No national news items available for this period.')
    
    # ========== INTERNATIONAL NEWS SECTION ==========
    pdf.add_page()
    pdf.section_title('INTERNATIONAL NEWS')
    intl_news = brief.get('international_news', [])
    if intl_news:
        for i, news in enumerate(intl_news[:15], 1):
            if isinstance(news, dict):
                pdf.news_item_comprehensive(i, news)
            else:
                pdf.body_text(f'{i}. {news}')
    else:
        pdf.body_text('No international news items available for this period.')
    
    # ========== X (TWITTER) WATCH SECTION ==========
    pdf.add_page()
    pdf.section_title('X (TWITTER) WATCH - DEFENSE & GOVERNMENT ACCOUNTS')
    twitter_highlights = brief.get('twitter_highlights', [])
    if twitter_highlights:
        for i, tweet in enumerate(twitter_highlights[:20], 1):
            if isinstance(tweet, dict):
                handle = tweet.get('handle', '')
                account = tweet.get('account_name', '')
                text = tweet.get('tweet_text', '')
                url = tweet.get('tweet_url', '')
                posted = tweet.get('posted_at', '')
                
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_text_color(29, 161, 242)  # Twitter blue
                pdf.cell(0, 5, f'{i}. {handle} ({account})', new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font('Helvetica', '', 8)
                pdf.set_text_color(40, 40, 40)
                clean_text = text.encode('latin-1', 'replace').decode('latin-1')[:400]
                pdf.multi_cell(0, 4, clean_text)
                
                if url:
                    pdf.set_font('Helvetica', 'I', 7)
                    pdf.set_text_color(70, 100, 150)
                    pdf.cell(0, 4, f'[Link: {url[:60]}...]', new_x="LMARGIN", new_y="NEXT", link=url)
                
                if posted:
                    pdf.set_font('Helvetica', 'I', 7)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(0, 4, f'Posted: {posted}', new_x="LMARGIN", new_y="NEXT")
                
                pdf.ln(2)
    else:
        pdf.body_text('No Twitter/X updates available. Accounts monitored: @adgpi, @IAF_MCC, @indiannavy, @DefenceMinIndia, @MEAIndia, @HMOIndia, @PMOIndia, @BSF_India, @craborCRPF, @official_dgar')
    
    # ========== UPLOADED DOCUMENT INSIGHTS ==========
    uploaded_insights = brief.get('uploaded_insights', [])
    if uploaded_insights:
        pdf.add_page()
        pdf.section_title('UPLOADED DOCUMENT INSIGHTS')
        for i, doc in enumerate(uploaded_insights[:10], 1):
            if isinstance(doc, dict):
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_text_color(80, 60, 40)
                filename = doc.get('filename', 'Unknown Document')
                pdf.cell(0, 5, f'{i}. {filename}', new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font('Helvetica', '', 8)
                pdf.set_text_color(60, 60, 60)
                analysis = doc.get('ai_analysis', doc.get('content_summary', ''))[:500]
                clean_analysis = analysis.encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 4, clean_analysis)
                pdf.ln(2)
    
    # ========== ANALYST SUMMARY ==========
    pdf.add_page()
    pdf.section_title('ANALYST ASSESSMENT')
    summary = brief.get('analyst_summary', 'No analyst summary available.')
    pdf.body_text(summary)
    pdf.ln(2)

    # Classification footer
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(150, 50, 50)
    pdf.cell(0, 5, 'DISTRIBUTION: RESTRICTED | FOR AUTHORIZED PERSONNEL ONLY', align='C')

    return pdf.output()


@api_router.get("/weekly-trends")
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


@api_router.get("/sources")
async def get_sources():
    sources = await sources_col.find({}, {"_id": 0}).to_list(100)
    return {"sources": sources}


@api_router.get("/twitter-accounts")
async def get_twitter_accounts():
    """Get list of Twitter/X accounts being monitored"""
    return {"accounts": TWITTER_ACCOUNTS_TO_MONITOR}


@api_router.get("/twitter-feeds")
async def get_twitter_feeds(limit: int = Query(50, ge=1, le=200)):
    """Get recent Twitter/X feeds from monitored accounts"""
    feeds = await tweets_col.find({}, {"_id": 0}).sort("posted_at", -1).limit(limit).to_list(limit)
    return {"feeds": feeds, "count": len(feeds)}


@api_router.get("/uploaded-documents")
async def get_uploaded_documents():
    """Get list of uploaded documents"""
    docs = await uploads_col.find({}, {"_id": 0}).sort("uploaded_at", -1).to_list(100)
    return {"documents": docs, "count": len(docs)}


@api_router.post("/upload-document")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Upload a PDF, Word, or Excel document for intelligence analysis"""
    allowed_types = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "text/plain": "txt"
    }
    
    content_type = file.content_type
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not supported. Allowed: PDF, Word, Excel, TXT")
    
    file_type = allowed_types[content_type]
    file_content = await file.read()
    
    # Extract text from document
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
            extracted_text = "\n".join([para.text for para in doc.paragraphs])
        elif file_type in ["xlsx", "xls"]:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(file_content))
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    extracted_text += " | ".join([str(cell) for cell in row if cell]) + "\n"
        elif file_type == "txt":
            extracted_text = file_content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error extracting text from {file.filename}: {e}")
        extracted_text = f"Error extracting text: {str(e)}"
    
    # Create document record
    doc_record = {
        "id": str(uuid.uuid4()),
        "filename": file.filename,
        "file_type": file_type,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "content_summary": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
        "extracted_text": extracted_text[:10000],  # Limit to 10k chars
        "ai_analysis": "",
        "region": "",
        "processed": False
    }
    
    await uploads_col.insert_one(doc_record)
    
    # Trigger AI analysis in background
    if background_tasks:
        background_tasks.add_task(analyze_uploaded_document, doc_record["id"])
    
    return {
        "message": "Document uploaded successfully",
        "document_id": doc_record["id"],
        "filename": file.filename,
        "extracted_chars": len(extracted_text)
    }


@api_router.delete("/uploaded-documents/{doc_id}")
async def delete_uploaded_document(doc_id: str):
    """Delete an uploaded document"""
    result = await uploads_col.delete_one({"id": doc_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@api_router.post("/fetch-news")
async def trigger_fetch(background_tasks: BackgroundTasks):
    background_tasks.add_task(fetch_and_process_news)
    return {"message": "News fetch triggered"}


@api_router.post("/bulk-scrape")
async def trigger_bulk_scrape(background_tasks: BackgroundTasks):
    """Bulk scrape ALL articles from RSS feeds without AI processing.
    Articles are stored as unprocessed and will be AI-analyzed gradually."""
    background_tasks.add_task(bulk_scrape_all_feeds)
    return {"message": "Bulk scrape triggered - articles will be stored for gradual AI processing"}


@api_router.get("/scan-status")
async def get_scan_status():
    """Get real-time RSS scan status"""
    return scan_status


@api_router.post("/analyze-news")
async def trigger_analysis(background_tasks: BackgroundTasks):
    background_tasks.add_task(analyze_unprocessed_items)
    return {"message": "Analysis triggered"}


@api_router.get("/pipeline/status")
async def pipeline_status():
    """Show processing pipeline health with rate limit management info"""
    total = await intelligence_col.count_documents({})
    processed = await intelligence_col.count_documents({"processed": True})
    unprocessed = await intelligence_col.count_documents({"processed": False})
    sources = await sources_col.count_documents({})
    
    # Get recent processing stats (last 24 hours)
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_processed = await intelligence_col.count_documents({
        "processed": True,
        "fetched_at": {"$gte": yesterday}
    })
    
    return {
        "total_items": total,
        "ai_processed": processed,
        "pending_retry": unprocessed,
        "processing_rate": f"{(processed / total * 100):.1f}%" if total > 0 else "N/A",
        "recent_24h_processed": recent_processed,
        "rss_sources": sources,
        "rate_limit_config": {
            "max_articles_per_cycle": 25,
            "batch_size": 3,
            "batch_pause_seconds": 5,
            "inter_article_delay_seconds": 1.5,
            "max_retry_per_cycle": 15
        },
        "scheduler": "fetch every 30 min (max 25 articles), retry unprocessed every 15 min (max 15 articles)"
    }



async def generate_brief_for_date(date: str):
    """Generate comprehensive daily brief with ALL critical/high items from 0600 IST previous day"""
    
    # Define NER states (India's Northeast Region)
    NER_STATES = ["Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura"]
    
    # ========== TIME WINDOW: 0600 IST previous day to now ==========
    from datetime import timedelta
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now_utc = datetime.now(timezone.utc)
    # 0600 IST previous day
    today_ist = now_utc.astimezone(ist).replace(hour=6, minute=0, second=0, microsecond=0)
    cutoff_ist = today_ist - timedelta(days=1)
    cutoff_utc = cutoff_ist.astimezone(timezone.utc).isoformat()
    logger.info(f"Brief time window: {cutoff_ist.isoformat()} IST to now")
    
    # ========== TITLE SIMILARITY DEDUP HELPER ==========
    def normalize_title(title):
        """Normalize title for similarity comparison"""
        import re
        t = (title or "").lower().strip()
        t = re.sub(r'[^a-z0-9\s]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    
    def extract_key_entities(title):
        """Extract key entities (names, places, orgs) for event matching"""
        import re
        t = (title or "").lower()
        # Known NER entities
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
        # Extract numbers (casualties, etc.)
        numbers = re.findall(r'\b(\d+)\s*(?:killed|injured|arrested|seized|dead)\b', t)
        for n in numbers:
            entities.add(f"count_{n}")
        return entities
    
    def is_duplicate_title(new_title, seen_titles, seen_entities_list, threshold=0.55):
        """Check if title is similar to any already seen title using word overlap AND entity matching"""
        norm_new = normalize_title(new_title)
        if not norm_new or len(norm_new) < 10:
            return False
        new_words = set(norm_new.split())
        new_entities = extract_key_entities(new_title)
        
        for i, seen in enumerate(seen_titles):
            seen_words = set(seen.split())
            if not seen_words:
                continue
            # Word overlap check
            overlap = len(new_words & seen_words)
            total = max(len(new_words), len(seen_words))
            word_sim = overlap / total if total > 0 else 0
            
            # Entity overlap check (stricter - same event if key entities match)
            seen_ents = seen_entities_list[i] if i < len(seen_entities_list) else set()
            if new_entities and seen_ents:
                ent_overlap = len(new_entities & seen_ents)
                ent_total = max(len(new_entities), len(seen_ents))
                ent_sim = ent_overlap / ent_total if ent_total > 0 else 0
                
                # If 3+ entities match (e.g. ULFA + Tinsukia + attack), it's the same event
                if ent_overlap >= 3:
                    return True
                # If 2 entities match AND word similarity is moderate
                if ent_overlap >= 2 and word_sim >= 0.35:
                    return True
            
            # Standard word similarity
            if word_sim >= threshold:
                return True
        return False
    
    # ========== 1. GET ALL CRITICAL/HIGH ITEMS since 0600 IST prev day ==========
    critical_high_items = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff_utc},
            "$or": [
                {"severity": {"$in": ["critical", "high"]}},
                {"priority_score": {"$gte": 60}}
            ]
        },
        {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).to_list(100)
    
    # Fallback: if too few items in time window, expand to most recent critical/high
    if len(critical_high_items) < 5:
        logger.info(f"Brief: Only {len(critical_high_items)} items in time window, expanding to recent critical/high")
        fallback_items = await intelligence_col.find(
            {
                "processed": True,
                "$or": [
                    {"severity": {"$in": ["critical", "high"]}},
                    {"priority_score": {"$gte": 60}}
                ]
            },
            {"_id": 0}
        ).sort([("priority_score", -1), ("published_at", -1)]).limit(30).to_list(30)
        # Merge without duplicates
        existing_urls = set(i.get("source_url") for i in critical_high_items)
        for item in fallback_items:
            if item.get("source_url") not in existing_urls:
                critical_high_items.append(item)
                existing_urls.add(item.get("source_url"))
    
    # Dedup critical/high items by title similarity
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
    
    # ========== 2. GET NER REGIONAL ITEMS with time window ==========
    ner_items = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff_utc},
            "state": {"$in": NER_STATES + ["Multiple"]},
            "$or": [
                {"priority_score": {"$gte": 30}},
                {"tags": {"$exists": True, "$ne": []}},
                {"severity": {"$in": ["critical", "high", "medium"]}}
            ]
        },
        {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).limit(80).to_list(80)
    
    # Fallback: if too few NER items in time window
    if len(ner_items) < 5:
        logger.info(f"Brief: Only {len(ner_items)} NER items in window, expanding")
        fallback_ner = await intelligence_col.find(
            {
                "processed": True,
                "state": {"$in": NER_STATES + ["Multiple"]},
                "severity": {"$in": ["critical", "high", "medium"]}
            },
            {"_id": 0}
        ).sort([("priority_score", -1), ("published_at", -1)]).limit(40).to_list(40)
        existing_urls = set(i.get("source_url") for i in ner_items)
        for item in fallback_ner:
            if item.get("source_url") not in existing_urls:
                ner_items.append(item)
                existing_urls.add(item.get("source_url"))
    
    # Dedup NER items and diversify sources
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
    
    # ========== 3. GET NATIONAL NEWS with time window ==========
    national_items = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff_utc},
            "source": {"$in": ["The Hindu - National", "NDTV India News", "News18 India", "Times of India"]},
            "state": {"$nin": NER_STATES + ["Bangladesh", "Myanmar", "Multiple"]}
        },
        {"_id": 0}
    ).sort([("priority_score", -1), ("published_at", -1)]).limit(30).to_list(30)
    
    military_national = [
        item for item in national_items
        if item.get("priority_score", 0) >= 25 or 
           item.get("severity") in ["critical", "high", "medium"] or
           any(tag in str(item.get("tags", [])).lower() for tag in ["military", "security", "cross-border", "insurgency", "foreign", "infrastructure", "defence", "border"])
    ]
    
    logger.info(f"Brief: {len(national_items)} national items, {len(military_national)} military-relevant")
    
    # ========== 4. GET INTERNATIONAL NEWS with time window ==========
    international_items = await intelligence_col.find(
        {
            "processed": True,
            "published_at": {"$gte": cutoff_utc},
            "$or": [
                {"state": {"$in": ["Bangladesh", "Myanmar"]}},
                {"countries_involved": {"$in": ["China", "Pakistan"]}},
            ],
            "state": {"$nin": NER_STATES + ["Multiple", "India", ""]},
            "$or": [
                {"priority_score": {"$gte": 35}},
                {"severity": {"$in": ["critical", "high"]}},
                {"tags": {"$in": [
                    "Military Movement", "Cross-border Movement", "Insurgency / Militancy",
                    "Foreign Influence (China/Pakistan/USA)", "Border Security", "Arms Smuggling",
                    "Drug Trafficking", "Illegal Immigration", "Bangladesh Internal Dynamics",
                    "Myanmar Instability", "Infrastructure / Logistics"
                ]}}
            ]
        },
        {"_id": 0}
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
    
    # Dedup international items
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
    
    # ========== 5. GET TWITTER FEEDS ==========
    twitter_items = await tweets_col.find({}, {"_id": 0}).sort("posted_at", -1).limit(25).to_list(25)
    
    # ========== 6. GET UPLOADED DOCUMENT INSIGHTS ==========
    uploaded_docs = await uploads_col.find({"processed": True}, {"_id": 0}).sort("uploaded_at", -1).limit(10).to_list(10)
    
    # ========== 7. GENERATE AI BRIEF ==========
    items_for_ai = deduped_critical + diverse_ner_items[:20]
    
    try:
        from ai_pipeline import generate_daily_brief_ai
        brief_data = await generate_daily_brief_ai(items_for_ai, date)
    except Exception as e:
        logger.error(f"AI brief generation failed: {e}")
        brief_data = generate_manual_brief(items_for_ai, date)
    
    # ========== 8. BUILD COMPREHENSIVE KEY DEVELOPMENTS ==========
    # Helper to build a comprehensive item dict with all analysis fields
    def build_brief_item(item):
        """Build a comprehensive brief item including analysis and pattern detection"""
        result = {
            "title": item.get("title", ""),
            "summary": item.get("ai_summary", ""),
            "source_url": item.get("source_url", ""),
            "timestamp": item.get("published_at", ""),
            "severity": item.get("severity", "medium"),
            "priority_score": item.get("priority_score", 0),
            "state": item.get("state", ""),
            "source": item.get("source", ""),
        }
        # Include analysis fields
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
        return result
    
    key_developments = []
    added_ids = set()
    
    # Add ALL critical/high items (no cap - user wants comprehensive coverage)
    for item in deduped_critical:
        item_id = item.get("id")
        if item_id and item_id not in added_ids:
            if item.get("state") in NER_STATES + ["Multiple", "Bangladesh", "Myanmar", ""]:
                key_developments.append(build_brief_item(item))
                added_ids.add(item_id)
    
    # Add diverse NER items (medium+ severity)
    for item in diverse_ner_items:
        item_id = item.get("id")
        if item_id and item_id not in added_ids:
            key_developments.append(build_brief_item(item))
            added_ids.add(item_id)
    
    brief_data["key_developments"] = key_developments
    
    # ========== 9. BUILD NATIONAL NEWS ==========
    national_deduped = []
    for item in military_national:
        title = item.get("title", "")
        if item.get("id") not in added_ids and not is_duplicate_title(title, seen_titles, seen_entities):
            national_deduped.append(build_brief_item(item))
            seen_titles.append(normalize_title(title))
            seen_entities.append(extract_key_entities(title))
    brief_data["national_news"] = national_deduped[:15]
    
    # ========== 10. BUILD INTERNATIONAL NEWS ==========
    brief_data["international_news"] = [
        {
            **build_brief_item(item),
            "countries": ", ".join(item.get("countries_involved", [])) if isinstance(item.get("countries_involved"), list) else str(item.get("countries_involved", "")),
        }
        for item in diverse_intl_items
        if item.get("id") not in added_ids
    ]
    
    # ========== 11. ADD TWITTER AND UPLOADS ==========
    # If no tweets in DB, show the accounts being monitored with links
    if not twitter_items:
        brief_data["twitter_highlights"] = [
            {
                "handle": account.get("handle", ""),
                "account_name": account.get("name", ""),
                "tweet_text": f"Visit {account.get('url', '')} for latest updates from {account.get('name', '')}",
                "tweet_url": account.get("url", ""),
                "posted_at": "",
                "category": account.get("category", "defense")
            }
            for account in TWITTER_ACCOUNTS_TO_MONITOR
        ]
        logger.info("Twitter: No tweets in DB, showing monitored accounts list")
    else:
        brief_data["twitter_highlights"] = [
            {
                "handle": tweet.get("handle", ""),
                "account_name": tweet.get("account_name", ""),
                "tweet_text": tweet.get("tweet_text", ""),
                "tweet_url": tweet.get("tweet_url", ""),
                "posted_at": tweet.get("posted_at", ""),
                "category": tweet.get("category", "defense")
            }
            for tweet in twitter_items[:20]
        ]
    
    brief_data["uploaded_insights"] = [
        {
            "filename": doc.get("filename", ""),
            "ai_analysis": doc.get("ai_analysis", doc.get("content_summary", "")),
            "region": doc.get("region", ""),
            "uploaded_at": doc.get("uploaded_at", "")
        }
        for doc in uploaded_docs[:10]
    ]
    
    # ========== 12. SAVE AND RETURN ==========
    brief = DailyBrief(**brief_data)
    doc = brief.model_dump()
    await briefs_col.update_one({"date": date}, {"$set": doc}, upsert=True)
    
    logger.info(f"Brief generated: {len(key_developments)} NER developments, {len(brief_data.get('national_news', []))} national, {len(brief_data.get('international_news', []))} international")
    
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


async def fetch_and_process_news():
    """
    Fetch and process news with rate-limit-aware batching.
    
    Strategy to handle Claude Haiku rate limits:
    1. Fetch all RSS articles but only process NEW ones (skip already in DB)
    2. Limit to MAX_ARTICLES_PER_CYCLE (default 25) per cycle to stay under rate limits
    3. Use aggressive exponential backoff on rate limit errors
    4. Store failed articles as unprocessed for retry in next cycle
    """
    from rss_fetcher import fetch_all_feeds, RSS_SOURCES
    
    # Configuration for rate limit management
    MAX_ARTICLES_PER_CYCLE = 25
    BATCH_SIZE = 3
    BATCH_PAUSE = 5
    INTER_ARTICLE_DELAY = 1.5
    
    # Update scan status
    scan_status["is_scanning"] = True
    scan_status["progress"] = 0
    scan_status["total_sources"] = len(RSS_SOURCES)
    scan_status["sources_scanned"] = 0
    scan_status["current_source"] = ""
    scan_status["articles_found"] = 0
    scan_status["relevant_found"] = 0
    scan_status["scan_log"] = []
    
    async def on_source_progress(idx, total, source_name):
        scan_status["sources_scanned"] = idx
        scan_status["current_source"] = source_name
        scan_status["progress"] = int((idx / total) * 100) if total > 0 else 0
        if source_name != "Complete":
            scan_status["scan_log"].append(source_name)
            # Keep only last 10 entries
            if len(scan_status["scan_log"]) > 10:
                scan_status["scan_log"] = scan_status["scan_log"][-10:]
    
    logger.info("=== Starting news fetch cycle ===")
    try:
        # Step 1: Fetch all RSS articles with progress tracking
        articles = await fetch_all_feeds(progress_callback=on_source_progress)
        scan_status["articles_found"] = len(articles)
        logger.info(f"Fetched {len(articles)} relevant articles from RSS feeds")

        # Step 2: Deduplicate by URL AND title similarity
        import re
        def normalize_for_dedup(title):
            t = (title or "").lower().strip()
            t = re.sub(r'[^a-z0-9\s]', '', t)
            t = re.sub(r'\s+', ' ', t).strip()
            return t
        
        def title_is_similar(t1, existing_titles, threshold=0.65):
            words1 = set(t1.split())
            for t2 in existing_titles:
                words2 = set(t2.split())
                if not words2:
                    continue
                overlap = len(words1 & words2)
                total = max(len(words1), len(words2))
                if total > 0 and overlap / total >= threshold:
                    return True
            return False
        
        # Get recent titles from DB for title-level dedup
        recent_db_items = await intelligence_col.find(
            {"processed": True},
            {"title": 1, "source_url": 1, "_id": 0}
        ).sort("fetched_at", -1).limit(500).to_list(500)
        
        existing_urls = set(item.get("source_url", "") for item in recent_db_items)
        existing_titles = [normalize_for_dedup(item.get("title", "")) for item in recent_db_items]
        
        new_articles = []
        url_dupes = 0
        title_dupes = 0
        for article in articles:
            url = article.get("source_url", "")
            title = article.get("title", "")
            if not url:
                continue
            if url in existing_urls:
                url_dupes += 1
                continue
            norm_title = normalize_for_dedup(title)
            if len(norm_title) > 10 and title_is_similar(norm_title, existing_titles):
                title_dupes += 1
                continue
            new_articles.append(article)
            existing_urls.add(url)
            existing_titles.append(norm_title)
        
        skipped = url_dupes + title_dupes
        scan_status["relevant_found"] = len(new_articles)
        logger.info(f"Deduplication: {url_dupes} URL dupes, {title_dupes} title dupes, {len(new_articles)} new articles")

        if not new_articles:
            logger.info("No new articles to process. Cycle complete.")
            scan_status["is_scanning"] = False
            scan_status["progress"] = 100
            scan_status["current_source"] = ""
            scan_status["last_scan_at"] = datetime.now(timezone.utc).isoformat()
            scan_status["last_scan_result"] = {
                "feeds_scanned": len(RSS_SOURCES),
                "total_articles": len(articles),
                "new_relevant": 0,
                "duplicates_skipped": skipped
            }
            return

        # Step 3: Limit to MAX_ARTICLES_PER_CYCLE
        if len(new_articles) > MAX_ARTICLES_PER_CYCLE:
            logger.info(f"Limiting to {MAX_ARTICLES_PER_CYCLE} articles this cycle")
            new_articles = new_articles[:MAX_ARTICLES_PER_CYCLE]

        # Step 4: Process new articles in small batches with retry
        success_count = 0
        fail_count = 0
        skip_count = 0
        rate_limit_hits = 0

        for batch_start in range(0, len(new_articles), BATCH_SIZE):
            batch = new_articles[batch_start:batch_start + BATCH_SIZE]
            batch_num = (batch_start // BATCH_SIZE) + 1
            total_batches = (len(new_articles) + BATCH_SIZE - 1) // BATCH_SIZE
            
            logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} articles)...")
            
            for article in batch:
                await asyncio.sleep(INTER_ARTICLE_DELAY)
                result, was_rate_limited = await _classify_with_retry_v2(article)
                
                if was_rate_limited:
                    rate_limit_hits += 1
                
                if result is None:
                    raw_doc = _make_raw_doc(article)
                    await intelligence_col.insert_one(raw_doc)
                    fail_count += 1
                elif result.get("is_relevant", True):
                    item = IntelligenceItem(**result)
                    doc = item.model_dump()
                    await intelligence_col.insert_one(doc)
                    success_count += 1
                else:
                    skip_count += 1

            if batch_start + BATCH_SIZE < len(new_articles):
                pause_time = BATCH_PAUSE * 2 if rate_limit_hits > 2 else BATCH_PAUSE
                logger.info(f"  Batch {batch_num} done. Success: {success_count}, Failed: {fail_count}. "
                            f"Pausing {pause_time}s...")
                await asyncio.sleep(pause_time)

        logger.info("=== Fetch cycle complete ===")
        logger.info(f"  Processed: {success_count} | Failed: {fail_count} | Not relevant: {skip_count}")
        logger.info(f"  Duplicates skipped: {skipped} | Rate limit hits: {rate_limit_hits}")
        logger.info(f"  Remaining for next cycle: {max(0, len(articles) - skipped - MAX_ARTICLES_PER_CYCLE)}")

        # Finalize scan status
        scan_status["is_scanning"] = False
        scan_status["progress"] = 100
        scan_status["current_source"] = ""
        scan_status["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        scan_status["last_scan_result"] = {
            "feeds_scanned": scan_status["total_sources"],
            "total_articles": len(articles),
            "new_relevant": success_count,
            "duplicates_skipped": skipped,
            "failed": fail_count,
            "not_relevant": skip_count
        }

    except Exception as e:
        logger.error(f"News fetch cycle failed: {e}")
        scan_status["is_scanning"] = False
        scan_status["progress"] = 100
        scan_status["current_source"] = ""
        scan_status["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        scan_status["last_scan_result"] = {"error": str(e)}


async def _classify_with_retry(article, max_retries=3):
    """Classify an article with exponential backoff retry on failure."""
    result, _ = await _classify_with_retry_v2(article, max_retries)
    return result


async def _classify_with_retry_v2(article, max_retries=4):
    """
    Classify an article with aggressive exponential backoff for rate limits.
    
    Returns: (result, was_rate_limited)
    - result: classification dict or None if all retries failed
    - was_rate_limited: True if we hit rate limits during processing
    
    Backoff strategy:
    - Normal errors: 3s, 6s, 12s, 24s (doubling)
    - Rate limit errors: 15s, 30s, 60s, 120s (aggressive)
    """
    RATE_LIMIT_INDICATORS = ['rate', '429', 'limit', 'quota', 'too many', 'throttle']
    was_rate_limited = False
    
    for attempt in range(max_retries):
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_sync_classify, article),
                timeout=60  # Increased timeout to 60s
            )
            return result, was_rate_limited  # Success
            
        except asyncio.TimeoutError:
            base_wait = 5
            wait = base_wait * (2 ** attempt)  # 5s, 10s, 20s, 40s
            logger.warning(f"  [Attempt {attempt + 1}/{max_retries}] Timeout for: "
                           f"{article.get('title', '')[:40]}... retrying in {wait}s")
            await asyncio.sleep(wait)
            
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(indicator in err_str for indicator in RATE_LIMIT_INDICATORS)
            
            if is_rate_limit:
                was_rate_limited = True
                # Aggressive backoff for rate limits: 15s, 30s, 60s, 120s
                wait = 15 * (2 ** attempt)
                logger.warning(f"  [Attempt {attempt + 1}/{max_retries}] RATE LIMIT for: "
                               f"{article.get('title', '')[:40]}... backing off {wait}s")
            else:
                # Normal backoff for other errors: 3s, 6s, 12s, 24s
                wait = 3 * (2 ** attempt)
                logger.warning(f"  [Attempt {attempt + 1}/{max_retries}] Error ({str(e)[:60]}) for: "
                               f"{article.get('title', '')[:40]}... retrying in {wait}s")
            
            await asyncio.sleep(wait)
    
    logger.error(f"  All {max_retries} retries exhausted for: {article.get('title', '')[:50]}")
    return None, was_rate_limited  # Signal failure


def _sync_classify(article):
    """Synchronous wrapper for AI classification to run in thread pool"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        from ai_pipeline import classify_and_analyze_article
        return loop.run_until_complete(classify_and_analyze_article(article))
    finally:
        loop.close()


def _make_raw_doc(article):
    return {
        "id": str(uuid.uuid4()),
        "title": article.get("title", ""),
        "source": article.get("source", "Unknown"),
        "source_url": article.get("source_url", ""),
        "published_at": article.get("published_at", datetime.now(timezone.utc).isoformat()),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_content": article.get("raw_content", "")[:5000],
        "ai_summary": article.get("raw_content", "")[:200],
        "why_it_matters": "Pending AI analysis.",
        "potential_impact": "Assessment pending.",
        "attention_level": "Monitor",
        "state": "",
        "threat_category": "",
        "severity": "low",
        "is_cross_border": article.get("region", "") in ("Bangladesh", "Myanmar"),
        "countries_involved": [article["region"]] if article.get("region") in ("Bangladesh", "Myanmar") else [],
        "processed": False,
        "tags": ["unprocessed"]
    }


async def analyze_uploaded_document(doc_id: str):
    """Analyze an uploaded document using AI"""
    doc = await uploads_col.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        logger.error(f"Document {doc_id} not found")
        return
    
    extracted_text = doc.get("extracted_text", "")
    if not extracted_text:
        logger.warning(f"No text extracted from document {doc_id}")
        return
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
        
        analysis_prompt = """You are a military intelligence analyst. Analyze this document and provide:
1. A concise summary (3-4 lines)
2. Key intelligence points relevant to India's North Eastern Region, Bangladesh, or Myanmar
3. Any security implications
4. Recommended attention level (Immediate Action Required, Priority Monitoring, Active Monitoring, Monitor)
5. Primary region affected (if identifiable): Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar, or National/International

Respond in JSON format:
{
  "summary": "...",
  "key_points": ["...", "..."],
  "security_implications": "...",
  "attention_level": "...",
  "region": "..."
}"""
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"doc-{doc_id}",
            system_message=analysis_prompt
        ).with_model("anthropic", "claude-haiku-4-5-20251001")
        
        user_message = UserMessage(text=f"Analyze this document:\n\n{extracted_text[:4000]}")
        response = await chat.send_message(user_message)
        
        response_text = str(response)
        
        # Parse JSON from response
        import json
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            analysis = json.loads(response_text[json_start:json_end])
        else:
            analysis = {"summary": response_text[:500], "region": ""}
        
        # Update document with AI analysis
        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {
                "ai_analysis": analysis.get("summary", "") + "\n\nKey Points:\n" + "\n".join(analysis.get("key_points", [])),
                "region": analysis.get("region", ""),
                "processed": True
            }}
        )
        
        logger.info(f"Successfully analyzed document {doc_id}")
        
    except Exception as e:
        logger.error(f"Error analyzing document {doc_id}: {e}")
        await uploads_col.update_one(
            {"id": doc_id},
            {"$set": {"ai_analysis": f"Analysis failed: {str(e)}", "processed": True}}
        )


async def bulk_scrape_all_feeds():
    """
    BULK SCRAPE: Fetch ALL articles from ALL RSS feeds and store them as unprocessed.
    
    This is the initial data collection phase - no AI processing.
    Articles will be gradually AI-processed by the retry scheduler.
    
    Benefits:
    - Collects maximum articles quickly (no rate limit concerns)
    - AI processing happens gradually via scheduled retries
    - Keeps LLM costs low by spreading processing over time
    """
    from rss_fetcher import fetch_all_feeds
    
    logger.info("=" * 60)
    logger.info("=== BULK SCRAPE: Fetching ALL articles from RSS feeds ===")
    logger.info("=" * 60)
    
    try:
        # Step 1: Fetch all RSS articles
        articles = await fetch_all_feeds()
        logger.info(f"Fetched {len(articles)} total articles from RSS feeds")

        # Step 2: Deduplicate — only keep articles NOT already in DB
        new_articles = []
        for article in articles:
            url = article.get("source_url", "")
            if not url:
                continue
            existing = await intelligence_col.find_one({"source_url": url}, {"_id": 1})
            if not existing:
                new_articles.append(article)
        
        skipped = len(articles) - len(new_articles)
        logger.info(f"Deduplication: {skipped} already in DB, {len(new_articles)} new articles to store")

        if not new_articles:
            logger.info("No new articles to store. Bulk scrape complete.")
            return {"stored": 0, "skipped": skipped, "total_fetched": len(articles)}

        # Step 3: Store ALL new articles as unprocessed (NO AI processing)
        stored_count = 0
        for article in new_articles:
            raw_doc = _make_raw_doc(article)
            await intelligence_col.insert_one(raw_doc)
            stored_count += 1
            
            # Log progress every 50 articles
            if stored_count % 50 == 0:
                logger.info(f"  Stored {stored_count}/{len(new_articles)} articles...")

        logger.info("=" * 60)
        logger.info("=== BULK SCRAPE COMPLETE ===")
        logger.info(f"  Stored: {stored_count} new articles (unprocessed)")
        logger.info(f"  Skipped: {skipped} duplicates")
        logger.info(f"  Total in DB: {await intelligence_col.count_documents({})}")
        logger.info(f"  Pending AI processing: {await intelligence_col.count_documents({'processed': False})}")
        logger.info("=" * 60)
        logger.info("Articles will be AI-processed gradually via scheduled retries (every 15 min)")
        
        return {"stored": stored_count, "skipped": skipped, "total_fetched": len(articles)}

    except Exception as e:
        logger.error(f"Bulk scrape failed: {e}")
        raise


async def analyze_unprocessed_items():
    """
    Retry AI classification on previously failed items with exponential backoff.
    
    This runs every 15 minutes and processes items that failed in previous cycles.
    Uses conservative limits to avoid overwhelming the API.
    """
    # Configuration for retry processing - increased for faster processing
    MAX_RETRY_PER_CYCLE = 20  # Process max 20 unprocessed items per retry cycle
    INTER_ARTICLE_DELAY = 2.5  # 2.5 seconds between articles for safety
    
    unprocessed = await intelligence_col.find(
        {"processed": False}, {"_id": 0}
    ).limit(MAX_RETRY_PER_CYCLE).to_list(MAX_RETRY_PER_CYCLE)

    if not unprocessed:
        logger.info("No unprocessed items to retry.")
        return

    total_unprocessed = await intelligence_col.count_documents({"processed": False})
    logger.info(f"=== AI Processing Cycle: {len(unprocessed)}/{total_unprocessed} unprocessed items ===")
    
    success = 0
    not_relevant = 0
    rate_limit_hits = 0
    
    for idx, item in enumerate(unprocessed):
        await asyncio.sleep(INTER_ARTICLE_DELAY)
        result, was_rate_limited = await _classify_with_retry_v2(item, max_retries=3)
        
        if was_rate_limited:
            rate_limit_hits += 1
            # If we hit too many rate limits, stop early and wait for next cycle
            if rate_limit_hits >= 3:
                logger.warning(f"  Hit {rate_limit_hits} rate limits, stopping retry cycle early. "
                               f"Will continue in next cycle.")
                break
        
        if result and result.get("is_relevant", True):
            update_fields = {k: v for k, v in result.items() if k != "_id"}
            update_fields["processed"] = True
            update_fields.pop("is_relevant", None)
            await intelligence_col.update_one(
                {"id": item["id"]},
                {"$set": update_fields}
            )
            success += 1
        elif result and not result.get("is_relevant", True):
            # Mark as processed but not relevant
            await intelligence_col.update_one(
                {"id": item["id"]},
                {"$set": {"processed": True, "tags": ["not_relevant"]}}
            )
            not_relevant += 1
        
        # Log progress every 5 articles
        if (idx + 1) % 5 == 0:
            logger.info(f"  Progress: {idx + 1}/{len(unprocessed)} | Success: {success} | Not relevant: {not_relevant}")
    
    remaining = total_unprocessed - success - not_relevant
    logger.info("=== AI Processing Complete ===")
    logger.info(f"  Processed: {success} relevant | {not_relevant} not relevant")
    logger.info(f"  Remaining unprocessed: {remaining}")
    logger.info(f"  Rate limit hits: {rate_limit_hits}")


async def initialize_sources():
    """Seed RSS sources from rss_fetcher config if not already present"""
    from rss_fetcher import RSS_SOURCES
    count = await sources_col.count_documents({})
    if count == 0:
        for source in RSS_SOURCES:
            await sources_col.insert_one({**source, "id": str(uuid.uuid4())})
        logger.info(f"Initialized {len(RSS_SOURCES)} RSS sources (regional, national, Bangladesh, Myanmar)")


@app.on_event("startup")
async def startup():
    await initialize_sources()
    # Only trigger initial fetch if DB is empty (fresh start)
    item_count = await intelligence_col.count_documents({})
    if item_count == 0:
        logger.info("Empty database — triggering initial fetch...")
        asyncio.create_task(fetch_and_process_news())
    else:
        logger.info(f"Database has {item_count} items. Skipping startup fetch (scheduler will handle next cycle).")
        # Retry any unprocessed items from previous cycles
        unprocessed = await intelligence_col.count_documents({"processed": False})
        if unprocessed > 0:
            logger.info(f"{unprocessed} unprocessed items found — triggering retry...")
            asyncio.create_task(analyze_unprocessed_items())

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(fetch_and_process_news, 'interval', minutes=30, id='news_fetch')
        scheduler.add_job(analyze_unprocessed_items, 'interval', minutes=15, id='retry_unprocessed')
        scheduler.start()
        logger.info("Background scheduler started — fetch every 30 min, retry unprocessed every 15 min")
    except Exception as e:
        logger.warning(f"Scheduler setup failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
