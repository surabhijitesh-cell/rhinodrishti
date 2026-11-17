"""v44 - reliability: score banding, restart catch-up, feed download timeout.

Pure tests - no DB, network or LLM. Run:
  cd backend && python -m pytest tests/test_reliability_v44.py -q
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers.pipeline import finalize_score  # noqa: E402
from server import catchup_due  # noqa: E402
import rss_fetcher  # noqa: E402


def test_boost_within_band_is_added():
    assert finalize_score(45, "medium", 10) == (55, "medium")


def test_boost_capped_at_top_of_medium_band():
    assert finalize_score(55, "medium", 30) == (59, "medium")


def test_critical_never_exceeds_100():
    assert finalize_score(95, "critical", 20) == (100, "critical")


def test_low_stays_low():
    assert finalize_score(30, "low", 25) == (39, "low")


def test_high_capped_at_79():
    assert finalize_score(70, "high", 40) == (79, "high")


def utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_catchup_not_due_before_0610_ist():
    # 00:30 UTC = 06:00 IST
    assert catchup_due(utc(2026, 11, 18, 0, 30), None) is False


def test_catchup_due_after_0610_when_not_done():
    # 01:00 UTC = 06:30 IST
    assert catchup_due(utc(2026, 11, 18, 1, 0), "2026-11-17") is True
    assert catchup_due(utc(2026, 11, 18, 1, 0), None) is True


def test_catchup_not_due_when_done_today():
    assert catchup_due(utc(2026, 11, 18, 5, 0), "2026-11-18") is False


def test_catchup_ist_date_rollover():
    # 18:29 UTC = 23:59 IST on the 18th; 18:31 UTC = 00:01 IST on the 19th (too early)
    assert catchup_due(utc(2026, 11, 18, 18, 29), "2026-11-18") is False
    assert catchup_due(utc(2026, 11, 18, 18, 29), "2026-11-17") is True
    assert catchup_due(utc(2026, 11, 18, 18, 31), "2026-11-18") is False


def test_feed_download_timeout_reports_error(monkeypatch):
    class Boom:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(rss_fetcher.httpx, "Client", Boom)
    out = rss_fetcher.fetch_feed_outcome({"name": "Slow", "url": "http://x.invalid/feed"})
    assert out["articles"] == []
    assert "TimeoutException" in out["error"]


def test_feed_parse_ok_reports_items(monkeypatch):
    xml = (b"<?xml version='1.0'?><rss version='2.0'><channel><title>t</title>"
           b"<item><title>A</title><link>http://a</link><description>d</description></item>"
           b"</channel></rss>")

    class Resp:
        content = xml
        def raise_for_status(self): pass

    class Ok:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return Resp()

    monkeypatch.setattr(rss_fetcher.httpx, "Client", Ok)
    out = rss_fetcher.fetch_feed_outcome({"name": "Fast", "url": "http://x.invalid/feed"})
    assert out["error"] is None and len(out["articles"]) == 1
