# My Story 📖
> AI-Powered Personalized Children's Story Generator

An AWS serverless application that lets parents and children create unique, personalized 5-page picture books — complete with AI-generated watercolor illustrations and a custom cover — delivered as downloadable square 8×8 inch PDFs.

Anonymous users can generate a story without an account. Signed-in parents can save kid profiles for one-tap reuse and revisit their family's library of past stories.

Built as part of the **MSSE Capstone Project** at Quantic School of Business and Technology.

---

## 🌟 What It Does

Children (ages 4–12) enter their name, pick their age, and select 3 story cards:

- **Hero** — Boy or Girl
- **Adventure Theme** — Space, Under the Sea, Medieval Fantasy, or Dinosaurs
- **Adventure** — Secret Map, Talking Animal, Time Machine, or Magic Key

The app generates a unique **5-page personalized picture book** with:
- A custom cover page using the chosen theme illustration as a full-bleed background
- 5 story pages with full-bleed AI-generated watercolor illustrations
- Story text overlaid in a soft cream band, in age-appropriate prose
- Consistent character + setting across all pages (verbatim-repeated description in each page's image prompt)

**288 possible unique story-shape combinations** (2 heroes × 4 themes × 4 adventures × 9 ages), plus open-ended creative variation through the child's name and the LLM's generation.

### User accounts (Sprint 4)

Signed-in parents can:
- **Manage kid profiles** — name, birth year, hero (boy/girl) per child. One-tap reuse so they don't re-enter the same info every time.
- **View their family library** — all stories they've made, filterable by kid.
- **Re-download past stories** without regenerating them.

Authentication is **optional** — anonymous users can still generate stories. Sign-up is encouraged but never required (hybrid auth).

---

## 🏗️ Architecture

Fully serverless on AWS, built and deployed with AWS CDK (Python).

```
Frontend (React + Vite, S3 Static)
        ↓
   Cognito ──── Sign in ────┐
                            ↓
   API Gateway   ←── JWT (when signed in)
        ↓
  Entry Lambda  → schema-driven validation
                → DynamoDB (status: PROCESSING, parent_id OR claim_token)
        ↓
Step Functions Pipeline
   ├── Story Generation Lambda → AWS Bedrock (Claude Haiku 4.5)
   │     (one structured JSON response with text + image_prompt per page)
   ├── Image Generation Lambda → OpenAI gpt-image-1
   │     (5 illustrations × 1024×1024 watercolor)
   └── PDF Assembly Lambda → ReportLab
         (square 8×8 picture book + cover page)
        ↓
  Save to S3 + DynamoDB (status: COMPLETE)
        ↓
  Retrieval Lambda → Pre-signed S3 URL (single story OR my-library list)
  Kids Lambda      → Manage kid profiles (POST/GET/DELETE /kids)
  ClaimStories Lambda → Anonymous → owned conversion (deferred frontend wiring)
```

### AWS Services
| Service | Purpose |
|---------|---------|
| S3 (×4 buckets) | Frontend hosting, PDF storage, illustration storage, card images |
| API Gateway | REST API endpoints (`POST /generate`, `GET /story/{id}`, `GET /my-stories`, `POST/GET/DELETE /kids`, `POST /claim-stories`) |
| Lambda (×7) | Independent business logic functions (entry, story, image, pdf, retrieval, kids, claim_stories) |
| Step Functions | Pipeline orchestration with centralized failure handling |
| DynamoDB | Stories table with `parent_id` + `kid_id` GSIs; kids table for parent profiles |
| Cognito | User Pool + App Client for parent authentication (Sprint 4) |
| Bedrock | Foundation model invocation (Claude Haiku 4.5) for story text |
| Secrets Manager | OpenAI API key (Bedrock and Cognito use IAM, no key needed) |
| CloudWatch | Logging, metrics, error visibility |
| CDK | Infrastructure as Code (Python) |

### AI Providers
| Service | Purpose |
|---------|---------|
| AWS Bedrock — Claude Haiku 4.5 | Story text generation + sanitized image prompts |
| OpenAI gpt-image-1 (gpt-4o image generation) | Page illustrations in watercolor style |

V1 uses foundation models via API. The hexagonal/ports-and-adapters architecture is designed to allow Phase 2 swap to custom-trained LoRAs (proprietary visual style + brand voice) without rewriting any business logic — see `DESIGN_AND_TESTING.md` for the V2 roadmap.

---

## 📁 Repository Structure
```
MyStoryMSSECapstoneAyalaBartal/
├── infra/                          # AWS CDK app (Python)
│   ├── app.py                      # CDK entry point
│   └── stacks/
│       ├── storage_stack.py        # S3 buckets + DynamoDB stories + GSIs + kids table
│       ├── auth_stack.py           # Cognito User Pool + App Client + hosted UI
│       ├── api_stack.py            # API Gateway + 4 API-facing Lambdas + Cognito wiring
│       ├── pipeline_stack.py       # 3 Step Functions worker Lambdas + Secrets + Bedrock IAM
│       └── cicd_stack.py           # (placeholder; CI/CD lives in .github/workflows)
│
├── lambdas/
│   ├── entry/                      # POST /generate (anonymous + authed)
│   ├── story_generation/           # AWS Bedrock (Claude Haiku 4.5)
│   ├── image_generation/           # OpenAI gpt-image-1 adapter
│   ├── pdf_assembly/               # ReportLab picture-book composition
│   ├── retrieval/                  # GET /story/{id} (public) + GET /my-stories (authed)
│   ├── kids/                       # POST/GET/DELETE /kids (Sprint 4, authed)
│   └── claim_stories/              # POST /claim-stories (Sprint 4, authed)
│   (each contains: handler.py, service.py, auth.py, utils.py, requirements.txt, tests/)
│
├── frontend/                       # React + Vite SPA
│   ├── README.md                   # Frontend-specific dev instructions
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx                # Router + Amplify config
│       ├── App.jsx                 # Routes + story flow + auth modal
│       ├── App.css                 # Component styles
│       ├── Layout.jsx              # Auth header (avatar, nav, sign out)
│       ├── FamilyPage.jsx          # /family — kid profile manager
│       ├── LibraryPage.jsx         # /library — story library with kid filter
│       ├── api.js                  # fetch wrapper with auto-JWT attachment
│       ├── useAuth.js              # Cognito auth state hook
│       ├── useKids.js              # Loads parent's kid profiles
│       ├── useStories.js           # Loads parent's stories
│       ├── amplifyConfig.js        # Amplify.configure() at boot
│       ├── cardsConfig.js          # Card definitions
│       └── assets/cards/           # Card illustration assets
│
├── scripts/
│   ├── package_lambdas.sh          # Build Lambda zips for cdk deploy
│   ├── generate_card_images.py     # One-off card image generator
│   └── smoke_test_*.py             # End-to-end Lambda smoke tests
│
├── .github/workflows/
│   └── deploy.yml                  # CI/CD pipeline
│
├── DESIGN_AND_TESTING.md           # Full architecture + testing strategy
├── PROJECT_PLAN.md                 # Sprint plan + task board
├── COSTS.md                        # Cost tracking
└── README.md                       # This file
```
---

## 🚀 Live Demo

🔗 **Deployed application:** http://my-story-frontend-691304835962.s3-website-us-east-1.amazonaws.com

> Note: V1 deployment uses HTTP via S3 static website hosting. HTTPS via CloudFront is documented as Phase 2 work.

---

## 📋 Task Board

🔗 **Trello Scrum Board:** https://trello.com/b/nrrHEuFv/my-story-msse-capstone

---

## 📄 Design & Testing Document

🔗 [`DESIGN_AND_TESTING.md`](./DESIGN_AND_TESTING.md) — full architecture decisions, design patterns, testing strategy, deployment cost analysis, risks, and Phase 2 continuation roadmap.

---

## 🤖 AI Stack

### V1 (current — foundation models with prompt engineering)

- **Story text:** Anthropic Claude Haiku 4.5 via AWS Bedrock
  - Two-stage structured JSON output: text + sanitized image_prompt per page in a single response
  - Age-aware vocabulary calibration (4-12 year-olds)
  - Verbatim-repeated character + world descriptions across all 5 pages for visual consistency
- **Illustrations:** OpenAI `gpt-image-1` (gpt-4o image generation)
  - 1024×1024 medium quality
  - Watercolor children's-book aesthetic
  - Replaces DALL-E 3 from earlier in the project — gpt-image-1 has materially better character consistency and spatial composition adherence
- **PDF assembly:** ReportLab
  - Square 8×8 inch (576×576pt) picture-book pages
  - Custom cover page with theme card image background + italic Times typography
  - Full-bleed illustrations + semi-transparent cream text overlay band
  - Age-tiered font sizing
  - `KeepInFrame` overflow protection so text never silently disappears

### V2 (Phase 2 roadmap — see `DESIGN_AND_TESTING.md`)

- **Style LoRA** trained on commissioned designer portfolio (proprietary visual brand)
- **Voice fine-tune** of GPT-4o-mini on a custom story corpus (proprietary editorial voice)
- **Per-child Character LoRA** pipeline (kid uploads photos → trained LoRA in 15 min → kid is the visual hero)
- Inference hosted on Modal Labs serverless GPU (replaces foundation API calls)
- Hexagonal architecture means each swap is a single-class change — no business logic, no orchestration, no Lambda config changes

---

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.11+ (Lambdas run on Python 3.11 in AWS — match the runtime locally)
- Node.js 20+ (for Vite frontend dev + CDK)
- AWS CLI configured (only needed for deploying from your laptop)
- Homebrew (macOS): `brew install python@3.11 node` gets you the first two

### 1. Clone and create a virtualenv

All local work happens inside a project-local virtualenv. Do **not** install project dependencies into your global/system Python — that causes version conflicts across projects.

```bash
git clone https://github.com/AyalaBartal/MyStoryMSSECapstoneAyalaBartal.git
cd MyStoryMSSECapstoneAyalaBartal

# Create the virtualenv (one-time)
python3.11 -m venv .venv

# Activate it (every new terminal session)
source .venv/bin/activate

# Verify — prompt should now show (.venv)
python --version        # -> 3.11.x
which pip               # -> .../.venv/bin/pip
```

The `.venv/` directory is gitignored and will not be committed.

### 2. Install dev dependencies

```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Sanity check:
```bash
python -c "import pytest, moto, boto3; print('OK')"
```

### 3. Run tests

```bash
# From the repo root, with .venv active
pytest
```

You should see **239+ tests** pass in under 6 seconds.

### 4. Run the frontend locally

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on http://localhost:5173. You'll need a `frontend/.env.local` with:
```
VITE_API_BASE_URL=https://d2633mrual.execute-api.us-east-1.amazonaws.com/prod
VITE_USER_POOL_ID=us-east-1_HroqilVxq
VITE_USER_POOL_CLIENT_ID=157h8g823igbckk765rlf4k60p
VITE_USER_POOL_REGION=us-east-1
```
These are public, build-time-injected values. The Cognito IDs are designed to live in browser code.

### 5. Deploy from your laptop (optional)

The GitHub Actions workflow deploys automatically on push to `main`, so this is only needed if you want to deploy manually.

```bash
# One-time CDK setup
npm install -g aws-cdk
pip install -r infra/requirements.txt

# Build Lambda zips (CRITICAL — must run before every cdk deploy)
./scripts/package_lambdas.sh

# Deploy (one-time bootstrap, then deploy)
cd infra
cdk bootstrap                            # one-time per AWS account + region
cdk deploy --all
```

**Important:** Always run `./scripts/package_lambdas.sh` before `cdk deploy --all`. CDK reads pre-built zips from `infra/lambda_packages/` — if you skip the package step, CDK redeploys the previous build of your Lambda code.

### 6. Per-Lambda `requirements.txt` files

Each Lambda keeps its **own** `requirements.txt`. This is a deliberate architectural choice that preserves the ability to split any Lambda into its own standalone service in the future without rewriting dependency management.
```
lambdas/entry/requirements.txt              → boto3 + python-jose (for JWT)
lambdas/story_generation/requirements.txt   → boto3 only (Bedrock via boto3)
lambdas/image_generation/requirements.txt   → openai + boto3
lambdas/pdf_assembly/requirements.txt       → reportlab + pillow + boto3
lambdas/retrieval/requirements.txt          → boto3 + python-jose (for JWT)
lambdas/kids/requirements.txt               → boto3 + python-jose (for JWT)
lambdas/claim_stories/requirements.txt      → boto3 + python-jose (for JWT)
```
The packaging script (`scripts/package_lambdas.sh`) reads each file independently and bundles only that Lambda's declared dependencies into its zip. Keeps each Lambda's deployment artifact small and its dependency surface narrow.

---

## 🧪 Testing

Each Lambda has its own test suite in its `tests/` folder. All tests use mock adapters and stubbed S3/DDB callables — **no test ever hits real AWS or external APIs**.

```bash
pytest lambdas/entry/tests/             # Schema validation, JWT, claim_token minting
pytest lambdas/story_generation/tests/  # Bedrock adapter, mock, service
pytest lambdas/image_generation/tests/  # OpenAI adapter, mock, service
pytest lambdas/pdf_assembly/tests/      # ReportLab composition, layout, handler
pytest lambdas/retrieval/tests/         # /story/{id} + /my-stories with GSI queries
pytest lambdas/kids/tests/              # Kid profile CRUD + auth
pytest lambdas/claim_stories/tests/     # Conditional claim updates + ownership boundaries
```

Or run everything:
```bash
pytest
```

CI runs automatically on every push to `main` and all pull requests via GitHub Actions.

See `DESIGN_AND_TESTING.md` for the full testing strategy.

---

## 📅 Sprint Timeline

| Sprint | Duration | Focus |
|--------|----------|-------|
| Sprint 1 | Weeks 1–3 | Planning, architecture, CDK bootstrap, schema design, Entry Lambda |
| Sprint 2 | Weeks 4–6 | Story + Image + PDF Lambdas with foundation models, hexagonal pattern |
| Sprint 3 | Weeks 7–10 | Frontend, picture-book PDF format, gpt-image-1 swap, polish, demo prep |
| Sprint 4 | Weeks 10–11 | User accounts (Cognito), kid profiles, my-library page, hybrid auth flow |

---

## 👩‍💻 Author

**Ayala Bartal** — MSSE Candidate, Quantic School of Business and Technology

---

## 📜 License

This project is submitted as academic coursework for the Quantic MSSE Capstone Program.