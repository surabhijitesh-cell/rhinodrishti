# Rhino Drishti — Complete Feature Summary
### Master Reference for User Handbook Generation (v10.0, May 2026)

This document is a complete, structured description of every feature in the Rhino Drishti platform.
It is intended to be fed to Claude to generate an updated user handbook.

---

## WHAT RHINO DRISHTI IS

Rhino Drishti is an AI-powered military intelligence aggregation and analysis platform for monitoring India's North Eastern Region (NER) — Assam, Manipur, Mizoram, Meghalaya, Nagaland, Tripura, Arunachal Pradesh — plus cross-border intelligence from Bangladesh and Myanmar.

The platform ingests news from 89+ RSS feeds and social media sources, runs a 4-stage AI filter cascade to identify genuinely relevant security intelligence, stores classified items in MongoDB, and presents them through a React frontend to intelligence analysts.

**Target users:** Armed forces personnel, intelligence analysts, strategic planners, defense ministry officials.

**Deployment:** Backend on Render (FastAPI/Python), Frontend on Vercel (React), Database on MongoDB Atlas.

---

## 1. AUTHENTICATION & ACCESS CONTROL

### Login
- JWT-based authentication. Sessions last 24 hours.
- Login with username or email + password. Eye icon toggles password visibility.
- Default admin account auto-created on first deployment: `admin` / `Admin@2026!` — must be changed immediately.
- Session persists across page refreshes (stored in browser). Expired sessions redirect to login.
- Logout button in top-right bar.

### Role-Based Access Control (RBAC)
Three roles with different permissions:

| Feature | Admin | Analyst | Viewer |
|---------|-------|---------|--------|
| View Dashboard, Feeds, Briefs, Maps | Yes | Yes | Yes |
| Download/Export PDFs | Yes | Yes | Yes |
| Submit Feedback Ratings | Yes | Yes | No |
| Generate Briefs, Train AI | Yes | Yes | No |
| Upload / Add to Feed | Yes | Yes | No |
| Run Keyword Refresh | Yes | Yes | No |
| Draw Relationship Links | Yes | Yes | No |
| User Management | Yes | No | No |
| Settings | Yes | No | No |
| Admin Monitoring | Yes | No | No |

- **Admin**: Full access including user management, settings, admin monitoring.
- **Analyst**: All intelligence features. Redirected to Intelligence Feed after login.
- **Viewer**: Read-only. All action buttons disabled. Redirected to Dashboard after login.

### Sidebar Navigation
Adapts to role. Admin sees all items; Analyst/Viewer see User Management and Settings hidden.

### Guided Walkthrough (Joyride Tours)
Every page has a built-in step-by-step guided tour that auto-starts on first visit.
- Tour tracks seen-state per user via localStorage.
- Re-trigger any time via **? (Help Circle)** button top-right.
- Admin only: **↺ (Reset Tours)** button clears seen-state for all pages and restarts current page tour — useful for demos.

### Tooltips
Every button, label, stat card, chart heading, and parameter has a hover tooltip (auto-dismisses after 3 seconds).

---

## 2. DASHBOARD

Command center showing the current intelligence landscape at a glance.

### Stat Cards (Top Row)
Five cards: Total Items, Critical, High, Medium, Low. Click any card to filter the Intelligence Feed by that severity.

### NER Situation Map (full description in Section 3)

### Intelligence Source Monitor Panel
Collapsible panel below stat cards showing real-time status for all 6 intelligence source types.
- **FETCH INTEL** (Dashboard header): triggers ALL 6 sources simultaneously.
- **SCAN SOCIAL MEDIA** (panel header): triggers 5 non-RSS sources only.
- Each source card: status badge (SCANNING/FETCHING/CRAWLING/IDLE/SETUP), progress bar, item count, last-fetched time, per-source FETCH button, drill-down to individual sites/channels.

Source types:
| Source | Color | What it monitors |
|--------|-------|-----------------|
| RSS Feeds | Green | 89 curated NER/national/Bangladesh/Myanmar news feeds |
| YouTube | Red | Subscribed channels + keyword searches (requires YOUTUBE_API_KEY) |
| Facebook | Blue | Configured Facebook pages (requires Facebook App credentials) |
| Telegram | Sky | Monitored channels via Telethon session (requires telegram_setup.py) |
| X / Twitter | Slate | Twitter accounts + keyword searches (currently disabled, API costs) |
| Firecrawl | Orange | Deep-crawl websites without RSS + keyword web searches (currently disabled, insufficient credits) |

### Unacknowledged Critical Alerts
Sticky panel: CRITICAL and HIGH items not yet acknowledged. **ACK** button marks as handled.

### Live Feed Panel
WebSocket real-time updates — new items appear without page refresh. LIVE/OFFLINE indicator top-right.

### Pattern Insights
Summary of detected threat patterns with escalation risk levels (CRITICAL/HIGH/MODERATE/LOW).

