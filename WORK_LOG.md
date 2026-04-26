# My Story — Work Log

Rolling log of working sessions, decisions made, and key technical pivots. Add new sessions at the **top**.

---

## How to resume

When you come back to this project (new session, new day, new conversation):

1. Activate the venv: `source .venv/bin/activate`
2. Read the most recent session entry below to remember context
3. Read `DESIGN_AND_TESTING.md` for the full architecture
4. Check the Trello board for current sprint state

---

## Session 2 — 2026-04-25 — Project completion

### Summary

Capstone is feature-complete and deployed. All five Lambdas built, tested, integrated, and running in production. Frontend deployed to S3 static website. End-to-end pipeline (cards → story → illustrations → PDF → download) works reliably. Ready for demo recording and Quantic submission.

### What was built since Session 1

**Pipeline Lambdas (all done with hexagonal architecture)**
- **Story Generation Lambda** — `AnthropicLLMAdapter` wrapping the Anthropic SDK, `MockLLMAdapter` for tests. Two-stage prompt template producing both `text` and `image_prompt` per page in a single structured JSON response.
- **Image Generation Lambda** — `OpenAIImageAdapter` wrapping the OpenAI Images SDK, `MockImageAdapter` for tests. Generates 5 illustrations per story, uploads to S3.
- **PDF Assembly Lambda** — ReportLab. Built up iteratively: started with letter-portrait pages and basic text, evolved to square 8×8 picture-book format with cover page, full-bleed illustrations, semi-transparent cream text overlay band, age-tiered typography, and `KeepInFrame` overflow protection.
- **Retrieval Lambda** — built first as the canonical example of the hexagonal pattern; pre-signed S3 URL generation for PDF download.

**Frontend (React + Vite)**
- Card picker with name + age inputs
- Polaroid-framed loading state with custom WebP animation
- Polaroid-framed completion screen with custom illustration
- Polling state machine (`picking → generating → complete | failed`)
- Deployed to S3 static website hosting

**Card images**
- 14 illustrations across 4 categories (heroes, themes, adventures, age placeholders)
- Stored in dedicated public S3 bucket
- Used both as frontend selection cards and as PDF cover backgrounds

**Tests**
- 122+ unit tests across all five Lambdas
- All use mock adapters or stubbed AWS callables; zero real network calls
- Pytest config in `pyproject.toml` with `--import-mode=importlib` so each Lambda's tests can import its sibling modules cleanly

**CI/CD**
- GitHub Actions workflow: test → package Lambdas → deploy infra → deploy frontend
- Local equivalent via `scripts/package_lambdas.sh` + `cdk deploy --all`

### Key technical pivots (decisions that changed mid-project)

1. **Chose foundation models with structured prompt engineering instead of fine-tuning custom models.** Original Session 1 plan included Phase 3: fine-tune LLaMA 3 8B + Stable Diffusion 1.5 with LoRAs on the M5 Mac, deploy to HuggingFace + Replicate. After scoping the actual time required (weeks of dataset prep, training, model serving setup) against the capstone timeline, the call was to use Anthropic Claude Haiku + OpenAI gpt-image-1 directly. Quality is excellent, integration was hours not weeks, and the hexagonal architecture preserves the option to swap in custom-trained models later without business-logic changes.

2. **Swapped DALL-E 3 → gpt-image-1 mid-project.** Initial Image Generation Lambda used DALL-E 3 HD. Two limitations drove the upgrade: (a) character drift across pages (5 different-looking children in the same story) even with verbatim-repeated character descriptions in prompts, and (b) DALL-E 3 ignoring spatial composition rules ~60% of the time. `gpt-image-1` (gpt-4o image generation) is materially better at both, and cheaper at medium quality ($0.042/image vs $0.08 for DALL-E 3 HD). The swap was a single-class change thanks to the hexagonal architecture — no business logic, no orchestration, no Lambda config changes needed.

