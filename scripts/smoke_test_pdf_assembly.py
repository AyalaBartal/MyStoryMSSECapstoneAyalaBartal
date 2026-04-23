#!/usr/bin/env python3
"""Smoke test: build a real PDF from the images previously generated
by smoke_test_image_gen.py.

Run from repo root:
    python scripts/smoke_test_pdf_assembly.py

Prerequisites:
    - Run scripts/smoke_test_image_gen.py first (produces 5 PNGs in
      scripts/smoke_output/).

Outputs:
    scripts/smoke_output/final.pdf — open it to see the full storybook.

No cost — pure local Python. No AWS, no API calls. Uses disk-backed
downloader/uploader and a no-op DDB updater in place of the real ports.
"""

import sys
from pathlib import Path

LAMBDA_DIR = Path(__file__).resolve().parent.parent / "lambdas" / "pdf_assembly"
sys.path.insert(0, str(LAMBDA_DIR))

from service import assemble_pdf  # noqa: E402


# Canned pages matching the ones smoke_test_image_gen.py used — so the
# text in the PDF matches the illustrations that were generated.
SAMPLE_PAGES = [
    {"page_num": 1, "text": "A curious girl in a spacesuit floats outside her silver rocket, watching Earth glow below her."},
    {"page_num": 2, "text": "A huge jagged asteroid tumbles toward her ship, its shadow darkening the stars."},
    {"page_num": 3, "text": "The girl presses buttons frantically, but every system flashes red and refuses to respond."},
    {"page_num": 4, "text": "She closes her eyes, breathes, and whispers equations to herself — then reroutes the thrusters with a clever formula."},
    {"page_num": 5, "text": "The asteroid sails safely past as she drifts, smiling, bathed in golden sunlight from behind Earth."},
]

STORY_ID = "smoke-test-story"

SMOKE_OUTPUT_DIR = Path(__file__).resolve().parent / "smoke_output"


def make_disk_downloader(smoke_output_dir: Path):
    """S3-downloader-shaped callable that reads from disk.

    smoke_test_image_gen.py wrote PNGs with slashes flattened to
    underscores. Mirror that transform so the keys line up.
    """
    def download(key: str) -> bytes:
        filename = key.replace("/", "_")
        path = smoke_output_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Expected image at {path} — "
                "run scripts/smoke_test_image_gen.py first."
            )
        return path.read_bytes()

    return download


def make_disk_uploader(smoke_output_dir: Path):
    """S3-uploader-shaped callable that writes to disk."""
    smoke_output_dir.mkdir(parents=True, exist_ok=True)

    def upload(key: str, body: bytes, content_type: str) -> None:
        # Save as final.pdf for easy opening, regardless of S3 key shape.
        path = smoke_output_dir / "final.pdf"
        path.write_bytes(body)
        print(f"  saved: {path.relative_to(smoke_output_dir.parent.parent)}")
        print(f"  bytes: {len(body):,}")

    return upload


def noop_ddb_updater(story_id: str, pdf_s3_key: str) -> None:
    """No-op DDB updater for smoke test — nothing to update locally."""
    print(f"  (would update DDB: story_id={story_id}, "
          f"pdf_s3_key={pdf_s3_key})")


def main():
    image_s3_keys = [
        f"stories/{STORY_ID}/page_{i}.png" for i in range(1, 6)
    ]

    print(f"Building PDF for story_id={STORY_ID}")
    print(f"Reading images from: {SMOKE_OUTPUT_DIR}\n")

    try:
        pdf_key = assemble_pdf(
            story_id=STORY_ID,
            pages=SAMPLE_PAGES,
            image_s3_keys=image_s3_keys,
            s3_downloader=make_disk_downloader(SMOKE_OUTPUT_DIR),
            s3_uploader=make_disk_uploader(SMOKE_OUTPUT_DIR),
            ddb_updater=noop_ddb_updater,
        )
    except Exception as e:
        print(f"\n✗ FAILED: {type(e).__name__}: {e}")
        sys.exit(1)

    pdf_path = SMOKE_OUTPUT_DIR / "final.pdf"
    print(f"\n✓ Done. PDF written to {pdf_path}")
    print(f"   S3 key (would be): {pdf_key}")
    print(f"   Open it: open {pdf_path}")


if __name__ == "__main__":
    main()