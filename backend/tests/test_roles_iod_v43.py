"""
test_roles_iod_v43.py — viewers cannot start paid/destructive runs; faultline
access follows the user's IOD. Pure functions only: no Mongo, network or LLM.

Run:  cd backend && python -m pytest tests/test_roles_iod_v43.py -v
"""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from iod_registry import IOD_FAULTLINE_WATCHLIST, get_iod_faultline_ids
from utils.roles import can_access_faultline, require_analyst_or_admin


def _gate(role):
    return asyncio.run(require_analyst_or_admin({"role": role}))


class TestRoleGate:
    def test_viewer_refused(self):
        with pytest.raises(HTTPException) as e:
            _gate("viewer")
        assert e.value.status_code == 403

    @pytest.mark.parametrize("role", ["analyst", "admin"])
    def test_analyst_and_admin_pass(self, role):
        assert _gate(role)["role"] == role


def _iod4_ids():
    return get_iod_faultline_ids("IOD-4")


class TestFaultlineAccess:
    def test_admin_sees_all(self):
        assert can_access_faultline({"role": "admin", "iod": "IOD-4"}, {"id": "zzz"})

    def test_iod1_sees_all(self):
        assert can_access_faultline({"role": "analyst", "iod": "IOD-1"}, {"id": "zzz"})

    def test_iod4_sees_own_not_other(self):
        user = {"role": "analyst", "iod": "IOD-4", "username": "a"}
        own = _iod4_ids()[0]
        other = next(f for f in IOD_FAULTLINE_WATCHLIST["IOD-5"] if f not in _iod4_ids())
        assert can_access_faultline(user, {"id": own})
        assert not can_access_faultline(user, {"id": other})

    def test_custom_own_or_tagged(self):
        user = {"role": "analyst", "iod": "IOD-4", "username": "a"}
        assert can_access_faultline(user, {"id": "custom_x", "created_by": "a"})
        assert can_access_faultline(user, {"id": "custom_y", "iod": "IOD-4"})
        assert not can_access_faultline(user, {"id": "custom_z", "created_by": "b", "iod": "IOD-5"})

    def test_iod_falls_back_to_username_registry(self):
        user = {"role": "viewer", "username": "iod4_1"}
        assert can_access_faultline(user, {"id": _iod4_ids()[0]})
        assert not can_access_faultline(user, {"id": "custom_q"})
