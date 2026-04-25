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


class TestCreateStory:
    def test_happy_path_return_value(self, aws_mocks):
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        assert result == {"story_id": FIXED_ID, "status": "PROCESSING"}

    def test_writes_correct_dynamodb_item(self, aws_mocks):
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        item = table.get_item(Key={"story_id": FIXED_ID})["Item"]
        assert item["story_id"] == FIXED_ID
        assert item["hero"] == "girl"
        assert item["theme"] == "space"
        assert item["adventure"] == "talking_animal"
        assert item["age"] == "9"
        assert item["name"] == "Maya"
        assert item["status"] == "PROCESSING"
        assert item["created_at"] == "2026-04-22T10:00:00+00:00"
        assert int(item["ttl"]) == int(FIXED_NOW.timestamp()) + STORY_TTL_SECONDS

    def test_starts_step_functions_with_correct_input(self, aws_mocks):
        table, sfn, arn = aws_mocks

        create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        executions = sfn.list_executions(stateMachineArn=arn)["executions"]
        assert len(executions) == 1
        assert executions[0]["name"] == FIXED_ID

        details = sfn.describe_execution(
            executionArn=executions[0]["executionArn"]
        )
        assert json.loads(details["input"]) == {
            "story_id": FIXED_ID,
            "hero": "girl",
            "theme": "space",
            "adventure": "talking_animal",
            "age": "9",
            "name": "Maya",
        }

    def test_extra_body_fields_not_persisted(self, aws_mocks):
        table, sfn, arn = aws_mocks
        body = {**VALID_BODY, "injected": "malicious"}

        create_story(
            body=body, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
        )

        item = table.get_item(Key={"story_id": FIXED_ID})["Item"]
        assert "injected" not in item

    def test_invalid_body_raises_before_any_write(self, aws_mocks):
        table, sfn, arn = aws_mocks
        bad_body = {**VALID_BODY, "hero": "wizard"}

        with pytest.raises(ValueError):
            create_story(
                body=bad_body, table=table, stepfunctions_client=sfn,
                state_machine_arn=arn, now_fn=_fixed_now, id_fn=_fixed_id,
            )

        item = table.get_item(Key={"story_id": FIXED_ID}).get("Item")
        assert item is None
        assert sfn.list_executions(stateMachineArn=arn)["executions"] == []

    def test_default_now_and_id_work(self, aws_mocks):
        table, sfn, arn = aws_mocks

        result = create_story(
            body=VALID_BODY, table=table, stepfunctions_client=sfn,
            state_machine_arn=arn,
        )

        assert result["status"] == "PROCESSING"
        assert len(result["story_id"]) == 36
        item = table.get_item(Key={"story_id": result["story_id"]})["Item"]
        assert "ttl" in item
        assert "created_at" in item