# VS Code Test Configuration Guide

## Quick Start

Your VS Code is now configured with comprehensive test runners!

### How to Run Tests

**Method 1: Using Debug Panel (F5)**
1. Press `F5` or click the Debug icon in the sidebar
2. Select from the dropdown:
   - `AD 🧪 Run All Tests` - Run all unit + integration tests
   - `AD 🧪 Run Unit Tests` - Run only unit tests (fast)
   - `AD 🧪 Run Integration Tests` - Run only integration tests
   - `AD 📊 Run Tests with Coverage` - Generate coverage report
   - `AD 🎯 Run Current Test File` - Run the test file you're viewing
   - `AD 🔍 Debug Current Test` - Debug with breakpoints
   - `AD ⏮️ Re-run Failed Tests` - Only run tests that failed last time

**Method 2: Using Tasks (Cmd+Shift+P → "Run Task")**
1. Press `Cmd+Shift+P` (or `Ctrl+Shift+P` on Windows/Linux)
2. Type "Run Task"
3. Select from:
   - `AD 🧪 Run All Tests` - Default test runner
   - `AD 🧪 Run Unit Tests Only`
   - `AD 🧪 Run Integration Tests Only`
   - `AD 📊 Run Tests with Coverage Report`
   - `AD 📊 Open Coverage HTML Report` - View coverage in browser
   - `AD ⏮️ Re-run Failed Tests`
   - `AD 🧹 Clean Test Cache` - Clear pytest cache

**Method 3: Using Keyboard Shortcuts**
- `Cmd+Shift+B` - Run default build task (runs all tests)
- `F5` - Start debugging selected configuration

---

## Test Configurations Available

### Launch Configurations (For Debugging)

#### 🧪 AD Run All Tests
Runs all tests (unit + integration) with verbose output.
- **When to use**: Full test suite validation
- **Output**: Detailed test results with short tracebacks

#### 🧪 AD Run Unit Tests
Runs only unit tests (fast, 63 tests).
- **When to use**: Quick validation of core logic
- **Output**: 81% pass rate, ~1.3s execution time

#### 🧪 AD Run Integration Tests
Runs only integration tests (42 tests).
- **When to use**: API endpoint testing
- **Output**: Some tests fail due to BigInteger limitation

#### 📊 AD Run Tests with Coverage
Runs unit tests and generates HTML coverage report.
- **When to use**: Checking test coverage
- **Output**: Terminal report + htmlcov/index.html
- **Coverage**: Currently 40%

#### 🎯 AD Run Current Test File
Runs only the test file you're currently viewing.
- **When to use**: Testing specific functionality
- **How**: Open a test file and press F5

#### 🔍 AD Debug Current Test
Debug the current test file with breakpoints.
- **When to use**: Investigating test failures
- **How**: Set breakpoints, open test file, press F5
- **Features**: Step through code, inspect variables

#### ⏮️ AD Re-run Failed Tests
Only runs tests that failed in the last run.
- **When to use**: After fixing failing tests
- **How**: Press F5 after a failed test run
- **Saves**: Time by skipping passing tests

---

## Task Configurations (For Running)

### Available Tasks

**Test Tasks** (Press `Cmd+Shift+P` → "Run Task"):

1. **AD 🧪 Run All Tests** (Default)
   - Command: `pytest tests/ -v --tb=short`
   - Use for: Full validation

2. **AD 🧪 Run Unit Tests Only**
   - Command: `pytest tests/unit/ -v --tb=short`
   - Use for: Quick checks (1.3s)

3. **AD 🧪 Run Integration Tests Only**
   - Command: `pytest tests/integration/ -v --tb=short`
   - Use for: API testing

4. **AD 📊 Run Tests with Coverage Report**
   - Command: `pytest tests/unit/ --cov=app --cov-report=term --cov-report=html -v`
   - Generates: htmlcov/index.html

5. **AD 📊 Open Coverage HTML Report**
   - Opens: htmlcov/index.html in browser
   - Use after: Running coverage task

6. **AD ⏮️ Re-run Failed Tests**
   - Command: `pytest --lf -v --tb=short`
   - Use for: Iterative debugging

7. **AD 🧹 Clean Test Cache**
   - Removes: .pytest_cache, __pycache__, htmlcov, .coverage
   - Use when: Tests behave unexpectedly

---

## Keyboard Shortcuts

### Default Shortcuts

- `F5` - Start Debugging (runs selected launch config)
- `Shift+F5` - Stop Debugging
- `Cmd+Shift+B` - Run Default Build Task (Run All Tests)
- `Cmd+Shift+P` → "Run Task" - Show all available tasks

### Custom Shortcuts (Optional)

