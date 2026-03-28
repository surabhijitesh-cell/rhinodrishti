# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application called "Rhino Drishti" designed for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Automated collection from credible open-source news, AI-based filtering/classification, intelligence analysis engine, and professional dashboard UI.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui (Tactical Olive military theme)
- **Backend**: FastAPI + MongoDB + emergentintegrations
- **AI Layer**: Claude Haiku 4.5 via Emergent LLM Key
- **RSS Feeds**: feedparser with 25 configured sources
- **Background Scheduler**: APScheduler (30-min fetch, 15-min retry)
- **Deployment**: Vercel (frontend) + Render (backend) + MongoDB Atlas (database)

## What's Been Implemented

### Phase 1 - Core Features (2026-03-20)
- [x] Backend API: 10+ endpoints
- [x] MongoDB: intelligence_items, daily_briefs, rss_sources collections
- [x] AI Pipeline: Claude Haiku 4.5 classification and analysis
- [x] RSS Fetcher: 25 sources with keyword filtering
- [x] Background Scheduler: 30-min interval auto-fetch
- [x] Dashboard: Stats, NER SVG map, charts, recent alerts
- [x] Intelligence Feed: Filterable cards with search, state, threat type, severity filters
- [x] Daily Intelligence Brief: AI-generated with PDF export
- [x] Weekly Trends: Severity trend, category analysis, state analysis charts

### Phase 2 - Rate Limit & Bulk Processing (2026-03-20)
- [x] Exponential Backoff Retry
- [x] Article Deduplication
- [x] Batch Processing (3 articles/batch)
- [x] Bulk Scrape Endpoint

### Phase 3 - Enhanced Brief & Document Upload (2026-03-21)
- [x] Expanded Daily Brief (NER/National/International sections)
- [x] Document Upload Facility (PDF/Word/Excel/TXT)
- [x] Rhino Watermark on PDF
- [x] Local Language Translation (Bengali/Assamese/Hindi)
- [x] 7-step Military Intelligence AI Prompt

### Phase 4 - Deployment & Dashboard Enhancements (2026-03-28)
- [x] Deployment config: Vercel (frontend) + Render (backend) + MongoDB Atlas
- [x] Clickable stat cards → navigate to filtered Intelligence Feed
- [x] RSS Scan Progress Bar: real-time progress, source names, IST timestamps, scan results
- [x] Hide/show toggle for scan progress bar
- [x] Daily Brief React error #31 fix (safeStr helper)
- [x] Data migration from Emergent preview to MongoDB Atlas (560 documents)
- [x] CORS configuration for cross-origin Vercel↔Render communication

## API Endpoints
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/intelligence` - Paginated intelligence items (supports severity, state, threat_type, search filters)
- `GET /api/daily-brief` - Get/generate daily brief
- `GET /api/daily-brief/pdf` - Download PDF with watermark
- `GET /api/weekly-trends` - Weekly trend data
- `GET /api/scan-status` - Real-time RSS scan progress
- `POST /api/fetch-news` - Trigger RSS fetch + AI processing
- `POST /api/bulk-scrape` - Bulk fetch all RSS without AI
- `POST /api/analyze-news` - Retry unprocessed items
- `POST /api/upload-document` - Upload PDF/Word/Excel
- `GET /api/pipeline/status` - Pipeline health status

## Prioritized Backlog

### P1 (Next)
- Add more National Indian news sources to RSS fetcher
- Priority score filter/sorting on Intelligence Feed

### P2 (Future)
- Twitter/X monitoring integration (paused by user)
- Email/WhatsApp notifications for critical alerts
- Full-text search with MongoDB text indexes
- Interactive map with react-simple-maps
- User authentication (JWT or Google OAuth)
- Real-time WebSocket updates
- Email digest (auto-send Daily Brief PDF)
