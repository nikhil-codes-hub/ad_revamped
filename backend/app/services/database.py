"""
Database session utilities for AssistedDiscovery.

Provides database session management, connection handling, and utility functions
for interacting with the MySQL database through SQLAlchemy ORM.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.database import Base

logger = logging.getLogger(__name__)

# Global engine instance
engine = None
SessionLocal = None


def init_database():
    """Initialize database engine and session factory."""
    global engine, SessionLocal

    try:
        # Create database engine
        engine = create_engine(
            settings.mysql_url,
            echo=settings.DEBUG,  # Log SQL queries in debug mode
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,  # Recycle connections every hour
            pool_pre_ping=True   # Verify connections before use
        )

        # Create session factory
        SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False
        )

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.

    Yields:
        Session: SQLAlchemy database session
    """
    if SessionLocal is None:
        init_database()

    session = SessionLocal()
    try:
        yield session
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Get database session as context manager.

    Usage:
        with get_db_context() as session:
            # Use session here

    Yields:
        Session: SQLAlchemy database session
    """
    if SessionLocal is None:
        init_database()

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database context error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def create_session() -> Session:
    """
    Create a new database session.

    Note: Caller is responsible for closing the session.

    Returns:
        Session: SQLAlchemy database session
    """
    if SessionLocal is None:
        init_database()

    return SessionLocal()


def test_database_connection() -> bool:
    """
    Test database connection.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        from sqlalchemy import text
        with get_db_context() as session:
            # Execute a simple query
            session.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


# Initialize database on module import
try:
    init_database()
except Exception as e:
    logger.warning(f"Database initialization failed during import: {e}")
    # Don't fail module import, let individual functions handle initialization