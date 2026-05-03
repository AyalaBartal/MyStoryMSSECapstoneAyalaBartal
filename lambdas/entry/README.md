# Entry Lambda

Accepts card selections + name + age from the frontend, creates a story record in DynamoDB, and starts the Step Functions pipeline that turns those selections into a personalized PDF.

Supports **hybrid auth**: anonymous users can generate stories without an account, signed-in parents have stories tagged with their Cognito sub for later retrieval through the library.

## HTTP contract

**Route:** `POST /generate` (auth optional)

**Request body (JSON):**

```json
{
  "name":      "Ayala",
  "age":       "9",
  "hero":      "boy" | "girl",
  "theme":     "space" | "under_the_sea" | "medieval_fantasy" | "dinosaurs",
  "adventure": "secret_map" | "talking_animal" | "time_machine" | "magic_key",
  "kid_id":    "kid-uuid-optional"
}
```

The five card fields plus `name` are required. `kid_id` is optional — when provided by an authenticated request, links the story to a specific kid profile so it appears in that kid's library filter.

Values are validated against `cards_schema.json` (schema-driven validation — adding a new theme means editing one JSON file, not changing Python). Unknown extra fields are ignored (not persisted).

**Authorization (optional):**
- If the `Authorization: Bearer <jwt>` header is present and valid, the story is tagged with the parent's Cognito `sub` as `parent_id`.
- If absent, the story is anonymous and a random `claim_token` is minted and returned in the response so the parent can later claim it via `POST /claim-stories`.
- If the header is present but the token is invalid (expired, tampered, wrong audience), the request is rejected with 401 — better to reject than silently downgrade to anonymous.

**Responses:**

| Status | Shape | When |
|--------|-------|------|
| `202`  | `{ story_id, status: "PROCESSING" }` | Authed request — story tagged with `parent_id`. Client should poll `GET /story/{story_id}`. |
| `202`  | `{ story_id, status: "PROCESSING", claim_token }` | Anonymous request — `claim_token` saved on the story row so the parent can claim it later. |
| `400`  | `{ error: "Request body must be valid JSON" }` | Body wasn't parseable JSON. |
| `400`  | `{ error: "Missing required field: hero" }` etc. | Body was valid JSON but failed schema validation. |
| `401`  | `{ error: "Invalid or expired authentication token" }` | Authorization header was present but JWT verification failed. |
| `500`  | `{ error: "Internal server error" }` | Unexpected failure. Details only in CloudWatch. |

All responses include CORS headers for cross-origin calls from the static frontend.

## Environment variables

| Name                   | Required | Purpose |
|------------------------|----------|---------|
| `STORIES_TABLE`        | yes      | DynamoDB table name (hash key `story_id`). |
| `STATE_MACHINE_ARN`    | yes      | ARN of the Step Functions state machine to start. |
| `COGNITO_USER_POOL_ID` | yes      | For JWT verification when Authorization header is present. |
| `COGNITO_APP_CLIENT_ID`| yes      | For JWT audience validation. |
| `LOG_LEVEL`            | no       | `DEBUG`/`INFO`/`WARNING`/`ERROR`. Defaults to `INFO`. |

## IAM permissions required

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:PutItem` on the stories table (`grant_read_write_data`).
- `states:StartExecution` on the state machine (`grant_start_execution`).

JWT signature verification fetches the Cognito User Pool's JWKS over HTTPS (no IAM permission required — public endpoint). The verified `sub` claim is used directly as `parent_id`.

## File layout

```
entry/
├── __init__.py
├── handler.py         # AWS entry point — parses event, resolves auth, maps exceptions to HTTP
├── service.py         # pure business logic: validate → write → start pipeline
├── auth.py            # Cognito JWT verification (copy — see lambdas/README.md)
├── cards_schema.json  # whitelist of valid hero/theme/adventure/age values
├── utils.py           # inline helpers, Decimal-safe JSON encoder — NOT shared
├── requirements.txt   # boto3 + python-jose[cryptography]
├── README.md
└── tests/
    ├── __init__.py
    ├── conftest.py        # env vars + moto fixtures
    ├── test_service.py    # exercises service against moto DynamoDB + SFN
    ├── test_handler.py    # exercises handler with service mocked out
    └── test_auth.py       # JWT verification (valid + expired + tampered + wrong audience)
```

## Running the tests

From the repo root with `.venv` active:

```bash
pytest lambdas/entry/tests/ -v
```

36 tests covering schema validation, the create-story happy path, the anonymous claim_token mint, the authed parent_id flow, JWT verification, and the kid_id passthrough.

## Known operational limitations

**Partial-write window.** `create_story` writes to DynamoDB first, then starts the Step Functions execution. If the DynamoDB write succeeds but the Step Functions call fails (e.g. throttled, state machine paused), an orphaned `PROCESSING` record is left behind. It expires via the 30-day TTL. A production deployment would add a cleanup job + CloudWatch alarm on the mismatch.

**Dependency injection for `now` and `uuid`.** The service accepts `now_fn` and `id_fn` callables (default to real system calls) so tests can deterministically assert on timestamps and story IDs without monkeypatching the standard library.

**Frontend claim flow not yet wired.** Anonymous responses include a `claim_token` so a future-signed-in parent can claim past stories via `POST /claim-stories`. The frontend doesn't currently store these tokens to localStorage — the backend infrastructure is fully in place but the React side is documented as Sprint 5 work.