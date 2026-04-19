# Rhino Drishti — Product Requirements Document

## Original Problem Statement
Military-grade OSINT application for India's NER. Zero-noise intelligence, Daily Brief PDF, Cross-Border module, fusion engine, Intelligence Analysis, RBAC, feedback-driven AI classification.

## Architecture
React frontend + FastAPI backend + MongoDB Atlas + Claude Haiku 4.5 (Emergent LLM Key)

## What's Been Implemented
- RSS ingestion (72 sources), AI classification (10-step + feedback bias), fusion/dedup, vector search, knowledge graph
- Daily Intelligence Brief PDF, Cross-Border Watch, Intelligence Analysis tool
- JWT Auth with RBAC (admin/analyst/viewer), User Management
- Feedback Bias system: configurable window (rolling 30d/all-time), influence (light/moderate/high), Bias Impact Report
- Dashboard priority filter/sort, expanded national RSS (12 new sources)
- **Manual Int Uploads**: Renamed from "Upload Documents". Users can Analyze URLs (AI) OR Add directly to feed with custom severity, priority, threat category, region, summary. Inline quick-add form + post-analysis modal. Best-effort URL scraping.
- Manual keyword addition in Keyword Engine
- Settings page: side-by-side layout, viewer blocked, bias config + impact report
- User Handbook v8.0

## Key Endpoints
- `POST /api/auth/login`, `POST /api/add-to-feed`, `POST /api/analyze-url`
- `GET /api/intelligence?sort_by=priority_score&min_priority=80`
- `GET /api/feedback/bias-profile`, `GET /api/feedback/bias-impact`
- `GET/PUT /api/settings/bias`, `POST /api/keywords/add`

## Auth
- Admin: `admin` / `Admin@2026!` (auto-seeded)
- Test viewer: `testviewer` / `Viewer@2026!`

## Pending/Backlog
- P0 (Deferred): Viewer Role Restrictions Sweep
- P2 (Paused): Twitter/X monitoring

## Testing: Iterations 24-33 all passed 100%
