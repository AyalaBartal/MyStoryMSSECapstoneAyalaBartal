"""AWS Lambda entrypoint for story_generation.

Invoked by Step Functions with the input:
    {"story_id": "...", "hero": "...", "theme": "...",
     "challenge": "...", "strength": "..."}

Returns the input dict plus a "pages" array — preserving all input
keys so the next step (image_generation) has what it needs.

Error handling:
    Any exception bubbles up. Step Functions catches it, transitions
    the execution to FAILED, and a Fail state / pdf_assembly updates
    DDB. We don't try/except here — the state machine is the right
    place for that policy, and swallowing errors would hide real
    problems from CloudWatch alarms.
"""

from adapters import AnthropicLLMAdapter
from service import generate_story


# Module-level cache — Lambda containers are reused across invocations.
# Building the Anthropic client once per cold start (not per event)
# saves ~50-100ms of connection setup per warm invocation.
_ADAPTER = None


def _get_adapter():
    """Lazily build the LLM adapter on first call, cache for reuse.

    Deferred import of `anthropic` so the module loads fast at cold
    start — the SDK is only pulled in when we actually need to call it.
    Tests monkeypatch this function (or `_ADAPTER`) to inject a
    MockLLMAdapter and keep handler tests offline.
    """
    global _ADAPTER
    if _ADAPTER is None:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        _ADAPTER = AnthropicLLMAdapter(client=client)
    return _ADAPTER


def lambda_handler(event, context):
    """Step Functions entrypoint.

    Args:
        event:   {"story_id", "hero", "theme", "challenge", "strength", ...}
        context: AWS Lambda context (unused).

    Returns:
        event + {"pages": [...]} — input keys pass through untouched.
    """
    selections = {
        "hero":      event["hero"],
        "theme":     event["theme"],
        "challenge": event["challenge"],
        "strength":  event["strength"],
    }
    pages = generate_story(selections, adapter=_get_adapter())
    return {**event, "pages": pages}