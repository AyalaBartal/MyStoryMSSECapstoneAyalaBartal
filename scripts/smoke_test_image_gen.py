#!/usr/bin/env python3
"""Smoke test: calls real DALL-E 3 through the image_generation Lambda code.

Run from repo root:
    python scripts/smoke_test_image_gen.py

Requires OPENAI_API_KEY. Auto-loads .env via python-dotenv if available.

Uses a local-disk uploader instead of S3 so you can actually open the
generated images. Outputs go to scripts/smoke_output/.

Cost: ~$0.20 per run (5 images × ~$0.04 DALL-E 3 standard quality).

Not a unit test — real network call, real money. Run manually; don't
add to CI.
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

LAMBDA_DIR = Path(__file__).resolve().parent.parent / "lambdas" / "image_generation"
sys.path.insert(0, str(LAMBDA_DIR))

import openai  # noqa: E402
from adapters import OpenAIImageAdapter  # noqa: E402
from service import generate_images  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / "smoke_output"


def make_disk_uploader(output_dir: Path):
    """Build an uploader that writes bytes to disk instead of S3.

    Same signature as the production S3 uploader so service.py doesn't
    know the difference. This is the superpower of the port/adapter
    approach — same code, different backend.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    def upload(key: str, body: bytes, content_type: str) -> None:
        # Flatten the S3 key into a filename (swap / for _).
        filename = key.replace("/", "_")
        path = output_dir / filename
        path.write_bytes(body)
        print(f"  saved: {path.relative_to(output_dir.parent.parent)}")

    return upload


# Canned pages — mimic what story_generation would output. Using short
# evocative prompts to keep DALL-E focused.
SAMPLE_PAGES = [
    {"page_num": 1, "text": "A curious girl in a spacesuit floats outside her silver rocket, watching Earth glow below her."},
    {"page_num": 2, "text": "A huge jagged asteroid tumbles toward her ship, its shadow darkening the stars."},
    {"page_num": 3, "text": "The girl presses buttons frantically, but every system flashes red and refuses to respond."},
    {"page_num": 4, "text": "She closes her eyes, breathes, and whispers equations to herself — then reroutes the thrusters with a clever formula."},
    {"page_num": 5, "text": "The asteroid sails safely past as she drifts, smiling, bathed in golden sunlight from behind Earth."},
]


def main():
    if "OPENAI_API_KEY" not in os.environ:
        print("ERROR: OPENAI_API_KEY not set.")
        print("  Either: export OPENAI_API_KEY=sk-...")
        print("  Or:     put it in .env at repo root")
        sys.exit(1)

    story_id = "smoke-test-story"
    print(f"Generating 5 images for story_id={story_id}")
    print(f"Output folder: {OUTPUT_DIR}\n")

    client = openai.OpenAI()
    adapter = OpenAIImageAdapter(client=client)
    uploader = make_disk_uploader(OUTPUT_DIR)

    print("(Calling DALL-E 3 5 times... this takes ~30-60 seconds)")

    try:
        keys = generate_images(
            story_id=story_id,
            hero="girl",
            theme="space",
            pages=SAMPLE_PAGES,
            adapter=adapter,
            s3_uploader=uploader,
        )
    except Exception as e:
        print(f"\n✗ FAILED: {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"\n✓ Done. {len(keys)} images written to {OUTPUT_DIR}/")
    print("Open them to inspect quality:")
    for key in keys:
        print(f"  - {OUTPUT_DIR / key.replace('/', '_')}")


if __name__ == "__main__":
    main()