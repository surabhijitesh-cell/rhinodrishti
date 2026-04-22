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
║                                       v9.2 | April 2026                                  ║
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
│   (Future: X, IG) ─┘    ENGINE        (Claude AI)      (MongoDB)       │
│                                            │                            │
│                                            ▼                            │
│                    ┌──────────────────────────────────────┐              │
│                    │        OUTPUT LAYER                   │              │
│                    │  Dashboard | Feed | Briefs | Alerts  │              │
│                    │  Cross-Border | Patterns | Keywords  │              │
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
│  Section 8: UPLOADED DOCUMENT INSIGHTS            │
│  ─────────────────────────────────               │
│  Summaries of manually analyzed docs (24hr)      │
│                                                  │
│  DISTRIBUTION: RESTRICTED                        │
│  FOR AUTHORIZED PERSONNEL ONLY                   │
└─────────────────────────────────────────────────┘
```

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

---

# 10. ROLE-BASED ACCESS CONTROL (RBAC)

```
  ┌──────────┬────────────────────────────────────────────┐
  │  ADMIN   │  Full access. User management. Settings.   │
  │          │  All actions enabled. Auto-seeded on        │
  │          │  first deployment.                          │
  ├──────────┼────────────────────────────────────────────┤
  │  ANALYST │  All intelligence features. Cannot access   │
  │          │  User Management or Settings. Full feed,    │
  │          │  training, upload, rating capabilities.     │
  ├──────────┼────────────────────────────────────────────┤
  │  VIEWER  │  Read-only. Can view all intelligence,      │
  │          │  dashboards, download PDFs. All action      │
  │          │  buttons disabled. No Settings menu.        │
  └──────────┴────────────────────────────────────────────┘
```

---

# 11. COMPLETE DATA FLOW (End-to-End)

```
RSS (72 sources) ──────────────────┐
Manual URLs ───────────────────────┤
Uploaded Documents ────────────────┤
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
         DAILY BRIEF     SEMANTIC SEARCH      ALERTS
         (PDF @ 0600)    (vector-powered)     (critical/high)
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

# 13. KEY METRICS AT A GLANCE

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

---

```
╔══════════════════════════════════════════════════════════════════════╗
║  RHINO DRISHTI v9.2 | RESTRICTED | FOR AUTHORIZED PERSONNEL ONLY  ║
║  NER Intelligence Platform | Feedback-Driven AI | April 2026       ║
╚══════════════════════════════════════════════════════════════════════╝
```
