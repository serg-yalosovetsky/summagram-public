#!/bin/bash
echo "Stopping Summagram..."
docker compose -p summagram --profile models down --remove-orphans
# Clean up any containers from the old 'summagram' project name
docker compose -p summagram --profile models down --remove-orphans 2>/dev/null || true
# Force remove specifically matched lingering containers if compose down misses them
docker rm -f summagram-postgres-1 summagram-etl-1 summagram-backend-1 summagram-chroma-1 summagram-jaeger-1 summagram-model-orchestrator-1 2>/dev/null || true
echo "Summagram stopped."
