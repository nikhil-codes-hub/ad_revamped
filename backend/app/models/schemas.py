"""
Pydantic schemas for AssistedDiscovery API.

Request/response models for FastAPI endpoints.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, validator
from enum import Enum


class RunKind(str, Enum):
    """Types of processing runs."""
    PATTERN_EXTRACTOR = "pattern_extractor"  # Extracts and learns patterns from XML
    DISCOVERY = "discovery"  # Matches XML against learned patterns


class RunStatus(str, Enum):
    """Status of processing runs."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL_FAILURE = "partial_failure"


class ImportanceLevel(str, Enum):
    """Importance levels for target paths."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Verdict(str, Enum):
    """Pattern matching verdicts."""
    MATCH = "match"
    NO_MATCH = "no_match"
    UNCERTAIN = "uncertain"


# Request Models
class RunCreate(BaseModel):
    """Request model for creating a new run."""
    kind: RunKind = Field(..., description="Type of run: discovery or identify")


# Response Models
class RunResponse(BaseModel):
    """Response model for run information."""
    id: str = Field(..., description="Unique run identifier")
    kind: str = Field(..., description="Type of run")
    status: RunStatus = Field(..., description="Current run status")
    spec_version: Optional[str] = Field(None, description="Detected NDC version")
    message_root: Optional[str] = Field(None, description="Detected message root")
    airline_code: Optional[str] = Field(None, description="Detected airline code")
    airline_name: Optional[str] = Field(None, description="Detected airline name")
    filename: Optional[str] = Field(None, description="Original filename")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    created_at: Optional[str] = Field(None, description="When run was created (ISO format)")
    finished_at: Optional[str] = Field(None, description="When run finished (ISO format)")
    duration_seconds: Optional[int] = Field(None, description="Run duration in seconds")
    elements_analyzed: Optional[int] = Field(None, description="Number of XML elements analyzed")
    subtrees_processed: Optional[int] = Field(None, description="Number of subtrees processed")
    error_details: Optional[str] = Field(None, description="Error information if failed")
    warning: Optional[str] = Field(None, description="Warning message (e.g., no node configs found)")

    class Config:
        from_attributes = True


class NodeFactResponse(BaseModel):
    """Response model for node facts."""
    id: int = Field(..., description="Unique node fact identifier")
    run_id: str = Field(..., description="Associated run ID")
    spec_version: str = Field(..., description="NDC version")
    message_root: str = Field(..., description="Message type")
    section_path: str = Field(..., description="XML section path")
    node_type: str = Field(..., description="Type of node")
    node_ordinal: int = Field(..., description="Position within section")
    fact_json: Dict[str, Any] = Field(..., description="Structured node fact data")
    pii_masked: bool = Field(..., description="Whether PII was masked")
    created_at: str = Field(..., description="When fact was created (ISO format)")

    class Config:
        from_attributes = True


class PatternResponse(BaseModel):
    """Response model for patterns."""
    id: int = Field(..., description="Unique pattern identifier")
    spec_version: str = Field(..., description="NDC version")
    message_root: str = Field(..., description="Message type")
    airline_code: Optional[str] = Field(None, description="Airline code")
    section_path: str = Field(..., description="XML section path")
    selector_xpath: str = Field(..., description="XPath selector")
    decision_rule: Dict[str, Any] = Field(..., description="Pattern matching rule")
    description: Optional[str] = Field(None, description="Business-friendly pattern description")
    signature_hash: str = Field(..., description="Unique signature hash")
    times_seen: int = Field(..., description="Times pattern was discovered")
    created_by_model: Optional[str] = Field(None, description="LLM model that created pattern")
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Example matches")
    created_at: str = Field(..., description="When pattern was created (ISO format)")
    last_seen_at: str = Field(..., description="When pattern was last seen (ISO format)")
    superseded_by: Optional[int] = Field(None, description="Pattern ID that supersedes this pattern (if superseded)")

    class Config:
        from_attributes = True


class PatternMatchResponse(BaseModel):
    """Response model for pattern matches."""
    id: int = Field(..., description="Unique match identifier")
    run_id: str = Field(..., description="Associated run ID")
    element_id: int = Field(..., description="XML element that was matched")
    pattern_id: int = Field(..., description="Pattern that matched")
    confidence: Decimal = Field(..., description="Confidence score 0.000-1.000")
    verdict: Verdict = Field(..., description="Classification verdict")
    match_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional matching details")
    created_at: str = Field(..., description="When match was created (ISO format)")

    class Config:
        from_attributes = True


# Report Models
class DiscoveryReportSummary(BaseModel):
    """Summary section of discovery report."""
    patterns_discovered: int = Field(..., description="Number of new patterns found")
    nodes_processed: int = Field(..., description="Total nodes processed")
    sections_analyzed: int = Field(..., description="XML sections analyzed")
    coverage_percentage: float = Field(..., description="Percentage of target sections covered")
    processing_time_seconds: int = Field(..., description="Total processing time")


class DiscoveryReport(BaseModel):
    """Complete discovery run report."""
    run_id: str = Field(..., description="Run identifier")
    report_type: str = Field(default="discovery", description="Type of report")
    summary: DiscoveryReportSummary = Field(..., description="Summary statistics")
    patterns: List[PatternResponse] = Field(..., description="Discovered patterns")
    coverage_by_section: Dict[str, float] = Field(..., description="Coverage by XML section")
    generated_at: str = Field(..., description="Report generation timestamp")


class IdentifyReportSummary(BaseModel):
    """Summary section of identify report."""
    nodes_processed: int = Field(..., description="Total nodes processed")
    patterns_matched: int = Field(..., description="Patterns that found matches")
    high_confidence_matches: int = Field(..., description="Matches above 0.8 confidence")
    low_confidence_matches: int = Field(..., description="Matches below 0.6 confidence")
    unmatched_nodes: int = Field(..., description="Nodes with no pattern matches")
    avg_confidence: float = Field(..., description="Average confidence score")
    processing_time_seconds: int = Field(..., description="Total processing time")


class GapAnalysis(BaseModel):
    """Gap analysis for identify reports."""
    coverage_by_importance: Dict[ImportanceLevel, Dict[str, Any]] = Field(
        ..., description="Coverage grouped by importance level"
    )
    missing_required_sections: List[str] = Field(..., description="Required sections not found")
    constraint_violations: Dict[str, int] = Field(..., description="Types of constraint violations")
    unmatched_nodes_by_section: Dict[str, int] = Field(..., description="Unmatched nodes per section")


class IdentifyReport(BaseModel):
    """Complete identify run report."""
    run_id: str = Field(..., description="Run identifier")
    report_type: str = Field(default="identify", description="Type of report")
    summary: IdentifyReportSummary = Field(..., description="Summary statistics")
    gap_analysis: GapAnalysis = Field(..., description="Coverage and gap analysis")
    matches: List[PatternMatchResponse] = Field(..., description="Pattern matches")
    generated_at: str = Field(..., description="Report generation timestamp")


# Configuration Models
# (NdcTargetPathResponse removed - table is unused, superseded by NodeConfiguration)

# Utility Models
class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Health check timestamp")


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    timestamp: str = Field(..., description="Error timestamp")


# Relationship Models
class RelationshipResponse(BaseModel):
    """Response model for discovered node relationships."""
    model_config = {"protected_namespaces": (), "from_attributes": True}

    id: int = Field(..., description="Unique relationship ID")
    run_id: str = Field(..., description="Run ID this relationship belongs to")
    source_node_type: str = Field(..., description="Source node type (e.g., PaxSegment)")
    source_section_path: str = Field(..., description="Source node section path")
    target_node_type: str = Field(..., description="Target node type (e.g., Pax)")
    target_section_path: str = Field(..., description="Target node section path")
    reference_type: str = Field(..., description="Type of reference (e.g., pax_reference)")
    reference_field: Optional[str] = Field(None, description="Field containing reference (e.g., PaxRefID)")
    reference_value: Optional[str] = Field(None, description="Actual reference value (e.g., PAX1)")
    is_valid: bool = Field(..., description="Does the reference resolve to a target node?")
    was_expected: bool = Field(..., description="Was this in expected_references config?")
    confidence: Optional[float] = Field(None, description="LLM confidence score (0.0-1.0)")
    discovered_by: Optional[str] = Field(None, description="Discovery source (llm or config)")
    model_used: Optional[str] = Field(None, description="LLM model that discovered this")
    created_at: Optional[str] = Field(None, description="When relationship was discovered")


class RelationshipStatsResponse(BaseModel):
    """Statistics about discovered relationships."""
    total_relationships: int = Field(..., description="Total number of relationships")
    valid_relationships: int = Field(..., description="Number of valid relationships")
    broken_relationships: int = Field(..., description="Number of broken relationships")
    expected_relationships: int = Field(..., description="Number of expected relationships")
    discovered_relationships: int = Field(..., description="Number of discovered relationships")
    reference_type_breakdown: Dict[str, int] = Field(..., description="Count by reference type")
    top_reference_types: List[Dict[str, Any]] = Field(..., description="Most common reference types")

    class Config:
        from_attributes = True


# Conflict Detection Schemas

class ConflictType(str, Enum):
    """Types of pattern conflicts."""
    PARENT_CHILD = "parent_child"  # Extracting parent when child patterns exist
    CHILD_PARENT = "child_parent"  # Extracting child when parent pattern exists
    SIBLING = "sibling"            # Extracting sibling at different granularity
    EXACT_MATCH_VARIATION = "exact_match_variation"  # Same path/airline/version, different structure - can enhance


class ConflictResolution(str, Enum):
    """Strategies for resolving pattern conflicts."""
    REPLACE = "replace"        # Delete conflicting patterns, keep new ones
    KEEP_BOTH = "keep_both"    # Keep both (may cause ambiguous matches)
    MERGE = "merge"            # Mark old patterns as superseded by new
    ENHANCE = "enhance"        # Add new structure as a variation to existing pattern


class ExistingPatternInfo(BaseModel):
    """Information about an existing pattern that conflicts."""
    id: int = Field(..., description="Pattern ID")
    section_path: str = Field(..., description="Pattern section path")
    times_seen: int = Field(..., description="Number of times pattern was seen")
    created_at: str = Field(..., description="When pattern was created")
    node_type: str = Field(..., description="Node type of the pattern")


class PatternConflict(BaseModel):
    """Details about a pattern conflict."""
    extracting_path: str = Field(..., description="Path being extracted")
    conflict_type: ConflictType = Field(..., description="Type of conflict")
    existing_patterns: List[ExistingPatternInfo] = Field(..., description="Conflicting patterns")
    recommendation: ConflictResolution = Field(..., description="Recommended resolution")
    impact_description: str = Field(..., description="Human-readable impact description")


class ConflictDetectionResponse(BaseModel):
    """Response from conflict detection check."""
    has_conflicts: bool = Field(..., description="Whether conflicts were detected")
    conflicts: List[PatternConflict] = Field(default_factory=list, description="List of conflicts")
    can_proceed: bool = Field(..., description="Whether extraction can proceed safely")
    warning_message: Optional[str] = Field(None, description="Warning message if conflicts exist")