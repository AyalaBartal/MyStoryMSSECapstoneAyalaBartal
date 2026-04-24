"""Pure business logic for image_generation.

No AWS, no OpenAI SDK directly — just plain Python orchestrating:
  per page: build prompt → call adapter → upload bytes → collect key.

All I/O goes through injected ports (adapter, uploader, style_loader)
so tests don't need network or AWS.
"""

from pathlib import Path
from typing import Callable, List


_STYLE_PATH = Path(__file__).parent / "prompt_style.txt"

# Fixed 5-page story arc — matches story_generation.EXPECTED_PAGE_COUNT.
# Both Lambdas have their own copy of this constant (self-contained rule).
EXPECTED_PAGE_COUNT = 5


def _load_style_template(path: Path = _STYLE_PATH) -> str:
    """Read the illustration style template from disk.

    Function-shaped so tests can inject a custom path, and production
    reads once per cold start (handler caches the result).
    """
    with open(path) as f:
        return f.read()


def _humanize(value: str) -> str:
    """Turn card schema values into prose ('under_the_sea' -> 'under the sea').

    Duplicated from story_generation/service.py on purpose — self-contained
    Lambdas rule. If we ever extract a shared library, this is a candidate.
    """
    return value.replace("_", " ")


def build_image_prompt(
    page_image_prompt: str, hero: str, theme: str, style_template: str
) -> str:
    """Wrap Claude's sanitized image_prompt with our style layer.

    Claude produced page_image_prompt already safe for DALL-E's content
    filter. This function just adds the consistent style wrapper
    (watercolor, no text, etc.) without reintroducing dramatic language.
    """
    return style_template.format(
        hero=_humanize(hero),
        theme=_humanize(theme),
        image_prompt=page_image_prompt,
    )


def _s3_key_for_page(story_id: str, page_num: int) -> str:
    """Deterministic S3 key — same inputs always yield the same key.

    Idempotent: retrying the Lambda overwrites cleanly instead of
    writing duplicate copies. Matches the contract the downstream
    pdf_assembly Lambda expects.
    """
    return f"stories/{story_id}/page_{page_num}.png"


def generate_images(
    story_id: str,
    hero: str,
    theme: str,
    pages: List[dict],
    adapter,
    s3_uploader: Callable[..., None],
    style_loader: Callable[[], str] = _load_style_template,
) -> List[str]:
    """Generate one illustration per page, upload to S3, return keys.

    Args:
        story_id:     UUID for this story run — used as S3 key prefix.
        hero, theme:  card values (humanized internally).
        pages:        [{page_num, text}, ...] from story_generation.
        adapter:      any ImageAdapter instance.
        s3_uploader:  callable (key, body, content_type) -> None.
                      Injected so tests don't need real S3.
        style_loader: callable returning the style template string.

    Returns:
        List of S3 keys in page-number order.

    Raises:
        ValueError: if pages doesn't have exactly EXPECTED_PAGE_COUNT entries.
    """
    if len(pages) != EXPECTED_PAGE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAGE_COUNT} pages, got {len(pages)}"
        )

    style = style_loader()
    keys = []
    # Sort defensively — S3 keys must match page numbers, regardless
    # of input order.
    for page in sorted(pages, key=lambda p: p["page_num"]):
        prompt = build_image_prompt(
            page_image_prompt=page["image_prompt"],
            hero=hero,
            theme=theme,
            style_template=style,
        )
        image_bytes = adapter.generate(prompt)
        key = _s3_key_for_page(story_id, page["page_num"])
        s3_uploader(key=key, body=image_bytes, content_type="image/png")
        keys.append(key)
    return keys