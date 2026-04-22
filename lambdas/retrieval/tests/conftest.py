"""Pytest configuration for retrieval Lambda tests.

- Adds the Lambda package root to sys.path so `import handler`,
  `import service`, `import utils` work the same way they do at
  runtime (where AWS Lambda puts the Lambda folder on sys.path).
- Sets env vars that handler.py reads at import time, before any
  test module collects.
- Provides a moto fixture that spins up a fake DynamoDB table and
  S3 bucket so service tests can run against realistic AWS behavior
  without touching real AWS.
"""

import os
import sys
from pathlib import Path

# Make `import handler`, `import service`, `import utils` work.
# parent = tests/, parent.parent = lambdas/retrieval/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Env vars that handler.py reads at import time. Set BEFORE any test
# imports handler, or importing handler will KeyError.
os.environ.setdefault("STORIES_TABLE", "test-stories")
os.environ.setdefault("PDFS_BUCKET", "test-pdfs")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
# moto also looks for AWS credentials — dummy ones avoid accidental
# real-AWS calls if a test ever escapes the mock.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")


import boto3  # noqa: E402  — must come after env vars are set
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402


@pytest.fixture
def aws_mocks():
    """Spin up a mocked DynamoDB table and S3 bucket for one test.

    Yields (table, s3_client, bucket_name). Each test gets a fresh,
    empty table and bucket — moto tears everything down when the
    `with` block exits, so tests don't leak state into each other.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.create_table(
            TableName="test-stories",
            KeySchema=[{"AttributeName": "story_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "story_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="test-pdfs")

        yield table, s3, "test-pdfs"