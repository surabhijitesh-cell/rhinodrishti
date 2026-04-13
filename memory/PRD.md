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
- [x] Configurable max ratings cap via pill-button selector in Settings (default 20)
- [x] Aggregation engine: avg_rating, total_ratings, confidence_factor, derived_relevance
- [x] Training profile: positive/negative weights, preferred regions/threats/actors, noise patterns
- [x] Batch feedback API for efficient feed page loading
- [x] FeedbackWidget at TOP of every IntelligenceCard with spaced-out numbered stars
- [x] Rating guide banner on Intelligence Feed page
- [x] Training page with URL input, file upload, training queue, "Train Rhino Drishti" button
- [x] Training pipeline: URL scraping, file text extraction, AI analysis (Claude Haiku), pattern aggregation
- [x] Training progress tracker with polling
- [x] Training insights page showing extracted regions, actors, keywords from uploaded data
- [x] URL Relevance Tagging: 1-6 selector on URL input, stored in DB, displayed in queue with REL badge
- [x] Training Activity Log & Impact: GET /training/activity-log endpoint, summary metrics, AI impact (regions/actors/keywords learned), recent activity timeline
- [x] Activity Log Restructure: Replaced noisy per-event logging with clean session-level table. Only logs Training Sessions (on Train click) and Feedback Sessions (aggregated after 5+ ratings/device). AI-generated impact summaries via Claude Haiku. Paginated table UI with Timestamp/Device/Activity Type/Volume/Impact columns.
- [x] Training Effectiveness Score: Real-time alignment metric (0-100%) comparing AI severity to analyst ratings, with grade (EXCELLENT/GOOD/MODERATE), biggest gaps, best alignments, and trend tracking after each training run
- [x] 100% test pass rate (iteration_20: 14 backend + full frontend verification)

