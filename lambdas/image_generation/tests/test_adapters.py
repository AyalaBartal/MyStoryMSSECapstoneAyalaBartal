"""Unit tests for the ImageAdapter implementations."""

import base64
from unittest.mock import MagicMock

import pytest

from adapters import (
    ImageAdapter,
    MockImageAdapter,
    OpenAIImageAdapter,
)


class TestMockImageAdapter:
    def test_returns_default_bytes_when_no_canned(self):
        adapter = MockImageAdapter()
        result = adapter.generate("any prompt")
        assert isinstance(result, bytes)
        assert result.startswith(b"\x89PNG")  # PNG signature prefix

    def test_returns_canned_bytes_when_provided(self):
        custom = b"\x89PNG\r\n\x1a\nmy_custom_bytes"
        adapter = MockImageAdapter(canned=custom)
        assert adapter.generate("any prompt") == custom

    def test_canned_empty_bytes_is_respected(self):
        adapter = MockImageAdapter(canned=b"")
        assert adapter.generate("any prompt") == b""

    def test_is_instance_of_imageadapter(self):
        assert isinstance(MockImageAdapter(), ImageAdapter)


class TestOpenAIImageAdapter:
    """Tests use a stub client — no real OpenAI API call."""

    def _make_stub_client(self, png_bytes: bytes = b"\x89PNG\r\n\x1a\nfake"):
        """Build a client stub whose images.generate() returns an object
        shaped like the real OpenAI response: data=[obj with .b64_json]."""
        stub = MagicMock()
        image_obj = MagicMock()
        image_obj.b64_json = base64.b64encode(png_bytes).decode("ascii")
        response = MagicMock()
        response.data = [image_obj]
        stub.images.generate.return_value = response
        return stub, png_bytes

    def test_returns_decoded_bytes(self):
        client, expected = self._make_stub_client(png_bytes=b"\x89PNG\r\n\x1a\nhello")
        adapter = OpenAIImageAdapter(client=client)
        assert adapter.generate("prompt") == expected

    def test_calls_client_with_expected_kwargs(self):
        client, _ = self._make_stub_client()
        adapter = OpenAIImageAdapter(client=client)

        adapter.generate("my prompt")

        client.images.generate.assert_called_once_with(
            model="dall-e-3",
            prompt="my prompt",
            size="1024x1024",
            quality="standard",
            n=1,
            response_format="b64_json",
        )

    def test_custom_model_size_quality_are_used(self):
        client, _ = self._make_stub_client()
        adapter = OpenAIImageAdapter(
            client=client,
            model="dall-e-2",
            size="512x512",
            quality="hd",
        )

        adapter.generate("hi")

        call_kwargs = client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "dall-e-2"
        assert call_kwargs["size"] == "512x512"
        assert call_kwargs["quality"] == "hd"

    def test_is_instance_of_imageadapter(self):
        client, _ = self._make_stub_client()
        assert isinstance(OpenAIImageAdapter(client=client), ImageAdapter)


class TestImageAdapterABC:
    def test_cannot_instantiate_abstract_base(self):
        with pytest.raises(TypeError, match="abstract"):
            ImageAdapter()

    def test_subclass_without_generate_cannot_instantiate(self):
        class BadAdapter(ImageAdapter):
            pass

        with pytest.raises(TypeError, match="abstract"):
            BadAdapter()