-- Add description column to patterns table
-- Migration: 005_add_pattern_description.sql

ALTER TABLE patterns
ADD COLUMN description TEXT NULL COMMENT 'Human-readable pattern description' AFTER decision_rule;
