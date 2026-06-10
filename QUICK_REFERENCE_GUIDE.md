```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                          ║
║     ██████╗ ██╗  ██╗██╗███╗   ██╗ ██████╗     ██████╗ ██████╗ ██╗███████╗██╗  ██╗████████╗██╗    ║
║     ██╔══██╗██║  ██║██║████╗  ██║██╔═══██╗    ██╔══██╗██╔══██╗██║██╔════╝██║  ██║╚══██╔══╝██║    ║
║     ██████╔╝███████║██║██╔██╗ ██║██║   ██║    ██║  ██║██████╔╝██║███████╗███████║   ██║   ██║    ║
║     ██╔══██╗██╔══██║██║██║╚██╗██║██║   ██║    ██║  ██║██╔══██╗██║╚════██║██╔══██║   ██║   ██║    ║
║     ██║  ██║██║  ██║██║██║ ╚████║╚██████╔╝    ██████╔╝██║  ██║██║███████║██║  ██║   ██║   ██║    ║
║     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝     ╚═════╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝    ║
║                                                                                          ║
║                     OSINT INTELLIGENCE PLATFORM — QUICK REFERENCE GUIDE                  ║
║                            NER + CROSS-BORDER SECURITY MONITORING                        ║
║                                       v10.0 | June 2026                                  ║
║                                                                                          ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

---

# SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RHINO DRISHTI ARCHITECTURE                       │
│                                                                         │
│   72 RSS SOURCES ──┐                                                    │
│   Manual URLs ─────┤                                                    │
│   Uploaded Docs ───┤──▶ INGESTION ──▶ AI PIPELINE ──▶ INTELLIGENCE DB   │
│   Social Media ────┤    ENGINE        (Claude AI)      (MongoDB)       │
│   (Future: X, IG) ─┘                                                   │
│                                            │                            │
│                                            ▼                            │
│                    ┌──────────────────────────────────────┐              │
│                    │        OUTPUT LAYER                   │              │
│                    │  Dashboard | Feed | Briefs | Alerts  │              │
│                    │  Cross-Border | Patterns | Keywords  │              │
│                    │  Faultlines | Trends | Knowledge Graph│             │
│                    └──────────────────────────────────────┘              │
│                                            │                            │
│                    ANALYST FEEDBACK ◀──────┘                            │
│                         │                                               │
│                         ▼                                               │
│                    FEEDBACK BIAS ENGINE ──▶ AI PIPELINE (loop)          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# 1. DATA INGESTION

## Source Breakdown (72 RSS Feeds)

```
    ┌──────────────────────────────────────────────────────┐
    │  REGIONAL (12)    NE Now, Assam Tribune, Sentinel,   │
    │                   EastMojo, North East Live, etc.     │
    │──────────────────────────────────────────────────────│
    │  NATIONAL (19)    NDTV, Hindu, India Today, HT,      │
    │                   The Wire, Scroll, Print, Quint,     │
    │                   Indian Express, FirstPost, etc.     │
    │──────────────────────────────────────────────────────│
    │  BANGLADESH (19)  Prothom Alo, Daily Star, Kaler      │
    │                   Kantho, Dhaka Tribune, BD News, etc.│
    │──────────────────────────────────────────────────────│
    │  MYANMAR (14)     Myanmar Now, Irrawaddy, Mizzima,    │
    │                   DVB, Frontier Myanmar, etc.          │
    │──────────────────────────────────────────────────────│
    │  INTERNATIONAL (5) BBC, Al Jazeera, Reuters, etc.     │
    │──────────────────────────────────────────────────────│
    │  GOVERNMENT (3)   PIB Press Releases, PIB Defence,    │
    │                   MHA India                            │
    └──────────────────────────────────────────────────────┘
