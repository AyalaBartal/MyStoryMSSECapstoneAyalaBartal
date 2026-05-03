# kids Lambda

Manages kid profiles for authenticated parents. A parent can create kid
profiles, list their family's kids, and delete a kid profile.

All routes require a valid Cognito JWT in the Authorization header
(`Authorization: Bearer <jwt>`).

## HTTP contract

### POST /kids — create a kid profile

**Request body (JSON):**
```json
{
  "name": "Maya",
  "birth_year": 2018,
  "avatar_card_id": "girl_brown_hair",
  "hero": "girl"
}
```

`hero` must be `"boy"` or `"girl"`. It's used as the default hero card when generating a story for this kid (still editable per-story so the same kid can star in a "boy" or "girl" hero story).

**Responses:**

| Status | Shape | When |
|---|---|---|
| 201 | `{ parent_id, kid_id, name, birth_year, avatar_card_id, hero, created_at }` | Created |
| 400 | `{ error }` | Missing/invalid field |
| 401 | `{ error }` | Missing or invalid JWT |
| 500 | `{ error }` | Unexpected failure |

Validation:
- `name` — 1–30 characters after whitespace stripped
- `birth_year` — integer between 2010 and the current year
- `avatar_card_id` — non-empty string
- `hero` — must be `"boy"` or `"girl"`

### GET /kids — list this parent's kids

**Responses:**

| Status | Shape | When |
|---|---|---|
| 200 | `{ kids: [{...}, ...] }` | Success — list sorted newest-first |
| 401 | `{ error }` | Missing or invalid JWT |

Empty list if the parent has no kids. Older kids (created before the `hero` field was added) may have undefined `hero` — frontend should default gracefully.

### DELETE /kids/{kid_id} — delete a kid profile

**Responses:**

| Status | Shape | When |
|---|---|---|
| 204 | (empty body) | Deleted |
| 400 | `{ error }` | Missing kid_id in path, or kid doesn't exist |
| 401 | `{ error }` | Missing or invalid JWT |

Stories tagged with this kid_id are NOT deleted — they keep their kid_id. The frontend's library page handles the case where a story's kid_id no longer matches a profile.

## Environment variables

| Name | Required | Purpose |
|---|---|---|
| `KIDS_TABLE` | yes | DynamoDB table name (PK=parent_id, SK=kid_id) |
| `COGNITO_USER_POOL_ID` | yes | For JWT verification |
| `COGNITO_APP_CLIENT_ID` | yes | For JWT verification |
| `LOG_LEVEL` | no | DEBUG/INFO/WARNING/ERROR (default INFO) |

## IAM permissions

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:Query`, `PutItem`, `DeleteItem`, `GetItem` on the kids table (granted via `grant_read_write_data` for simplicity)

## File layout

```
kids/
├── handler.py         # AWS entry point — routes by HTTP method (POST/GET/DELETE)
├── service.py         # create_kid / list_kids / delete_kid with field validation
├── auth.py            # Cognito JWT verification (copy from entry/)
├── utils.py           # CORS + Decimal-safe JSON encoder (copy from entry/)
├── requirements.txt   # boto3 + python-jose[cryptography]
├── README.md
└── tests/
    ├── conftest.py
    ├── test_handler.py
    └── test_service.py
```

## Running the tests

From the repo root:

```bash
pytest lambdas/kids/tests/ -v
```

31 tests covering field validation (name length, birth year range, hero whitelist), the create/list/delete happy paths, and security boundaries (a parent cannot list or delete another parent's kids).

## Notes

**`delete_kid` does a get-then-delete.** DynamoDB's `delete_item` with `ReturnValues="ALL_OLD"` was the obvious approach to detect "kid not found," but moto's behavior here was inconsistent with real DynamoDB. Doing a `get_item` first and then `delete_item` is one extra ~5ms read per delete and works the same locally and in production.

**`hero` is used as a per-story default, not a profile lock-in.** When a parent picks a kid in the story flow, the kid's `hero` pre-fills the story's hero card — but the field stays editable. The same kid can star in a boy-hero or girl-hero story depending on the parent's choice that day.