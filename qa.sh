#!/bin/bash
set -e

# Make sure we are in the project root
cd "$(dirname "$0")"

echo "============================================="
echo "        Summagram Quality Assurance          "
echo "============================================="

# 1. Auto format code
echo -e "\n[1/4] Auto-formatting code (ruff)..."
uv run ruff format . --exclude .venv,postgres_data,chroma_data,storage,frontend,v0,node_modules || true

# 2. Auto fix imports and unused variables
echo -e "\n[2/4] Auto-fixing imports and lint issues (ruff)..."
# --fix applies safe fixes like removing unused imports and variables
uv run ruff check . --fix --exclude .venv,postgres_data,chroma_data,storage,frontend,v0,node_modules || true

# 3. Find unused code using Vulture
echo -e "\n[3/4] Finding unused code (vulture)..."
# Check if vulture is available
if ! uv run python -c "import vulture" &> /dev/null; then
    echo "Installing vulture into dev dependencies..."
    uv add --dev vulture
fi

# Run vulture. We exclude common non-python or generated directories.
# || true ensures the script doesn't stop if vulture finds dead code.
uv run vulture . --exclude .venv,frontend,v0,node_modules,chroma_data,postgres_data,.git --min-confidence 80 || true

# 4. Check code test coverage
echo -e "\n[4/4] Checking test coverage (pytest + coverage)..."
export PYTHONPATH="$(pwd)"

# Run pytest with coverage for both main test directories
uv run pytest --cov=. --cov-report=term --cov-report=html etl/tests backend/tests || true

echo -e "\n============================================="
echo "✅ QA Checks Completed!"
echo "To view detailed coverage report, run:"
echo "open htmlcov/index.html   (or xdg-open htmlcov/index.html)"
echo "============================================="
