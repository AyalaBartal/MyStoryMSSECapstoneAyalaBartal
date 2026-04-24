"""Unit tests for the LLMAdapter implementations."""

import json
from unittest.mock import MagicMock

import pytest

from adapters import (
    AnthropicLLMAdapter,
    LLMAdapter,
    MockLLMAdapter,
)


class TestMockLLMAdapter:
    def test_returns_default_response_when_no_canned(self):
        adapter = MockLLMAdapter()
        result = adapter.generate("any prompt")
        # Default should be valid JSON with 5 pages
        parsed = json.loads(result)
        assert len(parsed["pages"]) == 5
        assert parsed["pages"][0]["page_num"] == 1

    def test_returns_canned_string_when_provided(self):
        adapter = MockLLMAdapter(canned="hello world")
        assert adapter.generate("any prompt") == "hello world"

    def test_canned_empty_string_is_respected(self):
        """Empty string is a valid canned value (for error-path tests)."""
        adapter = MockLLMAdapter(canned="")
        assert adapter.generate("any prompt") == ""

    def test_canned_malformed_json_is_respected(self):
        """MockLLMAdapter doesn't validate — it just returns what's given."""
        bad = "{not: valid json"
        adapter = MockLLMAdapter(canned=bad)
        assert adapter.generate("any prompt") == bad

    def test_is_instance_of_llmadapter(self):
        assert isinstance(MockLLMAdapter(), LLMAdapter)


class TestAnthropicLLMAdapter:
    """Tests use a stub client — no real Anthropic API call."""

    def _make_stub_client(self, returned_text: str = "mock output"):
        """Build a client stub whose messages.create() returns an object
        shaped like the real Anthropic Message: content=[TextBlock(text=...)]."""
        stub = MagicMock()
        text_block = MagicMock()
        text_block.text = returned_text
        response = MagicMock()
        response.content = [text_block]
        stub.messages.create.return_value = response
        return stub

    def test_returns_text_from_first_content_block(self):
        client = self._make_stub_client(returned_text="generated story text")
        adapter = AnthropicLLMAdapter(client=client)
        assert adapter.generate("prompt") == "generated story text"

    def test_calls_client_with_expected_kwargs(self):
        client = self._make_stub_client()
        adapter = AnthropicLLMAdapter(client=client)

        adapter.generate("my prompt")

        client.messages.create.assert_called_once_with(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": "my prompt"}],
        )

    def test_custom_model_and_max_tokens_are_used(self):
        client = self._make_stub_client()
        adapter = AnthropicLLMAdapter(
            client=client,
            model="claude-3-opus-20240229",
            max_tokens=4096,
        )

        adapter.generate("hi")

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-3-opus-20240229"
        assert call_kwargs["max_tokens"] == 4096

    def test_is_instance_of_llmadapter(self):
        client = self._make_stub_client()
        assert isinstance(AnthropicLLMAdapter(client=client), LLMAdapter)


class TestLLMAdapterABC:
    def test_cannot_instantiate_abstract_base(self):
        with pytest.raises(TypeError, match="abstract"):
            LLMAdapter()

    def test_subclass_without_generate_cannot_instantiate(self):
        class BadAdapter(LLMAdapter):
            pass

        with pytest.raises(TypeError, match="abstract"):
            BadAdapter()