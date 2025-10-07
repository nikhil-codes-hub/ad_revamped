"""
Database models for AssistedDiscovery.

SQLAlchemy ORM models matching the MySQL schema design.
Designed with future CouchDB migration in mind.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, DECIMAL, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class ImportanceLevel(str, Enum):
    """Importance levels for target paths."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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


class Verdict(str, Enum):
    """Pattern matching verdicts."""
    MATCH = "match"
    NO_MATCH = "no_match"
    UNCERTAIN = "uncertain"


class NdcTargetPath(Base):
    """Configuration for target XML paths per NDC version."""

    __tablename__ = "ndc_target_paths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    spec_version = Column(String(10), nullable=False, comment="NDC specification version")
    message_root = Column(String(100), nullable=False, comment="Root element name")
    path_local = Column(Text, nullable=False, comment="Local-name path for targeting")
    extractor_key = Column(String(50), nullable=False, comment="template or generic_llm")
    is_required = Column(Boolean, default=False, comment="Whether this section is required")
    importance = Column(String(20), default=ImportanceLevel.MEDIUM, comment="Section importance level")
    constraints_json = Column(JSON, comment="Validation constraints and rules")
    notes = Column(Text, comment="Human-readable description and notes")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<NdcTargetPath({self.spec_version}/{self.message_root}: {self.path_local})>"


class NdcPathAlias(Base):
    """Path aliases for cross-version compatibility."""

    __tablename__ = "ndc_path_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_spec_version = Column(String(10), nullable=False, comment="Source NDC version")
    from_message_root = Column(String(100), nullable=False, comment="Source message type")
    from_path_local = Column(Text, nullable=False, comment="Source path")
    to_spec_version = Column(String(10), nullable=False, comment="Target NDC version")
    to_message_root = Column(String(100), nullable=False, comment="Target message type")
    to_path_local = Column(Text, nullable=False, comment="Target path")
    is_bidirectional = Column(Boolean, default=False, comment="Whether alias works both ways")
    reason = Column(String(255), comment="Reason for the alias")
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<NdcPathAlias({self.from_spec_version} -> {self.to_spec_version}: {self.from_path_local})>"


