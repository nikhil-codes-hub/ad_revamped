-- Add airline column to patterns table only
-- Migration: 003_add_airline_to_patterns.sql

-- Add airline column to patterns table
ALTER TABLE patterns
ADD COLUMN airline_code VARCHAR(10) COMMENT 'Airline code this pattern belongs to (e.g., SQ, AF, QF)' AFTER message_root;

-- Add composite index for airline-specific pattern lookup
CREATE INDEX idx_airline_version ON patterns(airline_code, spec_version, message_root);
