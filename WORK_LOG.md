# My Story — Work Log

Rolling log of working sessions, decisions made, and where we left off. Add new sessions at the **top**.

---

## How to resume

When you come back to this project (new session, new day, new Claude conversation):

1. Activate the venv: `source .venv/bin/activate`
2. Read the most recent session entry below to remember context
3. Read `DESIGN_AND_TESTING.md` for the full architecture + roadmap
4. Check the Trello board for current sprint state
5. Tell Claude: "read WORK_LOG.md and DESIGN_AND_TESTING.md to catch up"

---

## Session 1 — 2026-04-21

### Who & context
- **Ayala** — MSSE Capstone student + Amazon engineer
- Strong AWS / software engineering background, **new to AI/ML**
- Prefers: step-by-step guidance, well-written extensible code, the *why* behind decisions
- Returned to the project after "my entire plan was deleted"

### What we did
1. Full repo + Trello board review to re-establish context
2. Created **`DESIGN_AND_TESTING.md`** — formal design doc (rubric requirement) + recovered continuation roadmap
3. Cleaned up local dev environment — moved from global pip installs to a project `.venv`
4. Added **`requirements-dev.txt`** at repo root
5. Rewrote the **Local Development Setup** section of `README.md`
6. Made the **per-Lambda `requirements.txt`** separation explicit and architectural (not accidental)

### Key decisions

- **Implementation strategy:** Finish the backend with **mock ML responses first**, prove the full pipeline end-to-end, then swap real fine-tuned models in last. Reduces Capstone-deadline risk; debugging is easier with a known-good baseline.
- **Architecture pattern for Lambdas:** **Hexagonal / ports-and-adapters.** Thin `handler.py` (AWS entry point) → pure `service.py` (business logic, unit-testable without mocks) → shared `lambdas/_shared/` module for CORS helpers / error types / structured logging. Applies to every Lambda.
- **Per-Lambda `requirements.txt` stays separate on purpose** — preserves the future option to split any Lambda into its own standalone service/repo without reworking dependency management.
- **Three levels of Python dependencies:**
  - `lambdas/<name>/requirements.txt` → deployment contract for that Lambda only (bundled into zip)
  - `requirements-dev.txt` (root) → local test tooling (pytest, pytest-cov, moto, boto3, responses)
  - `infra/requirements.txt` → CDK tooling
- **Python 3.11 in `.venv/`** — matches the Lambda runtime in AWS; avoids the 3.9/3.11 mismatch Ayala's system Python had.

### State of the code (as of session end)

**✅ Done**
- CDK stacks: storage, api, pipeline (all working)
- Entry Lambda fully built (`lambdas/entry/handler.py`)
- CI/CD workflow (`.github/workflows/deploy.yml`)
- `README.md` (recently updated)
- `DESIGN_AND_TESTING.md` (new this session)
- `requirements-dev.txt` (new this session)

**🔄 In progress (Trello)**
- Frontend (`frontend/index.html`, `app.js`, `styles.css` — all empty)
- Story Generation Lambda (placeholder handler)

**⏳ Stubbed (placeholder `handler.py` only)**
- retrieval, image_generation, pdf_assembly Lambdas
- `infra/stacks/cicd_stack.py` (empty class)

**🚫 Not started**
- Any `tests/` folders (CI soft-fails with `|| true`)
- ML training code (`ml/llm/*.py`, `ml/mage_model/*.py` all empty)
- 14 pre-generated card illustrations
- Saved-stories page
- Mobile-responsive CSS
- Demo video

**Known issues to fix later**
- Typo: `ml/mage_model/` should be `ml/image_model/` per README
- `HF_ENDPOINT_URL` and `REPLICATE_API_TOKEN` are literal `"PLACEHOLDER"` strings in `pipeline_stack.py` — move to Secrets Manager before first real deploy

### Trello board hygiene notes
- **"Build API Gateway + Entry Lambda"** is in **To Do** but is actually done → move to Done
- **"Build card selection frontend"** appears twice in To Do → dedupe one

### Where we left off
- Local dev env: `.venv` active, `requirements-dev.txt` installed, test sanity check passes (`import pytest, moto, boto3; print('OK')` → `OK`)
- Not yet committed to git: `DESIGN_AND_TESTING.md`, `requirements-dev.txt`, README updates, this work log
- Ready to start **Step 1 of the implementation plan** (see below)

### Full implementation plan (the recovered roadmap)

**Phase 1 — establish clean foundation**
1. Create `lambdas/_shared/` module (`responses.py`, `errors.py`, `logging.py`)
2. Refactor Entry Lambda to use the pattern (split handler.py into handler + service)
3. Write tests for Entry Lambda (validates the pattern + greens up CI)
4. Build Retrieval Lambda using the pattern + tests
5. Add `lambdas/README.md` documenting the pattern

**Phase 2 — end-to-end pipeline with mocks**
6. Build frontend skeleton (HTML + card selection + POST /generate + poll GET /story/{id})
7. Build Story Generation Lambda with mock (canned 7-beat response)
8. Build Image Generation Lambda with mock (reuses pre-generated card images)
9. Build PDF Assembly Lambda (ReportLab, real — doesn't depend on ML)
10. End-to-end test: cards → story → PDF works on deployed AWS
11. Pre-generate the 14 card illustrations
12. Make frontend mobile-responsive

**Phase 3 — swap in real AI**
13. Prepare LLM training dataset (Brothers Grimm + Children's Book Test)
14. Fine-tune LLaMA 3 8B with LoRA on Apple MLX
15. Upload LoRA weights to HuggingFace Hub → deploy to HuggingFace Inference Endpoint
16. Swap Story Generation Lambda from mock to real HF endpoint
17. Prepare image-model dataset + fine-tune Stable Diffusion 1.5 with LoRA
18. Push to Replicate and deploy
19. Swap Image Generation Lambda from mock to real Replicate call

**Phase 4 — polish and submit**
20. Fill test gaps (image_gen + pdf_assembly tests, integration tests)
21. Build saved-stories page
22. Finalize `DESIGN_AND_TESTING.md`
23. Record 15–20 min demo video (all on camera, gov ID held up)
24. Submit

### Immediate next step (Step 1)

Create the shared module:

```
lambdas/
└── _shared/
    ├── __init__.py
    ├── responses.py   # make_response(), cors_headers()
    ├── errors.py      # ValidationError, NotFoundError, StoryProcessingError
    └── logging.py     # get_logger() — structured JSON logger
```

Then refactor `lambdas/entry/handler.py` to use them and write the first real test suite.

### Commit command when ready

```bash
git add README.md requirements-dev.txt DESIGN_AND_TESTING.md WORK_LOG.md
git commit -m "docs: add design doc, work log, dev requirements, update README setup

- DESIGN_AND_TESTING.md: formal design doc with architecture decisions,
  testing strategy, continuation roadmap
- WORK_LOG.md: rolling session notes
- requirements-dev.txt: local test tooling (pytest, moto, boto3, responses)
- README: rewrote Local Development Setup to use virtualenv;
  explain per-Lambda vs dev vs CDK requirements separation"
```

---

*Add future session entries above this line, newest first.*
