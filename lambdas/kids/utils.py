"""Inline helpers for the entry Lambda.

These are intentionally NOT imported from a shared module. Each Lambda
keeps its own copy so it can be extracted into a standalone service
later without unwinding an import graph. See lambdas/README.md.
"""

import json
import logging
import os
from decimal import Decimal


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


def _decimal_default(o):
    """JSON encoder fallback for DynamoDB Decimal values.

    DDB returns all numbers as decimal.Decimal — convert to int if whole,
    else float. Loses precision on very large floats but that's fine for
    user-facing data like birth years and counts.
    """
    if isinstance(o, Decimal):
        return int(o) if o == int(o) else float(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def make_response(status_code: int, body: dict) -> dict:
    """Wrap a dict body into a proper API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": _CORS_HEADERS,
        "body": json.dumps(body, default=_decimal_default),
    }

def error_response(status_code: int, message: str) -> dict:
    """Standardized error envelope."""
    return make_response(status_code, {"error": message})