"""v37 — every server action needs a login; admin screens need an admin.

No DB or LLM: the anonymous sweep is rejected before any handler runs, and the
role checks use an injected fake user and only assert on refusals.
Startup jobs never run (TestClient is used without its context manager).
"""
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app  # noqa: E402
from utils.auth import get_current_user  # noqa: E402

# The only actions that may answer without a login.
PUBLIC = {
    ("GET", "/api/"),
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),  # best-effort; does nothing without a token
}

client = TestClient(app)


def _all_actions():
    # The published action list is the same on every FastAPI version.
    for raw_path, methods in app.openapi()["paths"].items():
        path = re.sub(r"\{[^}]+\}", "1", raw_path)
        for method in sorted(m.upper() for m in methods):
            if (method, raw_path) not in PUBLIC:
                yield method, path


ACTIONS = list(_all_actions())


def test_sweep_covers_the_whole_server():
    assert len(ACTIONS) > 200


@pytest.mark.parametrize("method,path", ACTIONS)
def test_action_refuses_anonymous_caller(method, path):
    assert client.request(method, path).status_code == 401, f"{method} {path} is open"


def test_live_feed_refuses_anonymous_connection():
    with pytest.raises(Exception):
        with client.websocket_connect("/api/ws/intelligence"):
            pass


@pytest.fixture
def as_viewer():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1", "username": "v", "role": "viewer", "iod": "IOD-4",
    }
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/admin/storage/cleanup-articles"),
    ("POST", "/api/admin/filter-settings"),
    ("GET", "/api/admin/api-usage/debug"),
    ("PUT", "/api/settings/retention"),
    ("DELETE", "/api/settings/rss-feeds"),
    ("POST", "/api/web-sources"),
    ("DELETE", "/api/web-sources/1"),
    ("POST", "/api/fetch-news"),
    ("POST", "/api/generate-brief"),
    ("POST", "/api/fusion/run"),
    ("POST", "/api/training/run"),
    ("POST", "/api/keywords/refresh"),
    ("POST", "/api/faultlines/refresh"),
    ("POST", "/api/social/fetch-all"),
    ("POST", "/api/knowledge-graph/build"),
    ("DELETE", "/api/intelligence/1"),
    ("POST", "/api/fading/cleanup-low"),
    ("POST", "/api/admin/relationships/compute"),
    ("POST", "/api/admin/model-trial"),
    ("POST", "/api/admin/model-routing"),
    ("GET", "/api/admin/model-routing"),
])
def test_admin_only_action_refuses_non_admin(as_viewer, method, path):
    assert client.request(method, path, json={}).status_code == 403


def test_non_admin_cannot_pick_another_iods_briefs():
    from routers.brief_monthly import _effective_iod
    analyst = {"role": "analyst", "iod": "IOD-4"}
    assert _effective_iod(analyst, "IOD-1") == "IOD-4"
    assert _effective_iod(analyst, None) == "IOD-4"
    assert _effective_iod({"role": "admin", "iod": "IOD-1"}, "IOD-5") == "IOD-5"
