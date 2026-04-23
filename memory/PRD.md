# Rhino Drishti — Product Requirements Document

## Original Problem Statement
Military-grade OSINT application for India's NER. Zero-noise intelligence, Daily Brief PDF, Cross-Border module, fusion engine, Intelligence Analysis, RBAC, feedback-driven AI classification.

## Architecture
React frontend + FastAPI backend + MongoDB Atlas + Claude Haiku 4.5 (Emergent LLM Key)

## What's Been Implemented
- RSS ingestion (89 sources), AI classification (10-step + feedback bias), fusion/dedup, vector search, knowledge graph
- Daily Intelligence Brief PDF, Cross-Border Watch, Intelligence Analysis tool
- JWT Auth with RBAC (admin/analyst/viewer), User Management
- Feedback Bias system: configurable window/influence, Bias Impact Report
- Dashboard priority filter/sort, expanded national RSS + 17 government feeds
- Manual Int Uploads: Analyze URLs (AI) or Add directly to feed with translation
- Manual keyword addition + keyword selection from analysis results
- Settings page: side-by-side layout, viewer blocked, bias config + impact report
- **Update Notification System**: Priority-based (major/minor), per-user acknowledgment, sequential toast queue (max 3 for long-gap users + "More Updates" modal), admin CRUD/preview, Platform Updates page
- Delete intelligence items from any page
- User Handbook v9.2, Quick Reference Guide, Cost Proposal

## Key Endpoints
- `POST /api/auth/login`, `POST /api/add-to-feed`, `POST /api/analyze-url`
- `GET /api/intelligence?sort_by=priority_score&min_priority=80`
- `GET /api/feedback/bias-profile`, `GET /api/feedback/bias-impact`
- `GET/PUT /api/settings/bias`, `POST /api/keywords/add`
- `DELETE /api/intelligence/{item_id}`
- `GET /api/app/updates`, `POST /api/app/updates/acknowledge`, `GET /api/app/updates/all`
- `POST /api/admin/create-update`, `GET /api/admin/update-logs`, `POST /api/admin/trigger-update-preview`

## Auth
- Admin: `admin` / `Admin@2026!` (auto-seeded)
- Test viewer: `testviewer` / `Viewer@2026!`

## Pending/Backlog
- P0 (Deferred): Viewer Role Restrictions Sweep
- P2 (Paused): Twitter/X, Instagram/Facebook, Firecrawl integrations

## Testing: Iterations 24-34 all passed 100%
