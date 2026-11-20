"""
test_training_users_v49.py — training run rules, effectiveness score, user role
and last-admin rules, password generator and minor-update text.

Pure-function tests plus fake collections: no Mongo, network or LLM calls.

Run:  cd backend && python -m pytest tests/test_training_users_v49.py -v
"""
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from routers import training as tr
from routers import auth
from routers.app_updates import minor_update_text, GENERIC_MINOR_MESSAGE
from models.user import UserUpdate

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def _ago(minutes):
    return (NOW - timedelta(minutes=minutes)).isoformat()


# -- stale run / item ---------------------------------------------------------

def test_run_active_only_with_recent_heartbeat():
    assert tr.run_is_active({"running": True, "heartbeat": _ago(1)}, NOW)
    assert not tr.run_is_active({"running": True, "heartbeat": _ago(tr.RUN_STALE_MINUTES + 1)}, NOW)
    assert not tr.run_is_active({"running": False, "heartbeat": _ago(1)}, NOW)
    assert not tr.run_is_active({"running": True}, NOW)
    assert not tr.run_is_active({}, NOW)


def test_item_stale_after_threshold_or_unknown_start():
    assert not tr.item_is_stale({"status": "processing", "processing_started_at": _ago(1)}, NOW)
    assert tr.item_is_stale({"status": "processing", "processing_started_at": _ago(tr.ITEM_STALE_MINUTES + 1)}, NOW)
    assert tr.item_is_stale({"status": "processing"}, NOW)
    assert not tr.item_is_stale({"status": "pending"}, NOW)


# -- run lock (fake collection) -----------------------------------------------

class FakeStateCol:
    def __init__(self):
        self.doc = None

    async def update_one(self, flt, update, upsert=False):
        d = self.doc
        ors = flt.get("$or", [])

        def matches():
            if d is None:
                return False
            for c in ors:
                if "running" in c and d.get("running") is not True:
                    return True
                if "heartbeat" in c and d.get("heartbeat", "") < c["heartbeat"]["$lt"]:
                    return True
            return False

        if matches():
            d.update(update["$set"])
        elif d is None and upsert:
            self.doc = dict(update["$set"], _id="current")
        else:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("duplicate")


def test_second_run_is_refused_while_first_is_live(monkeypatch):
    monkeypatch.setattr(tr, "run_state_col", FakeStateCol())
    assert asyncio.run(tr._acquire_run_lock(3)) is True
    assert asyncio.run(tr._acquire_run_lock(3)) is False


def test_dead_run_does_not_block_new_run(monkeypatch):
    col = FakeStateCol()
    monkeypatch.setattr(tr, "run_state_col", col)
    assert asyncio.run(tr._acquire_run_lock(3)) is True
    col.doc["heartbeat"] = (datetime.now(timezone.utc) - timedelta(minutes=tr.RUN_STALE_MINUTES + 5)).isoformat()
    assert asyncio.run(tr._acquire_run_lock(2)) is True


def test_run_endpoint_returns_409_with_plain_message(monkeypatch):
    async def no_release():
        return None

    class Col:
        async def count_documents(self, q):
            return 2

    async def refuse(total):
        return False

    monkeypatch.setattr(tr, "_release_stale_items", no_release)
    monkeypatch.setattr(tr, "training_col", Col())
    monkeypatch.setattr(tr, "_acquire_run_lock", refuse)
    with pytest.raises(HTTPException) as e:
        asyncio.run(tr.run_training(None, {}))
    assert e.value.status_code == 409
    assert "already running" in e.value.detail


# -- result counts --------------------------------------------------------------

def test_complete_only_when_every_item_succeeded():
    assert tr.run_outcome(5, 5, 0)["ok"] is True
    out = tr.run_outcome(5, 3, 2)
    assert out["ok"] is False
    assert "3 of 5" in out["message"] and "2 failed" in out["message"]
    assert tr.run_outcome(0, 0, 0)["ok"] is False


# -- effectiveness --------------------------------------------------------------

def _item(sev, avg, i=0):
    return {"id": str(i), "severity": sev, "feedback_avg_rating": avg, "feedback_total_ratings": 1, "title": "t"}


def test_effectiveness_needs_minimum_ratings():
    out = tr.effectiveness_from_items([_item("high", 5, i) for i in range(tr.MIN_RATED_ITEMS - 1)])
    assert out["score"] is None
    assert out["sample_size"] == tr.MIN_RATED_ITEMS - 1
    assert "Not enough ratings yet" in out["message"]


