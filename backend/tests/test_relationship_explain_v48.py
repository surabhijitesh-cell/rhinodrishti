"""v48 — "Explain this link" uses the shared AI client, formats its prompt
properly, copes with missing dates and gives plain-English failures.

No DB or LLM: the collections and the AI client are fakes.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import relationships as rel  # noqa: E402


def test_prompt_has_clean_lines_and_handles_missing_dates():
    p = rel.build_pair_prompt(
        "same_actor",
        {"title": "A news", "state": "Manipur", "published_at": "2026-11-01T10:00:00Z"},
        {"title": "B news", "state": None, "published_at": None},
    )
    assert "A: A news [Manipur, 2026-11-01]" in p
    assert "B: B news [unknown state, date unknown]" in p
    assert "(" not in p.split("B:")[1].split("\n")[0]  # no stray tuple text


class FakeCol:
    def __init__(self, doc=None):
        self.doc, self.updated = doc, None

    async def find_one(self, *a, **k):
        return self.doc

    async def update_one(self, flt, upd):
        self.updated = upd


class FakeItems:
    def __init__(self, docs):
        self.docs = docs

    async def find_one(self, flt, proj=None):
        return self.docs.get(flt["id"])


def _setup(monkeypatch, edge, items, answer=None, boom=False):
    col = FakeCol(edge)
    monkeypatch.setattr(rel, "relationships_col", col)
    monkeypatch.setattr(rel, "db", SimpleNamespace(intelligence_items=FakeItems(items)))

    async def create(**kw):
        if boom:
            raise RuntimeError("secret key problem")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    import llm_client
    monkeypatch.setattr(llm_client, "get_client", lambda: client)
    return col


def _call():
    return asyncio.run(rel.explain_edge_by_pair(from_id="a", to_id="b", type="same_actor"))


ITEMS = {"a": {"title": "x", "published_at": None}, "b": {"title": "y"}}


def test_success_saves_and_returns_explanation(monkeypatch):
    col = _setup(monkeypatch, {"x": 1}, ITEMS, answer="  Linked by one group.  ")
    out = _call()
    assert out == {"explanation": "Linked by one group.", "cached": False}
    assert col.updated["$set"]["ai_explanation"] == "Linked by one group."


def test_cached_answer_skips_ai(monkeypatch):
    _setup(monkeypatch, {"ai_explanation": "old"}, ITEMS, boom=True)
    assert _call() == {"explanation": "old", "cached": True}


def test_missing_link_is_friendly_404(monkeypatch):
    _setup(monkeypatch, None, ITEMS)
    with pytest.raises(HTTPException) as e:
        _call()
    assert e.value.status_code == 404 and "no longer exists" in e.value.detail


def test_missing_item_is_friendly_404(monkeypatch):
    _setup(monkeypatch, {"x": 1}, {"a": ITEMS["a"]})
    with pytest.raises(HTTPException) as e:
        _call()
    assert e.value.status_code == 404


@pytest.mark.parametrize("kw", [{"boom": True}, {"answer": ""}, {"answer": None}])
def test_ai_failure_is_friendly_503_without_internals(monkeypatch, kw):
    col = _setup(monkeypatch, {"x": 1}, ITEMS, **kw)
    with pytest.raises(HTTPException) as e:
        _call()
    assert e.value.status_code == 503
    assert "secret" not in e.value.detail and "not available" in e.value.detail
    assert col.updated is None
