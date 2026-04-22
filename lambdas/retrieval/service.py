"""Pure business logic for the retrieval Lambda.

No AWS Lambda event shapes here — this module takes plain Python
arguments and returns plain Python values, so it can be unit tested
without mocking API Gateway.
"""

import uuid


# Pre-signed URL TTL. 15 minutes is long enough for a browser to
# click a download link without rushing; short enough that a leaked
# URL expires quickly.
PRESIGNED_URL_TTL_SECONDS = 15 * 60


class StoryNotFound(Exception):
    """Raised when the story_id does not exist in DynamoDB."""


def _validate_story_id(story_id: str) -> None:
    """Ensure story_id is a well-formed UUID.

    Defense in depth: API Gateway path params are already strings,
    but we don't want random input hitting DynamoDB or being echoed
    back in a response. UUID parsing raises on anything non-UUID.
    """
    try:
        uuid.UUID(story_id)
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"Invalid story_id: {story_id!r}") from e


def get_story(
    story_id: str,
    table,
    s3_client,
    bucket_name: str,
    url_ttl_seconds: int = PRESIGNED_URL_TTL_SECONDS,
) -> dict:
    """Look up a story by id and return its current state.

    Args:
        story_id:        UUID string identifying the story.
        table:           boto3 DynamoDB Table resource for the stories table.
        s3_client:       boto3 S3 client used to mint pre-signed URLs.
        bucket_name:     name of the S3 bucket storing finished PDFs.
        url_ttl_seconds: how long the pre-signed URL stays valid.

    Returns:
        A dict like::

            {
              "story_id": str,
              "status": "PROCESSING" | "COMPLETE" | "FAILED",
              "created_at": str | None,
              # When COMPLETE, also:
              "download_url": str,
              "expires_in": int,
              # When FAILED, also (optional):
              "error": str,
            }

    Raises:
        ValueError:     if story_id is not a valid UUID.
        StoryNotFound:  if no item exists for the given id.
        RuntimeError:   if the item is marked COMPLETE but has no pdf_s3_key
                        (indicates upstream pipeline bug).
    """
    _validate_story_id(story_id)

    response = table.get_item(Key={"story_id": story_id})
    item = response.get("Item")
    if item is None:
        raise StoryNotFound(story_id)

    status = item.get("status", "UNKNOWN")
    payload = {
        "story_id": story_id,
        "status": status,
        "created_at": item.get("created_at"),
    }

    if status == "COMPLETE":
        pdf_key = item.get("pdf_s3_key")
        if not pdf_key:
            raise RuntimeError(
                f"Story {story_id} marked COMPLETE but has no pdf_s3_key"
            )
        payload["download_url"] = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": pdf_key},
            ExpiresIn=url_ttl_seconds,
        )
        payload["expires_in"] = url_ttl_seconds

    elif status == "FAILED":
        # Surface the failure reason if the pipeline wrote one.
        if "error" in item:
            payload["error"] = item["error"]

    return payload