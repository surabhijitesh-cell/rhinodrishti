# Rhino Drishti - Comprehensive Product Report

## Executive Summary

**Rhino Drishti** is a full-stack AI-powered military intelligence aggregation and analysis platform designed for monitoring India's North Eastern Region (NER), Bangladesh, and Myanmar. The system automates news collection from **36 RSS sources** plus elite web-scraped targets, performs **tiered AI classification** (Level 1 Sifter pre-filter → Level 2 Deep Analyst 8-step military classification) using Claude Haiku 4.5 with confidence scoring and named entity extraction, detects recurring threat patterns, and generates daily intelligence briefs (auto-scheduled at 0600 IST) with PDF export. It features **real-time WebSocket updates**, **OpenAI vector embeddings for semantic search**, **adaptive scheduling** (grassroots/60min, standard/30min, established/12hr), **on-demand custom PDF briefs** with RESTRICTED headers, configurable retention windows, and critical alert acknowledgement workflows.

---

## 1. Product Overview

### 1.1 Purpose
- Real-time intelligence monitoring for armed forces and strategic analysts
- Automated collection and AI analysis of news from NER states, Bangladesh, and Myanmar
- **Tiered AI processing**: Level 1 Sifter pre-filters for border instability, refugee movements → Level 2 Deep Analyst performs 8-step military classification
- Pattern detection across regions to identify escalating threats early
- Daily intelligence brief generation (auto-scheduled 0600 IST) with cross-brief deduplication
- **Semantic search** via OpenAI vector embeddings for finding related intelligence across the corpus
- **On-demand custom PDF briefs** with filters (region, threat type, severity, time window) and RESTRICTED classification headers
- **Elite web scraping** of grassroots/hard-to-reach sources (SATP, Ukhrul Times, Frontier Myanmar) via BeautifulSoup/httpx
- Document upload facility for offline intelligence materials
- Critical alert acknowledgement workflow for high-severity items

### 1.2 Target Users
- Armed forces personnel monitoring NER security
- Intelligence analysts tracking cross-border activities
- Strategic planners assessing regional threat levels
- Defense ministry officials requiring daily situational awareness

### 1.3 Key Value Propositions
1. **36 RSS Sources + Elite Web Scraping**: PIB Defence, MHA, Assam Rifles, regional papers, Global Times, SCMP, plus NER/Bangladesh/Myanmar feeds and grassroots targets
2. **Tiered AI Classification**: Level 1 Sifter pre-filter → Level 2 8-step Deep Analyst with confidence scoring, threat trajectory, named entity extraction
3. **Semantic Search**: OpenAI `text-embedding-3-small` vector embeddings for finding contextually related intelligence items
4. **Pattern Detection Engine**: Sliding-window analysis detecting escalation across regions
5. **WebSocket Real-time Updates**: Live feed without polling, critical alert notifications
6. **Automated Daily Brief**: 0600 IST, no repeated news, pattern insights in PDF
7. **Custom On-Demand Briefs**: Filtered PDF generation with RESTRICTED classification headers
8. **Adaptive Scheduling**: Grassroots (60min), standard (30min), established (12hr), retry (15min)
9. **Multi-lingual**: Bengali, Assamese, Hindi auto-translated before AI processing
10. **Configurable Retention**: UI-adjustable news window (7-365 days)

---

## 2. Technical Architecture

### 2.1 Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Tailwind CSS + shadcn/ui + Recharts |
| Backend | FastAPI (Python 3.11) + WebSockets |
| Database | MongoDB Atlas (Motor async driver) |
| AI/LLM | Claude Haiku 4.5 via Emergent LLM Key |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensions) |
| RSS Parsing | feedparser |
| Web Scraping | BeautifulSoup4 + httpx (async) |
| PDF Generation | fpdf2 |
| Background Jobs | APScheduler (6 scheduled tasks) |
| Document Processing | PyPDF2, python-docx, openpyxl |
| Real-time | WebSocket (native FastAPI) |

