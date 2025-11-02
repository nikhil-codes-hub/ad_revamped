#!/usr/bin/env python3
"""
Apply migration 007: Add superseded_by column to patterns table

This script applies the migration to all existing workspace databases.
The migration is also automatically applied when workspaces are accessed
via the workspace_db.py _ensure_patterns_superseded_by() method.

Usage:
    python migrations/apply_007_superseded_by.py
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_workspace_dir() -> Path:
    """Get the workspace database directory."""
    backend_dir = Path(__file__).parent.parent
    workspace_dir = backend_dir / "data" / "workspaces"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def apply_migration_to_workspace(workspace_path: Path) -> bool:
    """
    Apply the superseded_by column migration to a single workspace database.

    Args:
        workspace_path: Path to the workspace .db file

    Returns:
        True if migration was applied or column already exists, False on error
    """
    print(f"\nProcessing workspace: {workspace_path.name}")

    try:
        conn = sqlite3.connect(workspace_path)
        cursor = conn.cursor()

        # Check if patterns table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='patterns'
        """)

        if not cursor.fetchone():
            print(f"  ⚠️  No patterns table found in {workspace_path.name} - skipping")
            conn.close()
            return True

        # Check if superseded_by column already exists
        cursor.execute("PRAGMA table_info(patterns)")
        columns = [row[1] for row in cursor.fetchall()]

        if "superseded_by" in columns:
            print(f"  ✓ Column 'superseded_by' already exists - skipping")
            conn.close()
            return True

        # Add the column
        print(f"  + Adding 'superseded_by' column...")
        cursor.execute("""
            ALTER TABLE patterns
            ADD COLUMN superseded_by INTEGER NULL
            REFERENCES patterns(id) ON DELETE SET NULL
        """)

        # Create index
        print(f"  + Creating index on 'superseded_by'...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_superseded_by
            ON patterns(superseded_by)
        """)

        conn.commit()
        conn.close()

        print(f"  ✓ Migration applied successfully to {workspace_path.name}")
        return True

    except Exception as e:
        print(f"  ✗ Error applying migration to {workspace_path.name}: {e}")
        return False


def main():
    """Apply migration to all workspace databases."""
    print("=" * 70)
    print("Migration 007: Add superseded_by column to patterns table")
    print("=" * 70)

    # Get workspace directory
    workspace_dir = get_workspace_dir()

    print(f"\nWorkspace directory: {workspace_dir}")

    # Find all .db files
    db_files = list(workspace_dir.glob("*.db"))

    if not db_files:
        print(f"\n⚠️  No workspace databases found in {workspace_dir}")
        print("Migration will be applied automatically when workspaces are created.")
        return

    print(f"\nFound {len(db_files)} workspace database(s)")

    # Apply migration to each workspace
    success_count = 0
    error_count = 0

    for db_file in sorted(db_files):
        if apply_migration_to_workspace(db_file):
            success_count += 1
        else:
            error_count += 1

    # Summary
    print("\n" + "=" * 70)
    print("Migration Summary:")
    print(f"  Total workspaces: {len(db_files)}")
    print(f"  ✓ Successful: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print("=" * 70)

    if error_count > 0:
        print("\n⚠️  Some migrations failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("\n✓ All migrations completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
