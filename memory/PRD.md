# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Features automated RSS collection, AI classification using 7-step military intelligence framework, comprehensive daily briefs, and professional dashboard. Transform into a HIGH-PRECISION, LOW-NOISE, REAL-TIME INTELLIGENCE PLATFORM via an 11-Phase Architectural Upgrade.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui + Recharts
- **Backend**: FastAPI + MongoDB + emergentintegrations + APScheduler
- **AI**: Claude Haiku 4.5 via Emergent LLM Key
- **Deployment**: Vercel (frontend) + Render (backend) + MongoDB Atlas

## What's Been Implemented

### Core Features
- [x] 32 RSS sources with keyword filtering + APScheduler
- [x] Claude Haiku 4.5 AI classification (7-step military intelligence prompt)
- [x] Dashboard with clickable stat cards, NER Map, charts
- [x] RSS Scan Progress Bar (real-time, with filter/translate stats)
- [x] Intelligence Feed with severity/state/threat/priority filters + sort
- [x] Daily Brief with comprehensive analysis fields
- [x] PDF export with full analysis + pattern insights
- [x] Document Upload (PDF/Word/Excel)
- [x] Weekly Trends charts
- [x] Local language translation (Bengali/Assamese/Hindi -> English)

### Advanced Relevance Filter (2026-04-06)
- [x] Stage 1: Rule-based hard filter (HARD_REJECT/HARD_ACCEPT keywords)
- [x] Geographic relevance matching (NER states, Bangladesh, Myanmar)
- [x] Language detection + pre-AI translation pipeline
- [x] Filter stats in scan status and pipeline status endpoints

### Pattern Detection Engine (2026-04-06)
- [x] `intelligence_patterns` DB collection
- [x] Sliding-window analysis (7d default, auto-expand to 30d)
- [x] Escalation risk levels (CRITICAL/HIGH/MODERATE/LOW)
- [x] Dedicated /patterns page with detection trigger
- [x] Pattern insights widget on Dashboard
- [x] Pattern insights included in Daily Brief and PDF

### Critical Alert Acknowledgement (2026-04-06)
- [x] `acknowledged`, `acknowledged_at` fields on intelligence items
- [x] Sticky unacknowledged alerts panel on Dashboard with ACK buttons

### Daily Brief Automation (2026-04-06)
- [x] Auto-generated at 0600 IST daily via APScheduler CronTrigger
- [x] Time window: previous day's latest brief → current generation time
- [x] Cross-brief dedup: tracks `included_item_ids`, no repeats
- [x] Twitter section completely removed
- [x] Pattern Insights / Escalation Warnings in brief + PDF
- [x] Fallback window for sparse data (first-ever brief)

### Intelligence Feed Enhancements (2026-04-06)
- [x] Priority score filter (80+/60+/40+/20+)
- [x] Sort by date or priority score

### Scheduler Jobs
- `fetch_and_process_news` — every 30 min
- `analyze_unprocessed_items` — every 15 min
- `generate_scheduled_daily_brief` — cron at 0030 UTC (0600 IST)

## API Endpoints
- GET /api/dashboard/stats, GET /api/intelligence, GET /api/scan-status
- GET /api/daily-brief, GET /api/daily-brief/pdf, POST /api/generate-brief
- GET /api/weekly-trends, POST /api/fetch-news, POST /api/bulk-scrape
- POST /api/upload-document, GET /api/pipeline/status
- GET /api/alerts/unacknowledged, POST /api/intelligence/{id}/acknowledge
- GET /api/patterns, POST /api/patterns/detect

## Prioritized Backlog

### P1 (Upcoming)
- WebSocket real-time frontend updates (replace polling)
- Enhanced AI prompts: negative filtering + NER extraction + confidence scores
- Semantic Search via Vector Embeddings

### P2 (Future)
- Configurable News Retention Window (UI toggle)
- Caching layer for /api/dashboard/stats
- Email digest distribution at 0600 IST
- Full-text search, Interactive map, Authentication
