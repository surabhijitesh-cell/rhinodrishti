# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Transform into a HIGH-PRECISION, LOW-NOISE, REAL-TIME INTELLIGENCE PLATFORM via an Elite OSINT Upgrade with tiered AI, adaptive scheduling, vector embeddings, and custom reporting.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui + Recharts
- **Backend**: FastAPI + MongoDB + emergentintegrations + APScheduler + WebSockets
- **AI**: Claude Haiku 4.5 via Emergent LLM Key (classification), OpenAI text-embedding-3-small (embeddings)
- **PDF**: fpdf2 for daily briefs and custom filtered reports with RESTRICTED headers

## Backend Structure (Post-Refactor)
```
/app/backend/
├── server.py              # ~140 lines: FastAPI app, CORS, router mounting, startup/shutdown, scheduler, WebSocket
├── shared.py              # DB connections, Pydantic models, constants, WebSocket manager, shared state, utilities
├── routers/
│   ├── intelligence.py    # Dashboard stats, intelligence CRUD, alerts, patterns, semantic search, embeddings
│   ├── settings.py        # Retention settings
│   ├── briefs.py          # Daily brief, PDF generation, custom briefs, weekly trends, brief scheduler
│   ├── pipeline.py        # Fetch/scrape/analyze news, scan status, pipeline health, scheduler wrappers
│   ├── documents.py       # Document upload, list, delete, AI analysis
│   ├── knowledge_graph_routes.py  # KG build, stats, actors, locations, edges, network
│   ├── keywords_routes.py # Keyword list, AI refresh
│   └── sources.py         # RSS sources, Twitter accounts/feeds, handbook
├── ai_pipeline.py         # Claude integration for article classification
├── embedding_service.py   # OpenAI embeddings
├── keyword_engine.py      # Dynamic AI keyword generation
├── knowledge_graph.py     # Entity relationship extraction
├── rss_fetcher.py         # RSS feed ingestion with dynamic keywords
├── intelligence_filter.py # Hard filter for non-intelligence content
├── sifter.py              # Level 1 pre-filter
├── pattern_engine.py      # Pattern detection
└── web_scraper.py         # Elite source scraping
```

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

### Phase 9: Elite OSINT Upgrade
- [x] Sifter (Level 1 pre-filter) - sifter.py
- [x] Web Scraper (BS4/httpx) - web_scraper.py
- [x] Embedding Service (OpenAI) - embedding_service.py
- [x] Adaptive Scheduling (grassroots/60min, standard/30min, established/12hr)
- [x] Custom PDF Briefs with RESTRICTED headers and filters
- [x] Frontend Semantic Search UI toggle
- [x] All P0 bug fixes (embeddings 401, custom PDF 500, daily brief endpoint, sports filter)

### Phase 10: Knowledge Graph
- [x] knowledge_graph.py, 3 MongoDB collections, 9 API endpoints, frontend visualization

### Phase 11: Dynamic Keyword Generation Engine
- [x] keyword_engine.py, AI-powered expansion, adaptive learning, 2 API endpoints, dedicated UI page

### Phase 12: User Handbook & UI Polish
- [x] USER_HANDBOOK.md, /api/handbook, /handbook page, sidebar reordering

### Phase 13: Backend Refactoring (2026-04-08)
- [x] Split monolithic server.py (2924 lines) into 8 modular routers + shared.py + slim server.py (~140 lines)
- [x] All 28 API endpoints verified working post-refactor
- [x] All frontend pages confirmed functional
- [x] 100% test pass rate (iteration_16)

## Prioritized Backlog

### P1 - Upcoming
- Add more National Indian news sources to RSS fetcher
- Dashboard priority_score filter/sort

### P2 - Future
- Twitter/X monitoring (paused by user)

### Not Required
- Authentication (user decision)
- Email digest (user decision)