```

## Fetch Schedule

| Cycle | Frequency | Sources |
|-------|-----------|---------|
| Grassroots | Every 60 min | Small/hard-to-reach NER outlets |
| Standard | Every 30 min | National + international feeds |
| Established | Every 12 hours | Government + stable large sources |
| AI Retry | Every 15 min | Reprocess failed classifications |
| Fusion Scan | Every 30 min | Detect and merge duplicate articles |
| Daily Brief | 06:00 IST | Auto-generate PDF intelligence report |
| Faultline Pass | Daily (scheduled) | Score all active faultlines |

---

# 2. THE AI PIPELINE (10-Step Classification)

Every article passes through a **10-step military intelligence analysis** powered by Claude Haiku 4.5:

```
 RAW ARTICLE
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  STEP 1 ─── RELEVANCE FILTER                                       │
│             Hard reject: sports, entertainment, lifestyle,          │
│             stock markets, weather, local crime, obituaries         │
│             Accept: security signals, border activity, military,    │
│             insurgency, cross-border, infrastructure, foreign       │
│             influence, societal instability, emerging tech           │
│                                                                     │
│  STEP 2 ─── PRIORITY SCORING (0-100)                               │
│             80-100 = CRITICAL  |  60-79 = HIGH                      │
│             40-59  = MEDIUM    |  <40   = LOW                       │
│             Boosters: Cross-border +10, China/Pak +15,              │
│             Military +10, Pattern detected +5                       │
│                                                                     │
│  STEP 3 ─── MULTI-LABEL CLASSIFICATION (19 threat categories)      │
│             Military Movement, Insurgency, Drug Trafficking,        │
│             Arms Smuggling, Border Security, Ethnic Tension,        │
│             Cyber Threats, Info Warfare, Foreign Influence...        │
│                                                                     │
│  STEP 4 ─── CONTEXTUAL EXTRACTION                                  │
│             Region(s), Cross-border flag, Countries, Actors          │
│                                                                     │
│  STEP 5 ─── NAMED ENTITY EXTRACTION                                │
│             Persons, Organizations, Locations                        │
│                                                                     │
│  STEP 6 ─── INTELLIGENCE OUTPUT                                    │
│             Summary (3 lines), Why It Matters (2 lines),            │
│             Early Warning Signal, Attention Level,                   │
│             Threat Trajectory, Confidence Score                      │
│                                                                     │
│  STEP 7 ─── SPECIAL FLAG DETECTION                                 │
│             PLA_PAKISTAN_PRESENCE | COORDINATED_NARRATIVE            │
│             DEMOGRAPHIC_TREND | DUAL_USE_INFRA | PATTERN_DETECTED   │
│                                                                     │
│  STEP 8 ─── INDIA-RELEVANCE SCORING (cross-border, 0-20)          │
│             +4 India mentioned, +3 NER states, +3 border keywords,  │
│             +2 armed actors, +2 economic spillover, +3 key locations │
│                                                                     │
│  STEP 9 ─── SIGNAL CLASSIFICATION (cross-border bucket)            │
│             border_security | infiltration | smuggling |             │
│             migration_refugees | insurgency | extremism |            │
│             military_movement | conflict_escalation                  │
│             Signal strength: HIGH / MEDIUM / LOW                     │
│                                                                     │
│  STEP 10 ── LANGUAGE ENFORCEMENT                                   │
│             All output in English regardless of input language       │
│                                                                     │
│  + FEEDBACK BIAS INJECTION (Dynamic)                                │
│    Analyst ratings aggregated into upweight/downweight patterns      │
│    Injected as calibration context into the prompt                   │
│    Influence: Light (10-15%) / Moderate (20-25%) / High (35-40%)    │
│                                                                     │
│  + FAULTLINE TAGGING (Post-Classification)                          │
│    Each article matched against active faultlines                    │
│    PAOI faultlines tagged RED in daily brief                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
 CLASSIFIED INTELLIGENCE ITEM ──▶ MongoDB ──▶ WebSocket ──▶ Live UI
```

---

# 3. SEVERITY & PRIORITY MATRIX

```
┌────────────┬───────────┬─────────────────────────────────────────────┐
│  SEVERITY  │  SCORE    │  MEANING                                    │
├────────────┼───────────┼─────────────────────────────────────────────┤
│  CRITICAL  │  80-100   │  Immediate operational relevance.           │
│            │           │  Active threat to personnel/assets.         │
│            │           │  Cards glow red. Triggers alert.            │
├────────────┼───────────┼─────────────────────────────────────────────┤
│  HIGH      │  60-79    │  Significant security concern.              │
│            │           │  Requires priority monitoring.              │
│            │           │  Orange severity badge.                     │
├────────────┼───────────┼─────────────────────────────────────────────┤
│  MEDIUM    │  40-59    │  Situational awareness required.            │
│            │           │  May escalate. Monitor trends.              │
│            │           │  Yellow severity badge.                     │
├────────────┼───────────┼─────────────────────────────────────────────┤
│  LOW       │  <40      │  Background noise. Filtered from            │
│            │           │  feeds and Daily Brief PDF.                 │
│            │           │  Not shown in main UI.                      │
└────────────┴───────────┴─────────────────────────────────────────────┘
```

## Threat Trajectory Indicators

```
  ESCALATING ──── Situation worsening. Multiple incidents forming pattern.
  STABLE ──────── No change in threat level. Ongoing monitoring.
  DE-ESCALATING ─ Tensions reducing. Positive signals detected.
  NEW_THREAT ──── Previously undetected threat vector. Requires assessment.
