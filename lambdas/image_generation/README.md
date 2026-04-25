# image_generation Lambda

Third stage of the pipeline. Takes the 5 story pages, generates an illustration per page, uploads them to S3, returns the S3 keys.

## Contract

**Input** (from story_generation):
```json
{
  "story_id": "uuid-string",
  "hero": "girl",
  "theme": "space",
  "adventure": "asteroid",
  "strength": "super_smart",
  "pages": [
    {"page_num": 1, "text": "..."},
    ...
    {"page_num": 5, "text": "..."}
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

- `handler.py` — Step Functions wrapper; builds real S3 client + image adapter
- `service.py` — pure logic: for each page, build prompt → call adapter → upload bytes to S3 → collect keys
- `adapters.py` — `ImageAdapter` ABC + `MockImageAdapter` (tests) + `OpenAIImageAdapter` (prod)
- `prompt_style.txt` — illustration style guide, editable without code change

S3 uploader is injected into the service as a plain callable `(key, body, content_type) -> None`, so tests never touch real S3.

## Image provider: OpenAI DALL-E 3

Chosen for: best-in-class quality for children's book illustrations, simple API, predictable cost (~$0.04 per 1024x1024 image → ~$0.20 per story).

Swap providers by adding a new class to `adapters.py` that implements `ImageAdapter.generate()` and updating `handler.py`. A locally-trained SD 1.5 LoRA is the post-capstone training-track goal.

## Env vars (production)

- `OPENAI_API_KEY` — required; injected via CDK from AWS Secrets Manager in production.
- `PDFS_BUCKET` — already set per the existing Lambdas.

## Tests

`pytest lambdas/image_generation/tests/ -v` — all tests use `MockImageAdapter` and a stubbed S3 uploader. Zero network, zero AWS.