def test_misses_are_ai_too_low_and_false_alarms_counted_separately():
    items = [_item("high", 5, i) for i in range(tr.MIN_RATED_ITEMS)]
    items[0] = _item("low", 6.0, "a")        # AI 2.0 vs analysts 6.0: miss
    items[1] = _item("critical", 1.0, "b")   # critical but judged irrelevant: false alarm, NOT a miss
    out = tr.effectiveness_from_items(items)
    assert out["score"] is not None
    assert out["misses"] == 1
    assert out["false_alarms"] == 1
    assert out["sample_size"] == tr.MIN_RATED_ITEMS


# -- role change / last admin -----------------------------------------------------

class FakeUsers:
    def __init__(self, users):
        self.users = users
        self.last_update = None

    async def find_one(self, flt, proj=None):
        return next((u for u in self.users if u["id"] == flt["id"]), None)

    async def count_documents(self, flt):
        return sum(1 for u in self.users
                   if u["role"] == "admin" and u.get("is_active", True) is not False and u["id"] != flt["id"]["$ne"])

    async def update_one(self, flt, change):
        self.last_update = change
        class R:
            matched_count = 1
        return R()


def _run_update(users, user_id, **fields):
    col = FakeUsers(users)
    auth.users_col = col
    async def go():
        try:
            return await auth.update_user(user_id, UserUpdate(**fields), {"id": "x", "role": "admin"})
        except AttributeError:
            return None
    return col, go


def _users():
    return [
        {"id": "a1", "role": "admin", "is_active": True},
        {"id": "an", "role": "analyst", "is_active": True},
    ]


def test_role_change_bumps_token_version(monkeypatch):
    col = FakeUsers(_users())
    monkeypatch.setattr(auth, "users_col", col)
    asyncio.run(auth.update_user("an", UserUpdate(role="viewer"), {"id": "a1"}))
    assert col.last_update["$inc"] == {"token_version": 1}
    assert col.last_update["$set"] == {"role": "viewer"}


def test_name_only_change_does_not_end_logins(monkeypatch):
    col = FakeUsers(_users())
    monkeypatch.setattr(auth, "users_col", col)
    asyncio.run(auth.update_user("an", UserUpdate(name="New"), {"id": "a1"}))
    assert "$inc" not in col.last_update


def test_cannot_demote_or_deactivate_last_admin(monkeypatch):
    monkeypatch.setattr(auth, "users_col", FakeUsers(_users()))
    for fields in ({"role": "analyst"}, {"is_active": False}):
        with pytest.raises(HTTPException) as e:
            asyncio.run(auth.update_user("a1", UserUpdate(**fields), {"id": "a1"}))
        assert e.value.status_code == 400
        assert "last active admin" in e.value.detail


def test_can_demote_admin_when_another_admin_exists(monkeypatch):
    users = _users() + [{"id": "a2", "role": "admin", "is_active": True}]
    col = FakeUsers(users)
    monkeypatch.setattr(auth, "users_col", col)
    asyncio.run(auth.update_user("a1", UserUpdate(role="analyst"), {"id": "a1"}))
    assert col.last_update["$set"] == {"role": "analyst"}


def test_removes_admin_access_rules():
    admin = {"role": "admin", "is_active": True}
    assert auth.removes_admin_access(admin, {"role": "viewer"})
    assert auth.removes_admin_access(admin, {"is_active": False})
    assert not auth.removes_admin_access(admin, {"name": "x"})
    assert not auth.removes_admin_access({"role": "analyst"}, {"is_active": False})
    assert not auth.removes_admin_access({"role": "admin", "is_active": False}, {"role": "viewer"})


# -- password generator -------------------------------------------------------------

def test_generated_password_shape():
    seen = set()
    for _ in range(50):
        p = auth.generate_password()
        seen.add(p)
        assert len(p) == 14
        assert any(c.islower() for c in p) and any(c.isupper() for c in p)
        assert any(c.isdigit() for c in p) and any(c in "!@#$%" for c in p)
        assert not set(p) & set("0O1lI")
    assert len(seen) == 50


# -- minor update text ----------------------------------------------------------------

def test_minor_update_shows_entered_text_and_old_records_degrade():
    assert minor_update_text({"message": "  Fixed the map zoom  "}) == "Fixed the map zoom"
    assert minor_update_text({"message": ""}) == GENERIC_MINOR_MESSAGE
    assert minor_update_text({}) == GENERIC_MINOR_MESSAGE
    assert minor_update_text({"message": None}) == GENERIC_MINOR_MESSAGE
