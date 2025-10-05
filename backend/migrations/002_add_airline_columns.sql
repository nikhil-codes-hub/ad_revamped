-- Add airline detection columns to runs and patterns tables
-- Migration: 002_add_airline_columns.sql

-- Add airline columns to runs table
ALTER TABLE runs
ADD COLUMN airline_code VARCHAR(10) COMMENT 'Detected airline code (e.g., SQ, AF, QF)' AFTER message_root,
ADD COLUMN airline_name VARCHAR(200) COMMENT 'Detected airline name (e.g., SINGAPORE AIRLINES)' AFTER airline_code;

-- Add index for airline filtering on runs
CREATE INDEX idx_airline_code ON runs(airline_code);

-- Add airline column to patterns table
ALTER TABLE patterns
ADD COLUMN airline_code VARCHAR(10) COMMENT 'Airline code this pattern belongs to (e.g., SQ, AF, QF)' AFTER message_root;

-- Add composite index for airline-specific pattern lookup
CREATE INDEX idx_airline_version ON patterns(airline_code, spec_version, message_root);
