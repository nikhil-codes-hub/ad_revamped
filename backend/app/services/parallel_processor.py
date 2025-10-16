"""
Parallel processing utilities for AssistedDiscovery.

Provides thread-safe database session management and parallel node processing
to improve Discovery workflow performance with large numbers of nodes.
"""

import logging
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.services.xml_parser import XmlSubtree
from app.services.llm_extractor import LLMNodeFactsExtractor, LLMExtractionResult
from app.models.database import NodeFact

logger = logging.getLogger(__name__)


class ThreadSafeDatabaseManager:
    """
    Manages database sessions for concurrent operations.

    Provides thread-local sessions and write locks to ensure database
    integrity during parallel processing.
    """

    def __init__(self, engine):
        """
        Initialize database manager with engine.

        Args:
            engine: SQLAlchemy engine instance
        """
        self.engine = engine
        self.session_factory = sessionmaker(bind=engine)
        self.scoped_session_factory = scoped_session(self.session_factory)
        self.write_lock = threading.Lock()

        logger.info("ThreadSafeDatabaseManager initialized")

    def get_session(self) -> Session:
        """
        Get thread-local database session.

        Returns:
            SQLAlchemy Session instance scoped to current thread
        """
        return self.scoped_session_factory()

    def write_with_lock(self, write_func: Callable) -> Any:
        """
        Execute write operation with lock to prevent conflicts.

        Args:
            write_func: Function that performs database write operations

        Returns:
            Result from write_func
        """
        with self.write_lock:
            return write_func()

    def cleanup_session(self):
        """Remove thread-local session."""
        self.scoped_session_factory.remove()


class NodeProcessingResult:
    """Result from processing a single node."""

    def __init__(self, subtree_path: str, status: str, facts_stored: int = 0,
                 confidence: float = 0.0, processing_time_ms: int = 0,
                 error: Optional[str] = None):
        self.subtree_path = subtree_path
        self.status = status  # 'success', 'skipped', 'error'
        self.facts_stored = facts_stored
        self.confidence = confidence
        self.processing_time_ms = processing_time_ms
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'subtree_path': self.subtree_path,
            'status': self.status,
            'facts_stored': self.facts_stored,
            'confidence': self.confidence,
            'processing_time_ms': self.processing_time_ms,
            'error': self.error
        }


def _store_llm_node_facts_with_session(
    session: Session,
    run_id: str,
    spec_version: str,
    message_root: str,
    subtree: XmlSubtree,
    llm_result: LLMExtractionResult
) -> int:
    """
    Store LLM-extracted node facts using provided session.

    This is a standalone function that can be used in parallel processing
    with different database sessions.

    Args:
        session: SQLAlchemy session to use
        run_id: Run identifier
        spec_version: NDC spec version
        message_root: Message root (e.g., OrderViewRS)
        subtree: XML subtree that was processed
        llm_result: LLM extraction result

    Returns:
        Number of node facts stored
    """
    node_facts_stored = 0

    for fact_data in llm_result.node_facts:
        node_fact = NodeFact(
            run_id=run_id,
            spec_version=spec_version,
            message_root=message_root,
            section_path=subtree.path,
            node_type=fact_data['node_type'],
            node_ordinal=fact_data['node_ordinal'],
            fact_json=fact_data,
            pii_masked=settings.PII_MASKING_ENABLED,
            created_at=datetime.utcnow()
        )

        session.add(node_fact)
        node_facts_stored += 1

    return node_facts_stored


def process_single_node(
    subtree: XmlSubtree,
    run_id: str,
    spec_version: str,
    message_root: str,
    llm_extractor: LLMNodeFactsExtractor,
    db_manager: ThreadSafeDatabaseManager,
    optimization_strategy: str,
    node_configs: Dict,
    should_extract_func: Optional[Callable] = None
) -> NodeProcessingResult:
    """
    Process a single node (subtree) with LLM extraction and database storage.

    This function is designed to be called in parallel by ThreadPoolExecutor.
    Each thread gets its own database session via scoped_session.

    Args:
        subtree: XML subtree to process
        run_id: Run identifier
        spec_version: NDC spec version
        message_root: Message root (e.g., OrderViewRS)
        llm_extractor: LLM extractor instance
        db_manager: Thread-safe database manager
        optimization_strategy: Strategy being used (for filtering logic)
        node_configs: Node configurations for filtering
        should_extract_func: Optional function to check if node should be extracted

    Returns:
        NodeProcessingResult with processing details
    """
    start_time = datetime.now()

    try:
        # Apply node config filtering (if applicable)
        if optimization_strategy == "ndc_target_paths" and should_extract_func:
            if not should_extract_func(subtree.path, node_configs):
                logger.info(f"Skipping node {subtree.path} - disabled by NodeConfiguration")
                return NodeProcessingResult(
                    subtree_path=subtree.path,
                    status='skipped',
                    facts_stored=0
                )

        # LLM Extraction
        logger.debug(f"[Thread-{threading.current_thread().name}] Processing node: {subtree.path}")

        llm_result = llm_extractor.extract_from_subtree_sync(
            subtree,
            context={
                'run_id': run_id,
                'spec_version': spec_version,
                'message_root': message_root
            }
        )

        # Thread-safe database write
        def write_facts():
            session = db_manager.get_session()
            try:
                facts_stored = _store_llm_node_facts_with_session(
                    session, run_id, spec_version, message_root, subtree, llm_result
                )
                session.commit()
                logger.debug(f"Stored {facts_stored} facts for {subtree.path}")
                return facts_stored
            except Exception as e:
                session.rollback()
                logger.error(f"Database error for {subtree.path}: {e}")
                raise
            finally:
                session.close()

        facts_stored = db_manager.write_with_lock(write_facts)

        total_time = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(f"✅ [Thread-{threading.current_thread().name}] "
                   f"Processed {subtree.path}: {facts_stored} facts "
                   f"(confidence: {llm_result.confidence_score:.2f}, time: {total_time}ms)")

        return NodeProcessingResult(
            subtree_path=subtree.path,
            status='success',
            facts_stored=facts_stored,
            confidence=llm_result.confidence_score,
            processing_time_ms=total_time
        )

    except ValueError as e:
        # LLM extraction errors (these are user-friendly error messages)
        logger.error(f"❌ LLM extraction failed for {subtree.path}: {str(e)}")
        total_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return NodeProcessingResult(
            subtree_path=subtree.path,
            status='error',
            facts_stored=0,
            processing_time_ms=total_time,
            error=str(e)
        )

    except Exception as e:
        # Unexpected errors
        logger.error(f"❌ Unexpected error processing {subtree.path}: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        total_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return NodeProcessingResult(
            subtree_path=subtree.path,
            status='error',
            facts_stored=0,
            processing_time_ms=total_time,
            error=f"{type(e).__name__}: {str(e)}"
        )