```

---

# 4. MULTI-ARTICLE FUSION ENGINE

When multiple sources cover the same event, the system detects and merges them:

```
  Source A: "Arms cache found in Chandel"  ──┐
  Source B: "Manipur police seize weapons"  ──┼──▶ FUSION ──▶ Single card
  Source C: "Indo-Myanmar border seizure"   ──┘              showing "3 sources"
```

**6 Detection Methods:**
1. Exact title matching
2. Source URL deduplication
3. Title word overlap (>60% similarity)
4. Named entity overlap (orgs, places, events)
5. Compound keyphrase matching ("ULFA-I chief", "shots fired")
6. Same-source geographic clustering

---

# 5. CROSS-BORDER INTELLIGENCE MODULE

```
┌──────────────────────────┐    ┌──────────────────────────┐
│      BANGLADESH          │    │        MYANMAR            │
│                          │    │                            │
│  4 Intelligence Domains: │    │  4 Intelligence Domains:  │
│  ┌────────────────────┐  │    │  ┌────────────────────┐   │
│  │ Diplomatic         │  │    │  │ Diplomatic          │   │
│  │ Defence            │  │    │  │ Defence             │   │
│  │ Internal Politics  │  │    │  │ Internal Politics   │   │
│  │ Economics          │  │    │  │ Economics           │   │
│  └────────────────────┘  │    │  └────────────────────┘   │
│                          │    │                            │
│  Posture Assessment:     │    │  Posture Assessment:      │
│  STABLE / WATCHFUL /     │    │  STABLE / WATCHFUL /      │
│  ELEVATED / DETERIORATING│    │  ELEVATED / DETERIORATING │
└──────────────────────────┘    └──────────────────────────┘
```

**Quality Filters Applied:**
- No LOW severity items
- No untranslated content (Bengali/Assamese/Hindi script filtered)
- Processed items only

---

# 6. FEEDBACK BIAS LOOP (Closed-Loop AI Learning)

```
  ┌───────────────────────────────────────────────────────────┐
  │                                                           │
  │  ANALYST rates articles 1-6 on Intelligence Feed          │
  │       │                                                   │
  │       ▼                                                   │
  │  FEEDBACK ENGINE aggregates ratings (30-day / all-time)   │
  │       │                                                   │
  │       ▼                                                   │
  │  BIAS PROFILE computed:                                   │
  │    Upweight: Regions + Threats analysts rated highly       │
  │    Downweight: Regions + Threats analysts rated poorly     │
  │       │                                                   │
  │       ▼                                                   │
  │  AI PROMPT INJECTION: Bias appended to classification     │
  │    prompt as "Analyst Feedback Calibration" section        │
  │       │                                                   │
  │       ▼                                                   │
  │  NEW ARTICLES scored with analyst-adjusted priorities      │
  │       │                                                   │
  │       ▼                                                   │
  │  IMPACT REPORT: Before/after scores visible in Settings   │
  │                                                           │
  └───────────────────────────────────────────────────────────┘

  Configurable in Settings:
  ┌─────────────────┬────────────────────────────────────────┐
  │ Window          │ Rolling 30 Days  |  All Time           │
  │ Influence       │ Light (10-15%)   |  Moderate (20-25%)  │
  │                 │ High (35-40%)                           │
  │ Cache TTL       │ 5 minutes (auto-recompute)             │
  └─────────────────┴────────────────────────────────────────┘
```

## Analyst Rating Scale

```
  1 ──── Entirely Irrelevant        (suppresses similar content)
  2 ──── Mostly Irrelevant          (reduces category weight)
  3 ──── Slightly Relevant          (neutral signal)
  4 ──── Moderately Relevant        (boosts similar content)
  5 ──── Very Relevant              (strong positive signal)
  6 ──── Extremely Relevant         (maximum boost for this type)
