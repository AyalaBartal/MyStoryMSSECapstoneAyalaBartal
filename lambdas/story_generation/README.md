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

### Model

AWS Bedrock — **Anthropic Claude Haiku 4.5** via the US cross-region inference
profile (`us.anthropic.claude-haiku-4-5-20251001-v1:0`). Selected for:

- Native AWS integration (no external API key, IAM-scoped access)
- Strong creative writing quality at low per-token cost
- ~6–10 second latency for ~1,500 output tokens, well within the 120s
  Lambda timeout

The model is called via `boto3.client("bedrock-runtime").invoke_model` with
the standard Anthropic Messages API body. The response `content[0].text` is
parsed as JSON to extract the `pages` array.

### Prompt

Loaded from `prompt_template.txt` at cold-start (module-level read, reused on
warm invocations). The template has six substitution slots: `{name}`, `{age}`,
`{hero}`, `{theme}`, `{adventure}`. Card values are mapped to natural-language
labels via the `CARD_LABELS` dict in `handler.py` before substitution
(e.g. `"space"` → `"outer space among the stars"`).

The prompt enforces:

- Age-appropriate vocabulary (3–5 sentences per page, calibrated to age)
- A 5-beat arc (intro → adventure begins → setback → personal-quality moment → resolution)
- Forbidden words list (no "scary", "evil", "monster", etc.)
- Strict separation between `text` (story prose) and `image_prompt` (visual)
- Consistent hero visual identity and world description across all 5 pages
- JSON-only response — no markdown fences, no preamble

The handler defensively strips ` ``` ` and ` ```json ` fences from the response
in case the model adds them anyway.

### Files

| File | Purpose |
|------|---------|
| `handler.py` | Lambda entry point; Bedrock call, response parsing, DynamoDB write |
| `prompt_template.txt` | Prompt loaded at cold-start; editable without code change |
| `requirements.txt` | Runtime deps (boto3 from Lambda runtime; nothing extra needed) |
| `tests/` | Unit tests (TODO — see Definition of Done below) |
| `README.md` | This file |

> **Note on canonical pattern.** The entry and retrieval Lambdas use a
> handler / service / utils split. This Lambda is currently flat — all logic
> lives in `handler.py`. Refactor to the canonical 3-file pattern is tracked
> as a follow-up; behaviour stays the same.

## Environment variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `STORIES_TABLE` | CDK pipeline_stack | DynamoDB table name |

## IAM permissions (granted in `infra/stacks/pipeline_stack.py`)

- `bedrock:InvokeModel` on:
  - `arn:aws:bedrock:us-east-1:*:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0`
  - `arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0`
- `dynamodb:PutItem`, `UpdateItem`, etc. on `my-story-stories`
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

Negligible compared to the image generation step (~$0.24 for 6 illustrations).

## Local testing

```bash
# From repo root
pytest lambdas/story_generation/tests/ -v
```

The Bedrock client and DynamoDB table are mocked with `moto` and `monkeypatch`
following the entry/retrieval Lambda pattern. Real Bedrock calls only happen
in deployed environments.

## Failure modes

| Failure | Cause | Surfaced as |
|---------|-------|-------------|
| Bedrock returns non-JSON content | Model didn't follow the prompt | `json.JSONDecodeError` → Step Functions catches → DDB row marked `FAILED` |
| Bedrock throttle / 5xx | Service issue | `botocore.exceptions.ClientError` → caught → `FAILED` |
| DynamoDB write fails | IAM or capacity issue | `ClientError` → caught → `FAILED` |
| Missing event field | Upstream bug in entry Lambda | `KeyError` → caught → `FAILED` |

The shared `MarkFailed` state in the Step Functions definition flips the
DynamoDB record to `FAILED` on any error so the retrieval Lambda surfaces
it to the user instead of polling forever.

## Definition of Done

Per `lambdas/README.md` (canonical pattern doc):

- [x] Lambda implemented and deployed
- [x] Output matches contract above (`pages` array of `{page_num, text, image_prompt}`)
- [x] Step Functions integration verified end-to-end (story → image → PDF)
- [x] DynamoDB status transitions verified (`PROCESSING` → `IMAGES_PENDING`)
- [x] IAM permissions scoped to specific resources (no `*`)
- [x] Prompt template externalized to `prompt_template.txt`
- [x] README in Lambda folder (this file)
- [ ] ≥10 unit tests passing (`pytest` from repo root)
- [ ] ≥80% line coverage on `handler.py`
- [ ] Adapter swap tested (mock Bedrock client substitutable)
- [ ] Refactor to canonical handler/service/utils pattern

## References

- `lambdas/README.md` — canonical Lambda architecture pattern
- `lambdas/entry/handler.py` — entry Lambda contract
- `infra/stacks/pipeline_stack.py` — Lambda definition + IAM + Step Functions wiring
- `prompt_template.txt` — the actual prompt sent to Claude