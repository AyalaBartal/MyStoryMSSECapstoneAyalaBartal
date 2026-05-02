"""AWS Lambda entry point for the entry Lambda.

Receives POST /generate with card selections, creates a story record,
and starts the generation pipeline. Thin — all business logic lives
in service.py.
"""

import json
import os

import boto3

from auth import InvalidTokenError, extract_token_from_event, verify_jwt
from service import create_story
from utils import error_response, get_logger, make_response


logger = get_logger(__name__)

# Module-level clients — created once in the Lambda init phase and
# reused across warm invocations.
_dynamodb = boto3.resource("dynamodb")
_stepfunctions = boto3.client("stepfunctions")

TABLE_NAME = os.environ["STORIES_TABLE"]
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

_table = _dynamodb.Table(TABLE_NAME)


def _resolve_parent_id(event: dict) -> str | None:
    """Return the Cognito sub if a valid JWT is attached, else None.

    Hybrid auth: anonymous requests are permitted (return None and let
    service.py mint a claim_token). A *present but invalid* token is
    treated as a hard failure — better to reject than silently downgrade
    a tampered token to anonymous, which would let a bad actor poison
    other users' libraries via a later claim.
    """
    token = extract_token_from_event(event)
    if token is None:
        return None
    claims = verify_jwt(token)  # raises InvalidTokenError if bad
    return claims["sub"]


def lambda_handler(event, context):
    """API Gateway handler for POST /generate."""

    # Parse the request body. API Gateway delivers it as a JSON string;
    # a missing/empty body comes in as None or "".
    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except (ValueError, TypeError):
        logger.info("Request body is not valid JSON")
        return error_response(400, "Request body must be valid JSON")

    # Resolve auth before validation so we can reject a bad token with
    # a clear 401 rather than letting it slide as anonymous.
    try:
        parent_id = _resolve_parent_id(event)
    except InvalidTokenError as e:
        logger.info("JWT verification failed: %s", e)
        return error_response(401, "Invalid or expired authentication token")

    try:
        result = create_story(
            body=body,
            table=_table,
            stepfunctions_client=_stepfunctions,
            state_machine_arn=STATE_MACHINE_ARN,
            parent_id=parent_id,
        )
    except ValueError as e:
        logger.info("Validation failed: %s", e)
        return error_response(400, str(e))
    except Exception:
        logger.exception("Unexpected error creating story")
        return error_response(500, "Internal server error")

    return make_response(202, result)