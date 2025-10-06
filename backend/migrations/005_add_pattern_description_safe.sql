-- Add description column to patterns table (SAFE VERSION)
-- Migration: 005_add_pattern_description_safe.sql
-- This version checks if the column exists before adding it

-- Add description column only if it doesn't exist
SET @dbname = DATABASE();
SET @tablename = 'patterns';
SET @columnname = 'description';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      table_name = @tablename
      AND table_schema = @dbname
      AND column_name = @columnname
  ) > 0,
  'SELECT ''Column description already exists'' AS Result',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' TEXT NULL COMMENT ''Human-readable pattern description'' AFTER decision_rule')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;
