"""AWS Lambda entrypoint for pdf_assembly.

Invoked by Step Functions with the input from image_generation:
    {"story_id", "hero", "theme", "challenge", "strength",
     "pages": [...], "image_s3_keys": [...]}

Returns event + {"pdf_s3_key": "...", "status": "COMPLETE"}.

This is the last Lambda in the pipeline. After it runs:
    - The PDF sits in S3 at the deterministic key
    - The DynamoDB record is marked COMPLETE with pdf_s3_key
    - The retrieval Lambda will serve a pre-signed URL next time the
      frontend polls

Error handling:
    Exceptions bubble up. Step Functions catches them, marks the
    execution FAILED. A Fail state would (or could) update DDB to
    FAILED separately; we keep PROCESSING until the PDF is live
    to avoid "complete but missing artifact" races.
"""

import os

import boto3

from service import assemble_pdf


# Module-level caches — Lambda containers are reused across warm
# invocations, so building S3/DDB clients once per cold start saves
# meaningful latency (boto3 client init is non-trivial).
_S3_CLIENT = None
_DDB_TABLE = None
_BUCKET = None


def _get_s3_downloader():
    """Return a callable (key) -> bytes backed by real S3.

    Shared bucket with image_generation (PDFS_BUCKET) — one bucket,
    different key prefixes: stories/{id}/page_N.png vs. final.pdf.
    """
    global _S3_CLIENT, _BUCKET
    if _S3_CLIENT is None:
        _S3_CLIENT = boto3.client("s3")
        _BUCKET = os.environ["PDFS_BUCKET"]

    def download(key: str) -> bytes:
        response = _S3_CLIENT.get_object(Bucket=_BUCKET, Key=key)
        return response["Body"].read()

    return download


def _get_s3_uploader():
    """Return a callable (key, body, content_type) -> None backed by real S3."""
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


def _get_ddb_updater():
    """Return a callable (story_id, pdf_s3_key) -> None that sets
    status=COMPLETE + pdf_s3_key on the DDB record.

    Uses a DDB UpdateExpression so we don't overwrite the rest of
    the record (selections, created_at, ttl). `status` is a DDB
    reserved word, hence the ExpressionAttributeNames alias.
    """
    global _DDB_TABLE
    if _DDB_TABLE is None:
        dynamodb = boto3.resource("dynamodb")
        _DDB_TABLE = dynamodb.Table(os.environ["STORIES_TABLE"])

    def update(story_id: str, pdf_s3_key: str) -> None:
        _DDB_TABLE.update_item(
            Key={"story_id": story_id},
            UpdateExpression="SET #s = :complete, pdf_s3_key = :key",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":complete": "COMPLETE",
                ":key": pdf_s3_key,
            },
        )

    return update


def lambda_handler(event, context):
    """Step Functions entrypoint.

    Args:
        event:   from image_generation — see module docstring.
        context: AWS Lambda context (unused).

    Returns:
        event + {"pdf_s3_key": "...", "status": "COMPLETE"}.
    """
    pdf_key = assemble_pdf(
        story_id=event["story_id"],
        pages=event["pages"],
        image_s3_keys=event["image_s3_keys"],
        s3_downloader=_get_s3_downloader(),
        s3_uploader=_get_s3_uploader(),
        ddb_updater=_get_ddb_updater(),
    )
    return {**event, "pdf_s3_key": pdf_key, "status": "COMPLETE"}