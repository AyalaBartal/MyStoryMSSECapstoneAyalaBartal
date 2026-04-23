"""Unit tests for pdf_assembly service.py."""

import pytest

import service
from service import (
    EXPECTED_PAGE_COUNT,
    _build_pdf_bytes,
    _page_num_from_key,
    _s3_key_for_pdf,
    assemble_pdf,
)


# Minimal 1x1 transparent PNG (67 bytes) — valid enough for ReportLab's
# ImageReader to parse. Embedding raw bytes avoids needing Pillow as
# a test-only dependency.
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


SAMPLE_PAGES = [
    {"page_num": 1, "text": "Maya lived in a coral city."},
    {"page_num": 2, "text": "A dragon appeared at dawn."},
    {"page_num": 3, "text": "She tried to speak to it."},
    {"page_num": 4, "text": "She thought of a clever plan."},
    {"page_num": 5, "text": "And they became friends."},
]

SAMPLE_IMAGE_KEYS = [
    f"stories/story-123/page_{i}.png" for i in range(1, 6)
]

SAMPLE_LAYOUT = {
    "page_size": "letter",
    "margin_pt": 54,
    "image": {"width_pt": 300, "height_pt": 300, "top_padding_pt": 50},
    "text": {
        "font_name": "Helvetica",
        "font_size_pt": 14,
        "leading_pt": 20,
        "top_padding_pt": 30,
    },
}


class TestS3KeyForPdf:
    def test_key_format(self):
        assert _s3_key_for_pdf("abc-123") == "stories/abc-123/final.pdf"

    def test_deterministic(self):
        assert _s3_key_for_pdf("abc") == _s3_key_for_pdf("abc")


class TestPageNumFromKey:
    def test_extracts_page_number(self):
        assert _page_num_from_key("stories/abc/page_3.png") == 3

    def test_handles_double_digits(self):
        assert _page_num_from_key("stories/abc/page_10.png") == 10

    def test_raises_on_unparseable_key(self):
        with pytest.raises(ValueError, match="Can't parse"):
            _page_num_from_key("stories/abc/final.pdf")


class TestBuildPdfBytes:
    def test_returns_valid_pdf_header(self):
        images = {i: TINY_PNG for i in range(1, 6)}
        result = _build_pdf_bytes(SAMPLE_PAGES, images, SAMPLE_LAYOUT)
        assert result[:4] == b"%PDF"

    def test_pdf_has_nonzero_size(self):
        images = {i: TINY_PNG for i in range(1, 6)}
        result = _build_pdf_bytes(SAMPLE_PAGES, images, SAMPLE_LAYOUT)
        assert len(result) > 1000  # real 5-page PDFs are a few KB


class TestAssemblePdf:
    def _make_spy_downloader(self):
        calls = []

        def downloader(key):
            calls.append(key)
            return TINY_PNG

        return downloader, calls

    def _make_spy_uploader(self):
        calls = []

        def uploader(key, body, content_type):
            calls.append(
                {"key": key, "body": body, "content_type": content_type}
            )

        return uploader, calls

    def _make_spy_ddb(self):
        calls = []

        def updater(story_id, pdf_s3_key):
            calls.append({"story_id": story_id, "pdf_s3_key": pdf_s3_key})

        return updater, calls

    def _common_call(self, **overrides):
        """Build all spies, run assemble_pdf with defaults, return spies + result."""
        downloader, dl_calls = self._make_spy_downloader()
        uploader, ul_calls = self._make_spy_uploader()
        ddb, ddb_calls = self._make_spy_ddb()

        kwargs = {
            "story_id": "story-123",
            "pages": SAMPLE_PAGES,
            "image_s3_keys": SAMPLE_IMAGE_KEYS,
            "s3_downloader": downloader,
            "s3_uploader": uploader,
            "ddb_updater": ddb,
            "layout_loader": lambda: SAMPLE_LAYOUT,
        }
        kwargs.update(overrides)

        result = assemble_pdf(**kwargs)
        return result, dl_calls, ul_calls, ddb_calls

    def test_returns_pdf_s3_key(self):
        result, _, _, _ = self._common_call()
        assert result == "stories/story-123/final.pdf"

    def test_downloads_all_images(self):
        _, dl_calls, _, _ = self._common_call()
        assert set(dl_calls) == set(SAMPLE_IMAGE_KEYS)

    def test_uploads_pdf_with_correct_content_type(self):
        _, _, ul_calls, _ = self._common_call()
        assert len(ul_calls) == 1
        assert ul_calls[0]["key"] == "stories/story-123/final.pdf"
        assert ul_calls[0]["content_type"] == "application/pdf"
        assert ul_calls[0]["body"][:4] == b"%PDF"

    def test_ddb_updated_with_story_id_and_pdf_key(self):
        _, _, _, ddb_calls = self._common_call()
        assert ddb_calls == [{
            "story_id": "story-123",
            "pdf_s3_key": "stories/story-123/final.pdf",
        }]

    def test_shuffled_pages_are_sorted_before_pdf_build(self, monkeypatch):
        """assemble_pdf must sort pages by page_num before PDF composition.

        Spies on _build_pdf_bytes to capture the sorted_pages argument it
        receives, so we can assert sort behavior without parsing the
        (compressed) PDF bytes.
        """
        captured_page_nums = []

        def spy_build_pdf(sorted_pages, images_by_page_num, layout):
            captured_page_nums.extend(p["page_num"] for p in sorted_pages)
            return b"%PDF-stub"

        monkeypatch.setattr(service, "_build_pdf_bytes", spy_build_pdf)

        shuffled = [
            SAMPLE_PAGES[4], SAMPLE_PAGES[2], SAMPLE_PAGES[0],
            SAMPLE_PAGES[3], SAMPLE_PAGES[1],
        ]

        self._common_call(pages=shuffled)

        assert captured_page_nums == [1, 2, 3, 4, 5]

    def test_wrong_page_count_raises(self):
        with pytest.raises(ValueError, match="Expected 5 pages, got 3"):
            self._common_call(pages=SAMPLE_PAGES[:3])

    def test_wrong_image_count_raises(self):
        with pytest.raises(ValueError, match="Expected 5 image keys"):
            self._common_call(image_s3_keys=SAMPLE_IMAGE_KEYS[:3])

    def test_download_failure_propagates(self):
        def failing_downloader(key):
            raise RuntimeError("S3 read failed")

        with pytest.raises(RuntimeError, match="S3 read failed"):
            self._common_call(s3_downloader=failing_downloader)

    def test_upload_failure_propagates(self):
        def failing_uploader(**kwargs):
            raise RuntimeError("S3 write failed")

        with pytest.raises(RuntimeError, match="S3 write failed"):
            self._common_call(s3_uploader=failing_uploader)

    def test_ddb_failure_propagates(self):
        def failing_ddb(story_id, pdf_s3_key):
            raise RuntimeError("DDB update failed")

        with pytest.raises(RuntimeError, match="DDB update failed"):
            self._common_call(ddb_updater=failing_ddb)