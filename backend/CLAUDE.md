# backend/ — technical gotchas

- fpdf2: `multi_cell` leaves x at the right margin — call
  `pdf.set_x(pdf.l_margin)` before consecutive multi_cells or the next one
  crashes with "Not enough horizontal space". `markdown=True` renders **bold**.
- LLM JSON must go through the existing `_coerce_json`-style helpers — raw
  `json.loads` on model output has silently emptied whole brief sections when
  responses were truncated.
- OpenRouter throttles bursts: make LLM calls sequentially with a short sleep
  (see `run_paoi_synthesis`), never `asyncio.gather` many at once.
- Tests: `cd backend && python -m pytest tests/`. Only pure-function tests run
  offline (motor connects lazily; LLM calls raise without a key). Follow the
  style of `tests/test_periodic_report_v36.py` — version-numbered, no DB/LLM.
- matplotlib is broken locally (Python 3.14 ft2font DLL failure) — use Pillow
  for any image/chart rasterization.
