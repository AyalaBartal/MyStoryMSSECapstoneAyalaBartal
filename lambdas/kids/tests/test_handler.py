"""Tests for kids handler.lambda_handler.

Stubs out service functions and auth.verify_jwt to test the handler's
own responsibilities: routing by HTTP method, JWT extraction, error
mapping, response shaping.
"""

import json

import pytest


PARENT_ID = "cognito-sub-abc123"

VALID_KID = {
    "name": "Maya",
    "birth_year": 2018,
    "avatar_card_id": "girl_brown_hair",
}

CREATED_KID = {
    "parent_id": PARENT_ID,
    "kid_id": "kid-uuid-001",
    "name": "Maya",
    "birth_year": 2018,
    "avatar_card_id": "girl_brown_hair",
    "created_at": "2026-04-30T10:00:00+00:00",
}


def _authed_event(method="POST", body=None, path_params=None):
    """Build an API Gateway event with a valid Authorization header."""
    event = {
        "httpMethod": method,
        "headers": {"Authorization": "Bearer valid.jwt.token"},
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path_params,
    }
    return event


@pytest.fixture(autouse=True)
def stub_auth(monkeypatch):
    """Replace verify_jwt with a stub that returns a fixed sub.

    autouse=True so every test in this module is isolated from real
    Cognito JWT verification. Tests that want to exercise auth-failure
    paths override this with a different stub.
    """
    import handler
    monkeypatch.setattr(
        handler, "verify_jwt",
        lambda token: {"sub": PARENT_ID, "email": "p@example.com"},
    )


class TestRouting:
    def test_post_routes_to_create(self, monkeypatch):
        import handler

        captured = {}
        def stub_create(**kwargs):
            captured.update(kwargs)
            return CREATED_KID

        monkeypatch.setattr(handler, "create_kid", stub_create)

        response = handler.lambda_handler(
            _authed_event(method="POST", body=VALID_KID), None
        )

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["kid_id"] == "kid-uuid-001"
        assert captured["parent_id"] == PARENT_ID
        assert captured["body"] == VALID_KID

    def test_get_routes_to_list(self, monkeypatch):
        import handler

        captured = {}
        def stub_list(**kwargs):
            captured.update(kwargs)
            return [CREATED_KID]

        monkeypatch.setattr(handler, "list_kids", stub_list)

        response = handler.lambda_handler(_authed_event(method="GET"), None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["kids"] == [CREATED_KID]
        assert captured["parent_id"] == PARENT_ID

    def test_delete_routes_to_delete(self, monkeypatch):
        import handler

        captured = {}
        def stub_delete(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(handler, "delete_kid", stub_delete)

        response = handler.lambda_handler(
            _authed_event(
                method="DELETE",
                path_params={"kid_id": "kid-uuid-001"},
            ),
            None,
        )

        assert response["statusCode"] == 204
        assert captured["parent_id"] == PARENT_ID
        assert captured["kid_id"] == "kid-uuid-001"

    def test_unknown_method_returns_405(self, monkeypatch):
        import handler

        response = handler.lambda_handler(
            _authed_event(method="PATCH"), None
        )

        assert response["statusCode"] == 405


class TestAuthHandling:
    def test_no_authorization_header_returns_401(self, monkeypatch):
        import handler

        # No service call should happen.
        monkeypatch.setattr(
            handler, "create_kid",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = {
            "httpMethod": "POST",
            "headers": {},  # no Authorization
            "body": json.dumps(VALID_KID),
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
            handler, "create_kid",
            lambda **k: pytest.fail("service should not be called"),
        )

        response = handler.lambda_handler(
            _authed_event(method="POST", body=VALID_KID), None
        )
        assert response["statusCode"] == 401


class TestErrorMapping:
    def test_value_error_returns_400(self, monkeypatch):
        import handler

        def raise_value_error(**kwargs):
            raise ValueError("name must be a string")

        monkeypatch.setattr(handler, "create_kid", raise_value_error)

        response = handler.lambda_handler(
            _authed_event(method="POST", body={}), None
        )
        assert response["statusCode"] == 400

    def test_unexpected_exception_returns_500(self, monkeypatch):
        import handler

        def raise_runtime_error(**kwargs):
            raise RuntimeError("DDB is on fire")

        monkeypatch.setattr(handler, "create_kid", raise_runtime_error)

        response = handler.lambda_handler(
            _authed_event(method="POST", body=VALID_KID), None
        )
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        # Don't leak internal details.
        assert "DDB" not in body["error"]


class TestEventParsing:
    def test_invalid_json_body_returns_400(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "create_kid",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = _authed_event(method="POST")
        event["body"] = "not json {"

        response = handler.lambda_handler(event, None)
        assert response["statusCode"] == 400

    def test_delete_without_path_kid_id_returns_400(self, monkeypatch):
        import handler

        monkeypatch.setattr(
            handler, "delete_kid",
            lambda **k: pytest.fail("service should not be called"),
        )

        event = _authed_event(method="DELETE", path_params={})
        response = handler.lambda_handler(event, None)
        assert response["statusCode"] == 400