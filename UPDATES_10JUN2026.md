# Rhino Drishti — Updates Log (10 June 2026)

## Summary

Eight major features shipped across Faultline Intelligence, Monthly Strategic Brief, Trends Intelligence Centre, Social Media, Knowledge Graph, Platform Notifications, Daily Brief enhancements, and Faultline PDF Report. User Handbook updated to v10.0.

---

## 1. Faultline Intelligence System (New Module)

New top-level module that tracks deep structural tensions — ethnic, political, economic, social — as continuous scores rather than event-driven news items.

**Registry:** 40 faultlines covering all 8 NER states, Bangladesh, and Myanmar.

**Scoring:**
- Daily pass scores each faultline 0–100 from matched article volume + severity weighting
- Status levels: CRITICAL (75–100) / MONITOR (40–74) / STABLE (15–39) / DORMANT (0–14)
- Month-over-month delta computed and shown

**Dashboard Pulse Strip:**
Top 5 most-stressed faultlines shown on main Dashboard. Shows name, score, MoM delta, and status badge.

**Warning Alerts:**
CRITICAL threshold triggers dismissable alert banner on Faultlines page. Auto-expires 48 h if unacknowledged. Analyst/Admin can acknowledge.

**Faultline Detail Page:**
- 30-day score trendline
- LLM narrative analysis paragraph
- Matched articles with relevance rationale
- Analyst notes (editable, auto-saved)

**Priority Areas of Interest (PAOIs):**
High-watch faultlines designated by analysts. Currently seeded: Bangladesh border-related faultlines + Myanmar conflict spillover. PAOI articles tagged RED in daily brief and Monthly Strategic Brief.

**Backfill:**
Historical backfill up to 90 days. Progress visible in status panel. Admin/Analyst only.

**New Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/faultlines | List all faultlines (optional state filter) |
| GET | /api/faultlines/dashboard-summary | Top stressed faultlines for pulse strip |
| GET | /api/faultlines/warnings | Active unacknowledged alerts |
| POST | /api/faultlines/warnings/{alert_id}/ack | Acknowledge alert |
| GET | /api/faultlines/{fl_id} | Single faultline + latest score |
| PATCH | /api/faultlines/{fl_id} | Update notes / active flag |
| GET | /api/faultlines/{fl_id}/history | Daily score history (default 30 days) |
| GET | /api/faultlines/{fl_id}/articles | Matched articles for a faultline |
| POST | /api/faultlines/run-daily | Trigger daily scoring pass (Analyst/Admin) |
| POST | /api/faultlines/backfill | Start historical backfill |
| GET | /api/faultlines/backfill/status | Backfill progress |
| GET | /api/faultlines/report | Download standalone Faultline PDF report |

**Files Changed:**
- `backend/faultline_engine.py` (new)
- `backend/faultline_seed.py` (new)
- `backend/priority_areas_seed.py` (new)
- `backend/routers/faultlines.py` (new)
- `frontend/src/pages/FaultlineIntelligence.js` (new)
- `frontend/src/pages/FaultlineDetail.js` (new)

---

## 2. Faultline PDF Report (5-Page Standalone Report)

Downloadable from the Faultlines page. Covers the selected month's faultline activity in a command-brief format.

**Pages:**
1. Cover + executive summary of top faultlines
2. Month-on-month movers (biggest score changes)
3. Top 5 faultlines — LLM narrative analysis
4. Drivers + article evidence
5. PAOI faultlines — dedicated deep-dive

LLM calls (via Gemini 2.5 Flash / OpenRouter) generate narrative for each section. Statistics drawn from DB aggregation — no hallucination.

**File Changed:** `backend/routers/faultlines.py` — `GET /api/faultlines/report`

---

## 3. Monthly Strategic Brief (New Module)

Senior-commander level monthly intelligence playbook. On-demand generation for any past month.

**Generation:**
- POST `/brief/monthly/generate?year=Y&month=M` kicks off background generation
- Per-state synthesis runs in parallel via asyncio.gather
- Model: Gemini 2.5 Flash via OpenRouter

