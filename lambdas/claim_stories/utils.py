"""Inline helpers for the entry Lambda.

These are intentionally NOT imported from a shared module. Each Lambda
keeps its own copy so it can be extracted into a standalone service
later without unwinding an import graph. See lambdas/README.md.
"""

import json
import logging
import os


# ── Logging ───────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for Lambda + CloudWatch."""
    logger = logging.getLogger(name)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    return logger


# ── HTTP response envelopes ───────────────────────────────────────────

# CORS headers. This Lambda handles POST /generate, hence the
# Allow-Methods value differs from retrieval's GET.
_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def make_response(status_code: int, body: dict) -> dict:
    """Wrap a dict body into a proper API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": _CORS_HEADERS,
        "body": json.dumps(body),
    }


def error_response(status_code: int, message: str) -> dict:
    """Standardized error envelope."""
    return make_response(status_code, {"error": message})