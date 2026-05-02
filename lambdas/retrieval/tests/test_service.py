"""Unit tests for service.get_story and _validate_story_id.

These tests use moto (via the aws_mocks fixture in conftest.py) to
exercise real boto3 code paths against a fake AWS — no mocking of
boto3 method calls, no assertions about which boto3 methods were
invoked. We test behavior, not implementation.
"""

import uuid

import pytest

from service import StoryNotFound, _validate_story_id, get_story, list_stories_for_parent


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

class TestListStoriesForParent:
    """Tests for list_stories_for_parent — the /my-stories backend."""

    PARENT_ID = "cognito-sub-parent-a"
    OTHER_PARENT_ID = "cognito-sub-parent-b"

    def _put_story(self, table, *, story_id, parent_id, status="COMPLETE",
                   created_at="2026-04-30T10:00:00+00:00", kid_id=None,
                   pdf_s3_key=None):
        """Helper to put a fully-formed story row into the table."""
        item = {
            "story_id": story_id,
            "parent_id": parent_id,
            "status": status,
            "created_at": created_at,
            "name": "Maya",
            "hero": "girl",
            "theme": "space",
            "adventure": "talking_animal",
            "age": "9",
        }
        if kid_id:
            item["kid_id"] = kid_id
        if pdf_s3_key:
            item["pdf_s3_key"] = pdf_s3_key
        table.put_item(Item=item)

    def test_empty_for_parent_with_no_stories(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        assert result == []

    def test_returns_only_this_parents_stories(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        self._put_story(table, story_id="story-a", parent_id=self.PARENT_ID,
                        pdf_s3_key="stories/story-a/final.pdf")
        self._put_story(table, story_id="story-b",
                        parent_id=self.OTHER_PARENT_ID,
                        pdf_s3_key="stories/story-b/final.pdf")

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        assert len(result) == 1
        assert result[0]["story_id"] == "story-a"

    def test_sorted_newest_first(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        self._put_story(table, story_id="oldest", parent_id=self.PARENT_ID,
                        created_at="2026-01-01T10:00:00+00:00",
                        pdf_s3_key="stories/oldest/final.pdf")
        self._put_story(table, story_id="newest", parent_id=self.PARENT_ID,
                        created_at="2026-04-01T10:00:00+00:00",
                        pdf_s3_key="stories/newest/final.pdf")
        self._put_story(table, story_id="middle", parent_id=self.PARENT_ID,
                        created_at="2026-02-01T10:00:00+00:00",
                        pdf_s3_key="stories/middle/final.pdf")

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        assert [s["story_id"] for s in result] == ["newest", "middle", "oldest"]

    def test_complete_story_has_download_url(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        self._put_story(table, story_id="story-a", parent_id=self.PARENT_ID,
                        status="COMPLETE",
                        pdf_s3_key="stories/story-a/final.pdf")

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        assert "download_url" in result[0]
        assert "expires_in" in result[0]

    def test_processing_story_has_no_download_url(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        self._put_story(table, story_id="story-a", parent_id=self.PARENT_ID,
                        status="PROCESSING")

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        assert result[0]["status"] == "PROCESSING"
        assert "download_url" not in result[0]

    def test_failed_story_includes_error_when_present(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        item = {
            "story_id": "story-a",
            "parent_id": self.PARENT_ID,
            "status": "FAILED",
            "created_at": "2026-04-30T10:00:00+00:00",
            "name": "Maya", "hero": "girl", "theme": "space",
            "adventure": "talking_animal", "age": "9",
            "error": "image generation timed out",
        }
        table.put_item(Item=item)

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        assert result[0]["status"] == "FAILED"
        assert result[0]["error"] == "image generation timed out"

    def test_kid_id_filter_returns_only_matching_kid(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        self._put_story(table, story_id="for-kid-a", parent_id=self.PARENT_ID,
                        kid_id="kid-a", pdf_s3_key="stories/for-kid-a/final.pdf")
        self._put_story(table, story_id="for-kid-b", parent_id=self.PARENT_ID,
                        kid_id="kid-b", pdf_s3_key="stories/for-kid-b/final.pdf")
        self._put_story(table, story_id="no-kid", parent_id=self.PARENT_ID,
                        pdf_s3_key="stories/no-kid/final.pdf")

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
            kid_id="kid-a",
        )
        assert len(result) == 1
        assert result[0]["story_id"] == "for-kid-a"

    def test_kid_id_filter_excludes_other_parents_kids(self, aws_mocks):
        """Defense: kid_id from another family must not leak across.

        The kid_id-index is global, so we must filter results by parent_id.
        """
        table, s3, bucket_name = aws_mocks
        # Other parent has a kid with this kid_id (unlikely with UUIDs,
        # but plausible if an attacker crafts the value).
        self._put_story(table, story_id="other-family-story",
                        parent_id=self.OTHER_PARENT_ID,
                        kid_id="kid-shared",
                        pdf_s3_key="stories/other/final.pdf")
        self._put_story(table, story_id="my-story",
                        parent_id=self.PARENT_ID,
                        kid_id="kid-shared",
                        pdf_s3_key="stories/mine/final.pdf")

        # I query for kid-shared, but I'm parent A.
        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
            kid_id="kid-shared",
        )
        assert len(result) == 1
        assert result[0]["story_id"] == "my-story"

    def test_payload_includes_card_selections(self, aws_mocks):
        table, s3, bucket_name = aws_mocks
        self._put_story(table, story_id="story-a", parent_id=self.PARENT_ID,
                        pdf_s3_key="stories/story-a/final.pdf")

        result = list_stories_for_parent(
            parent_id=self.PARENT_ID,
            table=table, s3_client=s3, bucket_name="test-pdfs",
        )
        s = result[0]
        assert s["name"] == "Maya"
        assert s["hero"] == "girl"
        assert s["theme"] == "space"
        assert s["adventure"] == "talking_animal"
        assert s["age"] == "9"