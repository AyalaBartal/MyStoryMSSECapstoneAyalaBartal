"""AWS Lambda entrypoint for pdf_assembly.

Input:  {"story_id", "hero", "theme", "adventure", "strength",
         "pages": [...], "image_s3_keys": [...]}
Output: event + {"pdf_s3_key": "...", "status": "COMPLETE"}

Env:
    STORIES_TABLE  — DDB table (CDK).
    IMAGES_BUCKET  — where to read page illustrations.
    PDFS_BUCKET    — where to write the final PDF.

No API keys — pure Python ReportLab + AWS S3 + DDB.
"""

import os

import boto3

from service import assemble_pdf


_S3_CLIENT = None
_DDB_TABLE = None
_IMAGES_BUCKET = None
_PDFS_BUCKET = None


def _get_s3_downloader():
    """Downloader bound to IMAGES_BUCKET (reads page illustrations)."""
    global _S3_CLIENT, _IMAGES_BUCKET
    if _S3_CLIENT is None:
        _S3_CLIENT = boto3.client("s3")
    if _IMAGES_BUCKET is None:
        _IMAGES_BUCKET = os.environ["IMAGES_BUCKET"]

    def download(key: str) -> bytes:
        response = _S3_CLIENT.get_object(Bucket=_IMAGES_BUCKET, Key=key)
        return response["Body"].read()

    return download


def _get_s3_uploader():
    """Uploader bound to PDFS_BUCKET (writes the final PDF)."""
    global _S3_CLIENT, _PDFS_BUCKET
    if _S3_CLIENT is None:
        _S3_CLIENT = boto3.client("s3")
    if _PDFS_BUCKET is None:
        _PDFS_BUCKET = os.environ["PDFS_BUCKET"]

    def upload(key: str, body: bytes, content_type: str) -> None:
        _S3_CLIENT.put_object(
            Bucket=_PDFS_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    return upload


def _get_ddb_updater():
    """Flips the record status=COMPLETE + stores pdf_s3_key."""
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
    # Fetch the theme card image as cover background — silent fallback to
    # plain cream cover if the bucket read fails for any reason.
    cover_bytes = b""
    theme = event.get("theme", "")
    if theme:
        try:
            import boto3
            s3 = boto3.client("s3")
            resp = s3.get_object(
                Bucket="my-story-cards-691304835962",
                Key=f"cards/theme/{theme}.png",
            )
            cover_bytes = resp["Body"].read()
        except Exception:
            cover_bytes = b""

    pdf_key = assemble_pdf(
        story_id=event["story_id"],
        pages=event["pages"],
        image_s3_keys=event["image_s3_keys"],
        age=event["age"],
        name=event.get("name", ""),
        theme=theme,
        cover_image_bytes=cover_bytes,
        s3_downloader=_get_s3_downloader(),
        s3_uploader=_get_s3_uploader(),
        ddb_updater=_get_ddb_updater(),
    )
    return {**event, "pdf_s3_key": pdf_key, "status": "COMPLETE"}