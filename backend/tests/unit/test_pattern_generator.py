"""
Unit tests for PatternGenerator service.

Tests pattern generation logic including:
- Child structure deduplication by node_type
- Signature hash generation
- Pattern creation and updates
- Decision rule generation
"""
import pytest
from sqlalchemy.orm import Session
from app.services.pattern_generator import PatternGenerator
from app.models.database import Pattern, NodeFact, Run


class TestPatternGenerator:
    """Test suite for PatternGenerator service."""

    def test_extract_required_attributes(self, db_session: Session):
        """Test that required attributes are correctly extracted."""
        generator = PatternGenerator(db_session)

        fact_json = {
            "attributes": {
                "PaxID": "PAX1",
                "PTC": "ADT",
                "summary": "This is metadata",  # Should be filtered out
                "confidence": 0.95  # Should be filtered out
            }
        }

        required = generator._extract_required_attributes(fact_json)

        assert "PaxID" in required
        assert "PTC" in required
        assert "summary" not in required
        assert "confidence" not in required
        assert len(required) == 2

    def test_child_structure_deduplication(self, db_session: Session):
        """Test that child structures are deduplicated by node_type."""
        generator = PatternGenerator(db_session)

        # Simulate PaxList with 2 Pax children (different instances, same type)
        children = [
            {
                "node_type": "Pax",
                "attributes": {"PaxID": "PAX1", "PTC": "ADT"},
                "references": {"PaxJourneyRefID": ["PJ1"]}
            },
            {
                "node_type": "Pax",
                "attributes": {"PaxID": "PAX2", "PTC": "ADT"},
                "references": {"PaxJourneyRefID": ["PJ2"]}
            }
        ]

        result = generator._get_child_structure_fingerprint(children)

        assert result["has_children"] is True
        assert result["is_container"] is True
        assert "Pax" in result["child_types"]

        # Should have only 1 child structure entry for "Pax", not 2
        assert len(result["child_structures"]) == 1
        assert result["child_structures"][0]["node_type"] == "Pax"

    def test_child_structure_attribute_intersection(self, db_session: Session):
        """Test that required attributes are intersected across instances."""
        generator = PatternGenerator(db_session)

        # First Pax has PaxID and PTC, second has only PaxID
        children = [
            {
                "node_type": "Pax",
                "attributes": {"PaxID": "PAX1", "PTC": "ADT"}
            },
            {
                "node_type": "Pax",
                "attributes": {"PaxID": "PAX2"}  # Missing PTC
            }
        ]

        result = generator._get_child_structure_fingerprint(children)

        child_structure = result["child_structures"][0]

        # Only PaxID should be required (present in ALL instances)
        assert "PaxID" in child_structure["required_attributes"]
        assert "PTC" not in child_structure["required_attributes"]
        assert len(child_structure["required_attributes"]) == 1

    def test_child_structure_reference_union(self, db_session: Session):
        """Test that reference fields are unioned across instances."""
        generator = PatternGenerator(db_session)

        children = [
            {
                "node_type": "Pax",
                "attributes": {},
                "references": {"PaxJourneyRefID": ["PJ1"]}
            },
            {
                "node_type": "Pax",
                "attributes": {},
                "references": {"PaxSegmentRefID": ["PS1"]}
            }
        ]

        result = generator._get_child_structure_fingerprint(children)

        child_structure = result["child_structures"][0]

        # Should have both reference fields (union)
        assert "PaxJourneyRefID" in child_structure["reference_fields"]
        assert "PaxSegmentRefID" in child_structure["reference_fields"]
        assert len(child_structure["reference_fields"]) == 2

    def test_signature_hash_consistency(self, db_session: Session):
        """Test that same structure generates same hash."""
        generator = PatternGenerator(db_session)

        decision_rule = {
            "node_type": "Pax",
            "must_have_attributes": ["PaxID"],
            "child_structure": {
                "has_children": True,
                "child_types": ["Individual"]
            }
        }

        hash1 = generator.generate_signature_hash(
            decision_rule, "21.3", "Response/DataLists/PaxList"
        )
        hash2 = generator.generate_signature_hash(
            decision_rule, "21.3", "Response/DataLists/PaxList"
        )

        assert hash1 == hash2

    def test_signature_hash_differs_with_changes(self, db_session: Session):
        """Test that different structures generate different hashes."""
        generator = PatternGenerator(db_session)

        rule1 = {
            "node_type": "Pax",
            "must_have_attributes": ["PaxID"]
        }

        rule2 = {
            "node_type": "Pax",
            "must_have_attributes": ["PaxID", "PTC"]  # Different attributes
        }

        hash1 = generator.generate_signature_hash(rule1, "21.3", "Response/DataLists/PaxList")
        hash2 = generator.generate_signature_hash(rule2, "21.3", "Response/DataLists/PaxList")

        assert hash1 != hash2

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment - NodeFact.id and Pattern.id fail with NOT NULL constraint")
    def test_find_or_create_pattern_new(self, db_session: Session, sample_run: Run):
        """Test creating a new pattern."""
        generator = PatternGenerator(db_session)

        decision_rule = {
            "node_type": "Pax",
            "must_have_attributes": ["PaxID"],
            "child_structure": {"has_children": False}
        }

        # Create a NodeFact first
        fact = NodeFact(
            run_id=sample_run.id,
            spec_version="21.3",
            message_root="OrderViewRS",
            section_path="Response/DataLists/PaxList",
            node_type="Pax",
            fact_json={"node_type": "Pax"}
        )
        db_session.add(fact)
        db_session.commit()

        pattern = generator.find_or_create_pattern(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            section_path="Response/DataLists/PaxList",
            decision_rule=decision_rule,
            example_node_fact_id=fact.id
        )

        assert pattern.id is not None
        assert pattern.times_seen == 1
        assert pattern.spec_version == "21.3"
        assert pattern.message_root == "OrderViewRS"
        assert pattern.airline_code == "AA"

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment - NodeFact.id fails with NOT NULL constraint")
    def test_find_or_create_pattern_existing(self, db_session: Session, sample_pattern: Pattern, sample_run: Run):
        """Test updating an existing pattern."""
        generator = PatternGenerator(db_session)

        initial_times_seen = sample_pattern.times_seen

        # Create a NodeFact
        fact = NodeFact(
            run_id=sample_run.id,
            spec_version=sample_pattern.spec_version,
            message_root=sample_pattern.message_root,
            section_path=sample_pattern.section_path,
            node_type="Pax",
            fact_json={"node_type": "Pax"}
        )
        db_session.add(fact)
        db_session.commit()

        # Use same decision rule to get same signature hash
        pattern = generator.find_or_create_pattern(
            spec_version=sample_pattern.spec_version,
            message_root=sample_pattern.message_root,
            airline_code=sample_pattern.airline_code,
            section_path=sample_pattern.section_path,
            decision_rule=sample_pattern.decision_rule,
            example_node_fact_id=fact.id
        )

        # Should be same pattern, with incremented times_seen
        assert pattern.id == sample_pattern.id
        assert pattern.times_seen == initial_times_seen + 1

    def test_generate_decision_rule(self, db_session: Session):
        """Test decision rule generation from NodeFacts."""
        generator = PatternGenerator(db_session)

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
        assert decision_rule["child_structure"]["has_children"] is False

    def test_normalize_path(self, db_session: Session):
        """Test path normalization."""
        generator = PatternGenerator(db_session)

        # Test removing leading slash
        normalized = generator._normalize_path("/Response/DataLists", "OrderViewRS")
        assert not normalized.startswith("/")

        # Test IATA_ prefix removal
        normalized = generator._normalize_path("IATA_OrderViewRS/Response", "OrderViewRS")
        assert not normalized.startswith("IATA_")
        assert normalized.startswith("OrderViewRS")

    def test_extract_optional_attributes(self, db_session: Session):
        """Test optional attribute extraction."""
        generator = PatternGenerator(db_session)

        facts_group = [
            {
                "attributes": {"PaxID": "PAX1", "Email": "john@example.com"}
            },
            {
                "attributes": {"PaxID": "PAX2"}  # Missing Email
            },
            {
                "attributes": {"PaxID": "PAX3", "Email": "jane@example.com"}
            }
        ]

        optional = generator._extract_optional_attributes(facts_group)

        # Email is present in 2 out of 3 facts, so it's optional
        assert "Email" in optional
        # PaxID is in all facts, so it's NOT optional
        assert "PaxID" not in optional

    @pytest.mark.skip(reason="SQLite doesn't support BigInteger auto-increment - NodeFact.id fails with NOT NULL constraint")
    def test_generate_patterns_from_run(self, db_session: Session, sample_run: Run):
        """Test pattern generation from a complete run."""
        # Add multiple NodeFacts to the run
        facts = [
            NodeFact(
                run_id=sample_run.id,
                spec_version="21.3",
                message_root="OrderViewRS",
                section_path="Response/DataLists/PaxList",
                node_type="Pax",
                fact_json={
                    "node_type": "Pax",
                    "attributes": {"PaxID": "PAX1"},
                    "children": []
                }
            ),
            NodeFact(
                run_id=sample_run.id,
                spec_version="21.3",
                message_root="OrderViewRS",
                section_path="Response/DataLists/PaxList",
                node_type="Pax",
                fact_json={
                    "node_type": "Pax",
                    "attributes": {"PaxID": "PAX2"},
                    "children": []
                }
            )
        ]

        for fact in facts:
            db_session.add(fact)
        db_session.commit()

        generator = PatternGenerator(db_session)
        result = generator.generate_patterns_from_run(sample_run.id)

        assert result["success"] is True
        assert result["node_facts_analyzed"] == 2
        assert result["patterns_created"] + result["patterns_updated"] > 0

    def test_empty_children_handling(self, db_session: Session):
        """Test that empty children list is handled correctly."""
        generator = PatternGenerator(db_session)

        result = generator._get_child_structure_fingerprint([])

        assert result["has_children"] is False
        assert "child_structures" not in result
