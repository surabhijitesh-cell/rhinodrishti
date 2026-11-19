"""v47 - faultline scoring: regions, labels, duplicates, candidate choice, AI
failure carry-forward, catch-up, one-job lock, PAOI seed that keeps edits.

No DB or LLM: fakes only.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faultline_engine as fe  # noqa: E402
from priority_areas_seed import paoi_seed_update, seed_priority_areas, PRIORITY_AREAS  # noqa: E402

NORTH_BENGAL = {
    "id": "nb", "name": "NB", "state": "North Bengal",
    "keywords": ["Siliguri corridor"], "tags": ["Border Security"], "signal_buckets": [],
}


def art(i, title="t", published="2026-11-10T00:00:00", **kw):
    return {"id": f"a{i}", "title": title, "published_at": published, **kw}


# ── region gate / whole words / labels ──────────────────────────────────────
def test_west_bengal_item_needs_north_bengal_to_match_north_bengal_faultline():
    south = art(1, "Kolkata port strike", regions=["West Bengal"], tags=["Border Security"])
    north = art(2, "Siliguri border patrol", regions=["West Bengal"], tags=["Border Security"])
    got = fe.pre_filter_articles(NORTH_BENGAL, [south, north])
    assert [a["id"] for a in got] == ["a2"]


def test_keywords_match_whole_words_only():
    fl = {"id": "x", "name": "X", "state": "Assam", "keywords": ["pla"], "tags": [], "signal_buckets": []}
    miss = art(1, "A new place to eat", regions=["Assam"])
    hit = art(2, "PLA troops seen", regions=["Assam"])
    assert [a["id"] for a in fe.pre_filter_articles(fl, [miss, hit])] == ["a2"]


def test_infrastructure_label_old_and_new_both_match():
    fl = {"id": "x", "name": "X", "state": "Assam", "keywords": [],
          "tags": ["Infrastructure / Logistics Disruption"], "signal_buckets": []}
    new = art(1, "Road cut", regions=["Assam"], tags=["Infrastructure / Logistics"])
    old = art(2, "Bridge down", regions=["Assam"], tags=["Infrastructure / Logistics Disruption"])
    assert {a["id"] for a in fe.pre_filter_articles(fl, [new, old])} == {"a1", "a2"}


def test_de_escalating_spellings_are_one_thing():
    assert fe.canonical_direction("DE-ESCALATING") == fe.canonical_direction("DE_ESCALATING") == "DE_ESCALATING"
    assert fe.canonical_tag("Infrastructure / Logistics") == "Infrastructure / Logistics Disruption"


# ── one story once / candidate choice ───────────────────────────────────────
def test_same_story_kept_once_strongest_newest_copy():
    fl = {**NORTH_BENGAL, "state": "Assam"}
    old = art(1, "Siliguri corridor: troops move!", "2026-11-01T00:00:00", regions=["Assam"])
    new = art(2, "siliguri corridor troops move", "2026-11-09T00:00:00", regions=["Assam"])
    got = fe.pre_filter_articles(fl, [old, new])
    assert [a["id"] for a in got] == ["a2"]


def test_ties_prefer_newest():
    fl = {**NORTH_BENGAL, "state": "Assam"}
    a = art(1, "Siliguri corridor one", "2026-11-01T00:00:00", regions=["Assam"])
    b = art(2, "Siliguri corridor two", "2026-11-09T00:00:00", regions=["Assam"])
    assert [x["id"] for x in fe.pre_filter_articles(fl, [a, b])] == ["a2", "a1"]


def test_candidate_cap_reserves_slots_for_newest_unchosen():
    ranked = [art(i, published=f"2026-11-{i + 1:02d}T00:00:00") for i in range(20)]  # a19 newest
    chosen = fe.choose_candidates(ranked, 12, reserve=4)
    ids = [a["id"] for a in chosen]
    assert len(ids) == 12 and len(set(ids)) == 12
    assert ids[:8] == [f"a{i}" for i in range(8)]          # best-ranked kept
    assert set(ids[8:]) == {"a16", "a17", "a18", "a19"}    # newest of the rest


def test_small_list_not_trimmed():
    ranked = [art(i) for i in range(5)]
    assert fe.choose_candidates(ranked, 12) == ranked


# ── AI failure / carry-forward ──────────────────────────────────────────────
GOOD = {"faultline_id": "f", "date": "2026-11-10", "score": 61.0, "level": "ELEVATED",
        "raw_score_pre_propagation": 58.0, "llm_ok": True}


def test_ai_failed_only_when_there_was_work_and_no_usable_answer():
    assert fe.ai_failed_for_faultline(5, 0, True)
    assert fe.ai_failed_for_faultline(5, 3, False)
    assert not fe.ai_failed_for_faultline(5, 2, True)
    assert not fe.ai_failed_for_faultline(0, 0, True)   # genuinely quiet


def test_failed_day_keeps_last_good_score_not_zero():
    assert fe.snapshot_action(True, GOOD, "2026-11-12") == "carry"
    doc = fe.carry_forward_snapshot({**GOOD, "_id": 1}, "2026-11-12", "now")
    assert doc["score"] == 61.0 and doc["date"] == "2026-11-12"
    assert doc["llm_ok"] is False and doc["stale"] and doc["carried_forward"]
    assert doc["stale_since_date"] == "2026-11-10" and "_id" not in doc


def test_failed_rerun_leaves_same_day_final_score_alone():
    assert fe.snapshot_action(True, GOOD, "2026-11-10") == "keep"
    assert fe.snapshot_action(True, None, "2026-11-10") == "fresh_failed"
    assert fe.snapshot_action(False, GOOD, "2026-11-12") == "fresh"


def test_no_alerts_from_failed_carried_or_provisional_scores():
    assert fe.alert_allowed({"llm_ok": True})
    assert not fe.alert_allowed({"llm_ok": False})
    assert not fe.alert_allowed({"llm_ok": True, "carried_forward": True})
    assert not fe.alert_allowed({"llm_ok": True, "provisional": True})
    assert not fe.alert_allowed({"llm_ok": True, "stale": True})


def test_baseline_filter_ignores_bad_scores():
    f = fe.GOOD_SCORE_FILTER
    assert f["llm_ok"] == {"$ne": False} and f["provisional"] == {"$ne": True}
    assert f["carried_forward"] == {"$ne": True}


# ── catch-up ────────────────────────────────────────────────────────────────
def _matches(doc, q):
    for k, v in q.items():
        if isinstance(v, dict) and "$ne" in v:
            if doc.get(k) == v["$ne"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


def test_catchup_counts_today_done_only_for_final_ai_ok_scores():
    q = fe.faultline_done_query("2026-11-12")
    assert _matches({"date": "2026-11-12", "llm_ok": True, "provisional": False}, q)
    assert not _matches({"date": "2026-11-12", "llm_ok": True, "provisional": True}, q)
    assert not _matches({"date": "2026-11-12", "llm_ok": False, "provisional": False}, q)
    assert not _matches({"date": "2026-11-12", "llm_ok": True, "carried_forward": True}, q)


# ── incremental ─────────────────────────────────────────────────────────────
def test_article_mapped_to_another_faultline_still_maps_here():
    cands = [art(1, "Story one"), art(2, "Story two")]
    # a1 already mapped to THIS faultline; a2 only to some other one
    fresh = fe.fresh_for_faultline(cands, {"a1"}, set())
    assert [a["id"] for a in fresh] == ["a2"]
    assert [a["id"] for a in fe.fresh_for_faultline(cands, set(), {"story two"})] == ["a1"]


# ── one scoring job at a time ───────────────────────────────────────────────
def test_second_scoring_job_is_refused_and_lock_always_released():
    assert fe.try_acquire_scoring("daily scoring")
    try:
        assert not fe.try_acquire_scoring("backfill")
        assert "daily scoring" in fe.busy_message()
        res = asyncio.run(fe.run_daily_faultline_pass(object()))
        assert res["skipped"] == "busy"
        res = asyncio.run(fe.run_incremental_faultline_pass(object()))
        assert res["skipped"] == "busy"
        res = asyncio.run(fe.run_backfill(object()))
        assert res["skipped"] == "busy"
    finally:
        fe.release_scoring()
    assert not fe.scoring_status()["busy"]
    assert fe.try_acquire_scoring("x")
    fe.release_scoring()


def test_lock_released_when_a_job_raises():
    class Boom:
        @property
        def faultlines(self):
            raise RuntimeError("db down")
    try:
        asyncio.run(fe.run_daily_faultline_pass(Boom()))
    except RuntimeError:
        pass
    assert not fe.scoring_status()["busy"]


# ── backfill estimate ───────────────────────────────────────────────────────
def test_estimate_counts_each_new_pair_once_and_skips_cached():
    day1 = [("f1", "a1"), ("f1", "a2")]
    day2 = [("f1", "a2"), ("f1", "a3")]           # a2 reused from day 1
    assert fe.count_new_ai_calls([day1, day2], set()) == 3
    assert fe.count_new_ai_calls([day1, day2], {("f1", "a1")}) == 2


# ── PAOI seed keeps edits ───────────────────────────────────────────────────
PA = {"id": "P1", "name": "Original", "rank": 1, "description": "d", "keyword_pull": {"keywords": ["k"]},
      "linked_faultline_ids": ["f1"], "new_field": "fresh"}


def test_seed_inserts_missing_paoi():
    action, doc = paoi_seed_update(None, PA, "now")
    assert action == "insert" and doc["name"] == "Original" and doc["enabled"] is True
    assert doc["created_at"] == "now" and doc["iod"] == "IOD-1"


def test_seed_never_overwrites_edited_fields_only_fills_absent_ones():
    edited = {"id": "P1", "name": "Renamed", "rank": 6, "description": "mine", "enabled": False,
              "keyword_pull": {"keywords": ["mine"]}, "linked_faultline_ids": ["f9"], "iod": "IOD-1"}
    action, fields = paoi_seed_update(edited, PA, "now")
    assert action == "update"
    assert set(fields) == {"new_field", "updated_at"}
    assert fields["new_field"] == "fresh"
    _, nothing = paoi_seed_update({**edited, "new_field": "x"}, PA, "now")
    assert nothing == {}


class _Col:
    def __init__(self, docs):
        self.docs = docs

    async def find_one(self, q, proj=None):
        return next((dict(d) for d in self.docs if d["id"] == q["id"]), None)

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, q, upd, **kw):
        d = next(d for d in self.docs if d["id"] == q["id"])
        d.update(upd["$set"])

        class R:
            matched_count = 1
        return R()

    def find(self, q, proj=None):
        docs = [d for d in self.docs if d.get("enabled", True)]

        class C:
            async def to_list(self_, n):
                return docs

            def __aiter__(self_):
                async def gen():
                    for d in docs:
                        yield d
                return gen()
        return C()


class _Db:
    def __init__(self, paois):
        self.priority_areas = _Col(paois)
        self.faultlines = _Col([])


def test_seed_run_keeps_a_renamed_paoi_and_is_idempotent():
    first = PRIORITY_AREAS[0]
    db = _Db([{"id": first["id"], "name": "My name", "rank": 9, "enabled": True, **{
        k: v for k, v in first.items() if k not in ("id", "name", "rank")}, "iod": "IOD-1"}])
    asyncio.run(seed_priority_areas(db))
    kept = next(d for d in db.priority_areas.docs if d["id"] == first["id"])
    assert kept["name"] == "My name" and kept["rank"] == 9
    assert len(db.priority_areas.docs) == len(PRIORITY_AREAS)
    n = len(db.priority_areas.docs)
    asyncio.run(seed_priority_areas(db))
    assert len(db.priority_areas.docs) == n
