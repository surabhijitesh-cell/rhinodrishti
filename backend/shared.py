"""
Shared state, models, and utilities used across all routers.
"""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import WebSocket
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ============================================================
# Database
# ============================================================
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

intelligence_col = db.intelligence_items
briefs_col = db.daily_briefs
sources_col = db.rss_sources
uploads_col = db.uploaded_documents
tweets_col = db.twitter_feeds
national_news_col = db.national_news
international_news_col = db.international_news
patterns_col = db.intelligence_patterns
feedback_col = db.intelligence_feedback
training_col = db.training_data
activity_log_col = db.training_activity_log

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

# ============================================================
# Constants
# ============================================================
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

TWITTER_ACCOUNTS_TO_MONITOR = [
    {"handle": "@adgpi", "name": "ADG PI - Indian Army", "category": "defense", "url": "https://twitter.com/adgpi"},
    {"handle": "@IAF_MCC", "name": "Indian Air Force", "category": "defense", "url": "https://twitter.com/IAF_MCC"},
    {"handle": "@indiannavy", "name": "Indian Navy", "category": "defense", "url": "https://twitter.com/indiannavy"},
    {"handle": "@easterncomd", "name": "Eastern Command - Indian Army", "category": "defense", "url": "https://twitter.com/easterncomd"},
    {"handle": "@DefenceMinIndia", "name": "Ministry of Defence", "category": "government", "url": "https://twitter.com/DefenceMinIndia"},
    {"handle": "@MEAIndia", "name": "Ministry of External Affairs", "category": "government", "url": "https://twitter.com/MEAIndia"},
    {"handle": "@HMOIndia", "name": "Home Ministry", "category": "government", "url": "https://twitter.com/HMOIndia"},
    {"handle": "@PMOIndia", "name": "Prime Minister's Office", "category": "government", "url": "https://twitter.com/PMOIndia"},
    {"handle": "@BSF_India", "name": "Border Security Force", "category": "paramilitary", "url": "https://twitter.com/BSF_India"},
    {"handle": "@crpf_sab", "name": "CRPF", "category": "paramilitary", "url": "https://twitter.com/crpf_sab"},
    {"handle": "@official_dgar", "name": "Assam Rifles", "category": "paramilitary", "url": "https://twitter.com/official_dgar"},
    {"handle": "@ITBP_official", "name": "ITBP", "category": "paramilitary", "url": "https://twitter.com/ITBP_official"},
]

# ============================================================
# Pydantic Models
# ============================================================
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
    priority_score: int = 30
    confidence_score: int = 70
    threat_trajectory: str = "INDETERMINATE"
    regions: List[str] = []
    actors: List[str] = []
    special_flags: List[str] = []
    early_warning_signal: str = ""
    original_title: Optional[str] = None
    entities: Dict = Field(default_factory=lambda: {"persons": [], "organizations": [], "locations": []})
    sifter_level: int = 1
    sifter_triggers: List[str] = []
    relationships: List[Dict] = []
    embedding: Optional[List[float]] = Field(default=None, exclude=True)


class DailyBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    key_developments: List[Dict] = []
    state_highlights: Dict[str, str] = {}
    cross_border_insights: str = ""
    cross_border_bangladesh: List[Dict] = []
    cross_border_myanmar: List[Dict] = []
    analyst_summary: str = ""
    national_news: List[Dict] = []
    international_news: List[Dict] = []
    pattern_insights: List[Dict] = []
    uploaded_insights: List[Dict] = []
    included_item_ids: List[str] = []
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


# ============================================================
# WebSocket Connection Manager
# ============================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)

ws_manager = ConnectionManager()

# ============================================================
# Shared Mutable State
# ============================================================
scan_status = {
    "is_scanning": False,
    "progress": 0,
    "total_sources": 0,
    "current_source": "",
    "sources_scanned": 0,
    "articles_found": 0,
    "relevant_found": 0,
    "filtered_out": 0,
    "translated": 0,
    "last_scan_at": None,
    "last_scan_result": None,
    "scan_log": [],
}

_stats_cache = {
    "data": None,
    "expires_at": None,
}
STATS_CACHE_TTL = 60


def invalidate_stats_cache():
    _stats_cache["data"] = None
    _stats_cache["expires_at"] = None


def has_non_latin_chars(text: str) -> bool:
    if not text:
        return False
    for char in text:
        code = ord(char)
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
        return text.encode('ascii', 'ignore').decode('ascii') or "[Non-English content]"
