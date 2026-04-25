"""Unit tests for service.py — prompt building, response parsing, orchestration."""

import json

import pytest

from adapters import MockLLMAdapter
from service import (
    EXPECTED_PAGE_COUNT,
    _humanize,
    build_prompt,
    generate_story,
    parse_llm_response,
)


# A complete, valid card selection.
VALID_SELECTIONS = {
    "name": "Maya",
    "age": "9",
    "hero": "girl",
    "theme": "under_the_sea",
    "adventure": "talking_animal",
}


class TestHumanize:
    def test_single_word_unchanged(self):
        assert _humanize("girl") == "girl"

    def test_snake_case_becomes_spaces(self):
        assert _humanize("under_the_sea") == "under the sea"

    def test_multiple_underscores(self):
        assert _humanize("a_b_c_d") == "a b c d"


class TestBuildPrompt:
    def test_all_placeholders_substituted(self):
        template = "Name: {name}, age {age}, a {hero} in {theme} facing {adventure}."
        result = build_prompt(VALID_SELECTIONS, template)
        assert "Maya" in result
        assert "9" in result
        assert "girl" in result
        assert "under the sea" in result
        assert "talking animal" in result
        assert "{" not in result

    def test_missing_selection_field_raises(self):
        """If selections lack any required field, build_prompt raises KeyError.
        (name is the first key looked up now, so the error message will say 'name',
        not 'hero'. Just assert that SOME KeyError is raised.)"""
        template = "Hero: {hero}"
        bad_selections = {"theme": "space"}
        with pytest.raises(KeyError):
            build_prompt(bad_selections, template)

    def test_selections_are_humanized_before_substitution(self):
        template = "The {theme} is calling {name}."
        result = build_prompt(VALID_SELECTIONS, template)
        assert result == "The under the sea is calling Maya."


class TestParseLLMResponse:
    def _valid_payload(self) -> str:
        return json.dumps({
            "pages": [
                {
                    "page_num": i,
                    "text": f"Page {i} text",
                    "image_prompt": f"Page {i} image prompt",
                }
                for i in range(1, EXPECTED_PAGE_COUNT + 1)
            ]
        })

    def test_happy_path_returns_pages(self):
        pages = parse_llm_response(self._valid_payload())
        assert len(pages) == EXPECTED_PAGE_COUNT
        assert pages[0] == {
            "page_num": 1,
            "text": "Page 1 text",
            "image_prompt": "Page 1 image prompt",
        }
        assert pages[4] == {
            "page_num": 5,
            "text": "Page 5 text",
            "image_prompt": "Page 5 image prompt",
        }

    def test_strips_markdown_code_fences(self):
        wrapped = f"```json\n{self._valid_payload()}\n```"
        pages = parse_llm_response(wrapped)
        assert len(pages) == EXPECTED_PAGE_COUNT

    def test_strips_plain_backtick_fences(self):
        wrapped = f"```\n{self._valid_payload()}\n```"
        pages = parse_llm_response(wrapped)
        assert len(pages) == EXPECTED_PAGE_COUNT

    def test_handles_leading_trailing_whitespace(self):
        padded = f"\n\n  {self._valid_payload()}  \n"
        pages = parse_llm_response(padded)
        assert len(pages) == EXPECTED_PAGE_COUNT

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_llm_response("{not valid json")

    def test_missing_pages_key_raises(self):
        payload = json.dumps({"stories": []})
        with pytest.raises(ValueError, match="missing 'pages'"):
            parse_llm_response(payload)

    def test_pages_not_a_list_raises(self):
        payload = json.dumps({"pages": "not a list"})
        with pytest.raises(ValueError, match="must be a list"):
            parse_llm_response(payload)

    def test_wrong_page_count_raises(self):
        payload = json.dumps({"pages": [{"page_num": 1, "text": "only one"}]})
        with pytest.raises(ValueError, match="Expected 5 pages, got 1"):
            parse_llm_response(payload)

    def test_page_missing_text_field_raises(self):
        payload = json.dumps({
            "pages": [{"page_num": i} for i in range(1, 6)]  # no 'text'
        })
        with pytest.raises(ValueError, match="missing required"):
            parse_llm_response(payload)

    def test_page_not_a_dict_raises(self):
        payload = json.dumps({
            "pages": ["page 1", "page 2", "page 3", "page 4", "page 5"]
        })
        with pytest.raises(ValueError, match="not a JSON object"):
            parse_llm_response(payload)


class TestGenerateStory:
    def test_happy_path_returns_five_pages(self):
        adapter = MockLLMAdapter()  # returns default 5-page response
        result = generate_story(
            VALID_SELECTIONS,
            adapter=adapter,
            template_loader=lambda: "N:{name} A:{age} H:{hero} T:{theme} C:{adventure}",
        )
        assert len(result) == EXPECTED_PAGE_COUNT
        assert all(
            "page_num" in p and "text" in p and "image_prompt" in p
            for p in result
        )

    def test_adapter_receives_built_prompt(self):
        """The adapter should see the fully-substituted prompt, not the raw template."""
        class SpyAdapter:
            def __init__(self):
                self.received = None
            def generate(self, prompt):
                self.received = prompt
                return MockLLMAdapter().generate("")

        adapter = SpyAdapter()
        generate_story(
            VALID_SELECTIONS,
            adapter=adapter,
            template_loader=lambda: "N:{name} A:{age} H:{hero} T:{theme} C:{adventure}",
        )
        assert adapter.received == (
            "N:Maya A:9 H:girl T:under the sea C:talking animal"
        )

    def test_bad_adapter_output_propagates_as_valueerror(self):
        adapter = MockLLMAdapter(canned="not json at all")
        with pytest.raises(ValueError, match="not valid JSON"):
            generate_story(
                VALID_SELECTIONS,
                adapter=adapter,
                template_loader=lambda: "N:{name} A:{age} H:{hero} T:{theme} C:{adventure}",
            )