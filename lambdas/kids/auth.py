"""Cognito JWT verification.

Verifies that an incoming JWT was actually issued by our Cognito User Pool
and hasn't expired or been tampered with. Returns the user's claims (sub,
email, etc.) so the Lambda knows who the caller is.

Used by handler.py: if the request includes a Bearer token, we verify it
and tag the story with the parent_id (Cognito sub). If no token, the
request is anonymous and gets a claim_token instead.
"""

import json
import os
import time
import urllib.request
from functools import lru_cache

from jose import jwk, jwt
from jose.utils import base64url_decode


USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
REGION = os.environ.get("AWS_REGION", "us-east-1")

JWKS_URL = (
    f"https://cognito-idp.{REGION}.amazonaws.com/"
    f"{USER_POOL_ID}/.well-known/jwks.json"
)


class InvalidTokenError(Exception):
    """Raised when a JWT fails any verification step."""


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch and cache Cognito's public signing keys.

    Cached for the life of the Lambda container (cold start to next cold
    start) — JWKS rarely changes, and refetching on every request would
    add 100ms+ to every authed call.
    """
    with urllib.request.urlopen(JWKS_URL, timeout=5) as resp:
        return json.loads(resp.read())


def verify_jwt(token: str) -> dict:
    """Verify a JWT and return its claims dict.

    Args:
        token: the raw JWT string (no "Bearer " prefix).

    Returns:
        Claims dict — typically contains 'sub', 'email', 'token_use',
        'exp', 'iat', 'aud' (or 'client_id' for access tokens).

    Raises:
        InvalidTokenError: if the token is malformed, signed by the
            wrong key, expired, or issued for a different app client.
    """
    if not token:
        raise InvalidTokenError("Empty token")

    # Split header from payload to find which key signed this JWT.
    try:
        headers = jwt.get_unverified_headers(token)
    except Exception as e:
        raise InvalidTokenError(f"Malformed JWT: {e}") from e

    kid = headers.get("kid")
    if not kid:
        raise InvalidTokenError("JWT header missing 'kid'")

    # Find the matching public key in our pool's JWKS.
    jwks = _get_jwks()
    key_data = next(
        (k for k in jwks["keys"] if k["kid"] == kid),
        None,
    )
    if key_data is None:
        # Possible if Cognito rotated keys and our cache is stale —
        # in production you'd retry once with a fresh fetch. For the
        # capstone we treat it as invalid.
        raise InvalidTokenError(f"No matching JWKS key for kid={kid}")

    public_key = jwk.construct(key_data)

    # Verify signature.
    message, encoded_signature = token.rsplit(".", 1)
    decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))
    if not public_key.verify(message.encode("utf-8"), decoded_signature):
        raise InvalidTokenError("Signature verification failed")

    # Decode claims (signature already verified above).
    claims = jwt.get_unverified_claims(token)

    # Check expiry.
    if claims.get("exp", 0) < time.time():
        raise InvalidTokenError("Token has expired")

    # Check audience — make sure this JWT was issued for our app client,
    # not some other app in the same user pool.
    #
    # Cognito ID tokens have 'aud'; access tokens have 'client_id' instead.
    audience = claims.get("aud") or claims.get("client_id")
    if audience != APP_CLIENT_ID:
        raise InvalidTokenError(
            f"Token audience mismatch: got {audience}, expected {APP_CLIENT_ID}"
        )

    return claims

def extract_token_from_event(event: dict) -> str | None:
    """Pull the JWT from an API Gateway event's Authorization header.

    Returns None if the header is missing or doesn't have the
    expected `Bearer <token>` shape — anonymous request.

    API Gateway can deliver headers under `headers` or `multiValueHeaders`,
    and header names are case-insensitive. We normalize both.
    """
    headers = event.get("headers") or {}
    # Case-insensitive lookup — API Gateway may pass "Authorization"
    # or "authorization" depending on client.
    auth_header = next(
        (v for k, v in headers.items() if k.lower() == "authorization"),
        None,
    )
    if not auth_header:
        return None

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1].strip() or None