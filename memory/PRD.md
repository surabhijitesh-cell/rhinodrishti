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
- [x] 32 RSS sources with keyword filtering + APScheduler (expanded from 25)
- [x] Claude Haiku 4.5 AI classification (7-step military intelligence prompt)
- [x] Dashboard with clickable stat cards, NER Map, charts
- [x] RSS Scan Progress Bar (real-time, with hide/show toggle, filter/translate stats)
- [x] Intelligence Feed with severity/state/threat filters
- [x] Daily Brief with comprehensive analysis fields
- [x] PDF export with full analysis (why_it_matters, potential_impact, early_warning, special_flags, actors)
- [x] Document Upload (PDF/Word/Excel)
- [x] Weekly Trends charts
- [x] Local language translation (Bengali/Assamese/Hindi -> English)

### Advanced Relevance Filter (2026-04-06)
- [x] Stage 1: Rule-based hard filter (HARD_REJECT/HARD_ACCEPT keywords)
- [x] Geographic relevance matching (NER states, Bangladesh, Myanmar)
- [x] Source region auto-accept (Bangladesh/Myanmar feeds)
- [x] Language detection + pre-AI translation pipeline
- [x] Filter stats in scan status and pipeline status endpoints

### Pattern Detection Engine (2026-04-06)
- [x] `intelligence_patterns` DB collection
- [x] Sliding-window analysis (7d default, auto-expand to 30d)
- [x] Entity/region/threat co-occurrence grouping
- [x] Escalation risk levels (CRITICAL/HIGH/MODERATE/LOW)
- [x] Dedicated /patterns page with pattern cards and detection trigger
- [x] Pattern insights widget on Dashboard

### Critical Alert Acknowledgement (2026-04-06)
- [x] `acknowledged`, `acknowledged_at` fields on intelligence items
- [x] GET /api/alerts/unacknowledged endpoint
- [x] POST /api/intelligence/{id}/acknowledge endpoint
- [x] Sticky unacknowledged alerts panel on Dashboard with ACK buttons

### New RSS Sources (2026-04-06)
- [x] PIB Defence, MHA India
- [x] Nagaland Post, The Shillong Times, Imphal Free Press
- [x] Global Times, SCMP Asia
- Total: 32 sources (was 25)

### Deduplication System
- [x] URL-based dedup at RSS ingestion
- [x] Title similarity matching (word overlap >=55%)
- [x] Entity-aware matching (orgs, places, events)
- [x] Source diversification (max 4 items per source in brief)

### Daily Brief Enhancements
- [x] Time window: 0600 IST previous day -> generation time
- [x] Smart fallback: expands to recent items if time window too sparse
- [x] ALL critical/high items included (no cap)
- [x] Full analysis fields in PDF

### Deployment
- [x] Vercel config (vercel.json, CI=false)
- [x] Render config (render.yaml, Procfile)
- [x] MongoDB Atlas migration (560 documents)
- [x] CORS configuration

## API Endpoints
- GET /api/dashboard/stats, GET /api/intelligence, GET /api/scan-status
- GET /api/daily-brief, GET /api/daily-brief/pdf, POST /api/generate-brief
- GET /api/weekly-trends, POST /api/fetch-news, POST /api/bulk-scrape
- POST /api/upload-document, GET /api/pipeline/status
- GET /api/alerts/unacknowledged, POST /api/intelligence/{id}/acknowledge
- GET /api/patterns, POST /api/patterns/detect

## Prioritized Backlog

### P0 (In Progress)
- (None - current batch complete)

### P1 (Upcoming)
- WebSocket real-time frontend updates (no polling needed)
- Enhance AI prompts for negative filtering + NER extraction + confidence scores
- Update Daily Brief PDF to include Pattern Insights and Escalation Warnings
- Priority score filter/sorting on Intelligence Feed

### P2 (Future)
- Semantic Search via Vector Embeddings
- Configurable News Retention Window (UI toggle)
- Caching layer for /api/dashboard/stats
- Twitter/X monitoring (paused by user)
- Email digest at 0600 IST
- Full-text search, Interactive map, Authentication

### Vercel Deployment
- User needs to verify Vercel webhook is picking up latest commits
