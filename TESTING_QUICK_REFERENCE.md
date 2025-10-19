# Testing Quick Reference Card

## Quick Commands

### Run All Tests
```bash
cd backend
pytest
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=term --cov-report=html
```

### Run Specific Test Suite
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific file
pytest tests/unit/test_pattern_generator.py

# Specific test
pytest tests/unit/test_pattern_generator.py::TestPatternGenerator::test_child_structure_deduplication
```

### Using Test Runner Script
```bash
# Run all tests
./run_tests.sh

# With coverage
./run_tests.sh --coverage

# Unit tests with verbose output
./run_tests.sh --unit --verbose

# Generate HTML coverage report
./run_tests.sh --coverage --html

# View help
./run_tests.sh --help
```

## Test File Locations

```
backend/tests/
├── conftest.py                      # Shared fixtures
├── unit/                            # Unit tests
│   ├── test_pattern_generator.py    # Pattern generation (13 tests)
│   ├── test_xml_parser.py           # XML parsing (15 tests)
│   ├── test_identify_workflow.py    # Identification (12 tests)
│   ├── test_parallel_processor.py   # Parallel processing (10 tests)
│   └── test_utils.py                # Utilities (12 tests)
└── integration/                     # API integration tests
    ├── test_api_patterns.py         # Pattern endpoints (10 tests)
    ├── test_api_discovery.py        # Discovery endpoints (10 tests)
    └── test_api_identify.py         # Identify endpoints (10 tests)
```

## Key Tests for Recent Fixes

### Pattern Deduplication Fix
```bash
# Test that PaxList with different passenger counts creates same pattern
pytest tests/unit/test_pattern_generator.py::TestPatternGenerator::test_child_structure_deduplication
pytest tests/unit/test_pattern_generator.py::TestPatternGenerator::test_child_structure_attribute_intersection
pytest tests/unit/test_pattern_generator.py::TestPatternGenerator::test_child_structure_reference_union
```

### Parallel Processing Fix
```bash
# Test that parallel processing improves performance
pytest tests/unit/test_parallel_processor.py::TestParallelProcessor::test_process_items_parallel
pytest tests/unit/test_parallel_processor.py::TestParallelProcessor::test_result_ordering
```

### Missing Pattern Detection
```bash
# Test missing pattern identification
pytest tests/unit/test_identify_workflow.py::TestIdentifyWorkflow::test_find_missing_patterns
pytest tests/integration/test_api_identify.py::TestIdentifyAPI::test_identify_missing_patterns
```

## Coverage Targets

- **Overall**: > 80%
- **Services**: > 85%
- **Critical paths**: 100%

## View Coverage Report

After running with `--cov-report=html`:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Debugging Failed Tests

```bash
# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Debug with pdb
pytest --pdb

# Verbose output
pytest -vv
```

## Common Pytest Options

| Option | Description |
|--------|-------------|
| `-v` | Verbose output |
| `-vv` | Extra verbose output |
| `-s` | Show print statements |
| `-x` | Stop on first failure |
| `--lf` | Run last failed tests |
| `--pdb` | Drop into debugger on failure |
| `-k EXPRESSION` | Run tests matching expression |
| `-m MARKER` | Run tests with specific marker |
| `--cov=app` | Enable coverage for app module |
| `--cov-report=html` | Generate HTML coverage report |
| `--tb=short` | Shorter traceback format |

## Test Markers

```bash
# Run only slow tests
pytest -m slow

# Run all except slow tests
pytest -m "not slow"

# Run critical tests
pytest -m critical

# Run integration tests
pytest -m integration
```

## CI/CD Command

```bash
pytest \
  --cov=app \
  --cov-report=xml \
  --cov-report=term \
  --cov-fail-under=80 \
  --junitxml=test-results.xml
```

## Test Statistics

- **Total Test Files**: 12
- **Total Test Classes**: 15+
- **Total Test Methods**: 82+
- **Lines of Test Code**: ~2,000

## Documentation

- Full documentation: `backend/tests/README.md`
- Test summary: `TEST_SUITE_SUMMARY.md`
- Configuration: `backend/pytest.ini`

## Getting Help

```bash
# Pytest help
pytest --help

# Test runner help
./run_tests.sh --help

# List all tests without running
pytest --collect-only

# List all markers
pytest --markers
```

## Requirements

All test dependencies are in `backend/requirements.txt`:
- pytest==7.4.3
- pytest-asyncio==0.21.1
- pytest-cov==4.1.0
- httpx==0.25.2

Install with:
```bash
pip install -r requirements.txt
```