### 2.2 System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          RHINO DRISHTI ELITE                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐      ┌───────────────────────────────────────┐    │
│  │  React Frontend   │◄────►│   FastAPI Backend                     │    │
│  │                   │ WS   │                                       │    │
│  │  - Dashboard      │◄────►│  ┌────────────────────────────────┐  │    │
│  │  - Intel Feed     │      │  │ APScheduler (6 Jobs)            │  │    │
│  │  - Cross-Border   │      │  │ - Grassroots Fetch (60min)      │  │    │
│  │  - Daily Brief    │      │  │ - Standard Fetch (30min)        │  │    │
│  │  - Weekly Trends  │      │  │ - Established Fetch (12hr)      │  │    │
│  │  - Patterns       │      │  │ - AI Retry (15min)              │  │    │
│  │  - Alerts         │      │  │ - Daily Brief (0600 IST)        │  │    │
│  │  - Upload Docs    │      │  │ - Embedding Backfill (6hr)      │  │    │
│  │  - Settings       │      │  └────────────────────────────────┘  │    │
│  └──────────────────┘      │                                       │    │
│                             │  ┌────────────────────────────────┐  │    │
│                             │  │ Elite Intelligence Pipeline     │  │    │
│                             │  │ 1. RSS Fetch / Web Scrape       │  │    │
│                             │  │ 2. Dedup (URL + Title)          │  │    │
│                             │  │ 3. Hard Filter                  │  │    │
│                             │  │ 4. Language Translation          │  │    │
│                             │  │ 5. Level 1 Sifter (pre-filter)  │  │    │
│                             │  │ 6. Level 2 AI Classification    │  │    │
│                             │  │ 7. Vector Embedding Generation  │  │    │
│                             │  │ 8. WebSocket Broadcast          │  │    │
│                             │  │ 9. Pattern Detection            │  │    │
│                             │  └────────────────────────────────┘  │    │
│                             │                                       │    │
│                             │  ┌────────────────────────────────┐  │    │
│                             │  │ Embedding Service (OpenAI)      │  │    │
│                             │  │ - text-embedding-3-small        │  │    │
│                             │  │ - Cosine similarity search      │  │    │
│                             │  │ - Batch backfill (50/cycle)     │  │    │
│                             │  └────────────────────────────────┘  │    │
│                             │                                       │    │
│                             └──────────────────┬────────────────────┘    │
│                                                │                         │
│                             ┌──────────────────▼────────────────────┐    │
│                             │     MongoDB Atlas                      │    │
│                             │  - intelligence_items (w/ embeddings)  │    │
│                             │  - daily_briefs                        │    │
│                             │  - intelligence_patterns               │    │
│                             │  - uploaded_documents                  │    │
│                             │  - rss_sources                         │    │
│                             │  - app_settings                        │    │
│                             └───────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Feature Inventory

### 3.1 Intelligence Pipeline

| Feature | Description | Status |
|---------|-------------|--------|
| RSS Ingestion | 36 sources across NER, National, International, Bangladesh, Myanmar | Active |
| Elite Web Scraping | BS4/httpx scraping of SATP, Ukhrul Times, Frontier Myanmar | Active |
| Adaptive Scheduling | Grassroots/60min, Standard/30min, Established/12hr, Retry/15min | Active |
| Deduplication | URL + title similarity matching (65% threshold) | Active |
| Hard Filter | Rule-based noise rejection (sports, entertainment, lifestyle) | Active |
| Language Detection | Bengali, Assamese, Hindi character analysis | Active |
| Pre-AI Translation | Translate non-English before Claude classification | Active |
| Level 1 Sifter | Pre-filter for border instability, refugee movements, militant activity | Active |
| Level 2 AI Classification | 8-step military intelligence prompt with Claude Haiku 4.5 | Active |
| Vector Embeddings | OpenAI text-embedding-3-small for semantic search | Active |
| WebSocket Broadcast | Real-time push to connected clients | Active |
| Pattern Detection | Post-processing sliding-window analysis | Active |

### 3.2 Tiered AI Classification

#### Level 1: Sifter (Pre-filter)
- Fast keyword/pattern scan for border instability, refugee movements, militant activity
- Assigns initial confidence and relevance scores
- Filters out obviously irrelevant content before expensive LLM calls
- Located in `sifter.py`

#### Level 2: Deep Analyst (8-Step Prompt)

