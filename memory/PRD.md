# Rhino Drishti - Product Requirements Document

## Original Problem Statement
Build a full-stack AI-powered web application called "Rhino Drishti" designed for intelligence aggregation, analysis, and reporting focused on India's North Eastern Region (NER). Automated collection from credible open-source news, AI-based filtering/classification, intelligence analysis engine, and professional dashboard UI.

## Architecture
- **Frontend**: React + Tailwind CSS + shadcn/ui (Tactical Olive military theme)
- **Backend**: FastAPI + MongoDB + emergentintegrations
- **AI Layer**: Claude Haiku 4.5 via Emergent LLM Key
- **RSS Feeds**: feedparser with 8 configured sources
- **Background Scheduler**: APScheduler (30-min interval)

## User Personas
- Armed forces personnel monitoring NER security
- Intelligence analysts tracking cross-border activities
- Strategic planners assessing threat levels

## Core Requirements
- Automated RSS data collection from Indian/international news sources
- AI-based classification (threat category, severity, state, cross-border status)
- Intelligence analysis (summary, why it matters, potential impact)
- Dashboard with overview stats, NER map, charts
- Search & filter by state, threat type, severity
- Daily intelligence brief generation (AI-powered)
- Weekly trend analysis with charts
- Dark military theme with light mode toggle

## What's Been Implemented (2026-03-20)
- [x] Backend API: 10+ endpoints (dashboard stats, intelligence CRUD, alerts, daily brief, weekly trends, sources, RSS fetch trigger)
- [x] MongoDB: intelligence_items, daily_briefs, rss_sources collections
- [x] AI Pipeline: Claude Haiku 4.5 classification and analysis
- [x] RSS Fetcher: 8 sources with keyword filtering
- [x] Background Scheduler: 30-min interval auto-fetch
- [x] Seed Data: 24 realistic intelligence items across all 6 NER states
- [x] Dashboard: Stats, NER SVG map, charts (threat/state distribution), recent alerts
- [x] Intelligence Feed: Filterable cards with search, state, threat type, severity filters
- [x] Cross-Border Developments: Filtered view for cross-border items
- [x] Daily Intelligence Brief: AI-generated with manual fallback
- [x] Weekly Trends: Severity trend, category analysis, state analysis charts
- [x] Alerts Page: Critical/High severity items
- [x] Theme Toggle: Dark (Tactical Olive) / Light mode
- [x] Responsive: Mobile-friendly with collapsible sidebar

## Prioritized Backlog
### P0 (Done)
- All core features implemented and tested

### P1 (Next Phase)
- Email/WhatsApp notifications for critical alerts
- Full-text search with MongoDB text indexes
- Manual override tagging for intelligence items
- User authentication (JWT or Google OAuth)

### P2 (Future)
- Interactive map with react-simple-maps (replacing SVG)
- Keyword heatmap visualization
- Multi-language support (Hindi, Assamese, Bengali)
- Cross-source validation for misinformation detection
- Export reports as PDF
- Real-time WebSocket updates

## Update 2026-03-20 - Phase 2
### Added Features:
1. **PDF Export for Daily Brief**: GET /api/daily-brief/pdf generates professional PDF with RESTRICTED classification header, analyst assessment, key developments, region-wise highlights, cross-border insights
2. **Bangladesh & Myanmar as Monitored Regions**: Both countries elevated from border areas to full monitored regions alongside 6 NER states
3. **Foreign Power Emphasis**: China/Pakistan/USA involvement flagged as HIGH/CRITICAL priority in AI classification
4. **Expanded Threat Categories**: Added Political Developments, Foreign Power Influence, Military Operations, Economic/Trade
5. **25 RSS Sources**: Including Prothom Alo (Bangla), Kaler Kantho (Bangla), Daily Star BD, Myanmar Now, Mizzima, Irrawaddy
6. **Updated NER Map**: Bangladesh & Myanmar shown as monitored regions with dashed borders

### Current Stats:
- 68+ live intelligence items from real RSS feeds
- 29 cross-border items tracked
- AI processing via Claude Haiku 4.5 with updated prompts
