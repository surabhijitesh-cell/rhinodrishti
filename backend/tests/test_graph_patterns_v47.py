"""v47 - safe knowledge-graph rebuild, PLA contexts, govt whole-word filter,
and distinct-story patterns. No DB, no LLM: fake collections only."""
import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")
os.environ.setdefault("DB_NAME", "test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import knowledge_graph as kg  # noqa: E402
import pattern_engine as pe  # noqa: E402
from routers.knowledge_graph_routes import _is_govt_actor  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def _match(doc, q):
    for k, v in q.items():
        if isinstance(v, dict) and "$ne" in v:
            if doc.get(k) == v["$ne"]:
                return False
        elif doc.get(k) != v:
            return False
    return True


class FakeCol:
    def __init__(self, rows=None, fail_insert=False):
        self.rows = list(rows or [])
        self.fail_insert = fail_insert

    async def insert_many(self, docs):
        if self.fail_insert:
            raise RuntimeError("insert failed")
        self.rows.extend(dict(d) for d in docs)

    async def delete_many(self, q):
        self.rows = [r for r in self.rows if not _match(r, q)]

    async def find_one(self, q, proj=None):
        return next((r for r in self.rows if _match(r, q)), None)

    async def update_one(self, q, upd, upsert=False):
        row = await self.find_one(q)
        if row is None:
            row = dict(q)
            self.rows.append(row)
        row.update(upd["$set"])


class FakeDB:
    def __init__(self, **cols):
        self.cols = {n: FakeCol() for n in
                     ("kg_actors", "kg_locations", "kg_edges", "app_settings", "intelligence_patterns")}
        self.cols.update(cols)

    def __getitem__(self, n):
        return self.cols[n]

    def __getattr__(self, n):
        return self.cols[n]


def _docs(build_id):
    return [{"name": "x", "build_id": build_id}]


# ---- graph swap ----
def test_successful_swap_replaces_old_rows_and_sets_active_build():
    db = FakeDB()
    for n in ("kg_actors", "kg_locations", "kg_edges"):
        db.cols[n].rows = [{"name": "old", "build_id": "old"}, {"name": "legacy"}]
    run(kg._swap_in_graph(db, "new", "t", _docs("new"), _docs("new"), _docs("new")))
    for n in ("kg_actors", "kg_locations", "kg_edges"):
        assert [r["build_id"] for r in db.cols[n].rows] == ["new"]
    assert run(kg.get_active_build_filter(db)) == {"build_id": "new"}


def test_failed_insert_keeps_old_rows_and_removes_partial_new_rows():
    db = FakeDB(kg_edges=FakeCol(rows=[{"name": "old", "build_id": "old"}], fail_insert=True))
    db.cols["kg_actors"].rows = [{"name": "old", "build_id": "old"}]
    db.cols["app_settings"].rows = [{"key": kg.ACTIVE_BUILD_KEY, "build_id": "old"}]
    with pytest.raises(RuntimeError):
        run(kg._swap_in_graph(db, "new", "t", _docs("new"), _docs("new"), _docs("new")))
    assert [r["build_id"] for r in db.cols["kg_actors"].rows] == ["old"]
    assert [r["build_id"] for r in db.cols["kg_edges"].rows] == ["old"]
    assert db.cols["kg_locations"].rows == []
    assert run(kg.get_active_build_filter(db)) == {"build_id": "old"}


class _Cursor:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self._it = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _ItemsCol:
    def __init__(self, items):
        self.items = items

    def find(self, *a, **k):
        return _Cursor(self.items)


def test_empty_result_does_not_wipe_existing_graph():
    db = FakeDB(intelligence_items=_ItemsCol([]))
    db.cols["kg_actors"].rows = [{"name": "old", "build_id": "old"}]
    res = run(kg.build_knowledge_graph(db))
    assert res["skipped"] is True
    assert len(db.cols["kg_actors"].rows) == 1


def test_full_build_from_items_swaps_in_new_graph():
    items = [{"id": "1", "title": "ULFA attack", "state": "Assam", "severity": "high",
              "threat_category": "Militancy", "actors": ["ULFA"],
              "entities": {"locations": ["Tinsukia"]}}]
    db = FakeDB(intelligence_items=_ItemsCol(items))
    db.cols["kg_actors"].rows = [{"name": "old"}]
    res = run(kg.build_knowledge_graph(db))
    assert res["actors"] == 1 and res["edges"] == 1
    assert [r["name"] for r in db.cols["kg_actors"].rows] == ["ULFA-I"]


# ---- PLA ----
@pytest.mark.parametrize("ctx,expected", [
    ("PLA troops near LAC in Arunachal", "PLA (China)"),
    ("Chinese buildup in Tibet", "PLA (China)"),
    ("RPF cadres arrested in Imphal", "PLA Manipur"),
    ("Meitei group, Manipur", "PLA Manipur"),
    ("PLA spotted", "PLA (unspecified)"),
    ("Manipur and China border talks", "PLA (unspecified)"),
    ("a place in the plain", "PLA (unspecified)"),
])
def test_bare_pla_uses_context(ctx, expected):
    assert kg.normalize_actor("PLA", ctx) == expected
    assert kg.normalize_actor("People's Liberation Army", ctx) == expected


def test_explicit_pla_names_and_other_aliases_unchanged():
    assert kg.normalize_actor("PLA Manipur", "China") == "PLA Manipur"
    assert kg.normalize_actor("PLA (China)") == "PLA (China)"
    assert kg.normalize_actor("NSCN") == "NSCN-IM"
    assert kg.normalize_actor("ULFA (I)") == "ULFA-I"


# ---- govt filter ----
def test_govt_filter_uses_whole_words():
    assert not _is_govt_actor("India Liberation Front")
    assert not _is_govt_actor("Draw Group")
    assert _is_govt_actor("NIA")
    assert _is_govt_actor("RAW officials")
    assert _is_govt_actor("Assam Police")
    assert _is_govt_actor("Indian Army")
    assert not _is_govt_actor("ULFA-I")


# ---- patterns ----
def _item(i, cluster=None, primary=None, title=None, sev="low"):
    d = {"id": str(i), "title": title or f"Story {i}", "state": "Assam",
         "threat_category": "Militancy", "severity": sev, "published_at": f"2026-11-{20 - i:02d}"}
    if cluster:
        d["cluster_id"] = cluster
    if primary is not None:
        d["is_cluster_primary"] = primary
    return d


def test_syndicated_copies_do_not_create_a_pattern():
    items = [_item(1, "c1", True), _item(2, "c1", False), _item(3, "c1", False),
             _item(4, title="Same headline"), _item(5, title="same  headline!")]
    assert pe.build_patterns(items, 7) == []


def test_three_distinct_stories_make_a_pattern_and_risk_uses_distinct_count():
    items = [_item(i) for i in range(1, 4)] + [_item(9, "c", True), _item(10, "c", False)]
    out = pe.build_patterns(items, 7)
    rt = next(p for p in out if p["pattern_type"] == "region_threat")
    assert rt["event_count"] == 4 and rt["escalation_risk"] == "MODERATE"


class _PatItems:
    def __init__(self, items):
        self.items = items

    def find(self, *a, **k):
        return self

    def sort(self, *a, **k):
        return self

    async def to_list(self, n):
        return self.items[:n]


def _patterns_db(items, old=None):
    db = FakeDB(intelligence_items=_PatItems(items))
    db.cols["intelligence_patterns"].rows = list(old or [])
    return db


def test_pattern_run_replaces_old_rows_and_records_run():
    db = _patterns_db([_item(i) for i in range(1, 4)], old=[{"pattern_key": "stale"}])
    out = run(pe.detect_patterns(db))
    rows = db.cols["intelligence_patterns"].rows
    assert out and len(rows) == len(out) and all("run_id" in r for r in rows)
    assert db.cols["app_settings"].rows[0]["ran_at"]


def test_zero_pattern_run_clears_stale_and_records_run():
    db = _patterns_db([_item(1)], old=[{"pattern_key": "stale"}])
    assert run(pe.detect_patterns(db)) == []
    assert db.cols["intelligence_patterns"].rows == []
    assert db.cols["app_settings"].rows[0]["pattern_count"] == 0


def test_failed_pattern_save_keeps_old_patterns():
    db = _patterns_db([_item(i) for i in range(1, 4)], old=[{"pattern_key": "stale"}])
    db.cols["intelligence_patterns"].fail_insert = True
    with pytest.raises(RuntimeError):
        run(pe.detect_patterns(db))
    assert db.cols["intelligence_patterns"].rows == [{"pattern_key": "stale"}]
    assert db.cols["app_settings"].rows == []
