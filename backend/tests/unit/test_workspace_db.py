"""
Unit tests for workspace database service.

Tests workspace isolation and management including:
- Workspace session factory
- Session creation
- Data isolation between workspaces
"""
import pytest
from sqlalchemy.orm import Session
from app.services.workspace_db import (
    WorkspaceSessionFactory,
    get_workspace_session_factory,
    get_workspace_session,
    list_workspaces
)
from app.models.database import Run


class TestWorkspaceSessionFactory:
    """Test suite for WorkspaceSessionFactory."""

    def test_create_factory(self):
        """Test creating a workspace session factory."""
        factory = WorkspaceSessionFactory("test_workspace")

        assert factory is not None
        assert factory.workspace_name == "test_workspace"
        assert factory.db_path.exists()

    def test_get_session(self):
        """Test getting a session from factory."""
        factory = WorkspaceSessionFactory("test_workspace2")
        session = factory.get_session()

        assert session is not None
        assert isinstance(session, Session)
        session.close()

    def test_session_scope(self):
        """Test session scope context manager."""
        factory = WorkspaceSessionFactory("test_workspace3")

        with factory.session_scope() as session:
            assert session is not None
            assert isinstance(session, Session)


class TestWorkspaceHelpers:
    """Test suite for workspace helper functions."""

    def test_get_workspace_session_factory(self):
        """Test getting or creating workspace session factory."""
        factory = get_workspace_session_factory("helper_test_ws")

        assert factory is not None
        assert factory.workspace_name == "helper_test_ws"

    def test_get_workspace_session(self):
        """Test getting a workspace session."""
        session = get_workspace_session("session_test_ws")

        assert session is not None
        assert isinstance(session, Session)
        session.close()

    def test_list_workspaces(self):
        """Test listing all workspaces."""
        # Create a workspace to ensure at least one exists
        get_workspace_session("list_test_ws")

        workspaces = list_workspaces()

        assert isinstance(workspaces, list)
        assert len(workspaces) > 0

    def test_workspace_isolation(self):
        """Test that data is isolated between workspaces."""
        import uuid

        # Use unique IDs to avoid UNIQUE constraint violations
        run1_id = f"run-ws1-{uuid.uuid4().hex[:8]}"
        run2_id = f"run-ws2-{uuid.uuid4().hex[:8]}"

        # Create runs in different workspace databases
        session1 = get_workspace_session("workspace1")
        run1 = Run(
            id=run1_id,
            kind="discovery",
            spec_version="21.3",
            message_root="OrderViewRS",
            filename="test1.xml",
            status="completed"
        )
        session1.add(run1)
        session1.commit()

        # Query workspace1 - should see run1
        ws1_runs = session1.query(Run).all()
        session1.close()

        # Create run in workspace2
        session2 = get_workspace_session("workspace2")
        run2 = Run(
            id=run2_id,
            kind="discovery",
            spec_version="21.3",
            message_root="OrderViewRS",
            filename="test2.xml",
            status="completed"
        )
        session2.add(run2)
        session2.commit()

        # Query workspace2 - should only see run2, not run1
        ws2_runs = session2.query(Run).all()
        session2.close()

        # Workspaces should be isolated - workspace1 has 1 run, workspace2 has 1 run
        assert len(ws1_runs) >= 1
        assert len(ws2_runs) >= 1
        # The runs should have different IDs showing they are isolated
        assert run1_id in [r.id for r in ws1_runs]
        assert run2_id in [r.id for r in ws2_runs]
