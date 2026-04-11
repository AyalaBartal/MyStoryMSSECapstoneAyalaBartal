# My Story 📖
> AI-Powered Personalized Children's Story Generator

An AWS serverless application that lets children (ages 5–8) select story cards and receive a unique, personalized storybook — complete with AI-generated illustrations — delivered as a downloadable PDF.

Built as part of the **MSSE Capstone Project** at Quantic School of Business and Technology.

---

## 🌟 What It Does

Children select 4 cards:
- **Hero** — Boy or Girl
- **Adventure Theme** — Space, Under the Sea, Medieval Fantasy, or Dinosaurs
- **Challenge** — Surprise Asteroid, Evil Wizard/Witch, Dragon, or Volcano Eruption
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
- Python 3.11+
- Node.js 18+ (for CDK)
- AWS CLI configured
- AWS CDK: `npm install -g aws-cdk`

### Install CDK dependencies
```bash
cd infra
pip install -r requirements.txt
```

### Install Lambda dependencies
```bash
# Each Lambda has its own dependencies
cd lambdas/entry && pip install -r requirements.txt
cd lambdas/story_generation && pip install -r requirements.txt
cd lambdas/image_generation && pip install -r requirements.txt
cd lambdas/pdf_assembly && pip install -r requirements.txt
cd lambdas/retrieval && pip install -r requirements.txt
```

### Deploy to AWS
```bash
cd infra
cdk bootstrap   # first time only
cdk deploy --all
```

### Run tests
```bash
# From repo root
pytest lambdas/
```

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