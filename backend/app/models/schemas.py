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
    DISCOVERY = "discovery"
    IDENTIFY = "identify"


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
    node_facts_count: Optional[int] = Field(None, description="Number of node facts extracted")
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
    signature_hash: str = Field(..., description="Unique signature hash")
    times_seen: int = Field(..., description="Times pattern was discovered")
    created_by_model: Optional[str] = Field(None, description="LLM model that created pattern")
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Example matches")
    created_at: str = Field(..., description="When pattern was created (ISO format)")
    last_seen_at: str = Field(..., description="When pattern was last seen (ISO format)")

    class Config:
        from_attributes = True


class PatternMatchResponse(BaseModel):
    """Response model for pattern matches."""
    id: int = Field(..., description="Unique match identifier")
    run_id: str = Field(..., description="Associated run ID")
    node_fact_id: int = Field(..., description="Node fact that was matched")
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
class NdcTargetPathResponse(BaseModel):
    """Response model for target path configuration."""
    id: int = Field(..., description="Unique identifier")
    spec_version: str = Field(..., description="NDC version")
    message_root: str = Field(..., description="Message root element")
    path_local: str = Field(..., description="Local path")
    extractor_key: str = Field(..., description="Extractor type")
    is_required: bool = Field(..., description="Whether section is required")
    importance: ImportanceLevel = Field(..., description="Section importance")
    constraints_json: Optional[Dict[str, Any]] = Field(None, description="Validation constraints")
    notes: Optional[str] = Field(None, description="Description and notes")

    class Config:
        from_attributes = True


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