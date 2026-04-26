# story_generation Lambda

Second stage of the pipeline. Takes card selections + name + age, calls Claude Haiku, returns 5 story pages — each with both story text AND a sanitized image prompt for the next stage.

## Contract

**Input** (from Step Functions, originally from the Entry Lambda event):
```json
{
  "story_id": "uuid-string",
  "name":     "Ayala",
  "age":      "9",
  "hero":     "girl",
  "theme":    "space",
  "adventure": "secret_map"
}
```

**Output:** input dict plus a `pages` array, where each page has both `text` and `image_prompt`:
```json
{
  "story_id": "...",
  "name": "...",
  "age": "...",
  "hero": "...",
  "theme": "...",
  "adventure": "...",
  "pages": [
    {
      "page_num": 1,
      "text": "Story prose for the child to read...",
      "image_prompt": "Visual description for the image generator..."
    },
    ...
    {
      "page_num": 5,
      "text": "...",
      "image_prompt": "..."
    }
  ]
}
```

## Architecture

Hexagonal / ports-and-adapters:

- `handler.py` — AWS event shell; builds the adapter, delegates to service
- `service.py` — pure logic: prompt build → LLM call → JSON parse
- `adapters.py` — `LLMAdapter` ABC + `MockLLMAdapter` (tests) + `AnthropicLLMAdapter` (prod)
- `prompt_template.txt` — edit the prompt without changing Python

## Two-stage prompt design

The prompt instructs Claude to produce both `text` (story prose) and `image_prompt` (visual description) for all 5 pages in a single structured JSON response. Constraints in the prompt:

- Each page's `image_prompt` includes a verbatim-repeated character description (15-25 words, locked in on page 1) so all 5 pages depict the same character
- Each page's `image_prompt` includes a verbatim-repeated world description (10-15 words) so all 5 pages share the same setting and palette
- `text` field MUST NEVER describe clothing — clothing belongs only in `image_prompt`
- A standardized style suffix appended to every `image_prompt` enforces the watercolor children's-book aesthetic
- Forbidden-word list (scary, attack, monster, etc.) keeps content age-appropriate

This design produces materially more consistent illustrations across a book vs. independent per-page prompts.

## LLM: Anthropic Claude Haiku

Chosen for: speed (~10-30s for 5 pages), cost (~$0.001-0.002 per story), and best-in-class long-form prose for children's storytelling. Strong instruction-following for structured JSON output.

Swap providers by adding a new class to `adapters.py` that implements `LLMAdapter.generate()` and passing it into `handler.py`.

## Env vars (production)

- `ANTHROPIC_SECRET_ARN` — required; ARN of the Secrets Manager secret holding the Anthropic API key. The actual key is fetched at cold start and never appears in env vars or logs.
- `LOG_LEVEL` — optional. Defaults to `INFO`.

## Tests

`pytest lambdas/story_generation/tests/ -v` — all tests use `MockLLMAdapter` (returns deterministic canned 5-page JSON), zero API calls.
