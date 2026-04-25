# My Story 📖
> AI-Powered Personalized Children's Story Generator

An AWS serverless application that lets children (ages 5–8) select story cards and receive a unique, personalized storybook — complete with AI-generated illustrations — delivered as a downloadable PDF.

Built as part of the **MSSE Capstone Project** at Quantic School of Business and Technology.

---

## 🌟 What It Does

Children select 4 cards:
- **Hero** — Boy or Girl
- **Adventure Theme** — Space, Under the Sea, Medieval Fantasy, or Dinosaurs
- **adventure** — Surprise Asteroid, Evil Wizard/Witch, Dragon, or Volcano Eruption
- **Secret Strength** — Super Strong, Friendship, Super Smart, or Super Speed

The app generates a unique **7-page personalized storybook** following a proven 5-beat narrative structure, illustrated with AI-generated artwork, and delivered as a downloadable PDF.

**128 possible unique story combinations.**

---

## 🏗️ Architecture

Fully serverless on AWS, built and deployed with AWS CDK (Python).

```
Frontend (S3 Static)
        ↓
   API Gateway
        ↓
  Entry Lambda
        ↓
Step Functions Pipeline
   ├── Story Generation Lambda → HuggingFace Inference Endpoint (Fine-tuned LLaMA 3 8B)
   ├── Image Generation Lambda → Replicate API (Fine-tuned Stable Diffusion)
   └── PDF Assembly Lambda → ReportLab
        ↓
  Save to S3 + DynamoDB
        ↓
  Retrieval Lambda
        ↓
  PDF Download
```

### AWS Services
| Service | Purpose |
|---------|---------|
| S3 | Frontend hosting, PDF storage, illustration storage |
| API Gateway | REST API endpoints |
| Lambda (x5) | Business logic — independent functions |
| Step Functions | Pipeline orchestration |
| DynamoDB | Story metadata |
| CloudWatch | Logging and cost alerts |
| CDK | Infrastructure as Code |

### ML Model Hosting
| Model | Hosting | Purpose |
|-------|---------|---------|
| Fine-tuned LLaMA 3 8B | HuggingFace Inference Endpoints | Story text generation |
| Fine-tuned Stable Diffusion 1.5 | Replicate | Story illustrations |

---

## 📁 Repository Structure

```
my-story/
├── infra/                          # AWS CDK app (Python)
│   ├── app.py                      # CDK entry point
│   ├── stacks/
│   │   ├── storage_stack.py        # S3 + DynamoDB
│   │   ├── api_stack.py            # API Gateway
│   │   ├── pipeline_stack.py       # Step Functions + Lambdas
│   │   └── cicd_stack.py           # CI/CD
│   └── requirements.txt
│
├── lambdas/
│   ├── entry/                      # Receives card selections, starts pipeline
│   │   ├── handler.py
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── story_generation/           # Calls HuggingFace LLM endpoint
│   │   ├── handler.py
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── image_generation/           # Calls Replicate image API
│   │   ├── handler.py
│   │   ├── requirements.txt
│   │   └── tests/
│   ├── pdf_assembly/               # Builds PDF with ReportLab
│   │   ├── handler.py
│   │   ├── requirements.txt
│   │   └── tests/
│   └── retrieval/                  # Returns pre-signed S3 URL
│       ├── handler.py
│       ├── requirements.txt
│       └── tests/
│
├── frontend/                       # Static card selection UI
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── ml/                             # Model training (local only, not deployed)
│   ├── llm/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── requirements.txt
│   └── image_model/
│       ├── train.py
│       ├── evaluate.py
│       └── requirements.txt
│
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD pipeline
│
└── README.md
```

---

## 🚀 Live Demo