### Latest Intelligence (bottom section)
Six most recent items. Controls:
- **Priority Filter** dropdown: All Priority, 80+ (Critical), 60+ (High), 40+ (Medium)
- **Sort By** dropdown: Most Recent (date) or Highest Priority (priority score)
- **Delete button** (trash icon) on each card: permanently removes item after confirmation.
- **View Full Feed** link to Intelligence Feed.

### Trend Charts
7-day severity distribution bar charts.

---

## 3. NER SITUATION MAP

Leaflet-based interactive map of India's Northeast showing intelligence concentration by state and individual item markers.

### Map Layers
1. NASA Blue Marble satellite base tile (GIBS WMTS)
2. ESRI World Imagery detail layer
3. Dark vignette colour-temperature CSS overlay
4. Semi-transparent GeoJSON state polygons coloured by threat severity
5. Pulsating SVG markers for intelligence items at their geographic location
6. State name labels

### State Polygon Colours
States are coloured based on current severity concentration:
- Dark red / red: Critical or high-severity concentration
- Amber: Medium concentration
- Olive/dark: Low activity
- Border colours animated based on the temporal timeline window (see below)

### Item Markers
Individual intelligence items plotted at their mentioned location using a gazetteer of 80+ known NER/border locations. Marker colour and pulse rate reflect severity:
- Red pulsating: Critical
- Orange: High
- Yellow: Medium
- Grey: Low

Click a marker to see: title, severity badge, threat category, region, priority score, summary excerpt. Click the title to navigate to the full item in the Intelligence Feed.

### Phase 1: Temporal Intelligence Map — Timeline Slider

A time-range slider at the bottom of the map lets analysts filter the intelligence landscape to a specific time window.

- Drag the left/right handles to set a date window
- Map markers and state polygon colours update in real-time to show only items within the window
- The current window's date range is displayed above the slider
- The slider auto-advances to "now" each time the map is opened
- Dense graduation markers on the slider show days, making precise selection easy

**Use case:** Replay an escalation corridor. Drag the window back to see how threat concentration shifted across states over the past 7 days.

### Phase 2: Fullscreen Map Mode

Click the expand button (bottom-right of the compact map) to enter fullscreen mode:
- Map fills the entire viewport
- Full Leaflet controls available (zoom, pan, layer toggle)
- Timeline slider still works in fullscreen
- All relationship lines and marker popups work in fullscreen
- **Exit Fullscreen**: click the minimize button (bottom-right) or press Esc

### Phase 3: Relationship Polylines (LINKS Layer)

A relationship visualization layer draws lines between intelligence items that are connected in the relationship database. This is the "LINKS" toggle.

**How to use:**
1. Click the **⬡ LINKS** button (top-right of map, below zoom controls)
2. Button turns lime-green and shows a count: `⬡ LINKS (147)`
3. Lines appear between related markers on the map

**Filter panel:** When LINKS is active, a filter panel appears below the toggle button with checkboxes for each relationship type. Toggle individual types on/off.

**Clicking a relationship line** opens a popup showing:
- Title of Item A (left side)
- Title of Item B (right side)
- Relationship type and strength score (0–1)
- **Explain** button — fetches a one-sentence AI explanation of why these items are linked (lazy-loaded from Gemini Flash, cached after first fetch)

**Performance:** Map fetches relationships in chunks of 90 item IDs, draws up to 250 lines (sorted strongest first to show the most significant links).

