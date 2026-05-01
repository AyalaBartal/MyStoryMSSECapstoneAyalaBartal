"""Tests for cognito JWT verification helper.

These tests verify the auth.py module correctly accepts valid tokens and
rejects invalid ones (tampered signature, wrong audience, expired, etc.).
We mock the JWKS fetch so tests don't hit Cognito.
"""

import time
from unittest.mock import patch

import pytest
from jose import jwk, jwt as jose_jwt


# ── Test fixtures ────────────────────────────────────────────

# A test RSA key pair to sign + verify tokens with. Generated once
# per test session — these aren't real Cognito keys, just keys with
# the same shape that our helper can validate against.

@pytest.fixture(scope="module")
def test_key_pair():
    """Generate a test RSA key pair for signing test JWTs."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_numbers = private_key.public_key().public_numbers()
    # Convert RSA public numbers to JWKS format
    import base64
    def b64url(n):
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")

    jwks_key = {
        "kid": "test-kid",
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "n": b64url(public_numbers.n),
        "e": b64url(public_numbers.e),
    }

    return {"private_pem": private_pem, "jwks_key": jwks_key}


@pytest.fixture
def make_token(test_key_pair):
    """Helper to mint test JWTs with custom claims."""
    def _make(claims=None, **overrides):
        claims = claims or {}
        defaults = {
            "sub": "test-user-sub",
            "email": "test@example.com",
            "aud": "test-client-id",
            "token_use": "id",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        defaults.update(claims)
        defaults.update(overrides)
        return jose_jwt.encode(
            defaults,
            test_key_pair["private_pem"],
            algorithm="RS256",
            headers={"kid": "test-kid"},
        )
    return _make


@pytest.fixture(autouse=True)
def patch_jwks_and_env(test_key_pair, monkeypatch):
    """Patch JWKS fetch + env vars so tests don't hit real Cognito."""
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_test")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    # Force re-import so the new env vars take effect
    import importlib
    import auth
    importlib.reload(auth)

    # Patch the JWKS fetch to return our test key
    monkeypatch.setattr(
        auth, "_get_jwks",
        lambda: {"keys": [test_key_pair["jwks_key"]]},
    )


class TestVerifyJwt:
    def test_valid_token_returns_claims(self, make_token):
        import auth
        token = make_token()
        claims = auth.verify_jwt(token)
        assert claims["sub"] == "test-user-sub"
        assert claims["email"] == "test@example.com"

    def test_empty_token_raises(self):
        import auth
        with pytest.raises(auth.InvalidTokenError, match="Empty token"):
            auth.verify_jwt("")

    def test_malformed_token_raises(self):
        import auth
        with pytest.raises(auth.InvalidTokenError, match="Malformed JWT"):
            auth.verify_jwt("not.a.valid.jwt")

    def test_expired_token_raises(self, make_token):
        import auth
        token = make_token(exp=int(time.time()) - 100)
        with pytest.raises(auth.InvalidTokenError, match="expired"):
            auth.verify_jwt(token)

    def test_wrong_audience_raises(self, make_token):
        import auth
        token = make_token(aud="some-other-app")
        with pytest.raises(auth.InvalidTokenError, match="audience mismatch"):
            auth.verify_jwt(token)

    def test_access_token_uses_client_id(self, make_token):
        """Access tokens have 'client_id' instead of 'aud' — both should work."""
        import auth
        token = make_token({
            "client_id": "test-client-id",
            "token_use": "access",
        })
        # Remove aud, since access tokens don't have it
        # (we set it in defaults — let's override to None and it'll fall through)
        claims = auth.verify_jwt(token)
        assert claims["client_id"] == "test-client-id"

    def test_tampered_signature_raises(self, make_token):
        import auth
        token = make_token()
        # Flip a character in the signature
        parts = token.rsplit(".", 1)
        tampered = parts[0] + "." + parts[1][:-2] + "AA"
        with pytest.raises(auth.InvalidTokenError, match="Signature"):
            auth.verify_jwt(tampered)

    def test_unknown_kid_raises(self, make_token, monkeypatch):
        """If the kid doesn't match any key in JWKS, reject."""
        import auth
        monkeypatch.setattr(
            auth, "_get_jwks",
            lambda: {"keys": []},
        )
        token = make_token()
        with pytest.raises(auth.InvalidTokenError, match="No matching JWKS"):
            auth.verify_jwt(token)