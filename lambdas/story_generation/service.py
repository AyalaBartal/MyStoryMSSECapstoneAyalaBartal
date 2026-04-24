"""Pure business logic for story_generation.

No AWS, no LLM SDK — just plain Python orchestrating a prompt build,
an adapter call, and a response parse. All I/O goes through injected
ports (adapter, template_loader) so tests don't need anything real.
"""

import json
import re
from pathlib import Path
from typing import Callable, List


_PROMPT_PATH = Path(__file__).parent / "prompt_template.txt"

# The story arc is always 5 pages. Fixed for the capstone scope.
EXPECTED_PAGE_COUNT = 5


def _load_prompt_template(path: Path = _PROMPT_PATH) -> str:
    """Read the prompt template from disk.

    Templatized as a function so tests can inject a custom path and so
    production reads once per cold start (handler caches the result).
    """
    with open(path) as f:
        return f.read()


def _humanize(value: str) -> str:
    """Turn card schema values into prose.

    Schema values are snake_case identifiers ('under_the_sea',
    'super_smart'). The LLM produces better output if we feed it
    natural phrases ('under the sea', 'super smart'). Kept as a pure
    helper so it's testable and reusable.
    """
    return value.replace("_", " ")


def build_prompt(selections: dict, template: str) -> str:
    """Substitute card selections into the prompt template.

    Args:
        selections: {"hero": ..., "theme": ..., "challenge": ..., "strength": ...}
        template:   prompt_template.txt contents — must contain the 4
                    placeholders.

    Raises:
        KeyError: if the template references a field not in selections,
                  or if selections is missing a field the template needs.
    """
    return template.format(
        hero=_humanize(selections["hero"]),
        theme=_humanize(selections["theme"]),
        challenge=_humanize(selections["challenge"]),
        strength=_humanize(selections["strength"]),
    )


def parse_llm_response(raw: str) -> List[dict]:
    """Parse the LLM's JSON output into a list of page dicts.

    Tolerates common LLM quirks:
      - leading/trailing whitespace
      - markdown code fences (```json ... ```)

    Returns:
        [{"page_num": 1, "text": "..."}, ..., {"page_num": 5, "text": "..."}]

    Raises:
        ValueError: if the output isn't valid JSON, is missing the
                    'pages' key, has the wrong page count, or any page
                    is missing required fields.
    """
    cleaned = raw.strip()

    # Strip markdown fences if the model ignored the "no fences" instruction.
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM response is not valid JSON: {e}") from e

    if not isinstance(data, dict) or "pages" not in data:
        raise ValueError("LLM response missing 'pages' field")
    if not isinstance(data["pages"], list):
        raise ValueError("'pages' must be a list")
    if len(data["pages"]) != EXPECTED_PAGE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAGE_COUNT} pages, got {len(data['pages'])}"
        )

    pages = []
    for i, page in enumerate(data["pages"], start=1):
        if not isinstance(page, dict):
            raise ValueError(f"Page {i} is not a JSON object")
        for required in ("page_num", "text", "image_prompt"):
            if required not in page:
                raise ValueError(
                    f"Page {i} missing required '{required}' field"
                )
        pages.append({
            "page_num": int(page["page_num"]),
            "text": str(page["text"]),
            "image_prompt": str(page["image_prompt"]),
        })
    return pages


def generate_story(
    selections: dict,
    adapter,
    template_loader: Callable[[], str] = _load_prompt_template,
) -> List[dict]:
    """Orchestrate: build prompt → call adapter → parse response.

    Args:
        selections:      card dict — already validated upstream by
                         the entry Lambda, but we don't assume that.
        adapter:         any LLMAdapter instance. Injected so tests
                         can use MockLLMAdapter with no network.
        template_loader: callable that returns the prompt template.
                         Injected so tests can bypass the file read.

    Returns:
        list of 5 {"page_num", "text"} dicts.
    """
    template = template_loader()
    prompt = build_prompt(selections, template)
    raw = adapter.generate(prompt)
    return parse_llm_response(raw)