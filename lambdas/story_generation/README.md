# story_generation Lambda

Generates a 5-page personalized children's story from card selections.
Invoked by the Step Functions pipeline as the first worker step:

    entry → [story_generation] → image_generation → pdf_assembly

## Contract

### Input event (from Step Functions)

```json
{
  "story_id": "uuid",
  "name": "Emma",
  "hero": "girl",
  "theme": "space",
  "adventure": "secret_map",
  "age": "7"
}
```

All six fields are required. The entry Lambda validates `hero`, `theme`,
`adventure`, and `age` against `lambdas/entry/cards_schema.json` before this
Lambda is invoked, so the values are guaranteed to be in the allowed set.

The event may also pass through other fields (`parent_id`, `kid_id`, `claim_token`)
that the entry Lambda set on the DynamoDB row. This Lambda doesn't read or
modify them — they're already persisted before the pipeline starts.

### Output (passed to image_generation Lambda)

```json
{
  "story_id": "uuid",
  "name": "Emma",
  "hero": "girl",
  "theme": "space",
  "adventure": "secret_map",
  "age": "7",
  "pages": [
    {"page_num": 1, "text": "...", "image_prompt": "..."},
    {"page_num": 2, "text": "...", "image_prompt": "..."},
    {"page_num": 3, "text": "...", "image_prompt": "..."},
    {"page_num": 4, "text": "...", "image_prompt": "..."},
    {"page_num": 5, "text": "...", "image_prompt": "..."}
  ]
}
```

Each page contains:

- `page_num` — 1 through 5
- `text` — story prose the child reads (clothing/visual descriptions stripped)
- `image_prompt` — purely visual description for the illustrator. Carries the
  hero's visual identity and world description verbatim across all 5 pages so
  illustrations stay consistent.

### Side effects

- DynamoDB `my-story-stories` row is updated:
  - `pages` attribute set to the page list above
  - `status` attribute set to `IMAGES_PENDING`

## Architecture

### Pattern: ports-and-adapters

The Lambda follows the canonical handler/service/adapters split:

- `handler.py` — Step Functions wrapper; builds the real Bedrock client + DDB table, injects them into service
- `service.py` — pure logic: build prompt → call adapter → parse JSON → save pages to DDB
- `adapters.py` — `LLMAdapter` ABC + `MockLLMAdapter` (tests) + `AnthropicLLMAdapter` (direct API, kept for reference) + `BedrockLLMAdapter` (production, calls Claude Haiku 4.5 via Bedrock)

Both real adapter implementations live in `adapters.py`. Production uses `BedrockLLMAdapter`; the `AnthropicLLMAdapter` stays as a documented alternative — keeping both is the proof that the hexagonal pattern actually swaps cleanly.

### Model

AWS Bedrock — **Anthropic Claude Haiku 4.5** via the US cross-region inference
profile (`us.anthropic.claude-haiku-4-5-20251001-v1:0`). Selected for:

- Native AWS integration (no external API key, IAM-scoped access)
- Strong creative writing quality at low per-token cost
- ~6–10 second latency for ~1,500 output tokens, well within the 120s
  Lambda timeout

The adapter is called via `bedrock-runtime.invoke_model` with the standard
Anthropic Messages API body. The response `content[0].text` is parsed as JSON
to extract the `pages` array.

### Prompt

Loaded from `prompt_template.txt` at cold-start (module-level read, reused on
warm invocations). The template has five substitution slots: `{name}`, `{age}`,
`{hero}`, `{theme}`, `{adventure}`. Card values are mapped to natural-language
labels via the `CARD_LABELS` dict in `service.py` before substitution
(e.g. `"space"` → `"outer space among the stars"`).

The prompt enforces:

- Age-appropriate vocabulary (3–5 sentences per page, calibrated to age)
- A 5-beat arc (intro → adventure begins → setback → personal-quality moment → resolution)
- Forbidden words list (no "scary", "evil", "monster", etc.)
- Strict separation between `text` (story prose) and `image_prompt` (visual)
- Consistent hero visual identity and world description across all 5 pages
- JSON-only response — no markdown fences, no preamble

The service defensively strips ` ``` ` and ` ```json ` fences from the response
in case the model adds them anyway.

### File layout

