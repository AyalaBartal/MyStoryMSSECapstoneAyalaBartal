# pdf_assembly Lambda

Final stage of the pipeline. Combines story text + images into a PDF, uploads to S3, and marks the DynamoDB record COMPLETE.

## Contract

**Input** (from image_generation):
```json
{
  "story_id": "uuid-string",
  "hero": "girl",
  "theme": "space",
  "challenge": "asteroid",
  "strength": "super_smart",
  "pages": [
    {"page_num": 1, "text": "..."},
    ...
    {"page_num": 5, "text": "..."}
  ],
  "image_s3_keys": [
    "stories/uuid/page_1.png",
    ...
    "stories/uuid/page_5.png"
  ]
}
```

**Output:**
```json
{
  "story_id": "uuid-string",
  "pdf_s3_key": "stories/uuid/final.pdf",
  "status": "COMPLETE"
}
```

**Side effects:**
- Downloads 5 images from S3
- Uploads PDF to S3 at `stories/{story_id}/final.pdf`
- Updates DDB record: `status = COMPLETE`, `pdf_s3_key = ...`

## Architecture

Hexagonal / ports-and-adapters:

- `handler.py` — Step Functions wrapper; wires real S3 client + DDB client
- `service.py` — PDF assembly logic using ReportLab; I/O via injected callables
- `layout.json` — page dimensions, margins, font sizes, image placement — edit without code change

No third-party ML adapters here — PDF generation is pure Python (ReportLab). The Lambda still uses the ports pattern: S3 download, S3 upload, and DDB update are injected as callables so tests don't touch AWS.

Injected ports:
- `s3_downloader(key) -> bytes` — fetch an image
- `s3_uploader(key, body, content_type) -> None` — upload PDF
- `ddb_updater(story_id, pdf_s3_key) -> None` — mark COMPLETE

## Layout (see `layout.json`)

| Element | Default |
|---|---|
| Page size | US Letter (612×792 pt) |
| Page margin | 54 pt (0.75 in) |
| Image size | 450×450 pt (6.25 in square), centered |
| Text font | Helvetica 14pt, 20pt leading |

Image sits above text, text wraps in the bottom region. One story page per PDF page; 5 PDF pages total.

## Env vars (production)

- `STORIES_TABLE` — DynamoDB table name (shared with entry/retrieval)
- `PDFS_BUCKET` — S3 bucket (shared with image_generation)

## Tests

`pytest lambdas/pdf_assembly/tests/ -v` — all tests use stub callables. Zero network, zero AWS.