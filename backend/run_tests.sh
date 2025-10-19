#!/bin/bash
# Test runner script for AssistedDiscovery backend
# Usage: ./run_tests.sh [options]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AssistedDiscovery Test Suite Runner${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}ERROR: pytest is not installed${NC}"
    echo "Install with: pip install -r requirements.txt"
    exit 1
fi

# Default options
COVERAGE=false
VERBOSE=false
TEST_PATH="tests/"
HTML_REPORT=false
MARKERS=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --unit|-u)
            TEST_PATH="tests/unit/"
            shift
            ;;
        --integration|-i)
            TEST_PATH="tests/integration/"
            shift
            ;;
        --html)
            HTML_REPORT=true
            shift
            ;;
        --markers|-m)
            MARKERS="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  -c, --coverage      Run with coverage report"
            echo "  -v, --verbose       Verbose output"
            echo "  -u, --unit          Run only unit tests"
            echo "  -i, --integration   Run only integration tests"
            echo "  --html              Generate HTML coverage report"
            echo "  -m, --markers       Run tests with specific markers"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_tests.sh                    # Run all tests"
            echo "  ./run_tests.sh -c                 # Run with coverage"
            echo "  ./run_tests.sh -u -v              # Run unit tests verbosely"
            echo "  ./run_tests.sh -c --html          # Generate HTML coverage report"
            echo "  ./run_tests.sh -m critical        # Run only critical tests"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest ${TEST_PATH}"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=term"
    if [ "$HTML_REPORT" = true ]; then
        PYTEST_CMD="$PYTEST_CMD --cov-report=html"
    fi
fi

if [ -n "$MARKERS" ]; then
    PYTEST_CMD="$PYTEST_CMD -m $MARKERS"
fi

# Print configuration
echo -e "${YELLOW}Configuration:${NC}"
echo "  Test path: $TEST_PATH"
echo "  Coverage: $COVERAGE"
echo "  Verbose: $VERBOSE"
echo "  HTML Report: $HTML_REPORT"
if [ -n "$MARKERS" ]; then
    echo "  Markers: $MARKERS"
fi
echo ""

# Run tests
echo -e "${YELLOW}Running tests...${NC}\n"
eval $PYTEST_CMD

# Check exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}All tests passed! ✅${NC}"
    echo -e "${GREEN}========================================${NC}"

    if [ "$HTML_REPORT" = true ]; then
        echo -e "\n${YELLOW}HTML coverage report generated in: htmlcov/index.html${NC}"
    fi
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}Tests failed! ❌${NC}"
    echo -e "${RED}========================================${NC}"
    exit $EXIT_CODE
fi

exit 0