| Step | Purpose |
|------|---------|
| 1. Relevance Filter | Strict negative filtering (sports/entertainment/lifestyle → reject) |
| 2. Priority Scoring | 0-100 score with boost rules (cross-border +10, China/Pakistan +15) |
| 3. Multi-label Classification | 19 threat tags (Military Movement, Insurgency, etc.) |
| 4. Contextual Extraction | Regions, cross-border flag, countries, actors |
| 5. Named Entity Extraction | Persons, organizations, locations |
| 6. Intelligence Output | Summary, why it matters, early warning, attention level |
| 7. Special Detection | PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, etc. |
| 8. Language Rule | All output in English regardless of input language |

**Enhanced Fields:**
- `confidence_score` (0-100): How confident the AI is in its classification
- `threat_trajectory`: ESCALATING / STABLE / DE-ESCALATING / NEW_THREAT / INDETERMINATE
- `entities`: Structured extraction of persons, organizations, locations

### 3.3 Semantic Search (Vector Embeddings)

- **Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Storage**: `embedding` field on each `intelligence_item` document
- **Search**: Cosine similarity between query embedding and stored item embeddings
- **Backfill**: Batch of 50 items per cycle, scheduled every 6 hours + manual trigger
- **Minimum Score**: 0.3 threshold for result inclusion
- **UI**: Toggle between keyword and semantic search in Intelligence Feed

### 3.4 Pattern Detection Engine

- **Collection**: `intelligence_patterns`
- **Algorithm**: Groups items by region+threat, region+actor, region+tag, crossborder keys
- **Threshold**: ≥3 events with same key = pattern detected
- **Escalation Risk**: CRITICAL (≥2 critical events), HIGH (≥5 events), MODERATE (≥4), LOW (≥3)
- **Window**: 7 days default, auto-expands to 30 days for sparse data
- **Runs**: After each fetch cycle + manual trigger via `/api/patterns/detect`

### 3.5 Daily Brief System

- **Auto-generation**: APScheduler cron at 0600 IST (0030 UTC) daily
- **Time Window**: From previous day's latest brief generation → current generation time
- **Cross-brief Dedup**: Tracks `included_item_ids` — no item appears in two consecutive briefs
- **Sections**: NER Key Developments, National News, International News, Pattern Insights, Document Insights
- **PDF Export**: Full analysis (Why it matters, Early Warning, Special Flags, Actors) + Pattern Detection section with color-coded risk levels
- **RESTRICTED Headers**: All PDFs carry RESTRICTED classification markings

### 3.6 Custom On-Demand Briefs

- **Endpoint**: POST `/api/intelligence/custom-brief`
- **Filters**: Region, threat type, severity, time window (hours), text search
- **Output**: Downloadable PDF with RESTRICTED headers
- **Content**: Filtered intelligence items with severity badges, priority scores, summaries, threat trajectories

### 3.7 Critical Alert Acknowledgement

- **Unacknowledged Alerts Panel**: Sticky panel on Dashboard showing critical/high items
- **One-click ACK**: Acknowledge button marks item as handled
- **Fields**: `acknowledged`, `acknowledged_at` on intelligence items
- **Endpoints**: GET `/api/alerts/unacknowledged`, POST `/api/intelligence/{id}/acknowledge`

### 3.8 Elite Web Scraping

- **Engine**: BeautifulSoup4 + httpx (async HTTP client)
- **Targets**: SATP (South Asia Terrorism Portal), Ukhrul Times, Frontier Myanmar
- **Dedup**: Checks against existing `source_url` before ingestion
- **Trigger**: Manual via `/api/scrape-elite` or scheduled
- **Located in**: `web_scraper.py`

### 3.9 Dashboard & UI

| Component | Description |
|-----------|-------------|
| Stat Cards | Clickable — filter by severity |
| NER Map | Geographic visualization |
| RSS Scanner | Real-time progress bar with filter/translate stats |
| WebSocket Indicator | LIVE/OFFLINE status |
| Live Feed Panel | Items appearing in real-time via WebSocket |
| Unacknowledged Alerts | Sticky panel with ACK buttons |
| Pattern Insights Widget | Top escalation warnings |
| Trend Charts | 7-day severity distribution |
| Semantic Search Toggle | Switch between keyword and vector search in Intel Feed |

### 3.10 Settings & Configuration

- **News Retention Window**: 7/14/30/60/90/180/365 days (UI toggle)
- **Dashboard Stats Cache**: 60-second in-memory TTL cache, auto-invalidated on new data or retention change
- **Pipeline Status**: Total items, processing rate, RSS sources, scheduler info

---

