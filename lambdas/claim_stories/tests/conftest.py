"""Test fixtures for the claim_stories Lambda.

Root conftest handles sys.path/sys.modules isolation. Here we just
set Lambda-specific env vars and provide a stories table fixture
that mirrors the production schema (with the GSIs, since the table
is the same physical table the retrieval Lambda uses).
"""

import os

import boto3
import pytest
from moto import mock_aws


# Env vars read at handler-import time.
os.environ.setdefault("STORIES_TABLE", "test-stories")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_test")
os.environ.setdefault("COGNITO_APP_CLIENT_ID", "test-client-id")


@pytest.fixture
def stories_table():
    """A moto-mocked stories table — schema mirrors storage_stack.py."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName="test-stories",
            KeySchema=[
                {"AttributeName": "story_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "story_id", "AttributeType": "S"},
                {"AttributeName": "parent_id", "AttributeType": "S"},
                {"AttributeName": "kid_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "parent_id-index",
                    "KeySchema": [
                        {"AttributeName": "parent_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "kid_id-index",
                    "KeySchema": [
                        {"AttributeName": "kid_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table