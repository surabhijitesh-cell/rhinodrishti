"""
test_small_screens_v48.py — adding an uploaded file to the Feed, with fakes.

Pure tests: no Mongo connection, network or LLM calls.

Run:  cd backend && python -m pytest tests/test_small_screens_v48.py -v
"""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from routers import documents as docs


class FakeCol:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None

    async def insert_one(self, row):
        self.rows.append(dict(row))


def _doc(**over):
    base = {"id": "d1", "filename": "report.pdf", "source_type": "file", "iod": "IOD-1",
            "processed": True, "analysis": {"executive_summary": "Summary text"},
            "extracted_text": "body"}
    base.update(over)
    return base


@pytest.fixture
def cols(monkeypatch):
    uploads, intel = FakeCol([_doc()]), FakeCol()
    monkeypatch.setattr(docs, "uploads_col", uploads)
    monkeypatch.setattr(docs, "intelligence_col", intel)
    return uploads, intel


def _add(user, **req):
    data = docs.AddToFeedRequest(document_id=req.pop("document_id", "d1"), **req)
    return asyncio.run(docs.add_url_to_feed(data, user))


ANALYST = {"role": "analyst", "iod": "IOD-1", "username": "a"}


def test_file_is_added_with_summary(cols):
    _, intel = cols
    out = _add(ANALYST, severity="HIGH", priority_score=500)
    assert out["severity"] == "high" and out["priority_score"] == 100
    assert intel.rows[0]["source_document_id"] == "d1"
    assert intel.rows[0]["ai_summary"] == "Summary text"


def test_viewer_cannot_add(cols):
    with pytest.raises(HTTPException) as e:
        _add({"role": "viewer", "iod": "IOD-1"})
    assert e.value.status_code == 403
    assert cols[1].rows == []


def test_other_iod_cannot_see_file(cols):
    with pytest.raises(HTTPException) as e:
        _add({"role": "analyst", "iod": "IOD-2"})
    assert e.value.status_code == 404


def test_unfinished_or_failed_analysis_is_refused(cols):
    uploads, _ = cols
    uploads.rows[0]["processed"] = False
    with pytest.raises(HTTPException) as e:
        _add(ANALYST)
    assert e.value.status_code == 400
    uploads.rows[0].update(processed=True, analysis={"error": "boom"})
    with pytest.raises(HTTPException) as e:
        _add(ANALYST)
    assert e.value.status_code == 400


def test_same_file_cannot_be_added_twice(cols):
    _add(ANALYST)
    with pytest.raises(HTTPException) as e:
        _add(ANALYST)
    assert e.value.status_code == 409
    assert len(cols[1].rows) == 1


def test_link_documents_must_use_their_address(cols):
    cols[0].rows[0]["source_type"] = "url"
    with pytest.raises(HTTPException) as e:
        _add(ANALYST)
    assert e.value.status_code == 400
