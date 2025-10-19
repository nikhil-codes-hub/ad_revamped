"""
Unit tests for repository implementations.

Tests the repository layer including:
- RunRepository
- PatternRepository
- NodeFactRepository
- PatternMatchRepository
- NodeRelationshipRepository
"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.sqlalchemy.run_repository import SQLAlchemyRunRepository
from app.repositories.sqlalchemy.pattern_repository import SQLAlchemyPatternRepository
from app.repositories.sqlalchemy.node_fact_repository import SQLAlchemyNodeFactRepository
from app.repositories.sqlalchemy.pattern_match_repository import SQLAlchemyPatternMatchRepository
from app.repositories.sqlalchemy.node_relationship_repository import SQLAlchemyNodeRelationshipRepository
from app.models.database import Run, Pattern, NodeFact, PatternMatch, NodeRelationship


class TestRunRepository:
    """Test suite for RunRepository."""

    def test_create_run(self, db_session: Session):
        """Test creating a new run."""
        repo = SQLAlchemyRunRepository(db_session)

        run = Run(
            id="test-run-001",
            kind="discovery",
            status="started",
            spec_version="21.3",
            message_root="OrderViewRS",
            filename="test.xml"
        )

        created = repo.create(run)

        assert created.id == "test-run-001"
        assert created.kind == "discovery"
        assert created.status == "started"

        # Verify it's in database
        db_session.commit()
        retrieved = db_session.query(Run).filter(Run.id == "test-run-001").first()
        assert retrieved is not None
        assert retrieved.kind == "discovery"

    def test_get_by_id(self, db_session: Session, sample_run: Run):
        """Test retrieving a run by ID."""
        repo = SQLAlchemyRunRepository(db_session)

        retrieved = repo.get_by_id(sample_run.id)

        assert retrieved is not None
        assert retrieved.id == sample_run.id
        assert retrieved.kind == sample_run.kind

    def test_get_by_id_not_found(self, db_session: Session):
        """Test retrieving a non-existent run."""
        repo = SQLAlchemyRunRepository(db_session)

        retrieved = repo.get_by_id("non-existent-id")

        assert retrieved is None

    def test_update_run_status(self, db_session: Session, sample_run: Run):
        """Test updating a run status."""
        repo = SQLAlchemyRunRepository(db_session)

        repo.update_status(sample_run.id, "completed", error_details=None)
        db_session.commit()

        # Verify in database
        retrieved = db_session.query(Run).filter(Run.id == sample_run.id).first()
        assert retrieved.status == "completed"
        assert retrieved.finished_at is not None

    def test_list_recent_runs(self, db_session: Session):
        """Test listing recent runs."""
        repo = SQLAlchemyRunRepository(db_session)

        # Create multiple runs with unique IDs
        import uuid
        for i in range(5):
            run = Run(
                id=f"test-recent-{uuid.uuid4().hex[:8]}",
                kind="discovery",
                status="completed",
                spec_version="21.3",
                message_root="OrderViewRS"
            )
            db_session.add(run)
        db_session.commit()

        runs = repo.list_recent(limit=10)

        assert len(runs) >= 5
        assert all(isinstance(r, Run) for r in runs)

    def test_list_recent_with_limit(self, db_session: Session):
        """Test listing runs with limit."""
        repo = SQLAlchemyRunRepository(db_session)

        # Create multiple runs with unique IDs
        import uuid
        for i in range(10):
            run = Run(
                id=f"test-limit-{uuid.uuid4().hex[:8]}",
                kind="discovery",
                status="completed",
                spec_version="21.3",
                message_root="OrderViewRS"
            )
            db_session.add(run)
        db_session.commit()

        runs = repo.list_recent(limit=3)

        assert len(runs) == 3


class TestPatternRepository:
    """Test suite for PatternRepository."""

    def test_create_pattern(self, db_session: Session):
        """Test creating a new pattern."""
        repo = SQLAlchemyPatternRepository(db_session)

        import uuid
        pattern = Pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="Response/DataLists/PaxList",
            selector_xpath="./Pax",
            decision_rule={"node_type": "Pax"},
            signature_hash=f"test-hash-{uuid.uuid4().hex[:8]}",
            times_seen=1,
            examples=[]  # Add empty examples list
        )

        created = repo.create(pattern)
        db_session.commit()
        db_session.refresh(created)

        assert created.id is not None
        assert created.spec_version == "21.3"

    def test_get_by_id(self, db_session: Session, sample_pattern: Pattern):
        """Test retrieving a pattern by ID."""
        repo = SQLAlchemyPatternRepository(db_session)

        retrieved = repo.get_by_id(sample_pattern.id)

        assert retrieved is not None
        assert retrieved.id == sample_pattern.id
        assert retrieved.spec_version == sample_pattern.spec_version

    def test_find_by_signature(self, db_session: Session):
        """Test finding pattern by signature."""
        repo = SQLAlchemyPatternRepository(db_session)

        # Create pattern with known signature
        import uuid
        unique_hash = f"unique-sig-{uuid.uuid4().hex[:8]}"
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
        db_session.add(pattern)
        db_session.commit()

        found = repo.find_by_signature(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            signature_hash=unique_hash
        )

        assert found is not None
        assert found.signature_hash == unique_hash

    def test_find_by_signature_not_found(self, db_session: Session):
        """Test finding non-existent signature."""
        repo = SQLAlchemyPatternRepository(db_session)

        found = repo.find_by_signature(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            signature_hash="non-existent-hash"
        )

        assert found is None

    def test_list_by_version(self, db_session: Session):
        """Test listing patterns by version."""
        repo = SQLAlchemyPatternRepository(db_session)

        import uuid
        # Create patterns for different versions
        for i in range(3):
            pattern = Pattern(
                spec_version="21.3",
                message_root="OrderViewRS",
                airline_code="AA",
                section_path=f"Path{i}",
                selector_xpath="./Node",
                decision_rule={"node_type": "Node"},
                signature_hash=f"hash-v21-{uuid.uuid4().hex[:8]}",
                times_seen=1,
                examples=[]
            )
            db_session.add(pattern)

        # Create pattern for different version
        other_pattern = Pattern(
            spec_version="18.1",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="OtherPath",
            selector_xpath="./Other",
            decision_rule={"node_type": "Other"},
            signature_hash=f"hash-v18-{uuid.uuid4().hex[:8]}",
            times_seen=1,
            examples=[]
        )
        db_session.add(other_pattern)
        db_session.commit()

        patterns = repo.list_by_version(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA"
        )

        assert len(patterns) == 3
        assert all(p.spec_version == "21.3" for p in patterns)

    def test_list_by_version_with_airline_filter(self, db_session: Session):
        """Test listing patterns filtered by airline."""
        repo = SQLAlchemyPatternRepository(db_session)

        import uuid
        # Create patterns for different airlines
        pattern_aa = Pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="PathAA",
            selector_xpath="./Node",
            decision_rule={"node_type": "Node"},
            signature_hash=f"hash-aa-{uuid.uuid4().hex[:8]}",
            times_seen=1,
            examples=[]
        )
        pattern_sq = Pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="SQ",
            section_path="PathSQ",
            selector_xpath="./Node",
            decision_rule={"node_type": "Node"},
            signature_hash=f"hash-sq-{uuid.uuid4().hex[:8]}",
            times_seen=1,
            examples=[]
        )
        db_session.add(pattern_aa)
        db_session.add(pattern_sq)
        db_session.commit()

        patterns = repo.list_by_version(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA"
        )

        assert len(patterns) >= 1
        assert all(p.airline_code == "AA" for p in patterns if p.airline_code)


class TestNodeFactRepository:
    """Test suite for NodeFactRepository."""

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment")
    def test_create_node_fact(self, db_session: Session, sample_run: Run):
        """Test creating a new node fact."""
        repo = SQLAlchemyNodeFactRepository(db_session)

        node_fact = NodeFact(
            run_id=sample_run.id,
            spec_version="21.3",
            message_root="OrderViewRS",
            section_path="Response/DataLists/PaxList",
            node_type="Pax",
            node_ordinal=0,
            fact_json={"node_type": "Pax", "attributes": {"PaxID": "PAX1"}}
        )

        created = repo.create(node_fact)
        db_session.commit()
        db_session.refresh(created)

        assert created.id is not None
        assert created.node_type == "Pax"
        assert created.run_id == sample_run.id

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment")
    def test_create_batch(self, db_session: Session, sample_run: Run):
        """Test creating multiple node facts in batch."""
        repo = SQLAlchemyNodeFactRepository(db_session)

        node_facts = []
        for i in range(5):
            nf = NodeFact(
                run_id=sample_run.id,
                spec_version="21.3",
                message_root="OrderViewRS",
                section_path="Response/DataLists/PaxList",
                node_type="Pax",
                node_ordinal=i,
                fact_json={"node_type": "Pax", "attributes": {"PaxID": f"PAX{i}"}}
            )
            node_facts.append(nf)

        created = repo.create_batch(node_facts)
        db_session.commit()

        assert len(created) == 5
        assert all(nf.id is not None for nf in created)

    def test_list_by_run(self, db_session: Session, sample_run: Run):
        """Test listing node facts by run."""
        repo = SQLAlchemyNodeFactRepository(db_session)

        # sample_run should already have node facts from fixture
        # But let's verify the method works
        node_facts = repo.list_by_run(sample_run.id)

        # May be empty if no facts created in fixture
        assert isinstance(node_facts, list)

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment")
    def test_get_by_id(self, db_session: Session, sample_node_fact: NodeFact):
        """Test retrieving node fact by ID."""
        repo = SQLAlchemyNodeFactRepository(db_session)

        retrieved = repo.get_by_id(sample_node_fact.id)

        assert retrieved is not None
        assert retrieved.id == sample_node_fact.id
        assert retrieved.node_type == sample_node_fact.node_type


class TestPatternMatchRepository:
    """Test suite for PatternMatchRepository."""

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment - requires NodeFact and Pattern")
    def test_create_pattern_match(self, db_session: Session, sample_run: Run, sample_node_fact: NodeFact, sample_pattern: Pattern):
        """Test creating a pattern match."""
        repo = SQLAlchemyPatternMatchRepository(db_session)

        match = PatternMatch(
            run_id=sample_run.id,
            node_fact_id=sample_node_fact.id,
            pattern_id=sample_pattern.id,
            confidence=0.95,
            verdict="EXACT_MATCH"
        )

        created = repo.create(match)
        db_session.commit()
        db_session.refresh(created)

        assert created.id is not None
        assert created.confidence == 0.95
        assert created.verdict == "EXACT_MATCH"

    def test_list_by_run(self, db_session: Session, sample_run: Run):
        """Test listing pattern matches by run."""
        repo = SQLAlchemyPatternMatchRepository(db_session)

        matches = repo.list_by_run(sample_run.id)

        assert isinstance(matches, list)


class TestNodeRelationshipRepository:
    """Test suite for NodeRelationshipRepository."""

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment - requires NodeFact")
    def test_create_relationship(self, db_session: Session, sample_run: Run, sample_node_fact: NodeFact):
        """Test creating a node relationship."""
        repo = SQLAlchemyNodeRelationshipRepository(db_session)

        relationship = NodeRelationship(
            run_id=sample_run.id,
            source_node_fact_id=sample_node_fact.id,
            source_node_type="Pax",
            source_section_path="Response/DataLists/PaxList",
            target_node_fact_id=sample_node_fact.id,
            target_node_type="Individual",
            target_section_path="Response/DataLists/PaxList",
            reference_type="parent_child",
            is_valid=True
        )

        created = repo.create(relationship)
        db_session.commit()
        db_session.refresh(created)

        assert created.id is not None
        assert created.reference_type == "parent_child"
        assert created.is_valid is True

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment")
    def test_create_batch(self, db_session: Session, sample_run: Run, sample_node_fact: NodeFact):
        """Test creating relationships in batch."""
        repo = SQLAlchemyNodeRelationshipRepository(db_session)

        relationships = []
        for i in range(3):
            rel = NodeRelationship(
                run_id=sample_run.id,
                source_node_fact_id=sample_node_fact.id,
                source_node_type="Pax",
                source_section_path="Response/DataLists/PaxList",
                target_node_fact_id=sample_node_fact.id,
                target_node_type="Individual",
                target_section_path="Response/DataLists/PaxList",
                reference_type=f"type_{i}",
                is_valid=True
            )
            relationships.append(rel)

        created = repo.create_batch(relationships)
        db_session.commit()

        assert len(created) == 3
        assert all(r.id is not None for r in created)

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment")
    def test_list_broken_for_node(self, db_session: Session, sample_run: Run, sample_node_fact: NodeFact):
        """Test listing broken relationships for a node."""
        repo = SQLAlchemyNodeRelationshipRepository(db_session)

        # Create broken relationship
        broken_rel = NodeRelationship(
            run_id=sample_run.id,
            source_node_fact_id=sample_node_fact.id,
            source_node_type="Pax",
            source_section_path="Response/DataLists/PaxList",
            target_node_fact_id=None,  # Broken - no target
            target_node_type="Missing",
            target_section_path="Response/DataLists/Missing",
            reference_type="broken_ref",
            is_valid=False
        )
        db_session.add(broken_rel)
        db_session.commit()

        broken = repo.list_broken_for_node(sample_node_fact.id)

        assert len(broken) >= 1
        assert all(r.is_valid is False for r in broken)
