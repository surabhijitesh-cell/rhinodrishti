"""Daily Brief window choice and report date/total helpers. Pure: no DB, no AI."""
from datetime import datetime, timezone

from routers.briefs import choose_brief_window, pick_prior_brief
from routers.reports import _date_range, total_text

NOW = datetime(2026, 11, 19, 3, 0, tzinfo=timezone.utc)  # 08:30 IST on 19 Nov
TODAY = "2026-11-19"


def test_past_date_window_is_24h_ending_0600_ist():
    start, end = choose_brief_window("2026-11-10", TODAY, NOW, None)
    assert end == "2026-11-10T00:30:00+00:00"
    assert start == "2026-11-09T00:30:00+00:00"


def test_today_starts_at_prior_brief_generation():
    prior = {"generated_at": "2026-11-18T01:00:00+00:00"}
    assert choose_brief_window(TODAY, TODAY, NOW, prior) == ("2026-11-18T01:00:00+00:00", None)


def test_backfilled_brief_does_not_push_today_forward():
    # Yesterday's brief was back-filled just now but covers an older window.
    prior = {"generated_at": "2026-11-19T02:59:00+00:00", "window_end": "2026-11-17T22:30:00+00:00"}
    assert choose_brief_window(TODAY, TODAY, NOW, prior)[0] == "2026-11-17T22:30:00+00:00"


def test_today_window_is_capped_at_48h_and_first_brief_uses_yesterday_0600():
    old = {"generated_at": "2026-11-01T00:00:00+00:00"}
    assert choose_brief_window(TODAY, TODAY, NOW, old)[0] == "2026-11-17T03:00:00+00:00"
    # first brief ever: yesterday 06:00 IST = 00:30 UTC on the 18th
    assert choose_brief_window(TODAY, TODAY, NOW, None)[0] == "2026-11-18T00:30:00+00:00"


def test_prior_brief_prefers_yesterday_and_skips_empty():
    y = {"date": "2026-11-18", "generated_at": "x"}
    o = {"date": "2026-11-10", "generated_at": "y"}
    assert pick_prior_brief(y, o) is y
    assert pick_prior_brief({"date": "2026-11-18"}, o) is o
    assert pick_prior_brief(None, None) is None


def test_bare_dates_are_ist_days():
    assert _date_range("2026-11-10", "2026-11-12") == {
        "$gte": "2026-11-09T18:30:00+00:00", "$lt": "2026-11-12T18:30:00+00:00"}


def test_full_timestamps_keep_old_behaviour():
    assert _date_range("2026-11-10T00:00:00+00:00", "2026-11-12T00:00:00+00:00") == {
        "$gte": "2026-11-10T00:00:00+00:00", "$lte": "2026-11-12T00:00:00+00:00"}
    assert _date_range(None, None) == {}


def test_total_text():
    assert total_text(200, 512) == "Showing 200 of 512 matching items"
    assert total_text(40, 40) == "40"


def test_capped_report_says_counts_cover_listed_items():
    from routers.reports import counted_label
    assert counted_label("Critical", 200, 900) == "Critical (items shown):"
    assert counted_label("Critical", 20, 20) == "Critical:"
