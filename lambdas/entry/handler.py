"""AWS Lambda entry point for the entry Lambda.

Receives POST /generate with card selections, creates a story record,
and starts the generation pipeline. Thin — all business logic lives
in service.py.
"""

import json
import os

import boto3

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

    try:
        result = create_story(
            body=body,
            table=_table,
            stepfunctions_client=_stepfunctions,
            state_machine_arn=STATE_MACHINE_ARN,
        )
    except ValueError as e:
        logger.info("Validation failed: %s", e)
        return error_response(400, str(e))
    except Exception:
        logger.exception("Unexpected error creating story")
        return error_response(500, "Internal server error")

    return make_response(202, result)