You can add these to your `keybindings.json`:

```json
[
    {
        "key": "cmd+shift+t",
        "command": "workbench.action.tasks.runTask",
        "args": "AD 🧪 Run Unit Tests Only"
    },
    {
        "key": "cmd+shift+c",
        "command": "workbench.action.tasks.runTask",
        "args": "AD 📊 Run Tests with Coverage Report"
    }
]
```

---

## Current Test Status

### Unit Tests (tests/unit/)
- **Total**: 78 tests
- **Passing**: 63 (81%)
- **Skipped**: 15 (BigInteger limitation)
- **Coverage**: 32%
- **Speed**: ~1.3 seconds

### Integration Tests (tests/integration/)
- **Total**: 42 tests
- **Passing**: 6 (14%)
- **Failing**: 19 (wrong endpoints)
- **Errors**: 17 (BigInteger limitation)

### Overall
- **Total**: 120 tests
- **Passing**: 69 (58%)
- **Coverage**: 40%

---

## Common Workflows

### Workflow 1: Quick Unit Test Check
```
1. Press Cmd+Shift+P
2. Type "Run Task"
3. Select "AD 🧪 Run Unit Tests Only"
4. View results in terminal (1.3s)
```

### Workflow 2: Debug Failing Test
```
1. Open the failing test file
2. Set breakpoint on failing line
3. Press F5
4. Select "AD 🔍 Debug Current Test"
5. Step through code to find issue
```

### Workflow 3: Check Coverage
```
1. Press Cmd+Shift+P
2. Type "Run Task"
3. Select "AD 📊 Run Tests with Coverage Report"
4. Wait for completion
5. Run "AD 📊 Open Coverage HTML Report"
6. View coverage in browser
```

### Workflow 4: Fix and Re-test
```
1. Run tests (fail)
2. Fix the code
3. Press F5
4. Select "AD ⏮️ Re-run Failed Tests"
5. Repeat until all pass
```

### Workflow 5: Clean Start
```
1. Run "AD 🧹 Clean Test Cache"
2. Run "AD 🧪 Run All Tests"
3. Fresh test results
```

---

## Environment Variables

All test configurations use:
```
PYTHONPATH=${workspaceFolder}/backend
```

This ensures:
- Correct module imports
- Access to app/ modules
- Proper test discovery

---

## Troubleshooting

### Tests Not Found
**Issue**: "No tests collected"
**Solution**:
1. Check you're in backend directory
2. Verify PYTHONPATH is set
3. Run "AD 🧹 Clean Test Cache"

### Import Errors
**Issue**: `ModuleNotFoundError: No module named 'app'`
**Solution**:
1. Check PYTHONPATH includes backend folder
2. Verify you're using the correct Python interpreter (assisted_discovery_env)

### Coverage Not Generated
**Issue**: No htmlcov folder
**Solution**:
1. Run "AD 📊 Run Tests with Coverage Report" first
2. Then run "AD 📊 Open Coverage HTML Report"

### Tests Run Slowly
**Issue**: Tests take too long
**Solution**:
1. Run unit tests only: "AD 🧪 Run Unit Tests Only"
2. Skip integration tests (they have BigInteger issues)

---

## Tips

1. **Fast Feedback**: Use "AD 🧪 Run Unit Tests Only" for quick checks (1.3s)

2. **Coverage Reports**: Run coverage weekly to track improvements

3. **Failed Tests**: Use "AD ⏮️ Re-run Failed Tests" for faster iteration

4. **Debugging**: Set breakpoints and use "AD 🔍 Debug Current Test"

5. **Clean Slate**: Run "AD 🧹 Clean Test Cache" if tests behave oddly

6. **Test File**: Use "AD 🎯 Run Current Test File" when working on specific module

---

## Next Steps

### To Improve Coverage (60% → 95%)

1. **Fix Integration Tests** (10 hours)
   - Skip BigInteger tests
   - Fix API endpoint URLs
   - Result: 65% coverage

2. **Mock LLM Services** (10 hours)
   - Mock OpenAI/Anthropic
   - Test llm_extractor
   - Result: 75% coverage

3. **Add Comprehensive Tests** (10 hours)
   - Endpoint tests
   - Edge cases
   - Error handling
   - Result: 95% coverage

---

## Files Modified

- `.vscode/launch.json` - Added 7 test debug configurations
- `.vscode/tasks.json` - Added 7 test task configurations
- `VSCODE_TEST_GUIDE.md` - This guide

---

**Happy Testing! 🧪**

For questions, see:
- `CLEAN_TEST_SUITE_REPORT.md` - Unit test cleanup
- `FINAL_COVERAGE_REPORT.md` - Complete coverage analysis
