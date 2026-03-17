#!/bin/bash
# automigrate.sh
# Separated script to run Piccolo ORM database migrations natively via uv.
# Usage: ./automigrate.sh
# Can be run locally or invoked if needed on a deployment stage.

echo "Running Piccolo migrations..."

# Ensure we're running in the etl/ directory relative to this script
cd "$(dirname "$0")/etl" || exit 1

# Setup environment variables for Piccolo
export PICCOLO_CONF="piccolo_conf"

# The original command that was removed from the startup process:
uv run piccolo migrations forwards all

echo "Migrations completed successfully."
