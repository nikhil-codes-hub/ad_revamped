-- Add airline support to runs table
-- Migration: 002_add_airline_columns.sql

-- Add airline_code column only if it doesn't exist
SET @dbname = DATABASE();
SET @tablename = 'runs';
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
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(10) COMMENT ''Detected airline code (e.g., SQ, AF)'' AFTER message_root')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add airline_name column only if it doesn't exist
SET @columnname = 'airline_name';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      table_name = @tablename
      AND table_schema = @dbname
      AND column_name = @columnname
  ) > 0,
  'SELECT ''Column airline_name already exists'' AS Result',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(200) COMMENT ''Detected airline name'' AFTER airline_code')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add index only if it doesn't exist
SET @indexname = 'idx_airline';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      table_name = @tablename
      AND table_schema = @dbname
      AND index_name = @indexname
  ) > 0,
  'SELECT ''Index idx_airline already exists'' AS Result',
  CONCAT('CREATE INDEX ', @indexname, ' ON ', @tablename, '(airline_code)')
));
PREPARE createIndexIfNotExists FROM @preparedStatement;
EXECUTE createIndexIfNotExists;
DEALLOCATE PREPARE createIndexIfNotExists;
