"""
test_periodic_ranges_v46.py — IST period dates through the periodic briefs,
fortnight faultline section, shared-core metadata, and the fortnightly
Faultline Report (IOD limiting + previous fortnight).

Pure logic with fake collections — no database, no AI calls.

Run:  cd backend && PYTHONUTF8=1 python -m pytest tests/test_periodic_ranges_v46.py -q
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import faultline_pdf
import paoi_brief
from routers import brief_monthly as bm
from routers import brief_fortnightly as bf


# ── Tiny fake Mongo ──────────────────────────────────────────────────────────

def _ok(row: dict, query: dict) -> bool:
    for key, cond in query.items():
        if key == "$or":
            if not any(_ok(row, c) for c in cond):
                return False
            continue
        val = row.get(key)
        if isinstance(cond, dict):
            if "$gte" in cond and not (val is not None and val >= cond["$gte"]):
                return False
            if "$lte" in cond and not (val is not None and val <= cond["$lte"]):
                return False
            if "$lt" in cond and not (val is not None and val < cond["$lt"]):
                return False
            if "$in" in cond and val not in cond["$in"]:
                return False
            if "$nin" in cond and val in cond["$nin"]:
                return False
            if "$exists" in cond and (key in row) != cond["$exists"]:
                return False
        elif val != cond:
            return False
    return True


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, key, direction=None):
        keys = key if isinstance(key, list) else [(key, direction or 1)]
        for k, d in reversed(keys):
            self.rows.sort(key=lambda r: r.get(k) if r.get(k) is not None else 0, reverse=d == -1)
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    async def to_list(self, length=None):
        return self.rows[:length] if length else self.rows

    def __aiter__(self):
        async def gen():
            for r in self.rows:
                yield r
        return gen()


class _Coll:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def find(self, query=None, projection=None):
        query = query or {}
        self.queries.append(query)
        return _Cursor(r for r in self.rows if _ok(r, query))

    async def find_one(self, query=None, projection=None, **kw):
        found = [r for r in self.rows if _ok(r, query or {})]
        return found[0] if found else None


class FakeDB:
    def __init__(self, **colls):
        self._c = {k: _Coll(v) for k, v in colls.items()}

    def __getattr__(self, name):
        return self._c.setdefault(name, _Coll([]))


def _score(fl, date, score, state="Assam", name=None):
    return {"faultline_id": fl, "faultline_name": name or fl.upper(), "state": state,
            "date": date, "score": score, "level": "MONITOR"}


# ── Period dates ─────────────────────────────────────────────────────────────

def test_fortnight_dates_inclusive_across_month_ends():
    assert bf._fortnight_dates(2026, 11, 1) == ("2026-11-01", "2026-11-15")
    assert bf._fortnight_dates(2026, 11, 2) == ("2026-11-16", "2026-11-30")
    assert bf._fortnight_dates(2026, 2, 2) == ("2026-02-16", "2026-02-28")
    assert bf._fortnight_dates(2026, 12, 2) == ("2026-12-16", "2026-12-31")


def test_previous_fortnight_across_month_and_year():
    assert bf._prev_fortnight(2026, 11, 2) == {"year": 2026, "month": 11, "period": 1}
    assert bf._prev_fortnight(2026, 3, 1) == {"year": 2026, "month": 2, "period": 2}
    assert bf._prev_fortnight(2026, 1, 1) == {"year": 2025, "month": 12, "period": 2}


def test_range_wrappers_use_ist_and_exclusive_end():
    assert bm._month_range(2026, 11) == ("2026-10-31T18:30:00+00:00", "2026-11-30T18:30:00+00:00")
    assert bf._fortnightly_range(2026, 11, 2)[:2] == (
        "2026-11-15T18:30:00+00:00", "2026-11-30T18:30:00+00:00")


def test_paoi_period_uses_true_last_day_and_excludes_neighbours():
    start, end = bm._month_range(2026, 11)
    db = FakeDB(
        priority_areas=[{"id": "P1", "name": "One", "enabled": True, "iod": "IOD-1",
                         "rank": 1, "linked_faultline_ids": ["f1"]}],
        faultline_scores=[
            _score("f1", "2026-10-31", 10), _score("f1", "2026-11-01", 20),
            _score("f1", "2026-11-30", 50), _score("f1", "2026-12-01", 99),
        ],
    )
    agg = asyncio.run(paoi_brief.aggregate_paoi_period(db, start, end))
    mv = agg["paois"][0]["faultline_movement"]
    assert (mv["first"], mv["last"]) == (20.0, 50.0)
    assert agg["as_of"] == "2026-11-30"


def test_other_movements_window_matches_period_dates():
    start, end = bf._fortnightly_range(2026, 11, 1)[:2]
    db = FakeDB(
        priority_areas=[],
        faultline_scores=[
            _score("f9", "2026-10-31", 5), _score("f9", "2026-11-01", 10),
            _score("f9", "2026-11-15", 40), _score("f9", "2026-11-16", 90),
        ],
    )
    out = asyncio.run(paoi_brief.other_faultline_movements(db, start, end))
    assert [r["id"] for r in out["rising"]] == ["f9"]
    assert out["rising"][0]["delta"] == 30.0


# ── Fortnight faultline section ──────────────────────────────────────────────

def _fl_rows():
    return [
        _score("f1", "2026-11-01", 10), _score("f1", "2026-11-15", 30),
        _score("f1", "2026-11-16", 60), _score("f1", "2026-11-30", 80),
    ]


def test_faultline_section_defaults_to_whole_ist_month(monkeypatch):
    monkeypatch.setattr(bm, "db", FakeDB(faultline_scores=_fl_rows() + [_score("f1", "2026-10-31", 1)]))
    sec = asyncio.run(bm._aggregate_faultline_section(2026, 11))
    f = sec["by_state"]["Assam"][0]
    assert (f["first"], f["last"], f["days_observed"]) == (10.0, 80.0, 4)


def test_faultline_section_uses_fortnight_dates(monkeypatch):
    monkeypatch.setattr(bm, "db", FakeDB(faultline_scores=_fl_rows()))
    first, last = bf._fortnight_dates(2026, 11, 2)
    sec = asyncio.run(bm._aggregate_faultline_section(2026, 11, start_date=first, end_date=last))
    f = sec["by_state"]["Assam"][0]
    assert (f["first"], f["last"], f["days_observed"]) == (60.0, 80.0, 2)
    first, last = bf._fortnight_dates(2026, 11, 1)
    sec = asyncio.run(bm._aggregate_faultline_section(2026, 11, start_date=first, end_date=last))
    assert sec["by_state"]["Assam"][0]["last"] == 30.0


# ── Shared IOD sections ──────────────────────────────────────────────────────

def test_shared_core_meta_lists_only_copied_sections():
    core = {"generated_at": "2026-11-02T01:00:00+00:00", "status": "ready", "stats": {},
            "executive_summary": "x", "scenarios": [], "faultline_analysis": {"a": 1}}
    meta = bf._shared_core_meta(core)
    assert meta["shared_core_iod"] == "IOD-1"
    assert meta["shared_core_generated_at"] == "2026-11-02T01:00:00+00:00"
    assert meta["shared_sections"] == ["status", "stats", "executive_summary", "scenarios"]
    assert bm._shared_core_meta is bf._shared_core_meta


# ── Faultline report: windows, IOD limiting ──────────────────────────────────

def test_report_windows_month_and_fortnight():
    m = faultline_pdf.report_windows(2026, 1)
    assert m["current"] == ("2026-01-01", "2026-01-31")
    assert m["previous"] == ("2025-12-01", "2025-12-31")
    assert (m["label"], m["prev_period"]) == ("January 2026", None)
    f = faultline_pdf.report_windows(2026, 1, 1)
    assert f["current"] == ("2026-01-01", "2026-01-15")
    assert f["previous"] == ("2025-12-16", "2025-12-31")
    assert (f["label"], f["prev_label"]) == ("1-15 January 2026", "16-31 December 2025")


def _report_db():
    scores = [
        _score("f1", "2026-11-16", 40, name="F1"), _score("f1", "2026-11-30", 70, name="F1"),
        _score("f1", "2026-11-01", 20, name="F1"), _score("f1", "2026-11-15", 30, name="F1"),
        _score("f2", "2026-11-16", 10, state="Manipur", name="F2"),
        _score("f2", "2026-11-30", 90, state="Manipur", name="F2"),
    ]
    return FakeDB(
        faultline_scores=scores, priority_areas=[],
        fortnightly_briefs=[{"year": 2026, "month": 11, "period": 2, "iod": "IOD-1",
                             "generated_at": "2026-12-01T00:00:00+00:00",
                             "faultline_analysis": {"state_narratives": {}}}],
    )


def test_fortnight_report_uses_fortnight_and_previous_fortnight():
    agg = asyncio.run(faultline_pdf.aggregate_faultline_report(_report_db(), 2026, 11, period=2))
    f1 = next(f for f in agg["all_faultlines"] if f["id"] == "f1")
    assert (f1["first"], f1["last"], f1["days"]) == (40.0, 70.0, 2)
    assert f1["prev_avg"] == 25.0  # P1 of November: avg of 20 and 30
    assert f1["mom_delta"] == 30.0  # current avg 55 - previous avg 25
    assert agg["month_name"] == "16-30 November 2026"
    assert agg["prev_month_name"] == "1-15 November 2026"
    assert agg["is_fortnight"] and agg["prev_period"] == 1
    assert agg["generated_at"] == "2026-12-01T00:00:00+00:00"


def test_report_limits_to_iod_faultlines_and_keeps_monthly_content():
    db = _report_db()
    agg = asyncio.run(faultline_pdf.aggregate_faultline_report(db, 2026, 11, iod="IOD-4", fl_ids=["f2"]))
    assert [f["id"] for f in agg["all_faultlines"]] == ["f2"]
    assert agg["month_name"] == "November 2026" and not agg["is_fortnight"]
    full = asyncio.run(faultline_pdf.aggregate_faultline_report(_report_db(), 2026, 11))
    assert {f["id"] for f in full["all_faultlines"]} == {"f1", "f2"}
    assert next(f for f in full["all_faultlines"] if f["id"] == "f1")["days"] == 4


# ── AI text safety ───────────────────────────────────────────────────────────

def test_faultline_pdf_renders_with_odd_ai_values():
    agg = asyncio.run(faultline_pdf.aggregate_faultline_report(_report_db(), 2026, 11, period=2))
    agg["top_actors"] = [{"name": "Actor", "count": 2, "faultlines": ["F1"], "headline": {}}]
    synthesis = {
        "bottom_line": ["list", "value"],
        "mover_outlooks": {"f1": ["a list outlook"], "f2": {"x": "dict"}},
        "advisory": {"odd": "dict — text →"},
        "actor_profiles": {"Actor": ["profile"]},
    }
    pdf = faultline_pdf.render_faultline_pdf(agg, synthesis)
    assert pdf[:4] == b"%PDF"


def test_mitigation_and_previous_excerpt_tolerate_odd_values():
    brief = _min_monthly_brief()
    brief["mitigation_playbook"] = {
        "Assam": {"immediate": ["plain string action", {"action": "ok", "lead_agency": "Army"}],
                  "short_term": "not a list"},
        "Bad": "not a dict",
    }
    prev = _min_monthly_brief()
    prev["executive_summary"] = ["odd", "list"]
    pdf = bm._render_pdf(brief, prev_brief=prev)
    assert pdf[:4] == b"%PDF"


def _min_monthly_brief():
    return {
        "year": 2026, "month": 11, "iod": "IOD-1", "status": "ready",
        "generated_at": "2026-12-01T00:00:00+00:00",
        "stats": {"total": 1, "sev_counts": {"low": 1}, "cross_border_count": 0,
                  "states": {}, "stability": [], "top_actors": [], "top_locations": [],
                  "top_categories": [], "daily_severity": [],
                  "month_start": "2026-10-31T18:30:00+00:00",
                  "month_end": "2026-11-30T18:30:00+00:00"},
        "executive_summary": "summary", "state_sections": {}, "scenarios": [],
        "mitigation_playbook": {}, "cross_border_analysis": {},
        "faultline_analysis": {"available": False}, "paoi_analysis": {},
        "attention_required": [],
    }
