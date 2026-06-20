# Handoff — feature/notifications-and-flagging — 2026-06-19

## What We Were Doing
Completed the `feature/notifications-and-flagging` branch with push notifications, red-flag flagging indicator, faultline time-decay scoring, and PAOI monitoring. Updated USER_HANDBOOK.md to v12.0 and generated a 27-slide PPTX presentation explaining the full application. Also raised the keyword fetch limit from 300 to 500.

## Work Completed This Session
- `acf8410` docs: update handbook to v12.0 + increase keyword fetch limit to 500
- `0f0fcfa` fix(notifications): fire push when active subscription exists regardless of pref
- `91e4eaa` feat(flagging): red flag icon for previously flagged articles
- `f0116c6` fix(flagging): portal modal to document.body to fix z-index clipping
- `ff78656` feat(notifications): test-push endpoint + background push UX improvements
- `9136e9b` feat(faultlines): time-decay scoring + newest-articles-first display
- `62eb4fa` feat(notifications): auto push permission prompt on app launch
- Handbook updated from v11.0 → v12.0 (new sections: Push Notifications, Faultline Intelligence/PAOI, Flagging, time-decay scoring, monthly report)
- PPT generated: `RhinoDrishti_Command_Intelligence_v2.pptx` (27 slides, 10 embedded screenshots)
- Keyword fetch limit raised: `frontend/src/pages/KeywordEngine.js` line 42 → `limit=500`

## Current State
- Branch `feature/notifications-and-flagging` is fully up to date with remote, all changes pushed
- All features on this branch are working: push notifications (Android background + iOS PWA), red flag icon, faultline time-decay scoring, PAOI manager, monthly faultline PDF report
- Keyword backend already had `MAX_KEYWORDS = 500` in `backend/keyword_engine.py`; frontend now matches
- PPT file is untracked at `RhinoDrishti_Command_Intelligence_v2.pptx` (2.9 MB) — not committed to git (large binary)
- `write_handbook.py` temp script is untracked at project root — safe to delete

## Immediately Next Steps
1. **Merge or PR** — `feature/notifications-and-flagging` is complete; consider merging to `main`
2. **Faultline prioritisation feature** — user asked: "add a feature in the faultlines page where I can add a new faultline or prioritise my faultlines of interest from the existing ones — allow me to rate 10 faultlines" — queued but NOT yet implemented; this is the next feature
3. **Delete temp files** — `write_handbook.py` can be deleted; it was a workaround for a context-compaction issue during handbook update
4. **Verify keyword limit** — confirm 500-limit working correctly on Keyword Engine page in browser
5. **Next branch** — create `feature/faultline-prioritisation` for the watchlist/ranking feature

## Key Files Touched
- `USER_HANDBOOK.md` — rewritten to v12.0; 5 new sections (15.1 Push Notifications, 16 Faultline Intelligence, 16.1 PAOI, 16.2 Faultline Cards, 16.3 Scoring, 16.4 Monthly Report, 17 Flagging)
- `frontend/src/pages/KeywordEngine.js` — line 42: `limit=300` → `limit=500`
- `RhinoDrishti_Command_Intelligence_v2.pptx` — new 27-slide PPTX (untracked, stays local)
- `build_rhino_ppt.js` — Node.js pptxgenjs script used to generate the PPTX (untracked)

## Commands to Know
- Start dev: `cd frontend && npm start` (or use `start-dev.bat`)
- Backend: `cd backend && uvicorn server:app --reload --port 8000`
- Regenerate PPT: `node build_rhino_ppt.js` (requires `npm install pptxgenjs` if not installed)
- Push notifications test: `POST /api/test-push` with auth header
- Faultline scoring manual trigger: `POST /api/faultlines/trigger-daily-pass` with auth header
- Keyword limit is now 500: `GET /api/keywords?limit=500`

## Open Questions / Decisions Pending
- Should `feature/notifications-and-flagging` be merged to `main` now? All features are stable.
- Faultline prioritisation feature (rate/rank up to 10 faultlines from the Faultlines page) — was queued but not started. Needs a new branch.
- Should the PPTX files be committed to git or kept local only? They are large binaries (~3 MB each).
- `write_handbook.py` — delete or keep as utility for future handbook updates?

## Optional Note from Outgoing Session
None
