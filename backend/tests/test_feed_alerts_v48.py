"""v48 - Feed and Alerts: honest AI search, alert filters/sorting/export, admin IOD
view, new-items check. Pure logic with fakes - no database, no AI calls.

Run:  cd backend && PYTHONUTF8=1 python -m pytest tests/test_feed_alerts_v48.py -q
"""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from routers import intelligence as intel  # noqa: E402


# -- AI search -----------------------------------------------------------------

def test_semantic_search_returns_clear_error_when_query_cannot_be_embedded(monkeypatch):
    import embedding_service

    async def no_embedding(_text):
        return None

    monkeypatch.setattr(embedding_service, "generate_embedding", no_embedding)
    with pytest.raises(HTTPException) as err:
        asyncio.run(intel.intelligence_semantic_search({"query": "border infiltration"}))
    assert err.value.status_code == 503
    assert "unavailable" in err.value.detail.lower()


def test_semantic_search_rejects_short_query():
    with pytest.raises(HTTPException) as err:
        asyncio.run(intel.intelligence_semantic_search({"query": "ab"}))
    assert err.value.status_code == 400


def test_rank_semantic_orders_filters_and_hides_embeddings():
    sim = lambda q, e: e[0]  # noqa: E731 - first number stands in for the score
    items = [
        {"id": "a", "embedding": [0.4]},
        {"id": "b", "embedding": [0.9]},
        {"id": "c", "embedding": [0.1]},
        {"id": "d", "embedding": None},
    ]
    out = intel.rank_semantic([1], items, limit=5, min_score=0.25, similarity=sim)
    assert [r["id"] for r in out] == ["b", "a"]
    assert "embedding" not in out[0]
    assert intel.rank_semantic([1], items, limit=1, min_score=0.25, similarity=sim)[0]["id"] == "b"
    assert intel.rank_semantic([1], items, limit=5, min_score=0.95, similarity=sim) == []


# -- Alerts: filters, sort, export ---------------------------------------------

BASE = intel.open_alert_filter("2026-10-18T00:00:00+00:00")


def test_alert_query_keeps_the_open_alert_rules_and_adds_filters():
    q = intel.build_alert_query(BASE, state="Assam", threat_type="Insurgency", min_priority=60, search="a(b)")
    assert q["severity"] == {"$in": ["critical", "high"]}
    assert q["acknowledged"] == {"$ne": True}
    assert q["state"] == "Assam" and q["threat_category"] == "Insurgency"
    assert q["priority_score"] == {"$gte": 60}
    assert q["$or"][0]["title"]["$regex"] == r"a\(b\)"   # typed text is literal, not a pattern
    assert "state" not in BASE and "$or" not in BASE      # the shared base is not modified


def test_alert_query_without_filters_is_the_plain_open_alert_list():
    assert intel.build_alert_query(BASE) == BASE


@pytest.mark.parametrize("by,order,expected", [
    (None, "desc", ("published_at", -1)),
    ("priority_score", "desc", ("priority_score", -1)),
    ("severity", "asc", ("severity", 1)),
    ("nonsense", "desc", ("published_at", -1)),
])
def test_resolve_sort(by, order, expected):
    assert intel.resolve_sort(by, order) == expected


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *a):
        self.sorted_by = a
        return self

    def limit(self, n):
        return self

    async def to_list(self, n):
        return self.rows


class _FakeCol:
    def __init__(self):
        self.find_queries, self.count_queries, self.pipelines = [], [], []

    def find(self, q, proj=None):
        self.find_queries.append(q)
        return _Cursor([{"id": "x"}])

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return _Cursor([{"id": "y"}])

    async def count_documents(self, q):
        self.count_queries.append(q)
        return 7 if "state" in q else 9


def _run_alerts(monkeypatch, **kw):
    col = _FakeCol()

    async def cutoff():
        return "2026-10-18T00:00:00+00:00"

    monkeypatch.setattr(intel, "intelligence_col", col)
    monkeypatch.setattr(intel, "_retention_cutoff", cutoff)
    return col, asyncio.run(intel.fetch_open_alerts(200, **kw))


def test_alert_list_applies_filters_and_reports_both_counts(monkeypatch):
    col, out = _run_alerts(monkeypatch, state="Assam", sort_by="priority_score")
    assert col.find_queries[0]["state"] == "Assam"
    assert out["alerts"] == [{"id": "x"}]
    assert out["matched"] == 7 and out["count"] == 9


def test_alert_list_severity_sort_uses_ranked_pipeline(monkeypatch):
    col, out = _run_alerts(monkeypatch, sort_by="severity")
    assert col.pipelines and out["alerts"] == [{"id": "y"}]


def test_alert_export_uses_same_list_as_the_page(monkeypatch):
    from routers import reports
    col, _ = _run_alerts(monkeypatch)
    captured = {}

    async def fake_fetch(limit, *args, **kw):
        captured.update(limit=limit, args=args, kw=kw)
        return {"alerts": [], "matched": 0, "count": 0}

    monkeypatch.setattr(intel, "fetch_open_alerts", fake_fetch)
    with pytest.raises(HTTPException) as err:
        asyncio.run(reports.filtered_feed_pdf(
            state="Assam", min_priority=60, sort_by="priority_score", sort_order="desc",
            alerts_only=True, iod=None, user={"role": "analyst", "iod": "IOD-1"},
        ))
    assert err.value.status_code == 404                      # nothing to export -> clear message
    assert captured["args"][0] == "Assam" and captured["args"][3] == 60
    assert captured["kw"]["iod_faultline_ids"] is None       # IOD-1 sees everything


# -- Admin IOD view -------------------------------------------------------------

def test_admin_can_view_another_iod():
    assert intel.effective_iod({"role": "admin", "iod": "IOD-1"}, "IOD-4") == "IOD-4"


def test_non_admin_override_is_ignored():
    assert intel.effective_iod({"role": "analyst", "iod": "IOD-5"}, "IOD-4") == "IOD-5"


def test_no_override_uses_own_iod_and_anonymous_is_iod1():
    assert intel.effective_iod({"role": "admin", "iod": "IOD-CIJ"}, None) == "IOD-CIJ"
    assert intel.effective_iod(None, None) == "IOD-1"


def test_unknown_iod_is_refused_for_everyone():
    for u in ({"role": "admin"}, {"role": "analyst"}, None):
        with pytest.raises(HTTPException) as err:
            intel.effective_iod(u, "IOD-99")
        assert err.value.status_code == 400


# -- New-items check ------------------------------------------------------------

def test_new_since_only_asks_for_items_collected_after_the_given_time(monkeypatch):
    col = _FakeCol()

    async def cutoff():
        return "2026-10-18T00:00:00+00:00"

    monkeypatch.setattr(intel, "intelligence_col", col)
    monkeypatch.setattr(intel, "_retention_cutoff", cutoff)
    out = asyncio.run(intel.get_new_since(since="2026-11-19T05:00:00+00:00", alerts_only=True, state="Assam"))
    q = col.find_queries[0]
    assert q["fetched_at"] == {"$gt": "2026-11-19T05:00:00+00:00"}
    assert q["severity"] == {"$in": ["critical", "high"]} and q["state"] == "Assam"
    assert out == {"ids": ["x"]}
