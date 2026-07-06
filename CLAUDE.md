# RhinoDrishti — NER Intelligence Platform

Army-context OSINT platform for India's North East Region: scrapes news and
social sources, classifies items with an LLM, tracks faultlines and Priority
Areas of Interest (PAOIs), and generates commander briefs (daily, fortnightly,
monthly PDFs) plus an admin-only chat-driven Custom Brief Generator.

## Stack & running it
- `backend/` — FastAPI + MongoDB Atlas (motor). Deployed on Render (Python 3.11).
- `frontend/` — React (CRA + craco), Radix UI, Tailwind, Leaflet, recharts.
  Deployed on Vercel.
- LLM calls via OpenRouter (`backend/llm_client.py`).
- Local dev: `start-dev.bat` (backend :8001, frontend :3000). Windows machine;
  local Python is 3.14 vs 3.11 on Render.

## Deployment rules (critical)
- Vercel and Render deploy from the CURRENT FEATURE BRANCH — never from main.
  Never merge to main.
- Therefore every `git push` is a production deploy: push only working states.
  Auto-push after each commit is approved and expected.
- Backend changes take effect only after Render redeploys — remind Rohit of
  this when he reports "no change" right after a push.

## Live data & credentials
- The Atlas DB in `backend/.env` IS production; there is no test/staging DB.
  Read freely; any write/modify/delete needs Rohit's approval first.
- `OPENROUTER_API_KEY` is deliberately NOT set locally: LLM calls fail on this
  machine, Mongo works. Test LLM features via deploy or stored outputs.
- Regenerating briefs spends OpenRouter credits — over ~$2 estimated, ask first.

## Verification (overrides the global testing rules)
- Proof here = rendered PDF pages / running-app screenshots against real data,
  plus targeted pytest for pure logic. The 80%-coverage/TDD mandate does not
  apply in this project.
- Any PDF change: render the PDF locally (PyMuPDF `fitz` → PNG; pdftoppm is not
  installed) and inspect every affected page BEFORE presenting. Bad PDF
  formatting is Rohit's #1 recurring complaint.
- Downloaded PDFs re-render server-side from stored JSON: formatting fixes
  reach old briefs after redeploy; only content changes need regeneration.

## Project memory
- Read `memory/PROJECT_HISTORY.md` at session start; append a dated 2–3 line
  entry after each completed feature/fix. Static profile facts (URLs, repo,
  module map) live in `memory/projects/rhinodrishti.md`.

## Key modules & gotchas
- `backend/routers/brief_monthly.py` holds the monthly generator AND the shared
  PDF renderer; `brief_fortnightly.py` imports from it — change shared code once.
- `backend/routers/report_agent.py` (Custom Brief Generator) is the REFERENCE
  format periodic briefs copy from — never modify it to fix a periodic-brief
  problem.
- `backend/priority_areas_seed.py` seeds the PAOI registry at startup
  (idempotent). PAOI ids are stable identifiers used in prompts and frontend —
  never rename one (e.g. `P5_meghalaya_tribal_dynamics` stays despite rank 6).
- `frontend/src/components/NERMap.js` is the visual style reference for maps
  rendered into PDFs.
