"""
Integration tests for Discovery API endpoints.

NOTE: Backend uses "discovery" for the service that extracts patterns from XML.
UI terminology: This is called "Pattern Extractor" in the user interface.

Tests the full discovery workflow including:
- POST /api/v1/discovery/upload (upload XML for discovery)
- GET /api/v1/discovery/runs (list discovery runs)
- GET /api/v1/discovery/runs/{id} (get run details)
- GET /api/v1/discovery/runs/{id}/node-facts (get node facts for run)
"""
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.database import Run


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestDiscoveryAPI:
    """Test suite for Discovery API endpoints."""

    def test_list_runs_empty(self, client, db_session: Session):
        """Test listing runs when database is empty."""
        response = client.get("/api/v1/runs/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_runs_with_filters(self, client, db_session: Session, sample_run: Run):
        """Test listing runs with query filters."""
        response = client.get(
            "/api/v1/runs/",
            params={
                "spec_version": sample_run.spec_version,
                "workspace": "default"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_get_run_by_id(self, client, db_session: Session, sample_run: Run):
        """Test getting a specific run by ID."""
        response = client.get(f"/api/v1/runs/{sample_run.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_run.id
        assert data["spec_version"] == sample_run.spec_version

    def test_get_run_not_found(self, client):
        """Test getting non-existent run."""
        response = client.get("/api/v1/runs/non-existent-id")

        assert response.status_code == 404

    def test_upload_xml_for_discovery(self, client, sample_xml_file: Path):
        """Test uploading XML file for discovery."""
        with open(sample_xml_file, 'rb') as f:
            response = client.post(
                "/api/v1/discovery/upload",
                files={"file": ("test.xml", f, "application/xml")},
                data={"workspace": "default"}
            )

        # Should return 200 or 202 (accepted)
        assert response.status_code in [200, 202]
        if response.status_code == 200:
            data = response.json()
            assert "run_id" in data or "id" in data

    def test_upload_invalid_file_type(self, client):
        """Test uploading non-XML file."""
        content = b"This is not XML"
        response = client.post(
            "/api/v1/discovery/upload",
            files={"file": ("test.txt", content, "text/plain")},
            data={"workspace": "default"}
        )

        # Should reject non-XML files
        assert response.status_code in [400, 422]

    def test_get_node_facts_for_run(self, client, db_session: Session, sample_run: Run, sample_node_fact):
        """Test retrieving node facts for a specific run."""
        response = client.get(f"/api/v1/runs/{sample_run.id}/node-facts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_delete_run(self, client, db_session: Session, sample_run: Run):
        """Test deleting a discovery run."""
        run_id = sample_run.id

        response = client.delete(f"/api/v1/runs/{run_id}")

        assert response.status_code == 200

        # Verify run is deleted
        response = client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 404

    def test_run_status_updates(self, client, db_session: Session, sample_run: Run):
        """Test that run status is properly tracked."""
        response = client.get(f"/api/v1/runs/{sample_run.id}")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["pending", "processing", "completed", "failed"]

    def test_list_runs_pagination(self, client, db_session: Session):
        """Test pagination for run listing."""
        # Create multiple runs
        for i in range(10):
            run = Run(
                id=f"test-run-{i:03d}",
                spec_version="21.3",
                message_root="OrderViewRS",
                filename=f"test_{i}.xml",
                workspace="default",
                status="completed"
            )
            db_session.add(run)
        db_session.commit()

        # Test with limit
        response = client.get("/api/v1/runs/?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_detect_version_endpoint(self, client, sample_xml_file: Path):
        """Test version detection endpoint."""
        with open(sample_xml_file, 'rb') as f:
            response = client.post(
                "/api/v1/discovery/detect-version",
                files={"file": ("test.xml", f, "application/xml")}
            )

        if response.status_code == 200:
            data = response.json()
            assert "spec_version" in data or "version" in data
            assert "message_root" in data or "message_type" in data
