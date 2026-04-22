"""Unit tests for service.get_story and _validate_story_id.

These tests use moto (via the aws_mocks fixture in conftest.py) to
exercise real boto3 code paths against a fake AWS — no mocking of
boto3 method calls, no assertions about which boto3 methods were
invoked. We test behavior, not implementation.
"""

import uuid

import pytest

from service import StoryNotFound, _validate_story_id, get_story


# A fixed, known-valid UUID. Using a constant (not uuid.uuid4()) keeps
# failures reproducible — if a test fails, the story_id in the error
# message is the same every time.
STORY_ID = str(uuid.UUID("01234567-89ab-4def-89ab-0123456789ab"))


class TestValidateStoryId:
    """Exercise _validate_story_id directly to lock in its contract."""

    def test_valid_uuid_accepted(self):
        # Should not raise
        _validate_story_id(STORY_ID)

    @pytest.mark.parametrize(
        "bad_id",
        ["", "not-a-uuid", "123", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
         None, 42],
    )
    def test_invalid_rejected(self, bad_id):
        with pytest.raises(ValueError):
            _validate_story_id(bad_id)


class TestGetStoryProcessing:
    def test_processing_returns_status_only(self, aws_mocks):
        table, s3, bucket = aws_mocks
        table.put_item(Item={
            "story_id": STORY_ID,
            "status": "PROCESSING",
            "created_at": "2026-04-22T10:00:00+00:00",
        })

        result = get_story(STORY_ID, table, s3, bucket)

        assert result == {
            "story_id": STORY_ID,
            "status": "PROCESSING",
            "created_at": "2026-04-22T10:00:00+00:00",
        }


class TestGetStoryComplete:
    def test_complete_returns_presigned_url(self, aws_mocks):
        table, s3, bucket = aws_mocks
        # Put a real (small) object so the pre-signed URL points to
        # something that actually exists in the mocked bucket.
        s3.put_object(
            Bucket=bucket, Key="stories/test.pdf", Body=b"fake pdf bytes"
        )
        table.put_item(Item={
            "story_id": STORY_ID,
            "status": "COMPLETE",
            "created_at": "2026-04-22T10:00:00+00:00",
            "pdf_s3_key": "stories/test.pdf",
        })

        result = get_story(STORY_ID, table, s3, bucket)

        assert result["status"] == "COMPLETE"
        assert result["story_id"] == STORY_ID
        assert result["expires_in"] == 15 * 60
        # URL shape: includes the key and a SigV4 signature
        assert "stories/test.pdf" in result["download_url"]
        assert "Signature" in result["download_url"]

    def test_complete_respects_custom_ttl(self, aws_mocks):
        table, s3, bucket = aws_mocks
        s3.put_object(Bucket=bucket, Key="k.pdf", Body=b"x")
        table.put_item(Item={
            "story_id": STORY_ID,
            "status": "COMPLETE",
            "pdf_s3_key": "k.pdf",
        })

        result = get_story(
            STORY_ID, table, s3, bucket, url_ttl_seconds=60
        )

        assert result["expires_in"] == 60

    def test_complete_without_pdf_key_raises_runtime(self, aws_mocks):
        table, s3, bucket = aws_mocks
        table.put_item(Item={
            "story_id": STORY_ID,
            "status": "COMPLETE",
            # pdf_s3_key deliberately missing — simulates upstream bug
        })

        with pytest.raises(RuntimeError, match="pdf_s3_key"):
            get_story(STORY_ID, table, s3, bucket)


class TestGetStoryFailed:
    def test_failed_surfaces_error_field(self, aws_mocks):
        table, s3, bucket = aws_mocks
        table.put_item(Item={
            "story_id": STORY_ID,
            "status": "FAILED",
            "error": "LLM endpoint timed out",
        })

        result = get_story(STORY_ID, table, s3, bucket)

        assert result["status"] == "FAILED"
        assert result["error"] == "LLM endpoint timed out"

    def test_failed_without_error_field_is_fine(self, aws_mocks):
        table, s3, bucket = aws_mocks
        table.put_item(Item={
            "story_id": STORY_ID,
            "status": "FAILED",
        })

        result = get_story(STORY_ID, table, s3, bucket)

        assert result["status"] == "FAILED"
        assert "error" not in result


class TestGetStoryErrors:
    def test_not_found_raises_story_not_found(self, aws_mocks):
        table, s3, bucket = aws_mocks
        # Table is empty

        with pytest.raises(StoryNotFound):
            get_story(STORY_ID, table, s3, bucket)

    def test_invalid_story_id_raises_value_error(self, aws_mocks):
        table, s3, bucket = aws_mocks

        with pytest.raises(ValueError, match="Invalid story_id"):
            get_story("not-a-uuid", table, s3, bucket)