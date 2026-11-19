"""
test_faultline_screens_v48.py - batch sparkline history, viewed-IOD saving and
custom-faultline visibility. Fake collections only: no Mongo, network or LLM.

Run:  cd backend && PYTHONUTF8=1 python -m pytest tests/test_faultline_screens_v48.py -v
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from routers import faultlines as fl
from iod_registry import IOD_FAULTLINE_WATCHLIST

TODAY = datetime.now(timezone.utc).date().isoformat()
IOD4_ID = IOD_FAULTLINE_WATCHLIST["IOD-4"][0]
OTHER_ID = next(f for f in IOD_FAULTLINE_WATCHLIST["IOD-5"] if f not in IOD_FAULTLINE_WATCHLIST["IOD-4"])


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *a, **k):
        return self

    async def to_list(self, length=None):
        return list(self.rows)


class FakeCol:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.inserted = []

    def find(self, q=None, proj=None):
        ids = (q or {}).get("id", {}).get("$in")
        fids = (q or {}).get("faultline_id", {}).get("$in")
        rows = [r for r in self.rows if (ids is None or r.get("id") in ids)
                and (fids is None or r.get("faultline_id") in fids)]
        return FakeCursor(rows)

    async def insert_one(self, doc):
        self.inserted.append(doc)

    async def count_documents(self, q):
        return 0

    async def find_one(self, q):
        return None


ANALYST4 = {"role": "analyst", "iod": "IOD-4", "username": "a4"}
ADMIN = {"role": "admin", "iod": "IOD-1", "username": "boss"}


@pytest.fixture
def cols(monkeypatch):
    f = FakeCol([
        {"id": IOD4_ID}, {"id": OTHER_ID},
        {"id": "custom_mine", "created_by": "a4", "is_custom": True},
        {"id": "custom_other", "created_by": "zz", "iod": "IOD-5", "is_custom": True},
    ])
    s = FakeCol([{"faultline_id": i, "date": TODAY, "score": 10.0, "level": "STABLE", "extra": 1}
                 for i in (IOD4_ID, OTHER_ID, "custom_mine", "custom_other")])
    pa = FakeCol()
    monkeypatch.setattr(fl, "faultlines_col", f)
    monkeypatch.setattr(fl, "scores_col", s)
    monkeypatch.setattr(fl, "priority_areas_col", pa)

    async def noop(now):
        return 0
    monkeypatch.setattr(fl, "_retag_faultlines", noop)
    return f, s, pa


def history(user, ids, days=7):
    return asyncio.run(fl.get_faultlines_history_batch(ids=ids, days=days, current_user=user))


class TestHistoryBatch:
    def test_returns_only_visible_faultlines(self, cols):
        out = history(ANALYST4, f"{IOD4_ID},{OTHER_ID},custom_mine,custom_other,nope")
        assert set(out["series"]) == {IOD4_ID, "custom_mine"}
        assert out["series"][IOD4_ID] == [{"date": TODAY, "score": 10.0, "level": "STABLE"}]

    def test_admin_sees_all_existing(self, cols):
        out = history(ADMIN, f"{OTHER_ID},custom_other,nope")
        assert set(out["series"]) == {OTHER_ID, "custom_other"}

    def test_empty_ids_rejected(self, cols):
        with pytest.raises(HTTPException) as e:
            history(ADMIN, " , ")
        assert e.value.status_code == 400

    def test_too_many_ids_rejected(self, cols):
        ids = ",".join(f"x{i}" for i in range(fl.MAX_HISTORY_IDS + 1))
        with pytest.raises(HTTPException) as e:
            history(ADMIN, ids)
        assert e.value.status_code == 400

    def test_duplicate_ids_not_counted_twice(self, cols):
        ids = ",".join([IOD4_ID] * (fl.MAX_HISTORY_IDS + 5))
        assert set(history(ADMIN, ids)["series"]) == {IOD4_ID}

    @pytest.mark.parametrize("days", [0, fl.MAX_HISTORY_DAYS + 1])
    def test_days_out_of_range_rejected(self, cols, days):
        with pytest.raises(HTTPException) as e:
            history(ADMIN, IOD4_ID, days=days)
        assert e.value.status_code == 422


class TestViewedIodSaving:
    def test_admin_viewing_iod_saves_there(self):
        assert fl._target_iod(ADMIN, "IOD-4") == "IOD-4"

    def test_admin_without_view_saves_own(self):
        assert fl._target_iod(ADMIN, None) == "IOD-1"

    def test_non_admin_ignores_override(self):
        assert fl._target_iod(ANALYST4, "IOD-5") == "IOD-4"

    def test_unknown_iod_rejected(self):
        with pytest.raises(HTTPException) as e:
            fl._target_iod(ADMIN, "IOD-99")
        assert e.value.status_code == 400

    def test_custom_faultline_saved_under_viewed_iod(self, cols):
        body = fl.CustomFaultlineCreate(name="x", state="Assam", description="d")
        out = asyncio.run(fl.create_custom_faultline(body, iod="IOD-5", current_user=ADMIN))
        assert out["faultline"]["iod"] == "IOD-5"

    def test_custom_faultline_non_admin_own_iod(self, cols):
        body = fl.CustomFaultlineCreate(name="x", state="Assam", description="d")
        out = asyncio.run(fl.create_custom_faultline(body, iod="IOD-5", current_user=ANALYST4))
        assert out["faultline"]["iod"] == "IOD-4"

    def test_paoi_saved_under_viewed_iod(self, cols):
        out = asyncio.run(fl.create_priority_area(fl.PAOICreate(name="p"), iod="IOD-CIJ", current_user=ADMIN))
        assert out["iod"] == "IOD-CIJ"

    def test_paoi_non_admin_own_iod(self, cols):
        out = asyncio.run(fl.create_priority_area(fl.PAOICreate(name="p"), iod="IOD-CIJ", current_user=ANALYST4))
        assert out["iod"] == "IOD-4"


class TestCustomVisibility:
    def test_no_filter_for_iod1(self):
        assert fl._faultline_list_filter(None, "IOD-1", "u") == {}

    def test_watchlist_plus_tagged_custom(self):
        q = fl._faultline_list_filter(["a"], "IOD-4", None)
        assert {"id": {"$in": ["a"]}} in q["$or"]
        assert {"is_custom": True, "iod": "IOD-4"} in q["$or"]
        assert not any("created_by" in c for c in q["$or"])

    def test_own_creations_included_for_own_view(self):
        q = fl._faultline_list_filter(["a"], "IOD-4", "a4")
        assert {"is_custom": True, "created_by": "a4"} in q["$or"]
