"""Unit tests for service.validate_card_selections and create_story."""

import json
from datetime import datetime, timezone

import pytest

from service import (
    STORY_TTL_SECONDS,
    VALID_SELECTIONS,
    create_story,
    validate_card_selections,
)


# A complete, valid card selection — the starting point for most tests.
VALID_BODY = {
    "hero": "girl",
    "theme": "space",
    "challenge": "asteroid",
    "strength": "super_smart",
}

# Injected fixed values so tests are deterministic.
FIXED_ID = "01234567-89ab-4def-89ab-0123456789ab"
FIXED_NOW = datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)


def _fixed_now():
    return FIXED_NOW


def _fixed_id():
    return FIXED_ID


class TestValidateCardSelections:
    def test_valid_body_returns_selections(self):
        assert validate_card_selections(VALID_BODY) == VALID_BODY

    def test_extra_fields_are_stripped(self):
        body = {**VALID_BODY, "injected": "malicious", "another": 42}
        result = validate_card_selections(body)
        assert result == VALID_BODY
        assert "injected" not in result

    @pytest.mark.parametrize("field", list(VALID_SELECTIONS.keys()))
    def test_missing_field_raises(self, field):
        body = {k: v for k, v in VALID_BODY.items() if k != field}
        with pytest.raises(
            ValueError, match=f"Missing required field: {field}"
        ):
            validate_card_selections(body)

    @pytest.mark.parametrize("field", list(VALID_SELECTIONS.keys()))
    def test_invalid_value_raises(self, field):
        body = {**VALID_BODY, field: "bogus_value"}
        with pytest.raises(ValueError, match=f"Invalid value for {field}"):
            validate_card_selections(body)

    @pytest.mark.parametrize("bad_body", ["not a dict", [1, 2, 3], None, 42])
    def test_non_dict_body_raises(self, bad_body):
        with pytest.raises(ValueError, match="must be a JSON object"):
            validate_card_selections(bad_body)


class TestCreateStory:
    def test_happy_path_return_value(self, aws_mocks):
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY,
            table=table,
            stepfunctions_client=sfn,
            state_machine_arn=arn,
            now_fn=_fixed_now,
            id_fn=_fixed_id,
        )

        assert result == {"story_id": FIXED_ID, "status": "PROCESSING"}

    def test_writes_correct_dynamodb_item(self, aws_mocks):
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY,
            table=table,
            stepfunctions_client=sfn,
            state_machine_arn=arn,
            now_fn=_fixed_now,
            id_fn=_fixed_id,
        )

        item = table.get_item(Key={"story_id": FIXED_ID})["Item"]
        assert item["story_id"] == FIXED_ID
        assert item["hero"] == "girl"
        assert item["theme"] == "space"
        assert item["challenge"] == "asteroid"
        assert item["strength"] == "super_smart"
        assert item["status"] == "PROCESSING"
        assert item["created_at"] == "2026-04-22T10:00:00+00:00"
        assert int(item["ttl"]) == int(FIXED_NOW.timestamp()) + STORY_TTL_SECONDS

    def test_starts_step_functions_with_correct_input(self, aws_mocks):
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY,
            table=table,
            stepfunctions_client=sfn,
            state_machine_arn=arn,
            now_fn=_fixed_now,
            id_fn=_fixed_id,
        )

        executions = sfn.list_executions(stateMachineArn=arn)["executions"]
        assert len(executions) == 1
        # Execution name equals story_id — natural idempotency guard.
        assert executions[0]["name"] == FIXED_ID

        details = sfn.describe_execution(
            executionArn=executions[0]["executionArn"]
        )
        assert json.loads(details["input"]) == {
            "story_id": FIXED_ID,
            "hero": "girl",
            "theme": "space",
            "challenge": "asteroid",
            "strength": "super_smart",
        }

    def test_extra_body_fields_not_persisted(self, aws_mocks):
        table, sfn, arn = aws_mocks
        body = {**VALID_BODY, "injected": "malicious"}

        create_story(
            body=body,
            table=table,
            stepfunctions_client=sfn,
            state_machine_arn=arn,
            now_fn=_fixed_now,
            id_fn=_fixed_id,
        )

        item = table.get_item(Key={"story_id": FIXED_ID})["Item"]
        assert "injected" not in item

        details = sfn.describe_execution(
            executionArn=sfn.list_executions(stateMachineArn=arn)[
                "executions"
            ][0]["executionArn"]
        )
        assert "injected" not in json.loads(details["input"])

    def test_invalid_body_raises_before_any_write(self, aws_mocks):
        table, sfn, arn = aws_mocks
        bad_body = {**VALID_BODY, "hero": "wizard"}  # not in whitelist

        with pytest.raises(ValueError):
            create_story(
                body=bad_body,
                table=table,
                stepfunctions_client=sfn,
                state_machine_arn=arn,
                now_fn=_fixed_now,
                id_fn=_fixed_id,
            )

        # Neither DB nor SFN should have received anything.
        item = table.get_item(Key={"story_id": FIXED_ID}).get("Item")
        assert item is None
        assert sfn.list_executions(stateMachineArn=arn)["executions"] == []

    def test_default_now_and_id_work(self, aws_mocks):
        """Sanity: defaults produce a UUID and real timestamp."""
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY,
            table=table,
            stepfunctions_client=sfn,
            state_machine_arn=arn,
        )

        assert result["status"] == "PROCESSING"
        assert len(result["story_id"]) == 36  # standard UUID string length
        item = table.get_item(Key={"story_id": result["story_id"]})["Item"]
        assert "ttl" in item
        assert "created_at" in item