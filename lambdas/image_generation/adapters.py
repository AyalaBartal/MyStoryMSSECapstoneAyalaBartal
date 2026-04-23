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
    """Calls OpenAI DALL-E 3 via the official SDK.

    The client is injected — handler.py builds it (reading OPENAI_API_KEY
    from the env) and passes it in. Tests inject a stub client and
    assert on how the adapter calls it.
    """

    DEFAULT_MODEL = "dall-e-3"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_QUALITY = "standard"

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
        """Call DALL-E 3 and return raw PNG bytes.

        response_format='b64_json' gets us bytes directly in the response
        payload. The alternative ('url') returns a URL that expires in
        60 minutes — we'd have to make a second HTTP call to download
        the image, which is slower and adds a failure mode. b64_json
        wins for this pipeline.
        """
        response = self._client.images.generate(
            model=self._model,
            prompt=prompt,
            size=self._size,
            quality=self._quality,
            n=1,
            response_format="b64_json",
        )
        # OpenAI returns data=[ImageObject(b64_json="...")].
        b64 = response.data[0].b64_json
        return base64.b64decode(b64)