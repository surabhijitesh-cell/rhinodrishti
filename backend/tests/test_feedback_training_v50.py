"""
test_feedback_training_v50.py - per-analyst ratings, no AI on rating, Accept
re-queue flag, training examples in the classifier guidance.
Fake collections only: no Mongo, network or LLM.

Run:  cd backend && python -m pytest tests/test_feedback_training_v50.py -v
"""
import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, BackgroundTasks

sys.path.insert(0, str(Path(__file__).parent.parent))

import feedback_bias as fb
from routers import feedback as fr
from routers import intelligence as intel
from routers import pipeline as pl
from utils.roles import require_analyst_or_admin


def _match(row, flt):
    for k, v in flt.items():
        if isinstance(v, dict) and "$exists" in v:
            if (k in row) != v["$exists"]:
                return False
        elif row.get(k) != v:
            return False
    return True


class FakeCol:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, flt, proj=None):
        return next((dict(r) for r in self.rows if _match(r, flt)), None)

    async def update_one(self, flt, upd):
        for r in self.rows:
            if _match(r, flt):
                r.update(upd["$set"])
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def insert_one(self, doc):
        self.rows.append(doc)

    async def count_documents(self, flt):
        return sum(1 for r in self.rows if _match(r, flt))

    def aggregate(self, _p):
        async def gen():
            if self.rows:
                yield {"_id": None, "avg_rating": sum(r["rating"] for r in self.rows) / len(self.rows),
                       "total_ratings": len(self.rows)}
        return gen()


class FakeIntel(FakeCol):
    pass


@pytest.fixture
def env(monkeypatch):
    col = FakeCol()
    monkeypatch.setattr(fr, "feedback_col", col)
    monkeypatch.setattr(fr, "intelligence_col", FakeIntel([{"id": "i1", "state": "Assam"}]))
    monkeypatch.setattr(fr, "db", SimpleNamespace(app_settings=FakeCol()))
    # any AI helper being touched during a rating must fail the test
    import routers.training as tr

    def boom(*a, **k):
        raise AssertionError("AI call made while rating")
    monkeypatch.setattr(tr, "_generate_feedback_impact_summary", boom, raising=False)
    return col


def _rate(user, rating, device_id=None):
    req = SimpleNamespace(client=SimpleNamespace(host="x"))
    body = {"intelligence_id": "i1", "rating": rating}
    if device_id:
        body["device_id"] = device_id
    return asyncio.run(fr.submit_feedback(body, req, BackgroundTasks(), user))


A = {"id": "u1", "username": "alice", "role": "analyst"}
B = {"id": "u2", "username": "bob", "role": "analyst"}


def test_rating_identified_by_user_not_device(env):
    _rate(A, 5, "devX")
    _rate(B, 2, "devX")  # same device, different analyst -> separate rating
    assert len(env.rows) == 2
    assert {r["user_id"] for r in env.rows} == {"u1", "u2"}
    assert asyncio.run(fr._find_user_rating(A, "i1")) == 5
    assert asyncio.run(fr._find_user_rating(B, "i1")) == 2


def test_viewer_refused():
    with pytest.raises(HTTPException) as e:
        asyncio.run(require_analyst_or_admin({"id": "v", "role": "viewer"}))
    assert e.value.status_code == 403


def test_rerate_updates_single_row(env):
    assert _rate(A, 3)["action"] == "created"
    assert _rate(A, 6)["action"] == "updated"
    assert len(env.rows) == 1 and env.rows[0]["rating"] == 6


def test_old_device_rating_adopted_not_double_counted(env):
    env.rows.append({"id": "old", "intelligence_id": "i1", "device_id": "devX", "rating": 2})
    assert asyncio.run(fr._find_user_rating(A, "i1", "devX")) == 2  # still readable
    assert _rate(A, 4, "devX")["action"] == "updated"
    assert len(env.rows) == 1 and env.rows[0]["user_id"] == "u1" and env.rows[0]["rating"] == 4


def test_no_session_check_left_in_feedback_module():
    assert not hasattr(fr, "_check_feedback_session")


def test_accept_requeues_for_full_check_and_clears_filter_marks():
    upd = intel.force_accept_fields("now")
    assert upd["$set"]["processed"] is False and upd["$set"]["force_full_check"] is True
    assert {"filter_reason", "severity"} <= set(upd["$unset"])
    assert "stage0_filtered" in upd["$pull"]["tags"]["$in"]


def test_flagged_items_skip_filters():
    items = [{"id": "a", "force_full_check": True}, {"id": "b"}, {"id": "c", "force_full_check": False}]
    forced, rest = pl.split_force_checked(items)
    assert [i["id"] for i in forced] == ["a"]
    assert [i["id"] for i in rest] == ["b", "c"]


def test_bias_context_includes_capped_training_examples(monkeypatch):
    docs = [{"title": "T" * 200 + str(i), "relevance": 5 if i % 2 else 1} for i in range(20)]
    text = fb.build_training_examples(docs)
    lines = [l for l in text.splitlines() if l.startswith("  - ")]
    assert len(lines) == fb.MAX_TRAINING_EXAMPLES
    assert all(len(l) < 140 for l in lines)
    assert "relevant" in text and "not relevant" in text

    class Cur:
        def __init__(self, d): self.d = d
        def sort(self, *a): return self
        async def to_list(self, n): return self.d[:n]

    monkeypatch.setattr(fb, "training_col", SimpleNamespace(find=lambda *a, **k: Cur(docs)))

    async def none(): return ""
    monkeypatch.setattr(fb, "_compute_bias_context", none)
    fb.invalidate_bias_cache()
    ctx = asyncio.run(fb.get_feedback_bias_context())
    fb.invalidate_bias_cache()
    assert "TRAINING EXAMPLES" in ctx


def test_no_training_examples_gives_empty():
    assert fb.build_training_examples([]) == ""


def test_posts_without_links_get_their_own_key():
    from apify_social_fetcher import _instagram_to_intel_item, _twitter_to_intel_item
    a = _twitter_to_intel_item({"text": "first post", "id": "1111", "author": {"userName": "u"}})
    b = _twitter_to_intel_item({"text": "second post", "author": {"userName": "u"}})
    c = _twitter_to_intel_item({"text": "third post", "author": {"userName": "u"}})
    assert a["source_url"] == "https://x.com/u/status/1111"
    assert b["source_url"] != c["source_url"]
    ig = _instagram_to_intel_item({"caption": "x", "ownerUsername": "o", "shortCode": "Abc"})
    assert ig["source_url"] == "https://www.instagram.com/p/Abc/"


def test_rate_limit_check_ignores_words_like_generate():
    import inspect
    from routers import pipeline
    src = inspect.getsource(pipeline)
    assert "['rate'," not in src and "'rate limit'" in src
