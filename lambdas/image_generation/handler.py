"""AWS Lambda entrypoint for image_generation.

Input:  {"story_id", "hero", "theme", "adventure", "strength",
         "pages": [{"page_num", "text"}]}
Output: input + {"image_s3_keys": [...]}.

Env:
    IMAGES_BUCKET      — S3 bucket for page illustrations (CDK).
    OPENAI_SECRET_ARN  — Secrets Manager ARN (production); resolves to
                         OPENAI_API_KEY at cold start.
    OPENAI_API_KEY     — direct key (local dev only, via .env).
"""

import os

import boto3

from adapters import OpenAIImageAdapter
from service import generate_images


_ADAPTER = None
_S3_CLIENT = None
_BUCKET = None


def _ensure_api_key_loaded():
    """Fetch OPENAI_API_KEY from Secrets Manager if not already in env.

    Local dev: .env provides OPENAI_API_KEY — no-op.
    Lambda:    OPENAI_SECRET_ARN provided by CDK; we fetch and cache
               the real key into os.environ so openai.OpenAI() reads it
               through its standard env-var path.
    """
    if "OPENAI_API_KEY" in os.environ:
        return
    secret_arn = os.environ.get("OPENAI_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError(
            "Neither OPENAI_API_KEY nor OPENAI_SECRET_ARN is set."
        )
    sm = boto3.client("secretsmanager")
    response = sm.get_secret_value(SecretId=secret_arn)
    os.environ["OPENAI_API_KEY"] = response["SecretString"]


def _get_adapter():
    global _ADAPTER
    if _ADAPTER is None:
        _ensure_api_key_loaded()
        import openai
        client = openai.OpenAI()
        _ADAPTER = OpenAIImageAdapter(client=client)
    return _ADAPTER


def _get_s3_uploader():
    """Uploader bound to the IMAGES_BUCKET."""
    global _S3_CLIENT, _BUCKET
    if _S3_CLIENT is None:
        _S3_CLIENT = boto3.client("s3")
        _BUCKET = os.environ["IMAGES_BUCKET"]

    def upload(key: str, body: bytes, content_type: str) -> None:
        _S3_CLIENT.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    return upload


def lambda_handler(event, context):
    keys = generate_images(
        story_id=event["story_id"],
        hero=event["hero"],
        theme=event["theme"],
        pages=event["pages"],
        adapter=_get_adapter(),
        s3_uploader=_get_s3_uploader(),
    )
    return {**event, "image_s3_keys": keys}