```

## Training Summary Page

The **Training Summary** page visualises the cumulative effect of analyst ratings:
- Breakdown of ratings by region and threat category
- Upweight / downweight bias profile as a chart
- Before/after priority score comparison for sampled articles
- Reachable from sidebar under "Training"

---

# 7. DAILY INTELLIGENCE BRIEF (PDF)

Auto-generated at 06:00 IST daily. Contains:

```
┌─────────────────────────────────────────────────┐
│  RHINO DRISHTI DAILY INTELLIGENCE BRIEF         │
│  Classification: RESTRICTED                      │
│                                                  │
│  Section 1: CRITICAL & HIGH PRIORITY             │
│  ─────────────────────────────────               │
│  Top severity items from the last 24 hours       │
│  PAOI faultlines flagged RED                     │
│                                                  │
│  Section 2: NER REGIONAL DEVELOPMENTS            │
│  ─────────────────────────────────               │
│  State-wise intelligence from all NER states     │
│                                                  │
│  Section 3: CROSS-BORDER — BANGLADESH            │
│  ─────────────────────────────────               │
│  Categorized: Diplomatic/Defence/Politics/Econ   │
│                                                  │
│  Section 4: CROSS-BORDER — MYANMAR               │
│  ─────────────────────────────────               │
│  Categorized: Diplomatic/Defence/Politics/Econ   │
│                                                  │
│  Section 5: NATIONAL DEVELOPMENTS                │
│  ─────────────────────────────────               │
│  Security-relevant national news (strict filter) │
│                                                  │
│  Section 6: INTERNATIONAL                        │
│  ─────────────────────────────────               │
│  Strategic international developments            │
│                                                  │
│  Section 7: PATTERN INSIGHTS                     │
│  ─────────────────────────────────               │
│  AI-detected patterns with escalation risk       │
│                                                  │
│  Section 8: FAULTLINE SUMMARY                    │  ← NEW
│  ─────────────────────────────────               │
│  Top stressed faultlines with scores + deltas    │
│  PAOI items highlighted                          │
│                                                  │
│  Section 9: UPLOADED DOCUMENT INSIGHTS            │
│  ─────────────────────────────────               │
│  Summaries of manually analyzed docs (24hr)      │
│                                                  │
│  DISTRIBUTION: RESTRICTED                        │
│  FOR AUTHORIZED PERSONNEL ONLY                   │
└─────────────────────────────────────────────────┘
```

## Brief Variants

The Briefs page has three tabs:

| Tab | Description |
|-----|-------------|
| **Daily Brief** | Auto-generated 06:00 IST. 24-hour window. PDF download available. |
| **Fortnightly Brief** | Two-week rolling synthesis. Covers major trends and emerging patterns across the period. |
| **Monthly Strategic Brief** | Senior-commander level. Full state analysis, PAOI assessment, faultline report, mitigation playbook. See Section 14. |

---

# 8. KEYWORD ENGINE (Dynamic Detection)

```
  ┌───────────────────────────────────────────────────────────┐
  │  KEYWORD TYPES                                            │
  │                                                           │
  │  [RED]    Primary Threat    "insurgency", "drone activity"│
  │  [BLUE]   Entity/Actor      "ULFA movement Assam"         │
  │  [YELLOW] Geographic         "Manipur violence"            │
  │  [PURPLE] Cross-Border       "India Bangladesh border"     │
  │  [GREEN]  AI Emerging Signal "drug-militant nexus"         │
  │  [GREY]   AI Expanded        "unauthorized border crossing"│
  │                                                           │
  │  SCORING: 0-100 (based on frequency, severity, recency)   │
  │  ADAPTIVE: High-severity matches boost, LOW matches decay  │
  │  MANUAL ADD: Search + add custom keywords with type/score  │
  │  ANALYSIS ADD: Select entities from analyzed docs/URLs     │
  └───────────────────────────────────────────────────────────┘
```

### Adding Keywords from Analysis Results

After analyzing a URL or document:
1. Expand the analysis card to see **Key Entities** (actors, locations, events)
2. Click any entity badge to select it — it highlights with a colored ring
3. Select multiple entities as needed
4. A bar appears: **"N selected → + ADD TO KEYWORD BANK"** — click to add all
5. Actors → `entity` type, Locations → `geo` type, Events → `primary` type
6. All added at score 70 (High). Duplicates are silently skipped.

---

# 9. MANUAL INTELLIGENCE UPLOADS

Three workflows for manually adding intelligence:

```
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  WORKFLOW 1: UPLOAD FILE                                │
  │  PDF/DOCX/TXT ──▶ Text extraction ──▶ AI Analysis      │
  │                                                         │
  │  WORKFLOW 2: ANALYZE URL                                │
  │  Paste URL ──▶ Scrape content ──▶ AI Contextual        │
  │                 Assessment (against last 7 days of      │
  │                 live intelligence)                       │
  │                                                         │
  │  WORKFLOW 3: ADD TO FEED (Direct)                       │
  │  Paste URL ──▶ Set severity, priority, threat,          │
  │                 region, summary manually                 │
  │             ──▶ Instantly appears in Feed + Dashboard    │
  │                                                         │
  │  POST-ANALYSIS: Click "Add to Feed" on any analyzed     │
  │  card ──▶ Modal pre-filled with AI classification       │
  │  ──▶ Review/adjust ──▶ Confirm ──▶ Added to Feed        │
  │                                                         │
  │  KEYWORD EXTRACTION: Click entity badges in analysis    │
  │  results to add actors/locations/events to Keyword Bank  │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

