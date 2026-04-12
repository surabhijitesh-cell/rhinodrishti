# Rhino Drishti — User Handbook

## Complete Guide for Intelligence Analysts

---

## Table of Contents

1. [Authentication & Access Control](#1-authentication--access-control)
2. [Getting Started](#2-getting-started)
3. [Dashboard](#3-dashboard)
4. [Intelligence Feed](#4-intelligence-feed)
5. [Cross-Border Intelligence](#5-cross-border-intelligence)
6. [Daily Brief](#6-daily-brief)
7. [Weekly Trends](#7-weekly-trends)
8. [Pattern Detection](#8-pattern-detection)
9. [Knowledge Graph](#9-knowledge-graph)
10. [Alerts](#10-alerts)
11. [Keyword Engine](#11-keyword-engine)
12. [Training & Feedback](#12-training--feedback)
13. [Document Upload](#13-document-upload)
14. [User Management](#14-user-management)
15. [Settings](#15-settings)
16. [How the AI Pipeline Works](#16-how-the-ai-pipeline-works)
17. [Glossary](#17-glossary)

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

The platform uses Role-Based Access Control (RBAC) with three roles:

| Feature | Admin | Analyst | Viewer |
|---------|-------|---------|--------|
| View Dashboard, Feeds, Briefs | Yes | Yes | Yes |
| Download/Export PDFs | Yes | Yes | Yes |
| Submit Feedback Ratings | Yes | Yes | No |
| Generate Briefs, Train AI | Yes | Yes | No |
| Upload Documents/URLs | Yes | Yes | No |
| Run Keyword Refresh | Yes | Yes | No |
| User Management | Yes | No | No |
| Settings | Yes | No | No |

**Admin** — Full access to all features including user creation, password resets, and system settings.

**Analyst** — Can access all intelligence features (feeds, briefs, training, uploads, feedback). Cannot access User Management or Settings. Redirects to Intelligence Feed after login.

**Viewer** — Read-only access. Can view all intelligence data, dashboards, and download PDFs. All action buttons (generate, train, upload, rate) are disabled. Redirects to Dashboard after login.

### Session Management
- Sessions last **24 hours** (JWT token expiry)
- Token persists across page refreshes (stored in browser)
- If your session expires, you'll be automatically redirected to the Login page
- Click the **Logout** button (top-right, next to your name) to end your session

### Sidebar Navigation
The sidebar menu adapts to your role:
- **Admin**: All menu items visible (including User Management and Settings)
- **Analyst**: User Management and Settings are hidden
- **Viewer**: User Management and Settings are hidden

---

## 2. Getting Started

### What is Rhino Drishti?
Rhino Drishti is an AI-powered military intelligence aggregation and analysis platform designed for monitoring India's North Eastern Region (NER), Bangladesh, and Myanmar. It automatically collects news from 36+ RSS sources, runs AI classification using a military intelligence framework, detects patterns, and generates daily intelligence briefs.

### First-time Access
- Open the application URL in your browser (Chrome, Firefox, or Edge recommended)
- You will be presented with the **Login** screen — enter your credentials (see Section 1)
- After login, the Dashboard loads as your home screen (Admin/Viewer) or Intelligence Feed (Analyst)
- The left sidebar provides navigation to all features

### Navigation
The sidebar contains all pages (visibility depends on your role):
- **Dashboard** — Overview of intelligence landscape
- **Intelligence Feed** — Full searchable list of classified items with analyst rating
- **Cross-Border** — Items specifically involving cross-border activity
- **Daily Brief** — Automated daily intelligence summary
- **Weekly Trends** — 7-day severity and threat type charts
- **Patterns** — Detected threat patterns across regions
- **Knowledge Graph** — Actor-location relationship mapping
- **Alerts** — Critical and high-severity items requiring attention
- **Keyword Engine** — AI-powered keyword management for detection
- **Training & Feedback** — Rate articles, upload training data, monitor AI learning
- **Upload Documents** — Upload offline intelligence materials (PDF, Word, Excel)
- **User Management** — Create/manage users and reset passwords (Admin only)
- **Settings** — Configure retention window and feedback limits (Admin only)
- **User Handbook** — This guide

---

## 3. Dashboard

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

## 4. Intelligence Feed

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
- **Relevance Rating** (top of card): 1-6 scale for analyst feedback (see Section 11)
- **Title** with severity badge (color-coded: red=Critical, orange=High, yellow=Medium)
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
- **Fused Sources Badge** (if applicable): Shows "X sources" when multiple outlets cover the same story. Click to expand and see all covering sources with links.

### Feed Quality Filter
The Intelligence Feed automatically excludes:
- **LOW severity** items — noise and low-value articles are hidden
- **Unprocessed** items — articles still awaiting AI classification are kept in the background
- **Duplicate articles** — when multiple sources cover the same story, only the best summary is shown (see Multi-Article Fusion below)

Only fully processed, medium-to-critical severity, deduplicated intelligence items appear in the feed.

### Multi-Article Fusion
When multiple news sources cover the same event, the system automatically detects and clusters them:
- A blue **"X sources"** badge appears on the card showing how many outlets covered the story
- Click the badge to expand a panel listing every source with the original article title and clickable link
- The system picks the **longest/best summary** as the primary display and cites all others
- Fusion runs both **in real-time** (as articles arrive) and as a **scheduled batch** every 30 minutes
- Detection uses title word overlap, entity matching (shared locations, actors, events), and vector embedding similarity

### Rating Banner
At the top of the Intelligence Feed, a guide banner explains: "Rate each article 1 (Entirely Irrelevant) to 6 (Extremely Relevant) to train the system." This feedback directly shapes how the AI prioritizes future intelligence.

### Sorting
- By publication date (newest first)
- By priority score (highest first)

---

## 5. Cross-Border Intelligence

A dedicated module for monitoring intelligence involving India's borders with Bangladesh and Myanmar. The view is **split into two sections** — Bangladesh and Myanmar — with strict quality filters applied.

### Geographic Split
- **Bangladesh**: Items involving India-Bangladesh border incidents, Rohingya movement, BGP/BGB activity, Dhaka politics with NER impact, economic relations
- **Myanmar**: Items involving India-Myanmar border activity, Tatmadaw operations, Chin/Sagaing/Rakhine spillover, NSCN-K cross-border operations

### Category Classification
Each item is auto-categorized into one of four intelligence domains:
- **Diplomatic**: Bilateral relations, diplomatic outreach, treaties, high-level engagements
- **Defence**: Military operations, border force activity, arms seizures, armed encounters
- **Internal Politics**: Domestic political events with cross-border implications (elections, arrests, protests)
- **Economics**: Trade, smuggling, economic agreements, sanctions impact

### Quality Filters
The Cross-Border view enforces strict quality standards:
- **No LOW severity items** — only Medium, High, and Critical intelligence appears
- **No untranslated content** — items with Bengali, Assamese, or Hindi script that failed translation are hidden
- **Processed only** — items awaiting AI classification are excluded

### Feedback Integration
Analyst feedback ratings on cross-border items are factored into the display scores. Items with high analyst ratings are prioritized within their section.

---

## 6. Daily Brief

Automated daily intelligence summary generated at 0600 IST each day.

### Analyst Assessment
AI-generated strategic overview summarizing the day's most significant developments, identifying trends, and highlighting items requiring immediate attention.

### Sections
- **NER Key Developments**: Top intelligence items strictly from Northeast Indian states (Assam, Manipur, Mizoram, Meghalaya, Nagaland, Tripura, Arunachal Pradesh, Sikkim). No international or non-NER items appear here
- **Cross-Border Intelligence**: Categorized Bangladesh and Myanmar news (Diplomatic, Defence, Internal Politics, Economics) — only items with India-facing relevance are included
- **National News**: Relevant national-level developments affecting NER security
- **International News**: Strategic international items
- **Pattern Insights**: Detected escalation patterns from the Pattern Detection Engine
- **Document Insights**: Analysis from documents uploaded during the current brief period only. Older document analyses do not carry over to new briefs

### Actions
- **REGENERATE BRIEF**: Force regenerate today's brief with the latest data. The brief runs automatically at 0600 IST, but you can manually trigger it anytime
- **EXPORT PDF**: Download the brief as a PDF document with RESTRICTED classification headers. Suitable for distribution within authorized channels

### Cross-Brief Deduplication
News items included in one day's brief are NOT repeated in subsequent briefs. Each brief contains only new intelligence.

---

## 7. Weekly Trends

Visual analytics showing intelligence trends over the past 7 days.

### Charts
- **Severity Distribution**: Bar chart showing Critical/High/Medium/Low counts per day
- **Threat Type Breakdown**: Which threat categories are most active
- **Regional Distribution**: Which NER states have the most activity
- **Cross-Border Activity**: Trend line for cross-border flagged items

Use this page to identify whether the overall threat environment is escalating, stable, or de-escalating over the week.

---

## 8. Pattern Detection

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

## 9. Knowledge Graph

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

## 10. Alerts

Filtered view of CRITICAL and HIGH severity items. This is effectively the Intelligence Feed filtered to only show items requiring immediate attention.

### Acknowledgement
Each alert has an **ACK** button. Clicking it marks the alert as reviewed/handled. Acknowledged alerts move out of the "Unacknowledged" panel on the Dashboard but remain accessible in the full feed.

---

## 11. Keyword Engine

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

## 12. Training & Feedback

The Training & Feedback page is the central hub for shaping the AI's intelligence priorities. It combines analyst feedback ratings, training data uploads, and AI learning analytics into a single operational view.

### Analyst Feedback (1-6 Rating Scale)

Every intelligence item on the Intelligence Feed has a numbered rating bar (1-6) at the top of the card. Rating an article tells the system what you consider relevant.

| Rating | Label | Effect |
|--------|-------|--------|
| 1 | Entirely Irrelevant | Suppresses similar content |
| 2 | Mostly Irrelevant | Reduces weight for this category |
| 3 | Slightly Relevant | Neutral signal |
| 4 | Moderately Relevant | Mild positive signal |
| 5 | Highly Relevant | Boosts similar content |
| 6 | Extremely Relevant | Strongly prioritizes this type |

- **One rating per device per item**: The system uses device fingerprinting to prevent duplicate manipulation. You can update your rating at any time.
- **Max ratings cap**: An admin-configurable limit controls how many total ratings each item can receive (default: 20). Once reached, no further ratings are accepted for that item.

### Key Metrics (Top Row)

The Training page shows five summary metrics:
- **Total Ratings**: All feedback ratings submitted across all analysts
- **Items Rated**: How many unique intelligence items have been rated
- **Analysts**: Number of distinct devices that have submitted ratings
- **Avg Rating**: Global average rating across all feedback
- **Training Queue**: Items waiting to be processed by the training pipeline

### Training Effectiveness Score

A prominent metric showing how well the AI's classifications align with analyst feedback.

- **Score (0-100%)**: Measures agreement between AI severity levels and analyst ratings
- **Grade**: EXCELLENT (80+), GOOD (65+), MODERATE (50+), NEEDS_IMPROVEMENT (35+), POOR (<35)
- **Biggest Gaps**: The 5 items where AI and analyst ratings disagree the most — useful for identifying where the AI needs improvement
- **Best Alignments**: The 5 items where AI and analyst ratings agree the most
- **Trend**: Historical scores captured after each training run, showing whether the system is improving over time
- **Delta**: Change from the last recorded score (e.g., "+3.2% since last run")

### Upload Intelligence URLs

Paste any news URL into the input field to add it to the training queue. The system will scrape the article content and run AI analysis on it.

- **Relevance Tag (1-6)**: Before adding a URL, optionally tag it with a relevance score (1-6) using the numbered buttons below the input. This tells the system how important you consider this source.
- Press Enter or click **Add** to submit

### Upload Documents

Click the upload area to browse for PDF, DOCX, or TXT files. The system extracts text and adds it to the training queue.

### Training Queue

The right panel shows all items awaiting processing:
- **Status badges**: Pending (yellow), Ready (blue), Processing (amber), Completed (green)
- **REL badge**: Shows the relevance tag if one was assigned (e.g., "REL: 5/6")
- Click the trash icon to remove an item from the queue

### Train Rhino Drishti

Click this button to start the training pipeline. The system will:
1. Scrape content from any pending URLs
2. Extract text from uploaded documents
3. Run AI analysis (Claude Haiku) on each item using the military intelligence framework
4. Extract regions, actors, threat categories, and keywords
5. Store results for the Training Pipeline Insights

A progress tracker shows real-time status: items processed, current item title, and percentage complete.

**Live Queue Clearing**: As each item is processed, it automatically disappears from the Training Queue in real-time. You can watch items clear sequentially without needing to refresh the page.

### Analyst Preferences (Feedback)

Aggregated view of what highly-rated content has in common:
- **Preferred Regions**: Regions that analysts consistently rate highly
- **Preferred Threats**: Threat categories that analysts consider most relevant

### Noise Patterns (Low-Rated)

Shows content characteristics that analysts consistently rate as irrelevant. Helps identify what the AI should deprioritize.

### Training Pipeline Insights

After running training, this section shows what the AI learned from uploaded content:
- **Priority Regions**: Regions mentioned in processed training data
- **Key Signals**: Keywords extracted from training articles

### Activity Log

The Activity Log is a clean, session-level table showing the outcome of training and feedback activity. Individual uploads and ratings are NOT logged — only meaningful sessions are recorded.

| Column | Description |
|--------|-------------|
| **Timestamp** | When the session occurred |
| **Device** | Analyst device ID (last 6 characters, for feedback sessions only) |
| **Activity Type** | "URL/Article Training" or "Rating Feedback" |
| **Volume** | Item count with breakdown (e.g., "12 items (8 URLs, 4 documents)" or "5 ratings (1x3, 2x4, 1x5, 1x6)") |
| **Impact** | AI-generated summary of what the system learned from this session |

**Training Sessions** are logged when you click "Train Rhino Drishti". The impact summary describes which regions, actors, and threat categories were strengthened.

**Feedback Sessions** are automatically created when an analyst submits 5 or more ratings. The impact summary describes what content types were upweighted or suppressed based on the rating distribution.

### Scoring Integration

The Scoring Integration panel shows the formula used to combine AI and analyst feedback:
```
final_score = base_ai_score + training_bias + feedback_bias
training_bias = log(total_ratings + 1) * (avg_rating - 3.5)
```

This means items with high analyst ratings get boosted in the intelligence feed, while low-rated items are deprioritized.

---

## 13. Document Upload

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

## 14. User Management

*Admin only — not visible to Analyst or Viewer roles.*

### Accessing User Management
Click **User Management** in the sidebar (visible to Admin users only).

### User List
Displays all registered users with:
- **Username** — login identifier
- **Name** — display name
- **Role** — Admin / Analyst / Viewer (color-coded badges)
- **Status** — Active (green) or Inactive (red). Click to toggle.
- **Last Login** — timestamp of most recent login
- **Actions** — Reset password, Delete user

### Creating a New User
1. Click **Create User** (top-right)
2. Fill in the form:
   - **Username** (required) — unique login identifier
   - **Email** — optional but useful for login flexibility (users can log in with either)
   - **Full Name** — display name shown in the interface
   - **Role** — select Admin, Analyst, or Viewer
   - **Password** (required, min 8 characters)
3. Use **Generate** button to create a strong 14-character random password
4. Use **Copy** button to copy the password to clipboard
5. Click **Create User** to save

**WARNING:** Passwords are shown only once during creation. Copy the password before closing the form.

### Resetting a Password
1. Click the **Key** icon next to any user in the table
2. Enter a new password manually, or click **Generate** for a random one
3. Click **Copy** to save the password to clipboard
4. Click **Reset** to apply
5. Share the new password securely with the user

**Passwords cannot be retrieved** — they can only be reset. This is by design for security.

### Deactivating a User
Click the **Active/Inactive** status text for any user to toggle their access. Deactivated users cannot log in but their account is preserved.

### Deleting a User
Click the **Trash** icon to permanently delete a user. You cannot delete your own account. This action cannot be undone.

---

## 15. Settings

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

### Maximum Feedback Ratings Per Item
Controls how many analyst ratings each intelligence item can receive before the system stops accepting new feedback. This prevents over-rating or manipulation.

Default: 20 ratings per item. Use the dropdown to adjust.

When the limit is reached for an item, the rating widget will indicate that no further ratings are accepted.

---

## 16. How the AI Pipeline Works

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
    Language Detection & Translation (Bengali/Assamese/Hindi -> English)
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
    Analyst Feedback Integration (rating-based bias adjustment)
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
| Article Fusion | Every 30 min | Detect and cluster duplicate articles across sources |

---

## 17. Glossary

| Term | Definition |
|------|-----------|
| **ACK** | Acknowledge — mark an alert as reviewed |
| **Activity Log** | Session-level record of training runs and feedback sessions with AI-generated impact summaries |
| **JWT** | JSON Web Token — authentication token used for session management |
| **RBAC** | Role-Based Access Control — restricts features based on user role |
| **Cluster / Fusion** | Group of similar articles from multiple sources merged into a single intelligence item |
| **Cross-border** | Activity involving more than one country |
| **Device Fingerprint** | Unique identifier generated per browser/device to prevent duplicate ratings |
| **Effectiveness Score** | Percentage (0-100) measuring alignment between AI classifications and analyst feedback ratings |
| **Escalation Risk** | Likelihood that a pattern of events will intensify |
| **Feedback Session** | Aggregated log entry created after an analyst submits 5+ ratings, with AI-generated impact summary |
| **Hard Filter** | Rule-based rejection of irrelevant content (sports, entertainment) |
| **Impact Summary** | AI-generated description of what the system learned from a training run or feedback session |
| **Knowledge Graph** | Network of relationships between actors and locations |
| **NER** | North Eastern Region of India (Assam, Manipur, Meghalaya, Mizoram, Tripura, Nagaland, Arunachal Pradesh, Sikkim) |
| **Pattern** | Cluster of 3+ intelligence items sharing the same region, threat type, or actor |
| **Priority Score** | AI-assigned importance score from 0-100 |
| **Relevance Tag** | Optional 1-6 score an analyst assigns to a URL when adding it to the training queue |
| **Semantic Search** | AI-powered search using vector embeddings that finds related concepts |
| **Severity** | Classification level: Critical > High > Medium > Low |
| **Sifter** | Level 1 pre-filter that screens articles for border/militant relevance |
| **Special Flags** | AI-detected indicators: PLA_PAKISTAN_PRESENCE, COORDINATED_NARRATIVE, INFRASTRUCTURE_DUAL_USE |
| **Threat Trajectory** | Direction of a threat: ESCALATING, STABLE, DE-ESCALATING, NEW_THREAT |
| **Training Pipeline** | Process of scraping, analyzing, and learning from analyst-submitted URLs and documents |
| **Training Session** | Log entry created when "Train Rhino Drishti" is clicked, capturing volume breakdown and AI impact |
| **Vector Embedding** | Mathematical representation of text meaning, enabling semantic similarity search |

---

*Rhino Drishti v6.0 — Elite OSINT Intelligence Platform with Authentication & RBAC*
*Handbook updated: April 2026*
