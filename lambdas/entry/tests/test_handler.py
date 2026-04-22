"""Tests for entry handler.lambda_handler.

The handler is a thin adapter around service.create_story. These
tests stub the service out with monkeypatch so we can verify the
handler's *own* responsibilities:

  - mapping the returned payload to 202 Accepted
  - mapping exceptions to HTTP error codes
  - parsing the API Gateway event (body JSON, missing body)
  - attaching CORS headers

Exhaustive business-logic tests live in test_service.py.
"""

import json

import pytest


# A canonical create_story payload. The handler shouldn't care what's
# inside — it just serializes it.
FAKE_RESULT = {
    "story_id": "01234567-89ab-4def-89ab-0123456789ab",
    "status": "PROCESSING",
}


def _event(body):
    """Build a minimal API Gateway event with a JSON string body."""
    return {"body": json.dumps(body) if body is not None else None}


class TestStatusMapping:
    """create_story always returns PROCESSING — handler maps it to 202."""

    def test_processing_returns_202(self, monkeypatch):
        import handler

        monkeypatch.setattr(handler, "create_story", lambda **kwargs: FAKE_RESULT)

        response = handler.lambda_handler(_event({"hero": "girl"}), None)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["story_id"] == FAKE_RESULT["story_id"]
        assert body["status"] == "PROCESSING"


class TestExceptionMapping:
    """Exceptions from the service map to HTTP status codes."""

    def test_value_error_returns_400(self, monkeypatch):
        import handler

        def raise_value_error(**kwargs):
            raise ValueError("Missing required field: hero")

        monkeypatch.setattr(handler, "create_story", raise_value_error)

        response = handler.lambda_handler(_event({}), None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Missing required field: hero" in body["error"]

    def test_unexpected_exception_returns_500(self, monkeypatch):
        import handler

        def raise_runtime_error(**kwargs):
            raise RuntimeError("DynamoDB is on fire")

        monkeypatch.setattr(handler, "create_story", raise_runtime_error)

        response = handler.lambda_handler(_event({"hero": "girl"}), None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        # We must not leak internal details to the client.
        assert "DynamoDB" not in body["error"]
        assert body["error"] == "Internal server error"


class TestEventParsing:
    """Handler must tolerate messy API Gateway event shapes."""

    def test_invalid_json_body_returns_400(self, monkeypatch):
        import handler

        # If we get past parsing, this would blow up — but we shouldn't.
        monkeypatch.setattr(
            handler,
            "create_story",
            lambda **kwargs: pytest.fail("service should not be called"),
        )

        response = handler.lambda_handler({"body": "not json {"}, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "valid JSON" in body["error"]

    def test_missing_body_defaults_to_empty_dict(self, monkeypatch):
        """event.body is None → handler passes {} to service, which raises ValueError."""
        import handler

        received_body = {}

        def capture_body(**kwargs):
            received_body.update(kwargs["body"])
            raise ValueError("Missing required field: hero")

        monkeypatch.setattr(handler, "create_story", capture_body)

        response = handler.lambda_handler({}, None)

        # Handler normalized missing body to {} and forwarded to service.
        assert received_body == {}
        assert response["statusCode"] == 400

    def test_empty_string_body_defaults_to_empty_dict(self, monkeypatch):
        """event.body is "" → same as None."""
        import handler

        received_body = {}

        def capture_body(**kwargs):
            received_body.update(kwargs["body"])
            raise ValueError("Missing required field: hero")

        monkeypatch.setattr(handler, "create_story", capture_body)

        response = handler.lambda_handler({"body": ""}, None)

        assert received_body == {}
        assert response["statusCode"] == 400


class TestResponseHeaders:
    """Every response must carry CORS headers so the browser can read it."""

    def test_cors_headers_on_success(self, monkeypatch):
        import handler

        monkeypatch.setattr(handler, "create_story", lambda **kwargs: FAKE_RESULT)

        response = handler.lambda_handler(_event({"hero": "girl"}), None)

        headers = response["headers"]
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in headers["Access-Control-Allow-Methods"]
        assert headers["Content-Type"] == "application/json"

    def test_cors_headers_on_error(self, monkeypatch):
        import handler

        def raise_runtime_error(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(handler, "create_story", raise_runtime_error)

        response = handler.lambda_handler(_event({"hero": "girl"}), None)

        headers = response["headers"]
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in headers["Access-Control-Allow-Methods"]

    def test_cors_headers_on_json_parse_error(self):
        """Even the pre-service 400 path gets CORS headers — via error_response."""
        import handler

        response = handler.lambda_handler({"body": "{not json"}, None)

        assert response["headers"]["Access-Control-Allow-Origin"] == "*"