"""v38 — every OpenRouter chat call is recorded once, with its feature and the
provider's own reported cost. No network, DB or LLM: the SDK call and the
database write are both replaced by fakes."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm_client  # noqa: E402
import usage_tracker  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402


def _tracked_client(monkeypatch, usage):
    """Real SDK client, wrapped, with the network call and DB write faked."""
    sent, written = {}, []

    async def fake_create(self, *args, **kwargs):
        sent.update(kwargs)
        return SimpleNamespace(usage=usage, choices=[])

    async def fake_update_one(flt, update, upsert=False):
        written.append((flt, update))

    monkeypatch.setattr("openai.resources.chat.completions.AsyncCompletions.create", fake_create)
    monkeypatch.setattr(usage_tracker, "db", SimpleNamespace(api_usage=SimpleNamespace(update_one=fake_update_one)))
    client = llm_client._with_usage_tracking(AsyncOpenAI(api_key="test", base_url="http://localhost"))
    return client, sent, written


def test_call_is_recorded_with_feature_and_reported_cost(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100, cost=0.0123)
    client, sent, written = _tracked_client(monkeypatch, usage)

    async def score_article():
        return await client.chat.completions.create(model=llm_client.MODEL, messages=[], extra_body={"include_reasoning": False})

    asyncio.run(score_article())

    assert sent["extra_body"] == {"include_reasoning": False, "usage": {"include": True}}
    assert len(written) == 1
    inc = written[0][1]["$inc"]
    assert inc["cost_usd"] == 0.0123
    assert inc["call_count"] == 1
    feature = "test_usage_tracking_v38__score_article"
    assert inc[f"by_feature.{feature}.call_count"] == 1
    assert inc[f"by_feature.{feature}.cost_usd"] == 0.0123


def test_price_table_is_used_when_provider_reports_no_cost(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    client, _, written = _tracked_client(monkeypatch, usage)
    asyncio.run(client.chat.completions.create(model="google/gemini-2.5-flash", messages=[]))
    # Nov 2026 list price: $0.30 in + $2.50 out per million tokens.
    assert written[0][1]["$inc"]["cost_usd"] == 2.80


def test_recording_failure_never_breaks_the_model_call(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    client, _, _ = _tracked_client(monkeypatch, usage)

    async def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(usage_tracker, "track_usage_generic", boom)
    assert asyncio.run(client.chat.completions.create(model="m", messages=[])).usage is usage
