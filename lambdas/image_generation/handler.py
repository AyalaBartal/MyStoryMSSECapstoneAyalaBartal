"""AWS Lambda entrypoint for image_generation.

Invoked by Step Functions with the input from story_generation:
    {"story_id", "hero", "theme", "challenge", "strength",
     "pages": [{"page_num", "text"}, ...]}

Returns the input dict plus "image_s3_keys": [5 keys] — preserving
all input keys so the next step (pdf_assembly) has what it needs.

Error handling:
    Exceptions bubble up. Step Functions catches them and marks the
    execution FAILED. This Lambda doesn't try/except — swallowing
    errors would hide real production issues from CloudWatch alarms.
"""

import os

import boto3

from adapters import OpenAIImageAdapter
from service import generate_images


# Module-level cache — Lambda containers are reused across invocations,
# so building the OpenAI client + S3 client once per cold start saves
# meaningful latency per warm call.
_ADAPTER = None
_S3_CLIENT = None
_BUCKET = None


def _get_adapter():
    """Lazily build the image adapter on first call, cache for reuse.

    Deferred import of `openai` so the module loads fast at cold start.
    Tests monkeypatch this to return a MockImageAdapter and stay offline.
    """
    global _ADAPTER
    if _ADAPTER is None:
        import openai
        client = openai.OpenAI()  # reads OPENAI_API_KEY
        _ADAPTER = OpenAIImageAdapter(client=client)
    return _ADAPTER


def _get_s3_uploader():
    """Return a callable (key, body, content_type) -> None bound to the
    S3 client and target bucket.

    Wrapping boto3 in a simple callable shape means service.py never
    imports boto3 — all AWS coupling lives right here.
    """
    global _S3_CLIENT, _BUCKET
    if _S3_CLIENT is None:
        _S3_CLIENT = boto3.client("s3")
        _BUCKET = os.environ["PDFS_BUCKET"]

    def upload(key: str, body: bytes, content_type: str) -> None:
        _S3_CLIENT.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    return upload


def lambda_handler(event, context):
    """Step Functions entrypoint.

    Args:
        event:   from story_generation — see module docstring.
        context: AWS Lambda context (unused).

    Returns:
        event + {"image_s3_keys": [...]} — input keys pass through.
    """
    keys = generate_images(
        story_id=event["story_id"],
        hero=event["hero"],
        theme=event["theme"],
        pages=event["pages"],
        adapter=_get_adapter(),
        s3_uploader=_get_s3_uploader(),
    )
    return {**event, "image_s3_keys": keys}