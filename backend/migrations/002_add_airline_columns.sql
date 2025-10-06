-- Add airline support to runs table
-- Migration: 002_add_airline_columns.sql

-- Add airline_code column to runs table
ALTER TABLE runs
ADD COLUMN IF NOT EXISTS airline_code VARCHAR(10) COMMENT 'Detected airline code (e.g., SQ, AF)' AFTER message_root;

-- Add airline_name column to runs table
ALTER TABLE runs
ADD COLUMN IF NOT EXISTS airline_name VARCHAR(200) COMMENT 'Detected airline name' AFTER airline_code;

-- Add index for airline filtering
CREATE INDEX IF NOT EXISTS idx_airline ON runs(airline_code);
