"""Per-Lambda conftest — provides aws_mocks fixture for entry tests.

sys.path and env vars are handled by the root conftest.py so all
Lambdas' tests can run in one pytest session without module-name
collisions.
"""

import json

import boto3
import pytest
from moto import mock_aws


# Trivial state machine — entry only needs start_execution to succeed;
# the actual pipeline behavior doesn't matter for these tests.
_TRIVIAL_STATE_MACHINE = {
    "StartAt": "Pass",
    "States": {"Pass": {"Type": "Pass", "End": True}},
}


@pytest.fixture
def aws_mocks():
    """Spin up a mocked DynamoDB table and Step Functions state machine.

    Yields (table, sfn_client, state_machine_arn).
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

        sfn = boto3.client("stepfunctions")
        response = sfn.create_state_machine(
            name="test-pipeline",
            definition=json.dumps(_TRIVIAL_STATE_MACHINE),
            roleArn="arn:aws:iam::123456789012:role/DummyRole",
        )
        state_machine_arn = response["stateMachineArn"]

        yield table, sfn, state_machine_arn