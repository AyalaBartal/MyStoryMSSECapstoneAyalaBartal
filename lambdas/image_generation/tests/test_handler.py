"""Unit tests for the image_generation Lambda handler.

Tests never hit OpenAI or S3. The autouse fixture monkeypatches
_get_adapter() → MockImageAdapter and _get_s3_uploader() → spy callable.
"""

import pytest

import handler
from adapters import MockImageAdapter


SAMPLE_EVENT = {
    "story_id": "01234567-89ab-4def-89ab-0123456789ab",
    "hero": "girl",
    "theme": "space",
    "adventure": "asteroid",
    "strength": "super_smart",
    "pages": [
        {"page_num": 1, "text": "Page 1 text", "image_prompt": "Page 1 image prompt"},
        {"page_num": 2, "text": "Page 2 text", "image_prompt": "Page 2 image prompt"},
        {"page_num": 3, "text": "Page 3 text", "image_prompt": "Page 3 image prompt"},
        {"page_num": 4, "text": "Page 4 text", "image_prompt": "Page 4 image prompt"},
        {"page_num": 5, "text": "Page 5 text", "image_prompt": "Page 5 image prompt"},
    ],
}


@pytest.fixture(autouse=True)
def stub_adapter_and_uploader(monkeypatch):
    """Swap real adapter + real S3 for mocks.

    autouse=True so every test is isolated from OpenAI + AWS.
    Stashes the captured uploader calls on the handler module for
    tests that want to inspect what was uploaded.
    """
    monkeypatch.setattr(handler, "_ADAPTER", None)
    monkeypatch.setattr(handler, "_S3_CLIENT", None)
    monkeypatch.setattr(handler, "_BUCKET", None)

    mock_adapter = MockImageAdapter()
    monkeypatch.setattr(handler, "_get_adapter", lambda: mock_adapter)

    calls = []

    def spy_uploader(key, body, content_type):
        calls.append({"key": key, "body": body, "content_type": content_type})

    monkeypatch.setattr(handler, "_get_s3_uploader", lambda: spy_uploader)
    handler._test_uploader_calls = calls  # exposed for assertions


class TestLambdaHandler:
    def test_returns_event_plus_image_keys(self):
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        assert result["story_id"] == SAMPLE_EVENT["story_id"]
        assert "image_s3_keys" in result
        assert len(result["image_s3_keys"]) == 5

    def test_image_keys_follow_expected_format(self):
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        sid = SAMPLE_EVENT["story_id"]
        assert result["image_s3_keys"] == [
            f"stories/{sid}/page_1.png",
            f"stories/{sid}/page_2.png",
            f"stories/{sid}/page_3.png",
            f"stories/{sid}/page_4.png",
            f"stories/{sid}/page_5.png",
        ]

    def test_input_fields_preserved(self):
        """All input fields pass through — pdf_assembly needs them."""
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        for key in ("story_id", "hero", "theme", "adventure", "strength", "pages"):
            assert result[key] == SAMPLE_EVENT[key]

    def test_uploader_called_once_per_page(self):
        handler.lambda_handler(SAMPLE_EVENT, context=None)
        assert len(handler._test_uploader_calls) == 5
        for i, call in enumerate(handler._test_uploader_calls, start=1):
            assert call["key"].endswith(f"page_{i}.png")
            assert call["content_type"] == "image/png"
            assert isinstance(call["body"], bytes)

    def test_extra_event_fields_preserved(self):
        event_with_extras = {**SAMPLE_EVENT, "trace_id": "trace-abc"}
        result = handler.lambda_handler(event_with_extras, context=None)
        assert result["trace_id"] == "trace-abc"

    def test_missing_required_field_raises(self):
        bad_event = {k: v for k, v in SAMPLE_EVENT.items() if k != "story_id"}
        with pytest.raises(KeyError):
            handler.lambda_handler(bad_event, context=None)

    def test_adapter_failure_propagates(self, monkeypatch):
        """Adapter errors bubble up so Step Functions can mark FAILED."""
        class FailingAdapter:
            def generate(self, prompt):
                raise RuntimeError("Image gen is down")

        monkeypatch.setattr(handler, "_get_adapter", lambda: FailingAdapter())

        with pytest.raises(RuntimeError, match="Image gen is down"):
            handler.lambda_handler(SAMPLE_EVENT, context=None)