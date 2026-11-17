"""v45 — model trial summary, two-step scoring routing, trial guard. No DB, no AI."""
import json
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

import ai_pipeline
import model_trial
from model_routing import FIRST_PASS_MODEL, FIRST_PASS_CONTENT_CHARS


def _r(sev, fp, stage1=True, title="t"):
    return {"title": title, "stored_severity": sev, "first_pass_priority": fp,
            "first_pass_severity": model_trial.severity_of(fp), "stage1_relevant": stage1}


def test_summarise_counts_and_examples():
    results = [
        _r("critical", 90, title="A"),
        _r("high", 30, title="missed-high"),
        _r("high", 70, stage1=False, title="dropped-high"),
        _r("low", 10, stage1=False, title="dropped-low"),
        {"title": "x", "error": "boom"},
    ]
    s = model_trial.summarise(results)
    assert s["scored"] == 4 and s["errors"] == 1
    assert s["stored_by_severity"] == {"critical": 1, "high": 2, "low": 1}
    assert s["stage1"]["would_reject"] == 2
    assert s["stage1"]["of_which_critical_high"] == 1
    assert s["stage1"]["examples"] == ["dropped-high"]
    assert s["first_pass"]["critical_high_missed"] == 1
    assert s["first_pass"]["missed_examples"] == ["missed-high"]
    assert s["first_pass"]["critical_high_kept_pct"] == 66.7
    assert s["first_pass"]["share_to_full_model_pct"] == 50.0
    assert s["first_pass"]["confusion"]["high->low"] == 1


def test_summarise_empty():
    s = model_trial.summarise([])
    assert s["first_pass"]["share_to_full_model_pct"] is None


def test_examples_capped_at_15():
    s = model_trial.summarise([_r("high", 10, title=str(i)) for i in range(40)])
    assert len(s["first_pass"]["missed_examples"]) == 15


def test_trial_guard():
    now = datetime.now(timezone.utc)
    assert model_trial.can_start(None, now) == (True, False)
    assert model_trial.can_start({"status": "done"}, now) == (True, False)
    assert model_trial.can_start({"status": "running", "started_at": now - timedelta(minutes=5)}, now) == (False, False)
    assert model_trial.can_start({"status": "running", "started_at": now - timedelta(hours=3)}, now) == (True, True)


# ---- two-step routing with a fake model client ----

class _FakeClient:
    def __init__(self, scores):
        self.calls, self._scores = [], list(scores)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    async def _create(self, **kw):
        self.calls.append(kw)
        body = json.dumps({"priority_score": self._scores.pop(0), "title_english": "x"})
        msg = types.SimpleNamespace(content=body)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


@pytest.fixture
def route(monkeypatch):
    fake_bias = types.ModuleType("feedback_bias")

    async def _none():
        return ""
    fake_bias.get_feedback_bias_context = _none
    monkeypatch.setitem(sys.modules, "feedback_bias", fake_bias)
    monkeypatch.setattr(ai_pipeline, "is_openrouter_exhausted", lambda: False)

    def setup(two_step, scores):
        client = _FakeClient(scores)
        monkeypatch.setattr(ai_pipeline, "get_client", lambda: client)

        async def _on():
            return two_step
        monkeypatch.setattr(ai_pipeline, "_two_step_on", _on)
        return client
    return setup


ARTICLE = {"title": "T", "raw_content": "x" * 3000}


@pytest.mark.asyncio
async def test_switch_off_is_one_full_model_call(route):
    c = route(False, [20])
    res = await ai_pipeline.classify_and_analyze_article(ARTICLE)
    assert len(c.calls) == 1 and c.calls[0]["model"] == ai_pipeline.MODEL
    assert "x" * 2000 in c.calls[0]["messages"][1]["content"]
    assert "x" * 2001 not in c.calls[0]["messages"][1]["content"]
    assert "scored_by" not in res


@pytest.mark.asyncio
async def test_two_step_low_first_pass_stops(route):
    c = route(True, [30])
    res = await ai_pipeline.classify_and_analyze_article(ARTICLE)
    assert len(c.calls) == 1 and c.calls[0]["model"] == FIRST_PASS_MODEL
    user = c.calls[0]["messages"][1]["content"]
    assert "x" * FIRST_PASS_CONTENT_CHARS in user and "x" * (FIRST_PASS_CONTENT_CHARS + 1) not in user
    assert res["scored_by"] == FIRST_PASS_MODEL and res["priority_score"] == 30


@pytest.mark.asyncio
async def test_two_step_high_first_pass_goes_to_full_model(route):
    c = route(True, [65, 85])
    res = await ai_pipeline.classify_and_analyze_article(ARTICLE)
    assert [k["model"] for k in c.calls] == [FIRST_PASS_MODEL, ai_pipeline.MODEL]
    assert res["scored_by"] == ai_pipeline.MODEL and res["priority_score"] == 85
