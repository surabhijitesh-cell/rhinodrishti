# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Transform into a HIGH-PRECISION, LOW-NOISE, REAL-TIME INTELLIGENCE PLATFORM via an 11-Phase Architectural Upgrade.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui + Recharts
- **Backend**: FastAPI + MongoDB + emergentintegrations + APScheduler + WebSockets
- **AI**: Claude Haiku 4.5 via Emergent LLM Key
- **Deployment**: Vercel (frontend) + Render (backend) + MongoDB Atlas

## Completed Features

### Core (v1)
- [x] 32 RSS sources, AI classification, Dashboard, Intel Feed, Daily Brief, PDF, Document Upload, Weekly Trends, Translation

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

## Prioritized Backlog

### P1 (Deferred)
- Semantic Search via Vector Embeddings (cost: ~$3-5/month)

### Not Required
- Authentication (user decision)
- Email digest (user decision)
