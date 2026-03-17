# Use vllm image as base because it includes optimized vLLM, Torch, and CUDA dependencies.
# Base image must provide StructuredOutputsParams (vLLM >= 0.12).
FROM vllm/vllm-openai:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (curl for healthcheck, git for pip git dependencies if any)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ffmpeg \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt

# Install python dependencies
# We use --mount=type=cache to speed up re-installs
# We rely on the base image's torch, transformers, and vllm. 
# pip will skip installing them if the versions in the base image satisfy the constraints of requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code to /app/backend to preserve package structure
COPY *.py /app/
COPY services/ /app/services/
COPY shared/ /app/shared/
COPY backend/ /app/backend/

# Set PYTHONPATH to include /app so we can import backend.xxx, AND /app/backend for direct imports
ENV PYTHONPATH=/app:/app/backend

# Expose API port
EXPOSE 8000

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Reset ENTRYPOINT to ensure our CMD runs
ENTRYPOINT []

# Run FastAPI from /app, invoking backend.main
# We use 'backend.main:app' so uvicorn finds it in the backend package
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
