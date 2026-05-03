# Lambda architecture pattern

Every Lambda in this project follows the same layout, and they do **not** share code with each other. This document explains why, what the layout is, and how to create a new Lambda that conforms.

## The rule: each Lambda is a self-contained unit

No `_shared/` module. No cross-Lambda imports. Helpers like CORS response envelopes, loggers, error formatters, and JWT verification are copied into each Lambda's own `utils.py` and `auth.py`.

**Why:** the point of serverless + microservices is that any one of these Lambdas should be extractable into its own repo, its own deploy pipeline, its own language runtime if needed — with zero dependency surgery. A shared-code module would couple them at the import graph level and quietly take that future away. The ~50 lines of duplicated boilerplate is the price we pay on purpose.

**When we'd reconsider:** if shared boilerplate grows past ~200 lines, the cost calculation flips. At that point the answer is a **proper versioned internal package** published to an internal PyPI (or CodeArtifact), not a folder import — because a published package maintains the extractability guarantee in a way a folder import can't.

## Standard structure

```
lambdas/<name>/
    ├── __init__.py
    ├── handler.py        # AWS entry point — thin, ≤ ~50 lines ideal
    ├── service.py        # pure business logic, AWS-event-shape-free
    ├── utils.py          # inline helpers: make_response, error_response, get_logger
    ├── auth.py           # OPTIONAL — Cognito JWT verification (auth-required Lambdas only)
    ├── adapters.py       # OPTIONAL — ports/adapters for external providers (LLM, image gen)
    ├── requirements.txt  # runtime deps that get bundled into the Lambda zip
    ├── README.md         # HTTP contract, env vars, IAM, file map
    └── tests/
        ├── __init__.py
        ├── conftest.py       # sys.path + env vars + moto fixture(s)
        ├── test_handler.py   # event parsing + exception-to-HTTP mapping
        ├── test_service.py   # business logic against moto
        └── test_adapters.py  # OPTIONAL — adapter unit tests
```

## What each file is for

### `handler.py` — thin AWS entry point

Responsibilities:
- Parse the API Gateway (or Step Functions) event.
- Extract and verify JWT if the route requires auth (delegates to `auth.py`).
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
- `make_response(status_code, body_dict) -> dict` — wraps CORS headers; uses a Decimal-safe JSON encoder so DynamoDB number values serialize cleanly.
- `error_response(status_code, message) -> dict` — standardized error envelope.
- `get_logger(name) -> logging.Logger` — log level from `LOG_LEVEL` env var.

The exact same file appears in every Lambda. That's correct. Do not DRY it up.

### `auth.py` — Cognito JWT verification (auth-required Lambdas only)

Lambdas behind authenticated routes (`entry`, `retrieval`, `kids`, `claim_stories`) include a copy of `auth.py` for verifying Cognito JWTs. Contents:

- `extract_token_from_event(event) -> str | None` — pull a Bearer token from the `Authorization` header (case-insensitive)
- `verify_jwt(token) -> dict` — verify signature, expiry, and audience against the Cognito User Pool's JWKS; return claims (`sub`, `email`, etc.)
- `InvalidTokenError` exception

Same file copied to every auth-required Lambda — same reasoning as `utils.py`. JWT verification needs `python-jose[cryptography]` in `requirements.txt`.

### `adapters.py` — ports/adapters (provider-using Lambdas only)

Lambdas that call external AI providers (`story_generation`, `image_generation`) define an abstract adapter interface plus concrete implementations:

- An ABC like `LLMAdapter` or `ImageAdapter` with one method (`generate`)
- A `Mock<X>Adapter` for tests that returns canned data
- A real provider implementation (`BedrockLLMAdapter`, `OpenAIImageAdapter`)

Service code depends only on the abstract interface. Swapping providers is a one-class change.

### `requirements.txt` — runtime deps only

What this Lambda imports at runtime (e.g. `boto3`, `reportlab`, `python-jose`). GitHub Actions reads this file and bundles **only these packages** into that Lambda's zip — every Lambda has its own deployment artifact with a minimal dependency surface.

- ✅ Belongs here: `boto3`, `reportlab`, `pillow`, `python-jose`, third-party SDKs.
- ❌ Does NOT belong here: `pytest`, `moto`, `responses` — those go in root `requirements-dev.txt`.

### `README.md` — the Lambda's contract

Must document: HTTP (or Step Functions) contract, environment variables, IAM permissions required, file layout, how to run its tests. Anyone extracting this Lambda into its own repo later should be able to do so by reading this file and copy-pasting the folder.

### `tests/conftest.py` — test-time wiring

Per-Lambda conftest jobs:
1. Pre-set env vars the handler reads at import time (e.g. table names, `COGNITO_USER_POOL_ID`) — must run before any test imports `handler`.
2. Provide moto-mocked fixtures (DynamoDB tables, S3 buckets) for tests that need them.

`sys.path` and `sys.modules` isolation across Lambdas is handled by the **repo-root** `conftest.py`, not the per-Lambda one. The root conftest detects which Lambda's tests are running and resets module caches accordingly so `import handler` in two different Lambdas doesn't conflict.

### `tests/test_service.py` and `tests/test_handler.py`

- **Service tests** use moto to exercise real boto3 code paths against fake AWS. Assert on returned values, not on which boto3 methods got called. Cover every status branch and every raised exception.
- **Handler tests** `monkeypatch` the service with a stub that returns canned values or raises canned exceptions. Cover event parsing and exception-to-HTTP mapping. Never hit moto — that's already tested in `test_service.py`.

## Canonical example: `retrieval/`

The `retrieval/` Lambda is the reference implementation of this pattern — it has the full set: handler, service, utils, auth, tests. When creating a new auth-required Lambda, copy its structure:

```bash
cp -r lambdas/retrieval lambdas/<new-name>
# then edit handler.py, service.py, README.md, tests/*.py to match the new Lambda's contract
```

For Step Functions worker Lambdas (no auth, no API Gateway), copy `pdf_assembly/` instead.

## Definition of Done for a Lambda

A Lambda is only "done" when it has:

- [ ] `__init__.py`
- [ ] `handler.py` (thin AWS entry point)
- [ ] `service.py` (pure business logic)
- [ ] `utils.py` (inline helpers)
- [ ] `auth.py` if route requires auth
- [ ] `adapters.py` if it calls an external provider
- [ ] `requirements.txt`
- [ ] `README.md` (HTTP/Step Functions contract, env vars, IAM)
- [ ] `tests/test_handler.py` — passing
- [ ] `tests/test_service.py` — passing
- [ ] `tests/test_adapters.py` — passing if adapters exist
- [ ] Wired into the correct CDK stack (`infra/stacks/api_stack.py` or `infra/stacks/pipeline_stack.py`) with appropriate IAM grants
- [ ] Coverage ≥ ~80% on `service.py`

Anything less = "In Progress," not "Done."

## Why this pattern

Each Lambda is a **small, self-contained service** that happens to be hosted in AWS Lambda. Treating it as a service (with its own contract, its own dependencies, its own README) instead of as "a function in a repo" makes the architecture portable: we could migrate any individual Lambda to ECS, Cloud Run, or a separate repo tomorrow without rewriting dependency management or unpicking shared imports. The boilerplate cost is small; the optionality it preserves is large.