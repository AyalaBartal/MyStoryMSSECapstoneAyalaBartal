#!/usr/bin/env python3
"""Generate card illustration images via DALL-E 3.

Run once to create cohesive storybook card images matching the book art.
Output: scripts/card_output/{category}/{value}.png (10 images total).

Run from repo root:
    python scripts/generate_card_images.py

Then upload to S3:
    aws s3 sync scripts/card_output/ s3://my-story-cards-691304835962/cards/

Cost: ~$0.40 (10 × $0.04 per DALL-E 3 standard 1024x1024).
Idempotent — skips files that already exist, so re-runs are free.
"""

import base64
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import openai  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / "card_output"


# Default style suffix for hero + adventure cards (simple subjects on cream).
# Theme cards use a richer inline style (torn paper + arch) defined per-prompt.
STYLE = (
    "single subject filling the entire frame. No border, no frame, no polaroid, "
    "no paint tools, no color swatches, no decorative elements. "
    "Soft watercolor illustration with gentle digital gouache shading, warm muted "
    "tones using only soft cream, peach, sage green, and dusty blue, gentle natural "
    "lighting, cream paper background, no text or written words anywhere in the image."
)

# Most prompts open with the "I NEED to test..." preamble. This is a known
# OpenAI workaround that disables DALL-E 3's automatic prompt-rewriting,
# which is what causes paint palettes / extra portraits / decorative
# clutter to creep into the generated images.
PREFIX = (
    "I NEED to test how the tool works with extremely simple prompts. "
    "DO NOT add any detail, just use it AS-IS: "
)

PROMPTS = {
    "hero": {
        "boy": (
            f"{PREFIX}"
            "A simple watercolor portrait of ONE young boy smiling warmly, "
            "head-and-shoulders only, plain soft cream background. "
            "ONE boy alone in the frame, no second portrait, no color palette, "
            "no swatches, no decorative elements."
        ),
        "girl": (
            f"{PREFIX}"
            "A simple watercolor portrait of ONE young girl smiling warmly, "
            "head-and-shoulders only, plain soft cream background. "
            "ONE girl alone in the frame, no second portrait, no color palette, "
            "no swatches, no decorative elements. "
            "Same illustrator style as the matching boy portrait."
        ),
    },
    "theme": {
        "space": (
            f"{PREFIX}"
            "A small whimsical rocket flying among one or two soft pastel planets, "
            "centered composition framed by a soft pastel arch, "
            "soft watercolor on torn cream paper background, "
            "tiny decorative grass and tiny flowers at the base, "
            "warm muted soft cream, peach, sage green, and dusty blue tones, "
            "no text, no other elements."
        ),
        "under_the_sea": (
            f"{PREFIX}"
            "A whimsical underwater scene with one glowing jellyfish over a small coral garden, "
            "centered composition framed by a soft pastel arch, "
            "soft watercolor on torn cream paper background, "
            "tiny decorative coral and seagrass at the base, "
            "warm muted soft cream, peach, sage green, and dusty blue tones, "
            "no text, no other elements."
        ),
        "medieval_fantasy": (
            f"{PREFIX}"
            "A small friendly castle on a gentle green hill, "
            "centered composition framed by a soft pastel rainbow arch, "
            "soft watercolor on torn cream paper background, "
            "tiny decorative grass and tiny flowers at the base, "
            "warm muted soft cream, peach, sage green, and dusty blue tones, "
            "no text, no other elements."
        ),
        "dinosaurs": (
            f"{PREFIX}"
            "A small friendly green dinosaur peeking through ferns, "
            "centered composition framed by a soft pastel arch, "
            "soft watercolor on torn cream paper background, "
            "tiny decorative ferns and tiny leaves at the base, "
            "warm muted soft cream, peach, sage green, and dusty blue tones, "
            "no text, no other elements."
        ),
    },
    "adventure": {
        "secret_map": (
            f"{PREFIX}"
            "A rolled treasure map and a small compass resting on cream paper, "
            "soft pastel colors, NOT dark wood, NOT sepia, NOT brown shadows, "
            "NO paint pots, NO brushes, NO color swatches, NO art supplies. "
            f"{STYLE}"
        ),
        "talking_animal": (
            f"{PREFIX}"
            "A single friendly woodland fox smiling gently, storybook character portrait, "
            "ONE fox alone in the frame, no second animal, no decorative elements. "
            f"{STYLE}"
        ),
        "time_machine": (
            f"{PREFIX}"
            "A single whimsical vintage clock with golden gears and tiny sparkles, "
            "centered on cream paper background, "
            "warm muted soft cream, peach, sage green, and dusty blue tones, "
            "NO paint pots, NO brushes, NO color swatches, NO color discs, "
            "NO art supplies, NO palette, NO design tools, "
            "just the clock alone in the frame."
        ),
        "magic_key": (
            f"{PREFIX}"
            "An ornate golden key glowing softly with a heart-shaped handle, "
            "ONE key alone, no decorative elements. "
            f"{STYLE}"
        ),
    },
}


def main():
    if "OPENAI_API_KEY" not in os.environ:
        print("ERROR: OPENAI_API_KEY not set (check .env).")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = openai.OpenAI()
    total = sum(len(v) for v in PROMPTS.values())
    done = 0

    for category, values in PROMPTS.items():
        category_dir = OUTPUT_DIR / category
        category_dir.mkdir(exist_ok=True)

        for value, prompt in values.items():
            done += 1
            out_path = category_dir / f"{value}.png"
            if out_path.exists():
                print(f"[{done}/{total}] {category}/{value}.png — skipped (exists)")
                continue

            print(f"[{done}/{total}] {category}/{value}.png — generating…")
            try:
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                    response_format="b64_json",
                )
                b64 = response.data[0].b64_json
                out_path.write_bytes(base64.b64decode(b64))
                print(f"              saved ({out_path.stat().st_size:,} bytes)")
            except Exception as e:
                print(f"              FAILED: {e}")

    print(f"\n✓ Done. Images in {OUTPUT_DIR}/")
    print("\nNext — upload to S3:")
    print("  aws s3 sync scripts/card_output/ s3://my-story-cards-691304835962/cards/")


if __name__ == "__main__":
    main()