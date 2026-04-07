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
- [x] P0 Bug Fix: Daily Brief not generating (DailyBrief.js called wrong endpoint)
- [x] P0 Bug Fix: Sports/entertainment leaking through filter (reject now checks title+content, word-boundary regex for short keywords, runs before NER source pass-through)

### Phase 10: Knowledge Graph
- [x] `knowledge_graph.py` — aggregates actor-location-context relationships from entities/actors fields
- [x] 3 MongoDB collections: `kg_actors` (113), `kg_locations` (21), `kg_edges` (144)
- [x] Actor normalization (BSF, ULFA(I), NSCN variants merged)
- [x] 9 API endpoints (build, stats, actors, actor detail, locations, edges, network graph)
- [x] Frontend page at `/knowledge-graph` with stats bar, actor/location tabs, search, filters
- [x] Actor detail view: locations, threats, co-occurring actors, movement edges, related articles

### Phase 11: Dynamic Keyword Generation Engine
- [x] `keyword_engine.py` — multi-layered keyword generation (primary, entity, geo, cross_border, emerging, expanded)
- [x] Input sources: historical intelligence (14 days), high-priority news, static seed keywords
- [x] AI-powered expansion: Claude Haiku generates emerging signals and synonym expansions
- [x] Keyword scoring (0-100) based on frequency, severity, cross-border relevance, recency decay
- [x] Adaptive learning loop: boosts keywords on HIGH/CRITICAL articles, decays on LOW
- [x] MongoDB `keyword_store` collection with score tracking
- [x] Integrated into `rss_fetcher.py` — dynamic weighted matching replaces static keywords
- [x] 2 API endpoints: GET /api/keywords (filtered), POST /api/keywords/refresh (AI regeneration)
- [x] Dedicated `/keywords` page with stats, search, type filters, sort, color-coded tags

### Phase 12: User Handbook & UI Polish
- [x] Comprehensive `/USER_HANDBOOK.md` (14 sections covering every feature)
- [x] Handbook served via `/api/handbook` and rendered at `/handbook` with markdown parser
- [x] Keyword Engine moved from Dashboard widget to dedicated sidebar page
- [x] Navigation reordered: Keyword Engine above Upload Documents, User Handbook below it

## Prioritized Backlog

### P0 - Resolved
- Embeddings Backfill: Working with new OpenAI API key. 532 items being backfilled in batches of 50. Semantic search operational.

### P1 - Upcoming
- Add more National Indian news sources to RSS fetcher
- Dashboard priority_score filter/sort
- Refactor server.py (~2600 lines) into separate router files

### P2 - Future
- Twitter/X monitoring (paused by user)

### Not Required
- Authentication (user decision)
- Email digest (user decision)
