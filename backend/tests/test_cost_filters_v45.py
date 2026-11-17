"""v45 cost filters: whole-word keyword matching, YouTube severity cap, comment-scrape gate."""
import pytest

from intelligence_filter import hard_filter, keyword_hits, has_keyword, word_in
from routers.pipeline import cap_youtube
from youtube_fetcher import add_region_context
from social_comment_sentiment import MIN_COMMENTS_FOR_SENTIMENT, analyze_comments

KW = ["pla", "ied", "lac", "militant"]


@pytest.mark.parametrize("text", ["a nice place", "black cat", "he studied hard", "display unit"])
def test_short_fragments_do_not_hit_inside_words(text):
    assert keyword_hits(text, KW) == []


@pytest.mark.parametrize("text,kw", [("pla troops moved", "pla"), ("an ied blast", "ied"),
                                     ("along the lac", "lac")])
def test_abbreviations_hit_as_whole_words(text, kw):
    assert kw in keyword_hits(text, KW)


def test_non_ascii_keyword_matches_as_substring():
    kws = ["উগ্রপন্থী"]
    assert has_keyword("আজ উগ্রপন্থীরা হামলা করেছে", kws)
    assert word_in("আজ উগ্রপন্থীরা", "উগ্রপন্থী")
    assert not word_in("a place", "pla")


def test_arsenal_and_wedding_no_longer_rejected():
    for title in ["Militants' arsenal seized in Manipur", "Attack at a wedding ceremony in Imphal"]:
        ok, reason = hard_filter({"title": title, "raw_content": "", "region": "india"})
        assert ok, reason


def test_cap_youtube():
    assert cap_youtube(92, "youtube_channel") == (79, "high")
    assert cap_youtube(80, "youtube_search") == (79, "high")
    assert cap_youtube(79, "youtube_search") == (79, None)
    assert cap_youtube(95, "rss") == (95, None)
    assert cap_youtube(95, None) == (95, None)


def test_bank_query_gets_region_context():
    assert add_region_context("ambush") == "ambush northeast India"
    assert add_region_context("Manipur violence") == "Manipur violence"


@pytest.mark.asyncio
async def test_low_comment_posts_skip_paid_scrape():
    assert MIN_COMMENTS_FOR_SENTIMENT == 5
    assert await analyze_comments("twitter", "https://x.com/a/1", 4) is None
