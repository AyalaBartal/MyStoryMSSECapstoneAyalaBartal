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
│       ├── pipeline_stack.py          # Story/Image/PDF Lambdas + Step Fns + Secrets Manager + Bedrock IAM
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
│   │   ├── handler.py                 # Calls AWS Bedrock (Claude Haiku 4.5)
│   │   ├── prompt_template.txt        # Two-stage structured prompt, loaded at cold start
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── tests/                     # TODO — pending adapter refactor
│   ├── image_generation/
│   │   ├── handler.py
│   │   ├── service.py
│   │   ├── adapters.py                # ImageAdapter interface + OpenAI + Mock impls
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