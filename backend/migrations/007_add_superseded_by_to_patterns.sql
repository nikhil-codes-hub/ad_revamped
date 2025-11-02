-- Add superseded_by column to patterns table for conflict resolution
-- Migration: 007_add_superseded_by_to_patterns.sql
-- Date: 2025-11-01
--
-- This migration adds a superseded_by column to track pattern replacement
-- during conflict resolution (e.g., when extracting /PaxList after extracting /PaxList/Pax)

-- NOTE: This migration is automatically applied by workspace_db.py via _ensure_patterns_superseded_by()
-- This file is for documentation and manual application if needed.

-- For SQLite (used in workspace databases):
ALTER TABLE patterns
ADD COLUMN superseded_by INTEGER NULL
REFERENCES patterns(id) ON DELETE SET NULL;

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_patterns_superseded_by ON patterns(superseded_by);

-- Example usage:
-- When extracting /PaxList (parent) after /PaxList/Pax (child) with MERGE resolution:
-- UPDATE patterns SET superseded_by = <new_paxlist_pattern_id> WHERE id IN (<old_pax_pattern_ids>);
-- This marks the old Pax patterns as superseded but keeps them for historical reference.
