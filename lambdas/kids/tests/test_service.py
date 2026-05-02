"""Unit tests for kids service business logic."""

from datetime import datetime, timezone

import pytest

from service import (
    BIRTH_YEAR_MAX,
    BIRTH_YEAR_MIN,
    NAME_MAX_LENGTH,
    create_kid,
    delete_kid,
    list_kids,
)


PARENT_ID = "cognito-sub-abc123"
FIXED_ID = "kid-uuid-001"
FIXED_NOW = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)


def _fixed_now():
    return FIXED_NOW


def _fixed_id():
    return FIXED_ID


VALID_KID = {
    "name": "Maya",
    "birth_year": 2018,
    "avatar_card_id": "girl_brown_hair",
}


class TestCreateKid:
    def test_happy_path_returns_kid_dict(self, kids_table):
        result = create_kid(
            parent_id=PARENT_ID, body=VALID_KID, table=kids_table,
            now_fn=_fixed_now, id_fn=_fixed_id,
        )
        assert result["parent_id"] == PARENT_ID
        assert result["kid_id"] == FIXED_ID
        assert result["name"] == "Maya"
        assert result["birth_year"] == 2018
        assert result["avatar_card_id"] == "girl_brown_hair"
        assert result["created_at"] == FIXED_NOW.isoformat()

    def test_kid_is_persisted_to_ddb(self, kids_table):
        create_kid(
            parent_id=PARENT_ID, body=VALID_KID, table=kids_table,
            now_fn=_fixed_now, id_fn=_fixed_id,
        )
        item = kids_table.get_item(
            Key={"parent_id": PARENT_ID, "kid_id": FIXED_ID}
        )["Item"]
        assert item["name"] == "Maya"

    def test_name_whitespace_is_stripped(self, kids_table):
        body = {**VALID_KID, "name": "  Maya  "}
        result = create_kid(
            parent_id=PARENT_ID, body=body, table=kids_table,
            now_fn=_fixed_now, id_fn=_fixed_id,
        )
        assert result["name"] == "Maya"

    def test_non_dict_body_raises(self, kids_table):
        with pytest.raises(ValueError, match="JSON object"):
            create_kid(
                parent_id=PARENT_ID, body="not a dict", table=kids_table,
            )

    def test_missing_name_raises(self, kids_table):
        body = {k: v for k, v in VALID_KID.items() if k != "name"}
        with pytest.raises(ValueError, match="name must be a string"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )

    def test_empty_name_raises(self, kids_table):
        body = {**VALID_KID, "name": "   "}
        with pytest.raises(ValueError, match=f"1-{NAME_MAX_LENGTH}"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )

    def test_too_long_name_raises(self, kids_table):
        body = {**VALID_KID, "name": "x" * (NAME_MAX_LENGTH + 1)}
        with pytest.raises(ValueError, match=f"1-{NAME_MAX_LENGTH}"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )

    def test_birth_year_too_old_raises(self, kids_table):
        body = {**VALID_KID, "birth_year": BIRTH_YEAR_MIN - 1}
        with pytest.raises(ValueError, match="birth_year"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )

    def test_birth_year_in_future_raises(self, kids_table):
        body = {**VALID_KID, "birth_year": BIRTH_YEAR_MAX + 1}
        with pytest.raises(ValueError, match="birth_year"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )

    def test_birth_year_non_integer_raises(self, kids_table):
        body = {**VALID_KID, "birth_year": "2018"}  # string, not int
        with pytest.raises(ValueError, match="birth_year must be an integer"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )

    def test_missing_avatar_card_id_raises(self, kids_table):
        body = {k: v for k, v in VALID_KID.items() if k != "avatar_card_id"}
        with pytest.raises(ValueError, match="avatar_card_id"):
            create_kid(
                parent_id=PARENT_ID, body=body, table=kids_table,
            )


class TestListKids:
    def test_empty_for_parent_with_no_kids(self, kids_table):
        result = list_kids(parent_id=PARENT_ID, table=kids_table)
        assert result == []

    def test_returns_only_this_parents_kids(self, kids_table):
        # Two parents, one kid each.
        create_kid(
            parent_id="parent-a", body=VALID_KID, table=kids_table,
            now_fn=_fixed_now, id_fn=lambda: "kid-a",
        )
        create_kid(
            parent_id="parent-b", body=VALID_KID, table=kids_table,
            now_fn=_fixed_now, id_fn=lambda: "kid-b",
        )

        result = list_kids(parent_id="parent-a", table=kids_table)
        assert len(result) == 1
        assert result[0]["kid_id"] == "kid-a"

    def test_sorted_newest_first(self, kids_table):
        # Three kids created at different times.
        for i, ts in enumerate(["2026-01-01", "2026-03-01", "2026-02-01"]):
            create_kid(
                parent_id=PARENT_ID,
                body={**VALID_KID, "name": f"Kid{i}"},
                table=kids_table,
                now_fn=lambda ts=ts: datetime.fromisoformat(ts).replace(
                    tzinfo=timezone.utc
                ),
                id_fn=lambda i=i: f"kid-{i}",
            )

        result = list_kids(parent_id=PARENT_ID, table=kids_table)
        # Order: March (newest) → February → January
        assert [k["name"] for k in result] == ["Kid1", "Kid2", "Kid0"]


class TestDeleteKid:
    def test_deletes_existing_kid(self, kids_table):
        create_kid(
            parent_id=PARENT_ID, body=VALID_KID, table=kids_table,
            now_fn=_fixed_now, id_fn=_fixed_id,
        )

        delete_kid(parent_id=PARENT_ID, kid_id=FIXED_ID, table=kids_table)

        # Confirm it's gone.
        result = kids_table.get_item(
            Key={"parent_id": PARENT_ID, "kid_id": FIXED_ID}
        )
        assert "Item" not in result

    def test_nonexistent_kid_raises(self, kids_table):
        with pytest.raises(ValueError, match="not found"):
            delete_kid(
                parent_id=PARENT_ID, kid_id="does-not-exist", table=kids_table,
            )

    def test_other_parents_kid_cannot_be_deleted(self, kids_table):
        """A parent shouldn't be able to delete another parent's kid."""
        create_kid(
            parent_id="parent-a", body=VALID_KID, table=kids_table,
            now_fn=_fixed_now, id_fn=_fixed_id,
        )

        # Parent B tries to delete parent A's kid.
        with pytest.raises(ValueError, match="not found"):
            delete_kid(
                parent_id="parent-b", kid_id=FIXED_ID, table=kids_table,
            )

        # Parent A's kid should still exist.
        item = kids_table.get_item(
            Key={"parent_id": "parent-a", "kid_id": FIXED_ID}
        )["Item"]
        assert item["name"] == "Maya"

    def test_empty_kid_id_raises(self, kids_table):
        with pytest.raises(ValueError, match="kid_id"):
            delete_kid(
                parent_id=PARENT_ID, kid_id="", table=kids_table,
            )