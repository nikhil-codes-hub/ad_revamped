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
import logging
import re
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.models.database import Base
from app.core.config import settings

logger = logging.getLogger(__name__)


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
        # Store workspace databases in backend/data/workspaces
        backend_dir = Path(__file__).parent.parent.parent
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
            echo=settings.LOG_LEVEL == "DEBUG"
        )

        # Enable foreign keys for SQLite
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Create all tables if they don't exist
        Base.metadata.create_all(bind=self.engine)

        # Fix SQLite AUTOINCREMENT for primary keys
        self._fix_sqlite_autoincrement()

        # Ensure pattern_matches table has expected schema (nullable pattern_id + autoincrement id)
        self._ensure_pattern_matches_schema()

        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )

    def _fix_sqlite_autoincrement(self):
        """
        Fix SQLite AUTOINCREMENT for tables with BigInteger primary keys.

        SQLAlchemy creates BigInteger columns which don't trigger SQLite's AUTOINCREMENT.
        This method recreates affected tables with INTEGER PRIMARY KEY AUTOINCREMENT.
        """
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        tables_to_fix = [
            'node_configurations',
            'reference_types',
            'node_facts',
            'patterns',
            'pattern_matches',
            'association_facts',
            'node_relationships'
            # Add other tables with BigInteger PKs as needed
        ]

        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            for table_name in tables_to_fix:
                if table_name not in inspector.get_table_names():
                    continue

                # Remove any abandoned backup table from previous runs
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}_old"))
                conn.commit()

                # Check if table needs fixing
                result = conn.execute(text(
                    f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                ))
                row = result.fetchone()

                if not row or not row[0]:
                    continue

                table_sql = row[0]
                table_sql_upper = table_sql.upper()
                needs_autoincrement = 'AUTOINCREMENT' not in table_sql_upper
                has_old_references = '_old' in table_sql

                if not needs_autoincrement and not has_old_references:
                    continue

                if needs_autoincrement and has_old_references:
                    logger.info(f"Fixing AUTOINCREMENT and cleaning _old references for table: {table_name}")
                elif needs_autoincrement:
                    logger.info(f"Fixing AUTOINCREMENT for table: {table_name}")
                else:
                    logger.info(f"Cleaning stale _old references for table: {table_name}")

                fixed_sql = table_sql

                if needs_autoincrement:
                    # Step 1: Replace all BIGINT with INTEGER (for foreign keys and primary key)
                    fixed_sql = fixed_sql.replace('BIGINT', 'INTEGER')

                    # Step 2: Fix the primary key column specifically
                    # Use regex to match ONLY the standalone 'id' column (with word boundary or tab/space before it)
                    # This prevents matching node_fact_id, pattern_id, etc.
                    fixed_sql = re.sub(
                        r'(\s)id INTEGER NOT NULL',  # Match 'id' preceded by whitespace
                        r'\1id INTEGER PRIMARY KEY AUTOINCREMENT',
                        fixed_sql
                    )

                    # Step 3: Remove the separate PRIMARY KEY constraint
                    fixed_sql = fixed_sql.replace(
                        'PRIMARY KEY (id)',
                        ''
                    ).replace('  ,', ',').replace(' ,', ',').replace('\n\t,\n', '\n\t')

                    # Clean up extra whitespace and commas
                    fixed_sql = re.sub(r'\n\s*,\s*\n\s*', '\n\t', fixed_sql)

                # Fix any stray references to *_old tables created during temporary renames
                fixed_sql = re.sub(
                    r'(REFERENCES\s+)("?)([A-Za-z_][A-Za-z0-9_]*?)_old("?)',
                    lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}",
                    fixed_sql
                )
                fixed_sql = re.sub(r'"([A-Za-z0-9_]+)_old"', r'"\1"', fixed_sql)
                fixed_sql = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)_old\b', r'\1', fixed_sql)

                # Remove any trailing commas before closing parenthesis
                fixed_sql = re.sub(r',\s*\)', '\n)', fixed_sql)

                # Clean up any leftover backup tables from previous failed attempts
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}_old"))
                conn.commit()

                # Backup data
                conn.execute(text(f"ALTER TABLE {table_name} RENAME TO {table_name}_old"))

                # Create new table
                conn.execute(text(fixed_sql))

                # Copy data if any exists
                try:
                    conn.execute(text(
                        f"INSERT INTO {table_name} SELECT * FROM {table_name}_old"
                    ))
                    conn.execute(text(f"DROP TABLE {table_name}_old"))
                except Exception as e:
                    # No data to copy or copy failed
                    logger.warning(f"Could not copy data from {table_name}_old: {e}")
                    try:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}_old"))
                    except Exception as drop_error:
                        logger.warning(f"Could not drop {table_name}_old: {drop_error}")

                conn.commit()
                logger.info(f"Successfully updated table definition for {table_name}")

            conn.execute(text("PRAGMA foreign_keys=ON"))

    def _ensure_pattern_matches_schema(self):
        """Ensure pattern_matches table supports nullable pattern_id and autoincrement IDs."""
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        if "pattern_matches" not in inspector.get_table_names():
            return

        with self.engine.connect() as conn:
            info = conn.execute(text("PRAGMA table_info(pattern_matches)")).fetchall()
            pattern_column = next((row for row in info if row[1] == "pattern_id"), None)
            id_column = next((row for row in info if row[1] == "id"), None)

            if not pattern_column:
                return

            need_nullable_pattern = pattern_column[3] == 1  # notnull flag

            create_sql = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='pattern_matches'")
            ).scalar() or ""
            needs_autoincrement = "PRIMARY KEY AUTOINCREMENT" not in create_sql.upper()
            if id_column:
                id_type = (id_column[2] or "").upper()
                if id_type not in ("INTEGER", "INT"):
                    needs_autoincrement = True

            if not need_nullable_pattern and not needs_autoincrement:
                return

            logger.info("Rebuilding pattern_matches table to enforce nullable pattern_id and autoincrement id")
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("ALTER TABLE pattern_matches RENAME TO pattern_matches_old"))

            conn.execute(text("""
                CREATE TABLE pattern_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id VARCHAR(50) NOT NULL,
                    node_fact_id INTEGER NOT NULL,
                    pattern_id INTEGER,
                    confidence DECIMAL(4, 3) NOT NULL,
                    verdict VARCHAR(20) NOT NULL,
                    match_metadata JSON,
                    created_at DATETIME,
                    FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE,
                    FOREIGN KEY(node_fact_id) REFERENCES node_facts (id) ON DELETE CASCADE,
                    FOREIGN KEY(pattern_id) REFERENCES patterns (id) ON DELETE CASCADE
                )
            """))

            conn.execute(text("""
                INSERT INTO pattern_matches (id, run_id, node_fact_id, pattern_id, confidence, verdict, match_metadata, created_at)
                SELECT id, run_id, node_fact_id, pattern_id, confidence, verdict, match_metadata, created_at
                FROM pattern_matches_old
            """))

            conn.execute(text("DROP TABLE pattern_matches_old"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

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
