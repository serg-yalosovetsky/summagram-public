#!/bin/bash

# Summagram Frontend Test Runner Script

# Default to "all" if no argument provided
TEST_TYPE=${1:-all}

# Directory where the frontend is located
FRONTEND_DIR="v0"

echo "Running Summagram frontend tests: $TEST_TYPE"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Error: Directory $FRONTEND_DIR not found."
    exit 1
fi

cd "$FRONTEND_DIR" || exit 1

EXIT_CODE=0

case $TEST_TYPE in
  unit)
    echo "---------------------------------------------------"
    echo "Executing Unit Tests (Jest)"
    echo "---------------------------------------------------"
    npm test || EXIT_CODE=1
    ;;
  integration)
    echo "---------------------------------------------------"
    echo "Executing Integration Tests (Playwright)"
    echo "---------------------------------------------------"
    npm run test:integration || EXIT_CODE=1
    ;;
  all)
    echo "---------------------------------------------------"
    echo "Executing Unit Tests (Jest)"
    echo "---------------------------------------------------"
    npm test || EXIT_CODE=1
    
    echo "---------------------------------------------------"
    echo "Executing Integration Tests (Playwright)"
    echo "---------------------------------------------------"
    npm run test:integration || EXIT_CODE=1
    ;;
  *)
    echo "Usage: $0 {unit|integration|all}"
    exit 1
    ;;
esac

exit $EXIT_CODE
