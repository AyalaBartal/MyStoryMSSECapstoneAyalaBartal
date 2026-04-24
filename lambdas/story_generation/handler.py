"""AWS Lambda entrypoint for story_generation.

Invoked by Step Functions with the input:
    {"story_id": "...", "hero": "...", "theme": "...",
     "challenge": "...", "strength": "..."}

Returns the input dict plus a "pages" array.

Secrets:
    ANTHROPIC_API_KEY is loaded from AWS Secrets Manager at cold start
    if not already in the env. Local dev sets it via .env so the
    Secrets Manager fetch is skipped. Production gets ANTHROPIC_SECRET_ARN
    from CDK and fetches the actual key at first invocation.
"""

import os

from adapters import AnthropicLLMAdapter
from service import generate_story


_ADAPTER = None


def _ensure_api_key_loaded():
    """Fetch ANTHROPIC_API_KEY from Secrets Manager if not already in env.

    Local dev: .env already provides ANTHROPIC_API_KEY — no-op.
    Lambda:    CDK sets ANTHROPIC_SECRET_ARN. First call fetches the
               value and stashes it in os.environ so anthropic.Anthropic()
               can read it the standard way.

    Deferred import of boto3 so local tests that never call this function
    don't pay the import cost.
    """
    if "ANTHROPIC_API_KEY" in os.environ:
        return
    secret_arn = os.environ.get("ANTHROPIC_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError(
            "Neither ANTHROPIC_API_KEY nor ANTHROPIC_SECRET_ARN is set. "
            "Local dev should have ANTHROPIC_API_KEY in .env; "
            "production Lambda should have ANTHROPIC_SECRET_ARN from CDK."
        )
    import boto3
    sm = boto3.client("secretsmanager")
    response = sm.get_secret_value(SecretId=secret_arn)
    os.environ["ANTHROPIC_API_KEY"] = response["SecretString"]


def _get_adapter():
    """Lazily build the LLM adapter on first call, cache for reuse."""
    global _ADAPTER
    if _ADAPTER is None:
        _ensure_api_key_loaded()
        import anthropic
        client = anthropic.Anthropic()
        _ADAPTER = AnthropicLLMAdapter(client=client)
    return _ADAPTER


def lambda_handler(event, context):
    """Step Functions entrypoint."""
    selections = {
        "hero":      event["hero"],
        "theme":     event["theme"],
        "challenge": event["challenge"],
        "strength":  event["strength"],
    }
    pages = generate_story(selections, adapter=_get_adapter())
    return {**event, "pages": pages}