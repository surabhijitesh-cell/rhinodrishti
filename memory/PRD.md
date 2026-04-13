# Rhino Drishti — Product Requirements Document

## Original Problem Statement
Build a military-grade OSINT application ("Rhino Drishti") for India's North Eastern Region (NER). The system requires:
- Zero-noise intelligence filtering
- Automated Daily Intelligence Brief (PDF) customized for NER
- Cross-Border module (Bangladesh/Myanmar)
- Multi-article fusion engine to deduplicate news
- Intelligence Analysis tool for contextual URL/Document evaluation
- Full JWT-based Role-Based Access Control (RBAC) system
- Feedback-driven AI classification improvement

## Architecture
- **Frontend**: React (port 3000) with Shadcn/UI components
- **Backend**: FastAPI (port 8001) with MongoDB Atlas
- **AI**: Claude Haiku 4.5 via Emergent LLM Key
- **Auth**: JWT (PyJWT + passlib/bcrypt)

## Code Structure
```
/app/
├── backend/
│   ├── ai_pipeline.py           # AI classification with dynamic feedback bias injection
│   ├── feedback_bias.py         # NEW: Feedback bias engine (rolling 30-day window)
│   ├── fusion_engine.py         # Multi-article deduplication
│   ├── rss_fetcher.py           # 72 RSS sources (19 national, expanded)
│   ├── keyword_engine.py        # Dynamic keyword generation
│   ├── models/user.py           # User schema
│   ├── routers/
│   │   ├── auth.py              # JWT Login & User Management
│   │   ├── feedback.py          # Ratings, training profile, bias-profile endpoint
│   │   ├── intelligence.py      # Feed with sort_by/min_priority/sort_order
│   │   ├── briefs.py, cross_border.py, documents.py, training.py, etc.
│   ├── utils/auth.py            # JWT, passlib, bcrypt helpers
│   └── server.py                # Auto-seeds admin on startup
├── frontend/src/
│   ├── pages/
│   │   ├── Dashboard.js         # Priority filter/sort in Latest Intelligence section
│   │   ├── TrainingSummary.js    # Active Feedback Bias card (Live AI Pipeline)
│   │   ├── IntelligenceFeed.js, CrossBorderWatch.js, DailyBrief.js, etc.
│   ├── components/Layout.js     # RBAC sidebar
│   ├── contexts/AuthContext.jsx  # JWT storage & Axios interceptors
```

## Key Database Schema
- `users`: {id, username, email, password_hash, name, role, is_active, created_at, last_login}
- `intelligence_items`: {..., priority_score, cluster_id, is_primary, cluster_size, feedback_avg_rating, feedback_total_ratings}
- `intelligence_feedback`: {id, intelligence_id, device_id, rating (1-6), derived_features, timestamp}
- `uploaded_documents`: {..., contextual_analysis: {executive_summary, relevance_score, threat_classification}}

## Auth Credentials
- Default admin: `admin` / `Admin@2026!` (auto-seeded on empty DB)
- Roles: admin, analyst, viewer

## What's Been Implemented
### Core Features (Complete)
- RSS ingestion from 72 sources (NER regional, national, cross-border, international, government)
- Claude Haiku 4.5 AI classification with 10-step intelligence pipeline
- Multi-article fusion & deduplication engine
- Vector search (semantic search)
- Dynamic keyword engine with AI expansion
- Knowledge graph & pattern detection
- Daily Intelligence Brief PDF generator (NER, cross-border, national, international sections)
- Cross-Border Watch module (Bangladesh/Myanmar with category grouping)
- Intelligence Analysis tool (contextual URL/PDF evaluation)
- Training & Feedback pipeline with effectiveness scoring
- JWT Authentication with RBAC (admin/analyst/viewer)
- User Management UI (admin only)
- WebSocket real-time intelligence feed
- Viewer restrictions on Training page (URL input, file upload, train button disabled)

### Recent Additions (This Session)
1. **P2: Feedback Bias in AI Pipeline** — Analyst ratings (1-6 scale) are now aggregated into a dynamic bias context and injected into the Claude Haiku 4.5 classification prompt. Uses rolling 30-day window with ~20-25% influence weight and 5-minute cache TTL. New `GET /api/feedback/bias-profile` endpoint. New "Active Feedback Bias" card on Training & Feedback page.
2. **P1: Dashboard Priority Filter/Sort** — Added priority filter dropdown (80+/60+/40+) and sort dropdown (Most Recent/Highest Priority) to the Dashboard's "Latest Intelligence" section.
3. **P1: Expanded National RSS Sources** — Added 12 new national Indian news sources: India Today, Hindustan Times, Deccan Herald, The Wire, Scroll.in, The Print, The Quint, Mint Defence, ET Defence, Firstpost, Indian Express India, Tribune India. Total sources: 72.

## Key API Endpoints
- `POST /api/auth/login` — Accepts username OR email
- `GET /api/intelligence?sort_by=priority_score&min_priority=80` — Feed with filter/sort
- `GET /api/feedback/bias-profile` — Active feedback bias profile for AI pipeline
- `POST /api/documents/analyze-url` — Contextual intelligence analysis
- `POST /api/intelligence/fuse` — Manual trigger for fusion engine

## Deployment Notes
- **Emergent**: Standard deployment, works out of the box
- **Render**: Must use build command: `pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/`
- **CORS**: Auth requires `allow_credentials=True`. Backend CORS must explicitly match frontend URL.

## Pending / Backlog
### P0 (Deferred by user)
- Complete Viewer Role Restrictions Sweep (all pages — Dashboard ACK, FeedbackWidget, DailyBrief regenerate, KeywordEngine refresh)

### P2 (Future)
- Twitter/X monitoring integration (paused by user preference)

## Testing Status
- Iterations 24-30 all passed 100%
- Backend and frontend fully tested
- No known regressions
