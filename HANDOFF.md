# Handoff — feature/multi-stage-filter — 2026-05-17

## What We Were Doing

Building the Intelligence Relationship Map for Rhino Drishti — a NER military
intelligence platform. Phase 1 (named militant group extraction + KG alias
normalization) shipped last session. Phase 2 (cascade/snowball incident pattern
detection) shipped this session. Phase 3B (KG "View on Map" button) is next.

## Work Completed This Session

- **Phase 2 — cascade_incident**: Pass 6 added to `relationship_engine.py`
  - Pass A: both items `threat_trajectory=ESCALATING`, same state, ≤14 days → strength 0.70–0.92
  - Pass B: same state + same `threat_category`, `priority_score` rises ≥15, ≤14 days → strength 0.50–0.90
  - `cascade_root_id` stored in meta to preserve true directionality through canonical pair key
  - `cascade_pass` ("A"/"B") and `score_delta` also stored for audit/display
  - `get_edges_for_items` projection updated to return these meta fields
- **NERMap.js**: `cascade_incident` added
  - `REL_STYLE`: deep-orange `#ea580c`, dashed `8 3`, weight 2.5, opacity 0.88, label "Cascade ↑"
  - `relTypes` default: **enabled** (unlike same_pattern/semantic which are off)
  - Popup: shows ⬆/🔺 icons with `+{score_delta} priority · Pass {A|B}` line
  - Uses `cascade_root_id` to correctly identify root vs peak item in the popup

## Current State

**Working:**
- Relationship engine: 6 passes (same_incident, same_actor, same_hotspot, same_pattern, semantic, cascade_incident)
- cascade_incident edges will be computed on next nightly batch or manual trigger
- NERMap shows cascade edges as deep-orange dashed lines, enabled by default, correct direction in popup

**Pending / low numbers:**
- `cascade_incident: 0` until next batch runs — trigger manually if needed (see Commands)
- `same_actor: 3` — grows naturally as new articles arrive with fixed prompt
- Animated line drawing (SVG stroke-dashoffset) — discussed but not built
- KG "View on Map" button (Phase 3B) — not yet built

**Branch:** `feature/multi-stage-filter` on `surabhijitesh-cell/rhinodrishti`
**Deployed:** Render (backend) + Vercel (frontend)
**Render URL:** `https://rhino-drishti-api.onrender.com`
**Vercel URL:** `https://rhinodrishti.vercel.app`

## Immediately Next Steps

1. **KG "View on Map" button** (Phase 3B)
   - When KG actor card has ≥2 articles → show "📍 View on Map" button
   - Click → map zooms to actor's locations, timeline sets to actor's date range
   - Filters LINKS to only that actor's edges
   - Likely involves: KG panel component sending a prop/event to the parent Dashboard,
     which passes it down to NERMap as `focusActorId` or similar

2. **Animated line drawing** (discussed but not yet built)
   - SVG `stroke-dashoffset` animation when user clicks a pattern type
   - Sequential reveal: same_actor = chronological, cascade = depth-first from root
   - 120–200ms stagger between lines per type

3. **Run nightly batch after next deploy** to pick up cascade_incident edges
   - Trigger manually with the fetch snippet below

4. **BERTopic semantic clustering** (Phase 4): requires bertopic + umap-learn + hdbscan
   - Not started; needs dependency additions in requirements.txt

## Key Files Touched

| File | Change |
|------|--------|
| `backend/ai_pipeline.py` | Step 4: exact militant group name requirement; Step 5: `militant_groups` entity; JSON schema updated |
| `backend/knowledge_graph.py` | `MILITANT_ALIASES` dict (80+ entries); `normalize_actor()` rebuilt on alias table; KG build loop merges `entities.militant_groups` |
| `backend/relationship_engine.py` | 6-pass batch engine; Pass 6 = cascade_incident (two-pass A/B); projection includes cascade_root_id |
| `backend/routers/relationships.py` | Full REST API: GET/POST/PATCH edges, GET stats, GET explain, POST compute |
| `backend/shared.py` | Added `relationships_col = db.item_relationships` |
| `backend/server.py` | Relationships router mounted; nightly batch at 21:30 UTC (03:00 IST) |
| `frontend/src/components/NERMap.js` | Phase 3 relationship polylines; LINKS toggle; filter panel; cascade_incident style + default; cascade direction in popup |
| `frontend/src/pages/Dashboard.js` | `windowStateStats` added to compact NERMap; `api` prop added to both NERMap instances |
| `FEATURE_SUMMARY.md` | 868-line complete feature reference v10.0 |

## Commands to Know

**Trigger relationship batch manually** (run from `rhinodrishti.vercel.app` console tab):
```javascript
fetch("https://rhino-drishti-api.onrender.com/api/admin/relationships/compute?rebuild_kg=true", {
  method: "POST",
  headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
}).then(r => r.json()).then(console.log)
```
Takes ~9 min. After it completes, check `cascade_incident` count in the result.

**Check relationship stats:**
```javascript
fetch("https://rhino-drishti-api.onrender.com/api/relationships/stats",{
  headers:{"Authorization":"Bearer "+localStorage.getItem("token")}
}).then(r=>r.json()).then(console.log)
```

**Wake Render** (free tier sleeps after 15 min idle):
Open `https://rhino-drishti-api.onrender.com/api/` in browser, wait for JSON response.

## Open Questions / Decisions Pending

- **Cascade detection root identification**: Currently earliest `published_at` in the
  state+category cluster is the root. Alternative: highest priority_score item as root.
  Current approach is more intuitive (chronological causation).
- **Adjacent threat categories** (Pass B improvement): Currently requires exact category
  match. A category adjacency map (e.g. Insurgency ↔ Arms Trafficking) would catch more
  chains. Deferred until real cascade edge counts are known.
- **Animated line drawing**: Design agreed (SVG stroke-dashoffset, staggered by type).
  Not implemented. Build after Phase 3B or alongside it.
- **BERTopic semantic clustering** (Phase 4): Needs deps added. Discussed but not started.
- **Smuggling route detection** (Phase 5): DBSCAN spatial clustering on border items.
  Not started.

## Optional Note from Outgoing Session

Phase 2 cascade_incident complete. Next: Phase 3B KG "View on Map" button.
