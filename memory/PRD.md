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
├── server.py              # ~150 lines: FastAPI app, CORS, router mounting, startup/shutdown, scheduler, WebSocket
├── shared.py              # DB connections, Pydantic models, constants, WebSocket manager, shared state, utilities
├── routers/
│   ├── intelligence.py    # Dashboard stats, intelligence CRUD, alerts, patterns, semantic search, embeddings
│   ├── settings.py        # Retention settings + Feedback limit settings
│   ├── briefs.py          # Daily brief, PDF generation, custom briefs, weekly trends, brief scheduler
│   ├── pipeline.py        # Fetch/scrape/analyze news, scan status, pipeline health, scheduler wrappers
│   ├── documents.py       # Document upload, list, delete, AI analysis
│   ├── knowledge_graph_routes.py  # KG build, stats, actors, locations, edges, network
│   ├── keywords_routes.py # Keyword list, AI refresh
│   ├── sources.py         # RSS sources, Twitter accounts/feeds, handbook
│   └── feedback.py        # Alpha feedback system: submit, batch, stats, training profile, aggregation
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

### Phase 2-12: (All Complete)
- [x] Advanced Relevance Filter, Pattern Detection, Critical Alerts, Daily Brief Automation
- [x] Enhanced AI Classification, WebSocket Real-time, Configurable Retention + Caching
- [x] Elite OSINT (Sifter, Web Scraper, Embeddings, Adaptive Scheduling, Custom PDF)
- [x] Knowledge Graph, Dynamic Keyword Engine, User Handbook

### Phase 13: Backend Refactoring (2026-04-08)
- [x] Split monolithic server.py (2924 lines) into 8 modular routers + shared.py + slim server.py

### Phase 14: Alpha Training & Feedback System (2026-04-08)
- [x] Multi-user relevance scoring (1-6 scale with labels)
- [x] Device-level duplicate prevention (localStorage fingerprint + backend enforcement)
- [x] Configurable max ratings cap per news item (admin-controlled via Settings, default 20)
- [x] Aggregation engine: avg_rating, total_ratings, confidence_factor, derived_relevance
- [x] Training profile: positive/negative weights, preferred regions/threats/actors, noise patterns
- [x] Batch feedback API for efficient feed page loading
- [x] Intelligence item update with feedback_avg_rating, feedback_total_ratings, feedback_derived_relevance
- [x] Training & Feedback summary page with full analytics dashboard
- [x] FeedbackWidget at TOP of every IntelligenceCard (compact inline layout)
- [x] Training Controls in Settings page with native dropdown for max ratings
- [x] 100% test pass rate (iteration_17: 27 backend tests + full frontend verification)

## Key DB Collections
- `intelligence_items`: Articles with AI classification, embeddings, feedback_avg_rating, feedback_total_ratings
- `intelligence_feedback`: {id, intelligence_id, device_id, rating (1-6), timestamp, derived_features}
- `keyword_store`: Dynamic AI keywords
- `kg_actors`, `kg_locations`, `kg_edges`: Knowledge graph
- `app_settings`: retention_days, max_feedback_per_item

## Prioritized Backlog

### P1 - Upcoming
- Dashboard priority_score filter/sort
- Add more National Indian news sources to RSS fetcher

### P2 - Future
- Twitter/X monitoring (paused by user)
- Integrate aggregated feedback bias into AI scoring pipeline (final_score formula)

### Not Required
- Authentication (user decision)
- Email digest (user decision)
