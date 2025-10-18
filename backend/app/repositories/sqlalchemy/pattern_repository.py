"""SQLAlchemy implementation of IPatternRepository."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.database import Pattern
from app.repositories.interfaces import IPatternRepository


class SQLAlchemyPatternRepository:
    """SQLAlchemy implementation for Pattern entity."""

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def create(self, pattern: Pattern) -> Pattern:
        """
        Create a new pattern.

        Args:
            pattern: Pattern entity to create

        Returns:
            Created pattern

        Note:
            Does not commit - let UnitOfWork handle transaction management
        """
        self.session.add(pattern)
        return pattern

    def get_by_id(self, pattern_id: int) -> Optional[Pattern]:
        """
        Get pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Pattern if found, None otherwise
        """
        return self.session.query(Pattern).filter(Pattern.id == pattern_id).first()

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
        query = self.session.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root,
            Pattern.airline_code == airline_code,
            Pattern.signature_hash == signature_hash
        )
        return query.first()

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
        query = self.session.query(Pattern).filter(
            Pattern.spec_version == spec_version,
            Pattern.message_root == message_root
        )
        if airline_code:
            query = query.filter(Pattern.airline_code == airline_code)
        return query.all()

    def increment_times_seen(self, pattern_id: int,
                           example_node_fact_id: int) -> None:
        """
        Increment times_seen counter and add example.

        Args:
            pattern_id: Pattern identifier
            example_node_fact_id: NodeFact ID to add as example
        """
        pattern = self.get_by_id(pattern_id)
        if pattern:
            pattern.times_seen += 1
            pattern.last_seen_at = datetime.utcnow()

            # Add new example (keep last 5)
            examples = pattern.examples or []
            examples.append({
                'node_fact_id': example_node_fact_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            pattern.examples = examples[-5:]  # Keep last 5 examples
