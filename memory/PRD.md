# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Transform into a HIGH-PRECISION, LOW-NOISE, REAL-TIME INTELLIGENCE PLATFORM via an Elite OSINT Upgrade with tiered AI, adaptive scheduling, vector embeddings, and custom reporting.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui + Recharts
- **Backend**: FastAPI + MongoDB + emergentintegrations + APScheduler + WebSockets
- **AI**: Claude Haiku 4.5 via Emergent LLM Key (classification), OpenAI text-embedding-3-small (embeddings)
- **PDF**: fpdf2 for daily briefs and custom filtered reports with RESTRICTED headers

## Completed Features

### Core (v1)
- [x] 36 RSS sources, AI classification, Dashboard, Intel Feed, Daily Brief, PDF, Document Upload, Weekly Trends, Translation

### Phase 2: Advanced Relevance Filter
- [x] Hard filter, geographic matching, language detection, pre-AI translation

### Phase 3: Pattern Detection Engine
- [x] intelligence_patterns collection, sliding-window, escalation risk, /patterns page

### Phase 4: Critical Alert Acknowledgement
- [x] Sticky panel, ACK buttons, unacknowledged alerts endpoint

### Phase 5: Daily Brief Automation
- [x] Auto 0600 IST, cross-brief dedup, no Twitter, pattern insights in PDF

### Phase 6: Enhanced AI Classification
- [x] 8-step prompt, confidence_score, threat_trajectory, named entities, stricter negative filtering

### Phase 7: WebSocket Real-time Updates
- [x] /api/ws/intelligence, ConnectionManager, live feed panel, LIVE/OFFLINE indicator

### Phase 8: Configurable Retention + Caching
- [x] Retention window (7-365 days) via Settings page
- [x] Dashboard stats cache (60s TTL, auto-invalidated)

### Phase 9: Elite OSINT Upgrade (In Progress)
- [x] Sifter (Level 1 pre-filter) - sifter.py
- [x] Web Scraper (BS4/httpx) - web_scraper.py
- [x] Embedding Service (OpenAI) - embedding_service.py (auth fixed, needs quota)
- [x] Adaptive Scheduling (grassroots/60min, standard/30min, established/12hr)
- [x] Custom PDF Briefs with RESTRICTED headers and filters
- [x] Frontend Semantic Search UI toggle
- [x] P0 Bug Fix: Custom PDF 500 error (fpdf2 effective_w fix)
- [x] P0 Bug Fix: Embeddings 401 error (switched to OPENAI_API_KEY)

## Prioritized Backlog

### P0 - Blocked
- Embeddings Backfill: User's OpenAI API key has insufficient quota (429). Needs billing credits added at platform.openai.com.

### P1 - Upcoming
- Knowledge Graph Prep: Extract relationships (Actor-Location-Border) as structured metadata
- Add more National Indian news sources to RSS fetcher
- Dashboard priority_score filter/sort
- Refactor server.py (~2600 lines) into separate router files

### P2 - Future
- Twitter/X monitoring (paused by user)

### Not Required
- Authentication (user decision)
- Email digest (user decision)
