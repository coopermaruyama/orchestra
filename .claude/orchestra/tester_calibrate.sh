#!/bin/bash
# Tester Calibration Script for Orchestra

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRA_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Calibrating Tester extension for Orchestra project..."

# Create calibration data directory
CALIBRATION_DIR="$SCRIPT_DIR/.tester"
mkdir -p "$CALIBRATION_DIR"

# Generate calibration configuration
cat > "$CALIBRATION_DIR/calibration.json" <<'EOF'
{
    "project_type": "python",
    "test_framework": "pytest",
    "test_patterns": {
        "unit": "tests/unit/test_*.py",
        "integration": "tests/integration/test_*.py",
        "e2e": "tests/e2e/test_*.py"
    },
    "coverage_config": {
        "source": ["src/orchestra"],
        "omit": ["*/tests/*", "*/__pycache__/*"],
        "min_coverage": 80
    },
    "test_commands": {
        "unit": "uv run pytest tests/unit -v",
        "integration": "uv run pytest tests/integration -v",
        "e2e": "uv run pytest tests/e2e -v",
        "all": "uv run pytest -v",
        "coverage": "uv run pytest --cov=orchestra --cov-report=term-missing"
    },
    "code_quality": {
        "formatter": "black",
        "linter": "ruff",
        "type_checker": "mypy",
        "commands": {
            "format": "uv run black .",
            "lint": "uv run ruff check .",
            "typecheck": "uv run mypy src/"
        }
    },
    "markers": [
        "unit",
        "integration",
        "slow",
        "deviation_detection"
    ]
}
EOF

# Create test runner helper
cat > "$CALIBRATION_DIR/run_tests.sh" <<'EOF'
#!/bin/bash
# Test runner helper for Orchestra

ORCHESTRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ORCHESTRA_DIR"

COMMAND="${1:-all}"

case "$COMMAND" in
    unit)
        echo "Running unit tests..."
        uv run pytest tests/unit -v
        ;;
    integration)
        echo "Running integration tests..."
        uv run pytest tests/integration -v
        ;;
    e2e)
        echo "Running e2e tests..."
        uv run pytest tests/e2e -v
        ;;
    coverage)
        echo "Running tests with coverage..."
        uv run pytest --cov=orchestra --cov-report=term-missing
        ;;
    quick)
        echo "Running quick unit tests..."
        uv run pytest tests/unit -v -m "not slow"
        ;;
    all)
        echo "Running all tests..."
        uv run pytest -v
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available commands: unit, integration, e2e, coverage, quick, all"
        exit 1
        ;;
esac
EOF

chmod +x "$CALIBRATION_DIR/run_tests.sh"

# Create tester configuration
cat > "$SCRIPT_DIR/tester.json" <<EOF
{
    "enabled": true,
    "calibrated": true,
    "calibration_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "project_root": "$ORCHESTRA_DIR",
    "calibration_dir": "$CALIBRATION_DIR",
    "test_runner": "$CALIBRATION_DIR/run_tests.sh"
}
EOF

echo ""
echo "✅ Tester calibration complete!"
echo ""
echo "Calibration files created:"
echo "  - $CALIBRATION_DIR/calibration.json"
echo "  - $CALIBRATION_DIR/run_tests.sh"
echo ""
echo "You can now run tests using:"
echo "  $CALIBRATION_DIR/run_tests.sh [unit|integration|e2e|coverage|quick|all]"
echo ""
