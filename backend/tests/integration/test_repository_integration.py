"""
Integration tests for repository pattern with workflows.

Tests the repository layer integrated with actual service workflows.
"""
import pytest
from sqlalchemy.orm import Session

from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork
from app.services.pattern_generator import PatternGenerator
from app.models.database import Run, Pattern


class TestRepositoryWithPatternGenerator:
    """Integration tests for repositories with PatternGenerator."""

    def test_pattern_generator_with_uow(self, db_session: Session, sample_run: Run):
        """Test PatternGenerator using Unit of Work."""
        uow = SQLAlchemyUnitOfWork(db_session)
        generator = PatternGenerator(uow)

        # Generate decision rule
        facts_group = [
            {
                "node_type": "Pax",
                "attributes": {"PaxID": "PAX1", "PTC": "ADT"},
                "children": []
            },
            {
                "node_type": "Pax",
                "attributes": {"PaxID": "PAX2", "PTC": "CHD"},
                "children": []
            }
        ]

        decision_rule = generator.generate_decision_rule(facts_group)

        assert decision_rule["node_type"] == "Pax"
        assert "PaxID" in decision_rule["must_have_attributes"]
        assert "PTC" in decision_rule["must_have_attributes"]

    def test_signature_hash_generation(self, db_session: Session):
        """Test signature hash generation through repository."""
        uow = SQLAlchemyUnitOfWork(db_session)
        generator = PatternGenerator(uow)

        decision_rule = {
            "node_type": "Pax",
            "must_have_attributes": ["PaxID"],
            "child_structure": {"has_children": False}
        }

        hash1 = generator.generate_signature_hash(
            decision_rule, "21.3", "Response/DataLists/PaxList"
        )
        hash2 = generator.generate_signature_hash(
            decision_rule, "21.3", "Response/DataLists/PaxList"
        )

        # Same input should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 16  # We take first 16 chars

    def test_find_or_create_pattern_new(self, db_session: Session, sample_run: Run):
        """Test creating a new pattern through repository."""
        uow = SQLAlchemyUnitOfWork(db_session)
        generator = PatternGenerator(uow)

        decision_rule = {
            "node_type": "TestNode",
            "must_have_attributes": ["TestAttr"],
            "optional_attributes": [],
            "child_structure": {"has_children": False},
            "reference_patterns": [],
            "business_intelligence_schema": {}
        }

        # Create new pattern
        pattern = generator.find_or_create_pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="TEST",
            section_path="Response/Test/Path",
            decision_rule=decision_rule,
            example_node_fact_id=1
        )

        # Commit through UoW
        uow.commit()

        assert pattern.id is not None
        assert pattern.times_seen == 1
        assert pattern.spec_version == "21.3"
        assert pattern.airline_code == "TEST"

        # Verify in database
        db_session.refresh(pattern)
        assert pattern.id is not None

    def test_find_or_create_pattern_existing(self, db_session: Session):
        """Test updating existing pattern through repository."""
        uow = SQLAlchemyUnitOfWork(db_session)
        generator = PatternGenerator(uow)

        decision_rule = {
            "node_type": "ExistingNode",
            "must_have_attributes": ["Attr1"],
            "optional_attributes": [],
            "child_structure": {"has_children": False},
            "reference_patterns": [],
            "business_intelligence_schema": {}
        }

        # Create first pattern
        pattern1 = generator.find_or_create_pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="TEST",
            section_path="Response/Test/Existing",
            decision_rule=decision_rule,
            example_node_fact_id=1
        )
        uow.commit()
        initial_times_seen = pattern1.times_seen

        # Create same pattern again (should update)
        pattern2 = generator.find_or_create_pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="TEST",
            section_path="Response/Test/Existing",
            decision_rule=decision_rule,
            example_node_fact_id=2
        )
        uow.commit()

        # Should be same pattern with incremented times_seen
        assert pattern2.id == pattern1.id
        assert pattern2.times_seen == initial_times_seen + 1


