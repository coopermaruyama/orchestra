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