```
story_generation/
├── handler.py            # AWS entry point — wires Bedrock client + DDB
├── service.py            # generate_story: prompt build, parse, save
├── adapters.py           # LLMAdapter ABC + Mock + Anthropic + Bedrock
├── prompt_template.txt   # Editable without code change
├── requirements.txt      # boto3 only — Bedrock SDK is in the Lambda runtime
├── README.md
└── tests/
    ├── conftest.py
    ├── test_adapters.py    # Adapter contract + mock + Anthropic + Bedrock
    ├── test_handler.py     # Event passthrough, error mapping
    └── test_service.py     # Prompt build, parse, validation, DDB write
```

## Environment variables

| Variable                | Required | Purpose |
|-------------------------|----------|---------|
| `STORIES_TABLE`         | yes      | DynamoDB table name |
| `BEDROCK_MODEL_ID`      | no       | Defaults to `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Override to switch models without redeploying code. |
| `LOG_LEVEL`             | no       | Defaults to `INFO` |

## IAM permissions (granted in `infra/stacks/pipeline_stack.py`)

- `bedrock:InvokeModel` on:
  - `arn:aws:bedrock:us-east-1:*:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0`
  - `arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0`
- `dynamodb:UpdateItem` on `my-story-stories`
  (granted via `storage.stories_table.grant_write_data(...)`)

The cross-region inference profile is required for Claude Haiku 4.5 — direct
foundation-model invocation isn't supported. Bedrock may route the request
to any US region internally, hence the `*` in the second ARN.

A one-time AWS Marketplace subscription is required for Anthropic models on
Bedrock. This is an account-level action performed once via the AWS Console
(Bedrock → Playground → Claude Haiku 4.5 → accept terms). Not a Lambda
permission.

## Cost

Per invocation (~1,500 in / ~1,500 out):

- Input: 1,500 / 1,000,000 × $0.80 = $0.0012
- Output: 1,500 / 1,000,000 × $4.00 = $0.0060
- **~$0.0072 per story**

Negligible compared to the image generation step (~$0.21 for 5 illustrations).
See `COSTS.md` for the full breakdown.

## Local testing

```bash
# From repo root
pytest lambdas/story_generation/tests/ -v
```

30 tests using `MockLLMAdapter` (returns canned 5-page JSON) and stubbed DDB.
Real Bedrock calls only happen in deployed environments.

## Failure modes

| Failure | Cause | Surfaced as |
|---------|-------|-------------|
| Bedrock returns non-JSON content | Model didn't follow the prompt | `ValueError("LLM response is not valid JSON")` → Step Functions catches → DDB row marked `FAILED` |
| Bedrock returns wrong page count or missing fields | Model partially followed prompt | `ValueError("Expected 5 pages")` etc. → caught → `FAILED` |
| Bedrock throttle / 5xx | Service issue | `botocore.exceptions.ClientError` → caught → `FAILED` |
| DynamoDB write fails | IAM or capacity issue | `ClientError` → caught → `FAILED` |
| Missing event field | Upstream bug in entry Lambda | `KeyError` → caught → `FAILED` |

The shared `MarkFailed` state in the Step Functions definition flips the
DynamoDB record to `FAILED` on any error so the retrieval Lambda surfaces
it to the user instead of polling forever.

**Known LLM brittleness:** Claude returns malformed JSON roughly 1–2% of the
time despite the strict prompt instructions. This was observed in production
during Sprint 4 testing. The retry-on-`ValueError` is documented as future
work — adding a `Step Functions Retry` with `States.ALL` and `MaxAttempts: 3`
would mask most transient parse failures from the user.

## Definition of Done

- [x] Lambda implemented and deployed
- [x] Output matches contract above (`pages` array of `{page_num, text, image_prompt}`)
- [x] Step Functions integration verified end-to-end (story → image → PDF)
- [x] DynamoDB status transitions verified (`PROCESSING` → `IMAGES_PENDING`)
- [x] IAM permissions scoped to specific resources (no `*` on Lambda role)
- [x] Prompt template externalized to `prompt_template.txt`
- [x] README in Lambda folder (this file)
- [x] Refactored to canonical handler/service/adapters pattern
- [x] Adapter swap tested — `MockLLMAdapter` covers tests, `BedrockLLMAdapter` covers production, `AnthropicLLMAdapter` retained as alternative
- [x] ≥10 unit tests passing (30 actually)
- [x] ≥80% line coverage on `service.py`

## References

- `lambdas/README.md` — canonical Lambda architecture pattern
- `lambdas/entry/service.py` — entry Lambda's create_story logic
- `infra/stacks/pipeline_stack.py` — Lambda definition + IAM + Step Functions wiring
- `prompt_template.txt` — the actual prompt sent to Claude
- `COSTS.md` — full cost breakdown