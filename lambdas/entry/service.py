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
NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 30

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
    """Validate schema whitelists + the free-text name field.

    Returns:
        The validated selections — whitelist fields straight from the
        schema plus the stripped name.

    Raises:
        ValueError: if body isn't a dict, a whitelist field is missing
                    or invalid, or name is missing / not a string /
                    out of the allowed length range.
    """
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")

    selections = {}

    # Whitelist-validated fields (loaded from cards_schema.json).
    for field, allowed in VALID_SELECTIONS.items():
        if field not in body:
            raise ValueError(f"Missing required field: {field}")
        if body[field] not in allowed:
            raise ValueError(
                f"Invalid value for {field}: {body[field]!r}. "
                f"Must be one of {allowed}"
            )
        selections[field] = body[field]

    # Optional kid_id — links the story to a specific kid profile in
    # the kids table. Only meaningful for authed requests; for anonymous
    # requests it's ignored (the claim flow attaches kid_id later).
    if "kid_id" in body:
        kid_id = body["kid_id"]
        if not isinstance(kid_id, str) or not kid_id.strip():
            raise ValueError("kid_id must be a non-empty string")
        selections["kid_id"] = kid_id.strip()

    # Free-text name — whitespace-stripped, length-bounded.
    if "name" not in body:
        raise ValueError("Missing required field: name")
    name = body["name"]
    if not isinstance(name, str):
        raise ValueError("Name must be a string")
    name = name.strip()
    if len(name) < NAME_MIN_LENGTH or len(name) > NAME_MAX_LENGTH:
        raise ValueError(
            f"Name must be {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} characters"
        )
    selections["name"] = name

    return selections


def create_story(
    body: dict,
    table,
    stepfunctions_client,
    state_machine_arn: str,
    parent_id: str | None = None,
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
        parent_id:             Cognito sub of the signed-in parent, or
                               None for anonymous requests. When None,
                               we generate a claim_token so the parent
                               can retroactively claim the story by
                               signing in.
        now_fn:                callable returning current UTC datetime.
                               Injectable so tests can freeze time.
        id_fn:                 callable returning a UUID string.
                               Injectable so tests get deterministic ids.

    Returns:
        Authed:     {"story_id": str, "status": "PROCESSING"}
        Anonymous:  {"story_id": str, "status": "PROCESSING", "claim_token": str}

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

    # Build the DDB item. Ownership fields are added conditionally
    # because GSIs only include items where the indexed attribute
    # exists — adding parent_id=None would still index the row under
    # an empty string, which would corrupt the parent_id-index.
    item = {
        "story_id": story_id,
        **selections,
        "status": "PROCESSING",
        "created_at": now.isoformat(),
        "ttl": int(now.timestamp()) + STORY_TTL_SECONDS,
    }

    claim_token = None
    if parent_id:
        item["parent_id"] = parent_id
    else:
        # Anonymous: mint a claim_token so the parent can later sign
        # in and claim this story via POST /claim-stories.
        claim_token = id_fn()
        item["claim_token"] = claim_token

    table.put_item(Item=item)

    stepfunctions_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=story_id,
        input=json.dumps({"story_id": story_id, **selections}),
    )

    response = {"story_id": story_id, "status": "PROCESSING"}
    if claim_token:
        response["claim_token"] = claim_token
    return response