def process_nodes_parallel(
    subtrees: list,
    run_id: str,
    spec_version: str,
    message_root: str,
    llm_extractor: LLMNodeFactsExtractor,
    db_manager: ThreadSafeDatabaseManager,
    optimization_strategy: str,
    node_configs: Dict,
    max_workers: int,
    should_extract_func: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Process multiple nodes in parallel using ThreadPoolExecutor.

    Args:
        subtrees: List of XML subtrees to process
        run_id: Run identifier
        spec_version: NDC spec version
        message_root: Message root
        llm_extractor: LLM extractor instance
        db_manager: Thread-safe database manager
        optimization_strategy: Strategy being used
        node_configs: Node configurations
        max_workers: Maximum number of parallel workers
        should_extract_func: Optional function to check if node should be extracted

    Returns:
        Dictionary with processing results and statistics
    """
    logger.info(f"Starting parallel processing of {len(subtrees)} nodes with {max_workers} workers")

    subtrees_processed = 0
    total_facts_extracted = 0
    nodes_skipped_by_config = 0
    processing_errors = []
    processing_results = []

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="NodeProc") as executor:
        # Submit all subtrees for processing
        future_to_subtree = {
            executor.submit(
                process_single_node,
                subtree=subtree,
                run_id=run_id,
                spec_version=spec_version,
                message_root=message_root,
                llm_extractor=llm_extractor,
                db_manager=db_manager,
                optimization_strategy=optimization_strategy,
                node_configs=node_configs,
                should_extract_func=should_extract_func
            ): subtree
            for subtree in subtrees
        }

        # Collect results as they complete
        for future in as_completed(future_to_subtree):
            subtree = future_to_subtree[future]

            try:
                result = future.result()  # Get result or raise exception
                processing_results.append(result)

                if result.status == 'success':
                    subtrees_processed += 1
                    total_facts_extracted += result.facts_stored
                    logger.info(f"Progress: {subtrees_processed}/{len(subtrees)} "
                               f"nodes processed, {total_facts_extracted} total facts")

                elif result.status == 'skipped':
                    nodes_skipped_by_config += 1
                    logger.debug(f"Node skipped: {result.subtree_path}")

                elif result.status == 'error':
                    processing_errors.append({
                        'subtree_path': result.subtree_path,
                        'error': result.error
                    })
                    logger.error(f"Error processing {result.subtree_path}: {result.error}")

            except Exception as e:
                # Catch any exceptions from future.result()
                logger.error(f"Failed to retrieve result for {subtree.path}: {e}")
                processing_errors.append({
                    'subtree_path': subtree.path,
                    'error': str(e)
                })

    # Log summary
    logger.info(f"Parallel processing completed: "
               f"{subtrees_processed} successful, "
               f"{nodes_skipped_by_config} skipped, "
               f"{len(processing_errors)} errors")

    # Handle errors
    if processing_errors:
        error_summary = "\n".join([
            f"  - {err['subtree_path']}: {err['error']}"
            for err in processing_errors[:5]  # Show first 5 errors
        ])
        logger.warning(f"Processing errors encountered:\n{error_summary}")
        if len(processing_errors) > 5:
            logger.warning(f"  ... and {len(processing_errors) - 5} more errors")

    return {
        'subtrees_processed': subtrees_processed,
        'total_facts_extracted': total_facts_extracted,
        'nodes_skipped_by_config': nodes_skipped_by_config,
        'processing_errors': processing_errors,
        'processing_results': processing_results,
        'total_nodes': len(subtrees)
    }
