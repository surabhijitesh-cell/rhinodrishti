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

# Twitter/X accounts to monitor for defense updates
TWITTER_ACCOUNTS_TO_MONITOR = [
    {"handle": "@adaborangga", "name": "ADG PI - Indian Army", "category": "defense"},
    {"handle": "@IAF_MCC", "name": "Indian Air Force", "category": "defense"},
    {"handle": "@indiannavy", "name": "Indian Navy", "category": "defense"},
    {"handle": "@SpsHanada", "name": "SPS Hanada - Defense Expert", "category": "defense"},
    {"handle": "@DefenceMinIndia", "name": "Ministry of Defence", "category": "government"},
    {"handle": "@MEAIndia", "name": "Ministry of External Affairs", "category": "government"},
    {"handle": "@HMOIndia", "name": "Home Ministry", "category": "government"},
    {"handle": "@PMOIndia", "name": "Prime Minister's Office", "category": "government"},
    {"handle": "@BSaborBSF", "name": "Border Security Force", "category": "paramilitary"},
    {"handle": "@craborCRPF", "name": "CRPF", "category": "paramilitary"},
    {"handle": "@official_dgar", "name": "Assam Rifles", "category": "paramilitary"},
    {"handle": "@ABORAITBP", "name": "ITBP", "category": "paramilitary"},
    {"handle": "@NaborSSG", "name": "NSG", "category": "paramilitary"},
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
    attention_level: str = "Monitor"
    state: str = ""
    threat_category: str = ""
    severity: str = "medium"
    is_cross_border: bool = False
    countries_involved: List[str] = []
    processed: bool = True
    tags: List[str] = []


class DailyBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    # NER Regional News
    key_developments: List[str] = []
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
    limit: int = Query(20, ge=1, le=100)
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
    """Generate and return a PDF of the daily intelligence brief"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief = await briefs_col.find_one({"date": date}, {"_id": 0})
    if not brief:
        brief = await generate_brief_for_date(date)

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


def generate_brief_pdf(brief: dict, date: str, total: int, critical: int, high: int) -> bytes:
    """Generate a professional PDF for the daily intelligence brief with watermark"""
    from fpdf import FPDF
    from PIL import Image
    import os
    
    # Watermark path
    watermark_path = os.path.join(ROOT_DIR, 'assets', 'rhino_watermark.jpg')
    has_watermark = os.path.exists(watermark_path)

    class BriefPDF(FPDF):
        def header(self):
            # Add watermark on every page
            if has_watermark:
                self.set_alpha(0.08)  # Very light watermark
                self.image(watermark_path, x=30, y=60, w=150)
                self.set_alpha(1.0)
            
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
        
        def set_alpha(self, alpha):
            """Set transparency (alpha) - requires fpdf2"""
            try:
                self.set_draw_color(255, 255, 255)
            except:
                pass

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
            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(40, 60, 80)
            clean_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.multi_cell(0, 5, f'{index}. {clean_title}')
            
            if summary:
                self.set_font('Helvetica', '', 8)
                self.set_text_color(60, 60, 60)
                clean_summary = summary.encode('latin-1', 'replace').decode('latin-1')[:300]
                self.multi_cell(0, 4, clean_summary)
            
            if source_url:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(70, 100, 150)
                self.cell(0, 4, f'[Source: {source_url[:80]}...]', new_x="LMARGIN", new_y="NEXT", link=source_url)
            
            if timestamp:
                self.set_font('Helvetica', 'I', 7)
                self.set_text_color(120, 120, 120)
                self.cell(0, 4, f'Time: {timestamp}', new_x="LMARGIN", new_y="NEXT")
            
            self.ln(2)

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
        for i, dev in enumerate(developments[:10], 1):
            if isinstance(dev, dict):
                pdf.news_item_with_link(i, dev.get('title', ''), dev.get('summary', ''), dev.get('source_url', ''), dev.get('timestamp', ''))
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
                pdf.news_item_with_link(i, news.get('title', ''), news.get('summary', ''), news.get('source_url', ''), news.get('timestamp', ''))
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
                pdf.news_item_with_link(i, news.get('title', ''), news.get('summary', ''), news.get('source_url', ''), news.get('timestamp', ''))
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
        raise HTTPException(status_code=400, detail=f"File type not supported. Allowed: PDF, Word, Excel, TXT")
    
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
    from datetime import timedelta
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
    """Generate comprehensive daily brief with NER, National, International news and Twitter feeds"""
    
    # Get NER regional items
    ner_items = await intelligence_col.find(
        {"state": {"$in": MONITORED_REGIONS + ["Multiple", ""]}},
        {"_id": 0}
    ).sort("published_at", -1).limit(50).to_list(50)
    
    # Get national news (from national sources or tagged as national)
    national_items = await intelligence_col.find(
        {"$or": [
            {"source": {"$regex": "hindu|times of india|ndtv|news18|indian express|pib", "$options": "i"}},
            {"tags": "national"}
        ]},
        {"_id": 0}
    ).sort("published_at", -1).limit(20).to_list(20)
    
    # Get international news
    international_items = await intelligence_col.find(
        {"$or": [
            {"source": {"$regex": "bbc|al jazeera|reuters", "$options": "i"}},
            {"tags": "international"},
            {"countries_involved": {"$in": ["China", "Pakistan", "USA"]}}
        ]},
        {"_id": 0}
    ).sort("published_at", -1).limit(20).to_list(20)
    
    # Get Twitter feeds
    twitter_items = await tweets_col.find({}, {"_id": 0}).sort("posted_at", -1).limit(25).to_list(25)
    
    # Get uploaded document insights
    uploaded_docs = await uploads_col.find({"processed": True}, {"_id": 0}).sort("uploaded_at", -1).limit(10).to_list(10)

    try:
        from ai_pipeline import generate_daily_brief_ai
        brief_data = await generate_daily_brief_ai(ner_items, date)
    except Exception as e:
        logger.error(f"AI brief generation failed: {e}")
        brief_data = generate_manual_brief(ner_items, date)
    
    # Add national news with source links
    brief_data["national_news"] = [
        {
            "title": item.get("title", ""),
            "summary": item.get("ai_summary", item.get("raw_content", "")[:200]),
            "source_url": item.get("source_url", ""),
            "timestamp": item.get("published_at", ""),
            "source": item.get("source", "")
        }
        for item in national_items[:15]
    ]
    
    # Add international news with source links
    brief_data["international_news"] = [
        {
            "title": item.get("title", ""),
            "summary": item.get("ai_summary", item.get("raw_content", "")[:200]),
            "source_url": item.get("source_url", ""),
            "timestamp": item.get("published_at", ""),
            "source": item.get("source", ""),
            "countries": item.get("countries_involved", [])
        }
        for item in international_items[:15]
    ]
    
    # Add Twitter highlights
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
    
    # Add uploaded document insights
    brief_data["uploaded_insights"] = [
        {
            "filename": doc.get("filename", ""),
            "ai_analysis": doc.get("ai_analysis", doc.get("content_summary", "")),
            "region": doc.get("region", ""),
            "uploaded_at": doc.get("uploaded_at", "")
        }
        for doc in uploaded_docs[:10]
    ]
    
    # Update key_developments to include source links
    key_developments_with_links = []
    for item in ner_items[:10]:
        key_developments_with_links.append({
            "title": item.get("title", ""),
            "summary": item.get("ai_summary", ""),
            "source_url": item.get("source_url", ""),
            "timestamp": item.get("published_at", ""),
            "severity": item.get("severity", "medium"),
            "state": item.get("state", "")
        })
    brief_data["key_developments"] = key_developments_with_links

    brief = DailyBrief(**brief_data)
    doc = brief.model_dump()
    await briefs_col.update_one({"date": date}, {"$set": doc}, upsert=True)
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
    from rss_fetcher import fetch_all_feeds
    
    # Configuration for rate limit management
    MAX_ARTICLES_PER_CYCLE = 25  # Process max 25 new articles per 30-min cycle
    BATCH_SIZE = 3  # Smaller batches = less burst, fewer rate limits
    BATCH_PAUSE = 5  # 5 seconds between batches (was 2)
    INTER_ARTICLE_DELAY = 1.5  # 1.5 seconds between articles in same batch (was 0.2)
    
    logger.info("=== Starting news fetch cycle ===")
    try:
        # Step 1: Fetch all RSS articles
        articles = await fetch_all_feeds()
        logger.info(f"Fetched {len(articles)} relevant articles from RSS feeds")

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
        logger.info(f"Deduplication: {skipped} already in DB, {len(new_articles)} new articles to process")

        if not new_articles:
            logger.info("No new articles to process. Cycle complete.")
            return

        # Step 3: Limit to MAX_ARTICLES_PER_CYCLE to avoid rate limits
        if len(new_articles) > MAX_ARTICLES_PER_CYCLE:
            logger.info(f"Limiting to {MAX_ARTICLES_PER_CYCLE} articles this cycle "
                        f"({len(new_articles) - MAX_ARTICLES_PER_CYCLE} deferred to next cycle)")
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
                await asyncio.sleep(INTER_ARTICLE_DELAY)  # Rate limit spacing
                result, was_rate_limited = await _classify_with_retry_v2(article)
                
                if was_rate_limited:
                    rate_limit_hits += 1
                
                if result is None:
                    # All retries exhausted — store as unprocessed for next cycle
                    raw_doc = _make_raw_doc(article)
                    await intelligence_col.insert_one(raw_doc)
                    fail_count += 1
                elif result.get("is_relevant", True):
                    item = IntelligenceItem(**result)
                    doc = item.model_dump()
                    await intelligence_col.insert_one(doc)
                    success_count += 1
                else:
                    skip_count += 1  # AI said not relevant

            # Pause between batches to avoid rate limits
            if batch_start + BATCH_SIZE < len(new_articles):
                # Dynamic pause: if we hit rate limits, wait longer
                pause_time = BATCH_PAUSE * 2 if rate_limit_hits > 2 else BATCH_PAUSE
                logger.info(f"  Batch {batch_num} done. Success: {success_count}, Failed: {fail_count}. "
                            f"Pausing {pause_time}s...")
                await asyncio.sleep(pause_time)

        logger.info(f"=== Fetch cycle complete ===")
        logger.info(f"  Processed: {success_count} | Failed: {fail_count} | Not relevant: {skip_count}")
        logger.info(f"  Duplicates skipped: {skipped} | Rate limit hits: {rate_limit_hits}")
        logger.info(f"  Remaining for next cycle: {max(0, len(articles) - skipped - MAX_ARTICLES_PER_CYCLE)}")

    except Exception as e:
        logger.error(f"News fetch cycle failed: {e}")


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
        logger.info(f"=== BULK SCRAPE COMPLETE ===")
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
    logger.info(f"=== AI Processing Complete ===")
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
