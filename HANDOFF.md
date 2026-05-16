# Handoff — feature/multi-stage-filter — 2026-05-16

## What We Were Doing

Building the Intelligence Relationship Map for Rhino Drishti — a NER military
intelligence platform. Phase 1 (named militant group extraction + KG alias
normalization) just shipped. Phase 2 (cascade/snowball incident pattern detection)
is the immediate next task.

## Work Completed This Session

- **Phase 3 map**: Relationship polylines on NERMap (LINKS toggle, 6 line types,
  animated popup with AI explanation, filter panel with per-type checkboxes)
- **Phase 1 patterns**: Stage 2 prompt upgraded to extract exact militant group names
  (ULFA-I, NSCN-IM, Arambai Tenggol etc.); 80+ alias variants → canonical names in
  `knowledge_graph.py`; `entities.militant_groups` new field in AI output
- **Map defaults fixed**: `same_pattern` disabled by default (too noisy); `same_actor`
  enabled (now produces edges after KG rebuild)
- **Compact map timeline**: `windowStateStats` prop was missing from compact NERMap —
  border colours now update on slider scrub in both compact and fullscreen views
- **LINKS button position**: Shifted from `top:48` to `top:90` — no longer hidden
  behind Leaflet zoom controls
- **FEATURE_SUMMARY.md**: Complete 868-line master feature reference (v10.0) covering
  all 22 feature areas — for handbook generation
- **Relationship batch verified**: After KG rebuild, `same_actor: 3` edges confirmed
  (was 0 before Phase 1 fix); semantic: 1640 edges still in DB; total: 82,836 edges

## Current State

**Working:**
- Relationship engine: 82,836 total edges in `item_relationships` collection
- LINKS layer on NERMap: amber (same_actor), orange (same_incident), cyan
  (same_hotspot), purple (semantic), lime (user_drawn) — all drawing correctly
- Timeline slider in both compact and fullscreen map updates border colours
- Stage 2 prompt now extracts named militant groups into `entities.militant_groups`

**Pending / low numbers:**
- `same_actor: 3` — low because existing ~3,000 items were classified before the
  prompt fix. Numbers grow naturally as new articles arrive. Do NOT re-classify old
  items unless user requests it (expensive).
- `same_hotspot: 0` — KG edges collection may be sparse; will improve with more data
- Phase 2 (cascade detection) not yet built

**Branch:** `feature/multi-stage-filter` on `surabhijitesh-cell/rhinodrishti`
**Deployed:** Render (backend) + Vercel (frontend)
**Render URL:** `https://rhino-drishti-api.onrender.com`
**Vercel URL:** `https://rhinodrishti.vercel.app`

## Immediately Next Steps

1. **Build Phase 2 — Cascade Incident Pattern Detection**
   - New relationship type: `cascade_incident` (directed, orange arrows on map)
   - Two-pass detection:
     - Pass A (AI-assisted): Stage 2 already has `threat_trajectory: ESCALATING` —
       use this + same state + 14-day window to find escalating chains
     - Pass B (temporal proximity): same state, same/adjacent threat category,
       within 14 days, priority score escalates (e.g. 45→65→82)
   - Add `cascade_incident` to `relationship_engine.py` as Pass 6
   - Add `cascade_incident` to `REL_STYLE` in `NERMap.js` (orange solid, directed arrow)
   - Add `cascade_incident` to default-enabled types in `relTypes` state

2. **Animated line drawing** (discussed but not yet built)
   - SVG `stroke-dashoffset` animation when user clicks a pattern type
   - Sequential reveal: same_actor = chronological, cascade = depth-first from root
   - 120–200ms stagger between lines per type

3. **KG "View on Map" button** (Phase 3B from plan)
   - When KG actor card has ≥2 articles → show "📍 View on Map" button
   - Click → map zooms to actor's locations, timeline sets to actor's date range
   - Filters LINKS to only that actor's edges

4. **Run nightly batch after next deploy** to pick up any newly classified items
   with named militant groups

## Key Files Touched

| File | Change |
|------|--------|
| `backend/ai_pipeline.py` | Step 4: exact militant group name requirement; Step 5: `militant_groups` entity; JSON schema updated |
| `backend/knowledge_graph.py` | `MILITANT_ALIASES` dict (80+ entries); `normalize_actor()` rebuilt on alias table; KG build loop merges `entities.militant_groups` |
| `backend/relationship_engine.py` | 5-pass batch engine (same_incident, same_actor, same_hotspot, same_pattern, semantic) — Phase 2 cascade pass NOT YET ADDED |
| `backend/routers/relationships.py` | Full REST API: GET/POST/PATCH edges, GET stats, GET explain, POST compute |
| `backend/shared.py` | Added `relationships_col = db.item_relationships` |
| `backend/server.py` | Relationships router mounted; nightly batch at 21:30 UTC (03:00 IST) |
| `frontend/src/components/NERMap.js` | Phase 3 relationship polylines; LINKS toggle; filter panel; animation hooks; `same_pattern` default off; LINKS button position fix |
| `frontend/src/pages/Dashboard.js` | `windowStateStats` added to compact NERMap; `api` prop added to both NERMap instances |
| `FEATURE_SUMMARY.md` | New — 868-line complete feature reference v10.0 |

## Commands to Know

**Trigger relationship batch manually** (run from `rhinodrishti.vercel.app` console tab):
```javascript
fetch("https://rhino-drishti-api.onrender.com/api/admin/relationships/compute?rebuild_kg=true", {
  method: "POST",
  headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
}).then(r => r.json()).then(console.log)
```
Takes ~9 min. Watch for `same_actor` count in result.

**Check relationship stats:**
```javascript
fetch("https://rhino-drishti-api.onrender.com/api/relationships/stats",{
  headers:{"Authorization":"Bearer "+localStorage.getItem("token")}
}).then(r=>r.json()).then(console.log)
```

**Wake Render** (free tier sleeps after 15 min idle):
Open `https://rhino-drishti-api.onrender.com/api/` in browser, wait for JSON response.

## Open Questions / Decisions Pending

- **Animated line drawing**: Design is agreed (SVG stroke-dashoffset, staggered by type).
  Not yet implemented. Build after cascade detection or alongside it.
- **BERTopic semantic clustering** (Phase 4): Needs `bertopic` + `umap-learn` + `hdbscan`
  added to `requirements.txt`. Discussed but not started.
- **Smuggling route detection** (Phase 5): DBSCAN spatial clustering on border items.
  Not started.
- **`same_actor` growth**: Will naturally increase as new articles are classified with
  the fixed prompt. No action needed unless user wants to force re-classify old items.
- **Cascade detection root identification**: Need to decide how to mark the "root"
  incident in a cascade chain (earliest item in cluster, or highest priority_score?).
  Recommendation: earliest `published_at` in the geographic+temporal cluster.

## Optional Note from Outgoing Session

"starting Phase 2 cascade patterns next"
