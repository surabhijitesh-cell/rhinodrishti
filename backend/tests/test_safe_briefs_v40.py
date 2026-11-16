"""v40 — briefs are never lost on Regenerate, gaps are never silent, and the
Daily Brief header covers the brief's own day. No DB or LLM (fake collection)."""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import brief_monthly as bm  # noqa: E402
from routers.briefs import _brief_day_window  # noqa: E402


class FakeCollection:
    """One stored document; just enough of the driver for these helpers."""

    def __init__(self, doc=None):
        self.doc = doc

    async def find_one(self, flt, projection=None):
        return dict(self.doc) if self.doc else None

    async def update_one(self, flt, update, upsert=False):
        self.doc = dict(self.doc or {})
        self.doc.update(update.get("$set", {}))
        for field in update.get("$unset", {}):
            self.doc.pop(field, None)


def _iso(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_regenerate_keeps_the_stored_brief_while_running():
    col = FakeCollection({"status": "ready", "executive_summary": "old text", "generation_count": 2})
    assert asyncio.run(bm._begin_generation(col, {}, {"iod": "IOD-1"})) is True
    assert col.doc["status"] == "generating"
    assert col.doc["executive_summary"] == "old text"
    assert col.doc["generation_count"] == 2


def test_failed_regeneration_brings_the_previous_brief_back():
    col = FakeCollection({"status": "ready", "executive_summary": "old text"})
    asyncio.run(bm._begin_generation(col, {}, {}))
    asyncio.run(bm._fail_generation(col, {}, "model unavailable"))
    assert col.doc["status"] == "ready"
    assert col.doc["executive_summary"] == "old text"
    assert col.doc["last_generation_error"] == "model unavailable"


def test_failed_first_generation_shows_an_error_not_endless_generating():
    col = FakeCollection()
    asyncio.run(bm._begin_generation(col, {}, {}))
    asyncio.run(bm._fail_generation(col, {}, "boom"))
    assert col.doc["status"] == "error" and col.doc["error"] == "boom"


def test_second_press_does_not_start_a_second_run():
    col = FakeCollection({"status": "generating", "started_at": _iso(2), "previous_status": "ready"})
    assert asyncio.run(bm._begin_generation(col, {}, {})) is False


def test_run_killed_by_a_restart_is_settled_when_the_brief_is_opened():
    col = FakeCollection({"status": "generating", "started_at": _iso(90), "previous_status": "ready", "stats": {}})
    brief = asyncio.run(bm._settle_if_interrupted(col, {}, dict(col.doc)))
    assert brief["status"] == "ready"
    assert "interrupted" in brief["last_generation_error"]


def test_a_run_still_in_progress_is_left_alone():
    doc = {"status": "generating", "started_at": _iso(3), "previous_status": "ready"}
    assert asyncio.run(bm._settle_if_interrupted(FakeCollection(doc), {}, dict(doc)))["status"] == "generating"


def test_period_with_no_items_is_settled_as_empty():
    col = FakeCollection()
    asyncio.run(bm._begin_generation(col, {}, {}))
    asyncio.run(bm._finish_generation(col, {}, {"status": "empty", "error": "No intelligence items found"}))
    assert col.doc["status"] == "empty"


def _brief(**overrides):
    brief = {
        "executive_summary": "text",
        "stats": {
            "states": {"Assam": {"total": 9}, "Manipur": {"total": 5}, "Sikkim": {"total": 0}},
            "stability": [{"state": "Assam", "level": "ELEVATED"}, {"state": "Manipur", "level": "STABLE"}],
        },
        "state_sections": {"Assam": {"x": 1}, "Manipur": {"x": 1}},
        "mitigation_playbook": {"Assam": {"x": 1}},
        "cross_border_analysis": {"x": 1},
        "scenarios": [{"x": 1}],
        "paoi_analysis": {"available": True, "paois": [{"id": "P1", "name": "Border"}],
                          "synthesis": {"per_paoi": {"P1": {}}}},
    }
    brief.update(overrides)
    return brief


def test_complete_brief_reports_nothing_missing():
    assert bm._infer_missing_sections(_brief()) == []


def test_every_dropped_section_is_named():
    missing = bm._infer_missing_sections(_brief(
        state_sections={"Assam": {"x": 1}}, mitigation_playbook={}, cross_border_analysis={}, scenarios=[],
        paoi_analysis={"available": True, "paois": [{"id": "P1", "name": "Border"}], "synthesis": {"per_paoi": {}}},
    ))
    assert missing == [
        "State assessment: Manipur", "Mitigation playbook: Assam", "Cross-border analysis",
        "Scenarios", "Priority Area analysis: Border",
    ]


def test_pdf_shows_the_incomplete_note_on_page_one():
    import fitz
    pdf = bm._render_pdf({**_brief(), "year": 2026, "month": 10, "status": "ready",
                          "missing_sections": ["Cross-border analysis"]})
    assert "INCOMPLETE BRIEF" in fitz.open(stream=pdf, filetype="pdf")[0].get_text()


def test_daily_brief_header_covers_the_24_hours_before_generation():
    start, end = _brief_day_window({"generated_at": "2026-11-16T00:30:00+00:00"}, "2026-11-16")
    assert (start, end) == ("2026-11-15T00:30:00+00:00", "2026-11-16T00:30:00+00:00")
