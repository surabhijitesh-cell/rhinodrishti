# Rhino Drishti — Product Requirements Document

## Original Problem Statement
Military-grade OSINT application for India's NER. Zero-noise intelligence, Daily Brief PDF, Cross-Border module, fusion engine, Intelligence Analysis, RBAC, feedback-driven AI classification, reports.

## Architecture
React frontend + FastAPI backend + MongoDB Atlas + Claude Haiku 4.5 (Emergent LLM Key) + fpdf2

## What's Been Implemented
- RSS ingestion (89 sources), AI classification (10-step + feedback bias), fusion/dedup, vector search, knowledge graph
- Daily Intelligence Brief PDF, Cross-Border Watch, Intelligence Analysis tool
- JWT Auth with RBAC (admin/analyst/viewer), User Management
- Feedback Bias system: configurable window/influence, Bias Impact Report
- Dashboard priority filter/sort, expanded national RSS + 17 government feeds
- Manual Int Uploads: Analyze URLs (AI) or Add directly to feed with auto-translation (Burmese/Thai/Chinese/Arabic/Korean/Japanese + Indian scripts)
- Manual keyword addition + keyword selection from analysis results
- Settings page: side-by-side layout, viewer blocked, bias config + impact report
- Update Notification System: priority-based toasts, admin CRUD, "More Updates" modal
- Delete intelligence items from any page
- **PDF Reports**: Filtered Feed export from Intelligence Feed + Reports page with Regional Threat Summary, Cross-Border SITREP, Custom Filtered Report
- User Handbook v9.2, Quick Reference Guide, Cost Proposal

## Key Endpoints
- Reports: `GET /api/reports/filtered-feed`, `/regional-threat`, `/cross-border-sitrep`, `/custom`
- Auth: `POST /api/auth/login`
- Intelligence: `GET /api/intelligence`, `DELETE /api/intelligence/{id}`, `POST /api/add-to-feed`
- Feedback: `GET /api/feedback/bias-profile`, `/bias-impact`
- Updates: `GET /api/app/updates`, `POST /api/admin/create-update`

## Auth
- Admin: `admin` / `Admin@2026!`
- Viewer: `testviewer` / `Viewer@2026!`

## Pending/Backlog
- P0 (Deferred): Viewer Role Restrictions Sweep
- P2 (Paused): Twitter/X, Instagram/Facebook, Firecrawl integrations
- Future: Trend/Actor/Source reports, email notifications

## Testing: Iterations 24-35 all passed 100%
