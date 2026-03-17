#!/bin/bash
echo "Starting Summagram with docker compose..."

# Prevent port conflicts by cleaning up beforehand
./stop.sh

docker rm -f summagram_sglang_text summagram_sglang_vision summagram_whisper_server 2>/dev/null || true
docker compose -p summagram --profile models up -d --no-start sglang_text sglang_vision whisper_server
docker compose -p summagram up --build --remove-orphans
