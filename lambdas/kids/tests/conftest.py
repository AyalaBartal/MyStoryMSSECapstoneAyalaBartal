"""Test fixtures for the kids Lambda.

The repo-root conftest.py handles sys.path and sys.modules isolation
across Lambdas. We only need to supply local fixtures and pre-set env
vars specific to the kids Lambda.
"""

import os

import boto3
import pytest
from moto import mock_aws


# Env vars read at handler-import time. Root conftest sets the shared
# ones (AWS region, credentials); we add kids-specific ones here.
os.environ.setdefault("KIDS_TABLE", "test-kids")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_test")
os.environ.setdefault("COGNITO_APP_CLIENT_ID", "test-client-id")


@pytest.fixture
def kids_table():
    """A moto-mocked DynamoDB kids table with the right schema."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName="test-kids",
            KeySchema=[
                {"AttributeName": "parent_id", "KeyType": "HASH"},
                {"AttributeName": "kid_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "parent_id", "AttributeType": "S"},
                {"AttributeName": "kid_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table