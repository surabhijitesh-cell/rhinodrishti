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
- Claude Haiku 4.5 AI classification with 10-step intelligence pipeline + dynamic feedback bias injection
- Multi-article fusion & deduplication engine
- Vector search (semantic search), Knowledge graph & pattern detection
- Daily Intelligence Brief PDF generator
- Cross-Border Watch module (Bangladesh/Myanmar)
- Intelligence Analysis tool (contextual URL/PDF evaluation)
- Training & Feedback pipeline with effectiveness scoring
- JWT Authentication with RBAC (admin/analyst/viewer)
- WebSocket real-time intelligence feed
- Dashboard priority filter/sort controls

### Feedback Bias System (Complete)
- **feedback_bias.py** engine: rolling window or all-time feedback aggregation
- **Configurable settings** via Settings page:
  - Feedback Window: Rolling 30 Days / All Time
  - Influence Level: Light (~10-15%) / Moderate (~20-25%) / High (~35-40%)
- **Bias Impact Report**: Shows before/after score comparison for all rated items
- Active bias profile visible on Training & Feedback page

### Settings Page (Complete)
- Side-by-side card layout (2-column grid)
- Row 1: Retention Window + Pipeline Status
- Row 2: Bias Configuration + Training Controls
- Row 3: Full-width Bias Impact Report with items table
- Viewer role blocked (redirect to dashboard)

## Key API Endpoints
- `POST /api/auth/login` — Accepts username OR email
- `GET /api/intelligence?sort_by=priority_score&min_priority=80`
- `GET /api/feedback/bias-profile` — Active feedback bias profile
- `GET /api/feedback/bias-impact` — Bias Impact Report (before/after scores)
- `GET/PUT /api/settings/bias` — Window & influence configuration
- `POST /api/documents/analyze-url` — Contextual intelligence analysis

## Auth & Credentials
- Default admin: `admin` / `Admin@2026!`
- Test viewer: `testviewer` / `Viewer@2026!`
- Roles: admin (full), analyst (no user mgmt/settings), viewer (read-only)

## Pending / Backlog
- P0 (Deferred): Complete Viewer Role Restrictions Sweep across all feature pages
- P2 (Future): Twitter/X monitoring integration (paused)

## Testing Status
- Iterations 24-32 all passed 100%. No known regressions.
