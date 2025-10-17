# AssistedDiscovery Test Suite

Comprehensive test suite for the AssistedDiscovery backend application.

## Overview

This test suite covers:
- **Unit Tests**: Test individual services and functions in isolation
- **Integration Tests**: Test API endpoints and full workflows
- **Test Coverage**: Pattern generation, XML parsing, identification, discovery workflows, and utilities

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures and configuration
├── unit/                                # Unit tests
│   ├── test_pattern_generator.py        # Pattern generation logic
│   ├── test_xml_parser.py               # XML parsing and version detection
│   ├── test_identify_workflow.py        # Pattern matching logic
│   ├── test_parallel_processor.py       # Parallel processing
│   └── test_utils.py                    # Utility functions
└── integration/                         # Integration tests
    ├── test_api_patterns.py             # Pattern API endpoints
    ├── test_api_discovery.py            # Discovery API endpoints
    └── test_api_identify.py             # Identify API endpoints
```

## Running Tests

### Run All Tests

```bash
# From backend directory
pytest

# With coverage report
pytest --cov=app --cov-report=html --cov-report=term

# With verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_pattern_generator.py

# Run specific test class
pytest tests/unit/test_pattern_generator.py::TestPatternGenerator

# Run specific test method
pytest tests/unit/test_pattern_generator.py::TestPatternGenerator::test_child_structure_deduplication
```

### Run Only Unit Tests

```bash
pytest tests/unit/
```

### Run Only Integration Tests

```bash
pytest tests/integration/
```

### Run with Markers

```bash
# Run only fast tests
pytest -m "not slow"

# Run only critical tests
pytest -m critical
```

## Test Coverage

### Unit Tests

#### test_pattern_generator.py
- ✅ Extract required attributes (filters metadata)
- ✅ Child structure deduplication by node_type
- ✅ Attribute intersection for required fields
- ✅ Reference field union across instances
- ✅ Signature hash consistency and uniqueness
- ✅ Pattern creation and updates
- ✅ Decision rule generation
- ✅ Path normalization
- ✅ Optional attribute detection
- ✅ Pattern generation from runs

#### test_xml_parser.py
- ✅ Path trie construction and matching
- ✅ NDC version detection (namespace, attributes, PayloadAttributes)
- ✅ Airline detection (Order/@Owner, BookingReference, CarrierInfo)
- ✅ Streaming XML parsing with target extraction
- ✅ IATA_ prefix normalization
- ✅ Malformed XML handling with recovery mode
- ✅ Version-specific parser creation

#### test_identify_workflow.py
- ✅ Path normalization
- ✅ Match score calculation (perfect, missing required, extra attributes)
- ✅ Node structure extraction from XML
- ✅ Pattern structure matching
- ✅ Quality alert generation (orphaned references)
- ✅ Missing pattern detection
- ✅ Pattern deduplication by signature
- ✅ XML structure validation
- ✅ Reference extraction from XML
- ✅ Child structure matching

#### test_parallel_processor.py
- ✅ Sequential processing
- ✅ Parallel processing with performance verification
- ✅ Error handling in parallel tasks
- ✅ Empty list and single item handling
- ✅ Max workers limit enforcement
- ✅ Different data type processing
- ✅ Task timeout handling
- ✅ Result ordering preservation

#### test_utils.py
- ✅ IATA prefix normalization (various message types)
- ✅ Path sanitization (leading/trailing slashes)
- ✅ Multiple slash handling
- ✅ Namespace extraction from tags
- ✅ Edge cases (empty paths, unicode, case preservation)

### Integration Tests

#### test_api_patterns.py
- ✅ List patterns (empty, with filters, pagination)
- ✅ Get pattern by ID
- ✅ Pattern not found handling
- ✅ Pattern regeneration
- ✅ Delete pattern
- ✅ Filter by airline code
- ✅ Pattern examples retrieval
- ✅ Pattern statistics

#### test_api_discovery.py
- ✅ List discovery runs (empty, with filters, pagination)
- ✅ Get run by ID
- ✅ Run not found handling
- ✅ Upload XML for discovery
- ✅ Invalid file type rejection
- ✅ Get node facts for run
- ✅ Delete run
- ✅ Run status tracking
- ✅ Version detection endpoint

#### test_api_identify.py
- ✅ Identify XML with existing patterns
- ✅ Identify XML with no patterns
- ✅ Invalid XML handling
- ✅ Version mismatch detection
- ✅ Quality alert generation
- ✅ Missing pattern detection
- ✅ Response structure validation
- ✅ Airline-specific pattern filtering
- ✅ Performance test with large XML (100+ elements)

## Key Test Scenarios

### Pattern Generation Deduplication (Critical)
Tests verify that the recent fix for pattern generation is working correctly:
- Same node type with different instances creates ONE pattern
- Child structures are deduplicated by node_type
- Required attributes use intersection logic
- Reference fields use union logic

```python
# Example: PaxList with 2 adults vs 1 adult + 1 child
# Should create SAME pattern (structure matters, not quantity)
```

### Parallel Processing (Performance)
Tests verify the parallel processing fix for Discovery API timeouts:
- Tasks execute in parallel with thread pools
- Performance improvement over sequential
- Error handling maintains stability
- Result ordering is preserved

### Missing Pattern Detection (Quality)
Tests verify the identify workflow correctly detects missing patterns:
- Patterns in library but not in XML are reported
- Duplicate patterns are handled correctly
- Pattern variations are distinguished by signature hash

## Fixtures

Common fixtures available in `conftest.py`:

- `db_session`: Clean database session for each test
- `sample_run`: Pre-created Run instance
- `sample_node_fact`: Pre-created NodeFact instance
- `sample_pattern`: Pre-created Pattern instance
- `sample_node_config`: Pre-created NodeConfiguration instance
- `sample_reference_type`: Pre-created ReferenceType instance
- `sample_xml_file`: Temporary XML file with test data
- `mock_llm_response`: Mock LLM response for testing

## Requirements

Tests require the following packages (already in `backend/requirements.txt`):
- pytest==7.4.3
- pytest-asyncio==0.21.1
- pytest-cov==4.1.0
- httpx==0.25.2 (for TestClient)

## Configuration

Tests use in-memory SQLite database for isolation:
- Each test gets a fresh database session
- No impact on development/production databases
- Fast test execution

## Coverage Goals

Target coverage levels:
- **Overall**: > 80%
- **Services**: > 85%
- **Critical paths**: 100% (pattern generation, XML parsing, identification)

## Running in CI/CD

For continuous integration:

```bash
# Run with JUnit XML output
pytest --junitxml=test-results/junit.xml

