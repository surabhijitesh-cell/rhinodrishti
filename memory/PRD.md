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
- [x] Exponential Backoff Retry: Aggressive backoff for rate limits
- [x] Article Deduplication: Skip already processed articles
- [x] Batch Processing: 3 articles/batch with 5s pause
- [x] Cycle Limits: Max 25 new articles per 30-min fetch
- [x] Bulk Scrape Endpoint: /api/bulk-scrape

### Phase 3 - Enhanced Daily Brief & Document Upload (2026-03-21)
- [x] Expanded Daily Brief Structure (NER/National/International sections)
- [x] Source Links Embedded in all news items
- [x] Document Upload Facility (PDF/Word/Excel/TXT)
- [x] Rhino Watermark on PDF brief
- [x] Twitter Accounts Monitored (13 defense accounts listed)
- [x] Local Language Translation (Bengali/Assamese/Hindi to English)
- [x] 7-step Military Intelligence AI Classification Prompt

### Session 2026-03-23
- [x] Environment recovery verification - all services healthy
- [x] Full application preview generated across all pages
- [x] Storage projection analysis (~200MB for 1 year)

## Rate Limit Configuration
```python
MAX_ARTICLES_PER_CYCLE = 25
BATCH_SIZE = 3
BATCH_PAUSE = 5
INTER_ARTICLE_DELAY = 1.5
MAX_RETRY_PER_CYCLE = 20
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
- `POST /api/bulk-scrape` - Bulk fetch all RSS without AI
- `POST /api/fetch-news` - Fetch and AI-process news
- `POST /api/analyze-news` - Retry unprocessed items
- `GET /api/pipeline/status` - Pipeline status

## Prioritized Backlog

### P1 (Next)
- Priority score filter on Dashboard/Intelligence Feed
- More National Indian news sources in RSS fetcher
- Twitter/X monitoring integration (paused by user)

### P2 (Future)
- Email/WhatsApp notifications for critical alerts
- Full-text search with MongoDB text indexes
- Interactive map with react-simple-maps
- User authentication (JWT or Google OAuth)
- Real-time WebSocket updates
- Keyword heatmap visualization
- Cross-source validation for misinformation detection
