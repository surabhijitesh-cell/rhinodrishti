# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Features automated RSS collection, AI classification using 7-step military intelligence framework, comprehensive daily briefs, and professional dashboard.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI + MongoDB + emergentintegrations
- **AI**: Claude Haiku 4.5 via Emergent LLM Key
- **Deployment**: Vercel (frontend) + Render (backend) + MongoDB Atlas

## What's Been Implemented

### Core Features
- [x] 25 RSS sources with keyword filtering + APScheduler
- [x] Claude Haiku 4.5 AI classification (7-step military intelligence prompt)
- [x] Dashboard with clickable stat cards → filtered Intelligence Feed
- [x] RSS Scan Progress Bar (real-time, with hide/show toggle)
- [x] Intelligence Feed with severity/state/threat filters
- [x] Daily Brief with comprehensive analysis fields
- [x] PDF export with full analysis (why_it_matters, potential_impact, early_warning, special_flags, actors)
- [x] Document Upload (PDF/Word/Excel)
- [x] Weekly Trends charts
- [x] Local language translation (Bengali/Assamese/Hindi → English)

### Deduplication System (2026-03-28)
- [x] URL-based dedup at RSS ingestion
- [x] Title similarity matching (word overlap ≥55%)
- [x] Entity-aware matching (orgs, places, events) — catches same-event stories from different agencies
- [x] Source diversification (max 4 items per source in brief)

### Daily Brief Enhancements (2026-03-28)
- [x] Time window: 0600 IST previous day → generation time
- [x] Smart fallback: expands to recent items if time window too sparse
- [x] ALL critical/high items included (no cap)
- [x] Full analysis fields: why_it_matters, potential_impact, early_warning, special_flags, actors, attention_level
- [x] PDF updated with comprehensive rendering method

### Deployment (2026-03-28)
- [x] Vercel config (vercel.json, CI=false)
- [x] Render config (render.yaml, Procfile)
- [x] MongoDB Atlas migration (560 documents)
- [x] CORS configuration
- [x] Deployment guide (DEPLOYMENT_GUIDE.md)

## API Endpoints
- GET /api/dashboard/stats, GET /api/intelligence, GET /api/scan-status
- GET /api/daily-brief, GET /api/daily-brief/pdf, POST /api/generate-brief
- GET /api/weekly-trends, POST /api/fetch-news, POST /api/bulk-scrape
- POST /api/upload-document, GET /api/pipeline/status

## Prioritized Backlog
### P1
- Fix Vercel stale commit (delete + reimport project)
- Add more National Indian news sources

### P2
- Twitter/X monitoring, Email digest at 0600 IST
- Priority score filter/sorting on Intelligence Feed
- Full-text search, Interactive map, Authentication