**Tabs (6):**

| Tab | Content |
|-----|---------|
| Overview | Executive summary, key stats, severity distribution |
| State Analysis | Per-state LLM synthesis, all 8 NER states |
| Cross-Border | Bangladesh + Myanmar assessments, posture rating |
| Faultline Assessment | All faultlines scored for the month, top movers |
| PAOI | Deep-dive on Priority Areas of Interest |
| Mitigation Playbook | Recommended actions for Bangladesh + Myanmar |

**Claim Labeling:** All LLM text tagged `[CONFIRMED]` / `[ASSESSED]` / `[SPECULATIVE]`.

**Download Options:**
- Full PDF
- Combined PDF (summary version)
- NotebookLM Export (markdown for Google NotebookLM video overview)

**New Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /brief/monthly/generate | Trigger generation (background) |
| GET | /brief/monthly/{year}/{month} | Fetch generated brief |
| GET | /brief/monthly/list | List available months |
| GET | /brief/monthly/{year}/{month}/pdf | PDF download |
| GET | /brief/monthly/{year}/{month}/notebooklm | NotebookLM markdown export |

**File Changed:** `backend/routers/brief_monthly.py` (new)

---

## 4. Fortnightly Brief (New Module)

Two-week rolling synthesis covering major trends and emerging patterns. Available as new tab on the Briefs page.

**File Changed:** `backend/routers/brief_fortnightly.py` (new)

---

## 5. Daily Brief — Faultline Section + PAOI Tagging

Daily Brief PDF now includes a **Section 8: Faultline Summary**:
- Top stressed faultlines with current scores and MoM deltas
- PAOI items highlighted separately

PAOI-tagged articles are marked RED throughout the brief for immediate commander attention.

**File Changed:** `backend/routers/briefs.py`

---

## 6. Trends Intelligence Centre (Revamp)

Weekly Trends page replaced with full **Trends Intelligence Centre**. Multi-timeframe, multi-chart analysis.

**Time Ranges:** 24h / 7d / 30d / 90d / 365d

**New Charts:**

| Chart | Description |
|-------|-------------|
| State Severity Evolution | Line chart per NER state. Hover tooltip sorted by score descending. |
| Severity Trend Aggregate | Area chart by severity. Tooltip ordered CRITICAL → HIGH → MEDIUM → LOW. |
| State-wise Activity | Bar chart by state. Items without a matched state shown as "Unclassified". |
| Threat Category Distribution | Top threat categories by article count |
| Top Actors Frequency | Actor mention frequency |
| Cross-Border Correlation | Bangladesh/Myanmar ↔ NER event correlation |
| Stability Index | Per-state composite stability score |

**State Drill-Down:** Click any state for per-state severity timeline, top threats, key actors, and cross-border linkages.

**New Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /trends | Top-level dashboard data |
| GET | /trends/state/{state} | Single-state drill-down |
| GET | /trends/stability | Per-state stability index |
| GET | /trends/cross-border | Cross-border correlation analysis |

**File Changed:** `backend/routers/trends.py` (new), `frontend/src/pages/Trends.js` (rewritten)

---

## 7. Social Media Intelligence (New Module)

Ingest content from X (Twitter), YouTube, Facebook, and Telegram into the intelligence pipeline.

**Supported Sources Per Platform:**

| Platform | Source Types |
|----------|-------------|
| X (Twitter) | Accounts, keyword searches, Twitter Lists |
| YouTube | Channels, keyword searches |
| Facebook | Public pages |
| Telegram | Public channels |

**Per Source:** Add / toggle active / fetch on demand / remove.

**Dashboard Widget:** Social Media Feed Widget on main Dashboard shows recent ingested social posts alongside RSS items.

**New Endpoints:**
- `GET/POST /api/social/{platform}` — list / add source
- `PATCH/DELETE /api/social/{platform}/{id}` — update / remove
- `POST /api/social/{platform}/{id}/fetch` — on-demand fetch
- `GET /api/social/status` — configured status of all platforms
- `POST /api/social/fetch-all` — trigger all platforms (Admin)

