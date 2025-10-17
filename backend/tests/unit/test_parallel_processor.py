"""
Unit tests for parallel processing functions.

Tests parallel processing functionality including:
- Thread-safe database management
- Node processing results
- Parallel execution coordination
"""
import pytest
from app.services.parallel_processor import ThreadSafeDatabaseManager, NodeProcessingResult


class TestNodeProcessingResult:
    """Test suite for NodeProcessingResult."""

    def test_create_result_success(self):
        """Test creating a successful result."""
        result = NodeProcessingResult(
            subtree_path="/Response/DataLists/PaxList",
            status="success",
            facts_stored=5,
            confidence=0.95,
            processing_time_ms=100
        )

        assert result.status == "success"
        assert result.facts_stored == 5
        assert result.confidence == 0.95

    def test_create_result_error(self):
        """Test creating an error result."""
        result = NodeProcessingResult(
            subtree_path="/Response/DataLists/PaxList",
            status="error",
            facts_stored=0,
            error="LLM extraction failed"
        )

        assert result.status == "error"
        assert result.facts_stored == 0
        assert result.error is not None

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = NodeProcessingResult(
            subtree_path="/Response/DataLists/PaxList",
            status="success",
            facts_stored=3
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["status"] == "success"
        assert result_dict["facts_stored"] == 3


class TestThreadSafeDatabaseManager:
    """Test suite for ThreadSafeDatabaseManager."""

    def test_create_manager(self, test_db_engine):
        """Test creating database manager."""
        manager = ThreadSafeDatabaseManager(test_db_engine)

        assert manager is not None
        assert manager.engine == test_db_engine

    def test_get_session(self, test_db_engine):
        """Test getting a session."""
        manager = ThreadSafeDatabaseManager(test_db_engine)
        session = manager.get_session()

        assert session is not None
        session.close()

    def test_write_with_lock(self, test_db_engine):
        """Test write operation with lock."""
        manager = ThreadSafeDatabaseManager(test_db_engine)

        result = []

        def write_func():
            result.append("written")
            return len(result)

        count = manager.write_with_lock(write_func)

        assert count == 1
        assert len(result) == 1

    def test_cleanup_session(self, test_db_engine):
        """Test session cleanup."""
        manager = ThreadSafeDatabaseManager(test_db_engine)
        session = manager.get_session()

        # Should not raise error
        manager.cleanup_session()
        success = True

        assert success is True
