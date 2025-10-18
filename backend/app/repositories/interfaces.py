"""
Repository interfaces (contracts) for data access.

These are database-agnostic interfaces that define WHAT operations
are supported, not HOW they're implemented.

Following the Repository Pattern and Unit of Work pattern for clean
separation between business logic and data access.
"""

from typing import Protocol, Optional, List, Dict, Any
from datetime import datetime
from app.models.database import (
    Run, RunKind, RunStatus,
    Pattern,
    NodeFact,
    PatternMatch,
    NodeRelationship
)


class IRunRepository(Protocol):
    """Interface for Run entity data access."""

    def create(self, run: Run) -> Run:
        """
        Create a new run.

        Args:
            run: Run entity to create

        Returns:
            Created run with any generated fields populated
        """
        ...

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """
        Get run by ID.

        Args:
            run_id: Unique run identifier

        Returns:
            Run if found, None otherwise
        """
        ...

    def update_status(self, run_id: str, status: RunStatus,
                     error_details: Optional[str] = None) -> None:
        """
        Update run status.

        Args:
            run_id: Run identifier
            status: New status
            error_details: Optional error message
        """
        ...

    def update_version_info(self, run_id: str, spec_version: str,
                           message_root: str,
                           airline_code: Optional[str] = None,
                           airline_name: Optional[str] = None) -> None:
        """
        Update run with detected version information.

        Args:
            run_id: Run identifier
            spec_version: NDC spec version (e.g., "17.2")
            message_root: Message type (e.g., "OrderViewRS")
            airline_code: Optional airline code
            airline_name: Optional airline name
        """
        ...

    def list_recent(self, limit: int = 10,
                   kind: Optional[RunKind] = None) -> List[Run]:
        """
        List recent runs.

        Args:
            limit: Maximum number of runs to return
            kind: Optional filter by run kind (DISCOVERY or IDENTIFY)

        Returns:
            List of recent runs, ordered by started_at descending
        """
        ...


class IPatternRepository(Protocol):
    """Interface for Pattern entity data access."""

    def create(self, pattern: Pattern) -> Pattern:
        """
        Create a new pattern.

        Args:
            pattern: Pattern entity to create

        Returns:
            Created pattern with generated ID
        """
        ...

    def get_by_id(self, pattern_id: int) -> Optional[Pattern]:
        """
        Get pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Pattern if found, None otherwise
        """
        ...

    def find_by_signature(self, spec_version: str, message_root: str,
                         airline_code: Optional[str],
                         signature_hash: str) -> Optional[Pattern]:
        """
        Find pattern by signature hash.

        Args:
            spec_version: NDC spec version
            message_root: Message type
            airline_code: Airline code (or None for generic)
            signature_hash: Pattern signature hash

        Returns:
            Matching pattern if found, None otherwise
        """
        ...

    def list_by_version(self, spec_version: str, message_root: str,
                       airline_code: Optional[str] = None) -> List[Pattern]:
        """
        List all patterns for a version/message/airline.

        Args:
            spec_version: NDC spec version
            message_root: Message type
            airline_code: Optional airline code filter

        Returns:
            List of matching patterns
        """
        ...

    def increment_times_seen(self, pattern_id: int,
                           example_node_fact_id: int) -> None:
        """
        Increment times_seen counter and add example.

        Args:
            pattern_id: Pattern identifier
            example_node_fact_id: NodeFact ID to add as example
        """
        ...


class INodeFactRepository(Protocol):
    """Interface for NodeFact entity data access."""

    def create(self, node_fact: NodeFact) -> NodeFact:
        """
        Create a new node fact.

        Args:
            node_fact: NodeFact entity to create

        Returns:
            Created node fact with generated ID
        """
        ...

    def create_batch(self, node_facts: List[NodeFact]) -> List[NodeFact]:
        """
        Create multiple node facts efficiently (bulk insert).

        Args:
            node_facts: List of NodeFact entities to create

        Returns:
            Created node facts with generated IDs
        """
        ...

    def get_by_id(self, node_fact_id: int) -> Optional[NodeFact]:
        """
        Get node fact by ID.

        Args:
            node_fact_id: NodeFact identifier

        Returns:
            NodeFact if found, None otherwise
        """
        ...

    def list_by_run(self, run_id: str) -> List[NodeFact]:
        """
        List all node facts for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of node facts for the run
        """
        ...

    def count_by_run(self, run_id: str) -> int:
        """
        Count node facts for a run.

        Args:
            run_id: Run identifier

        Returns:
            Number of node facts in the run
        """
        ...


class IPatternMatchRepository(Protocol):
    """Interface for PatternMatch entity data access."""

    def create(self, pattern_match: PatternMatch) -> PatternMatch:
        """
        Store a pattern match result.

        Args:
            pattern_match: PatternMatch entity to create

        Returns:
            Created pattern match with generated ID
        """
        ...

    def list_by_run(self, run_id: str) -> List[PatternMatch]:
        """
        List all pattern matches for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of pattern matches for the run
        """
        ...

    def get_match_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get aggregated match statistics for a run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with statistics (match_rate, verdict counts, etc.)
        """
        ...


class INodeRelationshipRepository(Protocol):
    """Interface for NodeRelationship entity data access."""

    def create(self, relationship: NodeRelationship) -> NodeRelationship:
        """
        Create a new node relationship.

        Args:
            relationship: NodeRelationship entity to create

        Returns:
            Created relationship with generated ID
        """
        ...

    def create_batch(self, relationships: List[NodeRelationship]) -> List[NodeRelationship]:
        """
        Create multiple relationships efficiently (bulk insert).

        Args:
            relationships: List of NodeRelationship entities to create

        Returns:
            Created relationships with generated IDs
        """
        ...

    def list_by_run(self, run_id: str) -> List[NodeRelationship]:
        """
        List all relationships for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of relationships discovered in the run
        """
        ...

    def list_broken_for_node(self, node_fact_id: int) -> List[NodeRelationship]:
        """
        List broken relationships for a specific node fact.

        Args:
            node_fact_id: NodeFact identifier

        Returns:
            List of broken relationships where this node is the source
        """
        ...


class IUnitOfWork(Protocol):
    """
    Unit of Work pattern - manages transactions.

    Ensures all repository operations in a workflow are atomic.
    Provides access to all repositories through a single interface.
    """

    # Repository instances
    runs: IRunRepository
    patterns: IPatternRepository
    node_facts: INodeFactRepository
    pattern_matches: IPatternMatchRepository
    node_relationships: INodeRelationshipRepository

    def commit(self) -> None:
        """
        Commit all changes made through repositories.

        Raises:
            Exception: If commit fails (database error, constraint violation, etc.)
        """
        ...

    def rollback(self) -> None:
        """
        Rollback all changes made through repositories.

        Use when an error occurs and you want to discard changes.
        """
        ...

    def __enter__(self) -> 'IUnitOfWork':
        """
        Context manager support for automatic transaction management.

        Example:
            with uow:
                uow.runs.create(run)
                uow.node_facts.create_batch(facts)
                # Automatically commits if no exception
                # Automatically rolls back if exception occurs
        """
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Automatic commit/rollback on context exit."""
        ...
