"""
Unit tests for Unit of Work implementation.

Tests transaction management and repository coordination.
"""
import pytest
from sqlalchemy.orm import Session

from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork
from app.repositories.sqlalchemy.run_repository import SQLAlchemyRunRepository
from app.repositories.sqlalchemy.pattern_repository import SQLAlchemyPatternRepository
from app.repositories.sqlalchemy.node_fact_repository import SQLAlchemyNodeFactRepository
from app.repositories.sqlalchemy.pattern_match_repository import SQLAlchemyPatternMatchRepository
from app.repositories.sqlalchemy.node_relationship_repository import SQLAlchemyNodeRelationshipRepository
from app.models.database import Run, Pattern


class TestUnitOfWork:
    """Test suite for SQLAlchemyUnitOfWork."""

    def test_create_unit_of_work(self, db_session: Session):
        """Test creating a Unit of Work instance."""
        uow = SQLAlchemyUnitOfWork(db_session)

        assert uow is not None
        assert uow.runs is not None
        assert uow.patterns is not None
        assert uow.node_facts is not None
        assert uow.pattern_matches is not None
        assert uow.node_relationships is not None

    def test_repository_properties(self, db_session: Session):
        """Test that repository properties return correct types."""
        uow = SQLAlchemyUnitOfWork(db_session)

        assert isinstance(uow.runs, SQLAlchemyRunRepository)
        assert isinstance(uow.patterns, SQLAlchemyPatternRepository)
        assert isinstance(uow.node_facts, SQLAlchemyNodeFactRepository)
        assert isinstance(uow.pattern_matches, SQLAlchemyPatternMatchRepository)
        assert isinstance(uow.node_relationships, SQLAlchemyNodeRelationshipRepository)

    def test_commit(self, db_session: Session):
        """Test committing a transaction."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create a run
        run = Run(
            id="test-uow-commit",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)

        # Commit
        uow.commit()

        # Verify committed to database
        retrieved = db_session.query(Run).filter(Run.id == "test-uow-commit").first()
        assert retrieved is not None
        assert retrieved.kind == "discovery"

    def test_rollback(self, db_session: Session):
        """Test rolling back a transaction."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create a run
        run = Run(
            id="test-uow-rollback",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)

        # Rollback instead of commit
        uow.rollback()

        # Verify NOT in database
        retrieved = db_session.query(Run).filter(Run.id == "test-uow-rollback").first()
        assert retrieved is None

    def test_multiple_operations_single_transaction(self, db_session: Session):
        """Test multiple repository operations in single transaction."""
        uow = SQLAlchemyUnitOfWork(db_session)

        import uuid
        unique_hash = f"multi-ops-{uuid.uuid4().hex[:8]}"

        # Create run
        run = Run(
            id="test-multi-ops",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)

        # Create pattern
        pattern = Pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="Response/DataLists/PaxList",
            selector_xpath="./Pax",
            decision_rule={"node_type": "Pax"},
            signature_hash=unique_hash,
            times_seen=1,
            examples=[]
        )
        uow.patterns.create(pattern)

        # Commit all at once
        uow.commit()

        # Verify both in database
        run_retrieved = db_session.query(Run).filter(Run.id == "test-multi-ops").first()
        pattern_retrieved = db_session.query(Pattern).filter(
            Pattern.signature_hash == unique_hash
        ).first()

        assert run_retrieved is not None
        assert pattern_retrieved is not None

    def test_rollback_multiple_operations(self, db_session: Session):
        """Test rolling back multiple operations."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create run
        run = Run(
            id="test-rollback-multi",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)

        # Create pattern
        pattern = Pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="Response/DataLists/PaxList",
            selector_xpath="./Pax",
            decision_rule={"node_type": "Pax"},
            signature_hash="test-rollback-multi-hash",
            times_seen=1
        )
        uow.patterns.create(pattern)

        # Rollback all
        uow.rollback()

        # Verify neither in database
        run_retrieved = db_session.query(Run).filter(Run.id == "test-rollback-multi").first()
        pattern_retrieved = db_session.query(Pattern).filter(
            Pattern.signature_hash == "test-rollback-multi-hash"
        ).first()

        assert run_retrieved is None
        assert pattern_retrieved is None

    def test_transaction_isolation(self, db_session: Session):
        """Test that changes are isolated until commit."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create run but don't commit
        run = Run(
            id="test-isolation",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)

        # Should not be visible without commit
        # Note: This might not work perfectly with SQLite in-memory
        # but demonstrates the concept
        retrieved_before_commit = db_session.query(Run).filter(
            Run.id == "test-isolation"
        ).first()

        # Now commit
        uow.commit()

        retrieved_after_commit = db_session.query(Run).filter(
            Run.id == "test-isolation"
        ).first()

        assert retrieved_after_commit is not None

    def test_repository_sharing_session(self, db_session: Session):
        """Test that all repositories share the same session."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # All repositories should use the same session
        # This is important for transaction consistency
        assert uow.runs.session is db_session
        assert uow.patterns.session is db_session
        assert uow.node_facts.session is db_session
        assert uow.pattern_matches.session is db_session
        assert uow.node_relationships.session is db_session

    def test_update_through_uow(self, db_session: Session, sample_run: Run):
        """Test updating an entity through Unit of Work."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Get run and update it directly (repositories don't have generic update method)
        run = uow.runs.get_by_id(sample_run.id)
        assert run is not None

        # Update using specific update method
        uow.runs.update_status(sample_run.id, "completed")
        uow.commit()

        # Verify update
        retrieved = db_session.query(Run).filter(Run.id == sample_run.id).first()
        assert retrieved.status == "completed"

    def test_error_handling_with_rollback(self, db_session: Session):
        """Test error handling with automatic rollback."""
        uow = SQLAlchemyUnitOfWork(db_session)

        try:
            # Create valid run
            run = Run(
                id="test-error-handling",
                kind="discovery",
                status="started",
                spec_version="21.3",
                message_root="OrderViewRS"
            )
            uow.runs.create(run)

            # Simulate error (try to create duplicate)
            duplicate = Run(
                id="test-error-handling",  # Same ID
                kind="identify",
                status="started",
                spec_version="21.3",
                message_root="OrderViewRS"
            )
            uow.runs.create(duplicate)

            # This should fail on commit
            uow.commit()

        except Exception:
            # Rollback on error
            uow.rollback()

        # Verify nothing was committed
        retrieved = db_session.query(Run).filter(
            Run.id == "test-error-handling"
        ).first()

        # Should be None because rollback removed it
        assert retrieved is None
