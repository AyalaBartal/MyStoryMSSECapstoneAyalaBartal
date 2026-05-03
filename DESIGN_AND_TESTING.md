MyStoryMSSECapstoneAyalaBartal/
├── README.md                          # Project intro + quickstart
├── DESIGN_AND_TESTING.md              # This document
├── PROJECT_PLAN.md                    # Sprint plan + task board
├── COSTS.md                           # Cost tracking notes
├── pyproject.toml                     # Pytest config (--import-mode=importlib)
├── requirements.txt                   # Top-level Python deps
├── requirements-dev.txt               # Dev/test deps
├── conftest.py                        # Per-Lambda sys.path/sys.modules isolation
│
├── infra/                             # AWS CDK (Python)
│   ├── app.py                         # Stack composition + region/account binding
│   ├── cdk.json                       # CDK config
│   ├── requirements.txt               # CDK deps
│   ├── lambda_packages/               # Built zips (gitignored, output of package_lambdas.sh)
│   └── stacks/
│       ├── storage_stack.py           # S3 buckets + DynamoDB stories table + GSIs + kids table
│       ├── auth_stack.py              # Cognito User Pool + App Client + hosted UI domain
│       ├── api_stack.py               # API Gateway + Entry/Retrieval/Kids/ClaimStories Lambdas + Cognito wiring
│       ├── pipeline_stack.py          # Story/Image/PDF Lambdas + Step Fns + Secrets Manager + Bedrock IAM
│       └── cicd_stack.py              # (placeholder; CI/CD lives in .github/workflows)
│
├── lambdas/
│   ├── README.md                      # Hexagonal Lambda pattern doc
│   ├── entry/                         # POST /generate
│   │   ├── handler.py                 # AWS entry point; reads JWT, mints claim_token if anonymous
│   │   ├── service.py                 # Schema-driven validation; saves parent_id or claim_token
│   │   ├── auth.py                    # Cognito JWT verification
│   │   ├── utils.py
│   │   ├── cards_schema.json          # Whitelist for hero/theme/adventure/age
│   │   ├── requirements.txt
│   │   └── tests/                     # 36 tests (handler + service + auth)
│   │
│   ├── story_generation/              # Step Fns worker — Bedrock Claude Haiku 4.5
│   │   ├── handler.py
│   │   ├── service.py
│   │   ├── adapters.py                # LLMAdapter ABC + AnthropicLLMAdapter + BedrockLLMAdapter + Mock
│   │   ├── prompt_template.txt        # Loaded at cold start; editable without code change
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── tests/                     # 30 tests (adapter + service + handler)
│   │
│   ├── image_generation/              # Step Fns worker — OpenAI gpt-image-1
│   │   ├── handler.py
│   │   ├── service.py
│   │   ├── adapters.py                # ImageAdapter ABC + OpenAIImageAdapter + Mock
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── tests/                     # 27 tests
│   │
│   ├── pdf_assembly/                  # Step Fns worker — ReportLab
│   │   ├── handler.py
│   │   ├── service.py                 # Square 8×8" picture-book composition
│   │   ├── layout.json                # Page size, age-tier typography, text-band, cover
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── tests/                     # 24 tests
│   │
│   ├── retrieval/                     # GET /story/{id} (public) + GET /my-stories (authed)
│   │   ├── handler.py                 # Routes by path; auth-gates /my-stories
│   │   ├── service.py                 # get_story + list_stories_for_parent (uses GSIs)
│   │   ├── auth.py                    # Cognito JWT verification
│   │   ├── utils.py                   # Includes Decimal-safe JSON encoder
│   │   ├── requirements.txt
│   │   └── tests/                     # 40 tests
│   │
│   ├── kids/                          # POST/GET/DELETE /kids — kid profile manager (Sprint 4)
│   │   ├── handler.py                 # Routes by HTTP method; all routes auth-required
│   │   ├── service.py                 # create_kid / list_kids / delete_kid with hero validation
│   │   ├── auth.py
│   │   ├── utils.py
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── tests/                     # 31 tests
│   │
│   └── claim_stories/                 # POST /claim-stories — anonymous → owned (Sprint 4)
│       ├── handler.py                 # Auth-required
│       ├── service.py                 # Conditional update: SET parent_id IF claim_token matches
│       ├── auth.py
│       ├── utils.py
│       ├── README.md
│       ├── requirements.txt
│       └── tests/                     # 27 tests
│
├── frontend/                          # React + Vite SPA
│   ├── README.md                      # Frontend-specific dev/build instructions
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── .env.local                     # Vite env vars (gitignored): API URL + Cognito IDs
│   └── src/
│       ├── main.jsx                   # App entry; wires Router + Amplify config
│       ├── App.jsx                    # Route definitions, story flow, auth modal
│       ├── App.css                    # All component styles (storybook palette + auth header + family/library)
│       ├── index.css                  # Body reset
│       ├── amplifyConfig.js           # Amplify.configure() with Cognito User Pool refs
│       │
│       ├── Layout.jsx                 # Auth header (avatar, email, nav links, sign out)
│       ├── FamilyPage.jsx             # /family — kid profile manager
│       ├── LibraryPage.jsx            # /library — generated story library with kid filter
│       │
│       ├── api.js                     # fetch wrapper with auto-JWT attachment
│       ├── useAuth.js                 # Cognito auth state hook
│       ├── useKids.js                 # Loads parent's kid profiles
│       ├── useStories.js              # Loads parent's stories (with optional kid_id filter)
│       │
│       ├── cardsConfig.js             # Static card data (heroes, themes, adventures)
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
    └── deploy.yml                     # CI/CD — test → cdk deploy --all → frontend S3 sync