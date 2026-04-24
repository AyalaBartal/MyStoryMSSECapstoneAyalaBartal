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
    {"page_num": 1, "text": "Maya lived in a coral city.", "image_prompt": "A girl smiling in a glowing coral city"},
    {"page_num": 2, "text": "A dragon appeared at dawn.", "image_prompt": "A curious dragon arriving at sunrise"},
    {"page_num": 3, "text": "She tried to speak to it.", "image_prompt": "A girl gently reaching out her hand"},
    {"page_num": 4, "text": "She thought of a clever plan.", "image_prompt": "A girl thinking with a spark of an idea"},
    {"page_num": 5, "text": "And they became friends.", "image_prompt": "A girl and a dragon sharing a gentle moment"},
]


class TestHumanize:
    def test_single_word_unchanged(self):
        assert _humanize("girl") == "girl"

    def test_snake_case_becomes_spaces(self):
        assert _humanize("under_the_sea") == "under the sea"


class TestBuildImagePrompt:
    def test_all_placeholders_substituted(self):
        template = "Hero: {hero}, setting: {theme}, scene: {image_prompt}"
        result = build_image_prompt(
            page_image_prompt="a quiet afternoon",
            hero="girl",
            theme="under_the_sea",
            style_template=template,
        )
        assert result == "Hero: girl, setting: under the sea, scene: a quiet afternoon"

    def test_hero_and_theme_humanized(self):
        template = "{hero} in {theme}"
        result = build_image_prompt(
            page_image_prompt="",
            hero="super_hero",
            theme="medieval_fantasy",
            style_template=template,
        )
        assert result == "super hero in medieval fantasy"

    def test_image_prompt_passed_verbatim(self):
        """Claude's image_prompt is already sanitized — don't touch it."""
        template = "{image_prompt}"
        original = "A whimsical scene"
        result = build_image_prompt(
            page_image_prompt=original,
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
            style_loader=lambda: "{hero}{theme}{image_prompt}",
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
            style_loader=lambda: "{hero}{theme}{image_prompt}",
        )
        assert len(calls) == EXPECTED_PAGE_COUNT
        for i, call in enumerate(calls, start=1):
            assert call["key"] == f"stories/story-123/page_{i}.png"
            assert call["content_type"] == "image/png"
            assert isinstance(call["body"], bytes)