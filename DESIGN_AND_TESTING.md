# My Story — Design & Testing Document

**Project:** My Story — AI-Powered Personalized Children's Story Generator
**Program:** MSSE Capstone, Quantic School of Business and Technology
**Author:** Ayala Bartal
**Document version:** 1.0
**Last updated:** 2026-04-25

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [User Stories & Scope](#2-user-stories--scope)
3. [System Architecture](#3-system-architecture)
4. [Design & Architecture Decisions](#4-design--architecture-decisions)
5. [Software & Architectural Patterns](#5-software--architectural-patterns)
6. [Deployment Strategy & Cost](#6-deployment-strategy--cost)
7. [Current Implementation Status](#7-current-implementation-status)
8. [Testing Strategy](#8-testing-strategy)
9. [CI/CD Pipeline](#9-cicd-pipeline)
10. [Risks & Mitigations](#10-risks--mitigations)
11. [Appendix — File Map](#11-appendix--file-map)

---

## 1. Project Overview

**My Story** is a serverless web application that lets children ages 4–12 create a personalized illustrated storybook by entering their name, picking their age, and selecting three story cards: a **Hero** (boy/girl), an **Adventure Theme** (Space, Under the Sea, Medieval Fantasy, Dinosaurs), and an **Adventure** (Secret Map, Talking Animal, Time Machine, Magic Key).

The backend generates a unique 5-page story (written by Anthropic's Claude Haiku, with prose calibrated to the reader's age) with matching AI-generated illustrations (created by OpenAI's `gpt-image-1` model in a consistent watercolor children's-book aesthetic), assembles the result into a square 8×8 inch picture-book PDF with a custom cover page, and delivers it back to the child as a downloadable file.

The schema yields **288 unique story-shape combinations** (2 heroes × 4 themes × 4 adventures × 9 ages), plus open-ended personalization through the child's name and the LLM's per-generation creativity.

### Business goals

- Demonstrate an end-to-end AI-engineered product built with modern serverless cloud patterns
- Produce tangible, share-able output (a personalized PDF storybook) rather than a screen-only experience
- Apply a hexagonal/ports-and-adapters Lambda architecture so AI providers can be swapped without rewriting the system

### Success criteria

- A child can complete the full flow — card selection → generated story → PDF download — end-to-end through the deployed app
- The deployed system works from a public URL on both desktop and mobile
- All infrastructure is reproducible via `cdk deploy --all` from a clean checkout
- Unit tests cover all five Lambdas and run automatically on every push via GitHub Actions
- The picture-book PDF format is consistent and visually polished — full-bleed illustrations with a soft cream text overlay band, age-appropriate typography, and a themed cover page

---

## 2. User Stories & Scope

### Core user stories (from Trello backlog)

1. As a child, I can **enter my name** so the hero of my story is named after me.
2. As a child, I can **pick my age** so the story uses words I can read.
3. As a child, I can see and select a **Hero** card (boy or girl) with an illustration so I can identify with my hero.
4. As a child, I can select an **Adventure Theme** card (Space, Under the Sea, Medieval Fantasy, Dinosaurs) so my story world is set.
5. As a child, I can select an **Adventure** card (Secret Map, Talking Animal, Time Machine, Magic Key) so my story has a clear starting hook.
6. As a user, I can click **Create my story** and receive a personalized 5-page picture book within a few minutes.
7. As a user, I see a **friendly loading state** with an animated polaroid while the story generates.
8. As a user, I can **download** the complete story as a square picture-book PDF with a custom cover.
9. As a user, I can access the website from any device (mobile-friendly).

### Out of scope (deliberately)

- User accounts / authentication (stories are identified by UUID; privacy via obscurity for the demo)
- Payments, subscriptions, or usage quotas
- Multi-language support (English only)
- Editing or regenerating individual pages after generation

---

## 3. System Architecture

### High-level flow

```
Frontend (React + Vite, hosted on S3 static site)
        │
        ▼
   API Gateway ───► POST /generate ───► Entry Lambda ──► DynamoDB (status: PROCESSING)
                                             │
                                             ▼
                                    Step Functions pipeline
                                             │
                  ┌──────────────────────────┼─────────────────────────────┐
                  ▼                          ▼                              ▼
          Story Generation Lambda    Image Generation Lambda        PDF Assembly Lambda
                  │                          │                              │
                  ▼                          ▼                              ▼
           Anthropic Claude Haiku    OpenAI gpt-image-1               ReportLab
           (text + image_prompt       (1024×1024 watercolor                  │
            per page, structured       illustrations)                         ▼
            JSON output)                      │                       S3 (PDFs bucket)
                                              ▼                              +
                                       S3 (Images bucket)          DynamoDB (status: COMPLETE)

        Frontend polls ────► GET /story/{id} ────► Retrieval Lambda ──► Pre-signed S3 URL
                                                                            │
                                                                            ▼
                                                                    PDF download
```

### AWS services

| Service | Purpose |
|---|---|
| **S3** | Frontend hosting; PDF storage; illustration storage; pre-generated card images |
| **API Gateway** | REST API endpoints (`POST /generate`, `GET /story/{id}`) |
| **Lambda** (×5) | Business logic — each function does one thing (entry, story, image, pdf, retrieval) |
| **Step Functions** | Orchestrates the asynchronous story-generation pipeline |
| **DynamoDB** | Story metadata (status, card selections, timestamps) with 30-day TTL |
| **Secrets Manager** | Stores Anthropic + OpenAI API keys, never in code or env vars |
| **CloudWatch** | Logging, metrics, error visibility |
| **IAM** | Least-privilege roles per Lambda |
| **AWS CDK** | Infrastructure-as-Code (Python) |

### External services

| Service | Purpose | Why |
|---|---|---|
| **Anthropic Claude Haiku** | Generates the 5-page story text + sanitized image prompts per page | Best-in-class long-form prose quality for children's storytelling at low cost (~$0.02/story); strong instruction-following for structured JSON output |
| **OpenAI `gpt-image-1`** (gpt-4o image generation) | Generates each page's illustration | Better character consistency, better spatial-composition adherence, and supports reference-image conditioning. Replaced DALL-E 3 mid-project. |
| **GitHub Actions** | CI/CD | Free for public repos; native GitHub integration |

---

## 4. Design & Architecture Decisions

### Why serverless AWS

- **Unpredictable, bursty load.** A capstone demo may see zero traffic for days and then a spike during the recorded walkthrough. Per-request billing on Lambda and DynamoDB means we pay only when a story is generated, not for idle capacity.
- **No servers to manage.** Graders should be able to `cdk deploy --all` and have a working system in under 15 minutes.
- **CDK (Python) over raw CloudFormation or Terraform.** Python keeps the infra language consistent with the Lambda code; higher-level CDK constructs (e.g. `tasks.LambdaInvoke`, `s3.Bucket`) dramatically cut boilerplate versus hand-written CloudFormation. Python was chosen over TypeScript for CDK because all other code in the project is Python.

### Why Step Functions for the pipeline

- The story flow is **inherently sequential** (text must exist before images can be prompted from it; PDF must wait for images) but also **long-running** (a Claude Haiku call takes 10–30s, gpt-image-1 takes 15–25s per image × 5 images, and PDF assembly takes 1–3s). Running everything inside a single Lambda risks the 15-minute cap and burns memory-time budget on waiting.
- Step Functions lets each stage be its own short-lived Lambda, with built-in retries, error handling, and a visual execution history that is excellent for debugging and the demo video.
- An alternative was SQS + polling, but Step Functions gave us a state machine with zero queue-management code AND a centralized failure-handling state (`MarkFailed`) that flips the DynamoDB record to `FAILED` if any worker step throws.

### Why five Lambdas instead of one

- **Single-responsibility principle** — each Lambda owns one concern (validation, text gen, image gen, PDF assembly, retrieval). Easier to test, easier to reason about, and each can be independently resized on memory and timeout.
- The `story_generation` and `image_generation` Lambdas are I/O-bound (waiting on external APIs) and run at 512 MB. `pdf_assembly` is CPU-bound (ReportLab + image processing) and runs at 1024 MB. Keeping them separate means we're not overpaying memory for I/O-bound functions.

### Why DynamoDB

- The data model is trivially key-value (`story_id` → status + metadata). No joins, no reporting queries.
- On-demand billing mode means no capacity planning for a demo workload.
- TTL-based expiry (30 days) means we don't need a cleanup job — DynamoDB does it for us.

### Why S3 buckets are split four ways

Separation makes lifecycle rules, public-access policies, and access control crisp:

| Bucket | Public? | Lifecycle |
|---|---|---|
| `my-story-frontend-<acct>` | **Public read** (static website) | None |
| `my-story-cards-<acct>` | **Public read** (card illustrations loaded by the frontend) | None |
| `my-story-images-<acct>` | Private (served via pre-signed URL if directly linked) | None |
| `my-story-pdfs-<acct>` | Private; access via pre-signed URL only | **Expire objects after 30 days** |

This means leaking a PDF URL doesn't leak the illustration source files, and vice versa.

### Why foundation models with structured prompt engineering

We use Anthropic Claude Haiku and OpenAI `gpt-image-1` directly via API, with rigorously structured prompt templates for both text and image generation.

Reasons:
- **Quality.** Claude Haiku writes more compelling children's prose than any 7-13B open-source LLM we could fine-tune at this scale; gpt-image-1's watercolor-style adherence and character drawing skill is currently unmatched by smaller diffusion models.
- **Reliability.** Foundation models have predictable uptime, content moderation, and well-documented APIs.
- **Cost is trivial at this scale.** ~$0.20-0.50 per generated book including text + 5 images.
- **Hexagonal architecture preserves flexibility.** Both `OpenAIImageAdapter` and the LLM adapter implement abstract interfaces — the system can swap providers (or move to self-hosted models) without rewriting business logic. This was demonstrated mid-project when we replaced DALL-E 3 with gpt-image-1 by changing a single class.

### Why two-stage LLM output (text + sanitized image prompt per page)

Initial design used separate Claude calls per page to produce text and image prompt independently. Two problems emerged: (1) the LLM occasionally embedded character dialogue or proper names into the image prompt, which confused the image model, and (2) image prompts varied wildly in length and style across pages of the same story.

The current design has the LLM produce both `text` and `image_prompt` for all 5 pages in a **single structured JSON response**. The image_prompt is constrained by template to:

- Include a verbatim-repeated character description across all 5 pages (15-25 words specifying hair, eyes, skin tone, AND a specific outfit) — for visual character consistency
- Include a verbatim-repeated world description across all 5 pages (10-15 words specifying environment, time of day, dominant tones) — for setting and palette cohesion
- End with a fixed style suffix specifying watercolor aesthetic + spatial composition rules — for art-style consistency

This produces materially more consistent illustrations across a book.

### Why gpt-image-1 over DALL-E 3 (mid-project upgrade)

The pipeline initially used DALL-E 3 HD. Two limitations drove the upgrade to `gpt-image-1`:

1. **Character drift across pages.** DALL-E 3 produces visibly different characters when given the same prompt across multiple generations — even with verbatim-repeated character descriptions. Pages 1-5 looked like five different children rather than one child in five moments.
2. **Spatial composition non-adherence.** DALL-E 3 ignored explicit "leave the bottom 35% of the image as flat painted background" instructions roughly 60% of the time, making text overlay placement unpredictable.

`gpt-image-1` is materially better at both: tighter character continuity across multi-page generation and stronger compositional prompt-following. It also costs less than DALL-E 3 HD ($0.042/image at medium quality vs $0.08/image for DALL-E 3 HD) while producing better output.

The swap was a single-class change (`OpenAIImageAdapter`) thanks to the hexagonal architecture — no business logic, no orchestration, no Lambda config changes were required.

### Why a square 8×8 inch picture-book PDF format with overlaid text

Initial design rendered text below the image on letter-portrait pages — produced a clinical "research paper" look, not a children's book.

The current format mimics real children's picture books:

- **Square 8×8 inch pages (576×576 points)** — the dominant trim size for picture books
- **Full-bleed illustrations** filling the entire page edge-to-edge
- **Text overlaid in a semi-transparent cream band** at the bottom (50% opacity) so the watercolor illustration bleeds softly through, rather than text on a hard white rectangle
- **Times-BoldItalic** typography for storybook warmth + readability against the band
- **Age-tiered font sizing** (24pt for ages 4-6, 19pt for 7-9, 16pt for 10-12) so younger readers get larger, more legible text
- **Custom cover page** using the selected theme card image as a full-bleed background, with the child's name as the title (e.g., "Ayala's Story") and the theme as a subtitle ("A medieval fantasy adventure"), framed by a `✦ ✦ ✦` flourish

The cover image is fetched at PDF-assembly time from the cards S3 bucket — no external API call needed.

### Why a layered approach to text legibility

The image bottom is *requested* to be calm via the prompt template, but `gpt-image-1` complies inconsistently. Rather than choosing a single defense, the system uses **layered defense**:

1. **Image-side:** prompt requests a clean lower third (works ~70% of the time)
2. **PDF-side:** semi-transparent cream band overlay at 0.5 opacity (always renders, provides text contrast even when the image's bottom is busy)
3. **Typography:** bold italic + dark brown color (#2b2320) gives strong contrast against the band
4. **Overflow protection:** text Paragraph wrapped in `KeepInFrame(mode="shrink")` so longer-than-expected prose auto-shrinks to fit instead of silently dropping (a real bug we hit when prompt iterations made stories longer)

Together these guarantee that text is always present and readable, even when individual layers fail.

### Why the cards bucket is separate and public

Card illustrations are static assets generated once and uploaded to S3. They:
- Need to be public for the React frontend to load them as `<img src="...">`
- Don't need lifecycle rules
- Are versioned manually, separately from generated story assets

Splitting them from the dynamic generated-images bucket means lifecycle rules on PDFs/illustrations don't accidentally delete the card images, and CDN caching policies can differ per bucket.

---

## 5. Software & Architectural Patterns

### Architectural patterns in use

1. **Serverless / FaaS** — every compute unit is a Lambda; no long-running servers
2. **Event-driven pipeline** — Entry Lambda kicks off Step Functions; downstream Lambdas react via state machine transitions
3. **Orchestrator pattern (Step Functions)** — central state machine coordinates the three pipeline Lambdas rather than each Lambda triggering the next (choreography). Chosen for visibility and centralized retry/failure logic.
4. **Hexagonal / Ports-and-Adapters** — each AI-calling Lambda (`story_generation`, `image_generation`) defines an abstract `Adapter` interface and provides concrete implementations (real provider call vs. mock for tests). Business logic depends only on the abstract interface. This is what made the DALL-E 3 → gpt-image-1 swap a one-class change.
5. **Infrastructure-as-Code** — all AWS resources are defined in `infra/stacks/*.py` via CDK. No click-ops.
6. **CQRS-lite** — writes go through `POST /generate` (command), reads go through `GET /story/{id}` (query), backed by two different Lambdas with two different IAM policies.
7. **Schema-driven validation** — the Entry Lambda's input validation is driven by `lambdas/entry/cards_schema.json`, not hardcoded conditionals. Adding a new theme means editing one JSON file, not changing Python code.

### Software patterns in use

- **Input validation at the edge.** The Entry Lambda validates card selections, name, and age against the schema before any persistence or pipeline trigger.
- **Idempotent pipeline execution name.** Step Functions execution name is set to the `story_id` so retrying the same generation can't spawn duplicate pipelines.
- **Graceful error envelopes.** Every API-facing Lambda returns JSON bodies with `statusCode`, CORS headers, and an `error` field on failure — never a bare 500 HTML page.
- **Environment-variable configuration.** Bucket names, table names, and state machine ARNs are passed through Lambda environment variables at deploy time by CDK — no hard-coded resource identifiers in handler code.
- **Secrets via AWS Secrets Manager.** Anthropic and OpenAI API keys live in Secrets Manager, fetched by Lambda at cold start via `ANTHROPIC_SECRET_ARN` / `OPENAI_SECRET_ARN`. The actual key never appears in source, env vars, or CloudFormation templates.
- **Dependency injection in handlers.** Each Lambda's `handler.py` builds the concrete adapters and injects them into the `service.py` business logic. This makes the business logic completely independent of AWS SDK or HTTP libraries — a major testability win.
- **Centralized failure handling in Step Functions.** A single shared `MarkFailed` state catches `States.ALL` from every worker step, flips the DynamoDB record to `FAILED`, and terminates the execution. The retrieval Lambda surfaces this status to the user instead of leaving them polling forever.

### Frontend patterns

- **React + Vite SPA** — fast dev loop, modern tooling, cheap to host (just static files on S3)
- **Polling pattern for async generation** — frontend POSTs to `/generate`, receives `story_id`, polls `/story/{id}` every 3 seconds until `COMPLETE` or `FAILED`. Maximum 3 minutes before timing out client-side.
- **State machine in the UI** — `picking → generating → complete` (or `failed`) cleanly separates the four screens
- **Polaroid loading + completion frames** — same visual language across loading and complete states (different image inside, same frame) so the transition feels like turning a page rather than loading a new screen

---

## 6. Deployment Strategy & Cost

### Recommended deployment: AWS cloud (us-east-1)

This project is cloud-first by design. On-premises deployment was rejected for the following reasons:

- Five Lambdas, Step Functions, and managed DynamoDB have no direct on-prem equivalent that wouldn't require substantial re-architecture (self-hosted k8s + Argo Workflows + Postgres).
- Foundation model providers (Anthropic, OpenAI) are SaaS-only — on-prem for just the orchestration layer wouldn't meaningfully reduce cloud dependency.
- For demo-scale workloads (<100 stories/day), on-demand cloud pricing is significantly cheaper than any self-hosted alternative.

### Cost estimate (demo scale, us-east-1)

For 100 generated stories per month:

| Component | Est. monthly cost |
|---|---|
| Lambda invocations (5 × 100 = 500) | < $0.01 |
| Step Functions state transitions (~15 per story × 100) | < $0.05 |
| DynamoDB on-demand (100 writes, ~500 reads) | < $0.01 |
| S3 storage (PDFs expire at 30 days; illustrations retained) | ~$0.05 |
| API Gateway (600 requests) | < $0.01 |
| Secrets Manager (2 secrets) | $0.80 |
| CloudWatch logs | ~$0.10 |
| **AWS subtotal** | **~$1.00 / month** |
| Anthropic Claude Haiku (~$0.02 / story × 100) | $2.00 |
| OpenAI gpt-image-1 medium (5 images × $0.042 × 100) | $21.00 |
| **External AI subtotal** | **~$23.00 / month** |
| **Total** | **~$24 / month at demo scale** |

The dominant cost is **AI image generation**, not AWS infrastructure. At 100x scale (10,000 stories/month), AWS costs scale roughly linearly to ~$50/month while AI costs scale to ~$2,300/month — approximately 98% of operating cost is the AI API.

### Scale-up considerations (documented for completeness)

- **CloudFront** in front of the frontend S3 bucket — reduces latency, adds HTTPS with a custom domain
- **Provisioned concurrency** on the Entry Lambda if cold start becomes visible in the UX
- **SQS dead-letter queue** on each pipeline Lambda to catch poison messages
- **Step Functions Express Workflows** if transitions/month ever exceeds ~100k (cheaper per transition than Standard at that volume)

---

## 7. Current Implementation Status

Snapshot of the repo as of submission, cross-referenced with the Trello board.

### ✅ Done — built, tested, and deployed

| Component | File | Notes |
|---|---|---|
| CDK app wiring | `infra/app.py` | Four stacks composed with explicit env (account, region) |
| Storage stack | `infra/stacks/storage_stack.py` | 4 S3 buckets + DynamoDB `my-story-stories` table with TTL |
| API stack | `infra/stacks/api_stack.py` | API Gateway + Entry & Retrieval Lambdas + IAM + CORS |
| Pipeline stack | `infra/stacks/pipeline_stack.py` | Story / Image / PDF Lambdas + Step Functions state machine + Secrets Manager + failure-handling state |
| Entry Lambda | `lambdas/entry/` | Schema-driven validation against `cards_schema.json`, DynamoDB write, Step Functions trigger, error envelopes |
| Story Generation Lambda | `lambdas/story_generation/` | Hexagonal: `LLMAdapter` interface + `AnthropicLLMAdapter` impl + `MockLLMAdapter` for tests. Two-stage prompt template producing `text` + `image_prompt` per page in structured JSON. Age-aware vocabulary calibration. |
| Image Generation Lambda | `lambdas/image_generation/` | Hexagonal: `ImageAdapter` interface + `OpenAIImageAdapter` (gpt-image-1) + `MockImageAdapter`. Generates 5 illustrations in parallel. Uploads to S3. |
| PDF Assembly Lambda | `lambdas/pdf_assembly/` | ReportLab. Square 576×576pt pages. Cover page with theme card image background. Full-bleed illustrations + semi-transparent cream text band + `KeepInFrame` overflow protection. Age-tiered typography from `layout.json`. |
| Retrieval Lambda | `lambdas/retrieval/` | DynamoDB read + pre-signed S3 URL generation for PDF download |
| Frontend | `frontend/src/` | React + Vite. Card picker UI, name + age inputs, polaroid loader, polaroid completion screen, error handling, polling. Deployed to S3 static website. |
| Card images | `frontend/src/assets/cards/`, `s3://my-story-cards-...` | 14 illustrations: 2 heroes + 4 themes + 4 adventures + 4 placeholder-age cards |
| Tests | `lambdas/*/tests/` | 122+ unit tests across all Lambdas; mock adapters; pytest config in `pyproject.toml` |
| CI/CD | `.github/workflows/deploy.yml` | GitHub Actions: test → package Lambdas → cdk deploy → S3 frontend sync |
| Documentation | `lambdas/README.md`, `README.md`, this file | Architecture explanation, setup instructions, sprint timeline |

---

## 8. Testing Strategy

### Testing pyramid

```
                ┌──────────────────────┐
                │  E2E (manual demo)   │  ← recorded demo video for submission
                └──────────────────────┘
              ┌──────────────────────────┐
              │   Integration (Step Fns) │  ← AWS Step Functions execution history
              └──────────────────────────┘
            ┌────────────────────────────────┐
            │    Unit tests (per Lambda)     │  ← 122+ tests, run on every CI build
            └────────────────────────────────┘
```

### Unit tests

- **Tooling:** `pytest`, `pytest-cov`, `moto` for AWS mocking (where AWS SDK calls couldn't be cleanly avoided), and the project's own `MockLLMAdapter` / `MockImageAdapter` for hexagonal-injected dependencies
- **Configuration:** `pyproject.toml` declares `--import-mode=importlib` so each Lambda's tests can import from its sibling source files without colliding with other Lambdas' modules
- **Isolation:** Every test injects a stub adapter and stubbed S3/DDB callables — **no test ever hits the real AWS or external APIs**. Tests run in milliseconds, deterministically, with zero cost.
- **Coverage focus:**
  - **Adapters:** assert correct call kwargs to provider SDKs, correct response parsing, error-path propagation
  - **Service layer:** assert correct business logic given known inputs/outputs from adapters
  - **Handlers:** assert event → output mapping, including event-field passthrough (so future debug fields like `trace_id` flow end-to-end)
  - **Schema validation (Entry Lambda):** valid input passes; missing fields, wrong values, oversized strings all raise typed errors

### Test counts per Lambda (as of submission)

| Lambda | Test files | Test count |
|---|---|---|
| `entry` | `test_handler.py`, `test_service.py` | ~20 |
| `story_generation` | `test_adapters.py`, `test_handler.py`, `test_service.py` | ~30 |
| `image_generation` | `test_adapters.py`, `test_handler.py`, `test_service.py` | ~25 |
| `pdf_assembly` | `test_handler.py`, `test_service.py` | ~25 |
| `retrieval` | `test_handler.py`, `test_service.py` | ~20 |
| **Total** | | **~120** |

### Integration testing

- **Step Functions execution history** is the integration test surface. Every real story generation is visible in the AWS console as a state machine execution, with input/output JSON for each step. This was used extensively during development to debug "the text disappeared in the PDF" type bugs by inspecting what Story Generation produced and what PDF Assembly received.
- **Manual end-to-end smoke tests** before each deploy — generate one story via the deployed app, open the PDF, verify cover + 5 pages + text rendering.

### Failure-mode testing

- **Adapter failure:** unit tests cover S3 read failure, S3 write failure, DDB update failure, and external API failure. All propagate cleanly to Step Functions, which routes to the `MarkFailed` state.
- **Pipeline failure:** Step Functions failure handling tested end-to-end by deliberately invalidating an API key — the pipeline correctly flips the DDB status to `FAILED`, and the retrieval Lambda + frontend surface this to the user as a friendly "Something went wrong" screen rather than indefinite polling.

### Why this strategy

- **Speed.** 120+ tests run in under 5 seconds because they avoid the network entirely.
- **Determinism.** No flaky tests waiting on real AWS or external APIs.
- **Cost.** $0 to run the test suite as many times as needed, including in CI on every PR.
- **Coverage of the hard parts.** The hexagonal architecture lets us test the business logic (which is where bugs tend to live) without testing the AWS SDK or the OpenAI SDK (which are well-tested by their authors).

---

## 9. CI/CD Pipeline

### Workflow: `.github/workflows/deploy.yml`

```
Push to main / open PR
        │
        ▼
   ┌─────────┐
   │  test   │  pip install requirements per Lambda; pytest with coverage
   └─────────┘
        │ (only on main, only on push)
        ▼
   ┌────────────────┐
   │ deploy-infra   │  Package Lambdas → cdk deploy --all
   └────────────────┘
        │
        ▼
   ┌──────────────────┐
   │ deploy-frontend  │  Sync frontend dist/ to S3
   └──────────────────┘
```

### CI stages

1. **Test stage** — runs on every push and PR. Installs dependencies for each Lambda, runs `pytest` with coverage.
2. **Deploy infra stage** — only runs on push to `main`. Packages Lambda source + dependencies into zip files (`infra/lambda_packages/*.zip`) using `scripts/package_lambdas.sh`, then runs `cdk deploy --all --require-approval never`.
3. **Deploy frontend stage** — runs after infra deploys successfully. Syncs the frontend build output to the public S3 bucket.

### AWS credentials

Stored as GitHub Actions secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `FRONTEND_BUCKET_NAME`). Never committed to source.

### Local deploy mirror

`scripts/package_lambdas.sh` is the same packaging step used in CI, so `cdk deploy` from a developer laptop produces identical Lambda artifacts as CI. This eliminates "works on my machine but not in production" Lambda-packaging bugs.

---

## 10. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Foundation-model character drift across pages | Medium | Verbatim-repeated character description in image prompt produces consistent characters across the majority of pages. |
| Foundation-model spatial composition non-adherence | Low (mitigated) | Layered defense: prompt requests calm bottom + cream band overlay always provides text contrast. |
| Cost spike from runaway pipeline (e.g., infinite retry loop) | Low | Step Functions has 10-minute total timeout; per-Lambda timeouts prevent any single step from running unbounded; no auto-retry on API failures (failed → MarkFailed → done). |
| Vendor lock-in to OpenAI / Anthropic | Medium | Hexagonal architecture means swapping providers is a single-class change. Demonstrated when the project replaced DALL-E 3 with gpt-image-1. |
| Anthropic / OpenAI service outage | Low | Pipeline correctly fails fast, surfaces error to user via DDB → retrieval Lambda → frontend. User can retry. |
| API key leak via logs or env vars | Low | Keys in AWS Secrets Manager, fetched at cold start, never logged. CloudFormation templates and CI logs are key-free. |
| S3 PDF URLs leaked or shared | Low | Pre-signed URLs with short expiry; PDFs auto-delete after 30 days via lifecycle rule. No PII in URL paths (UUID only). |
| Capstone reproducibility issue (grader can't deploy) | Low | All infra in CDK; `cdk deploy --all` from a clean checkout works. README + this document explain prerequisite setup. |
| Content-policy blocking on edge cases | Low (validated) | OpenAI moderation handled gracefully — we catch and surface clearly to the user. Most prompts pass. |

---

## 11. Appendix — File Map

```
MyStoryMSSECapstoneAyalaBartal/
├── README.md                          # Project intro + quickstart
├── DESIGN_AND_TESTING.md              # This document
├── WORK_LOG.md                        # Sprint diary, decisions log
├── COSTS.md                           # Cost tracking notes
├── pyproject.toml                     # Pytest config (--import-mode=importlib)
├── requirements.txt                   # Top-level Python deps
├── requirements-dev.txt               # Dev/test deps
├── conftest.py                        # Shared pytest fixtures
│
├── infra/                             # AWS CDK (Python)
│   ├── app.py                         # Stack composition + region/account binding
│   ├── cdk.json                       # CDK config
│   ├── requirements.txt               # CDK deps
│   ├── lambda_packages/               # Built zips (gitignored, output of package_lambdas.sh)
│   └── stacks/
│       ├── storage_stack.py           # 4 S3 buckets + DynamoDB + outputs
│       ├── api_stack.py               # API Gateway + Entry & Retrieval Lambdas
│       ├── pipeline_stack.py          # Story/Image/PDF Lambdas + Step Fns + Secrets Manager
│       └── cicd_stack.py              # (placeholder for self-hosted CI/CD; not used)
│
├── lambdas/
│   ├── README.md                      # Hexagonal Lambda pattern doc
│   ├── entry/
│   │   ├── handler.py                 # AWS entry point
│   │   ├── service.py                 # Business logic
│   │   ├── cards_schema.json          # Schema for input validation
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── story_generation/
│   │   ├── handler.py
│   │   ├── service.py
│   │   ├── adapters.py                # LLMAdapter interface + Anthropic + Mock impls
│   │   ├── prompt_template.txt        # Two-stage structured prompt
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── image_generation/
│   │   ├── handler.py
│   │   ├── service.py
│   │   ├── adapters.py                # ImageAdapter interface + OpenAI + Mock impls
│   │   ├── prompt_style.txt
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── pdf_assembly/
│   │   ├── handler.py
│   │   ├── service.py                 # ReportLab picture-book composition
│   │   ├── layout.json                # Page size, age-tier typography, text-band config, cover config
│   │   ├── requirements.txt
│   │   └── tests/
│   └── retrieval/
│       ├── handler.py
│       ├── service.py
│       ├── utils.py
│       ├── requirements.txt
│       └── tests/
│
├── frontend/                          # React + Vite SPA
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx                    # Card picker, polaroid loader, polaroid complete screen
│       ├── App.css
│       ├── cardsConfig.jsx            # Card definitions (themes, adventures, heroes)
│       ├── loading.webp               # Polaroid loading animation
│       ├── ready.png                  # Polaroid completion image
│       └── assets/cards/              # Card illustration assets
│
├── scripts/
│   ├── package_lambdas.sh             # Build Lambda zip artifacts for cdk deploy
│   ├── generate_card_images.py        # One-off card image generator
│   ├── smoke_test_story_gen.py        # Hit deployed story Lambda end-to-end
│   ├── smoke_test_image_gen.py        # Hit deployed image Lambda end-to-end
│   └── smoke_test_pdf_assembly.py     # Hit deployed PDF Lambda end-to-end
│
└── .github/workflows/
    └── deploy.yml                     # CI/CD pipeline
```

---

**End of document.**