## 4. API Reference

### Intelligence Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/dashboard/stats | Dashboard statistics (cached 60s, retention-filtered) |
| GET | /api/intelligence | Paginated feed with filters (state, severity, threat, priority, sort) |
| GET | /api/intelligence/{id} | Single item detail |
| POST | /api/fetch-news | Trigger RSS fetch cycle |
| POST | /api/bulk-scrape | Trigger bulk article scraping |
| POST | /api/scrape-elite | Trigger elite web scraping (SATP, Ukhrul Times, Frontier Myanmar) |
| GET | /api/scan-status | Real-time scan progress |
| GET | /api/pipeline/status | Pipeline health metrics |

### Semantic Search & Embeddings
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/intelligence/semantic-search | Semantic search via vector embeddings (body: {query, limit, min_score}) |
| POST | /api/embeddings/backfill | Trigger embedding backfill for unprocessed items (batch of 50) |

### Brief Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/daily-brief | Get today's brief (auto-generates if missing) |
| GET | /api/daily-brief/pdf | Download brief as PDF |
| POST | /api/generate-brief | Force regenerate today's brief |
| POST | /api/intelligence/custom-brief | Generate custom filtered PDF brief (body: {region, threat_type, severity, hours, search, title}) |
| GET | /api/weekly-trends | Weekly trend data |

### Pattern & Alert Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/patterns | Get detected patterns |
| POST | /api/patterns/detect | Trigger pattern detection |
| GET | /api/alerts | Get critical/high alerts |
| GET | /api/alerts/unacknowledged | Unacknowledged critical/high alerts |
| POST | /api/intelligence/{id}/acknowledge | Acknowledge an alert |

### Settings Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/settings/retention | Get retention window (days) |
| PUT | /api/settings/retention | Set retention window (1-365 days) |

### Upload & WebSocket
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/upload-document | Upload PDF/Word/Excel for analysis |
| WS | /api/ws/intelligence | WebSocket real-time feed |

---

## 5. Database Schema

### intelligence_items
```json
{
  "id": "uuid",
  "title": "string",
  "source": "string",
  "source_url": "string",
  "published_at": "ISO 8601",
  "raw_content": "string",
  "state": "Assam|Manipur|...",
  "severity": "critical|high|medium|low",
  "threat_category": "string",
  "priority_score": 0-100,
  "confidence_score": 0-100,
  "threat_trajectory": "ESCALATING|STABLE|DE-ESCALATING|NEW_THREAT|INDETERMINATE",
  "tags": ["string"],
  "regions": ["string"],
  "actors": ["string"],
  "entities": {"persons": [], "organizations": [], "locations": []},
  "special_flags": ["string"],
  "early_warning_signal": "string",
  "ai_summary": "string",
  "why_it_matters": "string",
  "attention_level": "string",
  "is_cross_border": false,
  "countries_involved": ["string"],
  "acknowledged": false,
  "acknowledged_at": "ISO 8601",
  "embedding": [1536-dim float vector],
  "processed": true
}
```

### daily_briefs
```json
{
  "id": "uuid",
  "date": "YYYY-MM-DD",
  "key_developments": [{"title": "", "summary": "", "source": "", ...}],
  "national_news": [],
  "international_news": [],
  "pattern_insights": [{"region": "", "detail": "", "escalation_risk": "", ...}],
  "uploaded_insights": [],
  "included_item_ids": ["uuid"],
  "analyst_summary": "string",
  "generated_at": "ISO 8601"
}
```

### intelligence_patterns
```json
{
  "pattern_key": "region_threat:Assam:Insurgency",
  "pattern_type": "region_threat",
  "region": "Assam",
  "detail": "Insurgency / Militancy",
  "event_count": 15,
  "window_days": 30,
  "avg_priority_score": 62.3,
  "severity_breakdown": {"critical": 2, "high": 5, "medium": 8},
  "escalation_risk": "HIGH",
  "sources": ["source1", "source2"],
  "sample_titles": ["title1", "title2"],
  "detected_at": "ISO 8601"
}
```

### app_settings
```json
{
  "key": "retention_days",
  "value": 30,
  "updated_at": "ISO 8601"
}
```

---

## 6. Scheduler Configuration

