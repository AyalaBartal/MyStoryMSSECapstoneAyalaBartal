"""LLM adapter interface and implementations.

Ports-and-adapters: the Lambda's business logic depends on the abstract
LLMAdapter interface, never on a concrete provider SDK. Swap providers
by writing a new subclass — no service.py change needed.
"""

import json
from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    """Port for calling a language model. One method: prompt in, text out."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return raw model output for a prompt."""
        raise NotImplementedError


class MockLLMAdapter(LLMAdapter):
    """Deterministic adapter for tests. No network, no cost.

    By default returns a well-formed 5-page JSON response matching the
    service's expected schema. Tests that want to exercise error paths
    can construct it with a custom canned string (e.g. malformed JSON).
    """

    def __init__(self, canned: str = None):
        self._canned = canned if canned is not None else self._default_response()

    def generate(self, prompt: str) -> str:
        return self._canned

    @staticmethod
    def _default_response() -> str:
        return json.dumps(
            {
                "pages": [
                    {"page_num": 1, "text": "Mock page 1 — hero's world."},
                    {"page_num": 2, "text": "Mock page 2 — challenge appears."},
                    {"page_num": 3, "text": "Mock page 3 — hero tries and fails."},
                    {"page_num": 4, "text": "Mock page 4 — hero uses their strength."},
                    {"page_num": 5, "text": "Mock page 5 — victory and warm ending."},
                ]
            }
        )


class AnthropicLLMAdapter(LLMAdapter):
    """Calls Anthropic Claude via the official SDK.

    The client is injected — handler.py builds it (reading ANTHROPIC_API_KEY
    from the env) and passes it in. This keeps the adapter testable
    without a real API call: tests inject a stub client and assert on
    how the adapter calls it.
    """

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    DEFAULT_MAX_TOKENS = 1024

    def __init__(
        self,
        client,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic returns Message(content=[TextBlock(text=...), ...]).
        # For single-turn prompts it's always a single TextBlock.
        return response.content[0].text