"""Tests for the story_generation Lambda handler.

The handler is thin — it builds the adapter, calls service.generate_story,
saves the pages to DynamoDB, and returns the event plus the new pages key.
These tests verify event passthrough, adapter injection, and DynamoDB write
behaviour. Service-level logic is tested separately in test_service.py.
"""

import pytest

import handler
from adapters import MockLLMAdapter


class StubTable:
    """Stand-in for a boto3 DynamoDB Table resource.

    Records every update_item() call so tests can assert on what would
    have been written to DynamoDB without hitting real AWS.
    """

    def __init__(self):
        self.updates = []

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        return {}


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    """Replace the module-level adapter and table caches with stubs.

    autouse=True so every test in this module is isolated from real
    Bedrock and real DynamoDB. Without this, importing handler.py would
    try to build a live boto3 client and eventually hit AWS.
    """
    monkeypatch.setattr(handler, "_ADAPTER", MockLLMAdapter())
    monkeypatch.setattr(handler, "_TABLE", StubTable())


@pytest.fixture
def valid_event():
    return {
        "story_id": "test-story-id",
        "name": "Emma",
        "hero": "girl",
        "theme": "space",
        "adventure": "secret_map",
        "age": "7",
    }


class TestLambdaHandler:
    def test_returns_event_plus_pages(self, valid_event):
        result = handler.lambda_handler(valid_event, None)

        # Original event fields are passed through
        assert result["story_id"] == "test-story-id"
        assert result["name"] == "Emma"

        # New `pages` field is added
        assert "pages" in result
        assert isinstance(result["pages"], list)

    def test_input_fields_preserved(self, valid_event):
        result = handler.lambda_handler(valid_event, None)

        for field in ("story_id", "name", "hero", "theme", "adventure", "age"):
            assert result[field] == valid_event[field]

    def test_pages_have_expected_shape(self, valid_event):
        result = handler.lambda_handler(valid_event, None)

        assert len(result["pages"]) == 5
        for page in result["pages"]:
            assert "page_num" in page
            assert "text" in page
            assert "image_prompt" in page

    def test_missing_required_field_raises(self, valid_event):
        del valid_event["name"]

        with pytest.raises(KeyError):
            handler.lambda_handler(valid_event, None)

    def test_extra_event_fields_are_preserved(self, valid_event):
        valid_event["trace_id"] = "abc-123"
        valid_event["debug_flag"] = True

        result = handler.lambda_handler(valid_event, None)

        assert result["trace_id"] == "abc-123"
        assert result["debug_flag"] is True

    def test_llm_failure_propagates(self, valid_event, monkeypatch):
        """If the adapter raises, the handler doesn't swallow it.

        Step Functions catches the exception and routes to the MarkFailed
        state, which flips the DynamoDB row to FAILED.
        """

        class FailingAdapter:
            def generate(self, prompt):
                raise RuntimeError("LLM call failed")

        monkeypatch.setattr(handler, "_ADAPTER", FailingAdapter())

        with pytest.raises(RuntimeError, match="LLM call failed"):
            handler.lambda_handler(valid_event, None)

    def test_pages_are_saved_to_dynamodb(self, valid_event):
        """Verify the handler writes the generated pages to DynamoDB
        and flips status to IMAGES_PENDING.
        """
        handler.lambda_handler(valid_event, None)

        # Exactly one update_item call expected
        assert len(handler._TABLE.updates) == 1
        update = handler._TABLE.updates[0]

        # Correct key
        assert update["Key"] == {"story_id": "test-story-id"}

        # Status flips to IMAGES_PENDING
        assert update["ExpressionAttributeValues"][":status"] == "IMAGES_PENDING"

        # Pages match what was returned
        saved_pages = update["ExpressionAttributeValues"][":pages"]
        assert len(saved_pages) == 5