**Add to Feed fields:**

| Field | Options |
|-------|---------|
| Title | Auto-scraped from URL or manual |
| Severity | Critical / High / Medium / Low |
| Priority Score | 0–100 slider |
| Threat Category | 18 categories |
| Region / State | All NER states + Bangladesh, Myanmar, India |
| Summary | Free-text intelligence summary |
| Cross-Border | Checkbox |

**Duplicate detection:** Same URL already in feed → "This URL already exists" error.

---

# 10. ROLE-BASED ACCESS CONTROL (RBAC)

```
  ┌──────────┬────────────────────────────────────────┐
  │  ADMIN   │  Full access. User management. Settings.   │
  │          │  All actions enabled. Auto-seeded on        │
  │          │  first deployment. Can create app updates.  │
  ├──────────┼────────────────────────────────────────┤
  │  ANALYST │  All intelligence features. Cannot access   │
  │          │  User Management or Settings. Full feed,    │
  │          │  training, upload, rating, brief-generate   │
  │          │  capabilities. Can trigger faultline pass.  │
  ├──────────┼────────────────────────────────────────┤
  │  VIEWER  │  Read-only. Can view all intelligence,      │
  │          │  dashboards, download PDFs. All action      │
  │          │  buttons disabled. No Settings menu.        │
  └──────────┴────────────────────────────────────────┘
```

---

# 11. COMPLETE DATA FLOW (End-to-End)

```
RSS (72 sources) ──────────────────┐
Manual URLs ───────────────────────┤
Uploaded Documents ────────────────┤
Social Media Feeds ────────────────┤
                                   ▼
                        ┌─────────────────┐
                        │  DEDUPLICATION   │  URL + title similarity check
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  HARD FILTER    │  Reject sports/entertainment/lifestyle
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  KEYWORD MATCH  │  Weighted scoring against 300+ keywords
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  TRANSLATION    │  Bengali/Assamese/Hindi ──▶ English
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  LEVEL 1 SIFT   │  Pre-filter: border, militant, security
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  LEVEL 2 AI     │  10-step Claude classification
                        │  + FEEDBACK     │  + Dynamic analyst bias injection
                        │    BIAS         │
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  FAULTLINE TAG  │  Match article to active faultlines
                        └────────┬────────┘  Flag PAOIs in daily brief
                                 ▼
                        ┌─────────────────┐
                        │  VECTOR EMBED   │  OpenAI text-embedding-3-small
                        └────────┬────────┘  (enables semantic search)
                                 ▼
                        ┌─────────────────┐
                        │  KEYWORD ADAPT  │  Boost/decay keyword scores based
                        └────────┬────────┘  on classification results
                                 ▼
                        ┌─────────────────┐
                        │  PATTERN DETECT │  Sliding-window cluster analysis
                        └────────┬────────┘  (3+ similar items = pattern)
                                 ▼
                        ┌─────────────────┐
                        │  FUSION ENGINE  │  Merge duplicate articles
                        └────────┬────────┘  across sources
                                 ▼
                        ┌─────────────────┐
                        │  WEBSOCKET      │  Real-time push to all
                        │  BROADCAST      │  connected clients
                        └────────┬────────┘
                                 ▼
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
         DASHBOARD       INTELLIGENCE         CROSS-BORDER
         (overview)       FEED (full)          WATCH (BD/MM)
              │                  │                  │
              ▼                  ▼                  ▼
         DAILY BRIEF     SEMANTIC SEARCH      FAULTLINE
         (PDF @ 0600)    (vector-powered)     INTELLIGENCE
              │                  │                  │
              ▼                  ▼                  ▼
        MONTHLY BRIEF    KNOWLEDGE GRAPH      TRENDS CENTRE
```

---

# 12. COVERAGE MAP

