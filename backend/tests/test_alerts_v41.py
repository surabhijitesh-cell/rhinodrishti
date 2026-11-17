"""v41 — one definition of an open alert, and acknowledged faultline alerts
stay acknowledged. Pure logic, no DB or LLM."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faultline_engine import should_suppress_alert  # noqa: E402
from routers.intelligence import open_alert_filter  # noqa: E402

NOW = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)


def _alert(hours_ago, acknowledged, score=80):
    return {"created_at": (NOW - timedelta(hours=hours_ago)).isoformat(), "acknowledged": acknowledged, "score": score}


def test_open_alert_is_unacknowledged_critical_or_high_visible_in_the_feed():
    flt = open_alert_filter("2026-10-18T00:00:00+00:00")
    assert flt["severity"] == {"$in": ["critical", "high"]}
    assert flt["acknowledged"] == {"$ne": True}
    assert flt["published_at"] == {"$gte": "2026-10-18T00:00:00+00:00"}
    assert "not_relevant" in flt["tags"]["$nin"]
    assert flt["is_archived"] == {"$ne": True}


def test_first_alert_for_a_faultline_is_raised():
    assert should_suppress_alert(None, 85, NOW) is False


def test_alert_is_not_repeated_within_a_day():
    assert should_suppress_alert(_alert(10, acknowledged=False), 85, NOW) is True


def test_acknowledged_alert_does_not_come_back_on_the_next_pass():
    # The old rule re-raised this ~12-24 hours after the analyst pressed ACK.
    assert should_suppress_alert(_alert(30, acknowledged=True, score=80), 82, NOW) is True


def test_acknowledged_alert_returns_if_the_situation_gets_much_worse():
    assert should_suppress_alert(_alert(30, acknowledged=True, score=80), 91, NOW) is False


def test_acknowledged_alert_can_return_after_a_week():
    assert should_suppress_alert(_alert(8 * 24, acknowledged=True, score=80), 80, NOW) is False


def test_ignored_alert_is_raised_again_after_a_day():
    assert should_suppress_alert(_alert(30, acknowledged=False), 80, NOW) is False