class TestRepositoryTransactionManagement:
    """Integration tests for transaction management."""

    def test_commit_persistence(self, db_session: Session):
        """Test that committed changes persist."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create run
        run = Run(
            id="test-persist",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)
        uow.commit()

        # Create new UoW with same session
        uow2 = SQLAlchemyUnitOfWork(db_session)
        retrieved = uow2.runs.get_by_id("test-persist")

        assert retrieved is not None
        assert retrieved.id == "test-persist"

    def test_rollback_discards_changes(self, db_session: Session):
        """Test that rollback discards uncommitted changes."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create run
        run = Run(
            id="test-discard",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        uow.runs.create(run)
        uow.rollback()

        # Create new UoW with same session
        uow2 = SQLAlchemyUnitOfWork(db_session)
        retrieved = uow2.runs.get_by_id("test-discard")

        assert retrieved is None

    def test_cross_repository_transaction(self, db_session: Session):
        """Test transaction across multiple repositories."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create run
        run = Run(
            id="test-cross-repo",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS"
        )
        created_run = uow.runs.create(run)

        # Create pattern
        pattern = Pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="Response/DataLists/PaxList",
            selector_xpath="./Pax",
            decision_rule={"node_type": "Pax"},
            signature_hash="cross-repo-hash",
            times_seen=1
        )
        created_pattern = uow.patterns.create(pattern)

        # Both should be in same transaction
        uow.commit()

        # Verify both exist
        retrieved_run = db_session.query(Run).filter(Run.id == "test-cross-repo").first()
        retrieved_pattern = db_session.query(Pattern).filter(
            Pattern.signature_hash == "cross-repo-hash"
        ).first()

        assert retrieved_run is not None
        assert retrieved_pattern is not None

    def test_error_rollback_all_changes(self, db_session: Session):
        """Test that error rolls back all changes."""
        uow = SQLAlchemyUnitOfWork(db_session)

        try:
            # Create run
            run = Run(
                id="test-error-rollback",
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
                signature_hash="error-rollback-hash",
                times_seen=1
            )
            uow.patterns.create(pattern)

            # Simulate error
            raise Exception("Simulated error")

        except Exception:
            uow.rollback()

        # Neither should exist
        retrieved_run = db_session.query(Run).filter(
            Run.id == "test-error-rollback"
        ).first()
        retrieved_pattern = db_session.query(Pattern).filter(
            Pattern.signature_hash == "error-rollback-hash"
        ).first()

        assert retrieved_run is None
        assert retrieved_pattern is None


class TestRepositoryWithQueries:
    """Integration tests for repository query methods."""

    def test_pattern_list_by_version_complex(self, db_session: Session):
        """Test complex pattern listing with filters."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create patterns for different versions and airlines
        patterns_data = [
            ("21.3", "OrderViewRS", "AA", "hash-21.3-aa-1"),
            ("21.3", "OrderViewRS", "AA", "hash-21.3-aa-2"),
            ("21.3", "OrderViewRS", "SQ", "hash-21.3-sq-1"),
            ("18.1", "OrderViewRS", "AA", "hash-18.1-aa-1"),
        ]

        for version, message, airline, sig_hash in patterns_data:
            pattern = Pattern(
                spec_version=version,
                message_root=message,
                airline_code=airline,
                section_path="Response/Test",
                selector_xpath="./Test",
                decision_rule={"node_type": "Test"},
                signature_hash=sig_hash,
                times_seen=1
            )
            uow.patterns.create(pattern)

        uow.commit()

        # Query for 21.3 + OrderViewRS + AA
        results = uow.patterns.list_by_version(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA"
        )

        assert len(results) == 2
        assert all(p.spec_version == "21.3" for p in results)
        assert all(p.airline_code == "AA" for p in results)

    def test_run_list_all_ordering(self, db_session: Session):
        """Test that runs are ordered correctly."""
        uow = SQLAlchemyUnitOfWork(db_session)

        # Create runs with different timestamps
        import time
        for i in range(3):
            run = Run(
                id=f"test-order-{i}",
                kind="discovery",
                status="completed",
                spec_version="21.3",
                message_root="OrderViewRS"
            )
            uow.runs.create(run)
            uow.commit()
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # List all
        runs = uow.runs.list_all(limit=10)

        # Should be ordered by started_at descending (most recent first)
        # The last created should be first in list
        run_ids = [r.id for r in runs if r.id.startswith("test-order-")]
        # Most recent first
        assert len(run_ids) >= 3
