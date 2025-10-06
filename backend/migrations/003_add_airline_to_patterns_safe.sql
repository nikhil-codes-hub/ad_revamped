-- Add airline column to patterns table (SAFE VERSION)
-- Migration: 003_add_airline_to_patterns_safe.sql
-- This version checks if the column exists before adding it

-- Add airline_code column only if it doesn't exist
SET @dbname = DATABASE();
SET @tablename = 'patterns';
SET @columnname = 'airline_code';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      table_name = @tablename
      AND table_schema = @dbname
      AND column_name = @columnname
  ) > 0,
  'SELECT ''Column airline_code already exists'' AS Result',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(10) COMMENT ''Airline code this pattern belongs to (e.g., SQ, AF, QF)'' AFTER message_root')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add composite index only if it doesn't exist
SET @indexname = 'idx_airline_version';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      table_name = @tablename
      AND table_schema = @dbname
      AND index_name = @indexname
  ) > 0,
  'SELECT ''Index idx_airline_version already exists'' AS Result',
  CONCAT('CREATE INDEX ', @indexname, ' ON ', @tablename, '(airline_code, spec_version, message_root)')
));
PREPARE createIndexIfNotExists FROM @preparedStatement;
EXECUTE createIndexIfNotExists;
DEALLOCATE PREPARE createIndexIfNotExists;
