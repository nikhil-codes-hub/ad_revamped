-- AssistedDiscovery Initial Database Schema - MySQL 9.4 Compatible
-- Based on enhanced design document specifications
-- Fixed for MySQL 9.4 TEXT column constraints

-- Run tracking table
CREATE TABLE runs (
    id VARCHAR(50) PRIMARY KEY COMMENT 'Unique run identifier',
    kind ENUM('discovery', 'identify') NOT NULL COMMENT 'Type of processing run',
    status ENUM('started', 'in_progress', 'completed', 'failed', 'partial_failure') DEFAULT 'started',
    spec_version VARCHAR(10) COMMENT 'Detected NDC version',
    message_root VARCHAR(100) COMMENT 'Detected message root element',
    filename VARCHAR(255) COMMENT 'Original uploaded filename',
    file_size_bytes BIGINT COMMENT 'File size in bytes',
    file_hash VARCHAR(64) COMMENT 'SHA-256 hash of uploaded file',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    metadata_json JSON COMMENT 'Additional run metadata and configuration',
    error_details TEXT COMMENT 'Error information if run failed',

    INDEX idx_kind_status (kind, status),
    INDEX idx_created_at (started_at),
    INDEX idx_spec_version (spec_version, message_root)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Tracking table for all processing runs';

-- Extracted node facts table
CREATE TABLE node_facts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(50) NOT NULL COMMENT 'Reference to runs table',
    spec_version VARCHAR(10) NOT NULL COMMENT 'NDC version for this fact',
    message_root VARCHAR(100) NOT NULL COMMENT 'Message type',
    section_path VARCHAR(500) NOT NULL COMMENT 'XML section path where node was found',
    node_type VARCHAR(100) NOT NULL COMMENT 'Type of node (e.g., Passenger, BookingReference)',
    node_ordinal INT NOT NULL COMMENT 'Position within section',
    fact_json JSON NOT NULL COMMENT 'Structured NodeFact data with PII masking',
    pii_masked BOOLEAN DEFAULT FALSE COMMENT 'Whether PII masking was applied',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    INDEX idx_run_section (run_id, section_path),
    INDEX idx_node_type (node_type),
    INDEX idx_spec_version (spec_version, message_root),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Extracted and masked node facts from XML processing';

-- Discovered patterns table
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

    UNIQUE KEY unique_signature (signature_hash),
    INDEX idx_spec_section (spec_version, message_root, section_path),
    INDEX idx_times_seen (times_seen DESC),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Discovered patterns for XML node classification';

-- Pattern matches for identify runs
CREATE TABLE pattern_matches (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(50) NOT NULL COMMENT 'Reference to runs table',
    node_fact_id BIGINT NOT NULL COMMENT 'Node fact that was matched',
    pattern_id BIGINT NOT NULL COMMENT 'Pattern that matched',
    confidence DECIMAL(4,3) NOT NULL COMMENT 'Confidence score 0.000-1.000',
    verdict ENUM('match', 'no_match', 'uncertain') NOT NULL COMMENT 'Classification verdict',
    match_metadata JSON COMMENT 'Additional matching details and scores',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE,
    INDEX idx_run_confidence (run_id, confidence DESC),
    INDEX idx_pattern_matches (pattern_id, verdict),
    INDEX idx_node_fact (node_fact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Results of pattern matching during identify runs';

-- Create views for common queries
CREATE VIEW v_run_summary AS
SELECT
    r.id,
    r.kind,
    r.status,
    r.spec_version,
    r.message_root,
    r.filename,
    r.started_at,
    r.finished_at,
    TIMESTAMPDIFF(SECOND, r.started_at, COALESCE(r.finished_at, NOW())) as duration_seconds,
    COUNT(DISTINCT nf.id) as node_facts_count,
    COUNT(DISTINCT p.id) as patterns_count,
    COUNT(DISTINCT pm.id) as matches_count,
    AVG(pm.confidence) as avg_confidence
FROM runs r
LEFT JOIN node_facts nf ON r.id = nf.run_id
LEFT JOIN patterns p ON r.spec_version = p.spec_version AND r.message_root = p.message_root AND r.kind = 'discovery'
LEFT JOIN pattern_matches pm ON r.id = pm.run_id AND r.kind = 'identify'
GROUP BY r.id, r.kind, r.status, r.spec_version, r.message_root, r.filename, r.started_at, r.finished_at;

COMMIT;