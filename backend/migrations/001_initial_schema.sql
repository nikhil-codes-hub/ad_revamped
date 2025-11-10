-- Initial database schema for AssistedDiscovery
-- Migration: 001_initial_schema.sql
-- This creates all base tables needed for the system

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS pattern_matches;
DROP TABLE IF EXISTS node_facts;
DROP TABLE IF EXISTS patterns;
DROP TABLE IF EXISTS runs;

-- Table: runs
-- Tracking table for all processing runs
CREATE TABLE runs (
    id VARCHAR(50) PRIMARY KEY COMMENT 'Unique run identifier',
    kind VARCHAR(20) NOT NULL COMMENT 'Type of processing run (discovery, identify)',
    status VARCHAR(20) DEFAULT 'started' COMMENT 'Current run status',
    spec_version VARCHAR(10) COMMENT 'Detected NDC version',
    message_root VARCHAR(100) COMMENT 'Detected message root element',
    filename VARCHAR(255) COMMENT 'Original uploaded filename',
    file_size_bytes BIGINT COMMENT 'File size in bytes',
    file_hash VARCHAR(64) COMMENT 'SHA-256 hash of uploaded file',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL COMMENT 'When run completed',
    metadata_json JSON COMMENT 'Additional run metadata and configuration',
    error_details TEXT COMMENT 'Error information if run failed',

    INDEX idx_kind (kind),
    INDEX idx_status (status),
    INDEX idx_version (spec_version, message_root),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracking table for all processing runs';

-- Table: node_facts
-- Extracted and masked node facts from XML processing
CREATE TABLE node_facts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(50) NOT NULL,
    spec_version VARCHAR(10) NOT NULL COMMENT 'NDC version for this fact',
    message_root VARCHAR(100) NOT NULL COMMENT 'Message type',
    section_path VARCHAR(500) NOT NULL COMMENT 'XML section path where node was found',
    node_type VARCHAR(100) NOT NULL COMMENT 'Type of node',
    node_ordinal INT NOT NULL COMMENT 'Position within section',
    fact_json JSON NOT NULL COMMENT 'Structured NodeFact data with PII masking',
    pii_masked BOOLEAN DEFAULT FALSE COMMENT 'Whether PII masking was applied',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    INDEX idx_run (run_id),
    INDEX idx_version (spec_version, message_root),
    INDEX idx_node_type (node_type),
    INDEX idx_section_path (section_path(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Extracted and masked node facts from XML processing';

-- Table: patterns
-- Discovered patterns for XML node classification
CREATE TABLE patterns (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    spec_version VARCHAR(10) NOT NULL COMMENT 'NDC version this pattern applies to',
    message_root VARCHAR(100) NOT NULL COMMENT 'Message type',
    section_path VARCHAR(500) NOT NULL COMMENT 'XML section where pattern was found',
    selector_xpath TEXT NOT NULL COMMENT 'XPath selector for matching nodes',
    decision_rule JSON NOT NULL COMMENT 'Rule for determining pattern matches',
    signature_hash VARCHAR(64) UNIQUE NOT NULL COMMENT 'SHA-256 hash for deduplication',
    times_seen INT DEFAULT 1 COMMENT 'Number of times this pattern was discovered',
    created_by_model VARCHAR(50) COMMENT 'LLM model that created this pattern',
    examples JSON COMMENT 'Masked examples of nodes matching this pattern',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_version (spec_version, message_root),
    INDEX idx_section_path (section_path(255)),
    INDEX idx_signature (signature_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Discovered patterns for XML node classification';

-- Table: pattern_matches
-- Results of pattern matching during identify runs
CREATE TABLE pattern_matches (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(50) NOT NULL,
    node_fact_id BIGINT NOT NULL,
    pattern_id BIGINT NOT NULL,
    confidence DECIMAL(4,3) NOT NULL COMMENT 'Confidence score 0.000-1.000',
    verdict VARCHAR(20) NOT NULL COMMENT 'Classification verdict (match, no_match, uncertain)',
    match_metadata JSON COMMENT 'Additional matching details and scores',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE,
    INDEX idx_run (run_id),
    INDEX idx_node_fact (node_fact_id),
    INDEX idx_pattern (pattern_id),
    INDEX idx_verdict (verdict),
    INDEX idx_confidence (confidence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Results of pattern matching during identify runs';
