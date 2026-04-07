# Rhino Drishti — User Handbook

## Complete Guide for Intelligence Analysts

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dashboard](#2-dashboard)
3. [Intelligence Feed](#3-intelligence-feed)
4. [Cross-Border Intelligence](#4-cross-border-intelligence)
5. [Daily Brief](#5-daily-brief)
6. [Weekly Trends](#6-weekly-trends)
7. [Pattern Detection](#7-pattern-detection)
8. [Knowledge Graph](#8-knowledge-graph)
9. [Alerts](#9-alerts)
10. [Keyword Engine](#10-keyword-engine)
11. [Document Upload](#11-document-upload)
12. [Settings](#12-settings)
13. [How the AI Pipeline Works](#13-how-the-ai-pipeline-works)
14. [Glossary](#14-glossary)

---

## 1. Getting Started

### What is Rhino Drishti?
Rhino Drishti is an AI-powered military intelligence aggregation and analysis platform designed for monitoring India's North Eastern Region (NER), Bangladesh, and Myanmar. It automatically collects news from 36+ RSS sources, runs AI classification using a military intelligence framework, detects patterns, and generates daily intelligence briefs.

### First-time Access
- Open the application URL in your browser (Chrome, Firefox, or Edge recommended)
- No login is required — the system is designed for deployment within secured networks
- The Dashboard loads automatically as your home screen
- The left sidebar provides navigation to all features

### Navigation
The sidebar contains all pages:
- **Dashboard** — Overview of intelligence landscape
- **Intelligence Feed** — Full searchable list of classified items
- **Cross-Border** — Items specifically involving cross-border activity
- **Daily Brief** — Automated daily intelligence summary
- **Weekly Trends** — 7-day severity and threat type charts
- **Patterns** — Detected threat patterns across regions
- **Knowledge Graph** — Actor-location relationship mapping
- **Alerts** — Critical and high-severity items requiring attention
- **Keyword Engine** — AI-powered keyword management for detection
- **Upload Documents** — Upload offline intelligence materials (PDF, Word, Excel)
- **Settings** — Configure retention window

---

## 2. Dashboard

The Dashboard is your command center showing the current intelligence landscape at a glance.

### Stat Cards (Top Row)
- **Total Items**: Total intelligence items within the retention window
- **Critical**: Items classified as CRITICAL severity (immediate threat to personnel/operations)
- **High**: Items classified as HIGH severity (significant security concern)
- **Medium**: Items classified as MEDIUM severity (monitoring required)
- **Low**: Items of LOW security significance
- Click any stat card to filter the Intelligence Feed by that severity level

### RSS Scanner Panel
Shows real-time progress when a fetch cycle is running:
- Source being scanned
- Progress bar (X of 36 sources)
- Articles found, filtered, and translated

### NER Threat Map
Visual map of India's Northeast showing threat concentration by state. Hover over states to see item counts and severity breakdown.

### Unacknowledged Critical Alerts
Sticky panel showing CRITICAL and HIGH items that haven't been acknowledged yet. Click **ACK** to mark an alert as handled. This prevents alert fatigue by tracking which items have been reviewed.

### Live Feed Panel
Real-time updates via WebSocket — new items appear here as they are processed by the AI pipeline without needing to refresh the page. Shows the LIVE/OFFLINE indicator in the top-right.

### Pattern Insights
Summary of the most significant detected threat patterns, showing escalation risk levels (CRITICAL, HIGH, MODERATE, LOW).

### Trend Charts
7-day severity distribution showing whether threat levels are increasing or decreasing.

---

## 3. Intelligence Feed

The full searchable, filterable list of all classified intelligence items.

### Search
- **Keyword Search** (default): Type any keyword to find matching items in titles and content
- **Semantic Search** (toggle): Switch to AI-powered search that finds contextually related items even if the exact words don't match. Example: searching "border infiltration" also finds articles about "cross-border movement" or "unauthorized entry"

### Filters
- **Severity**: Filter by Critical, High, Medium, or Low
- **State/Region**: Filter by specific NER states (Assam, Manipur, Nagaland, etc.)
- **Threat Category**: Filter by threat type (Insurgency, Drug Trafficking, etc.)
- **Date Range**: Filter by publication date

### Item Cards
Each intelligence item shows:
- **Title** with severity badge (color-coded: red=Critical, orange=High, yellow=Medium, green=Low)
- **Priority Score** (0-100): AI-assigned importance score. Higher = more urgent
- **Confidence Score** (0-100): How confident the AI is in its classification
- **Threat Trajectory**: ESCALATING / STABLE / DE-ESCALATING / NEW_THREAT
- **AI Summary**: Concise intelligence summary
- **Why It Matters**: Strategic significance explanation
- **Early Warning Signal**: Potential future implications
- **Special Flags**: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, etc.
- **Tags**: Classification labels (Military Movement, Border Security, etc.)
- **Actors**: Named organizations/groups involved
- **Source**: Original news source with link

### Sorting
- By publication date (newest first)
- By priority score (highest first)

---

## 4. Cross-Border Intelligence

A filtered view of the Intelligence Feed showing ONLY items flagged as cross-border activity. These are items involving:
- India-Bangladesh border incidents
- India-Myanmar border activity
- China-India border tensions (Arunachal)
- Pakistan-linked activity in NER
- Rohingya movement tracking
- Myanmar junta spillover effects

This view uses the same filters and search capabilities as the main Intelligence Feed.

---

## 5. Daily Brief

Automated daily intelligence summary generated at 0600 IST each day.

### Analyst Assessment
AI-generated strategic overview summarizing the day's most significant developments, identifying trends, and highlighting items requiring immediate attention.

### Sections
- **NER Key Developments**: Top intelligence items from the Northeast, each with full analysis (Why It Matters, Early Warning, Source, Actors)
- **National News**: Relevant national-level developments affecting NER security
- **International News**: Cross-border and strategic international items
- **Pattern Insights**: Detected escalation patterns from the Pattern Detection Engine
- **Document Insights**: Analysis from any uploaded documents

### Actions
- **REGENERATE BRIEF**: Force regenerate today's brief with the latest data. The brief runs automatically at 0600 IST, but you can manually trigger it anytime
- **EXPORT PDF**: Download the brief as a PDF document with RESTRICTED classification headers. Suitable for distribution within authorized channels

### Cross-Brief Deduplication
News items included in one day's brief are NOT repeated in subsequent briefs. Each brief contains only new intelligence.

---

## 6. Weekly Trends

Visual analytics showing intelligence trends over the past 7 days.

### Charts
- **Severity Distribution**: Bar chart showing Critical/High/Medium/Low counts per day
- **Threat Type Breakdown**: Which threat categories are most active
- **Regional Distribution**: Which NER states have the most activity
- **Cross-Border Activity**: Trend line for cross-border flagged items

Use this page to identify whether the overall threat environment is escalating, stable, or de-escalating over the week.

---

## 7. Pattern Detection

The Pattern Detection Engine automatically groups intelligence items to identify recurring threats and escalation corridors.

### How Patterns Are Detected
The system looks for clusters of items sharing:
- Same region + threat type (e.g., "Manipur Insurgency")
- Same region + actor (e.g., "Assam ULFA")
- Same region + tag combination
- Cross-border activity keys

When 3+ items share a pattern key within a 7-day window, a pattern is flagged.

### Escalation Risk Levels
- **CRITICAL**: 2+ critical-severity events in the pattern
- **HIGH**: 5+ events in the pattern cluster
- **MODERATE**: 4+ events
- **LOW**: 3+ events

### Pattern Cards
Each pattern shows:
- Region and threat detail
- Event count and time window
- Average priority score
- Severity breakdown
- Source diversity
- Sample article titles

---

## 8. Knowledge Graph

Entity relationship mapping that cross-references actors, locations, and contexts across the entire intelligence corpus. This surfaces connections that no single article reveals.

### Actors Tab
Lists all identified actors (organizations, security forces, militant groups) with:
- Activity count (total events)
- Article count (how many articles mention them)
- Locations where they've been active
- Threat types associated with them
- Cross-border flag

### Locations Tab
Lists all identified locations with:
- Activity count
- Actors seen at that location
- Border zone flag
- Associated states

### Actor Detail View
Click any actor card to see their full profile:
- **Timeline**: First seen and last seen dates
- **Locations**: All locations with event counts
- **Threat Types**: What types of activity they're involved in
- **Co-occurring Actors**: Other actors that appear in the same articles
- **Movement Edges**: Actor-to-location connections with frequency
- **Related Articles**: Sample article titles

### Filters
- **Cross-border only**: Show only actors with cross-border activity
- **Border zones only**: Show only locations near borders
- **Search**: Find specific actors or locations

### Rebuilding
Click **Rebuild Graph** to regenerate the knowledge graph from the latest data.

---

## 9. Alerts

Filtered view of CRITICAL and HIGH severity items. This is effectively the Intelligence Feed filtered to only show items requiring immediate attention.

### Acknowledgement
Each alert has an **ACK** button. Clicking it marks the alert as reviewed/handled. Acknowledged alerts move out of the "Unacknowledged" panel on the Dashboard but remain accessible in the full feed.

---

## 10. Keyword Engine

The Dynamic Keyword Engine generates and manages intelligence-relevant keywords that drive RSS detection and filtering.

### Keyword Types
- **Primary Threat** (Red): Direct threat terms like "insurgency", "arms smuggling", "drone activity"
- **Entity/Actor** (Blue): Named organizations and actor-action combinations like "ULFA movement Assam"
- **Geographic** (Yellow): Region-specific combinations like "Manipur violence", "Tripura border tension"
- **Cross-Border** (Purple): Cross-border intelligence terms like "India Bangladesh border issue"
- **AI Emerging Signal** (Green): AI-generated keywords from recent patterns like "drug-militant nexus expansion"
- **AI Expanded** (Grey): Synonym expansions of high-score keywords like "unauthorized border crossing" for "border infiltration"

### Keyword Scores (0-100)
Each keyword has a relevance score based on:
- Frequency in recent intelligence items
- Association with high/critical severity articles
- Cross-border relevance
- Recency (time decay — recent matches score higher)

### Adaptive Learning
Keywords automatically adjust based on AI classification results:
- When an article is classified as HIGH or CRITICAL, keywords that matched it get **boosted**
- When an article is classified as LOW relevance, matching keywords get **decayed**
- New keywords are automatically extracted from high-priority articles

### AI Refresh
Click **AI Refresh Keywords** to trigger Claude AI to:
1. Analyze recent high-priority intelligence
2. Generate emerging signal keywords (new threat patterns)
3. Expand top keywords into synonyms and related phrases

### How Keywords Drive Detection
During each RSS fetch cycle, the system uses these keywords for weighted matching against article titles and content. High-scoring keywords give articles higher priority, ensuring important intelligence is not missed.

---

## 11. Document Upload

Upload offline intelligence materials for AI analysis.

### Supported Formats
- **PDF** (.pdf): Intelligence reports, classified documents
- **Word** (.docx): Written assessments, memos
- **Excel** (.xlsx): Structured data, logs, manifests

### How It Works
1. Click **Upload Documents** in the sidebar
2. Drag and drop or select your file
3. The system extracts text content from the document
4. AI processes the extracted text using the same military intelligence framework
5. Insights from uploaded documents appear in the Daily Brief under "Document Insights"

### Use Cases
- Upload field reports from ground units
- Process intercepted communications transcripts
- Analyze seized document scans (if text-extractable PDF)
- Import structured data from border checkpoint logs

---

## 12. Settings

### News Retention Window
Controls how far back the system looks when displaying intelligence items.

Options: 7 / 14 / 30 / 60 / 90 / 180 / 365 days

- **Shorter window** (7-14 days): See only recent intelligence, faster page loads
- **Longer window** (90-365 days): See historical trends, more items to search through

Changing the retention window immediately affects:
- Dashboard statistics
- Intelligence Feed item count
- Alert counts
- Pattern detection window

---

## 13. How the AI Pipeline Works

### Data Flow
```
RSS Sources (36) + Elite Web Scraping
        |
        v
    Deduplication (URL + title similarity)
        |
        v
    Hard Filter (reject sports, entertainment, lifestyle)
        |
        v
    Dynamic Keyword Matching (weighted relevance scoring)
        |
        v
    Language Detection & Translation (Bengali/Assamese/Hindi → English)
        |
        v
    Level 1 Sifter (pre-filter for border instability, militant activity)
        |
        v
    Level 2 Deep Analyst (8-step Claude AI classification)
        |
        v
    Vector Embedding (OpenAI text-embedding-3-small)
        |
        v
    Adaptive Keyword Feedback (boost/decay keyword scores)
        |
        v
    WebSocket Broadcast (real-time push to connected clients)
        |
        v
    Pattern Detection (sliding-window cluster analysis)
```

### AI Classification (8-Step Military Intelligence Prompt)
The AI operates as a Senior Military Intelligence Analyst and performs:

1. **Relevance Filter**: Strict rejection of sports, entertainment, lifestyle content
2. **Priority Scoring** (0-100): With boost rules (cross-border +10, China/Pakistan +15)
3. **Multi-label Classification**: 19 threat categories (Military Movement, Insurgency, Drug Trafficking, etc.)
4. **Contextual Extraction**: Regions, cross-border flag, countries, actors
5. **Named Entity Extraction**: Persons, organizations, locations
6. **Intelligence Output**: Summary, why it matters, early warning signal, attention level
7. **Special Detection**: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, etc.
8. **Language Rule**: All output in English regardless of input language

### Scheduler (Automated Tasks)
| Task | Frequency | Purpose |
|------|-----------|---------|
| Grassroots Source Fetch | Every 60 min | Small/hard-to-reach NER news sources |
| Standard Source Fetch | Every 30 min | Main RSS feeds (PIB, NDTV, The Hindu, etc.) |
| Established Source Fetch | Every 12 hours | Stable large sources |
| AI Retry | Every 15 min | Reprocess any items that failed AI classification |
| Daily Brief | 0600 IST daily | Auto-generate the daily intelligence brief |
| Embedding Backfill | Every 6 hours | Generate vector embeddings for semantic search |

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| **ACK** | Acknowledge — mark an alert as reviewed |
| **Cross-border** | Activity involving more than one country |
| **Escalation Risk** | Likelihood that a pattern of events will intensify |
| **Hard Filter** | Rule-based rejection of irrelevant content (sports, entertainment) |
| **Knowledge Graph** | Network of relationships between actors and locations |
| **NER** | North Eastern Region of India (Assam, Manipur, Meghalaya, Mizoram, Tripura, Nagaland, Arunachal Pradesh, Sikkim) |
| **Pattern** | Cluster of 3+ intelligence items sharing the same region, threat type, or actor |
| **Priority Score** | AI-assigned importance score from 0-100 |
| **Semantic Search** | AI-powered search using vector embeddings that finds related concepts |
| **Severity** | Classification level: Critical > High > Medium > Low |
| **Sifter** | Level 1 pre-filter that screens articles for border/militant relevance |
| **Special Flags** | AI-detected indicators: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, INFRASTRUCTURE_DUAL_USE |
| **Threat Trajectory** | Direction of a threat: ESCALATING, STABLE, DE-ESCALATING, NEW_THREAT |
| **Vector Embedding** | Mathematical representation of text meaning, enabling semantic similarity search |

---

*Rhino Drishti v3.0 — Elite OSINT Intelligence Platform*
*Handbook generated: April 2026*
