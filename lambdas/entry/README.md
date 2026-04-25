# Entry Lambda

Accepts card selections from the frontend, creates a story record in DynamoDB, and starts the Step Functions pipeline that turns those selections into a personalized PDF.

## HTTP contract

**Route:** `POST /generate`

**Request body (JSON):**

```json
{
  "hero":      "boy" | "girl",
  "theme":     "space" | "under_the_sea" | "medieval_fantasy" | "dinosaurs",
  "adventure": "asteroid" | "wizard_witch" | "dragon" | "volcano",
  "strength":  "super_strong" | "friendship" | "super_smart" | "super_speed"
}
```

All four fields are required. Values are whitelisted — anything else is rejected with 400. Unknown extra fields are ignored (not persisted).

**Responses:**

| Status | Shape | When |
|--------|-------|------|
| `202`  | `{ story_id, status: "PROCESSING" }` | Story row written, pipeline started. Client should poll `GET /story/{story_id}`. |
| `400`  | `{ error: "Request body must be valid JSON" }` | Body wasn't parseable JSON. |
| `400`  | `{ error: "Missing required field: hero" }` etc. | Body was valid JSON but failed validation. |
| `500`  | `{ error: "Internal server error" }` | Unexpected failure. Details only in CloudWatch. |

All responses include CORS headers for cross-origin calls from the static frontend.

## Environment variables

| Name                 | Required | Purpose |
|----------------------|----------|---------|
| `STORIES_TABLE`      | yes      | DynamoDB table name (hash key `story_id`). |
| `STATE_MACHINE_ARN`  | yes      | ARN of the Step Functions state machine to start. |
| `LOG_LEVEL`          | no       | `DEBUG`/`INFO`/`WARNING`/`ERROR`. Defaults to `INFO`. |

## IAM permissions required

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:PutItem` on the stories table (`grant_read_write_data`).
- `states:StartExecution` on the state machine (`grant_start_execution`).

## File layout
```
entry/
    ├── init.py
    ├── handler.py        # AWS entry point — parses event, maps exceptions to HTTP
    ├── service.py        # pure business logic: validate → write → start pipeline
    ├── utils.py          # inline helpers — NOT shared, see lambdas/README.md
    ├── requirements.txt  # runtime deps (just boto3)
    └── tests/
        ├── init.py
        ├── conftest.py       # sys.path + env vars + moto fixtures
        ├── test_service.py   # exercises service against moto DynamoDB + SFN
        └── test_handler.py   # exercises handler with service mocked out
```

## Running the tests

From the repo root with `.venv` active:

```bash
pytest lambdas/entry/tests/ -v
```

## Known operational limitations

**Partial-write window.** `create_story` writes to DynamoDB first, then starts the Step Functions execution. If the DynamoDB write succeeds but Step Functions call fails (e.g. throttled, state machine paused), an orphaned `PROCESSING` record is left behind. It expires via the 30-day TTL. A production deployment would add a cleanup job + CloudWatch alarm on the mismatch; out of scope for the Capstone.

**Dependency injection for `now` and `uuid`.** The service accepts `now_fn` and `id_fn` callables (default to real system calls) so tests can deterministically assert on timestamps and story IDs without monkeypatching the standard library.