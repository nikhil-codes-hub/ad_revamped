"""
Workspace Database Adapter

Provides SQLAlchemy session factory that connects to workspace-specific SQLite databases
instead of centralized MySQL. Enables portable, user-friendly deployments.

Usage:
    # Get session for a specific workspace
    db = get_workspace_session(workspace="SQ")

    # Use with existing code
    node_facts = db.query(NodeFact).filter(NodeFact.run_id == run_id).all()
"""

import os
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.models.database import Base
from app.core.config import settings


class WorkspaceSessionFactory:
    """Creates SQLAlchemy sessions for workspace-specific SQLite databases."""

    def __init__(self, workspace_name: str = "default"):
        self.workspace_name = workspace_name
        self.db_dir = self._get_db_dir()
        self.db_path = self.db_dir / f"{workspace_name}.db"
        self.engine = None
        self.SessionLocal = None
        self._init_engine()

    def _get_db_dir(self) -> Path:
        """Get workspace database directory."""
        # Check if running from backend directory
        backend_dir = Path(__file__).parent.parent.parent

        # Try frontend data directory (if exists)
        frontend_data_dir = backend_dir.parent / "frontend" / "streamlit_ui" / "data" / "workspaces"
        if frontend_data_dir.parent.exists():
            frontend_data_dir.mkdir(parents=True, exist_ok=True)
            return frontend_data_dir

        # Fallback to backend data directory
        backend_data_dir = backend_dir / "data" / "workspaces"
        backend_data_dir.mkdir(parents=True, exist_ok=True)
        return backend_data_dir

    def _init_engine(self):
        """Initialize SQLite engine and session factory."""
        # SQLite connection string
        sqlite_url = f"sqlite:///{self.db_path}"

        # Create engine with SQLite-specific settings
        self.engine = create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},  # Allow multi-threading
            poolclass=StaticPool,  # Keep single connection
            echo=settings.DEBUG
        )

        # Enable foreign keys for SQLite
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Create all tables if they don't exist
        Base.metadata.create_all(bind=self.engine)

        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global workspace session factories (cached per workspace)
_workspace_factories = {}


def get_workspace_session_factory(workspace: str = "default") -> WorkspaceSessionFactory:
    """Get or create workspace session factory."""
    if workspace not in _workspace_factories:
        _workspace_factories[workspace] = WorkspaceSessionFactory(workspace)
    return _workspace_factories[workspace]


def get_workspace_session(workspace: str = "default") -> Session:
    """Get a database session for the specified workspace."""
    factory = get_workspace_session_factory(workspace)
    return factory.get_session()


@contextmanager
def workspace_session(workspace: str = "default") -> Generator[Session, None, None]:
    """Context manager for workspace database sessions."""
    factory = get_workspace_session_factory(workspace)
    with factory.session_scope() as session:
        yield session


def get_workspace_db_path(workspace: str = "default") -> Path:
    """Get the file path for a workspace database."""
    factory = get_workspace_session_factory(workspace)
    return factory.db_path


def list_workspaces() -> list[str]:
    """List all available workspace databases."""
    factory = WorkspaceSessionFactory("temp")
    db_dir = factory.db_dir

    if not db_dir.exists():
        return ["default"]

    workspaces = []
    for db_file in db_dir.glob("*.db"):
        workspace_name = db_file.stem
        workspaces.append(workspace_name)

    return sorted(workspaces) if workspaces else ["default"]


# FastAPI dependency for workspace database sessions
from typing import Generator
from functools import partial


def _get_workspace_session_generator(workspace: str) -> Generator[Session, None, None]:
    """Internal generator for workspace sessions."""
    factory = get_workspace_session_factory(workspace)
    session = factory.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_workspace_db(workspace: str) -> Generator[Session, None, None]:
    """
    Dependency factory for workspace database sessions.

    Returns a dependency function bound to the specific workspace.

    Usage in endpoint:
        from fastapi import Depends, Query

        @router.post("/example")
        def example(
            workspace: str = Query("default", description="Workspace name"),
            db: Session = Depends(lambda w=workspace: get_workspace_db(w))
        ):
            # Use db session
            pass

    Or simpler pattern with request parameter:
        from app.api.dependencies import get_workspace_from_request

        @router.post("/example")
        def example(db: Session = Depends(get_workspace_from_request)):
            # db is workspace-specific
            pass

    Args:
        workspace: Workspace name

    Yields:
        Session: SQLAlchemy session for the workspace
    """
    return _get_workspace_session_generator(workspace)
