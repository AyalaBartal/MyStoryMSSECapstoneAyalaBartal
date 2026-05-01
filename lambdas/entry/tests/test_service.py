"""Unit tests for service.validate_card_selections and create_story."""

import json
from datetime import datetime, timezone

import pytest

import service
from service import (
    NAME_MAX_LENGTH,
    STORY_TTL_SECONDS,
    VALID_SELECTIONS,
    create_story,
    validate_card_selections,
)


VALID_BODY = {
    "hero": "girl",
    "theme": "space",
    "adventure": "talking_animal",
    "age": "9",
    "name": "Maya",
}

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
    def test_missing_whitelist_field_raises(self, field):
        body = {k: v for k, v in VALID_BODY.items() if k != field}
        with pytest.raises(
            ValueError, match=f"Missing required field: {field}"
        ):
            validate_card_selections(body)

    @pytest.mark.parametrize("field", list(VALID_SELECTIONS.keys()))
    def test_invalid_whitelist_value_raises(self, field):
        body = {**VALID_BODY, field: "bogus_value"}
        with pytest.raises(ValueError, match=f"Invalid value for {field}"):
            validate_card_selections(body)

    @pytest.mark.parametrize("bad_body", ["not a dict", [1, 2, 3], None, 42])
    def test_non_dict_body_raises(self, bad_body):
        with pytest.raises(ValueError, match="must be a JSON object"):
            validate_card_selections(bad_body)

    def test_missing_name_raises(self):
        body = {k: v for k, v in VALID_BODY.items() if k != "name"}
        with pytest.raises(ValueError, match="Missing required field: name"):
            validate_card_selections(body)

    def test_empty_name_raises(self):
        body = {**VALID_BODY, "name": "   "}
        with pytest.raises(ValueError, match=f"1-{NAME_MAX_LENGTH} characters"):
            validate_card_selections(body)

    def test_too_long_name_raises(self):
        body = {**VALID_BODY, "name": "x" * (NAME_MAX_LENGTH + 1)}
        with pytest.raises(ValueError, match=f"1-{NAME_MAX_LENGTH} characters"):
            validate_card_selections(body)

    def test_non_string_name_raises(self):
        body = {**VALID_BODY, "name": 42}
        with pytest.raises(ValueError, match="Name must be a string"):
            validate_card_selections(body)

    def test_name_whitespace_is_stripped(self):
        body = {**VALID_BODY, "name": "  Maya  "}
        result = validate_card_selections(body)
        assert result["name"] == "Maya"


class TestSchemaDriven:
    """Prove validate_card_selections is schema-agnostic for whitelist fields."""

    def test_schema_addition_works_without_code_change(self, monkeypatch):
        custom_schema = {
            **service.VALID_SELECTIONS,
            "mood": ["happy", "curious", "brave"],
        }
        monkeypatch.setattr(service, "VALID_SELECTIONS", custom_schema)

        body = {**VALID_BODY, "mood": "happy"}
        result = service.validate_card_selections(body)
        assert result["mood"] == "happy"

        with pytest.raises(ValueError, match="Missing required field: mood"):
            service.validate_card_selections(VALID_BODY)

        with pytest.raises(ValueError, match="Invalid value for mood"):
            service.validate_card_selections({**VALID_BODY, "mood": "angry"})

    def test_schema_removal_works_without_code_change(self, monkeypatch):
        custom_schema = {
            k: v for k, v in service.VALID_SELECTIONS.items() if k != "age"
        }
        monkeypatch.setattr(service, "VALID_SELECTIONS", custom_schema)

        body = {k: v for k, v in VALID_BODY.items() if k != "age"}
        result = service.validate_card_selections(body)
        assert "age" not in result
        assert result == body


