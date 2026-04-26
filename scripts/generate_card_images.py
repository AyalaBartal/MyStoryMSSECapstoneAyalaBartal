#!/usr/bin/env python3
"""Generate card illustration images via gpt-image-1.

Replaces the previous DALL-E 3 version. Uses the same model + same visual
language as the story page illustrations, so cards and storybook pages
share one cohesive watercolor brand aesthetic.

Run from repo root:
    python scripts/generate_card_images.py

Then upload to S3:
    aws s3 sync scripts/card_output/ s3://my-story-cards-691304835962/cards/

Cost: ~$0.42 (10 × $0.042 per gpt-image-1 medium 1024x1024).
Idempotent — skips files that already exist, so re-runs are free.
To regenerate one specific card, delete its file first then re-run.
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

# Shared style language — matches the storybook pages so cards and stories
# look like the same illustrator made them. Same color palette, same gouache
# texture, same warm watercolor feel. Used by every card prompt below.
STYLE = (
    "Soft painted watercolor illustration in the style of a children's "
    "picture book, gentle digital gouache shading, warm muted palette of "
    "soft cream, peach, sage green, and dusty blue tones, gentle natural "
    "lighting, soft cream paper background. Single subject centered in the "
    "frame, simple clean composition, no border, no frame, no torn paper, "
    "no arch, no decorative clutter, no text or written words anywhere, "
    "no paint pots, no brushes, no color swatches, no palette, no art "
    "supplies of any kind."
)

PROMPTS = {
    "hero": {
        "boy": (
            "A single young boy smiling warmly, head-and-shoulders portrait, "
            "kind eyes, friendly expression. ONE boy alone in the frame. "
            f"{STYLE}"
        ),
        "girl": (
            "A single young girl smiling warmly, head-and-shoulders portrait, "
            "kind eyes, friendly expression. ONE girl alone in the frame. "
            "Same illustrator style as the matching boy portrait. "
            f"{STYLE}"
        ),
    },
    "theme": {
        "space": (
            "A small whimsical rocket flying among one or two soft pastel "
            "planets, with a few tiny stars sprinkled around. Centered "
            "composition. "
            f"{STYLE}"
        ),
        "under_the_sea": (
            "A whimsical underwater scene with one glowing jellyfish "
            "floating gently above a small coral garden, a few tiny fish "
            "drifting nearby. Centered composition. "
            f"{STYLE}"
        ),
        "medieval_fantasy": (
            "A small friendly storybook castle on a gentle green hill, "
            "with little flag pennants and a soft pastel sky. Centered "
            "composition. "
            f"{STYLE}"
        ),
        "dinosaurs": (
            "A small friendly green dinosaur peeking out from behind tall "
            "ferns, with a curious gentle expression. Centered composition. "
            f"{STYLE}"
        ),
    },
    "adventure": {
        "secret_map": (
            "A rolled-up treasure map with a small brass compass resting "
            "beside it, soft pastel colors, gentle warmth. NOT dark wood, "
            "NOT sepia, NOT brown shadows. Centered composition. "
            f"{STYLE}"
        ),
        "talking_animal": (
            "A single friendly woodland fox smiling gently, storybook "
            "character portrait, warm and approachable. ONE fox alone in "
            "the frame, no second animal. "
            f"{STYLE}"
        ),
        "time_machine": (
            "A single whimsical vintage pocket watch with golden gears "
            "visible and a few tiny sparkles, centered on cream paper. "
            "Just the watch alone in the frame. "
            f"{STYLE}"
        ),
        "magic_key": (
            "A single ornate golden key glowing softly, with a heart-shaped "
            "or star-shaped handle. ONE key alone in the frame, no other "
            "objects. "
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
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024",
                    quality="medium",
                    n=1,
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
