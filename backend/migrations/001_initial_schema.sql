-- AssistedDiscovery Initial Database Schema
-- Based on enhanced design document specifications
-- MySQL implementation with future CouchDB migration consideration

-- Create database (run separately if needed)
-- CREATE DATABASE assisted_discovery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE assisted_discovery;

-- Target paths configuration table
CREATE TABLE ndc_target_paths (
    id INT PRIMARY KEY AUTO_INCREMENT,
    spec_version VARCHAR(10) NOT NULL COMMENT 'NDC specification version (e.g., 17.2)',
    message_root VARCHAR(100) NOT NULL COMMENT 'Root element name (e.g., OrderViewRS)',
    path_local TEXT NOT NULL COMMENT 'Local-name path for targeting',
    extractor_key VARCHAR(50) NOT NULL COMMENT 'template or generic_llm',
    is_required BOOLEAN DEFAULT FALSE COMMENT 'Whether this section is required',
    importance ENUM('critical', 'high', 'medium', 'low') DEFAULT 'medium' COMMENT 'Section importance level',
    constraints_json JSON COMMENT 'Validation constraints and rules',
    notes TEXT COMMENT 'Human-readable description and notes',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_target (spec_version, message_root, path_local),
    INDEX idx_spec_message (spec_version, message_root),
    INDEX idx_importance (importance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Configuration table for target XML paths per NDC version';

-- Path aliases for version fallbacks
CREATE TABLE ndc_path_aliases (
    id INT PRIMARY KEY AUTO_INCREMENT,
    from_spec_version VARCHAR(10) NOT NULL COMMENT 'Source NDC version',
    from_message_root VARCHAR(100) NOT NULL COMMENT 'Source message type',
    from_path_local TEXT NOT NULL COMMENT 'Source path',
    to_spec_version VARCHAR(10) NOT NULL COMMENT 'Target NDC version',
    to_message_root VARCHAR(100) NOT NULL COMMENT 'Target message type',
    to_path_local TEXT NOT NULL COMMENT 'Target path',
    is_bidirectional BOOLEAN DEFAULT FALSE COMMENT 'Whether alias works both ways',
    reason VARCHAR(255) COMMENT 'Reason for the alias (e.g., minor version compatibility)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_from_version (from_spec_version, from_message_root),
    INDEX idx_to_version (to_spec_version, to_message_root)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Path aliases for cross-version compatibility';

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

-- Association facts for relationships between nodes
CREATE TABLE association_facts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(50) NOT NULL COMMENT 'Reference to runs table',
    rel_type VARCHAR(50) NOT NULL COMMENT 'Type of relationship (e.g., id_ref, parent_child)',
    from_node_fact_id BIGINT NOT NULL COMMENT 'Source node fact',
    to_node_fact_id BIGINT NOT NULL COMMENT 'Target node fact',
    from_node_type VARCHAR(100) NOT NULL COMMENT 'Source node type',
    to_node_type VARCHAR(100) NOT NULL COMMENT 'Target node type',
    ref_key VARCHAR(100) COMMENT 'Reference key/attribute name',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (from_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    FOREIGN KEY (to_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    INDEX idx_run_rel (run_id, rel_type),
    INDEX idx_from_node (from_node_fact_id),
    INDEX idx_to_node (to_node_fact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT 'Relationships and references between node facts';

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
LEFT JOIN patterns p ON r.id = p.created_at AND r.kind = 'discovery'  -- Only for discovery runs
LEFT JOIN pattern_matches pm ON r.id = pm.run_id AND r.kind = 'identify'  -- Only for identify runs
GROUP BY r.id, r.kind, r.status, r.spec_version, r.message_root, r.filename, r.started_at, r.finished_at;

-- Create view for pattern coverage analysis
CREATE VIEW v_pattern_coverage AS
SELECT
    ntp.spec_version,
    ntp.message_root,
    ntp.importance,
    COUNT(*) as total_target_sections,
    COUNT(CASE WHEN ntp.is_required THEN 1 END) as required_sections,
    COUNT(DISTINCT p.section_path) as sections_with_patterns,
    ROUND(COUNT(DISTINCT p.section_path) * 100.0 / COUNT(*), 2) as coverage_percentage
FROM ndc_target_paths ntp
LEFT JOIN patterns p ON ntp.spec_version = p.spec_version
    AND ntp.message_root = p.message_root
    AND ntp.path_local = p.section_path
GROUP BY ntp.spec_version, ntp.message_root, ntp.importance;

-- Insert sample target paths for OrderViewRS 17.2
INSERT INTO ndc_target_paths (spec_version, message_root, path_local, extractor_key, is_required, importance, notes) VALUES
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Order', 'template', TRUE, 'critical', 'Main order information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Order/BookingReferences', 'template', TRUE, 'critical', 'Booking reference numbers'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/PassengerList', 'template', TRUE, 'critical', 'Passenger information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/ContactList', 'template', TRUE, 'high', 'Contact information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Order/OrderItems', 'generic_llm', TRUE, 'critical', 'Order line items'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Order/Payments', 'generic_llm', TRUE, 'critical', 'Payment information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/BaggageList', 'generic_llm', FALSE, 'medium', 'Baggage information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/SeatList', 'generic_llm', FALSE, 'medium', 'Seat assignments'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Order/TimeLimits', 'template', TRUE, 'high', 'Time limits and deadlines'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Order/TotalOrderPrice', 'template', TRUE, 'critical', 'Total pricing information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/FlightSegmentList', 'generic_llm', TRUE, 'critical', 'Flight segment details'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/FlightList', 'generic_llm', TRUE, 'critical', 'Flight information'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/OriginDestinationList', 'template', TRUE, 'high', 'Origin and destination pairs'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/ServiceList', 'generic_llm', FALSE, 'medium', 'Ancillary services'),
('17.2', 'OrderViewRS', '/OrderViewRS/Response/Metadata', 'template', FALSE, 'low', 'Response metadata');

-- Insert sample path aliases for version compatibility
INSERT INTO ndc_path_aliases (from_spec_version, from_message_root, from_path_local, to_spec_version, to_message_root, to_path_local, is_bidirectional, reason) VALUES
('18.2', 'OrderViewRS', '/OrderViewRS/Response/Order/BookingReferences', '17.2', 'OrderViewRS', '/OrderViewRS/Response/Order/BookingReferences', TRUE, 'Structure unchanged between versions'),
('18.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/PassengerList', '17.2', 'OrderViewRS', '/OrderViewRS/Response/DataLists/PassengerList', TRUE, 'Passenger structure compatible'),
('19.1', 'OrderViewRS', '/OrderViewRS/Response/Order', '17.2', 'OrderViewRS', '/OrderViewRS/Response/Order', FALSE, 'Fallback for basic order structure');

COMMIT;