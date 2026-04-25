"""Unit tests for the story_generation Lambda handler.

Tests never hit the real Anthropic API — the autouse `stub_adapter`
fixture monkeypatches _get_adapter() to return a MockLLMAdapter, so
every test runs offline and deterministic.
"""

import pytest

import handler
from adapters import MockLLMAdapter


# Shape Step Functions passes to us (same as entry Lambda's output).
SAMPLE_EVENT = {
    "story_id": "01234567-89ab-4def-89ab-0123456789ab",
    "name": "Maya",
    "age": "9",
    "hero": "girl",
    "theme": "space",
    "adventure": "secret_map",
}


@pytest.fixture(autouse=True)
def stub_adapter(monkeypatch):
    """Swap _get_adapter() for one returning a MockLLMAdapter.

    autouse=True so every test in this module is isolated from the
    real Anthropic SDK. Also clears the module-level cache so test
    order can't cause state leakage.
    """
    monkeypatch.setattr(handler, "_ADAPTER", None)
    mock = MockLLMAdapter()
    monkeypatch.setattr(handler, "_get_adapter", lambda: mock)


class TestLambdaHandler:
    def test_returns_event_plus_pages(self):
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        assert result["story_id"] == SAMPLE_EVENT["story_id"]
        assert "pages" in result
        assert len(result["pages"]) == 5

    def test_input_fields_preserved(self):
        """All card selections pass through untouched — image_generation
        needs them too."""
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        for key in ("story_id", "name", "age", "hero", "theme", "adventure"):
            assert result[key] == SAMPLE_EVENT[key]

    def test_pages_have_expected_shape(self):
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        for page in result["pages"]:
            assert "page_num" in page and "text" in page
            assert isinstance(page["page_num"], int)
            assert isinstance(page["text"], str)

    def test_missing_required_field_raises(self):
        """If entry Lambda's validation fails to catch something,
        handler should fail loudly — no silent None values downstream."""
        bad_event = {k: v for k, v in SAMPLE_EVENT.items() if k != "hero"}
        with pytest.raises(KeyError):
            handler.lambda_handler(bad_event, context=None)

    def test_extra_event_fields_are_preserved(self):
        """Step Functions / future metadata fields should pass through."""
        event_with_extras = {**SAMPLE_EVENT, "execution_attempt": 1}
        result = handler.lambda_handler(event_with_extras, context=None)
        assert result["execution_attempt"] == 1

    def test_llm_failure_propagates(self, monkeypatch):
        """Adapter errors bubble up so Step Functions can mark the
        execution FAILED — swallowing would hide real production issues."""
        class FailingAdapter:
            def generate(self, prompt):
                raise RuntimeError("LLM is down")

        monkeypatch.setattr(handler, "_get_adapter", lambda: FailingAdapter())

        with pytest.raises(RuntimeError, match="LLM is down"):
            handler.lambda_handler(SAMPLE_EVENT, context=None)