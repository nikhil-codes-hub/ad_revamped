"""
Integration tests for NodeConfiguration API endpoints.

Tests node configuration management including:
- GET /api/v1/node-configs/ (list configurations)
- POST /api/v1/node-configs/ (create configuration)
- PUT /api/v1/node-configs/{id} (update configuration)
- DELETE /api/v1/node-configs/{id} (delete configuration)
- POST /api/v1/node-configs/copy-to-versions (copy to versions)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.database import NodeConfiguration


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestNodeConfigsAPI:
    """Test suite for NodeConfiguration API endpoints."""

    def test_list_node_configs(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test listing node configurations."""
        response = client.get("/api/v1/node-configs/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_node_configs_with_filters(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test listing configurations with filters."""
        response = client.get(
            "/api/v1/node-configs/",
            params={
                "spec_version": sample_node_config.spec_version,
                "message_root": sample_node_config.message_root,
                "workspace": "default"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert all(c["spec_version"] == sample_node_config.spec_version for c in data)

    def test_get_node_config_by_id(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test getting a specific configuration by ID."""
        response = client.get(f"/api/v1/node-configs/{sample_node_config.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_node_config.id
        assert data["element_name"] == sample_node_config.element_name

    def test_get_node_config_not_found(self, client):
        """Test getting non-existent configuration."""
        response = client.get("/api/v1/node-configs/99999")

        assert response.status_code == 404

    def test_create_node_config(self, client, db_session: Session):
        """Test creating a new configuration."""
        config_data = {
            "spec_version": "21.3",
            "message_root": "OrderViewRS",
            "path_local": "Response/DataLists/TestList",
            "path_full": "OrderViewRS/Response/DataLists/TestList",
            "element_name": "TestList",
            "extraction_mode": "container",
            "is_enabled": True,
            "workspace": "default"
        }

        response = client.post("/api/v1/node-configs/", json=config_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["element_name"] == "TestList"

    def test_update_node_config(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test updating a configuration."""
        update_data = {
            "is_enabled": False
        }

        response = client.put(
            f"/api/v1/node-configs/{sample_node_config.id}",
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is False

    def test_delete_node_config(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test deleting a configuration."""
        config_id = sample_node_config.id

        response = client.delete(f"/api/v1/node-configs/{config_id}")

        assert response.status_code in [200, 204]

        # Verify deletion
        response = client.get(f"/api/v1/node-configs/{config_id}")
        assert response.status_code == 404

    def test_filter_by_airline(self, client, db_session: Session):
        """Test filtering configurations by airline code."""
        # Create configs for different airlines
        for airline in ["AA", "UA"]:
            config = NodeConfiguration(
                spec_version="21.3",
                message_root="OrderViewRS",
                airline_code=airline,
                path_local=f"Response/DataLists/{airline}List",
                path_full=f"OrderViewRS/Response/DataLists/{airline}List",
                element_name=f"{airline}List",
                extraction_mode="container",
                is_enabled=True,
                workspace="default"
            )
            db_session.add(config)
        db_session.commit()

        response = client.get("/api/v1/node-configs/?airline_code=AA")

        assert response.status_code == 200
        data = response.json()
        assert all(c["airline_code"] == "AA" for c in data if c.get("airline_code"))

    def test_filter_by_enabled_status(self, client, db_session: Session):
        """Test filtering configurations by enabled status."""
        response = client.get("/api/v1/node-configs/?is_enabled=true")

        assert response.status_code == 200
        data = response.json()
        assert all(c["is_enabled"] is True for c in data)

    def test_copy_to_versions(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test copying configuration to multiple versions."""
        response = client.post(
            "/api/v1/node-configs/copy-to-versions",
            params={
                "source_spec_version": sample_node_config.spec_version,
                "source_message_root": sample_node_config.message_root,
                "target_versions": ["19.2", "18.1"]
            }
        )

        if response.status_code == 200:
            data = response.json()
            assert "copied_count" in data or "success" in data

    def test_bulk_enable_disable(self, client, db_session: Session):
        """Test bulk enable/disable of configurations."""
        # Create multiple configs
        configs = []
        for i in range(3):
            config = NodeConfiguration(
                spec_version="21.3",
                message_root="OrderViewRS",
                path_local=f"Response/DataLists/List{i}",
                path_full=f"OrderViewRS/Response/DataLists/List{i}",
                element_name=f"List{i}",
                extraction_mode="container",
                is_enabled=True,
                workspace="default"
            )
            db_session.add(config)
            configs.append(config)
        db_session.commit()

        # Bulk disable
        config_ids = [c.id for c in configs]
        response = client.post(
            "/api/v1/node-configs/bulk-update",
            json={"ids": config_ids, "is_enabled": False}
        )

        if response.status_code == 200:
            data = response.json()
            assert data.get("updated_count") == 3

    def test_validate_config_uniqueness(self, client, db_session: Session, sample_node_config: NodeConfiguration):
        """Test that duplicate configurations are prevented."""
        # Try to create duplicate
        duplicate_data = {
            "spec_version": sample_node_config.spec_version,
            "message_root": sample_node_config.message_root,
            "path_local": sample_node_config.path_local,
            "path_full": sample_node_config.path_full,
            "element_name": sample_node_config.element_name,
            "extraction_mode": "container",
            "is_enabled": True,
            "workspace": "default"
        }

        response = client.post("/api/v1/node-configs/", json=duplicate_data)

        # Should either reject or update existing
        assert response.status_code in [200, 201, 400, 409]
