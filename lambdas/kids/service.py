"""Pure business logic for the kids Lambda.

Manages kid profiles for authenticated parents. Keyed by:
  PK = parent_id (Cognito sub)
  SK = kid_id (UUID)
"""

import uuid
from datetime import datetime, timezone
from typing import Callable

# Validation bounds.
NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 30

# Birth year sanity check — anyone outside this range is almost
# certainly a typo or a tester. Update annually if needed.
BIRTH_YEAR_MIN = 2010
BIRTH_YEAR_MAX = datetime.now(timezone.utc).year


def _validate_name(name) -> str:
    if not isinstance(name, str):
        raise ValueError("name must be a string")
    name = name.strip()
    if len(name) < NAME_MIN_LENGTH or len(name) > NAME_MAX_LENGTH:
        raise ValueError(
            f"name must be {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} characters"
        )
    return name


def _validate_birth_year(birth_year) -> int:
    if not isinstance(birth_year, int):
        raise ValueError("birth_year must be an integer")
    if birth_year < BIRTH_YEAR_MIN or birth_year > BIRTH_YEAR_MAX:
        raise ValueError(
            f"birth_year must be between {BIRTH_YEAR_MIN} and {BIRTH_YEAR_MAX}"
        )
    return birth_year


def _validate_avatar_card_id(avatar_card_id) -> str:
    if not isinstance(avatar_card_id, str) or not avatar_card_id.strip():
        raise ValueError("avatar_card_id must be a non-empty string")
    return avatar_card_id.strip()


def create_kid(
    parent_id: str,
    body: dict,
    table,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    id_fn: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> dict:
    """Create a kid profile for the given parent.

    Args:
        parent_id:  Cognito sub from the verified JWT.
        body:       parsed JSON request body. Must contain name,
                    birth_year, avatar_card_id.
        table:      boto3 DynamoDB Table resource (kids table).
        now_fn:     callable returning current UTC datetime.
        id_fn:      callable returning a UUID string.

    Returns:
        The newly-created kid profile dict.

    Raises:
        ValueError: if any field is missing or invalid.
    """
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")

    name = _validate_name(body.get("name"))
    birth_year = _validate_birth_year(body.get("birth_year"))
    avatar_card_id = _validate_avatar_card_id(body.get("avatar_card_id"))

    kid_id = id_fn()
    created_at = now_fn().isoformat()

    item = {
        "parent_id": parent_id,
        "kid_id": kid_id,
        "name": name,
        "birth_year": birth_year,
        "avatar_card_id": avatar_card_id,
        "created_at": created_at,
    }

    table.put_item(Item=item)
    return item


def list_kids(parent_id: str, table) -> list:
    """List all kids for the given parent, sorted by created_at (newest first).

    Args:
        parent_id:  Cognito sub from the verified JWT.
        table:      boto3 DynamoDB Table resource (kids table).

    Returns:
        List of kid profile dicts. Empty list if the parent has no kids.
    """
    response = table.query(
        KeyConditionExpression="parent_id = :pid",
        ExpressionAttributeValues={":pid": parent_id},
    )
    items = response.get("Items", [])
    # Sort newest first. DynamoDB returns by SK (kid_id UUID) which has
    # no temporal meaning — we sort in app code.
    items.sort(key=lambda k: k.get("created_at", ""), reverse=True)
    return items


def delete_kid(parent_id: str, kid_id: str, table) -> None:
    """Delete a kid profile.

    Args:
        parent_id:  Cognito sub from the verified JWT.
        kid_id:     the kid's UUID.
        table:      boto3 DynamoDB Table resource.

    Raises:
        ValueError: if kid_id is empty or kid doesn't exist for this parent.

    Note:
        Stories tagged with this kid_id are NOT deleted — they keep their
        kid_id but the profile they reference is gone. The frontend's
        my-library page handles this gracefully (shows "Unknown kid").
    """
    if not isinstance(kid_id, str) or not kid_id.strip():
        raise ValueError("kid_id must be a non-empty string")

    # Conditional delete — fails if the row doesn't exist or belongs to
    # a different parent. Returns the deleted item if successful so we
    # can confirm the delete actually happened.
    # Check existence first via get_item — DynamoDB's delete_item with
    # ReturnValues="ALL_OLD" *should* return Attributes only when the
    # row existed, but moto's behavior here is inconsistent. Doing a
    # GET first is more portable and also makes the error path explicit.
    existing = table.get_item(
        Key={"parent_id": parent_id, "kid_id": kid_id}
    )
    if "Item" not in existing:
        raise ValueError(f"Kid not found: {kid_id}")

    table.delete_item(
        Key={"parent_id": parent_id, "kid_id": kid_id},
    )