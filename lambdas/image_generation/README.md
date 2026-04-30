# image_generation Lambda

Third stage of the pipeline. Takes the 5 story pages (each with an `image_prompt`), generates an illustration per page via OpenAI `gpt-image-1`, uploads them to S3, returns the S3 keys.

## Contract

**Input** (from story_generation):
```json
{
  "story_id": "uuid-string",
  "name":     "Ayala",
  "age":      "9",
  "hero":     "girl",
  "theme":    "space",
  "adventure": "secret_map",
  "pages": [
    {
      "page_num": 1,
      "text": "...",
      "image_prompt": "Visual description for the image generator..."
    },
    ...
    {"page_num": 5, "text": "...", "image_prompt": "..."}
  ]
}
```

**Output:** input dict plus an `image_s3_keys` array:
```json
{
  ...,
  "image_s3_keys": [
    "stories/uuid-string/page_1.png",
    "stories/uuid-string/page_2.png",
    "stories/uuid-string/page_3.png",
    "stories/uuid-string/page_4.png",
    "stories/uuid-string/page_5.png"
  ]
}
```

## Architecture

Hexagonal / ports-and-adapters:

- `handler.py` — Step Functions wrapper; builds real S3 client + OpenAI client + image adapter
- `service.py` — pure logic: for each page, take its `image_prompt` → call adapter → upload bytes to S3 → collect keys
- `adapters.py` — `ImageAdapter` ABC + `MockImageAdapter` (tests) + `OpenAIImageAdapter` (prod)

S3 uploader is injected into the service as a plain callable `(key, body, content_type) -> None`, so tests never touch real S3.

## Image provider: OpenAI gpt-image-1

Chosen for:
- Strong character consistency across multi-page generation
- Spatial-composition adherence (responds to "leave the bottom 35% calm" prompts)
- Watercolor + style-prompt fidelity
- ~$0.042 per 1024×1024 image at medium quality
- OpenAI client SDK is straightforward to use from Lambda

Cost: ~$0.21 per story (5 images × $0.042).

Swap providers by adding a new class to `adapters.py` that implements `ImageAdapter.generate()` and updating `handler.py`. The hexagonal pattern is what made the mid-project DALL-E 3 → gpt-image-1 swap a single-class change, and it's what lets us evaluate alternatives like Bedrock Stable Diffusion in future iterations without rewriting the pipeline.

## Env vars (production)

- `OPENAI_SECRET_ARN` — required; ARN of the Secrets Manager secret holding the OpenAI API key. Fetched at cold start, never logged.
- `IMAGES_BUCKET` — required; S3 bucket name where generated illustrations are uploaded.
- `LOG_LEVEL` — optional. Defaults to `INFO`.

## IAM permissions required

Wired in `infra/stacks/pipeline_stack.py`:
- `secretsmanager:GetSecretValue` on the OpenAI key secret (`grant_read`).
- `s3:PutObject` on the images bucket (`grant_write`).

## Tests

`pytest lambdas/image_generation/tests/ -v` — all tests use `MockImageAdapter` (returns canned PNG bytes) and a stubbed S3 uploader. Zero network, zero AWS.