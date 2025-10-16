# Discovery API Timeout Fix - Technical Solution Document

**Issue ID**: CRITICAL-001
**Date Created**: October 15, 2025
**Status**: Solution Proposed - Ready for Implementation
**Priority**: CRITICAL

---

## Problem Statement

### Issue Description
Discovery API times out when more than 20 nodes are enabled during NodeConfig. The current timeout is set to 10 minutes, and if the API takes longer than 10 minutes, an error message is displayed to the user.

**Reported By**: Maxence Barnet
**Date Reported**: October 15, 2025
**Affected Component**: `backend/app/services/discovery_workflow.py`

### Current Behavior
- Discovery processes nodes **sequentially** in a for-loop
- Each node waits for:
  1. LLM API call (5-30 seconds per node depending on complexity)
  2. Response parsing and validation (1-2 seconds)
  3. Database write operation (1-2 seconds)
  4. Only then moves to the next node

**Performance Impact**:
- 20 nodes × 30 seconds average = **600 seconds (10 minutes)**
- 30 nodes × 30 seconds average = **900 seconds (15 minutes)** → TIMEOUT
- Processing time scales **linearly** with node count

### Root Cause
Sequential processing architecture in `discovery_workflow.py:458-569`:

```python
for subtree in parser.parse_stream(xml_file_path):
    # ... version detection ...
    # ... LLM extraction for each node ...
    llm_result = llm_extractor.extract_from_subtree_sync(subtree, context)
    # ... store to database ...
    facts_stored = self._store_llm_node_facts(run_id, subtree, llm_result)
```

---

## Proposed Solution

### High-Level Approach
Implement **parallel processing using Python's `concurrent.futures.ThreadPoolExecutor`** to process multiple nodes concurrently while maintaining database integrity and handling errors gracefully.

### Why ThreadPoolExecutor?

| Feature | ThreadPoolExecutor | Basic Threading | asyncio |
|---------|-------------------|-----------------|---------|
| Resource Management | ✅ Auto-managed pool | ❌ Manual management | ✅ Auto-managed |
| Error Handling | ✅ Futures with exceptions | ❌ Complex | ✅ Tasks with exceptions |
| Database Compatibility | ✅ Works well with SQLAlchemy | ⚠️ Requires care | ⚠️ Needs async driver |
| Backpressure Control | ✅ Built-in via max_workers | ❌ Manual | ✅ Semaphores |
| LLM API Compatibility | ✅ Works with sync/async | ✅ Works | ✅ Native support |
| Implementation Complexity | ⭐⭐ Medium | ⭐⭐⭐ High | ⭐⭐⭐⭐ Very High |

**Decision**: Use **ThreadPoolExecutor** for optimal balance of simplicity, safety, and performance.

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Discovery Workflow                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              XML Parser (Streaming)                         │
│  Yields subtrees: [Subtree1, Subtree2, ..., SubtreeN]      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│          ThreadPoolExecutor (max_workers=10)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Thread 1 │  │ Thread 2 │  │ Thread 3 │  │ Thread N │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │             │          │
│       ▼             ▼              ▼             ▼          │
│  ┌────────┐   ┌────────┐    ┌────────┐    ┌────────┐     │
│  │ LLM    │   │ LLM    │    │ LLM    │    │ LLM    │     │
│  │ Call 1 │   │ Call 2 │    │ Call 3 │    │ Call N │     │
│  └────┬───┘   └────┬───┘    └────┬───┘    └────┬───┘     │
│       │            │             │             │           │
│       ▼            ▼             ▼             ▼           │
│  ┌────────┐   ┌────────┐    ┌────────┐    ┌────────┐     │
│  │ Parse  │   │ Parse  │    │ Parse  │    │ Parse  │     │
│  └────┬───┘   └────┬───┘    └────┬───┘    └────┬───┘     │
└───────┼────────────┼─────────────┼─────────────┼──────────┘
        │            │             │             │
        ▼            ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│         Thread-Safe Database Session Manager                │
│  (Scoped sessions per thread with write locks)              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Components

#### 1. Thread-Safe Database Session Manager

```python
from sqlalchemy.orm import scoped_session, sessionmaker
import threading

class ThreadSafeDatabaseManager:
    """Manages database sessions for concurrent operations."""

    def __init__(self, engine):
        self.session_factory = sessionmaker(bind=engine)
        self.scoped_session = scoped_session(self.session_factory)
        self.write_lock = threading.Lock()

    def get_session(self):
        """Get thread-local database session."""
        return self.scoped_session()

    def write_with_lock(self, write_func):
        """Execute write operation with lock to prevent conflicts."""
        with self.write_lock:
            return write_func()
```

#### 2. Node Processing Function