class Run(Base):
    """Tracking table for all processing runs."""

    __tablename__ = "runs"

    id = Column(String(50), primary_key=True, comment="Unique run identifier")
    kind = Column(String(20), nullable=False, comment="Type of processing run")
    status = Column(String(20), default=RunStatus.STARTED, comment="Current run status")
    spec_version = Column(String(10), comment="Detected NDC version")
    message_root = Column(String(100), comment="Detected message root element")
    airline_code = Column(String(10), comment="Detected airline code (e.g., SQ, AF)")
    airline_name = Column(String(200), comment="Detected airline name")
    filename = Column(String(255), comment="Original uploaded filename")
    file_size_bytes = Column(BigInteger, comment="File size in bytes")
    file_hash = Column(String(64), comment="SHA-256 hash of uploaded file")
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, comment="When run completed")
    metadata_json = Column(JSON, comment="Additional run metadata and configuration")
    error_details = Column(Text, comment="Error information if run failed")

    # Relationships
    node_facts = relationship("NodeFact", back_populates="run", cascade="all, delete-orphan")
    association_facts = relationship("AssociationFact", back_populates="run", cascade="all, delete-orphan")
    node_relationships = relationship("NodeRelationship", back_populates="run", cascade="all, delete-orphan")
    pattern_matches = relationship("PatternMatch", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Run({self.id}: {self.kind} - {self.status})>"

    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate run duration in seconds."""
        if self.started_at:
            end_time = self.finished_at or datetime.utcnow()
            return int((end_time - self.started_at).total_seconds())
        return None

    @property
    def is_completed(self) -> bool:
        """Check if run is in a completed state."""
        return self.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.PARTIAL_FAILURE]


class NodeFact(Base):
    """Extracted and masked node facts from XML processing."""

    __tablename__ = "node_facts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    spec_version = Column(String(10), nullable=False, comment="NDC version for this fact")
    message_root = Column(String(100), nullable=False, comment="Message type")
    section_path = Column(String(500), nullable=False, comment="XML section path where node was found")
    node_type = Column(String(100), nullable=False, comment="Type of node")
    node_ordinal = Column(Integer, nullable=False, comment="Position within section")
    fact_json = Column(JSON, nullable=False, comment="Structured NodeFact data with PII masking")
    pii_masked = Column(Boolean, default=False, comment="Whether PII masking was applied")
    created_at = Column(DateTime, default=func.now())

    # Relationships
    run = relationship("Run", back_populates="node_facts")
    from_associations = relationship("AssociationFact", foreign_keys="[AssociationFact.from_node_fact_id]", back_populates="from_node")
    to_associations = relationship("AssociationFact", foreign_keys="[AssociationFact.to_node_fact_id]", back_populates="to_node")
    pattern_matches = relationship("PatternMatch", back_populates="node_fact")

    def __repr__(self):
        return f"<NodeFact({self.id}: {self.node_type} in {self.section_path})>"


class AssociationFact(Base):
    """Relationships and references between node facts."""

    __tablename__ = "association_facts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    rel_type = Column(String(50), nullable=False, comment="Type of relationship")
    from_node_fact_id = Column(BigInteger, ForeignKey("node_facts.id", ondelete="CASCADE"), nullable=False)
    to_node_fact_id = Column(BigInteger, ForeignKey("node_facts.id", ondelete="CASCADE"), nullable=False)
    from_node_type = Column(String(100), nullable=False, comment="Source node type")
    to_node_type = Column(String(100), nullable=False, comment="Target node type")
    ref_key = Column(String(100), comment="Reference key/attribute name")
    created_at = Column(DateTime, default=func.now())

    # Relationships
    run = relationship("Run", back_populates="association_facts")
    from_node = relationship("NodeFact", foreign_keys=[from_node_fact_id], back_populates="from_associations")
    to_node = relationship("NodeFact", foreign_keys=[to_node_fact_id], back_populates="to_associations")

    def __repr__(self):
        return f"<AssociationFact({self.rel_type}: {self.from_node_type} -> {self.to_node_type})>"


class NodeRelationship(Base):
    """LLM-discovered and validated relationships between nodes with metadata."""

    __tablename__ = "node_relationships"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)

    # Source node (contains the reference)
    source_node_fact_id = Column(BigInteger, ForeignKey("node_facts.id", ondelete="CASCADE"), nullable=False)
    source_node_type = Column(String(255), nullable=False)
    source_section_path = Column(String(500), nullable=False)

    # Target node (being referenced)
    target_node_fact_id = Column(BigInteger, ForeignKey("node_facts.id", ondelete="CASCADE"), nullable=True, comment="NULL if reference is broken")
    target_node_type = Column(String(255), nullable=False)
    target_section_path = Column(String(500), nullable=False)

    # Relationship details
    reference_type = Column(String(100), nullable=False, comment="e.g., 'pax_reference', 'segment_reference', 'infant_parent'")
    reference_field = Column(String(255), comment="Field containing reference, e.g., 'PaxRefID'")
    reference_value = Column(String(255), comment="Actual reference value, e.g., 'PAX1'")

    # Validation and discovery metadata
    is_valid = Column(Boolean, default=True, comment="Does reference resolve to target?")
    was_expected = Column(Boolean, default=False, comment="Was this in expected_references?")
    confidence = Column(DECIMAL(3, 2), default=1.0, comment="LLM confidence (0.0-1.0)")

    # Discovery source
    discovered_by = Column(String(50), default='llm', comment="'llm' or 'config'")
    model_used = Column(String(100), comment="LLM model that discovered this")

    created_at = Column(DateTime, default=func.now())

    # Relationships
    run = relationship("Run", back_populates="node_relationships")
    source_node = relationship("NodeFact", foreign_keys=[source_node_fact_id])
    target_node = relationship("NodeFact", foreign_keys=[target_node_fact_id])

    def __repr__(self):
        status = "✓" if self.is_valid else "✗"
        expected = "[expected]" if self.was_expected else "[discovered]"
        return f"<NodeRelationship({status} {self.reference_type} {expected}: {self.source_node_type} -> {self.target_node_type})>"


class Pattern(Base):
    """Discovered patterns for XML node classification."""

    __tablename__ = "patterns"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    spec_version = Column(String(10), nullable=False, comment="NDC version this pattern applies to")
    message_root = Column(String(100), nullable=False, comment="Message type")
    airline_code = Column(String(10), comment="Airline code this pattern belongs to (e.g., SQ, AF, QF)")
    section_path = Column(String(500), nullable=False, comment="XML section where pattern was found")
    selector_xpath = Column(Text, nullable=False, comment="XPath selector for matching nodes")
    decision_rule = Column(JSON, nullable=False, comment="Rule for determining pattern matches")
    description = Column(Text, comment="Human-readable pattern description")
    signature_hash = Column(String(64), unique=True, nullable=False, comment="SHA-256 hash for deduplication")
    times_seen = Column(Integer, default=1, comment="Number of times this pattern was discovered")
    created_by_model = Column(String(50), comment="LLM model that created this pattern")
    examples = Column(JSON, comment="Masked examples of nodes matching this pattern")
    created_at = Column(DateTime, default=func.now())
    last_seen_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    pattern_matches = relationship("PatternMatch", back_populates="pattern")

    def __repr__(self):
        return f"<Pattern({self.id}: {self.selector_xpath} in {self.section_path})>"

    @property
    def match_count(self) -> int:
        """Get total number of matches for this pattern."""
        return len(self.pattern_matches)


class PatternMatch(Base):
    """Results of pattern matching during identify runs."""

    __tablename__ = "pattern_matches"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    node_fact_id = Column(BigInteger, ForeignKey("node_facts.id", ondelete="CASCADE"), nullable=False)
    pattern_id = Column(BigInteger, ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False)
    confidence = Column(DECIMAL(4, 3), nullable=False, comment="Confidence score 0.000-1.000")
    verdict = Column(String(20), nullable=False, comment="Classification verdict")
    match_metadata = Column(JSON, comment="Additional matching details and scores")
    created_at = Column(DateTime, default=func.now())

    # Relationships
    run = relationship("Run", back_populates="pattern_matches")
    node_fact = relationship("NodeFact", back_populates="pattern_matches")
    pattern = relationship("Pattern", back_populates="pattern_matches")

    def __repr__(self):
        return f"<PatternMatch({self.id}: {self.verdict} with {self.confidence} confidence)>"

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence match."""
        return float(self.confidence) >= 0.8

    @property
    def is_definitive(self) -> bool:
        """Check if this is a definitive match above threshold."""
        return float(self.confidence) >= 0.7 and self.verdict == Verdict.MATCH


class NodeConfiguration(Base):
    """BA-managed configuration for node extraction and pattern generation."""

    __tablename__ = "node_configurations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    spec_version = Column(String(10), nullable=False, comment="NDC specification version (e.g., 18.1, 21.3)")
    message_root = Column(String(100), nullable=False, comment="Message type (e.g., OrderViewRS)")
    airline_code = Column(String(10), comment="Airline code (NULL = applies to all airlines)")
    node_type = Column(String(100), nullable=False, comment="Node type name (e.g., PaxList, BaggageAllowanceList)")
    section_path = Column(String(500), nullable=False, comment="Full XML path to this node")
    enabled = Column(Boolean, default=True, comment="Should this node be extracted during Discovery?")
    expected_references = Column(JSON, comment="Array of reference types expected (e.g., ['infant_parent', 'segment_reference'])")
    ba_remarks = Column(Text, comment="Business analyst notes and instructions")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(100), comment="User who created/updated this configuration")

    def __repr__(self):
        return f"<NodeConfiguration({self.id}: {self.node_type} at {self.section_path})>"

    @property
    def reference_types(self) -> List[str]:
        """Get list of expected reference types."""
        if self.expected_references and isinstance(self.expected_references, list):
            return self.expected_references
        return []

    @property
    def applies_to_airline(self) -> str:
        """Get airline scope description."""
        return self.airline_code if self.airline_code else "All airlines"


class ReferenceType(Base):
    """Glossary of reference types used in NDC XML node relationships."""

    __tablename__ = "reference_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_type = Column(String(100), nullable=False, unique=True, comment="Unique reference type identifier")
    display_name = Column(String(200), nullable=False, comment="Human-readable display name")
    description = Column(Text, nullable=False, comment="Description of what this reference represents")
    example = Column(String(500), comment="Example of this reference type")
    category = Column(String(50), comment="Category: passenger, segment, journey, baggage, price, service")
    is_active = Column(Boolean, default=True, comment="Whether this reference type is active")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(100), comment="User who created this reference type")

    def __repr__(self):
        return f"<ReferenceType({self.reference_type}: {self.display_name})>"

    @property
    def full_description(self) -> str:
        """Get full description with example."""
        desc = self.description
        if self.example:
            desc += f"\n\nExample: {self.example}"
        return desc