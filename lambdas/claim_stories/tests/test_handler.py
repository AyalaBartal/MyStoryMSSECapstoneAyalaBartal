"""Tests for claim_stories handler.lambda_handler."""

import json

import pytest


PARENT_ID = "cognito-sub-parent-a"

VALID_BODY = {
    "claims": [
        {"story_id": "s1", "claim_token": "t1"},
    ]
}


def _authed_event(body=VALID_BODY):
    """Build an API Gateway event with a Bearer token."""
    return {
        "httpMethod": "POST",
        "headers": {"Authorization": "Bearer valid.jwt.token"},
        "body": json.dumps(body) if body is not None else None,
    }


@pytest.fixture(autouse=True)
def stub_auth(monkeypatch):
    """Replace verify_jwt with a stub returning a fixed sub.

    autouse so every test in this module bypasses real Cognito.
    Tests that exercise auth-failure paths override this.
    """
    import handler
    monkeypatch.setattr(
        handler, "verify_jwt",
        lambda token: {"sub": PARENT_ID, "email": "p@example.com"},
    )


class TestHappyPath:
    def test_returns_200_with_counts(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "claim_stories",
            lambda **kwargs: {"claimed": 2, "already": 1, "skipped": 0},
        )

        response = handler.lambda_handler(_authed_event(), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body == {"claimed": 2, "already": 1, "skipped": 0}

    def test_passes_parent_id_to_service(self, monkeypatch):
        import handler

        captured = {}
        def stub_claim(**kwargs):
            captured.update(kwargs)
            return {"claimed": 1, "already": 0, "skipped": 0}

        monkeypatch.setattr(handler, "claim_stories", stub_claim)

        handler.lambda_handler(_authed_event(), None)

        assert captured["parent_id"] == PARENT_ID
        assert captured["claims"] == VALID_BODY["claims"]

    def test_kid_id_passed_through_when_in_body(self, monkeypatch):
        import handler

        captured = {}
        def stub_claim(**kwargs):
            captured.update(kwargs)
            return {"claimed": 1, "already": 0, "skipped": 0}

        monkeypatch.setattr(handler, "claim_stories", stub_claim)

        body = {**VALID_BODY, "kid_id": "kid-uuid-abc"}
        handler.lambda_handler(_authed_event(body), None)

        assert captured["kid_id"] == "kid-uuid-abc"


class TestAuthHandling:
    def test_no_authorization_header_returns_401(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "claim_stories",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = {
            "httpMethod": "POST",
            "headers": {},
            "body": json.dumps(VALID_BODY),
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
            handler, "claim_stories",
            lambda **k: pytest.fail("service should not be called"),
        )

        response = handler.lambda_handler(_authed_event(), None)
        assert response["statusCode"] == 401


class TestErrorMapping:
    def test_validation_error_returns_400(self, monkeypatch):
        import handler

        def raise_value_error(**kwargs):
            raise ValueError("claims must be a list")

        monkeypatch.setattr(handler, "claim_stories", raise_value_error)

        response = handler.lambda_handler(_authed_event(), None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "claims must be a list" in body["error"]

    def test_unexpected_exception_returns_500(self, monkeypatch):
        import handler

        def raise_runtime(**kwargs):
            raise RuntimeError("DDB exploded")

        monkeypatch.setattr(handler, "claim_stories", raise_runtime)

        response = handler.lambda_handler(_authed_event(), None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "DDB" not in body["error"]


class TestEventParsing:
    def test_invalid_json_body_returns_400(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "claim_stories",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = _authed_event()
        event["body"] = "not json {"

        response = handler.lambda_handler(event, None)
        assert response["statusCode"] == 400

    def test_non_object_body_returns_400(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "claim_stories",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = _authed_event()
        event["body"] = json.dumps(["not", "an", "object"])

        response = handler.lambda_handler(event, None)
        assert response["statusCode"] == 400