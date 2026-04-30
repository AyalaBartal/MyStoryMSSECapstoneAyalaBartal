"""AWS Lambda entry point for the story_generation Lambda.

Receives card selections from Step Functions, calls the LLM via an adapter,
returns the structured 5-page story. Thin — all business logic lives in
service.py.
"""

import os
from typing import Optional

import boto3

from adapters import LLMAdapter, AnthropicLLMAdapter
from service import generate_story


# Module-level cached adapter and table — created once on cold start, reused
# on warm invocations. Tests override these by setting the module attributes
# directly (handler._ADAPTER = MockLLMAdapter(); handler._TABLE = stub).
_ADAPTER: Optional[LLMAdapter] = None
_TABLE = None

TABLE_NAME = os.environ["STORIES_TABLE"]
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
)


def _get_adapter() -> LLMAdapter:
    """Return the cached adapter, creating one on first call.

    Tests stub this by setting handler._ADAPTER to a MockLLMAdapter directly.
    """
    global _ADAPTER
    if _ADAPTER is None:
        bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
        _ADAPTER = AnthropicLLMAdapter(client=bedrock_client, model_id=MODEL_ID)
    return _ADAPTER


def _get_table():
    """Return the cached DynamoDB table resource, creating one on first call.

    Tests stub this by setting handler._TABLE to a stub object.
    """
    global _TABLE
    if _TABLE is None:
        _TABLE = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _TABLE


def _save_pages(story_id: str, pages: list) -> None:
    """Persist generated pages to DynamoDB and flip status to IMAGES_PENDING."""
    _get_table().update_item(
        Key={"story_id": story_id},
        UpdateExpression="SET pages = :pages, #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":pages": pages,
            ":status": "IMAGES_PENDING",
        },
    )


def lambda_handler(event, context):
    """Step Functions handler. Generates the story and returns the event
    plus a `pages` key.
    """
    selections = {
        "name": event["name"],
        "age": event["age"],
        "hero": event["hero"],
        "theme": event["theme"],
        "adventure": event["adventure"],
    }

    pages = generate_story(
        selections=selections,
        adapter=_get_adapter(),
    )

    _save_pages(event["story_id"], pages)

    return {**event, "pages": pages}