"""Pure business logic for the entry Lambda.

Takes plain Python arguments, returns plain Python values. No AWS
event shapes here — that's handler.py's job.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Story records expire after 30 days via DynamoDB TTL. The frontend
# shows finished PDFs to users; after a month, the record (and the
# pre-signed URL contract) can be safely forgotten.
STORY_TTL_SECONDS = 30 * 24 * 60 * 60

# Schema-driven validation: the list of valid card selections lives in
# cards_schema.json, not in code. Product/content changes (e.g., adding
# a 5th theme, renaming a hero) require editing JSON and redeploying —
# no Python edit needed. Read once at cold start; the Lambda container
# is reused across invocations so we don't pay the disk cost per request.
_SCHEMA_PATH = Path(__file__).parent / "cards_schema.json"

def _load_schema(path: Path) -> dict:
    """Load and return the card schema dict from disk.

    Exists as a named function so tests can point at a tmp_path JSON
    to verify the validation logic is genuinely schema-agnostic —
    see test_schema_*_works_without_code_change.
    """
    with open(path) as f:
        return json.load(f)

# Valid card selections. Deliberately a whitelist — anything not in
# the schema is rejected, so a typo or rogue client can never reach
# the ML pipeline with malformed input.
VALID_SELECTIONS = _load_schema(_SCHEMA_PATH)

def validate_card_selections(body: dict) -> dict:
    """Validate the four card selections against the whitelist.

    Returns:
        The validated selections (subset of `body`, only the expected fields).

    Raises:
        ValueError: if body is not a dict, a field is missing, or a
                    value is not in the allowed set.
    """
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")

    selections = {}
    for field, allowed in VALID_SELECTIONS.items():
        if field not in body:
            raise ValueError(f"Missing required field: {field}")
        if body[field] not in allowed:
            raise ValueError(
                f"Invalid value for {field}: {body[field]!r}. "
                f"Must be one of {allowed}"
            )
        selections[field] = body[field]
    return selections


def create_story(
    body: dict,
    table,
    stepfunctions_client,
    state_machine_arn: str,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    id_fn: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> dict:
    """Create a story record and start the generation pipeline.

    Writes two things in sequence:
      1. A PROCESSING row in DynamoDB.
      2. A Step Functions execution that will walk the row through
         story → image → PDF, updating it to COMPLETE (or FAILED).

    Args:
        body:                  parsed JSON body from API Gateway.
        table:                 boto3 DynamoDB Table resource.
        stepfunctions_client:  boto3 Step Functions client.
        state_machine_arn:     ARN of the state machine to start.
        now_fn:                callable returning current UTC datetime.
                               Injectable so tests can freeze time.
        id_fn:                 callable returning a UUID string.
                               Injectable so tests get deterministic ids.

    Returns:
        {"story_id": str, "status": "PROCESSING"}

    Raises:
        ValueError: if card selections are invalid.

    Known limitation:
        If DynamoDB put_item succeeds but Step Functions start_execution
        fails, an orphaned PROCESSING record is left behind. It will
        expire via TTL after 30 days. For Capstone scope we accept
        this; production would add a cleanup job and a CloudWatch
        alarm on the mismatch.
    """
    selections = validate_card_selections(body)
    story_id = id_fn()
    now = now_fn()

    table.put_item(Item={
        "story_id": story_id,
        **selections,
        "status": "PROCESSING",
        "created_at": now.isoformat(),
        "ttl": int(now.timestamp()) + STORY_TTL_SECONDS,
    })

    stepfunctions_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=story_id,
        input=json.dumps({"story_id": story_id, **selections}),
    )

    return {"story_id": story_id, "status": "PROCESSING"}