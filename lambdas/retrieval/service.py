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

# ── List my stories ──────────────────────────────────────────────────

# How many stories to return at most. Library page size; bigger than
# this and we should paginate via DDB LastEvaluatedKey.
MAX_STORIES_PER_LIST = 100


def list_stories_for_parent(
    parent_id: str,
    table,
    s3_client,
    bucket_name: str,
    kid_id: str | None = None,
    url_ttl_seconds: int = PRESIGNED_URL_TTL_SECONDS,
) -> list[dict]:
    """List a parent's stories, newest first.

    Args:
        parent_id:        Cognito sub of the requesting parent.
        table:            boto3 DynamoDB Table resource.
        s3_client:        boto3 S3 client for pre-signed URLs.
        bucket_name:      name of the S3 bucket storing finished PDFs.
        kid_id:           optional — return only stories for this kid.
                          When set, results are also filtered to ensure
                          they belong to parent_id (defense against URL
                          tampering / cross-tenant leakage).
        url_ttl_seconds:  pre-signed URL TTL for COMPLETE stories.

    Returns:
        List of story dicts. Each has the same shape get_story returns
        for that story's status — PROCESSING/COMPLETE/FAILED with a
        download_url field for COMPLETE.

    Notes:
        - Returns all states (PROCESSING, COMPLETE, FAILED). The frontend
          decides whether to hide any.
        - Sorted newest first by created_at.
        - Capped at MAX_STORIES_PER_LIST. Pagination would be a follow-up.
    """
    if kid_id is None:
        # Query the parent_id-index. Sort key is created_at, so reverse
        # ScanIndexForward gives newest-first directly from DDB.
        response = table.query(
            IndexName="parent_id-index",
            KeyConditionExpression="parent_id = :pid",
            ExpressionAttributeValues={":pid": parent_id},
            ScanIndexForward=False,  # newest first
            Limit=MAX_STORIES_PER_LIST,
        )
        items = response.get("Items", [])
    else:
        # Query the kid_id-index, then filter to ensure ownership.
        # Without this filter a parent could craft kid_id=<other-parent-kid>
        # and read another family's stories.
        response = table.query(
            IndexName="kid_id-index",
            KeyConditionExpression="kid_id = :kid",
            ExpressionAttributeValues={":kid": kid_id},
            ScanIndexForward=False,
            Limit=MAX_STORIES_PER_LIST,
        )
        items = [
            item for item in response.get("Items", [])
            if item.get("parent_id") == parent_id
        ]

    return [
        _build_list_payload(item, s3_client, bucket_name, url_ttl_seconds)
        for item in items
    ]


def _build_list_payload(
    item: dict, s3_client, bucket_name: str, url_ttl_seconds: int
) -> dict:
    """Project a DDB item into the public list payload.

    Same shape as get_story returns. We don't expose internal fields
    like ttl, claim_token, or pdf_s3_key.
    """
    story_id = item["story_id"]
    status = item.get("status", "UNKNOWN")
    payload = {
        "story_id": story_id,
        "status": status,
        "created_at": item.get("created_at"),
        # Card selections — useful for the library UI to show
        # "Maya's space adventure" without re-querying.
        "name": item.get("name"),
        "hero": item.get("hero"),
        "theme": item.get("theme"),
        "adventure": item.get("adventure"),
        "age": item.get("age"),
        "kid_id": item.get("kid_id"),
    }

    if status == "COMPLETE":
        pdf_key = item.get("pdf_s3_key")
        if pdf_key:
            # Don't raise on missing key here (unlike get_story) — a
            # corrupted single row shouldn't blow up the whole list.
            payload["download_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": pdf_key},
                ExpiresIn=url_ttl_seconds,
            )
            payload["expires_in"] = url_ttl_seconds
    elif status == "FAILED" and "error" in item:
        payload["error"] = item["error"]

    return payload