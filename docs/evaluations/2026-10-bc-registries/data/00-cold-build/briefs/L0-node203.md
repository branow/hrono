<!-- leaf 203, 12 members -->

**What this is:** A set of condensed notes on Alembic/SQLAlchemy migrations for a `documents` table. The table stores versioned terms-of-use HTML, and a `user` table tracks which version each user accepted. Most snippets are truncated or repeat one another.

## Groupings

**1. Table creation and schema changes**
- Creates `documents` with these columns:
  - `created` and `modified`: DateTime, nullable.
  - `version_id`: Integer, NOT NULL, primary key.
  - `type`: String(20), NOT NULL.
  - `content`: Text.
  - `created_by_id` and `modified_by_id`: Integer foreign keys to `user.id`.
- Adds two columns to `user`:
  - `is_terms_of_use_accepted`: Boolean.
  - `terms_of_use_accepted_version`: Integer foreign key to `documents.version_id`.
- The first insert in this group is `op.bulk_insert(documents, [{'version_id': 1, 'type': 'termsofuse', 'content': html_content}])`. Its `version_id` is an integer.

**2. Lightweight `documents` table declarations (repeated stubs)**
- These are SQLAlchemy `table()` definitions named `documents`. They have two variants:
  - 3 String columns: `version_id`, `type`, `content`.
  - 4 String columns: the same three plus `content_type`.
- Each is followed by an empty or truncated `html_content = ...`.
- They appear about four times, with only the column set differing.

**3. Per-version `bulk_insert` calls**
Each call inserts one row into `documents` with `type='termsofuse'` and `content=html_content`. The variations are:

| version_id | content_type | Other |
|---|---|---|
| `'2'` | not set | |
| `'3'` | not set | |
| `'4'` | `'text/html'` | followed by a comment "update terms of use version 3 content" with no code |
| `'5'` | `'text/html'` | |
| `'d1'` | not set | `type='termsofuse_directorsearch'` |

**4. Cleanup and update fragment**
- `op.execute("DELETE FROM DOCUMENTS WHERE version_id='4' AND type='termsofuse'")` is followed by `tos_version3_content = """..."""`.
- This looks like a rework of an earlier version's content.

## Caution:
- `version_id` is a String (`'2'`, `'3'`, `'4'`, `'5'`) in the stub tables. The real schema makes it an Integer primary key with a foreign key from `user`. The string values and the integer column don't match.
- `'d1'` is hardcoded. It likely needs to vary by environment or context, and it can't be an Integer.
- The primary key has no autoincrement, so the caller must supply `version_id`. The `user` foreign key depends on it, so its lifecycle is critical.
- `html_content` is undefined or truncated in every snippet. It must be bound in the migration scope.
- The stub tables show no primary key, indexes or constraints, and the full table likely has more columns than shown.
- The DELETE targets `version_id='4'`, but the content variable is `tos_version3_content`. Confirm the mismatch is intentional.
- `tos_version3_content` is declared but unused, which suggests copy-paste or work in progress.
- The fragment after version 4 is incomplete, with a comment but no code.
- Each `bulk_insert` adds one row with a fixed `version_id` and `type`, and nothing is assigned from the return value. Make sure each list matches the table's column contract, especially whether `content_type` is included.

## Members

- sbc-auth: auth-api/migrations/versions/08063ceec05d_add_term_of_use_for_director_search.py
- sbc-auth: auth-api/migrations/versions/3818a89ddedf_add_tos_version_5.py
- sbc-auth: auth-api/migrations/versions/3818a89ddedf_add_tos_version_5.py
- sbc-auth: auth-api/migrations/versions/4efb2fdcc1ab_new_tos_added.py
- sbc-auth: auth-api/migrations/versions/4efb2fdcc1ab_new_tos_added.py
- sbc-auth: auth-api/migrations/versions/933ecac34eb4_added_tos_including_bceid.py
- sbc-auth: auth-api/migrations/versions/933ecac34eb4_added_tos_including_bceid.py
- sbc-auth: auth-api/migrations/versions/c10f494d7e10_add_tos_verion_4.py
- sbc-auth: auth-api/migrations/versions/c10f494d7e10_add_tos_verion_4.py
- sbc-auth: auth-api/migrations/versions/c10f494d7e10_add_tos_verion_4.py
- sbc-auth: auth-api/migrations/versions/d0cd84858921_documents_and_add_terms_of_service_to_.py
- sbc-auth: auth-api/migrations/versions/d0cd84858921_documents_and_add_terms_of_service_to_.py
