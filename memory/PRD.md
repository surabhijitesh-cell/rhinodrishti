# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Transform into a HIGH-PRECISION, LOW-NOISE, REAL-TIME INTELLIGENCE PLATFORM via an 11-Phase Architectural Upgrade.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui + Recharts
- **Backend**: FastAPI + MongoDB + emergentintegrations + APScheduler + WebSockets
- **AI**: Claude Haiku 4.5 via Emergent LLM Key
- **Deployment**: Vercel (frontend) + Render (backend) + MongoDB Atlas

## What's Been Implemented

### Core Features
- [x] 32 RSS sources with keyword filtering + APScheduler
- [x] Claude Haiku 4.5 AI classification (8-step military intelligence prompt)
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

### Pattern Detection Engine (2026-04-06)
- [x] `intelligence_patterns` DB collection
- [x] Sliding-window analysis + escalation risk levels
- [x] /patterns page + Dashboard widget + Brief/PDF integration

### Critical Alert Acknowledgement (2026-04-06)
- [x] Sticky unacknowledged alerts panel on Dashboard with ACK buttons

### Daily Brief Automation (2026-04-06)
- [x] Auto-generated at 0600 IST daily via APScheduler CronTrigger
- [x] Cross-brief dedup: tracks included_item_ids, no repeats
- [x] Twitter section completely removed
- [x] Pattern Insights / Escalation Warnings in brief + PDF

### Enhanced AI Classification (2026-04-06)
- [x] Stricter negative filtering (explicit reject for sports/entertainment/lifestyle)
- [x] Confidence score (0-100) in AI output
- [x] Threat trajectory (ESCALATING/STABLE/DE-ESCALATING/NEW_THREAT)
- [x] Named Entity Extraction (persons, organizations, locations)
- [x] 8-step classification prompt (was 7-step)

### WebSocket Real-time Updates (2026-04-06)
- [x] WebSocket endpoint at /api/ws/intelligence
- [x] ConnectionManager with auto-reconnect
- [x] Broadcasts new_item and critical_alert messages
- [x] Dashboard LIVE/OFFLINE indicator
- [x] Live feed panel showing items as they arrive
- [x] Auto-refresh stats when new WS items arrive

### Scheduler Jobs
- `fetch_and_process_news` — every 30 min
- `analyze_unprocessed_items` — every 15 min
- `generate_scheduled_daily_brief` — cron at 0030 UTC (0600 IST)

## Prioritized Backlog

### P1 (Upcoming)
- Semantic Search via Vector Embeddings (cost analysis pending user decision)

### P2 (Future)
- Configurable News Retention Window (UI toggle)
- Caching layer for /api/dashboard/stats
- Email digest distribution at 0600 IST
- Full-text search, Interactive map, Authentication