```
  PRIMARY MONITORING ZONE (NER):
  ┌────────────────────────────────────────┐
  │  Arunachal Pradesh                      │
  │  Assam                                  │
  │  Manipur                                │
  │  Meghalaya                              │
  │  Mizoram                                │
  │  Nagaland                               │
  │  Sikkim                                 │
  │  Tripura                                │
  └────────────────────────────────────────┘

  CROSS-BORDER MONITORING:
  ┌────────────────────────────────────────┐
  │  Bangladesh (19 sources)                │
  │  Myanmar (14 sources)                   │
  └────────────────────────────────────────┘

  NATIONAL & STRATEGIC:
  ┌────────────────────────────────────────┐
  │  India National (19 sources)            │
  │  International (BBC, Al Jazeera, etc.)  │
  │  Government (PIB, MHA)                  │
  └────────────────────────────────────────┘

  THREAT ACTORS MONITORED:
  ┌────────────────────────────────────────┐
  │  ULFA-I, NSCN-K/IM, PLA (Manipur),    │
  │  HNLC, NLFT, KNF/KLA (Chin), Arakan   │
  │  Army, Tatmadaw, BGB, PLA (China),     │
  │  ISI/Pakistan proxies, JMB, HuJI       │
  └────────────────────────────────────────┘
```

---

# 13. FAULTLINE INTELLIGENCE SYSTEM

The **Faultline Intelligence** module tracks deep structural tensions — political, ethnic, economic, and social — that are precursors to instability. Unlike the news feed (event-driven), faultlines are scored continuously from the aggregate pattern of articles over time.

## Faultline Registry

```
  40 faultlines registered across:
  ┌────────────────────────────────────────────────────┐
  │  NER States (8):  Per-state structural tensions    │
  │  Bangladesh:      Border, political, economic       │
  │  Myanmar:         Conflict spillover, Arakan Army  │
  │  Cross-cutting:   Ethnic, insurgency, migration    │
  └────────────────────────────────────────────────────┘
```

## Faultline Scoring

Each faultline receives a **daily score (0–100)** computed from:
- Volume of matched articles in the scoring window
- Severity distribution of those articles (CRITICAL = 4×, HIGH = 3×, MEDIUM = 2×, LOW = 1×)
- Month-over-month (MoM) change in score

```
  ┌────────────┬───────────┬────────────────────────────────────────┐
  │  STATUS    │  SCORE    │  MEANING                               │
  ├────────────┼───────────┼────────────────────────────────────────┤
  │  CRITICAL  │  75-100   │  Active, high-volume faultline.        │
  │            │           │  Likely escalating. Immediate review.  │
  ├────────────┼───────────┼────────────────────────────────────────┤
  │  MONITOR   │  40-74    │  Elevated activity. Watch closely.     │
  ├────────────┼───────────┼────────────────────────────────────────┤
  │  STABLE    │  15-39    │  Low-level activity. Background noise. │
  ├────────────┼───────────┼────────────────────────────────────────┤
  │  DORMANT   │  0-14     │  No significant activity detected.     │
  └────────────┴───────────┴────────────────────────────────────────┘
```

## Dashboard Pulse Strip

Top 5 most-stressed faultlines displayed on the main Dashboard as a horizontal **Faultline Pulse Strip**:
- Faultline name + state
- Current score
- MoM delta (green = improving, red = worsening)
- Status badge (CRITICAL / MONITOR / STABLE / DORMANT)

## Warning Alerts

When a faultline crosses the CRITICAL threshold, a **warning alert** is raised:
- Shown as a dismissable banner on the Faultlines page
- Alert includes faultline name, score, and date triggered
- Analyst/Admin can acknowledge (dismiss) the alert
- Alerts auto-expire after 48 hours if not acknowledged

## Faultline Detail Page

Clicking any faultline opens a detail view:

```
  ┌──────────────────────────────────────────────────┐
  │  FAULTLINE NAME                                  │
  │  State | Category | Status badge                 │
  │                                                  │
  │  Current Score: 88/100 (CRITICAL)  MoM: +24     │
  │                                                  │
  │  30-day Score Trendline (line chart)             │
  │                                                  │
  │  LLM Narrative Analysis (paragraph)              │
  │                                                  │
  │  Matched Articles (last 7 days)                  │
  │  — Each article with title, date, severity,      │
  │    relevance rationale                           │
  │                                                  │
  │  Analyst Notes (editable, auto-saved)            │
  └──────────────────────────────────────────────────┘
```

## Priority Areas of Interest (PAOIs)

PAOIs are **designated high-watch faultlines** manually tagged by analysts as requiring sustained command attention. Currently seeded:
- Bangladesh border–related faultlines (disinformation, border security, infiltration)
- Myanmar conflict spillover faultlines

**PAOI articles are tagged RED** in the daily brief and in the Monthly Strategic Brief's PAOI section.

## Faultline PDF Report

A **standalone 5-page Faultline Analysis Report** PDF is downloadable from the Faultlines page:

