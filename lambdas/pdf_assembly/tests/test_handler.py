"""Unit tests for pdf_assembly Lambda handler.

Tests never hit S3 or DDB. The autouse fixture monkeypatches all
three _get_* callables to spies that capture what would have happened.
"""

import pytest

import handler


# Minimal 1x1 transparent PNG — same bytes used in test_service.py.
# Real-enough PNG for ReportLab to parse when assemble_pdf composes
# the PDF during these tests.
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

SAMPLE_EVENT = {
    "story_id": "01234567-89ab-4def-89ab-0123456789ab",
    "hero": "girl",
    "theme": "space",
    "challenge": "asteroid",
    "strength": "super_smart",
    "pages": [
        {"page_num": i, "text": f"Page {i} text"} for i in range(1, 6)
    ],
    "image_s3_keys": [
        f"stories/01234567-89ab-4def-89ab-0123456789ab/page_{i}.png"
        for i in range(1, 6)
    ],
}


@pytest.fixture(autouse=True)
def stub_aws(monkeypatch):
    """Swap real S3 + DDB callables for test spies.

    autouse so every test is isolated from AWS. Stashes spy call lists
    on the handler module so tests can inspect them.
    """
    monkeypatch.setattr(handler, "_S3_CLIENT", None)
    monkeypatch.setattr(handler, "_DDB_TABLE", None)
    monkeypatch.setattr(handler, "_BUCKET", None)

    download_calls = []

    def downloader(key):
        download_calls.append(key)
        return TINY_PNG

    upload_calls = []

    def uploader(key, body, content_type):
        upload_calls.append(
            {"key": key, "body": body, "content_type": content_type}
        )

    ddb_calls = []

    def updater(story_id, pdf_s3_key):
        ddb_calls.append({"story_id": story_id, "pdf_s3_key": pdf_s3_key})

    monkeypatch.setattr(handler, "_get_s3_downloader", lambda: downloader)
    monkeypatch.setattr(handler, "_get_s3_uploader", lambda: uploader)
    monkeypatch.setattr(handler, "_get_ddb_updater", lambda: updater)

    handler._test_download_calls = download_calls
    handler._test_upload_calls = upload_calls
    handler._test_ddb_calls = ddb_calls


class TestLambdaHandler:
    def test_returns_event_plus_pdf_key_and_status(self):
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        sid = SAMPLE_EVENT["story_id"]
        assert result["story_id"] == sid
        assert result["pdf_s3_key"] == f"stories/{sid}/final.pdf"
        assert result["status"] == "COMPLETE"

    def test_all_input_fields_preserved(self):
        """Even though this is the last Lambda, preserving input is
        good discipline — debugging in CloudWatch is easier when every
        Lambda's return shows the whole story context."""
        result = handler.lambda_handler(SAMPLE_EVENT, context=None)
        for key in (
            "story_id", "hero", "theme", "challenge",
            "strength", "pages", "image_s3_keys",
        ):
            assert result[key] == SAMPLE_EVENT[key]

    def test_all_images_downloaded(self):
        handler.lambda_handler(SAMPLE_EVENT, context=None)
        assert len(handler._test_download_calls) == 5
        assert set(handler._test_download_calls) == set(
            SAMPLE_EVENT["image_s3_keys"]
        )

    def test_pdf_uploaded_with_correct_metadata(self):
        handler.lambda_handler(SAMPLE_EVENT, context=None)
        sid = SAMPLE_EVENT["story_id"]
        assert len(handler._test_upload_calls) == 1
        call = handler._test_upload_calls[0]
        assert call["key"] == f"stories/{sid}/final.pdf"
        assert call["content_type"] == "application/pdf"
        assert call["body"][:4] == b"%PDF"

    def test_ddb_updated_with_complete_and_pdf_key(self):
        handler.lambda_handler(SAMPLE_EVENT, context=None)
        sid = SAMPLE_EVENT["story_id"]
        assert handler._test_ddb_calls == [
            {"story_id": sid, "pdf_s3_key": f"stories/{sid}/final.pdf"}
        ]

    def test_missing_required_field_raises(self):
        bad_event = {k: v for k, v in SAMPLE_EVENT.items() if k != "story_id"}
        with pytest.raises(KeyError):
            handler.lambda_handler(bad_event, context=None)

    def test_extra_event_fields_preserved(self):
        """Future metadata fields (trace IDs, retry counts) must pass through."""
        event_with_extras = {**SAMPLE_EVENT, "trace_id": "trace-abc"}
        result = handler.lambda_handler(event_with_extras, context=None)
        assert result["trace_id"] == "trace-abc"