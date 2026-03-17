# Build Instructions

## Using Buildx Bake (Recommended)
This uses the dedicated BuildKit driver and handles advanced features like cache mounts natively.
```bash
docker buildx bake -f docker-compose.yml
```

## Using Docker Compose (v2+)
Modern Docker Compose uses BuildKit by default.
```bash
docker compose build
```

## Using Docker Compose (Legacy/v1)
Force BuildKit execution:
```bash
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose build
```