> 🔗 [Deployed Application](#) *(link added after Sprint 3 deployment)*

---

## 📋 Task Board

> 🔗 [Trello Scrum Board](https://trello.com/b/nrrHEuFv/my-story-msse-capstone) 

---

## 📄 Design & Architecture Document

> 🔗 [Design Document](#) *(link added after document is finalized)*

---

## 🤖 ML Models

### Story Generation
- **Base model:** LLaMA 3 8B (Meta)
- **Fine-tuning:** LoRA via HuggingFace PEFT
- **Training data:** Brothers Grimm + Children's Book Test dataset
- **Training environment:** Apple M5 MacBook Air (Apple MLX framework)
- **Production:** HuggingFace Inference Endpoint

### Illustration Generation
- **Base model:** Stable Diffusion 1.5
- **Fine-tuning:** LoRA / DreamBooth
- **Training data:** Curated children's book illustration dataset
- **Training environment:** Apple M5 MacBook Air (PyTorch MPS backend)
- **Production:** Replicate

---

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.11+ (Lambdas run on Python 3.11 in AWS — match the runtime locally)
- Node.js 18+ (only needed if you want to run `cdk deploy` from your laptop)
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

`requirements-dev.txt` contains only what you need to write and test code locally (pytest, moto, boto3, responses). It does **not** install the Lambda deployment dependencies — those get bundled into each Lambda zip at deploy time by GitHub Actions, not installed on your laptop.

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
pytest lambdas/ -v
```

### 4. (Optional) Install CDK tooling for deployment from your laptop

The GitHub Actions workflow deploys automatically on push to `main`, so this is only needed if you want to deploy manually.

```bash
npm install -g aws-cdk                   # CDK CLI (one-time, global)
pip install -r infra/requirements.txt    # CDK Python libraries (into .venv)
cd infra
cdk bootstrap                            # one-time per AWS account + region
cdk deploy --all
```

### 5. About the per-Lambda `requirements.txt` files

Each Lambda keeps its **own** `requirements.txt` on purpose. This is a deliberate architectural choice that preserves the ability to split any Lambda into its own standalone service (own repo, own deploy pipeline, own runtime) in the future without rewriting dependency management.

```
lambdas/entry/requirements.txt            → only what entry/handler.py imports
lambdas/story_generation/requirements.txt → only what story_generation imports
lambdas/image_generation/requirements.txt → only what image_generation imports
lambdas/pdf_assembly/requirements.txt     → only what pdf_assembly imports (reportlab, pillow)
lambdas/retrieval/requirements.txt        → only what retrieval/handler.py imports
```

The GitHub Actions workflow (`.github/workflows/deploy.yml`) reads each file independently and bundles *only* that Lambda's declared dependencies into its zip. This keeps each Lambda's deployment artifact small and its dependency surface narrow.

**When to touch these files:**
- Add a package only to the specific Lambda that imports it
- Never put dev/test tooling (pytest, moto) in a Lambda's requirements — those live in `requirements-dev.txt`

**Running tests that exercise a specific Lambda's runtime deps:**
Our unit tests mock external I/O (HTTP, AWS) via `moto` and `responses`, so you generally don't need to install a Lambda's own `requirements.txt` on your laptop. If you ever do need to (e.g. running a Lambda handler interactively with `reportlab`), install it *ad hoc* inside your `.venv`:

```bash
# Example — temporary, for interactive debugging of pdf_assembly
pip install -r lambdas/pdf_assembly/requirements.txt
```

That's fine inside the venv, because the venv is isolated from your system Python.

---

## 🧪 Testing

Each Lambda has its own test suite in its `tests/` folder.

```bash
pytest lambdas/entry/tests/
pytest lambdas/story_generation/tests/
pytest lambdas/image_generation/tests/
pytest lambdas/pdf_assembly/tests/
pytest lambdas/retrieval/tests/
```

CI runs automatically on every push to `main` and all pull requests via GitHub Actions.

---

## 📅 Sprint Timeline

| Sprint | Duration | Focus |
|--------|----------|-------|
| Sprint 1 | Weeks 1–2 | Planning, setup, architecture, CDK bootstrap |
| Sprint 2 | Weeks 3–5 | Core app + LLM fine-tuning |
| Sprint 3 | Weeks 6–8 | Image model + PDF + deployment |

---

## 👩‍💻 Author

**Ayala** — MSSE Candidate, Quantic School of Business and Technology

---

## 📜 License

This project is submitted as academic coursework for the Quantic MSSE Capstone Program.