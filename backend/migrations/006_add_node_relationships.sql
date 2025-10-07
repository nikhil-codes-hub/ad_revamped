-- Migration 006: Add node_relationships table for storing discovered relationships between nodes
-- This table stores both BA-configured expected relationships and LLM-discovered relationships

CREATE TABLE IF NOT EXISTS node_relationships (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(36) NOT NULL,

    -- Source node (the one containing the reference)
    source_node_fact_id BIGINT NOT NULL,
    source_node_type VARCHAR(255) NOT NULL,
    source_section_path VARCHAR(500) NOT NULL,

    -- Target node (the one being referenced)
    target_node_fact_id BIGINT,  -- NULL if reference is broken
    target_node_type VARCHAR(255) NOT NULL,
    target_section_path VARCHAR(500) NOT NULL,

    -- Relationship details
    reference_type VARCHAR(100) NOT NULL,  -- e.g., 'pax_reference', 'segment_reference', 'infant_parent'
    reference_field VARCHAR(255),  -- e.g., 'PaxRefID', 'SegmentRefID'
    reference_value VARCHAR(255),  -- e.g., 'PAX1', 'SEG1'

    -- Validation status
    is_valid BOOLEAN DEFAULT TRUE,  -- Does the reference resolve to a target node?
    was_expected BOOLEAN DEFAULT FALSE,  -- Was this in expected_references config?
    confidence FLOAT DEFAULT 1.0,  -- LLM confidence score (0.0-1.0)

    -- Metadata
    discovered_by VARCHAR(50) DEFAULT 'llm',  -- 'llm' or 'config'
    model_used VARCHAR(100),  -- LLM model that discovered this

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (source_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_fact_id) REFERENCES node_facts(id) ON DELETE CASCADE,

    -- Indexes for performance
    INDEX idx_run_relationships (run_id),
    INDEX idx_source_node (source_node_fact_id),
    INDEX idx_target_node (target_node_fact_id),
    INDEX idx_reference_type (reference_type),
    INDEX idx_validity (is_valid, was_expected)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
