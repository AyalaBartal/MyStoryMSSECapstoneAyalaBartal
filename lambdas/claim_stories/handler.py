"""AWS Lambda entry point for the claim_stories Lambda.

POST /claim-stories — anonymous stories get attached to the signed-in
parent's account via their stored claim_tokens.

Required: valid Cognito JWT.
"""

import json
import os

import boto3

from auth import InvalidTokenError, extract_token_from_event, verify_jwt
from service import claim_stories
from utils import error_response, get_logger, make_response


logger = get_logger(__name__)

_dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["STORIES_TABLE"]
_table = _dynamodb.Table(TABLE_NAME)


def _resolve_parent_id(event: dict) -> str:
    """Extract and verify JWT, return the Cognito sub.

    Claim is auth-required — anonymous claims would let anyone steal
    stories by guessing tokens.
    """
    token = extract_token_from_event(event)
    if token is None:
        raise InvalidTokenError("Authorization header missing")
    claims = verify_jwt(token)
    return claims["sub"]


def lambda_handler(event, context):
    """API Gateway handler for POST /claim-stories."""

    try:
        parent_id = _resolve_parent_id(event)
    except InvalidTokenError as e:
        logger.info("Auth failed: %s", e)
        return error_response(401, "Authentication required")

    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except (ValueError, TypeError):
        return error_response(400, "Request body must be valid JSON")

    if not isinstance(body, dict):
        return error_response(400, "Request body must be a JSON object")

    try:
        result = claim_stories(
            parent_id=parent_id,
            claims=body.get("claims"),
            table=_table,
            kid_id=body.get("kid_id"),
        )
    except ValueError as e:
        logger.info("Validation failed: %s", e)
        return error_response(400, str(e))
    except Exception:
        logger.exception("Unexpected error claiming stories")
        return error_response(500, "Internal server error")

    return make_response(200, result)