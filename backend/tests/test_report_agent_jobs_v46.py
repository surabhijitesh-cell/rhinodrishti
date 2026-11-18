"""v46 — Custom Brief Generator runs as a background job.

No DB, no LLM: the report collection and the heavy generation step are fakes.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import report_agent as ra  # noqa: E402

USER = {"username": "admin", "role": "admin"}


class FakeCol:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    @staticmethod
    def _match(doc, flt):
        return all(doc.get(k) == v for k, v in flt.items())

    async def find_one(self, flt, proj=None):
        for d in self.docs:
            if self._match(d, flt):
                return dict(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, flt, upd):
        for d in self.docs:
            if self._match(d, flt):
                d.update(upd["$set"])
                return


@pytest.fixture
def env(monkeypatch):
    reports = FakeCol()
    specs = FakeCol([{"id": "s1", "report_type": "monthly"}])
    monkeypatch.setattr(ra, "agent_reports_col", reports)
    monkeypatch.setattr(ra, "specs_col", specs)
    monkeypatch.setattr(ra, "_JOBS", {})
    return reports


def _req(**kw):
    return ra.GenerateRequest(spec_id="s1", year=2026, month=10, period=None, **kw)


async def _start(monkeypatch, body):
    monkeypatch.setattr(ra, "_generate_body", body)
    return await ra.generate_report(_req(), USER)


async def _finish():
    await asyncio.gather(*list(ra._JOBS.values()), return_exceptions=True)


def test_job_success_ends_ready(env, monkeypatch):
    async def body(report_id, spec, req, user):
        await ra._set_progress(report_id, 1, "x", 2)
        await ra.agent_reports_col.update_one(
            {"id": report_id, "status": "generating"}, {"$set": {"status": "ready"}})

    async def go():
        out = await _start(monkeypatch, body)
        assert out["status"] == "generating" and out["already_running"] is False
        assert env.docs[0]["status"] == "generating"
        await _finish()
        return out["id"]

    rid = asyncio.run(go())
    assert env.docs[0]["id"] == rid and env.docs[0]["status"] == "ready"
    assert env.docs[0]["period_label"] == "October 2026"


def test_job_error_ends_failed_with_short_message(env, monkeypatch):
    async def body(*a):
        raise RuntimeError("x" * 1000)

    async def go():
        await _start(monkeypatch, body)
        await _finish()

    asyncio.run(go())
    d = env.docs[0]
    assert d["status"] == "failed" and len(d["error"]) <= 300 and not ra._JOBS


def test_duplicate_returns_running_job_and_starts_nothing(env, monkeypatch):
    gate = {}

    async def body(*a):
        await gate["ev"].wait()

    async def go():
        gate["ev"] = asyncio.Event()
        first = await _start(monkeypatch, body)
        second = await ra.generate_report(_req(), USER)
        gate["ev"].set()
        await _finish()
        return first, second

    first, second = asyncio.run(go())
    assert second == {"id": first["id"], "status": "generating", "already_running": True}
    assert len(env.docs) == 1


def test_stale_job_is_failed_and_retry_starts_new(env, monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(minutes=46)).isoformat()
    env.docs.append({"id": "old1", "spec_id": "s1", "year": 2026, "month": 10,
                     "period": None, "status": "generating", "started_at": old})
    ra._JOBS["old1"] = None  # present, so only age makes it stale

    async def body(*a):
        return None

    async def go():
        out = await _start(monkeypatch, body)
        await _finish()
        return out

    out = asyncio.run(go())
    assert out["id"] != "old1" and out["already_running"] is False
    assert env.docs[0]["status"] == "failed"


def test_lost_job_after_restart_reads_failed(env):
    env.docs.append({"id": "gone", "status": "generating",
                     "started_at": datetime.now(timezone.utc).isoformat()})
    out = asyncio.run(ra.get_report_status("gone", USER))
    assert out["status"] == "failed" and out["error"]


def test_old_report_without_status_counts_as_ready(env):
    env.docs.append({"id": "legacy", "period_label": "June 2026"})
    assert asyncio.run(ra.get_report_status("legacy", USER))["status"] == "ready"


def test_pdf_refused_while_generating(env):
    env.docs.append({"id": "busy", "status": "generating",
                     "started_at": datetime.now(timezone.utc).isoformat()})
    ra._JOBS["busy"] = None
    with pytest.raises(HTTPException) as e:
        asyncio.run(ra.download_pdf("busy", USER))
    assert e.value.status_code == 409


def test_bad_period_rejected(env):
    with pytest.raises(HTTPException) as e:
        asyncio.run(ra.generate_report(
            ra.GenerateRequest(spec_id="s1", year=2026, month=10, period=3), USER))
    assert e.value.status_code == 422


def test_period_uses_ist_day_boundaries():
    start, end, label = ra._period_range(2026, 10, None)
    assert start.startswith("2026-09-30T18:30") and end.startswith("2026-10-31T18:30")
    assert ra._period_range(2026, 10, 2)[2] == "16-31 October 2026"


PAOIS = [
    {"id": "P1_india_bangladesh_border", "name": "India-Bangladesh Border"},
    {"id": "P5_ras_locations", "name": "RAS Locations"},
    {"id": "P5_meghalaya_tribal_dynamics", "name": "Tribal Dynamics — Meghalaya"},
]


@pytest.mark.parametrize("asked", [
    "P5_ras_locations", "RAS Locations", "RAS locations", "RAS", "ras", "P5_ras",
])
def test_ras_resolves_by_name_and_id(asked):
    got = [p["id"] for p in ra._resolve_focus([asked], PAOIS)]
    assert got == ["P5_ras_locations"]


def test_legacy_tribal_slug_does_not_pull_in_ras():
    got = [p["id"] for p in ra._resolve_focus(["P5_tribal_meg"], PAOIS)]
    assert got == ["P5_meghalaya_tribal_dynamics"]
