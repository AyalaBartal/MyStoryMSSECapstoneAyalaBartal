"""Unit tests for handler.lambda_handler.

Handler tests mock out the service layer — they only verify
event-parsing and exception-to-HTTP mapping. Actual DynamoDB/S3
behavior is already covered by test_service.py, so there's no
reason to exercise it again here.
"""

import json

import pytest

import handler
from service import StoryNotFound


def _event(story_id="abc"):
    """Minimal API Gateway v1 proxy event for GET /story/{story_id}."""
    return {"pathParameters": {"story_id": story_id}}


class TestStatusMapping:
    """HTTP status code is derived from the service's status field."""

    def test_processing_returns_202(self, monkeypatch):
        monkeypatch.setattr(handler, "get_story", lambda **kw: {
            "story_id": kw["story_id"],
            "status": "PROCESSING",
            "created_at": "2026-04-22T10:00:00+00:00",
        })

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["statusCode"] == 202
        body = json.loads(resp["body"])
        assert body["status"] == "PROCESSING"
        assert body["story_id"] == "abc"

    def test_complete_returns_200_with_download_url(self, monkeypatch):
        monkeypatch.setattr(handler, "get_story", lambda **kw: {
            "story_id": kw["story_id"],
            "status": "COMPLETE",
            "download_url": "https://signed-url.example",
            "expires_in": 900,
        })

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["download_url"] == "https://signed-url.example"
        assert body["expires_in"] == 900

    def test_failed_returns_200_not_500(self, monkeypatch):
        """A story that failed is still a successful API response.

        The API call worked — it correctly reported the story's state.
        500 would imply our service broke, which it didn't.
        """
        monkeypatch.setattr(handler, "get_story", lambda **kw: {
            "story_id": kw["story_id"],
            "status": "FAILED",
            "error": "upstream error",
        })

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "FAILED"
        assert body["error"] == "upstream error"


class TestExceptionMapping:
    """Domain exceptions translate to specific HTTP status codes."""

    def test_story_not_found_returns_404(self, monkeypatch):
        def raise_not_found(**kw):
            raise StoryNotFound(kw["story_id"])
        monkeypatch.setattr(handler, "get_story", raise_not_found)

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["statusCode"] == 404
        assert json.loads(resp["body"]) == {"error": "Story not found"}

    def test_value_error_returns_400(self, monkeypatch):
        def raise_value_error(**kw):
            raise ValueError("Invalid story_id: 'abc'")
        monkeypatch.setattr(handler, "get_story", raise_value_error)

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "Invalid" in body["error"]

    def test_unexpected_exception_returns_500(self, monkeypatch):
        """Anything we didn't anticipate = 500 with a generic message.

        Crucially: we do NOT leak the original exception message to
        the client (it might contain internal info). Only CloudWatch
        logs get the full traceback via logger.exception.
        """
        def raise_runtime(**kw):
            raise RuntimeError("data inconsistent — pdf_s3_key missing")
        monkeypatch.setattr(handler, "get_story", raise_runtime)

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert body == {"error": "Internal server error"}
        # The internal detail must NOT be in the response
        assert "pdf_s3_key" not in resp["body"]


class TestEventParsing:
    """Handler defends against malformed or unexpected events."""

    def test_missing_path_parameters_returns_400(self, monkeypatch):
        # No need to patch get_story — handler must reject before calling it
        called = []
        monkeypatch.setattr(
            handler, "get_story",
            lambda **kw: called.append("should not be called"),
        )

        resp = handler.lambda_handler({"pathParameters": None}, None)

        assert resp["statusCode"] == 400
        assert called == []  # service was never invoked

    def test_missing_story_id_returns_400(self, monkeypatch):
        resp = handler.lambda_handler(
            {"pathParameters": {}}, None
        )
        assert resp["statusCode"] == 400

    def test_empty_event_returns_400(self):
        resp = handler.lambda_handler({}, None)
        assert resp["statusCode"] == 400


class TestResponseHeaders:
    def test_cors_headers_always_present(self, monkeypatch):
        """Every response (success or error) must carry CORS headers,
        or the browser will block it."""
        monkeypatch.setattr(handler, "get_story", lambda **kw: {
            "story_id": "abc", "status": "PROCESSING",
        })

        resp = handler.lambda_handler(_event("abc"), None)

        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "GET" in resp["headers"]["Access-Control-Allow-Methods"]

    def test_cors_headers_on_error_response(self, monkeypatch):
        resp = handler.lambda_handler({}, None)  # triggers 400

        assert resp["statusCode"] == 400
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"

class TestMyStoriesRoute:
    """Tests for the /my-stories handler route."""

    PARENT_ID = "cognito-sub-abc123"

    def _authed_event(self, kid_id=None):
        """Build an API Gateway event for /my-stories with a Bearer token."""
        event = {
            "resource": "/my-stories",
            "path": "/my-stories",
            "headers": {"Authorization": "Bearer valid.jwt.token"},
            "queryStringParameters": ({"kid_id": kid_id} if kid_id else None),
        }
        return event

    def test_authed_request_returns_stories(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "verify_jwt",
            lambda token: {"sub": self.PARENT_ID},
        )

        captured = {}
        def stub_list(**kwargs):
            captured.update(kwargs)
            return [{"story_id": "story-a", "status": "COMPLETE"}]

        monkeypatch.setattr(handler, "list_stories_for_parent", stub_list)

        response = handler.lambda_handler(self._authed_event(), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["stories"] == [{"story_id": "story-a", "status": "COMPLETE"}]
        assert captured["parent_id"] == self.PARENT_ID
        assert captured["kid_id"] is None

    def test_kid_id_query_param_passed_through(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "verify_jwt",
            lambda token: {"sub": self.PARENT_ID},
        )

        captured = {}
        def stub_list(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(handler, "list_stories_for_parent", stub_list)

        response = handler.lambda_handler(
            self._authed_event(kid_id="kid-uuid-001"), None
        )

        assert response["statusCode"] == 200
        assert captured["kid_id"] == "kid-uuid-001"

    def test_no_authorization_header_returns_401(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "list_stories_for_parent",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = {
            "resource": "/my-stories",
            "path": "/my-stories",
            "headers": {},  # no Authorization
        }
        response = handler.lambda_handler(event, None)
        assert response["statusCode"] == 401

    def test_invalid_jwt_returns_401(self, monkeypatch):
        import handler
        from auth import InvalidTokenError

        monkeypatch.setattr(
            handler, "verify_jwt",
            lambda token: (_ for _ in ()).throw(InvalidTokenError("expired")),
        )
        monkeypatch.setattr(
            handler, "list_stories_for_parent",
            lambda **k: pytest.fail("service should not be called"),
        )

        response = handler.lambda_handler(self._authed_event(), None)
        assert response["statusCode"] == 401

    def test_existing_story_route_still_works(self, monkeypatch):
        """Smoke test: adding /my-stories didn't break /story/{id}."""
        import handler

        monkeypatch.setattr(
            handler, "get_story",
            lambda **k: {
                "story_id": "test-id",
                "status": "PROCESSING",
                "created_at": "2026-04-30T10:00:00+00:00",
            },
        )

        event = {
            "resource": "/story/{story_id}",
            "path": "/story/test-id",
            "pathParameters": {"story_id": "test-id"},
        }
        response = handler.lambda_handler(event, None)

        assert response["statusCode"] == 202  # PROCESSING
        body = json.loads(response["body"])
        assert body["story_id"] == "test-id"