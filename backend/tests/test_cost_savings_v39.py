"""v39 — cost savings: no wasted model call for text-form items, and failing
items are given up on only when the failure is the item's own. No DB or LLM."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai_pipeline  # noqa: E402
from routers.pipeline import MAX_CLASSIFY_CYCLES, _is_provider_failure  # noqa: E402


def test_text_form_item_is_queued_without_a_paid_model_call(monkeypatch):
    def no_model_call():
        raise AssertionError("the model must not be called for the text form")

    monkeypatch.setattr(ai_pipeline, "get_client", no_model_call)
    monkeypatch.setattr(ai_pipeline, "get_anthropic_client", no_model_call)
    with pytest.raises(ValueError, match="retry job"):
        asyncio.run(ai_pipeline.classify_and_analyze_article("some post text", "A title"))


@pytest.mark.parametrize("error", [
    "",                                              # unknown — be safe, keep retrying
    "timeout",
    "APIStatusError: Error code: 402 - insufficient credits",
    "APIConnectionError: Connection error.",
    "InternalServerError: Error code: 503",
    "AuthenticationError: Error code: 401 - invalid api key",
])
def test_provider_trouble_never_counts_against_the_item(error):
    assert _is_provider_failure(error) is True


@pytest.mark.parametrize("error", [
    "bad answer format: Expecting ',' delimiter: line 1 column 1500 (char 1499)",
    "ValueError: No JSON found in response",
    "ValueError: Parsed JSON not object, got list",
    "ValidationError: 1 validation error for IntelligenceItem",
])
def test_item_specific_failures_count_toward_giving_up(error):
    assert _is_provider_failure(error) is False


def test_give_up_threshold_is_a_few_cycles_not_forever():
    assert 2 <= MAX_CLASSIFY_CYCLES <= 5
