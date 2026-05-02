"""Pure business logic for the claim_stories Lambda.

Attaches anonymous stories to a parent's account by setting parent_id
and clearing claim_token on the matching DynamoDB rows.

Idempotency: claiming an already-claimed story by the same parent is a
no-op success. Claiming a story that belongs to a different parent is
silently rejected (we don't tell the caller — that would leak whether
the story exists).
"""

# Maximum claims per request. localStorage realistically caps long
# before this; the limit guards against malicious payloads.
MAX_CLAIMS_PER_REQUEST = 50


def _validate_claims_payload(claims) -> list[dict]:
    """Validate the request body's `claims` field.

    Each claim must have `story_id` and `claim_token`, both non-empty
    strings. The function returns a clean list of well-formed claims;
    malformed entries raise ValueError.
    """
    if not isinstance(claims, list):
        raise ValueError("claims must be a list")
    if len(claims) == 0:
        raise ValueError("claims list cannot be empty")
    if len(claims) > MAX_CLAIMS_PER_REQUEST:
        raise ValueError(
            f"claims list cannot exceed {MAX_CLAIMS_PER_REQUEST} items"
        )

    cleaned = []
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"claims[{i}] must be an object")
        story_id = claim.get("story_id")
        claim_token = claim.get("claim_token")
        if not isinstance(story_id, str) or not story_id.strip():
            raise ValueError(f"claims[{i}].story_id must be a non-empty string")
        if not isinstance(claim_token, str) or not claim_token.strip():
            raise ValueError(
                f"claims[{i}].claim_token must be a non-empty string"
            )
        cleaned.append({
            "story_id": story_id.strip(),
            "claim_token": claim_token.strip(),
        })
    return cleaned


def claim_stories(
    parent_id: str,
    claims: list,
    table,
    kid_id: str | None = None,
) -> dict:
    """Attempt to claim each (story_id, claim_token) pair for parent_id.

    Args:
        parent_id:  Cognito sub from the verified JWT.
        claims:     list of {"story_id", "claim_token"} dicts.
        table:      boto3 DynamoDB Table resource.
        kid_id:     optional — if provided, also assign each claimed
                    story to this kid profile.

    Returns:
        {
          "claimed":  int  — newly attached this call
          "already":  int  — already belonged to this parent (no-op)
          "skipped":  int  — token mismatch or already claimed by someone else
        }

        We deliberately don't return per-token status. The frontend just
        treats the operation as best-effort and clears its localStorage.
        Per-token status would also leak whether story_ids exist.

    Raises:
        ValueError: if the claims payload is malformed.
    """
    cleaned = _validate_claims_payload(claims)

    # Optional kid_id validation — same shape as entry's kid_id rule.
    if kid_id is not None:
        if not isinstance(kid_id, str) or not kid_id.strip():
            raise ValueError("kid_id must be a non-empty string")
        kid_id = kid_id.strip()

    counts = {"claimed": 0, "already": 0, "skipped": 0}

    for claim in cleaned:
        outcome = _claim_one(
            parent_id=parent_id,
            story_id=claim["story_id"],
            claim_token=claim["claim_token"],
            kid_id=kid_id,
            table=table,
        )
        counts[outcome] += 1

    return counts


def _claim_one(
    parent_id: str,
    story_id: str,
    claim_token: str,
    kid_id: str | None,
    table,
) -> str:
    """Attempt to claim a single story. Returns "claimed" | "already" | "skipped"."""
    set_clauses = ["parent_id = :pid"]
    expr_values = {":pid": parent_id, ":token": claim_token}

    if kid_id is not None:
        set_clauses.append("kid_id = :kid")
        expr_values[":kid"] = kid_id

    update_expression = (
        "SET " + ", ".join(set_clauses) + " REMOVE claim_token"
    )

    try:
        table.update_item(
            Key={"story_id": story_id},
            UpdateExpression=update_expression,
            ConditionExpression="claim_token = :token",
            ExpressionAttributeValues=expr_values,
        )
        return "claimed"
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _classify_failed_claim(parent_id, story_id, table)


def _classify_failed_claim(parent_id: str, story_id: str, table) -> str:
    """When a conditional update fails, figure out why for accurate counting.

    Returns "already" if the story already belongs to this parent,
    otherwise "skipped" (token mismatch, story not found, or owned by
    another parent).
    """
    response = table.get_item(Key={"story_id": story_id})
    item = response.get("Item")
    if item is None:
        return "skipped"
    if item.get("parent_id") == parent_id:
        return "already"
    return "skipped"