```
  Page 1: Cover + executive summary of top faultlines
  Page 2: Month-on-month movers (biggest score changes)
  Page 3: Top 5 faultlines — narrative analysis
  Page 4: Drivers & article evidence
  Page 5: PAOI faultlines — dedicated deep-dive
```

## Backfill

Faultlines can be **backfilled** historically (up to 90 days by default) to establish baseline scores before the system was deployed. Backfill progress is visible in a status panel. Admin/Analyst only.

---

# 14. MONTHLY STRATEGIC BRIEF

The **Monthly Strategic Brief** is a comprehensive intelligence playbook for senior commanders, generated on demand for any past month.

## Generation

- Triggered manually from the Briefs → Monthly tab
- Runs in background; generation status shown in UI
- Uses Gemini 2.5 Flash via OpenRouter for synthesis
- Per-state synthesis runs in parallel for speed

## Structure

```
  ┌─────────────────────────────────────────────────┐
  │  MONTHLY STRATEGIC INTELLIGENCE BRIEF           │
  │  [Month Year] | Classification: RESTRICTED      │
  │                                                  │
  │  Tab 1: OVERVIEW                                 │
  │  ─────────────────────────────────               │
  │  Executive summary, key statistics,              │
  │  top threat categories, severity distribution    │
  │                                                  │
  │  Tab 2: STATE ANALYSIS                           │
  │  ─────────────────────────────────               │
  │  Per-state synthesis for all 8 NER states        │
  │  [CONFIRMED] / [ASSESSED] / [SPECULATIVE] labels │
  │                                                  │
  │  Tab 3: CROSS-BORDER                             │
  │  ─────────────────────────────────               │
  │  Bangladesh + Myanmar situation assessments      │
  │  Posture: STABLE / WATCHFUL / ELEVATED /         │
  │           DETERIORATING                          │
  │                                                  │
  │  Tab 4: FAULTLINE ASSESSMENT                     │
  │  ─────────────────────────────────               │
  │  All active faultlines scored for the month      │
  │  Top movers + LLM narrative                      │
  │                                                  │
  │  Tab 5: PRIORITY AREAS OF INTEREST (PAOI)        │
  │  ─────────────────────────────────               │
  │  Deep-dive on designated PAOI faultlines         │
  │  Evidence from matched articles                  │
  │                                                  │
  │  Tab 6: MITIGATION PLAYBOOK                      │
  │  ─────────────────────────────────               │
  │  Recommended actions for BD + Myanmar            │
  └─────────────────────────────────────────────────┘
```

## Claim Labeling

All LLM-generated text is tagged with one of three claim labels:

```
  [CONFIRMED]   — Direct factual claim drawn from intelligence items
  [ASSESSED]    — Inference from patterns and corroborating evidence
  [SPECULATIVE] — Forward-looking forecast / probability statement
```

## Download Options

| Option | Content |
|--------|---------|
| **Full PDF** | Complete brief — all tabs, all states, full narrative |
| **Combined PDF** | Summary version for distribution |
| **NotebookLM Export** | Markdown text optimised for Google NotebookLM video overview generation |

---

# 15. TRENDS INTELLIGENCE CENTRE

The **Trends** page provides multi-timeframe statistical analysis of intelligence patterns across NER and cross-border regions.

## Time Ranges

```
  24h | 7d | 30d | 90d | 365d
```

## Visualisations

| Chart | Description |
|-------|-------------|
| **State Severity Evolution** | Line chart — daily severity count per NER state. Hover tooltip lists states sorted by score descending. |
| **Severity Trend Aggregate** | Area chart — total articles per severity level over time. Tooltip orders: CRITICAL → HIGH → MEDIUM → LOW. |
| **State-wise Activity (Range)** | Bar chart — article count by state. Unclassified items grouped as "Unclassified". |
| **Threat Category Distribution** | Bar chart — top threat categories by article count in the selected window. |
| **Top Actors Frequency** | Actor mention frequency across the period. |
| **Cross-Border Correlation** | Correlation between Bangladesh/Myanmar events and NER activity. |
| **Stability Index** | Per-state composite stability score (composite of severity weight + volume + trajectory). |

## State Drill-Down

Clicking any state opens a drill-down view with:
- State-specific severity timeline
- Top threat categories for that state
- Key actors and entities extracted
- Cross-border linkages

---

# 16. SOCIAL MEDIA INTELLIGENCE

The **Social Media** module ingests content from multiple platforms into the intelligence pipeline.

## Supported Platforms

