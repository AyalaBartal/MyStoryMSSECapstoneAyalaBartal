"""AWS Lambda entry point for the retrieval Lambda.

Handles two routes:
  GET /story/{story_id}                     — public, returns one story
  GET /my-stories[?kid_id=...]              — authed, returns parent's library

Kept intentionally thin: parses the event, routes by path, calls service,
maps results and exceptions to HTTP responses. All business logic lives
in service.py so it can be unit tested without AWS event shapes.
"""

import os

import boto3

from auth import InvalidTokenError, extract_token_from_event, verify_jwt
from service import (
    StoryNotFound,
    get_story,
    list_stories_for_parent,
)
from utils import error_response, get_logger, make_response


logger = get_logger(__name__)

_dynamodb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")

TABLE_NAME = os.environ["STORIES_TABLE"]
PDFS_BUCKET = os.environ["PDFS_BUCKET"]

_table = _dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    """API Gateway handler — routes by path."""
    resource = event.get("resource") or event.get("path") or ""

    try:
        if "my-stories" in resource:
            return _handle_list_my_stories(event)
        # Default: GET /story/{story_id}
        return _handle_get_story(event)
    except Exception:
        logger.exception("Unexpected error in retrieval Lambda")
        return error_response(500, "Internal server error")


# ── /story/{story_id} ────────────────────────────────────────────────

def _handle_get_story(event):
    """Public route — returns one story by ID. No auth required."""
    path_params = event.get("pathParameters") or {}
    story_id = path_params.get("story_id")

    if not story_id:
        logger.warning("Missing story_id in path parameters")
        return error_response(400, "Missing story_id")

    try:
        result = get_story(
            story_id=story_id,
            table=_table,
            s3_client=_s3,
            bucket_name=PDFS_BUCKET,
        )
    except ValueError as e:
        logger.info("Invalid story_id request: %s", e)
        return error_response(400, str(e))
    except StoryNotFound:
        logger.info("Story not found: %s", story_id)
        return error_response(404, "Story not found")

    status_code = 202 if result["status"] == "PROCESSING" else 200
    return make_response(status_code, result)


# ── /my-stories ──────────────────────────────────────────────────────

def _handle_list_my_stories(event):
    """Authed route — returns the parent's library."""
    try:
        parent_id = _resolve_parent_id(event)
    except InvalidTokenError as e:
        logger.info("Auth failed for /my-stories: %s", e)
        return error_response(401, "Authentication required")

    # Optional ?kid_id=... query param.
    qs = event.get("queryStringParameters") or {}
    kid_id = qs.get("kid_id")
    if kid_id is not None:
        kid_id = kid_id.strip() or None  # treat empty string as no filter

    stories = list_stories_for_parent(
        parent_id=parent_id,
        table=_table,
        s3_client=_s3,
        bucket_name=PDFS_BUCKET,
        kid_id=kid_id,
    )

    return make_response(200, {"stories": stories})


def _resolve_parent_id(event: dict) -> str:
    """Extract and verify JWT, return the Cognito sub.

    /my-stories REQUIRES auth — missing or invalid both raise.
    """
    token = extract_token_from_event(event)
    if token is None:
        raise InvalidTokenError("Authorization header missing")
    claims = verify_jwt(token)
    return claims["sub"]