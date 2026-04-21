# My Story — Design & Testing Document

**Project:** My Story — AI-Powered Personalized Children's Story Generator
**Program:** MSSE Capstone, Quantic School of Business and Technology
**Author:** Ayala Bartal
**Document version:** 0.1 (in-progress working draft)
**Last updated:** 2026-04-21

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
10. [Continuation Roadmap](#10-continuation-roadmap)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Appendix — File Map](#12-appendix--file-map)

---

## 1. Project Overview

**My Story** is a serverless web application that lets children ages 5–8 create a personalized illustrated storybook by picking four cards: a **Hero**, an **Adventure Theme**, a **Challenge**, and a **Secret Strength**. The backend generates a unique 7-page story (written by a fine-tuned LLaMA 3 8B language model) with matching AI-generated illustrations (from a fine-tuned Stable Diffusion model), assembles the result into a PDF storybook, and delivers it back to the child as a downloadable file.

The card system yields **128 unique story combinations** (2 × 4 × 4 × 4).

### Business goals

- Demonstrate an end-to-end AI-powered product built with modern serverless cloud patterns
- Produce tangible, share-able output (a PDF storybook) rather than a purely screen-based experience
- Practice LLM and diffusion-model fine-tuning with LoRA on consumer hardware (Apple MLX / PyTorch MPS)

### Success criteria

- A child can complete the full flow — card selection → generated story → PDF download — in under two minutes end-to-end
- The deployed system works from a public URL on both desktop and mobile
- All infrastructure is reproducible via `cdk deploy --all` from a clean checkout
- Unit and integration tests run automatically on every pull request via GitHub Actions

---

## 2. User Stories & Scope

### Core user stories (from Trello backlog)

1. As a child, I can see and select a **Hero** card (boy or girl) with an illustration so I can identify with my hero.
2. As a child, I can select an **Adventure Theme** card (Space, Under the Sea, Medieval Fantasy, Dinosaurs) so my story world is set.
3. As a child, I can select a **Challenge** card and see how it adapts to my chosen theme.
4. As a child, I can select a **Secret Strength** card so my hero has a special power.
5. As a user, I can click **Generate My Story** and receive a personalized 7-page story based on my 4 card selections.
6. As a user, I can see **AI-generated illustrations** alongside the story text for each illustrated page.
7. As a user, I can **download** the complete story as a formatted PDF storybook with a custom cover image.
8. As a parent, I can **save and revisit** previously generated stories.
9. As a user, I can access the website from any device (**mobile-friendly**).

### Out of scope (deliberately)

- User accounts / authentication (stories are identified by UUID only; privacy via obscurity for the Capstone demo)
- Payments, subscriptions, or usage quotas
- Multi-language support (English only for v1)
- Editing or regenerating individual pages after generation
- Moderation / content filtering beyond what the base models already provide

---

## 3. System Architecture

### High-level flow

```
Frontend (S3 static site)
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
        HuggingFace Endpoint         Replicate API                   ReportLab
        (fine-tuned LLaMA 3 8B)      (fine-tuned SD 1.5)                    │
                                                                            ▼
                                                                   S3 (PDFs bucket)
                                                                            +
                                                              DynamoDB (status: COMPLETE)
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
| **CloudWatch** | Logging, metrics, cost alerts |
| **IAM** | Least-privilege roles per Lambda |
| **AWS CDK** | Infrastructure-as-Code (Python) |

### External services

| Service | Purpose | Why |
|---|---|---|
| **HuggingFace Inference Endpoints** | Host the fine-tuned LLaMA 3 8B | Cheapest managed GPU inference for custom HF-format LoRA weights |
| **Replicate** | Host the fine-tuned Stable Diffusion model | Pay-per-second GPU billing, simple CLI push, free tier for testing |
| **GitHub Actions** | CI/CD | Free for public repos; native GitHub integration |

---

## 4. Design & Architecture Decisions

### Why serverless AWS

- **Unpredictable, bursty load.** A capstone demo may see zero traffic for days and then a spike during the recorded walkthrough. Per-request billing on Lambda and DynamoDB means we pay only when a story is generated, not for idle capacity.
- **No servers to manage.** Graders should be able to `cdk deploy --all` and have a working system in under 15 minutes.
- **CDK (Python) over raw CloudFormation or Terraform.** Python keeps the infra language consistent with the Lambda code; higher-level CDK constructs (e.g. `tasks.LambdaInvoke`, `s3.Bucket`) dramatically cut boilerplate versus hand-written CloudFormation. Python was chosen over TypeScript for CDK because all other code in the project is Python.

### Why Step Functions for the pipeline

- The story flow is **inherently sequential** (text must exist before images can be prompted from it; PDF must wait for images) but also **long-running** (a fine-tuned LLaMA call on HF Inference can take 30–60s, Stable Diffusion 10–20s per image × 7 images). Running the whole thing inside a single Lambda risks the 15-minute cap and burns memory-time budget on waiting.
- Step Functions lets each stage be its own short-lived Lambda, with built-in retries, error handling, and a visual execution history that is excellent for debugging and for the capstone demo video.
- An alternative was SQS + polling, but Step Functions gave us a state machine with zero queue-management code.

### Why five Lambdas instead of one

- **Single-responsibility principle** — each Lambda owns one concern (validation, text gen, image gen, PDF assembly, retrieval). Easier to test, easier to reason about, and each can be independently resized on memory and timeout.
- The `story_generation` and `image_generation` Lambdas are I/O-bound (waiting on external APIs) and can run at 512 MB. `pdf_assembly` is CPU-bound (ReportLab) and will likely need 1024 MB. Keeping them separate means we're not overpaying memory for I/O-bound functions.

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
| `my-story-images-<acct>` | Private (served via pre-signed URL if ever directly linked) | None |
| `my-story-pdfs-<acct>` | Private; access via pre-signed URL only | **Expire objects after 30 days** |

This also means that leaking a PDF URL doesn't leak the illustration source files, and vice versa.

### Why fine-tune rather than use the base models with prompt engineering

- **Brand/voice control.** Base LLaMA 3 8B writes in a generic assistant voice; after LoRA fine-tuning on children's literature (Brothers Grimm + Children's Book Test dataset), output is more consistently in storybook register.
- **Output format reliability.** Fine-tuning on 5-beat story structures means the model produces the beat layout we need far more reliably than a prompt template against a base model.
- **Portfolio value.** A fine-tuned model is a more compelling artifact for a Capstone submission than prompt engineering against GPT-4.
- **Cost.** Fine-tuning is done once on a local Apple M5 (MLX / PyTorch MPS), then served from HuggingFace Inference at per-second GPU rates — materially cheaper than paying OpenAI per token at the expected volume.

### Why LoRA specifically

- Full fine-tuning of an 8B model is infeasible on consumer hardware.
- LoRA adapters train in hours instead of days and produce small (~50 MB) weight files that are easy to version and upload.

---

## 5. Software & Architectural Patterns

### Architectural patterns in use

1. **Serverless / FaaS** — every compute is a Lambda; no long-running servers.
2. **Event-driven pipeline** — the Entry Lambda emits a pipeline start event; downstream Lambdas react via Step Functions.
3. **Orchestrator pattern (Step Functions)** — a central state machine coordinates the three pipeline Lambdas rather than each Lambda triggering the next (choreography). This was chosen for visibility and centralized retry logic.
4. **Infrastructure-as-Code** — all AWS resources are defined in `infra/stacks/*.py` via CDK. No click-ops.
5. **CQRS-lite** — writes go through `POST /generate` (command), reads go through `GET /story/{id}` (query), backed by two different Lambdas and two different IAM policies.
6. **Separation of concerns by bucket/table** — each S3 bucket and the DynamoDB table has exactly one logical owner Lambda for writes.

### Software patterns in use

- **Input validation at the edge.** The Entry Lambda validates card selections against a whitelist before any persistence or pipeline trigger (`lambdas/entry/handler.py` → `validate_input`).
- **Idempotent pipeline execution name.** Step Functions execution name is set to the `story_id` so retrying the same generation can't spawn duplicate pipelines.
- **Graceful error envelopes.** Every API-facing Lambda returns JSON bodies with `statusCode`, CORS headers, and an `error` field on failure — never a bare 500 HTML page.
- **Environment-variable configuration.** Bucket names, table names, and state machine ARNs are passed through Lambda environment variables at deploy time by CDK — no hard-coded resource identifiers in handler code.

---

## 6. Deployment Strategy & Cost

### Recommended deployment: AWS cloud (us-east-1)

This project is cloud-first by design. On-premises deployment was rejected for the following reasons:

- Five Lambdas, Step Functions, and managed DynamoDB have no direct on-prem equivalent that wouldn't require substantial re-architecture (self-hosted k8s + Argo Workflows + Postgres, for example).
- The fine-tuned models are hosted on HuggingFace / Replicate regardless — on-prem for just the orchestration layer wouldn't meaningfully reduce cloud dependency.
- For a demo-scale workload (<100 stories/day), on-demand cloud pricing is much cheaper than any self-hosted alternative.

### Cost estimate (demo-scale, us-east-1)

For 100 generated stories per month:

| Component | Est. monthly cost |
|---|---|
| Lambda invocations (5 × 100 = 500 invocations) | < $0.01 |
| Step Functions state transitions (~15 per story × 100) | < $0.05 |
| DynamoDB on-demand (100 writes, ~500 reads) | < $0.01 |
| S3 storage (PDFs expire at 30 days; illustrations retained) | ~$0.05 |
| API Gateway (600 requests) | < $0.01 |
| CloudWatch logs | ~$0.10 |
| **AWS subtotal** | **~$0.25 / month** |
| HuggingFace Inference Endpoint (scale-to-zero, charged per minute of cold-start + inference) | $10–30 / month depending on usage |
| Replicate (per-second GPU) | $3–10 / month depending on usage |
| **Total** | **~$15–40 / month at demo scale** |

The dominant cost is **model hosting**, not AWS itself. If budget becomes a concern post-submission, the HF endpoint can be set to scale-to-zero and Replicate only charges for actual inference.

### Scale-up considerations (not implemented, documented for completeness)

- **CloudFront** in front of the frontend S3 bucket — reduces latency + adds HTTPS with a custom domain.
- **Provisioned concurrency** on the Entry Lambda if cold start becomes visible in the UX.
- **SQS dead-letter queue** on each pipeline Lambda to catch poison messages.
- **Step Functions Express Workflows** if transitions/month ever exceeds ~100k (cheaper per transition than Standard Workflows at that volume).

---

## 7. Current Implementation Status

Honest snapshot of the repo as of the document's `Last updated` date, cross-referenced with the Trello board.

### ✅ Done — built and working

| Component | File | Notes |
|---|---|---|
| CDK app wiring | `infra/app.py` | Four stacks composed with explicit env (account, region). |
| Storage stack | `infra/stacks/storage_stack.py` | 4 S3 buckets + DynamoDB `my-story-stories` table with TTL. |
| API stack | `infra/stacks/api_stack.py` | API Gateway + Entry & Retrieval Lambdas + IAM + CORS. |
| Pipeline stack | `infra/stacks/pipeline_stack.py` | Story / Image / PDF Lambdas + Step Functions state machine. |
| Entry Lambda | `lambdas/entry/handler.py` | Full implementation: input validation, DynamoDB write, Step Functions trigger, error envelopes. |
| CI/CD workflow | `.github/workflows/deploy.yml` | GitHub Actions: test → deploy infra → deploy frontend. |
| README | `README.md` | Architecture diagram, setup, sprint timeline. |

### 🔄 In progress

| Component | Trello card | State |
|---|---|---|
| Card selection frontend | "Wireframe card selection UI" | `frontend/index.html`, `app.js`, `styles.css` all exist but are empty. |
| Story generation Lambda | "Build story_generation Lambda" | `lambdas/story_generation/handler.py` returns placeholder beats. |

### ⏳ Stubbed (placeholder `handler.py` exists, no real logic)

- `lambdas/image_generation/handler.py` — returns `image_urls: []`.
- `lambdas/pdf_assembly/handler.py` — returns `pdf_url: "placeholder"`.
- `lambdas/retrieval/handler.py` — returns a generic placeholder message.
- `infra/stacks/cicd_stack.py` — empty class body with a TODO.

### 🚫 Not yet started

- Unit tests — **no `tests/` folders exist** under any Lambda, though the CI workflow expects them (currently soft-failing with `|| true`).
- ML training code — `ml/llm/train.py`, `evaluate.py` and `ml/mage_model/train.py`, `evaluate.py` are all empty files.
- Pre-generated card illustrations (14 total: 2 heroes + 4 themes + 4 challenges + 4 strengths).
- Design PDF layout.
- "Saved stories" page.
- Mobile-responsive CSS.
- Final demo video.
- Linked deployed URL in the README.

### Board hygiene notes

A few Trello cards in **To Do** are actually already done in code and should be moved to **Done**:

- "Build API Gateway + Entry Lambda" — entry Lambda is live and routed through API Gateway.
- "Build card selection frontend" appears twice in **To Do** (likely a duplicate card).

### Known issues / typos

- `ml/mage_model/` folder is misspelled — should be `ml/image_model/` per the README's architecture section.
- `lambdas/story_generation/handler.py` and `lambdas/image_generation/handler.py` both carry the comment "Sprint 2 Task 23" — they should probably be split into two separate tracking tasks.
- Two environment variables in `pipeline_stack.py` are literally `"PLACEHOLDER"` (`HF_ENDPOINT_URL`, `REPLICATE_API_TOKEN`). These need to be moved to AWS Secrets Manager or Systems Manager Parameter Store before first real deploy.

---

## 8. Testing Strategy

### Testing pyramid

```
              ┌──────────────────────┐
              │  E2E (manual demo)   │  ← recorded demo video for submission
              └──────────────────────┘
          ┌────────────────────────────┐
          │ Integration tests (moto)   │  ← full pipeline with mocked AWS
          └────────────────────────────┘
     ┌──────────────────────────────────────┐
     │       Unit tests (pytest)            │  ← one tests/ folder per Lambda
     └──────────────────────────────────────┘
```

### Unit tests — per-Lambda

Each `lambdas/<name>/tests/` folder will contain:

- **`test_handler.py`** — table-driven tests of `lambda_handler` for happy paths and each error branch.
- **`test_<specific_helper>.py`** — isolated tests for pure helper functions (e.g. `validate_input` in the Entry Lambda).

**Tools:**

- `pytest` — test runner (already in `requirements.txt`).
- `moto` — mocks DynamoDB, S3, and Step Functions locally so no AWS credentials are needed for unit tests.
- `responses` — mocks the HuggingFace and Replicate HTTP calls in `story_generation` and `image_generation` tests.
- `pytest-cov` — coverage reporting, already invoked in the CI workflow.

**Target coverage:** ≥ 80% line coverage per Lambda.

### Test plan per Lambda

| Lambda | Key test cases |
|---|---|
| **entry** | Valid payload returns 202 with `story_id`; each missing field returns 400; each invalid enum value returns 400; DynamoDB failure returns 500; Step Functions failure returns 500; request with no body returns 400. |
| **story_generation** | Happy path returns 7 beats with correct keys; HuggingFace timeout triggers retry; HuggingFace 500 returns structured error; malformed model output is rejected. |
| **image_generation** | Happy path returns image URLs for every illustrated page; Replicate rate-limit is retried with backoff; failed image defaults to a neutral placeholder so the PDF can still assemble. |
| **pdf_assembly** | Happy path writes a PDF to S3 and updates DynamoDB status to `COMPLETE`; missing image gracefully omitted; DynamoDB write failure still leaves the PDF reachable. |
| **retrieval** | Status `PROCESSING` returns 202 with no URL; status `COMPLETE` returns 200 with pre-signed URL; missing `story_id` returns 404; expired TTL record returns 410. |

### Integration tests

A single `tests/integration/test_pipeline.py` will:

1. Spin up moto-mocked AWS (S3, DynamoDB, Step Functions).
2. Invoke the Entry Lambda with a valid payload.
3. Invoke each pipeline Lambda in sequence with the handoff payload.
4. Assert the final DynamoDB record shows `COMPLETE` and points to a real S3 object.

This catches envelope-shape mismatches between Lambdas (the most common bug in Step Functions pipelines).

### Manual / end-to-end

- Recorded demo (Sprint 3 deliverable): full user journey on the deployed URL, showing cards → generation → PDF download, across two card combinations.
- Cross-browser spot checks: Chrome desktop, Safari iOS (for the mobile-friendly user story).

### What testing is **not** doing

- No load testing. At demo scale this isn't worth the time budget.
- No security scanning (SAST). Not a Capstone requirement; noted as future work.
- No visual-regression testing on the frontend. Manual spot check is sufficient.

---

## 9. CI/CD Pipeline

`.github/workflows/deploy.yml` runs on every push to `main` and on every pull request.

### Jobs

1. **`test`** — installs each Lambda's dependencies, runs its `tests/` folder with `pytest --cov`, uploads coverage artifact on PRs. Currently tolerant of missing test folders (`|| true`) — that tolerance should be removed once tests exist.
2. **`deploy-infra`** (main branch only) — configures AWS credentials from GitHub secrets, packages each Lambda into a zip, runs `cdk deploy --all --require-approval never`, uploads the CDK outputs as an artifact.
3. **`deploy-frontend`** (main branch only, after infra deploy) — syncs `frontend/` to the S3 frontend bucket.

### Secrets expected

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `FRONTEND_BUCKET_NAME`

### Known gaps

- CloudFront invalidation is a placeholder (`echo "..."`) — it will become real once CloudFront is added.
- No branch protection is enforced at the repo level — the workflow relies on team discipline. Should enable "require CI to pass" on `main` before submission.
- `cicd_stack.py` (the CDK stack for an AWS-native CodePipeline) is empty. The GitHub Actions workflow is currently the entire CI/CD, and that is fine for Capstone — the `cicd_stack` can remain unimplemented or be deleted.

---

## 10. Continuation Roadmap

This section documents what's left and the suggested order.

### Guiding principle

**Get the full pipeline running end-to-end with mocked models first**, then swap in the real fine-tuned models. This lets us demo a working system even if training runs late, and dramatically reduces integration risk.

### Sprint 2 — remaining work (core app + LLM)

Ordered by dependency:

1. **Finish the frontend skeleton** (currently empty) — wireframed card selection, calls `POST /generate`, polls `GET /story/{id}`.
   - Files: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`.
   - Can be built against a stubbed backend that returns a canned response.
2. **Build the Retrieval Lambda** — smallest remaining Lambda, unblocks the frontend.
   - File: `lambdas/retrieval/handler.py`.
   - Reads DynamoDB by `story_id`; if `COMPLETE`, returns a pre-signed S3 URL; else returns 202 with status.
3. **Build the Story Generation Lambda with a mock backend first.**
   - Return a hard-coded 7-beat story matching the card inputs so the pipeline is exercisable end-to-end.
   - Wire in the real HuggingFace Inference call behind a feature flag / env var once the model is deployed.
4. **Prepare the LLM training dataset.**
   - Brothers Grimm + Children's Book Test → clean, tokenize, format as 5-beat instructions.
5. **Fine-tune LLaMA 3 8B with LoRA on Apple MLX.**
6. **Upload LoRA weights to HuggingFace Hub → deploy to HuggingFace Inference Endpoint.**
7. **Swap the Story Generation Lambda from mock to real HF endpoint.**
8. **Write unit tests for Entry + Story Generation** (Trello backlog).

### Sprint 3 — image model + PDF + deployment

1. **Pre-generate 14 card illustrations** (this can be started in parallel — no ML pipeline dependency). Upload to the `cards` S3 bucket.
2. **Add card illustrations to frontend.**
3. **Make UI mobile-responsive.**
4. **Design PDF layout.** Mock it in Figma or on paper first.
5. **Build the Image Generation Lambda with a mock backend** that returns placeholder images from the `cards` bucket.
6. **Build the PDF Assembly Lambda** — ReportLab, 7 pages + cover, uses placeholder images from step 5.
   - At this point the whole pipeline runs end-to-end with mocked ML and real PDF output. This is the minimum demonstrable slice.
7. **Prepare image model training dataset + fine-tune Stable Diffusion 1.5 with LoRA.**
8. **Push to Replicate and deploy.**
9. **Swap the Image Generation Lambda from mock to real Replicate call.**
10. **Build the saved-stories page** (lower priority — can slip).
11. **Write unit tests for Image Generation + PDF Assembly.**
12. **Complete this design & testing document** (it should be final before submission).
13. **Record 15–20 minute demo video** — all team members on camera, government ID held up, screen share of working deployed app.

### Explicit dependencies

```
Frontend skeleton ──► Retrieval Lambda ──► End-to-end with stubs
                              │
LLM dataset ──► LoRA train ──► HF upload ──► HF endpoint ──► Story Lambda real
                              │
Image dataset ──► SD LoRA ──► Replicate push ──► Image Lambda real
                              │
                     Card illustrations pre-generated ──► Frontend uses them
                              │
                     PDF layout design ──► PDF Lambda ──► Pipeline complete
                                                  │
                              Design doc final ──┴──► Demo video ──► Submit
```

### Suggested order for the **next** work session

If picking up from the current state:

1. Finish the `retrieval` Lambda (smallest, highest unblocking value, ~30–60 min).
2. Write `tests/` folders + smoke tests for `entry` and `retrieval` (the two done Lambdas) to validate the CI pipeline actually passes.
3. Write the minimum-viable `index.html` + `app.js` so the page renders four card rows, lets you click through them, and POSTs to `/generate`.

After that, you'd have a real, testable foundation and could decide whether to push on the LLM fine-tune or the PDF assembly next based on which feels like the bigger risk.

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLaMA 3 8B LoRA fine-tune doesn't fit / is unusably slow on Apple M5 | Medium | High | Fall back to a smaller base model (LLaMA 3 1B or Mistral 7B); accept lower quality output for the Capstone. |
| HuggingFace Inference Endpoint cold start > 30s ruins the UX | High | Medium | Warm the endpoint before the demo; document the cold-start behavior in the video. Long-term: provisioned capacity. |
| Replicate billing accidentally drained (runaway generation) | Low | High | Set a hard monthly spend cap in Replicate dashboard; log every API call and add a CloudWatch alarm on `image_generation` invocation count. |
| Fine-tuned model produces inappropriate content for children | Low | High | Keep a pre-generation profanity/keyword check on card-combined prompts; post-generation regex scan; test with edge prompts before the demo. |
| AWS account gets misconfigured (public bucket contains private PDFs) | Low | High | Bucket split (see §4) means PDFs bucket is never public; pre-signed URLs only. CDK tests should assert this. |
| Capstone deadline hits before ML fine-tunes are ready | Medium | Medium | Keep the "mock ML" pipeline path working at all times; demo can ship with mock responses if needed. |
| Tests never get written and CI stays soft-failing | Medium | Medium | Write tests for `entry` and `retrieval` (the done Lambdas) **first**, before any new feature work. Remove the `|| true` from the CI step once green. |
| Frontend lags the backend and demo video has nothing to show | High | High | Build an ugly-but-working frontend before any polish. Polish is Sprint 3's job. |
| Unreproducible infra drift between CDK and actual AWS | Low | Medium | Never click-op in the AWS console. Every change goes through `cdk deploy`. |

---

## 12. Appendix — File Map

```
MyStoryMSSECapstoneAyalaBartal/
├── README.md                            ✅ done
├── DESIGN_AND_TESTING.md                ✅ this file
├── requirements.txt                     ✅ done
├── .gitignore                           ✅ done
│
├── infra/                               ✅ done (except cicd_stack)
│   ├── app.py                           ✅
│   ├── cdk.json                         ✅
│   ├── requirements.txt                 ✅
│   └── stacks/
│       ├── __init__.py                  ✅
│       ├── storage_stack.py             ✅
│       ├── api_stack.py                 ✅
│       ├── pipeline_stack.py            ✅
│       └── cicd_stack.py                ⏳ empty (optional — GH Actions covers CI/CD)
│
├── lambdas/
│   ├── entry/
│   │   ├── handler.py                   ✅ fully implemented
│   │   ├── requirements.txt             ✅
│   │   └── tests/                       🚫 not created
│   ├── story_generation/
│   │   ├── handler.py                   ⏳ placeholder (Trello "In Progress")
│   │   ├── requirements.txt             ✅
│   │   └── tests/                       🚫
│   ├── image_generation/
│   │   ├── handler.py                   ⏳ placeholder
│   │   ├── requirements.txt             ✅
│   │   └── tests/                       🚫
│   ├── pdf_assembly/
│   │   ├── handler.py                   ⏳ placeholder
│   │   ├── requirements.txt             ✅
│   │   └── tests/                       🚫
│   └── retrieval/
│       ├── handler.py                   ⏳ placeholder
│       ├── requirements.txt             ✅
│       └── tests/                       🚫
│
├── frontend/                            🚫 all empty
│   ├── index.html                       🚫
│   ├── app.js                           🚫
│   └── styles.css                       🚫
│
├── ml/
│   ├── llm/                             🚫 all empty
│   │   ├── train.py                     🚫
│   │   ├── evaluate.py                  🚫
│   │   └── requirements.txt             🚫
│   └── mage_model/   (⚠ typo — should be image_model)
│       ├── train.py                     🚫
│       ├── evaluate.py                  🚫
│       └── requirements.txt             🚫
│
└── .github/
    └── workflows/
        └── deploy.yml                   ✅ done
```

**Legend:** ✅ complete · 🔄 in progress · ⏳ stubbed · 🚫 not started

---

*End of document.*