**Line styles by relationship type:**
| Type | Colour | Style | Meaning |
|------|--------|-------|---------|
| same_incident | Orange (#f97316) | Solid, weight 2.5 | Same news cluster — progressive reports of one event |
| same_actor | Amber (#f59e0b) | Dashed 6-4, weight 1.5 | Share a militant group or organization |
| same_hotspot | Cyan (#06b6d4) | Dashed 4-4, weight 1.5 | Same actor–location pair from Knowledge Graph |
| same_pattern | Red (#ef4444) | Solid, weight 2.0 | Same detected threat pattern |
| semantic | Purple (#a855f7) | Fine dashed 2-5, weight 1.0 | Semantically similar (embedding cosine ≥ 0.72) |
| user_drawn | Lime (#a3e635) | Solid, weight 2.0 | Manually drawn by an analyst |

Default: all types enabled except `semantic` (too many lines, lower precision).

**Legend** is displayed on the left edge of the map showing all colour codes.

---

## 4. INTELLIGENCE FEED

Full searchable, filterable list of all classified intelligence items.

### Search Modes
- **Keyword Search** (default): matches titles and content
- **Semantic Search** (toggle): AI embedding search — finds contextually related items even when exact words don't match. Example: "border infiltration" finds "unauthorized entry" articles.

### Filters
- Severity (Critical / High / Medium / Low)
- State/Region (any NER state)
- Threat Category (Insurgency, Drug Trafficking, etc.)
- Date Range

### Feed Quality Filter (automatic)
The feed hides:
- LOW severity items (noise)
- Unprocessed items (still queued for AI)
- Duplicate articles (only the best summary shown — see Multi-Article Fusion)

Only processed, medium-to-critical, deduplicated items appear.

### Item Cards
Each card shows:
- **Relevance Rating bar** (1-6 scale) for analyst feedback
- **Title** with severity badge (red=Critical, orange=High, yellow=Medium)
- **Priority Score** (0-100): AI-assigned importance
- **Confidence Score** (0-100): AI certainty
- **Threat Trajectory**: ESCALATING / STABLE / DE-ESCALATING / NEW_THREAT
- **AI Summary**: Concise intelligence summary
- **Why It Matters**: Strategic significance
- **Early Warning Signal**: Future implications
- **Special Flags**: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, etc.
- **Tags**: Classification labels
- **Actors**: Named organizations/groups
- **Source** with link to original article
- **Fused Sources Badge** (if applicable): "X sources" — click to expand all covering outlets
- **Delete** (trash icon, top-right): permanently removes item after confirmation

### Multi-Article Fusion
When multiple outlets cover the same event:
- A blue "X sources" badge shows how many outlets covered the story
- The longest/best summary is the primary display; all sources cited
- Detection uses 6 methods: exact title matching, source URL deduplication, title word overlap, named entity overlap, compound keyphrase matching, same-source geographic clustering
- Runs both in real-time (as articles arrive) and as a scheduled batch every 30 minutes

### Sorting
- By publication date (newest first)
- By priority score (highest first)

### Export PDF
Green **Export PDF** button in feed header generates a PDF of the currently filtered results. Filename uses IST date in ddmmyyyy format.

### Pagination
20 items per page. Previous/Next buttons. Auto-scrolls to top on page change.

---

## 5. CROSS-BORDER INTELLIGENCE

Dedicated module split into two sections: Bangladesh and Myanmar.

### Quality Filters (stricter than Intelligence Feed)
- No LOW severity items
- No untranslated content (Bengali/Assamese/Hindi that failed translation is hidden)
- Processed items only

### Category Classification (auto-assigned)
- Diplomatic: bilateral relations, treaties, high-level engagements
- Defence: military operations, border force activity, arms seizures
- Internal Politics: domestic political events with cross-border implications
- Economics: trade, smuggling, sanctions

### Feedback Integration
Analyst ratings on cross-border items affect display priority within sections.

### Delete
Trash icon on each item for permanent removal.

---

## 6. DAILY BRIEF

Automated daily intelligence summary generated at 0600 IST. Access via **Daily Brief** in sidebar.

### Sections
- **Analyst Assessment**: AI strategic overview of the day's developments
- **NER Key Developments**: Top items from NE Indian states only (no international items here)
- **Cross-Border Intelligence**: Bangladesh and Myanmar categorized items (Diplomatic/Defence/Politics/Economics)
- **National News**: Relevant national-level developments
- **International News**: Strategic international items
- **Pattern Insights**: Escalation patterns from the Pattern Detection Engine
- **Document Insights**: Analysis from documents uploaded during this brief's period only

### Actions
- **REGENERATE BRIEF**: Force regenerate with latest data (auto-runs at 0600 IST)
- **EXPORT PDF**: Download as PDF with RESTRICTED classification headers

### Cross-Brief Deduplication
Items in one day's brief do NOT appear in subsequent briefs.

---

## 7. WEEKLY TRENDS

Visual analytics for the past 7 days. Charts:
- Severity Distribution (Critical/High/Medium/Low per day)
- Threat Type Breakdown (most active categories)
- Regional Distribution (most active NER states)
- Cross-Border Activity trend line

---

## 8. PATTERN DETECTION ENGINE

Automatically groups items to identify recurring threats and escalation corridors.

### Detection Logic
Clusters items sharing:
- Same region + threat type (e.g., "Manipur Insurgency")
- Same region + actor (e.g., "Assam ULFA")
- Same region + tag combination
- Cross-border activity keys

When 3+ items share a pattern key within a 7-day sliding window, a pattern is flagged.

### Escalation Risk Levels
- CRITICAL: 2+ critical-severity events in cluster
- HIGH: 5+ events
- MODERATE: 4+ events
- LOW: 3+ events

### Pattern Cards Show
- Region and threat detail
- Event count and time window
- Average priority score
- Severity breakdown
- Source diversity
- Sample article titles

### Scheduled
Pattern engine runs on a scheduled basis and after each batch fusion cycle. Can also be manually triggered via the admin compute endpoint.

---

## 9. KNOWLEDGE GRAPH

Entity relationship mapping cross-referencing actors, locations, and contexts across the full intelligence corpus. Surfaces connections no single article reveals.

### Actors Tab
Lists all identified actors (organizations, security forces, militant groups) with:
- Activity count (total events)
- Article count (how many articles mention them)
- Locations where active
- Threat types
- Cross-border flag

### Locations Tab
Lists all identified locations with:
- Activity count
- Actors seen there
- Border zone flag
- Associated states

### Actor Detail View
Click any actor card:
- Timeline (first seen / last seen)
- All locations with event counts
- Threat types
- Co-occurring actors (other actors appearing in same articles)
- Movement edges (actor-to-location connections with frequency)
- Related article titles

### Filters
- Cross-border only
- Border zones only
- Search by actor/location name

### Rebuild Graph
Click **Rebuild Graph** to regenerate from latest data. The graph is also rebuilt automatically before each nightly relationship batch.

---

## 10. RELATIONSHIP INTELLIGENCE

The Relationship Engine automatically discovers five types of connections between intelligence items and stores them as edges in the relationship database. These edges power the LINKS layer on the NER Situation Map and can be queried via API.

### Five Relationship Types (auto-computed)

**1. same_incident**
Two items belong to the same news cluster (assigned the same `cluster_id` by the fusion engine). They are progressive reports of the same event from different outlets. Strongest relationship type — strength 1.0.

**2. same_actor**
Two items share one or more organizations or militant groups, identified by cross-referencing both items against the Knowledge Graph actor nodes (`kg_actors` collection). Actor names are normalized (lowercase, trimmed) before matching. Strength is based on overlap count.

**3. same_hotspot**
Two items share an actor-location pair — both mention the same organization operating in the same geographic area. Cross-referenced against `kg_edges` (actor→location movement edges). Indicates a spatial hotspot with recurring activity.

**4. same_pattern**
Two items belong to the same detected threat pattern from the Pattern Detection Engine (`intelligence_patterns` collection). Pattern keys encode region + threat type + actor combinations. Strength reflects the pattern's escalation risk level (CRITICAL=0.95, HIGH=0.85, MODERATE=0.65, LOW=0.40).

**5. semantic**
Two items are semantically similar based on cosine similarity of their 1536-dimension OpenAI text embedding vectors. Threshold: cosine ≥ 0.72. Identifies topically related items that share no explicit actors or locations. Strength = cosine similarity score.

**6. user_drawn** (manual)
An analyst manually drew a connection between two items on the NER Situation Map or via the API. Always strength 1.0.

### How Relationships Are Computed
- **Nightly batch job**: Runs automatically at 03:00 IST (21:30 UTC) each night.
- Sequence: (1) Rebuild Knowledge Graph → (2) Detect Patterns → (3) Run all 5 relationship passes.
- A typical run on ~3,000 items produces ~65,000–70,000 edges in ~9 minutes.
- Results: last run produced same_incident: 2, same_actor: 0, same_hotspot: 0, same_pattern: 171, semantic: 1,640 — totalling 66,090 edges (including historical accumulation).

### Admin Manual Trigger
POST `/api/admin/relationships/compute` — runs batch without KG rebuild (safe, ~2-3 min).
With `rebuild_kg=true` flag — rebuilds KG + patterns first (~9 min total).

### Relationship API Endpoints
- `GET /api/relationships?item_ids=id1,id2,...` — edges for a set of item IDs (used by NER Map)
- `GET /api/relationships/stats` — edge counts by type (for admin dashboard)
- `GET /api/relationships/{edge_id}/explain` — lazy AI explanation for an edge (Gemini Flash, cached)
- `POST /api/relationships` — create a user-drawn edge (analyst manual link)
- `PATCH /api/relationships/{edge_id}` — confirm or soft-delete an edge
- `POST /api/admin/relationships/compute` — manual batch trigger (Admin only)

### User-Drawn Links
Analysts can manually link two items to record an observed relationship:
1. On the NER Map, select two markers and use the draw tool (future UI — currently via API)
2. Link is stored as `user_drawn` type with optional analyst note
3. Link appears immediately on the LINKS layer in lime-green
4. Soft-delete: PATCH with `user_deleted: true` — removes from map without deleting the record

### AI Edge Explanations
Click **Explain** on any relationship line popup:
- If explanation already cached: returns immediately
- If not cached: calls Gemini Flash to generate a 1-2 sentence explanation of strategic significance
- Explanation references both item titles, shared actors, locations, and threat escalation patterns
- Cached in database after first generation

---

## 11. ALERTS

Filtered view of CRITICAL and HIGH severity items requiring immediate attention.
- **ACK** button on each alert marks it as reviewed
- Acknowledged alerts move out of Dashboard's Unacknowledged panel but remain in full feed

---

## 12. KEYWORD ENGINE

Manages the intelligence-relevant keywords that drive RSS detection scoring.

### Keyword Types
- Primary Threat (Red): direct threat terms ("insurgency", "arms smuggling")
- Entity/Actor (Blue): organizations and actor-action combinations ("ULFA movement Assam")
- Geographic (Yellow): region-specific combinations ("Manipur violence")
- Cross-Border (Purple): border intelligence terms
- AI Emerging Signal (Green): AI-generated from recent patterns
- AI Expanded (Grey): synonym expansions of top keywords

### Keyword Scores (0–100)
Relevance score based on: frequency in recent items, association with high/critical articles, cross-border relevance, recency (time decay).

### Adaptive Learning
- HIGH/CRITICAL article → matching keywords boosted
- LOW relevance article → matching keywords decayed
- New keywords auto-extracted from high-priority articles

### AI Refresh
Click **AI Refresh Keywords** → Claude AI analyzes recent high-priority intelligence, generates emerging signal keywords, expands top keywords into synonyms.

### Manual Keyword Addition
1. Search for a keyword — if not found, **"Add it manually?"** prompt appears
2. Select Type and Score
3. Click **+ Add Keyword**
Duplicates rejected (case-insensitive matching).

---

## 13. TRAINING & FEEDBACK

Central hub for shaping AI intelligence priorities.

### Analyst Feedback (1-6 Rating Scale)
Every item in the Intelligence Feed has a 1-6 rating bar.

| Rating | Label | Effect |
|--------|-------|--------|
| 1 | Entirely Irrelevant | Suppresses similar content |
| 2 | Mostly Irrelevant | Reduces weight |
| 3 | Slightly Relevant | Neutral |
| 4 | Moderately Relevant | Mild positive |
| 5 | Highly Relevant | Boosts similar content |
| 6 | Extremely Relevant | Strong priority boost |

- One rating per device per item (device fingerprinting prevents manipulation)
- Admin-configurable max ratings per item (default: 20)

### Key Metrics
Total Ratings, Items Rated, Analysts (unique devices), Avg Rating, Training Queue count.

### Training Effectiveness Score
0–100% measuring AI/analyst alignment. Grades: EXCELLENT (80+), GOOD (65+), MODERATE (50+), NEEDS_IMPROVEMENT (35+), POOR (<35). Shows 5 biggest gaps and 5 best alignments.

### Upload Intelligence URLs
Paste any URL → scrapes content → AI analysis → adds to training queue. Optional relevance tag 1-6.

### Upload Documents
PDF, DOCX, TXT. System extracts text and runs AI analysis.

### Train Rhino Drishti Button
Starts training pipeline: scrape URLs → extract document text → Claude Haiku AI analysis → extract regions/actors/threat categories/keywords. Live progress tracker.

### Analyst Preferences & Noise Patterns
Aggregated view of what analysts consistently rate high (preferred regions/threats) and low (noise patterns).

### Scoring Integration
`final_score = base_ai_score + training_bias + feedback_bias`
`training_bias = log(total_ratings + 1) × (avg_rating - 3.5)`

### Active Feedback Bias (Live AI Pipeline)
When ACTIVE badge shows, analyst preferences are injected into every new article classification:
- Upweighted: regions/categories consistently rated high → +3 to +20 priority score boost
- Downweighted: regions/categories consistently rated low → priority score reduction
- Bias recalculates every 5 minutes (cache TTL)
- Configure influence level and feedback window in Settings

### Activity Log
Session-level log (not per-rating). Columns: Timestamp, Device, Activity Type, Volume, Impact (AI-generated summary of what the system learned).
- Training sessions logged when "Train Rhino Drishti" is clicked
- Feedback sessions auto-created when an analyst submits 5+ ratings

---

## 14. MANUAL INTELLIGENCE UPLOADS

Three distinct workflows. Access via **Manual Int Uploads** in sidebar.

### Workflow 1: Upload File
Upload PDF, DOCX, XLSX, or TXT → AI contextual threat analysis → Contextual Intelligence Assessment output.

### Workflow 2: Analyze URL
Paste URL → AI fetches and analyzes → Contextual Intelligence Assessment including:
- Executive Summary
- Threat Classification (severity, category, confidence)
- Pattern Analysis (escalation indicator)
- Relevance Assessment (1-10 score, affected regions)
- Key Entities (actors, locations, events — clickable badges for keyword bank)
- Recommended Actions (IMMEDIATE/HIGH/MEDIUM/LOW)
- Cross-References (how the document connects to existing platform intelligence)
- Intelligence Gaps

### Workflow 3: Add to Feed (Direct)
Add a URL directly to the Intelligence Feed with user-defined parameters, bypassing AI analysis:
- Title (auto-scraped or manual)
- Severity (Critical/High/Medium/Low)
- Priority Score (0-100)
- Threat Category (18 options)
- Region/State (13 options)
- Summary
- Cross-Border checkbox

### Add to Feed After Analysis
After analyzing a URL, click **Add to Feed** on the analysis card → opens pre-filled modal with AI's classification → review/adjust → confirm.

### Adding Keywords from Analysis Results
In the Key Entities section of any analysis card, click entity badges to select them → **"+ ADD TO KEYWORD BANK"** bar appears → click to add all selected to Keyword Engine (parenthetical descriptions auto-stripped, duplicates skipped).

### Duplicate Detection
Same URL already in feed → "This URL already exists" error.

---

## 15. REPORTS & PDF GENERATION

Access via **Reports** in sidebar (all roles).

### Report Types

**1. Regional Threat Summary**
Select NER state + optional date range → PDF with executive summary, severity breakdown, threat category distribution, items grouped by priority.

**2. Cross-Border SITREP**
Select Bangladesh or Myanmar + optional date range → PDF with situation overview, cross-border signal count, threat distribution, items by category.

**3. Custom Filtered Report**
Combine any filters: Region, Threat Category, Severity, Keywords, Source Name, Min Priority, Date Range, Cross-Border flag. PDF with executive summary, regional/category distribution, all items by severity.

### PDF Filename Convention
IST date in ddmmyyyy format: `Rhino_Drishti_Manipur_Threat_01042026_24042026.pdf`

### Quick Export from Intelligence Feed
**Export PDF** button in feed header — exports currently filtered view without navigating to Reports.

---

## 16. PLATFORM UPDATES & NOTIFICATIONS

### How Notifications Work
At login, system checks for updates since last visit:
- 1-3 major updates: sequential toast messages (5 seconds each, oldest first)
- 4+ major updates: latest 3 toasts + "More Updates Available" modal
- Only minor updates: one generic "bug fixes" toast
- No new updates: no notification

### Platform Updates Page
Timeline of all updates with version number, MAJOR/MINOR badge, message, date, author, and Preview button.

### Admin Controls
Create Update: Version number, Priority (Major/Minor), Message → Publish Update.
Preview: Enter version → see the toast notification without affecting user notification state.

---

## 17. USER MANAGEMENT

Admin only. Access via **User Management** in sidebar.

### User List
Columns: Username, Name, Role (color-coded), Status (Active/Inactive — click to toggle), Last Login, Actions.

### Creating Users
Click **Create User** → Username, Email, Full Name, Role, Password (min 8 chars). Generate button for 14-char random password. Copy button. Passwords shown only once.

### Password Reset
Key icon → new password (manual or generated) → Copy → Reset.

### Deactivating/Deleting
Toggle Active/Inactive status to block login. Trash icon for permanent delete (cannot delete own account).

---

## 18. SETTINGS

Admin only.

### Local Database Storage Card
Shows current storage mode: MongoDB Atlas (cloud), Local-Tailscale (VPN), Local-Direct (LAN). Displays document count, database size, migration log, and Setup Wizard button.

### Source Effectiveness Card
Each non-RSS source: item count, severity distribution bar, AI processing rate, latest catch title, high-value score (Critical + High count).

### News Retention Window
Options: 7/14/30/60/90/180/365 days. Affects Dashboard stats, Intelligence Feed count, alerts, pattern detection window.

### Pipeline Status
System health: total items, AI processing rate, RSS source count, scheduler configuration.

### Feedback Bias Configuration
**Feedback Window**: Rolling 30 Days (adapts quickly) or All Time (cumulative learning).
**Influence Level**: Mild (+3 pts max), Moderate (+7 pts max, default), Strong (+15 pts max), Very Strong (+20 pts max).

---

## 19. ADMIN MONITORING

Admin only. Access via **Admin Monitoring** in sidebar.

### API Spend Tracker
Tracks actual LLM API cost across all providers in real time.

Displays:
- Total API spend to date (USD)
- Daily spend breakdown chart (last 30 days)
- Per-model breakdown table: model name, provider, input tokens, output tokens, cost

Current models tracked:
- `google/gemini-2.0-flash-lite-001` (Stage 1 classifier, via OpenRouter)
- `google/gemini-2.5-flash` (Stage 2 classifier, via OpenRouter)
- `google/gemini-2.5-flash` (AI explanations, daily brief, keyword refresh)

### Filter Cascade Widget

Shows the health and pass/fail statistics for the 4-stage AI filter cascade in real time.

**Stage 0 — Keyword Filter:**
- Status badge: HEALTHY / DEGRADED / FAILING
- Pass rate: % of ingested articles passing keyword relevance check
- Items filtered out today

**Stage 0.5 — Semantic Embedding Filter:**
- Status badge with cosine similarity threshold shown
- Pass rate vs. baseline
- Calibration note: how the threshold was set

**Stage 1 — Gemini Flash-Lite Classifier:**
- Status badge: HEALTHY / DEGRADED / FAILING
- API key present indicator (OPENROUTER_API_KEY)
- Fail-open rate: % of items that bypassed Stage 1 due to API errors
- Fail-open threshold: FAILING if >85% fail-open, DEGRADED if >40%
- Items classified vs. fail-opened today

**Stage 2 — Gemini 2.5 Flash Deep Classifier:**
- Items processed, approved, rejected
- Cost per item
- Fail-open fallback rate

**Cascade Summary:**
- Total items ingested today
- % reaching Stage 2 (Gemini)
- Estimated cost at current rate
- System recommendation (healthy / needs attention / critical)

### Filter Threshold Simulator

An interactive tool for analysts and admins to model the impact of changing filter settings before applying them — without affecting the live system.

**Layout: two-column (sliders | simulated funnel)**

Left panel — Sliders:
- **Stage 0.5 min_sim**: Minimum cosine similarity threshold for the semantic filter (0.10–0.70, default 0.35). Higher = more aggressive filtering.
- **Stage 1 enabled**: Toggle — disable Stage 1 to let all Stage 0.5 survivors reach Stage 2 directly (risky, expensive).
- **Max scan/cycle**: Maximum articles to ingest per scheduler cycle (10–500, default 200).
- **Max Gemini/cycle**: Maximum items to send to Stage 2 Gemini 2.5 Flash per cycle (5–100, default 25).

Right panel — Simulated Funnel:
- Horizontal bar chart showing item counts through each stage: Ingested → After S0 → After S0.5 → After S1 → To Gemini
- Updates live as sliders move (no API call needed — all client-side simulation)
- Shows estimated Gemini calls/day and estimated ₹/day cost

**Impact Assessment panel (below funnel):**
- Coverage risk rating: LOW / MEDIUM / HIGH (with warning badge if min_sim > 0.45)
- % of articles filtered before Gemini
- Items filtered by S0.5 per cycle (estimated)
- Based on today's actual pipeline data as baseline

**Apply Settings button:**
1. Click → detailed impact modal
2. Modal shows: filter rate, ₹/day savings estimate, coverage risk
3. Confirm → POST `/admin/filter-settings` → pipeline picks up new values within 5 minutes

---

## 20. THE 4-STAGE AI PIPELINE

Every article ingested goes through a 4-stage cascade filter before appearing in the Intelligence Feed.

### Stage 0 — Keyword Filter
Fast keyword matching against the Keyword Engine. Articles with no NER-relevant keywords are immediately rejected. Pass rate typically 60-70%.

### Stage 0.5 — Semantic Embedding Filter
Articles that pass Stage 0 have their cosine similarity computed against a reference embedding centroid of known high-relevance NER security content. Articles scoring below the threshold (default: 0.35) are rejected. Runs in-process using pre-computed embeddings — no API call needed. Pass rate typically 70-80% of Stage 0 survivors.

### Stage 1 — Gemini Flash-Lite Rapid Classifier (OpenRouter)
Model: `google/gemini-2.0-flash-lite-001` via OpenRouter API.
A binary relevance classifier with a strict 10-rule NER security framework. Outputs RELEVANT or NOT_RELEVANT. Fail-open: if the API is unavailable, items pass to Stage 2 (never miss intelligence due to API downtime). Pass rate typically 50-70% of Stage 0.5 survivors.

### Stage 2 — Gemini 2.5 Flash Deep Classifier (OpenRouter)
Model: `google/gemini-2.5-flash` via OpenRouter API.
Full 10-step military intelligence classification producing all item fields:
- AI Summary, Why It Matters, Potential Impact, Attention Level
- Threat Category, Severity (low/medium/high/critical)
- Priority Score (0-100), Confidence Score (0-100)
- Threat Trajectory (ESCALATING/STABLE/DE-ESCALATING/NEW_THREAT)
- Regions, Actors, Special Flags, Early Warning Signal
- Named Entity Extraction (persons, organizations, locations)
- Sifter Level and triggers
- Cross-border flag, Countries Involved

### Prompt Caching
System/instruction blocks use prompt caching (`cache_control: ephemeral`) to reduce costs on repeated classifications. Cache TTL: 5 minutes.

### Feedback Bias Injection
When Active Feedback Bias is enabled, analyst preference data is appended to the Stage 2 prompt: "Analyst Feedback Calibration: upweight these regions/categories, downweight these."

### Multi-lingual Support
Bengali, Assamese, and Hindi content is auto-translated to English before Stage 2 classification using Claude.

### Scheduled Fetch Cycles
- Grassroots sources: every 60 minutes (SATP, Ukhrul Times, Frontier Myanmar, etc.)
- Standard RSS: every 30 minutes
- Established sources: every 12 hours
- Retry unprocessed: every 15 minutes
- Embedding backfill: every 6 hours
- Batch fusion: every 30 minutes
- Fading pass: every 1 hour
- Relationship batch: every night at 03:00 IST (21:30 UTC)
- Daily brief: every day at 06:00 IST (00:30 UTC)

### Item Visibility (Fading Engine)
Items have a `visibility_score` that decays over time. Very old low-severity items fade out of the feed automatically. Items with pinned flag never fade. Critical/high items have slower decay.

### Severity Derivation
Severity is derived from priority_score, not stored independently:
- 80–100 → Critical
- 60–79 → High
- 40–59 → Medium
- 0–39 → Low

---

## 21. GLOSSARY

| Term | Meaning |
|------|---------|
| NER | North Eastern Region — Assam, Manipur, Mizoram, Meghalaya, Nagaland, Tripura, Arunachal Pradesh |
| Priority Score | AI-assigned importance 0-100. Higher = more urgent. Drives severity label. |
| Confidence Score | AI certainty 0-100 about its classification |
| Threat Trajectory | ESCALATING / STABLE / DE-ESCALATING / NEW_THREAT |
| Fusion | Multi-article clustering — grouping multiple outlets covering the same event |
| Cluster ID | ID assigned to a group of fused articles |
| Knowledge Graph | Entity-relationship map of all actors and locations extracted from intelligence |
| KG | Abbreviation for Knowledge Graph |
| Pattern | A recurring threat cluster: same region + actor/threat type, 3+ events in 7 days |
| Escalation Risk | CRITICAL / HIGH / MODERATE / LOW — how serious a detected pattern is |
| Relationship Edge | A connection between two intelligence items (same_incident, same_actor, etc.) |
| Stage 0 | Keyword filter — fast keyword matching |
| Stage 0.5 | Semantic embedding filter — cosine similarity check |
| Stage 1 | Gemini Flash-Lite rapid binary classifier |
| Stage 2 | Gemini 2.5 Flash deep 10-step military classifier |
| Fail-open | When API is unavailable, items pass through rather than being dropped |
| Semantic Search | Embedding-vector based search — finds related articles by meaning, not exact words |
| JWT | JSON Web Token — used for authentication. Expires after 24 hours. |
| RBAC | Role-Based Access Control (Admin / Analyst / Viewer) |
| ACK | Acknowledge — marking a critical alert as reviewed |
| SITREP | Situation Report — a cross-border intelligence PDF format |
| PIB | Press Information Bureau — official Government of India press releases |
| ULFA | United Liberation Front of Asom — major insurgent group in Assam |
| NSCN | Nationalist Socialist Council of Nagaland — major insurgent group |
| BGP | Border Guard Police (Bangladesh) |
| BGB | Border Guard Bangladesh |
| Tatmadaw | Myanmar military |
| Cosine Similarity | Mathematical similarity score between two embedding vectors (0 to 1) |
| Embedding | 1536-dimension vector representation of text content for semantic comparison |
| Fading Engine | System that decays visibility of old low-severity items over time |
| same_incident | Relationship type: both items report the same event (same cluster) |
| same_actor | Relationship type: both items involve the same organization |
| same_hotspot | Relationship type: both items share an actor-location pair |
| same_pattern | Relationship type: both items belong to the same detected pattern |
| semantic | Relationship type: items are topically similar (cosine ≥ 0.72) |
| user_drawn | Relationship type: manually linked by an analyst |
| LINKS layer | The map overlay showing relationship polylines between item markers |
| OpenRouter | API gateway used to access Gemini models for Stage 1 and Stage 2 classification |
| APScheduler | Python background job scheduler running all timed tasks |

---

## 22. TECHNICAL ARCHITECTURE (for reference)

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Tailwind CSS + shadcn/ui + Recharts + Leaflet |
| Backend | FastAPI (Python 3.11) + WebSockets |
| Database | MongoDB Atlas (Motor async driver) |
| AI — Stage 1 | google/gemini-2.0-flash-lite-001 via OpenRouter |
| AI — Stage 2 | google/gemini-2.5-flash via OpenRouter |
| AI — Briefs/Docs | google/gemini-2.5-flash via OpenRouter |
| Embeddings | OpenAI text-embedding-3-small (1536 dimensions) |
| Map | Leaflet + NASA GIBS WMTS + ESRI World Imagery |
| RSS Parsing | feedparser |
| Web Scraping | BeautifulSoup4 + httpx (async) |
| PDF Generation | fpdf2 |
| Background Jobs | APScheduler (9 scheduled tasks) |
| Document Processing | PyPDF2, python-docx, openpyxl |
| Real-time | WebSocket (native FastAPI) |
| Deployment | Render (backend) + Vercel (frontend) |

### Key Collections (MongoDB)
- `intelligence_items` — all classified news items
- `item_relationships` — relationship edges between items
- `kg_actors` — knowledge graph actor nodes
- `kg_locations` — knowledge graph location nodes
- `kg_edges` — actor-location movement edges
- `intelligence_patterns` — detected threat patterns
- `daily_briefs` — generated daily briefs
- `rss_sources` — configured RSS feed sources
- `uploaded_documents` — manual upload records
- `intelligence_feedback` — analyst ratings
- `training_data` — training queue items
- `admin_settings` — pipeline threshold configuration

---

*Last updated: May 2026. Covers all features through Phase 3 of the Intelligence Relationship Map implementation.*
