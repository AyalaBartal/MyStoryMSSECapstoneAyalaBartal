#!/usr/bin/env python3
"""Smoke test: calls real Claude Haiku through the story_generation Lambda code.

Run from repo root:
    python scripts/smoke_test_story_gen.py

Requires ANTHROPIC_API_KEY. The script auto-loads .env at repo root if
python-dotenv is installed; otherwise export the key first:
    export ANTHROPIC_API_KEY=sk-ant-api03-...

Cost: ~$0.001 per run (Claude Haiku is cheap).

This is NOT a unit test — it makes a real network call and costs money.
Run it manually; don't add it to CI.
"""

import os
import sys
from pathlib import Path

# Auto-load .env if python-dotenv is available. Optional.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Same sys.path trick as the root conftest — make the Lambda importable.
LAMBDA_DIR = Path(__file__).resolve().parent.parent / "lambdas" / "story_generation"
sys.path.insert(0, str(LAMBDA_DIR))

import anthropic  # noqa: E402
from adapters import AnthropicLLMAdapter  # noqa: E402
from service import generate_story  # noqa: E402


def main():
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("  Either: export ANTHROPIC_API_KEY=sk-ant-...")
        print("  Or:     pip install python-dotenv and put it in .env at repo root")
        sys.exit(1)

    selections = {
        "hero": "girl",
        "theme": "under_the_sea",
        "challenge": "dragon",
        "strength": "super_smart",
    }

    print(f"Generating story for: {selections}\n")
    print("(Calling Claude Haiku... ~2 seconds)")

    client = anthropic.Anthropic()
    adapter = AnthropicLLMAdapter(client=client)

    try:
        pages = generate_story(selections, adapter=adapter)
    except Exception as e:
        print(f"\n✗ FAILED: {type(e).__name__}: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("STORY")
    print("=" * 60)
    for page in pages:
        print(f"\n--- Page {page['page_num']} ---")
        print(page["text"])
    print("\n" + "=" * 60)
    print(f"Done. {len(pages)} pages generated.")


if __name__ == "__main__":
    main()