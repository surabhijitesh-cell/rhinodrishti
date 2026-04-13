# Rhino Drishti — Product Requirements Document

## Original Problem Statement
Build a military-grade OSINT application ("Rhino Drishti") for India's North Eastern Region (NER). The system requires:
- Zero-noise intelligence filtering
- Automated Daily Intelligence Brief (PDF) customized for NER
- Cross-Border module (Bangladesh/Myanmar)
- Multi-article fusion engine to deduplicate news
- Intelligence Analysis tool for contextual URL/Document evaluation
- Full JWT-based Role-Based Access Control (RBAC) system
- Feedback-driven AI classification improvement with configurable settings

## Architecture
- **Frontend**: React (port 3000) with Shadcn/UI components
- **Backend**: FastAPI (port 8001) with MongoDB Atlas
- **AI**: Claude Haiku 4.5 via Emergent LLM Key
- **Auth**: JWT (PyJWT + passlib/bcrypt)

## What's Been Implemented

### Core Features (Complete)
- RSS ingestion from 72 sources (19 national, NER regional, cross-border, international, government)
- Claude Haiku 4.5 AI classification with 10-step intelligence pipeline
- Multi-article fusion & deduplication engine
- Vector search (semantic search), Knowledge graph & pattern detection
- Daily Intelligence Brief PDF generator (NER, cross-border, national, international sections)
- Cross-Border Watch module (Bangladesh/Myanmar with category grouping)
- Intelligence Analysis tool (contextual URL/PDF evaluation)
- Training & Feedback pipeline with effectiveness scoring
- JWT Authentication with RBAC (admin/analyst/viewer)
- WebSocket real-time intelligence feed
- Dashboard priority filter/sort controls

### Feedback Bias System (Complete)
- **feedback_bias.py** engine aggregates analyst ratings into dynamic bias context injected into AI prompts
- **Configurable settings** via Settings page:
  - **Feedback Window**: Rolling 30 Days (default) or All Time
  - **Influence Level**: Light (~10-15%), Moderate (~20-25% default), High (~35-40%)
- Settings stored in `app_settings` collection, cache invalidated on change
- Active bias profile visible on Training & Feedback page with upweight/downweight patterns
- New endpoints: `GET/PUT /api/settings/bias`, `GET /api/feedback/bias-profile`

## Key API Endpoints
- `POST /api/auth/login` — Accepts username OR email
- `GET /api/intelligence?sort_by=priority_score&min_priority=80` — Feed with filter/sort
- `GET /api/feedback/bias-profile` — Active feedback bias profile
- `GET/PUT /api/settings/bias` — Bias window & influence configuration
- `POST /api/documents/analyze-url` — Contextual intelligence analysis
- `POST /api/intelligence/fuse` — Manual trigger for fusion engine

## Auth Credentials
- Default admin: `admin` / `Admin@2026!` (auto-seeded on empty DB)
- Roles: admin, analyst, viewer

## Deployment Notes
- **Render**: Must use: `pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/`
- **CORS**: Auth requires `allow_credentials=True`, explicit origin matching

## Pending / Backlog
### P0 (Deferred by user)
- Complete Viewer Role Restrictions Sweep across all pages

### P2 (Future)
- Twitter/X monitoring integration (paused by user)

## Testing Status
- Iterations 24-31 all passed 100%
- No known regressions
