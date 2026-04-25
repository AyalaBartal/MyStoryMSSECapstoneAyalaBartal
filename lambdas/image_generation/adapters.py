"""Image adapter interface and implementations.

Ports-and-adapters: the Lambda's business logic depends on the abstract
ImageAdapter interface, never on a concrete provider SDK. Swap providers
by writing a new subclass — no service.py change needed.

generate() returns raw image bytes (PNG by convention). The caller is
responsible for uploading them wherever they belong (S3, disk, etc.).
"""

import base64
from abc import ABC, abstractmethod


class ImageAdapter(ABC):
    """Port for generating an image from a prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> bytes:
        """Return raw image bytes for a prompt (PNG by convention)."""
        raise NotImplementedError


class MockImageAdapter(ImageAdapter):
    """Deterministic adapter for tests. No network, no cost.

    Returns a tiny canned byte string with a PNG signature prefix so
    any downstream code that sniffs the first bytes still sees 'PNG'.
    Tests that want error paths can pass custom canned bytes.
    """

    # PNG magic number + short payload. Not a valid image, but valid
    # bytes — enough for service tests that care about "did we get
    # bytes?" and "were they uploaded to S3?"
    DEFAULT_BYTES = b"\x89PNG\r\n\x1a\n_mock_image_placeholder_"

    def __init__(self, canned: bytes = None):
        self._canned = canned if canned is not None else self.DEFAULT_BYTES

    def generate(self, prompt: str) -> bytes:
        return self._canned


class OpenAIImageAdapter(ImageAdapter):
    """Calls OpenAI gpt-image-1 (gpt-4o image generation) via the official SDK.

    Replaces DALL-E 3. Better at character consistency, prompt following
    (spatial composition rules), and supports reference-image conditioning
    for tighter character continuity across pages.

    The client is injected — handler.py builds it (reading OPENAI_API_KEY
    from the env) and passes it in. Tests inject a stub client and
    assert on how the adapter calls it.
    """

    DEFAULT_MODEL = "gpt-image-1"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_QUALITY = "medium"  # gpt-image-1 tiers: low / medium / high

    def __init__(
        self,
        client,
        model: str = DEFAULT_MODEL,
        size: str = DEFAULT_SIZE,
        quality: str = DEFAULT_QUALITY,
    ):
        self._client = client
        self._model = model
        self._size = size
        self._quality = quality

    def generate(self, prompt: str) -> bytes:
        """Call gpt-image-1 and return raw PNG bytes.

        gpt-image-1 always returns base64-encoded image data in
        response.data[0].b64_json (no response_format parameter to set,
        unlike DALL-E 3 where we had to opt in).
        """
        response = self._client.images.generate(
            model=self._model,
            prompt=prompt,
            size=self._size,
            quality=self._quality,
            n=1,
        )
        b64 = response.data[0].b64_json
        return base64.b64decode(b64)