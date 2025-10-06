-- Add description column to patterns table
-- Migration: 005_add_pattern_description.sql

-- Add description column to patterns table
ALTER TABLE patterns
ADD COLUMN IF NOT EXISTS description TEXT NULL COMMENT 'Human-readable pattern description' AFTER decision_rule;