```python
def process_single_node(
    subtree: XmlSubtree,
    run_id: str,
    version_info: VersionInfo,
    llm_extractor: LLMNodeFactsExtractor,
    db_manager: ThreadSafeDatabaseManager,
    optimization_strategy: str,
    node_configs: Dict
) -> Dict[str, Any]:
    """
    Process a single node (subtree) with LLM extraction and database storage.

    This function is designed to be called in parallel by ThreadPoolExecutor.
    Each thread gets its own database session via scoped_session.

    Returns:
        Dict with processing results including facts_stored count
    """
    try:
        # Apply node config filtering (if applicable)
        if optimization_strategy == "ndc_target_paths":
            if not self._should_extract_node(subtree.path, node_configs):
                logger.info(f"Skipping node {subtree.path} - disabled by NodeConfiguration")
                return {
                    'subtree_path': subtree.path,
                    'status': 'skipped',
                    'facts_stored': 0,
                    'reason': 'disabled_by_config'
                }

        # LLM Extraction
        logger.debug(f"Processing node: {subtree.path}")
        llm_result = llm_extractor.extract_from_subtree_sync(
            subtree,
            context={
                'run_id': run_id,
                'spec_version': version_info.spec_version if version_info else None,
                'message_root': version_info.message_root if version_info else None
            }
        )

        # Thread-safe database write
        def write_facts():
            session = db_manager.get_session()
            try:
                facts_stored = _store_llm_node_facts_with_session(
                    session, run_id, subtree, llm_result
                )
                session.commit()
                return facts_stored
            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()

        facts_stored = db_manager.write_with_lock(write_facts)

        logger.info(f"✅ Processed {subtree.path}: {facts_stored} facts extracted")

        return {
            'subtree_path': subtree.path,
            'status': 'success',
            'facts_stored': facts_stored,
            'confidence': llm_result.confidence_score,
            'processing_time_ms': llm_result.processing_time_ms
        }

    except ValueError as e:
        # LLM extraction errors
        logger.error(f"❌ LLM extraction failed for {subtree.path}: {str(e)}")
        return {
            'subtree_path': subtree.path,
            'status': 'error',
            'facts_stored': 0,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error processing {subtree.path}: {str(e)}")
        return {
            'subtree_path': subtree.path,
            'status': 'error',
            'facts_stored': 0,
            'error': str(e)
        }
```

#### 3. Parallel Processing Loop (Main Implementation)

```python
# In discovery_workflow.py, replace lines 458-569 with:

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
max_workers = min(settings.MAX_PARALLEL_NODES, 10)  # Configurable, default 10
logger.info(f"Starting parallel node processing with {max_workers} workers")

# Initialize thread-safe database manager
db_manager = ThreadSafeDatabaseManager(self.db_session.bind)

# Collect all subtrees first (required for progress tracking)
subtrees_to_process = []
for subtree in parser.parse_stream(xml_file_path):
    # Handle version info if not detected in Phase 1
    if (not version_info and
        not version_updated_during_processing and
        parser.version_info.spec_version):

        logger.info("Version detected during processing: "
                   f"{parser.version_info.spec_version}/"
                   f"{parser.version_info.message_root}")

        self._update_run_version_info(
            run_id,
            parser.version_info.spec_version,
            parser.version_info.message_root,
            airline_code=parser.version_info.airline_code,
            airline_name=parser.version_info.airline_name
        )
        version_updated_during_processing = True
        version_info = parser.version_info
        self.message_root = parser.version_info.message_root

    subtrees_to_process.append(subtree)

logger.info(f"Found {len(subtrees_to_process)} subtrees to process")

# Process subtrees in parallel
subtrees_processed = 0
total_facts_extracted = 0
nodes_skipped_by_config = 0
processing_errors = []

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit all subtrees for processing
    future_to_subtree = {
        executor.submit(
            process_single_node,
            subtree=subtree,
            run_id=run_id,
            version_info=version_info,
            llm_extractor=get_llm_extractor(),
            db_manager=db_manager,
            optimization_strategy=optimization_strategy,
            node_configs=node_configs
        ): subtree
        for subtree in subtrees_to_process
    }

    # Collect results as they complete
    for future in as_completed(future_to_subtree):
        subtree = future_to_subtree[future]

        try:
            result = future.result()  # Get result or raise exception

            if result['status'] == 'success':
                subtrees_processed += 1
                total_facts_extracted += result['facts_stored']
                logger.info(f"Progress: {subtrees_processed}/{len(subtrees_to_process)} "
                           f"nodes processed, {total_facts_extracted} total facts")

            elif result['status'] == 'skipped':
                nodes_skipped_by_config += 1

            elif result['status'] == 'error':
                processing_errors.append({
                    'subtree_path': result['subtree_path'],
                    'error': result['error']
                })
                logger.error(f"Error processing {result['subtree_path']}: {result['error']}")

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
```

---

## Configuration Changes

### 1. Add to `backend/app/core/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Parallel Processing Configuration
    MAX_PARALLEL_NODES: int = Field(
        default=10,
        env="MAX_PARALLEL_NODES",
        description="Maximum number of nodes to process in parallel during Discovery"
    )

    ENABLE_PARALLEL_PROCESSING: bool = Field(
        default=True,
        env="ENABLE_PARALLEL_PROCESSING",
        description="Enable parallel node processing (set to False for debugging)"
    )