```
  ┌──────────────┬──────────────────────────────────────────┐
  │  X (Twitter) │  Monitor accounts, keyword searches,     │
  │              │  and Twitter Lists                        │
  ├──────────────┼──────────────────────────────────────────┤
  │  YouTube     │  Monitor channels and keyword searches   │
  ├──────────────┼──────────────────────────────────────────┤
  │  Facebook    │  Monitor public pages                    │
  ├──────────────┼──────────────────────────────────────────┤
  │  Telegram    │  Monitor public channels                 │
  └──────────────┴──────────────────────────────────────────┘
```

## Configuration

Each platform source can be:
- Added with a name, handle/channel ID, and category
- Toggled active/inactive without deletion
- Fetched on-demand per source
- Fetched across all platforms in one operation (Admin)

## Social Media Feed Widget

The Dashboard includes a **Social Media Feed Widget** showing recent ingested social posts alongside RSS items. Posts that pass the AI relevance filter appear as intelligence cards in the main feed.

---

# 17. KNOWLEDGE GRAPH

The **Knowledge Graph** page visualises entity relationships extracted from intelligence items.

## What It Shows

```
  NODES:
  ┌────────────────────────────────────────────┐
  │  Persons        — named individuals        │
  │  Organizations  — militant groups, govt    │
  │  Locations      — states, cities, borders  │
  └────────────────────────────────────────────┘

  EDGES:
  ┌────────────────────────────────────────────┐
  │  Co-occurrence in articles                 │
  │  Directional relationships (actor→action)  │
  └────────────────────────────────────────────┘
```

## Usage

- **Build Graph** — Admin/Analyst can trigger a rebuild from recent articles
- **Filter by actor type** — Security forces vs insurgent groups vs government
- **Insurgent whitelist** — Militant actor aliases are canonicalised (e.g., multiple names for ULFA-I resolve to one node)

---

# 18. PLATFORM UPDATE NOTIFICATIONS

The system displays **in-app version update notifications** to keep users informed of new features and fixes.

## How It Works

```
  New version released by Admin
       │
       ▼
  Notification appears on next login
  (priority-based: MAJOR or MINOR)
       │
       ▼
  User sees banner/modal with release notes
       │
       ▼
  User acknowledges → notification cleared
```

## Priority Levels

| Priority | Behaviour |
|----------|-----------|
| **MAJOR** | Full notification shown. Up to 3 major updates shown at once. Long-gap users see latest 3. |
| **MINOR** | Shown as single "Performance improvements and bug fixes" notice if no major updates pending. |

## View All Updates

Accessible from the notification panel — shows full update history with version numbers, messages, and dates.

## Admin

Admins can create new update entries at `/admin/create-update` with version string, message, and priority.

---

# 19. COMPLETE DATA FLOW (End-to-End)

See Section 11 for the full pipeline diagram.

---

# 20. KEY METRICS AT A GLANCE

| Metric | Value |
|--------|-------|
| RSS Sources | 72 active feeds |
| AI Classification Steps | 10-step military intelligence prompt |
| Threat Categories | 19 multi-label tags |
| NER States Monitored | 8 (all NER states) |
| Countries Monitored | India, Bangladesh, Myanmar + China/Pakistan signals |
| Keyword Bank | 300+ dynamic keywords (AI + manual) |
| Fusion Detection Methods | 6 algorithms |
| Special Flags | 5 (PLA/Pak, Narratives, Demographics, Dual-Use, Patterns) |
| Feed Refresh | Every 30-60 minutes |
| Daily Brief Generation | 06:00 IST automatic |
| Analyst Rating Scale | 1-6 (Irrelevant → Extremely Relevant) |
| Feedback Bias Influence | Configurable: 10-40% weight |
| User Roles | 3 (Admin, Analyst, Viewer) |
| Authentication | JWT Bearer Token |
| Faultlines | 40 active (NER + BD + MM) |
| PAOIs | Designated high-watch faultlines (BD border + Myanmar) |
| Monthly Brief Tabs | 6 (Overview, States, Cross-Border, Faultlines, PAOI, Playbook) |
| Trends Time Ranges | 5 (24h / 7d / 30d / 90d / 365d) |
| Social Platforms | 4 (X, YouTube, Facebook, Telegram) |

---

```
╔══════════════════════════════════════════════════════════════════════╗
║  RHINO DRISHTI v10.0 | RESTRICTED | FOR AUTHORIZED PERSONNEL ONLY  ║
║  NER Intelligence Platform | Feedback-Driven AI | June 2026        ║
╚══════════════════════════════════════════════════════════════════════╝
```
