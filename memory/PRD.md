# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application called "Rhino Drishti" designed for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Automated collection from credible open-source news, AI-based filtering/classification, intelligence analysis engine, and professional dashboard UI.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui (Tactical Olive military theme)
- **Backend**: FastAPI + MongoDB + emergentintegrations
- **AI Layer**: Claude Haiku 4.5 via Emergent LLM Key
- **RSS Feeds**: feedparser with 25 configured sources
- **Background Scheduler**: APScheduler (30-min fetch, 15-min retry)

## User Personas
- Armed forces personnel monitoring NER security
- Intelligence analysts tracking cross-border activities
- Strategic planners assessing threat levels

## Core Requirements
- Automated RSS data collection from Indian/international news sources
- AI-based classification (threat category, severity, state, cross-border status)
- Intelligence analysis (summary, why it matters, potential impact)
- Dashboard with overview stats, NER map, charts
- Search & filter by state, threat type, severity
- Daily intelligence brief generation (AI-powered)
- Weekly trend analysis with charts
- Dark military theme with light mode toggle

## What's Been Implemented

### Phase 1 - Core Features (2026-03-20)
- [x] Backend API: 10+ endpoints (dashboard stats, intelligence CRUD, alerts, daily brief, weekly trends, sources, RSS fetch trigger)
- [x] MongoDB: intelligence_items, daily_briefs, rss_sources collections
- [x] AI Pipeline: Claude Haiku 4.5 classification and analysis
- [x] RSS Fetcher: 25 sources with keyword filtering
- [x] Background Scheduler: 30-min interval auto-fetch
- [x] Dashboard: Stats, NER SVG map, charts, recent alerts
- [x] Intelligence Feed: Filterable cards with search, state, threat type, severity filters
- [x] Cross-Border Developments: Filtered view for cross-border items
- [x] Daily Intelligence Brief: AI-generated with manual fallback
- [x] Weekly Trends: Severity trend, category analysis, state analysis charts
- [x] PDF Export for Daily Brief

### Phase 2 - Rate Limit Management (2026-03-20)
- [x] **Exponential Backoff Retry**: Aggressive backoff for rate limits (15s, 30s, 60s, 120s)
- [x] **Article Deduplication**: Skip already processed articles in each cycle
- [x] **Batch Processing**: 3 articles/batch with 5s pause between batches
- [x] **Cycle Limits**: Max 25 new articles per 30-min fetch, max 20 retry per cycle
- [x] **Bulk Scrape Endpoint**: `/api/bulk-scrape` to fetch all RSS articles without AI processing

### Phase 3 - Enhanced Daily Brief & Document Upload (2026-03-21)
- [x] **Expanded Daily Brief Structure**:
  - NER Regional News (key developments with source links)
  - National News Section (15 items from The Hindu, TOI, NDTV, etc.)
  - International News Section (15 items from BBC, Al Jazeera, Bangladesh/Myanmar sources)
  - Twitter/X Watch Section (monitoring 13 defense accounts)
  - Uploaded Document Insights
- [x] **Source Links Embedded**: All news items include clickable source URLs
- [x] **Document Upload Facility**:
  - Accepts PDF, Word (.doc, .docx), Excel (.xls, .xlsx), TXT files
  - Text extraction using PyPDF2, python-docx, openpyxl
  - AI analysis of uploaded documents
  - Insights included in daily brief
- [x] **Rhino Watermark**: Charging rhino image appears on every page of PDF brief
- [x] **Twitter Accounts Monitored**:
  - @adgpi (ADG PI - Indian Army)
  - @IAF_MCC (Indian Air Force)
  - @indiannavy (Indian Navy)
  - @DefenceMinIndia (Ministry of Defence)
  - @MEAIndia (Ministry of External Affairs)
  - @HMOIndia (Home Ministry)
  - @PMOIndia (PMO)
  - @BSF_India (BSF), @crpf (CRPF), @official_dgar (Assam Rifles), @ITBP (ITBP), @NSG

## Rate Limit Configuration
```python
MAX_ARTICLES_PER_CYCLE = 25      # Max new articles per 30-min fetch
BATCH_SIZE = 3                   # Articles per batch
BATCH_PAUSE = 5                  # Seconds between batches
INTER_ARTICLE_DELAY = 1.5        # Seconds between articles
MAX_RETRY_PER_CYCLE = 20         # Max items in 15-min retry cycle
```

## API Endpoints
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/intelligence` - Paginated intelligence items
- `GET /api/daily-brief` - Get/generate daily brief
- `POST /api/daily-brief` - Force regenerate daily brief
- `GET /api/daily-brief/pdf` - Download PDF with watermark
- `GET /api/weekly-trends` - Weekly trend data
- `GET /api/twitter-accounts` - List monitored Twitter accounts
- `GET /api/twitter-feeds` - Get Twitter feeds
- `POST /api/upload-document` - Upload PDF/Word/Excel
- `GET /api/uploaded-documents` - List uploaded documents
- `DELETE /api/uploaded-documents/{id}` - Delete document
- `POST /api/bulk-scrape` - Bulk fetch all RSS without AI processing
- `POST /api/fetch-news` - Fetch and AI-process news
- `POST /api/analyze-news` - Retry unprocessed items

## Prioritized Backlog

### P0 (Done)
- All core features implemented and tested
- Rate limit management with exponential backoff
- Enhanced daily brief with national/international sections
- Document upload facility
- PDF watermark

### P1 (Next Phase)
- **Twitter API Integration**: Real-time tweet fetching from defense accounts
- Email/WhatsApp notifications for critical alerts
- Full-text search with MongoDB text indexes
- Manual override tagging for intelligence items
- User authentication (JWT or Google OAuth)

### P2 (Future)
- Interactive map with react-simple-maps (replacing SVG)
- Keyword heatmap visualization
- Multi-language support (Hindi, Assamese, Bengali)
- Cross-source validation for misinformation detection
- Real-time WebSocket updates