### Phase 15: Cross-Border Watch Module (2026-04-09)
- [x] Dedicated Cross-Border Watch page: Bangladesh & Myanmar split view with country posture badges
- [x] Watchpoints: Auto-detected trend themes from signal_bucket + early_warning_signal
- [x] Signal Distribution: Visual distribution of signal bucket categories
- [x] Signal Filtering: ALL / MEDIUM / HIGH signal strength filter buttons
- [x] Expandable signal items: "What happened" + "India-relevant implication" + "Early warning" format
- [x] Geographic boost: +2-3 priority for items mentioning border locations (Moreh, Champhai, Cox's Bazar, Chin State, etc.)
- [x] RSS Expansion: 24+ new Bangladesh/Myanmar feeds (Dhaka Tribune, BSS News, Daily Star BD, Irrawaddy, Mizzima, DVB, Shan Herald, BNI, Narinjara, Chin World, ANI, etc.)
- [x] AI Prompt Enhancement: India-relevance scoring (0-20), signal bucket classification (12 categories), signal strength (HIGH/MEDIUM/LOW), cross_border_category (diplomatic/defence/internal_politics/economics)
- [x] Posture computation: auto-calculated from priority scores + escalation ratio per country
- [x] Sub-categorization: Items grouped by Diplomatic/Defence/Internal Politics/Economics with icons and numbered display
- [x] Keyword-based auto-categorization fallback for items processed before prompt update
- [x] Training/Feedback integration: feedback_avg_rating bias applied to cross-border item scoring (feedback_bias = log(n+1) * (avg-3.5))
- [x] Strict country classification: Indian border state items only shown if title explicitly references BD/MM
- [x] Unprocessed items filtered out (require ai_summary)
- [x] 100% test pass rate (iteration_23: 21 backend + full frontend verification)

### Phase 16: P0 Bug Fixes - Noise Elimination (2026-04-10)
- [x] Cross-Border Watch: Added `severity != low` DB query filter + application-level LOW severity exclusion
- [x] Cross-Border Watch: Added `has_non_latin_chars()` check to filter untranslated Bengali/Hindi/Assamese items from UI
- [x] Daily Brief PDF: Removed Bangladesh, Myanmar, and empty-state from NER Key Developments allowed states
- [x] Daily Brief PDF: Added Nagaland and Sikkim to NER state lists across all queries (ner_query, fallback_ner_query, NER_STATES_PDF)
- [x] Daily Brief PDF: Removed `or not state` catch-all that let empty-state items into NER section
- [x] 100% test pass rate (iteration_24: 22 backend + full frontend verification)

### Phase 17: Multi-Article Fusion & Deduplication (2026-04-10)
- [x] `fusion_engine.py`: Title normalization, entity extraction, word overlap + entity similarity detection (threshold 0.50)
- [x] Embedding cosine similarity fallback (threshold 0.88) for items with vector embeddings
- [x] Cluster management: picks best/longest summary as primary, cites all covering sources
- [x] Real-time fusion: hooks into AI classification pipeline (`pipeline.py`) — new articles auto-merge with existing clusters
- [x] Scheduled batch fusion: runs every 30 min via APScheduler, processes unclustered items + merges orphans into existing clusters
- [x] Intelligence Feed query updated: only shows cluster primaries (`is_cluster_primary != False`), hiding duplicates
- [x] API endpoints: `POST /api/fusion/run` (manual trigger), `GET /api/fusion/stats` (dedup statistics)
- [x] Frontend `IntelligenceCard.js`: "X sources" badge with expandable panel showing all covering sources with clickable links
- [x] Initial batch fusion: 30 clusters from 72 items, 8.3% dedup ratio, feed reduced from 506 to 464 visible items
- [x] 100% test pass rate (iteration_25: 19 backend + full frontend verification, plus P0 regression passing)

### Phase 18: Feed Quality, Training UX, Cross-Border Brief (2026-04-11)
- [x] Intelligence Feed: Added `severity != low` and `tags != not_relevant/unprocessed` DB filters — feed reduced from 464 to 82 high-value items
- [x] Training Queue: Live sequential clearing during training — polls queue every 2s alongside progress, completed items disappear in real-time
- [x] Daily Brief: Added Cross-Border Intelligence section (Bangladesh & Myanmar) with category grouping (Diplomatic/Defence/Economics/Internal Politics)
- [x] Daily Brief PDF: Cross-Border section renders with per-country category headers, severity markers, summaries and sources
- [x] Frontend: Cross-Border section positioned before International News per user request
- [x] 100% test pass rate (iteration_26: 18 backend + full frontend verification)

### Phase 19: JWT Authentication & RBAC (2026-04-12)
- [x] Backend auth utilities: bcrypt password hashing, JWT creation/verification (PyJWT), get_current_user + require_admin_role dependencies
- [x] Auth endpoints: POST /api/auth/login (accepts username OR email via $or), GET /api/auth/me
- [x] User Management endpoints: GET/POST /api/users (admin only), PUT/DELETE /api/users/{id}, PUT /api/users/{id}/password (password reset)
- [x] Three roles: Admin (full access), Analyst (no User Management/Settings), Viewer (read-only)
- [x] Frontend AuthContext with axios interceptors (token attachment + 401 redirect)
- [x] ProtectedRoute wrapper, Login page with password visibility toggle
- [x] User Management page: create/delete users, password reset with generate/copy, role assignment, active/inactive toggle
- [x] Layout RBAC: sidebar filters menu items by role, logout button with user display
- [x] Admin seed script: username=admin, password=Admin@2026!
- [x] 100% test pass rate (iteration_27: 22 backend + full frontend verification)

### Phase 20: Multi-Article Fusion Fix + Intelligence Analysis Tool (2026-04-13)
- [x] Fusion engine overhaul: 6 detection methods (exact title, source_url, title word overlap 0.40, entity overlap 2+, keyphrase matching, same-source+state)
- [x] Added compound keyphrase extraction (ULFA-I chief, shots fired, bunkers destroyed, etc.)
- [x] Expanded entity dictionaries: added NER-specific orgs (manipur police, kuki, meitei), places (dibrugarh, chabua, churachandpur), events (encounter, yaba, smuggling)
- [x] Re-ran batch fusion: 46 clusters from 140 items, 17.8% dedup (up from 8.3%)
- [x] Reworked Upload Documents → Intelligence Analysis tool: upload PDF/Word/TXT or paste URL
- [x] AI generates comprehensive contextual analysis: threat classification, pattern matching vs current NER security env, relevance score, recommended actions, cross-references, intelligence gaps
- [x] Frontend: tabbed interface (Upload File / Analyze URL), analysis cards with expandable detail (severity, category, escalation, entities)
- [x] Backend auto-seeds admin user on startup if users collection is empty (no MongoDB access needed for deployment)
- [x] 100% test pass rate (iteration_28: 13 backend + full frontend verification)

## Key DB Collections
- `intelligence_items`: Articles with AI classification, embeddings, feedback_avg_rating, feedback_total_ratings
- `intelligence_feedback`: {id, intelligence_id, device_id, rating (1-6), timestamp, derived_features}
- `training_data`: {id, title, source, url, type, status, ai_analysis, relevance (1-6 optional)}
- `training_activity_log`: {id, type (url_added/file_uploaded/training_run), description, relevance_tag, timestamp, items_processed, errors, regions_found, actors_found}
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
