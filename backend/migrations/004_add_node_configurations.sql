-- Add node_configurations table for BA-managed extraction rules
-- Migration: 004_add_node_configurations.sql

CREATE TABLE node_configurations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    spec_version VARCHAR(10) NOT NULL COMMENT 'NDC specification version (e.g., 18.1, 21.3)',
    message_root VARCHAR(100) NOT NULL COMMENT 'Message type (e.g., OrderViewRS)',
    airline_code VARCHAR(10) NULL COMMENT 'Airline code (NULL = applies to all airlines)',
    node_type VARCHAR(100) NOT NULL COMMENT 'Node type name (e.g., PaxList, BaggageAllowanceList)',
    section_path VARCHAR(500) NOT NULL COMMENT 'Full XML path to this node',
    enabled BOOLEAN DEFAULT TRUE COMMENT 'Should this node be extracted during Discovery?',
    expected_references JSON NULL COMMENT 'Array of reference types expected (e.g., ["infant_parent", "segment_reference"])',
    ba_remarks TEXT NULL COMMENT 'Business analyst notes and instructions',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NULL COMMENT 'User who created/updated this configuration',

    -- Ensure one config per node per version/airline
    UNIQUE KEY unique_node_config (spec_version, message_root, airline_code, section_path),

    -- Performance indexes
    INDEX idx_version_message (spec_version, message_root),
    INDEX idx_airline (airline_code),
    INDEX idx_enabled (enabled),
    INDEX idx_node_type (node_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='BA-managed node extraction configurations';

-- Add description column to patterns table
ALTER TABLE patterns
ADD COLUMN description TEXT NULL COMMENT 'Human-readable pattern description' AFTER decision_rule;