3. **Schema redesign: removed `strength` card, added `name` + `age` inputs.** Original spec had four cards including a "Secret Strength" card. Pivoted to: 3 cards (hero, theme, adventure) + free-text name input + age dropdown. Reasons: (a) real personalization (the kid's actual name as the hero) is more emotionally resonant than a 4th card category, (b) age input enables age-appropriate vocabulary calibration in the prose, (c) simpler and less cluttered UI. Schema-driven validation in the Entry Lambda made this a one-JSON-file change.

4. **Picture-book PDF format instead of letter-portrait.** Initial PDF design rendered text below the image on letter-portrait pages — read like a research paper, not a children's book. Rebuilt around square 8×8 inch pages (the dominant trim size for picture books), full-bleed illustrations, and text overlaid in a soft cream band at the bottom. Added a cover page using the selected theme card image as a full-bleed background.

5. **Layered text-legibility defense.** Tried multiple solo approaches (fully transparent overlay, fully opaque band, dynamic placement) and ultimately landed on layered defense: prompt requests calm bottom + cream band overlay (50% opacity) + bold italic dark text + `KeepInFrame(mode="shrink")` overflow protection. Each layer fails gracefully into the next.

### Final state

**✅ Done**
- All 5 Lambdas built, tested, deployed
- Step Functions pipeline with centralized failure handling
- React + Vite frontend deployed to public S3 URL
- Picture-book PDF format with cover, full-bleed illustrations, age-tiered typography
- 14 card illustrations
- 122+ unit tests passing
- CI/CD workflow live
- Documentation: `DESIGN_AND_TESTING.md`, `README.md`, `COSTS.md`, `lambdas/README.md`, this file

**📋 Submission checklist**
- [x] GitHub repo with code, shared with `quantic-grader`
- [x] Deployed app URL
- [x] Trello board up to date
- [x] `DESIGN_AND_TESTING.md` complete
- [ ] Demo video recorded
- [ ] Submit on Quantic dashboard

### Where we left off

Project is feature-complete. Final tasks: record the 15-20 minute demo video and submit on the Quantic dashboard.

---

## Session 1 — 2026-04-21

### Who & context
- **Ayala** — MSSE Capstone student + Amazon engineer
- Strong AWS / software engineering background, **new to AI/ML**
- Prefers: step-by-step guidance, well-written extensible code, the *why* behind decisions
- Returned to the project after "my entire plan was deleted"

### What we did
1. Full repo + Trello board review to re-establish context
2. Created **`DESIGN_AND_TESTING.md`** — formal design doc (rubric requirement)
3. Cleaned up local dev environment — moved from global pip installs to a project `.venv`
4. Added **`requirements-dev.txt`** at repo root
5. Rewrote the **Local Development Setup** section of `README.md`
6. Made the **per-Lambda `requirements.txt`** separation explicit and architectural (not accidental)

### Key decisions

- **Implementation strategy:** Finish the backend with **mock ML responses first**, prove the full pipeline end-to-end, then swap real AI providers in. Reduces Capstone-deadline risk; debugging is easier with a known-good baseline.
- **Architecture pattern for Lambdas:** **Hexagonal / ports-and-adapters.** Thin `handler.py` (AWS entry point) → pure `service.py` (business logic, unit-testable) → small `utils.py` (or inline helpers) inside each Lambda. Applies to every Lambda.
- **Each Lambda is a fully self-contained unit. NO shared-code module between Lambdas.** ⚠️ This is non-negotiable — the whole point is that any Lambda can be extracted into its own repo/service later without unwinding an import graph. Documented as a pattern in `lambdas/README.md`.
- **Per-Lambda `requirements.txt` stays separate on purpose** — same rationale: preserves the future option to split any Lambda into its own standalone service/repo without reworking dependency management.
- **Three levels of Python dependencies:**
  - `lambdas/<name>/requirements.txt` → deployment contract for that Lambda only (bundled into zip)
  - `requirements-dev.txt` (root) → local test tooling (pytest, pytest-cov, moto, boto3, responses)
  - `infra/requirements.txt` → CDK tooling
- **Python 3.11 in `.venv/`** — matches the Lambda runtime in AWS.

### Implementation plan (recovered roadmap)

**Phase 1 — establish clean foundation (NO shared-code module)**
1. Build Retrieval Lambda as the first-of-kind: `handler.py` (thin) + `service.py` (pure logic) + `utils.py` + `tests/`
2. Document the pattern in `lambdas/README.md` using retrieval as the canonical example
3. Refactor Entry Lambda to match the pattern
4. Write tests for Entry Lambda
5. Every future Lambda copies this self-contained structure

**Phase 2 — end-to-end pipeline with mocks, then real providers**
6. Build frontend skeleton (card selection + POST /generate + poll GET /story/{id})
7. Build Story Generation Lambda with adapter pattern (mock + real)
8. Build Image Generation Lambda with adapter pattern (mock + real)
9. Build PDF Assembly Lambda (ReportLab)
10. End-to-end test on deployed AWS
11. Pre-generate the card illustrations
12. Make frontend mobile-responsive

**Phase 3 — polish and submit**
13. Fill test gaps, add integration tests
14. Iterate on prompt templates for character consistency + age-appropriate prose
15. Iterate on PDF format until it looks like a real picture book
16. Finalize `DESIGN_AND_TESTING.md`
17. Record demo video, submit

### Where we left off

- Local dev env: `.venv` active, `requirements-dev.txt` installed, test sanity check passes
- Ready to start **Step 1 of the implementation plan** (Retrieval Lambda)

---

*Add future session entries above this line, newest first.*