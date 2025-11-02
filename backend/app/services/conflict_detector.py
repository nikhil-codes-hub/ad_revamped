"""
Pattern Conflict Detection Service.

Detects conflicts when extracting patterns at different granularities
(e.g., extracting /PaxList when /PaxList/Pax patterns already exist).
"""

import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session

from app.models.database import Pattern
from app.models.schemas import (
    ConflictDetectionResponse,
    PatternConflict,
    ExistingPatternInfo,
    ConflictType,
    ConflictResolution
)
from app.services.utils import normalize_iata_prefix

logger = logging.getLogger(__name__)


class ConflictDetector:
    """Detects pattern conflicts before extraction."""

    def __init__(self, db_session: Session):
        """Initialize conflict detector with database session."""
        self.db_session = db_session

    def _normalize_path(self, path: str, message_root: str) -> str:
        """
        Normalize a path by removing IATA_ prefix and stripping slashes.

        Args:
            path: Path to normalize (e.g., "IATA_AirShoppingRS/Response/DataLists/PaxList")
            message_root: Message root (e.g., "AirShoppingRS")

        Returns:
            Normalized path (e.g., "AirShoppingRS/Response/DataLists/PaxList")
        """
        # Remove IATA_ prefix if present
        normalized = normalize_iata_prefix(path, message_root)
        # Strip leading/trailing slashes
        return normalized.strip('/').rstrip('/')

    def _is_parent_path(self, parent_path: str, child_path: str, message_root: str) -> bool:
        """Check if parent_path is a parent of child_path."""
        # Normalize both paths to handle IATA_ prefix differences
        parent = self._normalize_path(parent_path, message_root)
        child = self._normalize_path(child_path, message_root)

        # Child must start with parent and have additional segments
        return child.startswith(parent + '/')

    def _is_child_path(self, child_path: str, parent_path: str, message_root: str) -> bool:
        """Check if child_path is a child of parent_path."""
        return self._is_parent_path(parent_path, child_path, message_root)

    def check_conflicts(
        self,
        extracting_paths: List[str],
        spec_version: str,
        message_root: str,
        airline_code: Optional[str] = None
    ) -> ConflictDetectionResponse:
        """
        Check for pattern conflicts before extraction.

        Args:
            extracting_paths: List of section paths to be extracted
            spec_version: NDC version
            message_root: Message type (e.g., AirShoppingRS)
            airline_code: Airline code (optional)

        Returns:
            ConflictDetectionResponse with detected conflicts
        """
        logger.info(f"Checking conflicts for {len(extracting_paths)} paths in {message_root} {spec_version}")
        logger.info(f"Extracting paths: {extracting_paths}")

        conflicts = []

        # Get all existing patterns for this spec_version and message_root
        query = self.db_session.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.superseded_by.is_(None)  # Only active patterns
        )

        if airline_code:
            query = query.filter(Pattern.airline_code == airline_code)

        existing_patterns = query.all()

        logger.info(f"Found {len(existing_patterns)} existing active patterns")
        if existing_patterns:
            logger.info(f"Existing pattern paths: {[p.section_path for p in existing_patterns]}")

        # Check each path being extracted
        for extracting_path in extracting_paths:
            # Normalize path (removes IATA_ prefix if present)
            normalized_extracting_path = self._normalize_path(extracting_path, message_root)

            # Check for parent-child conflicts
            parent_conflicts = []  # Extracting parent when child patterns exist
            child_conflicts = []   # Extracting child when parent pattern exists

            for pattern in existing_patterns:
                # Normalize pattern path (removes IATA_ prefix if present)
                normalized_pattern_path = self._normalize_path(pattern.section_path, message_root)

                # Check if we're extracting a parent of an existing pattern
                if self._is_parent_path(normalized_extracting_path, normalized_pattern_path, message_root):
                    parent_conflicts.append(pattern)

                # Check if we're extracting a child of an existing pattern
                elif self._is_child_path(normalized_extracting_path, normalized_pattern_path, message_root):
                    child_conflicts.append(pattern)

            # Create conflict entries
            if parent_conflicts:
                logger.info(f"Parent-child conflict: extracting '{normalized_extracting_path}' conflicts with {len(parent_conflicts)} child pattern(s)")
                conflicts.append(self._create_parent_child_conflict(
                    extracting_path=extracting_path,
                    existing_patterns=parent_conflicts
                ))

            if child_conflicts:
                logger.info(f"Child-parent conflict: extracting '{normalized_extracting_path}' conflicts with {len(child_conflicts)} parent pattern(s)")
                conflicts.append(self._create_child_parent_conflict(
                    extracting_path=extracting_path,
                    existing_patterns=child_conflicts
                ))

        # Build response
        has_conflicts = len(conflicts) > 0
        warning_message = None

        if has_conflicts:
            conflict_count = len(conflicts)
            warning_message = (
                f"Found {conflict_count} pattern conflict(s). "
                f"Extracting these paths will create overlapping patterns. "
                f"Please choose a conflict resolution strategy."
            )

        return ConflictDetectionResponse(
            has_conflicts=has_conflicts,
            conflicts=conflicts,
            can_proceed=True,  # Can always proceed with user's choice
            warning_message=warning_message
        )

    def _create_parent_child_conflict(
        self,
        extracting_path: str,
        existing_patterns: List[Pattern]
    ) -> PatternConflict:
        """Create conflict for extracting parent when child patterns exist."""
        existing_info = [
            ExistingPatternInfo(
                id=p.id,
                section_path=p.section_path,
                times_seen=p.times_seen,
                created_at=p.created_at.isoformat() if p.created_at else "",
                node_type=p.decision_rule.get('node_type', 'Unknown') if p.decision_rule else 'Unknown'
            )
            for p in existing_patterns
        ]

        # Extract child node names for impact description
        child_names = ", ".join(set(p.section_path.split('/')[-1] for p in existing_patterns[:3]))
        if len(existing_patterns) > 3:
            child_names += f" (and {len(existing_patterns) - 3} more)"

        impact_description = (
            f"Extracting parent container '{extracting_path}' will create patterns that overlap with "
            f"existing child patterns ({child_names}). Child patterns may become redundant."
        )

        return PatternConflict(
            extracting_path=extracting_path,
            conflict_type=ConflictType.PARENT_CHILD,
            existing_patterns=existing_info,
            recommendation=ConflictResolution.REPLACE,  # Replace child patterns with parent
            impact_description=impact_description
        )

    def _create_child_parent_conflict(
        self,
        extracting_path: str,
        existing_patterns: List[Pattern]
    ) -> PatternConflict:
        """Create conflict for extracting child when parent pattern exists."""
        existing_info = [
            ExistingPatternInfo(
                id=p.id,
                section_path=p.section_path,
                times_seen=p.times_seen,
                created_at=p.created_at.isoformat() if p.created_at else "",
                node_type=p.decision_rule.get('node_type', 'Unknown') if p.decision_rule else 'Unknown'
            )
            for p in existing_patterns
        ]

        parent_names = ", ".join(set(p.section_path.split('/')[-1] for p in existing_patterns[:3]))
        if len(existing_patterns) > 3:
            parent_names += f" (and {len(existing_patterns) - 3} more)"

        impact_description = (
            f"Extracting child element '{extracting_path}' will create patterns that overlap with "
            f"existing parent container patterns ({parent_names}). May cause ambiguous matches during Discovery."
        )

        return PatternConflict(
            extracting_path=extracting_path,
            conflict_type=ConflictType.CHILD_PARENT,
            existing_patterns=existing_info,
            recommendation=ConflictResolution.KEEP_BOTH,  # Usually keep both, but warn user
            impact_description=impact_description
        )

    def resolve_conflicts(
        self,
        conflicts: List[PatternConflict],
        resolution_strategy: ConflictResolution
    ) -> Dict[str, Any]:
        """
        Apply conflict resolution strategy.

        Args:
            conflicts: List of conflicts to resolve
            resolution_strategy: Strategy to apply (REPLACE, KEEP_BOTH, MERGE)

        Returns:
            Dict with counts of patterns affected and list of patterns to supersede
        """
        patterns_superseded = 0
        patterns_deleted = 0
        patterns_to_supersede = []  # List of (pattern_id, extracting_path) tuples

        for conflict in conflicts:
            pattern_ids = [p.id for p in conflict.existing_patterns]

            if resolution_strategy == ConflictResolution.REPLACE:
                # Delete existing patterns
                deleted = self.db_session.query(Pattern).filter(
                    Pattern.id.in_(pattern_ids)
                ).delete(synchronize_session=False)
                patterns_deleted += deleted
                logger.info(f"Deleted {deleted} conflicting patterns for {conflict.extracting_path}")

            elif resolution_strategy == ConflictResolution.MERGE:
                # Store pattern IDs to be superseded after new pattern is created
                for pattern_id in pattern_ids:
                    patterns_to_supersede.append({
                        'pattern_id': pattern_id,
                        'extracting_path': conflict.extracting_path
                    })
                patterns_superseded += len(pattern_ids)
                logger.info(f"Will supersede {len(pattern_ids)} patterns for {conflict.extracting_path}")

            elif resolution_strategy == ConflictResolution.KEEP_BOTH:
                # Do nothing - keep both patterns
                logger.info(f"Keeping both new and existing patterns for {conflict.extracting_path}")

        if patterns_deleted > 0:
            self.db_session.commit()

        return {
            "patterns_deleted": patterns_deleted,
            "patterns_superseded": patterns_superseded,
            "patterns_to_supersede": patterns_to_supersede
        }


def create_conflict_detector(db_session: Session) -> ConflictDetector:
    """Create conflict detector instance."""
    return ConflictDetector(db_session)
