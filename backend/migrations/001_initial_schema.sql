-- Initial database schema for AssistedDiscovery
-- Migration: 001_initial_schema.sql
-- This creates all base tables needed for the system

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS pattern_matches;
DROP TABLE IF EXISTS association_facts;
DROP TABLE IF EXISTS node_facts;
DROP TABLE IF EXISTS patterns;
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS ndc_path_aliases;
DROP TABLE IF EXISTS ndc_target_paths;

-- Table: ndc_target_paths
-- Configuration for target XML paths per NDC version
CREATE TABLE ndc_target_paths (
    id INT PRIMARY KEY AUTO_INCREMENT,
    spec_version VARCHAR(10) NOT NULL COMMENT 'NDC specification version',
    message_root VARCHAR(100) NOT NULL COMMENT 'Root element name',
    path_local TEXT NOT NULL COMMENT 'Local-name path for targeting',
    extractor_key VARCHAR(50) NOT NULL COMMENT 'template or generic_llm',
    is_required BOOLEAN DEFAULT FALSE COMMENT 'Whether this section is required',
    importance VARCHAR(20) DEFAULT 'medium' COMMENT 'Section importance level',
    constraints_json JSON COMMENT 'Validation constraints and rules',
    notes TEXT COMMENT 'Human-readable description and notes',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_version_message (spec_version, message_root)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Configuration for target XML paths per NDC version';

-- Table: ndc_path_aliases
-- Path aliases for cross-version compatibility
CREATE TABLE ndc_path_aliases (
    id INT PRIMARY KEY AUTO_INCREMENT,
    from_spec_version VARCHAR(10) NOT NULL COMMENT 'Source NDC version',
    from_message_root VARCHAR(100) NOT NULL COMMENT 'Source message type',
    from_path_local TEXT NOT NULL COMMENT 'Source path',
    to_spec_version VARCHAR(10) NOT NULL COMMENT 'Target NDC version',
    to_message_root VARCHAR(100) NOT NULL COMMENT 'Target message type',
    to_path_local TEXT NOT NULL COMMENT 'Target path',
    is_bidirectional BOOLEAN DEFAULT FALSE COMMENT 'Whether alias works both ways',
    reason VARCHAR(255) COMMENT 'Reason for the alias',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Path aliases for cross-version compatibility';

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

-- Table: association_facts
-- Relationships and references between node facts
CREATE TABLE association_facts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(50) NOT NULL,
    rel_type VARCHAR(50) NOT NULL COMMENT 'Type of relationship',
    from_node_fact_id BIGINT NOT NULL,
    to_node_fact_id BIGINT NOT NULL,
    from_node_type VARCHAR(100) NOT NULL COMMENT 'Source node type',
    to_node_type VARCHAR(100) NOT NULL COMMENT 'Target node type',
    ref_key VARCHAR(100) COMMENT 'Reference key/attribute name',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (from_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    FOREIGN KEY (to_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    INDEX idx_run (run_id),
    INDEX idx_rel_type (rel_type),
    INDEX idx_from_node (from_node_fact_id),
    INDEX idx_to_node (to_node_fact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Relationships and references between node facts';

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
