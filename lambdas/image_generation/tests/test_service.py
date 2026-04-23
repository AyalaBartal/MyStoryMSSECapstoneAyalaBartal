"""Unit tests for image_generation service.py."""

import pytest

from adapters import MockImageAdapter
from service import (
    EXPECTED_PAGE_COUNT,
    _humanize,
    _s3_key_for_page,
    build_image_prompt,
    generate_images,
)


SAMPLE_PAGES = [
    {"page_num": 1, "text": "Maya lived in a coral city."},
    {"page_num": 2, "text": "A dragon appeared at dawn."},
    {"page_num": 3, "text": "She tried to speak to it."},
    {"page_num": 4, "text": "She thought of a clever plan."},
    {"page_num": 5, "text": "And they became friends."},
]


class TestHumanize:
    def test_single_word_unchanged(self):
        assert _humanize("girl") == "girl"

    def test_snake_case_becomes_spaces(self):
        assert _humanize("under_the_sea") == "under the sea"


class TestBuildImagePrompt:
    def test_all_placeholders_substituted(self):
        template = "Hero: {hero}, setting: {theme}, scene: {page_text}"
        result = build_image_prompt(
            page_text="a quiet afternoon",
            hero="girl",
            theme="under_the_sea",
            style_template=template,
        )
        assert result == "Hero: girl, setting: under the sea, scene: a quiet afternoon"

    def test_hero_and_theme_humanized(self):
        template = "{hero} in {theme}"
        result = build_image_prompt(
            page_text="",
            hero="super_hero",
            theme="medieval_fantasy",
            style_template=template,
        )
        assert result == "super hero in medieval fantasy"

    def test_page_text_not_humanized(self):
        """Page text from the LLM is already natural prose — don't touch it."""
        template = "{page_text}"
        original = "Maya_saw_a_dragon."  # artificial edge case
        result = build_image_prompt(
            page_text=original,
            hero="girl",
            theme="space",
            style_template=template,
        )
        assert result == original


class TestS3KeyForPage:
    def test_deterministic_key_format(self):
        assert _s3_key_for_page("abc-123", 1) == "stories/abc-123/page_1.png"

    def test_different_page_numbers_yield_different_keys(self):
        assert _s3_key_for_page("abc", 1) != _s3_key_for_page("abc", 2)

    def test_same_inputs_always_same_key(self):
        assert _s3_key_for_page("abc", 3) == _s3_key_for_page("abc", 3)


class TestGenerateImages:
    def _make_spy_uploader(self):
        """Return (uploader_fn, captured_calls_list)."""
        calls = []

        def uploader(key, body, content_type):
            calls.append(
                {"key": key, "body": body, "content_type": content_type}
            )

        return uploader, calls

    def test_returns_five_keys_in_order(self):
        uploader, _ = self._make_spy_uploader()
        keys = generate_images(
            story_id="story-123",
            hero="girl",
            theme="space",
            pages=SAMPLE_PAGES,
            adapter=MockImageAdapter(),
            s3_uploader=uploader,
            style_loader=lambda: "{hero}{theme}{page_text}",
        )
        assert keys == [
            "stories/story-123/page_1.png",
            "stories/story-123/page_2.png",
            "stories/story-123/page_3.png",
            "stories/story-123/page_4.png",
            "stories/story-123/page_5.png",
        ]

    def test_uploader_called_once_per_page(self):
        uploader, calls = self._make_spy_uploader()
        generate_images(
            story_id="story-123",
            hero="girl",
            theme="space",
            pages=SAMPLE_PAGES,
            adapter=MockImageAdapter(),
            s3_uploader=uploader,
            style_loader=lambda: "{hero}{theme}{page_text}",
        )
        assert len(calls) == EXPECTED_PAGE_COUNT
        for i, call in enumerate(calls, start=1):
            assert call["key"] == f"stories/story-123/page_{i}.png"
            assert call["content_type"] == "image/png"
            assert isinstance(call["body"], bytes)

    def test_uploader_receives_bytes_from_adapter(self):
        custom_bytes = b"\x89PNG\r\n\x1a\ntest-image-bytes"
        uploader, calls = self._make_spy_uploader()
        generate_images(
            story_id="story-123",
            hero="girl",
            theme="space",
            pages=SAMPLE_PAGES,
            adapter=MockImageAdapter(canned=custom_bytes),
            s3_uploader=uploader,
            style_loader=lambda: "{hero}{theme}{page_text}",
        )
        for call in calls:
            assert call["body"] == custom_bytes

    def test_adapter_receives_built_prompt(self):
        """The adapter sees the fully-substituted prompt, not the raw template."""
        class SpyAdapter:
            def __init__(self):
                self.received = []

            def generate(self, prompt):
                self.received.append(prompt)
                return b"\x89PNG_mock"

        adapter = SpyAdapter()
        uploader, _ = self._make_spy_uploader()
        generate_images(
            story_id="s",
            hero="girl",
            theme="under_the_sea",
            pages=SAMPLE_PAGES,
            adapter=adapter,
            s3_uploader=uploader,
            style_loader=lambda: "H:{hero} T:{theme} P:{page_text}",
        )
        assert adapter.received[0] == (
            "H:girl T:under the sea P:Maya lived in a coral city."
        )
        assert adapter.received[4] == (
            "H:girl T:under the sea P:And they became friends."
        )

    def test_wrong_page_count_raises(self):
        uploader, _ = self._make_spy_uploader()
        with pytest.raises(ValueError, match="Expected 5 pages, got 3"):
            generate_images(
                story_id="s",
                hero="girl",
                theme="space",
                pages=SAMPLE_PAGES[:3],
                adapter=MockImageAdapter(),
                s3_uploader=uploader,
                style_loader=lambda: "{hero}{theme}{page_text}",
            )

    def test_pages_processed_in_order_even_if_input_shuffled(self):
        """S3 keys must match page numbers regardless of input order."""
        uploader, _ = self._make_spy_uploader()
        shuffled = [
            SAMPLE_PAGES[4], SAMPLE_PAGES[2], SAMPLE_PAGES[0],
            SAMPLE_PAGES[3], SAMPLE_PAGES[1],
        ]
        keys = generate_images(
            story_id="story-123",
            hero="girl",
            theme="space",
            pages=shuffled,
            adapter=MockImageAdapter(),
            s3_uploader=uploader,
            style_loader=lambda: "{hero}{theme}{page_text}",
        )
        assert keys == [
            "stories/story-123/page_1.png",
            "stories/story-123/page_2.png",
            "stories/story-123/page_3.png",
            "stories/story-123/page_4.png",
            "stories/story-123/page_5.png",
        ]

    def test_upload_failure_propagates(self):
        """If S3 upload fails, error bubbles up for Step Functions to catch."""
        def failing_uploader(**kwargs):
            raise RuntimeError("S3 is down")

        with pytest.raises(RuntimeError, match="S3 is down"):
            generate_images(
                story_id="s",
                hero="girl",
                theme="space",
                pages=SAMPLE_PAGES,
                adapter=MockImageAdapter(),
                s3_uploader=failing_uploader,
                style_loader=lambda: "{hero}{theme}{page_text}",
            )