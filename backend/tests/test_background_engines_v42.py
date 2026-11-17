"""Stage 6 — background engines: fading covers every item, faultline scores
fall when the news is old, and X posts keep their real posting time.
Pure logic only: no database, no AI calls."""
import math
from datetime import datetime, timedelta, timezone

from apify_social_fetcher import (
    INSTAGRAM_ACCOUNTS, _instagram_to_intel_item, _parse_date, _tweet_time_from_id,
    _twitter_to_intel_item,
)
from fading_engine import fading_update
from faultline_engine import DECAY_LAMBDA, compute_faultline_score, compute_faultline_score_v2

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def _item(days_old: float, severity: str = "low", **extra) -> dict:
    return {"priority_score": 50, "severity": severity,
            "published_at": (NOW - timedelta(days=days_old)).isoformat(), **extra}


# ── Fading ───────────────────────────────────────────────────────────────────

def test_never_scored_item_is_always_written():
    fields = fading_update(_item(0.1, "high"), NOW)
    assert fields["visibility_band"] == "fading" and fields["is_archived"] is False


def test_old_low_item_is_archived():
    assert fading_update(_item(10), NOW)["is_archived"] is True


def test_low_score_item_younger_than_a_week_is_not_archived():
    fields = fading_update(_item(6), NOW)
    assert fields["visibility_band"] == "archived" and fields["is_archived"] is False


def test_unchanged_item_is_skipped():
    item = _item(10)
    stored = {**item, **fading_update(item, NOW)}
    assert fading_update(stored, NOW + timedelta(hours=1)) is None


def test_archived_item_rated_up_comes_back():
    item = _item(8, "medium", priority_score=20)
    stored = {**item, **fading_update(item, NOW)}
    assert stored["is_archived"] is True
    rated = {**stored, "analyst_avg_rating": 5, "is_cross_border": True, "special_flags": ["a", "b", "c", "d"]}
    assert fading_update(rated, NOW)["is_archived"] is False


# ── Faultline time decay ─────────────────────────────────────────────────────

def _articles(days_old: int, n: int = 5) -> tuple:
    day = (datetime(2026, 11, 17) - timedelta(days=days_old)).date().isoformat()
    arts = [{"id": f"a{i}", "severity": "high", "published_at": f"{day}T06:00:00+00:00",
             "actors": ["ULFA"], "is_cross_border": False} for i in range(n)]
    return arts, [{"impact_score": 80, "confidence": 80} for _ in arts]


def test_fresh_news_scores_in_full():
    for days in (0, 1):  # yesterday counts as fresh: the pass may run just after midnight
        assert compute_faultline_score(*_articles(days), target_date="2026-11-17")["freshness"] == 1.0


def test_old_news_scores_lower_than_the_same_news_fresh():
    fresh = compute_faultline_score(*_articles(0), target_date="2026-11-17")
    stale = compute_faultline_score(*_articles(6), target_date="2026-11-17")
    assert stale["freshness"] == round(math.exp(-DECAY_LAMBDA * 5), 3)
    assert stale["raw_score"] < fresh["raw_score"] * 0.25
    assert stale["avg_impact"] < fresh["avg_impact"] * 0.25


def test_one_fresh_article_keeps_old_ones_from_fading_the_score():
    old, old_m = _articles(6)
    new, new_m = _articles(0, n=1)
    assert compute_faultline_score(old + new, old_m + new_m, target_date="2026-11-17")["freshness"] == 1.0


def test_subissue_scoring_also_falls_with_old_news():
    def score(days_old: int) -> float:
        arts, _ = _articles(days_old)
        matches = [{"article_id": a["id"], "subissue_id": "s1", "llm_confidence": 80,
                    "llm_impact_score": 80, "structured_score": 60} for a in arts]
        return compute_faultline_score_v2(arts, matches, {"s1": {"default_weight": 1.0}},
                                          target_date="2026-11-17")["raw_score"]
    assert score(6) < score(0) * 0.25


# ── X post times ─────────────────────────────────────────────────────────────

def test_x_date_format_is_read_not_replaced_by_now():
    assert _parse_date("Wed Nov 11 08:15:00 +0000 2026") == "2026-11-11T08:15:00+00:00"


def test_iso_and_epoch_dates_still_work():
    assert _parse_date("2026-11-11T08:15:00Z") == "2026-11-11T08:15:00+00:00"
    assert _parse_date(1794384900000) == _parse_date(1794384900)


def test_post_time_can_be_read_from_the_post_id():
    # id taken from a stored live post that the old code stamped 12 Jul 15:26
    assert _tweet_time_from_id("https://x.com/someone/status/2076324299355672712").startswith("2026-07-1")
    assert _tweet_time_from_id("https://x.com/someone") == ""


def test_tweet_without_a_date_uses_its_id():
    item = _twitter_to_intel_item({"text": "hello", "url": "https://x.com/u/status/2076324299355672712"})
    assert item["published_at"] == _tweet_time_from_id("2076324299355672712")


# ── Instagram: named accounts ────────────────────────────────────────────────

def test_instagram_account_post_is_read_with_its_real_time():
    # shape of a real row from the account scraper (17 Nov 2026 test run)
    item = _instagram_to_intel_item({
        "ownerUsername": "pratidintime", "timestamp": "2026-11-17T03:31:18.000Z",
        "url": "https://www.instagram.com/p/Df0-IEpjvwO/", "commentsCount": 7,
        "caption": "Triple murder in Duliajan, Dibrugarh district of Assam",
    })
    assert item["source"] == "Instagram - @pratidintime"
    assert item["published_at"] == "2026-11-17T03:31:18+00:00"
    assert item["comments_count"] == 7


def test_instagram_row_for_an_account_with_nothing_new_is_skipped():
    assert _instagram_to_intel_item({"error": "no_items", "inputUrl": "https://www.instagram.com/x"}) is None


def test_instagram_accounts_are_listed_once_and_bangladesh_has_the_largest_share():
    names = [a for group in INSTAGRAM_ACCOUNTS.values() for a in group]
    assert len(names) == len(set(names))
    bangladesh = {"dhakatribune", "prothomalo", "dailystar_bd", "thebusinessstandard",
                  "jamunatv", "bdnews24", "dbcnews.tv"}
    posts = {a: n for n, group in INSTAGRAM_ACCOUNTS.items() for a in group}
    assam = {"pratidintime", "guwahatiplus", "news18assamne"}
    assert sum(posts[a] for a in bangladesh) > sum(posts[a] for a in assam)
    assert 50 <= sum(posts.values()) <= 70  # stays near the agreed ~60 posts a fetch