class TestCreateStoryOwnership:
    """Tests for parent_id / claim_token ownership behavior added in Sprint 4."""

    def test_authed_request_saves_parent_id_and_no_claim_token(self, aws_mocks):
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn,
            parent_id="cognito-sub-abc123",
            now_fn=_fixed_now, id_fn=_fixed_id,
        )

        # Response: no claim_token for authed requests
        assert "claim_token" not in result

        # DDB row has parent_id, no claim_token
        item = table.get_item(Key={"story_id": result["story_id"]})["Item"]
        assert item["parent_id"] == "cognito-sub-abc123"
        assert "claim_token" not in item

    def test_anonymous_request_saves_claim_token_and_no_parent_id(self, aws_mocks):
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn,
            # parent_id deliberately omitted — defaults to None
            now_fn=_fixed_now, id_fn=_fixed_id,
        )

        # Response includes claim_token
        assert "claim_token" in result
        assert isinstance(result["claim_token"], str)

        # DDB row has claim_token, no parent_id
        item = table.get_item(Key={"story_id": result["story_id"]})["Item"]
        assert "parent_id" not in item
        assert item["claim_token"] == result["claim_token"]

    def test_authed_request_with_kid_id_saves_both(self, aws_mocks):
        table, sfn, arn = aws_mocks

        body_with_kid = {**VALID_BODY, "kid_id": "kid-uuid-xyz"}
        result = create_story(
            body=body_with_kid, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn,
            parent_id="cognito-sub-abc123",
            now_fn=_fixed_now, id_fn=_fixed_id,
        )
        item = table.get_item(Key={"story_id": result["story_id"]})["Item"]
        assert item["parent_id"] == "cognito-sub-abc123"
        assert item["kid_id"] == "kid-uuid-xyz"

    def test_invalid_kid_id_raises(self, aws_mocks):
        table, sfn, arn = aws_mocks

        body_with_bad_kid = {**VALID_BODY, "kid_id": ""}  # empty string
        with pytest.raises(ValueError, match="kid_id"):
            create_story(
                body=body_with_bad_kid, table=table, stepfunctions_client=sfn,
                state_machine_arn=arn,
                parent_id="cognito-sub-abc123",
                now_fn=_fixed_now, id_fn=_fixed_id,
            )

class TestCreateStory:
    """Tests for the core create_story flow: DDB write, Step Functions
    invocation, return value shape. Ownership-specific behavior is
    covered separately in TestCreateStoryOwnership."""

    def test_happy_path_return_value(self, aws_mocks):
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        # Anonymous flow: response includes story_id, status, and claim_token.
        assert result["story_id"] == FIXED_ID
        assert result["status"] == "PROCESSING"
        assert "claim_token" in result

    def test_ddb_item_has_expected_shape(self, aws_mocks):
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        item = table.get_item(Key={"story_id": FIXED_ID})["Item"]

        # Card selections + name copied verbatim from validated body.
        for field, value in VALID_BODY.items():
            assert item[field] == value

        # Status starts as PROCESSING.
        assert item["status"] == "PROCESSING"

        # created_at is the fixed-now ISO string.
        assert item["created_at"] == FIXED_NOW.isoformat()

    def test_ttl_is_30_days_from_now(self, aws_mocks):
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        item = table.get_item(Key={"story_id": FIXED_ID})["Item"]
        expected_ttl = int(FIXED_NOW.timestamp()) + STORY_TTL_SECONDS
        assert int(item["ttl"]) == expected_ttl

    def test_step_functions_started_with_story_id_as_execution_name(
        self, aws_mocks
    ):
        """The execution name must equal story_id so retrying the same
        story is idempotent — Step Functions rejects duplicate names."""
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        executions = sfn.list_executions(stateMachineArn=arn)["executions"]
        assert len(executions) == 1
        assert executions[0]["name"] == FIXED_ID

    def test_step_functions_input_includes_story_id_and_selections(
        self, aws_mocks
    ):
        """The pipeline downstream Lambdas need card selections + story_id
        in the Step Functions input payload."""
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        executions = sfn.list_executions(stateMachineArn=arn)["executions"]
        execution_arn = executions[0]["executionArn"]
        description = sfn.describe_execution(executionArn=execution_arn)
        payload = json.loads(description["input"])

        assert payload["story_id"] == FIXED_ID
        for field, value in VALID_BODY.items():
            assert payload[field] == value

    def test_invalid_body_raises_before_ddb_write(self, aws_mocks):
        """Validation runs first — a bad body must NOT leave a partial
        DDB row or a Step Functions execution behind."""
        table, sfn, arn = aws_mocks

        bad_body = {**VALID_BODY, "hero": "not_a_real_hero"}

        with pytest.raises(ValueError, match="Invalid value for hero"):
            create_story(
                body=bad_body, table=table, stepfunctions_client=sfn,
                state_machine_arn=arn,
                now_fn=_fixed_now, id_fn=_fixed_id,
            )

        # Nothing should have been written.
        result = table.scan()
        assert result["Count"] == 0

        executions = sfn.list_executions(stateMachineArn=arn)["executions"]
        assert len(executions) == 0