-- Migration 008: Add warning column to runs table
-- Purpose: Store warning messages for runs (e.g., no patterns available for message type)
-- Date: 2024-11-10

-- Add warning column to runs table
ALTER TABLE runs ADD COLUMN warning TEXT;

-- Add comment explaining the column
-- SQLite doesn't support COMMENT directly, but we document it here:
-- warning: Warning message displayed to user (e.g., "No patterns available for 'AirShoppingRS' message type")
