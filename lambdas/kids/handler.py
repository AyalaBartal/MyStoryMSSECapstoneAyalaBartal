"""AWS Lambda entry point for the kids Lambda.

Handles three routes for managing kid profiles:
  POST   /kids              → create
  GET    /kids              → list mine
  DELETE /kids/{kid_id}     → delete

All routes require a valid Cognito JWT in the Authorization header.
"""

import json
import os

import boto3

from auth import InvalidTokenError, extract_token_from_event, verify_jwt
from service import create_kid, delete_kid, list_kids
from utils import error_response, get_logger, make_response


logger = get_logger(__name__)

_dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["KIDS_TABLE"]
_table = _dynamodb.Table(TABLE_NAME)


def _resolve_parent_id(event: dict) -> str:
    """Extract and verify JWT, return the Cognito sub.

    Unlike entry Lambda's hybrid auth, kids endpoints REQUIRE auth.
    Missing or invalid token both raise InvalidTokenError.
    """
    token = extract_token_from_event(event)
    if token is None:
        raise InvalidTokenError("Authorization header missing")
    claims = verify_jwt(token)
    return claims["sub"]


def lambda_handler(event, context):
    """API Gateway handler — routes by HTTP method."""

    # All routes require auth. Reject early with a clean 401.
    try:
        parent_id = _resolve_parent_id(event)
    except InvalidTokenError as e:
        logger.info("Auth failed: %s", e)
        return error_response(401, "Authentication required")

    method = event.get("httpMethod", "").upper()

    try:
        if method == "POST":
            return _handle_create(event, parent_id)
        if method == "GET":
            return _handle_list(parent_id)
        if method == "DELETE":
            return _handle_delete(event, parent_id)
        return error_response(405, f"Method not allowed: {method}")
    except ValueError as e:
        logger.info("Validation failed: %s", e)
        return error_response(400, str(e))
    except Exception:
        logger.exception("Unexpected error in kids Lambda")
        return error_response(500, "Internal server error")


def _handle_create(event: dict, parent_id: str):
    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except (ValueError, TypeError):
        return error_response(400, "Request body must be valid JSON")

    kid = create_kid(parent_id=parent_id, body=body, table=_table)
    return make_response(201, kid)


def _handle_list(parent_id: str):
    kids = list_kids(parent_id=parent_id, table=_table)
    return make_response(200, {"kids": kids})


def _handle_delete(event: dict, parent_id: str):
    path_params = event.get("pathParameters") or {}
    kid_id = path_params.get("kid_id")
    if not kid_id:
        return error_response(400, "kid_id is required in path")

    delete_kid(parent_id=parent_id, kid_id=kid_id, table=_table)
    return make_response(204, {})