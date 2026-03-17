#!/bin/bash

# Summagram Test Runner Script

# Default to "all" if no argument provided
TEST_TYPE=${1:-all}

echo "Running Summagram tests: $TEST_TYPE"

run_pytest() {
    local dir=$1
    local marker=$2
    echo "---------------------------------------------------"
    echo "Executing tests in: $dir (marker: $marker)"
    echo "---------------------------------------------------"
    if [ -d "$dir" ]; then
        # Run pytest inside the directory to ensure conftest.py isolation works
        # Set PYTHONPATH to the root directory so modules like 'shared' are found
        local root_dir=$(pwd)
        (cd "$dir" && PYTHONPATH="$root_dir" uv run pytest -v -m "$marker")
        return $?
    else
        echo "Directory $dir not found, skipping."
        return 0
    fi
}

EXIT_CODE=0

case $TEST_TYPE in
  unit)
    run_pytest "etl" "unit" || EXIT_CODE=1
    # run_pytest "backend" "unit" || EXIT_CODE=1
    ;;
  integration)
    run_pytest "etl" "integration" || EXIT_CODE=1
    run_pytest "backend" "integration" || EXIT_CODE=1
    ;;
  all)
    run_pytest "etl" "unit or integration" || EXIT_CODE=1
    run_pytest "backend" "unit or integration" || EXIT_CODE=1
    ;;
  *)
    echo "Usage: $0 {unit|integration|all}"
    exit 1
    ;;
esac

exit $EXIT_CODE
