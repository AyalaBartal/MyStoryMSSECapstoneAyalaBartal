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
                    {
                        "page_num": 1,
                        "text": "Mock page 1 — hero's world.",
                        "image_prompt": "Mock image prompt for page 1",
                    },
                    {
                        "page_num": 2,
                        "text": "Mock page 2 — adventure appears.",
                        "image_prompt": "Mock image prompt for page 2",
                    },
                    {
                        "page_num": 3,
                        "text": "Mock page 3 — hero tries and fails.",
                        "image_prompt": "Mock image prompt for page 3",
                    },
                    {
                        "page_num": 4,
                        "text": "Mock page 4 — hero uses their strength.",
                        "image_prompt": "Mock image prompt for page 4",
                    },
                    {
                        "page_num": 5,
                        "text": "Mock page 5 — victory and warm ending.",
                        "image_prompt": "Mock image prompt for page 5",
                    },
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
    DEFAULT_MAX_TOKENS = 3000

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


class BedrockLLMAdapter(LLMAdapter):
    """Calls Anthropic Claude via AWS Bedrock.

    Uses the boto3 bedrock-runtime client. The Lambda's IAM role grants
    bedrock:InvokeModel on the specific Claude inference profile, so no
    API key is needed — auth is via IAM.

    The client is injected — handler.py builds it and passes it in. Tests
    inject a stub client and assert on how the adapter calls it.
    """

    DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    DEFAULT_MAX_TOKENS = 4000

    def __init__(
        self,
        client,
        model_id: str = DEFAULT_MODEL_ID,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self._client = client
        self._model_id = model_id
        self._max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        response = self._client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self._max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        # Bedrock streams the body — read it once, decode, parse.
        response_body = json.loads(response["body"].read())
        # Same shape as direct Anthropic API: content[0].text
        return response_body["content"][0]["text"]