| Job | Schedule | Purpose |
|-----|----------|---------|
| `fetch_grassroots_sources` | Every 60 min | Fetch from grassroots/hard-to-reach RSS sources |
| `fetch_and_process_news` | Every 30 min | Fetch standard RSS → Dedup → Filter → Translate → AI → Store |
| `fetch_established_sources` | Every 12 hr | Fetch from established/stable sources (lower frequency) |
| `analyze_unprocessed_items` | Every 15 min | Retry failed/unprocessed items (max 15 per cycle) |
| `generate_scheduled_daily_brief` | 0030 UTC (0600 IST) | Auto-generate daily intelligence brief |
| `run_embedding_backfill` | Every 6 hr | Generate OpenAI embeddings for items missing vectors (batch of 50) |

---

## 7. RSS Sources (36 Total)

### NER Regional (12)
Sentinel Assam, Northeast Now, East Mojo, Morung Express, The Sangai Express, Manipur Express, Indian Express NE, Nagaland Post, The Shillong Times, Imphal Free Press, Eastern Mirror, Arunachal24

### National (9)
The Hindu National, The Hindu International, NDTV India, Times of India, News18, PIB Press Releases, PIB Defence, MHA India

### Bangladesh (5)
The Daily Star, Dhaka Tribune, bdnews24, Prothom Alo, The Business Standard

### Myanmar (2)
The Irrawaddy, Myanmar Now

### International (4)
BBC Asia/India, Al Jazeera, Global Times, SCMP Asia

### Elite Watchlist (4 — Web Scraped)
SATP (South Asia Terrorism Portal), Ukhrul Times, Frontier Myanmar, Assam Rifles (Official)

---

## 8. File Architecture

```
/app/
├── backend/
│   ├── server.py               # FastAPI endpoints, APScheduler, WebSocket, PDF generation
│   ├── ai_pipeline.py          # Claude Haiku 4.5 integration, 8-step military prompt
│   ├── rss_fetcher.py          # RSS ingestion with elite watchlists
│   ├── sifter.py               # Level 1 Sifter pre-filter
│   ├── web_scraper.py          # BS4/httpx web scraper for elite sources
│   ├── embedding_service.py    # OpenAI text-embedding-3-small service
│   ├── intelligence_filter.py  # Hard filter + geographic matching
│   ├── requirements.txt
│   └── .env                    # MONGO_URL, EMERGENT_LLM_KEY, OPENAI_API_KEY
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── IntelligenceCard.js
│   │   ├── pages/
│   │   │   ├── Dashboard.js
│   │   │   ├── IntelligenceFeed.js   # Semantic search UI toggle
│   │   │   ├── DailyBrief.js
│   │   │   ├── DocumentUpload.js
│   │   │   └── SettingsPage.js
│   │   └── hooks/
│   │       └── useIntelligenceWS.js
│   └── .env                    # REACT_APP_BACKEND_URL
├── memory/
│   └── PRD.md
└── PRODUCT_REPORT.md
```

---

## 9. Performance & Optimization

### Caching
- Dashboard stats: 60-second in-memory cache
- Auto-invalidated on new article insertion or retention setting change

### Rate Limiting
- Max 25 articles per fetch cycle
- Batch processing: 3 articles per batch, 5s pause between batches
- 1.5s inter-article delay
- Exponential backoff on Claude API rate limits
- 0.2-0.3s delay between embedding API calls

### Noise Reduction
- Hard filter rejects sports/entertainment/lifestyle before AI processing
- Level 1 Sifter pre-filters for relevance before expensive LLM calls
- Geographic relevance matching (NER states, Bangladesh, Myanmar)
- Title similarity dedup (65% word overlap threshold)
- AI negative filtering with explicit rejection criteria
- Cross-brief deduplication (no repeated news in consecutive briefs)

### Embedding Efficiency
- Batch backfill: 50 items per cycle with rate-limiting delays
- Scheduled every 6 hours to incrementally embed new items
- Text truncated to 8000 chars before embedding to stay within token limits

---

## 10. Security & Classification

- All PDF briefs carry **RESTRICTED** classification headers and footers
- Custom briefs include **FOR AUTHORIZED PERSONNEL ONLY** distribution notice
- No public authentication layer (designed for internal/classified network deployment)
- API keys stored in environment variables, not in codebase

---

*Report generated: April 6, 2026*
*Platform version: Rhino Drishti Elite v3.0 (OSINT Upgrade)*