**File Changed:** `backend/routers/social_media.py` (new), `frontend/src/components/SocialMediaFeedWidget.jsx` (new)

---

## 8. Knowledge Graph (New Page)

Visual entity relationship map built from extracted entities across intelligence items.

**Nodes:** Persons, Organizations, Locations  
**Edges:** Co-occurrence in articles, directional actor→action relationships  
**Insurgent canonicalization:** Militant group aliases resolved to single canonical nodes  
**Security force filter:** Government/security actors separated from insurgent nodes  

**Trigger:** Admin/Analyst can rebuild the graph via Build button (runs in background).

**File Changed:** `backend/routers/knowledge_graph_routes.py` (new), `backend/knowledge_graph.py` (new), `frontend/src/pages/KnowledgeGraph.js` (new)

---

## 9. Platform Update Notifications (New System)

In-app version update notification system. Users see new feature announcements on login without checking external channels.

**Priority Levels:**
- **MAJOR** — Full notification modal shown, up to 3 at a time
- **MINOR** — Collapsed to single "Performance improvements and bug fixes" notice

**Smart Batching:** Long-gap users (returning after many versions) see only the latest 3 major updates, with "X more" indicator.

**Acknowledgment:** User acknowledges to clear notification. Last-seen version stored per user.

**Admin CRUD:** `POST /admin/create-update` with version, message, priority.

**File Changed:** `backend/routers/app_updates.py` (new)

---

## 10. User Handbook Updated to v10.0

- New Section 13: Faultline Intelligence System (faultline scoring, PAOIs, alerts, detail page, PDF, backfill)
- New Section 14: Monthly Strategic Brief (tabs, claim labeling, download options)
- New Section 15: Trends Intelligence Centre (charts, drill-down, stability index)
- New Section 16: Social Media Intelligence (platforms, feed widget)
- New Section 17: Knowledge Graph
- New Section 18: Platform Update Notifications
- Section 7 (Daily Brief) updated with faultline section + PAOI tagging
- Section 9 (Manual Uploads) updated with Add to Feed workflow + keyword extraction
- Section 10 (RBAC) updated with analyst/admin faultline permissions
- Section 11 (Data Flow) updated with faultline tagging step + social media sources
- Section 13 (Key Metrics) updated with all new metrics
- Version bumped to v10.0 | June 2026

---

## Files Changed in This Release

| File | Change |
|------|--------|
| `backend/faultline_engine.py` | New — daily scoring, backfill, alert logic |
| `backend/faultline_seed.py` | New — 40 faultline definitions |
| `backend/priority_areas_seed.py` | New — PAOI faultline designations |
| `backend/routers/faultlines.py` | New — all faultline API endpoints |
| `backend/routers/brief_monthly.py` | New — monthly strategic brief generation + PDF |
| `backend/routers/brief_fortnightly.py` | New — fortnightly brief |
| `backend/routers/trends.py` | New — trends intelligence centre endpoints |
| `backend/routers/social_media.py` | New — social media source management |
| `backend/routers/knowledge_graph_routes.py` | New — knowledge graph build + query |
| `backend/knowledge_graph.py` | New — graph construction logic |
| `backend/routers/app_updates.py` | New — platform update notifications |
| `backend/routers/briefs.py` | Updated — faultline section + PAOI tags in daily brief |
| `frontend/src/pages/FaultlineIntelligence.js` | New — faultlines list page |
| `frontend/src/pages/FaultlineDetail.js` | New — faultline detail view |
| `frontend/src/pages/Trends.js` | Rewritten — full trends intelligence centre |
| `frontend/src/pages/KnowledgeGraph.js` | New — knowledge graph page |
| `frontend/src/pages/DailyBrief.js` | Updated — daily/fortnightly/monthly tabs |
| `frontend/src/components/SocialMediaFeedWidget.jsx` | New — social feed widget |
| `QUICK_REFERENCE_GUIDE.md` | Updated to v10.0 |
| `UPDATES_10JUN2026.md` | This file |
