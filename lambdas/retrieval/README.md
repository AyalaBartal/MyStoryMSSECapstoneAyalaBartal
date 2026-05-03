# Retrieval Lambda

Serves two routes for reading stories:

1. **`GET /story/{story_id}`** — public lookup of a single story by ID. Used by the frontend to poll while a story generates and to surface the download link when complete.
2. **`GET /my-stories`** — authenticated parent's library. Returns all stories tagged with the parent's Cognito sub, optionally filtered to a specific kid.

The frontend polls `GET /story/{id}` every 3 seconds while a story generates; the library page calls `GET /my-stories` once on load.

## HTTP contract

### `GET /story/{story_id}` — single story (public, no auth)

**Path parameters:**
- `story_id` (string, required) — UUID of the story to retrieve.

**Responses:**

| Status | Shape | When |
|--------|-------|------|
| `200`  | `{ story_id, status: "COMPLETE", created_at, download_url, expires_in }` | PDF is ready. `download_url` is a pre-signed S3 URL valid for `expires_in` seconds. |
| `200`  | `{ story_id, status: "FAILED", created_at, error? }` | The pipeline produced an error. `error` is a human-readable string if available. |
| `202`  | `{ story_id, status: "PROCESSING", created_at }` | Still generating. Client should poll. |
| `400`  | `{ error }` | Missing or malformed `story_id`. |
| `404`  | `{ error: "Story not found" }` | No story with that id. |
| `500`  | `{ error: "Internal server error" }` | Unexpected failure. Details only in CloudWatch, never in the response. |

This route is intentionally **unauthenticated** — anonymous users need to poll their own anonymously-generated stories. Story IDs are UUIDs, so guessing a valid one is computationally infeasible.

### `GET /my-stories` — parent library (auth required)

**Query parameters:**
- `kid_id` (string, optional) — filter to a specific kid's stories. Without this, returns all of the parent's stories.

**Responses:**

| Status | Shape | When |
|--------|-------|------|
| `200`  | `{ stories: [{...}, ...] }` | List of the parent's stories, newest first. Capped at 100. |
| `401`  | `{ error: "Authentication required" }` | Missing or invalid JWT. |
| `500`  | `{ error: "Internal server error" }` | Unexpected failure. |

Each story dict in the list has the same shape as `GET /story/{id}` returns for that story's status, plus the original card selections (`name`, `hero`, `theme`, `adventure`, `age`) and `kid_id` if set. COMPLETE stories include a fresh `download_url` so the frontend can render the open-link without a second request.

**Cross-tenant safety:** when `kid_id` is provided, the Lambda queries the `kid_id-index` GSI but post-filters results by `parent_id = <verified Cognito sub>`. This protects against a parent crafting another family's `kid_id` to read their stories.

All responses include CORS headers so the static-site frontend can call cross-origin.

## Environment variables

| Name                     | Required | Purpose |
|--------------------------|----------|---------|
| `STORIES_TABLE`          | yes      | DynamoDB table name (hash key `story_id`). |
| `PDFS_BUCKET`            | yes      | S3 bucket name where finished PDFs live. |
| `COGNITO_USER_POOL_ID`   | yes      | For JWT verification on `/my-stories`. |
| `COGNITO_APP_CLIENT_ID`  | yes      | For JWT audience validation on `/my-stories`. |
| `LOG_LEVEL`              | no       | `DEBUG`/`INFO`/`WARNING`/`ERROR`. Defaults to `INFO`. |

## IAM permissions required

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:GetItem` and `dynamodb:Query` on the stories table (`grant_read_data` covers both, including GSIs).
- `s3:GetObject` on the PDFs bucket (`grant_read`) — required for minting pre-signed URLs.

JWT signature verification fetches the Cognito User Pool's JWKS over HTTPS — public endpoint, no IAM grant needed.

## File layout

```
retrieval/
├── __init__.py
├── handler.py         # AWS entry point — routes by path; auth-gates /my-stories
├── service.py         # get_story + list_stories_for_parent (uses parent_id-index + kid_id-index GSIs)
├── auth.py            # Cognito JWT verification (copy from entry/)
├── utils.py           # CORS + Decimal-safe JSON encoder — NOT shared
├── requirements.txt   # boto3 + python-jose[cryptography]
├── README.md
└── tests/
    ├── __init__.py
    ├── conftest.py        # env vars + moto DynamoDB (with both GSIs) + S3 fixtures
    ├── test_service.py    # exercises both routes against moto
    └── test_handler.py    # event parsing, JWT extraction, exception-to-HTTP mapping
```

## Running the tests

From the repo root with `.venv` active:

```bash
pytest lambdas/retrieval/tests/ -v
```

For coverage:

```bash
pytest lambdas/retrieval/tests/ --cov=lambdas/retrieval --cov-report=term-missing
```

40 tests covering: UUID validation, the get-story status-to-HTTP mapping, the COMPLETE/FAILED/PROCESSING branches, my-stories listing for the authed parent, the optional kid_id filter, ownership boundaries (a parent cannot read another family's stories via crafted kid_id), and the empty-library / no-stories cases.

## How it handles data integrity

If a DynamoDB item on `GET /story/{id}` has `status="COMPLETE"` but no `pdf_s3_key`, the service raises `RuntimeError`. This indicates an upstream pipeline bug (the PDF assembly Lambda was supposed to write that key). The handler maps it to a 500 response and logs the full error via `logger.exception`, so CloudWatch surfaces it but the client only sees a generic message.

For `/my-stories`, the same missing-key situation is handled differently: a single corrupted row simply returns without a `download_url` field instead of raising. A bad row shouldn't blow up the whole library load — the user gets the rest of their stories minus that one broken entry.

## Notes

**Routing by `event["resource"]`.** API Gateway passes the route template (e.g. `/my-stories` or `/story/{story_id}`) in the event's `resource` field. The handler routes on substring match (`"my-stories" in resource`) rather than equality, with a fallback to `event["path"]`, so unusual API Gateway integrations (custom stages, prefixed paths) still work.

**`grant_read_data` covers GSIs automatically.** DynamoDB GSI permissions are inherited from the base table grant — no separate IAM block needed for `parent_id-index` or `kid_id-index`.