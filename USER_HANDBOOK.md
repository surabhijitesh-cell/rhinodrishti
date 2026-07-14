# Rhino Drishti — User Handbook

## Complete Guide for Intelligence Analysts

---

## Table of Contents

1. [Authentication & Access Control](#1-authentication--access-control)
2. [Getting Started](#2-getting-started)
3. [Dashboard](#3-dashboard)
4. [Intelligence Feed](#4-intelligence-feed)
5. [Cross-Border Intelligence](#5-cross-border-intelligence)
6. [Periodic Briefs (Daily / Fortnightly / Monthly)](#6-periodic-briefs-daily--fortnightly--monthly)
7. [Custom Brief Generator](#7-custom-brief-generator)
8. [Trends Intelligence Center](#8-trends-intelligence-center)
9. [Pattern Detection](#9-pattern-detection)
10. [Knowledge Graph](#10-knowledge-graph)
11. [Alerts](#11-alerts)
12. [Keyword Engine](#12-keyword-engine)
13. [Training & Feedback](#13-training--feedback)
14. [Manual Intelligence Uploads](#14-manual-intelligence-uploads)
15. [Intelligence Reports](#15-intelligence-reports)
16. [Platform Updates & Notifications](#16-platform-updates--notifications)
    - 16.1 [Push Notifications (Mobile & Desktop)](#161-push-notifications-mobile--desktop)
17. [Faultline Intelligence & PAOI Monitoring](#17-faultline-intelligence--paoi-monitoring)
    - 17.1 [Priority Areas of Interest (PAOI)](#171-priority-areas-of-interest-paoi)
    - 17.2 [Faultline Cards & Watchlist](#172-faultline-cards--watchlist)
    - 17.3 [Faultline Scoring & Time Decay](#173-faultline-scoring--time-decay)
    - 17.4 [Monthly Faultline Analysis Report](#174-monthly-faultline-analysis-report)
18. [Social Media Intelligence & Sentiment Pulse](#18-social-media-intelligence--sentiment-pulse)
19. [Flagging Intelligence to Commanders](#19-flagging-intelligence-to-commanders)
20. [User Management](#20-user-management)
21. [API & Pipeline Monitor](#21-api--pipeline-monitor)
22. [Settings](#22-settings)
    - 22.1 [Local Database Storage Card](#221-local-database-storage-card)
    - 22.2 [Source Effectiveness Card](#222-source-effectiveness-card)
23. [Local Database Setup Wizard](#23-local-database-setup-wizard)
24. [How the AI Pipeline Works](#24-how-the-ai-pipeline-works)
25. [Glossary](#25-glossary)

---

## 1. Authentication & Access Control

### Login
- Open the application URL — you will be presented with the **Login** screen
- Enter your **username** (or email address) and **password**
- Click **Authenticate** to log in
- Use the **eye icon** to toggle password visibility
- Invalid credentials display an error message — contact your administrator if locked out

### Default Admin Account
On first deployment, the system automatically creates an admin account:
- **Username:** `admin`
- **Password:** `Admin@2026!`
- **IMPORTANT:** Change this password immediately after first login via User Management

### Roles & Permissions

| Feature | Admin | Analyst | Viewer |
|---------|-------|---------|--------|
| View Dashboard, Feeds, Briefs | Yes | Yes | Yes |
| Download/Export PDFs | Yes | Yes | Yes |
| Submit Feedback Ratings | Yes | Yes | No |
| Generate Briefs, Train AI | Yes | Yes | No |
| Upload/Analyze/Add to Feed | Yes | Yes | No |
| Run Keyword Refresh | Yes | Yes | No |
| Flag Articles to Commanders | Yes | Yes | No |
| Custom Brief Generator | Yes | No | No |
| API & Pipeline Monitor | Yes | No | No |
| User Management | Yes | No | No |
| Settings | Yes | No | No |

**Admin** — Full access including user creation, password resets, system settings, the Custom Brief Generator, and the API & Pipeline Monitor.

**Analyst** — Can access all intelligence features (feeds, briefs, training, uploads, feedback, flagging). Cannot access User Management, Settings, the Custom Brief Generator, or the API & Pipeline Monitor.

**Viewer** — Read-only access. Can view all intelligence data and download PDFs. All action buttons are disabled.

### Session Management
- Sessions last **24 hours** (JWT token expiry)
- Token persists across page refreshes (stored in browser)
- If your session expires, you'll be automatically redirected to the Login page

---

## 2. Getting Started

### What is Rhino Drishti?
Rhino Drishti is an AI-powered military intelligence aggregation and analysis platform for monitoring India's North Eastern Region (NER), Bangladesh, and Myanmar. It automatically collects news and social media from RSS feeds, YouTube, Telegram, Facebook, Instagram and Twitter/X, runs AI classification using a military intelligence framework with dynamic analyst feedback bias, detects patterns, monitors strategic faultlines within Priority Areas of Interest (PAOI), tracks social-media sentiment, and generates Daily, Fortnightly and Monthly intelligence briefs.

### Navigation
The sidebar contains all pages:
- **Dashboard** — Overview of the intelligence landscape
- **Intelligence Feed** — Full searchable list of classified items
- **Cross-Border** — Items specifically involving cross-border activity
- **Periodic Briefs** — Daily, Fortnightly and Monthly automated intelligence briefs
- **Custom Brief Generator** — Chat-driven, PAOI-focused brief builder (Admin only)
- **Trends** — Trends Intelligence Center: stability index, severity trends, cross-border correlation
- **Faultlines** — PAOI-linked faultline monitoring with scoring and monthly reports
- **Patterns** — Detected threat patterns across regions
- **Knowledge Graph** — Actor-location relationship mapping
- **Alerts** — Critical and high-severity items requiring attention
- **Keyword Engine** — AI-powered keyword management for detection
- **Training & Feedback** — Rate articles, upload training data, monitor AI learning
- **Manual Int Uploads** — Analyze articles, upload documents, or add URLs directly to the feed
- **Reports** — Regional, Cross-Border and Custom filtered PDF reports
- **User Management** — Create/manage users (Admin only)
- **API & Pipeline Monitor** — API spend, credit balance, filter health, social scraping controls (Admin only)
- **Settings** — Configure retention, feedback limits, AI bias (Admin only)
- **Platform Updates** — Timeline of every version update
- **User Handbook** — This guide

---

## 3. Dashboard

The Dashboard is your command center showing the current intelligence landscape at a glance.

### Stat Cards (Top Row)
- **Total Items / Critical / High / Medium / Low**: Click any stat card to filter the Intelligence Feed by that severity level

### Intelligence Source Monitor Panel
The collapsible panel shows real-time status for **6 intelligence source types**.

**Two fetch controls:**
- **FETCH INTEL** — triggers ALL sources simultaneously
- **SCAN SOCIAL MEDIA** — triggers the social sources only (YouTube, Telegram, Facebook, Instagram, Twitter/X)

**Source cards, in order:**
| Source | What it monitors |
|--------|-----------------|
| **RSS Feeds** | Curated news feeds (regional NER, national, Bangladesh, Myanmar, government PIBs) |
| **YouTube** | Subscribed channels and keyword searches — requires `YOUTUBE_API_KEY` |
| **Telegram** | Monitored channels via a Telethon session |
| **Facebook** | Public posts scraped via Apify — requires `APIFY_TOKEN` |
| **Instagram** | Public posts scraped via Apify — requires `APIFY_TOKEN` |
| **Twitter/X** | Tweets scraped via Apify — requires `APIFY_TOKEN` |

Facebook, Instagram and Twitter/X each show a small **Social Pulse** badge (▲ positive % / ▼ negative %) next to the Fetch button — see [Section 18](#18-social-media-intelligence--sentiment-pulse). A combined **Social Media Pulse Indicator** sits in the panel header, to the left of the Scan Social Media button, averaging sentiment across all four social platforms.

Click any source card to open a live-feed widget for that source (Raw vs. AI-Curated toggle). The RSS card instead opens a static list of configured feeds.

### Custom Analytics Workspace
Below the source monitors, admins and analysts can build and save personal chart panels from any combination of intelligence metrics — pick the fields, pick the chart type, save it to your Dashboard for next time.

### Tooltips & Guided Walkthrough
Tooltips appear on every UI element (hover to see, auto-dismisses after 3 seconds). Each page has a built-in guided tour — re-trigger via the **?** button in the top-right bar. Admins can reset all tours with the **↺** button.

### Other Dashboard Sections
- **NER Threat Map** — Visual map of India's Northeast with threat concentration by state
- **Unacknowledged Critical Alerts** — Sticky panel of CRITICAL/HIGH items pending acknowledgement
- **Live Feed Panel** — Real-time WebSocket updates of new intelligence items
- **Pattern Insights** — Summary of the most significant detected threat patterns
- **Latest Intelligence** — Most recent items with Priority Filter and Sort By controls

---

## 4. Intelligence Feed

The full searchable, filterable list of all classified intelligence items.

### Search
- **Keyword Search** (default): Searches titles and content
- **Semantic Search** (toggle): AI-powered search that finds contextually related items

### Filters
Severity, State/Region, Threat Category, Date Range

### Item Cards
Each intelligence item shows:
- **Relevance Rating** (top): 1-6 scale for analyst feedback
- **Flag Icon** (top-right): Click to flag the article and send to a commander. If already flagged, the icon appears **red and filled**
- **Source Emblem**: a small platform icon (RSS / YouTube / Telegram / Facebook / Instagram / Twitter) so you can tell at a glance where an item came from
- **Title** with severity badge (red=Critical, orange=High, yellow=Medium)
- **Priority Score** (0-100) and **Confidence Score** (0-100)
- **Threat Trajectory**: ESCALATING / STABLE / DE-ESCALATING / NEW_THREAT
- **AI Summary**, **Why It Matters**, **Early Warning Signal**
- **Special Flags**: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, etc.
- **Comment Sentiment Tag** (Facebook/Instagram/Twitter/YouTube items only): ▲ green / ▼ red percentages showing what real commenters on that post feel about the situation — see [Section 18](#18-social-media-intelligence--sentiment-pulse)
- **Tags**, **Actors**, **Source** with link
- **Fused Sources Badge**: Shows "X sources" when multiple outlets cover the same story

### Feed Quality Filter
- **LOW severity** items are hidden
- **Unprocessed** items are hidden
- **Duplicate articles** are deduplicated — only the best summary is shown

### Multi-Article Fusion
When multiple sources cover the same event, a blue **"X sources"** badge appears. Click to expand and see all sources. Detection uses 6 methods: exact title matching, URL deduplication, title word overlap, named entity overlap, compound keyphrase matching, and geographic clustering.

### Export PDF
Click the green **Export PDF** button in the feed header to generate a PDF brief of currently filtered results.

### Pagination
20 items per page with Previous / Next navigation.

---

## 5. Cross-Border Intelligence

Dedicated module for monitoring intelligence involving India's borders with Bangladesh and Myanmar.

### Geographic Split
- **Bangladesh**: Border incidents, Rohingya movement, BGP/BGB activity, Dhaka politics with NER impact
- **Myanmar**: Border activity, Tatmadaw operations, Chin/Sagaing/Rakhine spillover, NSCN-K cross-border operations

### Category Classification
Each item is auto-categorized: **Diplomatic**, **Defence**, **Internal Politics**, or **Economics**

### Quality Filters
No LOW severity items. No untranslated content. Processed items only.

---

## 6. Periodic Briefs (Daily / Fortnightly / Monthly)

One page, three tabs — **Daily**, **Fortnightly**, and **Monthly Strategic**. Switch tabs at the top of the page.

### Daily Brief

Automated intelligence summary generated at **0600 IST** each day.

**Sections:**
- **NER Key Developments**: Top items from Northeast Indian states only
- **Cross-Border Intelligence**: Categorized Bangladesh and Myanmar news
- **National News**: National-level developments affecting NER security
- **International News**: Strategic international items
- **Pattern Insights**: Detected escalation patterns
- **Faultline Section**: HIGH/CRITICAL faultlines with PAOI tags
- **Social Media Pulse**: Sentiment breakdown (positive/negative %) per platform for the last 24 hours
- **Document Insights**: Analysis from documents uploaded during the current brief period

**Actions:** **REGENERATE BRIEF** (force regenerate with latest data), **EXPORT PDF**.

**Cross-Brief Deduplication:** Items included in one day's brief are NOT repeated in subsequent briefs.

### Fortnightly & Monthly Strategic Briefs

AI-generated strategic assessments covering a 15-day or full-month period, built from the entire intelligence corpus for that window — not just headlines.

**Navigating periods:** Use the **< Prev / Next >** controls to move between periods. If a brief hasn't been generated yet for the selected period, click **Generate** (Monthly briefs can take a few minutes — the page polls automatically and updates when ready).

**Sections in every Fortnightly/Monthly brief:**
- **Commander's Priority Dashboard** — verbal status strip for every PAOI (no raw scores)
- **PAOI Deep-Dives** — per-priority-area situation overview, most impactful events (with location, what happened, why it matters, linkages), overall assessment, and actionable recommendations, each with its own **Situation Map** (state/border outlines colour-coded by severity, clustered event markers)
- **Regional/Period Overview** — total items, critical/high counts, cross-border count, severity distribution, State Stability Index table
- **Social Media Pulse** — positive/negative sentiment per platform for that brief's own period (Facebook, Instagram, Twitter/X, YouTube)
- **Previous Period Recap** — how key numbers moved since last period
- **Executive Assessment / State-wise Security Assessment** — sorted most-critical-state-first, each state section expandable with analyst notes attachable inline
- **Cross-Border Threat Analysis**
- **Predictive Scenarios**
- **Commander Action Matrix** (Monthly only)
- **Mitigation Playbook**
- **Stability Trend** — historical 2×4 minigraph panel (one chart per NER state) with a Heatmap toggle and a 3/6/12-fortnight or all-time period selector

**Export options:** **Brief PDF**, **Combined PDF** (Monthly only — brief + Faultline Analysis Report in one file), and **NotebookLM** (copies a NotebookLM-formatted text export to your clipboard for use in Google NotebookLM).

**Analyst Enhancement notes** — any note you attach to an intelligence card is automatically pulled into the relevant brief section when it's next generated.

---

## 7. Custom Brief Generator

*Admin only.* Located at **Custom Brief Generator** in the sidebar.

A chat-driven tool for building a one-off, precisely-scoped intelligence brief instead of waiting for the next scheduled Daily/Fortnightly/Monthly cycle.

### How to use it
1. Type what you want in the chat panel on the left — e.g. *"fortnightly brief focused on Bangladesh border infiltration and the Jamaat-e-Islami faultline"*
2. The assistant replies and builds a structured **specification** (report type, PAOI focus, granularity, commander emphasis, custom notes), shown in the **Current Specification** card on the right
3. Refine the spec with further chat messages if it's not quite right
4. Pick a **period** (year/month, or for fortnightly output, Period 1 "1st–15th" or Period 2 "16th–end")
5. Click **Generate Brief** — takes roughly 30–90 seconds while PAOI synthesis runs
6. Download the resulting **PDF**, or find it later under **Past Briefs**

### Other features
- **Saved Configurations** — reload or delete a specification you built earlier without re-chatting
- **New Session** — clears the chat and starts a fresh specification
- **Past Briefs** — every brief you've generated this way, each with its own PDF download and delete button

This tool shares its PAOI-narrative format with the Fortnightly/Monthly briefs — it's the reference format they're built from — but is scoped to exactly what you ask for, on demand.

---

## 8. Trends Intelligence Center

Visual analytics for spotting shifts in the threat landscape over time. Range selector at the top: **7 Days / 30 Days / 90 Days / 1 Year**.

- **Strategic Stability Index** — clickable per-state cards, 0–100 score with a concern level (CRITICAL / ELEVATED / MONITOR / STABLE), showing item count, active actors, velocity and cross-border % for that state
- **State Severity Evolution** — multi-line chart, one line per state, daily incident counts
- **Severity Trend** — stacked area chart of all items by severity across the selected range
- **Cross-Border Correlation** — per-border (Bangladesh/Myanmar) chart comparing border-country events against correlated NER activity
- **Threat Category Analysis** — bar chart of the top categories by volume
- **Top Actors** — bar chart of the most-mentioned actors/groups
- **State Drill-Down** — click any state card or state-activity bar to see that state's top locations/districts, active actors, threat categories, and its own daily-severity mini chart

---

## 9. Pattern Detection

The Pattern Detection Engine automatically groups intelligence items to identify recurring threats.

### How Patterns Are Detected
Clusters of 3+ items sharing same region + threat type, same region + actor, or cross-border activity keys within a 7-day window.

### Escalation Risk Levels
- **CRITICAL**: 2+ critical-severity events in the pattern
- **HIGH**: 5+ events, **MODERATE**: 4+ events, **LOW**: 3+ events

---

## 10. Knowledge Graph

Entity relationship mapping that surfaces connections across the entire intelligence corpus.

**Actors Tab**: Lists identified actors with activity count, locations, threat types, and cross-border flag.
**Locations Tab**: Lists locations with activity count, actors, border zone flag.
**Actor Detail View**: Full profile with timeline, locations, threat types, co-occurring actors, movement edges, and related articles.

Click **Rebuild Graph** to regenerate from latest data.

---

## 11. Alerts

Filtered view of CRITICAL and HIGH severity items. Each alert has an **ACK** button to mark as reviewed/handled.

---

## 12. Keyword Engine

The Dynamic Keyword Engine manages intelligence-relevant keywords that drive RSS detection and filtering.

### Keyword Types
- **Primary Threat** (Red): Direct threat terms — "insurgency", "arms smuggling"
- **Entity/Actor** (Blue): Named organizations
- **Geographic** (Yellow): Region-specific combinations
- **Cross-Border** (Purple): Cross-border intelligence terms
- **AI Emerging Signal** (Green): AI-generated keywords from recent patterns
- **AI Expanded** (Grey): Synonym expansions

### AI Refresh
Click **AI Refresh Keywords** to trigger AI generation of emerging signal keywords and expansion of top keywords into synonyms.

### Manual Keyword Addition
Type a keyword in the search bar. When no results are found, an **"Add it manually?"** prompt appears with Type and Score (90=Critical, 75=High, 60=Medium, 40=Low) selectors.

---

## 13. Training & Feedback

The central hub for shaping the AI's intelligence priorities.

### Analyst Feedback (1-6 Rating Scale)

| Rating | Label | Effect |
|--------|-------|--------|
| 1 | Entirely Irrelevant | Suppresses similar content |
| 2 | Mostly Irrelevant | Reduces weight |
| 3 | Slightly Relevant | Neutral signal |
| 4 | Moderately Relevant | Mild positive signal |
| 5 | Highly Relevant | Boosts similar content |
| 6 | Extremely Relevant | Strongly prioritizes this type |

Rating uses device fingerprinting (one rating per device per item). Admin-configurable max ratings per item (default: 20).

### Train Rhino Drishti
Click to start the training pipeline: scrape pending URLs, extract text from uploaded documents, run AI analysis, extract regions/actors/keywords.

### Active Feedback Bias (Live AI Pipeline)
When status badge reads **ACTIVE**, analyst preferences are injected into every new article classification.

**How it works:**
1. Analysts rate articles 1-6 on the Intelligence Feed
2. System aggregates ratings into a bias profile (upweight/downweight patterns)
3. Bias is appended to the AI classification prompt as "Analyst Feedback Calibration"
4. New articles are scored with analyst-driven adjustments (bias recalculates every 5 minutes)

### Training Effectiveness Score
Shows how well AI classifications align with analyst feedback. Grade: EXCELLENT (80+), GOOD (65+), MODERATE (50+), NEEDS_IMPROVEMENT (35+), POOR (<35).

### Scoring Integration
```
final_score = base_ai_score + training_bias + feedback_bias
training_bias = log(total_ratings + 1) * (avg_rating - 3.5)
```

---

## 14. Manual Intelligence Uploads

Three workflows:
1. **Upload File** — PDF, Word, Excel, or TXT for AI contextual threat analysis
2. **Analyze URL** — Paste article URL for AI-powered contextual assessment
3. **Add to Feed** — Add a URL directly with user-defined severity, priority, threat category, region, and summary

### Use Cases
- Upload field reports from ground units for threat classification
- Analyze intercepted communications transcripts
- Process seized document scans for relevance to ongoing operations
- Paste breaking news URL → Add to Feed immediately with your own severity assessment

### Adding Keywords from Analysis
When you expand an analysis card, Key Entities (actors, locations, events) are shown as clickable badges. Select multiple and click **+ Add to Keyword Bank** to add them.

---

## 15. Intelligence Reports

Three report types, each on the **Reports** page:
1. **Regional Threat Summary** — Threat assessment for a specific NER state and date range
2. **Cross-Border SITREP** — Border situation report for Bangladesh or Myanmar, over a date range
3. **Custom Filtered Report** — Any combination of title, region, threat category, severity, minimum priority, keyword search, source name, date range, and a cross-border-only filter

All report filenames use **ddmmyyyy** format aligned to **IST**.

---

## 16. Platform Updates & Notifications

### How Update Notifications Work

| Scenario | What Happens |
|----------|-------------|
| 1-3 major updates | All shown as sequential toasts (oldest → newest) |
| 4+ major updates | Latest 3 toasts → "More Updates Available" modal |
| Only minor updates | One generic toast: "Performance improvements and bug fixes" |
| No new updates | No notification |

### Platform Updates Page
Access via **Platform Updates** in the sidebar. Shows a timeline of all updates with version, priority badge, message, date, and preview button.

---

## 16.1 Push Notifications (Mobile & Desktop)

Rhino Drishti supports **Web Push notifications** that appear on your device even when the browser tab is closed or the screen is locked.

### What Triggers a Push Notification

| Event | Description |
|-------|-------------|
| **CRITICAL_ITEM** | A new CRITICAL severity article arrives in the intelligence feed |
| **STATE_ESCALATION** | The concern level for a monitored NER state rises |
| **PATTERN_SURGE** | A detected threat pattern crosses the CRITICAL threshold |
| **USER_FILTER_MATCH** | A new article matches keywords you have configured |

### Enabling Push Notifications

**On Android / Desktop (Chrome, Firefox, Edge):**
1. Open the app in your browser
2. A permission prompt appears automatically on first visit
3. Click **Allow** in the browser's permission dialog
4. Notifications fire even when the tab is minimised or the browser is in the background

**On iPhone / iPad (iOS Safari — requires PWA install):**
iOS push only works from an installed PWA. The in-app prompt guides you:
1. Open the app in **Safari** (not Chrome)
2. Tap the **Share** button → select **"Add to Home Screen"** → tap **Add**
3. Open the app **from the home screen icon** (not from Safari)
4. The push permission prompt now appears — tap **Allow**

Note: The push prompt is intentionally suppressed on iOS browser tabs — it only appears after PWA installation.

### Notification Panel

Click the **Bell icon** in the top navigation bar:
- **In-app notification feed** — all recent alerts with timestamp, event type, article title
- **Push Notifications toggle** — enable or disable push delivery to this device
- **Test button** — sends an immediate test push to verify your device is working
- **iOS install guide** — appears automatically if iOS without PWA is detected

### Notification Persistence (Android)
On Android, push notifications **stay in the notification drawer until you explicitly dismiss them** — they do not auto-disappear. This ensures critical alerts are not missed when the phone is face-down or in a meeting.

### Managing Notification Preferences
Each device's subscription is managed separately. Enabling push on your phone does not affect your desktop.

---

## 17. Faultline Intelligence & PAOI Monitoring

The **Faultline Intelligence** module continuously monitors defined societal, political, and security fault lines within the Commander's **Priority Areas of Interest (PAOI)** and scores them based on recent intelligence activity.

### What is a Faultline?
A faultline is a persistent structural tension that can escalate into an active threat if not monitored. Examples:
- "Disinformation on border security and incursions" (P1)
- "Indigenous vs immigrant sentiment" (P4)
- "Drug-militant nexus in NER"
- "Bangladesh political instability spillover"

Unlike individual intelligence items (event-based), faultlines track the **underlying condition** over time. A rising score signals intensifying structural tension even without a single dramatic event.

---

## 17.1 Priority Areas of Interest (PAOI)

The Commander defines **Priority Areas of Interest** that group related faultlines for aggregate monitoring.

**Default PAOIs:**

| ID | Name | Description |
|----|------|-------------|
| P1 | Information Operations & Border Narrative | Disinformation, narrative warfare, border security messaging |
| P2 | Militant & Insurgent Activity | Active insurgent groups, ceasefire violations, arms movement |
| P3 | Lines of Communication | Road, rail, and infrastructure threats in NER |
| P4 | Ethnic & Social Cohesion | Inter-community tensions, indigenous vs immigrant dynamics |
| P5 | Cross-Border Influence Operations | Foreign-backed influence, proxy actors, subversion |

**Managing PAOIs:**
1. Click **Manage PAOIs** (top-right of Faultline Intelligence page)
2. The PAOI Manager modal shows all active Priority Areas
3. **Create**: Add new PAOI with name, description, rank, and linked faultline IDs
4. **Edit**: Update name, description, or linked faultlines
5. **Disable**: Temporarily remove from monitoring without deleting
6. **Delete**: Permanently remove a PAOI

Rank determines display order (P1 = highest priority, shown first).

---

## 17.2 Faultline Cards & Watchlist

Each faultline card shows:

| Field | Description |
|-------|-------------|
| **Name** | The faultline label |
| **PAOI Tag** | Which Priority Area it belongs to (P1, P2, etc.) |
| **Score** | Current faultline score (0-100) |
| **Severity Band** | CRITICAL (≥75) / HIGH (≥55) / MODERATE (≥35) / LOW (<35) |
| **Trend** | 7-day sparkline showing score trajectory |
| **Delta (7d)** | Score change over last 7 days (green=rising, red=falling) |
| **Article Count** | Number of intelligence items driving this score |

**Faultline Watchlist (Commander's Priorities):**
Pin up to **10 faultlines** as personal priorities, ranked 1-10.
- Click the **★ (star)** icon to add to watchlist
- Use the **rank selector** to set its priority rank (1 = top priority)
- Watchlisted faultlines appear at the **top of the page** in rank order
- If two faultlines are assigned the same rank, they swap — ranks are always unique
- Remove from watchlist by clicking the star again

**Creating a New Faultline:**
1. Click **+ New Faultline** (top-right)
2. Fill in: Name, Region, Category, PAOI, and optional Notes
3. Click **Create** — the faultline begins scoring on the next daily pass

**Faultline Detail View:**
Click any faultline card to see: 30-day score history chart, contributing articles (newest first), analyst notes (editable), and acknowledgement log.

---

## 17.3 Faultline Scoring & Time Decay

Scores are calculated by the **Daily Faultline Engine** running twice daily at **06:00 IST** and **18:00 IST**.

**Scoring formula:**
```
faultline_score = SUM(article_weight x e^(-0.35 x age_days))
```

- Each article's weight is derived from its AI priority score and severity
- The exponential decay factor `e^(-0.35 x age_days)` reduces older articles' contribution:
  - Today: 100% weight
  - 7 days ago: ~9% weight
  - 14+ days ago: negligible
- Scores reflect **current conditions**, not historical spikes

**Why time decay matters:** Without decay, a single event from 2 months ago would permanently inflate a faultline score. Decay ensures scores normalize after events subside.

**Manual re-score:** Click **Run Daily Pass** on the Faultline Intelligence page.

**Score interpretation:**
| Score | Band | Meaning |
|-------|------|---------|
| 75-100 | CRITICAL | Active escalation — immediate attention required |
| 55-74 | HIGH | Significant tension — elevated monitoring |
| 35-54 | MODERATE | Background activity — routine watch |
| 0-34 | LOW | Quiet — minimal recent activity |

---

## 17.4 Monthly Faultline Analysis Report

The primary instrument for presenting faultline status to the Commander.

**How to generate:**
1. Navigate to **Faultline Intelligence** in the sidebar
2. Click **Monthly Report** (or download the **Faultline Report PDF** from the Monthly Strategic Brief's Faultline Analysis section)

**Report structure:**
1. **Commander's Priority Dashboard** — All PAOI-linked faultlines with scores, month-on-month delta, and severity colour coding
2. **Top Movers** — Faultlines with the largest score changes (fastest rising = highest concern)
3. **Per-Faultline Deep Dives** — Score trend chart, contributing articles, AI-generated narrative
4. **Strategic Assessment** — AI synthesis of cross-faultline patterns and priority recommendations

**In Daily Brief:** Active HIGH/CRITICAL faultlines appear automatically in the daily brief's faultline section. PAOI-linked faultlines are tagged with a **red PAOI badge** to draw the Commander's attention.

---

## 18. Social Media Intelligence & Sentiment Pulse

Instagram, Facebook and Twitter/X posts are scraped via Apify (a managed web-scraping service) and processed through the same AI classification pipeline as news articles. YouTube video comments are read via YouTube's own free comments API.

### Comment Sentiment
For posts that have real comments, a second scrape pulls actual comment text (not just like/reaction counts) and a single AI call estimates what percentage of commenters are positive/supportive versus negative/critical about the situation described. This shows up as a green ▲ / red ▼ percentage tag:
- On the relevant **Intelligence Feed** card, next to the source name
- On the **Dashboard** scanner card for that platform, flanking the Fetch button
- Aggregated across all platforms in the **combined Social Media Pulse Indicator** in the Dashboard's Intelligence Source Monitors header
- As a **Social Media Pulse** section in every Daily, Fortnightly and Monthly brief, scoped to that brief's own time period

Sentiment is a best-effort enrichment — posts with no comments, or where the scrape/AI call fails, simply show no tag rather than a wrong one.

### Volume Modes
Admins control how much is scraped per cycle from the **API & Pipeline Monitor** page — see [Section 21](#21-api--pipeline-monitor).

---

## 19. Flagging Intelligence to Commanders

Any intelligence item in the feed can be **flagged** — sent directly to a commander for immediate attention.

### Flagging an Article

1. Find the article in the **Intelligence Feed**, **Dashboard Latest Items**, or **Alerts** page
2. Click the **Flag icon** in the top-right corner of the item card
3. A modal opens with:
   - **Recipient** — select the commander (dropdown of all registered users)
   - **Message** — optional context
   - **Priority** — URGENT / HIGH / ROUTINE
4. Click **Send Flag** to submit
5. The recipient receives an in-app notification and (if enabled) a push notification

### Red Flag Indicator

Once you flag an article, the **flag icon turns red and filled** on the card. This persists across sessions — the red icon tells you it has already been escalated, preventing duplicate flagging.

### Viewing Flags Received

Recipients view flagged articles in their **Notification Panel** (bell icon). Each flagged item shows article title, sender, timestamp, priority level, and message.

---

## 20. User Management

*Admin only.*

### User List
All registered users with username, name, role (Admin/Analyst/Viewer), status (Active/Inactive), last login, and actions.

### Creating a New User
1. Click **Create User** (top-right)
2. Fill in: Username, Email (optional), Full Name, Role, Password
3. Use **Generate** for a strong 14-character random password; **Copy** to save it
4. Click **Create User** to save

**WARNING:** Passwords are shown only once during creation.

### Resetting a Password
Click the **Key** icon next to any user → enter new password → **Copy** → **Reset**

### Deactivating / Deleting
- **Active/Inactive** toggle — preserves the account but blocks login
- **Trash** icon — permanently deletes the user (cannot delete your own account)

---

## 21. API & Pipeline Monitor

*Admin only.* Access via **API & Pipeline Monitor** in the sidebar.

### API Spend
Live multi-provider cost tracker: today's total spend against a daily limit (editable), a per-provider breakdown with its own sub-alert threshold, an hourly stacked spend chart, and 7-day daily cost history. Includes a live **OpenRouter Balance** row showing your actual remaining account credit, colour-coded (green/amber/red) with a top-up link once low.

### Credit Warning Banner
Appears automatically when OpenRouter credits run low or critical, with a direct top-up link.

### Social Media Scraping
Shows post counts captured per platform (Instagram, Facebook, Twitter/X). A **Throttled / Firehose** toggle controls scrape volume:
- **Throttled** (default) — roughly 50 posts/platform every ~3.5 days, near-zero cost
- **Firehose** — roughly 100 posts/platform/day, higher cost

**Fetch Now** triggers an immediate scrape cycle outside the schedule.

### Filter Cascade
Visualizes how many items survive each of the 4 pipeline filter stages (from raw ingestion down to what reaches the feed), with pass/reject counts per stage and overall pipeline health.

### Filter Threshold Simulator
Lets you experiment with different filter thresholds and see the projected effect on rejection rates before changing anything live.

### Storage Cleanup
Shows database collection counts. **Strip Raw Content** removes the full article body text for items older than a chosen age (keeps the link and AI analysis intact); **Delete Articles** permanently removes items older than a chosen threshold. The pipeline auto-strips article bodies older than 45 days daily regardless.

---

## 22. Settings

*Admin only.*

### 22.1 Local Database Storage Card

| Mode | Indicator | Meaning |
|------|-----------|---------|
| **MongoDB Atlas** | Cloud icon (blue) | Data stored on Atlas cloud |
| **Local — Tailscale** | Shield icon (green) | Data stored on local hard disk via Tailscale VPN |
| **Local — Direct** | Server icon (amber) | Data stored on local machine on same network |

### 22.2 Source Effectiveness Card

Shows which non-RSS sources are producing actionable intelligence:
Item count, Severity bar, AI processing rate, Latest catch, High-value score (Critical + High count).

### News Retention Window
Options: 7 / 14 / 30 / 60 / 90 / 180 / 365 days. Affects all pages immediately.

### Feedback Bias Configuration

**Feedback Window:**
- **Rolling 30 Days** (default) — most adaptive
- **All Time** — cumulative learning

**Influence Level:**
| Level | Score Adjustment | Best For |
|-------|-----------------|----------|
| **Light** | +/-3 to 5 pts | Minimal correction |
| **Moderate** | +/-5 to 10 pts | Balanced |
| **High** | +/-10 to 20 pts | Heavy analyst override |

### Bias Impact Report
Full-width analytics table showing exactly how analyst feedback changes article scores — Original vs. Biased vs. Delta per item with reasons.

---

## 23. Local Database Setup Wizard

Rhino Drishti can store collected intelligence on a **local 1 TB hard disk** at your intelligence collection centre.

### Architecture
```
CLOUD (unchanged): Frontend: Vercel | Backend: Render
         | (MongoDB driver via WireGuard tunnel)
ON-PREMISES (Windows 11 PC):
  MongoDB 7.0 Community + Tailscale Agent + 1 TB storage
```

### Setup Steps (Automated via PowerShell Wizard)
The wizard at `local-setup/setup-wizard.ps1`:
1. Installs MongoDB 7.0 Community (via winget)
2. Configures authentication
3. Creates database users
4. Installs and authenticates Tailscale
5. Sets Windows Firewall rules
6. Optionally migrates all data from Atlas to local

After setup, update `MONGO_URL` on Render and redeploy. Settings page switches from "Atlas" to "Local — Tailscale".

---

## 24. How the AI Pipeline Works

### Data Flow
```
INTELLIGENCE SOURCES (RSS, YouTube, Telegram, Facebook, Instagram, Twitter/X — parallel)
→ Manual Uploads (PDF, DOCX, URL)
→ Deduplication
→ Hard Filter (reject sports/entertainment)
→ Dynamic Keyword Matching
→ Language Detection & Translation
  (Bengali, Assamese, Hindi, Burmese, Thai, Chinese, Arabic, Japanese, Korean → English)
→ Level 1 Sifter (border instability pre-filter)
→ Level 2 Deep Analyst (multi-step AI classification + feedback bias injection)
→ Vector Embedding (for semantic search)
→ Adaptive Keyword Feedback (boost/decay keyword scores)
→ Analyst Feedback Integration
→ Comment Sentiment Scoring (social media items with comments)
→ WebSocket Broadcast + Push Notification Dispatch
→ Pattern Detection (sliding-window cluster analysis)
→ Faultline Scoring (time-decay weighted aggregation)
```

### AI Classification (Military Intelligence Prompt)
1. Relevance Filter: Strict rejection of sports, entertainment, lifestyle
2. Priority Scoring (0-100) with boost rules (cross-border +10, China/Pakistan +15)
3. Multi-label Classification: 19 threat categories
4. Contextual Extraction: Regions, cross-border flag, countries, actors
5. Named Entity Extraction: Persons, organizations, locations
6. Intelligence Output: Summary, why it matters, early warning signal
7. Special Detection: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE
8. India-Relevance Scoring: Cross-border items scored 0-20
9. Signal Classification: Cross-border signal bucket and strength
10. Language Rule: All output in English regardless of input language

### RSS Source Breakdown
| Category | Examples |
|----------|---------|
| Regional (NER) | NE Now, Assam Tribune, EastMojo |
| National | NDTV, Hindu, India Today, HT, The Wire |
| Bangladesh | Prothom Alo, Daily Star, Dhaka Tribune |
| Myanmar | Myanmar Now, Irrawaddy, Mizzima, DVB |
| International | BBC, Al Jazeera, Reuters |
| Government | PIB (all NER states + Delhi), MEA, NIA, MHA, DoNER, NDMA |

### Scheduler (Automated Tasks)
| Task | Frequency | Purpose |
|------|-----------|---------|
| Grassroots Source Fetch | Every 60 min | Small/hard-to-reach NER news sources |
| Standard Source Fetch | Every 30 min | Main RSS feeds |
| Established Source Fetch | Every 12 hours | Stable large sources (PIB, MHA) |
| AI Retry | Every 15 min | Reprocess failed items |
| Daily Brief | 0600 IST daily | Auto-generate daily brief |
| Embedding Backfill | Every 6 hours | Vector embeddings for semantic search |
| Article Fusion | Every 30 min | Detect and cluster duplicate articles |
| YouTube Fetch | Every 4 hours | Channels + keyword searches, with comment sentiment on new videos |
| Telegram Fetch | Every hour | Monitored channels |
| Social Media (Apify) Fetch | Every 6 hours, gated by Throttled/Firehose mode | Instagram, Facebook, Twitter/X posts + comment sentiment |
| **Faultline Daily Pass** | **06:00 + 18:00 IST** | **Re-score all faultlines with time-decay formula** |
| Credit Monitor | Every 30 min | Checks OpenRouter account balance, warns when low |

---

## 25. Glossary

| Term | Definition |
|------|-----------|
| **ACK** | Acknowledge — mark an alert as reviewed |
| **Activity Log** | Session-level record of training runs and feedback sessions |
| **Apify** | Managed web-scraping service used to collect Instagram, Facebook and Twitter/X posts without logins or proxy management |
| **Auto-Translation** | Automatic translation of non-English content to English before display |
| **Bias Impact Report** | Analytics table showing how analyst feedback changes article priority scores |
| **Comment Sentiment** | AI-estimated positive/negative percentage from real comments on a social media post, shown as a ▲/▼ tag |
| **C-Score** | Confidence Score (0-100%) — AI's certainty in its own classification |
| **Cluster / Fusion** | Group of similar articles from multiple sources merged into one intelligence item |
| **Cross-border** | Activity involving more than one country |
| **Cross-Border SITREP** | Situation Report for Bangladesh or Myanmar border intelligence |
| **Custom Brief Generator** | Admin-only chat tool for building an on-demand, precisely-scoped PAOI brief |
| **Device Fingerprint** | Unique identifier per browser/device to prevent duplicate ratings |
| **DIPR** | Department of Information and Public Relations — state government press release office |
| **Escalation Risk** | Likelihood that a pattern of events will intensify |
| **Faultline** | A persistent structural tension (ethnic, political, security) monitored over time, scored with time-decay weighted article aggregation |
| **Faultline Daily Pass** | Scheduled re-scoring of all faultlines at 06:00 IST and 18:00 IST |
| **Faultline Decay** | Exponential decay formula `e^(-0.35 x age_days)` applied to each article's contribution to a faultline score |
| **Feedback Bias** | Dynamic analyst-driven adjustment injected into the AI classification prompt |
| **Feedback Session** | Aggregated log entry created after an analyst submits 5+ ratings |
| **Filter Cascade** | The 4-stage pipeline that filters raw ingested items down to what reaches the feed |
| **Firehose Mode** | Higher-volume social media scraping setting (~100 posts/platform/day) |
| **Flag** | Escalation action — sends a specific intelligence article to a commander with priority level and message |
| **Flag Icon (Red)** | Red, filled flag icon on an item card indicating the article has already been flagged to a commander |
| **Guided Tour** | Step-by-step page walkthrough. Re-trigger via the ? button; admin can reset all tours |
| **Hard Filter** | Rule-based rejection of irrelevant content (sports, entertainment) |
| **Impact Summary** | AI-generated description of what the system learned from a training or feedback session |
| **Influence Level** | Controls feedback override strength — Light (~10-15%), Moderate (~20-25%), High (~35-40%) |
| **JWT** | JSON Web Token — authentication token used for session management |
| **Knowledge Graph** | Network of relationships between actors and locations |
| **Local Database** | On-premises MongoDB 7.0 installation connected to Render backend via Tailscale VPN |
| **Monthly Faultline Analysis Report** | Multi-page PDF summarising faultline scores, month-on-month changes, top movers, and AI strategic narrative |
| **NER** | North Eastern Region of India (Assam, Manipur, Meghalaya, Mizoram, Tripura, Nagaland, Arunachal Pradesh, Sikkim) |
| **NotebookLM Export** | A NotebookLM-formatted text version of a brief, copied to your clipboard for use in Google NotebookLM |
| **P-Score** | Priority Score (0-100) — AI-computed urgency combining severity, source credibility and strategic relevance |
| **PAOI** | Priority Area of Interest — a strategic topic defined by the Commander grouping related faultlines |
| **PAOI Manager** | Modal interface for creating, editing, and reordering Priority Areas of Interest |
| **Pattern** | Cluster of 3+ intelligence items sharing region, threat type, or actor |
| **PIB** | Press Information Bureau — Government of India's official communication agency |
| **Priority Score** | AI-assigned importance score from 0-100, adjusted by feedback bias |
| **Push Notification** | Web push alert delivered to a device's notification tray even when the app is closed |
| **PWA** | Progressive Web App — Rhino Drishti installed to a mobile home screen, enabling push notifications on iOS |
| **RBAC** | Role-Based Access Control — restricts features based on user role |
| **Relevance Tag** | Optional 1-6 score an analyst assigns to a URL when adding it to the training queue |
| **Semantic Search** | AI-powered search using vector embeddings that finds related concepts |
| **Severity** | Classification level: Critical > High > Medium > Low |
| **Sifter** | Level 1 pre-filter that screens articles for border/militant relevance |
| **Situation Map** | Per-PAOI map in Fortnightly/Monthly briefs showing state/border outlines colour-coded by severity plus clustered event markers |
| **Social Media Pulse** | Aggregated positive/negative sentiment indicator for a social platform, shown on Dashboard cards, feed cards, and in briefs |
| **Source Effectiveness** | Settings card showing intelligence yield per non-RSS source |
| **Special Flags** | AI-detected indicators: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, INFRASTRUCTURE_DUAL_USE |
| **Tailscale** | WireGuard-based VPN mesh network for secure local database connection |
| **Telethon** | Python Telegram client library for reading messages from Telegram channels |
| **Threat Trajectory** | Direction of a threat: ESCALATING, STABLE, DE-ESCALATING, NEW_THREAT |
| **Throttled Mode** | Lower-volume social media scraping setting (~50 posts/platform every ~3.5 days), near-zero cost |
| **Toast Notification** | Brief popup message at the top-center of the screen |
| **Training Pipeline** | Process of scraping, analyzing, and learning from analyst-submitted URLs and documents |
| **Trends Intelligence Center** | Analytics page for stability index, severity trends, cross-border correlation, and per-state drill-down |
| **VAPID** | Voluntary Application Server Identification — standard used for secure web push delivery |
| **Vector Embedding** | Mathematical representation of text meaning, enabling semantic similarity search |
| **Watchlist** | Commander's personal priority list of up to 10 faultlines, ranked 1-10, pinned to the top of the Faultline Intelligence page |

---

*Rhino Drishti v14.4 — Elite OSINT Intelligence Platform — Apify Social Scraping, Comment Sentiment, Social Media Pulse, Strategic Briefs Suite, Faultline & PAOI Monitoring*
*Handbook updated: 13 July 2026*
