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
- [x] GET /api/alerts/unacknowledged endpoint
- [x] POST /api/intelligence/{id}/acknowledge endpoint
- [x] Sticky unacknowledged alerts panel on Dashboard with ACK buttons

### Daily Brief Enhancements (2026-04-06)
- [x] Cross-brief dedup: tracks `included_item_ids`, excludes from next brief
- [x] Time window: "since last brief generation" (not fixed 24h)
- [x] Twitter section completely removed
- [x] Pattern Insights / Escalation Warnings section added
- [x] PDF includes Pattern Detection section with color-coded risk levels
- [x] Fallback window for sparse data

### Intelligence Feed Enhancements (2026-04-06)
- [x] Priority score filter (80+/60+/40+/20+)
- [x] Sort by date or priority score
- [x] Backend: min_priority, sort_by, sort_order query params

### Deployment
- [x] Vercel config (vercel.json, CI=false)
- [x] Render config (render.yaml, Procfile)
- [x] MongoDB Atlas migration
- [x] CORS configuration

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
- Email digest at 0600 IST
- Full-text search, Interactive map, Authentication

### Vercel Deployment
- User needs to verify Vercel webhook is picking up latest commits
