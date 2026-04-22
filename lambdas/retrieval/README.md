# Retrieval Lambda

Returns the current state of a story — either "still processing" or a
pre-signed S3 URL for the finished PDF.

## HTTP contract

**Route:** `GET /story/{story_id}`

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

All responses include CORS headers so the static-site frontend can call this endpoint cross-origin.

## Environment variables

| Name            | Required | Purpose |
|-----------------|----------|---------|
| `STORIES_TABLE` | yes      | DynamoDB table name (hash key `story_id`). |
| `PDFS_BUCKET`   | yes      | S3 bucket name where finished PDFs live. |
| `LOG_LEVEL`     | no       | `DEBUG`/`INFO`/`WARNING`/`ERROR`. Defaults to `INFO`. |

## IAM permissions required

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:GetItem` on the stories table (`grant_read_data`).
- `s3:GetObject` on the PDFs bucket (`grant_read`) — required for minting pre-signed URLs.

## File layout
```
retrieval/
    ├── init.py
    ├── handler.py        # AWS entry point — thin, parses events and maps exceptions to HTTP
    ├── service.py        # pure business logic — testable without AWS event shapes
    ├── utils.py          # inline helpers (CORS responses, logger) — NOT shared, see lambdas/README.md
    ├── requirements.txt  # runtime deps bundled into the deployment zip (just boto3)
    └── tests/
            ├── init.py
            ├── conftest.py       # sys.path + env vars + moto fixture
            ├── test_service.py   # 15 tests — exercise service against moto
            └── test_handler.py   # 11 tests — exercise handler with service mocked out
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

## How it handles data integrity

If a DynamoDB item has `status="COMPLETE"` but no `pdf_s3_key`, the service raises `RuntimeError`. 
This indicates an upstream pipeline bug (the PDF assembly Lambda was supposed to write that key). The handler maps it to a 500 response and logs the full error via `logger.exception`, so CloudWatch surfaces it but the client only sees a generic message.

