"""
test_fusion_sort_pdf_v47.py - duplicate merging, Feed severity sort, Faultline PDF
(same-measure levels, no internal ids on the Actors page, cached AI text).

Pure logic with fakes - no database, no AI calls.

Run:  cd backend && PYTHONUTF8=1 python -m pytest tests/test_fusion_sort_pdf_v47.py -q
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import fusion_engine as fe
import faultline_pdf as fp
from routers import intelligence as intel


def _item(title, url=""):
    return {"title": title, "source_url": url, "source": "x", "state": "Manipur"}


# -- 1. duplicate merging ------------------------------------------------------

def test_fragments_do_not_match_inside_words():
    ents = fe.extract_key_entities("Please replace the broke bridge in India")
    assert not ents & {"pla", "bro", "nia"}
    assert "nia" in fe.extract_key_entities("NIA raids house")
    assert "naga" not in fe.extract_key_entities("Nagaland polls")
    assert "naga" in fe.extract_key_entities("Naga groups meet")


def test_exact_title_and_same_url_still_merge():
    assert fe.are_similar(_item("Blast in Imphal"), _item("blast in imphal!"))
    assert fe.are_similar(_item("One headline", "http://a/1"), _item("Totally different", "http://a/1"))


def test_syndicated_story_still_merges():
    a = _item("Two militants killed in encounter in Manipur's Churachandpur district")
    b = _item("2 militants killed in encounter in Churachandpur district, Manipur")
    assert fe.are_similar(a, b)


def test_differing_numbers_do_not_merge():
    a = _item("Two militants killed in encounter in Churachandpur Manipur")
    b = _item("Three militants killed in encounter in Churachandpur Manipur")
    assert not fe.are_similar(a, b)
    # unless it is literally the same source URL
    a["source_url"] = b["source_url"] = "http://same/url"
    assert fe.are_similar(a, b)


def test_unrelated_stories_sharing_only_places_do_not_merge():
    a = _item("Flood warning issued for Assam and Meghalaya districts")
    b = _item("Assam and Meghalaya agree on border talks schedule")
    assert not fe.are_similar(a, b)


# -- 2. severity sort ----------------------------------------------------------

def test_severity_rank_order():
    vals = ["low", "Critical", "weird", None, "HIGH", "medium"]
    assert sorted(vals, key=lambda v: -intel.severity_rank(v)) == ["Critical", "HIGH", "medium", "low", "weird", None]
    assert intel.severity_rank("weird", descending=False) > intel.severity_rank("critical", descending=False)


def test_severity_pipeline_plain_and_boost():
    p = intel.build_feed_pipeline({"processed": True}, "severity", -1, 40, 20)
    sort = next(s["$sort"] for s in p if "$sort" in s)
    assert list(sort.items()) == [("_sev_rank", -1), ("published_at", -1)]
    assert p.index({"$skip": 40}) < p.index({"$limit": 20})
    assert not any("$lookup" in s for s in p)
    assert p[-1]["$project"] == {"_id": 0, "_sev_lc": 0, "_sev_rank": 0}

    b = intel.build_feed_pipeline({}, "severity", -1, 0, 20, ["fl1"])
    sort = next(s["$sort"] for s in b if "$sort" in s)
    assert list(sort.items()) == [("_iod_boost", -1), ("_sev_rank", -1), ("published_at", -1)]
    assert any("$lookup" in s for s in b)
    assert b[-1]["$project"]["_iod_boost"] == 0 and b[-1]["$project"]["_sev_rank"] == 0


def test_other_sorts_unchanged_in_boost_pipeline():
    b = intel.build_feed_pipeline({}, "priority_score", -1, 0, 10, ["fl1"])
    assert next(s["$sort"] for s in b if "$sort" in s) == {"_iod_boost": -1, "priority_score": -1}


# -- 3. PDF --------------------------------------------------------------------

def test_level_distribution_uses_average_for_both_periods():
    scores = {"a": {"avg": 80, "last": 10}, "b": {"avg": 10, "last": 90}}
    d = fp.level_distribution(scores)
    assert d["CRITICAL"] == 1 and sum(d.values()) == 2
    assert d == fp.level_distribution({"a": {"avg": 80, "last": 90}, "b": {"avg": 10, "last": 10}})


def _agg(actors):
    lv = {"current": fp.level_distribution({}), "previous": fp.level_distribution({}), "measure": "avg"}
    lv["delta"] = {k: 0 for k in lv["current"]}
    return {
        "year": 2026, "month": 11, "period": None, "iod": "IOD-1", "is_fortnight": False,
        "month_name": "November 2026", "prev_month_name": "October 2026", "generated_at": "",
        "key_metrics": {"total": 0, "critical_now": 0, "rising_period": 0, "declining_period": 0},
        "mom_levels": lv, "paois": [], "state_summaries": [], "top_movers": [],
        "all_faultlines": [], "top_actors": actors,
    }


def test_actor_page_shows_names_not_ids():
    import pytest
    fitz = pytest.importorskip("fitz")
    actors = [{"name": "NSCN-K", "count": 3,
               "faultlines": ["p5_meghalaya_tribal_dynamics", "Manipur Valley-Hills"],
               "headline": {}}]
    pdf = fp.render_faultline_pdf(_agg(actors), {})
    text = "".join(pg.get_text() for pg in fitz.open(stream=pdf, filetype="pdf"))
    assert "p5_meghalaya_tribal_dynamics" not in text
    assert "Manipur Valley-Hills" in text
    assert fp.reader_faultline_name("fl_x_1", {"fl_x_1": "Real Name"}) == "Real Name"


# -- 4. synthesis cache --------------------------------------------------------

class _Col:
    def __init__(self, preset=None):
        self.rows, self.writes = list(preset or []), 0

    async def find_one(self, key, proj=None):
        return next((r for r in self.rows if all(r.get(k) == v for k, v in key.items())), None)

    async def update_one(self, key, upd, upsert=False):
        self.writes += 1
        self.rows.append(dict(upd["$set"]))


class _DB:
    def __init__(self, col):
        self.faultline_report_synthesis = col


class _LLM:
    def __init__(self, ok=True):
        self.calls, self.ok = 0, ok

    async def __call__(self, prompt, max_tokens=0):
        self.calls += 1
        if not self.ok:
            raise RuntimeError("boom")
        return {"bottom_line": "BL", "advisory": "ADV"}


def _run(c):
    return asyncio.run(c)


def test_synthesis_cache_miss_then_hit():
    col, llm = _Col(), _LLM()
    agg = _agg([])
    first = _run(fp.get_or_run_pdf_synthesis(_DB(col), agg, llm))
    assert first["bottom_line"] == "BL" and first["generated_at"] and col.writes == 1
    n = llm.calls
    second = _run(fp.get_or_run_pdf_synthesis(_DB(col), agg, llm))
    assert second["bottom_line"] == "BL" and llm.calls == n and col.writes == 1
    assert second["generated_at"] == first["generated_at"]


def test_changed_data_creates_new_text():
    col, llm = _Col(), _LLM()
    agg = _agg([])
    _run(fp.get_or_run_pdf_synthesis(_DB(col), agg, llm))
    agg2 = _agg([])
    agg2["key_metrics"] = {**agg2["key_metrics"], "critical_now": 5}
    _run(fp.get_or_run_pdf_synthesis(_DB(col), agg2, llm))
    assert col.writes == 2


def test_failed_ai_text_is_not_cached():
    col = _Col()
    out = _run(fp.get_or_run_pdf_synthesis(_DB(col), _agg([]), _LLM(ok=False)))
    assert out["bottom_line"] == "" and col.writes == 0


def test_odd_stored_value_is_a_miss():
    agg = _agg([])
    key = {"year": 2026, "month": 11, "period": None, "iod": "IOD-1",
           "input_hash": fp.synthesis_input_hash(agg)}
    for bad in ("garbage", None, {"bottom_line": 5}, ["x"]):
        col, llm = _Col([{**key, "synthesis": bad, "generated_at": 7}]), _LLM()
        out = _run(fp.get_or_run_pdf_synthesis(_DB(col), agg, llm))
        assert out["bottom_line"] == "BL" and llm.calls > 0
