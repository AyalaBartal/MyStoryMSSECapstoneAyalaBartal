# story_generation Lambda

Second stage of the pipeline. Takes card selections, calls an LLM, returns 5 story pages.

## Contract

**Input** (from Step Functions):
```json
{
  "story_id": "uuid-string",
  "hero": "girl",
  "theme": "space",
  "challenge": "asteroid",
  "strength": "super_smart"
}
```

**Output:** input dict plus a `pages` array:
```json
{
  "story_id": "...",
  "hero": "...",
  "pages": [
    {"page_num": 1, "text": "..."},
    ...
    {"page_num": 5, "text": "..."}
  ]
}
```

## Architecture

Hexagonal / ports-and-adapters:

- `handler.py` — AWS event shell; builds the adapter, delegates to service
- `service.py` — pure logic: prompt build → LLM call → parse
- `adapters.py` — `LLMAdapter` ABC + `MockLLMAdapter` (tests) + `AnthropicLLMAdapter` (prod)
- `prompt_template.txt` — edit the prompt without changing Python

## LLM: Anthropic Claude 3.5 Haiku

Chosen for: speed (~2s for 5 pages), cost (~$0.001 per story), and best-in-class creative writing for middle-grade fiction (ages 8-12).

Swap providers by adding a new class to `adapters.py` that implements `LLMAdapter.generate()` and passing it into `handler.py`.

## Env vars (production)

- `ANTHROPIC_API_KEY` — required; injected via CDK from AWS Secrets Manager in production.

## Tests

`pytest lambdas/story_generation/tests/ -v` — all tests use `MockLLMAdapter`, zero API calls.