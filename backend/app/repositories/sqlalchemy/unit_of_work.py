"""
SQLAlchemy Unit of Work implementation.

Manages transaction boundaries and coordinates multiple repositories.
"""

from sqlalchemy.orm import Session
from app.repositories.interfaces import IUnitOfWork
from app.repositories.sqlalchemy.run_repository import SQLAlchemyRunRepository
from app.repositories.sqlalchemy.pattern_repository import SQLAlchemyPatternRepository
from app.repositories.sqlalchemy.node_fact_repository import SQLAlchemyNodeFactRepository
from app.repositories.sqlalchemy.pattern_match_repository import SQLAlchemyPatternMatchRepository
from app.repositories.sqlalchemy.node_relationship_repository import SQLAlchemyNodeRelationshipRepository


class SQLAlchemyUnitOfWork:
    """
    SQLAlchemy implementation of Unit of Work pattern.

    Manages transaction boundaries and repository instances.
    All repositories share the same session for transactional consistency.

    Example usage:
        # Automatic transaction management
        with uow:
            run = uow.runs.create(run)
            uow.node_facts.create_batch(facts)
            # Automatically commits if no exception
            # Automatically rolls back if exception occurs

        # Manual transaction management
        try:
            uow.runs.create(run)
            uow.patterns.create(pattern)
            uow.commit()
        except Exception:
            uow.rollback()
            raise
    """

    def __init__(self, session: Session):
        """
        Initialize Unit of Work with database session.

        Args:
            session: SQLAlchemy session for transaction management
        """
        self.session = session

        # Initialize all repositories with the same session
        # This ensures transactional consistency across operations
        self.runs = SQLAlchemyRunRepository(session)
        self.patterns = SQLAlchemyPatternRepository(session)
        self.node_facts = SQLAlchemyNodeFactRepository(session)
        self.pattern_matches = SQLAlchemyPatternMatchRepository(session)
        self.node_relationships = SQLAlchemyNodeRelationshipRepository(session)

    def commit(self) -> None:
        """
        Commit all changes made through repositories.

        Raises:
            Exception: If commit fails (database error, constraint violation, etc.)
        """
        self.session.commit()

    def rollback(self) -> None:
        """
        Rollback all changes made through repositories.

        Use when an error occurs and you want to discard changes.
        """
        self.session.rollback()

    def __enter__(self) -> 'SQLAlchemyUnitOfWork':
        """
        Context manager support for automatic transaction management.

        Returns:
            Self for use in with statement

        Example:
            with uow:
                uow.runs.create(run)
                uow.node_facts.create_batch(facts)
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Automatic commit/rollback on context exit.

        Args:
            exc_type: Exception type if exception occurred
            exc_val: Exception value if exception occurred
            exc_tb: Exception traceback if exception occurred
        """
        if exc_type is not None:
            # Exception occurred - rollback
            self.rollback()
        else:
            # No exception - commit
            self.commit()
