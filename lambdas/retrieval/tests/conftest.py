"""Per-Lambda conftest — provides aws_mocks fixture for retrieval tests.

sys.path and env vars are handled by the root conftest.py so all
Lambdas' tests can run in one pytest session without module-name
collisions.
"""

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws_mocks():
    """Spin up a mocked DynamoDB table and S3 bucket for one test.

    Yields (table, s3_client, bucket_name).
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