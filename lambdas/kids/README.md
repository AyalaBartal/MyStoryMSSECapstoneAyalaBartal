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
  "avatar_card_id": "girl_brown_hair"
}
```

**Responses:**

| Status | Shape | When |
|---|---|---|
| 201 | `{ parent_id, kid_id, name, birth_year, avatar_card_id, created_at }` | Created |
| 400 | `{ error }` | Missing/invalid field |
| 401 | `{ error }` | Missing or invalid JWT |
| 500 | `{ error }` | Unexpected failure |

### GET /kids — list this parent's kids

**Responses:**

| Status | Shape | When |
|---|---|---|
| 200 | `{ kids: [{...}, ...] }` | Success — list sorted newest-first |
| 401 | `{ error }` | Missing or invalid JWT |

Empty list if the parent has no kids.

### DELETE /kids/{kid_id} — delete a kid profile

**Responses:**

| Status | Shape | When |
|---|---|---|
| 204 | (empty body) | Deleted |
| 400 | `{ error }` | Missing kid_id in path, or kid doesn't exist |
| 401 | `{ error }` | Missing or invalid JWT |

Stories tagged with this kid_id are NOT deleted — they keep their kid_id.

## Environment variables

| Name | Required | Purpose |
|---|---|---|
| `KIDS_TABLE` | yes | DynamoDB table name (PK=parent_id, SK=kid_id) |
| `COGNITO_USER_POOL_ID` | yes | For JWT verification |
| `COGNITO_APP_CLIENT_ID` | yes | For JWT verification |
| `LOG_LEVEL` | no | DEBUG/INFO/WARNING/ERROR (default INFO) |

## IAM permissions

Wired in `infra/stacks/api_stack.py`:
- `dynamodb:Query`, `PutItem`, `DeleteItem` on the kids table

## File layout