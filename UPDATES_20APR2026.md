# Rhino Drishti — Updates Log (20 April 2026)

## Summary
Seven features and fixes shipped today across the Manual Intelligence Uploads page, Keyword Engine, Settings, Daily Brief PDF, and AI Pipeline.

---

## 1. Manual Intelligence Uploads — Add to Feed

**Page renamed** from "Upload Documents" to **"Manual Int Uploads"** in the sidebar.

**New workflow — Add to Feed (Direct):**
When pasting a URL in the Analyze URL tab, you now have two action buttons side by side:
- **Analyze** — runs AI contextual threat assessment (existing)
- **Add to Feed** — adds the article directly to the Intelligence Feed with custom parameters (new)

Clicking **Add to Feed** expands an inline form with:
| Field | Options |
|-------|---------|
| Title | Auto-scraped from URL, or enter manually |
| Severity | Critical / High / Medium / Low |
| Priority Score | 0–100 slider |
| Threat Category | 18 categories (Military Movement, Insurgency, Arms Smuggling, etc.) |
| Region / State | 13 options (all NER states + Bangladesh, Myanmar, India, etc.) |
| Summary | Free-text intelligence summary |
| Cross-Border | Checkbox |

Articles added this way appear immediately in the Intelligence Feed and Dashboard with source labeled **"Manual Upload"**.

**Add to Feed after Analysis:**
Each analyzed URL card now shows a green **"Add to Feed"** button. Clicking it opens a modal pre-filled with the AI's classification (severity, threat category, region, summary). You can review and adjust before confirming.

**Best-effort scraping:** If a website blocks scraping (403/paywall), the article is still added using the title and summary you provide.

**Duplicate detection:** If the same URL already exists in the feed, you'll get a "This URL already exists" error.

---

## 2. Keyword Selection from Analysis Results

When expanding an analysis card, the **Key Entities** section (actors, locations, events) now has **clickable badges**. 

**How it works:**
1. Click any entity badge to select it — it highlights with a colored ring
2. Select as many as you want
3. A bar appears: **"3 selected → + ADD TO KEYWORD BANK"**
4. Click to add all selected keywords to the Keyword Engine

**Processing:**
- Parenthetical descriptions are auto-stripped ("Assam Rifles (paramilitary)" → "Assam Rifles")
- Actors → `entity` type, Locations → `geo` type, Events → `primary` type
- All added at score 70 (High)
- Duplicates are silently skipped

---

## 3. Keyword Badge Hover/Selection Colors Fixed

Selected and hovered keyword badges previously turned bright green, masking text. Now each badge stays in its original color family:
- **Actors** (red): subtle red highlight on select, slight red deepening on hover
- **Locations** (blue): subtle blue highlight on select, slight blue deepening on hover
- **Events** (amber): subtle amber highlight on select, slight amber deepening on hover

---

## 4. Select File Button Fix

The **Select File** button on the Upload File tab was not opening the file dialog. Fixed — it now correctly triggers the native file chooser.

---

## 5. Analysis Card Render Fix

Expanding analysis cards crashed with **"Objects are not valid as a React child"** when the AI returned `cross_references` as an object (with keys like `primary_connection`, `secondary_connection`) instead of a string. Fixed with type-checking — objects are now rendered as labeled key-value pairs. Same safety applied to `intelligence_gaps`.

---

## 6. Daily Brief — National News Filter Fix

The deployed app was showing irrelevant national news in the Daily Brief PDF (cruise ships, volcanoes, Pulp Fiction, etc.).

**Fixes applied:**
- **Dynamic source list:** Replaced hardcoded 7 sources with all 22 national + government sources from `RSS_SOURCES`
- **Strict filtering:** Requires `processed: True`, `is_relevant: True`, severity in critical/high/medium
- **Noise keyword blocklist:** Added 40+ exclusion keywords (sports, entertainment, lifestyle, etc.)
- **Raised priority threshold:** From 25 to 40 (or must have security-related tags)

---

## 7. User Handbook Updated to v9.1

- Section 13 rewritten as "Manual Intelligence Uploads" with all 3 workflows documented
- Section 11 updated with Manual Keyword Addition documentation
- New "Adding Keywords from Analysis Results" subsection in Section 13
- Updated Key Entities description in analysis output table
- Sidebar references, permissions table updated throughout

---

## Files Changed Today

| File | Change |
|------|--------|
| `frontend/src/pages/DocumentUpload.js` | Rewritten — Add to Feed workflow, keyword selection, file button fix, render fix |
| `frontend/src/components/Layout.js` | Sidebar label: "Upload Documents" → "Manual Int Uploads" |
| `backend/routers/documents.py` | New `POST /api/add-to-feed` endpoint |
| `backend/routers/briefs.py` | National news filter overhaul |
| `USER_HANDBOOK.md` | Updated to v9.1 |
| `UPDATES_20APR2026.md` | This file |