# Run with coverage and fail if below threshold
pytest --cov=app --cov-fail-under=80

# Run with HTML coverage report for CI artifacts
pytest --cov=app --cov-report=html:coverage-report
```

## Debugging Tests

```bash
# Run with print statements visible
pytest -s

# Run with debugger on failure
pytest --pdb

# Run last failed tests only
pytest --lf

# Show detailed traceback
pytest --tb=long
```

## Writing New Tests

When adding new tests:

1. **Unit tests** go in `tests/unit/test_<module>.py`
2. **Integration tests** go in `tests/integration/test_api_<feature>.py`
3. Use fixtures from `conftest.py` when possible
4. Follow existing naming conventions: `test_<function>_<scenario>`
5. Add docstrings explaining what is being tested
6. Test both success and failure cases

Example:

```python
def test_pattern_creation_success(self, db_session: Session):
    """Test creating a new pattern with valid data."""
    # Arrange
    generator = PatternGenerator(db_session)
    decision_rule = {...}

    # Act
    pattern = generator.find_or_create_pattern(...)

    # Assert
    assert pattern.id is not None
    assert pattern.times_seen == 1
```

## Known Issues / TODO

- [ ] Add tests for LLM extraction service (requires mocking Azure OpenAI)
- [ ] Add tests for relationship analyzer
- [ ] Add tests for business intelligence extraction
- [ ] Add performance benchmarks for large XML files (>10MB)
- [ ] Add stress tests for concurrent requests

## Contributing

When contributing new features:
1. Write tests FIRST (TDD approach)
2. Ensure all existing tests pass
3. Aim for > 80% coverage on new code
4. Run `pytest --cov=app` before submitting PR

## Support

For test-related questions, see:
- Test documentation: This README
- Pytest docs: https://docs.pytest.org/
- FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/