```

### 2. Add to `.env` file

```bash
# Parallel Processing Settings
MAX_PARALLEL_NODES=10          # Adjust based on LLM rate limits
ENABLE_PARALLEL_PROCESSING=true # Set to false for debugging
```

---

## Performance Analysis

### Expected Performance Improvement

| Nodes | Sequential (Current) | Parallel (10 workers) | Improvement |
|-------|---------------------|----------------------|-------------|
| 10 | 300s (5 min) | 30s | **90% faster** |
| 20 | 600s (10 min) | 60s (1 min) | **90% faster** |
| 30 | 900s (15 min) | 90s (1.5 min) | **90% faster** |
| 50 | 1500s (25 min) | 150s (2.5 min) | **90% faster** |

**Formula**:
- Sequential: `time = nodes × avg_time_per_node`
- Parallel: `time = (nodes / workers) × avg_time_per_node`

### Resource Utilization

**CPU**: Low to Medium (mostly I/O bound waiting for LLM API)
**Memory**: ~50MB per thread (XMLsubtree + LLM response buffers)
**Database Connections**: 1 connection per thread (max 10)
**Network**: Parallel LLM API calls (limited by Azure/OpenAI rate limits)

---

## Risk Mitigation

### 1. LLM Rate Limits
**Risk**: Parallel requests may exceed Azure/OpenAI rate limits
**Mitigation**:
- Configurable `MAX_PARALLEL_NODES` (default: 10)
- Monitor rate limit errors and implement exponential backoff
- Consider implementing request queuing if rate limits are hit

### 2. Database Deadlocks
**Risk**: Concurrent writes could cause deadlocks
**Mitigation**:
- Use thread-local scoped sessions
- Implement write locks for database operations
- Each thread commits independently

### 3. Memory Consumption
**Risk**: Processing many large nodes in parallel could consume excessive memory
**Mitigation**:
- Limit `max_workers` to 10 (configurable)
- Monitor memory usage during testing
- Consider implementing batch processing for very large XMLs

### 4. Error Handling
**Risk**: One node failure could impact overall workflow
**Mitigation**:
- Isolate errors per node using try/except in `process_single_node`
- Collect all errors and report at the end
- Continue processing other nodes even if some fail

---

## Testing Strategy

### Unit Tests
- [ ] Test `process_single_node` function with mock LLM responses
- [ ] Test thread-safe database session management
- [ ] Test error handling and isolation

### Integration Tests
- [ ] Test with 10, 20, 30, 50 nodes
- [ ] Test with intentional node failures
- [ ] Test database concurrency and integrity
- [ ] Test LLM rate limit handling

### Performance Tests
- [ ] Benchmark sequential vs parallel processing
- [ ] Measure memory consumption with varying `max_workers`
- [ ] Test with production-sized XML files

### Load Tests
- [ ] Test concurrent API requests with parallel processing
- [ ] Monitor LLM API usage and rate limits
- [ ] Verify database connection pool handling

---

## Implementation Checklist

### Phase 1: Core Implementation
- [ ] Create `ThreadSafeDatabaseManager` class
- [ ] Implement `process_single_node` function
- [ ] Refactor `discovery_workflow.py` parallel processing loop
- [ ] Add configuration settings to `config.py`
- [ ] Update `.env.example` with new settings

### Phase 2: Testing
- [ ] Write unit tests for parallel processing components
- [ ] Write integration tests with sample XML files
- [ ] Perform performance benchmarking
- [ ] Test error scenarios and edge cases

### Phase 3: Documentation
- [ ] Update API documentation
- [ ] Add inline code comments
- [ ] Document configuration options
- [ ] Create troubleshooting guide

### Phase 4: Deployment
- [ ] Code review
- [ ] Merge to feature branch
- [ ] Deploy to staging environment
- [ ] Performance validation in staging
- [ ] Deploy to production

---

## Rollback Plan

If issues are encountered in production:

1. **Immediate**: Set `ENABLE_PARALLEL_PROCESSING=false` in `.env`
2. **Service restart**: Application will revert to sequential processing
3. **Monitoring**: Check logs for specific error patterns
4. **Fix**: Address issues in development environment
5. **Re-deploy**: After thorough testing

---

## Success Criteria

- [ ] Discovery API completes 30+ nodes within 10-minute timeout
- [ ] No database integrity issues (deadlocks, corruption)
- [ ] Error handling properly isolates failures
- [ ] Memory usage remains within acceptable limits
- [ ] LLM rate limits are not exceeded
- [ ] All existing functionality continues to work
- [ ] Performance improvement of at least 80% for 20+ nodes

---

## Estimated Effort

**Development**: 2-3 days
**Testing**: 1-2 days
**Documentation**: 0.5 days
**Total**: 3.5-5.5 days

---

**Document Owner**: AssistedDiscovery Development Team
**Last Updated**: October 15, 2025
**Implementation Status**: Awaiting Approval
