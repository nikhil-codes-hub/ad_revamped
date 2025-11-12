# Migration 007: Add superseded_by to Patterns Table

**Date:** 2025-11-01
**Purpose:** Add conflict resolution support for pattern hierarchies

## What This Migration Does

Adds a `superseded_by` column to the `patterns` table to track when patterns are replaced during conflict resolution.

### Use Case

When users extract patterns at different granularities, conflicts can occur:

**Example:**
1. User first extracts `/PaxList/Pax` (item pattern)
2. User later extracts `/PaxList` (parent container pattern)

**Conflict:** Both patterns represent the same data at different levels.

**Resolution Strategies:**
- **REPLACE**: Delete old child patterns, keep new parent pattern
- **KEEP_BOTH**: Keep both (may cause ambiguous matches)
- **MERGE**: Mark old patterns as superseded (keeps history)

The `superseded_by` column enables the MERGE strategy by tracking which pattern replaced another.

## Database Changes

```sql
ALTER TABLE patterns
ADD COLUMN superseded_by INTEGER NULL
REFERENCES patterns(id) ON DELETE SET NULL;

CREATE INDEX idx_patterns_superseded_by ON patterns(superseded_by);
```

## How to Apply

### Automatic (Recommended)

The migration is **automatically applied** when workspaces are accessed via `workspace_db.py`.

The `WorkspaceSessionFactory.__init__()` calls `_ensure_patterns_superseded_by()` which:
1. Checks if the column exists
2. Adds it if missing
3. Safely handles existing columns

**No manual action required!** Just restart your application.

### Manual (If Needed)

If you want to apply the migration to all workspaces immediately:

```bash
cd backend
python migrations/apply_007_superseded_by.py
```

This script:
- Finds all workspace `.db` files
- Checks each for the `superseded_by` column
- Adds it if missing
- Creates the index
- Reports success/failure

## Schema After Migration

```sql
CREATE TABLE patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_version VARCHAR(10) NOT NULL,
    message_root VARCHAR(100) NOT NULL,
    airline_code VARCHAR(10),
    section_path VARCHAR(500) NOT NULL,
    selector_xpath TEXT NOT NULL,
    decision_rule JSON NOT NULL,
    description TEXT,
    signature_hash VARCHAR(64) UNIQUE NOT NULL,
    times_seen INTEGER DEFAULT 1,
    created_by_model VARCHAR(50),
    examples JSON,
    superseded_by INTEGER,                    -- NEW COLUMN
    created_at DATETIME,
    last_seen_at DATETIME,
    FOREIGN KEY(superseded_by) REFERENCES patterns(id) ON DELETE SET NULL
);

CREATE INDEX idx_patterns_superseded_by ON patterns(superseded_by);
```

## Example Usage

### MERGE Resolution Strategy

When a user extracts `/PaxList` after extracting `/PaxList/Pax` with MERGE resolution:

```python
# Old Pax pattern
old_pattern_id = 123

# New PaxList pattern
new_pattern_id = 456

# Mark old pattern as superseded
UPDATE patterns
SET superseded_by = 456
WHERE id = 123;
```

Now:
- Pattern 123 (Pax) has `superseded_by = 456`
- Pattern 456 (PaxList) has `superseded_by = NULL` (active)

During Discovery, the system:
- Skips patterns where `superseded_by IS NOT NULL`
- Only matches against active patterns
- Preserves superseded patterns for audit/history

## Rollback (If Needed)

SQLite doesn't support dropping columns easily, but you can:

1. **Mark as unused** (safest):
```sql
-- Set all superseded_by values to NULL
UPDATE patterns SET superseded_by = NULL;
```

2. **Recreate table** (complete removal):
```sql
-- Backup data
CREATE TABLE patterns_backup AS SELECT * FROM patterns;

-- Drop and recreate without superseded_by
DROP TABLE patterns;
-- (recreate with original schema)

-- Restore data (excluding superseded_by column)
INSERT INTO patterns (...) SELECT ... FROM patterns_backup;
DROP TABLE patterns_backup;
```

## Testing

Verify the migration was successful:

```bash
# For a specific workspace
sqlite3 backend/data/workspaces/Wet.db "PRAGMA table_info(patterns);"

# Should show superseded_by column:
# 11|superseded_by|INTEGER|0||0
```

## Affected Code

Files using the `superseded_by` column:
- `app/models/database.py` - Pattern model definition
- `app/services/conflict_detector.py` - Conflict detection and resolution
- `app/services/workspace_db.py` - Auto-migration on workspace access
- `app/api/v1/endpoints/runs.py` - Conflict resolution API

## Related Features

- Pattern conflict detection (pre-flight check)
- Conflict resolution strategies (REPLACE, KEEP_BOTH, MERGE)
- Pattern deletion endpoints (single and bulk)
- Historical pattern tracking

## Notes

- **New workspaces**: Get the column automatically from SQLAlchemy model
- **Existing workspaces**: Get the column added on first access
- **Safe to run multiple times**: The migration checks if column exists first
- **Foreign key constraint**: ON DELETE SET NULL ensures referential integrity
- **Indexed**: Fast lookups for active vs superseded patterns

## Questions?

Contact: [Your Team/Support]
