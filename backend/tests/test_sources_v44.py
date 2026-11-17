"""
test_sources_v44.py — source health status, translation client shape, AI keyword
refresh parsing, honest filter-savings arithmetic.

Pure tests — no Mongo connection or LLM calls (fake clients only).

Run:  cd backend && python -m pytest tests/test_sources_v44.py -v
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from source_health import health_status
import filter_metrics


# ── fake OpenAI-style client ──────────────────────────────────────────────────

class _FakeClient:
    """Exposes only chat.completions.create (async) — no .messages, like the real one."""
    def __init__(self, reply=None, error=None):
        self.calls = []
        self._reply, self._error = reply, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        msg = SimpleNamespace(content=self._reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def _iso(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).isoformat()


# ── health_status ─────────────────────────────────────────────────────────────

def test_status_ok_within_limit():
    assert health_status({"kind": "rss", "last_success": _iso(3)}, NOW) == "ok"


def test_status_silent_past_limit():
    assert health_status({"kind": "rss", "last_success": _iso(30)}, NOW) == "silent"


def test_status_failing_when_error_after_success_and_overdue():
    doc = {"kind": "youtube", "last_success": _iso(30), "last_error_at": _iso(1), "last_error": "x"}
    assert health_status(doc, NOW) == "failing"


def test_status_never_without_success_or_error():
    assert health_status({"kind": "web"}, NOW) == "never"


def test_status_failing_when_only_errors():
    assert health_status({"kind": "web", "last_error": "no content"}, NOW) == "failing"


def test_web_limit_is_longer_than_rss():
    doc = {"last_success": _iso(30)}
    assert health_status({**doc, "kind": "web"}, NOW) == "ok"
    assert health_status({**doc, "kind": "rss"}, NOW) == "silent"


# ── translation ───────────────────────────────────────────────────────────────

def test_shared_translate_uses_chat_completions(monkeypatch):
    import llm_client
    import shared
    fake = _FakeClient(reply="  Hello world  ")
    monkeypatch.setattr(llm_client, "get_client", lambda: fake)
    out = asyncio.run(shared.translate_to_english("নমস্কার পৃথিবী"))
    assert out == "Hello world"
    assert fake.calls[0]["max_tokens"] == 400
    assert fake.calls[0]["messages"][0]["role"] == "system"


def test_shared_translate_falls_back_on_error(monkeypatch):
    import llm_client
    import shared
    monkeypatch.setattr(llm_client, "get_client", lambda: _FakeClient(error=RuntimeError("boom")))
    assert asyncio.run(shared.translate_to_english("নমস্কার")) == "[Non-English content]"


def test_filter_translate_uses_chat_completions(monkeypatch):
    import intelligence_filter as f
    fake = _FakeClient(reply="Security forces arrived at the border post today")
    monkeypatch.setattr(f, "get_client", lambda: fake)
    text, conf = asyncio.run(f.translate_to_english("সীমান্ত চৌকিতে নিরাপত্তা বাহিনী এসেছে আজ", "bn"))
    assert text.startswith("Security forces")
    assert conf >= 50


def test_filter_translate_falls_back_on_error(monkeypatch):
    import intelligence_filter as f
    monkeypatch.setattr(f, "get_client", lambda: _FakeClient(error=RuntimeError("boom")))
    src = "সীমান্ত চৌকিতে নিরাপত্তা বাহিনী"
    assert asyncio.run(f.translate_to_english(src, "bn")) == (src, 0)


# ── AI keyword steps ──────────────────────────────────────────────────────────

def _historical():
    from collections import Counter
    return {"high_priority_texts": [{"severity": "high", "text": "border tension"}],
            "actors": Counter({"NSCN": 2}), "threats": Counter({"ambush": 1}),
            "locations": Counter({"Manipur": 3})}


def test_emerging_keywords_parsed(monkeypatch):
    import keyword_engine as k
    fake = _FakeClient(reply='Sure: ["coordinated ethnic mobilization", "x", "arms cache recovery"]')
    monkeypatch.setattr(k, "get_client", lambda: fake)
    errors = []
    out = asyncio.run(k._generate_emerging_keywords(_historical(), errors=errors))
    assert [o["keyword"] for o in out] == ["coordinated ethnic mobilization", "arms cache recovery"]
    assert errors == []


def test_emerging_keywords_error_is_reported(monkeypatch):
    import keyword_engine as k
    monkeypatch.setattr(k, "get_client", lambda: _FakeClient(error=RuntimeError("no key")))
    errors = []
    assert asyncio.run(k._generate_emerging_keywords(_historical(), errors=errors)) == []
    assert errors and "no key" in errors[0]


def test_expansion_parsed(monkeypatch):
    import keyword_engine as k
    fake = _FakeClient(reply='{"border infiltration": ["illegal border crossing", "cross-border intrusion"]}')
    monkeypatch.setattr(k, "get_client", lambda: fake)
    out = asyncio.run(k._expand_keywords_with_ai([{"keyword": "border infiltration", "score": 80}]))
    assert {o["keyword"] for o in out} == {"illegal border crossing", "cross-border intrusion"}
    assert all(o["score"] == 65 for o in out)


# ── filter savings ────────────────────────────────────────────────────────────

def test_calls_saved_counts_only_rejections():
    assert filter_metrics.calls_saved(10, 5, 3) == 18
    assert filter_metrics.calls_saved(0, 0, 0) == 0


def test_cost_uses_measured_price():
    assert filter_metrics._CLASSIFY_COST_PER_CALL_USD == 0.0012
    assert round(filter_metrics.calls_saved(100, 0, 0) * filter_metrics._CLASSIFY_COST_PER_CALL_USD, 4) == 0.12
