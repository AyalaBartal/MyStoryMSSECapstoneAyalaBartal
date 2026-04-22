"""AWS Lambda entry point for the retrieval Lambda.

Kept intentionally thin: parses the event, calls service.get_story,
maps results and exceptions to HTTP responses. All business logic
lives in service.py so it can be unit tested without AWS event shapes.
"""

import os

import boto3

from service import StoryNotFound, get_story
from utils import error_response, get_logger, make_response


logger = get_logger(__name__)

# Module-level AWS clients are reused across warm invocations.
# Creating them at import time keeps cold-start work in the Lambda
# init phase (which AWS measures and bills separately) rather than
# on every request.
_dynamodb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")

TABLE_NAME = os.environ["STORIES_TABLE"]
PDFS_BUCKET = os.environ["PDFS_BUCKET"]

_table = _dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    """API Gateway handler for GET /story/{story_id}."""

    # API Gateway guarantees story_id is in the path (routing wouldn't
    # match otherwise), but we still defensively read it.
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
        # Malformed story_id — 400
        logger.info("Invalid story_id request: %s", e)
        return error_response(400, str(e))
    except StoryNotFound:
        logger.info("Story not found: %s", story_id)
        return error_response(404, "Story not found")
    except Exception:
        # Catch-all. We log full details to CloudWatch but never
        # leak them to the client.
        logger.exception("Unexpected error retrieving story %s", story_id)
        return error_response(500, "Internal server error")

    # Map status to HTTP status code. Body shape is identical for
    # PROCESSING/COMPLETE — the frontend branches on status.
    status_code = 202 if result["status"] == "PROCESSING" else 200
    return make_response(status_code, result)