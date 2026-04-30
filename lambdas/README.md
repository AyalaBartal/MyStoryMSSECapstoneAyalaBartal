# Lambda architecture pattern

Every Lambda in this project follows the same layout, and they do **not** share code with each other. This document explains why, what the layout is, and how to create a new Lambda that conforms.

## The rule: each Lambda is a self-contained unit

No `_shared/` module. No cross-Lambda imports. Helpers like CORS response envelopes, loggers, and error formatters are copied into each Lambda's own `utils.py`.

**Why:** the point of serverless + microservices is that any one of these Lambdas should be extractable into its own repo, its own deploy pipeline, its own language runtime if needed — with zero dependency surgery. A shared-code module would couple them at the import graph level and quietly take that future away. The ~35 lines of duplicated boilerplate is the price we pay on purpose.

**When we'd reconsider:** if shared boilerplate grows past ~200 lines, the cost calculation flips. At that point the answer is a **proper versioned internal package** published to an internal PyPI (or CodeArtifact), not a folder import — because a published package maintains the extractability guarantee in a way a folder import can't.

## Standard structure
Lambdas/<name>/
    ├── init.py
    ├── handler.py        # AWS entry point — thin, ≤ ~50 lines ideal
    ├── service.py        # pure business logic, AWS-event-shape-free
    ├── utils.py          # inline helpers: make_response, error_response, get_logger
    ├── requirements.txt  # runtime deps that get bundled into the Lambda zip
    ├── README.md         # HTTP contract, env vars, IAM, file map
    └── tests/
        ├── init.py
        ├── conftest.py       # sys.path + env vars + moto fixture(s)
        ├── test_handler.py   # event parsing + exception-to-HTTP mapping
        └── test_service.py   # business logic against moto

## What each file is for

### `handler.py` — thin AWS entry point

Responsibilities:
- Parse the API Gateway (or Step Functions) event.
- Call into `service.py` with plain Python arguments.
- Translate service return values → HTTP status codes.
- Translate service exceptions → HTTP error responses.
- Catch the `Exception` catch-all and log via `logger.exception`.

Non-responsibilities:
- No business logic.
- No DynamoDB/S3/Step Functions calls (those go through service).
- No domain validation (service owns that).

Keep it ≤ ~50 lines. If it grows past that, logic is leaking — move it to service.

### `service.py` — pure business logic

Takes plain Python arguments (e.g. `story_id: str`, a boto3 table, a boto3 client, a bucket name). Returns plain Python values (dicts, strings). Raises **domain exceptions** (e.g. `StoryNotFound`, `ValueError`) — never HTTP status codes.

This is the file that gets ~90% of the tests. It can be unit-tested with moto without ever constructing a fake API Gateway event.

This is also the file that changes when we swap one provider implementation for another: the function signature stays the same, the internals change. Handler code never knows. The story_generation Lambda uses this pattern with AWS Bedrock; the image_generation Lambda uses it with OpenAI.

### `utils.py` — inline helpers (NOT shared)

Typical contents:
- `make_response(status_code, body_dict) -> dict` — wraps CORS headers.
- `error_response(status_code, message) -> dict` — standardized error envelope.
- `get_logger(name) -> logging.Logger` — log level from `LOG_LEVEL` env var.

The exact same file appears in every Lambda. That's correct. Do not DRY it up.

### `requirements.txt` — runtime deps only

What this Lambda imports at runtime (e.g. `boto3`, `reportlab`, `requests`). GitHub Actions reads this file and bundles **only these packages** into that Lambda's zip — every Lambda has its own deployment artifact with a minimal dependency surface.

- ✅ Belongs here: `boto3`, `reportlab`, `pillow`, third-party SDKs.
- ❌ Does NOT belong here: `pytest`, `moto`, `responses` — those go in root `requirements-dev.txt`.

### `README.md` — the Lambda's contract

Must document: HTTP (or Step Functions) contract, environment variables, IAM permissions required, file layout, how to run its tests. Anyone extracting this Lambda into its own repo later should be able to do so by reading this file and copy-pasting the folder.

### `tests/conftest.py` — test-time wiring

Three jobs:
1. `sys.path.insert` to put the Lambda's folder on Python's import path (mirrors what AWS Lambda does at runtime).
2. `os.environ.setdefault` for every env var the handler reads at import time — must run before any test imports `handler`.
3. Provide an `aws_mocks` fixture (or similar) that spins up moto-mocked resources for the test.

### `tests/test_service.py` and `tests/test_handler.py`

- **Service tests** use moto to exercise real boto3 code paths against fake AWS. Assert on returned values, not on which boto3 methods got called. Cover every status branch and every raised exception.
- **Handler tests** `monkeypatch` the service with a stub that returns canned values or raises canned exceptions. Cover event parsing and exception-to-HTTP mapping. Never hit moto — that's already tested in `test_service.py`.

## Canonical example: `retrieval/`

The `retrieval/` Lambda is the reference implementation of this pattern. When creating a new Lambda, copy its structure:

```bash
cp -r lambdas/retrieval lambdas/<new-name>
# then edit handler.py, service.py, README.md, tests/*.py to match the new Lambda's contract
```

## Definition of Done for a Lambda

A Lambda is only "done" when it has:

- [ ] `__init__.py`
- [ ] `handler.py` (thin AWS entry point)
- [ ] `service.py` (pure business logic)
- [ ] `utils.py` (inline helpers)
- [ ] `requirements.txt`
- [ ] `README.md` (HTTP/Step Functions contract, env vars, IAM)
- [ ] `tests/test_handler.py` — passing
- [ ] `tests/test_service.py` — passing
- [ ] Wired into the correct CDK stack (`infra/stacks/api_stack.py` or `infra/stacks/pipeline_stack.py`) with appropriate IAM grants
- [ ] Coverage ≥ ~80% on `service.py`

Anything less than all nine items = "In Progress," not "Done."

## Why this pattern 

Each Lambda is a **small, self-contained service** that happens to be hosted in AWS Lambda. Treating it as a service (with its own contract, its own dependencies, its own README) instead of as "a function in a repo" makes the architecture portable: we could migrate any individual Lambda to ECS, Cloud Run, or a separate repo tomorrow without rewriting dependency management or unpicking shared imports. The boilerplate cost is small; the optionality it preserves is large.