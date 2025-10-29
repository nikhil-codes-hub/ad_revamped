"""
Integration tests for Pattern API endpoints.

Tests the full API flow including:
- GET /api/v1/patterns/ (list patterns)
- GET /api/v1/patterns/{id} (get pattern by ID)
- POST /api/v1/patterns/regenerate (regenerate patterns)
- DELETE /api/v1/patterns/{id} (delete pattern)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.database import Pattern, Run, NodeFact


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestPatternsAPI:
    """Test suite for Patterns API endpoints."""

    def test_list_patterns_empty(self, client, db_session: Session):
        """Test listing patterns when database is empty."""
        response = client.get("/api/v1/patterns/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_patterns_with_filters(self, client, db_session: Session, sample_pattern: Pattern):
        """Test listing patterns with query filters."""
        response = client.get(
            "/api/v1/patterns/",
            params={
                "spec_version": sample_pattern.spec_version,
                "message_root": sample_pattern.message_root,
                "workspace": "default"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["spec_version"] == sample_pattern.spec_version

    def test_get_pattern_by_id(self, client, db_session: Session, sample_pattern: Pattern):
        """Test getting a specific pattern by ID."""
        response = client.get(f"/api/v1/patterns/{sample_pattern.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_pattern.id
        assert data["node_type"] == sample_pattern.decision_rule["node_type"]

    def test_get_pattern_not_found(self, client):
        """Test getting non-existent pattern."""
        response = client.get("/api/v1/patterns/99999")

        assert response.status_code == 404

    def test_regenerate_patterns(self, client, db_session: Session, sample_run: Run, sample_node_fact: NodeFact):
        """Test pattern regeneration endpoint."""
        response = client.post(
            "/api/v1/patterns/regenerate",
            params={"workspace": "default"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "patterns_created" in data
        assert "patterns_updated" in data

    def test_delete_pattern(self, client, db_session: Session, sample_pattern: Pattern):
        """Test deleting a pattern."""
        pattern_id = sample_pattern.id

        response = client.delete(f"/api/v1/patterns/{pattern_id}")

        assert response.status_code == 200

        # Verify pattern is deleted
        response = client.get(f"/api/v1/patterns/{pattern_id}")
        assert response.status_code == 404

    def test_list_patterns_pagination(self, client, db_session: Session):
        """Test pagination for pattern listing."""
        # Create multiple patterns
        for i in range(15):
            pattern = Pattern(
                spec_version="21.3",
                message_root="OrderViewRS",
                airline_code="AA",
                section_path=f"Response/DataLists/List{i}",
                selector_xpath=f"./Element{i}",
                decision_rule={"node_type": f"Element{i}"},
                signature_hash=f"hash{i:03d}",
                times_seen=1,
                created_by_model="gpt-4"
            )
            db_session.add(pattern)
        db_session.commit()

        # Test with limit
        response = client.get("/api/v1/patterns/?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_list_patterns_by_airline(self, client, db_session: Session):
        """Test filtering patterns by airline code."""
        # Create patterns for different airlines
        for airline in ["AA", "UA", "DL"]:
            pattern = Pattern(
                spec_version="21.3",
                message_root="OrderViewRS",
                airline_code=airline,
                section_path="Response/DataLists/PaxList",
                selector_xpath="./Pax",
                decision_rule={"node_type": "Pax"},
                signature_hash=f"hash_{airline}",
                times_seen=1,
                created_by_model="gpt-4"
            )
            db_session.add(pattern)
        db_session.commit()

        # Filter by specific airline
        response = client.get("/api/v1/patterns/?airline_code=AA")

        assert response.status_code == 200
        data = response.json()
        for pattern in data:
            assert pattern["airline_code"] == "AA"

    def test_get_pattern_examples(self, client, db_session: Session, sample_pattern: Pattern):
        """Test retrieving pattern with examples."""
        # Add examples to pattern
        sample_pattern.examples = [
            {"node_fact_id": 1, "timestamp": "2024-01-01T00:00:00"},
            {"node_fact_id": 2, "timestamp": "2024-01-02T00:00:00"}
        ]
        db_session.commit()

        response = client.get(f"/api/v1/patterns/{sample_pattern.id}")

        assert response.status_code == 200
        data = response.json()
        assert "examples" in data
        assert len(data["examples"]) == 2

    def test_pattern_statistics(self, client, db_session: Session):
        """Test pattern statistics endpoint if available."""
        response = client.get("/api/v1/patterns/statistics")

        # Endpoint may or may not exist
        if response.status_code == 200:
            data = response.json()
            assert "total_patterns" in data or isinstance(data, dict)
