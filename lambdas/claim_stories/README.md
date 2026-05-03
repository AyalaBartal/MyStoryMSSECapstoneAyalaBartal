# claim_stories Lambda

Attaches previously-anonymous stories to a parent's account when they
sign in. Bridges the hybrid auth flow: a child generates a story
without an account → entry Lambda mints a `claim_token` → frontend
stores it in localStorage → on first sign-in the frontend POSTs all
stored claims here, and they get attached to the new account.

> **Status:** Backend deployed and tested (27 unit tests passing). Frontend
> integration is deferred — the React app does not yet write claim_tokens
> to localStorage or call this endpoint on sign-in. Documented as Sprint 5
> work in `PROJECT_PLAN.md`. The endpoint is fully functional and can be
> exercised via direct API calls.

## HTTP contract

**Route:** `POST /claim-stories` (auth required)

**Request body (JSON):**
```json
{
  "claims": [
    {"story_id": "uuid-1", "claim_token": "uuid-2"},
    {"story_id": "uuid-3", "claim_token": "uuid-4"}
  ],
  "kid_id": "kid-uuid-optional"
}
```

`claims` is required (1–50 items). `kid_id` is optional — when
provided, each claimed story is also assigned to that kid profile.

**Responses:**

| Status | Shape | When |
|---|---|---|
| 200 | `{ claimed: int, already: int, skipped: int }` | Done — counts of outcomes |
| 400 | `{ error }` | Body malformed (not JSON, invalid claim shape, list too long) |
| 401 | `{ error }` | Missing or invalid JWT |
| 500 | `{ error }` | Unexpected failure |

The response gives **aggregate counts**, not per-token status. Per-token
status would leak whether specific story_ids exist in the system.

- `claimed`: stories newly attached on this call
- `already`: stories that already belonged to this parent (no-op success)
- `skipped`: stories where the token didn't match — already claimed by
  someone else, story doesn't exist, or token tampered

## Atomicity

Each claim is a **conditional DynamoDB update**: parent_id is set ONLY
if claim_token currently matches. The same atomic op also REMOVEs
claim_token. This guarantees:
- A race between two simultaneous claims for the same token: only one wins
- A token can never be used twice
- A tampered token never updates anything

## Environment variables

| Name | Required | Purpose |
|---|---|---|
| `STORIES_TABLE` | yes | DynamoDB table (PK=story_id) |
| `COGNITO_USER_POOL_ID` | yes | For JWT verification |
| `COGNITO_APP_CLIENT_ID` | yes | For JWT verification |
| `LOG_LEVEL` | no | DEBUG/INFO/WARNING/ERROR (default INFO) |

## IAM permissions

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:UpdateItem`, `GetItem` on the stories table

## File layout

```
claim_stories/
├── handler.py        # AWS entry point — JWT + POST routing
├── service.py        # claim logic with conditional updates
├── auth.py           # JWT verification (copy from entry/)
├── utils.py          # CORS, logger, Decimal-safe JSON encoder (copy from entry/)
├── requirements.txt  # boto3 + python-jose[cryptography]
├── README.md
└── tests/
    ├── conftest.py
    ├── test_handler.py
    └── test_service.py
```

## Running the tests

From the repo root:

```bash
pytest lambdas/claim_stories/tests/ -v
```

27 tests covering input validation, the happy claim path, idempotency
(same parent re-claiming), and security boundaries (a parent cannot
claim another parent's story even if they guess the story_id).