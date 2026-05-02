"""Unit tests for claim_stories service."""

import pytest

from service import MAX_CLAIMS_PER_REQUEST, claim_stories


PARENT_ID = "cognito-sub-parent-a"
OTHER_PARENT_ID = "cognito-sub-parent-b"


def _put_anonymous_story(table, story_id, claim_token, **extra):
    """Helper: write an anonymous story row (has claim_token, no parent_id)."""
    item = {
        "story_id": story_id,
        "claim_token": claim_token,
        "status": "COMPLETE",
        "created_at": "2026-04-30T10:00:00+00:00",
        **extra,
    }
    table.put_item(Item=item)


def _put_owned_story(table, story_id, parent_id, **extra):
    """Helper: write a story already owned by a parent."""
    item = {
        "story_id": story_id,
        "parent_id": parent_id,
        "status": "COMPLETE",
        "created_at": "2026-04-30T10:00:00+00:00",
        **extra,
    }
    table.put_item(Item=item)


class TestClaimStoriesValidation:
    """Input validation — bad payloads raise ValueError."""

    def test_non_list_raises(self, stories_table):
        with pytest.raises(ValueError, match="claims must be a list"):
            claim_stories(
                parent_id=PARENT_ID, claims="not a list", table=stories_table,
            )

    def test_empty_list_raises(self, stories_table):
        with pytest.raises(ValueError, match="cannot be empty"):
            claim_stories(parent_id=PARENT_ID, claims=[], table=stories_table)

    def test_too_many_raises(self, stories_table):
        too_many = [
            {"story_id": f"s-{i}", "claim_token": f"t-{i}"}
            for i in range(MAX_CLAIMS_PER_REQUEST + 1)
        ]
        with pytest.raises(ValueError, match="cannot exceed"):
            claim_stories(
                parent_id=PARENT_ID, claims=too_many, table=stories_table,
            )

    def test_non_dict_item_raises(self, stories_table):
        with pytest.raises(ValueError, match="must be an object"):
            claim_stories(
                parent_id=PARENT_ID,
                claims=["not-an-object"],
                table=stories_table,
            )

    def test_missing_story_id_raises(self, stories_table):
        with pytest.raises(ValueError, match="story_id"):
            claim_stories(
                parent_id=PARENT_ID,
                claims=[{"claim_token": "t1"}],
                table=stories_table,
            )

    def test_missing_claim_token_raises(self, stories_table):
        with pytest.raises(ValueError, match="claim_token"):
            claim_stories(
                parent_id=PARENT_ID,
                claims=[{"story_id": "s1"}],
                table=stories_table,
            )

    def test_empty_string_fields_raise(self, stories_table):
        with pytest.raises(ValueError, match="story_id"):
            claim_stories(
                parent_id=PARENT_ID,
                claims=[{"story_id": "  ", "claim_token": "t"}],
                table=stories_table,
            )

    def test_invalid_kid_id_raises(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "t1")
        with pytest.raises(ValueError, match="kid_id"):
            claim_stories(
                parent_id=PARENT_ID,
                claims=[{"story_id": "s1", "claim_token": "t1"}],
                table=stories_table,
                kid_id="",
            )


class TestClaimStoriesHappyPath:
    """Successful claim flows — anonymous → owned."""

    def test_single_claim_attaches_parent_id(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "t1")

        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
        )

        assert result == {"claimed": 1, "already": 0, "skipped": 0}

        # Row now has parent_id set, claim_token gone.
        item = stories_table.get_item(Key={"story_id": "s1"})["Item"]
        assert item["parent_id"] == PARENT_ID
        assert "claim_token" not in item

    def test_multiple_claims_in_one_call(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "t1")
        _put_anonymous_story(stories_table, "s2", "t2")
        _put_anonymous_story(stories_table, "s3", "t3")

        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[
                {"story_id": "s1", "claim_token": "t1"},
                {"story_id": "s2", "claim_token": "t2"},
                {"story_id": "s3", "claim_token": "t3"},
            ],
            table=stories_table,
        )

        assert result == {"claimed": 3, "already": 0, "skipped": 0}

    def test_kid_id_is_attached_when_provided(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "t1")

        claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
            kid_id="kid-uuid-abc",
        )

        item = stories_table.get_item(Key={"story_id": "s1"})["Item"]
        assert item["kid_id"] == "kid-uuid-abc"

    def test_claim_without_kid_id_leaves_kid_id_unset(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "t1")

        claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
        )

        item = stories_table.get_item(Key={"story_id": "s1"})["Item"]
        assert "kid_id" not in item


class TestClaimStoriesIdempotency:
    """Repeated claims — same parent retrying is a no-op success."""

    def test_already_claimed_by_same_parent_returns_already(self, stories_table):
        # Pre-claimed by this parent (no claim_token).
        _put_owned_story(stories_table, "s1", PARENT_ID)

        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
        )

        assert result == {"claimed": 0, "already": 1, "skipped": 0}

    def test_repeated_claim_in_two_calls_is_safe(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "t1")

        first = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
        )
        second = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
        )

        assert first == {"claimed": 1, "already": 0, "skipped": 0}
        assert second == {"claimed": 0, "already": 1, "skipped": 0}


class TestClaimStoriesSecurityBoundaries:
    """A parent cannot claim someone else's story."""

    def test_already_claimed_by_other_parent_returns_skipped(self, stories_table):
        _put_owned_story(stories_table, "s1", OTHER_PARENT_ID)

        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "t1"}],
            table=stories_table,
        )

        assert result == {"claimed": 0, "already": 0, "skipped": 1}

        # And the row is unchanged — still owned by the other parent.
        item = stories_table.get_item(Key={"story_id": "s1"})["Item"]
        assert item["parent_id"] == OTHER_PARENT_ID

    def test_wrong_token_for_anonymous_story_returns_skipped(self, stories_table):
        _put_anonymous_story(stories_table, "s1", "real-token")

        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "s1", "claim_token": "wrong-token"}],
            table=stories_table,
        )

        assert result == {"claimed": 0, "already": 0, "skipped": 1}

        # Row unchanged — token still there, no parent_id.
        item = stories_table.get_item(Key={"story_id": "s1"})["Item"]
        assert item["claim_token"] == "real-token"
        assert "parent_id" not in item

    def test_nonexistent_story_returns_skipped(self, stories_table):
        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[{"story_id": "does-not-exist", "claim_token": "t1"}],
            table=stories_table,
        )

        assert result == {"claimed": 0, "already": 0, "skipped": 1}


class TestClaimStoriesMixedOutcomes:
    """A single call can have a mix of claimed/already/skipped."""

    def test_mixed_batch_counts_correctly(self, stories_table):
        _put_anonymous_story(stories_table, "fresh", "t-fresh")
        _put_owned_story(stories_table, "mine", PARENT_ID)
        _put_owned_story(stories_table, "theirs", OTHER_PARENT_ID)

        result = claim_stories(
            parent_id=PARENT_ID,
            claims=[
                {"story_id": "fresh", "claim_token": "t-fresh"},
                {"story_id": "mine", "claim_token": "t-mine"},
                {"story_id": "theirs", "claim_token": "t-theirs"},
                {"story_id": "missing", "claim_token": "t-missing"},
            ],
            table=stories_table,
        )

        assert result == {"claimed": 1, "already": 1, "skipped": 2}