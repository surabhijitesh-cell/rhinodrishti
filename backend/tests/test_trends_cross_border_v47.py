"""Trends stability maths, counting rules and Cross-Border Watch classification. Pure logic only."""
from intel_rules import cross_border_query
from routers import trends as T
from routers import cross_border as C


def _m(total=0, sev=0, early=0, late=0, actors=(), xb=0):
    return {"total": total, "sev_weight": sev, "early_count": early, "late_count": late,
            "actors": set(actors), "cross_border_count": xb}


def test_state_with_no_items_is_no_data_not_stable():
    r = T.compute_stability(_m(), 30)
    assert r["concern_level"] == "No data" and r["stability_score"] is None


def test_busiest_state_is_not_automatically_the_maximum_concern():
    quiet = T.compute_stability(_m(total=3, sev=6, early=1, late=1, actors=["A"]), 30)
    assert quiet["stability_score"] > 70   # busiest-of-peers but far below reference load


def test_heavy_state_reaches_critical_and_scores_stay_in_range():
    r = T.compute_stability(_m(total=500, sev=5000, early=1, late=900, actors=range(100), xb=500), 30)
    assert r["concern_level"] == "CRITICAL"
    assert 0 <= r["stability_score"] <= 100


def test_countable_query_rules():
    q = T.countable_query("2026-01-01")
    assert q["processed"] is True
    assert set(q["severity"]["$in"]) == {"critical", "high", "medium", "low"}
    assert "not_relevant" in q["tags"]["$nin"] and "stage1_filtered" in q["tags"]["$nin"]
    assert q["is_cluster_primary"] == {"$ne": False}


def test_is_countable_item_filters():
    ok = {"processed": True, "severity": "high", "tags": []}
    assert T.is_countable_item(ok)
    assert not T.is_countable_item({**ok, "processed": False})
    assert not T.is_countable_item({**ok, "severity": "unknown"})
    assert not T.is_countable_item({**ok, "severity": None})
    assert not T.is_countable_item({**ok, "tags": ["not_relevant"]})
    assert not T.is_countable_item({**ok, "tags": ["stage05_filtered"]})
    assert not T.is_countable_item({**ok, "is_cluster_primary": False})
    assert not T.is_countable_item(None)


def test_known_state_excludes_unclassified_and_countries():
    assert T._known_state({"state": "Manipur"}) == "Manipur"
    assert T._known_state({"state": "Unclassified"}) is None
    assert T._known_state({"state": "Bangladesh"}) is None
    assert T._known_state({"state": None}) is None


def test_cross_border_rules_come_from_shared_module():
    assert T.cross_border_query is cross_border_query
    assert C.cross_border_query is cross_border_query
    assert C.build_watch_query("2026-01-01")["$or"] == cross_border_query()["$or"]


def _item(i, **kw):
    base = {"id": i, "title": "t", "ai_summary": "summary", "severity": "high",
            "priority_score": 50, "state": "Bangladesh"}
    base.update(kw)
    return base


def test_limit_applies_per_country_and_counts_are_true():
    items = [_item(f"b{i}", priority_score=i) for i in range(10)]
    items += [_item(f"m{i}", state="Myanmar", priority_score=i) for i in range(4)]
    out = C.build_watch_payload(items, 3)
    assert out["bangladesh"]["count"] == 10 and out["bangladesh"]["shown"] == 3
    assert [i["id"] for i in out["bangladesh"]["items"]] == ["b9", "b8", "b7"]
    assert out["myanmar"]["count"] == 4 and len(out["myanmar"]["items"]) == 3
    assert out["total"] == 14


def test_low_priority_country_not_crowded_out_by_other_country():
    items = [_item(f"b{i}", priority_score=90) for i in range(20)]
    items.append(_item("m1", state="Myanmar", priority_score=1))
    out = C.build_watch_payload(items, 5)
    assert out["myanmar"]["count"] == 1


def test_bad_records_are_skipped_or_defaulted():
    items = [
        None, "junk", {"id": None},
        _item("n1", title=None, priority_score=None, entities=None,
              countries_involved=None, regions=None, feedback_total_ratings=None,
              feedback_avg_rating=4),
        _item("n2", entities="oops", signal_bucket=5, early_warning_signal=7),
        _item("ok", priority_score=10),
    ]
    out = C.build_watch_payload(items, 10)
    assert {i["id"] for i in out["bangladesh"]["items"]} == {"n1", "n2", "ok"}


def test_indian_border_state_needs_title_naming_country():
    hit = _item("a", state="Assam", title="Bangladesh BGB firing", countries_involved=["Bangladesh"])
    miss = _item("b", state="Assam", title="Flood relief", countries_involved=["Bangladesh"])
    out = C.build_watch_payload([hit, miss], 10)
    assert [i["id"] for i in out["bangladesh"]["items"]] == ["a"]


def test_a_few_items_do_not_look_like_a_surge():
    from routers.trends import compute_stability
    quiet = {"total": 1, "sev_weight": 2, "actors": set(), "early_count": 0,
             "late_count": 1, "cross_border_count": 1}
    assert compute_stability(quiet, 7)["concern_level"] == "STABLE"
