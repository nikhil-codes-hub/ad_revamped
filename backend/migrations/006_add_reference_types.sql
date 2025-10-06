-- Add reference_types table for managing reference type glossary
-- Migration: 006_add_reference_types.sql

-- Drop table if exists for clean setup
DROP TABLE IF EXISTS reference_types;

-- Create reference_types table
CREATE TABLE reference_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    reference_type VARCHAR(100) NOT NULL UNIQUE COMMENT 'Unique reference type identifier (e.g., infant_parent)',
    display_name VARCHAR(200) NOT NULL COMMENT 'Human-readable display name',
    description TEXT NOT NULL COMMENT 'Description of what this reference represents',
    example VARCHAR(500) NULL COMMENT 'Example of this reference type',
    category VARCHAR(50) NULL COMMENT 'Category: passenger, segment, journey, baggage, price, service',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Whether this reference type is active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NULL COMMENT 'User who created this reference type',

    INDEX idx_category (category),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Glossary of reference types used in NDC XML node relationships';

-- Insert default/common reference types
INSERT INTO reference_types (reference_type, display_name, description, example, category, created_by) VALUES
('infant_parent', 'Infant-Parent Reference', 'Reference from infant passenger to parent passenger in PaxList', 'Infant PaxID:2 references Parent PaxID:1', 'passenger', 'system'),
('segment_reference', 'Segment Reference', 'Reference to flight segment from passenger or service', 'PaxSegment references SegmentID:SEG1', 'segment', 'system'),
('pax_reference', 'Passenger Reference', 'Reference to passenger from service, baggage, or seat', 'BaggageItem references PaxID:1', 'passenger', 'system'),
('baggage_reference', 'Baggage Reference', 'Reference to baggage allowance or item', 'BaggageAllowance references BaggageID:BAG1', 'baggage', 'system'),
('journey_reference', 'Journey Reference', 'Reference to journey or origin-destination pair', 'PriceClass references JourneyID:J1', 'journey', 'system'),
('price_reference', 'Price Reference', 'Reference to price detail or offer', 'TaxBreakdown references OfferID:OFFER1', 'price', 'system'),
('service_reference', 'Service Reference', 'Reference to ancillary service or service list', 'ServicePrice references ServiceID:SRV1', 'service', 'system'),
('seat_reference', 'Seat Reference', 'Reference to seat assignment or seat map', 'SeatAssignment references SeatID:12A', 'service', 'system'),
('paxsegment_reference', 'Passenger-Segment Reference', 'Reference linking passenger to specific flight segment', 'PaxSegment references both PaxID:1 and SegmentID:SEG1', 'segment', 'system'),
('order_reference', 'Order Reference', 'Reference to order or booking', 'OrderItem references OrderID:ORDER123', 'order', 'system');
