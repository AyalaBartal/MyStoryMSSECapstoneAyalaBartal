# pdf_assembly Lambda

Final stage of the pipeline. Combines the 5 illustrations + story text into a square picture-book PDF (with a custom cover page), uploads to S3, and marks the DynamoDB record COMPLETE.

## Contract

**Input** (from image_generation):
```json
{
  "story_id": "uuid-string",
  "name":     "Ayala",
  "age":      "9",
  "hero":     "girl",
  "theme":    "space",
  "adventure": "secret_map",
  "pages": [
    {"page_num": 1, "text": "...", "image_prompt": "..."},
    ...
    {"page_num": 5, "text": "...", "image_prompt": "..."}
  ],
  "image_s3_keys": [
    "stories/uuid/page_1.png",
    ...
    "stories/uuid/page_5.png"
  ]
}
```

**Output:** input dict plus the final PDF key + status flip:
```json
{
  ...,
  "pdf_s3_key": "stories/uuid/final.pdf",
  "status": "COMPLETE"
}
```

**Side effects:**
- Downloads 5 page illustrations from `IMAGES_BUCKET`
- Downloads the theme card image from the public cards bucket (used as the cover page background)
- Composes a square 8×8 inch picture-book PDF
- Uploads PDF to `PDFS_BUCKET` at `stories/{story_id}/final.pdf`
- Updates the DynamoDB record: `status = COMPLETE`, `pdf_s3_key = ...`

## Architecture

Hexagonal / ports-and-adapters:

- `handler.py` — Step Functions wrapper; wires real S3 client + DDB client + cover image fetch
- `service.py` — PDF composition logic using ReportLab; all I/O via injected callables
- `layout.json` — page dimensions, age-tier typography, text-band config, cover config — edit without code change

No third-party AI adapters here — PDF generation is pure Python (ReportLab + Pillow). The Lambda still uses the ports pattern: S3 download, S3 upload, and DDB update are injected as callables so tests don't touch AWS.

Injected ports:
- `s3_downloader(key) -> bytes` — fetch an image
- `s3_uploader(key, body, content_type) -> None` — upload PDF
- `ddb_updater(story_id, pdf_s3_key) -> None` — mark COMPLETE
- `cover_image_bytes` — fetched by the handler from the cards bucket and passed in

## Picture-book PDF format

Square 8×8 inch pages, modeled on real children's picture books:

| Element | Details |
|---|---|
| Page size | Square 576 × 576 pt (8 × 8 inch) — the dominant trim size for picture books |
| Cover page | Theme card image as full-bleed background, child's name as title in big italic Times, theme as subtitle, `✦ ✦ ✦` flourish |
| Story pages (×5) | Full-bleed illustration filling the entire page edge-to-edge |
| Text overlay | Soft cream band at the bottom (50% opacity) so the watercolor bleeds through softly |
| Text typography | Times-BoldItalic, dark brown (`#2b2320`), centered |
| Age-tiered font sizing | 24pt for ages 4-6, 19pt for 7-9, 16pt for 10-12 |
| Overflow protection | Text wrapped in `KeepInFrame(mode="shrink")` so longer-than-expected prose auto-shrinks instead of silently dropping |

## Layout config (`layout.json`)

```json
{
  "page_size_pt": 576,
  "age_buckets": {
    "young":  { "ages": ["4","5","6"], "font_size_pt": 24, ... },
    "middle": { "ages": ["7","8","9"], "font_size_pt": 19, ... },
    "older":  { "ages": ["10","11","12"], "font_size_pt": 16, ... }
  },
  "text_band": {
    "background_color": "#faf6f0",
    "background_opacity": 0.5,
    "font_name": "Times-BoldItalic",
    ...
  },
  "cover": {
    "title_font_name": "Times-BoldItalic",
    "title_font_size_pt": 54,
    ...
  }
}
```

## Env vars (production)

- `STORIES_TABLE` — DynamoDB table name (shared with entry/retrieval).
- `IMAGES_BUCKET` — S3 bucket for page illustrations (shared with image_generation, read-only here).
- `PDFS_BUCKET` — S3 bucket where the final PDF is uploaded.
- `LOG_LEVEL` — optional. Defaults to `INFO`.

## Tests

`pytest lambdas/pdf_assembly/tests/ -v` — all tests use stub callables and a tiny canned PNG. Zero network, zero AWS.
