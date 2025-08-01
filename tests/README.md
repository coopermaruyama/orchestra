# Orchestra Test Suite

This directory contains comprehensive tests for the Orchestra extension manager and task monitor system.

## Test Structure

### Core Test Files

- **`test_deviation_detection.py`** - Tests for the enhanced deviation detection system
  - Unit tests for scope creep, over-engineering, and off-topic detection
  - Tests for subagent simulation methods
  - Hook integration tests

- **`test_task_monitor_integration.py`** - Integration tests for task monitor functionality
  - Command line interface tests
  - End-to-end workflow tests
  - Progress tracking and requirement management tests

- **`test_orchestra.py`** - Tests for Orchestra extension management
  - Subagent installation tests
  - Template validation tests
  - Extension management functionality

### Test Utilities

- **`run_tests.py`** - Test runner script for executing all tests
- **`__init__.py`** - Test package initialization

## Running Tests

### Run All Tests
```bash
python3 tests/run_tests.py
```

### Run Specific Test Module
```bash
python3 tests/run_tests.py test_deviation_detection
```

### Using pytest (if available)
```bash
pytest tests/
```

### Using unittest directly
```bash
python3 -m unittest discover tests/
```

## Test Coverage

The test suite covers:

### Deviation Detection System
- ✅ Scope creep detection (enhancement work before core completion)
- ✅ Over-engineering detection (premature complexity and patterns) 
- ✅ Off-topic detection (unrelated work)
- ✅ Progress-based severity adjustment
- ✅ Fallback detection for when subagents aren't available

### Task Monitor Integration
- ✅ Task initialization and persistence
- ✅ Progress calculation and tracking
- ✅ Requirement completion management
- ✅ Hook system integration (pre-command, post-command, etc.)
- ✅ Command line interface functionality

### Orchestra Extension Management
- ✅ Subagent template installation
- ✅ Extension file management
- ✅ Configuration generation

### End-to-End Workflows
- ✅ Complete bug fix workflow simulation
- ✅ Command validation and blocking/warning behavior
- ✅ Progress tracking through task completion

## Test Philosophy

These tests are based on the manual testing performed during the refactoring from simple string matching to intelligent subagent-based deviation detection. They validate that:

1. **Enhanced Detection Works**: The new subagent-based system detects deviations more intelligently than simple pattern matching
2. **Graduated Responses**: The system provides warnings vs. blocks based on severity
3. **Context Awareness**: Detection considers task progress, requirement priorities, and semantic relevance
4. **Backward Compatibility**: The system still works when subagents aren't available (fallback mode)

## Test Data

Tests use realistic scenarios based on common development tasks:
- Bug fix workflows
- Feature development scenarios  
- Refactoring and optimization work
- Documentation and testing tasks

Each test validates both positive cases (valid work is allowed) and negative cases (deviations are caught).

## Dependencies

Core tests only require Python standard library. Some tests may be skipped if optional dependencies aren't available:
- `rich` - Required for Orchestra extension management tests