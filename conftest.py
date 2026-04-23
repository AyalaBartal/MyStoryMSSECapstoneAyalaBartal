"""Root conftest — enables running all Lambda tests in one pytest session.

Each Lambda has identically-named modules (handler.py, service.py, utils.py).
Python's sys.modules cache normally means "import service" returns the
same module regardless of which Lambda you're in — so tests from a
second Lambda would see the first Lambda's code.

This conftest uses pytest_collectstart to reset sys.modules and sys.path
every time pytest enters a different Lambda folder. Also pre-sets the
env vars every Lambda reads at import time, so any Lambda's handler
can be imported without a KeyError.
"""

import os
import sys
from pathlib import Path


# ── Env vars read at handler-import time by various Lambdas ──────────
# Each Lambda only reads its own subset; setting them all up front
# means any Lambda's handler imports cleanly.
os.environ.setdefault("STORIES_TABLE", "test-stories")
os.environ.setdefault("PDFS_BUCKET", "test-pdfs")
os.environ.setdefault(
    "STATE_MACHINE_ARN",
    "arn:aws:states:us-east-1:123456789012:stateMachine:test-pipeline",
)
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")


# ── Per-Lambda import isolation ──────────────────────────────────────

_LAMBDAS_ROOT = (Path(__file__).resolve().parent / "lambdas").resolve()
_MODULES_TO_RESET = ("handler", "service", "utils", "adapters")
_current_lambda = None


def _activate_lambda_for(raw_path):
    """If raw_path sits inside a Lambda folder, reset sys.modules/sys.path
    to point at that Lambda. No-op if we're already configured for it."""
    global _current_lambda

    if raw_path is None:
        return
    try:
        path = Path(str(raw_path)).resolve()
    except (OSError, ValueError):
        return

    try:
        rel = path.relative_to(_LAMBDAS_ROOT)
    except ValueError:
        return  # Not inside lambdas/ — nothing to do

    if not rel.parts:
        return
    lambda_dir = _LAMBDAS_ROOT / rel.parts[0]
    if not lambda_dir.is_dir():
        return

    if lambda_dir == _current_lambda:
        return  # Already configured for this Lambda

    # Entering a new Lambda — purge cached modules from any prior Lambda
    for mod in _MODULES_TO_RESET:
        sys.modules.pop(mod, None)

    # Remove other Lambdas' paths from sys.path; put this one at [0]
    lambda_dir_str = str(lambda_dir)
    for p in list(sys.path):
        if p.startswith(str(_LAMBDAS_ROOT)) and p != lambda_dir_str:
            sys.path.remove(p)
    if lambda_dir_str in sys.path:
        sys.path.remove(lambda_dir_str)
    sys.path.insert(0, lambda_dir_str)

    _current_lambda = lambda_dir


def pytest_collectstart(collector):
    """Fires during collection — handles test files with module-level
    imports like `from service import X` at the top of test_service.py."""
    raw_path = getattr(collector, "path", None) or getattr(
        collector, "fspath", None
    )
    _activate_lambda_for(raw_path)


def pytest_runtest_setup(item):
    """Fires right before each test runs — handles test files that do
    `import handler` *inside* a test function. Needed because by the
    time execution starts, collection has already walked through every
    Lambda folder and sys.path points at whichever was collected last."""
    raw_path = getattr(item, "path", None) or getattr(item, "fspath", None)
    _activate_lambda_for(raw_path)